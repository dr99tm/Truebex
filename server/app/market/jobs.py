"""The marketplace's background jobs (registered with app.tasks; main.py
imports this module). Each runs in its own DB session."""

from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..tasks import periodic
from . import checkout, commissions, embeddings, orders
from .models import VariantAvailability

STALE_AFTER = timedelta(days=7)


@periodic("market.embeddings", 60)
def embed_new_products(db: Session, now: datetime) -> int:
    return embeddings.embed_pending(db)


@periodic("market.quotes.expire", 24 * 3600)
def expire_quotes(db: Session, now: datetime) -> int:
    return orders.expire_quotes(db, now)


@periodic("market.orders.unpaid", 3600)
def cancel_unpaid_orders(db: Session, now: datetime) -> int:
    return orders.cancel_unpaid(db, now)


@periodic("market.transfers", 300)
def transfer_accepted_parts(db: Session, now: datetime) -> int:
    if not checkout.enabled():
        return 0
    return checkout.run_transfers(db, now)


# Daily, and idempotent: on the 1st (or the first run after it) last month's
# statements are made; later runs find them made.
@periodic("market.commissions.invoice", 24 * 3600)
def monthly_statements(db: Session, now: datetime) -> int:
    return len(commissions.run_statements(db, now))


@periodic("market.availability.stale", 24 * 3600)
def mark_stale_availability(db: Session, now: datetime) -> int:
    result = db.execute(
        update(VariantAvailability)
        .where(VariantAvailability.updated_at < now - STALE_AFTER, VariantAvailability.stale.is_(False))
        .values(stale=True)
    )
    return result.rowcount or 0
