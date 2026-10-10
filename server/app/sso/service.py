"""SSO connections, sign-in routing, just-in-time membership and the
"SSO required" policy.

* One connection per organisation (`oidc` or `saml`); client secrets are
  sealed and never returned.
* `/auth/sso/start?email=` finds the organisation that verified the e-mail's
  domain and has an enabled connection, then hands over to OIDC or SAML.
* A verified sign-in signs the person in: an existing account with that
  address is used (the domain is verified for this organisation, the gap
  Google sign-in closes with `email_verified`), else one is created; the
  person joins the organisation as a member just in time.
* SSO required: password and Google sign-in are refused for the
  organisation's verified domains; owners keep a one-time break-glass code.
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock
from ..licence.ids import uuid7_hex
from ..models import User
from ..orgs import audit
from ..orgs import service as orgs
from ..orgs.models import Organisation
from ..security import create_access_token
from . import crypto, domains, oidc, saml
from .models import SsoAssertionSeen, SsoConnection, SsoRequest

REQUEST_TTL = timedelta(minutes=10)
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_next(next_: str | None) -> str:
    """Same-site relative paths only (no open redirect), as the site's safeNext."""
    if next_ and next_.startswith("/") and not next_.startswith("//") and "\\" not in next_ and len(next_) <= 500:
        return next_
    return "/dashboard/"


# --- connection settings ------------------------------------------------------------


def connection(db: Session, org_id: str) -> SsoConnection | None:
    return db.get(SsoConnection, org_id)


def sp_info(org: Organisation) -> dict:
    return {
        "oidc_redirect_uri": oidc.redirect_uri(),
        "saml_entity_id": saml.sp_entity_id(org),
        "saml_acs_url": saml.acs_url(org),
        "saml_metadata_url": saml.metadata_url(org),
    }


def connection_json(db: Session, org: Organisation) -> dict:
    conn = connection(db, org.id)
    out = {
        "configured": conn is not None,
        "kind": conn.kind if conn else None,
        "enabled": bool(conn.enabled) if conn else False,
        "required": bool(org.sso_required),
        "issuer": conn.issuer if conn else None,
        "client_id": conn.client_id if conn else None,
        "has_client_secret": bool(conn and conn.client_secret_enc),
        "idp_entity_id": conn.idp_entity_id if conn else None,
        "idp_sso_url": conn.idp_sso_url if conn else None,
        "idp_cert_sha256": None,
        "has_break_glass_code": org.break_glass_hash is not None,
        "sp": sp_info(org),
        "domains": [domains.domain_json(d) for d in domains.list_for(db, org)],
    }
    if conn and conn.idp_cert_pem:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes

        cert = x509.load_pem_x509_certificate(conn.idp_cert_pem.encode("ascii"))
        out["idp_cert_sha256"] = cert.fingerprint(hashes.SHA256()).hex(":").upper()
    return out


def _field_error(field: str, message: str) -> ContractError:
    return ContractError(
        "validation_failed", 422, f"{field}: {message}",
        {"fields": [{"field": field, "in": "body", "message": message}]},
    )


def new_break_glass(db: Session, org: Organisation, actor: int, now: datetime) -> str:
    """A fresh one-time code for owners (the old one stops working); shown once."""
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(20))
    code = "-".join(raw[i:i + 5] for i in range(0, 20, 5))
    org.break_glass_hash = _hash(raw)
    db.add(org)
    audit.record(db, org.id, "sso.break_glass_created", actor=actor, target_kind="org", target_id=org.id, at=now)
    db.commit()
    return code


def save(db: Session, org: Organisation, actor: int, body, now: datetime) -> dict:
    """PUT /orgs/{id}/sso. Returns the connection JSON (plus a break-glass
    code, once, when the policy first turns on)."""
    conn = connection(db, org.id) or SsoConnection(org_id=org.id, kind=body.kind)
    if body.kind == "oidc":
        issuer = oidc.normalise_issuer(body.issuer or "")
        if not issuer or not oidc.issuer_is_acceptable(issuer):
            raise _field_error("issuer", "an https URL (or http://127.0.0.1 for a local test provider)")
        if not body.client_id:
            raise _field_error("client_id", "required for OIDC")
        if not body.client_secret and not (conn.kind == "oidc" and conn.client_secret_enc):
            raise _field_error("client_secret", "required for OIDC")
        conn.issuer, conn.client_id = issuer, body.client_id
        if body.client_secret:
            conn.client_secret_enc = crypto.seal(body.client_secret)
        conn.idp_entity_id = conn.idp_sso_url = conn.idp_cert_pem = None
    else:
        if body.idp_metadata_xml:
            idp = saml.parse_idp_metadata(body.idp_metadata_xml)
            entity, sso_url, cert = idp.entity_id, idp.sso_url, idp.cert_pem
        elif body.idp_entity_id and body.idp_sso_url and body.idp_cert_pem:
            try:
                cert = saml.cert_pem_from_text(body.idp_cert_pem)
            except (ValueError, TypeError):
                raise _field_error("idp_cert_pem", "the certificate does not load")
            entity, sso_url = body.idp_entity_id, body.idp_sso_url
        elif conn.kind == "saml" and conn.idp_cert_pem:
            entity, sso_url, cert = conn.idp_entity_id, conn.idp_sso_url, conn.idp_cert_pem
        else:
            raise _field_error("idp_metadata_xml", "paste your identity provider's SAML metadata")
        if not entity or not (sso_url or "").startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise _field_error("idp_metadata_xml", "the metadata needs an entityID and an https sign-in URL")
        conn.idp_entity_id, conn.idp_sso_url, conn.idp_cert_pem = entity, sso_url, cert
        conn.issuer = conn.client_id = conn.client_secret_enc = None
    conn.kind = body.kind
    conn.enabled = body.enabled
    db.add(conn)
    audit.record(
        db, org.id, "sso.configured", actor=actor, target_kind="org", target_id=org.id, at=now,
        protocol=conn.kind, enabled=conn.enabled, issuer=conn.issuer or conn.idp_entity_id,
    )
    code = None
    if body.required != bool(org.sso_required):
        if body.required:
            if not conn.enabled or not any(d.verified_at for d in domains.list_for(db, org)):
                db.rollback()
                raise ContractError(
                    "sso_not_ready", 409,
                    "Verify at least one e-mail domain and enable the connection before requiring SSO.",
                )
        org.sso_required = body.required
        db.add(org)
        audit.record(
            db, org.id, "sso.policy_changed", actor=actor, target_kind="org", target_id=org.id, at=now,
            required=body.required,
        )
    db.commit()
    if org.sso_required and org.break_glass_hash is None:
        code = new_break_glass(db, org, actor, now)
    out = connection_json(db, org)
    if code:
        out["break_glass_code"] = code
    return out


def remove(db: Session, org: Organisation, actor: int, now: datetime) -> None:
    db.execute(delete(SsoConnection).where(SsoConnection.org_id == org.id))
    org.sso_required = False
    db.add(org)
    audit.record(db, org.id, "sso.removed", actor=actor, target_kind="org", target_id=org.id, at=now)
    db.commit()


# --- sign-in routing ----------------------------------------------------------------


def _routable(db: Session, email: str) -> tuple[Organisation, SsoConnection] | None:
    org = domains.verified_owner(db, email)
    if org is None:
        return None
    conn = connection(db, org.id)
    if conn is None or not conn.enabled:
        return None
    return org, conn


def _new_request(db: Session, org: Organisation, now: datetime, next_: str, login_hint: str | None, **fields) -> str:
    state = secrets.token_urlsafe(32)
    db.add(
        SsoRequest(
            id=uuid7_hex(),
            org_id=org.id,
            state=_hash(state),
            next=safe_next(next_),
            login_hint=login_hint,
            created_at=now,
            expires_at=now + REQUEST_TTL,
            **fields,
        )
    )
    db.commit()
    return state


def start(db: Session, email: str, next_: str | None, now: datetime) -> str:
    """The provider URL to send the browser to (404 when the domain has no SSO)."""
    email = (email or "").strip().lower()
    found = _routable(db, email) if "@" in email else None
    if found is None:
        raise ContractError("sso_not_found", 404, "Single sign-on is not set up for this e-mail domain.")
    org, conn = found
    if conn.kind == "oidc":
        verifier, challenge = oidc.pkce_pair()
        nonce = secrets.token_urlsafe(24)
        url_args = dict(issuer=conn.issuer, client_id=conn.client_id)
        oidc.discover(conn.issuer)  # fail before storing anything when the provider is down
        state = _new_request(db, org, now, next_, email, nonce=nonce, code_verifier=verifier)
        return oidc.authorize_url(**url_args, state=state, nonce=nonce, challenge=challenge, login_hint=email)
    request_id = saml.new_request_id()
    state = _new_request(db, org, now, next_, email, saml_request_id=request_id)
    return saml.authn_request_url(org, conn.idp_sso_url, request_id, state, now)


def _take_request(db: Session, row: SsoRequest | None, now: datetime) -> SsoRequest:
    if row is None or row.used_at is not None or now >= clock.aware(row.expires_at):
        raise ContractError("sso_failed", 401, "This sign-in has expired or was already used. Start again.")
    row.used_at = now
    db.add(row)
    db.commit()
    return row


def finish_oidc(db: Session, *, code: str, state: str, now: datetime) -> tuple[User, str]:
    row = _take_request(db, db.scalar(select(SsoRequest).where(SsoRequest.state == _hash(state or ""))), now)
    org = db.get(Organisation, row.org_id)
    conn = connection(db, row.org_id)
    if org is None or org.deleted_at is not None or conn is None or conn.kind != "oidc" or not conn.enabled:
        raise oidc.fail("Single sign-on is no longer set up for this organisation.")
    secret = crypto.unseal(conn.client_secret_enc)
    if not secret:
        raise oidc.fail("The organisation's SSO client secret must be entered again.")
    tokens = oidc.exchange_code(conn.issuer, conn.client_id, secret, code, row.code_verifier or "")
    claims = oidc.verify_id_token(
        conn.issuer, conn.client_id, tokens["id_token"], nonce=row.nonce or "", access_token=tokens.get("access_token")
    )
    user = sign_in(db, org, claims["email"], claims.get("name"), "oidc", now)
    return user, row.next


def finish_saml(db: Session, *, org_slug: str, saml_response: str, relay_state: str | None, now: datetime) -> tuple[User, str]:
    org = orgs.by_slug(db, org_slug)
    conn = connection(db, org.id) if org is not None else None
    if org is None or conn is None or conn.kind != "saml" or not conn.enabled:
        raise saml.fail("Single sign-on is not set up for this organisation.")
    assertion = saml.verify_response(
        org, saml_response_b64=saml_response, idp_entity_id=conn.idp_entity_id, cert_pem=conn.idp_cert_pem, now=now
    )
    row = db.scalar(
        select(SsoRequest).where(SsoRequest.saml_request_id == assertion.in_response_to, SsoRequest.org_id == org.id)
    )
    if row is not None and relay_state and _hash(relay_state) != row.state:
        raise saml.fail("The SAML response does not answer this sign-in (RelayState).")
    row = _take_request(db, row, now)
    db.add(SsoAssertionSeen(assertion_id=assertion.id[:256], expires_at=assertion.not_on_or_after + saml.SKEW))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise saml.fail("This SAML assertion was already used.")
    user = sign_in(db, org, assertion.email, assertion.name, "saml", now)
    return user, row.next


def assertion_seen(db: Session, assertion_id: str) -> bool:
    return db.get(SsoAssertionSeen, assertion_id) is not None


def sign_in(db: Session, org: Organisation, email: str, name: str | None, via: str, now: datetime) -> User:
    """Just-in-time: the account for a verified address, joined to the organisation."""
    email = email.strip().lower()
    if not domains.is_verified_for(db, org, email):
        raise ContractError(
            "sso_failed", 401, "Your identity provider signed in an address outside the organisation's verified domains."
        )
    user = db.scalar(select(User).where(User.email == email))
    created = user is None
    if created:
        user = User(email=email, hashed_password="", name=name or None)
        db.add(user)
        db.flush()
    elif name and not user.name:
        user.name = name
        db.add(user)
    orgs.add_member(db, org, user, "member", now, actor=user.id, via=f"sso.{via}")
    audit.record(
        db, org.id, "sso.signin", actor=user.id, target_kind="user", target_id=user.id, at=now,
        protocol=via, new_account=created,
    )
    db.commit()
    db.refresh(user)
    return user


def site_redirect(user: User, next_: str) -> str:
    """`/login/sso/` with the session in the fragment, which browsers never
    send to a server or write to access logs."""
    fragment = urlencode({"token": create_access_token(str(user.id)), "next": safe_next(next_)}, quote_via=quote)
    return f"{get_settings().site_url.rstrip('/')}/login/sso/#{fragment}"


# --- the "SSO required" policy ----------------------------------------------------------


def required_org(db: Session, email: str) -> Organisation | None:
    org = domains.verified_owner(db, email or "")
    if org is None or not org.sso_required:
        return None
    conn = connection(db, org.id)
    return org if conn is not None and conn.enabled else None


def use_sso(org: Organisation, status: int = 401) -> ContractError:
    return ContractError(
        "sso_required",
        status,
        f"{org.name} signs in with single sign-on. Choose Continue with SSO and enter your work e-mail.",
        {"org_name": org.name},
    )


def _normal_code(code: str) -> str:
    return re.sub(r"[\s-]", "", code or "").upper()


def use_break_glass(db: Session, org: Organisation, user: User, code: str, now: datetime) -> None:
    """An owner's one-time way in when the identity provider is down."""
    member = orgs.membership(db, org.id, user.id)
    ok = (
        member is not None
        and member.role == "owner"
        and org.break_glass_hash is not None
        and secrets.compare_digest(_hash(_normal_code(code)), org.break_glass_hash)
    )
    if not ok:
        audit.record(db, org.id, "sso.break_glass_refused", actor=user.id, target_kind="user", target_id=user.id, at=now)
        db.commit()
        raise ContractError("sso_required", 401, "That break-glass code is not valid. Each code works once.")
    org.break_glass_hash = None  # used up; an owner makes a new one on the SSO tab
    db.add(org)
    audit.record(db, org.id, "sso.break_glass_used", actor=user.id, target_kind="user", target_id=user.id, at=now)
    db.commit()


def purge(db: Session, now: datetime) -> int:
    """The sso.requests.purge job: used or expired requests, expired assertion ids."""
    gone = db.execute(
        delete(SsoRequest).where(or_(SsoRequest.used_at.is_not(None), SsoRequest.expires_at < now))
    ).rowcount or 0
    gone += db.execute(delete(SsoAssertionSeen).where(SsoAssertionSeen.expires_at < now)).rowcount or 0
    return gone
