"""Provider-independent billing state: which plan a user has, and how paid
events change it.

Rules:
- A plan only changes from a provider event the server verified itself
  (a signed Stripe webhook, or a Wayl link status fetched from Wayl's API).
  The browser can never grant a plan.
- `users.plan` is a cache of `effective_plan`. "enterprise" is assigned by
  hand and is never overwritten here.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Payment, Subscription, User
from ..plans import plan_rank

# One Wayl payment buys this much Pro time.
WAYL_PERIOD = timedelta(days=30)

# Trials are subscriptions rows too (licence contract 5.6).
TRIAL_PROVIDER = "trial"


def _rank(sub: Subscription) -> tuple[int, int]:
    # Higher tier wins (ranks come from catalogue.json); on a tie a paid row
    # beats a trial, so a user who buys Pro mid-trial reads as a paid seat.
    return plan_rank(sub.plan), 0 if sub.provider == TRIAL_PROVIDER else 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    # SQLite hands back naive datetimes; everything we store is UTC.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_live(sub: Subscription, now: datetime | None = None) -> bool:
    if sub.status != "active":
        return False
    end = _aware(sub.current_period_end)
    return end is None or end > (now or _now())


def live_subscription(db: Session, user: User) -> Subscription | None:
    """The user's own best live subscription. An organisation's subscription
    (PF3, `organisation_id` set) is never its buyer's personal plan."""
    subs = db.scalars(
        select(Subscription).where(
            Subscription.user_id == user.id, Subscription.organisation_id.is_(None)
        )
    )
    best: Subscription | None = None
    for sub in subs:
        if is_live(sub) and (best is None or _rank(sub) > _rank(best)):
            best = sub
    return best


def effective_plan(db: Session, user: User) -> str:
    """The plan the user is entitled to right now (and sync the cache)."""
    if user.plan == "enterprise":
        return "enterprise"
    sub = live_subscription(db, user)
    plan = sub.plan if sub else "free"
    if user.plan != plan:
        user.plan = plan
        db.add(user)
        db.commit()
    return plan


def mark_payment_paid(db: Session, payment: Payment) -> bool:
    """Flip a payment to paid. Returns False if it already was (idempotent)."""
    if payment.status == "paid":
        return False
    payment.status = "paid"
    payment.paid_at = _now()
    db.add(payment)
    return True


def grant_wayl_period(db: Session, payment: Payment) -> None:
    """Credit one prepaid period for a paid Wayl payment (once per payment)."""
    if not mark_payment_paid(db, payment):
        db.commit()
        return
    sub = db.scalar(
        select(Subscription).where(
            Subscription.user_id == payment.user_id,
            Subscription.provider == "wayl",
            Subscription.plan == payment.plan,
        )
    )
    now = _now()
    if sub is None:
        sub = Subscription(
            user_id=payment.user_id,
            plan=payment.plan,
            provider="wayl",
            status="active",
            current_period_end=now + WAYL_PERIOD,
        )
    else:
        # Stack on top of time already paid for.
        start = max(now, _aware(sub.current_period_end) or now)
        sub.status = "active"
        sub.current_period_end = start + WAYL_PERIOD
    db.add(sub)
    db.commit()
    _refresh_cache(db, payment.user_id)


def upsert_stripe_subscription(
    db: Session,
    *,
    user_id: int,
    plan: str,
    stripe_subscription_id: str,
    stripe_customer_id: str | None,
    status: str,
    current_period_end: datetime | None,
) -> None:
    sub = db.scalar(
        select(Subscription).where(
            Subscription.provider == "stripe",
            Subscription.provider_subscription_id == stripe_subscription_id,
        )
    )
    if sub is None:
        sub = Subscription(
            user_id=user_id,
            plan=plan,
            provider="stripe",
            provider_subscription_id=stripe_subscription_id,
        )
    sub.status = status
    sub.current_period_end = current_period_end
    if stripe_customer_id:
        sub.provider_customer_id = stripe_customer_id
    db.add(sub)
    db.commit()
    _refresh_cache(db, user_id)


def stripe_customer_id(db: Session, user: User) -> str | None:
    """The Stripe customer id from the user's latest Stripe subscription."""
    sub = db.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.provider == "stripe",
            Subscription.provider_customer_id.is_not(None),
        )
        .order_by(Subscription.updated_at.desc())
    )
    return sub.provider_customer_id if sub else None


def _refresh_cache(db: Session, user_id: int) -> None:
    user = db.get(User, user_id)
    if user is not None:
        effective_plan(db, user)
