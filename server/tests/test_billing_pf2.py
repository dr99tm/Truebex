"""PF2: billing through the UK company (Paddle by default, Stripe upgraded).

Paddle's API is tests/mock_paddle.py served in-process (the `paddle`
fixture); Stripe calls are monkeypatched. Webhooks are signed here exactly as
the providers sign them.
"""

import copy
import dataclasses
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import stripe
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import tasks
from app.billing import consent, jobs, providers, service
from app.billing.base import NotSupported
from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models import BillingEvent, FoundingReservation, Payment, Subscription
from app.plans import PLANS

from .conftest import CONSENT, checkout_body, signup
from .test_billing import stripe_post, stripe_sub_event

SECRET = "pdl_ntfset_test_secret"
REPO = Path(__file__).resolve().parents[2]


# --- helpers --------------------------------------------------------------------------


def paddle_post(client, event: dict, secret=SECRET, ts=None):
    body = json.dumps(event).encode()
    from . import mock_paddle

    return client.post(
        "/billing/webhooks/paddle",
        content=body,
        headers={"Paddle-Signature": mock_paddle.sign(secret, body, ts), "Content-Type": "application/json"},
    )


def start_checkout(client, h, **kw):
    res = client.post("/billing/checkout", json=checkout_body(**kw), headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def txn_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["_ptxn"][0]


def buy(client, h, paddle, deliver=True, **kw):
    """Checkout, pay on the mock, deliver the webhooks. Returns (checkout, events)."""
    co = start_checkout(client, h, **kw)
    events = paddle.pay(txn_of(co["url"]))
    if deliver:
        for ev in events:
            assert paddle_post(client, ev).status_code == 200
    return co, events


def me(client, h):
    return client.get("/auth/me", headers=h).json()


def local_sub(user_email="dev@example.com") -> Subscription:
    with SessionLocal() as db:
        return db.scalar(select(Subscription).order_by(Subscription.id.desc()))


# --- catalogue ----------------------------------------------------------------------------


def test_billing_plans_lists_tiers_without_wayl(client):
    res = client.get("/billing/plans")
    assert res.status_code == 200
    cat = res.json()
    assert [t["id"] for t in cat["tiers"]] == ["free", "pro", "studio", "team", "enterprise"]
    assert cat["provider"] == "paddle"
    pro = next(t for t in cat["tiers"] if t["id"] == "pro")
    pairs = {(p["interval"], p["currency"]) for p in pro["prices"]}
    assert pairs == {(i, c) for i in ("month", "year") for c in ("GBP", "USD", "EUR")}
    team = next(t for t in cat["tiers"] if t["id"] == "team")
    assert team["per_seat"] and team["min_seats"] >= 2
    assert cat["founding"]["enabled"] and cat["founding"]["remaining"] == cat["founding"]["total"]
    assert "wayl" not in res.text.lower() and "price_iqd" not in res.text and "IQD" not in res.text


def test_billing_plans_wayl_dormant_flag(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "wayl_enabled", True)
    cat = client.get("/billing/plans").json()
    assert "wayl" in cat["providers"]
    pro = next(t for t in cat["tiers"] if t["id"] == "pro")
    assert {"interval": "month", "currency": "IQD", "amount_minor": 130000} in pro["prices"]
    # The site never offers it: the checkout provider stays Paddle.
    assert cat["provider"] == "paddle"


def test_billing_consent_version_matches_site():
    constants = (REPO / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")
    assert f'version: "{consent.CONSENT_VERSION}"' in constants
    assert CONSENT["version"] == consent.CONSENT_VERSION


# --- checkout -------------------------------------------------------------------------------


def test_billing_checkout_paddle_creates_transaction(client, paddle):
    h = signup(client)
    uid = me(client, h)["id"]
    co = start_checkout(client, h, tier="team", interval="year", currency="EUR", seats=3)
    url = urlparse(co["url"])
    assert url.path == "/checkout/" and url.netloc == "truebex.com"
    assert parse_qs(url.query)["ref"] == [co["reference"]]
    txn = paddle.STATE["transactions"][txn_of(co["url"])]
    assert txn["custom_data"]["user_id"] == str(uid)
    assert txn["custom_data"]["reference"] == co["reference"]
    assert txn["items"][0]["quantity"] == 3
    price = txn["items"][0]["price"]
    assert price["custom_data"]["tier"] == "team" and price["billing_cycle"]["interval"] == "year"
    assert txn["currency_code"] == "EUR"
    assert paddle.STATE["customers"][txn["customer_id"]]["email"] == "dev@example.com"
    with SessionLocal() as db:
        pay = db.scalar(select(Payment).where(Payment.reference == co["reference"]))
        assert pay.provider == "paddle" and pay.seats == 3 and pay.interval == "year"
        assert pay.consent_version == consent.CONSENT_VERSION and pay.consent_at is not None


def test_billing_checkout_requires_session_and_consent(client, paddle):
    assert client.post("/billing/checkout", json=checkout_body()).status_code == 401
    h = signup(client)
    body = checkout_body()
    del body["consent"]
    assert client.post("/billing/checkout", json=body, headers=h).status_code == 422
    body["consent"] = {"version": consent.CONSENT_VERSION, "accepted": False}
    assert client.post("/billing/checkout", json=body, headers=h).status_code == 422
    body["consent"] = {"version": "1999-01-01", "accepted": True}
    assert client.post("/billing/checkout", json=body, headers=h).status_code == 422
    res = client.post("/billing/checkout", json=checkout_body(tier="team", interval="year", seats=1), headers=h)
    assert res.status_code == 422
    res = client.post("/billing/checkout", json=checkout_body(tier="pro", seats=2), headers=h)
    assert res.status_code == 422
    assert client.post("/billing/checkout", json=checkout_body(seats=0), headers=h).status_code == 422


def test_billing_checkout_rejects_unpurchasable_and_unknown_price(client, paddle):
    h = signup(client)
    assert client.post("/billing/checkout", json=checkout_body(tier="enterprise"), headers=h).status_code == 400
    assert client.post("/billing/checkout", json=checkout_body(tier="free"), headers=h).status_code == 400
    assert client.post("/billing/checkout", json=checkout_body(tier="gold"), headers=h).status_code == 400
    assert client.post("/billing/checkout", json=checkout_body(currency="JPY"), headers=h).status_code == 400


def test_billing_checkout_without_provider_or_prices(client, monkeypatch):
    h = signup(client)
    # Paddle keyed but no prices synced: not set up yet.
    assert client.post("/billing/checkout", json=checkout_body(), headers=h).status_code == 503
    monkeypatch.setattr(get_settings(), "paddle_api_key", "")
    assert client.get("/billing/plans").json()["provider"] is None
    assert client.post("/billing/checkout", json=checkout_body(), headers=h).status_code == 503


def test_billing_checkout_server_picks_price(client, paddle):
    h = signup(client)
    body = checkout_body(tier="pro", interval="year", currency="GBP")
    body.update(amount=1, amount_minor=1, price_id="pri_forged", founding=True)
    co = client.post("/billing/checkout", json=body, headers=h).json()
    txn = paddle.STATE["transactions"][txn_of(co["url"])]
    price = txn["items"][0]["price"]
    listed = PLANS["pro"].price("year", "GBP").amount_minor
    founding_price = service.FOUNDING.discounted(listed)
    assert int(price["unit_price"]["amount"]) == (founding_price if co["founding"] else listed)
    assert price["id"] != "pri_forged"
    with SessionLocal() as db:
        assert db.scalar(select(Payment.amount).where(Payment.reference == co["reference"])) == int(
            price["unit_price"]["amount"]
        )


def test_billing_checkout_coupon_passed_to_paddle(client, paddle):
    h = signup(client)
    res = client.post("/billing/checkout", json=checkout_body(coupon="NOPE"), headers=h)
    assert res.status_code == 400
    co = start_checkout(client, h, interval="year", coupon="launch10")
    txn = paddle.STATE["transactions"][txn_of(co["url"])]
    assert txn["discount_id"] == "dsc_launch10"
    # One discount per checkout: a coupon replaces the founding price.
    assert co["founding"] is False
    assert txn["items"][0]["price"]["custom_data"]["founding"] == "0"


def test_billing_checkout_conflict_when_subscribed(client, paddle):
    h = signup(client)
    _, events = buy(client, h, paddle)
    res = client.post("/billing/checkout", json=checkout_body(tier="studio"), headers=h)
    assert res.status_code == 409
    # A failed renewal: the plan lapses, the card is fixed under Manage, and a
    # second subscription cannot be bought on top.
    created = next(e for e in events if e["event_type"] == "subscription.created")["data"]
    overdue = {**copy.deepcopy(created), "status": "past_due"}
    paddle_post(client, paddle.event("subscription.past_due", overdue))
    assert me(client, h)["plan"] == "free"
    sub = client.get("/billing/subscription", headers=h).json()
    assert sub["status"] == "past_due" and sub["can_manage"]
    res = client.post("/billing/checkout", json=checkout_body(tier="studio"), headers=h)
    assert res.status_code == 409


# --- webhooks -------------------------------------------------------------------------------


def test_billing_paddle_webhook_signature(client, paddle):
    ev = paddle.event("subscription.updated", {"id": "sub_x", "status": "active", "custom_data": {}})
    assert paddle_post(client, ev).status_code == 200
    ev2 = paddle.event("subscription.updated", {"id": "sub_x", "status": "active", "custom_data": {}})
    assert paddle_post(client, ev2, secret="pdl_ntfset_wrong").status_code == 400
    assert paddle_post(client, ev2, ts=int(time.time()) - 301).status_code == 400
    assert paddle_post(client, ev2, ts=int(time.time()) + 301).status_code == 400
    res = client.post("/billing/webhooks/paddle", content=json.dumps(ev2).encode())
    assert res.status_code == 400


def test_billing_paddle_subscription_lifecycle(client, paddle):
    h = signup(client)
    _, events = buy(client, h, paddle)
    assert me(client, h)["plan"] == "pro"
    sub = client.get("/billing/subscription", headers=h).json()
    assert sub["tier"] == "pro" and sub["seats"] == 1 and sub["interval"] == "month"
    assert sub["provider"] == "paddle" and sub["can_manage"] and not sub["cancel_at_period_end"]
    period_end = datetime.fromisoformat(sub["current_period_end"])
    assert timedelta(days=27) < period_end.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc) < timedelta(days=32)

    created = next(e for e in events if e["event_type"] == "subscription.created")["data"]
    updated = copy.deepcopy(created)
    updated["items"][0]["quantity"] = 3
    assert paddle_post(client, paddle.event("subscription.updated", updated)).status_code == 200
    assert client.get("/billing/subscription", headers=h).json()["seats"] == 3

    ending = copy.deepcopy(updated)
    ending["scheduled_change"] = {"action": "cancel", "effective_at": created["current_billing_period"]["ends_at"]}
    paddle_post(client, paddle.event("subscription.updated", ending))
    sub = client.get("/billing/subscription", headers=h).json()
    assert sub["cancel_at_period_end"] and sub["tier"] == "pro"

    canceled = copy.deepcopy(ending)
    canceled.update(status="canceled", scheduled_change=None, current_billing_period=None)
    paddle_post(client, paddle.event("subscription.canceled", canceled))
    assert me(client, h)["plan"] == "free"
    assert client.get("/billing/subscription", headers=h).json()["status"] == "none"


def test_billing_webhook_replay_and_out_of_order(client, paddle):
    h = signup(client)
    _, events = buy(client, h, paddle, tier="team", interval="year", seats=2)
    # Replays of the same events are applied once.
    for ev in events:
        assert paddle_post(client, ev).status_code == 200
    with SessionLocal() as db:
        ids = [e["event_id"] for e in events]
        assert db.scalar(select(func.count()).select_from(BillingEvent).where(BillingEvent.event_id.in_(ids))) == 2

    created = next(e for e in events if e["event_type"] == "subscription.created")["data"]
    now = datetime.now(timezone.utc)
    newer = copy.deepcopy(created)
    newer["items"][0]["quantity"] = 5
    older = copy.deepcopy(created)
    older["items"][0]["quantity"] = 4
    paddle_post(client, paddle.event("subscription.updated", newer, occurred_at=now + timedelta(seconds=10)))
    paddle_post(client, paddle.event("subscription.updated", older, occurred_at=now + timedelta(seconds=5)))
    assert client.get("/billing/subscription", headers=h).json()["seats"] == 5

    # Stripe: the same event delivered twice applies once.
    h2 = signup(client, email="two@example.com")
    uid2 = me(client, h2)["id"]
    end = int(time.time()) + 30 * 86400
    ev = stripe_sub_event("customer.subscription.created", uid2, "active", end, sub_id="sub_s2")
    assert stripe_post(client, ev).status_code == 200
    assert stripe_post(client, ev).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(BillingEvent).where(BillingEvent.event_id == ev["id"])
        ) == 1


def test_billing_refresh_verifies_with_paddle(client, paddle):
    h = signup(client)
    co = start_checkout(client, h)
    ref = co["reference"]
    # Back on ?checkout=success&ref=… before paying: nothing changes.
    pay = client.post(f"/billing/payments/{ref}/refresh", headers=h).json()
    assert pay["status"] == "pending" and me(client, h)["plan"] == "free"
    paddle.pay(txn_of(co["url"]))  # webhooks lost (the PC was off)
    pay = client.post(f"/billing/payments/{ref}/refresh", headers=h).json()
    assert pay["status"] == "paid" and pay["tax_minor"] > 0
    assert me(client, h)["plan"] == "pro"
    assert client.post("/billing/payments/tbx_nope/refresh", headers=h).status_code == 404
    assert client.post(f"/billing/payments/{ref}/refresh").status_code == 401


# --- Stripe -----------------------------------------------------------------------------------


def test_billing_stripe_tax_and_annual_checkout(client, stripe_prices, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "billing_provider", "stripe")
    monkeypatch.setattr(s, "stripe_tax_enabled", True)
    captured = {}

    def create(**params):
        captured.update(params)
        return {"id": "cs_test_1", "url": "https://checkout.stripe.test/cs_test_1"}

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    assert client.get("/billing/plans").json()["provider"] == "stripe"
    h = signup(client)
    co = start_checkout(client, h, tier="team", interval="year", currency="EUR", seats=3)
    assert co["url"] == "https://checkout.stripe.test/cs_test_1"
    assert captured["automatic_tax"] == {"enabled": True}
    assert captured["tax_id_collection"] == {"enabled": True}
    assert captured["billing_address_collection"] == "required"
    assert captured["consent_collection"] == {"terms_of_service": "required"}
    item = captured["line_items"][0]
    amount = PLANS["team"].price("year", "EUR").amount_minor
    assert co["founding"] is True
    key = f"truebex_team_year_eur_{service.FOUNDING.discounted(amount)}_founding"
    assert item == {"price": stripe_prices[key], "quantity": 3}
    assert captured["metadata"]["reference"] == co["reference"]
    # One discount per checkout, and the session ends with its founding hold.
    assert "allow_promotion_codes" not in captured
    assert captured["expires_at"] - time.time() <= 31 * 60 + 5


def test_billing_stripe_legacy_pro_still_applies(client, stripe_prices):
    h = signup(client)
    uid = me(client, h)["id"]
    end = int(time.time()) + 30 * 86400
    ev = stripe_sub_event(
        "customer.subscription.updated", uid, "active", end, price="price_test_pro", meta={"user_id": str(uid)}
    )
    assert stripe_post(client, ev).status_code == 200
    assert me(client, h)["plan"] == "pro"
    sub = client.get("/billing/subscription", headers=h).json()
    assert sub["tier"] == "pro" and sub["interval"] == "month"


def test_billing_stripe_checkout_completed_marks_paid(client, stripe_prices, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "billing_provider", "stripe")
    monkeypatch.setattr(
        stripe.checkout.Session, "create", lambda **p: {"id": "cs_test_2", "url": "https://checkout.stripe.test/2"}
    )
    h = signup(client)
    uid = me(client, h)["id"]
    co = start_checkout(client, h, tier="pro", currency="USD")
    end = int(time.time()) + 30 * 86400
    price_id = stripe_prices["truebex_pro_month_usd_2900"]
    sub_obj = stripe_sub_event("x", uid, "active", end, price=price_id, sub_id="sub_c2",
                               meta={"user_id": str(uid), "plan": "pro", "founding": "0"})["data"]["object"]
    monkeypatch.setattr(stripe.Subscription, "retrieve", lambda *a, **k: sub_obj)
    session = {
        "id": "cs_test_2",
        "object": "checkout.session",
        "client_reference_id": co["reference"],
        "status": "complete",
        "payment_status": "paid",
        "amount_total": 11880,
        "total_details": {"amount_tax": 1980},
        "subscription": "sub_c2",
        "invoice": "in_1",
        "metadata": {"founding": "1" if co["founding"] else "0"},
    }
    ev = {"id": "evt_cs2", "type": "checkout.session.completed", "created": int(time.time()), "data": {"object": session}}
    assert stripe_post(client, ev).status_code == 200
    pay = client.get("/billing/payments", headers=h).json()[0]
    assert pay["status"] == "paid" and pay["amount"] == 11880 and pay["tax_minor"] == 1980
    assert me(client, h)["plan"] == "pro"


# --- seats, changes, founding ----------------------------------------------------------------------


def test_billing_seats_change(client, paddle):
    assert client.post("/billing/seats", json={"seats": 5}).status_code == 401
    h = signup(client)
    assert client.post("/billing/seats", json={"seats": 5}, headers=h).status_code == 404
    buy(client, h, paddle, tier="team", seats=3, interval="year")
    assert client.get("/billing/subscription", headers=h).json()["seats"] == 3
    assert client.post("/billing/seats", json={"seats": 0}, headers=h).status_code == 422
    assert client.post("/billing/seats", json={"seats": 1}, headers=h).status_code == 422
    res = client.post("/billing/seats", json={"seats": 5}, headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["seats"] == 5
    sub_id = local_sub().provider_subscription_id
    assert paddle.STATE["subscriptions"][sub_id]["items"][0]["quantity"] == 5
    assert paddle.STATE["prorations"][-1] == "prorated_immediately"
    # PF3 hook: fewer seats than are assigned is refused.
    import app.billing.service as svc

    original = svc.seats_assigned
    try:
        svc.seats_assigned = lambda db, sub: 4
        assert client.post("/billing/seats", json={"seats": 3}, headers=h).status_code == 409
    finally:
        svc.seats_assigned = original


def test_billing_seats_single_seat_plan(client, paddle):
    h = signup(client)
    buy(client, h, paddle)
    assert client.post("/billing/seats", json={"seats": 2}, headers=h).status_code == 422


def test_billing_change_interval(client, paddle):
    assert client.post("/billing/change", json={"interval": "year"}).status_code == 401
    h = signup(client)
    buy(client, h, paddle, tier="pro", interval="month")
    res = client.post("/billing/change", json={"interval": "year"}, headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["interval"] == "year"
    sub_id = local_sub().provider_subscription_id
    price = paddle.STATE["subscriptions"][sub_id]["items"][0]["price"]
    assert price["billing_cycle"]["interval"] == "year" and price["custom_data"]["tier"] == "pro"
    assert client.post("/billing/change", json={"tier": "enterprise"}, headers=h).status_code == 400
    assert client.post("/billing/change", json={}, headers=h).status_code == 422
    res = client.post("/billing/change", json={"tier": "team"}, headers=h)
    assert res.status_code == 200 and res.json()["tier"] == "team"
    assert res.json()["seats"] == PLANS["team"].min_seats


def test_billing_founding_counts_and_holds(client, paddle, monkeypatch):
    total = service.FOUNDING.total
    h = signup(client)
    co, _ = buy(client, h, paddle, interval="year")
    assert co["founding"] is True
    assert client.get("/billing/plans").json()["founding"]["remaining"] == total - 1
    assert client.get("/billing/subscription", headers=h).json()["founding"] is True

    # A Team checkout holds one place, whatever its seats.
    h2 = signup(client, email="two@example.com")
    co2 = start_checkout(client, h2, tier="team", interval="year", seats=4)
    assert co2["founding"] is True
    assert client.get("/billing/plans").json()["founding"]["remaining"] == total - 2
    # Abandoned for 30 minutes: the hold is released and its checkout cancelled.
    assert jobs.expire_founding(datetime.now(timezone.utc) + timedelta(minutes=31)) == 1
    assert client.get("/billing/plans").json()["founding"]["remaining"] == total - 1
    assert paddle.STATE["transactions"][txn_of(co2["url"])]["status"] == "canceled"
    assert client.get("/billing/payments", headers=h2).json()[0]["status"] == "canceled"

    # Sold out: the next checkout pays the list price.
    monkeypatch.setattr(service, "FOUNDING", dataclasses.replace(service.FOUNDING, total=1))
    cat = client.get("/billing/plans").json()
    assert cat["founding"]["remaining"] == 0 and cat["founding"]["enabled"] is False
    co3 = start_checkout(client, h2, interval="year")
    assert co3["founding"] is False
    txn = paddle.STATE["transactions"][txn_of(co3["url"])]
    assert int(txn["items"][0]["price"]["unit_price"]["amount"]) == PLANS["pro"].price("year", "GBP").amount_minor


def test_billing_founding_seat_changes_keep_one_place(client, paddle):
    total = service.FOUNDING.total
    h = signup(client)
    buy(client, h, paddle, tier="team", interval="year", seats=2)
    assert client.get("/billing/plans").json()["founding"]["remaining"] == total - 1
    res = client.post("/billing/seats", json={"seats": 40}, headers=h)
    assert res.status_code == 200 and res.json()["seats"] == 40 and res.json()["founding"] is True
    assert client.get("/billing/plans").json()["founding"]["remaining"] == total - 1


def test_billing_founding_paid_after_hold_expired(client, paddle):
    h = signup(client)
    co = start_checkout(client, h, interval="year")
    jobs.expire_founding(datetime.now(timezone.utc) + timedelta(minutes=31))
    # Paddle completed it anyway (a race with the cancel): the place is counted.
    for ev in paddle.pay(txn_of(co["url"])):
        paddle_post(client, ev)
    with SessionLocal() as db:
        hold = db.scalar(select(FoundingReservation).where(FoundingReservation.reference == co["reference"]))
        assert hold is not None and hold.consumed_at is not None
    assert client.get("/billing/plans").json()["founding"]["remaining"] == service.FOUNDING.total - 1


def test_billing_founding_counted_without_our_checkout(client, paddle):
    """Paddle.js can buy a founding price straight from its id: still counted."""
    h = signup(client)
    uid = me(client, h)["id"]
    founding_price = next(
        p for p in paddle.STATE["prices"].values()
        if p["custom_data"]["tier"] == "pro" and p["custom_data"]["founding"] == "1"
        and p["billing_cycle"]["interval"] == "year" and p["unit_price"]["currency_code"] == "GBP"
    )
    cust = next(iter(paddle.STATE["customers"]), None) or "ctm_x"
    sub = {
        "id": "sub_direct", "status": "active", "customer_id": cust, "currency_code": "GBP",
        "custom_data": {"user_id": str(uid)},
        "items": [{"price": founding_price, "quantity": 1, "status": "active"}],
        "current_billing_period": {"starts_at": "2026-10-09T00:00:00Z", "ends_at": "2099-01-01T00:00:00Z"},
        "scheduled_change": None, "updated_at": "2026-10-09T00:00:00Z",
    }
    assert paddle_post(client, paddle.event("subscription.created", sub)).status_code == 200
    assert me(client, h)["plan"] == "pro"
    assert client.get("/billing/plans").json()["founding"]["remaining"] == service.FOUNDING.total - 1
    paddle_post(client, paddle.event("subscription.updated", sub))  # counted once
    assert client.get("/billing/plans").json()["founding"]["remaining"] == service.FOUNDING.total - 1


def test_billing_custom_data_cannot_choose_tier_or_founding(client, paddle):
    h = signup(client)
    uid = me(client, h)["id"]
    base = {
        "status": "active", "customer_id": "ctm_x", "currency_code": "GBP",
        "current_billing_period": {"starts_at": "2026-10-09T00:00:00Z", "ends_at": "2099-01-01T00:00:00Z"},
        "scheduled_change": None,
    }
    # A price we never synced grants nothing, whatever custom_data claims.
    forged = {**base, "id": "sub_forged", "custom_data": {"user_id": str(uid), "tier": "enterprise", "founding": "1"},
              "items": [{"price": {"id": "pri_not_ours", "billing_cycle": {"interval": "month"}}, "quantity": 1}]}
    assert paddle_post(client, paddle.event("subscription.created", forged)).status_code == 200
    assert me(client, h)["plan"] == "free"
    # The list price with founding claimed in custom_data: not a founding subscription.
    _, events = buy(client, h, paddle, coupon="LAUNCH10")
    created = next(e for e in events if e["event_type"] == "subscription.created")["data"]
    claimed = copy.deepcopy(created)
    claimed["custom_data"]["founding"] = "1"
    paddle_post(client, paddle.event("subscription.updated", claimed))
    assert client.get("/billing/subscription", headers=h).json()["founding"] is False
    client.post("/billing/change", json={"interval": "year"}, headers=h)
    price = paddle.STATE["subscriptions"][created["id"]]["items"][0]["price"]
    assert price["custom_data"]["founding"] == "0"
    # A null user id is not ours: acknowledged, nothing applied.
    nobody = {**base, "id": "sub_nobody", "custom_data": {"user_id": None}, "items": created["items"]}
    assert paddle_post(client, paddle.event("subscription.created", nobody)).status_code == 200


def test_billing_renewal_does_not_overwrite_checkout_payment(client, paddle):
    h = signup(client)
    co, events = buy(client, h, paddle)
    before = client.get("/billing/payments", headers=h).json()[0]
    txn = copy.deepcopy(next(e for e in events if e["event_type"] == "transaction.completed")["data"])
    txn.update(id="txn_renewal", origin="subscription_recurring", invoice_id="inv_renewal")
    txn["details"]["totals"].update(grand_total="123", tax="7")
    assert paddle_post(client, paddle.event("transaction.completed", txn)).status_code == 200
    after = client.get("/billing/payments", headers=h).json()[0]
    assert after["amount"] == before["amount"] and after["tax_minor"] == before["tax_minor"]


def test_billing_stripe_same_second_events_use_current_state(client, stripe_prices):
    h = signup(client)
    uid = me(client, h)["id"]
    end = int(time.time()) + 30 * 86400
    now = int(time.time())
    active = stripe_sub_event("customer.subscription.updated", uid, "active", end, created=now, sub_id="sub_ss")
    late = stripe_sub_event("customer.subscription.created", uid, "incomplete", end, created=now, sub_id="sub_ss")
    stripe_post(client, active)
    stripe_post(client, late, current=False)  # delivered late; Stripe now says active
    assert me(client, h)["plan"] == "pro"


def test_billing_reconcile_without_changes_keeps_updated_at(client, paddle):
    h = signup(client)
    buy(client, h, paddle)
    with SessionLocal() as db:
        first = db.scalar(select(Subscription.updated_at).where(Subscription.provider == "paddle"))
    time.sleep(0.05)
    jobs.reconcile(datetime.now(timezone.utc))
    with SessionLocal() as db:
        assert db.scalar(select(Subscription.updated_at).where(Subscription.provider == "paddle")) == first


def test_billing_one_row_per_provider_subscription(client):
    h = signup(client)
    uid = me(client, h)["id"]
    with SessionLocal() as db:
        for _ in range(2):
            db.add(Subscription(user_id=uid, plan="pro", provider="paddle", status="active",
                                provider_subscription_id="sub_dup"))
        with pytest.raises(IntegrityError):
            db.commit()


# --- invoices and portal ----------------------------------------------------------------------------


def test_billing_invoices_list(client, paddle):
    assert client.get("/billing/invoices").status_code == 401
    h = signup(client)
    assert client.get("/billing/invoices", headers=h).json() == []
    buy(client, h, paddle)
    rows = client.get("/billing/invoices", headers=h).json()
    assert len(rows) == 1
    inv = rows[0]
    assert inv["number"] and inv["tax_minor"] > 0 and inv["currency"] == "GBP"
    assert inv["pdf_url"].startswith(f"/billing/invoices/{inv['id']}/pdf?")
    res = client.get(inv["pdf_url"], follow_redirects=False)
    assert res.status_code == 302 and res.headers["location"].endswith(f"/invoices/{inv['id']}.pdf")
    forged = re.sub(r"sig=[0-9a-f]+", "sig=" + "0" * 64, inv["pdf_url"])
    assert client.get(forged, follow_redirects=False).status_code == 403
    pdf = paddle.invoice_pdf_bytes(paddle.STATE["transactions"][inv["id"]])
    assert pdf.startswith(b"%PDF") and b"VAT" in pdf


def test_billing_invoices_stripe(client, monkeypatch):
    h = signup(client)
    uid = me(client, h)["id"]
    stripe_post(client, stripe_sub_event("customer.subscription.created", uid, "active", int(time.time()) + 86400))
    monkeypatch.setattr(
        stripe.Invoice,
        "list",
        lambda **k: {
            "data": [
                {"id": "in_1", "number": "TBX-0001", "created": int(time.time()), "total": 11880, "tax": 1980,
                 "currency": "gbp", "status": "paid", "invoice_pdf": "https://pay.stripe.test/in_1.pdf"}
            ]
        },
    )
    rows = client.get("/billing/invoices", headers=h).json()
    assert rows == [
        {**rows[0], "id": "in_1", "number": "TBX-0001", "total_minor": 11880, "tax_minor": 1980, "currency": "GBP"}
    ]
    assert rows[0]["pdf_url"].startswith("/billing/invoices/in_1/pdf?")
    owner = {"customer": "cus_123", "invoice_pdf": "https://pay.stripe.test/in_1.pdf"}
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda *a, **k: owner)
    res = client.get(rows[0]["pdf_url"], follow_redirects=False)
    assert res.status_code == 302 and res.headers["location"] == "https://pay.stripe.test/in_1.pdf"
    owner["customer"] = "cus_someone_else"
    assert client.get(rows[0]["pdf_url"], follow_redirects=False).status_code == 404


def test_billing_portal_paddle_and_stripe(client, paddle, monkeypatch):
    assert client.post("/billing/portal").status_code == 401
    h = signup(client)
    assert client.post("/billing/portal", headers=h).status_code == 404
    buy(client, h, paddle)
    url = client.post("/billing/portal", headers=h).json()["url"]
    assert "/portal/ctm_" in url

    h2 = signup(client, email="stripe@example.com")
    uid2 = me(client, h2)["id"]
    stripe_post(client, stripe_sub_event("customer.subscription.created", uid2, "active", int(time.time()) + 86400, sub_id="sub_p2"))
    monkeypatch.setattr(stripe.billing_portal.Session, "create", lambda **k: {"url": f"https://billing.stripe.test/{k['customer']}"})
    assert client.post("/billing/portal", headers=h2).json()["url"] == "https://billing.stripe.test/cus_123"


# --- the interface other features call ------------------------------------------------------------------


def test_billing_charge_usage_interface(client, paddle, monkeypatch):
    h = signup(client)
    buy(client, h, paddle, currency="USD")
    with SessionLocal() as db:
        sub = db.scalar(select(Subscription).where(Subscription.provider == "paddle"))
        adapter = providers.get_provider("paddle")
        adapter.charge_usage(db, sub, "cloud_cu", 3, 250, "Cloud renders")
        charge = paddle.STATE["charges"][-1]
        assert charge["subscription_id"] == sub.provider_subscription_id
        item = charge["items"][0]
        assert item["quantity"] == 3
        assert item["price"]["unit_price"] == {"amount": "250", "currency_code": "USD"}
        with pytest.raises(NotSupported):
            adapter.create_invoice(db, "ctm_x", [])

        captured = {}
        monkeypatch.setattr(stripe.InvoiceItem, "create", lambda **k: captured.update(k) or {"id": "ii_1"})
        sub.provider_customer_id, sub.provider_subscription_id = "cus_1", "sub_1"
        assert providers.get_provider("stripe").charge_usage(db, sub, "ai_credits", 4, 125, "AI credits") == "ii_1"
        assert captured["amount"] == 500 and captured["currency"] == "usd"
        db.rollback()


# --- PF1's entitlement (the joint proof, contract section 10) ------------------------------------------


def _has_route(path: str) -> bool:
    return any(getattr(r, "path", None) == path for r in app.routes)


@pytest.mark.skipif(not _has_route("/licence/entitlement"), reason="needs PF1's licence API (merge)")
def test_billing_entitlement_follows_purchase(client, paddle):
    h = signup(client)
    buy(client, h, paddle, tier="team", interval="year", seats=3)
    contract = {"X-Truebex-Contract": "licence-api/1.0"}
    fp = "a" * 64
    act = client.post(
        "/licence/activate",
        json={"fingerprint": fp, "device_name": "TEST-PC", "os": "windows 10.0.26200", "app_version": "1.0.0",
              "replace_device_id": None},
        headers={**h, **contract},
    )
    assert act.status_code in (200, 201), act.text
    device = {"Authorization": f"Bearer {act.json()['device_token']}", **contract}
    ent = client.post("/licence/entitlement", json={"fingerprint": fp, "app_version": "1.0.0"}, headers=device)
    doc = ent.json()["entitlement"]["document"]
    assert doc["plan"] == "team" and doc["plan_period_end"]
    account = client.get("/licence/account", headers=device).json()
    assert account["seats"]["total"] == 3


# --- guards, jobs, script ----------------------------------------------------------------------------


def test_billing_no_client_side_plan_grant(client, paddle):
    h = signup(client)
    attempts = [
        ("post", "/billing/activate", {"plan": "pro"}),
        ("post", "/billing/seats", {"seats": 9}),
        ("post", "/billing/change", {"tier": "team"}),
        ("post", "/billing/checkout", checkout_body(tier="studio", status="paid", founding=True)),
        ("post", "/billing/portal", None),
        ("get", "/billing/invoices", None),
    ]
    for method, path, body in attempts:
        getattr(client, method)(path, headers=h, **({"json": body} if body is not None else {}))
        assert me(client, h)["plan"] == "free", path
    ref = client.get("/billing/payments", headers=h).json()[0]["reference"]
    client.post(f"/billing/payments/{ref}/refresh", headers=h)
    # Unsigned or forged webhooks claiming a purchase.
    uid = me(client, h)["id"]
    forged = {"event_id": "evt_forged", "event_type": "subscription.created", "occurred_at": "2026-10-09T00:00:00Z",
              "data": {"id": "sub_forged", "status": "active", "custom_data": {"user_id": str(uid), "tier": "team"},
                       "items": [{"quantity": 9, "price": {"id": "pri_x"}}]}}
    assert client.post("/billing/webhooks/paddle", json=forged).status_code == 400
    assert paddle_post(client, forged, secret="guess").status_code == 400
    assert stripe_post(client, stripe_sub_event("customer.subscription.created", uid, "active", 2_000_000_000),
                       secret="whsec_guess").status_code == 400
    assert me(client, h)["plan"] == "free"
    assert client.get("/billing/subscription", headers=h).json()["tier"] == "free"


def test_billing_reconcile_job_applies_missed_webhooks(client, paddle):
    h = signup(client)
    co = start_checkout(client, h)
    events = paddle.pay(txn_of(co["url"]))  # never delivered
    assert me(client, h)["plan"] == "free"
    assert jobs.reconcile(datetime.now(timezone.utc)) >= 1
    assert me(client, h)["plan"] == "pro"
    # A cancellation made while the API was down is picked up too.
    sub_id = next(e for e in events if e["event_type"] == "subscription.created")["data"]["id"]
    paddle.cancel_now(sub_id)
    jobs.reconcile(datetime.now(timezone.utc) + timedelta(seconds=1))
    assert me(client, h)["plan"] == "free"


def test_billing_purchase_ends_trial(client, paddle):
    h = signup(client)
    uid = me(client, h)["id"]
    with SessionLocal() as db:
        db.add(Subscription(user_id=uid, plan="pro", provider="trial", status="active",
                            current_period_end=datetime.now(timezone.utc) + timedelta(days=10)))
        db.commit()
    buy(client, h, paddle, tier="studio")
    with SessionLocal() as db:
        trial = db.scalar(select(Subscription).where(Subscription.provider == "trial"))
        assert trial.status == "canceled"
    assert me(client, h)["plan"] == "studio"


def test_tasks_registry_and_run_due():
    names = set(tasks.jobs())
    assert {"billing.founding.expire", "billing.reconcile"} <= names
    assert tasks.jobs()["billing.founding.expire"].seconds == 300
    ran = []
    tasks.periodic("test.tick", 60)(lambda now: ran.append(now))
    try:
        t0 = datetime(2026, 10, 9, tzinfo=timezone.utc)
        assert "test.tick" in tasks.run_due(t0)
        assert "test.tick" not in tasks.run_due(t0 + timedelta(seconds=30))
        assert "test.tick" in tasks.run_due(t0 + timedelta(seconds=61))
        assert len(ran) == 2
    finally:
        tasks._JOBS.pop("test.tick", None)
        for job in tasks._JOBS.values():
            job.next_run = None


def test_sync_prices_paddle_idempotent(client, paddle):
    from scripts import sync_prices

    first = len(paddle.STATE["prices"])
    targets = sync_prices.targets()
    assert first == len(targets) > 0
    again = sync_prices.sync_paddle(get_settings())
    assert not any(created for _, _, created in again)
    assert len(paddle.STATE["prices"]) == first
    team = [t for t in targets if t.tier == "team"]
    assert team and all(t.per_seat for t in team)
    team_price = next(p for p in paddle.STATE["prices"].values() if p["custom_data"]["tier"] == "team")
    assert team_price["quantity"]["minimum"] == PLANS["team"].min_seats
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(sync_prices.ProviderPrice)) == len(targets)
