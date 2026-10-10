"""Commissions on paid orders and the suppliers' monthly statements.

The commission is a rate (basis points) of a paid order's goods value
excluding tax and delivery (GD1 §4.2: GBP 1,299.00 incl. 20 % VAT → base
129 900 × 10 000 / 12 000 = 108 250 pence, half-even; at 10 % → 10 825).
It is accrued when the supplier's part is transferred (the transfer is the
part minus the commission, so the platform has collected it), voided when
that part is refunded, and listed on a monthly statement with the listing
fee. The statement becomes an invoice through PF2's `create_invoice`
(Stripe) when PF2 is merged and the supplier has a billing customer;
otherwise it stays `pending` for the owner to invoice by hand.
"""

import logging
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .common import apply_bp, format_major, money, net_of_tax, new_id, rfc3339
from .listing import commission_bp_for, monthly_fee
from .models import (
    Commission,
    CommissionStatement,
    MarketOrder,
    MarketOrderLine,
    MarketOrderSupplier,
    Supplier,
    SupplierRegion,
)

log = logging.getLogger("truebex.market")


def goods_base(lines: list[MarketOrderLine]) -> int:
    """Goods value excluding tax (delivery is never in it)."""
    base = 0
    for line in lines:
        unit = line.quoted_unit_amount if line.quoted_unit_amount is not None else line.unit_amount
        gross = unit * line.qty
        base += net_of_tax(gross, line.tax_rate_bp) if line.includes_tax else gross
    return base


def compute(db: Session, order: MarketOrder, group: MarketOrderSupplier, supplier: Supplier) -> tuple[int, int, int]:
    """(rate_bp, base, amount) for one supplier's part of an order."""
    lines = list(
        db.scalars(
            select(MarketOrderLine).where(
                MarketOrderLine.order_id == order.order_id, MarketOrderLine.supplier_id == group.supplier_id
            )
        )
    )
    rate = group.commission_bp if group.commission_bp is not None else commission_bp_for(supplier)
    base = goods_base(lines)
    return rate, base, apply_bp(base, rate)


def accrue(db: Session, order: MarketOrder, group: MarketOrderSupplier, rate: int, base: int, amount: int) -> Commission:
    row = db.scalar(
        select(Commission).where(Commission.order_id == order.order_id, Commission.supplier_id == group.supplier_id)
    ) or Commission(order_id=order.order_id, supplier_id=group.supplier_id)
    row.rate_bp, row.base, row.amount = rate, base, amount
    row.currency, row.exponent = order.currency, order.exponent
    row.state = "accrued"
    db.add(row)
    return row


def void(db: Session, order_id: str, supplier_id: str) -> None:
    row = db.scalar(select(Commission).where(Commission.order_id == order_id, Commission.supplier_id == supplier_id))
    if row is not None and row.state == "accrued":
        row.state = "void"
        db.add(row)


def commission_json(c: Commission) -> dict:
    return {
        "order_id": c.order_id,
        "supplier_id": c.supplier_id,
        "rate_bp": c.rate_bp,
        "base": money(c.base, c.currency, c.exponent),
        "amount": money(c.amount, c.currency, c.exponent),
        "state": c.state,
        "statement_id": c.statement_id,
        "invoice_ref": c.invoice_ref,
        "created_at": rfc3339(c.created_at),
    }


def statement_json(s: CommissionStatement, supplier_name: str | None = None) -> dict:
    return {
        "statement_id": s.statement_id,
        "supplier_id": s.supplier_id,
        "supplier_name": supplier_name,
        "month": s.month,
        "orders": s.orders,
        "commission": money(s.commission_total, s.currency, s.exponent),
        "listing_fee": money(s.listing_fee, s.currency, s.exponent),
        "total": money(s.total, s.currency, s.exponent),
        "state": s.state,
        "invoice_ref": s.invoice_ref,
        "created_at": rfc3339(s.created_at),
    }


# --- Monthly statements ------------------------------------------------------------------


def previous_month(now: datetime) -> tuple[str, datetime, datetime]:
    first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_last = first.replace(day=1)
    year, month = (first.year, first.month - 1) if first.month > 1 else (first.year - 1, 12)
    start = prev_last.replace(year=year, month=month)
    return f"{year:04d}-{month:02d}", start, first


def _pf2_invoice(db: Session, supplier: Supplier, lines: list[tuple[str, int, str]]) -> str | None:
    """PF2's billing interface, when it is merged (`create_invoice` on the
    Stripe provider). Returns the invoice id, or None to leave it pending."""
    if not supplier.billing_customer_id:
        return None
    try:
        from ..billing.base import InvoiceLine  # type: ignore[attr-defined]  (PF2)
        from ..billing.providers import get_provider  # type: ignore[attr-defined]  (PF2)
    except ImportError:
        return None
    provider = get_provider("stripe")
    if not provider.enabled():
        return None
    return provider.create_invoice(
        db,
        supplier.billing_customer_id,
        [InvoiceLine(description=d, amount_minor=a, currency=c.lower()) for d, a, c in lines],
    )


def run_statements(db: Session, now: datetime) -> list[CommissionStatement]:
    """One statement per supplier and currency for last month's accrued
    commissions and listing fee (idempotent: a month is stated once)."""
    month, start, end = previous_month(now)
    rows = db.scalars(
        select(Commission).where(
            Commission.state == "accrued",
            Commission.statement_id.is_(None),
            Commission.created_at < end,
        )
    )
    groups: dict[tuple[str, str], list[Commission]] = defaultdict(list)
    exponents: dict[str, int] = {}
    for c in rows:
        groups[(c.supplier_id, c.currency)].append(c)
        exponents[c.currency] = c.exponent
    # Listing fees of verified suppliers in each currency they sell in.
    for supplier in db.scalars(select(Supplier).where(Supplier.status == "verified")):
        currencies = set(
            db.scalars(select(SupplierRegion.currency).where(SupplierRegion.supplier_id == supplier.supplier_id))
        )
        for currency in currencies:
            if monthly_fee(supplier, currency):
                groups.setdefault((supplier.supplier_id, currency), [])
                exponents.setdefault(currency, 2)

    made = []
    for (supplier_id, currency), commissions in sorted(groups.items()):
        exists = db.scalar(
            select(CommissionStatement).where(
                CommissionStatement.supplier_id == supplier_id,
                CommissionStatement.month == month,
                CommissionStatement.currency == currency,
            )
        )
        if exists is not None:
            continue
        supplier = db.get(Supplier, supplier_id)
        if supplier is None:
            continue
        fee = monthly_fee(supplier, currency)
        total_commission = sum(c.amount for c in commissions)
        statement = CommissionStatement(
            statement_id=new_id(),
            supplier_id=supplier_id,
            month=month,
            currency=currency,
            exponent=exponents[currency],
            commission_total=total_commission,
            listing_fee=fee,
            total=total_commission + fee,
            orders=len({c.order_id for c in commissions}),
            state="pending",
        )
        db.add(statement)
        db.flush()
        lines = []
        if total_commission:
            lines.append((f"Marketplace commission, {month} ({statement.orders} orders)", total_commission, currency))
        if fee:
            lines.append((f"Listing fee, {month}", fee, currency))
        invoice = None
        if lines:
            try:
                invoice = _pf2_invoice(db, supplier, lines)
            except Exception:  # the provider failed: leave it pending, retried by hand
                log.exception("commission invoice failed for %s %s", supplier_id, month)
        for c in commissions:
            c.statement_id = statement.statement_id
            if invoice:
                c.state, c.invoice_ref = "invoiced", invoice
            db.add(c)
        if invoice:
            statement.state, statement.invoice_ref = "invoiced", invoice
        log.info(
            "statement %s %s %s: %s %s",
            supplier_id,
            month,
            statement.state,
            format_major(statement.total, statement.exponent),
            currency,
        )
        made.append(statement)
    db.commit()
    return made
