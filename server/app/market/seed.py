"""Load a fixture catalogue into the database: the seed script, the fixture
generator and the tests share it. Two shapes are read:

* PF7's own (`truebex-market-fixture/1`, server/tests/fixtures/market/): one
  supplier and its products, each variant with its §6.3 price, delivery and
  availability per region under `regions`. Images and geometry are files
  beside it; `media-map.json` maps the https URLs the feed files use to those
  files, so a feed import in a test or on a local machine fetches nothing
  from the internet.
* The app's stub (`truebex-market-stub/1`, MK1's set copied into
  server/tests/contracts/marketplace/, contract §9): suppliers and products
  each written once, a variant's `prices` and `deliveries` keyed by region,
  one `availability` (and, since MK2, `availabilities` keyed by region for a
  region where it differs, projected like prices: PF7e), a product's
  `substitutes`. Its files are named by
  `https://market.truebex.com/files/<path>`, served from the folder (PF7c).
"""

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..licence import clock
from ..storage import Store, get_store
from . import media
from .catalogue import add_category, add_member, create_supplier, set_supplier_regions
from .models import MarketRegion, Product, ProductVariant, Supplier, VariantAvailability, VariantPrice
from .search import reindex
from .taxonomy import active_categories, active_regions, app_path_of

STUB_SCHEMA = "truebex-market-stub/1"
STUB_FILES = "/files/"


class StubFetcher:
    """The stub's rule (its README): any https URL whose path holds `/files/`
    is the file of that path in the folder; nothing outside it."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder.resolve()

    def path_of(self, url: str) -> Path | None:
        parts = urlsplit(url)
        if parts.scheme != "https" or STUB_FILES not in parts.path:
            return None
        path = (self.folder / parts.path.split(STUB_FILES, 1)[1]).resolve()
        return path if path.is_relative_to(self.folder) and path.is_file() else None

    def get(self, url: str, max_bytes: int) -> bytes:
        path = self.path_of(url)
        if path is None:
            raise media.MediaError("fetch_failed", "404")
        data = path.read_bytes()
        if len(data) > max_bytes:
            raise media.MediaError("too_large", f"over {max_bytes} bytes")
        return data


def media_fetcher(folder: Path) -> media.Fetcher:
    """The fixture's files by the URLs its feeds name: PF7's media-map.json,
    or the stub's /files/ rule for a folder without one (the app's set)."""
    if not (folder / "media-map.json").is_file():
        return StubFetcher(folder)
    mapping = json.loads((folder / "media-map.json").read_text(encoding="utf-8"))["urls"]
    return media.MapFetcher({url: folder / rel for url, rel in mapping.items()})


def is_stub(folder: Path) -> bool:
    data = json.loads((folder / "products.json").read_text(encoding="utf-8"))
    return data.get("schema") == STUB_SCHEMA


def load_catalogue(
    db: Session,
    folder: Path,
    *,
    store: Store | None = None,
    payments_ready: bool = False,
    owner=None,
) -> list[Supplier]:
    """Create (or refresh) the folder's suppliers, verified, and their
    products, approved, as products.json states them; either shape. Returns
    the suppliers in the file's order."""
    if is_stub(folder):
        return _load_stub(db, folder, store=store or get_store(), payments_ready=payments_ready, owner=owner)
    return [load_fixture(db, folder, store=store, payments_ready=payments_ready, owner=owner)]


def load_fixture(
    db: Session,
    folder: Path,
    *,
    store: Store | None = None,
    payments_ready: bool = False,
    owner=None,
) -> Supplier:
    """Create (or refresh) the fixture's supplier, verified, and its products
    as products.json states them. Returns the supplier (the stub's first)."""
    store = store or get_store()
    if is_stub(folder):
        return _load_stub(db, folder, store=store, payments_ready=payments_ready, owner=owner)[0]
    data = json.loads((folder / "products.json").read_text(encoding="utf-8"))
    at = clock.parse_rfc3339(data["at"])
    spec = data["supplier"]
    regions = active_regions(db)
    supplier = db.get(Supplier, spec["supplier_id"])
    if supplier is None:
        supplier = create_supplier(db, supplier_id=spec["supplier_id"], name=spec["name"], country=spec["country"])
    for key in ("name", "legal_name", "country", "company_number", "vat_id", "website", "contact_email"):
        setattr(supplier, key, spec.get(key))
    supplier.status, supplier.verified_at = "verified", at
    if payments_ready:
        supplier.connect_account_id, supplier.connect_ready = spec.get("connect_account_id") or "acct_fixture", True
    db.add(supplier)
    set_supplier_regions(db, supplier, {r: regions[r] for r in spec["regions"]})
    if owner is not None:
        add_member(db, supplier, owner, "owner")
    db.flush()

    for n, p in enumerate(data["products"]):
        product = db.get(Product, p["product_id"]) or Product(product_id=p["product_id"], supplier_id=supplier.supplier_id)
        images = [media.store_image(store, (folder / rel).read_bytes()).sha256 for rel in p["images"]]
        product.sku, product.name, product.kind = p["sku"], p["name"], p["kind"]
        product.category, product.description = p["category"], p.get("description", "")
        product.brand, product.classification = p.get("brand"), p.get("classification")
        product.images, product.includes = images, p.get("includes", [])
        product.status = p.get("status", "approved")
        product.approved_at = at if product.status in ("approved", "withdrawn", "hidden") else None
        product.created_at = at
        db.add(product)
        db.flush()
        for sort, v in enumerate(p["variants"]):
            variant = _variant(db, product, v["variant_id"])
            variant.sort, variant.gtin = sort, v.get("gtin")
            variant.options, variant.dims_mm, variant.materials = v.get("options", {}), v.get("dims_mm"), v.get("materials", [])
            variant.status = v.get("status", "active")
            variant.images = [media.store_image(store, (folder / rel).read_bytes()).sha256 for rel in v.get("images", [])]
            variant.images_src = ";".join(v.get("image_urls", [])) or None
            variant.geometry, variant.geometry_src = None, v.get("geometry_url")
            if v.get("geometry"):
                g = v["geometry"]
                stored = media.store_geometry(store, (folder / g["file"]).read_bytes(), g["format"])
                if stored["sha256"] != g["sha256"]:
                    raise ValueError(f"{g['file']}: SHA-256 differs from products.json")
                variant.geometry = {**stored, "asset": g["asset"]}
            db.add(variant)
            for region, offer in v["regions"].items():
                _offer(db, product, v["variant_id"], region, offer["price"], offer.get("delivery"), offer["availability"], at)
        db.flush()
        reindex(db, product, supplier)
    db.commit()
    return supplier


# --- The app's stub shape (PF7c) --------------------------------------------------------------


def _variant(db: Session, product: Product, variant_id: str) -> ProductVariant:
    return db.scalar(
        select(ProductVariant).where(ProductVariant.product_id == product.product_id, ProductVariant.variant_id == variant_id)
    ) or ProductVariant(product_id=product.product_id, variant_id=variant_id)


def _offer(
    db: Session, product: Product, variant_id: str, region: str, pr: dict, d: dict | None, a: dict, at: datetime
) -> None:
    """A variant's price, delivery and availability in one region."""
    key = (VariantPrice.product_id == product.product_id, VariantPrice.variant_id == variant_id, VariantPrice.region == region)
    price = db.scalar(select(VariantPrice).where(*key)) or VariantPrice(
        product_id=product.product_id, variant_id=variant_id, region=region
    )
    price.amount, price.currency, price.exponent = pr["amount"], pr["currency"], pr["exponent"]
    price.includes_tax, price.tax_rate_bp = pr["includes_tax"], pr["tax_rate_bp"]
    d = d or {}
    price.delivery_fee = d["fee"]["amount"] if d.get("fee") else None
    price.delivery_days_min, price.delivery_days_max = d.get("days_min"), d.get("days_max")
    price.source, price.updated_at = "manual", clock.parse_rfc3339(pr["at"]) if pr.get("at") else at
    db.add(price)
    avail = db.scalar(
        select(VariantAvailability).where(
            VariantAvailability.product_id == product.product_id,
            VariantAvailability.variant_id == variant_id,
            VariantAvailability.region == region,
        )
    ) or VariantAvailability(product_id=product.product_id, variant_id=variant_id, region=region)
    avail.state, avail.stock, avail.lead_time_days = a["state"], a.get("stock"), a.get("lead_time_days")
    avail.source, avail.stale = "manual", False
    avail.updated_at = clock.parse_rfc3339(a["updated_at"]) if a.get("updated_at") else at
    db.add(avail)


def _stub_at(data: dict) -> datetime:
    """The catalogue's own time: the earliest price time it states."""
    times = [
        pr["at"] for p in data["products"] for v in p["variants"] for pr in v.get("prices", {}).values() if pr.get("at")
    ]
    return clock.parse_rfc3339(min(times)) if times else clock.now()


def _label(path: str, stated: dict[str, str]) -> str:
    return stated.get(path) or path.rsplit("/", 1)[-1].replace("-", " ").capitalize()


def _stub_categories(db: Session, folder: Path, data: dict) -> list[str]:
    """Paths the stub files products under that the platform's tree lacks
    (MK1's `furniture/tables/coffee`, `lighting/wall/sconces`) are added with
    the stub's labels, parents first, so 5.1 lists them and 5.3 filters by
    them. Returns the paths added."""
    stated: dict[str, str] = {}
    if (folder / "categories.json").is_file():
        cats = json.loads((folder / "categories.json").read_text(encoding="utf-8")).get("categories", [])
        stated = {c["path"]: c["label"] for c in cats if isinstance(c, dict) and c.get("path") and c.get("label")}
    have = set(active_categories(db))
    wanted: set[str] = set()
    for path in [*stated, *(p["category"] for p in data["products"])]:
        if app_path_of(path) is None:
            raise ValueError(f"category {path!r} is not rooted on the app's taxonomy")
        parts = path.split("/")
        wanted.update("/".join(parts[:n]) for n in range(1, len(parts) + 1))
    added = sorted((p for p in wanted - have), key=lambda p: (p.count("/"), p))
    for path in added:
        add_category(db, path, _label(path, stated))
    db.flush()
    return added


def _stub_file(folder: Path, fetcher: StubFetcher, url: str) -> bytes:
    path = fetcher.path_of(url)
    if path is None:
        raise ValueError(f"{url}: not a file of {folder}")
    return path.read_bytes()


def _load_stub(db: Session, folder: Path, *, store: Store, payments_ready: bool, owner) -> list[Supplier]:
    data = json.loads((folder / "products.json").read_text(encoding="utf-8"))
    at = _stub_at(data)
    files = StubFetcher(folder)
    regions: dict[str, MarketRegion] = active_regions(db)
    ids = {p["product_id"] for p in data["products"]}
    for p in data["products"]:
        unknown = [s for s in [*p.get("substitutes", []), *p.get("includes", [])] if s not in ids]
        if unknown:
            raise ValueError(f"{p['sku']}: substitutes or includes name products not in the file: {unknown}")
    _stub_categories(db, folder, data)

    suppliers: dict[str, Supplier] = {}
    for spec in data["suppliers"]:
        supplier = db.get(Supplier, spec["supplier_id"]) or create_supplier(
            db, supplier_id=spec["supplier_id"], name=spec["name"], country=spec["country"]
        )
        supplier.name, supplier.country, supplier.website = spec["name"], spec["country"], spec.get("website")
        # The platform lists only a verified supplier's products (5.3, 5.4) and
        # answers 5.6 only for one; a stub supplier marked `verified: false`
        # still sells in the stub, so it is verified here too (PF7c D12).
        supplier.status, supplier.verified_at = "verified", at
        if spec.get("logo_url"):
            supplier.logo_key = media.store_image(store, _stub_file(folder, files, spec["logo_url"])).sha256
        if payments_ready:
            supplier.connect_account_id, supplier.connect_ready = f"acct_fixture_{spec['supplier_id'][:8]}", True
        db.add(supplier)
        missing = [r for r in spec["regions"] if r not in regions]
        if missing:
            raise ValueError(f"{spec['name']}: regions {missing} are not marketplace regions")
        set_supplier_regions(db, supplier, {r: regions[r] for r in spec["regions"]})
        if owner is not None:
            add_member(db, supplier, owner, "owner")
        suppliers[supplier.supplier_id] = supplier
    db.flush()

    for p in data["products"]:
        supplier = suppliers.get(p["supplier_id"])
        if supplier is None:
            raise ValueError(f"{p['sku']}: supplier {p['supplier_id']} is not in the file")
        product = db.get(Product, p["product_id"]) or Product(product_id=p["product_id"], supplier_id=supplier.supplier_id)
        product.supplier_id = supplier.supplier_id
        product.sku, product.name, product.kind = p["sku"], p["name"], p["kind"]
        product.category, product.description = p["category"], p.get("description", "")
        product.brand, product.classification = p.get("brand"), p.get("classification")
        product.images = [media.store_image(store, _stub_file(folder, files, url)).sha256 for url in p.get("images", [])]
        product.includes = list(p.get("includes", []))
        product.status, product.prev_status, product.review_note = "approved", None, None
        product.approved_at = product.created_at = at
        db.add(product)
        db.flush()
        for sort, v in enumerate(p["variants"]):
            variant = _variant(db, product, v["variant_id"])
            a = v["availability"]
            per_region = v.get("availabilities") or {}
            variant.sort, variant.gtin = sort, v.get("gtin")
            variant.options, variant.dims_mm, variant.materials = v.get("options", {}), v.get("dims_mm"), v.get("materials", [])
            variant.status = "discontinued" if a["state"] == "discontinued" else "active"
            variant.images, variant.images_src = [], None
            variant.geometry, variant.geometry_src = None, None
            if v.get("geometry"):
                g = v["geometry"]
                stored = media.store_geometry(store, _stub_file(folder, files, g["url"]), g["format"])
                if (stored["sha256"], stored["bytes"]) != (g["sha256"], g["bytes"]):
                    raise ValueError(f"{g['url']}: SHA-256 or size differs from products.json")
                variant.geometry, variant.geometry_src = {**stored, "asset": g["asset"]}, g["url"]
            db.add(variant)
            for region, pr in v["prices"].items():
                if region not in regions or pr["currency"] != regions[region].currency:
                    raise ValueError(f"{p['sku']} / {v['variant_id']}: {region} {pr['currency']} is not a marketplace price list")
                deliveries = (v.get("deliveries") or {}).get(region)
                _offer(db, product, v["variant_id"], region, pr, deliveries, per_region.get(region, a), at)
        db.flush()
        reindex(db, product, supplier)
    db.commit()
    return list(suppliers.values())
