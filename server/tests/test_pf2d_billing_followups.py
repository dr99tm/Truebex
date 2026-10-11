"""PF2d billing follow-ups: a paid Paddle checkout always gets its
subscription, and a supplier's listing checkout returns to the portal.

Paddle is tests/mock_paddle.py served in-process (the `paddle` fixture, which
sends no webhooks: each test delivers the events it wants, signed as Paddle
signs them). Stripe calls are monkeypatched as in test_billing_orgs.
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import stripe
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.billing import jobs, service
from app.config import get_settings
from app.database import SessionLocal
from app.models import Payment, ProviderPrice, Subscription

from .conftest import CONSENT, STRIPE_SUBS, signup
from .test_billing_pf2 import paddle_post, start_checkout, txn_of

OUT = Path(__file__).resolve().parents[2] / "out"


# --- helpers --------------------------------------------------------------------------


def _event(events: list[dict], kind: str) -> dict:
    return next(e for e in events if e["event_type"] == kind)


def _me(client, h) -> dict:
    return client.get("/auth/me", headers=h).json()


def _subs(user_id: int, provider: str = "paddle") -> list[Subscription]:
    with SessionLocal() as db:
        return list(
            db.scalars(select(Subscription).where(Subscription.user_id == user_id, Subscription.provider == provider))
        )


def _payment(reference: str) -> Payment:
    with SessionLocal() as db:
        return db.scalar(select(Payment).where(Payment.reference == reference))


def _fetches(paddle, sub_id: str | None = None) -> list[str]:
    """The API's GET /subscriptions/{id} calls the mock has answered."""
    return [
        r["path"]
        for r in paddle.STATE["requests"]
        if r["method"] == "GET"
        and r["path"].startswith("/subscriptions/")
        and (sub_id is None or r["path"] == f"/subscriptions/{sub_id}")
    ]


def _pro_paid_on_mock(client, paddle, email: str):
    """A personal Pro checkout paid on the mock, no webhook delivered yet."""
    h = signup(client, email)
    co = start_checkout(client, h)
    events = paddle.pay(txn_of(co["url"]))
    return h, co, events


# --- 1. Paddle: transaction.completed alone ------------------------------------------------


def test_paddle_personal_plan_live_from_transaction_completed_alone(client, paddle):
    """subscription.created never arrives and the buyer never opens the
    return page: the paid transaction fetches its subscription from Paddle."""
    h, co, events = _pro_paid_on_mock(client, paddle, "solo@example.com")
    sub_id = _event(events, "subscription.created")["data"]["id"]
    uid = _me(client, h)["id"]
    assert _me(client, h)["plan"] == "free"

    assert paddle_post(client, _event(events, "transaction.completed")).status_code == 200
    assert _me(client, h)["plan"] == "pro"
    (sub,) = _subs(uid)
    assert (sub.provider_subscription_id, sub.plan, sub.status, sub.organisation_id) == (sub_id, "pro", "active", None)
    assert sub.provider_customer_id and sub.current_period_end is not None
    pay = _payment(co["reference"])
    assert (pay.status, pay.provider_subscription_id) == ("paid", sub_id)
    assert _fetches(paddle, sub_id) == [f"/subscriptions/{sub_id}"]
    # The Billing page, opened fresh: the plan and its one invoice.
    view = client.get("/billing/subscription", headers=h).json()
    assert (view["tier"], view["status"]) == ("pro", "active")
    assert len(client.get("/billing/invoices", headers=h).json()) == 1
    # Without the return page the refresh has nothing to do: no second fetch.
    client.post(f"/billing/payments/{co['reference']}/refresh", headers=h)
    assert len(_fetches(paddle, sub_id)) == 1


# --- 2. Paddle: the reconcile alone ------------------------------------------------------------


def test_paddle_reconcile_alone_makes_plan_live(client, paddle):
    """No webhook at all: the daily reconcile verifies the pending checkout,
    then its subscription."""
    h, co, events = _pro_paid_on_mock(client, paddle, "offline@example.com")
    uid = _me(client, h)["id"]
    assert _payment(co["reference"]).status == "pending"
    assert jobs.reconcile(datetime.now(timezone.utc)) >= 1
    assert _me(client, h)["plan"] == "pro"
    assert [s.provider_subscription_id for s in _subs(uid)] == [_event(events, "subscription.created")["data"]["id"]]
    assert _payment(co["reference"]).status == "paid"


def test_paddle_fetch_error_logged_then_refresh_or_reconcile_attach(client, paddle, caplog):
    """The fetch on transaction.completed fails: it is logged, the payment is
    still paid, and the return-page refresh or the reconcile (a payment paid
    in its window whose subscription is not stored) attaches it."""
    caplog.set_level(logging.ERROR, logger="truebex.billing.paddle")
    for email, recover in (("refresh@example.com", "refresh"), ("daily@example.com", "reconcile")):
        h, co, events = _pro_paid_on_mock(client, paddle, email)
        uid = _me(client, h)["id"]
        sub_id = _event(events, "subscription.created")["data"]["id"]
        hidden = paddle.STATE["subscriptions"].pop(sub_id)  # Paddle answers 404 for a moment
        assert paddle_post(client, _event(events, "transaction.completed")).status_code == 200
        assert any(sub_id in r.getMessage() and co["reference"] in r.getMessage() for r in caplog.records)
        pay = _payment(co["reference"])
        assert (pay.status, pay.provider_subscription_id) == ("paid", sub_id)
        assert _subs(uid) == [] and _me(client, h)["plan"] == "free"
        with SessionLocal() as db:
            assert service.awaits_subscription(db, pay)

        paddle.STATE["subscriptions"][sub_id] = hidden
        if recover == "refresh":
            res = client.post(f"/billing/payments/{co['reference']}/refresh", headers=h)
            assert res.status_code == 200 and res.json()["status"] == "paid"
        else:
            assert jobs.reconcile(datetime.now(timezone.utc)) >= 1
        assert _me(client, h)["plan"] == "pro"
        assert [s.provider_subscription_id for s in _subs(uid)] == [sub_id]
        with SessionLocal() as db:
            assert not service.awaits_subscription(db, _payment(co["reference"]))

    # Outside the reconcile's window a paid checkout is left alone.
    h, co, events = _pro_paid_on_mock(client, paddle, "old@example.com")
    sub_id = _event(events, "subscription.created")["data"]["id"]
    hidden = paddle.STATE["subscriptions"].pop(sub_id)
    paddle_post(client, _event(events, "transaction.completed"))
    paddle.STATE["subscriptions"][sub_id] = hidden
    before = len(_fetches(paddle, sub_id))
    jobs.reconcile(datetime.now(timezone.utc) + jobs.RECONCILE_WINDOW + timedelta(hours=1))
    assert len(_fetches(paddle, sub_id)) == before and _me(client, h)["plan"] == "free"


# --- 3. Paddle: either event order, one row ------------------------------------------------------


@pytest.mark.parametrize("order", ["transaction_first", "subscription_first"])
def test_paddle_either_event_order_one_subscription_row(client, paddle, order):
    h, co, events = _pro_paid_on_mock(client, paddle, f"{order}@example.com")
    uid = _me(client, h)["id"]
    created, completed = _event(events, "subscription.created"), _event(events, "transaction.completed")
    sub_id = created["data"]["id"]
    first, second = (completed, created) if order == "transaction_first" else (created, completed)
    for ev in (first, second, first, second):  # and each delivered twice
        assert paddle_post(client, ev).status_code == 200
    # A late transaction.paid (Paddle sends it too) and the return page change nothing.
    paid = paddle.event("transaction.paid", completed["data"])
    assert paddle_post(client, paid).status_code == 200
    client.post(f"/billing/payments/{co['reference']}/refresh", headers=h)
    assert reconcile_ok()
    assert _me(client, h)["plan"] == "pro"
    with SessionLocal() as db:
        rows = db.scalar(
            select(func.count()).select_from(Subscription).where(Subscription.provider_subscription_id == sub_id)
        )
    assert rows == 1 and len(_subs(uid)) == 1
    # Fetched on transaction.completed only while the row was missing.
    fetched_by_events = 1 if order == "transaction_first" else 0
    assert len(_fetches(paddle, sub_id)) == fetched_by_events + 1  # + the reconcile's re-fetch


def reconcile_ok() -> bool:
    jobs.reconcile(datetime.now(timezone.utc))
    return True


# --- 4. Paddle: a credit pack has no subscription ------------------------------------------------


def test_paddle_credit_pack_fetches_no_subscription(client, paddle):
    h = signup(client, "packs@example.com")
    co = start_checkout(client, h)
    for ev in paddle.pay(txn_of(co["url"])):  # Pro first: packs need a plan with AI
        assert paddle_post(client, ev).status_code == 200
    before = len(_fetches(paddle))
    res = client.post("/account/ai/top-ups", json={"pack": "credits-5000", "currency": "GBP", "consent": CONSENT}, headers=h)
    assert res.status_code == 201, res.text
    pack = res.json()
    events = paddle.pay(parse_qs(urlparse(pack["url"]).query)["_ptxn"][0])
    assert [e["event_type"] for e in events] == ["transaction.completed"]
    assert paddle_post(client, events[0]).status_code == 200
    row = _payment(pack["reference"])
    assert (row.plan, row.status, row.provider_subscription_id) == ("ai_credits", "paid", None)
    with SessionLocal() as db:
        assert not service.awaits_subscription(db, row)
    # Neither the event, the refresh nor the reconcile fetches a subscription for it.
    client.post(f"/billing/payments/{pack['reference']}/refresh", headers=h)
    jobs.reconcile(datetime.now(timezone.utc))
    pro_sub = _subs(_me(client, h)["id"])[0].provider_subscription_id
    assert [p for p in _fetches(paddle)[before:] if p != f"/subscriptions/{pro_sub}"] == []
    tops = client.get("/account/ai", headers=h).json()["top_ups"]
    assert [t["state"] for t in tops if t["reference"] == pack["reference"]] == ["credited"]


def test_paddle_attach_skips_one_off_items(client, paddle):
    """Even a pack's transaction naming a subscription id (it never does)
    fetches nothing: a one-off item starts no subscription."""
    from app.billing import providers

    adapter = providers.get_provider("paddle")
    with SessionLocal() as db:
        pay = Payment(user_id=1, provider="paddle", plan="ai_credits", reference="tbx_pack_x", amount=600,
                      currency="GBP", status="paid", provider_ref="txn_x")  # fmt: skip
        adapter._attach_from_transaction(db, pay, "sub_never")
    assert _fetches(paddle, "sub_never") == []


# --- 5. Stripe: the listing checkout returns to the portal ------------------------------------------


def _listing_fee(monkeypatch, fee: int = 4900):
    """A listing plan with a fee (GD7 sets them; listing_plans.json has none yet)."""
    from app.market import listing as m_listing

    plans = dict(m_listing.plans())
    paid = m_listing.ListingPlan("standard", "Standard", 800, {"GBP": fee})
    every = {**plans, "standard": paid}
    monkeypatch.setattr(m_listing, "plans", lambda: every)
    monkeypatch.setattr(m_listing, "plan_of", lambda s: every.get(s.listing_plan or "founding"))
    with SessionLocal() as db:  # sync_prices' row for that fee
        db.add(ProviderPrice(provider="stripe", tier="listing_standard", interval="month", currency="GBP",
                             amount_minor=fee, provider_price_id="price_listing_standard_gbp"))  # fmt: skip
        db.commit()


def test_stripe_listing_checkout_returns_to_supplier_billing(client, stripe_prices, monkeypatch):
    from .supplier_helpers import verified

    monkeypatch.setattr(get_settings(), "billing_provider", "stripe")
    site = get_settings().site_url
    sessions: list[dict] = []

    def create(**params):
        sessions.append(params)
        n = len(sessions)
        return {"id": f"cs_t42_{n}", "url": f"https://checkout.stripe.test/cs_t42_{n}"}

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    _listing_fee(monkeypatch)
    owner, sid = verified(client)

    # The listing plan's checkout: back on the portal's billing page.
    res = client.post("/supplier/listing", json={"plan": "standard"}, headers=owner)
    assert res.status_code == 200, res.text
    assert res.json()["state"] == "checkout"
    listing_co = sessions[-1]
    ref = listing_co["client_reference_id"]
    assert ref.startswith("lst_") and listing_co["metadata"]["plan"] == "listing_standard"
    assert listing_co["success_url"] == f"{site}/supplier/billing/?checkout=success&ref={ref}"
    assert listing_co["cancel_url"] == f"{site}/supplier/billing/?checkout=canceled&ref={ref}"

    # A personal checkout still returns to the dashboard's Billing page.
    h = signup(client, "person@example.com")
    co = client.post("/billing/checkout", json={"tier": "pro", "interval": "month", "currency": "GBP", "seats": 1,
                                                "consent": CONSENT}, headers=h).json()  # fmt: skip
    personal = sessions[-1]
    assert personal["success_url"] == f"{site}/dashboard/billing/?checkout=success&ref={co['reference']}"
    assert personal["cancel_url"] == f"{site}/dashboard/billing/?checkout=canceled&ref={co['reference']}"

    # Back on the portal: the page's refresh verifies the session with Stripe.
    owner_id = _me(client, owner)["id"]
    with SessionLocal() as db:  # a running app trial, which a listing plan leaves alone
        db.add(Subscription(user_id=owner_id, plan="pro", provider="trial", status="active",
                            current_period_end=datetime.now(timezone.utc) + timedelta(days=14)))  # fmt: skip
        db.commit()
    STRIPE_SUBS["sub_listing_1"] = {
        "id": "sub_listing_1", "object": "subscription", "customer": "cus_nord", "currency": "gbp",
        "status": "active", "cancel_at_period_end": False, "metadata": listing_co["metadata"],
        "items": {"data": [{"id": "si_l1", "quantity": 1, "current_period_end": int(time.time()) + 30 * 86400,
                            "price": {"id": "price_listing_standard_gbp", "recurring": {"interval": "month"}}}]},
    }  # fmt: skip
    session = {
        "id": "cs_t42_1", "object": "checkout.session", "client_reference_id": ref, "status": "complete",
        "payment_status": "paid", "amount_total": 5880, "total_details": {"amount_tax": 980},
        "subscription": "sub_listing_1", "invoice": "in_listing_1", "metadata": listing_co["metadata"],
        "customer_details": {"address": {"country": "GB"}, "tax_ids": [{"type": "gb_vat", "value": "GB123456789"}]},
    }  # fmt: skip
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda *a, **k: session)
    paid = client.post(f"/billing/payments/{ref}/refresh", headers=owner)
    assert paid.status_code == 200 and paid.json()["status"] == "paid" and paid.json()["plan"] == "listing_standard"
    (sub,) = _subs(owner_id, "stripe")
    assert (sub.plan, sub.status, sub.provider_customer_id) == ("listing_standard", "active", "cus_nord")
    # The plan's state on the portal at once: the listing row follows the subscription.
    view = client.get("/supplier/listing", headers=owner).json()
    assert view["plan"] == "standard" and view["subscription"]["status"] == "active"
    assert view["commission_bp"] == 800
    # Never the owner's app plan, and their trial runs on.
    assert _me(client, owner)["plan"] == "pro"
    with SessionLocal() as db:
        trial = db.scalar(select(Subscription).where(Subscription.user_id == owner_id, Subscription.provider == "trial"))
        assert trial.status == "active"
        from app.models import User

        assert service.live_subscription(db, db.get(User, owner_id)).provider == "trial"


def test_stripe_org_checkout_return_unchanged(client, stripe_prices, monkeypatch):
    """An organisation's checkout keeps PF3a's return (its billing page, `&org=`)."""
    from .org_helpers import make_org

    monkeypatch.setattr(get_settings(), "billing_provider", "stripe")
    captured: dict = {}
    monkeypatch.setattr(
        stripe.checkout.Session, "create",
        lambda **p: captured.update(p) or {"id": "cs_org_t42", "url": "https://checkout.stripe.test/cs_org_t42"},
    )  # fmt: skip
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    res = client.post(
        "/billing/checkout",
        json={"tier": "team", "interval": "year", "currency": "GBP", "seats": 3, "consent": CONSENT, "org_id": org["id"]},
        headers=h,
    )
    assert res.status_code == 200, res.text
    ref, site = res.json()["reference"], get_settings().site_url
    assert captured["success_url"] == f"{site}/dashboard/billing/?checkout=success&ref={ref}&org={org['id']}"
    assert captured["cancel_url"] == f"{site}/dashboard/billing/?checkout=canceled&ref={ref}&org={org['id']}"


# --- the mock's switches for the human test ---------------------------------------------------------


def test_mock_paddle_drop_and_no_return_switches(paddle, monkeypatch):
    """MOCK_PADDLE_DROP leaves out the named events (they are still made);
    MOCK_PADDLE_NO_RETURN keeps the buyer on the pay page after paying."""
    import httpx

    assert paddle.drop_list(" subscription.created, transaction.completed ,") == {
        "subscription.created", "transaction.completed"}  # fmt: skip
    assert paddle.drop_list("") == set()
    posted: list[str] = []
    monkeypatch.setattr(httpx, "post", lambda url, content, **kw: posted.append(__import__("json").loads(content)["event_type"]))
    monkeypatch.setitem(paddle.WEBHOOK, "send", True)
    monkeypatch.setattr(paddle, "DROP", {"subscription.created"})
    monkeypatch.setitem(paddle.CHECKOUT, "style", "page")
    paddle.STATE["customers"]["ctm_1"] = {"id": "ctm_1", "email": "a@example.com", "name": None, "status": "active"}
    price = next(iter(paddle.STATE["prices"].values()))
    mock = TestClient(paddle.app, headers={"Authorization": "Bearer pdl_sdbx_local"})
    txn = mock.post("/transactions", json={
        "items": [{"price_id": price["id"], "quantity": 1}], "customer_id": "ctm_1", "currency_code": "GBP",
        "custom_data": {"reference": "tbx_drop"}, "checkout": {"url": "http://127.0.0.1:3142/checkout/"},
    }).json()["data"]  # fmt: skip

    monkeypatch.setitem(paddle.RETURN, "to_site", False)
    page = mock.post(f"/pay/{txn['id']}", content="country=GB", follow_redirects=False)
    assert page.status_code == 200 and "close this tab" in page.text
    assert posted == ["transaction.completed"]
    assert [e["event_type"] for e in paddle.STATE["dropped"]] == ["subscription.created"]
    assert [e["event_type"] for e in paddle.STATE["sent"]] == ["transaction.completed", "subscription.created"]
    # Without the switch the pay page sends the buyer back to Billing.
    monkeypatch.setitem(paddle.RETURN, "to_site", True)
    again = mock.post(f"/pay/{txn['id']}", content="country=GB", follow_redirects=False)
    assert again.status_code == 303 and "/dashboard/billing/?checkout=success&ref=tbx_drop" in again.headers["location"]


# --- 6. build check: the supplier billing page reads the return ---------------------------------------


@pytest.mark.skipif(not (OUT / "index.html").exists(), reason="needs the static build in out/ (npm run build)")
def test_site_pf2d_supplier_billing_return_copy():
    from .test_site_pf2 import _loads

    page = OUT / "supplier" / "billing" / "index.html"
    for needle in (
        "{plan} is your listing plan",
        "Confirming your payment",
        "Your listing plan is unchanged",
        "/refresh",
    ):
        assert _loads(page, needle), needle
    source = (OUT.parent / "src" / "app" / "supplier" / "billing" / "page.tsx").read_text(encoding="utf-8")
    assert "SUPPLIER_CHECKOUT" in source and "refreshPayment" in source
    assert re.search(r"params\.get\(\"checkout\"\)", source) and re.search(r"params\.get\(\"ref\"\)", source)
