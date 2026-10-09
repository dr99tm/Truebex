"""Which seat a user holds, and so which tier their devices get.

`seat_source(db, user)` is the one function every entitlement goes through.
PF1 knows personal seats (the user's own live subscription), the trial and
Free; PF3 extends it with named and floating seats from organisations,
picking the best by tier rank. Callers look it up as `seats.seat_source` at
call time, so a test (or PF3) can swap it.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from ..billing.service import TRIAL_PROVIDER, effective_plan, live_subscription
from ..models import Subscription, User
from ..plans import get_plan
from . import clock

# Prepaid periods that end unless paid again: the entitlement may not outlive
# them (contract §6.1). Stripe renews by itself, so its period end is shown
# ("Renews on") but does not cut the document short.
FIXED_TERM_PROVIDERS = {TRIAL_PROVIDER, "wayl"}


@dataclass(frozen=True)
class Seat:
    kind: str  # free | personal | trial | named | floating
    plan: str  # tier id from catalogue.json
    devices_limit: int | None
    org_id: str | None = None
    org_name: str | None = None
    # The hard end of a trial or fixed term (caps expires_at), else None.
    ends_at: datetime | None = None
    # current_period_end of the live subscription, for display only.
    period_end: datetime | None = None
    seats_total: int = 1
    seats_assigned: int = 1
    subscription: Subscription | None = None


def personal_seat(db: Session, user: User) -> Seat:
    """The user's own seat: their live subscription, the trial, or Free."""
    plan_id = effective_plan(db, user)
    tier = get_plan(plan_id)
    limit = tier.limits.get("devices")
    sub = live_subscription(db, user)
    if sub is None or sub.plan != plan_id:
        if plan_id == "free":
            return Seat(kind="free", plan="free", devices_limit=limit)
        # "enterprise" assigned by hand, outranking any subscription row.
        return Seat(kind="personal", plan=tier.id, devices_limit=limit)
    period_end = clock.aware(sub.current_period_end)
    kind = "trial" if sub.provider == TRIAL_PROVIDER else "personal"
    return Seat(
        kind=kind,
        plan=tier.id,
        devices_limit=limit,
        ends_at=period_end if sub.provider in FIXED_TERM_PROVIDERS else None,
        period_end=period_end,
        seats_total=sub.seats or 1,
        seats_assigned=1,
        subscription=sub,
    )


# --- PF3: named and floating seats from organisations ------------------------------


def seat_source(db: Session, user: User) -> Seat:
    """The best seat the user holds, by tier rank: their own (personal, trial
    or Free) or a named or floating seat of an organisation they belong to.
    No lease is taken here; `claim` does that for a device."""
    from ..orgs import seats as org_seats

    return org_seats.best_seat(db, user, personal_seat(db, user))


def claim(db: Session, user: User, device, seat: Seat, now: datetime, *, when_full: str = "raise") -> Seat:
    """Make `seat` this device's: a floating seat takes or renews a lease
    (409 `no_seat_available` when the pool is full and nothing else is held,
    or the personal seat with when_full="free"); any other seat hands back the
    device's leases."""
    from ..orgs import seats as org_seats

    return org_seats.claim(db, user, device, seat, now, when_full=when_full)
