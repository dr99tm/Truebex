"""Where PF7b (the "Buy this look" basket page and its POST /market/basket
route) meets PF7c (the app's own marketplace fixtures, MK1's catalogue in
tests/contracts/marketplace/, and 5.4 answering a theme's `includes` as
product ids): the app's theme THEME-CALM, read through 5.4 as PR2 reads it,
turned into the basket link's lines with `default` for each variant (the app
knows only the included products' ids), is named by the basket route and
priced through 5.5 at the prices the app's prices-<region>.json give. Its
Halden table is discontinued in the app's set, so the page offers the Fjord
table instead, and the order then goes through 5.7 on the app's catalogue."""

import json

import pytest

from app.database import SessionLocal
from app.market import seed

from .conftest import signup
from .licence_helpers import error_of
from .market_helpers import CONTRACT, CONTRACT_FIXTURES, payments_on, with_contract

STUB = json.loads((CONTRACT_FIXTURES / "products.json").read_text(encoding="utf-8"))
PRODUCTS = {p["product_id"]: p for p in STUB["products"]}
BY_SKU = {p["sku"]: p for p in STUB["products"]}
SUPPLIER_NAMES = {s["supplier_id"]: s["name"] for s in STUB["suppliers"]}
THEME = BY_SKU["THEME-CALM"]
FJORD = BY_SKU["TABLE-FJORD"]
# How the basket route resolves the app's `default` on each included product.
RESOLVED = {
    "SOFA-OSLO-3": ("oat-linen", "first"),  # two variants: the first orderable in the region
    "TABLE-HALDEN": ("walnut", "only"),  # one variant with its own id (discontinued)
    "PAINT-SAND-5L": ("default", "asked"),  # a variant named `default`
}


def _load_apps_catalogue(*, payments_ready: bool = False) -> None:
    with SessionLocal() as db:
        seed.load_catalogue(db, CONTRACT_FIXTURES, payments_ready=payments_ready)


def _theme_items(client) -> list[dict]:
    """The basket link's lines the app writes for THEME-CALM: each included
    product (5.4 by id) as <supplier hex>:<sku>:default."""
    theme = client.get(f"/market/products/{THEME['product_id']}", headers=CONTRACT)
    assert theme.status_code == 200, theme.text
    assert theme.json()["includes"] == THEME["includes"]
    items = []
    for pid in theme.json()["includes"]:
        product = client.get(f"/market/products/{pid}", headers=CONTRACT).json()
        items.append({"supplier_id": product["supplier_id"], "sku": product["sku"], "variant_id": "default"})
    return items


def _priced(client, region: str, items: list[dict], lines: list[dict]) -> tuple[list[dict], list[dict]]:
    """What the page sends to 5.5: each line with the variant the basket route resolved."""
    refs = [{**i, "variant_id": ln["variant"]["variant_id"], "qty": 1} for i, ln in zip(items, lines)]
    res = client.post("/market/prices", json={"region": region, "items": refs}, headers=CONTRACT)
    assert res.status_code == 200, res.text
    return refs, res.json()["items"]


@pytest.mark.parametrize("region", ["GB", "AE"])
def test_apps_theme_basket_named_and_priced_like_the_app(client, region):
    _load_apps_catalogue()
    items = _theme_items(client)
    assert [i["sku"] for i in items] == list(RESOLVED)

    res = client.post("/market/basket", json={"region": region, "items": items})
    assert res.status_code == 200, res.text
    lines = res.json()["items"]
    for line, pid in zip(lines, THEME["includes"]):
        want = PRODUCTS[pid]
        assert line["status"] == "found" and line["product_id"] == pid
        assert (line["name"], line["kind"]) == (want["name"], want["kind"])
        assert line["supplier_name"] == SUPPLIER_NAMES[want["supplier_id"]] == want["supplier_name"]
        variant_id, how = RESOLVED[line["sku"]]
        assert (line["variant"]["variant_id"], line["variant"]["resolved"]) == (variant_id, how)
        options = next(v["options"] for v in want["variants"] if v["variant_id"] == variant_id)
        assert line["variant"]["options"] == options
        assert line["orderable"] is False  # payments off: quote only
    # The sofa's other version is offered on the page.
    assert [v["variant_id"] for v in lines[0]["variants"]] == ["oat-linen", "charcoal-wool"]

    # 5.5 with the resolved variants answers the app's own prices for the region:
    # its prices-<region>.json where that names the line (not the paint), else products.json.
    _, priced = _priced(client, region, items, lines)
    want = json.loads((CONTRACT_FIXTURES / f"prices-{region.lower()}.json").read_text(encoding="utf-8"))
    by_line = {(i["supplier_id"], i["sku"], i["variant_id"]): i for i in want["items"]}
    assert [(p["sku"], (p["supplier_id"], p["sku"], p["variant_id"]) in by_line) for p in priced] == [
        ("SOFA-OSLO-3", True), ("TABLE-HALDEN", True), ("PAINT-SAND-5L", False),
    ]  # fmt: skip
    for p in priced:
        theirs = by_line.get((p["supplier_id"], p["sku"], p["variant_id"]))
        if theirs is None:
            v = next(v for v in BY_SKU[p["sku"]]["variants"] if v["variant_id"] == p["variant_id"])
            theirs = {"price": v["prices"][region], "availability": v["availability"], "substitutes": []}
        assert (p["price"], p["availability"]) == (theirs["price"], theirs["availability"])
        # D5: the platform's substitutes are objects; the app's file lists their ids.
        assert [s["product_id"] for s in p["substitutes"]] == theirs["substitutes"]
    # The discontinued table: the page's "Use this instead" is the Fjord table at its price.
    halden = priced[1]
    assert halden["availability"]["state"] == "discontinued"
    (sub,) = halden["substitutes"]
    assert (sub["product_id"], sub["supplier_id"], sub["sku"], sub["variant_id"]) == (
        FJORD["product_id"], FJORD["supplier_id"], FJORD["sku"], FJORD["variants"][0]["variant_id"],
    )  # fmt: skip
    assert sub["price"] == FJORD["variants"][0]["prices"][region]


def test_apps_theme_basket_orders_on_the_apps_catalogue(client, monkeypatch):
    payments_on(monkeypatch)
    _load_apps_catalogue(payments_ready=True)
    items = _theme_items(client)
    lines = client.post("/market/basket", json={"region": "GB", "items": items}).json()["items"]
    assert all(ln["orderable"] for ln in lines)
    refs, priced = _priced(client, "GB", items, lines)

    h = with_contract(signup(client, email="buyer@example.com"))

    def order(refs: list[dict], priced: list[dict], key: str):
        body = {
            "kind": "order", "region": "GB", "project": {},
            "contact": {"name": "Sam Reed", "email": "buyer@example.com", "phone": None, "message": None},
            "delivery": {"country": "GB", "city": "Leeds", "postcode": "LS1 4AP", "address": "1 Park Row"},
            "lines": [
                {**r, "price_seen": {"amount": p["price"]["amount"], "currency": p["price"]["currency"]}}
                for r, p in zip(refs, priced)
            ],
        }  # fmt: skip
        return client.post("/market/orders", json=body, headers={**h, "Idempotency-Key": key})

    # Ordered as the theme lists it: the discontinued table is refused (the page then prices again).
    err = error_of(order(refs, priced, "7b" * 16), 409, "unavailable")
    assert [(ln["sku"], ln["reason"]) for ln in err["data"]["lines"]] == [("TABLE-HALDEN", "discontinued")]

    # "Use this instead": the Fjord table in its place.
    sub = priced[1]["substitutes"][0]
    refs[1] = {"supplier_id": sub["supplier_id"], "sku": sub["sku"], "variant_id": sub["variant_id"], "qty": 1}
    priced = client.post("/market/prices", json={"region": "GB", "items": refs}, headers=CONTRACT).json()["items"]
    assert [p["availability"]["state"] for p in priced] == ["in_stock", "low_stock", "in_stock"]
    res = order(refs, priced, "7c" * 16)
    assert res.status_code == 201, res.text
    placed = res.json()
    assert placed["state"] == "awaiting_payment"
    assert placed["checkout_url"].endswith(f"/market/checkout/?order={placed['order_id']}")
    # One group per supplier (Nord Living: the sofa and the table; Gulf Paints: the paint).
    groups = {g["supplier_id"]: g for g in placed["suppliers"]}
    assert {sid: g["lines"] for sid, g in groups.items()} == {FJORD["supplier_id"]: 2, BY_SKU["PAINT-SAND-5L"]["supplier_id"]: 1}
    subtotal = sum(p["price"]["amount"] for p in priced)
    assert subtotal == sum(BY_SKU[r["sku"]]["variants"][0]["prices"]["GB"]["amount"] for r in refs)
    assert sum(g["subtotal"]["amount"] for g in groups.values()) == subtotal
    assert placed["total"]["amount"] == subtotal + sum(g["delivery"]["amount"] for g in groups.values())
    assert placed["total"]["currency"] == "GBP"
