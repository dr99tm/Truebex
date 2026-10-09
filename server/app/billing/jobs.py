"""Billing jobs (server/app/tasks.py): founding holds, the daily reconcile, and
PF2b's subscription notices and exit retries."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import or_, select

from ..database import SessionLocal
from ..models import Payment, Subscription
from ..tasks import periodic
from . import consumer, providers, service

log = logging.getLogger("truebex.billing.jobs")

# Webhooks missed while the API was down (the host PC is off at times until
# PF14) are covered by re-fetching what changed in this window.
RECONCILE_WINDOW = timedelta(hours=48)


@periodic("billing.founding.expire", 300)
def expire_founding(now: datetime) -> int:
    """Release founding places held by checkouts abandoned for 30 minutes, and
    cancel those checkouts so the founding price cannot be paid afterwards."""
    with SessionLocal() as db:
        for hold in service.expired_holds(db, now):
            payment = db.scalar(
                select(Payment).where(
                    Payment.reference == hold.reference, Payment.status == "pending"
                )
            )
            if payment is None:
                continue
            try:
                adapter = providers.get_provider(payment.provider)
                if adapter.enabled():
                    adapter.cancel_checkout(db, payment)
            except Exception:  # paid meanwhile, or the provider is down
                log.exception("could not cancel checkout %s", payment.reference)
                continue
            payment.status = "canceled"
            db.add(payment)
            db.commit()
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


# --- PF2b: subscription consumer rules ------------------------------------------------


@periodic("billing.subscription_notices", 3600)
def subscription_notices(now: datetime) -> int:
    """Renewal reminders before each renewal of a live paid subscription and
    the trial-end notice, once per period (subscription_notices). A no-op
    while SUBSCRIPTION_NOTICES_ENABLED is false or before
    SUBSCRIPTION_RULES_FROM."""
    if not consumer.dmcc_active(now):
        return 0
    with SessionLocal() as db:
        return consumer.send_due_notices(db, now)


@periodic("billing.exits.retry", 900)
def retry_exits(now: datetime) -> int:
    """Finish cancellations, cooling-off refunds and withdrawals whose
    provider call failed, so a customer's statement is never lost."""
    with SessionLocal() as db:
        return consumer.retry_exits(db, now)
