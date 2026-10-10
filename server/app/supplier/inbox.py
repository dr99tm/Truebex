"""The leads and orders inbox (PF8 Scope 5): requests for quote answered
with quoted prices and a message; orders accepted or rejected, then shipped
(carrier and reference) and delivered. State changes are PF7's
(`orders.supplier_*`, contract §5.7–5.10).

A supplier sees only its own part of each request or order: its lines, its
totals and the buyer's contact. Orders still awaiting payment are not
shown (the buyer has not paid; nothing to do yet).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..market import orders
from ..market.common import is_hex32, money, not_found, parse_major, rfc3339
from ..market.models import MarketOrder, MarketOrderLine, MarketOrderSupplier, Supplier
from ..market.schemas import SupplierQuoteIn
from .schemas import InboxQuoteIn

OPEN_STATES = {"quote": ("submitted",), "order": ("pending", "accepted", "shipped")}
HIDDEN_ORDER_STATES = ("awaiting_payment",)


def _item(db: Session, order: MarketOrder, group: MarketOrderSupplier, *, lines: list[MarketOrderLine] | None = None) -> dict:
    cur, exp = order.currency, order.exponent
    if lines is None:
        lines = list(
            db.scalars(
                select(MarketOrderLine)
                .where(MarketOrderLine.order_id == order.order_id, MarketOrderLine.supplier_id == group.supplier_id)
                .order_by(MarketOrderLine.id)
            )
        )

    def unit(amount: int | None) -> dict | None:
        return None if amount is None else money(amount, cur, exp)

    contact = order.contact or {}
    return {
        "order_id": order.order_id,
        "ref": order.order_id[:8].upper(),
        "kind": order.kind,
        "order_state": order.state,
        "state": group.state,
        "payment": order.payment,
        "region": order.region,
        "currency": cur,
        "exponent": exp,
        "project": {"name": (order.project or {}).get("name")},
        "buyer": {
            "name": contact.get("name"),
            "email": contact.get("email"),
            "phone": contact.get("phone"),
            "message": contact.get("message"),
        },
        "delivery": order.delivery or {},
        "lines": [
            {
                "product_id": ln.product_id,
                "sku": ln.sku,
                "variant_id": ln.variant_id,
                "name": ln.name,
                "qty": ln.qty,
                "unit": money(ln.unit_amount, cur, exp),
                "quoted_unit": unit(ln.quoted_unit_amount),
                "includes_tax": ln.includes_tax,
                "tax_rate_bp": ln.tax_rate_bp,
                "delivery_fee": unit(ln.delivery_fee),
            }
            for ln in lines
        ],
        "subtotal": money(group.subtotal, cur, exp),
        "delivery_fee": money(group.delivery, cur, exp),
        "tax": money(group.tax, cur, exp),
        "total": money(group.total, cur, exp),
        "delivery_days": {"min": group.delivery_days_min, "max": group.delivery_days_max},
        "quote": (
            {"quoted_at": rfc3339(group.quoted_at), "valid_until": rfc3339(group.quote_valid_until), "message": group.message}
            if group.quoted_at
            else None
        ),
        "shipment": {"carrier": group.carrier, "reference": group.tracking_ref} if group.carrier else None,
        "reason": group.reason,
        "expires_at": rfc3339(order.expires_at) if order.kind == "quote" else None,
        "created_at": rfc3339(order.created_at),
        "updated_at": rfc3339(group.updated_at),
        "open": group.state in OPEN_STATES.get(order.kind, ()),
    }


def list_items(db: Session, supplier: Supplier, kind: str | None, state: str | None, open_only: bool) -> dict:
    stmt = (
        select(MarketOrder, MarketOrderSupplier)
        .join(MarketOrderSupplier, MarketOrderSupplier.order_id == MarketOrder.order_id)
        .where(MarketOrderSupplier.supplier_id == supplier.supplier_id, MarketOrder.state.not_in(HIDDEN_ORDER_STATES))
        .order_by(MarketOrder.created_at.desc())
    )
    if kind in ("order", "quote"):
        stmt = stmt.where(MarketOrder.kind == kind)
    if state:
        stmt = stmt.where(MarketOrderSupplier.state == state)
    rows = list(db.execute(stmt.limit(300)).tuples())
    order_ids = [o.order_id for o, _ in rows]
    by_order: dict[str, list[MarketOrderLine]] = {}
    if order_ids:
        for ln in db.scalars(
            select(MarketOrderLine)
            .where(MarketOrderLine.order_id.in_(order_ids), MarketOrderLine.supplier_id == supplier.supplier_id)
            .order_by(MarketOrderLine.id)
        ):
            by_order.setdefault(ln.order_id, []).append(ln)
    items = [_item(db, o, g, lines=by_order.get(o.order_id, [])) for o, g in rows]
    if open_only:
        items = [i for i in items if i["open"]]
    return {"items": items, "open": open_counts(db, supplier)}


def open_counts(db: Session, supplier: Supplier) -> dict:
    rows = db.execute(
        select(MarketOrder.kind, MarketOrderSupplier.state)
        .join(MarketOrderSupplier, MarketOrderSupplier.order_id == MarketOrder.order_id)
        .where(MarketOrderSupplier.supplier_id == supplier.supplier_id, MarketOrder.state.not_in(HIDDEN_ORDER_STATES))
    ).all()
    return {
        "requests": sum(1 for kind, state in rows if kind == "quote" and state in OPEN_STATES["quote"]),
        "orders": sum(1 for kind, state in rows if kind == "order" and state in OPEN_STATES["order"]),
    }


def _get(db: Session, supplier: Supplier, order_id: str) -> tuple[MarketOrder, MarketOrderSupplier]:
    order = db.get(MarketOrder, order_id) if is_hex32(order_id) else None
    group = (
        db.scalar(
            select(MarketOrderSupplier).where(
                MarketOrderSupplier.order_id == order_id, MarketOrderSupplier.supplier_id == supplier.supplier_id
            )
        )
        if order
        else None
    )
    if order is None or group is None or order.state in HIDDEN_ORDER_STATES:
        raise not_found("That request or order")
    return order, group


def one(db: Session, supplier: Supplier, order_id: str) -> dict:
    order, group = _get(db, supplier, order_id)
    return _item(db, order, group)


def _after(db: Session, supplier: Supplier, order_id: str) -> dict:
    db.expire_all()
    return one(db, supplier, order_id)


def quote(db: Session, supplier: Supplier, order_id: str, body: InboxQuoteIn) -> dict:
    order, _group = _get(db, supplier, order_id)
    lines = []
    for n, q in enumerate(body.lines):
        try:
            lines.append({"sku": q.sku, "variant_id": q.variant_id, "unit_amount": parse_major(q.price, order.exponent)})
        except ValueError:
            raise ContractError(
                "validation_failed", 422, f"lines.{n}.price: bad_price ({order.currency} has {order.exponent} decimals)",
                {"fields": [{"field": f"lines.{n}.price", "in": "body", "message": "bad_price"}]},
            )  # fmt: skip
    fee = None
    if body.delivery_fee is not None and body.delivery_fee != "":
        try:
            fee = parse_major(body.delivery_fee, order.exponent)
        except ValueError:
            raise ContractError(
                "validation_failed", 422, "delivery_fee: bad_price",
                {"fields": [{"field": "delivery_fee", "in": "body", "message": "bad_price"}]},
            )  # fmt: skip
    if body.delivery_days_min is not None and body.delivery_days_max is not None and body.delivery_days_min > body.delivery_days_max:
        raise ContractError(
            "validation_failed", 422, "delivery_days_max: not before delivery_days_min",
            {"fields": [{"field": "delivery_days_max", "in": "body", "message": "not before delivery_days_min"}]},
        )  # fmt: skip
    orders.supplier_quote(
        db,
        order,
        supplier.supplier_id,
        SupplierQuoteIn(
            lines=lines,
            delivery_fee=fee,
            delivery_days_min=body.delivery_days_min,
            delivery_days_max=body.delivery_days_max,
            valid_days=body.valid_days,
            message=body.message,
        ),
    )
    return _after(db, supplier, order_id)


def act(db: Session, supplier: Supplier, order_id: str, action: str, *, reason: str | None = None, carrier: str | None = None, reference: str | None = None) -> dict:
    order, group = _get(db, supplier, order_id)
    sid = supplier.supplier_id
    if action == "accept":
        orders.supplier_accept(db, order, sid)
    elif action == "reject":
        orders.supplier_reject(db, order, sid, reason)
    elif action == "decline":
        orders.supplier_decline(db, order, sid, reason)
    elif action == "ship":
        orders.supplier_ship(db, order, sid)
        group = db.scalar(
            select(MarketOrderSupplier).where(MarketOrderSupplier.order_id == order_id, MarketOrderSupplier.supplier_id == sid)
        )
        group.carrier, group.tracking_ref = carrier, reference
        db.add(group)
        db.commit()
    elif action == "deliver":
        orders.supplier_deliver(db, order, sid)
    else:
        raise not_found("That action")
    return _after(db, supplier, order_id)
