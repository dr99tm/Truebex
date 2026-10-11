"""PF11's AI credit packs on master's billing (PF2b consumer rules, PF3a
organisation billing): a pack is a one-off item, so its paid payment credits
the pack once and never becomes a subscription, a renewal, an organisation's
seats or a subscription order confirmation, whichever provider took it.

Paddle is tests/mock_paddle.py served in-process; Stripe calls are
monkeypatched and its webhooks signed as test_billing does.
"""

import time
from urllib.parse import parse_qs, urlparse

import pytest
import stripe
from sqlalchemy import select

from app.ai.models import AiCreditLedger
from app.billing import consumer, service
from app.billing.paddle_provider import PaddleProvider
from app.config import get_settings
from app.database import SessionLocal
from app.models import Payment, Subscription

from .conftest import CONSENT
from .project_helpers import Person
from .test_billing import stripe_post
from .test_billing_pf2 import paddle_post
from .test_billing_pf2b import buy, mails, need_mail, payment


@pytest.fixture()
def approved(monkeypatch):
    """Every PF2b switch on: the order confirmation, the notices and the EU
    withdrawal function, as once the owner's solicitor approves the wording."""
    s = get_settings()
    for name in ("legal_wording_approved", "subscription_notices_enabled", "eu_withdrawal_enabled"):
        monkeypatch.setattr(s, name, True)


@pytest.fixture()
def spies(monkeypatch):
    """Record renewals and subscription fetches the billing code makes."""
    seen: dict[str, list] = {"renewals": [], "fetches": []}
    renewal = service.record_renewal
    fetch = PaddleProvider._fetch_subscription

    def record_renewal(*args, **kwargs):
        seen["renewals"].append(args)
        return renewal(*args, **kwargs)

    def fetch_subscription(self, db, sub_id, origin=None):
        seen["fetches"].append(sub_id)
        return fetch(self, db, sub_id, origin)

    monkeypatch.setattr(service, "record_renewal", record_renewal)
    monkeypatch.setattr(PaddleProvider, "_fetch_subscription", fetch_subscription)
    return seen


def _top_up(client, p: Person, currency: str = "GBP") -> dict:
    res = client.post(
        "/account/ai/top-ups", json={"pack": "credits-5000", "currency": currency, "consent": CONSENT}, headers=p.session
    )
    assert res.status_code == 201, res.text
    return res.json()


def _top_up_rows(user_id: int) -> list[tuple]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(AiCreditLedger).where(AiCreditLedger.account_id == user_id, AiCreditLedger.bucket == "top_up")
        ).all()
        return [(r.kind, r.delta, r.ref) for r in rows]


def _subscriptions(user_id: int) -> list[Subscription]:
    with SessionLocal() as db:
        return list(db.scalars(select(Subscription).where(Subscription.user_id == user_id)))


def _assert_one_off(user_id: int, reference: str, subs_before: list[tuple]) -> None:
    """Credited once; no subscription, renewal or organisation from it."""
    assert _top_up_rows(user_id) == [("top_up", 5000, reference)]
    pay = payment(reference)
    assert (pay.plan, pay.status) == ("ai_credits", "paid")
    assert pay.provider_subscription_id is None and pay.organisation_id is None
    after = [(s.provider, s.plan, s.organisation_id, s.renewed_at) for s in _subscriptions(user_id)]
    assert after == subs_before


def test_ai_pack_paddle_on_consumer_rules(client, paddle, approved, spies):
    mail = need_mail(pytest.importorskip("app.mail"))
    p = Person(client, "buyer@example.com")  # a Pro trial (holds ai.metered)
    before = [(s.provider, s.plan, s.organisation_id, s.renewed_at) for s in _subscriptions(p.user_id)]
    out = _top_up(client, p)
    txn = parse_qs(urlparse(out["url"]).query)["_ptxn"][0]
    events = paddle.pay(txn, country="DE")
    assert [e["event_type"] for e in events] == ["transaction.completed"]
    assert events[0]["data"]["origin"] != "subscription_recurring"
    for ev in events:
        assert paddle_post(client, ev).status_code == 200
    # A replay, and the return page's refresh, change nothing.
    assert paddle_post(client, dict(events[0], event_id="evt_replayed")).status_code == 200
    assert client.post(f"/billing/payments/{out['reference']}/refresh", headers=p.session).json()["status"] == "paid"
    _assert_one_off(p.user_id, out["reference"], before)
    assert payment(out["reference"]).country == "DE"  # PF2b still records where it was bought
    assert spies["renewals"] == [] and spies["fetches"] == []
    assert client.get("/account/ai", headers=p.session).json()["balance"]["top_up_remaining"] == 5000
    # With the wording approved, no subscription order confirmation for a pack.
    assert mails(mail, "order") == []
    assert not any("billed every" in m.text for m in mail.OUTBOX)
    with SessionLocal() as db:
        row = db.scalar(select(Payment).where(Payment.reference == out["reference"]))
        assert consumer.payment_paid(db, row) is False and row.confirmation_sent_at is None


def test_ai_pack_stripe_on_consumer_rules(client, monkeypatch, approved, spies):
    mail = need_mail(pytest.importorskip("app.mail"))
    monkeypatch.setattr(get_settings(), "billing_provider", "stripe")
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **k: {"id": "cs_pack_1", "url": "https://checkout.stripe.test/pack"})
    p = Person(client, "buyer@example.com")
    before = [(s.provider, s.plan, s.organisation_id, s.renewed_at) for s in _subscriptions(p.user_id)]
    out = _top_up(client, p, "USD")
    session = {
        "id": "cs_pack_1", "object": "checkout.session", "mode": "payment", "client_reference_id": out["reference"],
        "status": "complete", "payment_status": "paid", "amount_total": 900, "total_details": {"amount_tax": 150},
        "subscription": None, "invoice": "in_pack_1",
        "customer_details": {"address": {"country": "FR"}, "tax_ids": []},
        "metadata": {"user_id": str(p.user_id), "reference": out["reference"], "item": "ai_credits"},
    }
    now = int(time.time())
    ev = {"id": "evt_pack_1", "type": "checkout.session.completed", "created": now, "data": {"object": session}}
    assert stripe_post(client, ev).status_code == 200
    assert stripe_post(client, dict(ev, id="evt_pack_replayed")).status_code == 200
    # Stripe's invoice for a payment-mode session is not a renewal.
    invoice = {"id": "in_pack_1", "object": "invoice", "billing_reason": "manual", "subscription": None,
               "status": "paid", "status_transitions": {"paid_at": now}}
    assert stripe_post(client, {"id": "evt_inv_pack", "type": "invoice.paid", "created": now,
                                "data": {"object": invoice}}).status_code == 200
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda *a, **k: session)
    assert client.post(f"/billing/payments/{out['reference']}/refresh", headers=p.session).json()["status"] == "paid"
    _assert_one_off(p.user_id, out["reference"], before)
    row = payment(out["reference"])
    assert (row.amount, row.tax_minor, row.country, row.invoice_id) == (900, 150, "FR", "in_pack_1")
    assert spies["renewals"] == []
    assert mails(mail, "order") == [] and not any("billed every" in m.text for m in mail.OUTBOX)


def test_subscription_checkout_payment_is_never_a_pack(client, paddle, monkeypatch):
    """PF2b finds a subscription's own checkout by its provider subscription
    id, else (payments from before PF2b) the latest paid one: a credit pack
    bought later is never taken for it, so a withdrawal never refunds a pack."""
    from .conftest import signup

    monkeypatch.setattr(get_settings(), "eu_withdrawal_enabled", True)
    h = signup(client, "eu@example.com")
    co, _ = buy(client, h, paddle, country="DE")
    with SessionLocal() as db:
        # As a checkout paid before PF2b recorded the subscription id.
        db.get(Payment, payment(co["reference"]).id).provider_subscription_id = None
        db.commit()
    uid = payment(co["reference"]).user_id
    res = client.post("/account/ai/top-ups", json={"pack": "credits-5000", "currency": "GBP", "consent": CONSENT}, headers=h)
    assert res.status_code == 201, res.text
    pack = res.json()
    for ev in paddle.pay(parse_qs(urlparse(pack["url"]).query)["_ptxn"][0], country="DE"):
        assert paddle_post(client, ev).status_code == 200
    assert _top_up_rows(uid) == [("top_up", 5000, pack["reference"])]
    with SessionLocal() as db:
        sub = db.scalar(select(Subscription).where(Subscription.user_id == uid, Subscription.provider == "paddle"))
        found = consumer.checkout_payment(db, sub)
        assert found is not None and found.reference == co["reference"]
    view = client.get("/billing/subscription", headers=h).json()
    assert view["withdrawal_until"] is not None
    res = client.post("/billing/withdraw", json={"confirm": True}, headers=h)
    assert res.status_code == 200, res.text
    pack_txn = payment(pack["reference"]).provider_ref
    adjustment = paddle.STATE["adjustments"][-1]
    assert adjustment["transaction_id"] == payment(co["reference"]).provider_ref != pack_txn


def test_mock_pay_page_returns_a_pack_to_cloud(client, paddle, monkeypatch):
    """The click-through (the mock's own pay page, as the human test uses it)
    returns a pack to the Cloud page as /checkout/ does, and a plan to billing."""
    from fastapi.testclient import TestClient

    monkeypatch.setitem(paddle.CHECKOUT, "style", "page")
    p = Person(client, "buyer@example.com")
    out = _top_up(client, p)
    url = urlparse(out["url"])
    assert url.path.startswith("/pay/txn_") and parse_qs(url.query)["back"] == ["dashboard-cloud"]
    mock = TestClient(paddle.app)
    page = mock.get(f"{url.path}?{url.query}").text
    assert f"action='{url.path}?back=dashboard-cloud'" in page
    assert f"/dashboard/cloud/?topup=canceled&amp;ref={out['reference']}" in page
    res = mock.post(f"{url.path}?back=dashboard-cloud", data={"country": "GB"}, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"].endswith(f"/dashboard/cloud/?topup=success&ref={out['reference']}")
    assert paddle.STATE["transactions"][url.path.rsplit("/", 1)[1]]["status"] == "completed"
    for ev in paddle.STATE["sent"]:
        assert paddle_post(client, ev).status_code == 200
    assert _top_up_rows(p.user_id) == [("top_up", 5000, out["reference"])]
    # Any other value of `back` is billing's return, as before.
    plain = mock.get(f"{url.path}?back=elsewhere").text
    assert "/dashboard/billing/?checkout=canceled" in plain and "action='" + url.path + "'" in plain
