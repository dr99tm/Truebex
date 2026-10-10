"""Turning a file's parts into one verified blob (share-bundle §5.2).

When the last part of a file arrives, the parts are read in order and hashed;
a size or SHA-256 mismatch drops the parts (422 `file_hash_mismatch`), a
match stores the file once at `blobs/{account_id}/{sha256}` and records it.
The `s3` adapter (PF14) maps the same parts onto an S3 multipart upload.
"""

import hashlib
import threading
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..licence import clock
from ..storage import Store
from .models import Blob

_CHUNK = 1024 * 1024

# One assembly per (account, file) at a time in this process; a second part
# finishing the same file waits, then finds the blob already made.
_locks_guard = threading.Lock()
_locks: dict[tuple[int, str], threading.Lock] = {}


def file_lock(account_id: int, sha256: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault((account_id, sha256), threading.Lock())


def part_key(upload_id: str, sha256: str, n: int) -> str:
    return f"uploads/parts/{upload_id}/{sha256}/{n}"


def blob_key(account_id: int, sha256: str) -> str:
    return f"blobs/{account_id}/{sha256}"


class PartsReader:
    """A read-only stream over a file's parts, in order."""

    def __init__(self, store: Store, keys: list[str]) -> None:
        self._store = store
        self._keys = list(keys)
        self._fh: BinaryIO | None = None

    def read(self, size: int = -1) -> bytes:
        out = bytearray()
        while size < 0 or len(out) < size:
            if self._fh is None:
                if not self._keys:
                    break
                self._fh = self._store.open(self._keys.pop(0))
            want = _CHUNK if size < 0 else size - len(out)
            chunk = self._fh.read(want)
            if not chunk:
                self._fh.close()
                self._fh = None
                continue
            out += chunk
        return bytes(out)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def digest_of(store: Store, keys: list[str]) -> tuple[str, int]:
    reader = PartsReader(store, keys)
    h = hashlib.sha256()
    size = 0
    try:
        while chunk := reader.read(_CHUNK):
            h.update(chunk)
            size += len(chunk)
    finally:
        reader.close()
    return h.hexdigest(), size


def assemble(
    db: Session, store: Store, *, account_id: int, upload_id: str, sha256: str, size: int, content_type: str, parts: int
) -> bool:
    """Assemble and record the blob. False (parts dropped) on a mismatch."""
    keys = [part_key(upload_id, sha256, n) for n in range(parts)]
    with file_lock(account_id, sha256):
        if db.scalar(select(Blob).where(Blob.account_id == account_id, Blob.sha256 == sha256)) is not None:
            _drop(store, keys)
            return True
        got_sha, got_size = digest_of(store, keys)
        if got_sha != sha256 or got_size != size:
            _drop(store, keys)
            return False
        key = blob_key(account_id, sha256)
        reader = PartsReader(store, keys)
        try:
            info = store.put(key, reader, content_type=content_type)
        finally:
            reader.close()
        if info.sha256 != sha256:  # the parts changed under us
            store.delete(key)
            _drop(store, keys)
            return False
        db.add(
            Blob(
                account_id=account_id, sha256=sha256, bytes=size, content_type=content_type,
                storage_key=key, refs=0, created_at=clock.now(),
            )
        )
        try:
            db.commit()
        except IntegrityError:  # another process recorded it first
            db.rollback()
        _drop(store, keys)
        return True


def _drop(store: Store, keys: list[str]) -> None:
    for key in keys:
        store.delete(key)
    prune_dirs(store, keys)


def prune_dirs(store: Store, keys: list[str]) -> None:
    """Local adapter: remove the part folders left empty (best effort)."""
    file_path = getattr(store, "file_path", None)
    if file_path is None or not keys:
        return
    try:
        folder = file_path(keys[0]).parent
        for _ in range(2):  # {sha256}/ then {upload_id}/
            folder.rmdir()
            folder = folder.parent
    except OSError:
        pass
