"""Snapshots (contract 5.8, 5.9, §6.4).

The app uploads `<name>.tbxp` (and `<name>.tbxpack` when the project embeds
assets) through the upload protocol (share-bundle §5, purpose `snapshot`) and
registers them at `at_seq`. Registering copies each file, content-addressed,
to `projects/{pid}/blobs/{sha256}` (a file the project already holds is not
copied or counted twice) and adds its bytes to the project. Download URLs are
signed for 15 minutes. `prune` keeps the newest five and every version's.
"""

import re
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from ..storage import get_store
from ..uploads import service as uploads
from ..uploads.credentials import UploadCaller
from . import quotas
from .models import Project, ProjectSnapshot, ProjectVersion
from .service import is_hex32, not_found, touch

URL_TTL_S = 900
KEEP_NEWEST = 5
_SHA = re.compile(r"^[0-9a-f]{64}$")
_FILENAME_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def blob_key(project_id: str, sha256: str) -> str:
    return f"projects/{project_id}/blobs/{sha256}"


def _filename(project: Project, ext: str) -> str:
    base = _FILENAME_UNSAFE.sub("", project.name).strip(" .") or "project"
    return f"{base[:80]}.{ext}"


def _file_json(project: Project, sha: str | None, size: int | None, ext: str) -> dict | None:
    if sha is None:
        return None
    expires = clock.now() + timedelta(seconds=URL_TTL_S)
    url = get_store().signed_get_url(blob_key(project.project_id, sha), expires_in=URL_TTL_S, filename=_filename(project, ext))
    return {"sha256": sha, "bytes": size, "url": url, "url_expires_at": clock.rfc3339(expires)}


def snapshot_json(project: Project, snap: ProjectSnapshot) -> dict:
    return {
        "snapshot_id": snap.snapshot_id,
        "at_seq": snap.at_seq,
        "doc_version": snap.doc_version,
        "created_by": snap.created_by,
        "created_at": clock.rfc3339(snap.created_at),
        "files": {
            "tbxp": _file_json(project, snap.tbxp_sha256, snap.tbxp_bytes, "tbxp"),
            "tbxpack": _file_json(project, snap.tbxpack_sha256, snap.tbxpack_bytes, "tbxpack"),
        },
    }


def _bad(field: str, message: str) -> ContractError:
    return ContractError(
        "validation_failed", 422, f"{field}: {message}", {"fields": [{"field": field, "in": "body", "message": message}]}
    )


def register(
    db: Session,
    project: Project,
    *,
    user_id: int,
    upload_caller: UploadCaller,
    at_seq: int,
    doc_version: int,
    upload_id: str,
    files: dict,
    bytes_cap: int | None,
) -> dict:
    tbxp = str(files.get("tbxp") or "").lower()
    tbxpack = files.get("tbxpack")
    tbxpack = str(tbxpack).lower() if tbxpack else None
    if not _SHA.match(tbxp):
        raise _bad("files.tbxp", "the .tbxp file's SHA-256 (64 hex)")
    if tbxpack is not None and not _SHA.match(tbxpack):
        raise _bad("files.tbxpack", "the .tbxpack file's SHA-256 (64 hex) or null")
    if doc_version < 1:
        raise _bad("doc_version", "1 or more")
    if at_seq < 0:
        raise _bad("at_seq", "0 or more")
    if at_seq > project.head_seq:
        raise ContractError(
            "seq_ahead",
            409,
            f"The project's log ends at {project.head_seq}; a snapshot cannot be ahead of it.",
            {"head_seq": project.head_seq, "at_seq": at_seq},
        )
    session = uploads.get_session(db, upload_caller, upload_id)
    if session.purpose != "snapshot":
        raise _bad("upload_id", "an upload opened with purpose snapshot")
    named = [s for s in (tbxp, tbxpack) if s]
    listed = {f["sha256"]: f for f in session.files}
    have = uploads.blobs_by_sha(db, session.account_id, named)
    missing = [s for s in named if s not in listed or s not in have]
    if missing:
        raise ContractError(
            "upload_incomplete",
            422,
            f"The upload is still missing {len(missing)} of the snapshot's files.",
            {"missing": missing},
        )
    store = get_store()
    new_bytes = sum(have[s].bytes for s in set(named) if store.stat(blob_key(project.project_id, s)) is None)
    if new_bytes and bytes_cap is not None:
        used = quotas.bytes_used(db, project.owner_user_id)
        if used + new_bytes > bytes_cap:
            raise quotas.exceeded("cloud_bytes", bytes_cap, used)
    for sha in set(named):
        key = blob_key(project.project_id, sha)
        if store.stat(key) is None:
            with store.open(have[sha].storage_key) as fh:
                store.put(key, fh, content_type="application/octet-stream")
    snap = ProjectSnapshot(
        snapshot_id=secrets.token_hex(16),
        project_id=project.project_id,
        at_seq=at_seq,
        doc_version=doc_version,
        tbxp_sha256=tbxp,
        tbxp_bytes=have[tbxp].bytes,
        tbxpack_sha256=tbxpack,
        tbxpack_bytes=have[tbxpack].bytes if tbxpack else None,
        created_by=user_id,
        created_at=clock.now(),
    )
    db.add(snap)
    project.bytes += new_bytes
    if doc_version > project.doc_version:
        project.doc_version = doc_version
    touch(project)
    db.commit()
    return snapshot_json(project, snap)


def latest(db: Session, project: Project) -> dict:
    snap = db.scalar(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project.project_id)
        .order_by(ProjectSnapshot.at_seq.desc(), ProjectSnapshot.created_at.desc())
        .limit(1)
    )
    if snap is None:
        raise ContractError("not_found", 404, "This project has no snapshot yet. Open it from sequence 0.")
    return snapshot_json(project, snap)


def get(db: Session, project: Project, snapshot_id: str) -> ProjectSnapshot:
    snap = db.get(ProjectSnapshot, snapshot_id) if is_hex32(snapshot_id) else None
    if snap is None or snap.project_id != project.project_id:
        raise not_found("snapshot")
    return snap


# --- projects.snapshots.prune ------------------------------------------------------


def prune_project(db: Session, project: Project) -> int:
    """Keep the newest five and every version's snapshot; drop the rest and
    the blobs nothing names any more. Returns how many snapshots went."""
    snaps = db.scalars(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project.project_id)
        .order_by(ProjectSnapshot.at_seq.desc(), ProjectSnapshot.created_at.desc())
    ).all()
    pinned = set(db.scalars(select(ProjectVersion.snapshot_id).where(ProjectVersion.project_id == project.project_id)))
    keep = [s for i, s in enumerate(snaps) if i < KEEP_NEWEST or s.snapshot_id in pinned]
    drop = [s for s in snaps if s not in keep]
    if not drop:
        return 0
    kept_shas = {s.tbxp_sha256 for s in keep} | {s.tbxpack_sha256 for s in keep if s.tbxpack_sha256}
    store = get_store()
    freed = 0
    for sha in {s.tbxp_sha256 for s in drop} | {s.tbxpack_sha256 for s in drop if s.tbxpack_sha256}:
        if sha in kept_shas:
            continue
        info = store.stat(blob_key(project.project_id, sha))
        if info is not None:
            freed += info.bytes
            store.delete(blob_key(project.project_id, sha))
    for snap in drop:
        db.delete(snap)
    project.bytes = max(0, project.bytes - freed)
    db.commit()
    return len(drop)


def prune_all(db: Session) -> int:
    ids = db.scalars(
        select(ProjectSnapshot.project_id)
        .join(Project, Project.project_id == ProjectSnapshot.project_id)
        .where(Project.deleted_at.is_(None))
        .group_by(ProjectSnapshot.project_id)
    ).all()
    total = 0
    for pid in ids:
        project = db.get(Project, pid)
        if project is not None:
            total += prune_project(db, project)
    return total
