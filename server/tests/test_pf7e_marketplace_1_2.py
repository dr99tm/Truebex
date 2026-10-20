"""PF7e: the marketplace follows contract marketplace-api 1.2.0 (MK4's
orders and leads, MK2's regional pricing; both 2026-10-18).

* The app's fixture folder again, byte for byte: app commit 123b88c59 (the
  folder's last commit on the app's main, 689da345d when copied), pinned by
  its git tree id; 15 products (MK2's Sund and Vik coffee tables), the Oslo
  sofa's Oat variant low stock in AE, and the order fixtures in 1.2.0's shape
  (MK4's living-room basket: two Oslo sofas, Oat, and the Fjord table from
  Nord Living, the Arc wall light from Atelier Lumen, region AE).
* 5.7-5.10 answer 1.2.0's keys, all added beside the platform's own:
  `web_url`, and per supplier `name`, `days_min`, `days_max` and `items`
  ({sku, variant_id, qty, price_seen, quoted}).
* Every 5.7 error carries 1.2.0's `data` (§7): each line of a 409
  `unavailable` its §6.3 `availability` (null = not sold in the region).
* The wire header is marketplace-api/1.2; a 1.1 reader is still served.

Masked against the app's fixtures, and how (the readings are numbered in
docs/roadmap/40/PF7e-marketplace-api-1-2-0.md, As-built):
* `order_id`: minted by each side (the stub hashes its Idempotency-Key):
  both 32 hex.
* `created_at`: the server's clock at 5.7 (the stub's snapshot time): a valid
  RFC 3339 UTC time no earlier than the test's start.
* `checkout_url` (D6) and `web_url` (D18): the same https://truebex.com
  origin; the platform's path is a static page with the order in the query
  (/market/checkout/?order=<id>, /dashboard/orders/?order=<id>), the stub's
  the id in the path (/market/checkout/<id>, /market/orders/<id>).
* A quoted price's `at`: when the supplier quoted (the stub writes the
  catalogue's time).
"""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.market import seed
from app.market.common import format_major, is_hex32, tax_on
from app.market.models import MarketOrder, SupplierRegion, VariantAvailability, VariantPrice
from app.models import User

from .conftest import signup
from .licence_helpers import error_of
from .market_helpers import CONTRACT, CONTRACT_FIXTURES, payments_on, with_contract
from .supplier_helpers import as_supplier
from .test_market_contract_fixtures import APP_BLOBS

# The app's folder as copied: its last commit on the app's main and the git
# tree id of Docs/roadmap/fixtures/contracts/marketplace/ there
# (`git rev-parse <commit>:<folder>`; the same tree at main 689da345d).
APP_COMMIT = "123b88c597d20bba2f4247d00b864b4757fca91d"
APP_TREE = "2a1a2ace5d42d95335411c3c5c99576017a7ed23"
APP_REPO = Path(r"T:\unreal5_7_4_projects\truebex_compact")
APP_DIR = "Docs/roadmap/fixtures/contracts/marketplace"
WIRE = "marketplace-api/1.2"

STUB = json.loads((CONTRACT_FIXTURES / "products.json").read_text(encoding="utf-8"))
BY_SKU = {p["sku"]: p for p in STUB["products"]}
SUPPLIERS = {s["supplier_id"]: s for s in STUB["suppliers"]}
NORD, LUMEN = STUB["suppliers"][0]["supplier_id"], STUB["suppliers"][1]["supplier_id"]
SOFA = BY_SKU["SOFA-OSLO-3"]


def fixture(name: str) -> dict:
    return json.loads((CONTRACT_FIXTURES / name).read_text(encoding="utf-8"))


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _tree(entries: dict[str, object]) -> str:
    """A git tree id: `entries` maps a name to a blob id (a file) or to a
    dict of the same kind (a folder). Git sorts a folder's name as name + "/"."""
    rows = []
    for name, value in entries.items():
        raw = name.encode("utf-8")
        if isinstance(value, dict):
            rows.append((raw + b"/", b"40000 " + raw + b"\0" + bytes.fromhex(_tree(value))))
        else:
            rows.append((raw, b"100644 " + raw + b"\0" + bytes.fromhex(value)))
    body = b"".join(row for _, row in sorted(rows))
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def tree_of_folder(folder: Path) -> str:
    def walk(d: Path) -> dict:
        return {p.name: (walk(p) if p.is_dir() else git_blob_id(p.read_bytes())) for p in d.iterdir()}

    return _tree(walk(folder))


def tree_of_listing(blobs: dict[str, str]) -> str:
    """The tree a `git ls-tree -r` listing (path → blob id) makes."""
    root: dict = {}
    for path, blob in blobs.items():
        node = root
        *dirs, name = path.split("/")
        for d in dirs:
            node = node.setdefault(d, {})
        node[name] = blob
    return _tree(root)


def load_stub(*, payments_ready: bool = False, owner_email: str | None = None) -> None:
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == owner_email)) if owner_email else None
        seed.load_catalogue(db, CONTRACT_FIXTURES, payments_ready=payments_ready, owner=owner)


def money(price: dict) -> dict:
    return {k: price[k] for k in ("amount", "currency", "exponent")}


def mk4_request(kind: str, want: dict, key_project: dict | None = None) -> dict:
    """5.7 as MK4 sends the fixture's basket: every item as a line with the
    price it saw, the project as the fixture echoes it."""
    return {
        "kind": kind,
        "region": want["region"],
        "project": key_project or want["project"],
        "contact": {"name": "Stub Person", "email": "buyer@example.com", "phone": None, "message": "Delivery after 1 Dec"},
        "delivery": {"country": want["region"], "city": "Dubai", "postcode": None},
        "lines": [
            {"supplier_id": s["supplier_id"], "sku": i["sku"], "variant_id": i["variant_id"], "qty": i["qty"], "price_seen": i["price_seen"]}
            for s in want["suppliers"]
            for i in s["items"]
        ],
    }  # fmt: skip


def assert_masked_like(mine: dict, want: dict, started: datetime) -> None:
    """The keys this module's docstring masks, and how."""
    assert is_hex32(mine["order_id"]) and is_hex32(want["order_id"])
    created = datetime.fromisoformat(mine["created_at"].replace("Z", "+00:00"))
    assert mine["created_at"].endswith("Z") and created >= started.replace(microsecond=0)
    web, theirs = urlsplit(mine["web_url"]), urlsplit(want["web_url"])
    assert (web.scheme, web.netloc) == (theirs.scheme, theirs.netloc) == ("https", "truebex.com")
    assert web.path == "/dashboard/orders/" and parse_qs(web.query) == {"order": [mine["order_id"]]}
    assert theirs.path == f"/market/orders/{want['order_id']}" and not theirs.query
    if want["checkout_url"] is None:
        assert mine["checkout_url"] is None
    else:  # D6
        url, stub_url = urlsplit(mine["checkout_url"]), urlsplit(want["checkout_url"])
        assert (url.scheme, url.netloc, url.path) == ("https", "truebex.com", "/market/checkout/")
        assert parse_qs(url.query) == {"order": [mine["order_id"]]}
        assert stub_url.path == f"/market/checkout/{want['order_id']}"


def assert_suppliers_like(mine: dict, want: dict, *, quoted_at_masked: bool = False) -> None:
    """Each supplier's 1.2.0 keys equal the fixture's; the platform's own keys
    beside them say the same (supplier_name, delivery_days)."""
    assert [g["supplier_id"] for g in mine["suppliers"]] == [w["supplier_id"] for w in want["suppliers"]]
    for g, w in zip(mine["suppliers"], want["suppliers"], strict=True):
        assert (g["name"], g["state"], g["lines"]) == (w["name"], w["state"], w["lines"]), w["name"]
        # D7: money {amount, currency, exponent} on the platform, a §6.3 price in the stub.
        assert g["subtotal"] == money(w["subtotal"]), w["name"]
        assert g["delivery"] == w["delivery"], w["name"]
        assert (g["days_min"], g["days_max"]) == (w["days_min"], w["days_max"]), w["name"]
        assert g["supplier_name"] == g["name"] == SUPPLIERS[w["supplier_id"]]["name"]
        assert g["delivery_days"] == {"min": g["days_min"], "max": g["days_max"]}
        assert len(g["items"]) == g["lines"]
        for item, wi in zip(g["items"], w["items"], strict=True):
            assert set(item) == {"sku", "variant_id", "qty", "price_seen", "quoted"}
            assert (item["sku"], item["variant_id"], item["qty"]) == (wi["sku"], wi["variant_id"], wi["qty"])
            # The §6.3 unit price the order was placed at: the seeded price, its time included.
            assert item["price_seen"] == wi["price_seen"], wi["sku"]
            if wi["quoted"] is None:
                assert item["quoted"] is None, wi["sku"]
            else:
                assert {**item["quoted"], "at": None} == {**wi["quoted"], "at": None}, wi["sku"]
                if quoted_at_masked:
                    assert item["quoted"]["at"].endswith("Z")
    assert mine["total"] == money(want["total"])
    assert mine["region"] == want["region"] == want["total"]["region"]


def assert_arithmetic(order: dict) -> None:
    """§5.7 (1.2.0): per supplier subtotal = Σ unit × qty (the quoted unit once
    quoted); total = Σ (subtotal + delivery), in the region's currency."""
    total = 0
    for g in order["suppliers"]:
        units = [(i["quoted"] or i["price_seen"])["amount"] * i["qty"] for i in g["items"]]
        assert g["subtotal"]["amount"] == sum(units), g["name"]
        assert {g["subtotal"]["currency"], g["delivery"]["currency"]} == {order["currency"]}
        total += g["subtotal"]["amount"] + g["delivery"]["amount"]
    assert order["total"]["amount"] == total and order["total"]["currency"] == order["currency"]


# --- The copy -------------------------------------------------------------------------------------


def test_pf7e_folder_is_the_apps_at_the_recorded_commit():
    """tests/contracts/marketplace/ is the app's folder at 123b88c59, byte for
    byte (its git tree id), and APP_BLOBS (test_market_contract_fixtures.py)
    is that commit's listing. MK2 and MK4 changed 7 files and added 4."""
    assert tree_of_folder(CONTRACT_FIXTURES) == APP_TREE
    assert tree_of_listing(APP_BLOBS) == APP_TREE
    assert len(APP_BLOBS) == 40
    assert {f"{d}/table-{n}.{e}" for d, e in (("geometry", "glb"), ("thumbs", "png")) for n in ("sund", "vik")} <= set(APP_BLOBS)
    assert len(STUB["products"]) == 15 and {"TABLE-SUND", "TABLE-VIK"} <= set(BY_SKU)
    halden = BY_SKU["TABLE-HALDEN"]
    assert halden["substitutes"] == [BY_SKU[s]["product_id"] for s in ("TABLE-FJORD", "TABLE-SUND", "TABLE-VIK")]
    oat = SOFA["variants"][0]
    assert oat["availabilities"]["AE"]["state"] == "low_stock" and oat["availability"]["state"] == "in_stock"
    for name in ("order-awaiting-payment.json", "order-quoted.json"):
        order = fixture(name)
        assert {"web_url", "created_at", "region", "project"} <= set(order), name
        assert order["project"]["project_uid"] and order["project"]["project_id"] is None


@pytest.mark.skipif(not (APP_REPO / ".git").exists(), reason="the app repository is not on this machine")
def test_pf7e_recorded_blobs_are_the_apps_at_the_commit():
    """Where the app repo is present, git agrees with the recorded commit."""
    out = subprocess.run(
        ["git", "ls-tree", "-r", APP_COMMIT, "--", f"{APP_DIR}/"], cwd=APP_REPO, capture_output=True, text=True, timeout=60
    )
    if out.returncode != 0:
        pytest.skip(f"git ls-tree failed: {out.stderr.strip()}")
    listed = {}
    for line in out.stdout.splitlines():
        meta, path = line.split("\t", 1)
        listed[path[len(APP_DIR) + 1 :]] = meta.split()[2]
    assert listed == APP_BLOBS
    tree = subprocess.run(["git", "rev-parse", f"{APP_COMMIT}:{APP_DIR}"], cwd=APP_REPO, capture_output=True, text=True, timeout=60)
    assert tree.stdout.strip() == APP_TREE


# --- §10 test_order_idempotency_and_project_filter -------------------------------------------------


def test_order_idempotency_and_project_filter(client, monkeypatch):
    """§10 (1.2.0): the same Idempotency-Key and body answer the same order
    (one order stored), another body is 409 `idempotency_mismatch`; 5.8
    `?project_uid=` keeps that project's orders only. Answered in 1.2's
    shape with the 1.2 header; a 1.1 reader is served the same."""
    payments_on(monkeypatch)
    load_stub(payments_ready=True)
    want = fixture("order-awaiting-payment.json")
    h = with_contract(signup(client, email="buyer@example.com"))
    cloud = {"name": "House", "project_id": "6b1f0d6a2c4e4f8a9b0c1d2e3f405162", "project_uid": "a1" * 16}
    local = {"name": "Cabin", "project_id": None, "project_uid": "b2" * 16}
    key = "1d" * 16

    first = client.post("/market/orders", json=mk4_request("order", want, cloud), headers={**h, "Idempotency-Key": key})
    assert first.status_code == 201, first.text
    assert first.headers["X-Truebex-Contract"] == WIRE
    again = client.post("/market/orders", json=mk4_request("order", want, cloud), headers={**h, "Idempotency-Key": key})
    assert again.status_code == 201 and again.headers.get("Idempotency-Replayed") == "true"
    assert again.json() == first.json()  # the same order, 1.2.0's keys included
    assert again.json()["web_url"].endswith(f"?order={first.json()['order_id']}")
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(MarketOrder)) == 1
    # The same key with another body (one sofa fewer).
    other = mk4_request("order", want, cloud)
    other["lines"][0]["qty"] = 1
    body = error_of(client.post("/market/orders", json=other, headers={**h, "Idempotency-Key": key}), 409, "idempotency_mismatch")
    assert body["retry_after_s"] is None
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(MarketOrder)) == 1

    # A request for quote from the same cloud project, and an order from a local one.
    quote = client.post("/market/orders", json=mk4_request("quote", want, cloud), headers={**h, "Idempotency-Key": "2e" * 16})
    cabin = client.post("/market/orders", json=mk4_request("order", want, local), headers={**h, "Idempotency-Key": "3f" * 16})
    assert quote.status_code == cabin.status_code == 201
    listed = client.get("/market/orders", params={"project_uid": cloud["project_uid"]}, headers=h)
    assert listed.status_code == 200 and listed.headers["X-Truebex-Contract"] == WIRE
    house = listed.json()
    assert [o["order_id"] for o in house["orders"]] == [quote.json()["order_id"], first.json()["order_id"]]  # newest first
    assert all(o["project"] == cloud for o in house["orders"]) and house["next_cursor"] is None
    only = client.get("/market/orders", params={"project_uid": local["project_uid"]}, headers=h).json()["orders"]
    assert [o["order_id"] for o in only] == [cabin.json()["order_id"]]
    assert only[0]["project"] == local and only[0]["project"]["project_id"] is None
    assert client.get("/market/orders", params={"project_uid": "c3" * 16}, headers=h).json()["orders"] == []
    assert len(client.get("/market/orders", headers=h).json()["orders"]) == 3
    # Another account sees none of them.
    stranger = with_contract(signup(client, email="other@example.com"))
    assert client.get("/market/orders", params={"project_uid": cloud["project_uid"]}, headers=stranger).json()["orders"] == []
    # A 1.1 reader is served (same MAJOR); 2.0 is refused, naming 1.2.
    old = client.get("/market/orders", headers={**h, "X-Truebex-Contract": "marketplace-api/1.1"})
    assert old.status_code == 200 and old.headers["X-Truebex-Contract"] == WIRE
    refused = error_of(client.get("/market/orders", headers={**h, "X-Truebex-Contract": "marketplace-api/2.0"}), 400, "contract_version")
    assert refused["data"]["supported"] == [WIRE]


# --- 5.7 / 5.9 against the app's order fixtures ----------------------------------------------------


def test_order_awaiting_payment_like_the_apps_fixture(client, monkeypatch):
    """MK4's basket placed on the seeded catalogue (AE, payments ready)
    answers order-awaiting-payment.json: each supplier's supplier_id, name,
    state, lines, subtotal, delivery, days_min and days_max, each item's sku,
    variant_id, qty, price_seen and quoted null, and the total."""
    payments_on(monkeypatch)
    load_stub(payments_ready=True)
    want = fixture("order-awaiting-payment.json")
    assert want["kind"] == "order" and [len(s["items"]) for s in want["suppliers"]] == [2, 1]
    started = datetime.now(timezone.utc)
    h = with_contract(signup(client, email="buyer@example.com"))
    res = client.post("/market/orders", json=mk4_request("order", want), headers={**h, "Idempotency-Key": "0d3e" * 8})
    assert res.status_code == 201, res.text
    mine = res.json()
    assert (mine["kind"], mine["state"]) == (want["kind"], want["state"]) == ("order", "awaiting_payment")
    assert mine["project"] == want["project"]  # echoed as sent, project_uid included
    assert_masked_like(mine, want, started)
    assert_suppliers_like(mine, want)
    assert_arithmetic(mine)
    assert_arithmetic(want)
    assert mine["total"]["amount"] == 343100  # AED 3,431.00: MK4's human test step 1
    # 5.9 answers the same order the same way.
    again = client.get(f"/market/orders/{mine['order_id']}", headers=h)
    assert again.status_code == 200 and again.headers["X-Truebex-Contract"] == WIRE
    assert again.json() == mine


def test_order_quoted_like_the_apps_fixture(client):
    """The basket as a request for quote; both suppliers quote in their inbox
    (PF8) at order-quoted.json's unit prices. Before a supplier quotes, its
    items' `quoted` stays null; after, 5.9 shows each item's quoted unit price
    as the fixture has it, and the subtotals and the total follow."""
    signup(client, email="owner@suppliers.example.com")
    load_stub(owner_email="owner@suppliers.example.com")
    token = client.post("/auth/login", json={"email": "owner@suppliers.example.com", "password": "password123"}).json()
    owner = {"Authorization": f"Bearer {token['access_token']}"}
    want = fixture("order-quoted.json")
    assert want["kind"] == "quote" and want["state"] == "quoted"
    started = datetime.now(timezone.utc)
    h = with_contract(signup(client, email="buyer@example.com"))
    res = client.post("/market/orders", json=mk4_request("quote", want), headers={**h, "Idempotency-Key": "0d3e" * 8})
    assert res.status_code == 201, res.text
    placed = res.json()
    assert (placed["state"], placed["checkout_url"]) == ("submitted", None)
    assert all(g["state"] == "submitted" for g in placed["suppliers"])
    assert all(i["quoted"] is None for g in placed["suppliers"] for i in g["items"])
    oid = placed["order_id"]

    def quote(supplier: dict) -> None:
        body = {
            "lines": [{"sku": i["sku"], "variant_id": i["variant_id"], "price": format_major(i["quoted"]["amount"], 2)} for i in supplier["items"]],
            "delivery_fee": format_major(supplier["delivery"]["amount"], 2),
        }  # fmt: skip
        res = client.post(f"/supplier/inbox/{oid}/quote", json=body, headers=as_supplier(owner, supplier["supplier_id"]))
        assert res.status_code == 200, res.text

    nord, lumen = want["suppliers"]
    quote(nord)
    half = client.get(f"/market/orders/{oid}", headers=h).json()
    g_nord, g_lumen = half["suppliers"]
    assert (half["state"], g_nord["state"], g_lumen["state"]) == ("quoted", "quoted", "submitted")
    assert [i["quoted"]["amount"] for i in g_nord["items"]] == [i["quoted"]["amount"] for i in nord["items"]]
    assert all(i["quoted"] is None for i in g_lumen["items"])  # not quoted yet
    assert g_nord["subtotal"]["amount"] == nord["subtotal"]["amount"]
    assert g_lumen["subtotal"]["amount"] == sum(i["price_seen"]["amount"] * i["qty"] for i in lumen["items"])
    assert_arithmetic(half)

    quote(lumen)
    mine = client.get(f"/market/orders/{oid}", headers=h).json()
    assert (mine["kind"], mine["state"]) == (want["kind"], want["state"])
    assert mine["project"] == want["project"]
    assert_masked_like(mine, want, started)
    assert_suppliers_like(mine, want, quoted_at_masked=True)
    assert_arithmetic(mine)
    assert_arithmetic(want)
    assert mine["total"]["amount"] == 313900  # AED 3,139.00: MK4's human test step 3
    # The platform's own line list says the same (quoted_price beside price).
    assert [ln["quoted_price"]["amount"] for ln in mine["lines"]] == [i["quoted"]["amount"] for s in want["suppliers"] for i in s["items"]]


# --- MK2: availability per region ----------------------------------------------------------------


def test_oslo_oat_availability_per_region(client):
    """products.json's per-region `availabilities` (the stub's own shape) is
    projected like prices: the Oslo sofa (Oat) is low stock in AE and in
    stock in GB, in 5.5 (as prices-<region>.json), 5.3 and 5.4."""
    load_stub()
    for region in ("AE", "GB"):
        _oat_in(client, region)


def _oat_in(client, region: str) -> None:
    oat = SOFA["variants"][0]
    want = oat.get("availabilities", {}).get(region, oat["availability"])
    assert want["state"] == {"AE": "low_stock", "GB": "in_stock"}[region]
    listed = next(i for i in fixture(f"prices-{region.lower()}.json")["items"] if (i["sku"], i["variant_id"]) == ("SOFA-OSLO-3", "oat-linen"))
    assert listed["availability"] == want
    ref = {"supplier_id": NORD, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "qty": 2}
    res = client.post("/market/prices", json={"region": region, "items": [ref]}, headers=CONTRACT)
    assert res.status_code == 200, res.text
    (line,) = res.json()["items"]
    assert (line["price"], line["availability"], line["substitutes"]) == (listed["price"], want, [])
    hits = client.get("/market/search", params={"q": "Oslo", "region": region}, headers=CONTRACT).json()["results"]
    hit = next(h for h in hits if h["product_id"] == SOFA["product_id"])
    assert (hit["variant_id"], hit["availability"]) == ("oat-linen", want)
    product = client.get(f"/market/products/{SOFA['product_id']}", params={"region": region}, headers=CONTRACT).json()
    assert product["variants"][0]["availability"] == want
    # The Charcoal variant has no per-region entry: its one availability everywhere.
    assert product["variants"][1]["availability"] == SOFA["variants"][1]["availability"]


@pytest.mark.parametrize("region", ["GB", "AE"])
def test_batch_prices_new_lists_and_limits(client, region):
    """5.5 with the new prices-<region>.json (14 lines: MK2's Sund and Vik
    tables included) answers each line as the file; a line it cannot price
    answers price and availability null; over 500 items is 413 too_large."""
    load_stub()
    want = fixture(f"prices-{region.lower()}.json")
    assert len(want["items"]) == 14 and [i["sku"] for i in want["items"][-2:]] == ["TABLE-SUND", "TABLE-VIK"]
    items = [{"supplier_id": i["supplier_id"], "sku": i["sku"], "variant_id": i["variant_id"]} for i in want["items"]]
    unknown = {"supplier_id": NORD, "sku": "NO-SUCH-SKU", "variant_id": "default"}
    body = client.post("/market/prices", json={"region": region, "items": [*items, unknown]}, headers=CONTRACT).json()
    for mine, theirs in zip(body["items"], want["items"]):
        assert (mine["sku"], mine["price"], mine["availability"]) == (theirs["sku"], theirs["price"], theirs["availability"])
        assert [s["product_id"] for s in mine["substitutes"]] == theirs["substitutes"]  # D5: objects on the platform
    last = body["items"][-1]
    assert (last["sku"], last["price"], last["availability"], last["substitutes"]) == ("NO-SUCH-SKU", None, None, [])
    too_many = {"region": region, "items": [unknown] * 501}
    body = error_of(client.post("/market/prices", json=too_many, headers=CONTRACT), 413, "too_large")
    assert body["data"]["max_items"] == 500


# --- 5.7's error data (§7, 1.2.0) ----------------------------------------------------------------


def test_unavailable_lines_carry_availability(client, monkeypatch):
    """Every line of a 409 `unavailable` carries `availability` (§6.3; null =
    not sold in the region): the quote-only branch too (its reason kept), a
    discontinued line, a withdrawn one, an unknown one, and a line its
    supplier does not price in the region. A supplier that does not deliver
    there is still 422 `region_not_served` with data.suppliers."""
    payments_on(monkeypatch)
    load_stub(payments_ready=False)  # every supplier quote-only
    h = with_contract(signup(client, email="buyer@example.com"))
    want = fixture("order-awaiting-payment.json")
    body = error_of(client.post("/market/orders", json=mk4_request("order", want), headers=h), 409, "unavailable")
    assert body["data"]["reason"] == "quote_only" and sorted(body["data"]["suppliers"]) == sorted([NORD, LUMEN])
    lines = {(ln["sku"], ln["variant_id"]): ln for ln in body["data"]["lines"]}
    assert set(lines) == {("SOFA-OSLO-3", "oat-linen"), ("TABLE-FJORD", "oak"), ("LIGHT-ARC-W", "brass")}
    for (sku, variant), ln in lines.items():
        v = next(v for v in BY_SKU[sku]["variants"] if v["variant_id"] == variant)
        assert ln["reason"] == "quote_only" and ln["supplier_id"] == BY_SKU[sku]["supplier_id"]
        assert ln["availability"] == v.get("availabilities", {}).get("AE", v["availability"]), sku
    assert lines[("SOFA-OSLO-3", "oat-linen")]["availability"]["state"] == "low_stock"

    def line(sku: str, variant: str, supplier: str = NORD) -> dict:
        return {"supplier_id": supplier, "sku": sku, "variant_id": variant, "qty": 1}

    def order(*lines: dict, kind: str = "quote") -> dict:
        req = mk4_request(kind, want)
        req["lines"] = list(lines)
        return req

    # The Arc light no longer priced in AE (Atelier Lumen still delivers there); the Fjord table withdrawn.
    with SessionLocal() as db:
        arc = BY_SKU["LIGHT-ARC-W"]["product_id"]
        db.execute(delete(VariantPrice).where(VariantPrice.product_id == arc, VariantPrice.region == "AE"))
        db.execute(delete(VariantAvailability).where(VariantAvailability.product_id == arc, VariantAvailability.region == "AE"))
        from app.market.models import Product

        db.get(Product, BY_SKU["TABLE-FJORD"]["product_id"]).status = "withdrawn"
        db.commit()
    req = order(line("TABLE-HALDEN", "walnut"), line("TABLE-FJORD", "oak"), line("NO-SUCH-SKU", "default"), line("LIGHT-ARC-W", "brass", LUMEN))
    body = error_of(client.post("/market/orders", json=req, headers=h), 409, "unavailable")
    got = {ln["sku"]: (ln["reason"], ln["availability"] and ln["availability"]["state"]) for ln in body["data"]["lines"]}
    assert got == {
        "TABLE-HALDEN": ("discontinued", "discontinued"),
        "TABLE-FJORD": ("withdrawn", "discontinued"),  # as 5.5 answers a withdrawn line
        "NO-SUCH-SKU": ("not_found", None),
        "LIGHT-ARC-W": ("not_sold_in_region", None),  # null = not sold in the region
    }
    assert all(set(ln) >= {"supplier_id", "sku", "variant_id", "availability"} for ln in body["data"]["lines"])

    # A supplier that does not deliver to AE: 422 region_not_served, data.suppliers [{supplier_id, name}].
    with SessionLocal() as db:
        row = db.scalar(select(SupplierRegion).where(SupplierRegion.supplier_id == LUMEN, SupplierRegion.region == "AE"))
        row.active = False
        db.commit()
    body = error_of(client.post("/market/orders", json=order(line("LIGHT-ARC-W", "brass", LUMEN)), headers=h), 422, "region_not_served")
    assert body["data"]["suppliers"] == [{"supplier_id": LUMEN, "name": "Atelier Lumen"}]


def test_price_changed_lines_name_supplier_and_unit_price(client, monkeypatch):
    """409 `price_changed` (§7, 1.2.0): data.lines[] = {supplier_id, sku,
    variant_id, price}, the unit price now (§6.3); a resend at that price is
    placed, the new price as its items' price_seen."""
    payments_on(monkeypatch)
    load_stub(payments_ready=True)
    want = fixture("order-awaiting-payment.json")
    h = with_contract(signup(client, email="buyer@example.com"))
    req = mk4_request("order", want)
    req["lines"][1]["price_seen"] = {**req["lines"][1]["price_seen"], "amount": 47900}  # an older Fjord price
    body = error_of(client.post("/market/orders", json=req, headers=h), 409, "price_changed")
    (changed,) = body["data"]["lines"]
    fjord = want["suppliers"][0]["items"][1]
    assert (changed["supplier_id"], changed["sku"], changed["variant_id"]) == (NORD, "TABLE-FJORD", "oak")
    assert changed["price"] == fjord["price_seen"]
    req["lines"][1]["price_seen"] = changed["price"]
    res = client.post("/market/orders", json=req, headers={**h, "Idempotency-Key": "4a" * 16})
    assert res.status_code == 201, res.text
    assert res.json()["suppliers"][0]["items"][1]["price_seen"] == changed["price"]


# --- 5.10 ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["order", "quote"])
def test_cancel_answers_the_whole_order(client, monkeypatch, kind):
    """5.10 → 200 with the whole order, `cancelled`, in 1.2.0's shape."""
    payments_on(monkeypatch)
    load_stub(payments_ready=True)
    want = fixture("order-awaiting-payment.json")
    h = with_contract(signup(client, email="buyer@example.com"))
    placed = client.post("/market/orders", json=mk4_request(kind, want), headers=h).json()
    res = client.post(f"/market/orders/{placed['order_id']}/cancel", headers=h)
    assert res.status_code == 200 and res.headers["X-Truebex-Contract"] == WIRE
    mine = res.json()
    assert (mine["order_id"], mine["kind"], mine["state"]) == (placed["order_id"], kind, "cancelled")
    assert mine["checkout_url"] is None and mine["web_url"] == placed["web_url"]
    assert [g["state"] for g in mine["suppliers"]] == ["cancelled", "cancelled"]
    assert [g["name"] for g in mine["suppliers"]] == ["Nord Living", "Atelier Lumen"]
    assert [[i["sku"] for i in g["items"]] for g in mine["suppliers"]] == [["SOFA-OSLO-3", "TABLE-FJORD"], ["LIGHT-ARC-W"]]
    assert_arithmetic(mine)
    assert client.get(f"/market/orders/{placed['order_id']}", headers=h).json() == mine


# --- Totals where a price excludes tax ------------------------------------------------------------


def test_totals_where_a_price_excludes_tax(client, monkeypatch):
    """§5.7's total = Σ (subtotal + delivery) holds for prices that include
    tax (GB and AE). A line priced without tax gets its tax added on top: the
    group's and the order's `total` carry it, so the platform's total is
    Σ (subtotal + delivery) + the tax added (As-built, the arithmetic)."""
    payments_on(monkeypatch)
    load_stub(payments_ready=True)
    arc = BY_SKU["LIGHT-ARC-W"]
    with SessionLocal() as db:
        row = db.scalar(select(VariantPrice).where(VariantPrice.product_id == arc["product_id"], VariantPrice.region == "GB"))
        row.includes_tax = False  # GBP 129.00 plus VAT
        db.commit()
    h = with_contract(signup(client, email="buyer@example.com"))
    req = {
        "kind": "order", "region": "GB", "project": {"name": "Flat", "project_id": None, "project_uid": "d4" * 16},
        "contact": {"name": "Sam Reed", "email": "buyer@example.com", "phone": None, "message": None},
        "delivery": {"country": "GB", "city": "Leeds", "postcode": "LS1 4AP"},
        "lines": [
            {"supplier_id": NORD, "sku": "TABLE-FJORD", "variant_id": "oak", "qty": 1},
            {"supplier_id": LUMEN, "sku": "LIGHT-ARC-W", "variant_id": "brass", "qty": 2},
        ],
    }  # fmt: skip
    res = client.post("/market/orders", json=req, headers=h)
    assert res.status_code == 201, res.text
    mine = res.json()
    nord, lumen = mine["suppliers"]
    assert (nord["subtotal"]["amount"], nord["delivery"]["amount"]) == (42900, 2900)
    assert (lumen["subtotal"]["amount"], lumen["delivery"]["amount"]) == (25800, 900)
    assert lumen["items"][0]["price_seen"]["includes_tax"] is False
    added = tax_on(25800, 2000, False)
    assert added == 5160
    assert nord["total"]["amount"] == 42900 + 2900
    assert lumen["total"]["amount"] == 25800 + 900 + added
    assert mine["total"]["amount"] == (42900 + 2900) + (25800 + 900) + added
