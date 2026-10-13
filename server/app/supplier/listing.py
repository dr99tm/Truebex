"""Listing plan and billing in the portal (PF8 Scope 7): choose a listing
plan (`market/listing_plans.json`, placeholders until GD7), pay it through
PF2's billing interface (Stripe: a business customer with its VAT id), see
commission statements and their invoices, connect payouts for orders
(Stripe Connect onboarding, PF7).

PF2's interface (`billing.base`, `billing.providers.get_provider`) is
imported in `billing_interface()`. While Stripe is off or a plan's fee has no
synced price (`sync_prices.py` syncs `listing_<plan>` once GD7 sets fees), a
plan with a fee is recorded `pending` (the owner bills it by hand).

A paid plan is a Stripe subscription opened with PF2's
`create_checkout(db, user, payment, price, seats, discount)` on the synced
listing price (`provider_prices` tier `listing_<plan>`, interval `month`);
its checkout returns to `/supplier/billing/?checkout=…&ref=…`, whose page
calls PF2's refresh (PF2d). PF2's webhook or that refresh writes the
subscription and names it on the paid payment; `supplier.listing.sync` (and
each read of the plan) finds it by that id (PF8a) and copies its state into
`listing_subscriptions` and the customer into
`suppliers.billing_customer_id`, which PF7's statements invoice through
`create_invoice(db, customer, lines)`. A plan billed by its subscription
leaves the listing fee off the monthly statement.

PF8b: the checkout opens on the supplier's own Stripe customer
(`billing_customer_id`, found by PF2 through the listing row that names the
checkout's payment), or on a new one made from the member's e-mail, never on
the customer the member pays their own plan on. So the sync copies the
supplier's own customer, and only into an empty `billing_customer_id`: one
already set (by the admin, or by an earlier checkout) wins. A statement's
invoice PDF is opened on that customer, for any of the supplier's owners.
"""

import logging
import secrets
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..market import checkout
from ..market.commissions import commission_json, statement_json
from ..market.common import is_hex32, money, not_found, now, rfc3339
from ..market import listing as market_listing
from ..market.models import Commission, CommissionStatement, Supplier, SupplierRegion
from ..market.taxonomy import active_regions
from ..models import Payment, Subscription
from .common import Member, require_verified
from .models import ListingSubscription

log = logging.getLogger("truebex.supplier")

CHECKOUT_TTL = timedelta(hours=24)
LIVE = ("active", "past_due")


def tier_of(plan: str) -> str:
    """The `provider_prices` / `subscriptions` tier of a listing plan."""
    return f"listing_{plan}"


def billing_interface() -> SimpleNamespace:
    """PF2's billing interface (imported here, so tests can stand in for it;
    a stand-in without `InvoiceScope` gets the member-scoped invoice call)."""
    from ..billing.base import InvoiceLine, ProviderError
    from ..billing.providers import get_provider

    try:
        from ..billing.base import InvoiceScope
    except ImportError:
        InvoiceScope = None
    return SimpleNamespace(
        InvoiceLine=InvoiceLine, ProviderError=ProviderError, InvoiceScope=InvoiceScope, get_provider=get_provider
    )


def listing_price(db: Session, plan: str, currency: str, amount: int):
    """PF2's synced Stripe price for this plan's fee (None when not synced)."""
    from ..billing import service

    return service.provider_price(db, "stripe", tier_of(plan), "month", currency, amount)


def billing_currency(db: Session, supplier: Supplier) -> str:
    """The currency the supplier is billed in: its home country's region's,
    else its first region's, else GBP (the UK company's)."""
    regions = active_regions(db)
    if supplier.country in regions:
        return regions[supplier.country].currency
    first = db.scalar(
        select(SupplierRegion.currency).where(SupplierRegion.supplier_id == supplier.supplier_id).order_by(SupplierRegion.id)
    )
    return first or "GBP"


def _exponent(db: Session, currency: str) -> int:
    for r in active_regions(db).values():
        if r.currency == currency:
            return r.exponent
    return 2


def current(db: Session, supplier: Supplier) -> ListingSubscription | None:
    return db.scalar(
        select(ListingSubscription)
        .where(ListingSubscription.supplier_id == supplier.supplier_id)
        .order_by(ListingSubscription.created_at.desc(), ListingSubscription.id.desc())
    )


def billed_by_subscription(db: Session, supplier: Supplier) -> bool:
    """True when the listing fee is paid by a live provider subscription."""
    sub = current(db, supplier)
    return bool(sub and sub.provider != "none" and sub.status in LIVE and sub.plan == (supplier.listing_plan or ""))


def subscription_json(sub: ListingSubscription | None, exponent: int = 2) -> dict | None:
    if sub is None:
        return None
    return {
        "plan": sub.plan,
        "provider": sub.provider,
        "status": sub.status,
        "amount": money(sub.amount, sub.currency, exponent) if sub.amount and sub.currency else None,
        "current_period_end": rfc3339(sub.current_period_end),
        "detail": sub.detail,
        "created_at": rfc3339(sub.created_at),
    }


def overview(db: Session, supplier: Supplier) -> dict:
    # The supplier's own plan follows PF2's subscription first, so the page
    # shows a plan just paid for at once (PF2d: back from its checkout).
    sync(db, now(), supplier.supplier_id)
    currency = billing_currency(db, supplier)
    exp = _exponent(db, currency)
    bi = billing_interface()
    stripe_ready = False
    if bi is not None:
        try:
            stripe_ready = bool(bi.get_provider("stripe").enabled())
        except Exception:  # noqa: BLE001
            stripe_ready = False
    active = market_listing.plan_of(supplier)
    return {
        "plan": active.id,
        "commission_bp": market_listing.commission_bp_for(supplier),
        "currency": currency,
        "plans": [
            {
                "id": p.id,
                "name": p.name,
                "commission_bp": p.commission_bp,
                "monthly_fee": money(int(p.monthly_fee[currency]), currency, exp) if p.monthly_fee.get(currency) else None,
            }
            for p in market_listing.plans().values()
        ],
        "subscription": subscription_json(current(db, supplier), exp),
        "billing": {"interface": bi is not None, "stripe_ready": stripe_ready},
        "payouts": {
            "connected": bool(supplier.connect_account_id),
            "ready": bool(supplier.connect_ready),
            "payments_enabled": get_settings().market_payments_enabled,
            "stripe_configured": bool(get_settings().stripe_secret_key),
        },
        "verified": supplier.status == "verified",
    }


def choose(db: Session, m: Member, plan_id: str) -> dict:
    """Switch plan: a plan without a fee applies now; one with a fee opens a
    checkout through PF2 (or waits `pending` without PF2)."""
    supplier = m.supplier
    all_plans = market_listing.plans()
    if plan_id not in all_plans:
        raise ContractError(
            "validation_failed", 422, f"plan: one of {', '.join(all_plans)}",
            {"fields": [{"field": "plan", "in": "body", "message": "unknown plan"}]},
        )  # fmt: skip
    plan = all_plans[plan_id]
    currency = billing_currency(db, supplier)
    fee = int(plan.monthly_fee.get(currency) or 0)
    at = now()
    if not fee:
        supplier.listing_plan = plan_id
        db.add(supplier)
        db.add(
            ListingSubscription(
                supplier_id=supplier.supplier_id, plan=plan_id, provider="none", status="active",
                currency=currency, amount=0, created_by=m.user.id, created_at=at,
            )
        )  # fmt: skip
        db.commit()
        return {"state": "active", "plan": plan_id, "checkout_url": None}

    require_verified(supplier, "choose a paid listing plan")
    row = ListingSubscription(
        supplier_id=supplier.supplier_id, plan=plan_id, provider="stripe", status="pending",
        currency=currency, amount=fee, created_by=m.user.id, created_at=at,
    )  # fmt: skip
    bi = billing_interface()
    provider = bi.get_provider("stripe") if bi is not None else None
    if provider is None or not provider.enabled():
        row.detail = "Online payment for listing plans is not open yet; Truebex invoices this plan."
        db.add(row)
        db.commit()
        return {"state": "pending", "plan": plan_id, "checkout_url": None, "detail": row.detail}
    price = listing_price(db, plan_id, currency, fee)
    if price is None:
        row.detail = "Online payment for this plan isn't set up yet; Truebex invoices this plan."
        db.add(row)
        db.commit()
        return {"state": "pending", "plan": plan_id, "checkout_url": None, "detail": row.detail}
    payment = Payment(
        user_id=m.user.id,
        provider="stripe",
        plan=tier_of(plan_id),
        reference=f"lst_{secrets.token_hex(12)}",
        amount=fee,
        currency=currency,
        status="pending",
    )
    for column, value in (("interval", "month"), ("seats", 1)):  # PF2's columns
        if hasattr(Payment, column):
            setattr(payment, column, value)
    # The row names its payment before the checkout opens: PF2's Stripe
    # checkout finds the supplier's own customer through it (PF8b).
    row.status, row.payment_ref = "checkout", payment.reference
    db.add(payment)
    db.add(row)
    db.flush()
    try:
        url = provider.create_checkout(db, m.user, payment, price, 1, None)
    except bi.ProviderError:
        db.rollback()
        raise ContractError("provider_error", 502, "The payment provider didn't respond. Please try again.")
    db.add(payment)
    db.commit()
    return {"state": "checkout", "plan": plan_id, "checkout_url": url}


_STATUS = {"active": "active", "trialing": "active", "past_due": "past_due", "canceled": "canceled", "paused": "past_due"}


def _stripe_subscription(db: Session, provider_subscription_id: str) -> Subscription | None:
    return db.scalar(
        select(Subscription).where(
            Subscription.provider == "stripe", Subscription.provider_subscription_id == provider_subscription_id
        )
    )


def subscription_of(db: Session, row: ListingSubscription, payment: Payment | None) -> Subscription | None:
    """PF2's subscription that pays this listing row (PF8a): the one the row
    names, else the one its checkout's payment names (set when PF2 marks a
    Stripe checkout paid, PF2d). Owner and tier are only the fallback for a
    paid checkout whose payment names none (rows from before PF2d), and never
    take a subscription another checkout or listing row names. An unpaid
    checkout matches nothing: it expires after CHECKOUT_TTL."""
    if row.provider_subscription_id:
        return _stripe_subscription(db, row.provider_subscription_id)
    if payment is None or payment.status != "paid":
        return None
    if payment.provider_subscription_id:
        return _stripe_subscription(db, payment.provider_subscription_id)
    db.flush()  # rows matched earlier in this sync name theirs
    named_by_payment = select(Payment.provider_subscription_id).where(
        Payment.provider == "stripe", Payment.provider_subscription_id.is_not(None)
    )
    named_by_row = select(ListingSubscription.provider_subscription_id).where(
        ListingSubscription.id != row.id, ListingSubscription.provider_subscription_id.is_not(None)
    )
    return db.scalar(
        select(Subscription)
        .where(
            Subscription.provider == "stripe",
            Subscription.user_id == payment.user_id,
            Subscription.plan == tier_of(row.plan),
            Subscription.provider_subscription_id.not_in(named_by_payment),
            Subscription.provider_subscription_id.not_in(named_by_row),
        )
        .order_by(Subscription.updated_at.desc(), Subscription.id.desc())
    )


def sync(db: Session, at: datetime, supplier_id: str | None = None) -> int:
    """Keep listing_subscriptions in step with PF2's subscriptions (every
    supplier's, or only `supplier_id`'s), each row with its own
    (subscription_of)."""
    n = 0
    query = select(ListingSubscription).where(
        ListingSubscription.provider == "stripe", ListingSubscription.status.in_(("checkout", "active", "past_due"))
    )
    if supplier_id is not None:
        query = query.where(ListingSubscription.supplier_id == supplier_id)
    rows = list(db.scalars(query.order_by(ListingSubscription.id)))
    for row in rows:
        payment = db.scalar(select(Payment).where(Payment.reference == row.payment_ref)) if row.payment_ref else None
        sub = subscription_of(db, row, payment)
        supplier = db.get(Supplier, row.supplier_id)
        if sub is None:
            created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=at.tzinfo)
            if row.status == "checkout" and created < at - CHECKOUT_TTL and (payment is None or payment.status != "paid"):
                row.status, row.detail = "expired", "The checkout was not completed."
                db.add(row)
                n += 1
            continue
        status = _STATUS.get(sub.status, "canceled")
        matched = row.provider_subscription_id != sub.provider_subscription_id
        changed = matched or row.status != status or row.current_period_end != sub.current_period_end
        row.status, row.provider_subscription_id = status, sub.provider_subscription_id
        row.current_period_end = sub.current_period_end
        if supplier is not None:
            customer = sub.provider_customer_id
            if customer and not supplier.billing_customer_id:
                supplier.billing_customer_id = customer
                changed = True
            elif customer and supplier.billing_customer_id != customer and matched:
                # PF8b: the billing customer already set wins (the admin's, or
                # the one an earlier listing checkout made). Listing checkouts
                # open on it, so they differ only after the admin changed it.
                log.warning(
                    "supplier %s: listing subscription %s is on %s; statements stay on %s",
                    supplier.supplier_id, sub.provider_subscription_id, customer, supplier.billing_customer_id,
                )  # fmt: skip
            if status == "active" and supplier.listing_plan != row.plan:
                supplier.listing_plan = row.plan
                changed = True
            db.add(supplier)
        db.add(row)
        n += 1 if changed else 0
    db.commit()
    return n


# --- Statements and payouts ---------------------------------------------------------------


def statements(db: Session, supplier: Supplier) -> dict:
    rows = db.scalars(
        select(CommissionStatement)
        .where(CommissionStatement.supplier_id == supplier.supplier_id)
        .order_by(CommissionStatement.month.desc(), CommissionStatement.created_at.desc())
        .limit(60)
    )
    comms = db.scalars(
        select(Commission).where(Commission.supplier_id == supplier.supplier_id).order_by(Commission.created_at.desc()).limit(200)
    )
    return {
        "statements": [
            {**statement_json(s, supplier.name), "invoice_available": bool(s.invoice_ref)} for s in rows
        ],
        "commissions": [commission_json(c) for c in comms],
    }


def invoice_url(db: Session, m: Member, statement_id: str) -> str:
    s = db.get(CommissionStatement, statement_id) if is_hex32(statement_id) else None
    if s is None or s.supplier_id != m.supplier.supplier_id:
        raise not_found("That statement")
    if not s.invoice_ref:
        raise ContractError("not_invoiced", 409, "This statement has no invoice yet.")
    bi = billing_interface()
    if bi is None:
        raise ContractError("unavailable", 503, "Invoices open here once billing is connected.")
    provider = bi.get_provider("stripe")
    try:
        if bi.InvoiceScope is None:
            return provider.invoice_pdf_url(db, m.user, s.invoice_ref)
        # PF8b: invoiced to the supplier's own customer (PF7), not to the
        # customer the member pays their own plan on.
        customers = (m.supplier.billing_customer_id,) if m.supplier.billing_customer_id else ()
        return provider.invoice_pdf_url(db, m.user, s.invoice_ref, bi.InvoiceScope(customers=customers))
    except bi.ProviderError:
        raise not_found("That invoice")


def connect(db: Session, supplier: Supplier) -> dict:
    require_verified(supplier, "connect payouts")
    site = get_settings().site_url.rstrip("/")
    url = checkout.onboarding_link(
        db, supplier, f"{site}/supplier/billing/?connect=refresh", f"{site}/supplier/billing/?connect=done"
    )
    return {"url": url, "connected": True}
