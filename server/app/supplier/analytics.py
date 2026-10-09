"""What designers look at and buy, per product, region and UTC day (PF8
Scope 6): search impressions, product views, geometry downloads
(placements), requests for quote, orders and order value. Counts only:
no buyer, no account, no address is ever stored here.

PF7's endpoints emit `market.hooks` events; the listeners below turn them
into one `count_event()` upsert each.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..market import hooks
from ..market.common import money, now
from ..market.models import MarketOrder, MarketOrderLine, MarketRegion, Product, Supplier
from .models import MarketEventDaily

FIELDS = ("impressions", "views", "geometry_downloads", "quotes", "orders", "order_value")
MAX_DAYS = 366


def _insert(db: Session):
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert(MarketEventDaily)


def count_event(
    db: Session, counts: dict[tuple[str, str], dict[str, int]], *, day: date | None = None, commit: bool = True
) -> None:
    """Add counts per (product_id, region) for one day: {(pid, "AE"): {"views": 1}}."""
    if not counts:
        return
    day = day or now().date()
    pids = sorted({pid for pid, _ in counts})
    owners = dict(db.execute(select(Product.product_id, Product.supplier_id).where(Product.product_id.in_(pids))).all())
    for (pid, region), add in counts.items():
        if pid not in owners:
            continue
        values = {k: int(add.get(k, 0)) for k in FIELDS}
        if not any(values.values()):
            continue
        stmt = _insert(db).values(product_id=pid, supplier_id=owners[pid], region=region or "", day=day, **values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["product_id", "region", "day"],
            set_={k: getattr(MarketEventDaily, k) + stmt.excluded[k] for k in FIELDS if values[k]},
        )
        db.execute(stmt)
    if commit:
        db.commit()


# --- Listeners -------------------------------------------------------------------------------


@hooks.on("search.results")
def _impressions(db: Session, product_ids: list[str], region: str | None) -> None:
    count_event(db, {(pid, region or ""): {"impressions": 1} for pid in dict.fromkeys(product_ids)})


@hooks.on("product.viewed")
def _viewed(db: Session, product_id: str, region: str | None) -> None:
    count_event(db, {(product_id, region or ""): {"views": 1}})


@hooks.on("geometry.downloaded")
def _downloaded(db: Session, product_id: str, region: str | None) -> None:
    count_event(db, {(product_id, region or ""): {"geometry_downloads": 1}})


def _lines(db: Session, order: MarketOrder) -> list[MarketOrderLine]:
    return list(db.scalars(select(MarketOrderLine).where(MarketOrderLine.order_id == order.order_id)))


@hooks.on("order.placed")
def _quotes(db: Session, order: MarketOrder) -> None:
    if order.kind == "quote":
        count_event(db, {(ln.product_id, order.region): {"quotes": 1} for ln in _lines(db, order)})


@hooks.on("order.confirmed")
def _orders(db: Session, order: MarketOrder) -> None:
    counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"orders": 0, "order_value": 0})
    for ln in _lines(db, order):
        unit = ln.quoted_unit_amount if ln.quoted_unit_amount is not None else ln.unit_amount
        c = counts[(ln.product_id, order.region)]
        c["orders"] = 1
        c["order_value"] += unit * ln.qty
    count_event(db, dict(counts))


# --- The report ------------------------------------------------------------------------------


def _parse_day(text: str | None, field: str, default: date) -> date:
    if not text:
        return default
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ContractError(
            "validation_failed",
            422,
            f"{field}: a day as YYYY-MM-DD",
            {"fields": [{"field": field, "in": "query", "message": "a day as YYYY-MM-DD"}]},
        )


def report(db: Session, supplier: Supplier, start: str | None, end: str | None, region: str | None) -> dict:
    today = now().date()
    last = _parse_day(end, "to", today)
    first = _parse_day(start, "from", last - timedelta(days=29))
    if first > last or (last - first).days >= MAX_DAYS:
        raise ContractError(
            "validation_failed",
            422,
            f"from: at most {MAX_DAYS} days, and not after to",
            {"fields": [{"field": "from", "in": "query", "message": f"at most {MAX_DAYS} days, not after to"}]},
        )
    regions = {r.region: r for r in db.scalars(select(MarketRegion))}
    if region and region not in regions:
        raise ContractError(
            "validation_failed",
            422,
            "region: not a region Truebex serves",
            {"fields": [{"field": "region", "in": "query", "message": "not a region Truebex serves"}]},
        )
    stmt = select(MarketEventDaily).where(
        MarketEventDaily.supplier_id == supplier.supplier_id, MarketEventDaily.day >= first, MarketEventDaily.day <= last
    )
    if region:
        stmt = stmt.where(MarketEventDaily.region == region)
    rows = list(db.scalars(stmt))

    def value_list(by_region: dict[str, int]) -> list[dict]:
        per_currency: dict[tuple[str, int], int] = defaultdict(int)
        for code, amount in by_region.items():
            r = regions.get(code)
            if r is not None and amount:
                per_currency[(r.currency, r.exponent)] += amount
        return [money(a, c, e) for (c, e), a in sorted(per_currency.items())]

    days: dict[date, dict] = {}
    day_values: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    products: dict[str, dict] = {}
    product_values: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals = {k: 0 for k in FIELDS if k != "order_value"}
    total_values: dict[str, int] = defaultdict(int)
    for d in range((last - first).days + 1):
        day = first + timedelta(days=d)
        days[day] = {"day": day.isoformat(), **{k: 0 for k in totals}}
    for r in rows:
        day = r.day if isinstance(r.day, date) else datetime.fromisoformat(str(r.day)).date()
        p = products.setdefault(r.product_id, {"product_id": r.product_id, **{k: 0 for k in totals}})
        for k in totals:
            v = getattr(r, k)
            days[day][k] += v
            p[k] += v
            totals[k] += v
        day_values[day][r.region] += r.order_value
        product_values[r.product_id][r.region] += r.order_value
        total_values[r.region] += r.order_value
    names = {
        p.product_id: (p.sku, p.name)
        for p in db.scalars(select(Product).where(Product.product_id.in_(list(products))))
    } if products else {}
    out_products = []
    for pid, p in products.items():
        sku, name = names.get(pid, ("", ""))
        out_products.append({**p, "sku": sku, "name": name, "order_value": value_list(product_values[pid])})
    out_products.sort(key=lambda p: (-p["orders"], -p["views"], -p["impressions"], p["name"]))
    return {
        "from": first.isoformat(),
        "to": last.isoformat(),
        "region": region or None,
        "days": [{**v, "order_value": value_list(day_values[k])} for k, v in sorted(days.items())],
        "products": out_products,
        "totals": {**totals, "order_value": value_list(total_values)},
        "regions": sorted(
            set(db.scalars(select(MarketEventDaily.region).where(MarketEventDaily.supplier_id == supplier.supplier_id).distinct()))
        ),
    }


def week(db: Session, supplier: Supplier) -> dict:
    """This week's (the last 7 days') views and quotes for the overview."""
    since = now().date() - timedelta(days=6)
    row = db.execute(
        select(
            func.coalesce(func.sum(MarketEventDaily.impressions), 0),
            func.coalesce(func.sum(MarketEventDaily.views), 0),
            func.coalesce(func.sum(MarketEventDaily.geometry_downloads), 0),
            func.coalesce(func.sum(MarketEventDaily.quotes), 0),
            func.coalesce(func.sum(MarketEventDaily.orders), 0),
        ).where(MarketEventDaily.supplier_id == supplier.supplier_id, MarketEventDaily.day >= since)
    ).one()
    return dict(zip(("impressions", "views", "geometry_downloads", "quotes", "orders"), (int(v) for v in row)))
