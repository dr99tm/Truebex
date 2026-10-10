"""Estimates (contract 5.1 `cost_units_estimate`).

Seconds per unit (a view for `panorama` and `tiles`, an item for `pack`) come
from estimates.json, the placeholders GD3 measures; once 50 jobs of a kind
and quality have succeeded, the median of their last 50 replaces the seed.
Quotas refuse on estimates; charges use the measured time.
"""

import json
import statistics
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import quotas
from .models import RenderJob

PATH = Path(__file__).with_name("estimates.json")
_DATA = json.loads(PATH.read_text(encoding="utf-8"))
WINDOW = int(_DATA.get("window", 50))
SEEDS: dict[str, dict[str, float]] = _DATA["seconds_per_unit"]


def seconds_per_unit(db: Session, kind: str, quality: str) -> float:
    rows = db.execute(
        select(RenderJob.wall_s, RenderJob.est_units)
        .where(
            RenderJob.kind == kind,
            RenderJob.quality == quality,
            RenderJob.state == "succeeded",
            RenderJob.wall_s.is_not(None),
        )
        .order_by(RenderJob.finished_at.desc())
        .limit(WINDOW)
    ).all()
    if len(rows) >= WINDOW:
        return float(statistics.median(w / max(1, u) for w, u in rows))
    seeds = SEEDS.get(kind) or SEEDS["panorama"]
    return float(seeds.get(quality, seeds["standard"]))


def units(kind: str, views: list, params: dict) -> int:
    if quotas.KINDS[kind].unit == "item":
        return max(1, len(params.get("items") or []))
    return max(1, len(views))


def estimate(db: Session, kind: str, quality: str, n_units: int) -> Decimal:
    seconds = seconds_per_unit(db, kind, quality) * n_units
    return quotas.cost_units(seconds, quotas.KINDS[kind].worker_class)
