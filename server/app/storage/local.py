"""The `local` storage adapter: files under STORAGE_DIR, one JSON sidecar per
blob for its size, SHA-256 and content type, and HMAC-SHA256 signed URLs that
`routers/files.py` serves (GET with Range, PUT up to `max` bytes).

A URL signs the method, the key, its expiry and what else it fixes (the
download file name; the upload's content type and size cap), so altering any
of them answers 403. The key is STORAGE_URL_SECRET, or one derived from
SECRET_KEY.
"""

import base64
import hashlib
import hmac
import io
import json
import os
import time
from pathlib import Path
from typing import BinaryIO, Iterator
from urllib.parse import quote, urlencode

from . import META_SUFFIX, BlobInfo, check_key

# Unix seconds; patched by tests to move time.
clock = time.time

_CHUNK = 1024 * 1024


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class LocalStore:
    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root).resolve()

    # --- paths ------------------------------------------------------------------

    def file_path(self, key: str) -> Path:
        path = (self.root / check_key(key)).resolve()
        if self.root not in path.parents:
            raise ValueError("key escapes the store")
        return path

    def _meta_path(self, key: str) -> Path:
        path = self.file_path(key)
        return path.with_name(path.name + META_SUFFIX)

    # --- blobs ------------------------------------------------------------------

    def put(
        self, key: str, data: bytes | BinaryIO, *, content_type: str, cache_control: str | None = None
    ) -> BlobInfo:
        path = self.file_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        source = io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data
        digest = hashlib.sha256()
        size = 0
        tmp = path.with_name(path.name + ".part")
        with open(tmp, "wb") as out:
            while chunk := source.read(_CHUNK):
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
        os.replace(tmp, path)
        info = BlobInfo(key, size, digest.hexdigest(), content_type, cache_control)
        self._meta_path(key).write_text(
            json.dumps({"bytes": size, "sha256": info.sha256, "content_type": content_type,
                        "cache_control": cache_control}),
            encoding="utf-8",
        )
        return info

    def open(self, key: str) -> BinaryIO:
        return open(self.file_path(key), "rb")

    def stat(self, key: str) -> BlobInfo | None:
        path = self.file_path(key)
        meta = self._meta_path(key)
        if not path.is_file() or not meta.is_file():
            return None
        data = json.loads(meta.read_text(encoding="utf-8"))
        return BlobInfo(key, int(data["bytes"]), data["sha256"], data["content_type"], data.get("cache_control"))

    def delete(self, key: str) -> None:
        for path in (self.file_path(key), self._meta_path(key)):
            path.unlink(missing_ok=True)

    def list(self, prefix: str) -> Iterator[BlobInfo]:
        if not self.root.is_dir():
            return iter(())
        found = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.name.endswith((META_SUFFIX, ".part")):
                continue
            key = path.relative_to(self.root).as_posix()
            if key.startswith(prefix):
                info = self.stat(key)
                if info is not None:
                    found.append(info)
        return iter(sorted(found, key=lambda b: b.key))

    # --- signed URLs --------------------------------------------------------------

    @staticmethod
    def _secret() -> bytes:
        from ..config import get_settings

        s = get_settings()
        if s.storage_url_secret:
            return s.storage_url_secret.encode("utf-8")
        return hashlib.sha256(b"truebex-storage-urls/1\n" + s.secret_key.encode("utf-8")).digest()

    def _sign(self, method: str, key: str, exp: str, extra: str) -> str:
        msg = f"{method}\n{key}\n{exp}\n{extra}".encode("utf-8")
        return _b64(hmac.new(self._secret(), msg, hashlib.sha256).digest())

    def verify(self, method: str, key: str, exp: str | None, sig: str | None, extra: str = "") -> bool:
        if not exp or not sig or not exp.isdigit() or int(exp) < clock():
            return False
        return hmac.compare_digest(self._sign(method, key, exp, extra), sig)

    @staticmethod
    def _base(key: str) -> str:
        from ..config import get_settings

        return f"{get_settings().api_url.rstrip('/')}/files/{quote(key, safe='/')}"

    def signed_get_url(self, key: str, *, expires_in: int = 900, filename: str | None = None) -> str:
        check_key(key)
        exp = str(int(clock()) + int(expires_in))
        query = {"exp": exp, "sig": self._sign("GET", key, exp, filename or "")}
        if filename:
            query["fn"] = filename
        return f"{self._base(key)}?{urlencode(query)}"

    def signed_put_url(self, key: str, *, expires_in: int = 900, content_type: str, max_bytes: int) -> str:
        check_key(key)
        exp = str(int(clock()) + int(expires_in))
        sig = self._sign("PUT", key, exp, f"{content_type}\n{int(max_bytes)}")
        return f"{self._base(key)}?{urlencode({'exp': exp, 'sig': sig, 'ct': content_type, 'max': int(max_bytes)})}"
