"""The plan catalog: prices and API limits per plan.

The marketing site shows the same plans (src/lib/constants.ts PRICING_PLANS);
keep the two in step when changing prices.
"""

from dataclasses import dataclass


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


PLANS: dict[str, Plan] = {
    "free": Plan(
        id="free",
        name="Starter",
        price_usd_cents=0,
        monthly_requests=1_000,
        max_api_keys=2,
        purchasable=False,
    ),
    "pro": Plan(
        id="pro",
        name="Professional",
        price_usd_cents=99_00,
        monthly_requests=100_000,
        max_api_keys=20,
        purchasable=True,
    ),
    "enterprise": Plan(
        id="enterprise",
        name="Enterprise",
        price_usd_cents=None,
        monthly_requests=5_000_000,
        max_api_keys=200,
        purchasable=False,
    ),
}


def get_plan(plan_id: str) -> Plan:
    return PLANS.get(plan_id, PLANS["free"])
