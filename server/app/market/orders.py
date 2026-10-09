"""Orders and requests for quote (5.7–5.10) and the suppliers' answers.

* 5.7 prices every line again on the server; prices are never taken from
  the client. The checks run in this order: region (422
  `region_not_served`), availability and quote-only suppliers (409
  `unavailable`), then the buyer's `price_seen` (409 `price_changed`).
* An `order` is split per supplier, totalled in the region's currency and
  answers `awaiting_payment` with `checkout_url` (the platform's checkout
  page); a `quote` sends one lead per supplier and answers `submitted`.
* `Idempotency-Key` (32 hex, kept 24 h): the same key and body replay the
  first answer; the same key with another body is 409 `idempotency_mismatch`.
* States: order `awaiting_payment` → `paid` → per supplier `accepted` or
  `rejected` → `shipped` → `delivered`, or `cancelled`; the order's own state
  follows its suppliers. Quote `submitted` → `quoted` → `accepted` (an order
  is made from it) or `expired` 30 days after it was sent.
* Supplier answers (`supplier_quote`, `supplier_accept`, …) are called by
  PF8's inbox and, for now, by the admin pages.
"""

import base64
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..models import User
from .catalogue import payments_ready
from .common import aware, invalid, money, new_id, not_found, now, rfc3339, tax_on
from .models import (
    MarketOrder,
    MarketOrderLine,
    MarketOrderSupplier,
    MarketRegion,
    Product,
    ProductVariant,
    Supplier,
)
from .prices import Offer, availability_json, offers, price_json, region_or_invalid, state_of
from .schemas import OrderRequest, SupplierQuoteIn

IDEMPOTENCY_TTL = timedelta(hours=24)
QUOTE_TTL = timedelta(days=30)
UNPAID_TTL = timedelta(hours=48)

ORDER_STATES = ("awaiting_payment", "paid", "accepted", "shipped", "delivered", "rejected", "cancelled")
QUOTE_STATES = ("submitted", "quoted", "accepted", "expired", "cancelled")


def checkout_url(order: MarketOrder) -> str:
    return f"{get_settings().site_url.rstrip('/')}/market/checkout/?order={order.order_id}"


def request_hash(req: OrderRequest) -> str:
    raw = json.dumps(req.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


# --- Loading what the lines name ---------------------------------------------------------


class _Resolved:
    def __init__(self, line, product, supplier, variant, offer):
        self.line, self.product, self.supplier, self.variant, self.offer = line, product, supplier, variant, offer

    @property
    def ref(self) -> dict:
        return {"supplier_id": self.line.supplier_id, "sku": self.line.sku, "variant_id": self.line.variant_id}


def _resolve(db: Session, region: MarketRegion, lines) -> list[_Resolved]:
    supplier_ids = {ln.supplier_id for ln in lines}
    suppliers = {s.supplier_id: s for s in db.scalars(select(Supplier).where(Supplier.supplier_id.in_(supplier_ids)))}
    products = {
        (p.supplier_id, p.sku): p
        for p in db.scalars(
            select(Product).where(Product.supplier_id.in_(supplier_ids), Product.sku.in_({ln.sku for ln in lines}))
        )
    }
    pids = [p.product_id for p in products.values()]
    variants = {
        (v.product_id, v.variant_id): v
        for v in db.scalars(select(ProductVariant).where(ProductVariant.product_id.in_(pids)))
    } if pids else {}
    offs = offers(db, pids, region.region)
    out = []
    for ln in lines:
        product = products.get((ln.supplier_id, ln.sku))
        variant = variants.get((product.product_id, ln.variant_id)) if product else None
        offer = offs.get((product.product_id, ln.variant_id), Offer(None, None)) if product else Offer(None, None)
        out.append(_Resolved(ln, product, suppliers.get(ln.supplier_id), variant, offer))
    return out


def _why_unavailable(r: _Resolved, kind: str) -> str | None:
    if r.product is None or r.variant is None:
        return "not_found"
    if r.product.status != "approved" or r.supplier is None or r.supplier.status != "verified" or r.variant.status == "hidden":
        return "withdrawn"
    state = state_of(r.variant, r.offer.availability)
    if state == "discontinued":
        return "discontinued"
    if state == "out_of_stock" and kind == "order":
        return "out_of_stock"  # a request for quote may still ask for a lead time
    return None


# --- 5.7 -----------------------------------------------------------------------------------


def find_replay(db: Session, user: User, key: str, at: datetime) -> MarketOrder | None:
    return db.scalar(
        select(MarketOrder)
        .where(
            MarketOrder.user_id == user.id,
            MarketOrder.idempotency_key == key,
            MarketOrder.created_at >= at - IDEMPOTENCY_TTL,
        )
        .order_by(MarketOrder.created_at.desc())
    )


def place(
    db: Session, user: User, device_id: str | None, req: OrderRequest, idempotency_key: str | None
) -> tuple[MarketOrder, bool]:
    """Create an order or a request. Returns (order, replayed)."""
    at = now()
    digest = request_hash(req)
    if idempotency_key:
        first = find_replay(db, user, idempotency_key, at)
        if first is not None:
            if first.request_hash != digest:
                raise ContractError(
                    "idempotency_mismatch",
                    409,
                    "This Idempotency-Key was used for a different request. Send a new key.",
                )
            return first, True

    region = region_or_invalid(db, req.region, where="body")
    if req.delivery.country.upper() != region.region.split("-")[0]:
        raise invalid("delivery.country", f"delivery must be in the order's region ({region.region})", "body")
    seen: set[tuple[str, str, str]] = set()
    for ln in req.lines:
        key = (ln.supplier_id, ln.sku, ln.variant_id)
        if key in seen:
            raise invalid("lines", f"{ln.sku} / {ln.variant_id} is listed twice; send one line with its quantity", "body")
        seen.add(key)

    resolved = _resolve(db, region, req.lines)

    # 1. Unknown or withdrawn lines, and suppliers that do not deliver there.
    unavailable = [(r, why) for r in resolved if (why := _why_unavailable(r, req.kind))]
    not_served = [r for r in resolved if r not in [u for u, _ in unavailable] and r.offer.price is None]
    if not_served:
        names = {r.supplier.supplier_id: r.supplier.name for r in not_served}
        raise ContractError(
            "region_not_served",
            422,
            f"{', '.join(sorted(names.values()))} does not deliver to {region.name}.",
            {
                "region": region.region,
                "suppliers": [{"supplier_id": k, "name": v} for k, v in sorted(names.items())],
                "lines": [r.ref for r in not_served],
            },
        )
    if unavailable:
        raise ContractError(
            "unavailable",
            409,
            "Some products are no longer available.",
            {
                "reason": "unavailable",
                "lines": [
                    {
                        **r.ref,
                        "reason": why,
                        "availability": availability_json(r.variant, r.offer.availability) if r.variant else None,
                    }
                    for r, why in unavailable
                ],
            },
        )
    # 2. Quote-only suppliers (payments off, or not onboarded to Connect).
    if req.kind == "order":
        quote_only = [r for r in resolved if not payments_ready(r.supplier)]
        if quote_only:
            raise ContractError(
                "unavailable",
                409,
                "These suppliers take requests for quote only for now. Send a request for quote instead.",
                {
                    "reason": "quote_only",
                    "suppliers": sorted({r.supplier.supplier_id for r in quote_only}),
                    "lines": [{**r.ref, "reason": "quote_only"} for r in quote_only],
                },
            )
    # 3. Prices the buyer saw.
    changed = [
        r
        for r in resolved
        if r.line.price_seen is not None
        and (
            r.line.price_seen.amount != r.offer.price.amount
            or r.line.price_seen.currency.upper() != r.offer.price.currency
        )
    ]
    if changed:
        raise ContractError(
            "price_changed",
            409,
            "Prices changed since you added these products.",
            {
                "lines": [
                    {**r.ref, "price": price_json(r.offer.price), "price_seen": r.line.price_seen.model_dump()}
                    for r in changed
                ]
            },
        )

    order = MarketOrder(
        order_id=new_id(),
        user_id=user.id,
        device_id=device_id,
        kind=req.kind,
        state="submitted" if req.kind == "quote" else "awaiting_payment",
        region=region.region,
        currency=region.currency,
        exponent=region.exponent,
        project=req.project.model_dump(),
        project_uid=req.project.project_uid,
        contact=req.contact.model_dump(mode="json"),
        delivery={**req.delivery.model_dump(), "country": req.delivery.country.upper()},
        expires_at=at + QUOTE_TTL if req.kind == "quote" else None,
        idempotency_key=idempotency_key,
        request_hash=digest,
        created_at=at,
    )
    db.add(order)
    by_supplier: dict[str, list[_Resolved]] = defaultdict(list)
    for r in resolved:
        by_supplier[r.supplier.supplier_id].append(r)
        p = r.offer.price
        db.add(
            MarketOrderLine(
                order_id=order.order_id,
                supplier_id=r.supplier.supplier_id,
                product_id=r.product.product_id,
                sku=r.product.sku,
                variant_id=r.variant.variant_id,
                name=r.product.name,
                qty=r.line.qty,
                unit_amount=p.amount,
                includes_tax=p.includes_tax,
                tax_rate_bp=p.tax_rate_bp,
                price_at=p.updated_at,
                delivery_fee=p.delivery_fee,
                delivery_days_min=p.delivery_days_min,
                delivery_days_max=p.delivery_days_max,
            )
        )
    for supplier_id in by_supplier:
        db.add(
            MarketOrderSupplier(
                order_id=order.order_id,
                supplier_id=supplier_id,
                state="submitted" if req.kind == "quote" else "pending",
            )
        )
    db.flush()
    retotal(db, order, region)
    db.commit()
    return order, False


# --- Totals ------------------------------------------------------------------------------


def _lines(db: Session, order_id: str) -> list[MarketOrderLine]:
    return list(db.scalars(select(MarketOrderLine).where(MarketOrderLine.order_id == order_id).order_by(MarketOrderLine.id)))


def _groups(db: Session, order_id: str) -> list[MarketOrderSupplier]:
    return list(
        db.scalars(select(MarketOrderSupplier).where(MarketOrderSupplier.order_id == order_id).order_by(MarketOrderSupplier.id))
    )


def unit_of(line: MarketOrderLine) -> int:
    return line.quoted_unit_amount if line.quoted_unit_amount is not None else line.unit_amount


def retotal(db: Session, order: MarketOrder, region: MarketRegion | None = None) -> None:
    """Group and order totals from the lines (quoted prices when quoted).
    Delivery is one fee per supplier: the largest of its lines' fees, unless
    the supplier quoted its own. Tax is what the subtotal and delivery
    contain (tax-inclusive prices) or add (tax-exclusive)."""
    region = region or db.get(MarketRegion, order.region)
    rate = region.tax_rate_bp if region else 0
    inclusive = region.prices_include_tax if region else True
    lines = _lines(db, order.order_id)
    order.subtotal = order.delivery_total = order.tax_total = order.total = 0
    for g in _groups(db, order.order_id):
        mine = [ln for ln in lines if ln.supplier_id == g.supplier_id]
        g.lines = len(mine)
        g.subtotal = sum(unit_of(ln) * ln.qty for ln in mine)
        if g.quoted_at is None:
            g.delivery = max((ln.delivery_fee or 0 for ln in mine), default=0)
            mins = [ln.delivery_days_min for ln in mine if ln.delivery_days_min is not None]
            maxs = [ln.delivery_days_max for ln in mine if ln.delivery_days_max is not None]
            g.delivery_days_min = max(mins) if mins else None
            g.delivery_days_max = max(maxs) if maxs else None
        goods_tax = sum(tax_on(unit_of(ln) * ln.qty, ln.tax_rate_bp, ln.includes_tax) for ln in mine)
        added = sum(tax_on(unit_of(ln) * ln.qty, ln.tax_rate_bp, False) for ln in mine if not ln.includes_tax)
        g.tax = goods_tax + tax_on(g.delivery, rate, inclusive)
        g.total = g.subtotal + g.delivery + added + (0 if inclusive else tax_on(g.delivery, rate, False))
        db.add(g)
        order.subtotal += g.subtotal
        order.delivery_total += g.delivery
        order.tax_total += g.tax
        order.total += g.total
    order.updated_at = now()
    db.add(order)


# --- Reading ------------------------------------------------------------------------------


def order_json(db: Session, order: MarketOrder, *, include_contact: bool = True) -> dict:
    cur, exp = order.currency, order.exponent
    suppliers = {
        s.supplier_id: s
        for s in db.scalars(
            select(Supplier).where(Supplier.supplier_id.in_([g.supplier_id for g in _groups(db, order.order_id)]))
        )
    }
    lines = _lines(db, order.order_id)
    groups = []
    for g in _groups(db, order.order_id):
        s = suppliers.get(g.supplier_id)
        groups.append(
            {
                "supplier_id": g.supplier_id,
                "supplier_name": s.name if s else None,
                "state": g.state,
                "lines": g.lines,
                "subtotal": money(g.subtotal, cur, exp),
                "delivery": money(g.delivery, cur, exp),
                "tax": money(g.tax, cur, exp),
                "total": money(g.total, cur, exp),
                "delivery_days": {"min": g.delivery_days_min, "max": g.delivery_days_max},
                "quote": (
                    {"quoted_at": rfc3339(g.quoted_at), "valid_until": rfc3339(g.quote_valid_until), "message": g.message}
                    if g.quoted_at
                    else None
                ),
                "reason": g.reason,
            }
        )

    def unit(ln: MarketOrderLine, amount: int) -> dict:
        return {
            "amount": amount,
            "currency": cur,
            "exponent": exp,
            "region": order.region,
            "includes_tax": ln.includes_tax,
            "tax_rate_bp": ln.tax_rate_bp,
            "at": rfc3339(ln.price_at),
        }

    out = {
        "order_id": order.order_id,
        "kind": order.kind,
        "state": order.state,
        "payment": order.payment,
        "region": order.region,
        "currency": cur,
        "exponent": exp,
        "checkout_url": checkout_url(order) if order.state == "awaiting_payment" else None,
        "project": order.project or {},
        "delivery": order.delivery or {},
        "suppliers": groups,
        "lines": [
            {
                "supplier_id": ln.supplier_id,
                "product_id": ln.product_id,
                "sku": ln.sku,
                "variant_id": ln.variant_id,
                "name": ln.name,
                "qty": ln.qty,
                "price": unit(ln, ln.unit_amount),
                "quoted_price": unit(ln, ln.quoted_unit_amount) if ln.quoted_unit_amount is not None else None,
                "total": money(unit_of(ln) * ln.qty, cur, exp),
            }
            for ln in lines
        ],
        "subtotal": money(order.subtotal, cur, exp),
        "delivery_total": money(order.delivery_total, cur, exp),
        "tax": money(order.tax_total, cur, exp),
        "total": money(order.total, cur, exp),
        "quote_id": order.quote_id,
        "order_ref": order.accepted_order_id,
        "expires_at": rfc3339(order.expires_at) if order.kind == "quote" else None,
        "paid_at": rfc3339(order.paid_at),
        "created_at": rfc3339(order.created_at),
        "updated_at": rfc3339(order.updated_at),
    }
    if include_contact:
        out["contact"] = order.contact or {}
    return out


def get_owned(db: Session, user: User, order_id: str) -> MarketOrder:
    order = db.get(MarketOrder, order_id) if isinstance(order_id, str) else None
    if order is None:
        raise not_found("That order")
    if order.user_id != user.id:
        raise ContractError("forbidden", 403, "That order belongs to another account.")
    return order


def _encode(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).rstrip(b"=").decode()


def _decode(cursor: str) -> int:
    try:
        return max(0, int(json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))["o"]))
    except (ValueError, KeyError, TypeError):
        raise invalid("cursor", "not a cursor this list returned")


def list_orders(
    db: Session, user: User, *, state: str | None, cursor: str | None, project_uid: str | None, limit: int = 50
) -> dict:
    if state is not None and state not in set(ORDER_STATES) | set(QUOTE_STATES):
        raise invalid("state", "an order or quote state of contract 5.7–5.10")
    stmt = select(MarketOrder).where(MarketOrder.user_id == user.id)
    if state:
        stmt = stmt.where(MarketOrder.state == state)
    if project_uid:
        stmt = stmt.where(MarketOrder.project_uid == project_uid)
    offset = _decode(cursor) if cursor else 0
    rows = list(
        db.scalars(stmt.order_by(MarketOrder.created_at.desc(), MarketOrder.order_id).offset(offset).limit(limit + 1))
    )
    return {
        "orders": [order_json(db, o) for o in rows[:limit]],
        "next_cursor": _encode(offset + limit) if len(rows) > limit else None,
    }


# --- State changes -------------------------------------------------------------------------


def derive_state(db: Session, order: MarketOrder) -> str:
    """The order's own state from its suppliers' (after payment, or for an
    accepted quote paid off the platform)."""
    groups = _groups(db, order.order_id)
    if order.kind == "quote":
        if order.state not in ("submitted", "quoted"):
            return order.state
        states = {g.state for g in groups}
        if "quoted" in states:
            return "quoted"
        if states and states <= {"declined", "expired", "cancelled"}:
            return "expired"
        return "submitted"
    if order.state in ("awaiting_payment", "cancelled"):
        return order.state
    live = [g for g in groups if g.state not in ("rejected", "cancelled")]
    if not live:
        return "rejected" if any(g.state == "rejected" for g in groups) else "cancelled"
    states = [g.state for g in live]
    if all(s == "delivered" for s in states):
        return "delivered"
    if all(s in ("shipped", "delivered") for s in states):
        return "shipped"
    if all(s in ("accepted", "shipped", "delivered") for s in states):
        return "accepted"
    return "paid"


def _touch(db: Session, order: MarketOrder) -> None:
    order.state = derive_state(db, order)
    order.updated_at = now()
    db.add(order)


def cancel(db: Session, order: MarketOrder) -> MarketOrder:
    """5.10: before any supplier accepts. A paid order is refunded in full."""
    if order.state == "cancelled":
        return order
    groups = _groups(db, order.order_id)
    if order.kind == "quote":
        if order.state not in ("submitted", "quoted"):
            raise ContractError("not_cancellable", 409, f"This request is {order.state} and can no longer be cancelled.")
    elif order.state not in ("awaiting_payment", "paid") or any(g.state != "pending" for g in groups):
        raise ContractError(
            "not_cancellable", 409, "A supplier has already accepted this order, so it can no longer be cancelled here."
        )
    if order.kind == "order" and order.state == "paid":
        from . import checkout

        checkout.refund_order(db, order)
    at = now()
    for g in groups:
        g.state = "cancelled"
        db.add(g)
    order.state = "cancelled"
    order.cancelled_at = order.updated_at = at
    db.add(order)
    db.commit()
    return order


def mark_paid(db: Session, order: MarketOrder, payment_intent: str | None) -> bool:
    """Called only from a verified Stripe event or a server-side retrieval."""
    if order.state != "awaiting_payment":
        return False
    order.state = "paid"
    order.paid_at = order.updated_at = now()
    order.payment_intent = payment_intent or order.payment_intent
    db.add(order)
    db.commit()
    return True


def accept_quote(db: Session, quote: MarketOrder) -> MarketOrder:
    """The buyer accepts the quoted suppliers' prices: an order is made from
    them. It is paid on the checkout page when payments are on and every
    supplier in it is onboarded; otherwise it is `accepted` and paid off the
    platform (each supplier invoices the buyer itself: GD1 Phase A)."""
    if quote.kind != "quote" or quote.state != "quoted":
        raise ContractError("not_acceptable", 409, f"Only a quoted request can be accepted; this one is {quote.state}.")
    at = now()
    groups = [g for g in _groups(db, quote.order_id) if g.state == "quoted"]
    valid = [g for g in groups if g.quote_valid_until is None or aware(g.quote_valid_until) >= at]
    if not valid:
        raise ContractError("not_acceptable", 409, "These quotes have expired. Send a new request.")
    suppliers = {s.supplier_id: s for s in db.scalars(select(Supplier).where(Supplier.supplier_id.in_([g.supplier_id for g in valid])))}
    platform = all(payments_ready(s) for s in suppliers.values())
    order = MarketOrder(
        order_id=new_id(),
        user_id=quote.user_id,
        device_id=quote.device_id,
        kind="order",
        state="awaiting_payment" if platform else "accepted",
        payment="platform" if platform else "offline",
        region=quote.region,
        currency=quote.currency,
        exponent=quote.exponent,
        project=quote.project,
        project_uid=quote.project_uid,
        contact=quote.contact,
        delivery=quote.delivery,
        quote_id=quote.order_id,
        created_at=at,
    )
    db.add(order)
    keep = {g.supplier_id for g in valid}
    for ln in _lines(db, quote.order_id):
        if ln.supplier_id not in keep:
            continue
        db.add(
            MarketOrderLine(
                order_id=order.order_id,
                supplier_id=ln.supplier_id,
                product_id=ln.product_id,
                sku=ln.sku,
                variant_id=ln.variant_id,
                name=ln.name,
                qty=ln.qty,
                unit_amount=ln.unit_amount,
                includes_tax=ln.includes_tax,
                tax_rate_bp=ln.tax_rate_bp,
                price_at=ln.price_at,
                quoted_unit_amount=unit_of(ln),
                delivery_fee=ln.delivery_fee,
                delivery_days_min=ln.delivery_days_min,
                delivery_days_max=ln.delivery_days_max,
            )
        )
    for g in _groups(db, quote.order_id):
        if g.supplier_id in keep:
            db.add(
                MarketOrderSupplier(
                    order_id=order.order_id,
                    supplier_id=g.supplier_id,
                    state="pending" if platform else "accepted",
                    accepted_at=None if platform else at,
                    delivery=g.delivery,
                    delivery_days_min=g.delivery_days_min,
                    delivery_days_max=g.delivery_days_max,
                    quoted_at=g.quoted_at,
                    quote_valid_until=g.quote_valid_until,
                    message=g.message,
                )
            )
            g.state = "accepted"
        elif g.state in ("submitted", "quoted"):
            g.state = "cancelled"
        db.add(g)
    db.flush()
    retotal(db, order)
    quote.state = "accepted"
    quote.accepted_order_id = order.order_id
    quote.updated_at = at
    db.add(quote)
    db.commit()
    return order


# --- Supplier answers (PF8's inbox; admin acts for a supplier until then) ------------------


def group_of(db: Session, order: MarketOrder, supplier_id: str) -> MarketOrderSupplier:
    g = db.scalar(
        select(MarketOrderSupplier).where(
            MarketOrderSupplier.order_id == order.order_id, MarketOrderSupplier.supplier_id == supplier_id
        )
    )
    if g is None:
        raise not_found("That supplier's part of the order")
    return g


def _wrong_state(g: MarketOrderSupplier, action: str) -> ContractError:
    return ContractError("conflict", 409, f"Cannot {action}: this part is {g.state}.")


def supplier_quote(db: Session, order: MarketOrder, supplier_id: str, body: SupplierQuoteIn) -> MarketOrder:
    if order.kind != "quote" or order.state not in ("submitted", "quoted"):
        raise ContractError("conflict", 409, f"Only an open request can be quoted; this one is {order.state}.")
    g = group_of(db, order, supplier_id)
    if g.state not in ("submitted", "quoted"):
        raise _wrong_state(g, "quote")
    at = now()
    mine = {(ln.sku, ln.variant_id): ln for ln in _lines(db, order.order_id) if ln.supplier_id == supplier_id}
    for q in body.lines:
        ln = mine.get((q.sku, q.variant_id))
        if ln is None:
            raise invalid("lines", f"{q.sku} / {q.variant_id} is not in this request", "body")
        ln.quoted_unit_amount = q.unit_amount
        db.add(ln)
    for ln in mine.values():
        if ln.quoted_unit_amount is None:
            ln.quoted_unit_amount = ln.unit_amount
            db.add(ln)
    if body.delivery_fee is not None:
        g.delivery = body.delivery_fee
    else:
        g.delivery = max((ln.delivery_fee or 0 for ln in mine.values()), default=0)
    if body.delivery_days_min is not None:
        g.delivery_days_min = body.delivery_days_min
    if body.delivery_days_max is not None:
        g.delivery_days_max = body.delivery_days_max
    g.quoted_at = at
    expires = aware(order.expires_at) if order.expires_at else at + QUOTE_TTL
    g.quote_valid_until = min(at + timedelta(days=body.valid_days), expires)
    g.message = body.message
    g.state = "quoted"
    db.add(g)
    db.flush()
    retotal(db, order)
    _touch(db, order)
    db.commit()
    return order


def supplier_decline(db: Session, order: MarketOrder, supplier_id: str, reason: str | None) -> MarketOrder:
    g = group_of(db, order, supplier_id)
    if order.kind != "quote" or g.state not in ("submitted", "quoted"):
        raise _wrong_state(g, "decline")
    g.state, g.reason = "declined", reason
    db.add(g)
    _touch(db, order)
    db.commit()
    return order


def supplier_accept(db: Session, order: MarketOrder, supplier_id: str) -> MarketOrder:
    g = group_of(db, order, supplier_id)
    if order.kind != "order" or order.state not in ("paid", "accepted", "shipped") or g.state != "pending":
        raise _wrong_state(g, "accept")
    g.state, g.accepted_at = "accepted", now()
    db.add(g)
    _touch(db, order)
    db.commit()
    return order


def supplier_reject(db: Session, order: MarketOrder, supplier_id: str, reason: str | None) -> MarketOrder:
    """A paid part the supplier cannot fulfil is refunded to the buyer."""
    g = group_of(db, order, supplier_id)
    if order.kind != "order" or g.state != "pending" or order.state == "awaiting_payment":
        raise _wrong_state(g, "reject")
    if order.payment == "platform" and order.payment_intent:
        from . import checkout

        checkout.refund_part(db, order, g)
    g.state, g.reason = "rejected", reason
    db.add(g)
    _touch(db, order)
    db.commit()
    return order


def supplier_ship(db: Session, order: MarketOrder, supplier_id: str) -> MarketOrder:
    g = group_of(db, order, supplier_id)
    if g.state != "accepted":
        raise _wrong_state(g, "mark as shipped")
    g.state, g.shipped_at = "shipped", now()
    db.add(g)
    _touch(db, order)
    db.commit()
    return order


def supplier_deliver(db: Session, order: MarketOrder, supplier_id: str) -> MarketOrder:
    g = group_of(db, order, supplier_id)
    if g.state not in ("accepted", "shipped"):
        raise _wrong_state(g, "mark as delivered")
    at = now()
    g.shipped_at = g.shipped_at or at
    g.state, g.delivered_at = "delivered", at
    db.add(g)
    _touch(db, order)
    db.commit()
    return order


# --- Jobs ------------------------------------------------------------------------------------


def expire_quotes(db: Session, at: datetime) -> int:
    """`submitted` or `quoted` requests 30 days old → `expired`."""
    n = 0
    for order in db.scalars(
        select(MarketOrder).where(
            MarketOrder.kind == "quote",
            MarketOrder.state.in_(("submitted", "quoted")),
            MarketOrder.created_at <= at - QUOTE_TTL,
        )
    ):
        for g in _groups(db, order.order_id):
            if g.state in ("submitted", "quoted"):
                g.state = "expired"
                db.add(g)
        order.state, order.updated_at = "expired", at
        db.add(order)
        n += 1
    return n


def cancel_unpaid(db: Session, at: datetime) -> int:
    """`awaiting_payment` orders 48 hours old → `cancelled`."""
    n = 0
    for order in db.scalars(
        select(MarketOrder).where(
            MarketOrder.kind == "order",
            MarketOrder.state == "awaiting_payment",
            MarketOrder.created_at <= at - UNPAID_TTL,
        )
    ):
        for g in _groups(db, order.order_id):
            g.state = "cancelled"
            db.add(g)
        order.state, order.cancelled_at, order.updated_at = "cancelled", at, at
        db.add(order)
        n += 1
    return n
