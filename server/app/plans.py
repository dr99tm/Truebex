"""The plan catalogue: tiers, prices and API limits, read from catalogue.json.

`server/app/catalogue.json` is the one source: the API reads it here, the
website imports it at build time (src/lib/catalogue.ts) and
`server/scripts/sync_prices.py` mirrors its prices to the payment providers.
Prices and the founding offer are placeholders until guides/GD7.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

CATALOGUE_PATH = Path(__file__).with_name("catalogue.json")

INTERVALS = ("month", "year")

# Minor-unit exponent per currency (CLDR digits, as the site's Intl formats
# them). IQD is whole dinars, as Wayl payments were always stored.
_CURRENCY_DIGITS = {"GBP": 2, "USD": 2, "EUR": 2, "IQD": 0}


def currency_digits(currency: str) -> int:
    return _CURRENCY_DIGITS.get(currency.upper(), 2)


@dataclass(frozen=True)
class Price:
    interval: str  # month | year
    currency: str  # ISO 4217, upper case
    amount_minor: int


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    rank: int
    # Sold through checkout (free and enterprise are not).
    purchasable: bool
    # Bought with a quantity of seats (Team).
    per_seat: bool
    min_seats: int
    prices: tuple[Price, ...]
    # API requests allowed per calendar month (UTC), across all keys.
    monthly_requests: int
    # Active (non-revoked) API keys allowed at once.
    max_api_keys: int
    features: tuple[str, ...]
    limits: dict[str, int | None]

    def price(self, interval: str, currency: str) -> Price | None:
        for p in self.prices:
            if p.interval == interval and p.currency == currency.upper():
                return p
        return None


@dataclass(frozen=True)
class FoundingOffer:
    total: int
    discount_percent: int
    ends_at: datetime | None
    tiers: tuple[str, ...]

    def discounted(self, amount_minor: int) -> int:
        """The founding price of a seat that lists at `amount_minor`."""
        return (amount_minor * (100 - self.discount_percent) + 50) // 100


def _load(path: Path = CATALOGUE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _plan(raw: dict[str, Any]) -> Plan:
    api = raw.get("api") or {}
    return Plan(
        id=raw["id"],
        name=raw["name"],
        rank=int(raw.get("rank", 0)),
        purchasable=bool(raw.get("purchasable")),
        per_seat=bool(raw.get("per_seat")),
        min_seats=max(1, int(raw.get("min_seats") or 1)),
        prices=tuple(
            Price(p["interval"], p["currency"].upper(), int(p["amount_minor"]))
            for p in raw.get("prices") or []
        ),
        monthly_requests=int(api.get("monthly_requests", 0)),
        max_api_keys=int(api.get("max_api_keys", 0)),
        features=tuple(raw.get("features") or ()),
        limits=dict(raw.get("limits") or {}),
    )


def _founding(raw: dict[str, Any] | None) -> FoundingOffer:
    raw = raw or {}
    ends = raw.get("ends_at")
    return FoundingOffer(
        total=int(raw.get("total") or 0),
        discount_percent=int(raw.get("discount_percent") or 0),
        ends_at=datetime.fromisoformat(ends.replace("Z", "+00:00")) if ends else None,
        tiers=tuple(raw.get("tiers") or ()),
    )


CATALOGUE: dict[str, Any] = _load()
PLANS: dict[str, Plan] = {t["id"]: _plan(t) for t in CATALOGUE["tiers"]}
FOUNDING: FoundingOffer = _founding(CATALOGUE.get("founding"))
CURRENCIES: tuple[str, ...] = tuple(c.upper() for c in CATALOGUE.get("currencies") or ())


def get_plan(plan_id: str) -> Plan:
    return PLANS.get(plan_id, PLANS["free"])


def rank(plan_id: str) -> int:
    """Higher wins when a user has several live subscriptions."""
    plan = PLANS.get(plan_id)
    return plan.rank if plan else 0
