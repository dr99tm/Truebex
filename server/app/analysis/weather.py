"""The weather library for the `energy` kind (PF11 Scope 3).

`params.weather` names an id here; the EPW file lives in storage at
`weather/<id>.epw` and reaches the energy worker as a signed URL in the claim
(`inputs.files.weather`). Each entry records where the file came from and
under which licence, for GD2. Files are added by an admin (PUT
/admin/analysis/weather/{id}, or server/scripts/load_weather.py); nothing is
committed to the repository.
"""

import hashlib
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from ..storage import get_store
from .models import AnalysisWeather

ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
MAX_BYTES = 20 * 1024 * 1024


def key(weather_id: str) -> str:
    return f"weather/{weather_id}.epw"


def entry_json(row: AnalysisWeather) -> dict:
    return {
        "weather_id": row.weather_id,
        "name": row.name,
        "location": row.location,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "source": row.source,
        "licence": row.licence,
        "bytes": int(row.bytes),
        "sha256": row.sha256,
    }


def listing(db: Session) -> list[dict]:
    return [entry_json(r) for r in db.scalars(select(AnalysisWeather).order_by(AnalysisWeather.weather_id)).all()]


def known(db: Session, weather_id: str) -> bool:
    return db.get(AnalysisWeather, weather_id) is not None


def parse_location(data: bytes) -> tuple[str, float | None, float | None]:
    """The EPW's first line: LOCATION,city,state,country,source,WMO,lat,lon,tz,elev."""
    first = data.split(b"\n", 1)[0].decode("latin-1").strip()
    parts = [p.strip() for p in first.split(",")]
    if len(parts) < 8 or parts[0].upper() != "LOCATION":
        raise ContractError(
            "validation_failed", 422, "An EPW weather file starts with its LOCATION line.",
            {"fields": [{"field": "body", "in": "body", "message": "an EPW file"}]},
        )
    place = ", ".join(p for p in (parts[1], parts[3]) if p and p != "-")
    try:
        return place, float(parts[6]), float(parts[7])
    except ValueError:
        return place, None, None


def put(db: Session, weather_id: str, data: bytes, *, name: str, source: str, licence: str, location: str | None = None, now: datetime | None = None) -> AnalysisWeather:
    if not ID.match(weather_id or ""):
        raise ContractError("validation_failed", 422, "weather_id: 3 to 64 lowercase letters, digits and dashes", {"fields": [{"field": "weather_id"}]})
    if not data or len(data) > MAX_BYTES:
        raise ContractError("too_large" if data else "validation_failed", 413 if data else 422, "An EPW file of at most 20 MB.", {"limit": MAX_BYTES})
    for field, value in (("name", name), ("source", source), ("licence", licence)):
        if not (value or "").strip():
            raise ContractError("validation_failed", 422, f"{field}: required (GD2 records the source and the licence of every file)", {"fields": [{"field": field}]})
    place, lat, lon = parse_location(data)
    get_store().put(key(weather_id), data, content_type="text/plain; charset=latin-1")
    row = db.get(AnalysisWeather, weather_id)
    if row is None:
        row = AnalysisWeather(weather_id=weather_id, created_at=now or clock.now())
        db.add(row)
    row.name = name.strip()[:120]
    row.location = (location or place)[:160]
    row.latitude, row.longitude = lat, lon
    row.source = source.strip()[:300]
    row.licence = licence.strip()[:120]
    row.storage_key = key(weather_id)
    row.sha256 = hashlib.sha256(data).hexdigest()
    row.bytes = len(data)
    db.commit()
    return row


def remove(db: Session, weather_id: str) -> None:
    row = db.get(AnalysisWeather, weather_id)
    if row is None:
        raise ContractError("not_found", 404, "No such weather file.")
    get_store().delete(row.storage_key)
    db.delete(row)
    db.commit()


def claim_file(db: Session, weather_id: str, ttl: int) -> dict | None:
    row = db.get(AnalysisWeather, weather_id)
    if row is None:
        return None
    return {"sha256": row.sha256, "bytes": int(row.bytes), "url": get_store().signed_get_url(row.storage_key, expires_in=ttl)}
