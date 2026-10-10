"""Supplier listing plans and their fees (`listing_plans.json`, placeholders
until GD7 §4: every number is `confirm at writing time`).

A plan sets the default commission rate (a supplier's own `commission_bp`
overrides it) and an optional monthly listing fee per currency. Listing fees
are billed with the monthly statement (commissions.py) through PF2's
`create_invoice` once PF2 is merged; until then statements stay `pending`.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .models import Supplier

PLANS_FILE = Path(__file__).with_name("listing_plans.json")


@dataclass(frozen=True)
class ListingPlan:
    id: str
    name: str
    commission_bp: int
    # currency → minor units a month; empty = no listing fee.
    monthly_fee: dict


@lru_cache
def _load() -> tuple[str, dict[str, ListingPlan]]:
    data = json.loads(PLANS_FILE.read_text(encoding="utf-8"))
    plans = {
        p["id"]: ListingPlan(p["id"], p["name"], int(p["commission_bp"]), dict(p.get("monthly_fee") or {}))
        for p in data["plans"]
    }
    return data["default_plan"], plans


def plans() -> dict[str, ListingPlan]:
    return _load()[1]


def plan_of(supplier: Supplier) -> ListingPlan:
    default, all_plans = _load()
    return all_plans.get(supplier.listing_plan or default) or all_plans[default]


def commission_bp_for(supplier: Supplier) -> int:
    if supplier.commission_bp is not None:
        return supplier.commission_bp
    return plan_of(supplier).commission_bp


def monthly_fee(supplier: Supplier, currency: str) -> int:
    """The listing fee for one month in `currency` (0 when none is set)."""
    return int(plan_of(supplier).monthly_fee.get(currency, 0) or 0)


def plans_json() -> list[dict]:
    return [
        {"id": p.id, "name": p.name, "commission_bp": p.commission_bp, "monthly_fee": p.monthly_fee}
        for p in plans().values()
    ]
