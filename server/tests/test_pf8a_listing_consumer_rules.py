"""PF8a: a supplier's listing plan (`listing_<plan>`, PF8) is a business
contract, not a consumer subscription, so PF2b's consumer rules skip it
(`billing.service.is_consumer_plan`); and the listing sync matches a listing
row to its own subscription.

Rows are seeded through the app's models (no listing fee exists until GD7),
except the order confirmation, which runs PF2d's Stripe flow: the portal's
checkout, then the return page's refresh. Tests that read mail skip while
PF14's app.mail is missing (test_billing_pf2b.need_mail).
"""

import time
from datetime import datetime, timedelta, timezone

import pytest
import stripe
from sqlalchemy import select

from app.billing import consumer, jobs
from app.config import get_settings
from app.database import SessionLocal
from app.market.models import Supplier
from app.models import Payment, Subscription, SubscriptionExit, SubscriptionNotice
from app.supplier import listing
from app.supplier.models import ListingSubscription

from .conftest import STRIPE_SUBS
from .supplier_helpers import verified
from .test_billing_pf2b import LONG_AGO, approved_body, mails, need_mail
from .test_pf2d_billing_followups import _listing_fee, _me

OWNER = "owner@nord.example.com"


@pytest.fixture()
def rules(monkeypatch):
    """Flip PF2b settings for one test."""
    s = get_settings()

    def flip(**values):
        for name, value in values.items():
            monkeypatch.setattr(s, name, value)

    return flip


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _owner(client) -> tuple[dict, str, int]:
    """A verified supplier's owner: (headers, supplier id, user id)."""
    owner, sid = verified(client, OWNER)
    return owner, sid, _me(client, owner)["id"]


def _subscription(db, uid: int, plan: str, sub_id: str, *, interval="month", ends_in=timedelta(days=30), **kw):
    row = Subscription(
        user_id=uid, plan=plan, provider="stripe", status="active", interval=interval, currency="GBP", seats=1,
        provider_subscription_id=sub_id, provider_customer_id="cus_nord", current_period_end=_now() + ends_in, **kw,
    )  # fmt: skip
    db.add(row)
    db.flush()
    return row


def _payment(db, uid: int, plan: str, ref: str, *, status="paid", sub_id=None, paid_ago=timedelta(hours=1), **kw):
    row = Payment(
        user_id=uid, provider="stripe", plan=plan, reference=ref, provider_ref=f"cs_{ref}", amount=4900,
        currency="GBP", status=status, paid_at=_now() - paid_ago if status == "paid" else None, interval="month",
        seats=1, provider_subscription_id=sub_id, **kw,
    )  # fmt: skip
    db.add(row)
    db.flush()
    return row


def _checkout_row(db, sid: str, uid: int, ref: str, *, created_ago=timedelta(hours=1)) -> ListingSubscription:
    """The listing row `choose()` writes for a plan with a fee (PF8)."""
    row = ListingSubscription(
        supplier_id=sid, plan="standard", provider="stripe", status="checkout", currency="GBP", amount=4900,
        payment_ref=ref, created_by=uid, created_at=_now() - created_ago,
    )  # fmt: skip
    db.add(row)
    db.flush()
    return row


def _row_state(db, row_id: int) -> tuple[str, str | None]:
    row = db.get(ListingSubscription, row_id)
    db.refresh(row)
    return row.status, row.provider_subscription_id


# --- 1. Renewal reminders ------------------------------------------------------------------------


def test_listing_subscription_gets_no_renewal_reminder(client, monkeypatch, rules):
    """The DMCC switch on: a live listing plan due to renew (on its synced
    listing price, so it has an amount) gets no renewal reminder; the owner's
    own Pro plan, due the same day, still gets one, once."""
    mail = need_mail(pytest.importorskip("app.mail"))
    rules(subscription_notices_enabled=True, subscription_rules_from=LONG_AGO)
    _listing_fee(monkeypatch)  # the listing price, as sync_prices.py will sync it once GD7 sets the fee
    _, _, uid = _owner(client)
    with SessionLocal() as db:
        lst = _subscription(db, uid, "listing_standard", "sub_listing_1", ends_in=timedelta(days=2),
                            provider_price_id="price_listing_standard_gbp")  # fmt: skip
        pro = _subscription(db, uid, "pro", "sub_pro_1", ends_in=timedelta(days=2))
        db.commit()
        listing_id, pro_id = lst.id, pro.id
    mail.OUTBOX.clear()

    assert jobs.subscription_notices(_now()) == 1
    (msg,) = mail.OUTBOX  # the Pro reminder, and nothing about the listing plan
    assert msg.to == OWNER and msg.subject.startswith("Your Truebex Pro plan renews on")
    with SessionLocal() as db:
        notices_sent = db.scalars(select(SubscriptionNotice.subscription_id)).all()
    assert notices_sent == [pro_id] and listing_id not in notices_sent
    assert jobs.subscription_notices(_now()) == 0  # once per period


# --- 2. The order confirmation -------------------------------------------------------------------


def _paid_on_stripe(params: dict, sessions: dict, sub_id: str) -> str:
    """Stripe's side of a checkout created with `params`: the session,
    complete and paid, and the subscription it started. Returns our reference."""
    meta = params["metadata"]
    STRIPE_SUBS[sub_id] = {
        "id": sub_id, "object": "subscription", "customer": "cus_nord", "currency": "gbp", "status": "active",
        "cancel_at_period_end": False, "metadata": meta,
        "items": {"data": [{"id": f"si_{sub_id}", "quantity": 1, "current_period_end": int(time.time()) + 30 * 86400,
                            "price": {"id": params["line_items"][0]["price"], "recurring": {"interval": "month"}}}]},
    }  # fmt: skip
    sessions[params["id"]] = {
        "id": params["id"], "object": "checkout.session", "client_reference_id": params["client_reference_id"],
        "status": "complete", "payment_status": "paid", "subscription": sub_id, "invoice": f"in_{sub_id}",
        "metadata": meta, "customer_details": {"address": {"country": "GB"}},
    }  # fmt: skip
    return params["client_reference_id"]


def test_listing_checkout_gets_no_order_confirmation(client, stripe_prices, monkeypatch, rules):
    """LEGAL_WORDING_APPROVED on: a paid listing checkout gets no consumer
    order confirmation (the provider's receipt and the commission statements
    are its record); the owner's own Pro checkout still gets it."""
    mail = need_mail(pytest.importorskip("app.mail"))
    rules(legal_wording_approved=True)
    monkeypatch.setattr(get_settings(), "billing_provider", "stripe")
    created: list[dict] = []
    sessions: dict[str, dict] = {}

    def create(**params):
        params["id"] = f"cs_pf8a_{len(created) + 1}"
        created.append(params)
        return {"id": params["id"], "url": f"https://checkout.stripe.test/{params['id']}"}

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda sid, **k: sessions[sid])
    _listing_fee(monkeypatch)
    owner, _, _ = _owner(client)
    mail.OUTBOX.clear()  # the supplier's own mails (application, verified)

    # The listing plan, paid: back on the portal, the refresh verifies it.
    res = client.post("/supplier/listing", json={"plan": "standard"}, headers=owner)
    assert res.status_code == 200 and res.json()["state"] == "checkout", res.text
    listing_ref = _paid_on_stripe(created[-1], sessions, "sub_listing_1")
    paid = client.post(f"/billing/payments/{listing_ref}/refresh", headers=owner).json()
    assert (paid["status"], paid["plan"]) == ("paid", "listing_standard")
    assert mails(mail, "order") == []
    with SessionLocal() as db:
        row = db.scalar(select(Payment).where(Payment.reference == listing_ref))
        assert row.confirmation_sent_at is None
        assert consumer.payment_paid(db, row) is False  # a replayed event sends nothing either
    assert client.get("/supplier/listing", headers=owner).json()["plan"] == "standard"

    # The owner's own Pro plan: the consumer confirmation still goes, once.
    co = client.post("/billing/checkout", json=approved_body(), headers=owner)
    assert co.status_code == 200, co.text
    pro_ref = _paid_on_stripe(created[-1], sessions, "sub_pro_1")
    assert client.post(f"/billing/payments/{pro_ref}/refresh", headers=owner).json()["status"] == "paid"
    (msg,) = mails(mail, "order")
    assert msg.to == OWNER and msg.subject.endswith(": Pro") and pro_ref in msg.text
    assert listing_ref not in msg.text
    with SessionLocal() as db:
        assert db.scalar(select(Payment).where(Payment.reference == pro_ref)).confirmation_sent_at is not None
    assert _me(client, owner)["plan"] == "pro"


# --- 3. The paid checkout behind a subscription --------------------------------------------------


def test_paid_checkout_fallback_keeps_listing_and_app_apart(client, rules):
    """Payments from before PF2b name no subscription, so a subscription's
    paid checkout is its buyer's latest with the provider. One person with a
    paid Pro checkout and a paid listing checkout, both on Stripe: each
    subscription gets its own, whichever was paid last, and a one-off item is
    neither's. So the supplier's business payment never decides the person's
    EU withdrawal."""
    rules(eu_withdrawal_enabled=True)
    _, _, uid = _owner(client)
    with SessionLocal() as db:
        pro = _subscription(db, uid, "pro", "sub_pro")
        lst = _subscription(db, uid, "listing_standard", "sub_listing")
        _payment(db, uid, "pro", "tbx_pro", country="DE", business=False)
        _payment(db, uid, "listing_standard", "lst_listing", country="DE", business=True)
        _payment(db, uid, "ai_credits", "tbx_pack", country="DE", paid_ago=timedelta(minutes=1))
        db.commit()
        now = _now()
        for last in ("lst_listing", "tbx_pro"):
            for p in db.scalars(select(Payment).where(Payment.reference.in_(("tbx_pro", "lst_listing")))):
                p.paid_at = now - (timedelta(minutes=10) if p.reference == last else timedelta(hours=2))
            db.commit()
            assert consumer.checkout_payment(db, pro).reference == "tbx_pro", last
            assert consumer.checkout_payment(db, lst).reference == "lst_listing", last
            # The German consumer's Pro keeps its withdrawal (its own checkout: no business).
            assert consumer.withdrawal_until(db, pro, now) is not None, last


# --- 4. The listing sync -----------------------------------------------------------------------------


def test_listing_sync_matches_by_subscription_id(client):
    """Two checkouts for the same plan by one owner, one of them paid: only
    the paid one follows the subscription its payment names; the unpaid one
    matches nothing and expires after CHECKOUT_TTL. A paid checkout whose
    subscription is not stored yet waits for its own, never expires, and
    never takes the other's."""
    _, sid, uid = _owner(client)
    with SessionLocal() as db:
        _payment(db, uid, "listing_standard", "lst_unpaid", status="pending")
        _payment(db, uid, "listing_standard", "lst_paid", sub_id="sub_listing_1")
        _payment(db, uid, "listing_standard", "lst_waiting", sub_id="sub_listing_2")
        unpaid = _checkout_row(db, sid, uid, "lst_unpaid", created_ago=timedelta(hours=2))  # first in the sync
        paid = _checkout_row(db, sid, uid, "lst_paid")
        waiting = _checkout_row(db, sid, uid, "lst_waiting")
        _subscription(db, uid, "listing_standard", "sub_listing_1")
        db.commit()
        rows = {"unpaid": unpaid.id, "paid": paid.id, "waiting": waiting.id}

        now = _now()
        assert listing.sync(db, now) == 1
        assert {k: _row_state(db, v) for k, v in rows.items()} == {
            "unpaid": ("checkout", None),
            "paid": ("active", "sub_listing_1"),
            "waiting": ("checkout", None),
        }
        assert db.get(Supplier, sid).listing_plan == "standard"

        # A day later the unpaid checkout has expired; the paid ones have not.
        assert listing.sync(db, now + listing.CHECKOUT_TTL + timedelta(minutes=5)) == 1
        assert {k: _row_state(db, v) for k, v in rows.items()} == {
            "unpaid": ("expired", None),
            "paid": ("active", "sub_listing_1"),
            "waiting": ("checkout", None),
        }
        assert db.get(ListingSubscription, rows["unpaid"]).detail == "The checkout was not completed."

        # Its own subscription arrives: the waiting checkout follows it.
        _subscription(db, uid, "listing_standard", "sub_listing_2")
        db.commit()
        assert listing.sync(db, now) == 1
        assert _row_state(db, rows["waiting"]) == ("active", "sub_listing_2")
        assert _row_state(db, rows["paid"]) == ("active", "sub_listing_1")


def test_listing_sync_falls_back_to_owner_and_tier(client):
    """Rows from before PF2d: a paid checkout whose payment names no
    subscription is matched by owner and tier, to the newest listing_<plan>
    subscription that no other checkout or listing row names."""
    _, sid, uid = _owner(client)
    now = _now()
    with SessionLocal() as db:
        _payment(db, uid, "listing_standard", "lst_old_1", paid_ago=timedelta(days=60))
        _payment(db, uid, "listing_standard", "lst_old_2", paid_ago=timedelta(days=40))
        _payment(db, uid, "listing_standard", "lst_new", sub_id="sub_new")  # paid after PF2d
        old_1 = _checkout_row(db, sid, uid, "lst_old_1", created_ago=timedelta(days=60))
        old_2 = _checkout_row(db, sid, uid, "lst_old_2", created_ago=timedelta(days=40))
        new = _checkout_row(db, sid, uid, "lst_new")
        _subscription(db, uid, "listing_standard", "sub_a", updated_at=now - timedelta(days=50))
        _subscription(db, uid, "listing_standard", "sub_b", updated_at=now - timedelta(days=30))
        _subscription(db, uid, "listing_standard", "sub_new", updated_at=now)  # the newest
        db.commit()

        assert listing.sync(db, now) == 3
        assert _row_state(db, new.id) == ("active", "sub_new")
        old = {_row_state(db, old_1.id), _row_state(db, old_2.id)}
        assert old == {("active", "sub_a"), ("active", "sub_b")}
        supplier = db.get(Supplier, sid)
        assert (supplier.listing_plan, supplier.billing_customer_id) == ("standard", "cus_nord")
        assert listing.sync(db, now) == 0  # in step: nothing changes


# --- 5. The exits and the Billing page's exit offers ------------------------------------------------


def _listing_then_pro(client, *, interval="month"):
    """The owner's live listing plan, paid from Germany without a VAT id (as
    a consumer's checkout would look) and renewed yesterday. Returns the
    owner's headers, the listing subscription and a function that adds the
    owner's own Pro plan, paid and renewed the same way."""
    owner, _, uid = _owner(client)

    def plan(tier: str, sub_id: str, ref: str) -> Subscription:
        with SessionLocal() as db:
            sub = _subscription(db, uid, tier, sub_id, interval=interval, ends_in=timedelta(days=300),
                                renewed_at=_now() - timedelta(days=1), renewal_charge_id=f"in_{sub_id}")  # fmt: skip
            _payment(db, uid, tier, ref, sub_id=sub_id, country="DE", business=False)
            db.commit()
            db.refresh(sub)
            db.expunge(sub)
            return sub

    return owner, plan("listing_standard", "sub_listing", "lst_listing"), lambda: plan("pro", "sub_pro", "tbx_pro")


def _offers(client, owner) -> dict:
    res = client.get("/billing/subscription", headers=owner)
    assert res.status_code == 200, res.text
    body = res.json()
    return {k: body[k] for k in ("tier", "can_cancel", "cooling_off_until", "withdrawal_until")}


def test_listing_plan_offers_no_easy_exit(client, monkeypatch):
    """Cancel in Billing (the easy exit) is a consumer's: a listing plan is
    never offered it, even asked directly, and Billing's cancel acts only on
    the owner's own Pro plan."""
    calls: list = []
    monkeypatch.setattr(stripe.Subscription, "modify", lambda sid, **k: calls.append((sid, k)) or {"id": sid})
    owner, lst, add_pro = _listing_then_pro(client)
    with SessionLocal() as db:
        assert consumer.can_cancel(db, lst) is False
    assert _offers(client, owner) == {"tier": "free", "can_cancel": False, "cooling_off_until": None,
                                      "withdrawal_until": None}  # fmt: skip
    assert client.post("/billing/cancel", json={"confirm": True}, headers=owner).status_code == 404

    pro = add_pro()
    with SessionLocal() as db:
        assert consumer.can_cancel(db, pro) is True and consumer.can_cancel(db, lst) is False
    assert _offers(client, owner)["can_cancel"] is True
    res = client.post("/billing/cancel", json={"confirm": True}, headers=owner)
    assert res.status_code == 200 and res.json()["kind"] == "cancel", res.text
    assert [sid for sid, _ in calls] == ["sub_pro"]
    with SessionLocal() as db:
        assert db.scalars(select(SubscriptionExit.subscription_id)).all() == [pro.id]


def test_listing_plan_offers_no_cooling_off_refund(client, rules):
    """The renewal cooling-off (DMCC) is a consumer's: a listing plan renewed
    yesterday is not offered "Cancel and get a refund"; the owner's own
    annual Pro, renewed the same day, is."""
    rules(subscription_notices_enabled=True, subscription_rules_from=LONG_AGO)
    owner, lst, add_pro = _listing_then_pro(client, interval="year")
    with SessionLocal() as db:
        assert consumer.cooling_off_until(db, lst) is None
    assert _offers(client, owner)["cooling_off_until"] is None
    assert client.post("/billing/cancel", json={"confirm": True, "refund": True}, headers=owner).status_code == 404

    pro = add_pro()
    with SessionLocal() as db:
        assert consumer.cooling_off_until(db, pro) is not None
        assert consumer.cooling_off_until(db, lst) is None
    assert _offers(client, owner)["cooling_off_until"] is not None


def test_listing_plan_offers_no_eu_withdrawal(client, rules):
    """The EU withdrawal function is a consumer's: a listing plan paid from
    Germany without a VAT id is not offered "Withdraw from contract"; the
    owner's own Pro, paid the same way, is."""
    rules(eu_withdrawal_enabled=True)
    owner, lst, add_pro = _listing_then_pro(client)
    with SessionLocal() as db:
        assert consumer.withdrawal_until(db, lst) is None
    assert _offers(client, owner)["withdrawal_until"] is None
    assert client.post("/billing/withdraw", json={"confirm": True}, headers=owner).status_code == 404

    pro = add_pro()
    with SessionLocal() as db:
        assert consumer.withdrawal_until(db, pro) is not None
        assert consumer.withdrawal_until(db, lst) is None
    assert _offers(client, owner)["withdrawal_until"] is not None
