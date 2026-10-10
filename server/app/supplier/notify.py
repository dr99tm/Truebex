"""The suppliers' e-mails (PF8 Scope 10), sent through `app.mail` (PF14
Plumbing; its `console` adapter prints them in the API console).

Listeners on the marketplace's events (`market.hooks`) plus the calls the
portal makes itself (application received, feed runs, invitations). Who gets
what: the supplier's contact address and its owners always; catalogue
e-mails also go to `catalogue` members, order e-mails to `orders` members.
A mail failure is logged and never fails the request.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import mail
from ..market import hooks
from ..market.common import format_major
from ..market.models import MarketOrder, MarketOrderLine, MarketOrderSupplier, Product, Supplier, SupplierMember
from ..models import User
from .common import portal_url

log = logging.getLogger("truebex.supplier")

CATALOGUE_MAIL = ("owner", "catalogue")
ORDER_MAIL = ("owner", "orders")


def recipients(db: Session, supplier: Supplier, roles: tuple[str, ...] = ("owner",)) -> list[str]:
    emails = db.scalars(
        select(User.email)
        .join(SupplierMember, SupplierMember.user_id == User.id)
        .where(SupplierMember.supplier_id == supplier.supplier_id, SupplierMember.role.in_(roles))
        .order_by(SupplierMember.id)
    )
    out: list[str] = []
    for email in [supplier.contact_email, *emails]:
        if email and email.lower() not in {e.lower() for e in out}:
            out.append(email)
    return out


def send(to: list[str] | str, template: str, data: dict) -> int:
    """Send one template to each address; returns how many were sent."""
    sent = 0
    for address in [to] if isinstance(to, str) else to:
        try:
            mail.send_mail(address, template, data)
        except Exception:  # noqa: BLE001 - a mail outage never fails the request
            log.exception("mail %s to %s failed", template, address)
            continue
        sent += 1
    return sent


# --- Orders and requests ------------------------------------------------------------------


def _ref(order: MarketOrder) -> str:
    return order.order_id[:8].upper()


def _lines_text(db: Session, order: MarketOrder, supplier_id: str) -> tuple[str, int]:
    lines = db.scalars(
        select(MarketOrderLine)
        .where(MarketOrderLine.order_id == order.order_id, MarketOrderLine.supplier_id == supplier_id)
        .order_by(MarketOrderLine.id)
    )
    out, n = [], 0
    for ln in lines:
        unit = ln.quoted_unit_amount if ln.quoted_unit_amount is not None else ln.unit_amount
        out.append(f"{ln.qty} x {ln.name} ({ln.sku} / {ln.variant_id}), {order.currency} {format_major(unit, order.exponent)} each")
        n += 1
    return "\n".join(out), n


def _delivery(order: MarketOrder) -> str:
    d = order.delivery or {}
    return ", ".join(p for p in (d.get("city"), d.get("postcode"), d.get("country")) if p) or order.region


def _groups(db: Session, order: MarketOrder) -> list[tuple[MarketOrderSupplier, Supplier]]:
    return list(
        db.execute(
            select(MarketOrderSupplier, Supplier)
            .join(Supplier, Supplier.supplier_id == MarketOrderSupplier.supplier_id)
            .where(MarketOrderSupplier.order_id == order.order_id)
            .order_by(MarketOrderSupplier.id)
        ).tuples()
    )


@hooks.on("order.placed")
def quote_requested(db: Session, order: MarketOrder) -> None:
    if order.kind != "quote":
        return  # an order reaches the suppliers once it is paid (order.confirmed)
    contact = order.contact or {}
    for group, supplier in _groups(db, order):
        lines, _ = _lines_text(db, order, supplier.supplier_id)
        send(
            recipients(db, supplier, ORDER_MAIL),
            "supplier_quote_request",
            {
                "supplier_name": supplier.name,
                "buyer_name": contact.get("name") or "A Truebex user",
                "order_ref": _ref(order),
                "delivery": _delivery(order),
                "lines": lines,
                "message": contact.get("message") or "(none)",
                "inbox_url": portal_url(f"inbox/?order={order.order_id}"),
            },
        )


@hooks.on("order.confirmed")
def order_confirmed(db: Session, order: MarketOrder) -> None:
    for group, supplier in _groups(db, order):
        if group.state in ("cancelled", "rejected"):
            continue
        lines, _ = _lines_text(db, order, supplier.supplier_id)
        send(
            recipients(db, supplier, ORDER_MAIL),
            "supplier_new_order",
            {
                "supplier_name": supplier.name,
                "order_ref": _ref(order),
                "payment": "paid on Truebex" if order.payment == "platform" else "you invoice the buyer",
                "delivery": _delivery(order),
                "lines": lines,
                "total": f"{order.currency} {format_major(group.total, order.exponent)}",
                "inbox_url": portal_url(f"inbox/?order={order.order_id}"),
            },
        )


@hooks.on("order.cancelled")
def order_cancelled(db: Session, order: MarketOrder, previous: str) -> None:
    if order.kind == "order" and previous == "awaiting_payment":
        return  # never reached the suppliers
    for _group, supplier in _groups(db, order):
        send(
            recipients(db, supplier, ORDER_MAIL),
            "supplier_order_cancelled",
            {
                "supplier_name": supplier.name,
                "kind": "request for quote" if order.kind == "quote" else "order",
                "order_ref": _ref(order),
                "inbox_url": portal_url("inbox/"),
            },
        )


# --- Catalogue -------------------------------------------------------------------------------


@hooks.on("product.reviewed")
def product_reviewed(db: Session, product: Product, decision: str, note: str | None = None) -> None:
    supplier = db.get(Supplier, product.supplier_id)
    if supplier is None or decision not in ("approved", "rejected"):
        return
    send(
        recipients(db, supplier, CATALOGUE_MAIL),
        "supplier_product_approved" if decision == "approved" else "supplier_product_rejected",
        {
            "product_name": product.name,
            "sku": product.sku,
            "reason": note or "(no reason given)",
            "product_url": portal_url(f"catalogue/product/?id={product.product_id}"),
        },
    )


def feed_rejected(db: Session, supplier: Supplier, report: dict) -> None:
    errors = [
        f"row {e['row']}, {e['column']}: {e['code']} ({e.get('value') or 'empty'})" for e in (report.get("errors") or [])[:10]
    ]
    if report.get("rejected", 0) > len(report.get("errors") or []):
        errors.append("…")
    send(
        recipients(db, supplier, CATALOGUE_MAIL),
        "supplier_feed_rejected",
        {
            "supplier_name": supplier.name,
            "rejected": report.get("rejected", 0),
            "rows": report.get("rows", 0),
            "source": {"pull": "daily feed", "upload": "feed upload", "portal": "portal upload"}.get(
                report.get("source", ""), "import"
            ),
            "finished": report.get("finished_at") or "",
            "errors": "\n".join(errors),
            "imports_url": portal_url(f"imports/?run={report.get('feed_id', '')}"),
        },
    )


def feed_pull_failed(db: Session, supplier: Supplier, url: str, error: str) -> None:
    send(
        recipients(db, supplier, CATALOGUE_MAIL),
        "supplier_feed_pull_failed",
        {"supplier_name": supplier.name, "url": url, "error": error, "imports_url": portal_url("imports/")},
    )
