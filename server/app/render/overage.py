"""Overage (PF6 Scope 6): cost units past the allowance, charged monthly
through PF2 (`providers.get_provider(sub.provider).charge_usage(...)`).

Overage is accrued when it happens, under the terms in force then: each
completed job that takes a Studio or Team account past its allowance adds
the part beyond it, up to the account's own cap, to the month's `open` row
(`accrue`, inside the job's completion). Lowering the cap or changing plan
later never rewrites a month already used. `render.overage.charge` (every 6
hours) charges every earlier month's `open` row, catching up after downtime:

* `charged`: the provider took it (`provider_ref`).
* `pending`: no provider can charge this subscription (a trial, a dormant
  provider, or none): the owner settles it by hand.
* `failed`: the provider refused or was unreachable; the next run retries.

The quantity is whole cost units, rounded up, at the GD7 placeholder price in
the subscription's currency. Tiers without overage are never charged: a
measured time past the estimate the quota let through is ours to carry.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..billing import providers
from ..billing.base import NotSupported, ProviderError
from ..billing.service import TRIAL_PROVIDER
from ..database import dialect_insert
from ..licence import clock, seats
from ..models import User
from . import quotas
from .models import OverageCharge

log = logging.getLogger("truebex.render.overage")
METRIC = "cloud_cu"


@dataclass(frozen=True)
class Terms:
    limit: int | None
    allowed: bool
    cap: Decimal


def terms_for(db: Session, account_id: int) -> Terms | None:
    """The account's allowance and overage cap now (read before any row lock:
    looking a plan up may write)."""
    user = db.get(User, account_id)
    if user is None:
        return None
    plan = quotas.plan_of(db, user)
    allowed = quotas.overage_allowed(plan)
    return Terms(quotas.allowance(plan), allowed, quotas.overage_cap(db, account_id) if allowed else Decimal(0))


def month_of(at: datetime) -> str:
    return quotas.month_bounds(at)[0].strftime("%Y-%m")


def _row(db: Session, account_id: int, month: str) -> OverageCharge | None:
    return db.scalar(
        select(OverageCharge)
        .where(
            OverageCharge.account_kind == quotas.ACCOUNT_KIND,
            OverageCharge.account_id == account_id,
            OverageCharge.month == month,
        )
        .with_for_update()
    )


def accrue(db: Session, account_id: int, cost: Decimal, terms: Terms | None, now: datetime) -> Decimal:
    """Add the part of `cost` past the allowance (within the cap) to the
    month's open row. Call after metering the cost, in the same transaction."""
    if terms is None or not terms.allowed or terms.limit is None or cost <= 0:
        return Decimal(0)
    used = quotas.used_cu(db, account_id, now)
    limit = Decimal(terms.limit)
    new = max(Decimal(0), used - limit) - max(Decimal(0), used - cost - limit)
    if new <= 0:
        return Decimal(0)
    month = month_of(now)
    row = _row(db, account_id, month)
    add = min(new, max(Decimal(0), terms.cap - (Decimal(row.cu) if row is not None else Decimal(0))))
    if add <= 0:
        return Decimal(0)
    if row is None:
        db.execute(
            dialect_insert(db, OverageCharge)
            .values(
                account_kind=quotas.ACCOUNT_KIND, account_id=account_id, month=month, cu=Decimal(0), amount_minor=0,
                currency="GBP", state="open", note="", created_at=now,
            )
            .on_conflict_do_nothing(index_elements=["account_kind", "account_id", "month"])
        )
        row = _row(db, account_id, month)
    row.cu = (Decimal(row.cu) + add).quantize(quotas.TENTH)
    return add


def used_this_month(db: Session, account_id: int, at: datetime | None = None) -> Decimal:
    row = db.scalar(
        select(OverageCharge).where(
            OverageCharge.account_kind == quotas.ACCOUNT_KIND,
            OverageCharge.account_id == account_id,
            OverageCharge.month == month_of(at or clock.now()),
        )
    )
    return Decimal(row.cu).quantize(quotas.TENTH) if row is not None else Decimal("0.0")


def charge(db: Session, row: OverageCharge, now: datetime) -> OverageCharge:
    user = db.get(User, row.account_id)
    sub = seats.seat_source(db, user).subscription if user is not None else None
    currency = (sub.currency if sub is not None and sub.currency else "GBP").upper()
    quantity = quotas.whole_units(Decimal(row.cu))
    price = quotas.overage_price_minor(currency)
    row.amount_minor = quantity * price
    row.currency = currency
    row.provider = sub.provider if sub is not None else None
    year, month = (int(x) for x in row.month.split("-"))
    description = f"Cloud rendering beyond your plan, {datetime(year, month, 1).strftime('%B %Y')}"
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
        log.warning("overage charge for user %s %s failed: %s", row.account_id, row.month, exc)
    return row


def run(db: Session, now: datetime | None = None) -> int:
    """Charge every earlier month's open (or failed) row."""
    now = now or clock.now()
    ids = list(
        db.scalars(
            select(OverageCharge.id).where(
                OverageCharge.state.in_(("open", "failed")),
                OverageCharge.month < month_of(now),
                OverageCharge.cu > 0,
            )
        )
    )
    db.rollback()
    done = 0
    for row_id in ids:
        row = db.scalar(select(OverageCharge).where(OverageCharge.id == row_id).with_for_update())
        if row is None or row.state not in ("open", "failed"):
            db.rollback()
            continue
        charge(db, row, now)
        db.commit()
        done += 1
    return done
