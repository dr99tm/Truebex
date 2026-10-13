"""PF7c: the platform's marketplace answers checked against the app's own
contract fixtures (contracts/marketplace-api.md §9). MK1 wrote them in the
app repo (Docs/roadmap/fixtures/contracts/marketplace/, app main 90799860);
they are copied byte for byte into tests/contracts/marketplace/.

The platform is seeded from the app's products.json (the stub's catalogue:
three suppliers, nine products, per-region prices and deliveries) and asked
what the stub answers from the same files. Only what is volatile is masked:
the ids and times the server mints, and URLs (the stub serves
https://market.truebex.com/files/<path>; the platform its own picture and
geometry links). Every other difference is asserted as the platform's
behaviour with its number in PF7c's As-built ("Differences",
docs/roadmap/40/PF7c-marketplace-fixtures-from-mk1.md), where the PATCH line
for the app side is written. PF7's own catalogue, which the older
marketplace tests count on, is tests/fixtures/market/.
"""

import hashlib
import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import func, select

from app.database import SessionLocal
from app.market import importer, media, seed
from app.market.common import format_major, is_hex32
from app.market.models import Product, Supplier
from app.models import User

from .conftest import signup
from .licence_helpers import error_of
from .market_helpers import CONTRACT, CONTRACT_FIXTURES, PRODUCT, SUPPLIER_ID, load, payments_on, png, with_contract
from .supplier_helpers import (
    admin_headers,
    as_supplier,
    key_headers,
    no_internet,
    post_feed,
    run_feeds,
    supplier_key,
    verified,
)

STUB = json.loads((CONTRACT_FIXTURES / "products.json").read_text(encoding="utf-8"))
PRODUCTS = {p["product_id"]: p for p in STUB["products"]}
BY_SKU = {p["sku"]: p for p in STUB["products"]}
NORD = STUB["suppliers"][0]["supplier_id"]
SOFA = BY_SKU["SOFA-OSLO-3"]
REGIONS = ("GB", "AE")
FILES = "https://market.truebex.com/files/"
# Keys the stub keeps in products.json but drops from 5.4 (its README).
STUB_ONLY = ("substitutes", "supplier_name", "thumbnail_url")
# The app's set as MK1 committed it (tests/contracts/marketplace/README.md).
APP_FILES = {
    "README.md", "categories.json", "regions.json", "products.json", "prices-gb.json", "prices-ae.json",
    "order-awaiting-payment.json", "order-quoted.json", "feed-two-regions.csv", "feed-two-regions.json",
    "feed-report.json",
    "geometry/sofa-oslo.tbxa", "geometry/sofa-oslo-charcoal.tbxa", "geometry/chair-bergen.tbxa",
    "geometry/sideboard-nord.tbxa", "geometry/light-arc.glb", "geometry/table-fjord.glb", "geometry/table-halden.glb",
    *(f"thumbs/{n}.png" for n in (
        "sofa-oslo", "sofa-oslo-charcoal", "chair-bergen", "table-halden", "table-fjord", "light-arc",
        "sideboard-nord", "paint-sand", "wallpaper-palm", "theme-calm",
    )),
}  # fmt: skip


def stub(name: str) -> dict:
    return json.loads((CONTRACT_FIXTURES / name).read_text(encoding="utf-8"))


def stub_file(url: str) -> bytes:
    """The fixture file a stub URL names (https://market.truebex.com/files/<path>)."""
    assert url.startswith(FILES), url
    return (CONTRACT_FIXTURES / url[len(FILES) :]).read_bytes()


def load_stub(*, payments_ready: bool = False, owner_email: str | None = None) -> list[str]:
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == owner_email)) if owner_email else None
        return [s.supplier_id for s in seed.load_catalogue(db, CONTRACT_FIXTURES, payments_ready=payments_ready, owner=owner)]


def counts_of(products: list[dict]) -> dict[str, int]:
    """Products per category path and every ancestor (5.1's `products`)."""
    out: dict[str, int] = {}
    for p in products:
        parts = p["category"].split("/")
        for n in range(1, len(parts) + 1):
            path = "/".join(parts[:n])
            out[path] = out.get(path, 0) + 1
    return out


def money(price: dict) -> dict:
    return {k: price[k] for k in ("amount", "currency", "exponent")}


def when(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def projected(p: dict, region: str) -> dict:
    """What the stub answers for 5.4 `?region=`: the product without its
    stub-only keys, each variant's `prices` / `deliveries` lists projected to
    §6.1's `price` / `delivery` for the region."""
    out = {k: v for k, v in p.items() if k not in STUB_ONLY}
    out["variants"] = []
    for v in p["variants"]:
        pv = {k: x for k, x in v.items() if k not in ("prices", "deliveries")}
        pv["price"], pv["delivery"] = v["prices"][region], v["deliveries"][region]
        out["variants"].append(pv)
    return out


def order_request(kind: str) -> dict:
    """5.7 for the Oslo sofa (oat-linen) in AE, as the app sends it."""
    oat = SOFA["variants"][0]
    return {
        "kind": kind,
        "region": "AE",
        "project": {"name": "House", "project_id": None},
        "contact": {"name": "Layla Haddad", "email": "buyer@example.com", "phone": None, "message": "Delivery after 1 Dec"},
        "delivery": {"country": "AE", "city": "Dubai", "postcode": None},
        "lines": [{"supplier_id": NORD, "sku": SOFA["sku"], "variant_id": oat["variant_id"], "qty": 1, "price_seen": oat["prices"]["AE"]}],
    }


def assert_groups_like_the_stub(mine: dict, want: dict) -> None:
    """5.7 / 5.9's supplier groups and total. D7: `subtotal` and `total` are
    money {amount, currency, exponent} on the platform (its order also names
    `region`, and each group its `tax`); the stub writes a §6.3 price there."""
    assert len(mine["suppliers"]) == len(want["suppliers"])
    for g, w in zip(mine["suppliers"], want["suppliers"]):
        assert (g["supplier_id"], g["state"], g["lines"]) == (w["supplier_id"], w["state"], w["lines"])
        assert g["delivery"] == w["delivery"]
        assert g["subtotal"] == money(w["subtotal"])
        assert set(w["subtotal"]) - set(g["subtotal"]) == {"region", "includes_tax", "tax_rate_bp", "at"}
    assert mine["total"] == money(want["total"])
    assert mine["region"] == want["total"]["region"] == "AE"


# --- The copy ---------------------------------------------------------------------------------


def test_contract_folder_is_the_apps_copy():
    """tests/contracts/marketplace/ holds the app's set and nothing else
    (PF7's catalogue moved to tests/fixtures/market/); its geometry is the
    bytes products.json names."""
    files = {p.relative_to(CONTRACT_FIXTURES).as_posix() for p in CONTRACT_FIXTURES.rglob("*") if p.is_file()}
    assert files == APP_FILES
    assert STUB["schema"] == "truebex-market-stub/1"
    assert len(STUB["suppliers"]) == 3 and len(STUB["products"]) == 9
    # Copied as the app's blobs: no line ending converted on the way.
    for rel in APP_FILES:
        if rel.endswith((".json", ".csv", ".md")):
            assert b"\r" not in (CONTRACT_FIXTURES / rel).read_bytes(), rel
    named = {}
    for p in STUB["products"]:
        for v in p["variants"]:
            if v.get("geometry"):
                g = v["geometry"]
                named[g["url"][len(FILES) :]] = (g["sha256"], g["bytes"], g["format"])
    assert set(named) == {f for f in APP_FILES if f.startswith("geometry/")}
    for rel, (sha, size, fmt) in named.items():
        data = (CONTRACT_FIXTURES / rel).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (sha, size), rel
        assert rel.endswith(f".{fmt}")
        if fmt == "tbxa":  # the app's serializer: one line of JSON, no newline
            assert b"\n" not in data and json.loads(data)["assetVersion"] == 1
        else:
            assert data[:4] == b"glTF"
    from PIL import Image

    for rel in (f for f in APP_FILES if f.startswith("thumbs/")):
        with Image.open(CONTRACT_FIXTURES / rel) as img:
            assert img.format == "PNG" and min(img.size) >= 512, rel


# --- The seed ---------------------------------------------------------------------------------


def test_seed_reads_the_apps_catalogue(client, capsys):
    """seed_market.py --fixture with the app's set: its three suppliers
    (verified) and nine products (approved), each found by 5.3 with the price
    products.json gives it in GB and AE. A second run changes nothing."""
    from scripts import seed_market

    for _ in range(2):
        assert seed_market.main(["--fixture", str(CONTRACT_FIXTURES)]) == 0
    out = capsys.readouterr().out
    for s in STUB["suppliers"]:
        assert f"supplier {s['name']} ({s['supplier_id']}): verified" in out
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Supplier)) == 3
        assert {p.product_id: p.status for p in db.scalars(select(Product))} == {pid: "approved" for pid in PRODUCTS}

    listed = client.get("/market/search", params={"region": "GB", "limit": 100}, headers=CONTRACT).json()
    assert sorted(r["product_id"] for r in listed["results"]) == sorted(PRODUCTS)
    for p in STUB["products"]:
        for region in REGIONS:
            res = client.get("/market/search", params={"q": p["name"], "region": region}, headers=CONTRACT)
            assert res.status_code == 200, res.text
            hit = next(h for h in res.json()["results"] if h["product_id"] == p["product_id"])
            assert (hit["supplier_id"], hit["supplier_name"], hit["name"], hit["kind"]) == (
                p["supplier_id"], p["supplier_name"], p["name"], p["kind"],
            )  # fmt: skip
            assert (hit["category"], hit["app_path"], hit["variants"]) == (p["category"], p["app_path"], len(p["variants"]))
            assert hit["price"] in [v["prices"][region] for v in p["variants"]]
            assert hit["price"]["currency"] == {"GB": "GBP", "AE": "AED"}[region]
    # "sofa" in AE: the sofa first (a name hit), with the AED price products.json
    # gives its first variant, then the theme whose description names it.
    ae = client.get("/market/search", params={"q": "sofa", "region": "AE"}, headers=CONTRACT).json()["results"]
    assert [h["product_id"] for h in ae] == [SOFA["product_id"], BY_SKU["THEME-CALM"]["product_id"]]
    assert ae[0]["price"] == SOFA["variants"][0]["prices"]["AE"]


# --- 5.1, 5.2 ---------------------------------------------------------------------------------


def test_categories_like_the_stub(client):
    load_stub()
    res = client.get("/market/categories", headers=CONTRACT)
    assert res.status_code == 200, res.text
    body, want = res.json(), stub("categories.json")
    # D16: equal, but both are the hash of the app's taxonomy file as checked out with CRLF.
    assert body["taxonomy_sha256"] == want["taxonomy_sha256"]
    got = {c["path"]: c for c in body["categories"]}
    counts = counts_of(STUB["products"])
    # D3: an app path's label is the app's taxonomy file's own (CAD/taxonomy/categories.json: "Wall").
    labels = {"lighting/wall": "Wall"}
    for c in want["categories"]:
        mine = got.pop(c["path"])  # D2: the seed adds the stub's two paths the platform's tree lacks
        assert (mine["app_path"], mine["label"]) == (c["app_path"], labels.get(c["path"], c["label"])), c
        assert mine["products"] == counts[c["path"]], c
        if c["path"] != "furniture":
            assert c["products"] == mine["products"], c
    # D1: the stub's categories.json says 6 under furniture; products.json files 5 there.
    assert next(c for c in want["categories"] if c["path"] == "furniture")["products"] == 6
    assert counts["furniture"] == 5
    # D4: 5.1 is the platform's whole tree; the rest of it holds no fixture product.
    assert got and all(c["products"] == 0 for c in got.values())


def test_regions_like_the_stub(client):
    res = client.get("/market/regions", headers=CONTRACT)
    assert res.status_code == 200 and res.json() == stub("regions.json")


# --- 5.5 --------------------------------------------------------------------------------------


@pytest.mark.parametrize("region", REGIONS)
def test_batch_prices_like_the_stub(client, region):
    load_stub()
    want = stub(f"prices-{region.lower()}.json")
    request = {
        "region": region,
        "items": [{"supplier_id": i["supplier_id"], "sku": i["sku"], "variant_id": i["variant_id"], "qty": 1} for i in want["items"]],
    }
    res = client.post("/market/prices", json=request, headers=CONTRACT)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["region"] == want["region"] == region
    for answer in (body, want):  # masked: when the answer was made; stale 24 h later on both
        assert when(answer["stale_after"]) - when(answer["at"]) == timedelta(hours=24)
    assert len(body["items"]) == len(want["items"])
    for mine, theirs in zip(body["items"], want["items"]):
        # D5: a substitute is an object on the platform (product_id, supplier_id,
        # sku, variant_id, name, category, thumbnail_url, price, availability);
        # the stub lists product ids.
        subs = mine["substitutes"]
        assert [s["product_id"] for s in subs] == theirs["substitutes"]
        for s in subs:
            sub = PRODUCTS[s["product_id"]]
            assert (s["sku"], s["category"]) == (sub["sku"], sub["category"])
            assert s["price"] == next(v["prices"][region] for v in sub["variants"] if v["variant_id"] == s["variant_id"])
        assert mine.pop("qty") == 1  # the request's quantity, echoed (readers ignore unknown keys, §3)
        assert {**mine, "substitutes": theirs["substitutes"]} == theirs
    halden = next(i for i in body["items"] if i["sku"] == "TABLE-HALDEN")
    assert halden["availability"]["state"] == "discontinued" and halden["substitutes"]


# --- 5.7, 5.9 ---------------------------------------------------------------------------------


def test_order_awaiting_payment_like_the_stub(client, monkeypatch):
    payments_on(monkeypatch)
    load_stub(payments_ready=True)
    want = stub("order-awaiting-payment.json")
    h = {**with_contract(signup(client, email="buyer@example.com")), "Idempotency-Key": "0d3e" * 8}
    res = client.post("/market/orders", json=order_request("order"), headers=h)
    assert res.status_code == 201, res.text
    mine = res.json()
    assert is_hex32(mine["order_id"]) and is_hex32(want["order_id"])  # masked: minted
    assert (mine["kind"], mine["state"]) == (want["kind"], want["state"]) == ("order", "awaiting_payment")
    # D6: checkout_url is the static site's page with the order in the query;
    # the stub puts the id in the path (a page the static export cannot serve).
    url, theirs = urlsplit(mine["checkout_url"]), urlsplit(want["checkout_url"])
    assert (url.scheme, url.netloc) == (theirs.scheme, theirs.netloc) == ("https", "truebex.com")
    assert url.path == "/market/checkout/" and parse_qs(url.query) == {"order": [mine["order_id"]]}
    assert theirs.path == f"/market/checkout/{want['order_id']}" and not theirs.query
    assert_groups_like_the_stub(mine, want)
    assert want["total"]["amount"] == want["suppliers"][0]["subtotal"]["amount"] + want["suppliers"][0]["delivery"]["amount"]
    # 5.9 answers the same order the same way.
    again = client.get(f"/market/orders/{mine['order_id']}", headers=h).json()
    assert_groups_like_the_stub(again, want)
    assert again["checkout_url"] == mine["checkout_url"]


def test_order_quoted_like_the_stub(client):
    signup(client, email="owner@nord.example.com")
    load_stub(owner_email="owner@nord.example.com")
    owner = client.post("/auth/login", json={"email": "owner@nord.example.com", "password": "password123"}).json()
    owner = as_supplier({"Authorization": f"Bearer {owner['access_token']}"}, NORD)
    want = stub("order-quoted.json")
    h = with_contract(signup(client, email="buyer@example.com"))
    res = client.post("/market/orders", json=order_request("quote"), headers=h)
    assert res.status_code == 201, res.text
    placed = res.json()
    assert placed["state"] == "submitted" and placed["checkout_url"] is None
    # Nord Living quotes in its inbox (PF8): the stub's quoted subtotal, no delivery fee.
    quoted = want["suppliers"][0]
    body = {
        "lines": [{"sku": SOFA["sku"], "variant_id": "oat-linen", "price": format_major(quoted["subtotal"]["amount"], 2)}],
        "delivery_fee": format_major(quoted["delivery"]["amount"], 2),
    }
    res = client.post(f"/supplier/inbox/{placed['order_id']}/quote", json=body, headers=owner)
    assert res.status_code == 200, res.text
    mine = client.get(f"/market/orders/{placed['order_id']}", headers=h).json()
    assert is_hex32(mine["order_id"]) and is_hex32(want["order_id"])  # masked: minted
    assert (mine["kind"], mine["state"], mine["checkout_url"]) == (want["kind"], want["state"], want["checkout_url"])
    assert_groups_like_the_stub(mine, want)


# --- 5.11-5.13 --------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["csv", "json"])
def test_feed_import_like_the_stub_report(client, monkeypatch, fmt):
    """The app's feed (the Oslo sofa, GB and AE) through 5.11 into an empty
    catalogue gives feed-report.json; approved, 5.4 serves the stub's sofa."""
    no_internet(monkeypatch, seed.media_fetcher(CONTRACT_FIXTURES))
    owner, sid = verified(client)
    key = supplier_key(client, owner)
    res = post_feed(client, key, (CONTRACT_FIXTURES / f"feed-two-regions.{fmt}").read_bytes(), fmt)
    assert res.status_code == 202, res.text
    run_feeds()
    mine = client.get(f"/market/feeds/{res.json()['feed_id']}", headers=key_headers(key)).json()
    want = stub("feed-report.json")
    assert is_hex32(mine["feed_id"]) and is_hex32(want["feed_id"])  # masked: minted
    # D8: `created` counts rows on the platform (§5.13's example adds up:
    # created + updated + unchanged + rejected = rows); the stub's report
    # counts the one product the rows make.
    assert (mine["rows"], mine["created"], want["rows"], want["created"]) == (4, 4, 4, 1)
    assert mine["created"] + mine["updated"] + mine["unchanged"] + mine["rejected"] == mine["rows"]
    same = [k for k in want if k not in ("feed_id", "created")]
    assert {k: mine[k] for k in same} == {k: want[k] for k in same}
    assert mine["warnings"] == []

    with SessionLocal() as db:
        product = db.scalar(select(Product).where(Product.supplier_id == sid))
        assert (product.sku, product.status) == (SOFA["sku"], "pending_review")
        pid = product.product_id
    assert client.post(f"/admin/market/products/{pid}/approve", headers=admin_headers(client)).status_code == 200
    for region in REGIONS:
        got = client.get(f"/market/products/{pid}", params={"region": region}, headers=CONTRACT).json()
        expected = projected(SOFA, region)
        assert (got["name"], got["category"], got["description"], got["brand"]) == (
            expected["name"], expected["category"], expected["description"], expected["brand"],
        )  # fmt: skip
        for v, w in zip(got["variants"], expected["variants"], strict=True):
            assert (v["variant_id"], v["gtin"], v["options"], v["dims_mm"]) == (w["variant_id"], w["gtin"], w["options"], w["dims_mm"])
            assert {**v["price"], "at": None} == {**w["price"], "at": None}  # masked: stamped at import
            assert v["delivery"] == w["delivery"]
            assert {**v["availability"], "updated_at": None} == {**w["availability"], "updated_at": None}
            assert (v["geometry"]["format"], v["geometry"]["sha256"], v["geometry"]["bytes"]) == (
                w["geometry"]["format"], w["geometry"]["sha256"], w["geometry"]["bytes"],
            )  # fmt: skip
            # D9: the app's feed files describe the sofa differently from
            # products.json: the CSV has no `classification` column, the JSON
            # feed no `materials` (contract §6.4 lists no such JSON key).
            assert v["materials"] == (w["materials"] if fmt == "csv" else [])
        assert got.get("classification") == (None if fmt == "csv" else SOFA["classification"])


# --- 5.4, 5.6 ---------------------------------------------------------------------------------


def test_products_and_suppliers_like_the_stub(client):
    load_stub()
    for p in STUB["products"]:
        for region in REGIONS:
            res = client.get(f"/market/products/{p['product_id']}", params={"region": region}, headers=CONTRACT)
            assert res.status_code == 200, res.text
            mine, want = res.json(), projected(p, region)
            # Extras the platform serves (readers ignore unknown keys, §3; PF7's MINOR proposals).
            assert mine.pop("supplier_name") == p["supplier_name"]
            assert mine.pop("thumbnail_url").startswith("http://testserver/market/media/thumbs/")
            assert mine.pop("rating") == {"avg": None, "count": 0} and mine.pop("orderable") is False
            # Masked: picture URLs (the stub's files, the platform's stored JPEGs).
            assert len(mine["images"]) == len(want["images"])
            assert all(u.startswith("http://testserver/market/media/images/") for u in mine["images"])
            mine["images"] = want["images"]
            for v, w in zip(mine["variants"], want["variants"], strict=True):
                assert v.pop("images") == []
                if "geometry" not in w:  # D10: no geometry is `null` on the platform; the stub leaves the key out
                    assert v.pop("geometry") is None
                    continue
                link = f"http://testserver/market/geometry/{p['product_id']}/{v['variant_id']}?region={region}"
                assert v["geometry"]["url"] == link  # masked: the API's link (PF8) vs the stub's file
                v["geometry"]["url"] = w["geometry"]["url"]
            assert mine == want, p["sku"]
    for s in STUB["suppliers"]:
        res = client.get(f"/market/suppliers/{s['supplier_id']}", headers=CONTRACT)
        assert res.status_code == 200, res.text
        mine = res.json()
        assert {k: mine[k] for k in ("supplier_id", "name", "country", "website")} == {k: s[k] for k in ("supplier_id", "name", "country", "website")}
        assert mine["logo_url"].startswith("http://testserver/market/media/thumbs/")  # masked: picture URL
        assert mine["orderable"] is False  # a platform extra (PF7's MINOR proposal)
        # D11: regions in alphabetical order (the stub keeps the supplier's order).
        assert mine["regions"] == sorted(s["regions"])
        # D12: the platform serves only verified suppliers (an unverified one is
        # 404 and its products are never listed); the seed verifies Gulf Paints,
        # which the stub lists as `verified: false` with its paint on sale.
        assert mine["verified"] is True
        assert s["verified"] is (s["name"] != "Gulf Paints")


def test_withdrawn_substitutes_like_the_stub(client):
    """5.4's 410 `product_withdrawn` names the substitutes products.json
    gives, but one: D13, the platform offers only a substitute that can be
    ordered in the region, and the stub offers the discontinued Halden table
    for the Fjord table."""
    load_stub()
    for p in STUB["products"]:
        with SessionLocal() as db:
            db.get(Product, p["product_id"]).status = "withdrawn"
            db.commit()
        for region in REGIONS:
            res = client.get(f"/market/products/{p['product_id']}", params={"region": region}, headers=CONTRACT)
            body = error_of(res, 410, "product_withdrawn")
            ids = [s["product_id"] for s in body["data"]["substitutes"]]
            assert ids == ([] if p["sku"] == "TABLE-FJORD" else p["substitutes"]), p["sku"]
        with SessionLocal() as db:
            db.get(Product, p["product_id"]).status = "approved"
            db.commit()
    assert BY_SKU["TABLE-FJORD"]["substitutes"] == [BY_SKU["TABLE-HALDEN"]["product_id"]]


# --- Geometry byte for byte -------------------------------------------------------------------


def download(client, url: str) -> bytes:
    """5.4's geometry link: a redirect to a signed URL served as an attachment."""
    parts = urlsplit(url)
    res = client.get(f"{parts.path}?{parts.query}")
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"], res.text
    return res.content


def test_app_geometry_through_the_seed_and_the_product_link(client):
    load_stub()
    seen = 0
    for p in STUB["products"]:
        for region in REGIONS:
            product = client.get(f"/market/products/{p['product_id']}", params={"region": region}, headers=CONTRACT).json()
            for v, w in zip(product["variants"], p["variants"], strict=True):
                if not w.get("geometry"):
                    continue
                data = download(client, v["geometry"]["url"])
                assert data == stub_file(w["geometry"]["url"])
                assert (hashlib.sha256(data).hexdigest(), len(data)) == (w["geometry"]["sha256"], w["geometry"]["bytes"])
                seen += 1
    assert seen == 2 * 8  # eight variants carry a file: four .tbxa uses, three .glb, the second sideboard size


def test_app_geometry_survives_the_portal_upload(client):
    """Every geometry file of the app's set uploaded through PF8's portal,
    published and downloaded through 5.4's link: the same bytes, the sha256
    products.json names."""
    owner, sid = verified(client)
    admin = admin_headers(client)
    uploaded = 0
    for p in STUB["products"]:
        variants = [v for v in p["variants"] if v.get("geometry")]
        if not variants:
            continue
        # The app path as the category: the platform's tree has it, whatever deeper segment the stub uses.
        res = client.post(
            "/supplier/products",
            json={"sku": p["sku"], "name": p["name"], "category": p["app_path"], "description": p["description"]},
            headers=owner,
        )
        assert res.status_code == 201, res.text
        pid = res.json()["product_id"]
        for v in variants:
            res = client.post(
                f"/supplier/products/{pid}/variants",
                json={"variant_id": v["variant_id"], "options": v["options"], "dims_mm": v["dims_mm"], "materials": v["materials"]},
                headers=owner,
            )
            assert res.status_code == 201, res.text
            picture = stub_file(p["images"][0])
            res = client.post(f"/supplier/products/{pid}/variants/{v['variant_id']}/images", files={"image": ("t.png", picture, "image/png")}, headers=owner)
            assert res.status_code == 201, res.text
            g = v["geometry"]
            name = g["url"].rsplit("/", 1)[1]
            res = client.post("/supplier/geometry", data={"product_id": pid, "variant_id": v["variant_id"]}, files={"file": (name, stub_file(g["url"]))}, headers=owner)
            assert res.status_code == 200, res.text
            got = res.json()["geometry"]
            assert (got["format"], got["sha256"], got["bytes"]) == (g["format"], g["sha256"], g["bytes"])
            assert res.json()["check"]["warnings"] == []  # the app's boxes are the size dims_mm says
            rows = [{"sku": p["sku"], "variant_id": v["variant_id"], "price": format_major(v["prices"]["GB"]["amount"], 2), "stock": "3"}]
            assert client.put("/supplier/prices", params={"region": "GB"}, json={"rows": rows}, headers=owner).status_code == 200
            uploaded += 1
        res = client.post(f"/supplier/products/{pid}/submit", headers=owner)
        assert res.status_code == 200 and res.json()["status"] == "pending_review", res.text
        assert client.post(f"/admin/market/products/{pid}/approve", headers=admin).status_code == 200
        product = client.get(f"/market/products/{pid}", params={"region": "GB"}, headers=CONTRACT).json()
        for v, w in zip(product["variants"], variants, strict=True):
            data = download(client, v["geometry"]["url"])
            assert data == stub_file(w["geometry"]["url"])
            assert hashlib.sha256(data).hexdigest() == v["geometry"]["sha256"] == w["geometry"]["sha256"]
            # D14: the platform names the asset itself (a stable 32-hex id per
            # product variant, contract §6.1's form); it does not read the S1
            # id the app's .tbxa carries (products.json: a hyphenated FGuid).
            asset = v["geometry"]["asset"]
            assert asset["id"] == importer.asset_id(pid, v["variant_id"]) and asset["kind"] == "object"
            if w["geometry"]["asset"].get("id"):
                assert asset["id"] != w["geometry"]["asset"]["id"] and "-" in w["geometry"]["asset"]["id"]
    assert uploaded == 8


# --- Theme includes ---------------------------------------------------------------------------


def test_theme_includes_are_product_ids(client):
    """PR2 reads a theme's `includes` with 5.4 each (contract §3 Changes,
    2026-10-11): product ids, as the stub writes them. PF7's catalogue and a
    JSON feed may name an included product by supplier, SKU and variant;
    5.4 answers its product id (D15)."""
    load()
    theme = PRODUCT["THEME-NORDIC-LIVING"]
    assert theme["includes"][0] == {"supplier_id": SUPPLIER_ID, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen"}
    body = client.get(f"/market/products/{theme['product_id']}", headers=CONTRACT).json()
    assert body["includes"] == [PRODUCT[s]["product_id"] for s in ("SOFA-OSLO-3", "PAINT-CHALK", "WP-LATTICE")]
    # The app's own theme keeps the ids products.json writes.
    load_stub()
    calm = BY_SKU["THEME-CALM"]
    assert client.get(f"/market/products/{calm['product_id']}", headers=CONTRACT).json()["includes"] == calm["includes"]

    # A JSON feed naming them either way; an unknown product is left out.
    picture = "https://cdn.example.com/theme.png"
    feed = {
        "schema": "truebex-feed/1",
        "products": [{
            "sku": "THEME-MIX", "name": "Mixed theme", "category": "decoration/themes", "kind": "theme",
            "includes": [calm["includes"][0], {"supplier_id": SUPPLIER_ID, "sku": "PAINT-CHALK", "variant_id": "2-5l"}, {"sku": "NO-SUCH-SKU"}],
            "variants": [{"variant_id": "default", "image_urls": [picture],
                          "prices": [{"region": "GB", "currency": "GBP", "price": "19.00", "price_includes_tax": True}]}],
        }],
    }  # fmt: skip
    with SessionLocal() as db:
        supplier = db.get(Supplier, NORD)
        run = importer.run_feed(db, supplier, json.dumps(feed).encode(), "json", "upsert", fetcher=media.MapFetcher({picture: png()}))
        assert (run.rows, run.rejected) == (1, 0), importer.report_json(run)
        product = db.scalar(select(Product).where(Product.supplier_id == NORD, Product.sku == "THEME-MIX"))
        product.status = "approved"
        db.commit()
        pid = product.product_id
    body = client.get(f"/market/products/{pid}", headers=CONTRACT).json()
    assert body["includes"] == [calm["includes"][0], PRODUCT["PAINT-CHALK"]["product_id"]]


def test_stub_media_fetcher_serves_only_the_files_folder(monkeypatch):
    """A folder without media-map.json (the app's set) is served by the
    stub's rule: any https URL whose path holds /files/ → that file there,
    also as a local trial's MARKET_MEDIA_FIXTURES."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "market_media_fixtures", str(CONTRACT_FIXTURES))
    geometry = SOFA["variants"][0]["geometry"]
    assert hashlib.sha256(media.default_fetcher().get(geometry["url"], 10_000_000)).hexdigest() == geometry["sha256"]
    fetcher = seed.media_fetcher(CONTRACT_FIXTURES)
    assert fetcher.get(SOFA["images"][0], 10_000_000) == stub_file(SOFA["images"][0])
    assert fetcher.get("https://cdn.example.com/files/geometry/sofa-oslo.tbxa", 10_000_000) == (CONTRACT_FIXTURES / "geometry" / "sofa-oslo.tbxa").read_bytes()
    for url in ("https://market.truebex.com/files/../products.json", "https://market.truebex.com/files/nope.png",
                "https://market.truebex.com/other/thumbs/sofa-oslo.png", "http://market.truebex.com/files/thumbs/sofa-oslo.png"):
        with pytest.raises(media.MediaError):
            fetcher.get(url, 10_000_000)
    with pytest.raises(media.MediaError):
        fetcher.get(SOFA["images"][0], 10)
    # The PF7 catalogue keeps its media-map.json.
    assert isinstance(seed.media_fetcher(CONTRACT_FIXTURES.parent.parent / "fixtures" / "market"), media.MapFetcher)
