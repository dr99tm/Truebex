"""PF7b: the lines of a "Buy this look" basket, named for the site's basket
page (/market/basket/), which the app's room themes open with
`?region=<r>&items=<supplier hex>:<sku>:<variant>:<qty>,...` (contract
marketplace-api §3, the PR2 line of 2026-10-11).

5.5 prices a line by (supplier, sku, variant) but answers no names, and the
app writes `default` for a product whose variant it does not know (contract
§6.3: `default` names a single variant). This module answers, per line, the
product and supplier names and the variant the page should price:

* the asked variant when the product has it (a variant may be named
  `default`);
* for `default`: the product's only visible variant, or with several the
  first one orderable in the region, else the first listed (the app's
  `FCadProduct::DefaultVariant`).

A product with several variants lists them (`variants`), so the page can
offer another version of any line.

Products never published are not revealed; a product published once and
since withdrawn keeps its name (5.4 answers 410 for it too).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalogue import payments_ready, thumbnail_url
from .models import MarketRegion, Product, ProductVariant, Supplier
from .prices import Offer, is_public, offers, orderable, visible_variants

MAX_LINES = 100
DEFAULT = "default"


def _variant_json(v: ProductVariant, resolved: str) -> dict:
    return {"variant_id": v.variant_id, "options": v.options or {}, "resolved": resolved}


def _pick(
    variants: list[ProductVariant], asked: str, offs: dict[tuple[str, str], Offer]
) -> tuple[ProductVariant | None, str | None]:
    """The variant a line stands for and how it was chosen."""
    for v in variants:
        if v.variant_id == asked:
            return v, "asked"
    if asked != DEFAULT or not variants:
        return None, None
    if len(variants) == 1:
        return variants[0], "only"
    for v in variants:
        if orderable(v, offs.get((v.product_id, v.variant_id), Offer(None, None))):
            return v, "first"
    return variants[0], "first"


def _known(product: Product, supplier: Supplier | None) -> bool:
    """Public now, or withdrawn after publication: 5.4's 200 and 410 cases."""
    if is_public(product, supplier):
        return True
    return product.approved_at is not None and (
        product.status in ("hidden", "withdrawn")
        or (product.status == "approved" and (supplier is None or supplier.status != "verified"))
    )


def describe(db: Session, region: MarketRegion, items: list[dict]) -> dict:
    """Names and resolved variants for ≤ 100 basket lines, a few queries in all."""
    keys = {(i["supplier_id"], i["sku"]) for i in items}
    supplier_ids = {s for s, _ in keys}
    suppliers: dict[str, Supplier] = {}
    products: dict[tuple[str, str], Product] = {}
    if supplier_ids:
        suppliers = {s.supplier_id: s for s in db.scalars(select(Supplier).where(Supplier.supplier_id.in_(supplier_ids)))}
        for p in db.scalars(
            select(Product).where(Product.supplier_id.in_(supplier_ids), Product.sku.in_({sku for _, sku in keys}))
        ):
            products[(p.supplier_id, p.sku)] = p
    # Never-published (or back in review) products stay unknown, as on 5.4.
    shown = {k: p for k, p in products.items() if _known(p, suppliers.get(p.supplier_id))}
    pids = [p.product_id for p in shown.values()]
    variants = visible_variants(db, pids) if pids else {}
    offs = offers(db, pids, region.region) if pids else {}

    out = []
    for item in items:
        line: dict = {
            "supplier_id": item["supplier_id"],
            "sku": item["sku"],
            "variant_id": item["variant_id"],
            "status": "not_found",
            "variant": None,
        }
        product = shown.get((item["supplier_id"], item["sku"]))
        if product is not None:
            supplier = suppliers.get(product.supplier_id)
            choices = variants.get(product.product_id, [])
            variant, how = _pick(choices, item["variant_id"], offs)
            line.update(
                product_id=product.product_id,
                name=product.name,
                kind=product.kind,
                supplier_name=supplier.name if supplier else None,
                thumbnail_url=thumbnail_url(product),
                orderable=bool(supplier and payments_ready(supplier)),
            )
            if variant is not None:
                line["variant"] = _variant_json(variant, how)
                line["status"] = "found" if is_public(product, supplier) else "withdrawn"
                if len(choices) > 1:
                    # What the person may pick instead (discontinued ones left out).
                    line["variants"] = [
                        {"variant_id": v.variant_id, "options": v.options or {}}
                        for v in choices
                        if v.status == "active" or v is variant
                    ]
        out.append(line)
    return {"region": region.region, "items": out}
