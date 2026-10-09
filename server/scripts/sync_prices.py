"""Mirror catalogue.json's prices to a payment provider and fill provider_prices.

    cd server
    .venv\\Scripts\\python.exe scripts\\sync_prices.py --provider paddle --env sandbox
    .venv\\Scripts\\python.exe scripts\\sync_prices.py --provider stripe --env sandbox --dry-run

For every purchasable tier, interval and currency (and the founding price of
each the offer covers, `founding.discount_percent` off: the annual prices of
`founding.tiers` today) it finds or creates the provider's
product and price, keyed by a lookup key `truebex_<tier>_<interval>_<cur>_<amount>[_founding]`
(Paddle: the price's custom_data; Stripe: lookup_key), so a second run creates
nothing. A changed amount is a new price; the old row stays in provider_prices
(inactive) so webhooks for existing subscribers still map to their tier.

Run it whenever a price changes in catalogue.json, with the keys of the environment the
API runs against (server/.env). Tax: prices follow the provider account's
default (inclusive or exclusive), which GD5 decides.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stripe  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.billing import providers  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models import ProviderPrice  # noqa: E402
from app.plans import FOUNDING, PLANS  # noqa: E402


@dataclass(frozen=True)
class Target:
    tier: str
    tier_name: str
    interval: str
    currency: str
    amount_minor: int
    founding: bool
    per_seat: bool
    min_seats: int

    @property
    def lookup_key(self) -> str:
        key = f"truebex_{self.tier}_{self.interval}_{self.currency.lower()}_{self.amount_minor}"
        return f"{key}_founding" if self.founding else key

    @property
    def label(self) -> str:
        period = "monthly" if self.interval == "month" else "annual"
        seat = " per seat" if self.per_seat else ""
        return f"Truebex {self.tier_name}, {period}{seat}{' (founding)' if self.founding else ''}"


def targets() -> list[Target]:
    out = []
    for plan in PLANS.values():
        if not plan.purchasable:
            continue
        for price in plan.prices:
            variants = [(price.amount_minor, False)]
            if FOUNDING.covers(plan.id, price.interval) and FOUNDING.total and FOUNDING.discount_percent:
                variants.append((FOUNDING.discounted(price.amount_minor), True))
            for amount, founding in variants:
                out.append(
                    Target(
                        tier=plan.id,
                        tier_name=plan.name,
                        interval=price.interval,
                        currency=price.currency,
                        amount_minor=amount,
                        founding=founding,
                        per_seat=plan.per_seat,
                        min_seats=plan.min_seats,
                    )
                )
    return out


# --- Paddle --------------------------------------------------------------------------


def _paddle_all(client: Any, path: str, params: dict) -> list[dict]:
    rows: list[dict] = []
    url: str | None = path
    query: dict | None = {**params, "per_page": 200}
    while url:
        res = client.get(url, params=query)
        res.raise_for_status()
        body = res.json()
        rows.extend(body.get("data") or [])
        url = ((body.get("meta") or {}).get("pagination") or {}).get("next")
        query = None  # `next` is a full URL with its own cursor
    return rows


def sync_paddle(s: Settings, dry_run: bool = False) -> list[tuple[Target, str, bool]]:
    """Returns (target, price id, created) for every target."""
    out = []
    with providers._paddle_client(s) as client:
        products = {
            (p.get("custom_data") or {}).get("truebex_tier"): p["id"]
            for p in _paddle_all(client, "/products", {"status": "active"})
        }
        prices: dict[str, str] = {}
        for tier, product_id in products.items():
            if not tier:
                continue
            for price in _paddle_all(client, "/prices", {"product_id": product_id, "status": "active"}):
                key = (price.get("custom_data") or {}).get("lookup_key")
                if key:
                    prices[key] = price["id"]
        for t in targets():
            if t.lookup_key in prices:
                out.append((t, prices[t.lookup_key], False))
                continue
            if dry_run:
                out.append((t, "(would create)", True))
                continue
            product_id = products.get(t.tier)
            if product_id is None:
                res = client.post(
                    "/products",
                    json={
                        "name": f"Truebex {t.tier_name}",
                        "tax_category": "standard",
                        "custom_data": {"truebex_tier": t.tier},
                    },
                )
                res.raise_for_status()
                product_id = products[t.tier] = res.json()["data"]["id"]
            res = client.post(
                "/prices",
                json={
                    "product_id": product_id,
                    "description": t.label,
                    "name": t.label,
                    "unit_price": {"amount": str(t.amount_minor), "currency_code": t.currency},
                    "billing_cycle": {"interval": t.interval, "frequency": 1},
                    "tax_mode": "account_setting",
                    "quantity": {
                        "minimum": t.min_seats if t.per_seat else 1,
                        "maximum": 1000 if t.per_seat else 1,
                    },
                    "custom_data": {
                        "lookup_key": t.lookup_key,
                        "tier": t.tier,
                        "interval": t.interval,
                        "founding": "1" if t.founding else "0",
                    },
                },
            )
            res.raise_for_status()
            price_id = prices[t.lookup_key] = res.json()["data"]["id"]
            out.append((t, price_id, True))
    return out


# --- Stripe ----------------------------------------------------------------------------


def sync_stripe(s: Settings, dry_run: bool = False) -> list[tuple[Target, str, bool]]:
    key = s.stripe_secret_key
    all_targets = targets()
    found: dict[str, str] = {}
    keys = [t.lookup_key for t in all_targets]
    for i in range(0, len(keys), 10):  # Stripe takes at most 10 lookup keys per call
        page = stripe.Price.list(api_key=key, lookup_keys=keys[i : i + 10], active=True, limit=10)
        for price in page.get("data") or []:
            found[price["lookup_key"]] = price["id"]
    products: dict[str, str] = {}
    for product in stripe.Product.list(api_key=key, active=True, limit=100).auto_paging_iter():
        tier = (product.get("metadata") or {}).get("truebex_tier")
        if tier:
            products[tier] = product["id"]
    out = []
    for t in all_targets:
        if t.lookup_key in found:
            out.append((t, found[t.lookup_key], False))
            continue
        if dry_run:
            out.append((t, "(would create)", True))
            continue
        if t.tier not in products:
            products[t.tier] = stripe.Product.create(
                api_key=key, name=f"Truebex {t.tier_name}", metadata={"truebex_tier": t.tier}
            )["id"]
        price = stripe.Price.create(
            api_key=key,
            product=products[t.tier],
            currency=t.currency.lower(),
            unit_amount=t.amount_minor,
            recurring={"interval": t.interval},
            lookup_key=t.lookup_key,
            nickname=t.label,
            metadata={"tier": t.tier, "interval": t.interval, "founding": "1" if t.founding else "0"},
        )
        out.append((t, price["id"], True))
    return out


# --- provider_prices ---------------------------------------------------------------------


def store(db: Session, provider: str, synced: list[tuple[Target, str, bool]]) -> int:
    """Upsert one row per synced price; rows for amounts no longer in the
    catalogue are kept but marked inactive. Returns the active row count."""
    live_ids = set()
    for t, price_id, _created in synced:
        row = db.scalar(
            select(ProviderPrice).where(
                ProviderPrice.provider == provider, ProviderPrice.provider_price_id == price_id
            )
        )
        if row is None:
            row = ProviderPrice(provider=provider, provider_price_id=price_id)
        row.tier, row.interval, row.currency = t.tier, t.interval, t.currency
        row.amount_minor, row.founding, row.active = t.amount_minor, t.founding, True
        db.add(row)
        live_ids.add(price_id)
    for row in db.scalars(select(ProviderPrice).where(ProviderPrice.provider == provider)):
        if row.provider_price_id not in live_ids:
            row.active = False
    db.commit()
    return len(live_ids)


def sync(provider: str, env: str, settings: Settings | None = None, dry_run: bool = False) -> list[tuple[Target, str, bool]]:
    s = settings or get_settings()
    if provider == "paddle":
        if not s.paddle_api_key:
            raise SystemExit("PADDLE_API_KEY is not set in server/.env")
        if env != s.paddle_env:
            raise SystemExit(f"--env {env} but PADDLE_ENV={s.paddle_env}: the price ids would not match the API's")
        synced = sync_paddle(s, dry_run)
    elif provider == "stripe":
        if not s.stripe_secret_key:
            raise SystemExit("STRIPE_SECRET_KEY is not set in server/.env")
        live = s.stripe_secret_key.startswith(("sk_live_", "rk_live_"))
        if live != (env == "production"):
            raise SystemExit(f"--env {env} does not match the Stripe key's mode")
        synced = sync_stripe(s, dry_run)
    else:
        raise SystemExit(f"unknown provider {provider}")
    if not dry_run:
        init_db()
        with SessionLocal() as db:
            store(db, provider, synced)
    return synced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", choices=["paddle", "stripe"], required=True)
    parser.add_argument("--env", choices=["sandbox", "production"], required=True)
    parser.add_argument("--dry-run", action="store_true", help="list what would be created")
    args = parser.parse_args(argv)
    synced = sync(args.provider, args.env, dry_run=args.dry_run)
    for t, price_id, created in synced:
        amount = f"{t.amount_minor / 100:.2f} {t.currency}"
        print(f"{'created' if created else 'exists '}  {t.lookup_key:<40} {amount:>12}  {price_id}")
    print(f"{len(synced)} prices, {sum(1 for _, _, c in synced if c)} new")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
