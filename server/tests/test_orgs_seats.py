"""Named and floating seats reaching the entitlement (PF3; contract
licence-api §6.1, 5.5, 5.7, 5.11, §7 `no_seat_available`, `not_floating`)."""

import threading
from datetime import timedelta

from sqlalchemy import select

from app import tasks
from app.database import SessionLocal
from app.licence import clock
from app.models import Subscription
from app.orgs import seats as org_seats
from app.orgs.models import FloatingLease

from .conftest import signup
from .licence_helpers import CONTRACT, FP1, FP2, FP3, Clock, activate, activated, bearer, error_of, fp, refresh, ts
from .org_helpers import (  # noqa: F401  (_clean_mail_and_caches is an autouse fixture)
    _clean_mail_and_caches,
    assign,
    envelope,
    grant,
    join,
    make_org,
    me,
    set_floating,
)


def _team(client, seats=2, floating=0):
    """An owner with a Team organisation of `seats` seats, `floating` of them floating."""
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    grant(org["slug"], "team", seats)
    if floating:
        set_floating(client, h, org["id"], floating)
    return h, org


def _doc(res) -> dict:
    assert res.status_code in (200, 201), res.text
    return res.json()["entitlement"]["document"]


def _release(client, token):
    return client.post("/licence/release", headers=bearer(token))


def test_orgs_named_seat_assignment(client):
    h, org = _team(client, seats=1)
    a = join(client, h, org["id"], "a@example.com")
    b = join(client, h, org["id"], "b@example.com")
    a_id, b_id = me(client, a)["id"], me(client, b)["id"]

    # Before a seat: the member's own Free plan.
    dev = activated(client, a)
    assert dev["entitlement"]["document"]["plan"] == "free"

    res = assign(client, h, org["id"], a_id, "named")
    assert res.status_code == 200 and res.json() == {"user_id": a_id, "seat_kind": "named"}
    doc = _doc(refresh(client, dev["device_token"]))
    assert doc["plan"] == "team" and doc["seat_kind"] == "named" and doc["account"]["org_id"] == org["id"]
    issued = ts(doc["issued_at"])
    assert ts(doc["refresh_after"]) - issued == timedelta(hours=24) and ts(doc["expires_at"]) - issued == timedelta(days=14)
    acct = client.get("/licence/account", headers=bearer(dev["device_token"])).json()
    assert acct["seat"] == {"kind": "named", "org_id": org["id"], "org_name": "Studio North"}
    assert acct["seats"] == {"total": 1, "assigned": 1} and acct["plan"] == "team"
    # The organisation's tier never lands in the personal plan cache.
    assert me(client, a)["plan"] == "free"

    # The one seat is taken.
    body = envelope(assign(client, h, org["id"], b_id, "named"), 409, "no_seat_left")
    assert body["data"]["total"] == 1
    envelope(assign(client, h, org["id"], b_id, "floating"), 409, "no_seat_left")
    envelope(assign(client, a, org["id"], b_id, "named"), 403, "forbidden")
    envelope(client.put(f"/orgs/{org['id']}/seats/{b_id}", json={"kind": "named"}), 401, "unauthenticated")
    envelope(assign(client, h, org["id"], b_id, "gold"), 422, "validation_failed")
    envelope(assign(client, h, org["id"], 9999, "named"), 404, "not_found")

    # Unassigning returns the member to their own plan.
    assert assign(client, h, org["id"], a_id, "none").json()["seat_kind"] == "none"
    assert _doc(refresh(client, dev["device_token"]))["plan"] == "free"
    assert assign(client, h, org["id"], b_id, "named").status_code == 200

    seats = client.get(f"/orgs/{org['id']}/seats", headers=h).json()
    assert seats["tier"] == "team" and seats["total"] == 1 and seats["named"] == {"total": 1, "assigned": 1}


def test_orgs_named_seat_device_limit(client):
    h, org = _team(client, seats=2)
    a = join(client, h, org["id"], "a@example.com", seat="named")
    one = activated(client, a, FP1)
    two = activated(client, a, FP2)
    assert _doc(refresh(client, one["device_token"]))["limits"]["devices"] == 2
    body = error_of(activate(client, a, FP3), 409, "device_limit")
    assert body["data"]["limit"] == 2 and {d["device_id"] for d in body["data"]["devices"]} == {
        one["device_id"], two["device_id"],
    }
    # The limit is per member: the owner's devices do not count.
    assert activate(client, h, fp("owner-pc")).status_code == 201


def test_licence_floating_lease_refresh_and_release(client, monkeypatch):
    clk = Clock(monkeypatch)
    h, org = _team(client, seats=2, floating=1)
    b = join(client, h, org["id"], "b@example.com", seat="floating")
    dev = activated(client, b, FP2, "Test PC 2")
    doc = dev["entitlement"]["document"]
    issued = ts(doc["issued_at"])
    assert doc["plan"] == "team" and doc["seat_kind"] == "floating" and doc["account"]["org_id"] == org["id"]
    assert ts(doc["refresh_after"]) - issued == timedelta(minutes=30)
    assert ts(doc["expires_at"]) - issued == timedelta(hours=2)

    seats = client.get(f"/orgs/{org['id']}/seats", headers=h).json()
    assert seats["floating"]["total"] == 1 and seats["floating"]["in_use"] == 1
    lease = seats["floating"]["leases"][0]
    assert lease["user"]["email"] == "b@example.com" and lease["device"]["name"] == "Test PC 2"
    assert lease["expires_at"] == doc["expires_at"]

    # A second 5.5 renews the same lease to 2 h from now.
    clk.advance(minutes=31)
    again = _doc(refresh(client, dev["device_token"], FP2))
    assert ts(again["expires_at"]) - ts(again["issued_at"]) == timedelta(hours=2)
    with SessionLocal() as db:
        rows = list(db.scalars(select(FloatingLease)))
        assert len(rows) == 1 and clock.rfc3339(rows[0].expires_at) == again["expires_at"]

    # 5.11 hands it back: the seat is free, and repeating is harmless.
    res = _release(client, dev["device_token"])
    assert res.status_code == 204 and res.headers["X-Truebex-Contract"] == "licence-api/1.0"
    assert client.get(f"/orgs/{org['id']}/seats", headers=h).json()["floating"]["in_use"] == 0
    assert _release(client, dev["device_token"]).status_code == 204
    # The next 5.5 leases again.
    assert _doc(refresh(client, dev["device_token"], FP2))["seat_kind"] == "floating"
    assert client.get(f"/orgs/{org['id']}/seats", headers=h).json()["floating"]["in_use"] == 1

    error_of(client.post("/licence/release", headers=CONTRACT), 401, "unauthenticated")
    session = {"Authorization": h["Authorization"], **CONTRACT}
    error_of(client.post("/licence/release", headers=session), 401, "unauthenticated")
    error_of(client.post("/licence/release", headers={**bearer(dev["device_token"]),
                                                     "X-Truebex-Contract": "licence-api/2.0"}), 400, "contract_version")

    # Removing the device hands its lease back too.
    mine = {"Authorization": b["Authorization"], **CONTRACT}
    assert client.delete(f"/licence/devices/{dev['device_id']}", headers=mine).status_code == 200
    assert client.get(f"/orgs/{org['id']}/seats", headers=h).json()["floating"]["in_use"] == 0


def test_licence_release_not_floating(client):
    h, org = _team(client, seats=2)
    a = join(client, h, org["id"], "a@example.com", seat="named")
    dev = activated(client, a)
    error_of(_release(client, dev["device_token"]), 409, "not_floating")
    personal = activated(client, signup(client, "solo@example.com"), FP3)
    error_of(_release(client, personal["device_token"]), 409, "not_floating")


def test_licence_floating_pool_full(client):
    h, org = _team(client, seats=2, floating=1)
    b = join(client, h, org["id"], "b@example.com", seat="floating")
    c = join(client, h, org["id"], "c@example.com", seat="floating")
    b_dev = activated(client, b, FP2, "Test PC 2")
    assert b_dev["entitlement"]["document"]["seat_kind"] == "floating"

    # Activation still hands c a device token (with the personal Free seat)...
    c_dev = activated(client, c, FP3, "Test PC 3")
    assert c_dev["entitlement"]["document"]["plan"] == "free"
    # ...and 5.5 says the pool is full.
    body = error_of(refresh(client, c_dev["device_token"], FP3), 409, "no_seat_available")
    assert body["detail"] == "All 1 floating seat is in use. Try again when someone closes Truebex."
    assert body["data"]["total"] == 1 and "b@example.com" not in str(body)

    # The console names the holder, for admins only.
    lease = client.get(f"/orgs/{org['id']}/seats", headers=h).json()["floating"]["leases"]
    assert [(l["user"]["email"], l["device"]["name"]) for l in lease] == [("b@example.com", "Test PC 2")]
    envelope(client.get(f"/orgs/{org['id']}/seats", headers=c), 403, "forbidden")
    envelope(client.get(f"/orgs/{org['id']}/seats"), 401, "unauthenticated")

    # When b hands it back, c gets it.
    assert _release(client, b_dev["device_token"]).status_code == 204
    assert _doc(refresh(client, c_dev["device_token"], FP3))["seat_kind"] == "floating"
    error_of(refresh(client, b_dev["device_token"], FP2), 409, "no_seat_available")

    # Floating settings: at most the seats bought; named seats in use cap it.
    envelope(client.put(f"/orgs/{org['id']}/seats/settings", json={"floating": 3}, headers=h), 422, "validation_failed")
    envelope(client.put(f"/orgs/{org['id']}/seats/settings", json={"floating": -1}, headers=h), 422, "validation_failed")
    envelope(client.put(f"/orgs/{org['id']}/seats/settings", json={"floating": 1}, headers=c), 403, "forbidden")
    owner_id = me(client, h)["id"]
    assert assign(client, h, org["id"], owner_id, "named").status_code == 200
    envelope(client.put(f"/orgs/{org['id']}/seats/settings", json={"floating": 2}, headers=h), 409, "no_seat_left")


def test_licence_floating_race_last_seat(client, monkeypatch):
    h, org = _team(client, seats=2, floating=1)
    devs = []
    for n, email in enumerate(("b@example.com", "c@example.com")):
        member = join(client, h, org["id"], email)
        devs.append(activated(client, member, fp(f"race-{n}")))  # no seat yet: Free, no lease
        assert assign(client, h, org["id"], me(client, member)["id"], "floating").status_code == 200

    # Widen the window between "count the leases" and "insert one": without the
    # organisation row lock both requests would see a free seat.
    real_pool = org_seats.pool
    barrier = threading.Barrier(2, timeout=10)

    def slow_pool(db, organisation, now):
        result = real_pool(db, organisation, now)
        if threading.current_thread() is not threading.main_thread():
            try:
                barrier.wait(timeout=1)
            except threading.BrokenBarrierError:
                pass
        return result

    monkeypatch.setattr(org_seats, "pool", slow_pool)
    results: list[int] = []

    def take(n: int) -> None:
        results.append(refresh(client, devs[n]["device_token"], fp(f"race-{n}")).status_code)

    threads = [threading.Thread(target=take, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(results) == [200, 409]
    with SessionLocal() as db:
        open_rows = [r for r in db.scalars(select(FloatingLease)) if r.released_at is None]
        assert len(open_rows) == 1


def test_licence_lease_expiry_job(client, monkeypatch):
    clk = Clock(monkeypatch)
    h, org = _team(client, seats=2, floating=1)
    b = join(client, h, org["id"], "b@example.com", seat="floating")
    c = join(client, h, org["id"], "c@example.com", seat="floating")
    activated(client, b, FP2)  # takes the seat, then the laptop is closed
    c_dev = activated(client, c, FP3)
    assert c_dev["entitlement"]["document"]["seat_kind"] == "free"

    later = clk.advance(hours=2, seconds=1)
    assert "licence.leases.expire" in tasks.run_due(later, force=True)
    with SessionLocal() as db:
        lease = db.scalar(select(FloatingLease))
        assert lease.end_reason == "lapsed" and clock.aware(lease.released_at) == clock.aware(lease.expires_at)
    assert client.get(f"/orgs/{org['id']}/seats", headers=h).json()["floating"]["in_use"] == 0
    assert _doc(refresh(client, c_dev["device_token"], FP3))["seat_kind"] == "floating"
    kinds = [e["kind"] for e in client.get(f"/orgs/{org['id']}/audit?kind=lease", headers=h).json()["events"]]
    assert "lease.lapsed" in kinds and "lease.taken" in kinds


def test_orgs_seat_source_picks_best(client):
    h, org = _team(client, seats=2)
    a = join(client, h, org["id"], "a@example.com")
    a_id = me(client, a)["id"]
    # A personal Pro subscription of a's own.
    with SessionLocal() as db:
        db.add(Subscription(user_id=a_id, plan="pro", provider="stripe", status="active",
                            provider_subscription_id="sub_a"))
        db.commit()
    dev = activated(client, a)
    doc = dev["entitlement"]["document"]
    assert doc["plan"] == "pro" and doc["seat_kind"] == "personal" and doc["account"]["org_id"] is None

    # Personal Pro + named Team: Team ranks higher.
    assert assign(client, h, org["id"], a_id, "named").status_code == 200
    doc = _doc(refresh(client, dev["device_token"]))
    assert doc["plan"] == "team" and doc["seat_kind"] == "named" and doc["account"]["org_id"] == org["id"]
    assert me(client, a)["plan"] == "pro"  # the personal plan stays the personal plan

    # A full floating Team pool falls back to the personal Pro instead of 409.
    set_floating(client, h, org["id"], 1)
    assert assign(client, h, org["id"], a_id, "floating").status_code == 200
    holder = join(client, h, org["id"], "holder@example.com", seat="floating")
    assert activated(client, holder, fp("holder"))["entitlement"]["document"]["seat_kind"] == "floating"
    doc = _doc(refresh(client, dev["device_token"]))
    assert doc["plan"] == "pro" and doc["seat_kind"] == "personal"
