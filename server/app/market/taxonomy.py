"""Categories rooted on the app's taxonomy (contract §6.2) and the regions.

`taxonomy/categories.json` is the app's `CAD/taxonomy/categories.json`,
copied byte for byte and never edited: 5.1 reports its SHA-256, and a new
path in the app is a MINOR contract change that replaces the copy. The
marketplace's deeper categories (`furniture/seating/sofas`) live in
`taxonomy/market_categories.json`; each one starts with an app path, and its
`app_path` is the deepest prefix the app knows, so the app places a product
by `CadTaxonomy::RuleOf(app_path)` with no mapping table.
"""

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MarketCategory, MarketRegion

HERE = Path(__file__).parent
TAXONOMY_FILE = HERE / "taxonomy" / "categories.json"
MARKET_CATEGORIES_FILE = HERE / "taxonomy" / "market_categories.json"
REGIONS_FILE = HERE / "regions.json"

# Sheet templates live in the taxonomy but are never products.
NOT_PRODUCT_ROOTS = frozenset({"sheets"})

PATH_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$")


@lru_cache
def taxonomy_rows() -> tuple[dict, ...]:
    data = json.loads(TAXONOMY_FILE.read_text(encoding="utf-8"))
    return tuple(data["categories"])


@lru_cache
def app_paths() -> frozenset[str]:
    return frozenset(row["path"] for row in taxonomy_rows())


@lru_cache
def taxonomy_sha256() -> str:
    return hashlib.sha256(TAXONOMY_FILE.read_bytes()).hexdigest()


def app_path_of(path: str) -> str | None:
    """The deepest prefix of `path` in the app's tree; None when the path is
    not rooted on it (or is a sheet template)."""
    if not isinstance(path, str) or not PATH_RE.match(path) or len(path) > 160:
        return None
    parts = path.split("/")
    if parts[0] in NOT_PRODUCT_ROOTS:
        return None
    known = app_paths()
    for n in range(len(parts), 0, -1):
        prefix = "/".join(parts[:n])
        if prefix in known:
            return prefix
    return None


def parent_of(path: str) -> str | None:
    return path.rsplit("/", 1)[0] if "/" in path else None


def _category_rows() -> list[tuple[str, str]]:
    rows = [
        (row["path"], row["label"])
        for row in taxonomy_rows()
        if row["path"].split("/")[0] not in NOT_PRODUCT_ROOTS
    ]
    extra = json.loads(MARKET_CATEGORIES_FILE.read_text(encoding="utf-8"))["categories"]
    rows += [(row["path"], row["label"]) for row in extra]
    return rows


def seed(db: Session) -> None:
    """Upsert the categories and regions from the files (admin-added
    categories stay). Called at startup by database.init_db."""
    have = {c.path: c for c in db.scalars(select(MarketCategory))}
    for sort, (path, label) in enumerate(_category_rows()):
        app_path = app_path_of(path)
        if app_path is None:
            raise ValueError(f"market category {path!r} is not rooted on the app's taxonomy")
        row = have.get(path) or MarketCategory(path=path)
        row.label, row.app_path, row.parent_path, row.sort = label, app_path, parent_of(path), sort
        db.add(row)

    regions = json.loads(REGIONS_FILE.read_text(encoding="utf-8"))["regions"]
    have_regions = {r.region: r for r in db.scalars(select(MarketRegion))}
    for sort, spec in enumerate(regions):
        row = have_regions.get(spec["region"]) or MarketRegion(region=spec["region"])
        row.name, row.currency, row.exponent = spec["name"], spec["currency"], spec["exponent"]
        row.tax_name = spec["tax"]["name"]
        row.tax_rate_bp = spec["tax"]["rate_bp"]
        row.prices_include_tax = spec["tax"]["prices_include_tax"]
        row.sort = sort
        db.add(row)
    db.commit()


def active_categories(db: Session) -> dict[str, MarketCategory]:
    rows = db.scalars(select(MarketCategory).where(MarketCategory.active.is_(True)).order_by(MarketCategory.sort))
    return {c.path: c for c in rows}


def active_regions(db: Session) -> dict[str, MarketRegion]:
    rows = db.scalars(select(MarketRegion).where(MarketRegion.active.is_(True)).order_by(MarketRegion.sort))
    return {r.region: r for r in rows}


def region_json(r: MarketRegion) -> dict:
    return {
        "region": r.region,
        "name": r.name,
        "currency": r.currency,
        "exponent": r.exponent,
        "tax": {"name": r.tax_name, "rate_bp": r.tax_rate_bp, "prices_include_tax": r.prices_include_tax},
    }
