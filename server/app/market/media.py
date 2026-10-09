"""Product images and geometry: fetched from a feed's URLs, stored by SHA-256.

* Images are re-encoded to JPEG at import (strips metadata and any active
  content), at most 2048 px, and a 512 px thumbnail is made beside them:
  `market/images/<sha>.jpg`, `market/thumbs/<sha>.jpg` (<sha> = the stored
  full-size JPEG's SHA-256). They are public and immutable, served by
  `GET /market/media/{images|thumbs}/<sha>.jpg`.
* Geometry is stored as sent: `market/geometry/<sha>.<format>`, served by a
  signed URL (1 h) with `Content-Disposition: attachment`.
* Remote fetches (contract §6.4 `geometry_url`, `image_urls`) go through a
  `Fetcher`: https only, private, loopback and link-local addresses refused
  after DNS resolution, size and time capped (the request-forgery guard).
"""

import hashlib
import io
import ipaddress
import socket
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from ..config import get_settings
from ..storage import Store

GEOMETRY_FORMATS = ("tbxa", "glb", "gltf", "obj", "fbx")
GEOMETRY_TYPES = {
    "tbxa": "application/json",
    "glb": "model/gltf-binary",
    "gltf": "model/gltf+json",
    "obj": "text/plain",
    "fbx": "application/octet-stream",
}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_GEOMETRY_BYTES = 100 * 1024 * 1024
MIN_IMAGE_PX = 512
MAX_IMAGE_PX = 2048
THUMB_PX = 512
# Decompression bombs: refuse anything bigger than 50 megapixels.
MAX_PIXELS = 50_000_000


class MediaError(Exception):
    """`code` is a §6.4 row error code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code


def geometry_format(url: str) -> str | None:
    path = urlsplit(url).path.lower()
    ext = path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
    return ext if ext in GEOMETRY_FORMATS else None


def is_https_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme == "https" and bool(parts.hostname) and len(url) <= 1000


# --- Fetchers ------------------------------------------------------------------------


class Fetcher(Protocol):
    def get(self, url: str, max_bytes: int) -> bytes: ...


def _public_address(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return bool(infos)


class HttpFetcher:
    """Fetches https URLs from the internet only (never this host's network)."""

    def __init__(self, timeout: float = 20.0, max_redirects: int = 3, resolver: Callable[[str], bool] = _public_address):
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.resolver = resolver

    def get(self, url: str, max_bytes: int) -> bytes:
        import httpx

        for _ in range(self.max_redirects + 1):
            if not is_https_url(url):
                raise MediaError("bad_url", "only https URLs are fetched")
            if not self.resolver(urlsplit(url).hostname or ""):
                raise MediaError("bad_url", "the host is not a public internet address")
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                    with client.stream("GET", url, headers={"User-Agent": "Truebex-Marketplace/1"}) as res:
                        if res.status_code in (301, 302, 303, 307, 308) and res.headers.get("location"):
                            url = urljoin(url, res.headers["location"])
                            continue
                        if res.status_code != 200:
                            raise MediaError("fetch_failed", f"HTTP {res.status_code}")
                        body = bytearray()
                        for chunk in res.iter_bytes():
                            body.extend(chunk)
                            if len(body) > max_bytes:
                                raise MediaError("too_large", f"over {max_bytes} bytes")
                        return bytes(body)
            except httpx.HTTPError as exc:
                raise MediaError("fetch_failed", str(exc)[:200]) from exc
        raise MediaError("fetch_failed", "too many redirects")


class MapFetcher:
    """URL → bytes or a local file (the seed script and the tests)."""

    def __init__(self, files: Mapping[str, bytes | str | Path]) -> None:
        self.files = dict(files)

    def get(self, url: str, max_bytes: int) -> bytes:
        if url not in self.files:
            raise MediaError("fetch_failed", "404")
        value = self.files[url]
        data = value if isinstance(value, bytes) else Path(value).read_bytes()
        if len(data) > max_bytes:
            raise MediaError("too_large", f"over {max_bytes} bytes")
        return data


# --- Images ----------------------------------------------------------------------------


@dataclass(frozen=True)
class StoredImage:
    sha256: str
    width: int
    height: int


def _open_image(data: bytes):
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # Pillow raises many kinds; all mean "not an image"
        raise MediaError("image_fetch_failed", f"not a readable JPEG or PNG ({type(exc).__name__})") from exc
    if img.format not in ("JPEG", "PNG"):
        raise MediaError("image_fetch_failed", "only JPEG and PNG images are accepted")
    return img


def _jpeg(img, max_px: int) -> bytes:
    from PIL import Image

    img = img.convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


def store_image(store: Store, data: bytes) -> StoredImage:
    """Re-encode, check the size rule (≥ 512 px on the short side) and store
    the image with its thumbnail."""
    img = _open_image(data)
    if min(img.size) < MIN_IMAGE_PX:
        raise MediaError("image_too_small", f"{img.size[0]}x{img.size[1]} px; at least {MIN_IMAGE_PX} px")
    full = _jpeg(img, MAX_IMAGE_PX)
    sha = hashlib.sha256(full).hexdigest()
    cache = "public, max-age=31536000, immutable"
    if store.stat(f"market/images/{sha}.jpg") is None:
        store.put(f"market/images/{sha}.jpg", full, content_type="image/jpeg", cache_control=cache)
        store.put(f"market/thumbs/{sha}.jpg", _jpeg(img, THUMB_PX), content_type="image/jpeg", cache_control=cache)
    return StoredImage(sha256=sha, width=img.size[0], height=img.size[1])


def image_url(sha: str, *, thumb: bool = False) -> str:
    base = get_settings().api_url.rstrip("/")
    return f"{base}/market/media/{'thumbs' if thumb else 'images'}/{sha}.jpg"


# --- Geometry --------------------------------------------------------------------------


def store_geometry(store: Store, data: bytes, fmt: str) -> dict:
    if fmt not in GEOMETRY_FORMATS:
        raise MediaError("bad_geometry_format", fmt)
    if fmt == "glb" and not data.startswith(b"glTF"):
        raise MediaError("geometry_fetch_failed", "not a binary glTF file")
    sha = hashlib.sha256(data).hexdigest()
    key = f"market/geometry/{sha}.{fmt}"
    if store.stat(key) is None:
        store.put(key, data, content_type=GEOMETRY_TYPES[fmt])
    return {"format": fmt, "sha256": sha, "bytes": len(data), "storage_key": key}


def geometry_url(store: Store, geometry: dict, name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in name)[:80].strip("-") or "geometry"
    return store.signed_get_url(geometry["storage_key"], expires_in=3600, filename=f"{safe}.{geometry['format']}")
