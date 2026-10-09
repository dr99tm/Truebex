"""Admin endpoints (users.is_admin, set by hand). PF7 and PF14 add theirs here.

Releases: an installer of at most 90 MB can be uploaded with a manifest that
was signed off-host (the API host never holds a rel-* key). Bigger files are
published on the host with server/scripts/publish_release.py; Cloudflare's
100 MB body limit applies through the tunnel either way.
"""

import json

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from ..contract_http import ContractError, enveloped
from ..database import get_db
from ..deps import require_admin
from ..licence import clock
from ..licence.jcs import canonicalize
from ..models import User
from ..releases import service
from ..releases.models import Release
from ..storage import get_store

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[enveloped()])


def _summary(row: Release) -> dict:
    manifest = json.loads(row.manifest)
    return {
        "version": row.version,
        "platform": row.platform,
        "channel": row.channel,
        "kid": row.kid,
        "storage_key": row.storage_key,
        "bytes": manifest["installer"]["bytes"],
        "sha256": manifest["installer"]["sha256"],
        "published_at": clock.rfc3339(row.published_at),
        "withdrawn_at": clock.rfc3339(row.withdrawn_at),
    }


def _json_field(form, name: str) -> dict:
    raw = form.get(name)
    try:
        value = json.loads(raw) if isinstance(raw, str) else None
    except ValueError:
        value = None
    if not isinstance(value, dict):
        raise ContractError(
            "validation_failed",
            422,
            f"{name}: expected a JSON object",
            {"fields": [{"field": name, "in": "body", "message": "expected a JSON object"}]},
        )
    return value


@router.get("/releases")
def list_releases(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(Release).order_by(Release.published_at.desc()))
    return {"releases": [_summary(r) for r in rows]}


@router.post("/releases", status_code=status.HTTP_201_CREATED)
async def upload_release(
    request: Request, _admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Multipart: `manifest` (JSON), `signature` (JSON {alg, kid, value}), `file`."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > service.MAX_UPLOAD_BYTES + 1024 * 1024:
        raise ContractError(
            "too_large", 413, "Installers over 90 MB are published on the host with publish_release.py."
        )
    form = await request.form(max_files=1, max_fields=4)
    manifest = _json_field(form, "manifest")
    signature = _json_field(form, "signature")
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise ContractError(
            "validation_failed", 422, "file: the installer is missing",
            {"fields": [{"field": "file", "in": "body", "message": "required"}]},
        )
    if (upload.size or 0) > service.MAX_UPLOAD_BYTES:
        raise ContractError("too_large", 413, "Installers over 90 MB are published on the host with publish_release.py.")
    errors = service.manifest_errors(manifest)
    if errors:
        raise ContractError("validation_failed", 422, "; ".join(errors), {"errors": errors})
    if not service.signature_ok(manifest, signature):
        raise ContractError(
            "invalid_signature", 422, "The manifest's signature does not verify with a published rel-* key."
        )
    row = service.register(db, get_store(), manifest, signature, upload.file)
    return _summary(row)


class ReleasePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    withdrawn: bool | None = None
    manifest: dict | None = None
    signature: dict | None = None


@router.patch("/releases/{version}")
def edit_release(
    version: str,
    body: ReleasePatch,
    platform: str = "win64",
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Withdraw (or restore) a release, or replace its manifest (new notes):
    a changed manifest needs a new signature, and keeps version, channel,
    platform and installer."""
    row = db.scalar(select(Release).where(Release.version == version, Release.platform == platform))
    if row is None:
        raise ContractError("not_found", 404, f"There is no release {version} for {platform}.")
    if body.manifest is not None:
        old = json.loads(row.manifest)
        new = body.manifest
        errors = service.manifest_errors(new)
        for k in ("version", "channel", "platform", "installer"):
            if new.get(k) != old.get(k):
                errors.append(f"{k} cannot change; publish a new version instead")
        if errors:
            raise ContractError("validation_failed", 422, "; ".join(errors), {"errors": errors})
        if body.signature is None or not service.signature_ok(new, body.signature):
            raise ContractError(
                "invalid_signature", 422, "A changed manifest needs a new signature from a published rel-* key."
            )
        row.manifest = canonicalize(new)
        row.signature = body.signature["value"]
        row.kid = body.signature["kid"]
    if body.withdrawn is not None:
        row.withdrawn_at = clock.now() if body.withdrawn else None
    db.add(row)
    db.commit()
    db.refresh(row)
    return _summary(row)
