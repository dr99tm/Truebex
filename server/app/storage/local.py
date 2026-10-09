"""The `local` storage adapter: files on this machine's disk.

Each blob is a file under STORAGE_DIR with a `<file>.meta.json` beside it
(content type, size, SHA-256). Signed URLs point at this API's /files route
(server/app/routers/files.py) and carry `exp` (Unix seconds) and `sig`, an
HMAC-SHA256 over the method, key, expiry and the URL's other parameters.
"""

import base64
import hashlib
import hmac
import json
import os
import tempfile
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote, urlencode

from . import BlobInfo, check_key

# Patched by tests to move time.
clock: Callable[[], float] = time.time

_CHUNK = 1024 * 1024


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class LocalStore:
    def __init__(self, root: str | Path, *, base_url: str, secret: bytes) -> None:
        self.root = Path(root).resolve()
        self.base_url = base_url.rstrip("/")
        self._secret = secret

    @classmethod
    def from_settings(cls, s) -> "LocalStore":
        secret = (s.storage_url_secret or "").encode() or hmac.new(
            s.secret_key.encode(), b"truebex-storage-urls", hashlib.sha256
        ).digest()
        return cls(s.storage_dir, base_url=s.api_url, secret=secret)

    # --- paths ---------------------------------------------------------------

    def _path(self, key: str) -> Path:
        path = (self.root / check_key(key)).resolve()
        if self.root not in path.parents:
            raise ValueError("invalid storage key")
        return path

    @staticmethod
    def _meta_path(path: Path) -> Path:
        return path.with_name(path.name + ".meta.json")

    # --- blobs ---------------------------------------------------------------

    def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        *,
        content_type: str,
        cache_control: str | None = None,
    ) -> BlobInfo:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as out:
                if isinstance(data, (bytes, bytearray, memoryview)):
                    chunk = bytes(data)
                    out.write(chunk)
                    digest.update(chunk)
                    size = len(chunk)
                else:
                    while chunk := data.read(_CHUNK):
                        out.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        meta = {
            "content_type": content_type,
            "cache_control": cache_control,
            "bytes": size,
            "sha256": digest.hexdigest(),
        }
        self._meta_path(path).write_text(json.dumps(meta), encoding="utf-8")
        return self._info(key, path, meta)

    def _info(self, key: str, path: Path, meta: dict) -> BlobInfo:
        return BlobInfo(
            key=key,
            bytes=int(meta["bytes"]),
            content_type=meta["content_type"],
            sha256=meta["sha256"],
            cache_control=meta.get("cache_control"),
            modified_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
        )

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def file_path(self, key: str) -> Path:
        """The file on disk (the /files route streams it)."""
        return self._path(key)

    def stat(self, key: str) -> BlobInfo | None:
        path = self._path(key)
        meta_path = self._meta_path(path)
        if not path.is_file() or not meta_path.is_file():
            return None
        return self._info(key, path, json.loads(meta_path.read_text(encoding="utf-8")))

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)
        self._meta_path(path).unlink(missing_ok=True)

    def list(self, prefix: str = "") -> list[BlobInfo]:
        if not self.root.is_dir():
            return []
        out = []
        for meta_path in sorted(self.root.rglob("*.meta.json")):
            path = meta_path.with_name(meta_path.name[: -len(".meta.json")])
            key = path.relative_to(self.root).as_posix()
            if key.startswith(prefix) and path.is_file():
                out.append(self._info(key, path, json.loads(meta_path.read_text(encoding="utf-8"))))
        return out

    # --- signed URLs -----------------------------------------------------------

    def _sign(self, method: str, key: str, exp: int, extra: str) -> str:
        msg = f"{method}\n{key}\n{exp}\n{extra}".encode()
        return _b64(hmac.new(self._secret, msg, hashlib.sha256).digest())

    def _url(self, key: str, params: dict[str, str]) -> str:
        return f"{self.base_url}/files/{quote(key)}?{urlencode(params)}"

    def signed_get_url(self, key: str, *, expires_in: int = 900, filename: str | None = None) -> str:
        check_key(key)
        exp = int(clock()) + int(expires_in)
        params = {"exp": str(exp)}
        if filename:
            params["fn"] = filename
        params["sig"] = self._sign("GET", key, exp, filename or "")
        return self._url(key, params)

    def signed_put_url(
        self, key: str, *, expires_in: int = 900, content_type: str, max_bytes: int
    ) -> str:
        check_key(key)
        exp = int(clock()) + int(expires_in)
        extra = f"{content_type}\n{int(max_bytes)}"
        params = {
            "exp": str(exp),
            "ct": content_type,
            "max": str(int(max_bytes)),
            "sig": self._sign("PUT", key, exp, extra),
        }
        return self._url(key, params)

    def verify(self, method: str, key: str, exp: str | None, sig: str | None, extra: str = "") -> bool:
        """True when the URL's signature matches and it has not expired."""
        if not exp or not sig or not exp.isdigit():
            return False
        if int(exp) <= clock():
            return False
        return hmac.compare_digest(self._sign(method, key, int(exp), extra), sig)
