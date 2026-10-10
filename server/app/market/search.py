"""Catalogue search (5.3): text, category subtree, region, price range in
minor units, availability, supplier, sort, facets and an opaque cursor.

Text goes through the `SearchIndex` interface: SQLite FTS5 now
(`Fts5Index`, the `market_search_fts` table), Postgres full-text after PF14
(one more adapter; `LikeIndex` is the portable fallback). The importer and
the admin tools call `reindex(db, product)` whenever a product's text
changes; status filters run in SQL, so approving or hiding a product needs
no index change.

Ranking for `sort=relevance` (the main parameters GD1 §4.9 lists): text
relevance, availability in the asked region (availability not updated for
7 days counts as unknown), reviews, then the newest approval.
"""

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .catalogue import payments_ready, rating_json, thumbnail_url
from .common import invalid, is_hex32
from .models import FTS_TABLE, Product, ProductVariant, Supplier
from .prices import (
    Offer,
    availability_json,
    offers,
    orderable,
    price_json,
    region_or_invalid,
    state_of,
    visible_variants,
)
from .taxonomy import active_categories, app_path_of

SORTS = ("relevance", "price_asc", "price_desc", "newest")
MAX_LIMIT = 100
_TOKEN = re.compile(r"\w+", re.UNICODE)


# --- The index interface and its adapters --------------------------------------------


class SearchIndex(Protocol):
    def upsert(self, db: Session, product_id: str, name: str, body: str) -> None: ...

    def remove(self, db: Session, product_id: str) -> None: ...

    def match(self, db: Session, query: str, limit: int = 5000) -> dict[str, float]:
        """product_id → relevance (higher is better) for every product whose
        text matches all the query's words (prefix match)."""
        ...


def tokens(query: str) -> list[str]:
    return [t for t in _TOKEN.findall((query or "").lower()) if t][:10]


class Fts5Index:
    def upsert(self, db: Session, product_id: str, name: str, body: str) -> None:
        db.execute(text(f"DELETE FROM {FTS_TABLE} WHERE product_id = :id"), {"id": product_id})
        db.execute(
            text(f"INSERT INTO {FTS_TABLE} (product_id, name, body) VALUES (:id, :name, :body)"),
            {"id": product_id, "name": name, "body": body},
        )

    def remove(self, db: Session, product_id: str) -> None:
        db.execute(text(f"DELETE FROM {FTS_TABLE} WHERE product_id = :id"), {"id": product_id})

    def match(self, db: Session, query: str, limit: int = 5000) -> dict[str, float]:
        words = tokens(query)
        if not words:
            return {}
        fts = " ".join(f'"{w}"*' for w in words)
        rows = db.execute(
            text(
                f"SELECT product_id, bm25({FTS_TABLE}, 0.0, 10.0, 1.0) AS r FROM {FTS_TABLE} "
                f"WHERE {FTS_TABLE} MATCH :q ORDER BY r LIMIT :n"
            ),
            {"q": fts, "n": limit},
        )
        # bm25 is lower-is-better and negative; flip it.
        return {pid: -float(r) for pid, r in rows}


class LikeIndex:
    """Portable fallback: scans names and descriptions (no index table)."""

    def upsert(self, db: Session, product_id: str, name: str, body: str) -> None:
        pass

    def remove(self, db: Session, product_id: str) -> None:
        pass

    def match(self, db: Session, query: str, limit: int = 5000) -> dict[str, float]:
        words = tokens(query)
        if not words:
            return {}
        stmt = select(Product.product_id, Product.name, Product.description, Product.brand, Product.sku)
        for w in words:
            like = f"%{w}%"
            stmt = stmt.where(
                Product.name.ilike(like) | Product.description.ilike(like) | Product.brand.ilike(like) | Product.sku.ilike(like)
            )
        out = {}
        for pid, name, desc, brand, sku in db.execute(stmt.limit(limit)):
            low = (name or "").lower()
            out[pid] = float(sum(10 if w in low else 1 for w in words))
        return out


def index_for(db: Session) -> SearchIndex:
    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        return Fts5Index()
    return LikeIndex()


def document(db: Session, product: Product, supplier: Supplier) -> tuple[str, str]:
    """The text a product is found by: its name, then description, brand,
    SKU, category labels, supplier, variant options, materials, GTINs."""
    cats = active_categories(db)
    parts = product.category.split("/")
    labels = [cats[p].label for n in range(1, len(parts) + 1) if (p := "/".join(parts[:n])) in cats]
    variants = db.scalars(select(ProductVariant).where(ProductVariant.product_id == product.product_id))
    extra: list[str] = []
    for v in variants:
        extra += [str(x) for x in (v.options or {}).values()]
        extra += [str(x) for x in (v.materials or [])]
        if v.gtin:
            extra.append(v.gtin)
    body = " ".join(
        x
        for x in [product.description or "", product.brand or "", product.sku, " ".join(labels), supplier.name, " ".join(extra)]
        + list(product.classification or [])
        if x
    )
    return product.name, body


def reindex(db: Session, product: Product, supplier: Supplier | None = None) -> None:
    supplier = supplier or db.get(Supplier, product.supplier_id)
    name, body = document(db, product, supplier)
    index_for(db).upsert(db, product.product_id, name, body)


def rebuild(db: Session) -> int:
    """Re-index every product (after a restore or an adapter change)."""
    index = index_for(db)
    n = 0
    for product, supplier in db.execute(select(Product, Supplier).join(Supplier, Supplier.supplier_id == Product.supplier_id)):
        name, body = document(db, product, supplier)
        index.upsert(db, product.product_id, name, body)
        n += 1
    db.commit()
    return n


# --- 5.3 ------------------------------------------------------------------------------------


@dataclass
class SearchParams:
    q: str | None = None
    category: str | None = None
    region: str | None = None
    min: int | None = None
    max: int | None = None
    available: bool | None = None
    supplier: str | None = None
    kind: str | None = None
    sort: str = "relevance"
    cursor: str | None = None
    limit: int = 24


def _fingerprint(p: SearchParams) -> str:
    raw = json.dumps(
        [p.q or "", p.category, p.region, p.min, p.max, p.available, p.supplier, p.kind, p.sort], separators=(",", ":")
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def encode_cursor(offset: int, p: SearchParams) -> str:
    raw = json.dumps({"o": offset, "f": _fingerprint(p)}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def decode_cursor(cursor: str, p: SearchParams) -> int:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        offset, fp = int(data["o"]), data["f"]
    except (ValueError, KeyError, TypeError):
        raise invalid("cursor", "not a cursor this search returned")
    if fp != _fingerprint(p) or offset < 0:
        raise invalid("cursor", "this cursor belongs to a different search")
    return offset


_STATE_BOOST = {"in_stock": 1.0, "low_stock": 0.8, "made_to_order": 0.5, "out_of_stock": 0.0, "discontinued": -1.0}


def result_item(prod: Product, supplier: Supplier, variant: ProductVariant, offer: Offer, n: int, regional: bool) -> dict:
    """One 5.3 result (`rating` and `orderable` are MINOR proposals)."""
    return {
        "product_id": prod.product_id,
        "supplier_id": prod.supplier_id,
        "supplier_name": supplier.name,
        "name": prod.name,
        "kind": prod.kind,
        "category": prod.category,
        "app_path": app_path_of(prod.category),
        "thumbnail_url": thumbnail_url(prod),
        "dims_mm": variant.dims_mm,
        "variants": n,
        "variant_id": variant.variant_id,
        "price": price_json(offer.price) if offer.price else None,
        "availability": availability_json(variant, offer.availability) if regional else None,
        "rating": rating_json(prod),
        "orderable": payments_ready(supplier),
    }


def items_for(db: Session, product_ids: list[str], region: str | None) -> list[dict]:
    """5.3 results for these products, in this order (picture search):
    public ones only, and with a region only those sold there."""
    if not product_ids:
        return []
    rows = {
        prod.product_id: (prod, supplier)
        for prod, supplier in db.execute(
            select(Product, Supplier)
            .join(Supplier, Supplier.supplier_id == Product.supplier_id)
            .where(Product.product_id.in_(product_ids), Product.status == "approved", Supplier.status == "verified")
        ).tuples()
    }
    variants = visible_variants(db, list(rows))
    offs = offers(db, list(rows), region) if region else {}
    out = []
    for pid in product_ids:
        if pid not in rows or not variants.get(pid):
            continue
        prod, supplier = rows[pid]
        vs = variants[pid]
        variant, offer = vs[0], Offer(None, None)
        if region:
            priced = [(v, offs[(pid, v.variant_id)]) for v in vs if (pid, v.variant_id) in offs and offs[(pid, v.variant_id)].price]
            if not priced:
                continue
            variant, offer = min(priced, key=lambda t: t[1].price.amount)
        out.append(result_item(prod, supplier, variant, offer, len(vs), region is not None))
    return out


def search(db: Session, p: SearchParams) -> dict:
    cats = active_categories(db)
    if p.category is not None and p.category not in cats:
        raise invalid("category", f"unknown category {p.category!r}; GET /market/categories lists them")
    region = region_or_invalid(db, p.region) if p.region is not None else None
    if region is None and (p.min is not None or p.max is not None or p.available or p.sort in ("price_asc", "price_desc")):
        raise invalid("region", "a region is needed to filter or sort by price or availability")
    if p.sort not in SORTS:
        raise invalid("sort", f"one of {', '.join(SORTS)}")
    if p.min is not None and p.max is not None and p.min > p.max:
        raise invalid("min", "min is greater than max")
    if p.supplier is not None and not is_hex32(p.supplier):
        raise invalid("supplier", "a supplier id is 32 hex characters")
    if p.kind is not None and p.kind not in ("object", "material", "finish", "theme"):
        raise invalid("kind", "one of object, material, finish, theme")
    offset = decode_cursor(p.cursor, p) if p.cursor else 0

    stmt = (
        select(Product, Supplier)
        .join(Supplier, Supplier.supplier_id == Product.supplier_id)
        .where(Product.status == "approved", Supplier.status == "verified")
    )
    if p.category:
        stmt = stmt.where((Product.category == p.category) | Product.category.like(f"{p.category}/%"))
    if p.supplier:
        stmt = stmt.where(Product.supplier_id == p.supplier)
    if p.kind:
        stmt = stmt.where(Product.kind == p.kind)
    scores: dict[str, float] | None = None
    if p.q and tokens(p.q):
        scores = index_for(db).match(db, p.q)
        if not scores:
            return {"results": [], "facets": {"category": {}, "supplier": {}}, "next_cursor": None}
        ids = list(scores)
        rows = []
        for start in range(0, len(ids), 500):
            rows += list(db.execute(stmt.where(Product.product_id.in_(ids[start : start + 500]))).tuples())
    else:
        rows = list(db.execute(stmt).tuples())

    ids = [prod.product_id for prod, _ in rows]
    variants = visible_variants(db, ids)
    offs = offers(db, ids, region.region) if region else {}

    hits = []
    for prod, supplier in rows:
        vs = variants.get(prod.product_id, [])
        if not vs:
            continue
        shown = None
        if region:
            for v in vs:
                offer = offs.get((prod.product_id, v.variant_id), Offer(None, None))
                if offer.price is None:
                    continue
                if p.available and not orderable(v, offer):
                    continue
                amount = offer.price.amount
                if (p.min is not None and amount < p.min) or (p.max is not None and amount > p.max):
                    continue
                if shown is None or amount < shown[1].price.amount:
                    shown = (v, offer)  # the cheapest matching variant is shown
            if shown is None:
                continue  # not sold in the region, or filtered out
            variant, offer = shown
        else:
            variant, offer = vs[0], Offer(None, None)
        hits.append((prod, supplier, variant, offer, len(vs)))

    facets = {"category": {}, "supplier": {}}
    for prod, supplier, *_ in hits:
        facets["category"][prod.category] = facets["category"].get(prod.category, 0) + 1
        facets["supplier"][prod.supplier_id] = facets["supplier"].get(prod.supplier_id, 0) + 1

    def newest(prod: Product) -> float:
        return prod.approved_at.timestamp() if prod.approved_at else 0.0

    if p.sort == "price_asc":
        hits.sort(key=lambda h: (h[3].price.amount, h[0].product_id))
    elif p.sort == "price_desc":
        hits.sort(key=lambda h: (-h[3].price.amount, h[0].product_id))
    elif p.sort == "newest":
        hits.sort(key=lambda h: (-newest(h[0]), h[0].product_id))
    else:

        def relevance(h) -> tuple:
            prod, _, variant, offer, _ = h
            score = (scores or {}).get(prod.product_id, 0.0)
            if region:
                stale = offer.availability is not None and offer.availability.stale
                state = None if stale else state_of(variant, offer.availability)
                score += _STATE_BOOST.get(state, 0.3)
            if prod.rating_count:
                score += 0.5 * (prod.rating_avg or 0) / 5
            return (-score, -newest(prod), prod.product_id)

        hits.sort(key=relevance)

    page = hits[offset : offset + p.limit]
    results = [result_item(prod, supplier, variant, offer, n, region is not None) for prod, supplier, variant, offer, n in page]
    more = offset + p.limit < len(hits)
    return {
        "results": results,
        "facets": facets,
        "next_cursor": encode_cursor(offset + p.limit, p) if more else None,
    }
