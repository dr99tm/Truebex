"""PF7b: the "Buy this look" basket page (/market/basket/) the app's room
themes open (contract marketplace-api §3, the 2026-10-11 PR2 line).

* `POST /market/basket` (a platform route for the page, no credential):
  each line's product and supplier names, and the variant the URL's
  `default` stands for (contract §6.3: `default` for a single variant).
* The page then prices the lines through 5.5 and orders them through 5.7:
  the flow is exercised here with the variant ids the basket route resolved.
* `src/lib/basket.ts`: the `items` parser, run by Node (type stripping).
* The build check reads out/ after the verify gate's `npm run build`.

The catalogue is this file's own (market_helpers' style), not
tests/contracts/marketplace/products.json, which PF7c may replace."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.market.catalogue import create_supplier, set_supplier_regions
from app.market.common import now
from app.market.models import Product, ProductVariant, VariantAvailability, VariantPrice
from app.market.search import reindex
from app.market.taxonomy import active_regions

from .conftest import signup
from .licence_helpers import error_of
from .market_helpers import CONTRACT, payments_on, second_supplier, with_contract

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
BASKET_TS = ROOT / "src" / "lib" / "basket.ts"
NODE = shutil.which("node")
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")
NOINDEX = re.compile(r'<meta name="robots" content="[^"]*noindex')


def _pid(sku: str) -> str:
    return hashlib.sha256(f"pf7b {sku}".encode()).hexdigest()[:32]


def _product(db, supplier_id, sku, name, category, variants, *, status="approved", published=True):
    """variants: [(variant_id, options, {region: (amount, state)} , variant status)]."""
    regions = active_regions(db)
    p = Product(
        product_id=_pid(sku), supplier_id=supplier_id, sku=sku, name=name, kind="object", category=category,
        description="", images=[], includes=[], status=status,
    )  # fmt: skip
    p.approved_at = now() if published else None
    db.add(p)
    db.flush()
    for sort, (vid, options, offers, vstatus) in enumerate(variants):
        db.add(ProductVariant(
            product_id=p.product_id, variant_id=vid, sort=sort, options=options, materials=[], images=[],
            dims_mm=[900, 800, 900], status=vstatus,
        ))  # fmt: skip
        for code, (amount, state) in offers.items():
            r = regions[code]
            db.add(VariantPrice(
                product_id=p.product_id, variant_id=vid, region=code, amount=amount, currency=r.currency,
                exponent=r.exponent, includes_tax=True, tax_rate_bp=r.tax_rate_bp, delivery_fee=2500,
                delivery_days_min=3, delivery_days_max=7,
            ))  # fmt: skip
            if state:
                db.add(VariantAvailability(product_id=p.product_id, variant_id=vid, region=code, state=state, stock=3))
    return p


def _catalogue(*, ready: bool = False) -> str:
    """A verified supplier (GB) with the shapes a theme's basket meets."""
    with SessionLocal() as db:
        s = create_supplier(
            db, name="Kelda Home", country="GB", status="verified",
            connect_account_id="acct_kelda" if ready else None, connect_ready=ready,
        )  # fmt: skip
        set_supplier_regions(db, s, {"GB": active_regions(db)["GB"]})
        sid = s.supplier_id
        sofa = "furniture/seating/sofas"
        made = [
            # Several variants, the first out of stock: `default` → the first available one.
            _product(db, sid, "SOFA-KELDA", "Kelda sofa", sofa, [
                ("moss", {"colour": "Moss"}, {"GB": (99900, "out_of_stock")}, "active"),
                ("rust", {"colour": "Rust"}, {"GB": (104900, "in_stock")}, "active"),
                ("sand", {"colour": "Sand"}, {"GB": (109900, "in_stock")}, "active"),
            ]),
            # One variant with its own id: `default` → that one.
            _product(db, sid, "LAMP-ORB", "Orb floor lamp", "lighting", [
                ("brass", {"finish": "Brass"}, {"GB": (18900, "in_stock")}, "active"),
            ]),
            # A variant literally named `default` (the contract's single-variant name).
            _product(db, sid, "RUG-DUNE", "Dune rug", "furniture", [
                ("default", {}, {"GB": (32000, None)}, "active"),
            ]),
            # Discontinued, with a same-category product in stock as its substitute.
            _product(db, sid, "SOFA-OLD", "Fenn sofa", sofa, [
                ("grey", {"colour": "Grey"}, {"GB": (89900, "in_stock")}, "discontinued"),
            ]),
            # Published once, then withdrawn: named, never priced.
            _product(db, sid, "SHELF-GONE", "Tor shelf", "furniture", [
                ("oak", {}, {"GB": (15000, "in_stock")}, "active"),
            ], status="withdrawn"),
            # Never published: not revealed.
            _product(db, sid, "CHAIR-NEW", "Secret chair", "furniture", [
                ("default", {}, {"GB": (5000, "in_stock")}, "active"),
            ], status="pending_review", published=False),
        ]  # fmt: skip
        db.flush()
        for p in made:
            reindex(db, p, s)
        db.commit()
        return sid


def _ref(supplier: str, sku: str, variant: str) -> dict:
    return {"supplier_id": supplier, "sku": sku, "variant_id": variant}


def _basket(client, region: str, items: list[dict]):
    return client.post("/market/basket", json={"region": region, "items": items})


# --- POST /market/basket ---------------------------------------------------------------------


def test_basket_lines_named_and_default_resolved(client):
    sid = _catalogue()
    nobody = "0" * 32
    asked = [
        _ref(sid, "SOFA-KELDA", "default"),
        _ref(sid, "LAMP-ORB", "default"),
        _ref(sid, "RUG-DUNE", "default"),
        _ref(sid, "SOFA-KELDA", "sand"),
        _ref(sid, "SOFA-OLD", "grey"),
        _ref(sid, "SHELF-GONE", "oak"),
        _ref(sid, "CHAIR-NEW", "default"),
        _ref(sid, "LAMP-ORB", "chrome"),
        _ref(nobody, "NOPE", "default"),
    ]
    res = _basket(client, "gb", asked)  # region in any case, like 5.5
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["region"] == "GB"
    lines = body["items"]
    assert [(ln["sku"], ln["variant_id"]) for ln in lines] == [(a["sku"], a["variant_id"]) for a in asked]
    sofa, lamp, rug, sand, old, gone, secret, chrome, unknown = lines

    # Names for the page; the supplier takes requests for quote only (payments off).
    assert sofa["status"] == "found" and sofa["name"] == "Kelda sofa" and sofa["supplier_name"] == "Kelda Home"
    assert sofa["product_id"] == _pid("SOFA-KELDA") and sofa["kind"] == "object" and sofa["orderable"] is False
    # `default` on a product with several variants: the first one available in
    # the region (the app's DefaultVariant), and the choices to change it.
    assert sofa["variant"] == {"variant_id": "rust", "options": {"colour": "Rust"}, "resolved": "first"}
    assert [v["variant_id"] for v in sofa["variants"]] == ["moss", "rust", "sand"]
    assert sofa["variants"][0]["options"] == {"colour": "Moss"}
    # `default` on a single variant with its own id: that variant.
    assert lamp["variant"] == {"variant_id": "brass", "options": {"finish": "Brass"}, "resolved": "only"}
    assert "variants" not in lamp
    # A variant literally named `default`.
    assert rug["variant"]["variant_id"] == "default" and rug["variant"]["resolved"] == "asked"
    # An explicit variant is kept as asked.
    assert sand["variant"] == {"variant_id": "sand", "options": {"colour": "Sand"}, "resolved": "asked"}
    assert old["status"] == "found" and old["variant"]["variant_id"] == "grey"
    # Withdrawn after publication: named, so the page can say what is gone.
    assert gone["status"] == "withdrawn" and gone["name"] == "Tor shelf"
    # Never published, unknown variant, unknown product: not found; a
    # never-published product's name is never revealed.
    assert secret["status"] == "not_found" and secret.get("name") is None and secret.get("product_id") is None
    assert chrome["status"] == "not_found" and chrome["name"] == "Orb floor lamp" and chrome["variant"] is None
    assert unknown["status"] == "not_found" and unknown.get("name") is None


def test_basket_lines_orderable_follows_payments(client, monkeypatch):
    payments_on(monkeypatch)
    sid = _catalogue(ready=True)
    dune = second_supplier(ready=False, region="GB")
    res = _basket(client, "GB", [_ref(sid, "LAMP-ORB", "brass"), _ref(dune, "DUNE-ARM", "default")])
    assert res.status_code == 200, res.text
    lamp, chair = res.json()["items"]
    assert lamp["orderable"] is True
    assert chair["orderable"] is False and chair["supplier_name"] == "Dune Interiors"
    assert chair["variant"]["variant_id"] == "sand" and chair["variant"]["resolved"] == "only"


def test_basket_lines_validation(client):
    sid = _catalogue()
    one = _ref(sid, "LAMP-ORB", "default")
    # The page holds at most 100 lines (a theme's basket).
    assert _basket(client, "GB", [one] * 100).status_code == 200
    body = error_of(_basket(client, "GB", [one] * 101), 413, "too_large")
    assert body["data"]["max_items"] == 100
    error_of(_basket(client, "ZZ", [one]), 422, "validation_failed")
    error_of(_basket(client, "GB", [{**one, "supplier_id": "XYZ"}]), 422, "validation_failed")
    error_of(_basket(client, "GB", [{**one, "sku": "S" * 65}]), 422, "validation_failed")
    error_of(_basket(client, "GB", [{**one, "variant_id": ""}]), 422, "validation_failed")
    assert _basket(client, "GB", []).json() == {"region": "GB", "items": []}


def test_basket_lines_need_no_credential_and_are_rate_limited(client, monkeypatch):
    from app.config import get_settings

    sid = _catalogue()
    # No credential: the page prices a basket before anyone signs in.
    res = client.post("/market/basket", json={"region": "GB", "items": [_ref(sid, "LAMP-ORB", "brass")]})
    assert res.status_code == 200
    # A bad session token is not needed and not read.
    res = client.post(
        "/market/basket", json={"region": "GB", "items": []}, headers={"Authorization": "Bearer nonsense"}
    )
    assert res.status_code == 200
    # Catalogue reads per address (contract §7: 429 with retry_after_s).
    monkeypatch.setattr(get_settings(), "market_reads_per_minute", 2)
    from app import ratelimit

    ratelimit.reset()
    for _ in range(2):
        assert _basket(client, "GB", []).status_code == 200
    body = error_of(_basket(client, "GB", []), 429, "rate_limited")
    assert body["retry_after_s"] >= 1


def test_basket_flow_prices_then_orders(client, monkeypatch):
    """What the page does: names (basket route) → prices (5.5) → an order
    (5.7, Idempotency-Key, price_seen) → its checkout page; a changed price
    is 409 `price_changed` and the page prices again."""
    payments_on(monkeypatch)
    sid = _catalogue(ready=True)
    asked = [_ref(sid, "SOFA-KELDA", "default"), _ref(sid, "LAMP-ORB", "default"), _ref("f" * 32, "NOPE", "default")]
    described = _basket(client, "GB", asked).json()["items"]
    refs = [
        {**a, "variant_id": d["variant"]["variant_id"] if d["variant"] else a["variant_id"], "qty": q}
        for a, d, q in zip(asked, described, (1, 2, 1))
    ]
    priced = client.post("/market/prices", json={"region": "GB", "items": refs}, headers=CONTRACT).json()["items"]
    assert [p["price"]["amount"] if p["price"] else None for p in priced] == [104900, 18900, None]
    assert priced[2]["status"] == "not_found"

    h = with_contract(signup(client))
    lines = [
        {**r, "price_seen": {"amount": p["price"]["amount"], "currency": p["price"]["currency"]}}
        for r, p in zip(refs, priced)
        if p["price"]
    ]
    body = {
        "kind": "order", "region": "GB", "project": {},
        "contact": {"name": "Sam Reed", "email": "dev@example.com", "phone": None, "message": None},
        "delivery": {"country": "GB", "city": "Leeds", "postcode": "LS1 4AP", "address": "1 Park Row"},
        "lines": lines,
    }  # fmt: skip
    key = "a" * 32
    res = client.post("/market/orders", json=body, headers={**h, "Idempotency-Key": key})
    assert res.status_code == 201, res.text
    order = res.json()
    assert order["state"] == "awaiting_payment"
    assert order["checkout_url"].endswith(f"/market/checkout/?order={order['order_id']}")
    assert order["total"]["amount"] == 104900 + 2 * 18900 + 2500  # one delivery fee per supplier
    # The same key (a retried click) replays the first order.
    again = client.post("/market/orders", json=body, headers={**h, "Idempotency-Key": key})
    assert again.status_code == 201 and again.json()["order_id"] == order["order_id"]

    # The supplier changes a price: the page's next order is 409, nothing is made.
    with SessionLocal() as db:
        from sqlalchemy import select

        row = db.scalar(select(VariantPrice).where(VariantPrice.product_id == _pid("LAMP-ORB")))
        row.amount = 19900
        db.commit()
    res = client.post("/market/orders", json=body, headers={**h, "Idempotency-Key": "b" * 32})
    err = error_of(res, 409, "price_changed")
    assert err["data"]["lines"][0]["sku"] == "LAMP-ORB" and err["data"]["lines"][0]["price"]["amount"] == 19900


def test_basket_quote_only_supplier_sends_a_request(client):
    """Payments off (the default until GD5): every supplier is quote-only, so
    the page sends a request for quote, which answers `submitted`."""
    sid = _catalogue()
    described = _basket(client, "GB", [_ref(sid, "RUG-DUNE", "default")]).json()["items"]
    assert described[0]["orderable"] is False
    h = with_contract(signup(client))
    body = {
        "kind": "quote", "region": "GB", "project": {},
        "contact": {"name": "Sam Reed", "email": "dev@example.com"},
        "delivery": {"country": "GB", "city": "Leeds", "address": "1 Park Row"},
        "lines": [{**_ref(sid, "RUG-DUNE", "default"), "qty": 1, "price_seen": {"amount": 32000, "currency": "GBP"}}],
    }  # fmt: skip
    res = client.post("/market/orders", json=body, headers={**h, "Idempotency-Key": "c" * 32})
    assert res.status_code == 201, res.text
    assert res.json()["kind"] == "quote" and res.json()["state"] == "submitted"


# --- src/lib/basket.ts (the items parser) ----------------------------------------------------


def _run_basket_ts(script: str) -> dict:
    if NODE is None:
        pytest.skip("node is not installed")
    assert BASKET_TS.is_file(), "src/lib/basket.ts is missing"
    code = f"import * as b from {json.dumps(BASKET_TS.as_uri())};\n{script}"
    run = subprocess.run(
        [NODE, "--input-type=module", "-e", code],
        capture_output=True, text=True, timeout=60, cwd=ROOT, env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )  # fmt: skip
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


HEX = "f8afe1ba2b0bf97f23ef888f040cf46a"


def test_basket_parser_items():
    out = _run_basket_ts(
        """
const hex = "%s";
const enc = (s) => encodeURIComponent(s);
const q = (items, region = "GB") => "?region=" + region + "&items=" + enc(items);
const cases = {
  // What the app sends: the whole items value URL-encoded once (%%2C, %%3A).
  app: b.parseBasketQuery(q(`${hex}:SOFA-OSLO-3:oat-linen:1,${hex}:PAINT-CHALK:default:4`)),
  // Decoded once only: a SKU holding "%%3A" keeps it (%%253A on the wire).
  once: b.parseBasketQuery("?region=gb&items=" + hex + "%%3AA%%253AB%%3Adefault%%3A2"),
  // Already-decoded values (useSearchParams) parse the same way.
  plain: b.parseBasket("AE", `${hex.toUpperCase()}:SKU 1:v:99, ,`),
  bad: b.parseBasket("GB", [
    `${hex}:ONLY-THREE:2`,
    `xyz:SKU:v:1`,
    `${hex}0:SKU:v:1`,
    `${hex}:${"S".repeat(65)}:v:1`,
    `${hex}:SKU:${"V".repeat(65)}:1`,
    `${hex}:SKU:v:0`,
    `${hex}:SKU:v:100`,
    `${hex}:SKU:v:1.5`,
    `${hex}:SKU:v:-1`,
    `${hex}::v:1`,
    `${hex}:SKU::1`,
    `${hex}:${"S".repeat(64)}:${"V".repeat(64)}:1`,
  ].join(",")),
  dup: b.parseBasket("GB", `${hex}:A:x:2,${hex}:A:x:3,${hex}:A:y:1`),
  cap100: b.parseBasket("GB", Array.from({ length: 100 }, (_, i) => `${hex}:S${i}:default:1`).join(",")),
  cap101: b.parseBasket("GB", Array.from({ length: 101 }, (_, i) => `${hex}:S${i}:default:1`).join(",")),
  regions: ["gb", "US-CA", "", null, "G", "GBR", "gb;x"].map((r) => b.parseBasket(r, `${hex}:A:x:1`).region),
  empty: b.parseBasketQuery("?region=GB"),
  link: b.basketQuery("AE", [{ supplier_id: hex, sku: "A B", variant_id: "default", qty: 2 }]),
};
cases.back = b.parseBasketQuery(cases.link).items;
process.stdout.write(JSON.stringify(cases));
"""
        % HEX
    )
    app = out["app"]
    assert app["region"] == "GB" and app["rejected"] == [] and app["tooMany"] is None
    assert app["items"] == [
        {"supplier_id": HEX, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "qty": 1},
        {"supplier_id": HEX, "sku": "PAINT-CHALK", "variant_id": "default", "qty": 4},
    ]
    assert out["once"]["region"] == "GB"
    assert out["once"]["items"] == [{"supplier_id": HEX, "sku": "A%3AB", "variant_id": "default", "qty": 2}]
    # Upper-case hex is the same id (the wire's form is lower case); empty segments are skipped.
    assert out["plain"]["items"] == [{"supplier_id": HEX, "sku": "SKU 1", "variant_id": "v", "qty": 99}]
    assert out["plain"]["rejected"] == []

    bad = out["bad"]
    reasons = [(r["position"], r["reason"]) for r in bad["rejected"]]
    assert reasons == [
        (1, "malformed"), (2, "supplier"), (3, "supplier"), (4, "sku"), (5, "variant"),
        (6, "qty"), (7, "qty"), (8, "qty"), (9, "qty"), (10, "sku"), (11, "variant"),
    ]  # fmt: skip
    assert bad["rejected"][0]["text"] == f"{HEX}:ONLY-THREE:2"
    # 64 characters is still a SKU and a variant.
    assert bad["items"] == [{"supplier_id": HEX, "sku": "S" * 64, "variant_id": "V" * 64, "qty": 1}]

    # The same product and variant twice: one line with both quantities.
    assert out["dup"]["items"] == [
        {"supplier_id": HEX, "sku": "A", "variant_id": "x", "qty": 5},
        {"supplier_id": HEX, "sku": "A", "variant_id": "y", "qty": 1},
    ]
    assert len(out["cap100"]["items"]) == 100 and out["cap100"]["tooMany"] is None
    assert out["cap101"]["items"] == [] and out["cap101"]["tooMany"] == 101
    assert out["regions"] == ["GB", "US-CA", None, None, None, None, None]
    assert out["empty"]["items"] == [] and out["empty"]["rejected"] == [] and out["empty"]["tooMany"] is None
    # A link back to the basket (another region, the sign-in return) round-trips.
    assert out["link"] == f"?region=AE&items={HEX}%3AA%20B%3Adefault%3A2"
    assert out["back"] == [{"supplier_id": HEX, "sku": "A B", "variant_id": "default", "qty": 2}]


def test_basket_parser_totals_and_order_lines():
    out = _run_basket_ts(
        """
const gbp = (amount) => ({ amount, currency: "GBP", exponent: 2 });
const aed = (amount) => ({ amount, currency: "AED", exponent: 2 });
const lines = [
  { ref: { supplier_id: "s1", sku: "A", variant_id: "x" }, qty: 2, price: gbp(1000), included: true },
  { ref: { supplier_id: "s1", sku: "B", variant_id: "y" }, qty: 1, price: aed(500), included: true },
  { ref: { supplier_id: "s1", sku: "A", variant_id: "x" }, qty: 1, price: gbp(1000), included: true },
  { ref: { supplier_id: "s2", sku: "C", variant_id: "z" }, qty: 3, price: gbp(700), included: false },
  { ref: { supplier_id: "s3", sku: "D", variant_id: "w" }, qty: 1, price: null, included: true },
];
const key = b.newIdempotencyKey();
process.stdout.write(JSON.stringify({
  totals: b.totalsByCurrency(lines),
  order: b.orderLines(lines),
  key, other: b.newIdempotencyKey(),
  buyable: ["in_stock", "low_stock", "made_to_order", "out_of_stock", "discontinued", null].map((s) => b.canOrder(s)),
  label: [b.variantLabel({ size: "3-seater", colour: "Oat" }), b.variantLabel({})],
}));
"""
    )
    # Per currency, in the order first seen; excluded and unpriced lines left out.
    assert out["totals"] == [
        {"amount": 3000, "currency": "GBP", "exponent": 2},
        {"amount": 500, "currency": "AED", "exponent": 2},
    ]
    # One line per product and variant (5.7 refuses a line listed twice), with the price seen.
    assert out["order"] == [
        {"supplier_id": "s1", "sku": "A", "variant_id": "x", "qty": 3, "price_seen": {"amount": 1000, "currency": "GBP"}},
        {"supplier_id": "s1", "sku": "B", "variant_id": "y", "qty": 1, "price_seen": {"amount": 500, "currency": "AED"}},
    ]
    assert re.fullmatch(r"[0-9a-f]{32}", out["key"]) and out["key"] != out["other"]
    assert out["buyable"] == [True, True, True, False, False, True]
    assert out["label"] == ["3-seater, Oat", ""]


# --- the page (build check) ------------------------------------------------------------------


@built
def test_site_pf7b_basket_noindex():
    page = OUT / "market" / "basket" / "index.html"
    assert page.is_file(), "out/market/basket/index.html is missing"
    html = page.read_text(encoding="utf-8")
    assert NOINDEX.search(html)
    assert len(re.findall(r"<h1[\s>]", html)) == 1 and ">Buy this look</h1>" in html
    # Per person: no canonical to a crawlable URL (the root layout's "/" is dropped).
    assert '<link rel="canonical"' not in html
    # The basket is read in the browser (static export): the shell carries no line.
    assert "SOFA-OSLO-3" not in html
    sitemap = (OUT / "sitemap.xml").read_text(encoding="utf-8")
    assert "/market/basket" not in sitemap
    assert not re.search(r"<loc>[^<]*\.com/market/", sitemap)


def test_site_pf7b_copy_and_sources():
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")
    assert "export const MARKET_BASKET = {" in constants
    block = constants.split("export const MARKET_BASKET = {", 1)[1].split("} as const;", 1)[0]
    # Brand voice: no other product, engine or vendor named; no hype.
    assert not re.search(r"\b(unreal|unity|ikea|amazon|wayfair|houzz|stripe|paddle|AI)\b|!", block, re.I)
    assert '"Buy this look"' in block
    page = (ROOT / "src" / "app" / "market" / "basket" / "page.tsx").read_text(encoding="utf-8")
    assert "robots: { index: false, follow: false }" in page and "canonical: null" in page
    panel = (ROOT / "src" / "components" / "market" / "BasketPanel.tsx").read_text(encoding="utf-8")
    # Prices through 5.5, orders through 5.7 with an Idempotency-Key, then PF7's checkout page.
    client_ts = (ROOT / "src" / "lib" / "basket-api.ts").read_text(encoding="utf-8")
    assert '"/market/prices"' in client_ts and '"/market/orders"' in client_ts and '"/market/basket"' in client_ts
    assert '"Idempotency-Key"' in client_ts
    assert "/market/checkout/?order=" in panel and "/login/?next=" in panel and "/signup/?next=" in panel
    # The basket keeps PF7's dark theme tokens (no hard-coded colours).
    assert not re.search(r"#[0-9a-fA-F]{6}\b", panel)
