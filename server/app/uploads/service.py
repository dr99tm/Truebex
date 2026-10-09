"""The resumable, content-addressed upload of share-bundle §5.1-5.3.

    session = open_session(db, caller, purpose="share", files=[...])   # 5.1
    put_part(db, caller, upload_id, sha256, n, body, part_sha256)        # 5.2
    status(db, caller, upload_id)                                        # 5.3

Files are stored once per account (`blobs/{account_id}/{sha256}`); a file the
account already holds answers `present` and needs no part. Parts are 8 MiB
(Cloudflare's 100 MB request limit), each hashed; a session lives 24 h.
Shares (PF5), snapshots (PF4) and jobs (PF6) take a ref on the blobs they
keep (`add_refs` / `drop_refs`); a blob nobody took within 7 days is dropped
by `uploads.expire`.
"""

import hashlib
import math
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock
from ..storage import get_store
from . import assemble
from .credentials import UploadCaller
from .models import Blob, UploadSession

PART_BYTES = 8 * 1024 * 1024
MAX_FILES = 500
MAX_FILE_BYTES = 512 * 1024 * 1024
SESSION_LIFETIME = timedelta(hours=24)
ORPHAN_AFTER = timedelta(days=7)
PURPOSES = ("share", "snapshot", "job-input", "job-output")
# Content types a share bundle carries (§6.1); other purposes take any.
SHARE_TYPES = ("image/jpeg", "image/png", "application/pdf")
_OTHER_TOTAL = 8 * 1024 * 1024 * 1024

_SHA = re.compile(r"^[0-9a-f]{64}$")
_CONTENT_TYPE = re.compile(r"^[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*$")


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA.match(value))


def parts_of(size: int) -> int:
    return max(1, math.ceil(size / PART_BYTES))


def purpose_max_total(purpose: str) -> int:
    # Per-tier bundle bytes are checked by POST /shares; this is the ceiling.
    return get_settings().share_max_bytes if purpose == "share" else _OTHER_TOTAL


def _allowed(caller: UploadCaller, purpose: str) -> bool:
    if caller.kind == "worker":
        return purpose == "job-output"
    return purpose != "job-output"


# --- blobs --------------------------------------------------------------------


def find_blob(db: Session, account_id: int, sha256: str) -> Blob | None:
    return db.scalar(select(Blob).where(Blob.account_id == account_id, Blob.sha256 == sha256))


def blobs_by_sha(db: Session, account_id: int, shas: list[str]) -> dict[str, Blob]:
    if not shas:
        return {}
    rows = db.scalars(select(Blob).where(Blob.account_id == account_id, Blob.sha256.in_(set(shas))))
    return {b.sha256: b for b in rows}


def missing_files(db: Session, account_id: int, shas: list[str]) -> list[str]:
    have = blobs_by_sha(db, account_id, shas)
    return [s for s in dict.fromkeys(shas) if s not in have]


def add_refs(db: Session, account_id: int, shas: list[str]) -> None:
    for blob in blobs_by_sha(db, account_id, shas).values():
        blob.refs += 1


def drop_refs(db: Session, account_id: int, shas: list[str]) -> int:
    """Release one ref per file; blobs left with none are deleted. Returns how many."""
    store = get_store()
    dropped = 0
    for blob in blobs_by_sha(db, account_id, shas).values():
        blob.refs = max(0, blob.refs - 1)
        if blob.refs == 0:
            store.delete(blob.storage_key)
            db.delete(blob)
            dropped += 1
    return dropped


# --- sessions -----------------------------------------------------------------


def _validate_files(files: list[dict], purpose: str) -> list[dict]:
    if not isinstance(files, list) or not files:
        raise ContractError("validation_failed", 422, "List at least one file.", {"fields": [{"field": "files"}]})
    if len(files) > MAX_FILES:
        raise ContractError(
            "validation_failed", 422, f"An upload holds at most {MAX_FILES} files.", {"limit": MAX_FILES}
        )
    seen: dict[str, dict] = {}
    for i, f in enumerate(files):
        sha = str(f.get("sha256", "")).lower()
        size = f.get("bytes")
        ctype = str(f.get("content_type", "")).lower().strip()
        where = {"fields": [{"field": f"files.{i}"}]}
        if not is_sha256(sha):
            raise ContractError("validation_failed", 422, f"files[{i}].sha256 must be 64 hex characters.", where)
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise ContractError("validation_failed", 422, f"files[{i}].bytes must be a positive whole number.", where)
        if size > MAX_FILE_BYTES:
            raise ContractError(
                "too_large", 413, "A file may be at most 512 MiB.", {"limit": MAX_FILE_BYTES, "sha256": sha}
            )
        if not _CONTENT_TYPE.match(ctype) or (purpose == "share" and ctype not in SHARE_TYPES):
            raise ContractError(
                "validation_failed", 422, f"files[{i}].content_type {ctype or '(empty)'} is not accepted here.", where
            )
        if sha in seen:
            if seen[sha]["bytes"] != size:
                raise ContractError("validation_failed", 422, f"files[{i}] repeats a file with another size.", where)
            continue
        seen[sha] = {"sha256": sha, "bytes": size, "content_type": ctype}
    total = sum(f["bytes"] for f in seen.values())
    limit = purpose_max_total(purpose)
    if total > limit:
        raise ContractError(
            "too_large", 413, f"This upload is {total} bytes; at most {limit} are allowed.", {"limit": limit, "used": total}
        )
    return list(seen.values())


def open_session(db: Session, caller: UploadCaller, *, purpose: str, files: list[dict]) -> UploadSession:
    if purpose not in PURPOSES:
        raise ContractError(
            "validation_failed", 422, f"purpose must be one of {', '.join(PURPOSES)}.", {"fields": [{"field": "purpose"}]}
        )
    if not _allowed(caller, purpose):
        raise ContractError(
            "forbidden", 403, f"This credential cannot open {purpose} uploads.", {"purpose": purpose, "credential": caller.kind}
        )
    declared = _validate_files(files, purpose)
    now = clock.now()
    session = UploadSession(
        upload_id=secrets.token_hex(16),
        account_id=caller.account_id,
        credential_kind=caller.kind,
        credential_id=caller.credential_id,
        purpose=purpose,
        files=declared,
        created_at=now,
        expires_at=now + SESSION_LIFETIME,
    )
    db.add(session)
    db.commit()
    return session


def get_session(db: Session, caller: UploadCaller, upload_id: str, *, now: datetime | None = None) -> UploadSession:
    """The caller's own session (404 otherwise); 410 once it is 24 h old."""
    session = db.get(UploadSession, upload_id) if re.fullmatch(r"[0-9a-f]{32}", upload_id or "") else None
    if (
        session is None
        or session.account_id != caller.account_id
        or session.credential_kind != caller.kind
        or (caller.kind == "worker" and session.credential_id != caller.credential_id)
    ):
        raise ContractError("not_found", 404, "No such upload.")
    if clock.aware(session.expires_at) <= (now or clock.now()):
        raise ContractError(
            "upload_expired", 410, "This upload ended after 24 hours. Start a new one; finished files are kept.",
            {"expires_at": clock.rfc3339(session.expires_at)},
        )
    return session


def _received(upload_id: str, sha256: str, parts: int) -> list[int]:
    store = get_store()
    return [n for n in range(parts) if store.stat(assemble.part_key(upload_id, sha256, n)) is not None]


def file_states(db: Session, session: UploadSession) -> list[dict]:
    have = blobs_by_sha(db, session.account_id, [f["sha256"] for f in session.files])
    out = []
    for f in session.files:
        parts = parts_of(f["bytes"])
        if f["sha256"] in have:
            state, received = "complete", list(range(parts))
        else:
            received = _received(session.upload_id, f["sha256"], parts)
            state = "partial" if received else "missing"
        out.append({"sha256": f["sha256"], "state": state, "parts": parts, "received": received})
    return out


def opened_json(db: Session, session: UploadSession) -> dict:
    """5.1's response: `present` for files the account already holds."""
    files = []
    for f in file_states(db, session):
        files.append({**f, "state": "present" if f["state"] == "complete" else f["state"]})
    return {
        "upload_id": session.upload_id,
        "purpose": session.purpose,
        "part_bytes": PART_BYTES,
        "expires_at": clock.rfc3339(session.expires_at),
        "files": files,
    }


def status_json(db: Session, session: UploadSession) -> dict:
    """5.3's response."""
    return {
        "upload_id": session.upload_id,
        "purpose": session.purpose,
        "part_bytes": PART_BYTES,
        "expires_at": clock.rfc3339(session.expires_at),
        "files": file_states(db, session),
    }


def put_part(
    db: Session, caller: UploadCaller, upload_id: str, sha256: str, n: int, body: bytes, part_sha256: str | None
) -> None:
    session = get_session(db, caller, upload_id)
    sha256 = sha256.lower()
    entry = next((f for f in session.files if f["sha256"] == sha256), None)
    if entry is None:
        raise ContractError("not_found", 404, "This file is not part of the upload.")
    parts = parts_of(entry["bytes"])
    if n < 0 or n >= parts:
        raise ContractError(
            "part_out_of_range", 422, f"This file has parts 0 to {parts - 1}.", {"parts": parts, "n": n}
        )
    if find_blob(db, session.account_id, sha256) is not None:
        return  # already complete: a repeated part is harmless
    want = PART_BYTES if n < parts - 1 else entry["bytes"] - (parts - 1) * PART_BYTES
    if len(body) != want:
        raise ContractError(
            "validation_failed", 422, f"Part {n} must be {want} bytes; {len(body)} arrived.",
            {"expected_bytes": want, "received_bytes": len(body)},
        )
    claimed = (part_sha256 or "").strip().lower()
    if not is_sha256(claimed):
        raise ContractError(
            "validation_failed", 422, "Send the part's SHA-256 as X-Part-Sha256.", {"fields": [{"field": "X-Part-Sha256"}]}
        )
    if hashlib.sha256(body).hexdigest() != claimed:
        raise ContractError("part_hash_mismatch", 422, f"Part {n} did not arrive intact. Send it again.", {"n": n})
    store = get_store()
    store.put(assemble.part_key(upload_id, sha256, n), body, content_type="application/octet-stream")
    if len(_received(upload_id, sha256, parts)) < parts:
        return
    ok = assemble.assemble(
        db, store, account_id=session.account_id, upload_id=upload_id, sha256=sha256,
        size=entry["bytes"], content_type=entry["content_type"], parts=parts,
    )
    if not ok:
        raise ContractError(
            "file_hash_mismatch", 422, "The assembled file does not match its SHA-256. Send all its parts again.",
            {"sha256": sha256},
        )


# --- the uploads.expire job -------------------------------------------------------


def expire(db: Session, now: datetime) -> int:
    """Drop sessions past 24 h (with their parts) and blobs nobody took in 7 days."""
    store = get_store()
    done = 0
    for session in db.scalars(select(UploadSession).where(UploadSession.expires_at <= now)).all():
        for f in session.files:
            keys = [assemble.part_key(session.upload_id, f["sha256"], n) for n in range(parts_of(f["bytes"]))]
            for key in keys:
                store.delete(key)
            assemble.prune_dirs(store, keys)
        db.delete(session)
        done += 1
    orphans = db.scalars(select(Blob).where(Blob.refs <= 0, Blob.created_at <= now - ORPHAN_AFTER)).all()
    for blob in orphans:
        store.delete(blob.storage_key)
    if orphans:
        db.execute(delete(Blob).where(Blob.id.in_([b.id for b in orphans])))
    db.commit()
    return done + len(orphans)
