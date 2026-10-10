"""PF2b: subscription consumer rules (GD5 §7.1-7.4), built switched off.

DMCC Act 2024 reminder notices and the renewal cooling-off, the easy exit,
the EU withdrawal function (Directive 2011/83/EU Art. 11a), the key
pre-contract information and the confirmation on a durable medium. Paddle is
tests/mock_paddle.py served in-process; Stripe calls are monkeypatched.

Mail is PF14's console backend (app.mail.OUTBOX). Every test that reads mail
starts with pytest.importorskip("app.mail") and skips while PF14 is not merged
into this branch; the others run either way.
"""

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import stripe
from sqlalchemy import func, select

from app import tasks
from app.billing import consent, consumer, jobs, notices, pricing
from app.config import get_settings
from app.database import SessionLocal
from app.models import Payment, Subscription, SubscriptionExit, SubscriptionNotice
from app.plans import PLANS

from .conftest import STRIPE_SUBS, checkout_body, signup
from .test_billing import stripe_post, stripe_sub_event
from .test_billing_pf2 import me, paddle_post, txn_of

REPO = Path(__file__).resolve().parents[2]
LONG_AGO = date(2020, 1, 1)


# --- helpers --------------------------------------------------------------------------


def need_mail(mod):
    """`mod` is pytest.importorskip("app.mail"). Before PF14 is merged only
    PF2b's templates are in app/mail/, which then imports as an empty
    namespace package: skip in that case too. Returns the module, its OUTBOX
    emptied."""
    if not hasattr(mod, "send_mail"):
        pytest.skip("PF14's app.mail (send_mail, OUTBOX) is not merged into this branch yet")
    mod.OUTBOX.clear()
    return mod


@pytest.fixture()
def rules(monkeypatch):
    """Flip PF2b settings for one test."""
    s = get_settings()

    def flip(**values):
        for name, value in values.items():
            monkeypatch.setattr(s, name, value)

    return flip


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def approved_body(variant="digital_content", **kw):
    body = checkout_body(**kw)
    body["consent"] = {"version": notices.CONSENT_DRAFT[variant].version, "accepted": True}
    body["key_info"] = {"version": notices.KEY_INFO.version, "acknowledged": True}
    return body


def buy(client, h, paddle, *, country="GB", business=False, body=None, deliver=True, **kw):
    """Checkout, pay on the mock from `country`, deliver the webhooks."""
    body = body or checkout_body(**kw)
    if business:
        body["business"] = True
    res = client.post("/billing/checkout", json=body, headers=h)
    assert res.status_code == 200, res.text
    co = res.json()
    events = paddle.pay(txn_of(co["url"]), country=country, business=business)
    if deliver:
        for ev in events:
            assert paddle_post(client, ev).status_code == 200
    return co, events


def deliver_sent(client, paddle, since=0):
    """Deliver the events the mock produced after `since` (the API's own calls)."""
    for ev in paddle.STATE["sent"][since:]:
        assert paddle_post(client, ev).status_code == 200


def local_sub(**where) -> Subscription:
    with SessionLocal() as db:
        q = select(Subscription).order_by(Subscription.id.desc())
        for name, value in where.items():
            q = q.where(getattr(Subscription, name) == value)
        return db.scalar(q)


def payment(reference: str) -> Payment:
    with SessionLocal() as db:
        return db.scalar(select(Payment).where(Payment.reference == reference))


def mails(mail, subject_part: str) -> list:
    return [m for m in mail.OUTBOX if subject_part in m.subject]


def sub_view(client, h) -> dict:
    res = client.get("/billing/subscription", headers=h)
    assert res.status_code == 200, res.text
    return res.json()


# --- settings and wording --------------------------------------------------------------


def test_pf2b_settings_off_by_default(client):
    s = get_settings()
    assert s.subscription_notices_enabled is False
    assert s.subscription_rules_from == date(2027, 1, 1)
    assert s.eu_withdrawal_enabled is False
    assert s.legal_wording_approved is False
    assert s.consent_variant == "digital_content"
    # GD5 names no lead time: 14 days before an annual renewal, 3 before a monthly one.
    assert (s.renewal_reminder_days_year, s.renewal_reminder_days_month, s.trial_end_notice_days) == (14, 3, 3)
    cat = client.get("/billing/plans").json()
    assert cat["rules"] == {
        "wording_approved": False,
        "consent_variant": "digital_content",
        "consent_version": consent.CONSENT_VERSION,
        "key_info_version": None,
        "eu_withdrawal": False,
        "renewal_notices": False,
    }


def test_pf2b_wording_matches_site():
    """notices.py and BILLING in constants.ts carry the same texts and versions."""
    ts = (REPO / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")

    def literal(key: str) -> str:
        m = re.search(rf'\b{key}:\s*"((?:[^"\\]|\\.)*)"', ts)
        assert m, f"{key} missing from constants.ts"
        return m.group(1).replace('\\"', '"')

    assert literal("draftVersion") == notices.DRAFT_VERSION
    assert literal("keyInfo") == notices.KEY_INFO.text
    assert literal("keyInfoAck") == notices.KEY_INFO_ACK.text
    assert literal("consentDigital") == notices.CONSENT_DRAFT["digital_content"].text
    assert literal("consentDigitalVersion") == notices.CONSENT_DRAFT["digital_content"].version
    assert literal("consentService") == notices.CONSENT_DRAFT["service"].text
    assert literal("consentServiceVersion") == notices.CONSENT_DRAFT["service"].version
    assert literal("business") == notices.BUSINESS.text
    assert literal("trialEnd") == notices.TRIAL_END.text
    assert literal("withdrawButton") == notices.WITHDRAW_BUTTON.text
    assert literal("withdrawConfirm") == notices.WITHDRAW_CONFIRM.text
    assert literal("withdrawAck") == notices.WITHDRAW_ACK.text
    assert literal("sellerPaddle") == notices.SELLERS["paddle"]
    assert literal("sellerStripe") == notices.SELLERS["stripe"]
    assert literal("noticeVersion") == notices.NOTICE_VERSION
    assert literal("renewalReminder") == notices.RENEWAL_REMINDER.text
    assert literal("renewalCoolingOff") == notices.RENEWAL_COOLING_OFF.text
    # The 7.4 drafts compile into the site only with the build-time flag.
    assert "process.env.NEXT_PUBLIC_LEGAL_WORDING_APPROVED" in ts


# --- reminder notices (DMCC) ----------------------------------------------------------------


def test_notices_off_by_default(client, paddle, rules):
    h = signup(client)
    buy(client, h, paddle)
    uid = me(client, h)["id"]
    with SessionLocal() as db:
        db.add(Subscription(user_id=uid, plan="pro", provider="trial", status="active",
                            current_period_end=datetime.now(timezone.utc) + timedelta(days=2)))
        db.commit()
    assert "billing.subscription_notices" in tasks.jobs()
    end = aware(local_sub(provider="paddle").current_period_end)
    at = end - timedelta(days=2)
    # Flag off: nothing, however close the renewal.
    assert jobs.subscription_notices(at) == 0
    # Flag on, but before the rules start: nothing either.
    rules(subscription_notices_enabled=True, legal_wording_approved=True,
          subscription_rules_from=(at + timedelta(days=1)).date())
    assert jobs.subscription_notices(at) == 0
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SubscriptionNotice)) == 0


def test_pf2b_without_mail_logs_and_does_nothing(client, paddle, rules, monkeypatch, caplog):
    """Until PF14's send_mail is importable the notices job logs and does
    nothing, and an exit is still recorded and sent to the provider; its
    confirmation waits for billing.exits.retry."""
    monkeypatch.setattr(notices, "send_mail", None)
    rules(subscription_notices_enabled=True, subscription_rules_from=LONG_AGO)
    h = signup(client)
    buy(client, h, paddle)
    end = aware(local_sub(provider="paddle").current_period_end)
    caplog.set_level("WARNING")
    assert jobs.subscription_notices(end - timedelta(days=2)) == 0
    assert "not merged" in caplog.text
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SubscriptionNotice)) == 0
    res = client.post("/billing/cancel", json={"confirm": True}, headers=h)
    assert res.status_code == 200 and res.json()["status"] == "done"
    assert paddle.STATE["cancels"][-1]["effective_from"] == "next_billing_period"
    with SessionLocal() as db:
        exit_ = db.scalar(select(SubscriptionExit))
        assert exit_.canceled_at is not None and exit_.mail_sent_at is None


def test_renewal_reminder_sent_once_per_period(client, paddle, rules):
    mail = need_mail(pytest.importorskip("app.mail"))
    rules(subscription_notices_enabled=True, subscription_rules_from=LONG_AGO)
    h = signup(client)
    co, events = buy(client, h, paddle)
    sub_id = local_sub(provider="paddle").provider_subscription_id
    end = aware(local_sub(provider="paddle").current_period_end)
    mail.OUTBOX.clear()

    assert jobs.subscription_notices(end - timedelta(days=4)) == 0  # 3-day lead for monthly
    assert jobs.subscription_notices(end - timedelta(days=2)) == 1
    assert jobs.subscription_notices(end - timedelta(days=1)) == 0  # once per period
    (msg,) = mails(mail, "renews")
    assert msg.to == "dev@example.com"
    amount = pricing.amount("pro", "month", "GBP", co["founding"])
    assert consumer.money(amount, "GBP") in msg.text
    assert consumer.long_date(end) in msg.text
    assert "/dashboard/billing/" in msg.text
    # A monthly renewal has no renewal cooling-off line.
    assert notices.RENEWAL_COOLING_OFF.text not in msg.text

    # The next period gets its own reminder.
    deliver = paddle.renew(sub_id)
    for ev in deliver:
        assert paddle_post(client, ev).status_code == 200
    new_end = aware(local_sub(provider="paddle").current_period_end)
    assert new_end > end
    assert jobs.subscription_notices(new_end - timedelta(days=2)) == 1
    assert len(mails(mail, "renews")) == 2
    with SessionLocal() as db:
        rows = db.scalars(select(SubscriptionNotice).order_by(SubscriptionNotice.id)).all()
        assert [r.kind for r in rows] == ["renewal_reminder", "renewal_reminder"]

    # Annual: 14 days ahead, with the renewal cooling-off line.
    h2 = signup(client, email="annual@example.com")
    buy(client, h2, paddle, interval="year")
    annual_end = aware(local_sub(provider="paddle", interval="year").current_period_end)
    assert jobs.subscription_notices(annual_end - timedelta(days=15)) == 0
    assert jobs.subscription_notices(annual_end - timedelta(days=10)) == 1
    annual = [m for m in mails(mail, "renews") if m.to == "annual@example.com"]
    assert len(annual) == 1 and notices.RENEWAL_COOLING_OFF.text in annual[0].text

    # Set to end at the period end: no reminder.
    h3 = signup(client, email="leaving@example.com")
    buy(client, h3, paddle)
    leaving = local_sub(provider="paddle")
    paddle.cancel_at_period_end(leaving.provider_subscription_id)
    deliver_sent(client, paddle, len(paddle.STATE["sent"]) - 1)
    assert local_sub(provider="paddle").cancel_at_period_end is True
    assert jobs.subscription_notices(aware(leaving.current_period_end) - timedelta(days=2)) == 0
    assert not [m for m in mail.OUTBOX if m.to == "leaving@example.com"]


def test_trial_end_notice(client, rules):
    mail = need_mail(pytest.importorskip("app.mail"))
    rules(subscription_notices_enabled=True, subscription_rules_from=LONG_AGO)
    h = signup(client)
    uid = me(client, h)["id"]
    end = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=10)
    with SessionLocal() as db:
        db.add(Subscription(user_id=uid, plan="pro", provider="trial", status="active", current_period_end=end))
        db.commit()
    # The trial text is GD5 7.4 draft wording: not sent until it is approved.
    assert jobs.subscription_notices(end - timedelta(days=2)) == 0
    rules(legal_wording_approved=True)
    assert jobs.subscription_notices(end - timedelta(days=4)) == 0  # 3 days ahead, not 4
    assert jobs.subscription_notices(end - timedelta(days=2)) == 1
    assert jobs.subscription_notices(end - timedelta(days=1)) == 0  # once
    (msg,) = mails(mail, "trial")
    assert msg.to == "dev@example.com"
    expected = notices.TRIAL_END.render(days=get_settings().trial_days, plan="Pro", date=consumer.long_date(end))
    assert expected in msg.text
    # A trial that ended (a purchase, or it lapsed) gets nothing.
    h2 = signup(client, email="ended@example.com")
    uid2 = me(client, h2)["id"]
    with SessionLocal() as db:
        db.add(Subscription(user_id=uid2, plan="pro", provider="trial", status="canceled", current_period_end=end))
        db.commit()
    assert jobs.subscription_notices(end - timedelta(days=2)) == 0


# --- easy exit ------------------------------------------------------------------------------------


def test_cancel_easy_exit(client, paddle):
    assert client.post("/billing/cancel", json={"confirm": True}).status_code == 401
    h = signup(client)
    assert client.post("/billing/cancel", json={"confirm": True}, headers=h).status_code == 404
    buy(client, h, paddle)
    sub = local_sub(provider="paddle")
    # The confirm step is required, and must be a real true.
    assert client.post("/billing/cancel", json={}, headers=h).status_code == 422
    assert client.post("/billing/cancel", json={"confirm": False}, headers=h).status_code == 422
    assert client.post("/billing/cancel", json={"confirm": True, "refund": "maybe"}, headers=h).status_code == 422
    view = sub_view(client, h)
    assert view["can_cancel"] is True and view["cooling_off_until"] is None and view["withdrawal_until"] is None

    sent = len(paddle.STATE["sent"])
    res = client.post("/billing/cancel", json={"confirm": True}, headers=h)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["kind"] == "cancel" and out["status"] == "done" and out["refund_minor"] is None
    assert aware(datetime.fromisoformat(out["effective_at"])) == aware(sub.current_period_end)
    # Asked the provider to cancel at the period end, inside Billing (no portal).
    assert paddle.STATE["cancels"][-1] == {
        "subscription_id": sub.provider_subscription_id, "effective_from": "next_billing_period"
    }
    assert paddle.STATE["subscriptions"][sub.provider_subscription_id]["scheduled_change"]["action"] == "cancel"
    # Our state waits for the provider's signed webhook.
    view = sub_view(client, h)
    assert view["cancel_at_period_end"] is False and view["can_cancel"] is False
    assert client.post("/billing/cancel", json={"confirm": True}, headers=h).status_code == 409
    with SessionLocal() as db:
        exit_ = db.scalar(select(SubscriptionExit))
        assert exit_.kind == "cancel" and exit_.canceled_at is not None

    deliver_sent(client, paddle, sent)
    view = sub_view(client, h)
    assert view["cancel_at_period_end"] is True and view["tier"] == "pro" and view["can_cancel"] is False
    assert me(client, h)["plan"] == "pro"
    assert client.post("/billing/cancel", json={"confirm": True}, headers=h).status_code == 409
    # The portal link stays.
    assert client.post("/billing/portal", headers=h).status_code == 200


def test_exit_retry_job(client, paddle, monkeypatch):
    """A cancellation the provider could not take is recorded and finished by
    billing.exits.retry."""
    from app.billing import paddle_provider

    h = signup(client)
    buy(client, h, paddle)
    original = paddle_provider.PaddleProvider.cancel_subscription

    def down(self, db, sub, *, immediately):
        raise paddle_provider.ProviderError("Paddle unreachable")

    monkeypatch.setattr(paddle_provider.PaddleProvider, "cancel_subscription", down)
    res = client.post("/billing/cancel", json={"confirm": True}, headers=h)
    assert res.status_code == 200 and res.json()["status"] == "processing"
    assert client.post("/billing/cancel", json={"confirm": True}, headers=h).status_code == 409
    monkeypatch.setattr(paddle_provider.PaddleProvider, "cancel_subscription", original)
    assert "billing.exits.retry" in tasks.jobs()
    assert jobs.retry_exits(datetime.now(timezone.utc)) == 1
    assert paddle.STATE["cancels"][-1]["effective_from"] == "next_billing_period"
    assert jobs.retry_exits(datetime.now(timezone.utc)) == 0


# --- renewal cooling-off (DMCC) ---------------------------------------------------------------------


def test_renewal_cooling_off_refund_via_provider_mock(client, paddle, rules):
    h = signup(client)
    buy(client, h, paddle, interval="year")
    sub = local_sub(provider="paddle")
    renewal = paddle.renew(sub.provider_subscription_id)
    for ev in renewal:
        assert paddle_post(client, ev).status_code == 200
    renewal_txn = next(e for e in renewal if e["event_type"] == "transaction.completed")["data"]
    sub = local_sub(provider="paddle")
    assert sub.renewed_at is not None and sub.renewal_charge_id == renewal_txn["id"]

    # Behind the flag: not offered and refused while the DMCC rules are off.
    assert sub_view(client, h)["cooling_off_until"] is None
    assert client.post("/billing/cancel", json={"confirm": True, "refund": True}, headers=h).status_code == 409
    rules(subscription_notices_enabled=True, subscription_rules_from=LONG_AGO)
    until = sub_view(client, h)["cooling_off_until"]
    assert until is not None
    assert timedelta(days=14) <= aware(datetime.fromisoformat(until)) - aware(sub.renewed_at) < timedelta(days=15)

    sent = len(paddle.STATE["sent"])
    res = client.post("/billing/cancel", json={"confirm": True, "refund": True}, headers=h)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["kind"] == "cooling_off" and out["status"] == "done"
    assert 0 < out["refund_minor"] <= int(renewal_txn["details"]["totals"]["grand_total"])
    # The provider is asked: cancel now, refund the renewal charge.
    assert paddle.STATE["cancels"][-1] == {
        "subscription_id": sub.provider_subscription_id, "effective_from": "immediately"
    }
    adj = paddle.STATE["adjustments"][-1]
    assert adj["action"] == "refund" and adj["transaction_id"] == renewal_txn["id"]
    # The plan changes only from the provider's verified webhook.
    assert me(client, h)["plan"] == "pro"
    assert client.post("/billing/cancel", json={"confirm": True, "refund": True}, headers=h).status_code == 409
    forged = paddle.event("subscription.canceled", {**paddle.STATE["subscriptions"][sub.provider_subscription_id]})
    assert paddle_post(client, forged, secret="pdl_ntfset_wrong").status_code == 400
    assert me(client, h)["plan"] == "pro"
    deliver_sent(client, paddle, sent)
    assert me(client, h)["plan"] == "free"

    # Outside the 14 days: refused.
    h2 = signup(client, email="late@example.com")
    buy(client, h2, paddle, interval="year")
    late = local_sub(provider="paddle")
    for ev in paddle.renew(late.provider_subscription_id):
        paddle_post(client, ev)
    with SessionLocal() as db:
        row = db.get(Subscription, late.id)
        row.renewed_at = datetime.now(timezone.utc) - timedelta(days=15)
        db.commit()
    assert sub_view(client, h2)["cooling_off_until"] is None
    assert client.post("/billing/cancel", json={"confirm": True, "refund": True}, headers=h2).status_code == 409
    # A monthly renewal has no cooling-off.
    h3 = signup(client, email="monthly@example.com")
    buy(client, h3, paddle)
    monthly = local_sub(provider="paddle")
    for ev in paddle.renew(monthly.provider_subscription_id):
        paddle_post(client, ev)
    assert sub_view(client, h3)["cooling_off_until"] is None


def test_renewal_cooling_off_refund_stripe(client, stripe_prices, monkeypatch, rules):
    rules(subscription_notices_enabled=True, subscription_rules_from=LONG_AGO)
    h = signup(client)
    uid = me(client, h)["id"]
    end = int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp())
    # Pro annual in GBP from the catalogue (PF2a's prices), charged with 20 % VAT.
    year_gbp = next(p.amount_minor for p in PLANS["pro"].prices if (p.interval, p.currency) == ("year", "GBP"))
    paid = year_gbp * 6 // 5
    price = stripe_prices[f"truebex_pro_year_gbp_{year_gbp}"]
    ev = stripe_sub_event("customer.subscription.created", uid, "active", end, price=price, sub_id="sub_y1",
                          meta={"user_id": str(uid), "plan": "pro"}, interval="year")
    assert stripe_post(client, ev).status_code == 200
    # Stripe tells us about the renewal with a signed invoice.paid (billing_reason subscription_cycle).
    invoice = {"id": "in_renew", "object": "invoice", "billing_reason": "subscription_cycle",
               "subscription": "sub_y1", "status": "paid", "amount_paid": paid, "currency": "gbp",
               "payment_intent": "pi_renew", "status_transitions": {"paid_at": int(datetime.now(timezone.utc).timestamp())}}
    renewal = {"id": "evt_inv_1", "type": "invoice.paid", "created": int(datetime.now(timezone.utc).timestamp()),
               "data": {"object": invoice}}
    assert stripe_post(client, renewal).status_code == 200
    sub = local_sub(provider="stripe")
    assert sub.renewal_charge_id == "in_renew" and sub.renewed_at is not None
    assert sub_view(client, h)["cooling_off_until"] is not None

    calls: dict = {}
    monkeypatch.setattr(stripe.Subscription, "cancel", lambda sid, **k: calls.setdefault("cancel", sid) and {"id": sid})
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda iid, **k: invoice if iid == "in_renew" else None)
    monkeypatch.setattr(stripe.Refund, "create", lambda **k: calls.setdefault("refund", k) and {"id": "re_1", **k})
    res = client.post("/billing/cancel", json={"confirm": True, "refund": True}, headers=h)
    assert res.status_code == 200, res.text
    assert calls["cancel"] == "sub_y1"
    assert calls["refund"]["payment_intent"] == "pi_renew" and 0 < calls["refund"]["amount"] <= paid
    assert res.json()["refund_minor"] == calls["refund"]["amount"]
    # Still Pro until Stripe's signed customer.subscription.deleted.
    assert me(client, h)["plan"] == "pro"
    gone = stripe_sub_event("customer.subscription.deleted", uid, "canceled", end, price=price, sub_id="sub_y1",
                            meta={"user_id": str(uid), "plan": "pro"}, interval="year")
    assert stripe_post(client, gone).status_code == 200
    assert me(client, h)["plan"] == "free"
    assert STRIPE_SUBS["sub_y1"]["status"] == "canceled"


# --- EU withdrawal function (Art. 11a) -----------------------------------------------------------------


def test_eu_withdrawal_flow(client, paddle, rules):
    mail = need_mail(pytest.importorskip("app.mail"))
    assert client.post("/billing/withdraw", json={"confirm": True}).status_code == 401
    h = signup(client)
    co, events = buy(client, h, paddle, country="DE")
    pay = payment(co["reference"])
    assert pay.country == "DE" and pay.business is False
    # Flag off: no button, and the endpoint refuses.
    assert sub_view(client, h)["withdrawal_until"] is None
    assert client.post("/billing/withdraw", json={"confirm": True}, headers=h).status_code == 404

    rules(eu_withdrawal_enabled=True)
    until = sub_view(client, h)["withdrawal_until"]
    assert until is not None
    assert timedelta(days=14) <= aware(datetime.fromisoformat(until)) - aware(pay.paid_at) < timedelta(days=15)
    assert client.post("/billing/withdraw", json={}, headers=h).status_code == 422
    assert client.post("/billing/withdraw", json={"confirm": "yes please"}, headers=h).status_code == 422

    mail.OUTBOX.clear()
    sent = len(paddle.STATE["sent"])
    res = client.post("/billing/withdraw", json={"confirm": True}, headers=h)
    assert res.status_code == 200, res.text
    out = res.json()
    checkout_txn = next(e for e in events if e["event_type"] == "transaction.completed")["data"]
    # Placeholder consent and no confirmation on a durable medium: the right
    # stayed whole, so the whole first payment comes back.
    assert out["kind"] == "withdrawal" and out["refund_minor"] == int(checkout_txn["details"]["totals"]["grand_total"])
    sub = local_sub(provider="paddle")
    assert paddle.STATE["cancels"][-1] == {
        "subscription_id": sub.provider_subscription_id, "effective_from": "immediately"
    }
    adj = paddle.STATE["adjustments"][-1]
    assert adj["transaction_id"] == checkout_txn["id"] and adj["type"] == "full"
    # The acknowledgement on a durable medium, with the date and time.
    (ack,) = mails(mail, "withdrawal")
    requested = aware(datetime.fromisoformat(out["requested_at"]))
    assert consumer.long_date(requested) in ack.text and requested.strftime("%H:%M") in ack.text
    assert notices.WITHDRAW_ACK.render(plan="Pro", date=consumer.long_date(requested),
                                       time=requested.strftime("%H:%M")) in ack.text
    assert client.post("/billing/withdraw", json={"confirm": True}, headers=h).status_code == 409
    assert me(client, h)["plan"] == "pro"
    deliver_sent(client, paddle, sent)
    assert me(client, h)["plan"] == "free"

    # Not for a consumer outside the EU.
    h2 = signup(client, email="uk@example.com")
    buy(client, h2, paddle, country="GB")
    assert sub_view(client, h2)["withdrawal_until"] is None
    assert client.post("/billing/withdraw", json={"confirm": True}, headers=h2).status_code == 409
    # Never for a business purchase.
    h3 = signup(client, email="firm@example.com")
    co3, _ = buy(client, h3, paddle, country="FR", business=True)
    assert payment(co3["reference"]).business is True
    assert sub_view(client, h3)["withdrawal_until"] is None
    assert client.post("/billing/withdraw", json={"confirm": True}, headers=h3).status_code == 409
    # Not after the withdrawal period.
    h4 = signup(client, email="late@example.com")
    co4, _ = buy(client, h4, paddle, country="IE")
    with SessionLocal() as db:
        row = db.scalar(select(Payment).where(Payment.reference == co4["reference"]))
        row.paid_at = datetime.now(timezone.utc) - timedelta(days=16)
        db.commit()
    assert sub_view(client, h4)["withdrawal_until"] is None
    assert client.post("/billing/withdraw", json={"confirm": True}, headers=h4).status_code == 409


def test_eu_withdrawal_rules_without_mail(client, paddle, rules):
    """The withdrawal's rules and provider steps, which need no mail: off ->
    404; inside the window for an EU consumer -> cancel now and refund in
    full, the plan changing only from the webhook; outside the EU, a business
    purchase or after the period -> 409."""
    h = signup(client)
    co, events = buy(client, h, paddle, country="DE")
    assert client.post("/billing/withdraw", json={"confirm": True}, headers=h).status_code == 404
    rules(eu_withdrawal_enabled=True)
    assert sub_view(client, h)["withdrawal_until"] is not None
    assert client.post("/billing/withdraw", json={"confirm": False}, headers=h).status_code == 422
    sent = len(paddle.STATE["sent"])
    res = client.post("/billing/withdraw", json={"confirm": True}, headers=h)
    assert res.status_code == 200 and res.json()["kind"] == "withdrawal"
    checkout_txn = next(e for e in events if e["event_type"] == "transaction.completed")["data"]
    assert paddle.STATE["adjustments"][-1]["transaction_id"] == checkout_txn["id"]
    assert paddle.STATE["cancels"][-1]["effective_from"] == "immediately"
    assert me(client, h)["plan"] == "pro"
    deliver_sent(client, paddle, sent)
    assert me(client, h)["plan"] == "free"
    for email, country, business in (("uk@example.com", "GB", False), ("firm@example.com", "FR", True)):
        hx = signup(client, email=email)
        buy(client, hx, paddle, country=country, business=business)
        assert sub_view(client, hx)["withdrawal_until"] is None
        assert client.post("/billing/withdraw", json={"confirm": True}, headers=hx).status_code == 409
    h4 = signup(client, email="late@example.com")
    co4, _ = buy(client, h4, paddle, country="IE")
    with SessionLocal() as db:
        db.scalar(select(Payment).where(Payment.reference == co4["reference"])).paid_at = (
            datetime.now(timezone.utc) - timedelta(days=16)
        )
        db.commit()
    assert client.post("/billing/withdraw", json={"confirm": True}, headers=h4).status_code == 409


def test_eu_withdrawal_after_complete_waiver_is_not_offered(client, paddle, rules):
    """Digital content: consent, acknowledgement and the confirmation mail
    together end the right (reg. 37, Art. 16(m)); the button then stays away."""
    mail = need_mail(pytest.importorskip("app.mail"))
    rules(eu_withdrawal_enabled=True, legal_wording_approved=True)
    h = signup(client)
    buy(client, h, paddle, country="NL", body=approved_body())
    assert len(mails(mail, "order")) == 1
    assert sub_view(client, h)["withdrawal_until"] is None
    # The service variant keeps the right (the customer pays for the days used).
    rules(consent_variant="service")
    h2 = signup(client, email="svc@example.com")
    co2, _ = buy(client, h2, paddle, country="NL", body=approved_body("service"))
    assert sub_view(client, h2)["withdrawal_until"] is not None
    res = client.post("/billing/withdraw", json={"confirm": True}, headers=h2)
    assert res.status_code == 200
    paid = payment(co2["reference"]).amount
    assert 0 < res.json()["refund_minor"] <= paid
    assert paddle.STATE["adjustments"][-1]["type"] in ("full", "partial")


# --- key information and the confirmation -------------------------------------------------------------


def test_key_information_acknowledged_with_payment(client, paddle, rules):
    h = signup(client)
    # Off: today's placeholder consent, no key information asked or stored.
    res = client.post("/billing/checkout", json=checkout_body(), headers=h)
    assert res.status_code == 200 and res.json()["key_info"] is None
    first = payment(res.json()["reference"])
    assert first.key_info is None and first.key_info_version is None
    assert first.consent_version == consent.CONSENT_VERSION

    rules(legal_wording_approved=True)
    cat = client.get("/billing/plans").json()["rules"]
    assert cat["wording_approved"] is True and cat["key_info_version"] == notices.KEY_INFO.version
    assert cat["consent_version"] == notices.CONSENT_DRAFT["digital_content"].version
    # The placeholder consent no longer passes; the key information must be acknowledged.
    assert client.post("/billing/checkout", json=checkout_body(), headers=h).status_code == 422
    body = approved_body()
    del body["key_info"]
    assert client.post("/billing/checkout", json=body, headers=h).status_code == 422
    body = approved_body()
    body["key_info"]["version"] = "1999-01-01"
    assert client.post("/billing/checkout", json=body, headers=h).status_code == 422
    body = approved_body()
    body["key_info"]["acknowledged"] = False
    assert client.post("/billing/checkout", json=body, headers=h).status_code == 422

    res = client.post("/billing/checkout", json=approved_body(tier="team", seats=3, interval="year"), headers=h)
    assert res.status_code == 200, res.text
    co = res.json()
    total = pricing.amount("team", "year", "GBP", co["founding"]) * 3
    expected = notices.KEY_INFO.render(
        plan="Team, 3 seats", price=consumer.money(total, "GBP"), interval="year", currency="GBP",
        seller=notices.SELLERS["paddle"],
    )
    assert co["key_info"] == expected
    assert "Renews automatically every year" in expected and "Sold by Paddle.com" in expected
    row = payment(co["reference"])
    assert row.key_info == expected and row.key_info_version == notices.KEY_INFO.version
    assert row.key_info_at is not None and row.consent_version == notices.CONSENT_DRAFT["digital_content"].version

    # The /checkout/ page reads it back to show beside the pay button.
    got = client.get(f"/billing/payments/{co['reference']}", headers=h)
    assert got.status_code == 200 and got.json()["key_info"] == expected
    assert client.get(f"/billing/payments/{co['reference']}").status_code == 401
    other = signup(client, email="other@example.com")
    assert client.get(f"/billing/payments/{co['reference']}", headers=other).status_code == 404

    # The QS-17 variant setting picks the consent text the server expects.
    rules(consent_variant="service")
    assert client.get("/billing/plans").json()["rules"]["consent_version"] == notices.CONSENT_DRAFT["service"].version
    assert client.post("/billing/checkout", json=approved_body(), headers=other).status_code == 422
    assert client.post("/billing/checkout", json=approved_body("service"), headers=other).status_code == 200


def test_confirmation_mail_contents(client, paddle, rules):
    mail = need_mail(pytest.importorskip("app.mail"))
    h = signup(client)
    first, _ = buy(client, h, paddle)
    assert mails(mail, "order") == []  # wording not approved: the provider's receipt only

    rules(legal_wording_approved=True)
    h2 = signup(client, email="buyer@example.com")
    co, events = buy(client, h2, paddle, body=approved_body(interval="year"))
    for ev in events:  # replays do not send it twice
        paddle_post(client, ev)
    (msg,) = mails(mail, "order")
    assert msg.to == "buyer@example.com"
    row = payment(co["reference"])
    text = msg.text
    # The order, price and renewal terms.
    assert "Pro" in text and co["reference"] in text
    assert consumer.money(row.amount, "GBP") in text and "every year" in text
    assert notices.RENEWAL_TERMS.render(interval="year") in text
    # The seller, and who licenses the software.
    assert notices.SELLERS["paddle"] in text
    assert notices.LICENSOR.render(company="Truebex Ltd") in text
    # The exact consent and acknowledgement text, with versions and times.
    assert notices.CONSENT_DRAFT["digital_content"].text in text
    assert notices.CONSENT_DRAFT["digital_content"].version in text
    assert consumer.stamp(row.consent_at) in text
    assert row.key_info in text and notices.KEY_INFO.version in text and consumer.stamp(row.key_info_at) in text
    # How to cancel, and the terms and EULA in force.
    assert notices.HOW_TO_CANCEL.text.split("{")[0] in text and "/dashboard/billing/" in text
    s = get_settings()
    assert f"{s.site_url}/terms/" in text and consumer.eula_url() in text
    assert row.confirmation_sent_at is not None
    # The HTML part carries the same record.
    assert "<h2" in msg.html and notices.SELLERS["paddle"] in msg.html and co["reference"] in msg.html
    # Approval later does not mail old orders when a late event about them arrives.
    with SessionLocal() as db:
        old = db.scalar(select(Payment).where(Payment.reference == first["reference"]))
        old.paid_at = datetime.now(timezone.utc) - timedelta(days=3)
        db.commit()
        assert consumer.payment_paid(db, old) is False
    assert len(mails(mail, "order")) == 1


def test_exit_confirmation_mails(client, paddle, rules, monkeypatch):
    """The easy exit's confirmation (once, also when the provider needed a
    retry) and the cooling-off refund mail with the amount."""
    from app.billing import paddle_provider

    mail = need_mail(pytest.importorskip("app.mail"))
    h = signup(client)
    buy(client, h, paddle)
    sub = local_sub(provider="paddle")
    original = paddle_provider.PaddleProvider.cancel_subscription

    def down(self, db, sub, *, immediately):
        raise paddle_provider.ProviderError("Paddle unreachable")

    monkeypatch.setattr(paddle_provider.PaddleProvider, "cancel_subscription", down)
    assert client.post("/billing/cancel", json={"confirm": True}, headers=h).json()["status"] == "processing"
    (msg,) = mails(mail, "cancelled")
    assert msg.to == "dev@example.com"
    assert f"It stays active until {consumer.long_date(sub.current_period_end)} and won't renew" in msg.text
    monkeypatch.setattr(paddle_provider.PaddleProvider, "cancel_subscription", original)
    assert jobs.retry_exits(datetime.now(timezone.utc)) == 1
    assert len(mails(mail, "cancelled")) == 1  # confirmed once

    rules(subscription_notices_enabled=True, subscription_rules_from=LONG_AGO)
    h2 = signup(client, email="annual@example.com")
    buy(client, h2, paddle, interval="year")
    for ev in paddle.renew(local_sub(provider="paddle").provider_subscription_id):
        paddle_post(client, ev)
    out = client.post("/billing/cancel", json={"confirm": True, "refund": True}, headers=h2).json()
    (refund,) = mails(mail, "refunded")
    assert refund.to == "annual@example.com"
    assert notices.REFUND_AMOUNT.render(amount=consumer.money(out["refund_minor"], "GBP")) in refund.text
