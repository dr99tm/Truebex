"""Analysis catalogue and the weather library (PF11).

GET    /analysis/catalogue                 the kinds, the weather files `params.weather` names,
                                           the wind terrain classes and Lawson criteria
                                           (device, session or API key)
GET    /admin/analysis/weather             admins: the library
PUT    /admin/analysis/weather/{id}        admins: add or replace an EPW (body = the file;
                                           ?name=&source=&licence=[&location=])
DELETE /admin/analysis/weather/{id}        admins: remove one
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..analysis import estimates, kinds, weather
from ..contract_http import ContractError, contract, enveloped
from ..database import get_db
from ..deps import require_admin
from ..models import User
from ..projects.caller import ProjectCaller
from .jobs import get_job_caller

router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[contract("render-jobs", 1, 2)])
admin_router = APIRouter(prefix="/admin/analysis", tags=["admin"], dependencies=[enveloped()])


@router.get("/catalogue")
def catalogue(caller: ProjectCaller = Depends(get_job_caller), db: Session = Depends(get_db)) -> dict:
    wind = kinds.PROFILES["wind"]
    return {
        "kinds": [
            {
                "kind": name,
                "class": k.worker_class,
                "feature": k.feature,
                "required_files": list(kinds.REQUIRED_FILES.get(name, ())),
                "optional_files": list(kinds.OPTIONAL_FILES.get(name, ())),
                "estimate_unit": estimates.DATA["kinds"][name]["unit"],
            }
            for name, k in kinds.KINDS.items()
            if kinds.handles(name)
        ],
        "weather": weather.listing(db),
        "terrain": [{"id": tid, **t} for tid, t in wind["terrain"].items()],
        "comfort": {"lawson": wind["lawson"]},
        "acoustics_bands_hz": kinds.PROFILES["acoustics"]["bands_hz"],
    }


@admin_router.get("/weather")
def list_weather(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return {"weather": weather.listing(db)}


@admin_router.put("/weather/{weather_id}")
async def put_weather(
    weather_id: str,
    request: Request,
    name: str = Query(..., max_length=120),
    source: str = Query(..., max_length=300),
    licence: str = Query(..., max_length=120),
    location: str | None = Query(default=None, max_length=160),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > weather.MAX_BYTES:
            raise ContractError("too_large", 413, "An EPW file of at most 20 MB.", {"limit": weather.MAX_BYTES})
    row = weather.put(db, weather_id, bytes(data), name=name, source=source, licence=licence, location=location)
    return weather.entry_json(row)


@admin_router.delete("/weather/{weather_id}")
def delete_weather(weather_id: str, _admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    weather.remove(db, weather_id)
    return {"removed": weather_id}
