"""Object storage behind one interface (PF14 §Design Plumbing; first user PF1).

    store = get_store()
    info = store.put("releases/1.1.0/win64/Truebex-Setup-1.1.0.exe", fh, content_type=…)
    url = store.signed_get_url(info.key, expires_in=900, filename="Truebex-Setup-1.1.0.exe")

Adapters: `local` (files under STORAGE_DIR, URLs served by GET / PUT
/files/{key}?exp=&sig= with HMAC-SHA256; this package) and `s3` (presigned
URLs, PF14). STORAGE_BACKEND picks one. Keys are relative paths of safe
segments (`check_key`); nothing outside the store is reachable through one.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import BinaryIO, Iterator, Protocol

_SEGMENT = re.compile(r"^[A-Za-z0-9_+=@-][A-Za-z0-9._+=@-]*$")
# The local adapter keeps each blob's metadata in a sidecar with this suffix.
META_SUFFIX = ".meta.json"
MAX_KEY = 512


class InvalidKey(ValueError):
    pass


@dataclass(frozen=True)
class BlobInfo:
    key: str
    bytes: int
    sha256: str
    content_type: str
    cache_control: str | None = None


def check_key(key: str) -> str:
    """The key itself when it is a safe relative path, else InvalidKey."""
    if not isinstance(key, str) or not key or len(key) > MAX_KEY:
        raise InvalidKey("empty or too long")
    if key.endswith(META_SUFFIX):
        raise InvalidKey("reserved suffix")
    for part in key.split("/"):
        if part in ("", ".", "..") or not _SEGMENT.match(part):
            raise InvalidKey(f"bad segment {part!r}")
    return key


class Store(Protocol):
    def put(
        self, key: str, data: bytes | BinaryIO, *, content_type: str, cache_control: str | None = None
    ) -> BlobInfo: ...

    def open(self, key: str) -> BinaryIO: ...

    def stat(self, key: str) -> BlobInfo | None: ...

    def delete(self, key: str) -> None: ...

    def list(self, prefix: str) -> Iterator[BlobInfo]: ...

    def signed_get_url(self, key: str, *, expires_in: int = 900, filename: str | None = None) -> str: ...

    def signed_put_url(self, key: str, *, expires_in: int = 900, content_type: str, max_bytes: int) -> str: ...


@lru_cache
def get_store() -> Store:
    from ..config import get_settings

    settings = get_settings()
    if settings.storage_backend == "local":
        from .local import LocalStore

        return LocalStore(settings.storage_dir)
    raise RuntimeError(f"STORAGE_BACKEND={settings.storage_backend!r} is not available (PF14 adds s3)")
