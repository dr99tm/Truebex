"""Licence API (contract licence-api v1.0, PF1): the contract's §10 platform
tests and a test per endpoint (happy path, auth failure, validation failure)."""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.exceptions import InvalidSignature
from sqlalchemy import func, select

from app import tasks
from app.database import SessionLocal
from app.licence import jcs, seats
from app.licence.models import Device, LicenceEvent, LinkCode, TrialFingerprint
from app.models import Subscription, User
from app.plans import get_plan

from .conftest import LICENCE_FIXTURES, TEST_KEY, signup
from .licence_helpers import (
    CONTRACT,
    FP1,
    FP2,
    FP3,
    Clock,
    activate,
    activated,
    bearer,
    error_of,
    fp,
    published_key,
    refresh,
    session,
    ts,
    verify_with,
)
from .test_billing import _stripe_post, _sub_event

CODE_RE = re.compile(r"^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{4}-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{4}$")
LINK_BODY = {"device_name": "TEST-PC", "fingerprint": FP1, "app_version": "1.0.0"}


def _start_link(client, **over):
    res = client.post("/licence/link", json={**LINK_BODY, **over}, headers=CONTRACT)
    assert res.status_code == 201, res.text
    return res.json()


def _poll(client, secret):
    return client.post("/licence/link/poll", json={"poll_secret": secret}, headers=CONTRACT)


def _approve(client, headers, code, approve=True):
    return client.post(
        "/licence/link/approve", json={"link_code": code, "approve": approve}, headers=session(headers)
    )


def _user_id(client, headers) -> int:
    return client.get("/auth/me", headers=headers).json()["id"]


def _events(kind: str | None = None) -> list[LicenceEvent]:
    with SessionLocal() as db:
        q = select(LicenceEvent)
        if kind:
            q = q.where(LicenceEvent.kind == kind)
        return list(db.scalars(q))


# --- contract §10 -----------------------------------------------------------------


def test_link_flow_pending_approved_expired(client, monkeypatch):
    clk = Clock(monkeypatch)
    h = signup(client)
    link = _start_link(client)
    code, secret = link["link_code"], link["poll_secret"]
    assert CODE_RE.match(code)
    assert len(secret) == 43
    assert link["verify_url"] == f"https://truebex.com/dashboard/link/?code={code}"
    assert link["expires_in_s"] == 600 and link["interval_s"] == 5

    # The poll secret is stored only as its SHA-256.
    with SessionLocal() as db:
        row = db.get(LinkCode, code)
        assert row.poll_secret_hash == hashlib.sha256(secret.encode()).hexdigest()
        assert secret not in json.dumps([row.poll_secret_hash, row.device_name, row.fingerprint])

    assert _poll(client, secret).json() == {"status": "pending"}

    # The website shows the device before Approve.
    seen = client.get(f"/licence/link/{code.lower().replace('-', '')}", headers=session(h)).json()
    assert seen["device_name"] == "TEST-PC" and seen["app_version"] == "1.0.0" and seen["status"] == "pending"

    res = _approve(client, h, code)
    assert res.status_code == 200
    assert res.json() == {"status": "approved", "device_name": "TEST-PC"}

    clk.advance(seconds=5)
    approved = _poll(client, secret).json()
    assert approved["status"] == "approved"
    token = approved["token"]
    assert token["token_type"] == "bearer" and token["user"]["email"] == "dev@example.com"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert me.status_code == 200

    # Handed over once: the code is spent.
    clk.advance(seconds=5)
    error_of(_poll(client, secret), 410, "link_expired")

    # Expired after 600 s: polling says so and the website cannot approve it.
    late = _start_link(client)
    clk.advance(seconds=601)
    error_of(_poll(client, late["poll_secret"]), 410, "link_expired")
    error_of(_approve(client, h, late["link_code"]), 404, "not_found")

    # Denied in the browser.
    denied = _start_link(client)
    assert _approve(client, h, denied["link_code"], approve=False).json()["status"] == "denied"
    error_of(_poll(client, denied["poll_secret"]), 403, "link_denied")


def test_activate_signs_entitlement(client):
    h = signup(client)
    res = activate(client, h)
    assert res.status_code == 201, res.text
    body = res.json()
    device_id, token = body["device_id"], body["device_token"]
    assert re.fullmatch(r"[0-9a-f]{32}", device_id) and device_id[12] == "7"  # UUIDv7
    assert token.startswith("tbx_dev_") and len(token) == 51

    env = body["entitlement"]
    doc, sig = env["document"], env["signature"]
    assert sig["alg"] == "Ed25519" and sig["kid"] == TEST_KEY["kid"] and len(sig["value"]) == 86
    # The published key verifies the signature over the RFC 8785 bytes.
    verify_with(published_key(client, sig["kid"]), doc, sig["value"])
    tampered = {**doc, "plan": "pro"}
    with pytest.raises(InvalidSignature):
        verify_with(published_key(client, sig["kid"]), tampered, sig["value"])
    # For these documents JCS equals sorted, compact, non-ASCII-preserving JSON.
    assert jcs.canonicalize(doc) == json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    assert doc["schema"] == "truebex-entitlement/1"
    assert doc["plan"] == "free" and doc["seat_kind"] == "free" and doc["trial"] is False
    assert doc["device_id"] == device_id and doc["fingerprint"] == FP1
    assert doc["features"] == sorted(set(doc["features"])) == list(get_plan("free").features)
    assert all(re.fullmatch(r"[a-z0-9_.]{1,64}", f) for f in doc["features"])
    assert doc["limits"] == {"storeys": 1, "devices": 2, "share_links": 1, "cloud_cu_month": 0, "ai_credits_month": 0}
    issued = ts(doc["issued_at"])
    assert ts(doc["refresh_after"]) - issued == timedelta(hours=24)
    assert ts(doc["expires_at"]) - issued == timedelta(days=14)
    assert doc["plan_period_end"] is None
    assert re.fullmatch(r"[0-9a-f]{32}", doc["nonce"])
    acct = doc["account"]
    assert acct["email"] == "dev@example.com" and acct["org_id"] is None
    assert re.fullmatch(r"[0-9a-f]{32}", acct["author_id"])
    for key in ("issued_at", "refresh_after", "expires_at"):
        assert doc[key].endswith("Z")

    # Only a hash of the device token is stored.
    with SessionLocal() as db:
        row = db.get(Device, device_id)
        assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()


def test_activate_same_fingerprint_reuses_device(client):
    h = signup(client)
    first = activated(client, h)
    res = activate(client, h, name="TEST-PC renamed")
    assert res.status_code == 200
    again = res.json()
    assert again["device_id"] == first["device_id"]
    assert again["device_token"] != first["device_token"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Device.device_id))) == 1
        assert db.get(Device, first["device_id"]).name == "TEST-PC renamed"
    error_of(refresh(client, first["device_token"]), 401, "device_revoked")
    assert refresh(client, again["device_token"]).status_code == 200


def test_device_limit_and_replace(client):
    h = signup(client)
    one = activated(client, h, FP1, "PC-1")
    two = activated(client, h, FP2, "PC-2")
    body = error_of(activate(client, h, FP3, "PC-3"), 409, "device_limit")
    assert body["data"]["limit"] == 2
    assert {d["device_id"] for d in body["data"]["devices"]} == {one["device_id"], two["device_id"]}
    assert {d["name"] for d in body["data"]["devices"]} == {"PC-1", "PC-2"}

    error_of(activate(client, h, FP3, "PC-3", replace="0" * 32), 404, "not_found")

    res = activate(client, h, FP3, "PC-3", replace=one["device_id"])
    assert res.status_code == 201, res.text
    listed = client.get("/licence/devices", headers=session(h)).json()
    assert {d["name"] for d in listed["devices"]} == {"PC-2", "PC-3"}
    error_of(refresh(client, one["device_token"]), 401, "device_revoked")


def test_entitlement_revoked_and_fingerprint(client):
    h = signup(client)
    dev = activated(client, h)
    assert client.delete(f"/licence/devices/{dev['device_id']}", headers=session(h)).status_code == 200
    error_of(refresh(client, dev["device_token"]), 401, "device_revoked")

    dev = activated(client, h)
    ok = refresh(client, dev["device_token"])
    assert ok.status_code == 200 and ok.json()["entitlement"]["document"]["device_id"] == dev["device_id"]
    # The token copied to another machine: refused, and revoked for good.
    error_of(refresh(client, dev["device_token"], fingerprint=FP2), 409, "fingerprint_mismatch")
    error_of(refresh(client, dev["device_token"]), 401, "device_revoked")


def test_trial_once_per_account(client, monkeypatch):
    clk = Clock(monkeypatch)
    h = signup(client)
    dev = activated(client, h)
    res = client.post("/licence/trial", json={"plan": "pro"}, headers=bearer(dev["device_token"]))
    assert res.status_code == 201, res.text
    body = res.json()
    doc = body["entitlement"]["document"]
    assert doc["plan"] == "pro" and doc["seat_kind"] == "trial" and doc["trial"] is True
    assert "export.clean" in doc["features"]
    assert ts(body["trial_ends_at"]) - clk.at == timedelta(days=14)
    assert doc["expires_at"] == body["trial_ends_at"]
    assert client.get("/auth/me", headers=h).json()["plan"] == "pro"

    second = error_of(
        client.post("/licence/trial", json={"plan": "pro"}, headers=bearer(dev["device_token"])), 409, "trial_used"
    )
    assert second["data"]["used_at"].endswith("Z")

    # Another account on the same computer cannot start a second trial.
    h2 = signup(client, email="other@example.com")
    dev2 = activated(client, h2)
    error_of(client.post("/licence/trial", json={"plan": "pro"}, headers=bearer(dev2["device_token"])), 409, "trial_used")

    # Day 15: the trial has ended and the next document is Free again.
    with SessionLocal() as db:
        sub = db.scalar(select(Subscription).where(Subscription.provider == "trial"))
        sub.current_period_end = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    after = refresh(client, dev["device_token"]).json()["entitlement"]["document"]
    assert after["plan"] == "free" and after["seat_kind"] == "free" and "export.clean" not in after["features"]


def test_plan_change_reaches_entitlement(client):
    h = signup(client)
    uid = _user_id(client, h)
    dev = activated(client, h)
    assert refresh(client, dev["device_token"]).json()["entitlement"]["document"]["plan"] == "free"

    # The browser cannot grant a plan (as test_billing.test_no_client_side_plan_grant).
    assert client.post("/billing/activate", json={"plan": "pro"}, headers=h).status_code in (404, 405)
    assert client.post("/licence/trial", json={"plan": "pro"}, headers=session(h)).status_code == 401
    assert refresh(client, dev["device_token"]).json()["entitlement"]["document"]["plan"] == "free"

    # A signed Stripe event does.
    end = int(datetime.now(timezone.utc).timestamp()) + 30 * 86400
    assert _stripe_post(client, _sub_event("customer.subscription.created", uid, "active", end)).status_code == 200
    doc = refresh(client, dev["device_token"]).json()["entitlement"]["document"]
    assert doc["plan"] == "pro" and doc["seat_kind"] == "personal" and "export.clean" in doc["features"]
    assert doc["plan_period_end"] == datetime.fromtimestamp(end, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # A renewing subscription keeps the full 14-day offline grace.
    assert ts(doc["expires_at"]) - ts(doc["issued_at"]) == timedelta(days=14)

    # An unsigned (forged) event changes nothing; a signed cancellation does.
    assert _stripe_post(client, _sub_event("customer.subscription.deleted", uid, "canceled", end), secret="whsec_x").status_code == 400
    assert refresh(client, dev["device_token"]).json()["entitlement"]["document"]["plan"] == "pro"
    _stripe_post(client, _sub_event("customer.subscription.deleted", uid, "canceled", end))
    assert refresh(client, dev["device_token"]).json()["entitlement"]["document"]["plan"] == "free"


def test_canonical_json_matches_fixtures():
    files = sorted(LICENCE_FIXTURES.glob("entitlement-*.json"))
    assert {f.stem for f in files} == {
        f"entitlement-{n}"
        for n in ("free", "pro", "studio", "team", "enterprise", "trial", "floating", "expired", "tampered")
    }
    keys = {TEST_KEY["kid"]: TEST_KEY["public_key"]}
    for path in files:
        fx = json.loads(path.read_text(encoding="utf-8"))
        doc = fx["envelope"]["document"]
        assert jcs.canonicalize(doc) == fx["canonical"], path.name
        assert jcs.canonical_bytes(doc) == fx["canonical"].encode("utf-8")
        valid = path.stem != "entitlement-tampered"
        from app.licence import signing

        assert signing.verify(doc, fx["envelope"]["signature"], keys) is valid, path.name
    cases = json.loads((LICENCE_FIXTURES / "jcs-cases.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 5
    for case in cases:
        assert jcs.canonicalize(case["document"]) == case["canonical"], case["name"]
    with pytest.raises(TypeError):
        jcs.canonicalize({"x": 1.5})


def test_contract_header_and_error_envelope(client):
    ok = client.get("/licence/keys", headers=CONTRACT)
    assert ok.status_code == 200 and ok.headers["X-Truebex-Contract"] == "licence-api/1.0"
    assert len(ok.headers["X-Request-Id"]) == 32
    # A newer MINOR is served; no header is read as the current version.
    assert client.get("/licence/keys", headers={"X-Truebex-Contract": "licence-api/1.7"}).status_code == 200
    assert client.get("/releases/feed").headers["X-Truebex-Contract"] == "licence-api/1.0"

    body = error_of(client.get("/licence/keys", headers={"X-Truebex-Contract": "licence-api/2.0"}), 400, "contract_version")
    assert body["data"]["supported"] == ["licence-api/1.0"]
    error_of(client.get("/releases/feed", headers={"X-Truebex-Contract": "garbage"}), 400, "contract_version")

    # Every error on a contract route carries code and request_id.
    cases = [
        (client.get("/licence/account", headers=CONTRACT), 401, "unauthenticated"),
        (client.post("/licence/activate", json={}, headers=CONTRACT), 401, "unauthenticated"),
        (client.post("/licence/link", json={"fingerprint": "x"}, headers=CONTRACT), 422, "validation_failed"),
        (client.get("/releases/feed?channel=nightly", headers=CONTRACT), 422, "validation_failed"),
        (client.get("/releases/9.9.9/download", headers=CONTRACT), 404, "not_found"),
        (client.post("/licence/link/poll", json={"poll_secret": "x" * 43}, headers=CONTRACT), 410, "link_expired"),
    ]
    for res, status, code in cases:
        body = error_of(res, status, code)
        assert res.headers["X-Truebex-Contract"] == "licence-api/1.0"
        assert set(body) == {"detail", "code", "status", "request_id", "retry_after_s", "data"}
    fields = client.post("/licence/link", json={"fingerprint": "x"}, headers=CONTRACT).json()["data"]["fields"]
    assert {f["field"] for f in fields} >= {"fingerprint", "device_name", "app_version"}

    # Routers outside the contracts keep their {"detail": …} bodies.
    plain = client.get("/auth/me")
    assert plain.status_code == 401 and "code" not in plain.json() and isinstance(plain.json()["detail"], str)


# --- endpoint tests ----------------------------------------------------------------


def test_licence_link_rate_limits(client, monkeypatch):
    clk = Clock(monkeypatch)
    for _ in range(10):
        assert client.post("/licence/link", json=LINK_BODY, headers=CONTRACT).status_code == 201
    body = error_of(client.post("/licence/link", json=LINK_BODY, headers=CONTRACT), 429, "rate_limited")
    assert body["retry_after_s"] >= 1

    # Polling faster than interval_s is refused; waiting it out works.
    from app import ratelimit

    ratelimit.reset()
    link = _start_link(client)
    assert _poll(client, link["poll_secret"]).status_code == 200
    body = error_of(_poll(client, link["poll_secret"]), 429, "rate_limited")
    assert 1 <= body["retry_after_s"] <= 5
    clk.advance(seconds=5)
    assert _poll(client, link["poll_secret"]).json() == {"status": "pending"}


def test_licence_link_approve_requires_session(client):
    h = signup(client)
    link = _start_link(client)
    code = link["link_code"]
    error_of(client.post("/licence/link/approve", json={"link_code": code}, headers=CONTRACT), 401, "unauthenticated")
    dev = activated(client, h)
    error_of(client.post("/licence/link/approve", json={"link_code": code}, headers=bearer(dev["device_token"])), 401, "unauthenticated")
    error_of(client.get(f"/licence/link/{code}", headers=CONTRACT), 401, "unauthenticated")
    unknown = "AAAA-2222" if code != "AAAA-2222" else "BBBB-3333"
    error_of(_approve(client, h, unknown), 404, "not_found")
    error_of(client.get(f"/licence/link/{unknown}", headers=session(h)), 404, "not_found")
    body = error_of(_approve(client, h, "ABC"), 422, "validation_failed")
    assert body["data"]["fields"][0]["field"] == "link_code"
    error_of(_approve(client, h, "IIII-0000"), 422, "validation_failed")  # letters outside the alphabet
    error_of(client.get("/licence/link/nope", headers=session(h)), 422, "validation_failed")
    assert _approve(client, h, code).status_code == 200
    assert _approve(client, h, code).status_code == 200  # a second press is harmless


def test_licence_activate_validation(client):
    h = signup(client)
    body = error_of(activate(client, h, fingerprint="a" * 63), 422, "validation_failed")
    assert body["data"]["fields"][0]["field"] == "fingerprint"
    error_of(activate(client, h, fingerprint="A" * 64), 422, "validation_failed")  # lowercase hex only
    error_of(activate(client, h, replace="xyz"), 422, "validation_failed")
    dev = activated(client, h)
    payload = {"fingerprint": FP2, "device_name": "PC", "app_version": "1.0.0"}
    error_of(client.post("/licence/activate", json=payload, headers=bearer(dev["device_token"])), 401, "unauthenticated")
    error_of(client.post("/licence/activate", json=payload, headers=CONTRACT), 401, "unauthenticated")


def test_licence_trial_plan_active_and_auth(client):
    h = signup(client)
    uid = _user_id(client, h)
    dev = activated(client, h)
    error_of(client.post("/licence/trial", json={"plan": "pro"}, headers=CONTRACT), 401, "unauthenticated")
    error_of(client.post("/licence/trial", json={"plan": "pro"}, headers=session(h)), 401, "unauthenticated")
    error_of(client.post("/licence/trial", json={"plan": "studio"}, headers=bearer(dev["device_token"])), 422, "validation_failed")

    with SessionLocal() as db:
        db.add(Subscription(user_id=uid, plan="pro", provider="stripe", status="active",
                            current_period_end=datetime.now(timezone.utc) + timedelta(days=20)))
        db.commit()
    body = error_of(client.post("/licence/trial", json={"plan": "pro"}, headers=bearer(dev["device_token"])), 409, "plan_active")
    assert body["data"]["plan"] == "pro"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(TrialFingerprint)) == 0


def test_licence_account_panel(client):
    h = signup(client)
    dev = activated(client, h)
    first = client.get("/licence/account", headers=bearer(dev["device_token"]))
    assert first.status_code == 200
    a = first.json()
    assert re.fullmatch(r"[0-9a-f]{32}", a["author_id"])
    assert a["author_id"] == client.get("/licence/account", headers=bearer(dev["device_token"])).json()["author_id"]
    assert a["author_id"] == refresh(client, dev["device_token"]).json()["entitlement"]["document"]["account"]["author_id"]
    assert a["user"] == {"id": _user_id(client, h), "email": "dev@example.com", "name": None, "avatar_url": None}
    assert a["plan"] == "free" and a["plan_name"] == "Free"
    assert a["trial"] == {"used": False, "active": False, "ends_at": None}
    assert a["seat"] == {"kind": "free", "org_id": None, "org_name": None}
    assert a["seats"] == {"total": 1, "assigned": 1}
    assert a["devices"] == {"active": 1, "limit": get_plan("free").limits["devices"]}
    assert a["manage_url"] == "https://truebex.com/dashboard/billing/"
    error_of(client.get("/licence/account", headers=CONTRACT), 401, "unauthenticated")
    error_of(client.get("/licence/account", headers=session(h)), 401, "unauthenticated")
    error_of(client.get("/licence/account", headers=bearer("tbx_dev_" + "x" * 43)), 401, "device_revoked")

    client.post("/licence/trial", json={"plan": "pro"}, headers=bearer(dev["device_token"]))
    t = client.get("/licence/account", headers=bearer(dev["device_token"])).json()
    assert t["plan_name"] == "Pro" and t["seat"]["kind"] == "trial"
    assert t["trial"]["used"] and t["trial"]["active"] and t["trial"]["ends_at"].endswith("Z")


def test_licence_devices_list_remove_and_deactivate(client):
    h = signup(client)
    a = activated(client, h, FP1, "PC-A")
    b = activated(client, h, FP2, "PC-B")
    listed = client.get("/licence/devices", headers=bearer(a["device_token"])).json()
    assert listed["limit"] == 2
    assert {d["name"]: d["current"] for d in listed["devices"]} == {"PC-A": True, "PC-B": False}
    row = listed["devices"][0]
    assert set(row) == {"device_id", "name", "os", "app_version", "activated_at", "last_seen_at", "current"}
    assert not any(d["current"] for d in client.get("/licence/devices", headers=session(h)).json()["devices"])
    error_of(client.get("/licence/devices", headers=CONTRACT), 401, "unauthenticated")

    # Remove B from device A: the slot frees up.
    removed = client.delete(f"/licence/devices/{b['device_id']}", headers=bearer(a["device_token"]))
    assert removed.status_code == 200 and removed.json()["deactivated_at"].endswith("Z")
    assert [d["name"] for d in client.get("/licence/devices", headers=session(h)).json()["devices"]] == ["PC-A"]
    assert activate(client, h, FP3, "PC-C").status_code == 201
    # Removing again is harmless.
    assert client.delete(f"/licence/devices/{b['device_id']}", headers=session(h)).status_code == 200

    # Another account's device is not found.
    h2 = signup(client, email="other@example.com")
    other = activated(client, h2, fp("other"), "OTHER")
    error_of(client.delete(f"/licence/devices/{other['device_id']}", headers=session(h)), 404, "not_found")
    error_of(client.delete(f"/licence/devices/{other['device_id']}", headers=CONTRACT), 401, "unauthenticated")

    # 5.10 signs out; repeating it is safe; the token is then refused.
    out = client.post("/licence/deactivate", headers=bearer(a["device_token"]))
    assert out.status_code == 200 and out.json()["device_id"] == a["device_id"]
    again = client.post("/licence/deactivate", headers=bearer(a["device_token"]))
    assert again.status_code == 200 and again.json() == out.json()
    error_of(refresh(client, a["device_token"]), 401, "device_revoked")
    error_of(client.post("/licence/deactivate", headers=session(h)), 401, "unauthenticated")


def test_licence_devices_lapse_after_90_days(client):
    h = signup(client)
    a = activated(client, h, FP1)
    b = activated(client, h, FP2)
    old = datetime.now(timezone.utc) - timedelta(days=91)
    with SessionLocal() as db:
        for d in db.scalars(select(Device)):
            d.last_seen_at = old
        db.commit()
    # The token is refused at once, even before the job runs.
    error_of(refresh(client, b["device_token"]), 401, "device_revoked")

    ran = tasks.run_due(datetime.now(timezone.utc))
    assert "licence.devices.lapse" in ran and "licence.links.purge" in ran
    with SessionLocal() as db:
        row = db.get(Device, a["device_id"])
        assert row.deactivated_at is not None and row.deactivated_reason == "lapsed"
    error_of(refresh(client, a["device_token"]), 401, "device_revoked")
    # Not due again until a day later.
    assert "licence.devices.lapse" not in tasks.run_due(datetime.now(timezone.utc) + timedelta(hours=1))


def test_licence_links_purged(client, monkeypatch):
    clk = Clock(monkeypatch)
    _start_link(client)
    clk.advance(seconds=700)
    tasks.run_due(clk.at, force=True)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(LinkCode)) == 0


def test_licence_floating_durations_hook(client, monkeypatch):
    h = signup(client)
    dev = activated(client, h)
    org = "0" * 31 + "a"
    monkeypatch.setattr(
        seats, "seat_source",
        lambda db, user: seats.Seat(kind="floating", plan="team", devices_limit=5, org_id=org, org_name="Studio A"),
    )
    doc = refresh(client, dev["device_token"]).json()["entitlement"]["document"]
    issued = ts(doc["issued_at"])
    assert ts(doc["refresh_after"]) - issued == timedelta(minutes=30)
    assert ts(doc["expires_at"]) - issued == timedelta(hours=2)
    assert doc["seat_kind"] == "floating" and doc["plan"] == "team" and doc["account"]["org_id"] == org
    assert doc["features"] == list(get_plan("team").features)
    acct = client.get("/licence/account", headers=bearer(dev["device_token"])).json()
    assert acct["seat"] == {"kind": "floating", "org_id": org, "org_name": "Studio A"}


def test_licence_events_recorded(client, monkeypatch):
    clk = Clock(monkeypatch)
    h = signup(client)
    link = _start_link(client)
    assert _approve(client, h, link["link_code"]).status_code == 200  # link.approved
    one = activated(client, h, FP1)  # device.activated
    two = activated(client, h, FP2)  # device.activated
    assert activate(client, h, FP3).status_code == 409  # seat.device_limit
    assert activate(client, h, FP3, replace=one["device_id"]).status_code == 201  # activated + replaced
    assert client.delete(f"/licence/devices/{two['device_id']}", headers=session(h)).status_code == 200  # revoked
    clk.advance(seconds=1)
    four = activated(client, h, fp("machine-4"))  # device.activated
    res = client.post("/licence/trial", json={"plan": "pro"}, headers=bearer(four["device_token"]))
    assert res.status_code == 201  # trial.started

    counts = {}
    for e in _events():
        counts[e.kind] = counts.get(e.kind, 0) + 1
    assert counts["link.approved"] == 1
    assert counts["seat.device_limit"] == 1
    assert counts["device.replaced"] == 1
    assert counts["device.revoked"] == 1
    assert counts["trial.started"] == 1
    assert counts["device.activated"] == 4  # FP1, FP2, FP3 (replacing FP1), machine-4
    revoked = _events("device.revoked")[0]
    assert revoked.details == {"reason": "removed"} and revoked.user_id == _user_id(client, h)
    # No secrets in the log.
    dumped = json.dumps([e.details for e in _events()])
    assert link["poll_secret"] not in dumped and one["device_token"] not in dumped and FP1 not in dumped


def test_licence_keys_published(client):
    keys = client.get("/licence/keys", headers=CONTRACT).json()["keys"]
    by_kid = {k["kid"]: k for k in keys}
    assert by_kid[TEST_KEY["kid"]] == {
        "kid": TEST_KEY["kid"], "alg": "Ed25519", "use": "entitlement", "public_key": TEST_KEY["public_key"],
    }
    rel = [k for k in keys if k["use"] == "release"]
    assert rel and all(k["kid"].startswith("rel-") and len(k["public_key"]) == 43 for k in rel)
    # Only public halves: nothing like a seed appears.
    assert TEST_KEY["private_key"] not in json.dumps(keys)


def test_licence_unavailable_without_signing_key(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "licence_signing_key", "")
    h = signup(client)
    error_of(activate(client, h), 503, "unavailable")
    keys = client.get("/licence/keys", headers=CONTRACT).json()["keys"]
    assert all(k["use"] == "release" for k in keys)


def test_users_get_author_id_once(client):
    h = signup(client)
    dev = activated(client, h)
    with SessionLocal() as db:
        author = db.scalar(select(User.author_id))
    client.get("/licence/account", headers=bearer(dev["device_token"]))
    with SessionLocal() as db:
        assert db.scalar(select(User.author_id)) == author
