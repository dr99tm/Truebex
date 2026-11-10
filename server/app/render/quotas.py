"""Kinds, worker classes, cost units, allowances and overage (contract §6.4, §7).

* One cost unit (cu) = one minute of wall time on `gpu-std`; other classes
  carry the weight CU_CLASS_WEIGHTS gives them. Charge = wall_s / 60 × weight,
  rounded up to 0.1 cu, for `succeeded` jobs only.
* The month's allowance is the entitlement's `limits.cloud_cu_month`
  (licence-api §6.3): an integer, or null = no limit. The contract's
  placeholder matrix still says 0 for every tier while GD7 is unwritten, so a
  tier that holds `cloud.panoramas` with 0 cu takes the placeholder below; any
  other number (or null) the owner writes in catalogue.json wins at once.
* Tiers with overage (GD7 placeholder: Studio, Team) may go past the
  allowance up to the account's own cap; the monthly run charges it through
  PF2 (`overage.py`).
* 403 `quota_exceeded` when an estimate exceeds what is left: the allowance
  plus the overage cap, minus what was charged this month and the estimates of
  jobs still in flight.
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import metering
from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock, seats
from ..models import User
from ..plans import Plan, get_plan
from .models import OverageCap, RenderJob

ACCOUNT_KIND = "user"
METRIC = "cu"
# PF11 adds acoustics and texture (MINOR proposals) beside the contract's five;
# render-jobs 1.2.0 adds airflow (PF11c).
CONTRACT_KINDS = ("panorama", "tiles", "pack", "wind", "energy", "acoustics", "texture", "airflow")
LIVE_STATES = ("queued", "claimed", "running")
TENTH = Decimal("0.1")


@dataclass(frozen=True)
class Kind:
    name: str
    feature: str
    worker_class: str
    # What the estimate counts: views (panorama, tiles) or items (pack).
    unit: str


# Kinds this platform runs. PF11 adds `wind`, `energy`, `acoustics` (feature
# `analysis.reports`, class `cpu-8`) and `texture` (gpu-ai) on the same queue
# (app.analysis.kinds.sync).
KINDS: dict[str, Kind] = {
    "panorama": Kind("panorama", "cloud.panoramas", "gpu-std", "view"),
    "tiles": Kind("tiles", "cloud.panoramas", "gpu-std", "view"),
    "pack": Kind("pack", "cloud.panoramas", "gpu-std", "item"),
}
# Each kind's worker class, switched-off kinds included (a worker token's
# kinds must all run on its class).
KIND_CLASSES: dict[str, str] = {name: k.worker_class for name, k in KINDS.items()}


def kind_class(kind: str) -> str | None:
    known = KINDS.get(kind)
    return known.worker_class if known is not None else KIND_CLASSES.get(kind)

# Placeholders "from GD7" (the guide has no matrix yet).
PLACEHOLDER_CU: dict[str, int | None] = {"free": 0, "pro": 120, "studio": 600, "team": 600, "enterprise": None}
OVERAGE_TIERS = ("studio", "team")
# Price of one cost unit past the allowance, in minor units ("from GD7").
OVERAGE_PRICE_MINOR = {"GBP": 10, "USD": 12, "EUR": 12}


def class_weights() -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for part in get_settings().cu_class_weights.split(","):
        name, _, weight = part.strip().partition(":")
        if name and weight:
            out[name.strip()] = Decimal(weight.strip())
    return out or {"gpu-std": Decimal("1.0")}


def round_up_tenth(value: Decimal) -> Decimal:
    return (value * 10).to_integral_value(rounding=ROUND_CEILING) / 10


def cost_units(wall_s: float, worker_class: str) -> Decimal:
    weight = class_weights().get(worker_class)
    if weight is None:
        raise ContractError(
            "output_invalid", 422, f"usage.class {worker_class} is not a known worker class.",
            {"errors": [{"path": "usage.class", "rule": "class", "message": "a class 5.6 publishes"}]},
        )
    return round_up_tenth(Decimal(str(max(0.0, wall_s))) / 60 * weight).quantize(TENTH)


# --- months -------------------------------------------------------------------------


def month_bounds(at: datetime | None = None) -> tuple[date, date]:
    """[first day of the month, first day of the next) in UTC."""
    day = (at or clock.now()).astimezone(timezone.utc).date().replace(day=1)
    nxt = day.replace(year=day.year + 1, month=1) if day.month == 12 else day.replace(month=day.month + 1)
    return day, nxt


def rfc3339_day(day: date) -> str:
    return f"{day.isoformat()}T00:00:00Z"


# --- plans --------------------------------------------------------------------------


def plan_of(db: Session, user: User) -> Plan:
    # Looked up at call time: PF3 (and tests) swap seats.seat_source.
    return get_plan(seats.seat_source(db, user).plan)


def require_feature(db: Session, user: User, kind: Kind) -> Plan:
    plan = plan_of(db, user)
    if kind.feature not in plan.features:
        raise ContractError(
            "plan_required",
            403,
            "Cloud rendering comes with a paid plan or the trial. Upgrade to render in the cloud.",
            {"feature": kind.feature, "plan": plan.id},
        )
    return plan


def allowance(plan: Plan) -> int | None:
    """The month's cost units, or None for no limit."""
    if "cloud_cu_month" in plan.limits:
        value = plan.limits["cloud_cu_month"]
        if value is None:
            return None
        if int(value) > 0 or "cloud.panoramas" not in plan.features:
            return int(value)
    return PLACEHOLDER_CU.get(plan.id, 0)


def overage_allowed(plan: Plan) -> bool:
    return plan.id in OVERAGE_TIERS and allowance(plan) is not None


# --- what is used ---------------------------------------------------------------------


def used_cu(db: Session, account_id: int, at: datetime | None = None) -> Decimal:
    start, end = month_bounds(at)
    return metering.total(db, ACCOUNT_KIND, account_id, METRIC, start, end)


def in_flight_cu(db: Session, account_id: int, *, exclude: str | None = None) -> Decimal:
    """Estimates of the account's jobs that have not finished yet."""
    q = select(func.coalesce(func.sum(RenderJob.cost_units_estimate), 0)).where(
        RenderJob.account_kind == ACCOUNT_KIND, RenderJob.account_id == account_id, RenderJob.state.in_(LIVE_STATES)
    )
    if exclude:
        q = q.where(RenderJob.job_id != exclude)
    return Decimal(str(db.scalar(q) or 0)).quantize(TENTH)


def overage_cap(db: Session, account_id: int) -> Decimal:
    row = db.get(OverageCap, (ACCOUNT_KIND, account_id))
    return Decimal(row.cap_cu).quantize(TENTH) if row is not None else Decimal("0.0")


def set_overage_cap(db: Session, user: User, cap: Decimal) -> Decimal:
    plan = plan_of(db, user)
    if cap > 0 and not overage_allowed(plan):
        raise ContractError(
            "plan_required", 403, "Going past the monthly allowance comes with Team.",
            {"feature": "cloud.overage", "plan": plan.id},
        )
    cap = cap.quantize(TENTH)
    row = db.get(OverageCap, (ACCOUNT_KIND, user.id))
    if row is None:
        row = OverageCap(account_kind=ACCOUNT_KIND, account_id=user.id, cap_cu=cap)
        db.add(row)
    row.cap_cu = cap
    row.updated_at = clock.now()
    db.commit()
    return cap


def check(db: Session, user: User, plan: Plan, estimate: Decimal) -> None:
    """403 `quota_exceeded` when `estimate` does not fit what is left."""
    limit = allowance(plan)
    if limit is None:
        return
    used = used_cu(db, user.id)
    reserved = in_flight_cu(db, user.id)
    cap = overage_cap(db, user.id) if overage_allowed(plan) else Decimal(0)
    left = Decimal(limit) + cap - used - reserved
    if estimate > left:
        _, resets = month_bounds()
        raise ContractError(
            "quota_exceeded",
            403,
            "This month's cloud allowance is used up." if used + reserved >= limit + cap
            else "This job needs more of this month's cloud allowance than is left.",
            {
                "used_cu": float(used),
                "limit_cu": limit,
                "reserved_cu": float(reserved),
                "overage_cap_cu": float(cap),
                "estimate_cu": float(estimate),
                "resets_at": rfc3339_day(resets),
            },
        )


def overage_price_minor(currency: str) -> int:
    return OVERAGE_PRICE_MINOR.get(currency.upper(), OVERAGE_PRICE_MINOR["GBP"])


def whole_units(cu: Decimal) -> int:
    """Overage is charged per whole cost unit, rounded up."""
    return int(math.ceil(cu))
