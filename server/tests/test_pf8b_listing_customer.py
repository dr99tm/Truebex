"""PF8b: a supplier's listing plan is paid on the supplier's own Stripe
customer, and the person's own app plan on theirs, never the other way round.

Stripe Checkout saves a tax id entered at checkout onto the customer the
session ran on, and reports a customer's saved tax ids on every later session
of that customer (`customer_details`: "the customer's tax IDs"). PF2b marks a
payment whose session reports one `business`, which takes the EU withdrawal
away. `_Stripe` below stands in for exactly that, so a listing checkout that
reused the owner's customer would make the owner's own Pro a business payment.

Listing fees do not exist until GD7: `_listing_fee` (PF2d's helper) gives
Standard one and its synced price, as PF8a's tests do.
"""

import json
import logging
import secrets
from datetime import timedelta

import pytest
import stripe
from sqlalchemy import select

from app.billing import org_billing, service
from app.config import get_settings
from app.database import SessionLocal
from app.market.models import CommissionStatement, Supplier, SupplierMember
from app.models import Payment, Subscription, User
from app.supplier import listing
from app.supplier.models import ListingSubscription

from .conftest import CONSENT, STRIPE_SUBS, checkout_body, signup
from .supplier_helpers import admin_headers, as_supplier
from .test_pf2d_billing_followups import _listing_fee
from .test_pf8a_listing_consumer_rules import OWNER, _checkout_row, _now, _owner, _payment, rules  # noqa: F401

VAT_ID = "GB123456789"


class _Stripe:
    """Stripe's side of the Checkout Sessions this server opens. A session
    runs on the customer it names, else on a new one. A tax id entered at
    checkout is saved onto that customer (Checkout shows no tax id field to a
    customer that has one), and every session reports its customer's saved
    tax ids."""

    def __init__(self, monkeypatch):
        self.created: list[dict] = []
        self.sessions: dict[str, dict] = {}
        self.tax_ids: dict[str, list[dict]] = {}
        self.new_customers = 0
        monkeypatch.setattr(stripe.checkout.Session, "create", self._create)
        monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda sid, **k: self.sessions[sid])

    def _create(self, **params):
        session_id = f"cs_pf8b_{len(self.created) + 1}"
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
            self.tax_ids[customer] = [{"type": "gb_vat", "value": vat_id}]
        meta = params["metadata"]
        STRIPE_SUBS[sub_id] = {
            "id": sub_id, "object": "subscription", "customer": customer, "currency": "gbp", "status": "active",
            "cancel_at_period_end": False, "metadata": meta,
            "items": {"data": [{"id": f"si_{sub_id}", "quantity": 1, "current_period_end": int(_now().timestamp()) + 30 * 86400,
                                "price": {"id": params["line_items"][0]["price"], "recurring": {"interval": "month"}}}]},
        }  # fmt: skip
        self.sessions[params["id"]] = {
            "id": params["id"], "object": "checkout.session", "client_reference_id": params["client_reference_id"],
            "status": "complete", "payment_status": "paid", "subscription": sub_id, "invoice": f"in_{sub_id}",
            "customer": customer, "metadata": meta,
            "customer_details": {"address": {"country": country}, "tax_ids": list(self.tax_ids.get(customer, []))},
        }  # fmt: skip
        return params["client_reference_id"], customer


@pytest.fixture()
def on_stripe(client, stripe_prices, monkeypatch) -> _Stripe:
    """Stripe as the checkout provider, a listing fee with its synced price,
    and Stripe's side of the checkouts."""
    monkeypatch.setattr(get_settings(), "billing_provider", "stripe")
    _listing_fee(monkeypatch)
    return _Stripe(monkeypatch)


def _sub(db, uid: int, plan: str, sub_id: str | None, customer: str | None, *, provider="stripe", status="active",
         ends_in=timedelta(days=30), updated_ago=timedelta(0)) -> Subscription:  # fmt: skip
    row = Subscription(
        user_id=uid, plan=plan, provider=provider, status=status, interval="month", currency="GBP", seats=1,
        provider_subscription_id=sub_id, provider_customer_id=customer, current_period_end=_now() + ends_in,
        updated_at=_now() - updated_ago,
    )  # fmt: skip
    db.add(row)
    db.flush()
    return row


def _billing_customer(sid: str) -> str | None:
    with SessionLocal() as db:
        return db.get(Supplier, sid).billing_customer_id


def _set_billing_customer(client, sid: str, customer: str) -> None:
    """The admin sets the supplier's billing customer (PF7's admin endpoint)."""
    res = client.patch(f"/admin/market/suppliers/{sid}", json={"billing_customer_id": customer}, headers=admin_headers(client))
    assert res.status_code == 200, res.text


def _open_listing(client, owner) -> None:
    res = client.post("/supplier/listing", json={"plan": "standard"}, headers=owner)
    assert res.status_code == 200 and res.json()["state"] == "checkout", res.text


def _refresh(client, h, reference: str) -> dict:
    res = client.post(f"/billing/payments/{reference}/refresh", headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def _named(params: dict) -> str:
    """Every value the checkout sent Stripe, to search for a customer id."""
    return json.dumps(params, default=str)


# --- 1. The listing checkout's customer ---------------------------------------------------------


def test_listing_checkout_never_takes_the_owners_pro_customer(client, on_stripe):
    """The owner pays Pro on `cus_pro`. The supplier has no billing customer
    yet, so its listing checkout opens on none: Stripe makes the supplier a new
    customer from the member's e-mail. `cus_pro` is not named at all."""
    owner, _, uid = _owner(client)
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_pro")
        db.commit()

    _open_listing(client, owner)
    params = on_stripe.last
    assert params["metadata"]["plan"] == "listing_standard"
    assert "customer" not in params and "customer_update" not in params
    assert params["customer_email"] == OWNER
    assert "cus_pro" not in _named(params)
    assert params["tax_id_collection"] == {"enabled": True}  # the supplier's VAT id goes onto its own customer


def test_listing_checkout_uses_the_suppliers_billing_customer(client, on_stripe, monkeypatch):
    """The supplier's billing customer is `cus_sup` (set by the admin, or by
    the sync after its first listing checkout): the listing checkout opens on
    it, and Checkout saves the address and the business name there."""
    owner, sid, uid = _owner(client)
    _set_billing_customer(client, sid, "cus_sup")
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_pro")
        db.commit()

    _open_listing(client, owner)
    params = on_stripe.last
    assert params["customer"] == "cus_sup"
    assert params["customer_update"] == {"address": "auto", "name": "auto"}
    assert "customer_email" not in params and "cus_pro" not in _named(params)
    with SessionLocal() as db:
        row = db.scalar(select(ListingSubscription).where(ListingSubscription.status == "checkout"))
        assert db.scalar(select(Payment).where(Payment.reference == row.payment_ref)).provider_ref == params["id"]

    # Stripe down: no checkout, and neither its payment nor its listing row is left behind.
    def down(**params):
        raise stripe.APIConnectionError("Stripe is unreachable")

    monkeypatch.setattr(stripe.checkout.Session, "create", down)
    res = client.post("/supplier/listing", json={"plan": "standard"}, headers=owner)
    assert res.status_code == 502, res.text
    with SessionLocal() as db:
        assert len(db.scalars(select(ListingSubscription).where(ListingSubscription.supplier_id == sid)).all()) == 1
        assert len(db.scalars(select(Payment).where(Payment.plan == "listing_standard")).all()) == 1


# --- 2. The app plan's customer -------------------------------------------------------------------


def test_app_checkouts_never_take_the_listing_customer(client, on_stripe):
    """The owner's listing plan on `cus_sup` was updated after their Pro on
    `cus_pro` (which has ended; a Pro trial runs, so AI credits can be bought).
    The Pro checkout and the AI top-up both open on `cus_pro`. Once the owner
    has no app plan with a customer at all, both open on none
    (`customer_email`), never on `cus_sup`."""
    owner, _, uid = _owner(client)
    with SessionLocal() as db:
        pro = _sub(db, uid, "pro", "sub_pro", "cus_pro", status="canceled", ends_in=-timedelta(days=3),
                   updated_ago=timedelta(days=3))  # fmt: skip
        _sub(db, uid, "listing_standard", "sub_listing", "cus_sup")
        _sub(db, uid, "pro", None, None, provider="trial", ends_in=timedelta(days=7), updated_ago=timedelta(days=7))
        db.commit()
        pro_id = pro.id

    def checkouts() -> tuple[dict, dict]:
        res = client.post("/billing/checkout", json=checkout_body(), headers=owner)
        assert res.status_code == 200, res.text
        pro_params = on_stripe.last
        res = client.post("/account/ai/top-ups", json={"pack": "credits-5000", "currency": "GBP", "consent": CONSENT}, headers=owner)
        assert res.status_code == 201, res.text
        assert on_stripe.last["mode"] == "payment"
        return pro_params, on_stripe.last

    for params in checkouts():
        assert params["customer"] == "cus_pro", params["mode"]
        assert params["customer_update"] == {"address": "auto", "name": "auto"}
        assert "customer_email" not in params and "cus_sup" not in _named(params)
    with SessionLocal() as db:
        assert service.customer_id(db, db.get(User, uid), "stripe") == "cus_pro"

    with SessionLocal() as db:  # no app plan with a customer any more: only the listing plan's
        db.delete(db.get(Subscription, pro_id))
        db.commit()
    for params in checkouts():
        assert "customer" not in params and params["customer_email"] == OWNER, params["mode"]
        assert "cus_sup" not in _named(params)
    with SessionLocal() as db:
        assert service.customer_id(db, db.get(User, uid), "stripe") is None


# --- 3. The VAT id stays with the supplier ------------------------------------------------------------


def test_listing_vat_id_never_makes_the_owners_pro_business(client, on_stripe, rules):
    """The listing plan is bought with the company's VAT id: that payment is
    `business`. The owner's own Pro, bought afterwards from Germany without a
    VAT id, runs on the owner's `cus_pro`, is not `business`, and keeps PF2b's
    EU withdrawal."""
    rules(eu_withdrawal_enabled=True)
    owner, sid, uid = _owner(client)
    with SessionLocal() as db:  # the owner's earlier Pro, on their own customer, has ended
        _sub(db, uid, "pro", "sub_pro_old", "cus_pro", status="canceled", ends_in=-timedelta(days=10),
             updated_ago=timedelta(days=10))  # fmt: skip
        db.commit()

    _open_listing(client, owner)
    listing_ref, listing_customer = on_stripe.pay("sub_listing", country="GB", vat_id=VAT_ID)
    assert listing_customer != "cus_pro"
    paid = _refresh(client, owner, listing_ref)
    assert (paid["status"], paid["plan"], paid["business"]) == ("paid", "listing_standard", True)
    assert on_stripe.tax_ids == {listing_customer: [{"type": "gb_vat", "value": VAT_ID}]}
    assert client.get("/supplier/listing", headers=owner).json()["plan"] == "standard"  # the portal's read syncs
    assert _billing_customer(sid) == listing_customer

    res = client.post("/billing/checkout", json=checkout_body(), headers=owner)
    assert res.status_code == 200, res.text
    assert on_stripe.last["customer"] == "cus_pro"
    pro_ref, pro_customer = on_stripe.pay("sub_pro_new", country="DE")
    assert pro_customer == "cus_pro"
    assert on_stripe.sessions[on_stripe.last["id"]]["customer_details"]["tax_ids"] == []
    paid = _refresh(client, owner, pro_ref)
    assert (paid["status"], paid["plan"], paid["business"]) == ("paid", "pro", False)
    offers = client.get("/billing/subscription", headers=owner).json()
    assert offers["tier"] == "pro" and offers["withdrawal_until"] is not None
    assert on_stripe.tax_ids == {listing_customer: [{"type": "gb_vat", "value": VAT_ID}]}  # cus_pro holds none


# --- 4. The listing sync -------------------------------------------------------------------------------


def test_listing_sync_copies_the_listing_customer_not_the_owners(client, on_stripe):
    """The owner pays Pro on `cus_pro`. Their first listing checkout makes the
    supplier a customer of its own; the sync copies that one into
    `billing_customer_id` (which PF7's statements invoice), and the next
    listing checkout opens on it."""
    owner, sid, uid = _owner(client)
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_pro")
        db.commit()

    _open_listing(client, owner)
    reference, customer = on_stripe.pay("sub_listing", country="GB", vat_id=VAT_ID)
    assert _refresh(client, owner, reference)["status"] == "paid"
    view = client.get("/supplier/listing", headers=owner).json()  # each read of the plan syncs it
    assert view["plan"] == "standard" and view["subscription"]["status"] == "active"
    assert _billing_customer(sid) == customer and customer != "cus_pro"

    _open_listing(client, owner)
    assert on_stripe.last["customer"] == customer


def test_listing_sync_keeps_the_billing_customer_already_set(client, caplog):
    """The admin set `cus_admin` after the listing plan started on `cus_sup`
    (say, to invoice another company of the same group). The sync follows the
    plan but keeps the billing customer already set, and says so once."""
    _, sid, uid = _owner(client)
    _set_billing_customer(client, sid, "cus_admin")
    with SessionLocal() as db:
        _payment(db, uid, "listing_standard", "lst_paid", sub_id="sub_listing")
        row = _checkout_row(db, sid, uid, "lst_paid")
        _sub(db, uid, "listing_standard", "sub_listing", "cus_sup")
        db.commit()
        row_id = row.id

        with caplog.at_level(logging.WARNING, logger="truebex.supplier"):
            assert listing.sync(db, _now()) == 1
            assert listing.sync(db, _now()) == 0  # in step: nothing changes, nothing said again
        row = db.get(ListingSubscription, row_id)
        assert (row.status, row.provider_subscription_id) == ("active", "sub_listing")
        assert db.get(Supplier, sid).listing_plan == "standard"
    assert _billing_customer(sid) == "cus_admin"
    said = [r.getMessage() for r in caplog.records if r.name == "truebex.supplier"]
    assert len(said) == 1 and "cus_sup" in said[0] and "cus_admin" in said[0]


# --- 5. Invoices ----------------------------------------------------------------------------------------------


def test_personal_invoices_are_the_app_plan_customers(client, monkeypatch):
    """The owner's Billing lists the invoices of their own customer `cus_pro`,
    not the supplier's `cus_sup`, although the listing plan was updated later."""
    asked: list[str] = []
    invoices = {
        "cus_pro": {"id": "in_pro_1", "customer": "cus_pro", "subscription": "sub_pro", "invoice_pdf": "https://pay.stripe.test/in_pro_1.pdf"},
        "cus_sup": {"id": "in_listing_1", "customer": "cus_sup", "subscription": "sub_listing", "invoice_pdf": "https://pay.stripe.test/in_listing_1.pdf"},
    }  # fmt: skip
    for inv in invoices.values():
        inv.update({"number": inv["id"].upper(), "created": int(_now().timestamp()), "total": 2400, "tax": 400,
                    "currency": "gbp", "status": "paid"})  # fmt: skip

    def list_invoices(customer, **_kw):
        asked.append(customer)
        return {"data": [invoices[customer]]}

    monkeypatch.setattr(stripe.Invoice, "list", list_invoices)
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda invoice_id, **_kw: next(i for i in invoices.values() if i["id"] == invoice_id))
    owner, _, uid = _owner(client)
    with SessionLocal() as db:
        _sub(db, uid, "pro", "sub_pro", "cus_pro", updated_ago=timedelta(days=2))
        _sub(db, uid, "listing_standard", "sub_listing", "cus_sup")
        db.commit()
        assert org_billing.personal_scope(db, db.get(User, uid), "stripe").customers == ("cus_pro",)

    rows = client.get("/billing/invoices", headers=owner).json()
    assert asked == ["cus_pro"] and [r["id"] for r in rows] == ["in_pro_1"]
    res = client.get(rows[0]["pdf_url"], follow_redirects=False)
    assert res.status_code == 302 and res.headers["location"] == "https://pay.stripe.test/in_pro_1.pdf"


def test_statement_invoice_is_opened_on_the_suppliers_customer(client, monkeypatch):
    """A commission statement is invoiced to the supplier's billing customer
    (PF7). Its PDF opens for the supplier's owners, whichever customer each
    pays their own plan on (the one who also pays Pro on `cus_pro`, and one
    with no customer at all); an invoice on another customer stays closed."""
    invoices = {
        "in_stmt_1": {"id": "in_stmt_1", "customer": "cus_sup", "invoice_pdf": "https://pay.stripe.test/in_stmt_1.pdf"},
        "in_stmt_2": {"id": "in_stmt_2", "customer": "cus_other", "invoice_pdf": "https://pay.stripe.test/in_stmt_2.pdf"},
    }  # fmt: skip
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda invoice_id, **_kw: invoices[invoice_id])
    owner, sid, uid = _owner(client)
    _set_billing_customer(client, sid, "cus_sup")
    second = as_supplier(signup(client, "second@nord.example.com"), sid)
    with SessionLocal() as db:
        _sub(db, uid, "listing_standard", "sub_listing", "cus_sup", updated_ago=timedelta(days=2))
        _sub(db, uid, "pro", "sub_pro", "cus_pro")
        second_id = db.scalar(select(User.id).where(User.email == "second@nord.example.com"))
        db.add(SupplierMember(supplier_id=sid, user_id=second_id, role="owner"))
        statements = {}
        for month, invoice in (("2026-08", "in_stmt_1"), ("2026-09", "in_stmt_2")):
            statements[invoice] = secrets.token_hex(16)
            db.add(CommissionStatement(statement_id=statements[invoice], supplier_id=sid, month=month, currency="GBP",
                                       exponent=2, commission_total=8660, total=8660, orders=1, state="invoiced",
                                       invoice_ref=invoice))  # fmt: skip
        db.commit()

    for h in (owner, second):
        res = client.get(f"/supplier/statements/{statements['in_stmt_1']}/invoice", headers=h)
        assert res.status_code == 200, res.text
        assert res.json()["url"] == "https://pay.stripe.test/in_stmt_1.pdf"
        res = client.get(f"/supplier/statements/{statements['in_stmt_2']}/invoice", headers=h)
        assert res.status_code == 404, res.text
