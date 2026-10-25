"""Release feed and downloads (contract licence-api 5.13, 5.14). No auth:
entitlements gate features, not installs."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import enums
from ..contract_http import CONTRACT_HEADER, ContractError, contract
from ..database import get_db
from ..releases import service
from ..storage import get_store

router = APIRouter(prefix="/releases", tags=["releases"], dependencies=[contract("licence-api", 1, 0)])

CHANNELS = ("stable", "beta")
Platform = Literal["win64"]


@router.get("/feed")
def feed(channel: str = "stable", platform: Platform = "win64", db: Session = Depends(get_db)) -> dict:
    """5.13: signed manifests, newest first, at most 10. `beta` lists stable too.
    The channel in any case (PF14f: the app's updater writes it from an FName)."""
    name = enums.canonical(channel, CHANNELS)
    if name is None:
        raise ContractError(
            "validation_failed", 422, "channel: stable or beta.",
            {"fields": [{"field": "channel", "in": "query", "message": "stable or beta"}]},
        )
    return service.feed(db, name, platform)


@router.get("/{version}/download")
def download(version: str, request: Request, platform: Platform = "win64", db: Session = Depends(get_db)):
    """5.14: a 15-minute download URL: 302, or JSON with `Accept: application/json`."""
    row = service.find_live(db, version, platform)
    out = service.download_url(db, get_store(), row)
    if "application/json" in request.headers.get("accept", ""):
        return out
    return RedirectResponse(
        out["url"],
        status_code=302,
        headers={CONTRACT_HEADER: request.state.contract, "Cache-Control": "no-store"},
    )
