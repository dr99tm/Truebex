"""Shares (contract share-bundle v1.0, §5.4-5.11) and the share page itself.

5.4-5.5 take a device token; 5.6-5.9 a device token or a website session;
5.10-5.11 nothing (anyone with the link). `GET /view/{slug}` is the share's
`url`: this share's link-preview tags around the static viewer shell.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from .. import ratelimit
from ..config import get_settings
from ..contract_http import ContractError, contract
from ..database import get_db
from ..deps import DeviceCaller, LicenceCaller, get_device, get_session_or_device
from ..shares import manifest, page
from ..shares import service as shares
from ..storage import get_store
from ..uploads.credentials import UploadCaller

router = APIRouter(tags=["shares"], dependencies=[contract("share-bundle", 1, 0)])
public = APIRouter(include_in_schema=False)

_PRIVATE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"}


class CreateShareIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    expires_in_days: int = Field(default=30, ge=1)
    manifest: Any

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title is empty")
        return v


class PatchShareIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    expires_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("title is empty")
        return v.strip() if v else v


class VisitIn(BaseModel):
    visitor: str = Field(pattern=r"^[0-9a-f]{32}$")


def _uploader(caller: DeviceCaller) -> UploadCaller:
    return UploadCaller(account_id=caller.user.id, kind="device", credential_id=caller.device.device_id)


# --- 5.4-5.9 -------------------------------------------------------------------------


@router.post("/shares", status_code=201)
def create_share(
    body: CreateShareIn, response: Response, caller: DeviceCaller = Depends(get_device), db: Session = Depends(get_db)
) -> dict:
    share, upload, created = shares.create(
        db, _uploader(caller), caller.user, title=body.title, days=body.expires_in_days, m=body.manifest
    )
    if not created:
        response.status_code = 200
    return {"share": shares.share_json(share), "upload": upload}


@router.post("/shares/{share_id}/publish")
def publish_share(share_id: str, caller: DeviceCaller = Depends(get_device), db: Session = Depends(get_db)) -> dict:
    share = shares.publish(db, caller.user, share_id)
    return {"share": shares.one_json(db, share)}


@router.get("/shares")
def list_shares(
    state: str | None = Query(default=None, pattern="^(uploading|live|expired|revoked)$"),
    caller: LicenceCaller = Depends(get_session_or_device),
    db: Session = Depends(get_db),
) -> dict:
    rows = shares.list_for(db, caller.user, state)
    visits = shares.visits_summary(db, [s.share_id for s in rows])
    return {
        "shares": [shares.share_json(s, visits[s.share_id]) for s in rows],
        "limits": shares.limits_json(shares.limits_for(db, caller.user)),
    }


@router.get("/shares/{share_id}")
def get_share(share_id: str, caller: LicenceCaller = Depends(get_session_or_device), db: Session = Depends(get_db)) -> dict:
    return shares.one_json(db, shares.get(db, caller.user, share_id))


@router.patch("/shares/{share_id}")
def patch_share(
    share_id: str,
    body: PatchShareIn,
    caller: LicenceCaller = Depends(get_session_or_device),
    db: Session = Depends(get_db),
) -> dict:
    if body.title is None and body.expires_at is None:
        raise ContractError("validation_failed", 422, "Send a title, an expires_at or both.", {"fields": []})
    share = shares.change(db, caller.user, share_id, title=body.title, expires_at=body.expires_at)
    return shares.one_json(db, share)


@router.delete("/shares/{share_id}")
def revoke_share(share_id: str, caller: LicenceCaller = Depends(get_session_or_device), db: Session = Depends(get_db)) -> dict:
    return shares.one_json(db, shares.revoke(db, caller.user, share_id))


# --- 5.10, 5.11 (anyone with the link) ------------------------------------------------------


@router.get("/s/{slug}")
def page_data(slug: str, response: Response, db: Session = Depends(get_db)) -> dict:
    response.headers.update(_PRIVATE)
    return shares.page_data(db, shares.by_slug(db, slug))


@router.post(
    "/s/{slug}/visits",
    status_code=204,
    dependencies=[ratelimit.limit(per_minute=60, burst=60, name="share-visits")],
)
def count_visit(slug: str, body: VisitIn, db: Session = Depends(get_db)) -> Response:
    shares.record_visit(db, shares.by_slug(db, slug), body.visitor)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


# --- the page and its preview image --------------------------------------------------------


def _html(content: str, status: int, headers: dict) -> HTMLResponse:
    return HTMLResponse(content, status_code=status, headers=headers)


@public.get("/view/{slug}")
def view(slug: str, db: Session = Depends(get_db)) -> HTMLResponse:
    s = get_settings()
    site = s.site_url.rstrip("/")
    base = {"X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}
    try:
        share = shares.by_slug(db, slug)
    except ContractError as exc:
        headers = {**base, "Cache-Control": "public, max-age=60", "Content-Security-Policy": page.csp(site, s.api_url)}
        return _html(page.render_ended(site=site, gone=exc.status == 410), exc.status, headers)

    urls = shares.page_urls(db, share)
    m = share.manifest
    start = manifest.start_panorama(m)
    preload = urls["derived"].get(start["file"], {}).get("pano-4096", {}).get("url") if start else None
    first_render = manifest.renders(m)[0]["file"] if manifest.renders(m) else None
    pdf = (m.get("sheets") or {}).get("file")
    content = page.render_view(
        title=share.title,
        m=m,
        url=shares.share_url(share.slug),
        slug=share.slug,
        api=s.share_base,
        site=site,
        card_url=shares.card_url(share.slug),
        preload_url=preload,
        first_render_url=urls["files"].get(first_render) if first_render else None,
        pdf_url=urls["files"].get(pdf) if pdf else None,
    )
    headers = {
        **base,
        "Cache-Control": "public, max-age=300",
        "Content-Security-Policy": page.csp(site, s.api_url),
    }
    return _html(content, 200, headers)


@public.get("/s/{slug}/card.jpg")
def card_image(slug: str, db: Session = Depends(get_db)) -> Response:
    try:
        share = shares.by_slug(db, slug)
    except ContractError as exc:
        return Response(status_code=exc.status, headers={"Cache-Control": "public, max-age=60"})
    if not share.card_key:
        return Response(status_code=404)
    with get_store().open(share.card_key) as fh:
        data = fh.read()
    return Response(
        data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=300", "X-Robots-Tag": "noindex", "X-Content-Type-Options": "nosniff"},
    )


@public.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    # Link-preview crawlers obey robots.txt (RFC 9309): share pages and their
    # cards are allowed, and the pages themselves say noindex. The API is not.
    return "User-agent: *\nAllow: /view/\nAllow: /s/\nDisallow: /\n"
