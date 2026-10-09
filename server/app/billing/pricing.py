"""From a tier, an interval and a currency to the provider price to charge.

The browser names only the tier, interval, currency and seats; the amount
always comes from catalogue.json and the price id from provider_prices.
"""

from sqlalchemy.orm import Session

from ..models import ProviderPrice
from ..plans import FOUNDING, PLANS, Plan, Price
from . import service


class PriceUnavailable(Exception):
    """No price to charge. `reason`: not_purchasable | no_price | not_synced."""

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def plan(tier: str) -> Plan:
    p = PLANS.get(tier)
    if p is None or not p.purchasable:
        raise PriceUnavailable("not_purchasable", "That plan can't be bought online.")
    return p


def catalogue_price(tier: str, interval: str, currency: str) -> Price:
    p = plan(tier)
    price = p.price(interval, currency)
    if price is None:
        raise PriceUnavailable(
            "no_price", f"{p.name} has no {interval}ly price in {currency.upper()}."
        )
    return price


def amount(tier: str, interval: str, currency: str, founding: bool) -> int:
    """Per-seat amount in minor units: the list price or the founding price."""
    price = catalogue_price(tier, interval, currency)
    return FOUNDING.discounted(price.amount_minor) if founding else price.amount_minor


def resolve(
    db: Session, provider: str, tier: str, interval: str, currency: str, founding: bool
) -> ProviderPrice:
    """The active provider price for this catalogue amount. Raises
    PriceUnavailable("not_synced") when sync_prices.py has not mirrored it."""
    row = service.provider_price(
        db, provider, tier, interval, currency, amount(tier, interval, currency, founding)
    )
    if row is None:
        raise PriceUnavailable(
            "not_synced", "Online payment for this plan isn't set up yet."
        )
    return row
