"""Regional prices, delivery and availability (contract §6.3), batch prices
with substitutes (5.5).

A variant's offer in a region is its `variant_prices` row (integer minor
units, tax rule, delivery) and its `variant_availability` row. A product is
sold in a region when one of its visible variants has a price there.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .common import ORDERABLE_STATES, invalid, money, now, rfc3339
from .models import (
    MarketRegion,
    Product,
    ProductVariant,
    Supplier,
    VariantAvailability,
    VariantPrice,
)
from .taxonomy import active_regions

MAX_BATCH = 500
STALE_AFTER = timedelta(hours=24)
MAX_SUBSTITUTES = 3


def region_or_invalid(db: Session, code: str | None, *, field: str = "region", where: str = "query") -> MarketRegion:
    region = active_regions(db).get((code or "").upper()) if code else None
    if region is None:
        raise invalid(field, f"unknown region {code!r}; GET /market/regions lists them", where)
    return region


@dataclass
class Offer:
    price: VariantPrice | None
    availability: VariantAvailability | None


def price_json(p: VariantPrice) -> dict:
    return {
        "amount": p.amount,
        "currency": p.currency,
        "exponent": p.exponent,
        "region": p.region,
        "includes_tax": p.includes_tax,
        "tax_rate_bp": p.tax_rate_bp,
        "at": rfc3339(p.updated_at),
    }


def delivery_json(p: VariantPrice) -> dict | None:
    if p.delivery_fee is None and p.delivery_days_min is None and p.delivery_days_max is None:
        return None
    return {
        "fee": money(p.delivery_fee or 0, p.currency, p.exponent),
        "days_min": p.delivery_days_min,
        "days_max": p.delivery_days_max,
    }


def state_of(variant: ProductVariant, availability: VariantAvailability | None) -> str | None:
    if variant.status == "discontinued":
        return "discontinued"
    return availability.state if availability is not None else None


def availability_json(variant: ProductVariant, a: VariantAvailability | None) -> dict | None:
    state = state_of(variant, a)
    if state is None:
        return None
    return {
        "state": state,
        "stock": a.stock if a is not None and state != "discontinued" else None,
        "lead_time_days": a.lead_time_days if a is not None and state == "made_to_order" else None,
        "updated_at": rfc3339(a.updated_at) if a is not None else None,
    }


def orderable(variant: ProductVariant, offer: Offer) -> bool:
    """Priced in the region and in a state that can be ordered (no row = not
    tracked = in stock)."""
    if offer.price is None or variant.status != "active":
        return False
    state = state_of(variant, offer.availability)
    return state is None or state in ORDERABLE_STATES


def offers(db: Session, product_ids: Iterable[str], region: str) -> dict[tuple[str, str], Offer]:
    ids = list(set(product_ids))
    out: dict[tuple[str, str], Offer] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        for p in db.scalars(
            select(VariantPrice).where(VariantPrice.product_id.in_(chunk), VariantPrice.region == region)
        ):
            out.setdefault((p.product_id, p.variant_id), Offer(None, None)).price = p
        for a in db.scalars(
            select(VariantAvailability).where(
                VariantAvailability.product_id.in_(chunk), VariantAvailability.region == region
            )
        ):
            out.setdefault((a.product_id, a.variant_id), Offer(None, None)).availability = a
    return out


def visible_variants(db: Session, product_ids: Iterable[str]) -> dict[str, list[ProductVariant]]:
    ids = list(set(product_ids))
    out: dict[str, list[ProductVariant]] = {pid: [] for pid in ids}
    for start in range(0, len(ids), 500):
        rows = db.scalars(
            select(ProductVariant)
            .where(ProductVariant.product_id.in_(ids[start : start + 500]), ProductVariant.status != "hidden")
            .order_by(ProductVariant.sort, ProductVariant.variant_id)
        )
        for v in rows:
            out[v.product_id].append(v)
    return out


def is_public(product: Product, supplier: Supplier | None) -> bool:
    return product.status == "approved" and supplier is not None and supplier.status == "verified"


# --- Substitutes ---------------------------------------------------------------------


def substitutes(
    db: Session,
    product: Product,
    region: MarketRegion | None,
    near_amount: int | None,
    *,
    limit: int = MAX_SUBSTITUTES,
) -> list[dict]:
    """≤ 3 approved products of the same category (then of the same app
    path), orderable in the region, nearest in price."""
    from .catalogue import thumbnail_url
    from .taxonomy import app_path_of

    def candidates(where) -> list[tuple[Product, Supplier]]:
        return list(
            db.execute(
                select(Product, Supplier)
                .join(Supplier, Supplier.supplier_id == Product.supplier_id)
                .where(
                    where,
                    Product.status == "approved",
                    Supplier.status == "verified",
                    Product.product_id != product.product_id,
                    Product.kind == product.kind,
                )
                .limit(400)
            )
        )

    pools = [candidates(Product.category == product.category)]
    app_path = app_path_of(product.category)
    if app_path:
        pools.append(
            candidates((Product.category == app_path) | Product.category.like(f"{app_path}/%"))
        )
    picked: list[dict] = []
    seen: set[str] = set()
    for pool in pools:
        ids = [p.product_id for p, _ in pool if p.product_id not in seen]
        variants = visible_variants(db, ids)
        offs = offers(db, ids, region.region) if region else {}
        scored = []
        for p, s in pool:
            if p.product_id in seen:
                continue
            best = None
            for v in variants.get(p.product_id, []):
                offer = offs.get((p.product_id, v.variant_id), Offer(None, None))
                if region is not None and not orderable(v, offer):
                    continue
                amount = offer.price.amount if offer.price else None
                key = abs(amount - near_amount) if (amount is not None and near_amount is not None) else 0
                if best is None or key < best[0]:
                    best = (key, v, offer)
            if best is None:
                continue
            scored.append((best[0], -(p.approved_at.timestamp() if p.approved_at else 0), p.product_id, p, s, best[1], best[2]))
        scored.sort(key=lambda t: t[:3])
        for _, _, _, p, s, v, offer in scored:
            if len(picked) >= limit:
                break
            seen.add(p.product_id)
            picked.append(
                {
                    "product_id": p.product_id,
                    "supplier_id": p.supplier_id,
                    "supplier_name": s.name,
                    "sku": p.sku,
                    "variant_id": v.variant_id,
                    "name": p.name,
                    "category": p.category,
                    "thumbnail_url": thumbnail_url(p),
                    "price": price_json(offer.price) if offer.price else None,
                    "availability": availability_json(v, offer.availability),
                }
            )
        if len(picked) >= limit:
            break
    return picked


# --- 5.5 batch prices --------------------------------------------------------------------


def batch(db: Session, region: MarketRegion, items: list[dict]) -> dict:
    """Prices and availability for ≤ 500 lines, a few queries in all."""
    at = now()
    keys = {(i["supplier_id"], i["sku"]) for i in items}
    supplier_ids = {s for s, _ in keys}
    products: dict[tuple[str, str], Product] = {}
    suppliers: dict[str, Supplier] = {}
    if supplier_ids:
        for s in db.scalars(select(Supplier).where(Supplier.supplier_id.in_(supplier_ids))):
            suppliers[s.supplier_id] = s
        skus = {sku for _, sku in keys}
        for p in db.scalars(
            select(Product).where(Product.supplier_id.in_(supplier_ids), Product.sku.in_(skus))
        ):
            products[(p.supplier_id, p.sku)] = p
    pids = [p.product_id for p in products.values()]
    variants = {
        (v.product_id, v.variant_id): v
        for v in db.scalars(select(ProductVariant).where(ProductVariant.product_id.in_(pids)))
    } if pids else {}
    offs = offers(db, pids, region.region)

    out = []
    for item in items:
        line = {
            "supplier_id": item["supplier_id"],
            "sku": item["sku"],
            "variant_id": item["variant_id"],
            "price": None,
            "availability": None,
            "substitutes": [],
        }
        if item.get("qty") is not None:
            line["qty"] = item["qty"]
        product = products.get((item["supplier_id"], item["sku"]))
        variant = variants.get((product.product_id, item["variant_id"])) if product else None
        if product is None or variant is None:
            line["status"] = "not_found"
            out.append(line)
            continue
        offer = offs.get((product.product_id, variant.variant_id), Offer(None, None))
        if not is_public(product, suppliers.get(product.supplier_id)) or variant.status == "hidden":
            line["status"] = "withdrawn"
            line["availability"] = {"state": "discontinued", "stock": None, "lead_time_days": None, "updated_at": None}
            line["substitutes"] = substitutes(db, product, region, offer.price.amount if offer.price else None)
            out.append(line)
            continue
        line["price"] = price_json(offer.price) if offer.price else None
        line["availability"] = availability_json(variant, offer.availability)
        if offer.price is None:
            line["status"] = "not_sold_in_region"
        if not orderable(variant, offer):  # unavailable, discontinued or not sold here
            line["substitutes"] = substitutes(db, product, region, offer.price.amount if offer.price else None)
        out.append(line)
    return {
        "region": region.region,
        "at": rfc3339(at),
        "stale_after": rfc3339(at + STALE_AFTER),
        "items": out,
    }
