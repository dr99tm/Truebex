"""The feed importer engine (contract §6.4 v1.1.0, report §5.13): what PF8's
feed endpoints, daily pull and spreadsheet upload call."""

import csv
import io
import json

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.market import importer, media, seed
from app.market.catalogue import create_supplier
from app.market.models import Product, VariantAvailability, VariantPrice

from .licence_helpers import error_of
from .market_helpers import CONTRACT, FIXTURES, load, make_admin, png

FEED_CSV = (FIXTURES / "feed-two-regions.csv").read_bytes()
FEED_JSON = (FIXTURES / "feed-two-regions.json").read_bytes()
GD1 = (FIXTURES / "GD1-supplier-catalogue-template.csv").read_bytes()


def _supplier(name: str = "Feed Co") -> str:
    with SessionLocal() as db:
        s = create_supplier(db, name=name, country="GB", status="verified")
        db.commit()
        return s.supplier_id


def _run(supplier_id: str, data: bytes, fmt: str = "csv", mode: str = "upsert", fetcher=None):
    with SessionLocal() as db:
        from app.market.models import Supplier

        supplier = db.get(Supplier, supplier_id)
        run = importer.run_feed(db, supplier, data, fmt, mode, fetcher=fetcher or seed.media_fetcher(FIXTURES))
        return importer.report_json(run)


def _rows(data: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def _csv(rows: list[dict], columns: list[str] | None = None, bom: bool = False) -> bytes:
    columns = columns or list(rows[0])
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\r\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return (b"\xef\xbb\xbf" if bom else b"") + buf.getvalue().encode("utf-8")


def _prices(sku: str) -> dict:
    with SessionLocal() as db:
        p = db.scalar(select(Product).where(Product.sku == sku))
        return {(r.variant_id, r.region): r.amount for r in db.scalars(select(VariantPrice).where(VariantPrice.product_id == p.product_id))}


def test_market_importer_upsert_and_replace(client):
    sid = _supplier()
    expected = json.loads((FIXTURES / "feed-report.json").read_text(encoding="utf-8"))["body"]
    report = _run(sid, FEED_CSV)
    counts = ("state", "rows", "created", "updated", "unchanged", "rejected", "errors", "hidden")
    assert {k: report[k] for k in counts} == {k: expected[k] for k in counts}
    assert report["rows"] == 6 and report["created"] == 6
    # New products wait for review; prices in integer minor units per region.
    with SessionLocal() as db:
        statuses = {p.sku: p.status for p in db.scalars(select(Product).where(Product.supplier_id == sid))}
    assert statuses == {"SOFA-OSLO-3": "pending_review", "CHAIR-BERGEN": "pending_review"}
    assert _prices("SOFA-OSLO-3") == {
        ("oat-linen", "GB"): 129900, ("oat-linen", "AE"): 129900, ("charcoal-wool", "GB"): 144900, ("charcoal-wool", "AE"): 144900,
    }  # fmt: skip

    # Idempotent: the same file again changes nothing.
    again = _run(sid, FEED_CSV)
    assert (again["created"], again["updated"], again["unchanged"], again["rejected"]) == (0, 0, 6, 0)

    # Approved stays approved when a price changes.
    with SessionLocal() as db:
        for p in db.scalars(select(Product).where(Product.supplier_id == sid)):
            p.status, p.approved_at = "approved", p.created_at
        db.commit()
    rows = _rows(FEED_CSV)
    rows[0]["price"] = "1249.00"
    report = _run(sid, _csv(rows))
    assert (report["created"], report["updated"], report["unchanged"]) == (0, 1, 5)
    with SessionLocal() as db:
        sofa = db.scalar(select(Product).where(Product.supplier_id == sid, Product.sku == "SOFA-OSLO-3"))
        assert sofa.status == "approved"
        price = db.scalar(select(VariantPrice).where(VariantPrice.product_id == sofa.product_id, VariantPrice.variant_id == "oat-linen", VariantPrice.region == "GB"))
        assert price.amount == 124900 and price.source == "feed" and price.feed_id
        sofa_id = sofa.product_id

    # Replace: the file omits the sofa → hidden (the app gets 410); listing it again restores it.
    chair_only = _csv([r for r in rows if r["sku"] == "CHAIR-BERGEN"])
    report = _run(sid, chair_only, mode="replace")
    assert report["hidden"] == 1 and report["unchanged"] == 2
    error_of(client.get(f"/market/products/{sofa_id}", headers=CONTRACT), 410, "product_withdrawn")
    report = _run(sid, _csv(rows))
    assert report["updated"] == 4  # the sofa's four rows: restored
    assert client.get(f"/market/products/{sofa_id}", headers=CONTRACT).status_code == 200

    # Replace also drops a region the file no longer lists, and a variant it omits.
    no_ae_charcoal = _csv([r for r in rows if not (r["variant_id"] == "charcoal-wool" and r["region"] == "AE")])
    _run(sid, no_ae_charcoal, mode="replace")
    with SessionLocal() as db:
        regions = {(r.variant_id, r.region) for r in db.scalars(select(VariantPrice).where(VariantPrice.product_id == sofa_id))}
    assert ("charcoal-wool", "AE") not in regions and ("charcoal-wool", "GB") in regions
    _run(sid, _csv([r for r in rows if r["variant_id"] != "charcoal-wool"]), mode="replace")
    product = client.get(f"/market/products/{sofa_id}", headers=CONTRACT).json()
    assert [v["variant_id"] for v in product["variants"]] == ["oat-linen"]

    # A run is recorded with its report.
    report = _run(sid, FEED_CSV)
    assert report["feed_id"] and report["format"] == "csv" and report["finished_at"]


def test_market_feed_json_matches_csv(client):
    a, b = _supplier("CSV Co"), _supplier("JSON Co")
    ra, rb = _run(a, FEED_CSV), _run(b, FEED_JSON, fmt="json")
    keys = ("rows", "created", "updated", "unchanged", "rejected", "errors")
    assert {k: ra[k] for k in keys} == {k: rb[k] for k in keys}

    def snapshot(supplier_id):
        with SessionLocal() as db:
            out = {}
            for p in db.scalars(select(Product).where(Product.supplier_id == supplier_id)):
                for r in db.scalars(select(VariantPrice).where(VariantPrice.product_id == p.product_id)):
                    a_ = db.scalar(select(VariantAvailability).where(VariantAvailability.product_id == p.product_id, VariantAvailability.variant_id == r.variant_id, VariantAvailability.region == r.region))
                    out[(p.sku, r.variant_id, r.region)] = (r.amount, r.currency, r.tax_rate_bp, r.delivery_fee, a_.state, a_.stock, a_.lead_time_days, p.brand, tuple(p.classification or ()))
            return out

    assert snapshot(a) == snapshot(b) and len(snapshot(a)) == 6


def test_market_feed_gd1_template(client):
    """GD1's template (contract 1.1.0): BOM-less and with a BOM, columns
    shuffled, one unknown column: 0 rejected; 1 product, 2 variants, 3 price
    lines; gtin and brand served by 5.4; charcoal made to order, 42 days."""
    fetcher = media.MapFetcher(
        {
            "https://cdn.example.com/catalogue/sofa-oslo-3/oat-linen.glb": (FIXTURES / "geometry" / "chair-bergen.glb"),
            "https://cdn.example.com/catalogue/sofa-oslo-3/charcoal-wool.glb": (FIXTURES / "geometry" / "chair-bergen.glb"),
            "https://cdn.example.com/catalogue/sofa-oslo-3/oat-linen-1.jpg": png(colour=(220, 210, 190)),
            "https://cdn.example.com/catalogue/sofa-oslo-3/oat-linen-2.jpg": png(colour=(200, 190, 170)),
            "https://cdn.example.com/catalogue/sofa-oslo-3/charcoal-wool-1.jpg": png(colour=(60, 60, 64)),
        }
    )
    rows = _rows(GD1)
    columns = list(rows[0])
    shuffled = list(reversed(columns)) + ["internal_note"]
    for r in rows:
        r["internal_note"] = "ignore me"
    for n, data in enumerate((GD1, _csv(rows, shuffled, bom=True))):
        sid = _supplier(f"GD1 Co {n}")
        report = _run(sid, data, fetcher=fetcher)
        assert report["rejected"] == 0, report["errors"]
        assert report["rows"] == 3 and report["created"] == 3
        if n == 1:
            assert report["warnings"] == [{"column": "internal_note", "code": "unknown_column"}]
        with SessionLocal() as db:
            products = list(db.scalars(select(Product).where(Product.supplier_id == sid)))
            assert len(products) == 1
            product = products[0]
            product.status, product.approved_at = "approved", product.created_at
            db.commit()
            pid = product.product_id
    admin = make_admin(client)
    assert admin
    body = client.get(f"/market/products/{pid}", params={"region": "GB"}, headers=CONTRACT).json()
    assert body["brand"] == "Nord Living" and body["classification"] == ["uniclass:Pr_40_50_12_81"]
    variants = {v["variant_id"]: v for v in body["variants"]}
    assert set(variants) == {"oat-linen", "charcoal-wool"}
    assert variants["oat-linen"]["gtin"] == "9501101530003" and variants["charcoal-wool"]["gtin"] == "9501101530010"
    assert variants["charcoal-wool"]["availability"]["state"] == "made_to_order"
    assert variants["charcoal-wool"]["availability"]["lead_time_days"] == 42
    assert variants["oat-linen"]["geometry"]["format"] == "glb" and len(variants["oat-linen"]["images"]) == 2
    assert body["description"].startswith("Three-seat sofa")

    # A row whose name differs from its SKU's first row; a GTIN with a wrong check digit.
    bad = _rows(GD1)
    bad[1]["name"] = "Oslo sofa"
    bad[2]["gtin"] = "9501101530011"
    report = _run(_supplier("GD1 bad"), _csv(bad), fetcher=fetcher)
    codes = {(e["row"], e["code"]) for e in report["errors"]}
    assert codes == {(3, "inconsistent_product"), (4, "bad_gtin")}
    assert report["rejected"] == 2 and report["created"] == 1


def test_market_importer_row_errors(client):
    good = {**_rows(FEED_CSV)[4]}  # the chair, GB
    fetcher = seed.media_fetcher(FIXTURES)
    fetcher.files["https://cdn.example.com/small.png"] = png(size=(300, 300))
    variations = {
        "missing_required": {"name": ""},
        "too_long": {"brand": "x" * 71},
        "unknown_category": {"category": "furniture/hovercraft"},
        "unknown_kind": {"kind": "chair"},
        "unknown_region": {"region": "XX"},
        "currency_mismatch": {"currency": "AED"},
        "bad_price": {"price": "649.999"},
        "bad_bool": {"price_includes_tax": "yes"},
        "bad_integer": {"stock": "many"},
        "bad_dims": {"width_mm": "78cm"},
        "bad_url": {"image_urls": "http://cdn.example.com/a.png"},
        "bad_geometry_format": {"geometry_url": "https://cdn.example.com/a.stl"},
        "geometry_fetch_failed": {"geometry_url": "https://cdn.example.com/missing.glb"},
        "image_fetch_failed": {"image_urls": "https://cdn.example.com/missing.png"},
        "image_too_small": {"image_urls": "https://cdn.example.com/small.png"},
        "bad_status": {"status": "gone"},
        "bad_gtin": {"gtin": "1234567"},
        "bad_availability": {"availability": "made_to_order"},
    }
    rows = []
    for n, (code, change) in enumerate(variations.items()):
        rows.append({**good, **change, "sku": f"BAD-{n}"})
    rows.append({**good, "sku": "DUP"})
    rows.append({**good, "sku": "DUP"})  # duplicate_row
    rows.append({**good, "sku": "MIX", "region": "GB"})
    rows.append({**good, "sku": "MIX", "region": "AE", "currency": "AED", "brand": "Other"})  # inconsistent_product
    rows.append({**good, "sku": "OK", "region": "AE", "currency": "AED"})
    report = _run(_supplier(), _csv(rows), fetcher=fetcher)
    found = {}
    for e in report["errors"]:
        found.setdefault(e["code"], e)
    expected = set(variations) | {"duplicate_row", "inconsistent_product"}
    assert set(found) == expected, sorted(set(found) ^ expected)
    assert len(expected) == 20  # every row error code of contract §6.4 (1.1.0)
    assert found["bad_price"]["column"] == "price" and found["bad_price"]["value"] == "649.999"
    assert found["missing_required"]["row"] == 2  # spreadsheet numbering: the header is row 1
    assert report["rejected"] == len(variations) + 2 and report["created"] == 3
    # The good rows imported.
    with SessionLocal() as db:
        assert {p.sku for p in db.scalars(select(Product))} >= {"OK", "DUP", "MIX"}


def test_market_feed_header_rules_and_dry_run(client, monkeypatch):
    with pytest.raises(importer.FeedInvalid):
        importer.validate(b"sku,variant_id,name\r\nA,B,C\r\n", "csv")
    with pytest.raises(importer.FeedInvalid):
        importer.validate(b"\xff\xfe not utf-8", "csv")
    with pytest.raises(importer.FeedInvalid):
        importer.validate(b'{"schema": "other/1", "products": []}', "json")
    with pytest.raises(importer.FeedInvalid):
        importer.validate(FEED_CSV.replace(b"category,", b"sku,", 1), "csv")  # a column twice
    with pytest.raises(importer.FeedTooLarge):
        importer.validate(b"x" * (importer.MAX_BYTES + 1), "csv")
    importer.validate(b"\xef\xbb\xbf" + FEED_CSV, "csv")  # a BOM is fine

    sid = _supplier()
    with SessionLocal() as db:
        from app.market.models import Supplier

        preview = importer.dry_run(db, db.get(Supplier, sid), FEED_CSV, "csv", "upsert")
    assert (preview["state"], preview["rows"], preview["created"], preview["rejected"]) == ("dry_run", 6, 6, 0)
    with SessionLocal() as db:
        assert db.scalars(select(Product).where(Product.supplier_id == sid)).first() is None

    # Through the admin route: a run per upload, 422 feed_invalid for a wrong header.
    load()
    admin = make_admin(client)
    monkeypatch.setattr(media, "HttpFetcher", lambda: seed.media_fetcher(FIXTURES))  # no internet in tests
    files = {"file": ("feed.csv", FEED_CSV, "text/csv")}
    res = client.post("/admin/market/feeds", data={"supplier_id": sid, "format": "csv", "mode": "upsert"}, files=files, headers=admin)
    assert res.status_code == 201, res.text
    assert (res.json()["state"], res.json()["created"], res.json()["source"]) == ("done", 6, "admin")
    bad = {"file": ("feed.csv", b"a,b\r\n1,2\r\n", "text/csv")}
    error_of(client.post("/admin/market/feeds", data={"supplier_id": sid, "format": "csv"}, files=bad, headers=admin), 422, "feed_invalid")
    assert client.get("/admin/market/feeds", headers=admin).json()["feeds"][0]["supplier_id"] == sid
