"""Marketplace API (PF7, contract marketplace-api v1.1): catalogue reads
5.1-5.6, orders and requests 5.7-5.10, checkout, webhooks and transfers.
The first seven tests are the contract's §10 platform tests."""

import hashlib
import json
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from app import ratelimit, tasks
from app.config import get_settings
from app.database import SessionLocal
from app.market import checkout, common, orders
from app.market.models import Commission, Supplier

from .conftest import signup
from .licence_helpers import Clock, error_of
from .market_helpers import (
    AKER,
    CONTRACT,
    FIXTURES,
    FJORD,
    SOFA,
    SUPPLIER_ID,
    FakeGateway,
    device_token,
    line,
    load,
    make_admin,
    order_body,
    payments_on,
    second_supplier,
    stripe_post,
    with_contract,
)

SERVER = Path(__file__).resolve().parents[1]
TAXONOMY = SERVER / "app" / "market" / "taxonomy" / "categories.json"
APP_TAXONOMY = Path(r"T:\unreal5_7_4_projects\truebex_compact\CAD\taxonomy\categories.json")
# Media URLs differ by the stored JPEG's hash and by the API origin (the
# fixtures carry https://api.truebex.com; this suite's API_URL is http://testserver).
_MEDIA = re.compile(r"(?:https?://[^/\"]+)?/market/media/(images|thumbs)/[0-9a-f]{64}\.jpg")


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _masked(value) -> str:
    return _MEDIA.sub("/market/media/<sha>.jpg", json.dumps(value, sort_keys=True))


def _gateway(monkeypatch) -> FakeGateway:
    fake = FakeGateway()
    monkeypatch.setattr(checkout, "gateway", lambda: fake)
    return fake


def _paid(client, monkeypatch, fake: FakeGateway, order_id: str, headers: dict) -> None:
    """Pay an order the way production does: checkout, then a signed webhook."""
    res = client.post(f"/market/checkout/{order_id}", headers=headers)
    assert res.status_code == 200, res.text
    sid = next(k for k, v in fake.sessions.items() if v["url"] == res.json()["url"])
    event = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": sid,
                "client_reference_id": order_id,
                "metadata": {"kind": "market_order", "order_id": order_id},
                "payment_status": "paid",
                "payment_intent": f"pi_{order_id[:8]}",
            }
        },
    }
    assert stripe_post(client, event).status_code == 200


# --- Contract §10 -----------------------------------------------------------------------------


def test_categories_root_on_app_taxonomy(client):
    load()
    res = client.get("/market/categories", headers=CONTRACT)
    assert res.status_code == 200, res.text
    body = res.json()
    raw = TAXONOMY.read_bytes()
    assert body["taxonomy_sha256"] == hashlib.sha256(raw).hexdigest()
    app_paths = {row["path"] for row in json.loads(raw)["categories"]}
    paths = {c["path"] for c in body["categories"]}
    for c in body["categories"]:
        assert c["app_path"] in app_paths, c
        assert c["path"] == c["app_path"] or c["path"].startswith(c["app_path"] + "/"), c
        # the deepest prefix the app knows
        parts = c["path"].split("/")
        deeper = ["/".join(parts[:n]) for n in range(len(parts), 0, -1)]
        assert next(p for p in deeper if p in app_paths) == c["app_path"]
        assert not c["path"].startswith("sheets")
    assert {"furniture", "furniture/seating", "furniture/seating/sofas", "decoration/themes"} <= paths
    counts = {c["path"]: c["products"] for c in body["categories"]}
    assert counts["furniture/seating/sofas"] == 1 and counts["furniture/tables/coffee-tables"] == 2
    assert counts["furniture"] == 3 and counts["finishes"] == 2
    # Cached by the app: ETag and a day.
    assert res.headers["Cache-Control"] == "public, max-age=86400"
    again = client.get("/market/categories", headers={**CONTRACT, "If-None-Match": res.headers["ETag"]})
    assert again.status_code == 304 and again.headers["X-Truebex-Contract"] == "marketplace-api/1.1"
    # The contract fixture is this server's answer.
    assert _fixture("categories")["body"] == body
    if APP_TAXONOMY.is_file():  # the copy is byte-identical to the app's file
        assert APP_TAXONOMY.read_bytes() == raw


def test_search_filters_and_region_prices(client):
    load()
    dune = second_supplier(region="AE")

    def search(**params):
        res = client.get("/market/search", params=params, headers=CONTRACT)
        assert res.status_code == 200, res.text
        return res.json()

    ae = search(q="sofa", category="furniture/seating", region="AE")
    assert [r["product_id"] for r in ae["results"]] == [SOFA["product_id"]]
    hit = ae["results"][0]
    assert hit["price"] == {**hit["price"], "amount": 129900, "currency": "AED", "exponent": 2, "includes_tax": True, "tax_rate_bp": 500}
    assert hit["app_path"] == "furniture/seating" and hit["dims_mm"] == [2100, 850, 950] and hit["variants"] == 2
    assert hit["supplier_name"] == "Nord Living" and hit["availability"]["state"] == "in_stock"
    assert ae["facets"] == {"category": {"furniture/seating/sofas": 1}, "supplier": {SUPPLIER_ID: 1}}

    gb = search(q="sofa", category="furniture/seating", region="GB")["results"][0]
    assert (gb["price"]["amount"], gb["price"]["currency"], gb["price"]["tax_rate_bp"]) == (129900, "GBP", 2000)

    # Subtree, facets across suppliers, availability, price range.
    furniture = search(category="furniture", region="AE")
    assert {r["name"] for r in furniture["results"]} == {"Oslo 3-seater sofa", "Aker coffee table", "Fjord coffee table", "Dune armchair"}
    assert furniture["facets"]["supplier"] == {SUPPLIER_ID: 3, dune: 1}
    assert furniture["facets"]["category"]["furniture/tables/coffee-tables"] == 2
    available = search(category="furniture", region="AE", available="true")
    assert "Aker coffee table" not in {r["name"] for r in available["results"]}
    ranged = search(region="GB", min=25000, max=30000)
    assert [r["name"] for r in ranged["results"]] == ["Fjord coffee table"]
    assert search(region="AE", supplier=dune)["facets"]["supplier"] == {dune: 1}
    assert {r["kind"] for r in search(region="GB", kind="finish")["results"]} == {"finish"}

    # Sorts.
    asc = [r["price"]["amount"] for r in search(region="GB", sort="price_asc")["results"]]
    assert asc == sorted(asc) and asc[0] == 1900
    desc = [r["price"]["amount"] for r in search(region="GB", sort="price_desc")["results"]]
    assert desc == sorted(desc, reverse=True)
    # GB excludes the AE-only supplier.
    assert dune not in search(region="GB")["facets"]["supplier"]

    # Text finds descriptions and materials too.
    assert {r["name"] for r in search(q="oak", region="GB")["results"]} >= {"Oslo 3-seater sofa", "Aker coffee table"}
    assert [r["name"] for r in search(q="linen")["results"]] == ["Oslo 3-seater sofa"]
    assert search(q="nothingmatchesthis")["results"] == []

    # Cursor pages cover everything once.
    seen, cursor = [], None
    while True:
        page = search(region="GB", limit=2, **({"cursor": cursor} if cursor else {}))
        seen += [r["product_id"] for r in page["results"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 6


def test_price_minor_units_and_tax(client):
    load()
    regions = client.get("/market/regions", headers=CONTRACT).json()["regions"]
    assert regions == _fixture("regions")["body"]["regions"]
    by = {r["region"]: r for r in regions}
    assert by["GB"]["tax"] == {"name": "VAT", "rate_bp": 2000, "prices_include_tax": True} and by["GB"]["currency"] == "GBP"
    assert by["AE"]["tax"]["rate_bp"] == 500 and by["AE"]["exponent"] == 2

    for region, currency, bp, fee in (("AE", "AED", 500, 15000), ("GB", "GBP", 2000, 4900)):
        res = client.get(f"/market/products/{SOFA['product_id']}", params={"region": region}, headers=CONTRACT)
        assert res.status_code == 200, res.text
        product = res.json()
        assert product["sku"] == "SOFA-OSLO-3" and product["brand"] == "Nord Living"
        assert product["classification"] == ["uniclass:Pr_40_50_12_81"] and product["app_path"] == "furniture/seating"
        for v in product["variants"]:
            p = v["price"]
            assert type(p["amount"]) is int and p["currency"] == currency and p["exponent"] == 2
            assert p["includes_tax"] is True and p["tax_rate_bp"] == bp and p["region"] == region
            assert v["delivery"]["fee"] == {"amount": fee, "currency": currency, "exponent": 2}
        oat = product["variants"][0]
        assert oat["gtin"] == "9501101530003" and oat["dims_mm"] == [2100, 850, 950]
        assert oat["geometry"]["asset"] == SOFA["variants"][0]["geometry"]["asset"]
        assert oat["geometry"]["format"] == "tbxa" and oat["availability"]["state"] in ("in_stock",)
        assert product["variants"][1]["availability"] == {
            "state": "made_to_order", "stock": None, "lead_time_days": 42, "updated_at": "2026-10-09T10:00:00Z",
        }  # fmt: skip

    # No float carries money anywhere in an answer.
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "amount":
                    assert type(v) is int, (k, v)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(product)
    # The geometry URL is signed (1 h) and served as an attachment with its hash.
    g = product["variants"][0]["geometry"]
    url = urlsplit(g["url"])
    res = client.get(f"{url.path}?{url.query}")
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
    assert hashlib.sha256(res.content).hexdigest() == g["sha256"] and len(res.content) == g["bytes"]

    # Money helpers: half-even integers (GD1 §4.2's illustration).
    assert common.parse_major("1299.00", 2) == 129900 and common.parse_major("5", 2) == 500
    for bad in ("1299.999", "1,299.00", "-1", "£12", "1e3", ""):
        with pytest.raises(ValueError):
            common.parse_major(bad, 2)
    assert common.net_of_tax(129900, 2000) == 108250 and common.apply_bp(108250, 1000) == 10825
    assert common.div_half_even(5, 2) == 2 and common.div_half_even(7, 2) == 4
    assert common.parse_percent_bp("20") == 2000 and common.parse_percent_bp("5.5") == 550


def test_batch_prices_and_substitutes(client):
    load()
    for region in ("ae", "gb"):
        fixture = _fixture(f"prices-{region}")
        res = client.post("/market/prices", json=fixture["request"]["body"], headers=CONTRACT)
        assert res.status_code == 200, res.text
        body = res.json()
        expected = dict(fixture["body"])
        for key in ("at", "stale_after"):
            body.pop(key), expected.pop(key)
        assert _masked(body) == _masked(expected)
    items = res.json()["items"]
    # Substitutes only for the discontinued line: the same category, orderable.
    assert [len(i["substitutes"]) for i in items] == [0, 0, 1, 0]
    assert items[2]["availability"]["state"] == "discontinued"
    assert items[2]["substitutes"][0]["sku"] == FJORD["sku"]
    at = common.aware(__import__("datetime").datetime.fromisoformat(res.json()["at"].replace("Z", "+00:00")))
    assert res.json()["stale_after"] == common.rfc3339(at + timedelta(hours=24))

    # 500 items in one call; 501 is too many.
    many = [{"supplier_id": SUPPLIER_ID, "sku": "PAINT-CHALK", "variant_id": "2-5l", "qty": 1}] * 500
    res = client.post("/market/prices", json={"region": "AE", "items": many}, headers=CONTRACT)
    assert res.status_code == 200 and len(res.json()["items"]) == 500
    error_of(client.post("/market/prices", json={"region": "AE", "items": many + many[:1]}, headers=CONTRACT), 413, "too_large")
    error_of(client.post("/market/prices", json={"region": "ZZ", "items": many[:1]}, headers=CONTRACT), 422, "validation_failed")
    error_of(client.post("/market/prices", json={"region": "AE", "items": [{"sku": "x"}]}, headers=CONTRACT), 422, "validation_failed")
    unknown = client.post(
        "/market/prices", json={"region": "AE", "items": [{**many[0], "sku": "NOPE"}]}, headers=CONTRACT
    ).json()["items"][0]
    assert unknown["price"] is None and unknown["status"] == "not_found"


def test_order_split_checkout_and_price_changed(client, monkeypatch):
    payments_on(monkeypatch)
    fake = _gateway(monkeypatch)
    load(payments_ready=True)
    dune = second_supplier(ready=True)
    h = with_contract(signup(client))

    lines = [line("SOFA-OSLO-3", "oat-linen", 1), line("DUNE-ARM", "sand", 2, supplier=dune)]
    res = client.post("/market/orders", json=order_body(lines=lines), headers=h)
    assert res.status_code == 201, res.text
    order = res.json()
    assert order["kind"] == "order" and order["state"] == "awaiting_payment"
    assert order["checkout_url"] == f"https://truebex.com/market/checkout/?order={order['order_id']}"
    groups = {g["supplier_id"]: g for g in order["suppliers"]}
    assert set(groups) == {SUPPLIER_ID, dune} and {g["state"] for g in groups.values()} == {"pending"}
    assert groups[SUPPLIER_ID]["subtotal"]["amount"] == 129900 and groups[SUPPLIER_ID]["delivery"]["amount"] == 15000
    assert groups[dune]["subtotal"]["amount"] == 420000 and groups[dune]["lines"] == 1
    assert order["total"] == {"amount": 129900 + 15000 + 420000 + 10000, "currency": "AED", "exponent": 2}
    # Tax inside the inclusive prices: 5 % VAT.
    assert groups[SUPPLIER_ID]["tax"]["amount"] == (129900 - common.net_of_tax(129900, 500)) + (15000 - common.net_of_tax(15000, 500))

    # The checkout page's Pay button: one Stripe session for both suppliers.
    res = client.post(f"/market/checkout/{order['order_id']}", headers=h)
    assert res.status_code == 200 and res.json()["url"].startswith("https://checkout.stripe.test/")
    params = fake.calls[-1][1]
    assert params["payment_intent_data"]["transfer_group"] == order["order_id"]
    assert params["client_reference_id"] == order["order_id"] and params["mode"] == "payment"
    assert sum(i["price_data"]["unit_amount"] * i["quantity"] for i in params["line_items"]) == order["total"]["amount"]
    assert params["success_url"].endswith(f"?order={order['order_id']}&paid=1")
    # Asking again reuses the open session.
    assert client.post(f"/market/checkout/{order['order_id']}", headers=h).json()["url"] == res.json()["url"]

    # A price the buyer saw that is no longer true: 409 with the new prices, no order.
    stale = {"amount": 120000, "currency": "AED", "exponent": 2}
    res = client.post("/market/orders", json=order_body(lines=[line("SOFA-OSLO-3", "oat-linen", 1, seen=stale)]), headers=h)
    body = error_of(res, 409, "price_changed")
    assert body["data"]["lines"][0]["price"]["amount"] == 129900 and body["data"]["lines"][0]["sku"] == "SOFA-OSLO-3"
    assert len(client.get("/market/orders", headers=h).json()["orders"]) == 1
    # The right price passes.
    ok = {"amount": 129900, "currency": "AED", "exponent": 2}
    assert client.post("/market/orders", json=order_body(lines=[line("SOFA-OSLO-3", "oat-linen", 1, seen=ok)]), headers=h).status_code == 201

    # A supplier that does not deliver there: 422 region_not_served.
    gb_only = order_body(region="GB", lines=[line("DUNE-ARM", "sand", 1, supplier=dune)])
    gb_only["delivery"]["country"] = "GB"
    body = error_of(client.post("/market/orders", json=gb_only, headers=h), 422, "region_not_served")
    assert body["data"]["suppliers"][0]["supplier_id"] == dune
    # Unavailable lines: discontinued.
    body = error_of(
        client.post("/market/orders", json=order_body(lines=[line("TABLE-AKER-CT", "default")]), headers=h), 409, "unavailable"
    )
    assert body["data"]["lines"][0]["reason"] == "discontinued"


def test_quote_lifecycle(client, monkeypatch):
    clk = Clock(monkeypatch)
    load()
    admin = make_admin(client)
    h = with_contract(signup(client))
    res = client.post("/market/orders", json=order_body("quote"), headers=h)
    assert res.status_code == 201, res.text
    quote = res.json()
    assert quote["kind"] == "quote" and quote["state"] == "submitted" and quote["checkout_url"] is None
    assert quote["suppliers"][0]["state"] == "submitted"
    assert quote["expires_at"] == common.rfc3339(clk.at + timedelta(days=30))

    # The supplier quotes (PF8's inbox; the admin page acts for it until then).
    res = client.post(
        f"/admin/market/orders/{quote['order_id']}/suppliers/{SUPPLIER_ID}/quote",
        json={"lines": [{"sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "unit_amount": 118000}], "delivery_fee": 15000, "message": "Assembled"},
        headers=admin,
    )
    assert res.status_code == 200, res.text
    seen = client.get(f"/market/orders/{quote['order_id']}", headers=h).json()
    assert seen["state"] == "quoted" and seen["suppliers"][0]["state"] == "quoted"
    assert seen["lines"][0]["quoted_price"]["amount"] == 118000 and seen["suppliers"][0]["quote"]["message"] == "Assembled"
    assert seen["total"]["amount"] == 118000 + 15000
    # Same shape as the stub's fixture (ids, times and image URLs aside).
    fixture = _fixture("order-quoted")["body"]
    assert set(seen) == set(fixture) and set(seen["suppliers"][0]) == set(fixture["suppliers"][0])

    # Accepted: it becomes an order (payments are off, so it is paid to the supplier directly).
    res = client.post(f"/market/orders/{quote['order_id']}/accept", headers=h)
    assert res.status_code == 201, res.text
    order = res.json()
    assert order["kind"] == "order" and order["quote_id"] == quote["order_id"] and order["state"] == "accepted"
    assert order["payment"] == "offline" and order["lines"][0]["quoted_price"]["amount"] == 118000
    after = client.get(f"/market/orders/{quote['order_id']}", headers=h).json()
    assert after["state"] == "accepted" and after["order_ref"] == order["order_id"]
    error_of(client.post(f"/market/orders/{quote['order_id']}/accept", headers=h), 409, "not_acceptable")

    # A request nobody accepts expires after 30 days.
    second = client.post("/market/orders", json=order_body("quote"), headers=h).json()
    clk.advance(days=31)
    tasks.run_due(clk.at, force=True)
    expired = client.get(f"/market/orders/{second['order_id']}", headers=h).json()
    assert expired["state"] == "expired" and expired["suppliers"][0]["state"] == "expired"
    assert client.get("/market/orders", params={"state": "expired"}, headers=h).json()["orders"][0]["order_id"] == second["order_id"]


def test_contract_header_and_error_envelope(client):
    load()
    res = client.get("/market/regions", headers=CONTRACT)
    assert res.status_code == 200 and res.headers["X-Truebex-Contract"] == "marketplace-api/1.1"
    # A 1.0 client is served (MINOR differences are additive); no header reads as current.
    assert client.get("/market/regions", headers={"X-Truebex-Contract": "marketplace-api/1.0"}).status_code == 200
    assert client.get("/market/regions").headers["X-Truebex-Contract"] == "marketplace-api/1.1"
    body = error_of(client.get("/market/regions", headers={"X-Truebex-Contract": "marketplace-api/2.0"}), 400, "contract_version")
    assert body["data"]["supported"] == ["marketplace-api/1.1"] and body["retry_after_s"] is None
    assert set(body) == {"detail", "code", "status", "request_id", "retry_after_s", "data"}
    error_of(client.get(f"/market/products/{'0' * 32}", headers=CONTRACT), 404, "not_found")
    error_of(client.get(f"/market/suppliers/{'0' * 32}", headers=CONTRACT), 404, "not_found")
    error_of(client.get("/market/orders/abc", headers=CONTRACT), 401, "unauthenticated")


# --- Platform tests -----------------------------------------------------------------------------


def test_market_reads_rate_limited(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "market_reads_per_minute", 5)
    now = [1000.0]
    monkeypatch.setattr(ratelimit, "clock", lambda: now[0])
    for _ in range(5):
        assert client.get("/market/regions", headers=CONTRACT).status_code == 200
    body = error_of(client.get("/market/search", headers=CONTRACT), 429, "rate_limited")
    assert isinstance(body["retry_after_s"], int) and body["retry_after_s"] >= 1
    assert client.post("/market/prices", json={"region": "AE", "items": []}, headers=CONTRACT).status_code == 429
    now[0] += 60
    assert client.get("/market/categories", headers=CONTRACT).status_code == 200


def test_market_search_validation(client):
    load()

    def bad(params: dict, field: str | None = None) -> None:
        body = error_of(client.get("/market/search", params=params, headers=CONTRACT), 422, "validation_failed")
        if field:
            assert body["data"]["fields"][0]["field"] == field, body

    bad({"category": "furniture/nope"}, "category")
    bad({"category": "sheets"}, "category")
    bad({"region": "ZZ"}, "region")
    bad({"limit": 101}, "limit")
    bad({"limit": 0}, "limit")
    bad({"region": "GB", "min": 500, "max": 100}, "min")
    bad({"min": -1}, "min")
    bad({"sort": "cheapest", "region": "GB"}, "sort")
    bad({"sort": "price_asc"}, "region")
    bad({"available": "true"}, "region")
    bad({"cursor": "not-a-cursor"}, "cursor")
    bad({"supplier": "xyz"}, "supplier")
    first = client.get("/market/search", params={"region": "GB", "limit": 1}, headers=CONTRACT).json()
    bad({"region": "AE", "limit": 1, "cursor": first["next_cursor"]}, "cursor")
    assert client.get("/market/search", params={"region": "GB", "limit": 100}, headers=CONTRACT).status_code == 200


def test_market_product_withdrawn(client):
    load()
    admin = make_admin(client)
    res = client.post(f"/admin/market/products/{AKER['product_id']}/withdraw", json={"reason": "recalled"}, headers=admin)
    assert res.status_code == 200, res.text
    body = error_of(client.get(f"/market/products/{AKER['product_id']}", params={"region": "AE"}, headers=CONTRACT), 410, "product_withdrawn")
    subs = body["data"]["substitutes"]
    assert [s["sku"] for s in subs] == [FJORD["sku"]] and subs[0]["price"]["currency"] == "AED"
    assert subs[0]["category"] == AKER["category"]
    # Gone from search and from 5.5 (a withdrawn line offers substitutes).
    names = {r["name"] for r in client.get("/market/search", params={"region": "AE"}, headers=CONTRACT).json()["results"]}
    assert "Aker coffee table" not in names
    line_ = client.post(
        "/market/prices",
        json={"region": "AE", "items": [{"supplier_id": SUPPLIER_ID, "sku": AKER["sku"], "variant_id": "default"}]},
        headers=CONTRACT,
    ).json()["items"][0]
    assert line_["status"] == "withdrawn" and line_["substitutes"][0]["sku"] == FJORD["sku"]
    # A suspended supplier's products are withdrawn too.
    res = client.patch(f"/admin/market/suppliers/{SUPPLIER_ID}", json={"status": "suspended", "reason": "test"}, headers=admin)
    assert res.status_code == 200
    error_of(client.get(f"/market/products/{SOFA['product_id']}", headers=CONTRACT), 410, "product_withdrawn")
    error_of(client.get(f"/market/suppliers/{SUPPLIER_ID}", headers=CONTRACT), 404, "not_found")
    error_of(client.get("/market/products/not-an-id", headers=CONTRACT), 404, "not_found")


def test_market_orders_auth_and_ownership(client, monkeypatch):
    payments_on(monkeypatch)
    fake = _gateway(monkeypatch)
    load(payments_ready=True)
    admin = make_admin(client)
    owner = signup(client, email="owner@example.com")
    other = with_contract(signup(client, email="other@example.com"))
    h = with_contract(owner)

    # 401 without a credential, and API keys are not accepted.
    for method, path in (("POST", "/market/orders"), ("GET", "/market/orders"), ("GET", f"/market/orders/{'a' * 32}"), ("POST", f"/market/orders/{'a' * 32}/cancel")):
        error_of(client.request(method, path, json=order_body(), headers=CONTRACT), 401, "unauthenticated")
    key = client.post("/keys", json={"name": "k"}, headers=owner).json()["key"]
    error_of(client.get("/market/orders", headers={**CONTRACT, "Authorization": f"Bearer {key}"}), 401, "unauthenticated")

    # The app's device token works for 5.7-5.10, for the same account.
    dev = device_token(client, owner)
    placed = client.post("/market/orders", json=order_body(), headers=dev)
    assert placed.status_code == 201, placed.text
    order_id = placed.json()["order_id"]
    assert [o["order_id"] for o in client.get("/market/orders", headers=h).json()["orders"]] == [order_id]
    assert client.get(f"/market/orders/{order_id}", headers=dev).json()["order_id"] == order_id

    # Another account's order is 403.
    error_of(client.get(f"/market/orders/{order_id}", headers=other), 403, "forbidden")
    error_of(client.post(f"/market/orders/{order_id}/cancel", headers=other), 403, "forbidden")
    error_of(client.post(f"/market/checkout/{order_id}", headers=other), 403, "forbidden")
    error_of(client.get(f"/market/orders/{'f' * 32}", headers=h), 404, "not_found")

    # Validation failures.
    error_of(client.post("/market/orders", json={**order_body(), "contact": {"name": "x"}}, headers=h), 422, "validation_failed")
    error_of(client.post("/market/orders", json=order_body(lines=[line("SOFA-OSLO-3", "oat-linen", 0)]), headers=h), 422, "validation_failed")
    wrong = order_body()
    wrong["delivery"]["country"] = "GB"
    error_of(client.post("/market/orders", json=wrong, headers=h), 422, "validation_failed")
    twice = order_body(lines=[line("SOFA-OSLO-3", "oat-linen"), line("SOFA-OSLO-3", "oat-linen")])
    error_of(client.post("/market/orders", json=twice, headers=h), 422, "validation_failed")
    error_of(client.get("/market/orders", params={"state": "lost"}, headers=h), 422, "validation_failed")

    # Cancel before any supplier accepts: fine. After acceptance: 409.
    first = client.post("/market/orders", json=order_body(), headers=h).json()
    res = client.post(f"/market/orders/{first['order_id']}/cancel", headers=h)
    assert res.status_code == 200 and res.json()["state"] == "cancelled"
    assert client.post(f"/market/orders/{first['order_id']}/cancel", headers=h).json()["state"] == "cancelled"
    _paid(client, monkeypatch, fake, order_id, h)
    assert client.post(f"/admin/market/orders/{order_id}/suppliers/{SUPPLIER_ID}/accept", headers=admin).status_code == 200
    error_of(client.post(f"/market/orders/{order_id}/cancel", headers=dev), 409, "not_cancellable")
    assert client.get(f"/market/orders/{order_id}", headers=h).json()["state"] == "accepted"

    # A paid order cancelled before acceptance is refunded in full.
    paid = client.post("/market/orders", json=order_body(), headers=h).json()
    _paid(client, monkeypatch, fake, paid["order_id"], h)
    assert client.post(f"/market/orders/{paid['order_id']}/cancel", headers=h).json()["state"] == "cancelled"
    assert fake.calls[-1][0] == "refund" and fake.calls[-1][1]["amount"] is None


def test_market_order_idempotency(client):
    load()
    h = with_contract(signup(client))
    key = "0123456789abcdef0123456789abcdef"
    first = client.post("/market/orders", json=order_body("quote"), headers={**h, "Idempotency-Key": key})
    again = client.post("/market/orders", json=order_body("quote"), headers={**h, "Idempotency-Key": key})
    assert first.status_code == again.status_code == 201
    assert again.json()["order_id"] == first.json()["order_id"] and again.headers["Idempotency-Replayed"] == "true"
    assert len(client.get("/market/orders", headers=h).json()["orders"]) == 1
    changed = order_body("quote", lines=[line("PAINT-CHALK", "2-5l", 3)])
    error_of(client.post("/market/orders", json=changed, headers={**h, "Idempotency-Key": key}), 409, "idempotency_mismatch")
    error_of(client.post("/market/orders", json=changed, headers={**h, "Idempotency-Key": "nope"}), 422, "validation_failed")
    # Another account may use the same key.
    other = with_contract(signup(client, email="b@example.com"))
    assert client.post("/market/orders", json=order_body("quote"), headers={**other, "Idempotency-Key": key}).json()["order_id"] != first.json()["order_id"]


def test_market_quote_only_supplier(client, monkeypatch):
    load(payments_ready=False)
    h = with_contract(signup(client))
    payments_on(monkeypatch)
    body = error_of(client.post("/market/orders", json=order_body(), headers=h), 409, "unavailable")
    assert body["data"]["reason"] == "quote_only" and body["data"]["lines"][0]["sku"] == "SOFA-OSLO-3"
    assert body["data"]["suppliers"] == [SUPPLIER_ID]
    assert client.post("/market/orders", json=order_body("quote"), headers=h).json()["state"] == "submitted"
    # The profile and search say so (a MINOR proposal: `orderable`).
    assert client.get(f"/market/suppliers/{SUPPLIER_ID}", headers=CONTRACT).json()["orderable"] is False
    # Onboarded, but payments switched off: still quote-only.
    with SessionLocal() as db:
        s = db.get(Supplier, SUPPLIER_ID)
        s.connect_account_id, s.connect_ready = "acct_1", True
        db.commit()
    assert client.post("/market/orders", json=order_body(), headers=h).status_code == 201
    monkeypatch.setattr(get_settings(), "market_payments_enabled", False)
    assert error_of(client.post("/market/orders", json=order_body(), headers=h), 409, "unavailable")["data"]["reason"] == "quote_only"


def test_market_checkout_webhook_marks_paid(client, monkeypatch):
    payments_on(monkeypatch)
    fake = _gateway(monkeypatch)
    load(payments_ready=True)
    h = with_contract(signup(client))
    order = client.post("/market/orders", json=order_body(), headers=h).json()
    url = client.post(f"/market/checkout/{order['order_id']}", headers=h).json()["url"]
    sid = url.rsplit("/", 1)[1]
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": sid, "metadata": {"kind": "market_order", "order_id": order["order_id"]}, "payment_status": "paid", "payment_intent": "pi_1"}},
    }
    # Unsigned or wrongly signed: 400, nothing changes.
    error_of(stripe_post(client, event, secret="whsec_wrong"), 400, "invalid_signature")
    assert client.get(f"/market/orders/{order['order_id']}", headers=h).json()["state"] == "awaiting_payment"
    # A session that is not the order's own is ignored.
    other = json.loads(json.dumps(event))
    other["data"]["object"]["id"] = "cs_forged"
    assert stripe_post(client, other).status_code == 200
    assert client.get(f"/market/orders/{order['order_id']}", headers=h).json()["state"] == "awaiting_payment"
    # Signed: paid; each supplier pending until it accepts.
    assert stripe_post(client, event).json() == {"received": "checkout.session.completed"}
    paid = client.get(f"/market/orders/{order['order_id']}", headers=h).json()
    assert paid["state"] == "paid" and paid["suppliers"][0]["state"] == "pending" and paid["checkout_url"] is None
    assert paid["paid_at"] is not None
    error_of(client.post(f"/market/checkout/{order['order_id']}", headers=h), 409, "conflict")

    # The buyer's return checks Stripe itself (a missed webhook).
    second = client.post("/market/orders", json=order_body(), headers=h).json()
    url = client.post(f"/market/checkout/{second['order_id']}", headers=h).json()["url"]
    fake.sessions[url.rsplit("/", 1)[1]].update(payment_status="paid", payment_intent="pi_2")
    assert client.post(f"/market/checkout/{second['order_id']}/refresh", headers=h).json()["state"] == "paid"

    # Connect onboarding finished: the supplier can take orders.
    with SessionLocal() as db:
        s = db.get(Supplier, SUPPLIER_ID)
        s.connect_account_id, s.connect_ready = "acct_nord", False
        db.commit()
    account = {"type": "account.updated", "data": {"object": {"id": "acct_nord", "payouts_enabled": True, "capabilities": {"transfers": "active"}}}}
    assert stripe_post(client, account).status_code == 200
    with SessionLocal() as db:
        assert db.get(Supplier, SUPPLIER_ID).connect_ready is True

    # Payments off: the checkout answers 503 and the webhook endpoint stays.
    error_of(client.post(f"/market/checkout/{'a' * 32}", headers=h), 404, "not_found")
    monkeypatch.setattr(get_settings(), "market_payments_enabled", False)
    third = client.post("/market/orders", json=order_body("quote"), headers=h).json()
    error_of(client.post(f"/market/checkout/{third['order_id']}", headers=h), 409, "conflict")
    monkeypatch.setattr(get_settings(), "stripe_connect_webhook_secret", "")
    error_of(stripe_post(client, event), 404, "not_found")


def test_market_transfers_after_acceptance(client, monkeypatch):
    clk = Clock(monkeypatch)
    payments_on(monkeypatch)
    fake = _gateway(monkeypatch)
    load(payments_ready=True)
    dune = second_supplier(ready=True)
    admin = make_admin(client)
    h = with_contract(signup(client))
    lines = [line("SOFA-OSLO-3", "oat-linen", 1), line("DUNE-ARM", "sand", 1, supplier=dune)]
    order = client.post("/market/orders", json=order_body(lines=lines), headers=h).json()
    _paid(client, monkeypatch, fake, order["order_id"], h)
    groups = {g["supplier_id"]: g for g in order["suppliers"]}

    # Nothing moves before a supplier accepts.
    tasks.run_due(clk.at, force=True)
    assert not [c for c in fake.calls if c[0] == "transfer"]

    assert client.post(f"/admin/market/orders/{order['order_id']}/suppliers/{SUPPLIER_ID}/accept", headers=admin).status_code == 200
    res = client.post(f"/admin/market/orders/{order['order_id']}/suppliers/{dune}/reject", json={"reason": "no stock"}, headers=admin)
    assert res.status_code == 200, res.text
    refund = [c for c in fake.calls if c[0] == "refund"][-1][1]
    assert refund["amount"] == groups[dune]["total"]["amount"] and refund["payment_intent"].startswith("pi_")

    tasks.run_due(clk.at, force=True)
    transfers = [c[1] for c in fake.calls if c[0] == "transfer"]
    assert len(transfers) == 1
    base = common.net_of_tax(129900, 500)  # goods excluding VAT and delivery (GD1 §4.2)
    commission = common.apply_bp(base, 1000)  # the placeholder 10 % of listing_plans.json
    assert transfers[0]["amount"] == groups[SUPPLIER_ID]["total"]["amount"] - commission
    assert transfers[0]["destination"] == "acct_fixture" and transfers[0]["transfer_group"] == order["order_id"]
    with SessionLocal() as db:
        rows = db.query(Commission).all()
        assert [(c.supplier_id, c.base, c.amount, c.rate_bp, c.state) for c in rows] == [(SUPPLIER_ID, base, commission, 1000, "accrued")]
    # Idempotent: no second transfer.
    tasks.run_due(clk.at + timedelta(minutes=10), force=True)
    assert len([c for c in fake.calls if c[0] == "transfer"]) == 1
    state = client.get(f"/market/orders/{order['order_id']}", headers=h).json()
    assert state["state"] == "accepted" and {g["supplier_id"]: g["state"] for g in state["suppliers"]} == {SUPPLIER_ID: "accepted", dune: "rejected"}

    # The month's statement (no PF2 invoice yet: pending).
    clk.advance(days=32)
    res = client.post("/admin/market/commissions/statements", headers=admin)
    statements = res.json()["statements"]
    assert len(statements) == 1 and statements[0]["commission"]["amount"] == commission and statements[0]["state"] == "pending"
    assert client.post("/admin/market/commissions/statements", headers=admin).json()["statements"] == []
    listed = client.get("/admin/market/commissions", headers=admin).json()
    assert listed["commissions"][0]["statement_id"] == statements[0]["statement_id"]


def test_market_supplier_profile_media_and_jobs(client, monkeypatch):
    clk = Clock(monkeypatch)
    load()
    profile = client.get(f"/market/suppliers/{SUPPLIER_ID}", headers=CONTRACT).json()
    assert profile == {
        "supplier_id": SUPPLIER_ID, "name": "Nord Living", "country": "GB", "website": "https://nordliving.example.com",
        "logo_url": None, "regions": ["AE", "GB"], "verified": True, "orderable": False,
    }  # fmt: skip
    hit = client.get("/market/search", params={"q": "sofa"}, headers=CONTRACT).json()["results"][0]
    thumb = urlsplit(hit["thumbnail_url"]).path
    res = client.get(thumb)
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
    assert "immutable" in res.headers["cache-control"] and res.content[:2] == b"\xff\xd8"
    assert client.get("/market/media/thumbs/../../secret.jpg").status_code == 404
    error_of(client.get("/market/media/thumbs/secret.jpg"), 404, "not_found")
    error_of(client.get(f"/market/media/other/{'a' * 64}.jpg"), 404, "not_found")

    # Unpaid orders are cancelled after 48 h; availability goes stale after 7 days.
    payments_on(monkeypatch)
    with SessionLocal() as db:
        s = db.get(Supplier, SUPPLIER_ID)
        s.connect_account_id, s.connect_ready = "acct_1", True
        db.commit()
    h = with_contract(signup(client))
    order = client.post("/market/orders", json=order_body(), headers=h).json()
    clk.advance(hours=49)
    tasks.run_due(clk.at, force=True)
    assert client.get(f"/market/orders/{order['order_id']}", headers=h).json()["state"] == "cancelled"
    clk.advance(days=8)
    tasks.run_due(clk.at, force=True)
    from app.market.models import VariantAvailability

    with SessionLocal() as db:
        assert all(a.stale for a in db.query(VariantAvailability).all())
    # Still found (stale availability only ranks lower).
    assert client.get("/market/search", params={"q": "sofa", "region": "AE"}, headers=CONTRACT).json()["results"]


def test_market_fixtures_up_to_date():
    """The contract fixtures are this server's answers (regenerated in a
    fresh process; image URLs masked)."""
    run = subprocess.run(
        [sys.executable, str(SERVER / "scripts" / "make_market_fixtures.py"), "--check"],
        capture_output=True, text=True, timeout=300, cwd=SERVER,
    )  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    assert orders.QUOTE_TTL == timedelta(days=30)
