"""The support API (`/internal/support`, routers/support.py): the Truebex Desk's
signed server-to-server gates. Signing and replay, 404 while unconfigured, no
account enumeration, one-time codes (expiry, tries, single use), sign-up only
after a verified address, the SSO and Google-only paths, link sign-in, the
summary and invoice shapes, device removal, rate limits, the audit line, the
purge job and the added columns. docs/support-api.md is the contract."""

import base64
import hashlib
import hmac
import io
import json
import logging
import re
import secrets
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session

from app import mail, tasks
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.idempotency import IdempotencyKey
from app.licence.ids import uuid7_hex
from app.licence.models import Device, LicenceEvent, LinkCode
from app.models import DownloadEvent, User
from app.render.models import RenderJob
from app.routers import support as support_router
from app.storage import get_store
from app.support import codes
from app.support.models import SupportEmailCode, SupportVerification
from app.webhooks import signing

from .conftest import TEST_DATABASE_URL, signup
from .licence_helpers import CONTRACT, FP1, Clock, activated, bearer, error_of, session
from .org_helpers import _clean_mail_and_caches  # noqa: F401  (autouse)
from .test_billing_pf2 import buy
from .test_releases import _publish
from .test_sso import DOMAIN, _oidc, _verified_org, idp  # noqa: F401  (idp is a fixture)

BASE = "/internal/support"
SECRET = "whsec_" + base64.b64encode(hashlib.sha256(b"truebex support api tests").digest()).decode()
OTHER_SECRET = "whsec_" + base64.b64encode(hashlib.sha256(b"someone else").digest()).decode()
CONTACT = hashlib.sha256(b"whatsapp:+447700900123").hexdigest()
CONTACT2 = hashlib.sha256(b"whatsapp:+447700900456").hexdigest()

# The worked example in docs/support-api.md (the Standard Webhooks spec's example secret).
EXAMPLE_SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
EXAMPLE_ID = "msg_2KWPBgLlAfxdpx2AI54pPJ85f4W"
EXAMPLE_TS = 1794312000  # 2026-11-10T12:00:00Z
EXAMPLE_CONTACT = "5f9801c1f8a8507e661ac3f136471d3eec7332db0859fd5026c8101c09af38c8"
EXAMPLE_BODY = (
    '{"email":"customer@example.com","contact_hash":"5f9801c1f8a8507e661ac3f136471d3eec7332db0859fd5026c8101c09af38c8"}'
)
EXAMPLE_SIGNATURE = "v1,3P81RD2ErBcLvksX9BvhjTWW9/WQrV6WeMofSReITjs="


class Desk:
    """Signs requests as the Desk does (docs/support-api.md), independently of the app's code."""

    def __init__(self, client) -> None:
        self.client = client

    @staticmethod
    def sign(secret: str, msg_id: str, ts: int, method: str, target: str, body: bytes) -> str:
        key = base64.b64decode(secret.removeprefix("whsec_"))
        content = f"{msg_id}.{ts}.{method} {target}\n".encode() + body
        return "v1," + base64.b64encode(hmac.new(key, content, hashlib.sha256).digest()).decode()

    def call(self, method: str, path: str, body=None, *, query: str = "", msg_id: str | None = None,
             ts: int | None = None, secret: str = SECRET, signature: str | None = None,
             signed_target: str | None = None, signed_body: bytes | None = None, headers: dict | None = None):
        raw = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
        msg_id = msg_id or "msg_" + secrets.token_hex(12)
        ts = int(time.time()) if ts is None else ts
        target = BASE + path + (f"?{query}" if query else "")
        sig = signature or self.sign(
            secret, msg_id, ts, method, signed_target or target, raw if signed_body is None else signed_body
        )
        h = {"webhook-id": msg_id, "webhook-timestamp": str(ts), "webhook-signature": sig}
        if body is not None:
            h["content-type"] = "application/json"
        h.update(headers or {})
        return self.client.request(method, target, content=raw if body is not None else None, headers=h)

    def post(self, path, body, **kw):
        return self.call("POST", path, body, **kw)

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def delete(self, path, **kw):
        return self.call("DELETE", path, **kw)


@pytest.fixture()
def desk(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "support_service_secret", SECRET)
    return Desk(client)


def _user_id(client, headers) -> int:
    return client.get("/auth/me", headers=headers).json()["id"]


def _last_code(email: str) -> str:
    msg = [m for m in mail.OUTBOX if m.to == email and m.template == "support_code"][-1]
    return re.search(r"^(\d{6})$", msg.text, re.M).group(1)


def _code(desk, email, contact=CONTACT) -> str:
    res = desk.post("/email-code", {"email": email, "contact_hash": contact})
    assert res.status_code == 202, res.text
    return _last_code(email)


def _verify(desk, email, code, contact=CONTACT):
    return desk.post("/email-code/verify", {"email": email, "code": code, "contact_hash": contact})


def _verified(desk, email) -> dict:
    res = _verify(desk, email, _code(desk, email))
    assert res.status_code == 200, res.text
    return res.json()


ROUTES = [
    ("POST", "/email-code", {"email": "a@example.com", "contact_hash": CONTACT}),
    ("POST", "/email-code/verify", {"email": "a@example.com", "code": "123456"}),
    ("POST", "/register", {"verification_id": "x" * 43, "password": "password123"}),
    ("POST", "/login", {"email": "a@example.com", "password": "password123"}),
    ("POST", "/link/start", {"contact_hash": CONTACT}),
    ("POST", "/link/poll", {"poll_secret": "x" * 43}),
    ("GET", "/users/1/summary", None),
    ("GET", "/users/1/invoices", None),
    ("DELETE", "/users/1/devices/" + "0" * 32, None),
]


# --- switched off, signing, replay ------------------------------------------------------------


def test_every_route_is_404_without_the_secret_and_hidden(client):
    assert get_settings().support_service_secret == ""
    d = Desk(client)
    for method, path, body in ROUTES:
        error_of(d.call(method, path, body), 404, "not_found")
    assert not [p for p in client.get("/openapi.json").json()["paths"] if p.startswith("/internal")]
    assert mail.OUTBOX == []


def test_signature_is_required_and_checked(desk, monkeypatch):
    body = {"email": "a@example.com", "contact_hash": CONTACT}
    raw = json.dumps(body, separators=(",", ":")).encode()
    # Nothing, or a malformed id.
    error_of(desk.client.post(BASE + "/email-code", json=body), 401, "invalid_signature")
    error_of(desk.post("/email-code", body, msg_id="bad id with spaces"), 401, "invalid_signature")
    # Another secret, another body, another path or query, an old or future timestamp.
    error_of(desk.post("/email-code", body, secret=OTHER_SECRET), 401, "invalid_signature")
    error_of(desk.post("/email-code", body, signed_body=raw.replace(b"a@", b"b@")), 401, "invalid_signature")
    error_of(desk.post("/email-code", body, signed_target=BASE + "/login"), 401, "invalid_signature")
    error_of(desk.get("/users/2/summary", signed_target=BASE + "/users/1/summary"), 401, "invalid_signature")
    error_of(desk.get("/users/1/summary", query=f"contact_hash={CONTACT}", signed_target=BASE + "/users/1/summary"),
             401, "invalid_signature")
    error_of(desk.post("/email-code", body, ts=int(time.time()) - 301), 401, "invalid_signature")
    error_of(desk.post("/email-code", body, ts=int(time.time()) + 301), 401, "invalid_signature")
    error_of(desk.post("/email-code", body, signature="v2," + desk.sign(SECRET, "m", 1, "POST", "/", b"")[3:]),
             401, "invalid_signature")
    assert mail.OUTBOX == []
    # Fresh (within 5 minutes) and signed: accepted; several signatures, one matching, too.
    assert desk.post("/email-code", body, ts=int(time.time()) - 290).status_code == 202
    good = desk.sign(SECRET, "msg_both", int(time.time()), "POST", BASE + "/email-code", raw)
    other = desk.sign(OTHER_SECRET, "msg_both", int(time.time()), "POST", BASE + "/email-code", raw)
    assert desk.post("/email-code", body, msg_id="msg_both", signature=f"{other} {good}").status_code == 202
    # Rotation: either secret of "new,old" is accepted.
    monkeypatch.setattr(get_settings(), "support_service_secret", f"{OTHER_SECRET},{SECRET}")
    assert desk.post("/email-code", body).status_code == 202
    assert desk.post("/email-code", body, secret=OTHER_SECRET).status_code == 202
    # A secret that is not whsec_<base64> is a server fault, never a pass.
    for bad in ("whsec_not base64!", "whsec_" + base64.b64encode(b"16 bytes is weak").decode(), SECRET[6:]):
        monkeypatch.setattr(get_settings(), "support_service_secret", bad)
        error_of(desk.post("/email-code", body, secret=SECRET), 503, "unavailable")


def test_a_request_id_is_accepted_once(desk):
    body = {"email": "a@example.com", "contact_hash": CONTACT}
    assert desk.post("/email-code", body, msg_id="msg_once").status_code == 202
    error_of(desk.post("/email-code", body, msg_id="msg_once"), 401, "replayed_request")
    # Even for another route and body: an id is single-use.
    error_of(desk.get("/users/1/summary", msg_id="msg_once"), 401, "replayed_request")
    assert len([m for m in mail.OUTBOX if m.template == "support_code"]) == 1
    with SessionLocal() as db:
        row = db.scalar(select(IdempotencyKey).where(IdempotencyKey.account == "support"))
        assert row.key == hashlib.sha256(b"msg_once").hexdigest()[:32]
    # A rejected signature does not use the id up.
    error_of(desk.post("/email-code", body, msg_id="msg_retry", secret=OTHER_SECRET), 401, "invalid_signature")
    assert desk.post("/email-code", body, msg_id="msg_retry").status_code == 202


def test_worked_example_from_the_contract(desk, monkeypatch):
    assert Desk.sign(EXAMPLE_SECRET, EXAMPLE_ID, EXAMPLE_TS, "POST", BASE + "/email-code",
                     EXAMPLE_BODY.encode()) == EXAMPLE_SIGNATURE
    assert hashlib.sha256(b"example contact").hexdigest() == EXAMPLE_CONTACT
    assert Desk.sign(EXAMPLE_SECRET, EXAMPLE_ID[:-1] + "X", EXAMPLE_TS, "GET", BASE + "/users/42/summary",
                     b"") == "v1,JFtL4ueD62LHPAV6mW6godMvNd00yw5AdUxdcpO6HF4="
    monkeypatch.setattr(get_settings(), "support_service_secret", EXAMPLE_SECRET)
    monkeypatch.setattr(signing, "time", SimpleNamespace(time=lambda: EXAMPLE_TS + 30))
    res = desk.client.post(
        BASE + "/email-code",
        content=EXAMPLE_BODY.encode(),
        headers={
            "content-type": "application/json",
            "webhook-id": EXAMPLE_ID,
            "webhook-timestamp": str(EXAMPLE_TS),
            "webhook-signature": EXAMPLE_SIGNATURE,
        },
    )
    assert res.status_code == 202, res.text
    assert res.json() == {"status": "sent", "expires_in_s": 600, "code_length": 6}


# --- e-mail codes ------------------------------------------------------------------------------


def test_email_code_answers_the_same_with_or_without_an_account(desk, client):
    signup(client, "known@example.com")
    known = desk.post("/email-code", {"email": "Known@Example.com", "contact_hash": CONTACT})
    unknown = desk.post("/email-code", {"email": "nobody@example.com", "contact_hash": CONTACT})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == {"status": "sent", "expires_in_s": 600, "code_length": 6}
    sent = [m for m in mail.OUTBOX if m.template == "support_code"]
    assert [m.to for m in sent] == ["known@example.com", "nobody@example.com"]
    assert sent[0].subject == sent[1].subject == "Your Truebex code"
    code = _last_code("known@example.com")
    assert code not in sent[0].subject and f">{code}<" in sent[0].html
    # Stored only as an HMAC bound to its row, never the code or its bare SHA-256.
    with SessionLocal() as db:
        row = db.scalar(select(SupportEmailCode).where(SupportEmailCode.email == "known@example.com"))
        assert row.code_hash == codes.code_hash(row.id, code)
        assert row.code_hash != hashlib.sha256(code.encode()).hexdigest()
        assert code not in json.dumps([row.id, row.code_hash, row.contact_hash])
        assert row.contact_hash == CONTACT and row.attempts == 0 and row.used_at is None
    error_of(desk.post("/email-code", {"email": "not-an-address", "contact_hash": CONTACT}), 422, "validation_failed")
    error_of(desk.post("/email-code", {"email": "a@example.com", "contact_hash": "+447700900123"}),
             422, "validation_failed")


def test_code_signs_in_an_existing_account_and_verifies_its_address(desk, client):
    h = signup(client, "known@example.com")
    uid = _user_id(client, h)
    with SessionLocal() as db:
        assert db.get(User, uid).email_verified_at is None
    out = _verified(desk, "known@example.com")
    assert out["exists"] is True and out["user_id"] == uid
    assert out["has_password"] is True and out["google_linked"] is False
    assert out["sso_required"] is False and out["org_name"] is None
    assert len(out["verification_id"]) == 43 and out["expires_in_s"] == 900
    with SessionLocal() as db:
        assert db.get(User, uid).email_verified_at is not None
    # The verification never makes a second account for a taken address, and is then spent.
    reg = {"verification_id": out["verification_id"], "password": "another-pass1"}
    error_of(desk.post("/register", reg), 409, "account_exists")
    error_of(desk.post("/register", reg), 410, "verification_expired")


def test_code_tries_expiry_and_single_use(desk, monkeypatch):
    clk = Clock(monkeypatch)
    email = "a@example.com"
    code = _code(desk, email)
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for left in (4, 3, 2, 1, 0):
        body = error_of(_verify(desk, email, wrong), 401, "invalid_code")
        assert body["data"] == {"attempts_left": left}
    # Out of tries: even the right code is refused now.
    error_of(_verify(desk, email, code), 410, "code_expired")

    # A new code replaces the old one; spaces and dashes are read away; it works once.
    first = _code(desk, email)
    second = _code(desk, email)
    if first != second:
        error_of(_verify(desk, email, first), 401, "invalid_code")
    spaced = f"{second[:3]} {second[3:]}"
    assert _verify(desk, email, spaced).status_code == 200
    error_of(_verify(desk, email, second), 410, "code_expired")

    # Ten minutes, then gone.
    late = _code(desk, email)
    clk.advance(seconds=601)
    error_of(_verify(desk, email, late), 410, "code_expired")
    # No code was ever sent to this address.
    error_of(_verify(desk, "never@example.com", "123456"), 410, "code_expired")


def test_register_only_after_a_verified_address(desk, client, monkeypatch):
    clk = Clock(monkeypatch)
    email = "new@example.com"
    # A made-up verification never registers anything.
    error_of(desk.post("/register", {"verification_id": secrets.token_urlsafe(32), "password": "password123"}),
             410, "verification_expired")
    out = _verified(desk, email)
    assert out == {**out, "exists": False, "user_id": None, "has_password": False, "google_linked": False,
                   "sso_required": False, "org_name": None}
    reg = {"verification_id": out["verification_id"], "password": "short", "name": "Ada"}
    error_of(desk.post("/register", reg), 422, "validation_failed")
    res = desk.post("/register", {**reg, "password": "password123", "name": "  Ada Lovelace  "})
    assert res.status_code == 201, res.text
    uid = res.json()["user_id"]
    assert res.json() == {"user_id": uid, "email": email}
    with SessionLocal() as db:
        user = db.get(User, uid)
        assert user.name == "Ada Lovelace" and user.email_verified_at is not None and user.hashed_password
    # The password works on the website too, and the verification is spent.
    assert client.post("/auth/login", json={"email": email, "password": "password123"}).status_code == 200
    error_of(desk.post("/register", {**reg, "password": "password123"}), 410, "verification_expired")
    # 15 minutes, then gone.
    late = _verified(desk, "late@example.com")
    clk.advance(minutes=16)
    error_of(desk.post("/register", {"verification_id": late["verification_id"], "password": "password123"}),
             410, "verification_expired")
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == "late@example.com")) is None


# --- SSO, Google-only, passwords -----------------------------------------------------------------


def test_sso_required_domain_is_refused_and_sent_to_the_link(desk, client, idp):  # noqa: F811
    h, org = _verified_org(client, idp)
    signup(client, f"m@{DOMAIN}")  # a password account from before the policy
    _oidc(client, h, org, required=True)
    new = _verified(desk, f"new@{DOMAIN}")
    assert new["sso_required"] is True and new["org_name"] == "Studio North" and new["exists"] is False
    error_of(desk.post("/register", {"verification_id": new["verification_id"], "password": "password123"}),
             403, "sso_required")
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == f"new@{DOMAIN}")) is None
    # An existing account in the domain: the code is not a sign-in, the link is.
    member = _verified(desk, f"m@{DOMAIN}")
    assert member["exists"] is True and member["user_id"] is None and member["sso_required"] is True
    body = error_of(desk.post("/login", {"email": f"m@{DOMAIN}", "password": "password123"}), 403, "use_link_sign_in")
    assert body["data"] == {"reason": "sso_required", "org_name": "Studio North", "google_linked": False}


def test_login_password_google_only_and_wrong(desk, client):
    h = signup(client, "pw@example.com")
    uid = _user_id(client, h)
    res = desk.post("/login", {"email": "PW@example.com", "password": "password123", "contact_hash": CONTACT})
    assert res.status_code == 200 and res.json() == {"user_id": uid}
    for email, password in (("pw@example.com", "wrong-password"), ("nobody@example.com", "password123")):
        body = error_of(desk.post("/login", {"email": email, "password": password}), 401, "invalid_credentials")
        assert body["detail"] == "Incorrect email or password."
    with SessionLocal() as db:
        db.add(User(email="g@example.com", hashed_password="", google_sub="google-1"))
        db.add(User(email="sso@example.com", hashed_password=""))
        db.commit()
    body = error_of(desk.post("/login", {"email": "g@example.com", "password": "password123"}), 403, "use_link_sign_in")
    assert body["data"] == {"reason": "no_password", "org_name": None, "google_linked": True}
    assert "uses Google" not in body["detail"]
    body = error_of(desk.post("/login", {"email": "sso@example.com", "password": "x"}), 403, "use_link_sign_in")
    assert body["data"]["google_linked"] is False
    # A Google-only account signs in with an e-mail code instead.
    out = _verified(desk, "g@example.com")
    assert out["exists"] and out["user_id"] and out["has_password"] is False and out["google_linked"] is True


# --- link sign-in ---------------------------------------------------------------------------------


def test_link_sign_in_answers_the_account_never_a_session(desk, client, monkeypatch):
    clk = Clock(monkeypatch)
    h = signup(client, "g@example.com")
    uid = _user_id(client, h)
    res = desk.post("/link/start", {"contact_hash": CONTACT})
    assert res.status_code == 201, res.text
    link = res.json()
    code, secret = link["link_code"], link["poll_secret"]
    assert link["verify_url"] == f"https://truebex.com/dashboard/link/?code={code}"
    assert link["expires_in_s"] == 600 and link["interval_s"] == 5 and len(secret) == 43
    # The approval page sees who asks.
    seen = client.get(f"/licence/link/{code}", headers=session(h)).json()
    assert seen["device_name"] == "Truebex support" and seen["app_version"] == "WhatsApp"
    assert seen["purpose"] == "support" and seen["status"] == "pending"

    assert desk.post("/link/poll", {"poll_secret": secret}).json() == {"status": "pending", "user_id": None}
    error_of(desk.post("/link/poll", {"poll_secret": secret}), 429, "rate_limited")
    # The device poll never answers a support code (so never a session for it).
    error_of(client.post("/licence/link/poll", json={"poll_secret": secret}, headers=CONTRACT), 410, "link_expired")
    ok = client.post("/licence/link/approve", json={"link_code": code, "approve": True}, headers=session(h))
    assert ok.status_code == 200
    clk.advance(seconds=5)
    res = desk.post("/link/poll", {"poll_secret": secret})
    assert res.json() == {"status": "approved", "user_id": uid}
    assert "token" not in res.text
    clk.advance(seconds=5)
    error_of(desk.post("/link/poll", {"poll_secret": secret}), 410, "link_expired")

    # A device's link is not the Desk's to poll.
    device = client.post("/licence/link", json={"device_name": "PC", "fingerprint": FP1, "app_version": "1.0.0"},
                         headers=CONTRACT).json()
    error_of(desk.post("/link/poll", {"poll_secret": device["poll_secret"]}), 410, "link_expired")
    assert client.get(f"/licence/link/{device['link_code']}", headers=session(h)).json()["purpose"] == "device"

    # A masked hint of the chat goes on the approval page; nothing else does.
    hinted = desk.post("/link/start", {"contact_hash": CONTACT, "contact_label": "+44 *** 0123"}).json()
    seen = client.get(f"/licence/link/{hinted['link_code']}", headers=session(h)).json()
    assert seen["app_version"] == "WhatsApp +44 *** 0123"
    error_of(desk.post("/link/start", {"contact_hash": CONTACT, "contact_label": "<b>you</b>"}), 422,
             "validation_failed")

    # Denied in the browser; e-mail as the channel.
    denied = desk.post("/link/start", {"contact_hash": CONTACT, "channel": "email"}).json()
    assert client.get(f"/licence/link/{denied['link_code']}", headers=session(h)).json()["app_version"] == "Email"
    client.post("/licence/link/approve", json={"link_code": denied["link_code"], "approve": False}, headers=session(h))
    error_of(desk.post("/link/poll", {"poll_secret": denied["poll_secret"]}), 403, "link_denied")
    with SessionLocal() as db:
        row = db.get(LinkCode, denied["link_code"])
        assert row.purpose == "support" and row.fingerprint == CONTACT


# --- account data ---------------------------------------------------------------------------------


def _analysis_job(uid: int, kind: str, report: bytes | None) -> str:
    job_id = uuid7_hex()
    key = f"jobs/{job_id}/output.json"
    output = {"schema": "truebex-analysis/1", "kind": kind, "report": None}
    store = get_store()
    if report is not None:
        sha = hashlib.sha256(report).hexdigest()
        output["report"] = sha
        store.put(f"jobs/{job_id}/files/{sha}", io.BytesIO(report), content_type="application/pdf")
    store.put(key, io.BytesIO(json.dumps(output).encode()), content_type="application/json")
    with SessionLocal() as db:
        db.add(RenderJob(job_id=job_id, account_kind="user", account_id=uid, kind=kind, worker_class="cpu-8",
                         state="succeeded", output_key=key))
        db.commit()
    return job_id


def test_summary_shape(desk, client, paddle, tmp_path):
    h = signup(client, "dev@example.com")
    uid = _user_id(client, h)
    buy(client, h, paddle)
    device = activated(client, h)
    key = client.post("/keys", json={"name": "CI"}, headers=h).json()["key"]
    _publish(tmp_path, "1.2.0", "stable")
    with_report = _analysis_job(uid, "wind", b"%PDF-1.7 wind report")
    _analysis_job(uid, "energy", None)
    _analysis_job(uid + 1000, "airflow", b"%PDF-1.7 someone else's")

    res = desk.get(f"/users/{uid}/summary", query=f"contact_hash={CONTACT}")
    assert res.status_code == 200, res.text
    s = res.json()
    assert set(s) == {"user", "plan", "plan_name", "trial", "seat", "seats", "devices", "subscription", "payments",
                      "api_keys", "release", "analysis_jobs", "report_urls_expire_in_s", "manage_url"}
    assert s["user"]["id"] == uid and s["user"]["email"] == "dev@example.com" and s["user"]["has_password"]
    assert s["plan"] == "pro" and s["plan_name"] and s["subscription"]["tier"] == "pro"
    assert set(s["trial"]) == {"used", "active", "ends_at"} and s["seat"]["kind"] and "total" in s["seats"]
    assert s["devices"]["count"] == 1 and s["devices"]["limit"] >= 1
    assert s["devices"]["active"][0]["device_id"] == device["device_id"]
    assert s["devices"]["active"][0]["name"] == "TEST-PC"
    assert 1 <= len(s["payments"]) <= 5 and s["payments"][0]["plan"] == "pro"
    assert [k["name"] for k in s["api_keys"]] == ["CI"] and s["api_keys"][0]["prefix"]
    assert key not in res.text and "key_hash" not in res.text and "device_token" not in res.text
    rel = s["release"]
    assert rel["version"] == "1.2.0" and rel["download_page_url"] == "https://truebex.com/download/"
    assert rel["bytes"] > 0 and len(rel["sha256"]) == 64
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DownloadEvent)) == 0  # never the counted download
    jobs = {j["job_id"]: j for j in s["analysis_jobs"]}
    assert set(jobs) >= {with_report} and all(j["kind"] in ("wind", "energy") for j in jobs.values())
    url = jobs[with_report]["report_pdf_url"]
    assert url.startswith("http://testserver/files/jobs/") and "fn=report.pdf" in url
    assert client.get(url[len("http://testserver"):]).content == b"%PDF-1.7 wind report"
    assert [j["report_pdf_url"] for j in jobs.values() if j["kind"] == "energy"] == [None]
    assert s["report_urls_expire_in_s"] == 3600
    assert s["manage_url"] == "https://truebex.com/dashboard/billing/"
    error_of(desk.get("/users/999999/summary"), 404, "not_found")


def test_summary_of_a_new_account(desk, client):
    uid = _user_id(client, signup(client))
    s = desk.get(f"/users/{uid}/summary").json()
    assert s["plan"] == "free" and s["payments"] == [] and s["api_keys"] == [] and s["release"] is None
    assert s["devices"] == {"active": [], "count": 0, "limit": s["devices"]["limit"]}
    assert s["analysis_jobs"] == [] and s["subscription"]["status"] == "none"


def test_invoices_have_absolute_signed_pdf_links(desk, client, paddle):
    h = signup(client)
    uid = _user_id(client, h)
    assert desk.get(f"/users/{uid}/invoices").json() == {"invoices": [], "pdf_links_expire_in_s": 3600}
    buy(client, h, paddle)
    out = desk.get(f"/users/{uid}/invoices").json()
    assert out["pdf_links_expire_in_s"] == 3600 and len(out["invoices"]) == 1
    inv = out["invoices"][0]
    assert set(inv) == {"id", "number", "issued_at", "total_minor", "tax_minor", "currency", "status", "pdf_url"}
    assert inv["pdf_url"].startswith(f"http://testserver/billing/invoices/{inv['id']}/pdf?u={uid}&")
    exp = int(re.search(r"exp=(\d+)", inv["pdf_url"]).group(1))
    assert 3500 <= exp - time.time() <= 3600
    res = client.get(inv["pdf_url"][len("http://testserver"):], follow_redirects=False)
    assert res.status_code == 302
    error_of(desk.get("/users/999999/invoices"), 404, "not_found")


def test_remove_device(desk, client):
    h = signup(client)
    uid = _user_id(client, h)
    device = activated(client, h)
    other = activated(client, signup(client, "other@example.com"))
    error_of(desk.delete(f"/users/{uid}/devices/{other['device_id']}"), 404, "not_found")
    error_of(desk.delete(f"/users/999999/devices/{device['device_id']}"), 404, "not_found")
    res = desk.delete(f"/users/{uid}/devices/{device['device_id']}")
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["device_id"] == device["device_id"] and out["removed"] is True and out["deactivated_at"]
    # Its token stops working at once; removing it again is harmless.
    assert client.get("/licence/account", headers=bearer(device["device_token"])).status_code == 401
    assert desk.delete(f"/users/{uid}/devices/{device['device_id']}").json()["removed"] is False
    with SessionLocal() as db:
        assert db.get(Device, device["device_id"]).deactivated_reason == "removed"
        kinds = [e.kind for e in db.scalars(select(LicenceEvent).where(LicenceEvent.device_id == device["device_id"]))]
        assert "device.revoked" in kinds


# --- rate limits ------------------------------------------------------------------------------------


def test_rate_limits_are_per_address_and_contact(desk, client, monkeypatch):
    # Per address: 5 codes, whatever the contact.
    for i in range(5):
        contact = CONTACT if i % 2 else CONTACT2
        assert desk.post("/email-code", {"email": "a@example.com", "contact_hash": contact}).status_code == 202
    body = error_of(desk.post("/email-code", {"email": "a@example.com", "contact_hash": CONTACT}), 429, "rate_limited")
    assert body["retry_after_s"] >= 1
    # Per contact: 10 asks, whatever the address (CONTACT asked 3 times above, the refused one too).
    for i in range(7):
        assert desk.post("/email-code", {"email": f"c{i}@example.com", "contact_hash": CONTACT}).status_code == 202
    error_of(desk.post("/email-code", {"email": "fresh@example.com", "contact_hash": CONTACT}), 429, "rate_limited")
    assert desk.post("/email-code", {"email": "fresh@example.com", "contact_hash": CONTACT2}).status_code == 202

    # Passwords: 10 tries per address an hour, then 429 even with the right one.
    signup(client, "pw@example.com")
    for _ in range(10):
        error_of(desk.post("/login", {"email": "pw@example.com", "password": "wrong-pass"}), 401, "invalid_credentials")
    error_of(desk.post("/login", {"email": "pw@example.com", "password": "password123"}), 429, "rate_limited")

    # Link codes: 10 per contact an hour.
    for _ in range(10):
        assert desk.post("/link/start", {"contact_hash": CONTACT2}).status_code == 201
    error_of(desk.post("/link/start", {"contact_hash": CONTACT2}), 429, "rate_limited")
    assert desk.post("/link/start", {"contact_hash": CONTACT}).status_code == 201

    # The ceiling on all codes together.
    monkeypatch.setitem(support_router.LIMITS, "code.all", (300, 1))
    from app import ratelimit

    ratelimit.reset()
    assert desk.post("/email-code", {"email": "x@example.com", "contact_hash": CONTACT}).status_code == 202
    error_of(desk.post("/email-code", {"email": "y@example.com", "contact_hash": CONTACT2}), 429, "rate_limited")


# --- audit, purge, columns ------------------------------------------------------------------------------


def test_audit_line_for_every_call_and_no_secrets(desk, client, caplog):
    caplog.set_level(logging.INFO)
    h = signup(client, "pw@example.com")
    uid = _user_id(client, h)
    code = _code(desk, "pw@example.com")
    out = _verify(desk, "pw@example.com", code).json()
    desk.post("/login", {"email": "pw@example.com", "password": "password123", "contact_hash": CONTACT})
    desk.post("/login", {"email": "pw@example.com", "password": "wrong-pass"})
    desk.get(f"/users/{uid}/summary", query=f"contact_hash={CONTACT}", msg_id="msg_summary_1")
    desk.post("/email-code", {"email": "x@example.com", "contact_hash": CONTACT}, secret=OTHER_SECRET)
    lines = [r.getMessage() for r in caplog.records if r.name == "truebex.support"]
    assert any(f"POST /internal/support/login by desk" in ln and f"user={uid}" in ln and "-> ok" in ln
               and f"contact={CONTACT[:12]}" in ln for ln in lines), lines
    assert any("POST /internal/support/login" in ln and "-> invalid_credentials" in ln for ln in lines), lines
    assert any("GET /internal/support/users/{user_id}/summary" in ln and "msg=msg_summary_1" in ln
               and f"user={uid}" in ln for ln in lines), lines
    assert any("POST /internal/support/email-code/verify" in ln and f"user={uid}" in ln for ln in lines), lines
    assert any("refused invalid_signature" in ln for ln in lines), lines
    everything = "\n".join(r.getMessage() for r in caplog.records)
    assert not re.search(rf"\b{code}\b", everything)
    for secret in ("password123", "wrong-pass", out["verification_id"], SECRET, "webhook-signature", "v1,"):
        assert secret not in everything, secret


def test_purge_job_drops_spent_and_expired(desk, monkeypatch):
    clk = Clock(monkeypatch)
    _verified(desk, "a@example.com")  # a spent code and a live verification
    _code(desk, "b@example.com")  # a live code
    assert "support.codes.purge" in tasks.registered()
    with SessionLocal() as db:
        assert codes.purge(db, clk.at) == 1
        db.commit()
        assert db.scalar(select(func.count()).select_from(SupportEmailCode)) == 1
        assert db.scalar(select(func.count()).select_from(SupportVerification)) == 1
    clk.advance(minutes=16)
    tasks.run_due(clk.at, only=["support.codes.purge"])
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SupportEmailCode)) == 0
        assert db.scalar(select(func.count()).select_from(SupportVerification)) == 0


@pytest.mark.parametrize("dialect", ["sqlite", pytest.param("postgresql", marks=pytest.mark.postgres)])
def test_added_columns_migrate_an_older_database(tmp_path, dialect):
    """A database from before the support API gains users.email_verified_at and
    link_codes.purpose (`_ADDED_COLUMNS`); old rows read as NULL."""
    if dialect == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    else:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    try:
        init_db(engine, seed=False)
        with Session(engine) as db:
            db.add(User(email="old@example.com", hashed_password="x"))
            db.commit()
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users DROP COLUMN email_verified_at"))
            conn.execute(text("ALTER TABLE link_codes DROP COLUMN purpose"))
        init_db(engine, seed=False)
        insp = inspect(engine)
        assert "email_verified_at" in {c["name"] for c in insp.get_columns("users")}
        assert "purpose" in {c["name"] for c in insp.get_columns("link_codes")}
        with Session(engine) as db:
            assert db.scalar(select(User)).email_verified_at is None
    finally:
        engine.dispose()
