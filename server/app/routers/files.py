"""Signed file URLs of the `local` storage adapter (app/storage/local.py).

GET /files/{key}?exp=&sig=[&fn=]           download
PUT /files/{key}?exp=&ct=&max=&sig=        upload (Content-Type must equal ct)

422 for a key that is not a valid storage key, 403 for a missing, wrong or
expired signature, 404 for a missing file, 413 above `max`. With the `s3`
adapter these routes answer 404: URLs point at the bucket instead.
"""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse

from ..storage import InvalidKey, get_store, validate_key
from ..storage.local import LocalStore

router = APIRouter(prefix="/files", tags=["files"], include_in_schema=False)


def _local() -> LocalStore:
    store = get_store()
    if not isinstance(store, LocalStore):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return store


def _checked_key(key: str) -> str:
    try:
        return validate_key(key)
    except InvalidKey as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _expiry(raw: str | None) -> int:
    try:
        return int(raw or "")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Link is not valid.")


@router.get("/{key:path}")
def download(key: str, exp: str | None = None, sig: str = "", fn: str | None = None):
    store = _local()
    key = _checked_key(key)
    if not store.verify("GET", key, _expiry(exp), sig, fn or ""):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Link is not valid or has expired.")
    info = store.stat(key)
    if info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    headers = {"Cache-Control": "private, no-store"}
    return FileResponse(
        store._path(key),
        media_type=info.content_type,
        filename=fn,
        headers=headers,
    )


@router.put("/{key:path}", status_code=status.HTTP_201_CREATED)
async def upload(
    key: str,
    request: Request,
    exp: str | None = None,
    ct: str = "",
    max: str = "0",  # noqa: A002 - the signed query parameter's name
    sig: str = "",
):
    store = _local()
    key = _checked_key(key)
    sent_type = request.headers.get("content-type", "")
    if not store.verify("PUT", key, _expiry(exp), sig, ct, max) or sent_type != ct:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Link is not valid or has expired.")
    limit = int(max)
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large.")
    info = store.put(key, bytes(body), content_type=ct)
    return JSONResponse(status_code=201, content={"key": info.key, "size": info.size})
