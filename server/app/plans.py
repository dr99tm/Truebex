"""The plan catalogue: tiers, ranks, the entitlement matrix and API limits.

The source of truth is `catalogue.json` beside this file (PF1). The website
imports the same file at build time (src/lib/catalogue.ts), so plan names and
limits are never typed twice. Until GD7 is written the matrix is the licence
contract's §6.3 placeholder; prices are PF2's.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

CATALOGUE_PATH = Path(__file__).with_name("catalogue.json")


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    # Monthly price in US cents (Stripe). None = not sold online.
    price_usd_cents: int | None
    # API requests allowed per calendar month (UTC), across all keys.
    monthly_requests: int
    # Active (non-revoked) API keys allowed at once.
    max_api_keys: int
    purchasable: bool
    # Higher wins when a user has several live subscriptions.
    rank: int = 0
    # Entitlement keys this tier unlocks (sorted, unique) and its limits
    # (an integer, or None = no limit).
    features: tuple[str, ...] = ()
    limits: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))


def _load(path: Path = CATALOGUE_PATH) -> dict[str, Plan]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    plans: dict[str, Plan] = {}
    for t in sorted(data["tiers"], key=lambda t: t["rank"]):
        plans[t["id"]] = Plan(
            id=t["id"],
            name=t["name"],
            price_usd_cents=t.get("price_usd_cents"),
            monthly_requests=int(t["api"]["monthly_requests"]),
            max_api_keys=int(t["api"]["max_api_keys"]),
            purchasable=bool(t["purchasable"]),
            rank=int(t["rank"]),
            features=tuple(sorted(set(t["features"]))),
            limits=MappingProxyType(dict(t["limits"])),
        )
    return plans


# In rank order: free, pro, studio, team, enterprise.
PLANS: dict[str, Plan] = _load()


def get_plan(plan_id: str) -> Plan:
    """The tier for an id; unknown ids fall back to free."""
    return PLANS.get(plan_id, PLANS["free"])


def plan_rank(plan_id: str) -> int:
    return get_plan(plan_id).rank
