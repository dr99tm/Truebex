"""Load the contract's fixture catalogue (server/tests/contracts/marketplace/
products.json) into the database: the seed script, the fixture generator
and the tests share it.

products.json is the stub's catalogue (contract §9): one supplier and its
products, each variant with its §6.3 price, delivery and availability per
region. Images and geometry are files beside it; `media-map.json` maps the
https URLs the feed files use to those files, so a feed import in a test or
on a local machine fetches nothing from the internet.
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..licence import clock
from ..storage import Store, get_store
from . import media
from .catalogue import add_member, create_supplier, set_supplier_regions
from .models import Product, ProductVariant, Supplier, VariantAvailability, VariantPrice
from .search import reindex
from .taxonomy import active_regions


def media_fetcher(folder: Path) -> media.MapFetcher:
    mapping = json.loads((folder / "media-map.json").read_text(encoding="utf-8"))["urls"]
    return media.MapFetcher({url: folder / rel for url, rel in mapping.items()})


def load_fixture(
    db: Session,
    folder: Path,
    *,
    store: Store | None = None,
    payments_ready: bool = False,
    owner=None,
) -> Supplier:
    """Create (or refresh) the fixture's supplier, verified, and its products
    as products.json states them. Returns the supplier."""
    store = store or get_store()
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
            variant = db.scalar(
                select(ProductVariant).where(
                    ProductVariant.product_id == product.product_id, ProductVariant.variant_id == v["variant_id"]
                )
            ) or ProductVariant(product_id=product.product_id, variant_id=v["variant_id"])
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
                price = db.scalar(
                    select(VariantPrice).where(
                        VariantPrice.product_id == product.product_id,
                        VariantPrice.variant_id == v["variant_id"],
                        VariantPrice.region == region,
                    )
                ) or VariantPrice(product_id=product.product_id, variant_id=v["variant_id"], region=region)
                pr = offer["price"]
                price.amount, price.currency, price.exponent = pr["amount"], pr["currency"], pr["exponent"]
                price.includes_tax, price.tax_rate_bp = pr["includes_tax"], pr["tax_rate_bp"]
                d = offer.get("delivery") or {}
                price.delivery_fee = d["fee"]["amount"] if d.get("fee") else None
                price.delivery_days_min, price.delivery_days_max = d.get("days_min"), d.get("days_max")
                price.source, price.updated_at = "manual", at
                db.add(price)
                a = offer["availability"]
                avail = db.scalar(
                    select(VariantAvailability).where(
                        VariantAvailability.product_id == product.product_id,
                        VariantAvailability.variant_id == v["variant_id"],
                        VariantAvailability.region == region,
                    )
                ) or VariantAvailability(product_id=product.product_id, variant_id=v["variant_id"], region=region)
                avail.state, avail.stock, avail.lead_time_days = a["state"], a.get("stock"), a.get("lead_time_days")
                avail.source, avail.stale, avail.updated_at = "manual", False, at
                db.add(avail)
        db.flush()
        reindex(db, product, supplier)
    db.commit()
    return supplier
