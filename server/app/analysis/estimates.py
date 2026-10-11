"""Estimates before an analysis runs (contract 5.1 `cost_units_estimate`; PF11 Scope 7).

    wind       cells × iterations       cells from the geometry: the domain (5 H upstream,
                                        15 H downstream, 5 H to the sides and above) at H/10
                                        cells, refined around the building
    energy     zones × timesteps        from the epJSON model: zones, timesteps per hour, a year
    acoustics  rays × sources           from the params
    texture    pixels × maps            from the params

seconds = fixed_s + seconds_per_unit × units (estimates.json, GD3's worked
examples); once 50 jobs of a kind have succeeded, the median of their measured
seconds per unit replaces the seed. cu = seconds / 60 × the class weight,
rounded up to 0.1. Quotas refuse on estimates; charges use measured time.
"""

import json
import math
import statistics
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..render import quotas
from ..render.models import RenderJob
from . import kinds
from .inputs import Mesh

DATA = json.loads(Path(__file__).with_name("estimates.json").read_text(encoding="utf-8"))
WINDOW = int(DATA.get("window", 50))


@dataclass(frozen=True)
class Estimate:
    units: int
    seconds: float
    cost_units: Decimal
    detail: dict


def wind_cells(mesh: Mesh) -> int:
    p = kinds.PROFILES["wind"]
    d = p["domain_h"]
    h = max(mesh.height_m, 3.0)
    footprint = max(mesh.footprint_m, 1.0)
    length = footprint + (d["upstream"] + d["downstream"]) * h
    width = footprint + 2 * d["sides"] * h
    height = h + d["top"] * h
    cell = h / p["cells_per_h"]
    bounds = DATA["wind_cells"]
    cells = length * width * height / cell**3 * bounds["refinement_factor"]
    return int(min(bounds["max"], max(bounds["min"], cells)))


def units_for(kind: str, *, mesh: Mesh | None = None, zones: int = 0, tph: int = 0, params: dict | None = None) -> tuple[int, dict]:
    params = params or {}
    if kind == "wind":
        cells = wind_cells(mesh)
        iterations = kinds.PROFILES["wind"]["iterations_max"]
        return max(1, math.ceil(cells * iterations / 1e6)), {"cells": cells, "iterations": iterations, "triangles": mesh.triangles}
    if kind == "energy":
        steps = zones * tph * kinds.PROFILES["energy"]["hours"]
        return max(1, math.ceil(steps / 1000)), {"zones": zones, "timesteps": tph * kinds.PROFILES["energy"]["hours"]}
    if kind == "acoustics":
        sources = len(params.get("sources") or [])
        return max(1, math.ceil(params["rays"] * sources / 1000)), {"rays": params["rays"], "sources": sources}
    maps = len(params.get("maps") or [])
    return max(1, math.ceil(params["size"] ** 2 * maps / 1e6)), {"size": params["size"], "maps": maps}


def seconds_per_unit(db: Session, kind: str) -> float:
    seed = DATA["kinds"][kind]
    rows = db.execute(
        select(RenderJob.wall_s, RenderJob.est_units)
        .where(RenderJob.kind == kind, RenderJob.state == "succeeded", RenderJob.wall_s.is_not(None))
        .order_by(RenderJob.finished_at.desc())
        .limit(WINDOW)
    ).all()
    if len(rows) >= WINDOW:
        return float(statistics.median(max(0.0, w - seed["fixed_s"]) / max(1, u) for w, u in rows))
    return float(seed["seconds_per_unit"])


def estimate(db: Session, kind: str, units: int, detail: dict) -> Estimate:
    seed = DATA["kinds"][kind]
    seconds = float(seed["fixed_s"]) + seconds_per_unit(db, kind) * units
    weight = quotas.class_weights().get(kinds.KINDS[kind].worker_class, Decimal("1.0"))
    cu = quotas.round_up_tenth(Decimal(str(seconds)) / 60 * weight).quantize(quotas.TENTH)
    return Estimate(units=units, seconds=round(seconds, 1), cost_units=cu, detail={**detail, "unit": seed["unit"], "seconds": round(seconds, 1)})
