"""Monthly overage (PF6 Scope 6): cost units past the allowance, charged
through PF2 (`providers.get_provider(sub.provider).charge_usage(...)`).

`render.overage.charge` runs every 6 hours and charges every finished month
that has usage and no row yet (so a day the host was down is caught up). One
`overage_charges` row per account and month:

* `charged`: the provider took it (`provider_ref`).
* `pending`: no provider can charge this subscription (a trial, a dormant
  provider, or none): the owner settles it by hand.
* `failed`: the provider refused or was unreachable; the next run retries.

Only tiers with overage are charged, and never past the account's own cap
(a measured time can exceed the estimate the quota let through). The
quantity is whole cost units, rounded up, at the GD7 placeholder price in the
subscription's currency.
"""

import logging
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import metering
from ..billing import providers
from ..billing.base import NotSupported, ProviderError
from ..billing.service import TRIAL_PROVIDER
from ..licence import clock, seats
from ..models import User
from . import quotas
from .models import OverageCharge

log = logging.getLogger("truebex.render.overage")
METRIC = "cloud_cu"
# How many finished months a run looks back over.
LOOKBACK_MONTHS = 3


def _months_before(at: datetime, n: int) -> list[date]:
    start, _ = quotas.month_bounds(at)
    out = []
    for _ in range(n):
        start = start.replace(year=start.year - 1, month=12) if start.month == 1 else start.replace(month=start.month - 1)
        out.append(start)
    return out


def _next_month(day: date) -> date:
    return day.replace(year=day.year + 1, month=1) if day.month == 12 else day.replace(month=day.month + 1)


def charge_month(db: Session, user: User, month_start: date, now: datetime, row: OverageCharge | None = None) -> OverageCharge | None:
    plan = quotas.plan_of(db, user)
    limit = quotas.allowance(plan)
    if limit is None or not quotas.overage_allowed(plan):
        return None  # without overage, a measured time past the estimate is ours to carry
    used = metering.total(db, quotas.ACCOUNT_KIND, user.id, quotas.METRIC, month_start, _next_month(month_start))
    # Never more than the account allowed: estimates can run short.
    over = min(used - Decimal(limit), quotas.overage_cap(db, user.id))
    if over <= 0:
        return None
    sub = seats.seat_source(db, user).subscription
    currency = (sub.currency if sub is not None and sub.currency else "GBP").upper()
    quantity = quotas.whole_units(over)
    price = quotas.overage_price_minor(currency)
    month = month_start.strftime("%Y-%m")
    if row is None:
        row = OverageCharge(account_kind=quotas.ACCOUNT_KIND, account_id=user.id, month=month, created_at=now)
        db.add(row)
    row.cu = over.quantize(quotas.TENTH)
    row.amount_minor = quantity * price
    row.currency = currency
    row.provider = sub.provider if sub is not None else None
    description = f"Cloud rendering beyond your plan, {month_start.strftime('%B %Y')}"
    if sub is None or sub.provider == TRIAL_PROVIDER:
        row.state = "pending"
        row.note = "No paid subscription to charge (trial or none)."
        return row
    try:
        provider = providers.get_provider(sub.provider)
        if not provider.enabled():
            row.state = "pending"
            row.note = f"{sub.provider} is not enabled on this server."
            return row
        row.provider_ref = provider.charge_usage(db, sub, METRIC, quantity, price, description)
        row.state = "charged"
        row.charged_at = now
        row.note = ""
    except NotSupported as exc:
        row.state = "pending"
        row.note = str(exc)[:300]
    except (ProviderError, KeyError) as exc:
        row.state = "failed"
        row.note = str(exc)[:300] or "The provider did not take the charge."
        log.warning("overage charge for user %s %s failed: %s", user.id, month, exc)
    return row


def run(db: Session, now: datetime | None = None) -> int:
    """Charge every finished month with usage and no `charged`/`pending` row."""
    now = now or clock.now()
    done = 0
    for month_start in _months_before(now, LOOKBACK_MONTHS):
        month = month_start.strftime("%Y-%m")
        for subject_kind, subject_id in metering.subjects(db, quotas.METRIC, month_start, _next_month(month_start)):
            if subject_kind != quotas.ACCOUNT_KIND:
                continue
            existing = db.scalar(
                select(OverageCharge).where(
                    OverageCharge.account_kind == subject_kind,
                    OverageCharge.account_id == int(subject_id),
                    OverageCharge.month == month,
                )
            )
            if existing is not None and existing.state != "failed":
                continue
            user = db.get(User, int(subject_id))
            if user is None:
                continue
            if charge_month(db, user, month_start, now, existing) is not None:
                done += 1
            db.commit()
    return done
