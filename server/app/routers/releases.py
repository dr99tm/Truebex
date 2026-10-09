"""Release feed and downloads (contract licence-api 5.13, 5.14). No auth:
entitlements gate features, not installs."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..contract_http import CONTRACT_HEADER, contract
from ..database import get_db
from ..releases import service
from ..storage import get_store

router = APIRouter(prefix="/releases", tags=["releases"], dependencies=[contract("licence-api", 1, 0)])

Channel = Literal["stable", "beta"]
Platform = Literal["win64"]


@router.get("/feed")
def feed(channel: Channel = "stable", platform: Platform = "win64", db: Session = Depends(get_db)) -> dict:
    """5.13: signed manifests, newest first, at most 10. `beta` lists stable too."""
    return service.feed(db, channel, platform)


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
