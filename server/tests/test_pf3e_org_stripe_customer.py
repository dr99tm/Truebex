"""PF3e: an organisation's Stripe checkout and subscription run on the
organisation's own Stripe customer, never on its buyer's personal one.

Stripe Checkout saves the business name, the address and a tax id entered at
checkout onto the customer the session ran on, and reports a customer's saved
tax ids on every later session of that customer. PF2b marks a payment whose
session reports one `business`, which takes the EU withdrawal away. `_Stripe`
below stands in for exactly that (PF8b's stand-in, with seats, plan changes,
the customer portal and invoice lists), so an organisation checkout that
reused the buyer's customer would make the buyer's own Pro a business payment
and open the organisation's portal on the buyer's own Stripe account.

Before PF3e an organisation's checkout opened on `service.customer_id` of its
buyer, and that answer counted organisation subscriptions: PF8b's scratch
check (its As-built, item 4) printed the buyer's own Pro "business: True".
"""

import json
import time
from datetime import datetime, timedelta, timezone

import pytest
import stripe
from sqlalchemy import select

from app.billing import org_billing, service
from app.config import get_settings
from app.database import SessionLocal
from app.models import Payment, Subscription, User

from .conftest import CONSENT, STRIPE_SUBS, checkout_body, signup
from .org_helpers import _clean_mail_and_caches, join, make_org, me  # noqa: F401  (autouse fixture)
from .test_billing import stripe_post
from .test_pf8a_listing_consumer_rules import rules  # noqa: F401  (the PF2b switches fixture)

BUYER = "buyer@example.com"
BILLING = "billing@example.com"
VAT_ID = "DE123456789"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _Stripe:
    """Stripe's side of what this server asks of it. A Checkout Session runs
    on the customer it names, else on a new one (`cus_new_N`). A tax id
    entered at checkout is saved onto that customer (Checkout asks a customer
    that has one for none), and every session reports its customer's saved
    tax ids. Subscriptions live in conftest's STRIPE_SUBS (what
    `stripe.Subscription.retrieve` answers); a change of price or seats
    modifies them there. Portal sessions and invoice lists record the
    customer they were opened for, and a customer's invoices are one per
    subscription on it (`in_<subscription id>`)."""

    def __init__(self, monkeypatch):
        self.created: list[dict] = []
        self.sessions: dict[str, dict] = {}
        self.tax_ids: dict[str, list[dict]] = {}
        self.new_customers = 0
        self.portals: list[dict] = []
        self.invoice_lists: list[str] = []
        self.modified: list[tuple[str, str, int]] = []
        monkeypatch.setattr(stripe.checkout.Session, "create", self._create)
        monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda sid, **_kw: self.sessions[sid])
        monkeypatch.setattr(stripe.Subscription, "modify", self._modify)
        monkeypatch.setattr(stripe.billing_portal.Session, "create", self._portal)
        monkeypatch.setattr(stripe.Invoice, "list", self._invoices)
        monkeypatch.setattr(stripe.Invoice, "retrieve", self._invoice)

    def _create(self, **params):
        session_id = f"cs_pf3e_{len(self.created) + 1}"
        self.created.append({**params, "id": session_id})
        return {"id": session_id, "url": f"https://checkout.stripe.test/{session_id}"}

    @property
    def last(self) -> dict:
        return self.created[-1]

    def pay(self, sub_id: str, *, country: str, vat_id: str | None = None) -> tuple[str, str]:
        """Complete the last session, paid from `country` (entering `vat_id`
        if Checkout asks for one), and start its subscription. Returns our
        reference and the customer it ran on."""
        params = self.last
        customer = params.get("customer")
        if customer is None:
            self.new_customers += 1
            customer = f"cus_new_{self.new_customers}"
        if vat_id and not self.tax_ids.get(customer):
            self.tax_ids[customer] = [{"type": "eu_vat", "value": vat_id}]
        line = params["line_items"][0]
        meta = params["metadata"]
        STRIPE_SUBS[sub_id] = {
            "id": sub_id, "object": "subscription", "customer": customer, "currency": "gbp", "status": "active",
            "cancel_at_period_end": False, "metadata": meta,
            "items": {"data": [{"id": f"si_{sub_id}", "quantity": line["quantity"], "price": {"id": line["price"]},
                                "current_period_end": int(_now().timestamp()) + 30 * 86400}]},
        }  # fmt: skip
        self.sessions[params["id"]] = {
            "id": params["id"], "object": "checkout.session", "client_reference_id": params["client_reference_id"],
            "status": "complete", "payment_status": "paid", "subscription": sub_id, "invoice": f"in_{sub_id}",
            "customer": customer, "metadata": meta,
            "customer_details": {"address": {"country": country}, "tax_ids": list(self.tax_ids.get(customer, []))},
        }  # fmt: skip
        return params["client_reference_id"], customer

    def _modify(self, sub_id, items, **_kw):
        sub = STRIPE_SUBS[sub_id]
        item = sub["items"]["data"][0]
        item["price"] = {"id": items[0]["price"]}
        item["quantity"] = items[0]["quantity"]
        self.modified.append((sub_id, items[0]["price"], items[0]["quantity"]))
        return sub

    def _portal(self, customer, return_url, **_kw):
        self.portals.append({"customer": customer, "return_url": return_url})
        return {"url": f"https://billing.stripe.test/p/{customer}"}

    def _invoice_of(self, sub: dict) -> dict:
        return {
            "id": f"in_{sub['id']}", "number": f"IN-{sub['id'].upper()}", "customer": sub["customer"],
            "subscription": sub["id"], "created": int(_now().timestamp()), "total": 2400, "tax": 400,
            "currency": "gbp", "status": "paid", "invoice_pdf": f"https://pay.stripe.test/in_{sub['id']}.pdf",
        }  # fmt: skip

    def _invoices(self, customer, **_kw):
        self.invoice_lists.append(customer)
        return {"data": [self._invoice_of(s) for s in STRIPE_SUBS.values() if s["customer"] == customer]}

    def _invoice(self, invoice_id, **_kw):
        return next(self._invoice_of(s) for s in STRIPE_SUBS.values() if f"in_{s['id']}" == invoice_id)


@pytest.fixture()
def on_stripe(client, stripe_prices, monkeypatch) -> _Stripe:
    """Stripe as the checkout provider, its synced prices, and Stripe's side."""
    monkeypatch.setattr(get_settings(), "billing_provider", "stripe")
    return _Stripe(monkeypatch)


# --- helpers ------------------------------------------------------------------------------------


def _people(client) -> tuple[dict, dict, dict, int]:
    """The buyer (the organisation's owner), a billing member who is not the
    buyer, the organisation, and the buyer's user id."""
    buyer = signup(client, BUYER)
    org = make_org(client, buyer)
    billing = join(client, buyer, org["id"], BILLING, role="billing")
    return buyer, billing, org, me(client, buyer)["id"]


def _sub(db, uid: int, plan: str, sub_id: str, customer: str, *, org_id: str | None = None, provider="stripe",
         status="active", ends_in=timedelta(days=30), updated_ago=timedelta(0)) -> Subscription:  # fmt: skip
    """A subscription row as an earlier checkout left it (for an organisation
    with `org_id`: a row from before PF3e when `customer` is a person's own),
    and Stripe's record of it."""
    row = Subscription(
        user_id=uid, plan=plan, provider=provider, status=status, interval="year" if plan == "team" else "month",
        currency="GBP", seats=3 if plan == "team" else 1, provider_subscription_id=sub_id,
        provider_customer_id=customer, current_period_end=_now() + ends_in, updated_at=_now() - updated_ago,
        organisation_id=org_id,
    )  # fmt: skip
    db.add(row)
    db.flush()
    if provider == "stripe":
        STRIPE_SUBS[sub_id] = {"id": sub_id, "object": "subscription", "customer": customer, "status": status}
    return row


def _org_checkout(client, h, org_id: str, seats: int = 3) -> dict:
    res = client.post("/billing/checkout", json=checkout_body(tier="team", interval="year", seats=seats, org_id=org_id), headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def _refresh(client, h, reference: str) -> dict:
    res = client.post(f"/billing/payments/{reference}/refresh", headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def _org_bought(client, on_stripe, h, org_id: str, sub_id: str, *, vat_id: str | None = VAT_ID) -> str:
    """Team x3 bought for the organisation, paid from Germany with its VAT
    id; returns the customer the checkout ran on."""
    _org_checkout(client, h, org_id)
    reference, customer = on_stripe.pay(sub_id, country="DE", vat_id=vat_id)
    paid = _refresh(client, h, reference)
    assert (paid["status"], paid["plan"], paid["organisation_id"]) == ("paid", "team", org_id), paid
    return customer


def _cancel(client, sub_id: str) -> None:
    """Stripe ends the subscription (customer.subscription.deleted, signed)."""
    ended = {**STRIPE_SUBS[sub_id], "status": "canceled"}
    event = {"id": f"evt_pf3e_end_{sub_id}", "object": "event", "type": "customer.subscription.deleted",
             "created": int(time.time()), "data": {"object": ended}}  # fmt: skip
    assert stripe_post(client, event).status_code == 200


def _org_subs(org_id: str) -> list[Subscription]:
    with SessionLocal() as db:
        return list(db.scalars(select(Subscription).where(Subscription.organisation_id == org_id).order_by(Subscription.id)))


def _named(params: dict) -> str:
    """Every value a checkout sent Stripe, to search for a customer id."""
    return json.dumps(params, default=str)


# --- 1. The organisation's checkout opens on the organisation's customer ---------------------------


def test_org_checkout_never_opens_on_the_buyers_own_customer(client, on_stripe):
    """The buyer pays their own Pro on `cus_pro`. Their Team checkout for the
    organisation names no customer: Stripe makes the organisation one from the
    buyer's e-mail, and the organisation's VAT id is saved there, not on
    `cus_pro`, which appears nowhere in the checkout."""
    buyer, _, org, uid = _people(client)
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_pro")
        db.commit()

    _org_checkout(client, buyer, org["id"])
    params = on_stripe.last
    assert params["metadata"]["org_id"] == org["id"]
    assert "customer" not in params and "customer_update" not in params
    assert params["customer_email"] == BUYER
    assert "cus_pro" not in _named(params)
    assert params["tax_id_collection"] == {"enabled": True}  # the organisation's VAT id, on its own customer

    reference, customer = on_stripe.pay("sub_org", country="DE", vat_id=VAT_ID)
    paid = _refresh(client, buyer, reference)
    assert (paid["status"], paid["business"]) == ("paid", True)
    (sub,) = _org_subs(org["id"])
    assert sub.provider_customer_id == customer != "cus_pro" and sub.user_id == uid
    assert on_stripe.tax_ids == {customer: [{"type": "eu_vat", "value": VAT_ID}]}
    with SessionLocal() as db:
        assert service.customer_id(db, db.get(User, uid), "stripe") == "cus_pro"
        assert org_billing.org_customer(db, org["id"], "stripe") == customer


def test_org_customer_is_reused_for_the_organisation_and_never_for_another(client, on_stripe):
    """After the organisation's subscription ends, the next checkout for it
    (by its billing member, not the buyer) opens on the organisation's
    customer, which already holds its VAT id. A second organisation the same
    buyer pays for gets a new customer of its own."""
    buyer, billing, org, uid = _people(client)
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_pro")
        db.commit()
    first = _org_bought(client, on_stripe, buyer, org["id"], "sub_org_1")
    assert first != "cus_pro"
    _cancel(client, "sub_org_1")
    assert [s.status for s in _org_subs(org["id"])] == ["canceled"]

    _org_checkout(client, billing, org["id"])
    params = on_stripe.last
    assert params["customer"] == first
    assert params["customer_update"] == {"address": "auto", "name": "auto"}
    assert "customer_email" not in params and "cus_pro" not in _named(params)
    reference, customer = on_stripe.pay("sub_org_2", country="DE")  # no VAT id asked: the customer has one
    assert customer == first
    assert _refresh(client, billing, reference)["status"] == "paid"
    assert [(s.provider_subscription_id, s.provider_customer_id) for s in _org_subs(org["id"])] == [
        ("sub_org_1", first), ("sub_org_2", first)
    ]  # fmt: skip

    second = make_org(client, buyer, name="Studio South")
    _org_checkout(client, buyer, second["id"])
    params = on_stripe.last
    assert "customer" not in params and params["customer_email"] == BUYER
    assert first not in _named(params) and "cus_pro" not in _named(params)
    reference, customer = on_stripe.pay("sub_org_b", country="FR", vat_id="FR12345678901")
    assert customer not in (first, "cus_pro")
    assert _refresh(client, buyer, reference)["status"] == "paid"
    with SessionLocal() as db:
        assert org_billing.org_customer(db, org["id"], "stripe") == first
        assert org_billing.org_customer(db, second["id"], "stripe") == customer
        assert service.customer_id(db, db.get(User, uid), "stripe") == "cus_pro"
    assert on_stripe.tax_ids == {
        first: [{"type": "eu_vat", "value": VAT_ID}], customer: [{"type": "eu_vat", "value": "FR12345678901"}]
    }  # fmt: skip


def test_org_checkout_never_reuses_a_customer_shared_before_pf3e(client, on_stripe):
    """Rows from before PF3e: the organisation's ended Team is on the buyer's
    own customer `cus_shared`, beside the buyer's own Pro. That customer is
    never the organisation's again: its next checkout opens on a new one. A
    customer that holds another organisation's subscription is not reused
    either; one that holds only this organisation's is. Paddle keeps one
    customer per e-mail, so there the buyer's customer is the organisation's
    (PF3a), as before."""
    buyer, _, org, uid = _people(client)
    two = make_org(client, buyer, name="Studio South")
    three = make_org(client, buyer, name="Studio East")
    alone = make_org(client, buyer, name="Studio West")
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_shared", updated_ago=timedelta(days=20))
        _sub(db, uid, "team", "sub_old_1", "cus_shared", org_id=org["id"], status="canceled",
             ends_in=-timedelta(days=10), updated_ago=timedelta(days=10))  # fmt: skip
        for n, o in enumerate((two, three), start=2):
            _sub(db, uid, "team", f"sub_old_{n}", "cus_two_orgs", org_id=o["id"], status="canceled",
                 ends_in=-timedelta(days=5), updated_ago=timedelta(days=5))  # fmt: skip
        _sub(db, uid, "team", "sub_old_alone", "cus_alone", org_id=alone["id"], status="canceled",
             ends_in=-timedelta(days=5), updated_ago=timedelta(days=5))  # fmt: skip
        db.commit()

    _org_checkout(client, buyer, org["id"])
    params = on_stripe.last
    assert "customer" not in params and params["customer_email"] == BUYER
    assert "cus_shared" not in _named(params)
    _org_checkout(client, buyer, two["id"])
    assert "customer" not in on_stripe.last and "cus_two_orgs" not in _named(on_stripe.last)
    _org_checkout(client, buyer, alone["id"])
    assert on_stripe.last["customer"] == "cus_alone"

    with SessionLocal() as db:
        user = db.get(User, uid)
        assert org_billing.org_customer(db, org["id"], "stripe") is None
        assert org_billing.org_customer(db, two["id"], "stripe") is None
        assert org_billing.org_customer(db, three["id"], "stripe") is None
        assert org_billing.org_customer(db, alone["id"], "stripe") == "cus_alone"
        assert service.customer_id(db, user, "stripe") == "cus_shared"  # the buyer's own Pro is on it
        # Paddle: the organisation's subscription is on its buyer's one customer.
        _sub(db, uid, "team", "sub_paddle_org", "ctm_buyer", org_id=org["id"], provider="paddle")
        db.commit()
        assert service.customer_id(db, user, "paddle") == "ctm_buyer"


# --- 2. The VAT id never reaches the buyer's own plan ---------------------------------------------------


@pytest.mark.parametrize("earlier_pro", [False, True], ids=["no-customer-yet", "earlier-pro"])
def test_org_vat_id_never_makes_the_buyers_pro_business(client, on_stripe, rules, earlier_pro):
    """PF8b's scratch check, reversed. The organisation's Team is paid with its
    VAT id DE123456789: that payment is `business`. The buyer's own Pro,
    bought afterwards from Germany without a VAT id, opens on the buyer's own
    customer (their earlier Pro's `cus_pro`, else a new one), is not
    `business`, and keeps PF2b's EU withdrawal. Their AI top-up opens on that
    same customer."""
    rules(eu_withdrawal_enabled=True)
    buyer, _, org, uid = _people(client)
    if earlier_pro:
        with SessionLocal() as db:  # the buyer's earlier Pro, on their own customer, has ended
            _sub(db, uid, "pro", "sub_pro_old", "cus_pro", status="canceled", ends_in=-timedelta(days=10),
                 updated_ago=timedelta(days=10))  # fmt: skip
            db.commit()

    _org_checkout(client, buyer, org["id"])
    reference, org_customer = on_stripe.pay("sub_org", country="DE", vat_id=VAT_ID)
    assert org_customer != "cus_pro"
    paid = _refresh(client, buyer, reference)
    assert (paid["status"], paid["plan"], paid["business"]) == ("paid", "team", True)

    res = client.post("/billing/checkout", json=checkout_body(), headers=buyer)
    assert res.status_code == 200, res.text
    params = on_stripe.last
    assert org_customer not in _named(params)
    if earlier_pro:
        assert params["customer"] == "cus_pro" and "customer_email" not in params
    else:
        assert "customer" not in params and params["customer_email"] == BUYER
    reference, pro_customer = on_stripe.pay("sub_pro_new", country="DE")
    assert pro_customer != org_customer
    assert on_stripe.sessions[params["id"]]["customer_details"]["tax_ids"] == []
    paid = _refresh(client, buyer, reference)
    assert (paid["status"], paid["plan"], paid["business"]) == ("paid", "pro", False)
    offers = client.get("/billing/subscription", headers=buyer).json()
    assert offers["tier"] == "pro" and offers["withdrawal_until"] is not None

    res = client.post("/account/ai/top-ups", json={"pack": "credits-5000", "currency": "GBP", "consent": CONSENT}, headers=buyer)
    assert res.status_code == 201, res.text
    top_up = on_stripe.last
    assert top_up["mode"] == "payment" and top_up["customer"] == pro_customer
    assert org_customer not in _named(top_up)
    assert on_stripe.tax_ids == {org_customer: [{"type": "eu_vat", "value": VAT_ID}]}  # the buyer's customer holds none
    with SessionLocal() as db:
        assert service.customer_id(db, db.get(User, uid), "stripe") == pro_customer
        assert db.scalar(select(Payment.business).where(Payment.reference == reference)) is False


# --- 3. The portal -------------------------------------------------------------------------------------------------


def test_org_portal_opens_on_the_organisations_customer(client, on_stripe):
    """A billing member who is not the buyer opens the organisation's portal on
    the organisation's customer, never on the buyer's whole Stripe account; the
    buyer's own portal opens on `cus_pro`. A row from before PF3e (another
    organisation's Team on `cus_pro`) is not changed: its portal still opens
    on the customer its subscription is on."""
    buyer, billing, org, uid = _people(client)
    legacy = make_org(client, buyer, name="Studio South")
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_pro", updated_ago=timedelta(days=2))
        _sub(db, uid, "team", "sub_legacy", "cus_pro", org_id=legacy["id"], updated_ago=timedelta(days=1))
        db.commit()
    org_customer = _org_bought(client, on_stripe, buyer, org["id"], "sub_org")
    assert org_customer != "cus_pro"

    res = client.post("/billing/portal", json={"org_id": org["id"]}, headers=billing)
    assert res.status_code == 200, res.text
    assert res.json()["url"] == f"https://billing.stripe.test/p/{org_customer}"
    assert on_stripe.portals[-1]["return_url"].endswith(f"/dashboard/billing/?org={org['id']}")
    res = client.post("/billing/portal", json={"org_id": org["id"]}, headers=buyer)
    assert res.status_code == 200 and on_stripe.portals[-1]["customer"] == org_customer

    res = client.post("/billing/portal", headers=buyer)
    assert res.status_code == 200, res.text
    assert on_stripe.portals[-1]["customer"] == "cus_pro"
    assert on_stripe.portals[-1]["return_url"].endswith("/dashboard/billing/")
    assert client.post("/billing/portal", headers=billing).status_code == 404  # no plan of their own

    res = client.post("/billing/portal", json={"org_id": legacy["id"]}, headers=buyer)
    assert res.status_code == 200 and on_stripe.portals[-1]["customer"] == "cus_pro"  # before PF3e: unchanged
    with SessionLocal() as db:
        user = db.get(User, uid)
        sub = org_billing.managed_subscription(db, org["id"])
        sub.provider_customer_id = None  # the fallback, too, is the organisation's
        assert service.customer_id(db, user, "stripe") == "cus_pro"
        from app.billing.providers import get_provider

        get_provider("stripe").portal_url(db, user, sub)
        db.rollback()
    assert on_stripe.portals[-1]["customer"] == org_customer


# --- 4. Invoices ----------------------------------------------------------------------------------------------------


def test_org_and_personal_invoices_are_split(client, on_stripe):
    """The organisation's invoice list asks Stripe for the organisation's
    customer only and lists its subscription's invoice; the buyer's own list
    asks for `cus_pro` only. A customer shared before PF3e (another
    organisation's Team on `cus_pro`) still splits: that organisation lists
    only its own invoice, and the buyer's list leaves it out."""
    buyer, billing, org, uid = _people(client)
    legacy = make_org(client, buyer, name="Studio South")
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_pro", updated_ago=timedelta(days=2))
        _sub(db, uid, "team", "sub_legacy", "cus_pro", org_id=legacy["id"], updated_ago=timedelta(days=1))
        db.commit()
    org_customer = _org_bought(client, on_stripe, buyer, org["id"], "sub_org")
    assert org_customer != "cus_pro"

    on_stripe.invoice_lists.clear()
    rows = client.get("/billing/invoices", params={"org_id": org["id"]}, headers=billing).json()
    assert on_stripe.invoice_lists == [org_customer] and [r["id"] for r in rows] == ["in_sub_org"]
    res = client.get(rows[0]["pdf_url"], follow_redirects=False)
    assert res.status_code == 302 and res.headers["location"] == "https://pay.stripe.test/in_sub_org.pdf"

    on_stripe.invoice_lists.clear()
    rows = client.get("/billing/invoices", headers=buyer).json()
    assert on_stripe.invoice_lists == ["cus_pro"] and [r["id"] for r in rows] == ["in_sub_pro"]
    res = client.get(rows[0]["pdf_url"], follow_redirects=False)
    assert res.status_code == 302 and res.headers["location"] == "https://pay.stripe.test/in_sub_pro.pdf"

    on_stripe.invoice_lists.clear()
    rows = client.get("/billing/invoices", params={"org_id": legacy["id"]}, headers=buyer).json()
    assert on_stripe.invoice_lists == ["cus_pro"] and [r["id"] for r in rows] == ["in_sub_legacy"]
    assert client.get("/billing/invoices", headers=billing).json() == []  # nothing of their own


# --- 5. Seats and plan changes ----------------------------------------------------------------------------------


def test_org_seats_and_plan_changes_on_the_organisations_customer(client, on_stripe):
    """Seats and plan changes for the organisation (POST /billing/seats and
    /billing/change with `org_id`) work on its own customer as before: the
    subscription is modified in place and stays the organisation's, on its
    customer; the buyer's own Pro is untouched."""
    buyer, billing, org, uid = _people(client)
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_pro")
        db.commit()
    org_customer = _org_bought(client, on_stripe, buyer, org["id"], "sub_org")
    assert org_customer != "cus_pro"

    res = client.post("/billing/seats", json={"seats": 4, "org_id": org["id"]}, headers=billing)
    assert res.status_code == 200, res.text
    assert (res.json()["tier"], res.json()["seats"], res.json()["org_id"]) == ("team", 4, org["id"])
    assert on_stripe.modified[-1][0] == "sub_org" and on_stripe.modified[-1][2] == 4

    # Studio is no longer sold (2026-11-10): the move away from Team is to Pro.
    res = client.post("/billing/change", json={"tier": "pro", "org_id": org["id"]}, headers=billing)
    assert res.status_code == 200 and res.json()["tier"] == "pro", res.text
    res = client.post("/billing/change", json={"tier": "team", "org_id": org["id"]}, headers=buyer)
    assert res.status_code == 200 and (res.json()["tier"], res.json()["seats"]) == ("team", 2), res.text
    assert [m[0] for m in on_stripe.modified] == ["sub_org"] * 3

    (sub,) = _org_subs(org["id"])
    assert (sub.plan, sub.seats, sub.provider_customer_id, sub.user_id) == ("team", 2, org_customer, uid)
    with SessionLocal() as db:
        user = db.get(User, uid)
        own = service.managed_subscription(db, user)
        assert (own.plan, own.provider_customer_id) == ("pro", "cus_pro")
        assert service.customer_id(db, user, "stripe") == "cus_pro"
        assert org_billing.org_customer(db, org["id"], "stripe") == org_customer
    assert me(client, buyer)["plan"] == "pro"
