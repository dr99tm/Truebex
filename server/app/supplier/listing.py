"""Listing plan and billing in the portal (PF8 Scope 7): choose a listing
plan (`market/listing_plans.json`, placeholders until GD7), pay it through
PF2's billing interface (Stripe: a business customer with its VAT id), see
commission statements and their invoices, connect payouts for orders
(Stripe Connect onboarding, PF7).

PF2's interface (`billing.base`, `billing.providers.get_provider`) is not
in this branch's tree yet, so it is imported behind `billing_interface()`:
without it a plan with a fee is recorded `pending` (the owner bills it by
hand) and statements stay `pending`, as PF7's `commissions._pf2_invoice`
does. The merge with PF2 removes the guard and nothing else.

A paid plan is a Stripe subscription opened with PF2's
`create_checkout(db, user, payment, price, seats, discount)` on the synced
listing price (`provider_prices` tier `listing_<plan>`, interval `month`).
PF2's webhook writes the subscription; `supplier.listing.sync` copies its
state into `listing_subscriptions` and the customer into
`suppliers.billing_customer_id`, which PF7's statements invoice through
`create_invoice(db, customer, lines)`. A plan billed by its subscription
leaves the listing fee off the monthly statement.
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


def billing_interface() -> SimpleNamespace | None:
    """PF2's billing interface, or None until PF2 is merged."""
    try:
        from ..billing.base import InvoiceLine, ProviderError  # type: ignore[attr-defined]  (PF2)
        from ..billing.providers import get_provider  # type: ignore[attr-defined]  (PF2)
    except ImportError:
        return None
    return SimpleNamespace(InvoiceLine=InvoiceLine, ProviderError=ProviderError, get_provider=get_provider)


def listing_price(db: Session, plan: str, currency: str, amount: int):
    """PF2's synced Stripe price for this plan's fee (None when not synced)."""
    try:
        from ..billing import service  # PF2's provider_price lives here
    except ImportError:
        return None
    find = getattr(service, "provider_price", None)
    if find is None:
        return None
    return find(db, "stripe", tier_of(plan), "month", currency, amount)


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
    db.add(payment)
    db.flush()
    try:
        url = provider.create_checkout(db, m.user, payment, price, 1, None)
    except bi.ProviderError:
        db.rollback()
        raise ContractError("provider_error", 502, "The payment provider didn't respond. Please try again.")
    row.status, row.payment_ref = "checkout", payment.reference
    db.add(payment)
    db.add(row)
    db.commit()
    return {"state": "checkout", "plan": plan_id, "checkout_url": url}


_STATUS = {"active": "active", "trialing": "active", "past_due": "past_due", "canceled": "canceled", "paused": "past_due"}


def sync(db: Session, at: datetime) -> int:
    """Keep listing_subscriptions in step with PF2's subscriptions."""
    n = 0
    rows = list(
        db.scalars(
            select(ListingSubscription).where(
                ListingSubscription.provider == "stripe", ListingSubscription.status.in_(("checkout", "active", "past_due"))
            )
        )
    )
    for row in rows:
        payment = db.scalar(select(Payment).where(Payment.reference == row.payment_ref)) if row.payment_ref else None
        sub = None
        if row.provider_subscription_id:
            sub = db.scalar(
                select(Subscription).where(
                    Subscription.provider == "stripe", Subscription.provider_subscription_id == row.provider_subscription_id
                )
            )
        elif payment is not None:
            sub = db.scalar(
                select(Subscription)
                .where(
                    Subscription.provider == "stripe",
                    Subscription.user_id == payment.user_id,
                    Subscription.plan == tier_of(row.plan),
                )
                .order_by(Subscription.updated_at.desc())
            )
        supplier = db.get(Supplier, row.supplier_id)
        if sub is None:
            created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=at.tzinfo)
            if row.status == "checkout" and created < at - CHECKOUT_TTL and (payment is None or payment.status != "paid"):
                row.status, row.detail = "expired", "The checkout was not completed."
                db.add(row)
                n += 1
            continue
        status = _STATUS.get(sub.status, "canceled")
        changed = (
            row.status != status
            or row.provider_subscription_id != sub.provider_subscription_id
            or row.current_period_end != sub.current_period_end
        )
        row.status, row.provider_subscription_id = status, sub.provider_subscription_id
        row.current_period_end = sub.current_period_end
        if supplier is not None:
            if sub.provider_customer_id and supplier.billing_customer_id != sub.provider_customer_id:
                supplier.billing_customer_id = sub.provider_customer_id
                changed = True
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
    try:
        return bi.get_provider("stripe").invoice_pdf_url(db, m.user, s.invoice_ref)
    except bi.ProviderError:
        raise not_found("That invoice")


def connect(db: Session, supplier: Supplier) -> dict:
    require_verified(supplier, "connect payouts")
    site = get_settings().site_url.rstrip("/")
    url = checkout.onboarding_link(
        db, supplier, f"{site}/supplier/billing/?connect=refresh", f"{site}/supplier/billing/?connect=done"
    )
    return {"url": url, "connected": True}
