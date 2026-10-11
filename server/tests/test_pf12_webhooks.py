"""Webhooks (PF12): endpoints per account, Standard Webhooks signatures, the
retry schedule, the delivery log, re-send, disabling after five days, and the
events the features cause."""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app import mail
from app.config import get_settings
from app.database import SessionLocal
from app.licence import clock
from app.webhooks import delivery, events, signing, urls
from app.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent, WebhookPendingOps

from .conftest import signup
from .pf12_helpers import PL, ROOT, RJ, SB, kh, make_key, node
from .project_helpers import Person, delta_op, hex32, pushed
from .project_helpers import create as create_project
from .share_helpers import published

# The Standard Webhooks specification's example (spec/standard-webhooks.md).
VECTOR = {
    "secret": "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw",
    "id": "msg_p5jXN8AQM9LWM0D4loKWxJek",
    "timestamp": 1614265330,
    "body": '{"test": 2432232314}',
    "signature": "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE=",
}
HOSTS = {
    "hooks.example.com": ["93.184.216.34"],
    "inside.example.com": ["10.0.0.7"],
    "mixed.example.com": ["93.184.216.34", "127.0.0.1"],
}


@pytest.fixture()
def resolver(monkeypatch):
    def fake(host: str) -> list[str]:
        if host in HOSTS:
            return HOSTS[host]
        raise OSError("no such host")

    monkeypatch.setattr(urls, "resolve", fake)
    return HOSTS


class Receiver:
    """Where deliveries go in tests: an httpx.MockTransport that records them."""

    def __init__(self) -> None:
        self.status = 200
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status)

    def bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests]


@pytest.fixture()
def receiver(monkeypatch):
    r = Receiver()
    monkeypatch.setattr(delivery, "client_factory", lambda: httpx.Client(transport=httpx.MockTransport(r.handler)))
    return r


def hook(client, key: dict, events_: list[str], url: str = "https://hooks.example.com/truebex") -> dict:
    res = client.post("/v1/webhooks", json={"url": url, "events": events_}, headers=kh(key))
    assert res.status_code == 201, res.text
    return res.json()


def run(now: datetime | None = None) -> int:
    with SessionLocal() as db:
        events.flush_ops(db, now)
        return delivery.deliver_due(db, now)


def deliveries(endpoint_id: str) -> list[WebhookDelivery]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint_id).order_by(WebhookDelivery.attempt)
            ).unique()
        )


# --- endpoints ----------------------------------------------------------------------------------


def test_webhooks_crud_and_https_only(client, resolver, monkeypatch):
    session = signup(client)
    key = make_key(client, session, ["webhooks:manage"])
    # 401 without a key; 403 without the scope.
    assert client.get("/v1/webhooks").status_code == 401
    reader = make_key(client, session, name="Reader")
    assert client.get("/v1/webhooks", headers=kh(reader)).json()["data"]["needed"] == "webhooks:manage"

    made = hook(client, key, ["share.published", "project.ops_appended"])
    assert made["secret"].startswith("whsec_") and len(made["secret"]) > 30
    assert made["events"] == ["project.ops_appended", "share.published"] and made["active"] is True
    eid = made["endpoint_id"]
    listed = client.get("/v1/webhooks", headers=kh(key)).json()
    assert [e["endpoint_id"] for e in listed["endpoints"]] == [eid] and "secret" not in listed["endpoints"][0]
    assert listed["events"] == list(events.EVENT_TYPES)
    with SessionLocal() as db:  # sealed, not stored in the clear
        stored = db.get(WebhookEndpoint, eid)
        assert made["secret"] not in stored.secret_enc and signing.unseal(stored.secret_enc) == made["secret"]

    res = client.patch(f"/v1/webhooks/{eid}", json={"events": ["job.failed"], "description": "CI"}, headers=kh(key))
    assert res.status_code == 200 and res.json()["events"] == ["job.failed"] and res.json()["description"] == "CI"
    off = client.patch(f"/v1/webhooks/{eid}", json={"active": False}, headers=kh(key)).json()
    assert off["active"] is False and off["disabled_reason"] == "owner"
    on = client.patch(f"/v1/webhooks/{eid}", json={"active": True}, headers=kh(key)).json()
    assert on["active"] is True and on["disabled_reason"] is None

    # https only, public addresses only; validation failures are 422.
    for url in (
        "http://hooks.example.com/x",
        "https://10.0.0.5/x",
        "https://127.0.0.1/x",
        "https://[::1]/x",
        "https://localhost/x",
        "https://inside.example.com/x",
        "https://mixed.example.com/x",
        "https://nowhere.example.com/x",
        "https://user:pass@hooks.example.com/x",
        "ftp://hooks.example.com/x",
        "hooks.example.com/x",
    ):
        res = client.post("/v1/webhooks", json={"url": url, "events": ["job.failed"]}, headers=kh(key))
        assert res.status_code == 422, url
        assert res.json()["code"] == "validation_failed" and res.json()["data"]["fields"][0]["field"] == "url", url
    for bad in ([], ["job.exploded"]):
        res = client.post("/v1/webhooks", json={"url": "https://hooks.example.com/y", "events": bad}, headers=kh(key))
        assert res.status_code == 422, bad
    assert client.patch(f"/v1/webhooks/{eid}", json={"url": "http://hooks.example.com/"}, headers=kh(key)).status_code == 422

    # Local testing only: http://127.0.0.1 with WEBHOOKS_ALLOW_HTTP_LOCAL.
    monkeypatch.setattr(get_settings(), "webhooks_allow_http_local", True)
    local = hook(client, key, ["job.failed"], url="http://127.0.0.1:9900/")
    assert local["url"] == "http://127.0.0.1:9900/"
    res = client.post("/v1/webhooks", json={"url": "http://10.0.0.5/", "events": ["job.failed"]}, headers=kh(key))
    assert res.status_code == 422

    # Another account sees none of them.
    other = make_key(client, signup(client, "other@example.com"), ["webhooks:manage"])
    assert client.patch(f"/v1/webhooks/{eid}", json={"active": False}, headers=kh(other)).status_code == 404
    assert client.get("/v1/webhooks", headers=kh(other)).json()["endpoints"] == []

    # Delete.
    assert client.delete(f"/v1/webhooks/{eid}", headers=kh(key)).status_code == 204
    assert [e["endpoint_id"] for e in client.get("/v1/webhooks", headers=kh(key)).json()["endpoints"]] == [local["endpoint_id"]]


def test_webhooks_dashboard_routes(client, resolver, receiver):
    """The website manages endpoints with a session, and may reveal a secret."""
    session = signup(client)
    assert client.get("/webhooks").status_code == 401
    made = client.post("/webhooks", json={"url": "https://hooks.example.com/a", "events": ["share.published"]}, headers=session)
    assert made.status_code == 201, made.text
    eid, secret = made.json()["endpoint_id"], made.json()["secret"]
    listed = client.get("/webhooks", headers=session).json()
    assert listed["endpoints"][0]["endpoint_id"] == eid and listed["descriptions"]["share.published"]
    revealed = client.get(f"/webhooks/{eid}/secret", headers=session)
    assert revealed.json()["secret"] == secret and revealed.headers["Cache-Control"] == "no-store"
    rotated = client.post(f"/webhooks/{eid}/secret/rotate", headers=session).json()["secret"]
    assert rotated != secret and client.get(f"/webhooks/{eid}/secret", headers=session).json()["secret"] == rotated

    # A test event: delivered, signed with the new secret, in the log.
    queued = client.post(f"/webhooks/{eid}/test", headers=session)
    assert queued.status_code == 201 and queued.json()["status"] == "pending"
    assert run() == 1
    req = receiver.requests[0]
    signing.verify(rotated, dict(req.headers), req.content)
    assert receiver.bodies()[0]["type"] == "webhook.test"
    log = client.get(f"/webhooks/{eid}/deliveries", headers=session).json()["deliveries"]
    assert log[0]["status"] == "succeeded" and log[0]["response_code"] == 200 and log[0]["event_type"] == "webhook.test"
    # Re-send: a new attempt of the same event, the same webhook-id.
    again = client.post(f"/webhooks/{eid}/deliveries/{log[0]['delivery_id']}/resend", headers=session)
    assert again.status_code == 201 and again.json()["manual"] is True
    assert run() == 1
    assert receiver.requests[1].headers["webhook-id"] == req.headers["webhook-id"]
    assert client.delete(f"/webhooks/{eid}", headers=session).status_code == 204


# --- signing ------------------------------------------------------------------------------------


def test_webhooks_signature_standard_vectors(client, resolver, receiver):
    body = VECTOR["body"].encode()
    # Our signer reproduces the specification's vector …
    assert signing.sign(VECTOR["secret"], VECTOR["id"], VECTOR["timestamp"], body) == VECTOR["signature"]
    headers = {"webhook-id": VECTOR["id"], "webhook-timestamp": str(VECTOR["timestamp"]), "webhook-signature": VECTOR["signature"]}
    signing.verify(VECTOR["secret"], headers, body, now=VECTOR["timestamp"] + 10)
    # … refuses a changed body, an old timestamp, and accepts one of several signatures.
    with pytest.raises(signing.SignatureError):
        signing.verify(VECTOR["secret"], headers, body + b" ", now=VECTOR["timestamp"])
    with pytest.raises(signing.SignatureError):
        signing.verify(VECTOR["secret"], headers, body, now=VECTOR["timestamp"] + 301)
    rotated = {**headers, "webhook-signature": f"v1,bm90IHRoaXMgb25l {VECTOR['signature']}"}
    signing.verify(VECTOR["secret"], rotated, body, now=VECTOR["timestamp"])
    assert signing.new_secret().startswith("whsec_")

    # The Python SDK's helper verifies the same vector.
    sys.path.insert(0, str(ROOT / "sdks" / "python"))
    try:
        import truebex

        payload = truebex.verify_webhook(VECTOR["secret"], headers, body, now=VECTOR["timestamp"])
        assert payload == {"test": 2432232314}
        with pytest.raises(truebex.WebhookVerificationError):
            truebex.verify_webhook(VECTOR["secret"], headers, b'{"test": 1}', now=VECTOR["timestamp"])
    finally:
        sys.path.remove(str(ROOT / "sdks" / "python"))

    # The JavaScript SDK's helper verifies it too.
    exe = node()
    if exe:
        script = (
            "import { verifyWebhook } from './sdks/js/src/webhooks.mjs';"
            f"const v = {json.dumps(VECTOR)};"
            "const h = {'webhook-id': v.id, 'webhook-timestamp': String(v.timestamp), 'webhook-signature': v.signature};"
            "const ok = await verifyWebhook(v.secret, h, v.body, { now: v.timestamp });"
            "let bad = false; try { await verifyWebhook(v.secret, h, v.body + ' ', { now: v.timestamp }); } catch { bad = true; }"
            "console.log(JSON.stringify({ ok, bad }));"
        )
        res = subprocess.run(
            [exe, "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60
        )
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout) == {"ok": {"test": 2432232314}, "bad": True}

    # A real delivery verifies with the endpoint's secret, with every header named.
    session = signup(client)
    key = make_key(client, session, ["webhooks:manage"])
    made = hook(client, key, ["job.failed"])
    client.post(f"/v1/webhooks/{made['endpoint_id']}/test", headers=kh(key))
    run()
    req = receiver.requests[0]
    assert req.headers["content-type"] == "application/json" and req.headers["user-agent"].startswith("Truebex-Webhooks/")
    assert req.headers["webhook-id"].startswith("msg_") and req.headers["webhook-signature"].startswith("v1,")
    signing.verify(made["secret"], dict(req.headers), req.content)


# --- retries --------------------------------------------------------------------------------------


def test_webhooks_retry_schedule_and_disable(client, resolver, receiver, monkeypatch):
    monkeypatch.setattr(delivery, "JITTER", 0.0)
    receiver.status = 500
    session = signup(client)
    key = make_key(client, session, ["webhooks:manage"])
    made = hook(client, key, ["job.failed"])
    eid = made["endpoint_id"]
    t0 = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        endpoint = db.get(WebhookEndpoint, eid)
        events.emit(db, [endpoint.account_id], "job.failed", {"job_id": "x"}, now=t0)

    # Ten attempts: immediately, then 5 s, 5 min, 30 min, 2 h, 5 h, 10 h, 14 h, 20 h, 24 h.
    now = t0
    for attempt in range(1, 11):
        assert run(now - timedelta(seconds=1)) == 0 or attempt == 1  # nothing early
        run(now)
        rows = deliveries(eid)
        assert len(rows) == min(attempt + 1, 10), attempt
        last = rows[attempt - 1]
        assert last.attempt == attempt and last.status == "failed" and last.response_code == 500
        if attempt < 10:
            nxt = rows[attempt]
            wait = clock.aware(nxt.next_attempt_at) - now
            assert wait == timedelta(seconds=delivery.SCHEDULE_S[attempt]), attempt
            now = clock.aware(nxt.next_attempt_at)
    assert len(receiver.requests) == 10
    assert run(now + timedelta(days=2)) == 0 and len(deliveries(eid)) == 10  # no eleventh
    log = client.get(f"/v1/webhooks/{eid}/deliveries", headers=kh(key)).json()["deliveries"]
    assert [d["attempt"] for d in log] == list(range(10, 0, -1)) and {d["status"] for d in log} == {"failed"}
    assert client.get(f"/v1/webhooks/{eid}/deliveries", params={"status": "succeeded"}, headers=kh(key)).json()["deliveries"] == []

    # Jitter keeps each wait within ±10 %.
    monkeypatch.setattr(delivery, "JITTER", 0.1)
    lo = delivery.delay_before(3, rng=lambda: 0.0)
    hi = delivery.delay_before(3, rng=lambda: 1.0)
    assert lo == timedelta(seconds=270) and hi == timedelta(seconds=330)

    # Failing for five days → switched off, one e-mail; less than five days → still on.
    mail.OUTBOX.clear()
    with SessionLocal() as db:
        assert clock.aware(db.get(WebhookEndpoint, eid).failing_since) == t0
        assert delivery.disable_failing(db, t0 + timedelta(days=4, hours=23)) == 0
        assert delivery.disable_failing(db, t0 + timedelta(days=5)) == 1
        assert delivery.disable_failing(db, t0 + timedelta(days=6)) == 0
        endpoint = db.get(WebhookEndpoint, eid)
        assert endpoint.active is False and endpoint.disabled_reason == "failing"
    sent = [m for m in mail.OUTBOX if m.template == "webhook_disabled"]
    assert len(sent) == 1 and sent[0].to == "dev@example.com" and made["url"] in sent[0].text
    # A disabled endpoint takes no re-send until it is switched on; a success clears the failure.
    first = log[-1]["delivery_id"]
    assert client.post(f"/v1/webhooks/{eid}/deliveries/{first}/resend", headers=kh(key)).json()["code"] == "endpoint_disabled"
    client.patch(f"/v1/webhooks/{eid}", json={"active": True}, headers=kh(key))
    receiver.status = 204
    resent = client.post(f"/v1/webhooks/{eid}/deliveries/{first}/resend", headers=kh(key)).json()
    run()
    log = client.get(f"/v1/webhooks/{eid}/deliveries", headers=kh(key)).json()["deliveries"]
    assert next(d for d in log if d["delivery_id"] == resent["delivery_id"])["status"] == "succeeded"
    with SessionLocal() as db:
        assert db.get(WebhookEndpoint, eid).failing_since is None


def test_webhooks_refuse_private_address_at_delivery(client, resolver, monkeypatch):
    """A name that later resolves to a private address fails that attempt (DNS
    rebinding): the delivery's own connection (PF14b's, not a mock transport)
    resolves it, refuses it and dials nothing. test_pf14b_outbound.py follows
    a delivery over that connection end to end."""
    from app.net import outbound

    dialled = []
    monkeypatch.setattr(outbound, "resolve", urls.resolve)  # the HOSTS table
    monkeypatch.setattr(outbound, "connect", lambda address, port, *a: dialled.append(address))
    session = signup(client)
    key = make_key(client, session, ["webhooks:manage"])
    monkeypatch.setitem(HOSTS, "rebind.example.com", ["93.184.216.40"])
    made = hook(client, key, ["job.failed"], url="https://rebind.example.com/x")
    monkeypatch.setitem(HOSTS, "rebind.example.com", ["192.168.1.20"])
    client.post(f"/v1/webhooks/{made['endpoint_id']}/test", headers=kh(key))
    run()
    assert dialled == []
    row = deliveries(made["endpoint_id"])[0]
    assert row.status == "failed" and row.error.startswith("refused")


# --- events -------------------------------------------------------------------------------------


def test_webhooks_ops_appended_debounced(client, resolver, receiver):
    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ["projects:read", "projects:write", "webhooks:manage"])
    made = hook(client, key, ["project.ops_appended"])
    pid = create_project(client, owner.dev)["project_id"]
    t0 = clock.now()

    # Three pushes within 30 s: two from the app, one from the key.
    pushed(client, owner.dev, pid, owner.replica, [delta_op(owner.author_id, [hex32()])])
    op = delta_op(owner.author_id, [hex32()], base_seq=1)
    del op["author"], op["author_kind"]
    assert client.post(f"/v1/projects/{pid}/ops", json={"replica_id": hex32(), "ops": [op]}, headers=kh(key, **PL)).status_code == 200
    pushed(client, owner.dev, pid, owner.replica, [delta_op(owner.author_id, [hex32()], base_seq=2)])

    assert run(t0 + timedelta(seconds=5)) == 0 and receiver.requests == []  # the window is open
    with SessionLocal() as db:
        assert db.get(WebhookPendingOps, pid).last_seq == 3
    assert run(t0 + timedelta(seconds=31)) == 1
    assert len(receiver.requests) == 1
    body = receiver.bodies()[0]
    assert body["type"] == "project.ops_appended"
    data = body["data"]
    assert (data["project_id"], data["first_seq"], data["last_seq"], data["count"]) == (pid, 1, 3, 3)
    assert {"author": owner.author_id, "author_kind": "person"} in data["authors"]
    assert {"author": format(key["id"], "032x"), "author_kind": "agent"} in data["authors"]
    signing.verify(made["secret"], dict(receiver.requests[0].headers), receiver.requests[0].content)
    with SessionLocal() as db:
        assert db.get(WebhookPendingOps, pid) is None
    # A project nobody listens to opens no window.
    quiet = create_project(client, Person(client, "quiet@example.com").dev)["project_id"]
    other = Person(client, "other@example.com")
    pid2 = create_project(client, other.dev)["project_id"]
    pushed(client, other.dev, pid2, other.replica, [delta_op(other.author_id, [hex32()])])
    with SessionLocal() as db:
        assert db.get(WebhookPendingOps, pid2) is None and db.get(WebhookPendingOps, quiet) is None


def test_webhooks_events_from_features(client, resolver, receiver):
    """A version, an invitation, a share going live and a failed job reach the
    accounts that subscribed, with the resource as its contract shapes it."""
    from .render_helpers import admin as admin_headers, claim, issue_worker, project, submitted, wk

    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ["projects:read", "projects:write", "webhooks:manage"])
    hook(client, key, ["project.version_created", "project.member_added", "share.published", "job.failed", "job.succeeded"])
    pid, head = project(client, owner, ops=1)

    # project.member_added (5.14) and project.version_created (5.11).
    res = client.post(f"/v1/projects/{pid}/members", json={"email": "friend@example.com", "role": "editor"}, headers=kh(key, **PL))
    assert res.status_code == 201, res.text
    snap = client.get(f"/projects/{pid}/snapshots/latest", headers=owner.dev).json()
    res = client.post(
        f"/projects/{pid}/versions", json={"name": "Issue A", "at_seq": 0, "snapshot_id": snap["snapshot_id"]}, headers=owner.dev
    )
    assert res.status_code == 201, res.text

    # share.published (5.5).
    share = published(client, owner.token)

    # job.failed: a worker gives up.
    token = issue_worker(client, admin_headers(client))
    job = submitted(client, {"Authorization": f"Bearer {owner.token}", **RJ}, project_id=pid, at_seq=head)
    claimed = claim(client, token).json()
    res = client.post(
        f"/workers/jobs/{job['job_id']}/fail",
        json={"lease_id": claimed["lease_id"], "code": "bad_input", "message": "No snapshot", "retryable": False},
        headers=wk(token),
    )
    assert res.status_code == 200 and res.json()["state"] == "failed"

    run()
    got = {b["type"]: b["data"] for b in receiver.bodies()}
    assert set(got) == {"project.member_added", "project.version_created", "share.published", "job.failed"}
    assert got["project.member_added"]["project_id"] == pid and got["project.member_added"]["email"] == "friend@example.com"
    assert got["project.version_created"]["name"] == "Issue A" and got["project.version_created"]["project_id"] == pid
    assert got["share.published"]["share_id"] == share["share_id"] and got["share.published"]["state"] == "live"
    assert got["job.failed"]["job_id"] == job["job_id"] and got["job.failed"]["error"]["code"] == "bad_input"
    # Nothing was stored for the account that has no endpoint (the worker's admin).
    with SessionLocal() as db:
        assert {e.type for e in db.scalars(select(WebhookEvent))} == set(got)


def test_webhooks_market_order_and_feed_events(client, resolver, receiver, monkeypatch):
    from .market_helpers import load, order_body, with_contract
    from .supplier_helpers import FEED_CSV, no_internet, post_feed, run_feeds, supplier_key, verified

    # The buyer hears about its request for quote, and each change of state.
    load()
    buyer = signup(client, "buyer@example.com")
    key = make_key(client, buyer, ["webhooks:manage"])
    hook(client, key, ["market.order.updated"])
    res = client.post("/market/orders", json=order_body("quote"), headers=with_contract(buyer))
    assert res.status_code == 201, res.text
    order_id = res.json()["order_id"]
    assert client.post(f"/market/orders/{order_id}/cancel", headers=with_contract(buyer)).status_code == 200
    run()
    updates = [b["data"] for b in receiver.bodies() if b["type"] == "market.order.updated"]
    # Deliveries go out in parallel (delivery.PARALLEL), so the two may arrive in either order.
    assert sorted(u["state"] for u in updates) == ["cancelled", "submitted"] and {u["order_id"] for u in updates} == {order_id}

    # A supplier's members hear when a feed run ends.
    no_internet(monkeypatch)
    h, sid = verified(client)
    owner_key = make_key(client, h, ["webhooks:manage"], name="Hooks")
    hook(client, owner_key, ["market.feed.completed"])
    feed_id = post_feed(client, supplier_key(client, h), FEED_CSV).json()["feed_id"]
    run_feeds()
    run()
    done = [b["data"] for b in receiver.bodies() if b["type"] == "market.feed.completed"]
    assert len(done) == 1 and done[0]["feed_id"] == feed_id and done[0]["state"] == "done" and done[0]["supplier_id"] == sid


def test_webhooks_visits_digest(client, resolver, receiver):
    from app.shares import service as shares_service
    from app.shares.models import Share

    from .share_helpers import device_token

    token, session = device_token(client)
    share = published(client, token)
    key = make_key(client, session, ["webhooks:manage"])
    hook(client, key, ["share.visits_daily"])
    yesterday = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        row = db.get(Share, share["share_id"])
        for visitor in ("a" * 32, "a" * 32, "b" * 32):
            shares_service.record_visit(db, row, visitor, now=yesterday)
    today_early = datetime(2026, 10, 11, 0, 5, tzinfo=timezone.utc)
    today = datetime(2026, 10, 11, 0, 12, tzinfo=timezone.utc)
    with SessionLocal() as db:
        assert events.digest(db, today_early) == 0  # before 00:10 UTC
        assert events.digest(db, today) == 1
        assert events.digest(db, today + timedelta(hours=3)) == 0  # once a day
    run(today)
    body = receiver.bodies()[0]
    assert body["type"] == "share.visits_daily"
    assert body["data"]["day"] == "2026-10-10" and body["data"]["visits"] == 3 and body["data"]["unique"] == 2
    assert body["data"]["shares"][0]["share_id"] == share["share_id"]


def test_webhooks_purge_after_30_days(client, resolver, receiver):
    session = signup(client)
    key = make_key(client, session, ["webhooks:manage"])
    made = hook(client, key, ["job.failed"])
    old = datetime(2026, 9, 1, tzinfo=timezone.utc)
    with SessionLocal() as db:
        events.emit(db, [db.get(WebhookEndpoint, made["endpoint_id"]).account_id], "job.failed", {"job_id": "y"}, now=old)
    run(old)
    with SessionLocal() as db:
        assert delivery.purge(db, old + timedelta(days=29)) == 0
        assert delivery.purge(db, old + timedelta(days=31)) == 1
        assert db.scalars(select(WebhookDelivery)).all() == []


def test_webhook_jobs_registered():
    from app import tasks

    names = tasks.registered()
    for name in ("webhooks.deliver", "webhooks.digest", "webhooks.disable", "webhooks.purge"):
        assert name in names
    assert tasks.jobs()["webhooks.deliver"].seconds == 5


def test_webhook_echo_receives_a_real_delivery(client, monkeypatch, capsys):
    """scripts/webhook_echo.py verifies what the API really sends over HTTP
    (the human test's receiver), with WEBHOOKS_ALLOW_HTTP_LOCAL."""
    import socket
    import threading
    from http.server import ThreadingHTTPServer

    from scripts import webhook_echo

    assert webhook_echo.verify(VECTOR["secret"], {"webhook-id": VECTOR["id"], "webhook-timestamp": str(VECTOR["timestamp"]),
                               "webhook-signature": VECTOR["signature"]}, VECTOR["body"].encode(), now=VECTOR["timestamp"]) is None
    monkeypatch.setattr(get_settings(), "webhooks_allow_http_local", True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    session = signup(client)
    key = make_key(client, session, ["webhooks:manage"])
    made = hook(client, key, ["job.failed"], url=f"http://127.0.0.1:{port}/")
    server = ThreadingHTTPServer(("127.0.0.1", port), webhook_echo.make_handler(made["secret"]))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client.post(f"/v1/webhooks/{made['endpoint_id']}/test", headers=kh(key))
        assert run() == 1
        out = capsys.readouterr().out
        assert "webhook.test" in out and "signature valid" in out
        log = client.get(f"/v1/webhooks/{made['endpoint_id']}/deliveries", headers=kh(key)).json()["deliveries"]
        assert log[0]["status"] == "succeeded" and log[0]["response_code"] == 204
        # A wrong secret on the receiver's side: 401, the delivery fails and is retried later.
        server.RequestHandlerClass = webhook_echo.make_handler(signing.new_secret())
        client.post(f"/v1/webhooks/{made['endpoint_id']}/test", headers=kh(key))
        run()
        assert "signature INVALID" in capsys.readouterr().out
        log = client.get(f"/v1/webhooks/{made['endpoint_id']}/deliveries", headers=kh(key)).json()["deliveries"]
        assert {d["status"] for d in log} == {"succeeded", "failed", "pending"}
    finally:
        server.shutdown()
