"""Signed file URLs for the `local` storage adapter (PF14 Plumbing).

GET /files/{key}?exp=&sig=[&fn=] streams the blob (HTTP Range supported, so
the app's updater can resume). PUT /files/{key}?exp=&sig=&ct=&max= stores a
body up to `max` bytes. A missing, altered or expired signature answers 403.
The `s3` adapter (PF14) presigns its own URLs and never comes here.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..contract_http import enveloped
from ..storage import InvalidKey, check_key, get_store

router = APIRouter(prefix="/files", tags=["files"], dependencies=[enveloped()], include_in_schema=False)


def _local():
    store = get_store()
    if not hasattr(store, "verify"):
        raise HTTPException(status_code=404, detail="Not found.")
    return store


def _key(key: str) -> str:
    try:
        return check_key(key)
    except InvalidKey:
        raise HTTPException(status_code=422, detail="Invalid file key.")


@router.get("/{key:path}")
def download(key: str, request: Request, exp: str | None = None, sig: str | None = None, fn: str | None = None):
    key = _key(key)
    store = _local()
    if not store.verify("GET", key, exp, sig, fn or ""):
        raise HTTPException(status_code=403, detail="This download link has expired or is not valid.")
    info = store.stat(key)
    if info is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(
        store.file_path(key),
        media_type=info.content_type,
        filename=fn or None,
        headers={"Cache-Control": "private, max-age=0, no-store"},
    )


@router.put("/{key:path}", status_code=201)
async def upload(
    key: str,
    request: Request,
    exp: str | None = None,
    sig: str | None = None,
    ct: str = "",
    max: str = "0",  # noqa: A002 - the query parameter's name
) -> dict:
    key = _key(key)
    store = _local()
    if not max.isdigit() or not store.verify("PUT", key, exp, sig, f"{ct}\n{max}"):
        raise HTTPException(status_code=403, detail="This upload link has expired or is not valid.")
    if ct and request.headers.get("content-type", "").split(";")[0].strip() != ct:
        raise HTTPException(status_code=415, detail=f"Expected Content-Type {ct}.")
    limit = int(max)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(status_code=413, detail=f"Uploads to this link are limited to {limit} bytes.")
    info = store.put(key, bytes(body), content_type=ct or "application/octet-stream")
    return {"key": info.key, "bytes": info.bytes, "sha256": info.sha256}
