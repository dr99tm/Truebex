"""Catalogue management in the portal (PF8 Scope 2): products, variants,
pictures and placeable geometry; submit for review, hide, withdraw, mark
discontinued.

A supplier edits its own `draft`, `rejected` and `approved` products. A
change to an approved product's name, kind, category, pictures or geometry
sends it back to review (`pending_review`); prices, stock and descriptions
do not. Unverified suppliers prepare products but cannot submit them.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..market import media
from ..market.catalogue import thumbnail_url
from ..market.common import invalid, is_hex32, new_id, not_found, now, rfc3339
from ..market.importer import asset_id, gtin_ok
from ..market.models import (
    Product,
    ProductEmbedding,
    ProductVariant,
    Supplier,
    VariantAvailability,
    VariantPrice,
)
from ..market.search import reindex
from ..market.taxonomy import active_categories, app_path_of
from ..storage import get_store
from . import geometry_check
from .common import Member, conflict, require_verified
from .schemas import ProductIn, ProductPatch, VariantIn, VariantPatch

EDITABLE = ("draft", "rejected", "approved")
# Changing these on an approved product sends it back to review.
REVIEWED_FIELDS = ("name", "kind", "category")
MAX_IMAGES_PER_VARIANT = 10
MAX_IMAGE_BYTES = media.MAX_IMAGE_BYTES


def owned(db: Session, supplier: Supplier, product_id: str) -> Product:
    """The supplier's own product; another supplier's is 404, never 403."""
    product = db.get(Product, product_id) if is_hex32(product_id) else None
    if product is None or product.supplier_id != supplier.supplier_id:
        raise not_found("That product")
    return product


def _variants(db: Session, product: Product) -> list[ProductVariant]:
    return list(
        db.scalars(select(ProductVariant).where(ProductVariant.product_id == product.product_id).order_by(ProductVariant.sort))
    )


def _variant(db: Session, product: Product, variant_id: str) -> ProductVariant:
    v = db.scalar(
        select(ProductVariant).where(ProductVariant.product_id == product.product_id, ProductVariant.variant_id == variant_id)
    )
    if v is None:
        raise not_found("That variant")
    return v


def summary_json(db: Session, product: Product, counts: dict | None = None) -> dict:
    return {
        "product_id": product.product_id,
        "sku": product.sku,
        "name": product.name,
        "kind": product.kind,
        "category": product.category,
        "status": product.status,
        "review_note": product.review_note,
        "thumbnail_url": thumbnail_url(product),
        "variants": (counts or {}).get(product.product_id, 0),
        "updated_at": rfc3339(product.updated_at),
    }


def list_products(db: Session, supplier: Supplier, status: str | None, q: str | None) -> dict:
    stmt = select(Product).where(Product.supplier_id == supplier.supplier_id)
    if status and status != "all":
        stmt = stmt.where(Product.status == status)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Product.name).like(like) | func.lower(Product.sku).like(like))
    rows = list(db.scalars(stmt.order_by(Product.updated_at.desc()).limit(1000)))
    counts = dict(
        db.execute(
            select(ProductVariant.product_id, func.count())
            .where(ProductVariant.product_id.in_([p.product_id for p in rows]), ProductVariant.status != "hidden")
            .group_by(ProductVariant.product_id)
        ).all()
    ) if rows else {}
    by_status = dict(
        db.execute(
            select(Product.status, func.count()).where(Product.supplier_id == supplier.supplier_id).group_by(Product.status)
        ).all()
    )
    return {"products": [summary_json(db, p, counts) for p in rows], "counts": by_status}


def variant_json(db: Session, v: ProductVariant) -> dict:
    g = v.geometry
    return {
        "variant_id": v.variant_id,
        "options": v.options or {},
        "dims_mm": v.dims_mm,
        "materials": v.materials or [],
        "gtin": v.gtin,
        "status": v.status,
        "images": [{"sha256": sha, "url": media.image_url(sha), "thumb_url": media.image_url(sha, thumb=True)} for sha in v.images or []],
        "geometry": (
            {
                "format": g["format"],
                "sha256": g["sha256"],
                "bytes": g["bytes"],
                "rev": (g.get("asset") or {}).get("rev"),
                "check": g.get("check"),
            }
            if g
            else None
        ),
    }


def detail_json(db: Session, product: Product) -> dict:
    variants = _variants(db, product)
    regions = db.execute(
        select(VariantPrice.variant_id, VariantPrice.region).where(VariantPrice.product_id == product.product_id)
    ).all()
    priced: dict[str, list[str]] = {}
    for vid, region in regions:
        priced.setdefault(vid, []).append(region)
    out = summary_json(db, product, {product.product_id: len([v for v in variants if v.status != "hidden"])})
    out.update(
        {
            "description": product.description or "",
            "brand": product.brand,
            "app_path": app_path_of(product.category),
            "images": [media.image_url(sha) for sha in product.images or []],
            "variants": [
                {**variant_json(db, v), "regions": sorted(priced.get(v.variant_id, []))} for v in variants if v.status != "hidden"
            ],
            "approved_at": rfc3339(product.approved_at),
            "created_at": rfc3339(product.created_at),
            "editable": product.status in EDITABLE,
        }
    )
    return out


def _category(db: Session, path: str) -> str:
    if path not in active_categories(db):
        raise ContractError(
            "unknown_category",
            422,
            "category: not a path of the category list (GET /market/categories)",
            {"fields": [{"field": "category", "in": "body", "message": "unknown_category"}]},
        )
    return path


def _touch(db: Session, product: Product, supplier: Supplier, *, review: bool = False) -> None:
    """Save, re-review an approved product when asked, and reindex."""
    if review and product.status == "approved":
        product.status, product.review_note = "pending_review", None
    product.updated_at = now()
    db.add(product)
    db.flush()
    reindex(db, product, supplier)
    db.commit()


def create(db: Session, m: Member, body: ProductIn) -> Product:
    if db.scalar(select(Product.product_id).where(Product.supplier_id == m.supplier.supplier_id, Product.sku == body.sku)):
        raise conflict(f"A product with SKU {body.sku} already exists.", "sku_taken")
    product = Product(
        product_id=new_id(),
        supplier_id=m.supplier.supplier_id,
        sku=body.sku,
        name=body.name,
        kind=body.kind,
        category=_category(db, body.category),
        description=body.description or "",
        brand=body.brand or None,
        images=[],
        includes=[],
        status="draft",
        created_at=now(),
    )
    db.add(product)
    _touch(db, product, m.supplier)
    return product


def _editable(product: Product) -> None:
    if product.status not in EDITABLE:
        labels = {"pending_review": "in review", "hidden": "hidden", "withdrawn": "withdrawn"}
        raise conflict(
            f"This product is {labels.get(product.status, product.status)}; it can be edited when it is a draft, rejected or approved.",
            "not_editable",
        )


def edit(db: Session, m: Member, product: Product, body: ProductPatch) -> Product:
    _editable(product)
    review = False
    changes = body.model_dump(exclude_unset=True)
    if "category" in changes:
        _category(db, changes["category"])
    for field_name, value in changes.items():
        if field_name == "description":
            value = value or ""
        if field_name == "brand":
            value = value or None
        if getattr(product, field_name) != value:
            setattr(product, field_name, value)
            review = review or field_name in REVIEWED_FIELDS
    _touch(db, product, m.supplier, review=review)
    return product


def add_variant(db: Session, m: Member, product: Product, body: VariantIn) -> ProductVariant:
    _editable(product)
    if body.gtin and not gtin_ok(body.gtin):
        raise invalid("gtin", "bad_gtin: wrong length or check digit", "body")
    existing = db.scalar(
        select(ProductVariant).where(ProductVariant.product_id == product.product_id, ProductVariant.variant_id == body.variant_id)
    )
    if existing is not None and existing.status != "hidden":
        raise conflict(f"Variant {body.variant_id} already exists.", "variant_taken")
    sort = (db.scalar(select(func.max(ProductVariant.sort)).where(ProductVariant.product_id == product.product_id)) or 0) + 1
    v = existing or ProductVariant(product_id=product.product_id, variant_id=body.variant_id, sort=sort, images=[])
    v.options = {k: val for k, val in body.options.model_dump().items() if val}
    v.dims_mm, v.materials, v.gtin, v.status = body.dims_mm, body.materials, body.gtin, "active"
    db.add(v)
    _touch(db, product, m.supplier)
    return v


def edit_variant(db: Session, m: Member, product: Product, variant_id: str, body: VariantPatch) -> ProductVariant:
    _editable(product)
    v = _variant(db, product, variant_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("gtin"):
        if not gtin_ok(changes["gtin"]):
            raise invalid("gtin", "bad_gtin: wrong length or check digit", "body")
    if "options" in changes:
        v.options = {k: val for k, val in (changes["options"] or {}).items() if val}
    if "dims_mm" in changes:
        v.dims_mm = changes["dims_mm"]
    if "materials" in changes:
        v.materials = changes["materials"] or []
    if "gtin" in changes:
        v.gtin = changes["gtin"] or None
    if changes.get("status"):
        v.status = changes["status"]
        if v.status == "discontinued":
            _discontinue_offers(db, product, [v.variant_id])
    db.add(v)
    _touch(db, product, m.supplier)
    return v


def remove_variant(db: Session, m: Member, product: Product, variant_id: str) -> None:
    """Hide a variant (its prices go; placed products keep their data)."""
    _editable(product)
    v = _variant(db, product, variant_id)
    v.status = "hidden"
    db.add(v)
    db.execute(delete(VariantPrice).where(VariantPrice.product_id == product.product_id, VariantPrice.variant_id == variant_id))
    db.execute(
        delete(VariantAvailability).where(
            VariantAvailability.product_id == product.product_id, VariantAvailability.variant_id == variant_id
        )
    )
    _recompute_images(db, product)
    _touch(db, product, m.supplier, review=True)


# --- Pictures ----------------------------------------------------------------------------------


def _recompute_images(db: Session, product: Product) -> bool:
    """The product's pictures are its variants' in order (the importer's rule);
    returns whether the thumbnail changed."""
    images: list[str] = []
    for v in _variants(db, product):
        if v.status != "hidden":
            images += [sha for sha in (v.images or []) if sha not in images]
    old_first = (product.images or [None])[0]
    product.images = images
    changed = old_first != (images or [None])[0]
    if changed:
        db.execute(delete(ProductEmbedding).where(ProductEmbedding.product_id == product.product_id))
    return changed


def add_image(db: Session, m: Member, product: Product, variant_id: str, data: bytes) -> ProductVariant:
    _editable(product)
    v = _variant(db, product, variant_id)
    if len(data) > MAX_IMAGE_BYTES:
        raise ContractError("too_large", 413, "A picture is at most 20 MB.")
    if len(v.images or []) >= MAX_IMAGES_PER_VARIANT:
        raise conflict(f"A variant has at most {MAX_IMAGES_PER_VARIANT} pictures.", "too_many")
    try:
        stored = media.store_image(get_store(), data)
    except media.MediaError as exc:
        code = "image_too_small" if exc.code == "image_too_small" else "bad_image"
        raise ContractError(code, 422, str(exc) if code == "image_too_small" else "Upload a JPEG or PNG picture.")
    if stored.sha256 not in (v.images or []):
        v.images = [*(v.images or []), stored.sha256]
        v.images_src = None  # set by hand: a feed that lists picture URLs replaces them
    db.add(v)
    _recompute_images(db, product)
    _touch(db, product, m.supplier, review=True)
    return v


def remove_image(db: Session, m: Member, product: Product, variant_id: str, sha: str) -> ProductVariant:
    _editable(product)
    v = _variant(db, product, variant_id)
    if sha not in (v.images or []):
        raise not_found("That picture")
    v.images = [s for s in v.images if s != sha]
    v.images_src = None
    db.add(v)
    _recompute_images(db, product)
    _touch(db, product, m.supplier, review=True)
    return v


# --- Geometry --------------------------------------------------------------------------------


def set_geometry(db: Session, m: Member, product: Product, variant_id: str, data: bytes, filename: str) -> dict:
    """Check, store by SHA-256 and attach a variant's 3D file."""
    _editable(product)
    v = _variant(db, product, variant_id)
    try:
        checked = geometry_check.check(data, filename, v.dims_mm)
    except geometry_check.GeometryRefused as exc:
        status = 413 if exc.code == "too_large" else 422
        raise ContractError(exc.code, status, exc.detail, exc.data or None)
    try:
        stored = media.store_geometry(get_store(), data, checked.format)
    except media.MediaError as exc:
        raise ContractError("bad_geometry_format", 422, str(exc))
    old = v.geometry or {}
    old_asset = old.get("asset") or {}
    rev = old_asset.get("rev", 0) + (1 if old.get("sha256") != stored["sha256"] else 0)
    v.geometry = {
        **stored,
        "asset": {
            "id": old_asset.get("id") or asset_id(product.product_id, v.variant_id),
            "name": old_asset.get("name") or product.name,
            "rev": max(rev, 1),
            "kind": "object" if product.kind == "object" else "material",
        },
        "check": checked.json(),
    }
    v.geometry_src = None
    db.add(v)
    _touch(db, product, m.supplier, review=old.get("sha256") != stored["sha256"])
    return {**variant_json(db, v), "check": checked.json()}


# --- Review and state ------------------------------------------------------------------------


def missing_for_review(db: Session, product: Product) -> list[str]:
    missing = []
    variants = [v for v in _variants(db, product) if v.status != "hidden"]
    if product.category not in active_categories(db):
        missing.append("category")
    if not variants:
        missing.append("variants")
    if not product.images:
        missing.append("images")
    if product.kind == "object":
        if any(not v.dims_mm for v in variants):
            missing.append("dims_mm")
        if any(not v.geometry for v in variants):
            missing.append("geometry")
    has_price = db.scalar(select(func.count()).select_from(VariantPrice).where(VariantPrice.product_id == product.product_id))
    if not has_price:
        missing.append("prices")
    return missing


def submit(db: Session, m: Member, product: Product) -> Product:
    require_verified(m.supplier, "submit products for review")
    if product.status not in ("draft", "rejected"):
        raise conflict(f"Only a draft or rejected product is submitted; this one is {product.status}.", "not_submittable")
    missing = missing_for_review(db, product)
    if missing:
        raise ContractError(
            "incomplete", 422, f"Add before submitting: {', '.join(missing)}.", {"missing": missing}
        )
    product.status, product.review_note = "pending_review", None
    _touch(db, product, m.supplier)
    return product


def submit_many(db: Session, m: Member, product_ids: list[str]) -> dict:
    require_verified(m.supplier, "submit products for review")
    stmt = select(Product).where(Product.supplier_id == m.supplier.supplier_id, Product.status.in_(("draft", "rejected")))
    if product_ids:
        stmt = stmt.where(Product.product_id.in_(product_ids))
    submitted, skipped = [], []
    for product in db.scalars(stmt):
        missing = missing_for_review(db, product)
        if missing:
            skipped.append({"product_id": product.product_id, "sku": product.sku, "missing": missing})
            continue
        product.status, product.review_note = "pending_review", None
        db.add(product)
        submitted.append(product.product_id)
    db.commit()
    return {"submitted": submitted, "skipped": skipped}


def hide(db: Session, m: Member, product: Product) -> Product:
    """Take an approved product out of the catalogue for now (Show restores it)."""
    if product.status != "approved":
        raise conflict("Only an approved product can be hidden.", "not_hideable")
    product.prev_status, product.status = "approved", "hidden"
    _touch(db, product, m.supplier)
    return product


def show(db: Session, m: Member, product: Product) -> Product:
    if product.status != "hidden":
        raise conflict("This product is not hidden.", "not_hidden")
    product.status, product.prev_status = product.prev_status or "pending_review", None
    _touch(db, product, m.supplier)
    return product


def withdraw(db: Session, m: Member, product: Product) -> Product:
    """Remove a product for good (the app offers substitutes for placed ones)."""
    if product.status == "withdrawn":
        return product
    product.status, product.prev_status = "withdrawn", None
    _touch(db, product, m.supplier)
    return product


def _discontinue_offers(db: Session, product: Product, variant_ids: list[str]) -> None:
    at = now()
    for a in db.scalars(
        select(VariantAvailability).where(
            VariantAvailability.product_id == product.product_id, VariantAvailability.variant_id.in_(variant_ids)
        )
    ):
        a.state, a.stock, a.lead_time_days, a.source, a.updated_at, a.stale = "discontinued", None, None, "manual", at, False
        db.add(a)


def discontinue(db: Session, m: Member, product: Product) -> Product:
    """Every variant discontinued: designers who placed it keep its data and
    are offered up to three similar products."""
    if product.status == "withdrawn":
        raise conflict("This product is withdrawn.", "not_editable")
    variants = [v for v in _variants(db, product) if v.status != "hidden"]
    for v in variants:
        v.status = "discontinued"
        db.add(v)
    _discontinue_offers(db, product, [v.variant_id for v in variants])
    _touch(db, product, m.supplier)
    return product
