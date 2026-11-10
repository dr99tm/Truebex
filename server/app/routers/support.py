"""The support API (`/internal/support`): server-to-server gates the Truebex Desk
(a Cloudflare Worker) calls when a customer signs in, signs up or asks about
their account from a chat. Hidden from the schema; the contract, with a worked
signing example, is docs/support-api.md.

* Off unless SUPPORT_SERVICE_SECRET is set: then every route answers 404 (as
  the marketplace's Stripe webhook does).
* Every request is signed the Standard Webhooks way with `webhooks/signing.py`
  `verify`: `webhook-id`, `webhook-timestamp` (5 minutes' tolerance) and
  `webhook-signature: v1,<base64 HMAC-SHA256>`. The signed body is the request
  line and the body, `<METHOD> <path>[?<query>]\\n<body>`, so the signature of
  a GET or DELETE (no body) names its account and device. An id is accepted
  once (kept 24 h in `idempotency_keys`): a retry is signed again with a new id.
* Rate limits are per address and per contact (`contact_hash`, the Desk's hash
  of the chat contact), never per IP: every Desk call leaves from Cloudflare.
* Account data is answered here for an account id the Desk learned from one of
  these gates (an e-mail code, a password or an approved link), never a session.
* Every call writes one audit line (logger `truebex.support`): the route, the
  Desk's request id, the contact hash's first 12 characters, the account and
  the outcome. Never a code, password, poll secret, verification id or signature.
"""

import base64
import binascii
import hashlib
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from .. import ratelimit
from ..analysis import results as analysis_results
from ..config import get_settings
from ..contract_http import ContractError, enveloped, request_id
from ..database import SessionLocal, get_db
from ..idempotency import IdempotencyKey
from ..licence import clock, devices, links
from ..licence import service as licence_service
from ..licence.models import Device
from ..models import ApiKey, Payment, User
from ..releases import service as release_service
from ..render import service as render_service
from ..render import tiles
from ..schemas import ApiKeyOut
from ..security import hash_password, verify_password
from ..sso import service as sso
from ..storage import get_store
from ..support import codes
from ..webhooks.signing import SECRET_PREFIX, SignatureError, verify
from . import auth as auth_router
from . import billing as billing_router

log = logging.getLogger("truebex.support")

CONTACT_HASH = r"^[0-9a-f]{64}$"
_MSG_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
# The replay store's row (idempotency_keys): one per accepted webhook-id.
_REPLAY_ACCOUNT = "support"
_REPLAY_ROUTE = "support:webhook-id"

# Rate limits: (bucket, per hour, burst). docs/support-api.md lists them.
LIMITS = {
    "code.email": (5, 5),
    "code.contact": (10, 10),
    "code.all": (300, 60),
    "verify.email": (10, 10),
    "verify.contact": (20, 20),
    "register.email": (5, 5),
    "register.contact": (10, 10),
    "login.email": (10, 10),
    "login.contact": (20, 20),
    "link.contact": (10, 10),
}

ANALYSIS_KINDS = ("wind", "energy", "acoustics", "airflow")
JOBS_SHOWN = 10
PAYMENTS_SHOWN = 5
REPORT_URL_TTL_S = 3600
LINK_CHANNELS = {"whatsapp": "WhatsApp", "email": "Email"}


# --- signing, replay, audit -----------------------------------------------------------


@dataclass
class SupportCall:
    msg_id: str
    action: str
    user_id: int | None = None
    contact: str | None = None


def signed_content(method: str, path: str, query: str, body: bytes) -> bytes:
    """What the HMAC covers after `<id>.<timestamp>.`: the request line and the body."""
    target = f"{path}?{query}" if query else path
    return f"{method.upper()} {target}\n".encode("utf-8") + body


def _secrets() -> list[str]:
    return [s.strip() for s in get_settings().support_service_secret.split(",") if s.strip()]


MIN_SECRET_BYTES = 24


def _usable(secret: str) -> bool:
    """`whsec_` + strict base64 of at least 24 bytes (32 are made)."""
    try:
        key = base64.b64decode(secret.removeprefix(SECRET_PREFIX), validate=True)
    except (ValueError, binascii.Error):
        return False
    return secret.startswith(SECRET_PREFIX) and len(key) >= MIN_SECRET_BYTES


def _verified(configured: list[str], headers, content: bytes) -> bool:
    usable = [s for s in configured if _usable(s)]
    if len(usable) < len(configured):
        log.error("SUPPORT_SERVICE_SECRET holds a value that is not whsec_<base64 of 24+ bytes>; it is ignored")
    if not usable:
        raise ContractError("unavailable", 503, "The support API is not set up correctly on this server.")
    for secret in usable:
        try:
            verify(secret, headers, content)
            return True
        except SignatureError:
            continue
    return False


def _first_use(msg_id: str, content: bytes) -> bool:
    """Record `msg_id`; False when it was seen before (a replay)."""
    with SessionLocal() as db:
        db.add(
            IdempotencyKey(
                key=hashlib.sha256(msg_id.encode("utf-8")).hexdigest()[:32],
                account=_REPLAY_ACCOUNT,
                route=_REPLAY_ROUTE,
                body_sha256=hashlib.sha256(content).hexdigest(),
                status=200,
                response=None,
                created_at=clock.now(),
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return False
    return True


def _refused(request: Request, msg_id: str | None, outcome: str) -> None:
    log.warning(
        "support %s %s by desk msg=%s -> refused %s (request %s)",
        request.method, request.url.path, (msg_id or "-")[:64], outcome, request_id(request),
    )


def _route_path(request: Request) -> str:
    return getattr(request.scope.get("route"), "path", request.url.path)


async def signed_call(request: Request) -> AsyncIterator[SupportCall]:
    """Router dependency: 404 while unconfigured, 401 for a bad or repeated
    signature; then one audit line for the call, whatever it answers."""
    configured = _secrets()
    if not configured:
        raise ContractError("not_found", 404, "Not found.")
    msg_id = request.headers.get("webhook-id")
    if not msg_id or not _MSG_ID.fullmatch(msg_id):
        _refused(request, None, "invalid_signature")
        raise ContractError("invalid_signature", 401, "The request signature is missing, wrong or too old.")
    body = await request.body()
    content = signed_content(
        request.method, request.scope["path"], request.scope.get("query_string", b"").decode("latin-1"), body
    )
    if not _verified(configured, request.headers, content):
        _refused(request, msg_id, "invalid_signature")
        raise ContractError("invalid_signature", 401, "The request signature is missing, wrong or too old.")
    if not await run_in_threadpool(_first_use, msg_id, content):
        _refused(request, msg_id, "replayed_request")
        raise ContractError(
            "replayed_request", 401, "This webhook-id was already used. Sign every request with a new id."
        )
    call = SupportCall(msg_id=msg_id[:64], action=f"{request.method} {_route_path(request)}")
    raw_user = request.path_params.get("user_id")
    if raw_user is not None and str(raw_user).isdigit():
        call.user_id = int(raw_user)
    contact = request.query_params.get("contact_hash")
    if contact and re.fullmatch(CONTACT_HASH, contact):
        call.contact = contact[:12]
    outcome = "ok"
    try:
        yield call
    except ContractError as exc:
        outcome = exc.code
        raise
    except HTTPException as exc:
        outcome = f"http_{exc.status_code}"
        raise
    except RequestValidationError:
        outcome = "validation_failed"
        raise
    except Exception:
        outcome = "error"
        raise
    finally:
        log.info(
            "support %s by desk msg=%s contact=%s user=%s -> %s (request %s)",
            call.action, call.msg_id, call.contact or "-",
            call.user_id if call.user_id is not None else "-", outcome, request_id(request),
        )


router = APIRouter(
    prefix="/internal/support",
    tags=["support"],
    include_in_schema=False,
    dependencies=[enveloped(), Depends(signed_call)],
)


def _limit(name: str, key: str) -> None:
    per_hour, burst = LIMITS[name]
    ratelimit.check(f"support.{name}:{key}", per_minute=per_hour / 60.0, burst=burst)


def _email(raw: str) -> str:
    return str(raw).strip().lower()


def _contact(call: SupportCall, contact_hash: str | None) -> None:
    if contact_hash:
        call.contact = contact_hash[:12]


# --- request bodies ------------------------------------------------------------------------


class EmailCodeRequest(BaseModel):
    email: EmailStr
    contact_hash: str = Field(pattern=CONTACT_HASH)


class EmailCodeVerify(BaseModel):
    email: EmailStr
    code: str = Field(min_length=1, max_length=16)
    contact_hash: str | None = Field(default=None, pattern=CONTACT_HASH)


class RegisterRequest(BaseModel):
    verification_id: str = Field(min_length=16, max_length=128)
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=200)
    contact_hash: str | None = Field(default=None, pattern=CONTACT_HASH)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    contact_hash: str | None = Field(default=None, pattern=CONTACT_HASH)


class LinkStartRequest(BaseModel):
    contact_hash: str = Field(pattern=CONTACT_HASH)
    channel: Literal["whatsapp", "email"] = "whatsapp"
    # A masked hint of the chat the code was sent to ("+44 *** 0123"), shown on
    # the approval page so the customer can tell their own chat from a phisher's.
    contact_label: str | None = Field(default=None, max_length=20, pattern=r"^[0-9A-Za-z+*.@ -]{1,20}$")


class LinkPollRequest(BaseModel):
    poll_secret: str = Field(min_length=16, max_length=128)


# --- e-mail codes, sign-up, sign-in ----------------------------------------------------------


@router.post("/email-code", status_code=status.HTTP_202_ACCEPTED)
def send_email_code(
    body: EmailCodeRequest, call: SupportCall = Depends(signed_call), db: Session = Depends(get_db)
) -> dict:
    """Mail a one-time code. The same answer whether or not the address has an account."""
    email = _email(body.email)
    _contact(call, body.contact_hash)
    _limit("code.contact", body.contact_hash)
    _limit("code.email", email)
    _limit("code.all", "all")
    codes.send_code(db, email, body.contact_hash, clock.now())
    return {
        "status": "sent",
        "expires_in_s": int(codes.CODE_LIFETIME.total_seconds()),
        "code_length": 6,
    }


@router.post("/email-code/verify")
def verify_email_code(
    body: EmailCodeVerify, call: SupportCall = Depends(signed_call), db: Session = Depends(get_db)
) -> dict:
    """The code proves the address. An existing account is then signed in
    (`user_id`) unless its organisation requires SSO; a new address gets a
    verification id for /register."""
    email = _email(body.email)
    _contact(call, body.contact_hash)
    if body.contact_hash:
        _limit("verify.contact", body.contact_hash)
    _limit("verify.email", email)
    now = clock.now()
    verification_id = codes.check_code(db, email, body.code, body.contact_hash, now)
    user = db.scalar(select(User).where(User.email == email))
    required = sso.required_org(db, email)
    if user is not None:
        codes.mark_verified(db, user, now)
        call.user_id = user.id
    return {
        "verification_id": verification_id,
        "expires_in_s": int(codes.VERIFICATION_LIFETIME.total_seconds()),
        "exists": user is not None,
        "user_id": user.id if user is not None and required is None else None,
        "has_password": bool(user is not None and user.hashed_password),
        "google_linked": bool(user is not None and user.google_sub),
        "sso_required": required is not None,
        "org_name": required.name if required is not None else None,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest, call: SupportCall = Depends(signed_call), db: Session = Depends(get_db)
) -> dict:
    """A password account for an address a code verified; never for any other."""
    _contact(call, body.contact_hash)
    if body.contact_hash:
        _limit("register.contact", body.contact_hash)
    now = clock.now()
    row = codes.find_verification(db, body.verification_id, now)
    _limit("register.email", row.email)
    # Spent first: one verification makes at most one account, whatever follows.
    codes.spend_verification(db, row, now)
    name = (body.name or "").strip() or None
    try:
        user = auth_router.create_account(db, row.email, body.password, name=name, email_verified_at=now)
    except auth_router.EmailTaken:
        raise ContractError(
            "account_exists", 409, "An account with this e-mail already exists. Sign in instead."
        )
    call.user_id = user.id
    return {"user_id": user.id, "email": user.email}


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Checked when the address has no account, so both answers take as long."""
    return hash_password("support-api: no such account")


def _use_link(reason: str, detail: str, **data) -> ContractError:
    return ContractError("use_link_sign_in", 403, detail, {"reason": reason, **data})


@router.post("/login")
def login(body: LoginRequest, call: SupportCall = Depends(signed_call), db: Session = Depends(get_db)) -> dict:
    """Email and password. Accounts without a password (Google or SSO) and
    domains that require SSO get 403 `use_link_sign_in`."""
    email = _email(body.email)
    _contact(call, body.contact_hash)
    if body.contact_hash:
        _limit("login.contact", body.contact_hash)
    _limit("login.email", email)
    required = sso.required_org(db, email)
    if required is not None:
        raise _use_link(
            "sso_required",
            f"{required.name} signs in with single sign-on, not a password. Use the sign-in link instead.",
            org_name=required.name,
            google_linked=False,
        )
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and not user.hashed_password:
        raise _use_link(
            "no_password",
            "This account has no password: it signs in with Google or single sign-on. Use the sign-in link instead.",
            org_name=None,
            google_linked=user.google_sub is not None,
        )
    ok = verify_password(body.password, user.hashed_password if user is not None else _dummy_hash())
    if user is None or not ok:
        raise ContractError("invalid_credentials", 401, "Incorrect email or password.")
    call.user_id = user.id
    return {"user_id": user.id}


@router.post("/link/start", status_code=status.HTTP_201_CREATED)
def start_link(
    body: LinkStartRequest, call: SupportCall = Depends(signed_call), db: Session = Depends(get_db)
) -> dict:
    """A link code the customer approves on truebex.com/dashboard/link/ while
    signed in there (any way: password, Google, SSO)."""
    _contact(call, body.contact_hash)
    _limit("link.contact", body.contact_hash)
    # The approval page shows "<device_name> · <app_version>": "Truebex support · WhatsApp +44 *** 0123".
    shown = LINK_CHANNELS[body.channel] + (f" {body.contact_label.strip()}" if body.contact_label else "")
    row, secret = links.start(
        db,
        device_name="Truebex support",
        fingerprint=body.contact_hash,
        app_version=shown[:32],
        now=clock.now(),
        purpose="support",
    )
    return {
        "link_code": row.link_code,
        "verify_url": links.verify_url(row.link_code),
        "poll_secret": secret,
        "expires_in_s": int(links.LIFETIME.total_seconds()),
        "interval_s": links.INTERVAL_S,
    }


@router.post("/link/poll")
def poll_link(body: LinkPollRequest, call: SupportCall = Depends(signed_call), db: Session = Depends(get_db)) -> dict:
    """pending, then (once) approved with the account id. Never a session."""
    out = links.poll_account(db, body.poll_secret, clock.now())
    call.user_id = out["user_id"]
    return out


# --- account data --------------------------------------------------------------------------


def _user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ContractError("not_found", 404, "There is no account with this id.")
    return user


def _latest_release(db: Session) -> dict | None:
    feed = release_service.feed(db, "stable", "win64")
    if not feed["releases"]:
        return None
    manifest = feed["releases"][0]["manifest"]
    installer = manifest["installer"]
    return {
        "version": manifest["version"],
        "channel": manifest["channel"],
        "platform": manifest["platform"],
        "published_at": manifest["published_at"],
        "mandatory": bool(manifest.get("mandatory")),
        "file": installer["file"],
        "bytes": installer["bytes"],
        "sha256": installer["sha256"],
        "notes_url": manifest.get("notes_url"),
        # The page, never the counted download endpoint.
        "download_page_url": f"{get_settings().site_url.rstrip('/')}/download/",
    }


def _report_url(db: Session, user: User, record: dict) -> str | None:
    """A 1 h link to an analysis job's report PDF, when its result names one."""
    if not record.get("output_ready"):
        return None
    job = render_service.own_job(db, user, record["job_id"])
    try:
        data = tiles.read_json(job.output_key) if job.output_key else None
    except Exception:  # noqa: BLE001  (storage hiccup: the summary still answers)
        log.warning("support summary: job %s output unreadable", job.job_id)
        return None
    if not data or not analysis_results.handles_output(data) or not data.get("report"):
        return None
    source = job.output_key.rsplit("/", 1)[0]
    return get_store().signed_get_url(
        f"{source}/files/{data['report']}", expires_in=REPORT_URL_TTL_S, filename="report.pdf"
    )


def _analysis_jobs(db: Session, user: User) -> list[dict]:
    records: list[dict] = []
    for kind in ANALYSIS_KINDS:
        records += render_service.list_jobs(
            db, user, project_id=None, kind=kind, state=None, cursor=None, limit=JOBS_SHOWN
        )["jobs"]
    records.sort(key=lambda r: (r["created_at"] or "", r["job_id"]), reverse=True)
    keep = ("job_id", "kind", "state", "project_id", "created_at", "finished_at", "progress", "message", "error")
    return [{**{k: r.get(k) for k in keep}, "report_pdf_url": _report_url(db, user, r)} for r in records[:JOBS_SHOWN]]


@router.get("/users/{user_id}/summary")
def summary(
    user_id: int = Path(ge=1),
    contact_hash: str | None = Query(default=None, pattern=CONTACT_HASH),
    db: Session = Depends(get_db),
) -> dict:
    """What the Desk shows a signed-in customer: plan, trial, seats, devices,
    subscription, payments, API keys (never secrets), the latest release and
    analysis reports."""
    user = _user(db, user_id)
    subscription = billing_router._subscription_out(db, user)  # expires a lapsed plan first
    panel = licence_service.account_panel(db, user, None)
    active = devices.active(db, user.id)
    payments = list(
        db.scalars(
            select(Payment)
            .where(Payment.user_id == user.id, Payment.organisation_id.is_(None))
            .order_by(Payment.created_at.desc())
            .limit(PAYMENTS_SHOWN)
        )
    )
    keys = db.scalars(
        select(ApiKey)
        .where(ApiKey.user_id == user.id, ApiKey.supplier_id.is_(None))
        .order_by(ApiKey.revoked_at.is_not(None), ApiKey.created_at.desc())
    )
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "created_at": clock.rfc3339(user.created_at),
            "has_password": bool(user.hashed_password),
            "google_linked": user.google_sub is not None,
            "email_verified_at": clock.rfc3339(user.email_verified_at),
        },
        "plan": panel["plan"],
        "plan_name": panel["plan_name"],
        "trial": panel["trial"],
        "seat": panel["seat"],
        "seats": panel["seats"],
        "devices": {
            "active": [devices.device_json(d) for d in active],
            "count": len(active),
            "limit": panel["devices"]["limit"],
        },
        "subscription": subscription.model_dump(mode="json"),
        "payments": [p.model_dump(mode="json") for p in billing_router._payments_out(db, payments)],
        "api_keys": [ApiKeyOut.model_validate(k).model_dump(mode="json") for k in keys],
        "release": _latest_release(db),
        "analysis_jobs": _analysis_jobs(db, user),
        "report_urls_expire_in_s": REPORT_URL_TTL_S,
        "manage_url": panel["manage_url"],
    }


@router.get("/users/{user_id}/invoices")
def invoices(
    user_id: int = Path(ge=1),
    contact_hash: str | None = Query(default=None, pattern=CONTACT_HASH),
    db: Session = Depends(get_db),
) -> dict:
    """The account's own invoices with absolute PDF links, valid 1 h."""
    user = _user(db, user_id)
    try:
        rows = billing_router.invoice_list(db, user, None)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_502_BAD_GATEWAY:
            raise
        raise ContractError("upstream_failed", 502, "The payment provider did not answer. Try again in a minute.")
    base = get_settings().api_url.rstrip("/")
    out = []
    for inv in rows:
        item = inv.model_dump(mode="json")
        if item["pdf_url"] and item["pdf_url"].startswith("/"):
            item["pdf_url"] = base + item["pdf_url"]
        out.append(item)
    return {"invoices": out, "pdf_links_expire_in_s": billing_router.PDF_LINK_TTL_S}


@router.delete("/users/{user_id}/devices/{device_id}")
def remove_device(
    user_id: int = Path(ge=1),
    device_id: str = Path(min_length=1, max_length=32),
    contact_hash: str | None = Query(default=None, pattern=CONTACT_HASH),
    db: Session = Depends(get_db),
) -> dict:
    """Sign a computer out of the account: its slot is freed and its token stops working."""
    user = _user(db, user_id)
    device = db.scalar(select(Device).where(Device.device_id == device_id, Device.user_id == user.id))
    if device is None:
        raise ContractError("not_found", 404, "That device is not on this account.")
    removed = devices.deactivate(db, device, "removed", clock.now())
    db.commit()
    out = devices.device_json(device)
    out["deactivated_at"] = clock.rfc3339(device.deactivated_at)
    out["removed"] = removed
    return out
