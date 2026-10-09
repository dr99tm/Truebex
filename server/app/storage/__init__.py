"""Blob storage behind one interface (PF14 §Design Plumbing; first user PF1).

    store = get_store()
    info = store.put("releases/1.1.0/win64/Truebex-Setup-1.1.0.exe", fh,
                     content_type="application/octet-stream")
    url = store.signed_get_url(info.key, expires_in=900, filename="Truebex-Setup-1.1.0.exe")

Adapters: `local` (files under STORAGE_DIR, URLs served by GET / PUT
/files/{key}?exp=&sig= with HMAC-SHA256, this module) and `s3` (presigned
URLs and a CDN for public prefixes, PF14). Swapping is one setting.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Protocol

_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,199}$")


class InvalidKey(ValueError):
    pass


def check_key(key: str) -> str:
    """Keys are relative, '/'-separated, no '..', no empty segments."""
    if not isinstance(key, str) or not key or len(key) > 512 or key.endswith(".meta.json"):
        raise InvalidKey("invalid storage key")
    parts = key.split("/")
    if any(p in ("", ".", "..") or not _SEGMENT.match(p) for p in parts):
        raise InvalidKey("invalid storage key")
    return key


@dataclass(frozen=True)
class BlobInfo:
    key: str
    bytes: int
    content_type: str
    sha256: str
    cache_control: str | None = None
    modified_at: datetime | None = None


class Store(Protocol):
    def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        *,
        content_type: str,
        cache_control: str | None = None,
    ) -> BlobInfo: ...

    def open(self, key: str) -> BinaryIO: ...

    def stat(self, key: str) -> BlobInfo | None: ...

    def delete(self, key: str) -> None: ...

    def list(self, prefix: str = "") -> list[BlobInfo]: ...

    def signed_get_url(
        self, key: str, *, expires_in: int = 900, filename: str | None = None
    ) -> str: ...

    def signed_put_url(
        self, key: str, *, expires_in: int = 900, content_type: str, max_bytes: int
    ) -> str: ...


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        from ..config import get_settings

        s = get_settings()
        if s.storage_backend != "local":
            raise RuntimeError(
                f"STORAGE_BACKEND={s.storage_backend!r} is not available yet (PF14 adds s3)"
            )
        from .local import LocalStore

        _store = LocalStore.from_settings(s)
    return _store


def reset_store() -> None:
    """Forget the cached adapter (tests change STORAGE_DIR)."""
    global _store
    _store = None
