"""Panorama derivatives made at publish (PF5): every panorama again at 4096 x
2048 and 1024 x 512, so a phone that cannot hold an 8192-wide texture (or is
on a metered connection) never downloads the 8k original. A source narrower
than a size is re-encoded at its own size, never enlarged.

Keys: shares/{share_id}/derived/{sha256}-{kind}.jpg
"""

import io
from dataclasses import dataclass

from PIL import Image

from ..storage import Store

KINDS = (("pano-4096", 4096), ("pano-1024", 1024))
QUALITY = 84


@dataclass(frozen=True)
class Made:
    kind: str
    key: str
    width: int
    height: int
    bytes: int


def key_for(share_id: str, sha256: str, kind: str) -> str:
    return f"shares/{share_id}/derived/{sha256}-{kind}.jpg"


def open_rgb(store: Store, key: str, *, draft_width: int | None = None) -> Image.Image:
    """Decode a stored image as RGB; `draft_width` lets JPEG decode at a smaller scale."""
    with store.open(key) as fh:
        img = Image.open(fh)
        if draft_width and img.format == "JPEG" and img.width > draft_width:
            img.draft("RGB", (draft_width, max(1, draft_width * img.height // img.width)))
        img.load()
    return img.convert("RGB")


def _jpeg(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=QUALITY, optimize=True, progressive=True)
    return out.getvalue()


def make(store: Store, *, share_id: str, sha256: str, source_key: str) -> tuple[list[Made], Image.Image]:
    """Write both derivatives; returns them and the largest (for the card)."""
    img = open_rgb(store, source_key, draft_width=KINDS[0][1])
    made: list[Made] = []
    largest = None
    current = img
    for kind, width in KINDS:
        w = min(width, current.width)
        size = (w, max(1, w // 2))
        if current.size != size:
            current = current.resize(size, Image.LANCZOS)
        data = _jpeg(current)
        key = key_for(share_id, sha256, kind)
        store.put(key, data, content_type="image/jpeg", cache_control="public, max-age=31536000, immutable")
        made.append(Made(kind=kind, key=key, width=size[0], height=size[1], bytes=len(data)))
        if largest is None:
            largest = current
    return made, largest
