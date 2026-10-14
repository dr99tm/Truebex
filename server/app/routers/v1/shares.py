"""`/v1/uploads…` and `/v1/shares…`: share-bundle 5.1-5.9 for API keys (PF12;
a MINOR proposal adds API keys to the contract's §4).

Uploads go to the contract router's handlers (`app/routers/uploads.py`) with
the key as an `api_key` upload caller; the scope follows the session's
purpose: `share` needs `shares:write`, `snapshot` `projects:write` (for
`/v1/projects/{id}/snapshots`), `job-input` `jobs:write`. Shares call the same
service functions as `app/routers/shares.py`.
"""

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.orm import Session

from ...contract_http import ContractError, contract
from ...database import get_db
from ...deps import ApiCaller
from ...shares import service as shares
from ...uploads import service as uploads
from ...uploads.credentials import UploadCaller
from .. import uploads as c_uploads
from . import models as m
from .common import AnyKey, doc, scope

router = APIRouter(tags=["shares"], dependencies=[contract("share-bundle", 1, 1)])

PURPOSE_SCOPES = {"share": "shares:write", "snapshot": "projects:write", "job-input": "jobs:write"}
Shares = scope("shares:write")


def upload_caller(api: ApiCaller) -> UploadCaller:
    return UploadCaller(account_id=api.user.id, kind="api_key", credential_id=str(api.key.id))


def _need_purpose(api: ApiCaller, purpose: str) -> None:
    needed = PURPOSE_SCOPES.get(purpose)
    if needed is None:
        raise ContractError(
            "forbidden", 403, f"API keys cannot open {purpose} uploads.", {"purpose": purpose, "credential": "api_key"}
        )
    if needed not in api.scopes:
        raise ContractError(
            "forbidden",
            403,
            f"A {purpose} upload needs the {needed} scope.",
            {"needed": needed, "scopes": list(api.scopes), "purpose": purpose},
        )


# --- 5.1-5.3 uploads ---------------------------------------------------------------------


@router.post("/uploads", status_code=201, operation_id="uploads_create", **doc("shares:write", m.Upload, 201, errors=(401, 403, 413, 422, 429)))
def open_upload(body: m.UploadRequest, api: ApiCaller = AnyKey, db: Session = Depends(get_db)) -> dict:
    """Open an upload session for a set of files (5.1); files the account already stored answer `present`.
    The scope follows `purpose`: share → shares:write, snapshot → projects:write, job-input → jobs:write."""
    _need_purpose(api, body.purpose)
    return c_uploads.open_upload(body=body, caller=upload_caller(api), db=db)


@router.get("/uploads/{upload_id}", operation_id="uploads_get", **doc("shares:write", m.Upload, errors=(401, 403, 404, 410, 429)))
def upload_status(upload_id: str, api: ApiCaller = AnyKey, db: Session = Depends(get_db)) -> dict:
    """What has arrived, to resume (5.3)."""
    caller = upload_caller(api)
    _need_purpose(api, uploads.get_session(db, caller, upload_id).purpose)
    return c_uploads.upload_status(upload_id=upload_id, caller=caller, db=db)


@router.put(
    "/uploads/{upload_id}/files/{sha256}/parts/{n}",
    status_code=204,
    operation_id="uploads_put_part",
    openapi_extra={
        "x-truebex-scope": "shares:write",
        "requestBody": {"required": True, "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}},
    },
    responses=doc(None, errors=(401, 403, 404, 410, 413, 422, 429))["responses"],
)
async def put_part(
    upload_id: str,
    sha256: str,
    n: int,
    request: Request,
    x_part_sha256: str | None = Header(default=None),
    api: ApiCaller = AnyKey,
    db: Session = Depends(get_db),
) -> Response:
    """Send one part (5.2): every part `part_bytes` long but the last, with `X-Part-Sha256`; repeating one is harmless."""
    from fastapi.concurrency import run_in_threadpool

    caller = upload_caller(api)
    session = await run_in_threadpool(uploads.get_session, db, caller, upload_id)
    _need_purpose(api, session.purpose)
    return await c_uploads.put_part(
        upload_id=upload_id, sha256=sha256, n=n, request=request, x_part_sha256=x_part_sha256, caller=caller, db=db
    )


# --- 5.4-5.9 shares ------------------------------------------------------------------------


@router.post("/shares", status_code=201, operation_id="shares_create", **doc("shares:write", m.ShareCreated, 201, errors=(401, 403, 422, 429)))
def create_share(body: m.ShareRequest, response: Response, api: ApiCaller = Shares, db: Session = Depends(get_db)) -> dict:
    """Create a share from a bundle manifest and get its upload session (5.4); the same `bundle_id` returns the same share (200)."""
    # 1.1: `replace_share_id` sends the bundle as an Update of that share.
    share, upload, created = shares.create(
        db, upload_caller(api), api.user, title=body.title, days=body.expires_in_days, m=body.manifest,
        replace=body.replace_share_id,
    )
    if not created:
        response.status_code = 200
    return {"share": shares.share_json(share), "upload": upload}


@router.post("/shares/{share_id}/publish", operation_id="shares_publish", **doc("shares:write", m.SharePublished, errors=(401, 403, 404, 422, 429)))
def publish_share(share_id: str, api: ApiCaller = Shares, db: Session = Depends(get_db)) -> dict:
    """Verify every file and go live (5.5); 422 `upload_incomplete` names the missing files."""
    return {"share": shares.one_json(db, shares.publish(db, api.user, share_id))}


@router.get("/shares", operation_id="shares_list", **doc("shares:write", m.ShareList))
def list_shares(
    state: str | None = Query(default=None, pattern="^(uploading|live|expired|revoked)$"),
    api: ApiCaller = Shares,
    db: Session = Depends(get_db),
) -> dict:
    """The account's shares and its plan's share limits (5.6)."""
    rows = shares.list_for(db, api.user, state)
    visits = shares.visits_summary(db, [s.share_id for s in rows])
    return {
        "shares": [shares.share_json(s, visits[s.share_id]) for s in rows],
        "limits": shares.limits_json(shares.limits_for(db, api.user)),
    }


@router.get("/shares/{share_id}", operation_id="shares_get", **doc("shares:write", m.Share))
def get_share(share_id: str, api: ApiCaller = Shares, db: Session = Depends(get_db)) -> dict:
    """One share with its visits of the last 30 days (5.7)."""
    return shares.one_json(db, shares.get(db, api.user, share_id))


@router.patch("/shares/{share_id}", operation_id="shares_update", **doc("shares:write", m.Share))
def patch_share(share_id: str, body: m.ShareUpdate, api: ApiCaller = Shares, db: Session = Depends(get_db)) -> dict:
    """Change the title or the expiry (5.8)."""
    if body.title is None and body.expires_at is None:
        raise ContractError("validation_failed", 422, "Send a title, an expires_at or both.", {"fields": []})
    return shares.one_json(db, shares.change(db, api.user, share_id, title=body.title, expires_at=body.expires_at))


@router.delete("/shares/{share_id}", operation_id="shares_revoke", **doc("shares:write", m.Share))
def revoke_share(share_id: str, api: ApiCaller = Shares, db: Session = Depends(get_db)) -> dict:
    """Revoke a share (5.9): its page answers 410 from then on."""
    return shares.one_json(db, shares.revoke(db, api.user, share_id))
