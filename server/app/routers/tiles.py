"""Public reads of the render output (PF6): tiles and a live share's set.

GET /tiles/{sha256}.jpg   one tile, immutable and cacheable forever, any origin
                          (WebGL refuses cross-origin textures without CORS).
                          With a CDN in front of the bucket, tiles_base points
                          there and this route only redirects.
GET /tiles/{sha256}.png   render-jobs 1.4 (PF6d): a face's id or depth PNG,
GET /tiles/{sha256}.json  a face's ids or the manifest's tour; the same rules
                          (one key per extension).
GET /s/{slug}/live        a live share's followed set (share-bundle MINOR
                          proposal): long-poll on `rev`, no credential.
"""

import asyncio
import re

from fastapi import APIRouter, Depends, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError, contract, enveloped
from ..database import SessionLocal, get_db
from ..projects import waiters
from ..render import live, queue, tiles
from ..render.models import RenderSet
from ..storage import get_store

router = APIRouter(tags=["tiles"], dependencies=[enveloped()], include_in_schema=False)
share_router = APIRouter(tags=["shares"], dependencies=[contract("share-bundle", 1, 1)])
_TILE = re.compile(r"^([0-9a-f]{64})\.(jpg|png|json)$")
PUBLIC = {"Cache-Control": tiles.IMMUTABLE, "Access-Control-Allow-Origin": "*", "X-Content-Type-Options": "nosniff"}
NO_STORE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"}


@router.get("/tiles/{name}")
def tile(name: str):
    match = _TILE.match(name)
    if match is None:
        raise ContractError("not_found", 404, "No such tile.")
    key = tiles.tile_key(match.group(1), match.group(2))
    store = get_store()
    if store.stat(key) is None:
        raise ContractError("not_found", 404, "No such tile.", headers={"Access-Control-Allow-Origin": "*"})
    file_path = getattr(store, "file_path", None)
    if file_path is not None:
        return FileResponse(file_path(key), media_type=tiles.MEDIA_TYPES[match.group(2)], headers=PUBLIC)
    return RedirectResponse(
        store.signed_get_url(key, expires_in=3600),
        status_code=307,
        headers={"Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*"},
    )


def _resolve(slug: str, panorama: str | None) -> tuple[str, int]:
    """The live share's set and its rev (404 / 410 as the share answers)."""
    with SessionLocal() as db:
        row = live.resolve(db, slug, panorama)
        return row.follow_job_id, row.rev


def _rev(set_id: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(RenderSet.rev).where(RenderSet.follow_job_id == set_id)) or 0


def _state(set_id: str) -> dict:
    with SessionLocal() as db:
        return live.state(db, db.get(RenderSet, set_id))


@share_router.get("/s/{slug}/live")
async def share_live(
    slug: str,
    response: Response,
    rev: int | None = None,
    wait_s: float = 0,
    panorama: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    if not 0 <= wait_s <= queue.STATUS_WAIT_MAX_S:
        raise ContractError(
            "validation_failed", 422, f"wait_s: 0 to {queue.STATUS_WAIT_MAX_S}.",
            {"fields": [{"field": "wait_s", "in": "query", "message": f"0 to {queue.STATUS_WAIT_MAX_S}"}]},
        )
    response.headers.update(NO_STORE)
    await run_in_threadpool(db.close)
    set_id, current = await run_in_threadpool(_resolve, slug, panorama)
    if wait_s <= 0 or rev is None or current > rev:
        return await run_in_threadpool(_state, set_id)
    # Viewers are anonymous and many: the wait re-checks one integer and reads
    # the manifest once, when it answers.
    waiter = waiters.Waiter(queue.job_key(set_id))
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_s
    try:
        while True:
            current = await run_in_threadpool(_rev, set_id)
            remaining = deadline - loop.time()
            if current > rev or remaining <= 0:
                return await run_in_threadpool(_state, set_id)
            await waiter.wait(min(waiters.RECHECK_S, remaining))
    finally:
        waiter.close()
