"""Suppliers and products as the contract shows them: 5.1 categories with
counts, 5.4 the product (§6.1), 5.6 a supplier's profile; supplier members
and roles (PF8 builds its portal and feed authentication on these)."""

import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..models import User
from ..storage import get_store
from . import media
from .common import new_id, not_found, now, rfc3339
from .models import (
    MarketCategory,
    MarketRegion,
    Product,
    ProductVariant,
    Supplier,
    SupplierMember,
    SupplierRegion,
)
from .prices import (
    Offer,
    availability_json,
    delivery_json,
    is_public,
    offers,
    orderable,
    price_json,
    substitutes,
    visible_variants,
)
from .taxonomy import active_categories, app_path_of, taxonomy_sha256

SUPPLIER_STATES = ("applied", "verified", "suspended")
PRODUCT_STATES = ("draft", "pending_review", "approved", "rejected", "hidden", "withdrawn")
ROLES = ("owner", "catalogue", "orders", "viewer")
# Roles whose API keys may feed the catalogue (contract §4: "the catalogue role").
CATALOGUE_ROLES = frozenset({"owner", "catalogue"})
ORDER_ROLES = frozenset({"owner", "orders"})


# --- Suppliers ---------------------------------------------------------------------------


def get_supplier(db: Session, supplier_id: str) -> Supplier:
    supplier = db.get(Supplier, supplier_id) if isinstance(supplier_id, str) else None
    if supplier is None:
        raise not_found("That supplier")
    return supplier


def payments_ready(supplier: Supplier) -> bool:
    """Orders (not only quotes) need payments switched on and the supplier's
    Stripe Connect account able to receive transfers."""
    from ..config import get_settings

    return bool(
        get_settings().market_payments_enabled and supplier.connect_account_id and supplier.connect_ready
    )


def supplier_regions(db: Session, supplier_id: str) -> list[str]:
    rows = db.scalars(
        select(SupplierRegion.region)
        .where(SupplierRegion.supplier_id == supplier_id, SupplierRegion.active.is_(True))
        .order_by(SupplierRegion.region)
    )
    return list(rows)


def logo_url(supplier: Supplier) -> str | None:
    if not supplier.logo_key:
        return None
    return media.image_url(supplier.logo_key, thumb=True)


def supplier_json(db: Session, supplier: Supplier) -> dict:
    """5.6, plus `orderable` (a MINOR proposal: false = quote-only)."""
    return {
        "supplier_id": supplier.supplier_id,
        "name": supplier.name,
        "country": supplier.country,
        "website": supplier.website,
        "logo_url": logo_url(supplier),
        "regions": supplier_regions(db, supplier.supplier_id),
        "verified": supplier.status == "verified",
        "orderable": payments_ready(supplier),
    }


def supplier_admin_json(db: Session, supplier: Supplier) -> dict:
    from .listing import commission_bp_for

    members = db.execute(
        select(SupplierMember, User.email)
        .join(User, User.id == SupplierMember.user_id)
        .where(SupplierMember.supplier_id == supplier.supplier_id)
        .order_by(SupplierMember.id)
    )
    counts = dict(
        db.execute(
            select(Product.status, func.count())
            .where(Product.supplier_id == supplier.supplier_id)
            .group_by(Product.status)
        ).all()
    )
    return {
        **supplier_json(db, supplier),
        "legal_name": supplier.legal_name,
        "company_number": supplier.company_number,
        "vat_id": supplier.vat_id,
        "contact_email": supplier.contact_email,
        "status": supplier.status,
        "status_reason": supplier.status_reason,
        "verified_at": rfc3339(supplier.verified_at),
        "commission_bp": commission_bp_for(supplier),
        "commission_bp_override": supplier.commission_bp,
        "listing_plan": supplier.listing_plan,
        "connect_account_id": supplier.connect_account_id,
        "connect_ready": supplier.connect_ready,
        "billing_customer_id": supplier.billing_customer_id,
        "members": [{"email": email, "role": m.role, "user_id": m.user_id} for m, email in members],
        "products": counts,
        "created_at": rfc3339(supplier.created_at),
    }


def create_supplier(db: Session, **fields) -> Supplier:
    supplier = Supplier(supplier_id=fields.pop("supplier_id", None) or new_id(), **fields)
    db.add(supplier)
    db.flush()
    return supplier


def set_supplier_regions(db: Session, supplier: Supplier, regions: dict[str, MarketRegion]) -> None:
    have = {r.region: r for r in db.scalars(select(SupplierRegion).where(SupplierRegion.supplier_id == supplier.supplier_id))}
    for code, region in regions.items():
        row = have.get(code) or SupplierRegion(supplier_id=supplier.supplier_id, region=code, currency=region.currency)
        row.active = True
        db.add(row)


def member_role(db: Session, user: User, supplier_id: str) -> str | None:
    return db.scalar(
        select(SupplierMember.role).where(
            SupplierMember.supplier_id == supplier_id, SupplierMember.user_id == user.id
        )
    )


def memberships(db: Session, user: User) -> list[tuple[Supplier, str]]:
    return list(
        db.execute(
            select(Supplier, SupplierMember.role)
            .join(SupplierMember, SupplierMember.supplier_id == Supplier.supplier_id)
            .where(SupplierMember.user_id == user.id)
            .order_by(Supplier.name)
        ).tuples()
    )


def catalogue_supplier(db: Session, user: User) -> Supplier:
    """The verified supplier whose catalogue this user may feed (the API key
    owner of PF8's 5.11–5.13). 403 `not_supplier` otherwise (contract §7)."""
    for supplier, role in memberships(db, user):
        if role in CATALOGUE_ROLES and supplier.status == "verified":
            return supplier
    raise ContractError(
        "not_supplier", 403, "This key's owner is not a catalogue member of a verified supplier."
    )


def add_member(db: Session, supplier: Supplier, user: User, role: str) -> SupplierMember:
    if role not in ROLES:
        raise ValueError(role)
    row = db.scalar(
        select(SupplierMember).where(
            SupplierMember.supplier_id == supplier.supplier_id, SupplierMember.user_id == user.id
        )
    ) or SupplierMember(supplier_id=supplier.supplier_id, user_id=user.id)
    row.role = role
    db.add(row)
    return row


# --- Categories (5.1) ---------------------------------------------------------------------


def public_products_query():
    return (
        select(Product)
        .join(Supplier, Supplier.supplier_id == Product.supplier_id)
        .where(Product.status == "approved", Supplier.status == "verified")
    )


def categories_json(db: Session) -> dict:
    cats = active_categories(db)
    counts: dict[str, int] = dict(
        db.execute(
            select(Product.category, func.count())
            .join(Supplier, Supplier.supplier_id == Product.supplier_id)
            .where(Product.status == "approved", Supplier.status == "verified")
            .group_by(Product.category)
        ).all()
    )
    out = []
    for path, cat in cats.items():
        n = sum(c for p, c in counts.items() if p == path or p.startswith(path + "/"))
        out.append({"path": path, "label": cat.label, "app_path": cat.app_path, "products": n})
    return {"taxonomy_sha256": taxonomy_sha256(), "categories": out}


def etag_of(body: dict) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return '"' + hashlib.sha256(raw).hexdigest()[:32] + '"'


def add_category(db: Session, path: str, label: str) -> MarketCategory:
    app_path = app_path_of(path)
    if app_path is None:
        raise ValueError("not rooted on the app's taxonomy")
    row = db.get(MarketCategory, path) or MarketCategory(path=path)
    row.label, row.app_path = label, app_path
    row.parent_path = path.rsplit("/", 1)[0] if "/" in path else None
    row.active = True
    row.sort = row.sort or 1000
    db.add(row)
    return row


# --- Products (5.4, §6.1) ----------------------------------------------------------------


def thumbnail_url(product: Product) -> str | None:
    return media.image_url(product.images[0], thumb=True) if product.images else None


def rating_json(product: Product) -> dict:
    """A MINOR proposal (5.3 and 5.4): published reviews' average and count."""
    avg = round(product.rating_avg, 2) if product.rating_avg is not None else None
    return {"avg": avg, "count": product.rating_count}


def _asset_kind(product: Product) -> str:
    # CadAssetKindName spellings (contract §6.1): object, material, texture, mesh.
    return "object" if product.kind == "object" else "material"


def geometry_link(product: Product, v: ProductVariant, region: str | None) -> str:
    """PF8: the API's own address for a variant's 3D file. It counts a
    placement for the supplier's analytics, then redirects to a signed URL
    (1 h), so a link the app keeps never expires."""
    from urllib.parse import quote

    from ..config import get_settings

    base = get_settings().api_url.rstrip("/")
    query = f"?region={quote(region)}" if region else ""
    return f"{base}/market/geometry/{product.product_id}/{quote(v.variant_id, safe='')}{query}"


def variant_json(product: Product, v: ProductVariant, offer: Offer | None, *, store=None, region: str | None = None) -> dict:
    geometry = None
    if v.geometry:
        g = v.geometry
        geometry = {
            "asset": g["asset"],
            "format": g["format"],
            "url": geometry_link(product, v, region),
            "sha256": g["sha256"],
            "bytes": g["bytes"],
        }
    out = {
        "variant_id": v.variant_id,
        "options": v.options or {},
        "dims_mm": v.dims_mm,
        "materials": v.materials or [],
        "geometry": geometry,
        "images": [media.image_url(sha) for sha in (v.images or [])],
        "price": price_json(offer.price) if offer and offer.price else None,
        "delivery": delivery_json(offer.price) if offer and offer.price else None,
        "availability": availability_json(v, offer.availability if offer else None),
    }
    if v.gtin:
        out["gtin"] = v.gtin
    return out


def product_json(db: Session, product: Product, supplier: Supplier, region: MarketRegion | None) -> dict:
    variants = visible_variants(db, [product.product_id])[product.product_id]
    offs = offers(db, [product.product_id], region.region) if region else {}
    out = {
        "product_id": product.product_id,
        "supplier_id": product.supplier_id,
        "supplier_name": supplier.name,
        "sku": product.sku,
        "name": product.name,
        "kind": product.kind,
        "category": product.category,
        "app_path": app_path_of(product.category),
        "description": product.description or "",
        "images": [media.image_url(sha) for sha in product.images],
        "thumbnail_url": thumbnail_url(product),
        "includes": product.includes or [],
        "variants": [
            variant_json(product, v, offs.get((product.product_id, v.variant_id)), region=region.region if region else None)
            for v in variants
        ],
        "rating": rating_json(product),
        "orderable": payments_ready(supplier),
    }
    if product.brand:
        out["brand"] = product.brand
    if product.classification:
        out["classification"] = product.classification
    return out


def public_product(db: Session, product_id: str, region: MarketRegion | None) -> dict:
    """5.4: 404 for an unknown or never-published product; 410
    `product_withdrawn` with `data.substitutes` when the supplier removed it."""
    product = db.get(Product, product_id) if isinstance(product_id, str) else None
    supplier = db.get(Supplier, product.supplier_id) if product else None
    if product is None:
        raise not_found("That product")
    if not is_public(product, supplier):
        # Withdrawn = it was published once and the supplier (or an admin)
        # took it away; never-published or back-in-review products are 404.
        gone = product.approved_at is not None and (
            product.status in ("hidden", "withdrawn")
            or (product.status == "approved" and (supplier is None or supplier.status != "verified"))
        )
        if not gone:
            raise not_found("That product")
        variants = visible_variants(db, [product.product_id])[product.product_id]
        near = None
        if region and variants:
            offer = offers(db, [product.product_id], region.region).get((product.product_id, variants[0].variant_id))
            near = offer.price.amount if offer and offer.price else None
        raise ContractError(
            "product_withdrawn",
            410,
            "The supplier no longer offers this product.",
            {"substitutes": substitutes(db, product, region, near)},
        )
    return product_json(db, product, supplier, region)


def product_admin_json(db: Session, product: Product) -> dict:
    supplier = db.get(Supplier, product.supplier_id)
    variants = visible_variants(db, [product.product_id])[product.product_id]
    return {
        "product_id": product.product_id,
        "supplier_id": product.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "supplier_status": supplier.status if supplier else None,
        "sku": product.sku,
        "name": product.name,
        "kind": product.kind,
        "category": product.category,
        "app_path": app_path_of(product.category),
        "category_known": product.category in active_categories(db),
        "description": product.description,
        "brand": product.brand,
        "thumbnail_url": thumbnail_url(product),
        "images": [media.image_url(sha) for sha in product.images],
        "status": product.status,
        "review_note": product.review_note,
        "variants": [
            {
                "variant_id": v.variant_id,
                "options": v.options,
                "dims_mm": v.dims_mm,
                "status": v.status,
                "geometry": {k: v.geometry[k] for k in ("format", "sha256", "bytes")} if v.geometry else None,
            }
            for v in variants
        ],
        "rating": rating_json(product),
        "created_at": rfc3339(product.created_at),
        "updated_at": rfc3339(product.updated_at),
    }


def set_product_status(db: Session, product: Product, status: str, note: str | None = None) -> Product:
    if status not in PRODUCT_STATES:
        raise ValueError(status)
    product.status = status
    product.prev_status = None
    product.review_note = note
    if status == "approved" and product.approved_at is None:
        product.approved_at = now()
    db.add(product)
    return product


def has_orderable_variant(db: Session, product: Product, region: str) -> bool:
    variants = visible_variants(db, [product.product_id])[product.product_id]
    offs = offers(db, [product.product_id], region)
    return any(orderable(v, offs.get((product.product_id, v.variant_id), Offer(None, None))) for v in variants)
