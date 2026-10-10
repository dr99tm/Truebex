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

from sqlalchemy import func, select, update
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

# PF8: a supplier's listing plan is a Stripe subscription on these tables too
# (tier `listing_<plan>`), but it is never an app plan.
LISTING_TIER_PREFIX = "listing_"

# Trials are subscriptions rows too (licence contract 5.6).
TRIAL_PROVIDER = "trial"


def _rank(sub: Subscription) -> tuple[int, int]:
    # Higher tier wins (ranks come from catalogue.json); on a tie a paid row
    # beats a trial, so a user who buys Pro mid-trial reads as a paid seat.
    return rank(sub.plan), 0 if sub.provider == TRIAL_PROVIDER else 1


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
    (PF3, `organisation_id` set) is never its buyer's personal plan, nor is a
    supplier's listing plan (PF8)."""
    subs = db.scalars(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.organisation_id.is_(None),
            ~Subscription.plan.startswith(LISTING_TIER_PREFIX, autoescape=True),
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


def managed_subscription(db: Session, user: User) -> Subscription | None:
    """The user's Paddle or Stripe subscription: the live one if any, else the
    most recently updated (a past-due card still needs the portal)."""
    subs = list(
        db.scalars(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.provider.in_(MANAGED_PROVIDERS),
                ~Subscription.plan.startswith(LISTING_TIER_PREFIX, autoescape=True),
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


def find_subscription(db: Session, provider: str, provider_subscription_id: str) -> Subscription | None:
    return db.scalar(
        select(Subscription).where(
            Subscription.provider == provider,
            Subscription.provider_subscription_id == provider_subscription_id,
        )
    )


def _same(old: object, new: object) -> bool:
    if isinstance(old, datetime) or isinstance(new, datetime):
        return _aware(old) == _aware(new)  # type: ignore[arg-type]
    return old == new


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
    _retry: bool = True,
) -> Subscription | None:
    """Mirror a provider subscription. Returns None (and changes nothing) when
    `event_at` is older than the newest state already applied.

    `updated_at` moves only when the subscription really changed, so a daily
    re-fetch of unchanged state leaves it alone."""
    sub = find_subscription(db, provider, provider_subscription_id)
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
    wanted: dict[str, object] = {
        "plan": tier if tier in PLANS else "pro",
        "interval": interval,
        "seats": max(1, int(seats or 1)),
        "status": status,
        "current_period_end": current_period_end,
        "cancel_at_period_end": bool(cancel_at_period_end),
    }
    if customer_id:
        wanted["provider_customer_id"] = customer_id
    if currency:
        wanted["currency"] = currency.upper()
    if provider_price_id:
        wanted["provider_price_id"] = provider_price_id
    if founding is not None:
        wanted["founding"] = founding
    changed = sub.id is None
    for attr, value in wanted.items():
        if not _same(getattr(sub, attr), value):
            setattr(sub, attr, value)
            changed = True
    if changed:
        sub.last_event_at = event_at
        db.add(sub)
        if is_live(sub):
            _end_trials(db, user_id)
        try:
            db.commit()
        except IntegrityError:
            # Another request (the return-page refresh or the webhook) created
            # the same provider subscription first: apply onto its row.
            db.rollback()
            if not _retry:
                raise
            return upsert_subscription(
                db,
                provider=provider,
                provider_subscription_id=provider_subscription_id,
                user_id=user_id,
                tier=tier,
                interval=interval,
                seats=seats,
                status=status,
                current_period_end=current_period_end,
                cancel_at_period_end=cancel_at_period_end,
                customer_id=customer_id,
                currency=currency,
                provider_price_id=provider_price_id,
                founding=founding,
                event_at=event_at,
                _retry=False,
            )
    elif _aware(sub.last_event_at) is None or event_at > _aware(sub.last_event_at):
        # Same state, newer evidence: advance the ordering mark only.
        db.execute(
            update(Subscription)
            .where(Subscription.id == sub.id)
            .values(last_event_at=event_at, updated_at=Subscription.updated_at)
        )
        db.commit()
        db.refresh(sub)
    _refresh_cache(db, user_id)
    return sub


def record_renewal(
    db: Session,
    provider: str,
    provider_subscription_id: str | None,
    at: datetime | None,
    charge_id: str,
) -> bool:
    """A renewal charge the provider billed (from its verified event or API):
    remember the newest one, which opens the renewal cooling-off (PF2b).
    Returns True when it was new."""
    if not provider_subscription_id or at is None:
        return False
    sub = find_subscription(db, provider, provider_subscription_id)
    if sub is None:
        return False
    newest = _aware(sub.renewed_at)
    if newest is not None and _aware(at) <= newest:
        return False
    sub.renewed_at = at
    sub.renewal_charge_id = charge_id
    db.add(sub)
    db.commit()
    return True


def _end_trials(db: Session, user_id: int) -> None:
    """A purchase ends a running trial (licence contract 5.6: a paid plan
    answers 409 plan_active to a trial request)."""
    for trial in db.scalars(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.provider == TRIAL_PROVIDER,
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
    db: Session,
    provider: str,
    tier: str,
    interval: str,
    currency: str,
    amount_minor: int,
    founding: bool = False,
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
            ProviderPrice.founding.is_(founding),
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
# A fixed number of founding places (catalogue `founding.total`), one per
# subscription bought at a founding price, whatever its seats. A checkout holds
# a place for 30 minutes; billing.founding.expire releases abandoned holds and
# cancels their checkout so the founding price cannot be paid after the hold.


def _founding_open(now: datetime) -> bool:
    ends = FOUNDING.ends_at
    return FOUNDING.total > 0 and (ends is None or now < ends)


def founding_taken(db: Session, now: datetime | None = None) -> int:
    """Places bought plus places held by open checkouts."""
    now = now or _now()
    return int(
        db.scalar(
            select(func.count())
            .select_from(FoundingReservation)
            .where(
                (FoundingReservation.consumed_at.is_not(None))
                | (FoundingReservation.expires_at > now)
            )
        )
        or 0
    )


def founding_status(db: Session, now: datetime | None = None) -> dict:
    now = now or _now()
    remaining = max(0, FOUNDING.total - founding_taken(db, now)) if FOUNDING.total else 0
    return {
        "enabled": _founding_open(now) and remaining > 0,
        "total": FOUNDING.total,
        "remaining": remaining,
        "discount_percent": FOUNDING.discount_percent,
        "ends_at": FOUNDING.ends_at,
        "tiers": list(FOUNDING.tiers),
        "intervals": list(FOUNDING.intervals),
    }


def hold_founding(
    db: Session,
    user: User,
    reference: str,
    tier: str,
    interval: str,
    now: datetime | None = None,
) -> bool:
    """Hold a founding place for one checkout. False when the offer is
    closed, does not cover the tier and interval, or has no place left."""
    now = now or _now()
    if not FOUNDING.covers(tier, interval) or not _founding_open(now):
        return False
    # A new checkout replaces the user's earlier open hold.
    for old in db.scalars(
        select(FoundingReservation).where(
            FoundingReservation.user_id == user.id,
            FoundingReservation.consumed_at.is_(None),
        )
    ):
        db.delete(old)
    db.flush()
    if FOUNDING.total - founding_taken(db, now) < 1:
        db.commit()
        return False
    db.add(
        FoundingReservation(
            user_id=user.id, reference=reference, seats=1, expires_at=now + FOUNDING_HOLD
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


def count_founding(db: Session, reference: str, user_id: int) -> None:
    """A founding price was paid: its place is taken for good (idempotent).
    Counted even when the hold had lapsed, so the count stays true."""
    hold = db.scalar(
        select(FoundingReservation).where(FoundingReservation.reference == reference)
    )
    if hold is None:
        hold = FoundingReservation(
            user_id=user_id, reference=reference, seats=1, expires_at=_now()
        )
    if hold.consumed_at is None:
        hold.consumed_at = _now()
        db.add(hold)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # counted by a concurrent delivery


def founding_reference(
    db: Session, provider: str, user_id: int, reference: str | None, provider_subscription_id: str
) -> str:
    """The place a founding subscription takes: its checkout's reference when
    the subscription came from our checkout for this user, else its own id."""
    if reference:
        payment = db.scalar(
            select(Payment).where(
                Payment.reference == reference,
                Payment.provider == provider,
                Payment.user_id == user_id,
            )
        )
        if payment is not None:
            return payment.reference
    return f"sub:{provider_subscription_id}"


def is_founding_reference(db: Session, reference: str) -> bool:
    return (
        db.scalar(
            select(FoundingReservation.id).where(FoundingReservation.reference == reference)
        )
        is not None
    )


def expired_holds(db: Session, now: datetime | None = None) -> list[FoundingReservation]:
    now = now or _now()
    return list(
        db.scalars(
            select(FoundingReservation).where(
                FoundingReservation.consumed_at.is_(None),
                FoundingReservation.expires_at <= now,
            )
        )
    )


def expire_founding_holds(db: Session, now: datetime | None = None) -> int:
    """Delete holds of checkouts abandoned for 30 minutes. Returns how many."""
    expired = expired_holds(db, now)
    for hold in expired:
        db.delete(hold)
    db.commit()
    return len(expired)
