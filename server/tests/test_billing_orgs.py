"""PF3a: organisations buy and change seats through PF2.

Paddle's API is tests/mock_paddle.py served in-process (the `paddle`
fixture); Stripe calls are monkeypatched; webhooks are signed exactly as the
providers sign them (helpers from test_billing_pf2.py).
"""

import copy
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import stripe
from sqlalchemy import select

from app.billing import service
from app.config import get_settings
from app.database import SessionLocal
from app.models import Payment, Subscription
from app.plans import PLANS

from .conftest import checkout_body, signup
from .licence_helpers import activated, bearer, refresh
from .org_helpers import (  # noqa: F401  (_clean_mail_and_caches is an autouse fixture)
    _clean_mail_and_caches,
    envelope,
    join,
    make_org,
    me,
    set_floating,
)
from .test_billing import stripe_post, stripe_sub_event
from .test_billing_pf2 import paddle_post, txn_of


# --- helpers --------------------------------------------------------------------------


def _org(client):
    """An owner and their organisation."""
    owner = signup(client, "owner@example.com")
    return owner, make_org(client, owner)


def _roles(client):
    """An organisation with one person per role, and someone outside it."""
    owner, org = _org(client)
    billing = join(client, owner, org["id"], "billing@example.com", role="billing")
    admin = join(client, owner, org["id"], "admin@example.com", role="admin")
    member = join(client, owner, org["id"], "member@example.com")
    outsider = signup(client, "outsider@example.com")
    return org, {"owner": owner, "billing": billing, "admin": admin, "member": member, "outsider": outsider}


def org_checkout(client, h, org_id, **kw):
    kw.setdefault("tier", "team")
    kw.setdefault("interval", "year")  # Team is annual only (PF2a)
    kw.setdefault("seats", 3)
    res = client.post("/billing/checkout", json=checkout_body(org_id=org_id, **kw), headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def org_buy(client, h, paddle, org_id, deliver=True, **kw):
    """Checkout for the organisation, pay on the mock, deliver the webhooks."""
    co = org_checkout(client, h, org_id, **kw)
    events = paddle.pay(txn_of(co["url"]))
    if deliver:
        for ev in events:
            assert paddle_post(client, ev).status_code == 200
    return co, events


def org_subs(org_id) -> list[Subscription]:
    with SessionLocal() as db:
        return list(db.scalars(select(Subscription).where(Subscription.organisation_id == org_id)))


def payment(reference) -> Payment:
    with SessionLocal() as db:
        return db.scalar(select(Payment).where(Payment.reference == reference))


def team_price(paddle, interval="year", currency="GBP") -> dict:
    return next(
        p for p in paddle.STATE["prices"].values()
        if p["custom_data"]["tier"] == "team" and p["custom_data"]["founding"] == "0"
        and p["billing_cycle"]["interval"] == interval and p["unit_price"]["currency_code"] == currency
    )


def forged_sub(paddle, sub_id, custom, quantity=5, **extra) -> dict:
    """A subscription as Paddle reports one opened with Paddle.js and the
    public client token: our synced Team price, the buyer's own custom_data."""
    return {
        "id": sub_id, "status": "active", "customer_id": "ctm_forger", "currency_code": "GBP",
        "custom_data": custom,
        "items": [{"price": team_price(paddle), "quantity": quantity, "status": "active"}],
        "current_billing_period": {"starts_at": "2026-10-09T00:00:00Z", "ends_at": "2099-01-01T00:00:00Z"},
        "scheduled_change": None, "updated_at": "2026-10-09T00:00:00Z",
        **extra,
    }


# --- checkout ---------------------------------------------------------------------------


def test_org_checkout_roles(client, paddle):
    org, h = _roles(client)
    body = checkout_body(tier="team", interval="year", seats=3, org_id=org["id"])
    assert client.post("/billing/checkout", json=body).status_code == 401
    envelope(client.post("/billing/checkout", json=body, headers=h["admin"]), 403, "forbidden")
    envelope(client.post("/billing/checkout", json=body, headers=h["member"]), 403, "forbidden")
    envelope(client.post("/billing/checkout", json=body, headers=h["outsider"]), 404, "not_found")
    unknown = checkout_body(tier="team", interval="year", seats=3, org_id="0" * 32)
    envelope(client.post("/billing/checkout", json=unknown, headers=h["owner"]), 404, "not_found")
    malformed = checkout_body(tier="team", interval="year", seats=3, org_id="Studio-North")
    assert client.post("/billing/checkout", json=malformed, headers=h["owner"]).status_code == 422

    # The catalogue's rules apply as for people.
    few = checkout_body(tier="team", interval="year", seats=1, org_id=org["id"])
    assert client.post("/billing/checkout", json=few, headers=h["owner"]).status_code == 422
    assert client.post(
        "/billing/checkout", json=checkout_body(tier="enterprise", org_id=org["id"]), headers=h["owner"]
    ).status_code == 400

    owner_id = me(client, h["owner"])["id"]
    for role in ("owner", "billing"):
        co = org_checkout(client, h[role], org["id"])
        url = urlparse(co["url"])
        assert parse_qs(url.query)["org"] == [org["id"]] and parse_qs(url.query)["ref"] == [co["reference"]]
        txn = paddle.STATE["transactions"][txn_of(co["url"])]
        assert txn["custom_data"]["org_id"] == org["id"]
        assert txn["custom_data"]["reference"] == co["reference"]
        assert txn["items"][0]["quantity"] == 3
        pay = payment(co["reference"])
        assert pay.organisation_id == org["id"] and pay.seats == 3 and pay.plan == "team"
        # PF2b: an organisation's purchase is a business one (no consumer cancellation rights).
        assert pay.business is True
        if role == "owner":
            assert txn["custom_data"]["user_id"] == str(owner_id)

    # A personal checkout names no organisation.
    co = client.post("/billing/checkout", json=checkout_body(), headers=h["admin"]).json()
    assert "org_id" not in paddle.STATE["transactions"][txn_of(co["url"])]["custom_data"]
    assert payment(co["reference"]).organisation_id is None


def test_org_checkout_attaches_subscription_from_payment(client, paddle):
    owner, org = _org(client)
    owner_id = me(client, owner)["id"]
    # A running personal trial is not the organisation's business.
    with SessionLocal() as db:
        db.add(Subscription(user_id=owner_id, plan="pro", provider="trial", status="active",
                            current_period_end=datetime.now(timezone.utc) + timedelta(days=10)))
        db.commit()
    assert me(client, owner)["plan"] == "pro"

    co, events = org_buy(client, owner, paddle, org["id"], seats=3)
    subs = org_subs(org["id"])
    assert len(subs) == 1
    sub = subs[0]
    assert sub.plan == "team" and sub.seats == 3 and sub.user_id == owner_id and sub.status == "active"
    created = next(e for e in events if e["event_type"] == "subscription.created")["data"]
    assert sub.provider_subscription_id == created["id"]
    assert payment(co["reference"]).status == "paid"

    # The organisation's tier never lands in the buyer's users.plan cache.
    assert me(client, owner)["plan"] == "pro"
    with SessionLocal() as db:
        trial = db.scalar(select(Subscription).where(Subscription.provider == "trial"))
        assert trial.status == "active"
    personal = client.get("/billing/subscription", headers=owner).json()
    assert personal["provider"] == "trial" and personal["org_id"] is None

    detail = client.get(f"/orgs/{org['id']}", headers=owner).json()
    assert detail["subscription"]["plan"] == "team" and detail["subscription"]["seats"] == 3
    assert detail["seats"]["total"] == 3
    view = client.get("/billing/subscription", params={"org_id": org["id"]}, headers=owner).json()
    assert view["tier"] == "team" and view["seats"] == 3 and view["seats_assigned"] == 0
    assert view["org_id"] == org["id"] and view["provider"] == "paddle" and view["can_manage"]

    # Updates keep it attached; the same events again change nothing.
    updated = copy.deepcopy(created)
    updated["items"][0]["quantity"] = 4
    del updated["transaction_id"]
    assert paddle_post(client, paddle.event("subscription.updated", updated)).status_code == 200
    for ev in events:
        paddle_post(client, ev)
    (sub,) = org_subs(org["id"])
    assert sub.seats == 4 and sub.organisation_id == org["id"]
    assert me(client, owner)["plan"] == "pro"


def test_org_checkout_attaches_when_webhooks_are_late_or_lost(client, paddle):
    owner, org = _org(client)
    org2 = make_org(client, owner, "Studio South")

    # The subscription's first event arrives before the one that names its
    # transaction: held back, never the buyer's personal plan.
    co = org_checkout(client, owner, org["id"])
    events = paddle.pay(txn_of(co["url"]))
    created = next(e for e in events if e["event_type"] == "subscription.created")["data"]
    early = {k: v for k, v in created.items() if k != "transaction_id"}
    assert paddle_post(client, paddle.event("subscription.updated", early)).status_code == 200
    with SessionLocal() as db:
        assert service.find_subscription(db, "paddle", created["id"]) is None
    assert me(client, owner)["plan"] == "free"
    # Back on the billing page: the payment is verified with Paddle and the
    # subscription attached from it.
    pay = client.post(f"/billing/payments/{co['reference']}/refresh", headers=owner).json()
    assert pay["status"] == "paid" and pay["organisation_id"] == org["id"]
    assert [s.provider_subscription_id for s in org_subs(org["id"])] == [created["id"]]
    assert me(client, owner)["plan"] == "free"

    # subscription.created lost: transaction.completed alone attaches it.
    co2 = org_checkout(client, owner, org2["id"], seats=2)
    events2 = paddle.pay(txn_of(co2["url"]))
    paid = next(e for e in events2 if e["event_type"] == "transaction.completed")
    assert paddle_post(client, paid).status_code == 200
    (sub2,) = org_subs(org2["id"])
    assert sub2.seats == 2 and sub2.plan == "team"
    assert me(client, owner)["plan"] == "free"


def test_org_forged_custom_data_not_attached(client, paddle):
    owner, org = _org(client)
    member = join(client, owner, org["id"], "member@example.com")
    member_id, owner_id = me(client, member)["id"], me(client, owner)["id"]

    # Paddle.js with the public token: a transaction of the buyer's own, and
    # custom_data naming the organisation. Not attached; custom_data names
    # only the person, as in PF2.
    forged = forged_sub(paddle, "sub_forged_1", {"user_id": str(member_id), "org_id": org["id"]},
                        transaction_id="txn_not_ours")
    assert paddle_post(client, paddle.event("subscription.created", forged)).status_code == 200
    with SessionLocal() as db:
        row = service.find_subscription(db, "paddle", "sub_forged_1")
        assert row is not None and row.organisation_id is None and row.user_id == member_id
    assert org_subs(org["id"]) == []
    detail = client.get(f"/orgs/{org['id']}", headers=owner).json()
    assert detail["subscription"] is None and detail["seats"]["total"] == 0
    txn = {"id": "txn_not_ours", "status": "completed", "subscription_id": "sub_forged_1",
           "custom_data": {"user_id": str(member_id), "org_id": org["id"]}, "items": forged["items"]}
    assert paddle_post(client, paddle.event("transaction.completed", txn)).status_code == 200
    assert org_subs(org["id"]) == []

    # Claiming a real organisation checkout's reference without its
    # transaction: never attached, and never anyone's personal plan.
    co = org_checkout(client, owner, org["id"])
    claim = forged_sub(paddle, "sub_forged_2",
                       {"user_id": str(owner_id), "org_id": org["id"], "reference": co["reference"]})
    assert paddle_post(client, paddle.event("subscription.created", claim)).status_code == 200
    with SessionLocal() as db:
        assert service.find_subscription(db, "paddle", "sub_forged_2") is None
    assert org_subs(org["id"]) == [] and me(client, owner)["plan"] == "free"

    # The real checkout still attaches when it is paid.
    for ev in paddle.pay(txn_of(co["url"])):
        assert paddle_post(client, ev).status_code == 200
    (sub,) = org_subs(org["id"])
    assert sub.seats == 3 and sub.user_id == owner_id


def test_org_second_live_subscription_conflict(client, paddle):
    org, h = _roles(client)
    org_buy(client, h["owner"], paddle, org["id"])
    for role in ("owner", "billing"):
        res = client.post("/billing/checkout", json=checkout_body(tier="team", interval="year", seats=4, org_id=org["id"]),
                          headers=h[role])
        assert res.status_code == 409, res.text
        assert res.json()["code"] == "live_subscription"

    # The organisation's subscription does not block the buyer's own.
    res = client.post("/billing/checkout", json=checkout_body(tier="pro"), headers=h["owner"])
    assert res.status_code == 200, res.text
    for ev in paddle.pay(txn_of(res.json()["url"])):
        paddle_post(client, ev)
    assert me(client, h["owner"])["plan"] == "pro"
    assert client.get("/billing/subscription", headers=h["owner"]).json()["tier"] == "pro"
    # ...and a personal subscription does not block buying for an organisation.
    org2 = make_org(client, h["owner"], "Studio South")
    org_checkout(client, h["owner"], org2["id"])
    assert client.post("/billing/checkout", json=checkout_body(tier="studio"), headers=h["owner"]).status_code == 409

    # A failed renewal keeps the organisation on its subscription: fixed
    # under Manage, never bought twice.
    (sub,) = org_subs(org["id"])
    data = paddle.STATE["subscriptions"][sub.provider_subscription_id]
    overdue = {**copy.deepcopy(data), "status": "past_due"}
    paddle_post(client, paddle.event("subscription.past_due", overdue))
    view = client.get("/billing/subscription", params={"org_id": org["id"]}, headers=h["billing"]).json()
    assert view["status"] == "past_due" and view["can_manage"]
    res = client.post("/billing/checkout", json=checkout_body(tier="team", interval="year", seats=3, org_id=org["id"]),
                      headers=h["owner"])
    assert res.status_code == 409


# --- seats and management ---------------------------------------------------------------


def test_org_seats_below_assigned_conflict(client, paddle):
    org, h = _roles(client)
    org_buy(client, h["owner"], paddle, org["id"], seats=3)
    set_floating(client, h["owner"], org["id"], 1)
    join(client, h["owner"], org["id"], "a@example.com", seat="named")
    join(client, h["owner"], org["id"], "b@example.com", seat="named")
    # 2 named + a floating pool of 1 = 3 assigned.
    view = client.get("/billing/subscription", params={"org_id": org["id"]}, headers=h["owner"]).json()
    assert view["seats"] == 3 and view["seats_assigned"] == 3

    body = envelope(client.post("/billing/seats", json={"seats": 2, "org_id": org["id"]}, headers=h["owner"]),
                    409, "seats_assigned")
    assert body["data"]["assigned"] == 3
    res = client.post("/billing/seats", json={"seats": 4, "org_id": org["id"]}, headers=h["billing"])
    assert res.status_code == 200, res.text
    assert res.json()["seats"] == 4 and res.json()["seats_assigned"] == 3
    (sub,) = org_subs(org["id"])
    assert paddle.STATE["subscriptions"][sub.provider_subscription_id]["items"][0]["quantity"] == 4
    assert paddle.STATE["prorations"][-1] == "prorated_immediately"
    assert client.get(f"/orgs/{org['id']}/seats", headers=h["owner"]).json()["total"] == 4

    # PF3's seat settings keep refusing anything above the bought total.
    res = client.put(f"/orgs/{org['id']}/seats/settings", json={"floating": 5}, headers=h["owner"])
    assert res.status_code == 422
    set_floating(client, h["owner"], org["id"], 2)
    envelope(client.post("/billing/seats", json={"seats": 3, "org_id": org["id"]}, headers=h["owner"]),
             409, "seats_assigned")
    # The catalogue's minimum still applies first.
    assert client.post("/billing/seats", json={"seats": 1, "org_id": org["id"]}, headers=h["owner"]).status_code == 422

    seats = {"seats": 5, "org_id": org["id"]}
    assert client.post("/billing/seats", json=seats).status_code == 401
    envelope(client.post("/billing/seats", json=seats, headers=h["admin"]), 403, "forbidden")
    envelope(client.post("/billing/seats", json=seats, headers=h["member"]), 403, "forbidden")
    envelope(client.post("/billing/seats", json=seats, headers=h["outsider"]), 404, "not_found")
    # The buyer's own (personal) subscription is a different one: none here.
    assert client.post("/billing/seats", json={"seats": 5}, headers=h["owner"]).status_code == 404


def test_org_billing_management_roles(client, paddle):
    org, h = _roles(client)
    q = {"org_id": org["id"]}
    calls = [
        ("get", "/billing/subscription", {"params": q}),
        ("get", "/billing/invoices", {"params": q}),
        ("get", "/billing/payments", {"params": q}),
        ("post", "/billing/portal", {"json": q}),
        ("post", "/billing/change", {"json": {"interval": "year", **q}}),
    ]
    # Before anything is bought: an organisation on no plan.
    view = client.get("/billing/subscription", params=q, headers=h["billing"]).json()
    assert view["tier"] == "free" and view["status"] == "none" and view["seats"] == 0
    assert client.post("/billing/portal", json=q, headers=h["owner"]).status_code == 404

    co, _ = org_buy(client, h["owner"], paddle, org["id"])
    for method, path, kw in calls:
        assert getattr(client, method)(path, **kw).status_code == 401, path
        envelope(getattr(client, method)(path, headers=h["admin"], **kw), 403, "forbidden")
        envelope(getattr(client, method)(path, headers=h["member"], **kw), 403, "forbidden")
        envelope(getattr(client, method)(path, headers=h["outsider"], **kw), 404, "not_found")
    assert client.get("/billing/subscription", params={"org_id": "nope"}, headers=h["owner"]).status_code == 422

    # Invoices: the organisation's to its billing people, never the buyer's own list.
    rows = client.get("/billing/invoices", params=q, headers=h["billing"]).json()
    assert len(rows) == 1 and rows[0]["tax_minor"] > 0
    res = client.get(rows[0]["pdf_url"], follow_redirects=False)
    assert res.status_code == 302 and res.headers["location"].endswith(f"/invoices/{rows[0]['id']}.pdf")
    assert "o=" in rows[0]["pdf_url"]
    assert client.get("/billing/invoices", headers=h["owner"]).json() == []
    # Payments: the organisation's history, not the buyer's personal one.
    pays = client.get("/billing/payments", params=q, headers=h["billing"]).json()
    assert [p["reference"] for p in pays] == [co["reference"]] and pays[0]["organisation_id"] == org["id"]
    assert client.get("/billing/payments", headers=h["owner"]).json() == []

    assert "/portal/ctm_" in client.post("/billing/portal", json=q, headers=h["billing"]).json()["url"]
    assert client.post("/billing/portal", headers=h["owner"]).status_code == 404  # no personal one

    # Team is annual only (PF2a), so the billing role changes the tier: to Studio
    # (one seat, none given out yet), then back to Team.
    res = client.post("/billing/change", json={"tier": "studio", **q}, headers=h["billing"])
    assert res.status_code == 200, res.text
    assert res.json()["tier"] == "studio" and res.json()["interval"] == "year" and res.json()["org_id"] == org["id"]
    (sub,) = org_subs(org["id"])
    assert sub.plan == "studio" and sub.interval == "year"
    price = paddle.STATE["subscriptions"][sub.provider_subscription_id]["items"][0]["price"]
    assert price["custom_data"]["tier"] == "studio" and price["billing_cycle"]["interval"] == "year"
    res = client.post("/billing/change", json={"tier": "team", **q}, headers=h["billing"])
    assert res.status_code == 200 and res.json()["tier"] == "team" and res.json()["seats"] == 2, res.text
    # A change that leaves fewer seats than are assigned is refused.
    set_floating(client, h["owner"], org["id"], 2)
    res = client.post("/billing/change", json={"tier": "pro", **q}, headers=h["owner"])
    assert res.status_code == 409 and res.json()["code"] == "seats_assigned"
    assert me(client, h["owner"])["plan"] == "free"


def test_org_founding_one_place_per_subscription(client, paddle):
    total = service.FOUNDING.total
    owner, org = _org(client)
    co, _ = org_buy(client, owner, paddle, org["id"], seats=5)
    assert co["founding"] is True
    assert client.get("/billing/plans").json()["founding"]["remaining"] == total - 1
    res = client.post("/billing/seats", json={"seats": 9, "org_id": org["id"]}, headers=owner)
    assert res.status_code == 200 and res.json()["founding"] is True
    assert client.get("/billing/plans").json()["founding"]["remaining"] == total - 1
    # The buyer's own founding subscription is a separate place.
    res = client.post("/billing/checkout", json=checkout_body(tier="pro", interval="year"), headers=owner)
    assert res.json()["founding"] is True
    for ev in paddle.pay(txn_of(res.json()["url"])):
        paddle_post(client, ev)
    assert client.get("/billing/plans").json()["founding"]["remaining"] == total - 2


# --- the licence path -------------------------------------------------------------------


def test_org_subscription_reaches_member_entitlement(client, paddle):
    owner, org = _org(client)
    org_buy(client, owner, paddle, org["id"], tier="team", seats=3)
    a = join(client, owner, org["id"], "a@example.com", seat="named")

    dev = activated(client, a)
    res = refresh(client, dev["device_token"])
    assert res.status_code == 200, res.text
    doc = res.json()["entitlement"]["document"]
    assert doc["plan"] == "team" and doc["seat_kind"] == "named"
    assert doc["account"]["org_id"] == org["id"] and doc["plan_period_end"]
    acct = client.get("/licence/account", headers=bearer(dev["device_token"])).json()
    assert acct["plan"] == "team"
    assert acct["seat"] == {"kind": "named", "org_id": org["id"], "org_name": "Studio North"}
    assert acct["seats"] == {"total": 3, "assigned": 1}
    # Neither the member's nor the buyer's personal plan changed.
    assert me(client, a)["plan"] == "free" and me(client, owner)["plan"] == "free"
    # The buyer holds no seat of it: their own device stays on Free.
    assert activated(client, owner, "b" * 64)["entitlement"]["document"]["plan"] == "free"

    # More seats bought reach the Account panel at once.
    client.post("/billing/seats", json={"seats": 5, "org_id": org["id"]}, headers=owner)
    acct = client.get("/licence/account", headers=bearer(dev["device_token"])).json()
    assert acct["seats"] == {"total": 5, "assigned": 1}


# --- Stripe ---------------------------------------------------------------------------------


def test_org_stripe_metadata_org_id(client, stripe_prices, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_provider", "stripe")
    captured = {}

    def create(**params):
        captured.update(params)
        return {"id": "cs_org_1", "url": "https://checkout.stripe.test/cs_org_1"}

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    owner, org = _org(client)
    member = join(client, owner, org["id"], "member@example.com")
    owner_id, member_id = me(client, owner)["id"], me(client, member)["id"]
    co = org_checkout(client, owner, org["id"], seats=3)
    assert captured["metadata"]["org_id"] == org["id"]
    assert captured["subscription_data"]["metadata"]["org_id"] == org["id"]
    assert captured["metadata"]["reference"] == co["reference"]
    assert captured["line_items"][0]["quantity"] == 3
    assert f"org={org['id']}" in captured["success_url"] and f"org={org['id']}" in captured["cancel_url"]
    assert payment(co["reference"]).organisation_id == org["id"]

    amount = PLANS["team"].price("year", "GBP").amount_minor
    key = (f"truebex_team_year_gbp_{service.FOUNDING.discounted(amount)}_founding" if co["founding"]
           else f"truebex_team_year_gbp_{amount}")
    end = int(time.time()) + 30 * 86400
    sub_event = stripe_sub_event(
        "customer.subscription.created", owner_id, "active", end, price=stripe_prices[key], quantity=3,
        sub_id="sub_org_s1", meta={"user_id": str(owner_id), "plan": "team", "org_id": org["id"],
                                   "reference": co["reference"], "founding": "1" if co["founding"] else "0"},
        interval="year",
    )
    # The subscription's own event comes first: held back until our session links it.
    assert stripe_post(client, sub_event).status_code == 200
    assert org_subs(org["id"]) == [] and me(client, owner)["plan"] == "free"
    session = {
        "id": "cs_org_1", "object": "checkout.session", "client_reference_id": co["reference"],
        "status": "complete", "payment_status": "paid", "amount_total": 32000,
        "total_details": {"amount_tax": 5000}, "subscription": "sub_org_s1", "invoice": "in_org_1",
        "metadata": captured["metadata"],
    }
    ev = {"id": "evt_cs_org_1", "type": "checkout.session.completed", "created": int(time.time()),
          "data": {"object": session}}
    assert stripe_post(client, ev).status_code == 200
    (sub,) = org_subs(org["id"])
    assert sub.provider == "stripe" and sub.seats == 3 and sub.plan == "team" and sub.user_id == owner_id
    assert payment(co["reference"]).status == "paid"
    assert me(client, owner)["plan"] == "free"

    # Metadata naming the organisation on a subscription no session of ours
    # created: not attached (the person it names gets it, as in PF2).
    forged = stripe_sub_event(
        "customer.subscription.created", member_id, "active", end, price=stripe_prices[f"truebex_team_year_gbp_{amount}"],
        quantity=9, sub_id="sub_forged_s", meta={"user_id": str(member_id), "plan": "team", "org_id": org["id"]},
        interval="year",
    )
    assert stripe_post(client, forged).status_code == 200
    assert [s.provider_subscription_id for s in org_subs(org["id"])] == ["sub_org_s1"]
    with SessionLocal() as db:
        assert service.find_subscription(db, "stripe", "sub_forged_s").organisation_id is None
