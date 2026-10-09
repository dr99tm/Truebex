"""Billing jobs: founding holds and the daily reconcile (server/app/tasks.py)."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import or_, select

from ..database import SessionLocal
from ..models import Payment, Subscription
from ..tasks import periodic
from . import providers, service

log = logging.getLogger("truebex.billing.jobs")

# Webhooks missed while the API was down (the host PC is off at times until
# PF14) are covered by re-fetching what changed in this window.
RECONCILE_WINDOW = timedelta(hours=48)


@periodic("billing.founding.expire", 300)
def expire_founding(now: datetime) -> int:
    """Release founding seats held by checkouts abandoned for 30 minutes."""
    with SessionLocal() as db:
        return service.expire_founding_holds(db, now)


@periodic("billing.reconcile", 24 * 3600)
def reconcile(now: datetime) -> int:
    """Re-fetch pending checkouts of the last 48 h and every subscription that
    is not long cancelled, from each enabled provider, and apply what the
    provider says."""
    since = now - RECONCILE_WINDOW
    checked = 0
    with SessionLocal() as db:
        for name in providers.ORDER:
            adapter = providers.get_provider(name)
            if not adapter.enabled():
                continue
            payments = list(
                db.scalars(
                    select(Payment).where(
                        Payment.provider == name,
                        Payment.status == "pending",
                        Payment.provider_ref.is_not(None),
                        Payment.created_at >= since,
                    )
                )
            )
            subs = list(
                db.scalars(
                    select(Subscription).where(
                        Subscription.provider == name,
                        Subscription.provider_subscription_id.is_not(None),
                        or_(Subscription.status != "canceled", Subscription.updated_at >= since),
                    )
                )
            )
            try:
                checked += adapter.reconcile(db, subs, payments)
            except Exception:
                log.exception("reconcile failed (%s)", name)
    return checked
