"""PF2a: the catalogue's prices per the owner's pricing plan.

The amounts below are the owner's (the PF2a task, 2026-10-09; the pricing
guide GD7 was still a stub). They live in `server/app/catalogue.json`; this
file pins them so a stray edit fails loudly. Team is per seat and annual
only; the founding offer is 30 % off the annual prices.
"""

import io
from contextlib import redirect_stdout

import pytest
import stripe
from sqlalchemy import select

from app.database import SessionLocal
from app.models import ProviderPrice
from app.plans import CATALOGUE, FOUNDING, PLANS

from .conftest import checkout_body, signup
from .test_billing_pf2 import buy, local_sub, start_checkout, txn_of

# (interval, currency) -> amount in minor units, per tier.
PLAN = {
    "pro": {
        ("month", "USD"): 2900, ("month", "GBP"): 2400, ("month", "EUR"): 2700,
        ("year", "USD"): 29000, ("year", "GBP"): 24000, ("year", "EUR"): 27000,
    },
    "studio": {
        ("month", "USD"): 9900, ("month", "GBP"): 7900, ("month", "EUR"): 8900,
        ("year", "USD"): 99000, ("year", "GBP"): 79000, ("year", "EUR"): 89000,
    },
    # Per seat, a year; no monthly price.
    "team": {("year", "USD"): 178800, ("year", "GBP"): 119000, ("year", "EUR"): 139000},
}
# The annual prices at 30 % off.
FOUNDING_YEAR = {
    ("pro", "USD"): 20300, ("pro", "GBP"): 16800, ("pro", "EUR"): 18900,
    ("studio", "USD"): 69300, ("studio", "GBP"): 55300, ("studio", "EUR"): 62300,
    ("team", "USD"): 125160, ("team", "GBP"): 83300, ("team", "EUR"): 97300,
}
# What the site shows for Team per seat per month: the annual charge / 12,
# billed annually (src/lib/catalogue.ts perMonthOfYear).
TEAM_PER_MONTH = {"USD": 14900, "GBP": 9917, "EUR": 11583}


def per_month_of_year(amount_minor: int) -> int:
    """Math.round(amount / 12), as the site rounds (halves up)."""
    return int(amount_minor / 12 + 0.5)


# --- the catalogue ----------------------------------------------------------------------


def test_pf2a_catalogue_prices_per_plan():
    tiers = {t["id"]: t for t in CATALOGUE["tiers"]}
    assert CATALOGUE["prices_final"] is True
    assert CATALOGUE["currencies"] == ["GBP", "USD", "EUR"]
    for tier_id, want in PLAN.items():
        got = {(p["interval"], p["currency"]): p["amount_minor"] for p in tiers[tier_id]["prices"]}
        assert got == want, tier_id
        assert len(tiers[tier_id]["prices"]) == len(want), f"{tier_id}: duplicate prices"
    assert tiers["free"]["prices"] == [] and not tiers["free"]["purchasable"]
    assert tiers["enterprise"]["prices"] == [] and not tiers["enterprise"]["purchasable"]
    assert (tiers["pro"]["per_seat"], tiers["studio"]["per_seat"], tiers["team"]["per_seat"]) == (False, False, True)
    assert tiers["team"]["min_seats"] == 2
    assert not any(p["interval"] == "month" for p in tiers["team"]["prices"]), "Team is never monthly"
    # The plan objects the API charges from read the same numbers.
    for tier_id, want in PLAN.items():
        assert {(p.interval, p.currency): p.amount_minor for p in PLANS[tier_id].prices} == want


def test_pf2a_founding_offer():
    f = CATALOGUE["founding"]
    assert f == {
        "total": 300,
        "discount_percent": 30,
        "ends_at": "2027-01-31T23:59:59Z",
        "tiers": ["pro", "studio", "team"],
        "intervals": ["year"],
    }
    assert FOUNDING.total == 300 and FOUNDING.discount_percent == 30
    assert FOUNDING.ends_at.isoformat() == "2027-01-31T23:59:59+00:00"
    for (tier_id, currency), founding in FOUNDING_YEAR.items():
        assert FOUNDING.discounted(PLANS[tier_id].price("year", currency).amount_minor) == founding
        assert FOUNDING.covers(tier_id, "year")
        assert not FOUNDING.covers(tier_id, "month"), "founding prices are the annual ones"
    assert not FOUNDING.covers("free", "year") and not FOUNDING.covers("enterprise", "year")


def test_pf2a_team_per_month_derived():
    """The per-month Team figure always matches the annual charge."""
    for currency, monthly in TEAM_PER_MONTH.items():
        yearly = PLANS["team"].price("year", currency).amount_minor
        assert per_month_of_year(yearly) == monthly, currency
        assert abs(monthly * 12 - yearly) < 12, currency
    # The owner's note said £119 and €139 a month: 12 x those is not the
    # annual charge, so the site derives the figure instead (As-built).
    assert 12 * 11900 != PLANS["team"].price("year", "GBP").amount_minor
    assert 12 * 13900 != PLANS["team"].price("year", "EUR").amount_minor


# --- the API ---------------------------------------------------------------------------


def test_pf2a_plans_endpoint_serves_the_plan(client):
    cat = client.get("/billing/plans").json()
    tiers = {t["id"]: t for t in cat["tiers"]}
    for tier_id, want in PLAN.items():
        got = {(p["interval"], p["currency"]): p["amount_minor"] for p in tiers[tier_id]["prices"]}
        assert got == want, tier_id
    assert tiers["enterprise"]["prices"] == []
    f = cat["founding"]
    assert (f["total"], f["remaining"], f["discount_percent"]) == (300, 300, 30)
    assert f["tiers"] == ["pro", "studio", "team"] and f["intervals"] == ["year"]
    assert f["ends_at"].startswith("2027-01-31T23:59:59")


def test_pf2a_team_monthly_checkout_is_400(client, paddle):
    h = signup(client)
    res = client.post("/billing/checkout", json=checkout_body(tier="team", interval="month", seats=2), headers=h)
    assert res.status_code == 400
    assert "no monthly price" in res.json()["detail"]
    assert client.get("/billing/payments", headers=h).json() == [], "nothing was started"
    co = start_checkout(client, h, tier="team", interval="year", seats=2)
    txn = paddle.STATE["transactions"][txn_of(co["url"])]
    item = txn["items"][0]
    assert item["quantity"] == 2 and item["price"]["billing_cycle"]["interval"] == "year"
    founding = FOUNDING_YEAR[("team", "GBP")]
    assert int(item["price"]["unit_price"]["amount"]) == founding and co["founding"] is True


def test_pf2a_team_change_to_monthly_is_400(client, paddle):
    h = signup(client)
    buy(client, h, paddle, tier="team", interval="year", seats=2)
    res = client.post("/billing/change", json={"interval": "month"}, headers=h)
    assert res.status_code == 400 and "no monthly price" in res.json()["detail"]
    assert client.get("/billing/subscription", headers=h).json()["interval"] == "year"

    # From Pro monthly, Team must be asked for annually.
    h2 = signup(client, email="two@example.com")
    buy(client, h2, paddle, tier="pro", interval="month")
    assert client.post("/billing/change", json={"tier": "team"}, headers=h2).status_code == 400
    res = client.post("/billing/change", json={"tier": "team", "interval": "year"}, headers=h2)
    assert res.status_code == 200, res.text
    assert (res.json()["tier"], res.json()["interval"], res.json()["seats"]) == ("team", "year", 2)


def test_pf2a_founding_is_annual_only(client, paddle):
    h = signup(client)
    monthly = start_checkout(client, h, tier="pro", interval="month", currency="USD")
    assert monthly["founding"] is False
    txn = paddle.STATE["transactions"][txn_of(monthly["url"])]
    assert int(txn["items"][0]["price"]["unit_price"]["amount"]) == PLAN["pro"][("month", "USD")]
    assert client.get("/billing/plans").json()["founding"]["remaining"] == 300, "no place held"

    yearly = start_checkout(client, h, tier="pro", interval="year", currency="USD")
    assert yearly["founding"] is True
    txn = paddle.STATE["transactions"][txn_of(yearly["url"])]
    assert int(txn["items"][0]["price"]["unit_price"]["amount"]) == 20300  # $203.00
    assert client.get("/billing/plans").json()["founding"]["remaining"] == 299


def test_pf2a_founding_ends_on_a_move_to_monthly(client, paddle):
    h = signup(client)
    buy(client, h, paddle, tier="studio", interval="year", currency="EUR")
    sub = client.get("/billing/subscription", headers=h).json()
    assert sub["founding"] is True and sub["interval"] == "year"
    res = client.post("/billing/change", json={"interval": "month"}, headers=h)
    assert res.status_code == 200, res.text
    assert (res.json()["interval"], res.json()["founding"]) == ("month", False)
    sub_id = local_sub().provider_subscription_id
    price = paddle.STATE["subscriptions"][sub_id]["items"][0]["price"]
    assert int(price["unit_price"]["amount"]) == PLAN["studio"][("month", "EUR")]
    # Its founding place stays taken.
    assert client.get("/billing/plans").json()["founding"]["remaining"] == 299


# --- sync_prices.py ---------------------------------------------------------------------


def expected_keys() -> set[str]:
    keys = set()
    for tier_id, prices in PLAN.items():
        for (interval, currency), amount in prices.items():
            keys.add(f"truebex_{tier_id}_{interval}_{currency.lower()}_{amount}")
    for (tier_id, currency), amount in FOUNDING_YEAR.items():
        keys.add(f"truebex_{tier_id}_year_{currency.lower()}_{amount}_founding")
    return keys


def run_main(argv: list[str]) -> str:
    from scripts import sync_prices

    out = io.StringIO()
    with redirect_stdout(out):
        assert sync_prices.main(argv) == 0
    return out.getvalue()


def test_pf2a_sync_prices_targets():
    from scripts import sync_prices

    targets = sync_prices.targets()
    assert {t.lookup_key for t in targets} == expected_keys()
    assert len(targets) == 24  # 6 + 6 + 3 list prices, 9 founding (annual)
    assert all(t.interval == "year" for t in targets if t.founding)
    assert not any(t.tier == "team" and t.interval == "month" for t in targets)
    assert all(t.per_seat and t.min_seats == 2 for t in targets if t.tier == "team")


def test_pf2a_sync_prices_paddle_regenerates(client, paddle):
    """Against tests/mock_paddle.py: a dry run on an empty account lists every
    price (founding included) without creating any; the sync creates them
    and retires the placeholder rows; a second dry run finds them all."""
    paddle.reset()
    with SessionLocal() as db:
        db.query(ProviderPrice).delete()
        # A placeholder-era price an old subscriber may still pay.
        db.add(ProviderPrice(provider="paddle", tier="pro", interval="month", currency="GBP",
                             amount_minor=7900, provider_price_id="pri_placeholder", founding=False, active=True))
        db.commit()

    out = run_main(["--provider", "paddle", "--env", "sandbox", "--dry-run"])
    assert "24 prices, 24 new" in out
    assert out.count("(would create)") == 24 and not paddle.STATE["prices"]
    for key in expected_keys():
        assert key in out, key

    out = run_main(["--provider", "paddle", "--env", "sandbox"])
    assert "24 prices, 24 new" in out
    assert len(paddle.STATE["prices"]) == 24
    by_key = {p["custom_data"]["lookup_key"]: p for p in paddle.STATE["prices"].values()}
    assert set(by_key) == expected_keys()
    pro_founding = by_key["truebex_pro_year_usd_20300_founding"]
    assert pro_founding["unit_price"] == {"amount": "20300", "currency_code": "USD"}
    assert pro_founding["billing_cycle"] == {"interval": "year", "frequency": 1}
    team = by_key["truebex_team_year_gbp_119000"]
    assert team["quantity"]["minimum"] == 2 and team["billing_cycle"]["interval"] == "year"
    with SessionLocal() as db:
        rows = list(db.scalars(select(ProviderPrice).where(ProviderPrice.provider == "paddle")))
        active = {(r.tier, r.interval, r.currency, r.amount_minor, r.founding) for r in rows if r.active}
        assert len(active) == 24
        old = next(r for r in rows if r.provider_price_id == "pri_placeholder")
        assert old.active is False and old.tier == "pro", "kept for old subscribers, never sold"

    out = run_main(["--provider", "paddle", "--env", "sandbox", "--dry-run"])
    assert "24 prices, 0 new" in out and "(would create)" not in out


def test_pf2a_sync_prices_stripe_dry_run(client, monkeypatch):
    """--dry-run against Stripe lists what it would create and creates nothing;
    with every lookup key present it finds them all."""
    existing: dict[str, str] = {}

    def price_list(api_key, lookup_keys, active, limit):
        assert len(lookup_keys) <= 10
        return {"data": [{"id": existing[k], "lookup_key": k} for k in lookup_keys if k in existing]}

    class _Products:
        def auto_paging_iter(self):
            return iter([{"id": "prod_pro", "metadata": {"truebex_tier": "pro"}}])

    def forbidden(**_kw):
        raise AssertionError("a dry run creates nothing")

    monkeypatch.setattr(stripe.Price, "list", price_list)
    monkeypatch.setattr(stripe.Product, "list", lambda **_kw: _Products())
    monkeypatch.setattr(stripe.Price, "create", forbidden)
    monkeypatch.setattr(stripe.Product, "create", forbidden)

    out = run_main(["--provider", "stripe", "--env", "sandbox", "--dry-run"])
    assert "24 prices, 24 new" in out and out.count("(would create)") == 24
    for key in expected_keys():
        assert key in out, key

    existing.update({k: f"price_{i}" for i, k in enumerate(sorted(expected_keys()))})
    out = run_main(["--provider", "stripe", "--env", "sandbox", "--dry-run"])
    assert "24 prices, 0 new" in out
    with SessionLocal() as db:
        assert not list(db.scalars(select(ProviderPrice).where(ProviderPrice.provider == "stripe"))), \
            "a dry run writes no provider_prices"


@pytest.mark.parametrize("tier_id", ["pro", "studio", "team"])
def test_pf2a_stripe_prices_cover_the_plan(stripe_prices, tier_id):
    for (interval, currency), amount in PLAN[tier_id].items():
        assert f"truebex_{tier_id}_{interval}_{currency.lower()}_{amount}" in stripe_prices
