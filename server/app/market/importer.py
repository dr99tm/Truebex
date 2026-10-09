"""The feed importer engine (contract §6.4, v1.1.0; report shape §5.13).

Every source becomes §6.4 rows first (a CSV file, a `truebex-feed/1` JSON
file, PF8's spreadsheet upload), then one engine turns rows into products,
variants, regional prices and availability:

* A row upserts by (supplier, `sku`, `variant_id`, `region`); re-running the
  same file changes nothing (every row `unchanged`).
* `replace` mode hides the supplier's products the file omits (a later file
  that lists one restores it), the variants of listed products it omits, and
  the regional prices of listed variants it omits.
* Header rules: column order free, unknown columns ignored with one warning
  each, a leading UTF-8 byte-order mark ignored; a missing required column or
  a broken JSON shape is `FeedInvalid` (PF8: 422 `feed_invalid`).
* Product-level columns must agree across a SKU's rows and variant-level
  columns across a variant's regional rows: the first row wins, a later row
  that differs is rejected with `inconsistent_product`.
* Rejected rows are skipped and listed (≤ 200) with the row number as a
  spreadsheet shows it (the header is row 1; JSON: the price entry's 1-based
  position), the column, the code and the value; every other row imports.
* New products wait for review (`pending_review`); an approved product
  stays approved when its prices, stock or details change.
* Geometry and images are fetched once per URL through a `media.Fetcher`
  (the request-forgery guard), re-encoded and stored by SHA-256; a later
  feed with the same URLs fetches nothing.

PF8 calls `validate` (header check at upload), `queue` + `execute` (a run),
`dry_run` (the portal's preview) and `report_json` (5.13).
"""

import csv
import hashlib
import io
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..storage import Store, get_store
from . import media
from .common import KINDS, new_id, now, parse_major, parse_percent_bp, rfc3339
from .models import (
    FeedRun,
    MarketRegion,
    Product,
    ProductEmbedding,
    ProductVariant,
    Supplier,
    SupplierRegion,
    VariantAvailability,
    VariantPrice,
)
from .taxonomy import active_categories, active_regions

log = logging.getLogger("truebex.market")

FEED_SCHEMA = "truebex-feed/1"
MAX_BYTES = 50 * 1024 * 1024
MAX_ROWS = 100_000
MAX_ERRORS = 200
MAX_IMAGES = 10

COLUMNS = (
    "sku", "variant_id", "name", "category", "kind",
    "option_size", "option_colour", "option_finish", "materials",
    "width_mm", "height_mm", "depth_mm", "geometry_url", "image_urls",
    "region", "currency", "price", "price_includes_tax", "tax_rate_percent",
    "delivery_fee", "delivery_days_min", "delivery_days_max",
    "stock", "lead_time_days", "status",
    "description", "brand", "gtin", "classification", "availability",
)  # fmt: skip
REQUIRED_HEADER = ("sku", "variant_id", "name", "category", "region", "currency", "price", "price_includes_tax", "image_urls")
PRODUCT_COLUMNS = ("name", "category", "kind", "description", "brand", "classification")
VARIANT_COLUMNS = (
    "option_size", "option_colour", "option_finish", "materials",
    "width_mm", "height_mm", "depth_mm", "geometry_url", "image_urls", "gtin",
)  # fmt: skip
ROW_STATUSES = ("active", "discontinued", "hidden")
FEED_AVAILABILITY = ("in_stock", "low_stock", "made_to_order", "out_of_stock")
CLASSIFICATION_SCHEMES = ("uniclass", "etim", "gpc")


class FeedInvalid(Exception):
    """The header or the JSON shape is wrong (PF8: 422 `feed_invalid`)."""


class FeedTooLarge(Exception):
    """Over 50 MB or 100 000 rows (PF8: 413 `too_large`)."""


@dataclass
class Row:
    number: int
    cells: dict[str, str]

    def get(self, column: str) -> str:
        return (self.cells.get(column) or "").strip()


# --- Parsing ------------------------------------------------------------------------------


def _parse_csv(data: bytes) -> tuple[list[Row], list[dict]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FeedInvalid("The file is not UTF-8 text. Save it as \"CSV UTF-8\".")
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        raise FeedInvalid("The file is empty: the first row must name the columns.")
    except csv.Error as exc:
        raise FeedInvalid(f"The CSV cannot be read: {exc}.")
    names = [h.strip() for h in header]
    dupes = sorted({n for n in names if n and names.count(n) > 1})
    if dupes:
        raise FeedInvalid(f"These columns appear twice in the header: {', '.join(dupes)}.")
    missing = [c for c in REQUIRED_HEADER if c not in names]
    if missing:
        raise FeedInvalid(f"The header is missing required columns: {', '.join(missing)}.")
    warnings = [{"column": n, "code": "unknown_column"} for n in names if n and n not in COLUMNS]
    rows: list[Row] = []
    try:
        for i, cells in enumerate(reader, start=2):
            if not any(c.strip() for c in cells):
                continue
            if len(rows) >= MAX_ROWS:
                raise FeedTooLarge(f"A feed holds at most {MAX_ROWS} rows; split it by category.")
            rows.append(Row(i, {n: (cells[k] if k < len(cells) else "") for k, n in enumerate(names) if n in COLUMNS}))
    except csv.Error as exc:
        raise FeedInvalid(f"The CSV cannot be read near row {reader.line_num}: {exc}.")
    return rows, warnings


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(Decimal(repr(value)), "f")
    if isinstance(value, (list, tuple)):
        return ";".join(_cell(v) for v in value)
    return str(value)


def _parse_json(data: bytes) -> tuple[list[Row], list[dict], dict[str, list]]:
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise FeedInvalid(f"The file is not valid JSON: {str(exc)[:120]}.")
    if not isinstance(doc, dict) or doc.get("schema") != FEED_SCHEMA or not isinstance(doc.get("products"), list):
        raise FeedInvalid(f'A JSON feed is {{"schema": "{FEED_SCHEMA}", "products": [...]}}.')
    rows: list[Row] = []
    includes: dict[str, list] = {}
    n = 0
    for p in doc["products"]:
        if not isinstance(p, dict) or not isinstance(p.get("variants", []), list):
            raise FeedInvalid("Every product is an object with a list of variants.")
        base = {k: _cell(p.get(k)) for k in PRODUCT_COLUMNS}
        base["sku"] = _cell(p.get("sku"))
        if isinstance(p.get("includes"), list):
            includes[base["sku"]] = p["includes"]
        for v in p.get("variants", []):
            if not isinstance(v, dict) or not isinstance(v.get("prices", []), list):
                raise FeedInvalid("Every variant is an object with a list of prices.")
            options = v.get("options") if isinstance(v.get("options"), dict) else {}
            dims = v.get("dims_mm") if isinstance(v.get("dims_mm"), list) else []
            vbase = {
                "variant_id": _cell(v.get("variant_id")),
                "gtin": _cell(v.get("gtin")),
                "option_size": _cell(options.get("size")),
                "option_colour": _cell(options.get("colour")),
                "option_finish": _cell(options.get("finish")),
                "materials": _cell(v.get("materials")),
                "width_mm": _cell(dims[0]) if len(dims) > 0 else "",
                "height_mm": _cell(dims[1]) if len(dims) > 1 else "",
                "depth_mm": _cell(dims[2]) if len(dims) > 2 else "",
                "geometry_url": _cell(v.get("geometry_url")),
                "image_urls": _cell(v.get("image_urls")),
            }
            avail = v.get("availability")
            vavail = avail if isinstance(avail, dict) else ({"availability": avail} if isinstance(avail, str) else {})
            for pr in v.get("prices", []):
                if not isinstance(pr, dict):
                    raise FeedInvalid("Every price is an object.")
                n += 1
                if n > MAX_ROWS:
                    raise FeedTooLarge(f"A feed holds at most {MAX_ROWS} rows; split it by category.")
                cells = {**base, **vbase}
                for k in (
                    "region", "currency", "price", "price_includes_tax", "tax_rate_percent", "delivery_fee",
                    "delivery_days_min", "delivery_days_max", "stock", "lead_time_days", "status", "availability",
                ):  # fmt: skip
                    cells[k] = _cell(pr[k] if k in pr else vavail.get(k))
                rows.append(Row(n, cells))
    return rows, [], includes


def parse(data: bytes, fmt: str) -> tuple[list[Row], list[dict], dict[str, list]]:
    """Rows, warnings and (JSON) theme includes. Raises FeedInvalid or FeedTooLarge."""
    if len(data) > MAX_BYTES:
        raise FeedTooLarge("A feed file is at most 50 MB; split it by category.")
    if fmt == "csv":
        rows, warnings = _parse_csv(data)
        return rows, warnings, {}
    if fmt == "json":
        return _parse_json(data)
    raise FeedInvalid("format is csv or json")


def validate(data: bytes, fmt: str) -> None:
    """The synchronous check at upload (header and shape only)."""
    parse(data, fmt)


# --- Row checks ---------------------------------------------------------------------------


def gtin_ok(text: str) -> bool:
    if not text.isdigit() or len(text) not in (8, 12, 13, 14):
        return False
    digits = [int(d) for d in text]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def _int(text: str) -> int:
    if not re.fullmatch(r"\d{1,9}", text):
        raise ValueError(text)
    return int(text)


@dataclass
class Checked:
    row: Row
    errors: list[tuple[str, str]] = field(default_factory=list)
    product: dict = field(default_factory=dict)
    variant: dict = field(default_factory=dict)
    offer: dict = field(default_factory=dict)
    product_errors: bool = False
    variant_errors: bool = False


def _check(row: Row, categories: dict, regions: dict[str, MarketRegion], warnings: list[dict]) -> Checked:
    c = Checked(row)

    def err(column: str, code: str) -> None:
        c.errors.append((column, code))
        if column in PRODUCT_COLUMNS or column == "sku":
            c.product_errors = True
        if column in VARIANT_COLUMNS or column == "variant_id":
            c.variant_errors = True

    def text(column: str, limit: int, required: bool = False) -> str:
        value = row.get(column)
        if required and not value:
            err(column, "missing_required")
        elif len(value) > limit:
            err(column, "too_long")
        return value

    sku = text("sku", 64, True)
    variant_id = text("variant_id", 64, True)
    name = text("name", 120, True)
    category = row.get("category")
    if not category:
        err("category", "missing_required")
    elif category not in categories:
        err("category", "unknown_category")
    kind = row.get("kind") or "object"
    if kind not in KINDS:
        err("kind", "unknown_kind")
    description = text("description", 2000)
    brand = text("brand", 70)
    classification = []
    for pair in [p.strip() for p in row.get("classification").split(";") if p.strip()]:
        scheme, _, code = pair.partition(":")
        if scheme in CLASSIFICATION_SCHEMES and code and len(pair) <= 64:
            classification.append(pair)
        else:
            warnings.append({"row": row.number, "column": "classification", "code": "classification_ignored", "value": pair[:100]})
    c.product = {
        "name": name,
        "category": category,
        "kind": kind,
        "description": description,
        "brand": brand or None,
        "classification": classification or None,
    }

    options = {}
    for col, key in (("option_size", "size"), ("option_colour", "colour"), ("option_finish", "finish")):
        value = text(col, 40)
        if value:
            options[key] = value
    materials = [m.strip() for m in row.get("materials").split(";") if m.strip()]
    if any(len(m) > 40 for m in materials):
        err("materials", "too_long")
    dims = []
    for col in ("width_mm", "height_mm", "depth_mm"):
        value = row.get(col)
        if not value:
            if kind == "object":
                err(col, "missing_required")
            continue
        try:
            n = _int(value)
            if not 0 < n <= 100_000:
                raise ValueError
            dims.append(n)
        except ValueError:
            err(col, "bad_dims")
    geometry_url = row.get("geometry_url")
    fmt = None
    if not geometry_url:
        if kind == "object":
            err("geometry_url", "missing_required")
    elif not media.is_https_url(geometry_url):
        err("geometry_url", "bad_url")
    elif (fmt := media.geometry_format(geometry_url)) is None:
        err("geometry_url", "bad_geometry_format")
    images = [u.strip() for u in row.get("image_urls").split(";") if u.strip()]
    if not images:
        err("image_urls", "missing_required")
    elif len(images) > MAX_IMAGES or any(not media.is_https_url(u) for u in images):
        err("image_urls", "bad_url")
    gtin = row.get("gtin")
    if gtin and not gtin_ok(gtin):
        err("gtin", "bad_gtin")
    c.variant = {
        "options": options,
        "materials": materials,
        "dims_mm": dims if len(dims) == 3 else None,
        "geometry_url": geometry_url or None,
        "geometry_format": fmt,
        "image_urls": images,
        "gtin": gtin or None,
    }

    c.offer = check_offer(row, regions, err)
    c.product["sku"], c.variant["variant_id"] = sku, variant_id
    return c


def check_offer(row: Row, regions: dict[str, MarketRegion], err) -> dict:
    """The row columns of §6.4 (region, currency, price, tax, delivery, stock,
    status, availability) → the offer; `err(column, code)` records a problem.
    PF8's price grid writes through this, so the grid and a feed refuse the
    same values with the same codes."""
    region = regions.get(row.get("region"))
    if not row.get("region"):
        err("region", "missing_required")
    elif region is None:
        err("region", "unknown_region")
    currency = row.get("currency")
    if not currency:
        err("currency", "missing_required")
    elif region is not None and currency != region.currency:
        err("currency", "currency_mismatch")
    amount = None
    if not row.get("price"):
        err("price", "missing_required")
    elif region is not None:
        try:
            amount = parse_major(row.get("price"), region.exponent)
        except ValueError:
            err("price", "bad_price")
    includes_tax = None
    flag = row.get("price_includes_tax").lower()
    if not flag:
        err("price_includes_tax", "missing_required")
    elif flag not in ("true", "false"):
        err("price_includes_tax", "bad_bool")
    else:
        includes_tax = flag == "true"
    tax_bp = region.tax_rate_bp if region is not None else None
    if row.get("tax_rate_percent"):
        try:
            tax_bp = parse_percent_bp(row.get("tax_rate_percent"))
        except ValueError:
            err("tax_rate_percent", "bad_price")
    delivery_fee = None
    if row.get("delivery_fee") and region is not None:
        try:
            delivery_fee = parse_major(row.get("delivery_fee"), region.exponent)
        except ValueError:
            err("delivery_fee", "bad_price")
    ints: dict[str, int | None] = {}
    for col in ("delivery_days_min", "delivery_days_max", "stock", "lead_time_days"):
        value = row.get(col)
        ints[col] = None
        if value:
            try:
                ints[col] = _int(value)
            except ValueError:
                err(col, "bad_integer")
    if ints["delivery_days_min"] is not None and ints["delivery_days_max"] is not None and ints["delivery_days_min"] > ints["delivery_days_max"]:
        err("delivery_days_max", "bad_integer")
    status = row.get("status") or "active"
    if status not in ROW_STATUSES:
        err("status", "bad_status")
    stated = row.get("availability")
    if stated and stated not in FEED_AVAILABILITY:
        err("availability", "bad_availability")
    elif stated == "made_to_order" and ints["lead_time_days"] is None:
        err("availability", "bad_availability")
    return {
        "region": row.get("region"),
        "currency": currency,
        "amount": amount,
        "includes_tax": includes_tax,
        "tax_rate_bp": tax_bp,
        "delivery_fee": delivery_fee,
        "delivery_days_min": ints["delivery_days_min"],
        "delivery_days_max": ints["delivery_days_max"],
        "status": status,
        "availability": derive_availability(status, stated or None, ints["stock"], ints["lead_time_days"]),
    }


def derive_availability(status: str, stated: str | None, stock: int | None, lead: int | None) -> dict:
    """§6.4 (1.1.0): discontinued wins; then the `availability` column; then
    stock > 0 → in_stock, stock 0 → made_to_order with a lead time else
    out_of_stock; no stock → made_to_order with a lead time, else in_stock
    with stock not tracked. `low_stock` is never derived."""
    if status == "discontinued":
        state = "discontinued"
    elif stated:
        state = stated
    elif stock is not None:
        state = "in_stock" if stock > 0 else ("made_to_order" if lead is not None else "out_of_stock")
    else:
        state = "made_to_order" if lead is not None else "in_stock"
    return {
        "state": state,
        "stock": stock,
        "lead_time_days": lead if state == "made_to_order" else None,
    }


# --- The run ---------------------------------------------------------------------------


@dataclass
class Report:
    rows: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    hidden: int = 0
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    error_count: int = 0
    # New products and variants (the portal's dry run shows them beside the row counts).
    new_products: int = 0
    new_variants: int = 0

    def error(self, row: Row, column: str, code: str) -> None:
        self.error_count += 1
        if len(self.errors) < MAX_ERRORS:
            self.errors.append({"row": row.number, "column": column, "code": code, "value": row.get(column)[:200]})


def asset_id(product_id: str, variant_id: str) -> str:
    """A stable S1 asset id per product variant (contract §6.1 geometry.asset)."""
    return hashlib.sha256(f"truebex-market-asset\n{product_id}\n{variant_id}".encode()).hexdigest()[:32]


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def import_rows(
    db: Session,
    supplier: Supplier,
    rows: list[Row],
    *,
    mode: str = "upsert",
    fetcher: media.Fetcher | None = None,
    store: Store | None = None,
    feed_id: str | None = None,
    dry_run: bool = False,
    warnings: list[dict] | None = None,
    includes: dict[str, list] | None = None,
    new_status: str | None = None,
) -> Report:
    """Apply §6.4 rows for one supplier. Commits, or rolls back when dry_run
    (nothing fetched, nothing stored). New products start in `new_status`:
    by default `pending_review` for a verified supplier and `draft` for one
    still under review (PF8: unverified suppliers prepare, never publish)."""
    if new_status is None:
        new_status = "pending_review" if supplier.status == "verified" else "draft"
    if mode not in ("upsert", "replace"):
        raise FeedInvalid("mode is upsert or replace")
    at = now()
    store = store or get_store()
    fetcher = fetcher or media.HttpFetcher()
    report = Report(rows=len(rows), warnings=list(warnings or []))
    categories = active_categories(db)
    regions = active_regions(db)

    # 1. Field checks.
    checked = [_check(r, categories, regions, report.warnings) for r in rows]

    # 2. Duplicates and agreement between a SKU's (and a variant's) rows.
    first_product: dict[str, Checked] = {}
    first_variant: dict[tuple[str, str], Checked] = {}
    seen_keys: set[tuple[str, str, str]] = set()
    for c in checked:
        sku, vid, region = c.product["sku"], c.variant["variant_id"], c.offer["region"]
        if not sku or not vid:
            continue
        key = (sku, vid, region)
        if key in seen_keys and region:
            c.errors.append(("region", "duplicate_row"))
        seen_keys.add(key)
        if not c.product_errors:
            head = first_product.setdefault(sku, c)
            if head is not c:
                for col in PRODUCT_COLUMNS:
                    if not _same(head.product.get(col), c.product.get(col)):
                        c.errors.append((col, "inconsistent_product"))
                        break
        if not c.variant_errors:
            head_v = first_variant.setdefault((sku, vid), c)
            if head_v is not c:
                for col, k in (
                    ("option_size", "options"), ("materials", "materials"), ("width_mm", "dims_mm"),
                    ("geometry_url", "geometry_url"), ("image_urls", "image_urls"), ("gtin", "gtin"),
                ):  # fmt: skip
                    if not _same(head_v.variant.get(k), c.variant.get(k)):
                        c.errors.append((col, "inconsistent_product"))
                        break

    # 3. Geometry and images, once per variant (skipped in a dry run).
    existing_products = {p.sku: p for p in db.scalars(select(Product).where(Product.supplier_id == supplier.supplier_id))}
    pids = [p.product_id for p in existing_products.values()]
    existing_variants: dict[tuple[str, str], ProductVariant] = {}
    variants_of: dict[str, list[ProductVariant]] = defaultdict(list)  # product_id → its variants
    for start in range(0, len(pids), 500):
        for v in db.scalars(select(ProductVariant).where(ProductVariant.product_id.in_(pids[start : start + 500]))):
            existing_variants[(v.product_id, v.variant_id)] = v
            variants_of[v.product_id].append(v)
    media_of: dict[tuple[str, str], dict] = {}
    fetched: dict[str, object] = {}
    by_variant: dict[tuple[str, str], list[Checked]] = defaultdict(list)
    for c in checked:
        if not c.errors:
            by_variant[(c.product["sku"], c.variant["variant_id"])].append(c)
    for (sku, vid), group in by_variant.items():
        head = group[0]
        prod = existing_products.get(sku)
        old = existing_variants.get((prod.product_id, vid)) if prod else None
        geometry_url, images = head.variant["geometry_url"], head.variant["image_urls"]
        out = {"geometry": None, "images": []}
        problem = None
        if dry_run:
            out = {"geometry": old.geometry if old else None, "images": old.images if old else []}
        else:
            if geometry_url and old is not None and old.geometry_src == geometry_url and old.geometry:
                out["geometry"] = old.geometry
            elif geometry_url:
                try:
                    data = fetched.get(geometry_url) or fetcher.get(geometry_url, media.MAX_GEOMETRY_BYTES)
                    fetched[geometry_url] = data
                    out["geometry"] = media.store_geometry(store, data, head.variant["geometry_format"])
                except media.MediaError as exc:
                    problem = ("geometry_url", "bad_geometry_format" if exc.code == "bad_geometry_format" else "geometry_fetch_failed")
            joined = ";".join(images)
            if problem is None and old is not None and old.images_src == joined and old.images:
                out["images"] = old.images
            elif problem is None:
                for url in images:
                    try:
                        cached = fetched.get(url)
                        if not isinstance(cached, media.StoredImage):
                            cached = media.store_image(store, fetcher.get(url, media.MAX_IMAGE_BYTES))
                            fetched[url] = cached
                        out["images"].append(cached.sha256)
                    except media.MediaError as exc:
                        problem = ("image_urls", "image_too_small" if exc.code == "image_too_small" else "image_fetch_failed")
                        break
        if problem:
            for c in group:
                c.errors.append(problem)
        else:
            media_of[(sku, vid)] = out

    # 4. Write.
    for c in checked:
        if c.errors:
            report.rejected += 1
            for column, code in c.errors:
                report.error(c.row, column, code)
    good = [c for c in checked if not c.errors]
    by_sku: dict[str, list[Checked]] = defaultdict(list)
    for c in good:
        by_sku[c.product["sku"]].append(c)

    price_rows: dict[tuple[str, str, str], VariantPrice] = {}
    avail_rows: dict[tuple[str, str, str], VariantAvailability] = {}
    for start in range(0, len(pids), 500):
        chunk = pids[start : start + 500]
        for p in db.scalars(select(VariantPrice).where(VariantPrice.product_id.in_(chunk))):
            price_rows[(p.product_id, p.variant_id, p.region)] = p
        for a in db.scalars(select(VariantAvailability).where(VariantAvailability.product_id.in_(chunk))):
            avail_rows[(a.product_id, a.variant_id, a.region)] = a
    supplier_regions = {
        r.region: r for r in db.scalars(select(SupplierRegion).where(SupplierRegion.supplier_id == supplier.supplier_id))
    }
    touched: list[Product] = []
    thumbs_changed: set[str] = set()

    for sku, group in by_sku.items():
        head = group[0]
        product = existing_products.get(sku)
        product_changed = False
        if product is None:
            product = Product(
                product_id=new_id(),
                supplier_id=supplier.supplier_id,
                sku=sku,
                status=new_status,
                images=[],
                includes=[],
                created_at=at,
            )
            existing_products[sku] = product
            product_changed = True
            report.new_products += 1
        for col in PRODUCT_COLUMNS:
            if not _same(getattr(product, col), head.product[col]):
                setattr(product, col, head.product[col] if col != "description" else (head.product[col] or ""))
                product_changed = True
        if product.status == "hidden" and product.prev_status:
            product.status, product.prev_status = product.prev_status, None
            product_changed = True
        if includes and sku in includes:
            refs = [
                {
                    "supplier_id": str(i.get("supplier_id") or supplier.supplier_id),
                    "sku": str(i.get("sku", ""))[:64],
                    "variant_id": str(i.get("variant_id") or "default")[:64],
                }
                for i in includes[sku]
                if isinstance(i, dict) and i.get("sku")
            ]
            if not _same(product.includes, refs):
                product.includes = refs
                product_changed = True
        db.add(product)
        db.flush()

        variant_changed: dict[str, bool] = {}
        sort_next = max((v.sort for v in variants_of[product.product_id]), default=-1) + 1
        for c in group:
            vid = c.variant["variant_id"]
            if vid in variant_changed:
                continue
            v = existing_variants.get((product.product_id, vid))
            changed = False
            if v is None:
                v = ProductVariant(product_id=product.product_id, variant_id=vid, sort=sort_next, options={}, materials=[], images=[])
                sort_next += 1
                report.new_variants += 1
                existing_variants[(product.product_id, vid)] = v
                variants_of[product.product_id].append(v)
                changed = True
            m = media_of.get((sku, vid), {"geometry": None, "images": []})
            geometry = None
            if m["geometry"]:
                g = dict(m["geometry"])
                old_asset = (v.geometry or {}).get("asset") or {}
                rev = old_asset.get("rev", 0) + (1 if (v.geometry or {}).get("sha256") != g["sha256"] else 0)
                g["asset"] = {
                    # Stable across feeds: an asset keeps the id it was given first.
                    "id": old_asset.get("id") or asset_id(product.product_id, vid),
                    "name": old_asset.get("name") or product.name,
                    "rev": max(rev, 1),
                    "kind": "object" if product.kind == "object" else "material",
                }
                geometry = g
            states = {x.offer["status"] for x in group if x.variant["variant_id"] == vid}
            status = "hidden" if states == {"hidden"} else ("discontinued" if states <= {"discontinued", "hidden"} else "active")
            new = {
                "gtin": c.variant["gtin"],
                "options": c.variant["options"],
                "dims_mm": c.variant["dims_mm"],
                "materials": c.variant["materials"],
                "geometry": geometry if not dry_run else v.geometry,
                "geometry_src": c.variant["geometry_url"],
                "images": m["images"],
                "images_src": ";".join(c.variant["image_urls"]),
                "status": status,
            }
            for k, value in new.items():
                if not _same(getattr(v, k), value):
                    setattr(v, k, value)
                    changed = True
            db.add(v)
            variant_changed[vid] = changed

        images: list[str] = []
        for v in sorted(variants_of[product.product_id], key=lambda x: x.sort):
            if v.status != "hidden":
                images += [sha for sha in (v.images or []) if sha not in images]
        if not dry_run and not _same(product.images, images):
            if (product.images or [None])[0] != (images or [None])[0]:
                thumbs_changed.add(product.product_id)
            product.images = images
            product_changed = True

        for c in group:
            vid, region = c.variant["variant_id"], c.offer["region"]
            key = (product.product_id, vid, region)
            o = c.offer
            if o["status"] == "hidden":
                existed = key in price_rows
                if existed:
                    db.delete(price_rows.pop(key))
                if key in avail_rows:
                    db.delete(avail_rows.pop(key))
                if existed or product_changed or variant_changed[vid]:
                    report.updated += 1
                else:
                    report.unchanged += 1
                continue
            sr = supplier_regions.get(region)
            if sr is None:
                sr = SupplierRegion(supplier_id=supplier.supplier_id, region=region, currency=o["currency"], active=True)
                supplier_regions[region] = sr
                db.add(sr)
            values = {
                "amount": o["amount"],
                "currency": o["currency"],
                "exponent": regions[region].exponent,
                "includes_tax": o["includes_tax"],
                "tax_rate_bp": o["tax_rate_bp"],
                "delivery_fee": o["delivery_fee"] if o["delivery_fee"] is not None else sr.default_delivery_fee,
                "delivery_days_min": o["delivery_days_min"] if o["delivery_days_min"] is not None else sr.delivery_days_min,
                "delivery_days_max": o["delivery_days_max"] if o["delivery_days_max"] is not None else sr.delivery_days_max,
            }
            price = price_rows.get(key)
            created = price is None
            price_changed = False
            if price is None:
                price = VariantPrice(product_id=product.product_id, variant_id=vid, region=region)
                price_rows[key] = price
            for k, value in values.items():
                if getattr(price, k) != value:
                    setattr(price, k, value)
                    price_changed = True
            price.source, price.feed_id, price.updated_at = "feed", feed_id, at
            db.add(price)
            a = o["availability"]
            avail = avail_rows.get(key)
            avail_changed = False
            if avail is None:
                avail = VariantAvailability(product_id=product.product_id, variant_id=vid, region=region)
                avail_rows[key] = avail
            for k in ("state", "stock", "lead_time_days"):
                if getattr(avail, k) != a[k]:
                    setattr(avail, k, a[k])
                    avail_changed = True
            avail.source, avail.stale, avail.updated_at = "feed", False, at
            db.add(avail)
            if created:
                report.created += 1
            elif product_changed or variant_changed[vid] or price_changed or avail_changed:
                report.updated += 1
            else:
                report.unchanged += 1
        db.add(product)
        touched.append(product)

    # 5. Replace: what the file omits is hidden. A rejected row still counts
    #    as listed, so a typo never hides what is already in the catalogue.
    if mode == "replace":
        in_file = {c.product["sku"] for c in checked if c.product["sku"]}
        in_file_variants = {(c.product["sku"], c.variant["variant_id"]) for c in checked}
        in_file_regions = {(c.product["sku"], c.variant["variant_id"], c.offer["region"]) for c in checked}
        sku_of = {p.product_id: sku for sku, p in existing_products.items()}
        for sku, product in existing_products.items():
            if sku not in in_file and product.status in ("approved", "pending_review", "draft"):
                product.prev_status, product.status = product.status, "hidden"
                db.add(product)
                report.hidden += 1
        for (pid, vid), v in existing_variants.items():
            sku = sku_of.get(pid)
            if sku in in_file and (sku, vid) not in in_file_variants and v.status != "hidden":
                v.status = "hidden"
                db.add(v)
        for pid, vid, region in list(price_rows):
            sku = sku_of.get(pid)
            if sku in in_file and (sku, vid) in in_file_variants and (sku, vid, region) not in in_file_regions:
                db.delete(price_rows.pop((pid, vid, region)))
                if (pid, vid, region) in avail_rows:
                    db.delete(avail_rows.pop((pid, vid, region)))

    if dry_run:
        db.rollback()
        return report

    # 6. Search index and picture-search embeddings.
    db.flush()
    from .search import reindex

    for product in touched:
        reindex(db, product, supplier)
    if thumbs_changed:
        db.execute(delete(ProductEmbedding).where(ProductEmbedding.product_id.in_(thumbs_changed)))
    db.commit()
    return report


# --- Runs (feed_runs) -------------------------------------------------------------------


def queue(
    db: Session, supplier: Supplier, data: bytes, fmt: str, mode: str, *, source: str = "upload", by_user_id: int | None = None
) -> FeedRun:
    """Check the header (FeedInvalid / FeedTooLarge raise here), store the
    file at market/feeds/<feed_id>/source and record a queued run."""
    if mode not in ("upsert", "replace"):
        raise FeedInvalid("mode is upsert or replace")
    validate(data, fmt)
    run = FeedRun(
        feed_id=new_id(),
        supplier_id=supplier.supplier_id,
        format=fmt,
        mode=mode,
        state="queued",
        source=source,
        by_user_id=by_user_id,
        created_at=now(),
    )
    key = f"market/feeds/{run.feed_id}/source"
    get_store().put(key, data, content_type="text/csv" if fmt == "csv" else "application/json")
    run.source_key = key
    db.add(run)
    db.commit()
    return run


def execute(db: Session, feed_id: str, *, fetcher: media.Fetcher | None = None, store: Store | None = None) -> FeedRun:
    """Run a queued feed; the report is saved beside the source."""
    store = store or get_store()
    run = db.get(FeedRun, feed_id)
    if run is None or run.state not in ("queued", "failed"):
        return run
    supplier = db.get(Supplier, run.supplier_id)
    run.state, run.started_at = "running", now()
    db.add(run)
    db.commit()
    try:
        with store.open(run.source_key) as fh:
            data = fh.read()
        rows, warnings, includes = parse(data, run.format)
        report = import_rows(
            db, supplier, rows, mode=run.mode, fetcher=fetcher, store=store, feed_id=run.feed_id,
            warnings=warnings, includes=includes,
            # An admin's import goes to the review queue whatever the supplier's state.
            new_status="pending_review" if run.source == "admin" else None,
        )  # fmt: skip
    except (FeedInvalid, FeedTooLarge) as exc:
        db.rollback()
        run = db.get(FeedRun, feed_id)
        run.state, run.detail, run.finished_at = "failed", str(exc)[:500], now()
        db.add(run)
        db.commit()
        return run
    except Exception as exc:  # a bug or the store failed: the run reports it
        log.exception("feed %s failed", feed_id)
        db.rollback()
        run = db.get(FeedRun, feed_id)
        run.state, run.detail, run.finished_at = "failed", f"internal error: {type(exc).__name__}", now()
        db.add(run)
        db.commit()
        return run
    run = db.get(FeedRun, feed_id)
    run.state = "done"
    run.rows, run.created, run.updated = report.rows, report.created, report.updated
    run.unchanged, run.rejected, run.hidden = report.unchanged, report.rejected, report.hidden
    run.errors, run.warnings = report.errors, report.warnings[:MAX_ERRORS]
    run.finished_at = now()
    run.report_key = f"market/feeds/{run.feed_id}/report.json"
    store.put(run.report_key, json.dumps(report_json(run), indent=2).encode(), content_type="application/json")
    db.add(run)
    db.commit()
    return run


def run_feed(db: Session, supplier: Supplier, data: bytes, fmt: str, mode: str, **kw) -> FeedRun:
    fetcher = kw.pop("fetcher", None)
    store = kw.pop("store", None)
    run = queue(db, supplier, data, fmt, mode, **kw)
    return execute(db, run.feed_id, fetcher=fetcher, store=store)


def dry_run(db: Session, supplier: Supplier, data: bytes, fmt: str, mode: str) -> dict:
    """What a run would do, without fetching, storing or writing (PF8's preview)."""
    rows, warnings, includes = parse(data, fmt)
    return dry_run_rows(db, supplier, rows, mode, warnings, includes)


def dry_run_rows(
    db: Session, supplier: Supplier, rows: list[Row], mode: str, warnings: list[dict] | None = None, includes: dict | None = None
) -> dict:
    report = import_rows(db, supplier, rows, mode=mode, dry_run=True, warnings=warnings, includes=includes)
    return {
        "state": "dry_run",
        "rows": report.rows,
        "created": report.created,
        "updated": report.updated,
        "unchanged": report.unchanged,
        "rejected": report.rejected,
        "hidden": report.hidden,
        "errors": report.errors,
        "warnings": report.warnings[:MAX_ERRORS],
        "new_products": report.new_products,
        "new_variants": report.new_variants,
    }


def report_json(run: FeedRun) -> dict:
    """§5.13, plus `hidden`, `warnings` and the run's details."""
    return {
        "feed_id": run.feed_id,
        "state": run.state,
        "rows": run.rows,
        "created": run.created,
        "updated": run.updated,
        "unchanged": run.unchanged,
        "rejected": run.rejected,
        "errors": run.errors or [],
        "hidden": run.hidden,
        "warnings": run.warnings or [],
        "format": run.format,
        "mode": run.mode,
        "source": run.source,
        "detail": run.detail,
        "supplier_id": run.supplier_id,
        "created_at": rfc3339(run.created_at),
        "finished_at": rfc3339(run.finished_at),
    }
