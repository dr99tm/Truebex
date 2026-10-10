"""Stock and prices by region (PF8 Scope 3): the grid per region and the
regions a supplier serves with their currency and delivery defaults.

A grid save is the §6.4 row columns per variant, checked by the importer's
own `check_offer` (the same codes a feed gets: `bad_price`,
`currency_mismatch`, …). A save is all or nothing: one bad cell answers 422
`rows_invalid` with every problem, and nothing is written.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..market.common import format_major, invalid, now, parse_major
from ..market.importer import Row, _cell, check_offer
from ..market.models import (
    MarketRegion,
    Product,
    ProductVariant,
    Supplier,
    SupplierRegion,
    VariantAvailability,
    VariantPrice,
)
from ..market.taxonomy import active_regions, region_json
from .schemas import PriceRowIn, RegionsIn


def _major(amount: int | None, exponent: int) -> str | None:
    return None if amount is None else format_major(amount, exponent)


def _pct(bp: int | None) -> str | None:
    if bp is None:
        return None
    whole, frac = divmod(bp, 100)
    return f"{whole}" if not frac else f"{whole}.{frac:02d}".rstrip("0")


def served(db: Session, supplier: Supplier) -> dict[str, SupplierRegion]:
    return {
        r.region: r
        for r in db.scalars(
            select(SupplierRegion).where(SupplierRegion.supplier_id == supplier.supplier_id).order_by(SupplierRegion.region)
        )
    }


def regions_json(db: Session, supplier: Supplier) -> dict:
    known = active_regions(db)
    mine = served(db, supplier)
    out = []
    for code, r in known.items():
        s = mine.get(code)
        out.append(
            {
                **region_json(r),
                "served": bool(s and s.active),
                "default_delivery_fee": _major(s.default_delivery_fee, r.exponent) if s else None,
                "delivery_days_min": s.delivery_days_min if s else None,
                "delivery_days_max": s.delivery_days_max if s else None,
            }
        )
    return {"regions": out}


def set_regions(db: Session, supplier: Supplier, body: RegionsIn) -> dict:
    known = active_regions(db)
    mine = served(db, supplier)
    for n, spec in enumerate(body.regions):
        code = spec.region.upper()
        r = known.get(code)
        if r is None:
            raise invalid(f"regions.{n}.region", f"{code!r} is not a region Truebex serves", "body")
        fee = None
        if spec.default_delivery_fee:
            try:
                fee = parse_major(spec.default_delivery_fee, r.exponent)
            except ValueError:
                raise invalid(f"regions.{n}.default_delivery_fee", f"bad_price: a decimal with at most {r.exponent} decimals", "body")
        if spec.delivery_days_min is not None and spec.delivery_days_max is not None and spec.delivery_days_min > spec.delivery_days_max:
            raise invalid(f"regions.{n}.delivery_days_max", "not before delivery_days_min", "body")
        row = mine.get(code) or SupplierRegion(supplier_id=supplier.supplier_id, region=code, currency=r.currency)
        row.currency = r.currency
        row.active = spec.active
        row.default_delivery_fee = fee
        row.delivery_days_min, row.delivery_days_max = spec.delivery_days_min, spec.delivery_days_max
        db.add(row)
    db.commit()
    return regions_json(db, supplier)


def _region(db: Session, supplier: Supplier, code: str | None) -> tuple[MarketRegion, SupplierRegion]:
    known = active_regions(db)
    mine = {k: v for k, v in served(db, supplier).items() if v.active}
    if not code:
        code = next(iter(mine), None) or next(iter(known))
    code = code.upper()
    if code not in known:
        raise invalid("region", f"{code!r} is not a region Truebex serves")
    if code not in mine:
        raise ContractError(
            "region_not_served",
            422,
            f"You do not sell in {known[code].name} yet. Add it under Regions first.",
            {"region": code, "served": sorted(mine)},
        )
    return known[code], mine[code]


def grid(db: Session, supplier: Supplier, code: str | None) -> dict:
    region, settings = _region(db, supplier, code)
    products = list(
        db.scalars(
            select(Product)
            .where(Product.supplier_id == supplier.supplier_id, Product.status != "withdrawn")
            .order_by(Product.name, Product.sku)
        )
    )
    pids = [p.product_id for p in products]
    variants: dict[str, list[ProductVariant]] = {}
    prices: dict[tuple[str, str], VariantPrice] = {}
    avail: dict[tuple[str, str], VariantAvailability] = {}
    for start in range(0, len(pids), 500):
        chunk = pids[start : start + 500]
        for v in db.scalars(
            select(ProductVariant)
            .where(ProductVariant.product_id.in_(chunk), ProductVariant.status != "hidden")
            .order_by(ProductVariant.sort)
        ):
            variants.setdefault(v.product_id, []).append(v)
        for p in db.scalars(select(VariantPrice).where(VariantPrice.product_id.in_(chunk), VariantPrice.region == region.region)):
            prices[(p.product_id, p.variant_id)] = p
        for a in db.scalars(
            select(VariantAvailability).where(VariantAvailability.product_id.in_(chunk), VariantAvailability.region == region.region)
        ):
            avail[(a.product_id, a.variant_id)] = a
    rows = []
    for product in products:
        for v in variants.get(product.product_id, []):
            p = prices.get((product.product_id, v.variant_id))
            a = avail.get((product.product_id, v.variant_id))
            rows.append(
                {
                    "product_id": product.product_id,
                    "sku": product.sku,
                    "name": product.name,
                    "product_status": product.status,
                    "variant_id": v.variant_id,
                    "options": v.options or {},
                    "variant_status": v.status,
                    "sold": p is not None,
                    "price": _major(p.amount, region.exponent) if p else None,
                    "amount": p.amount if p else None,
                    "price_includes_tax": p.includes_tax if p else region.prices_include_tax,
                    "tax_rate_percent": _pct(p.tax_rate_bp if p else region.tax_rate_bp),
                    "delivery_fee": _major(p.delivery_fee, region.exponent) if p else None,
                    "delivery_days_min": p.delivery_days_min if p else None,
                    "delivery_days_max": p.delivery_days_max if p else None,
                    "stock": a.stock if a else None,
                    "lead_time_days": a.lead_time_days if a else None,
                    "availability": a.state if a else None,
                    "source": p.source if p else None,
                }
            )
    return {
        "region": {
            **region_json(region),
            "default_delivery_fee": _major(settings.default_delivery_fee, region.exponent),
            "delivery_days_min": settings.delivery_days_min,
            "delivery_days_max": settings.delivery_days_max,
        },
        "served": sorted(k for k, v in served(db, supplier).items() if v.active),
        "rows": rows,
    }


def save(db: Session, supplier: Supplier, code: str | None, rows: list[PriceRowIn]) -> dict:
    region, settings = _region(db, supplier, code)
    regions = {region.region: region}
    products = {
        p.sku: p
        for p in db.scalars(
            select(Product).where(Product.supplier_id == supplier.supplier_id, Product.sku.in_({r.sku for r in rows}))
        )
    }
    variants = {
        (v.product_id, v.variant_id): v
        for v in db.scalars(
            select(ProductVariant).where(ProductVariant.product_id.in_([p.product_id for p in products.values()]))
        )
    } if products else {}
    errors: list[dict] = []
    checked = []
    seen: set[tuple[str, str]] = set()
    for n, body in enumerate(rows, start=1):
        cells = {k: _cell(v) for k, v in body.model_dump().items()}
        cells["region"] = region.region
        cells["currency"] = cells.get("currency") or region.currency
        existing = None
        product = products.get(body.sku)
        variant = variants.get((product.product_id, body.variant_id)) if product else None
        if variant is not None:
            existing = db.scalar(
                select(VariantPrice).where(
                    VariantPrice.product_id == product.product_id,
                    VariantPrice.variant_id == body.variant_id,
                    VariantPrice.region == region.region,
                )
            )
        if not cells.get("price_includes_tax"):
            includes = existing.includes_tax if existing else region.prices_include_tax
            cells["price_includes_tax"] = "true" if includes else "false"
        row = Row(n, cells)
        problems: list[tuple[str, str]] = []
        if variant is None or variant.status == "hidden" or product.status == "withdrawn":
            problems.append(("variant_id", "unknown_variant"))
        if (body.sku, body.variant_id) in seen:
            problems.append(("variant_id", "duplicate_row"))
        seen.add((body.sku, body.variant_id))
        offer = check_offer(row, regions, lambda col, code, p=problems: p.append((col, code)))
        for col, code in problems:
            errors.append({"row": n, "sku": body.sku, "variant_id": body.variant_id, "column": col, "code": code, "value": row.get(col)[:100]})
        if not problems:
            checked.append((product, variant, offer))
    if errors:
        raise ContractError(
            "rows_invalid", 422, f"{len(errors)} cell(s) need fixing; nothing was saved.", {"errors": errors[:200]}
        )
    at = now()
    written = 0
    for product, variant, o in checked:
        key = (VariantPrice.product_id == product.product_id, VariantPrice.variant_id == variant.variant_id, VariantPrice.region == region.region)
        price = db.scalar(select(VariantPrice).where(*key))
        akey = (
            VariantAvailability.product_id == product.product_id,
            VariantAvailability.variant_id == variant.variant_id,
            VariantAvailability.region == region.region,
        )
        avail = db.scalar(select(VariantAvailability).where(*akey))
        if o["status"] == "hidden":  # not sold in this region
            if price is not None:
                db.delete(price)
            if avail is not None:
                db.delete(avail)
            written += 1
            continue
        price = price or VariantPrice(product_id=product.product_id, variant_id=variant.variant_id, region=region.region)
        price.amount, price.currency, price.exponent = o["amount"], o["currency"], region.exponent
        price.includes_tax, price.tax_rate_bp = o["includes_tax"], o["tax_rate_bp"]
        price.delivery_fee = o["delivery_fee"] if o["delivery_fee"] is not None else settings.default_delivery_fee
        price.delivery_days_min = o["delivery_days_min"] if o["delivery_days_min"] is not None else settings.delivery_days_min
        price.delivery_days_max = o["delivery_days_max"] if o["delivery_days_max"] is not None else settings.delivery_days_max
        price.source, price.feed_id, price.updated_at = "manual", None, at
        db.add(price)
        a = o["availability"]
        avail = avail or VariantAvailability(product_id=product.product_id, variant_id=variant.variant_id, region=region.region)
        avail.state, avail.stock, avail.lead_time_days = a["state"], a["stock"], a["lead_time_days"]
        avail.source, avail.stale, avail.updated_at = "manual", False, at
        db.add(avail)
        written += 1
    db.commit()
    return {"saved": written, **grid(db, supplier, region.region)}
