"""The marketplace's background jobs (registered with app.tasks; main.py and
tasks._load_jobs import this module). Each runs in its own DB session."""

from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..tasks import periodic
from . import checkout, commissions, embeddings, orders
from .models import VariantAvailability

STALE_AFTER = timedelta(days=7)


def _job(name: str, seconds: int) -> Callable:
    """Register `fn(db, now)` with app.tasks, which calls jobs as `fn(now)`:
    the job gets its own session and is committed when it returns."""

    def register(fn: Callable[[Session, datetime], int]) -> Callable[[Session, datetime], int]:
        def run(now: datetime) -> int:
            with SessionLocal() as db:
                n = fn(db, now)
                db.commit()
                return n

        periodic(name, seconds)(run)
        return fn

    return register


@_job("market.embeddings", 60)
def embed_new_products(db: Session, now: datetime) -> int:
    return embeddings.embed_pending(db)


@_job("market.quotes.expire", 24 * 3600)
def expire_quotes(db: Session, now: datetime) -> int:
    return orders.expire_quotes(db, now)


@_job("market.orders.unpaid", 3600)
def cancel_unpaid_orders(db: Session, now: datetime) -> int:
    return orders.cancel_unpaid(db, now)


@_job("market.transfers", 300)
def transfer_accepted_parts(db: Session, now: datetime) -> int:
    if not checkout.enabled():
        return 0
    return checkout.run_transfers(db, now)


# Daily, and idempotent: on the 1st (or the first run after it) last month's
# statements are made; later runs find them made.
@_job("market.commissions.invoice", 24 * 3600)
def monthly_statements(db: Session, now: datetime) -> int:
    return len(commissions.run_statements(db, now))


@_job("market.availability.stale", 24 * 3600)
def mark_stale_availability(db: Session, now: datetime) -> int:
    result = db.execute(
        update(VariantAvailability)
        .where(VariantAvailability.updated_at < now - STALE_AFTER, VariantAvailability.stale.is_(False))
        .values(stale=True)
    )
    return result.rowcount or 0
