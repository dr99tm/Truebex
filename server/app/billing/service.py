"""Provider-independent billing state: which plan a user has, and how paid
events change it.

Rules:
- A plan, a seat count or a founding flag only changes from a provider event
  the server verified itself (a signed Paddle or Stripe webhook, or state
  fetched from the provider's API, as for a Wayl link). The browser can
  never grant a plan; it only names a tier, an interval, a currency and seats.
- Provider events are applied once (de-duplicated by event id) and in order:
  an event older than the newest one applied to a subscription changes
  nothing.
- `users.plan` is a cache of `effective_plan`. "enterprise" is assigned by
  hand and is never overwritten here.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    BillingEvent,
    FoundingReservation,
    Payment,
    ProviderPrice,
    Subscription,
    User,
)
from ..plans import FOUNDING, PLANS, rank

# One Wayl payment buys this much Pro time.
WAYL_PERIOD = timedelta(days=30)

# A founding seat is held this long for an open checkout.
FOUNDING_HOLD = timedelta(minutes=30)

# Providers whose subscriptions the customer manages (portal, seats, change).
MANAGED_PROVIDERS = ("paddle", "stripe")


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
    subs = db.scalars(select(Subscription).where(Subscription.user_id == user.id))
    best: Subscription | None = None
    for sub in subs:
        if is_live(sub) and (best is None or rank(sub.plan) > rank(best.plan)):
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


def managed_subscription(db: Session, user: User) -> Subscription | None:
    """The user's Paddle or Stripe subscription: the live one if any, else the
    most recently updated (a past-due card still needs the portal)."""
    subs = list(
        db.scalars(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.provider.in_(MANAGED_PROVIDERS),
            )
            .order_by(Subscription.updated_at.desc(), Subscription.id.desc())
        )
    )
    live = [s for s in subs if is_live(s)]
    if live:
        return max(live, key=lambda s: rank(s.plan))
    return subs[0] if subs else None


def customer_id(db: Session, user: User, provider: str) -> str | None:
    """The provider's customer id from the user's latest subscription there."""
    sub = db.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.provider == provider,
            Subscription.provider_customer_id.is_not(None),
        )
        .order_by(Subscription.updated_at.desc())
    )
    return sub.provider_customer_id if sub else None


def stripe_customer_id(db: Session, user: User) -> str | None:
    return customer_id(db, user, "stripe")


def seats_assigned(db: Session, sub: Subscription) -> int:
    """Seats of this subscription given to people. The buyer holds one until
    PF3's organisations assign the rest."""
    return 1


# --- Payments ------------------------------------------------------------------


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
            interval="month",
            currency=payment.currency,
            seats=1,
        )
    else:
        # Stack on top of time already paid for.
        start = max(now, _aware(sub.current_period_end) or now)
        sub.status = "active"
        sub.current_period_end = start + WAYL_PERIOD
    db.add(sub)
    db.commit()
    _refresh_cache(db, payment.user_id)


# --- Subscriptions -------------------------------------------------------------


def upsert_subscription(
    db: Session,
    *,
    provider: str,
    provider_subscription_id: str,
    user_id: int,
    tier: str,
    interval: str | None,
    seats: int,
    status: str,
    current_period_end: datetime | None,
    cancel_at_period_end: bool,
    customer_id: str | None = None,
    currency: str | None = None,
    provider_price_id: str | None = None,
    founding: bool | None = None,
    event_at: datetime | None = None,
) -> Subscription | None:
    """Mirror a provider subscription. Returns None (and changes nothing) when
    `event_at` is older than the newest state already applied."""
    sub = db.scalar(
        select(Subscription).where(
            Subscription.provider == provider,
            Subscription.provider_subscription_id == provider_subscription_id,
        )
    )
    event_at = _aware(event_at) or _now()
    if sub is not None:
        newest = _aware(sub.last_event_at)
        if newest is not None and event_at < newest:
            return None
        user_id = sub.user_id  # a subscription never changes hands
    else:
        sub = Subscription(
            user_id=user_id,
            plan=tier,
            provider=provider,
            provider_subscription_id=provider_subscription_id,
        )
    sub.plan = tier if tier in PLANS else "pro"
    sub.interval = interval
    sub.seats = max(1, int(seats or 1))
    sub.status = status
    sub.current_period_end = current_period_end
    sub.cancel_at_period_end = bool(cancel_at_period_end)
    sub.last_event_at = event_at
    if customer_id:
        sub.provider_customer_id = customer_id
    if currency:
        sub.currency = currency.upper()
    if provider_price_id:
        sub.provider_price_id = provider_price_id
    if founding is not None:
        sub.founding = founding
    db.add(sub)
    if is_live(sub):
        _end_trials(db, user_id)
    db.commit()
    _refresh_cache(db, user_id)
    return sub


def _end_trials(db: Session, user_id: int) -> None:
    """A purchase ends a running trial (licence contract 5.6: a paid plan
    answers 409 plan_active to a trial request)."""
    for trial in db.scalars(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.provider == "trial",
            Subscription.status == "active",
        )
    ):
        trial.status = "canceled"
        trial.current_period_end = _now()
        db.add(trial)


def _refresh_cache(db: Session, user_id: int) -> None:
    user = db.get(User, user_id)
    if user is not None:
        effective_plan(db, user)


# --- Provider prices -------------------------------------------------------------


def provider_price(
    db: Session, provider: str, tier: str, interval: str, currency: str, amount_minor: int
) -> ProviderPrice | None:
    """The active provider price for exactly this catalogue amount."""
    return db.scalar(
        select(ProviderPrice)
        .where(
            ProviderPrice.provider == provider,
            ProviderPrice.tier == tier,
            ProviderPrice.interval == interval,
            ProviderPrice.currency == currency.upper(),
            ProviderPrice.amount_minor == amount_minor,
            ProviderPrice.active.is_(True),
        )
        .order_by(ProviderPrice.id.desc())
    )


def price_by_provider_id(db: Session, provider: str, price_id: str | None) -> ProviderPrice | None:
    """Any row (active or not) for a provider price id: old prices keep mapping."""
    if not price_id:
        return None
    return db.scalar(
        select(ProviderPrice).where(
            ProviderPrice.provider == provider,
            ProviderPrice.provider_price_id == price_id,
        )
    )


# --- Events ----------------------------------------------------------------------


def event_seen(db: Session, provider: str, event_id: str) -> bool:
    return (
        db.scalar(
            select(BillingEvent.id).where(
                BillingEvent.provider == provider, BillingEvent.event_id == event_id
            )
        )
        is not None
    )


def record_event(
    db: Session,
    provider: str,
    event_id: str,
    type_: str,
    occurred_at: datetime | None,
    status: str,
) -> bool:
    """Store an applied event. False if another delivery stored it first."""
    db.add(
        BillingEvent(
            provider=provider,
            event_id=event_id,
            type=type_[:64],
            occurred_at=occurred_at,
            status=status,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


# --- The founding offer --------------------------------------------------------------


def _founding_open(now: datetime) -> bool:
    ends = FOUNDING.ends_at
    return FOUNDING.total > 0 and (ends is None or now < ends)


def founding_taken(db: Session, now: datetime | None = None) -> int:
    """Seats bought at the founding price plus seats held by open checkouts."""
    now = now or _now()
    bought = db.scalar(
        select(func.coalesce(func.sum(FoundingReservation.seats), 0)).where(
            FoundingReservation.consumed_at.is_not(None)
        )
    )
    held = db.scalar(
        select(func.coalesce(func.sum(FoundingReservation.seats), 0)).where(
            FoundingReservation.consumed_at.is_(None),
            FoundingReservation.expires_at > now,
        )
    )
    return int(bought or 0) + int(held or 0)


def founding_status(db: Session, now: datetime | None = None) -> dict:
    now = now or _now()
    remaining = max(0, FOUNDING.total - founding_taken(db, now)) if FOUNDING.total else 0
    return {
        "enabled": _founding_open(now) and remaining > 0,
        "total": FOUNDING.total,
        "remaining": remaining,
        "discount_percent": FOUNDING.discount_percent,
        "ends_at": FOUNDING.ends_at,
    }


def hold_founding(
    db: Session, user: User, reference: str, tier: str, seats: int, now: datetime | None = None
) -> bool:
    """Hold founding seats for one checkout. False when the offer is closed,
    does not cover the tier, or has fewer seats left than asked for."""
    now = now or _now()
    if tier not in FOUNDING.tiers or not _founding_open(now):
        return False
    # A new checkout replaces the user's earlier open holds.
    for old in db.scalars(
        select(FoundingReservation).where(
            FoundingReservation.user_id == user.id,
            FoundingReservation.consumed_at.is_(None),
        )
    ):
        db.delete(old)
    db.flush()
    if FOUNDING.total - founding_taken(db, now) < seats:
        db.commit()
        return False
    db.add(
        FoundingReservation(
            user_id=user.id,
            reference=reference,
            seats=seats,
            expires_at=now + FOUNDING_HOLD,
        )
    )
    db.commit()
    return True


def release_founding(db: Session, reference: str) -> None:
    """Give a hold back (the provider refused the checkout)."""
    hold = db.scalar(
        select(FoundingReservation).where(FoundingReservation.reference == reference)
    )
    if hold is not None and hold.consumed_at is None:
        db.delete(hold)
        db.commit()


def consume_founding(db: Session, payment: Payment, founding_hint: bool = False) -> bool:
    """A founding checkout was paid: its seats are sold for good. A hold that
    expired (or was released) is counted anyway when the provider's own record
    of the checkout, which our server wrote, says it was a founding one."""
    hold = db.scalar(
        select(FoundingReservation).where(FoundingReservation.reference == payment.reference)
    )
    if hold is None:
        if not founding_hint:
            return False
        hold = FoundingReservation(
            user_id=payment.user_id,
            reference=payment.reference,
            seats=payment.seats or 1,
            expires_at=_now(),
        )
    if hold.consumed_at is None:
        hold.consumed_at = _now()
        db.add(hold)
        db.commit()
    return True


def is_founding_reference(db: Session, reference: str) -> bool:
    return (
        db.scalar(
            select(FoundingReservation.id).where(FoundingReservation.reference == reference)
        )
        is not None
    )


def expire_founding_holds(db: Session, now: datetime | None = None) -> int:
    """Delete holds of checkouts abandoned for 30 minutes. Returns how many."""
    now = now or _now()
    expired = list(
        db.scalars(
            select(FoundingReservation).where(
                FoundingReservation.consumed_at.is_(None),
                FoundingReservation.expires_at <= now,
            )
        )
    )
    for hold in expired:
        db.delete(hold)
    db.commit()
    return len(expired)
