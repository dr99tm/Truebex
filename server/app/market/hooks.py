"""Marketplace events other features listen to (PF8: the suppliers' e-mails
and the daily analytics counts).

    @hooks.on("order.confirmed")
    def tell_suppliers(db, order): ...

    hooks.emit("order.confirmed", db, order=order)

The marketplace emits after its own commit, so a listener never undoes the
business change: a failing listener is logged and its writes rolled back.

Events: `supplier.status_changed` (supplier, old, new, reason),
`product.reviewed` (product, decision, note), `order.placed` (order),
`order.confirmed` (order: paid, or accepted to be paid off the platform),
`order.cancelled` (order, previous), `search.results` (product_ids, region),
`product.viewed` (product_id, region), `geometry.downloaded` (product_id,
region).
"""

import logging
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy.orm import Session

log = logging.getLogger("truebex.market")

Listener = Callable[..., object]
LISTENERS: dict[str, list[Listener]] = defaultdict(list)


def on(event: str) -> Callable[[Listener], Listener]:
    def register(fn: Listener) -> Listener:
        if fn not in LISTENERS[event]:
            LISTENERS[event].append(fn)
        return fn

    return register


def emit(event: str, db: Session, **data) -> None:
    for fn in list(LISTENERS.get(event, ())):
        try:
            fn(db, **data)
        except Exception:  # a listener must never fail the request that emitted
            log.exception("listener %s of %s failed", getattr(fn, "__name__", fn), event)
            db.rollback()
