"""PF7d: AU2's bedroom set (the Fjell double and single beds, the Nord
wardrobe and the Fjell bedside table; app commit 180b2d53) on the app's
catalogue, through PF7b's "Buy this look" basket route.

No theme in the app's products.json includes a bedroom product (the one
theme is MK1's Calm lounge, test_pf7b_pf7c_meet.py), so there is no theme
look to check; the test below fails when the app adds one, and that theme
then gets PF7b's basket test. The bedroom set itself is the look an auto
bedroom layout swaps its boxes for (AU2's `Layout.Products`): as basket lines
the app's link format allows, it is named by the basket route, priced through
5.5 at the app's prices-<region>.json and ordered through 5.7."""

import json

import pytest

from app.database import SessionLocal
from app.market import seed

from .conftest import signup
from .market_helpers import CONTRACT, CONTRACT_FIXTURES, payments_on, with_contract

STUB = json.loads((CONTRACT_FIXTURES / "products.json").read_text(encoding="utf-8"))
PRODUCTS = {p["product_id"]: p for p in STUB["products"]}
BY_SKU = {p["sku"]: p for p in STUB["products"]}
BEDROOM = ("BED-FJELL-160", "BED-FJELL-90", "WARDROBE-NORD-120", "BEDSIDE-FJELL")
NORD = STUB["suppliers"][0]["supplier_id"]


def _bedroom() -> list[dict]:
    missing = [sku for sku in BEDROOM if sku not in BY_SKU]
    assert not missing, f"the app's products.json has no {missing}"
    return [BY_SKU[sku] for sku in BEDROOM]


def _load_apps_catalogue(*, payments_ready: bool = False) -> None:
    with SessionLocal() as db:
        seed.load_catalogue(db, CONTRACT_FIXTURES, payments_ready=payments_ready)


def _items(variant: str | None = None) -> list[dict]:
    """The basket link's lines (<supplier hex>:<sku>:<variant>:1): `default`
    as the app writes it for a product whose variant it does not know, or
    each product's own variant id."""
    return [
        {"supplier_id": p["supplier_id"], "sku": p["sku"], "variant_id": variant or p["variants"][0]["variant_id"]}
        for p in _bedroom()
    ]


def test_no_theme_includes_the_bedroom_set():
    """Test 7's condition: a theme that includes a bedroom product would need
    PF7b's basket on that look. Today the app's one theme is MK1's."""
    bedroom = {p["product_id"] for p in _bedroom()}
    themes = {p["sku"]: p["includes"] for p in STUB["products"] if p["kind"] == "theme"}
    assert list(themes) == ["THEME-CALM"]
    assert [PRODUCTS[pid]["sku"] for pid in themes["THEME-CALM"]] == ["SOFA-OSLO-3", "TABLE-HALDEN", "PAINT-SAND-5L"]
    assert not any(bedroom & set(includes) for includes in themes.values())


@pytest.mark.parametrize("region", ["GB", "AE"])
def test_bedroom_set_basket_named_and_priced_like_the_app(client, region):
    _load_apps_catalogue()
    want = json.loads((CONTRACT_FIXTURES / f"prices-{region.lower()}.json").read_text(encoding="utf-8"))
    by_line = {(i["supplier_id"], i["sku"], i["variant_id"]): i for i in want["items"]}
    for variant in ("default", None):
        res = client.post("/market/basket", json={"region": region, "items": _items(variant)})
        assert res.status_code == 200, res.text
        lines = res.json()["items"]
        for line, p in zip(lines, _bedroom(), strict=True):
            (v,) = p["variants"]
            assert line["status"] == "found" and line["product_id"] == p["product_id"]
            assert (line["name"], line["kind"], line["supplier_name"]) == (p["name"], "object", "Nord Living")
            # One variant each: `default` resolves to it ("only").
            assert line["variant"] == {"variant_id": v["variant_id"], "options": v["options"], "resolved": "only" if variant else "asked"}
            assert "variants" not in line and line["orderable"] is False  # payments off: quote only

    # What the page then sends to 5.5: the app's own prices for the region, every line in stock.
    refs = [{**i, "qty": 1} for i in _items()]
    res = client.post("/market/prices", json={"region": region, "items": refs}, headers=CONTRACT)
    assert res.status_code == 200, res.text
    for line in res.json()["items"]:
        theirs = by_line[(line["supplier_id"], line["sku"], line["variant_id"])]
        assert (line["price"], line["availability"], line["substitutes"]) == (theirs["price"], theirs["availability"], [])
        assert line["price"]["currency"] == {"GB": "GBP", "AE": "AED"}[region]


def test_bedroom_set_orders_on_the_apps_catalogue(client, monkeypatch):
    payments_on(monkeypatch)
    _load_apps_catalogue(payments_ready=True)
    lines = client.post("/market/basket", json={"region": "AE", "items": _items("default")}).json()["items"]
    assert all(ln["orderable"] for ln in lines)
    refs = [{**i, "variant_id": ln["variant"]["variant_id"], "qty": 1} for i, ln in zip(_items("default"), lines)]
    priced = client.post("/market/prices", json={"region": "AE", "items": refs}, headers=CONTRACT).json()["items"]

    h = {**with_contract(signup(client, email="buyer@example.com")), "Idempotency-Key": "7d" * 16}
    body = {
        "kind": "order", "region": "AE", "project": {"name": "Bedroom", "project_id": None},
        "contact": {"name": "Layla Haddad", "email": "buyer@example.com", "phone": None, "message": None},
        "delivery": {"country": "AE", "city": "Dubai", "postcode": None},
        "lines": [{**r, "price_seen": p["price"]} for r, p in zip(refs, priced)],
    }  # fmt: skip
    res = client.post("/market/orders", json=body, headers=h)
    assert res.status_code == 201, res.text
    placed = res.json()
    assert placed["state"] == "awaiting_payment"
    assert placed["checkout_url"].endswith(f"/market/checkout/?order={placed['order_id']}")
    # One supplier (Nord Living) for all four; amounts are products.json's AED prices.
    (group,) = placed["suppliers"]
    assert (group["supplier_id"], group["lines"]) == (NORD, 4)
    subtotal = sum(p["variants"][0]["prices"]["AE"]["amount"] for p in _bedroom())
    assert subtotal == 94900 + 59900 + 119900 + 17900
    assert group["subtotal"] == {"amount": subtotal, "currency": "AED", "exponent": 2}
    assert placed["total"]["amount"] == subtotal + group["delivery"]["amount"]
    assert placed["total"]["currency"] == "AED"
