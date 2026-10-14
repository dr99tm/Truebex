"""PF7c: the platform's marketplace answers checked against the app's own
contract fixtures (contracts/marketplace-api.md §9). MK1 wrote them in the
app repo (Docs/roadmap/fixtures/contracts/marketplace/, app main 90799860);
they are copied byte for byte into tests/contracts/marketplace/. PF7d
re-copied them after AU2 added its bedroom set (app commit 180b2d53, on the
app's main since 7caa26aa; copied from main 7fe6b2c2): 13 products.

The platform is seeded from the app's products.json (the stub's catalogue:
three suppliers, thirteen products, per-region prices and deliveries) and
asked what the stub answers from the same files. Only what is volatile is
masked: the ids and times the server mints, and URLs (the stub serves
https://market.truebex.com/files/<path>; the platform its own picture and
geometry links). Every other difference is asserted as the platform's
behaviour with its number in PF7c's As-built ("Differences",
docs/roadmap/40/PF7c-marketplace-fixtures-from-mk1.md; D17 on in PF7d's,
docs/roadmap/40/PF7d-marketplace-fixtures-au2-bedroom-set.md), where the
PATCH line for the app side is written. PF7's own catalogue, which the older
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
# The app's set as committed (tests/contracts/marketplace/README.md): its git
# blob ids, as `git ls-tree -r <app main> -- Docs/roadmap/fixtures/contracts/marketplace/`
# prints them. PF7d: app commit 180b2d53 (AU2's bedroom set; the folder is the
# same at main 7caa26aa and 7fe6b2c2). A re-copy (scripts/sync-contract-fixtures.ps1
# -Contract marketplace) updates this table from the same listing.
APP_BLOBS = {
    "README.md": "a98aaed770c05ca63192957eff71e70c982f7795",
    "categories.json": "663d721377b193b4c88be732fca71b778a118e8f",
    "feed-report.json": "6345d627b877ddd11ecd39e13d9e94c683c879ea",
    "feed-two-regions.csv": "afc7711a2830ade310412e6fa54dc02e02bc99ec",
    "feed-two-regions.json": "a88c8f7ea97c2ad9bffd3b73bbceacb86b77a938",
    "geometry/bed-fjell-single.glb": "1ba19c19c08d621b2787ee7f4053811a212ffcce",
    "geometry/bed-fjell.glb": "780825d79611a42ea1efb078346d0cf414cf0bca",
    "geometry/bedside-fjell.glb": "66b91b69836e47e7572a781d13e0cad072e2f5da",
    "geometry/chair-bergen.tbxa": "858b5b80e13b5b4ef41c3ac052fd1ad8d8139a22",
    "geometry/light-arc.glb": "5799f14fc6ec46168d2dcfee4856aaa35ff0383d",
    "geometry/sideboard-nord.tbxa": "2bfe1dfd29601867e1639fb9550f17ddaf51042f",
    "geometry/sofa-oslo-charcoal.tbxa": "0fc6c1bacd1c51302bd3f4a171e3e181ae667e4e",
    "geometry/sofa-oslo.tbxa": "5a26f8274d49002ef90a2befadb0d834a70f595f",
    "geometry/table-fjord.glb": "2d44ddffa7746bb5e9294e6a42298db3d0780f9f",
    "geometry/table-halden.glb": "ca070d1bb6a5b8072512987be064e1b0c46771da",
    "geometry/wardrobe-nord.glb": "25907e2a6270f3aa50c4cc9665fa9bc01e44f328",
    "order-awaiting-payment.json": "0f777162c5278d69af0604b536d3848ddfdc81b3",
    "order-quoted.json": "1e9f21f9fc8f1b16e61b4f7d25c2dca759516a99",
    "prices-ae.json": "9e29a1555cd02b4812f3ffd3a5e4dc5091b4fd5a",
    "prices-gb.json": "a185245d61104e115fc7af16e6156361dee9d6a7",
    "products.json": "407d8319dc33088cfe46ec12fd65434204b59b2e",
    "regions.json": "8dd0bb1d2201c4e91270a5f6df3920a78e4262ce",
    "thumbs/bed-fjell-single.png": "0c715a3a1eeb6c4466c5e9459dcb81efa9931434",
    "thumbs/bed-fjell.png": "2b5e38b5877204939be737d2c39dc28a05cb8038",
    "thumbs/bedside-fjell.png": "69b1dbb6a3bbde27a2b21ae7cfcbf16d64b4c73d",
    "thumbs/chair-bergen.png": "83b277b6e7d35992b5f5d5ca2446b9871cd8bf31",
    "thumbs/light-arc.png": "e85add2b9430d2bff7544e63e6b462d623158253",
    "thumbs/paint-sand.png": "5e5c3bea24a9bf6e01abb7a83f01a7a459a20b02",
    "thumbs/sideboard-nord.png": "840cb4b780b1786e51938c6631475fd9d4915c03",
    "thumbs/sofa-oslo-charcoal.png": "924ede513df6b10226c2a5532ac00d8e15a3aefa",
    "thumbs/sofa-oslo.png": "1fecd9320a4a5ea39a85d6dbc8d2e9dcff1b2d7e",
    "thumbs/table-fjord.png": "467921e85b5c039aa5dbb2ed8e5a2e465ec086e2",
    "thumbs/table-halden.png": "da105a3a994d1959f7343ab0da1628a5947386fb",
    "thumbs/theme-calm.png": "c75de08eb1ec66c8e85dc7b07687a505102e7f0f",
    "thumbs/wallpaper-palm.png": "6155674e314377b8de39942cf896e6e377c32f0e",
    "thumbs/wardrobe-nord.png": "c8ae85689e0e70bc2ccde8d6781c14d2e727181d",
}
APP_FILES = set(APP_BLOBS)
# AU2's bedroom set (the products `Layout.Products` swaps an auto layout's boxes for).
BEDROOM = ("BED-FJELL-160", "BED-FJELL-90", "WARDROBE-NORD-120", "BEDSIDE-FJELL")
# Variants that carry a file: MK1's eight (four .tbxa uses, three .glb, the second
# sideboard size) and AU2's four .glb.
GEOMETRY_VARIANTS = 12


def stub(name: str) -> dict:
    return json.loads((CONTRACT_FIXTURES / name).read_text(encoding="utf-8"))


def git_blob_id(data: bytes) -> str:
    """What `git hash-object --no-filters` prints for these bytes."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


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
    # PF7d: MK1's nine products and AU2's bedroom set.
    assert len(STUB["suppliers"]) == 3 and len(STUB["products"]) == 13
    assert all(BY_SKU.get(sku, {}).get("supplier_id") == NORD for sku in BEDROOM)
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


def test_contract_folder_blobs_are_the_apps():
    """PF7d: every file is the app's blob at AU2's commit (on the app's main
    since 7caa26aa): its git blob id (`git hash-object --no-filters`) equals
    `git ls-tree`'s, so no byte differs, line endings included."""
    mine = {
        p.relative_to(CONTRACT_FIXTURES).as_posix(): git_blob_id(p.read_bytes())
        for p in CONTRACT_FIXTURES.rglob("*")
        if p.is_file()
    }
    assert {rel: blob for rel, blob in mine.items() if APP_BLOBS.get(rel) != blob} == {}
    assert set(mine) == set(APP_BLOBS)


# --- The seed ---------------------------------------------------------------------------------


def test_seed_reads_the_apps_catalogue(client, capsys):
    """seed_market.py --fixture with the app's set: its three suppliers
    (verified) and thirteen products (approved; PF7d: AU2's bedroom set
    among them), each found by 5.3 with the price products.json gives it in
    GB and AE. A second run prints and leaves the same."""
    from scripts import seed_market

    runs = []
    for _ in range(2):
        assert seed_market.main(["--fixture", str(CONTRACT_FIXTURES)]) == 0
        runs.append(capsys.readouterr().out)
        with SessionLocal() as db:
            runs.append(
                (db.scalar(select(func.count()).select_from(Supplier)), sorted((p.product_id, p.status) for p in db.scalars(select(Product))))
            )
    assert runs[0:2] == runs[2:4]
    out, (suppliers, products) = runs[0], runs[1]
    for s in STUB["suppliers"]:
        assert f"supplier {s['name']} ({s['supplier_id']}): verified" in out
    assert (suppliers, len(products)) == (3, 13)
    assert dict(products) == {pid: "approved" for pid in PRODUCTS}
    for sku in BEDROOM:
        assert f"approved        {sku:<22} {BY_SKU.get(sku, {}).get('name')}" in out

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
    # "bed" in GB and AE: the Fjell double and single beds, each with the price
    # products.json gives it there (PF7d's human test).
    for region in REGIONS:
        hits = client.get("/market/search", params={"q": "bed", "region": region}, headers=CONTRACT).json()["results"]
        found = {h["product_id"]: h for h in hits}
        for sku in ("BED-FJELL-160", "BED-FJELL-90"):
            bed = BY_SKU.get(sku, {"product_id": sku})
            hit = found.get(bed["product_id"])
            assert hit is not None, (region, sku, [h["name"] for h in hits])
            assert (hit["name"], hit["category"]) == (bed["name"], bed["category"])
            assert hit["price"] == bed["variants"][0]["prices"][region], (region, sku)


# --- 5.1, 5.2 ---------------------------------------------------------------------------------


def test_categories_like_the_stub(client):
    tree = {c["path"]: c for c in client.get("/market/categories", headers=CONTRACT).json()["categories"]}
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
    # D2: the seed adds the stub's paths the platform's tree lacks, with the
    # stub's labels: MK1's two and (PF7d) AU2's three. The platform's own
    # `double-beds` / `single-beds` stay beside the stub's `double` / `single`
    # (market_categories.json unchanged; which names stay is the owner's call).
    added = {p: got[p]["label"] for p in set(got) - set(tree)}
    assert added == {
        "furniture/tables/coffee": "Coffee tables",
        "lighting/wall/sconces": "Sconces",
        "furniture/beds/double": "Double beds",
        "furniture/beds/single": "Single beds",
        "furniture/storage/bedside": "Bedside tables",
    }
    assert {p: tree[p]["label"] for p in ("furniture/beds/double-beds", "furniture/beds/single-beds", "furniture/storage/wardrobes")} == {
        "furniture/beds/double-beds": "Double beds", "furniture/beds/single-beds": "Single beds", "furniture/storage/wardrobes": "Wardrobes",
    }  # fmt: skip
    for c in want["categories"]:
        mine = got.pop(c["path"])
        assert (mine["app_path"], mine["label"]) == (c["app_path"], labels.get(c["path"], c["label"])), c
        assert mine["products"] == counts[c["path"]], c
        if c["path"] != "furniture":
            assert c["products"] == mine["products"], c
    # D1: the stub's categories.json says 10 under furniture (6 before AU2);
    # products.json files 9 there (5 before).
    assert next(c for c in want["categories"] if c["path"] == "furniture")["products"] == 10
    assert counts["furniture"] == 9
    # D4: 5.1 is the platform's whole tree; the rest of it holds no fixture product.
    assert got and all(c["products"] == 0 for c in got.values())
    assert got["furniture/beds/double-beds"]["products"] == got["furniture/beds/single-beds"]["products"] == 0


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
    # PF7d: every line of the new file, AU2's bedroom set (one variant each) included.
    assert len(body["items"]) == 12
    assert [i["sku"] for i in body["items"][-4:]] == list(BEDROOM)
    for i in body["items"][-4:]:
        (v,) = BY_SKU[i["sku"]]["variants"]
        assert (i["variant_id"], i["price"], i["availability"]) == (v["variant_id"], v["prices"][region], v["availability"])


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
    # PF7d: all thirteen, AU2's bedroom set included, in both regions.
    assert {p["sku"] for p in STUB["products"]} >= set(BEDROOM) and len(STUB["products"]) == 13
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
    gives, but for four products. D13: the platform offers only a substitute
    that can be ordered in the region, and the stub offers the discontinued
    Halden table for the Fjord table. D17 (PF7d): the platform's rule is the
    same category, then the same app path, nearest in price, so the three
    `furniture/storage` products (MK1's sideboard, AU2's wardrobe and bedside
    table) offer each other where the stub lists none; the stub's own
    app-path substitutes (the sofa and the armchair, AU2's double and single
    beds) are the platform's too."""
    load_stub()
    # D17: in GB and AE alike (AE's prices keep GB's order).
    storage = {
        "SIDEBOARD-NORD": ["WARDROBE-NORD-120", "BEDSIDE-FJELL"],
        "WARDROBE-NORD-120": ["SIDEBOARD-NORD", "BEDSIDE-FJELL"],
        "BEDSIDE-FJELL": ["WARDROBE-NORD-120", "SIDEBOARD-NORD"],
    }
    platform = {
        "TABLE-FJORD": [],  # D13
        **{sku: [BY_SKU[s]["product_id"] for s in subs] for sku, subs in storage.items() if set(subs) <= set(BY_SKU)},
    }
    assert set(platform) == {"TABLE-FJORD", *storage}
    for p in STUB["products"]:
        with SessionLocal() as db:
            db.get(Product, p["product_id"]).status = "withdrawn"
            db.commit()
        for region in REGIONS:
            res = client.get(f"/market/products/{p['product_id']}", params={"region": region}, headers=CONTRACT)
            body = error_of(res, 410, "product_withdrawn")
            ids = [s["product_id"] for s in body["data"]["substitutes"]]
            assert ids == platform.get(p["sku"], p["substitutes"]), (p["sku"], region)
        with SessionLocal() as db:
            db.get(Product, p["product_id"]).status = "approved"
            db.commit()
    assert BY_SKU["TABLE-FJORD"]["substitutes"] == [BY_SKU["TABLE-HALDEN"]["product_id"]]
    assert all(BY_SKU[sku]["substitutes"] == [] for sku in storage)
    # The stub's beds name each other (another category, the same app path), as the platform does.
    assert BY_SKU["BED-FJELL-160"]["substitutes"] == [BY_SKU["BED-FJELL-90"]["product_id"]]
    assert BY_SKU["BED-FJELL-90"]["substitutes"] == [BY_SKU["BED-FJELL-160"]["product_id"]]


# --- Geometry byte for byte -------------------------------------------------------------------


def download(client, url: str) -> bytes:
    """5.4's geometry link: a redirect to a signed URL served as an attachment."""
    parts = urlsplit(url)
    res = client.get(f"{parts.path}?{parts.query}")
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"], res.text
    return res.content


def test_app_geometry_through_the_seed_and_the_product_link(client):
    load_stub()
    seen, downloaded = 0, []
    for p in STUB["products"]:
        for region in REGIONS:
            product = client.get(f"/market/products/{p['product_id']}", params={"region": region}, headers=CONTRACT).json()
            for v, w in zip(product["variants"], p["variants"], strict=True):
                if not w.get("geometry"):
                    continue
                data = download(client, v["geometry"]["url"])
                assert data == stub_file(w["geometry"]["url"])
                assert (hashlib.sha256(data).hexdigest(), len(data)) == (w["geometry"]["sha256"], w["geometry"]["bytes"])
                downloaded.append(w["geometry"]["url"][len(FILES) :])
                seen += 1
    assert seen == 2 * GEOMETRY_VARIANTS
    assert set(downloaded) >= {f"geometry/{n}.glb" for n in ("bed-fjell", "bed-fjell-single", "wardrobe-nord", "bedside-fjell")}


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
    assert uploaded == GEOMETRY_VARIANTS  # PF7d: AU2's four GLBs too, PF8's checks warning about none


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
