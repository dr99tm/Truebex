"""The bundle manifest `truebex-share/1` and its rules (share-bundle §6.1).

`check(manifest)` returns `data.errors[]` for 422 `manifest_invalid`: one
`{"path", "rule", "message"}` per broken rule. Since PF5b the paths and rule
ids are the app's (`CadShareBundle::Validate`, share-bundle 1.1 §6.1), so the
app and the platform name a broken rule alike:

    json               the manifest is a JSON object
    schema             `schema` is truebex-share/1 (a MAJOR this server reads)
    bundle_id          32 lowercase hex
    project            `project` is an object
    title_length       the project title is at most 120 characters
    units, region      metric or imperial; a two-letter country code or null
    file_entry         a `files` entry is an object
    file_hash_format   a file's sha256 is 64 lowercase hex
    file_bytes         a file's bytes is above 0
    file_type          a file is a JPEG, a PNG or a PDF
    file_name          a relative path inside the bundle: not empty, no "..",
                       no leading "/", no "\\" and no ":" (folders are fine)
    file_duplicate     a file is listed once
    file_unlisted      every referenced file is listed in `files`
    file_unreferenced  every listed file is used (nothing else travels)
    panorama_count     at most 50 panoramas
    panorama_entry     a panorama is an object
    duplicate_id       ids are unique and not empty
    name_length        a panorama's or a render's title is at most 60 characters
    panorama_ratio     width = 2 x height
    panorama_width     2048, 4096 or 8192 wide
    panorama_type      a panorama's file is a JPEG
    panorama_bytes     a panorama's file is at most 30 MiB
    eye_mm             [x, y, z] in doc millimetres
    bearing_range      compass degrees in [0, 360)
    pitch_range        degrees in [-90, 90]
    hfov_range         a field of view in (0, 180]
    hotspot_entry      a hotspot is an object
    hotspot_target     a hotspot names another panorama of the bundle
    label_length       a hotspot label is at most 60 characters
    start              `start` names a panorama
    render_count, render_entry, render_edge (long edge 1..8192 px),
    render_type, render_bytes (25 MiB)
    sheets_entry, sheets_type, sheets_bytes (200 MiB), sheets_pages
    cover_type         (1.1) the cover is a JPEG; it must be listed and counts
                       as a use of its file

Only the platform checks (the app writes these right, so they never fire on
its manifests): `type` (a field the page reads is missing or has the wrong
type), `empty` (no panorama, render or drawing) and, at publish,
`file_content` (service.py: the stored bytes are what the manifest says).
The app's `total_bytes` is the platform's 403 `quota_exceeded`
(`share_bytes`). The other 1.1 keys (`branding`, `plan`, `app_build`, the
project card) are a reader's to ignore and are not checked.
"""

import math
import re
from typing import Any

SCHEMA = "truebex-share/1"
SCHEMA_MAJOR = 1
PANO_WIDTHS = (2048, 4096, 8192)
MIB = 1024 * 1024
LIMITS = {
    "pano_bytes": 30 * MIB,
    "pano_count": 50,
    "render_edge": 8192,
    "render_bytes": 25 * MIB,
    "render_count": 50,
    "sheets_bytes": 200 * MIB,
    "title": 120,
    "name": 60,
    # A file name's length is the platform's own bound (the app checks none).
    "file_name": 255,
}
FILE_TYPES = ("image/jpeg", "image/png", "application/pdf")
PANO_TYPES = ("image/jpeg",)
RENDER_TYPES = ("image/jpeg", "image/png")
SHEETS_TYPES = ("application/pdf",)
COVER_TYPES = ("image/jpeg",)

_SHA = re.compile(r"[0-9a-f]{64}")
_HEX32 = re.compile(r"[0-9a-f]{32}")
_REGION = re.compile(r"[A-Z]{2}")

MESSAGES = {
    "json": "The manifest is a JSON object.",
    "schema": "This bundle was written for a newer share format. Update the server or write truebex-share/1.",
    "bundle_id": "bundle_id is 32 lowercase hex characters.",
    "project": "The manifest needs its project.",
    "title_length": "A title is at most 120 characters.",
    "units": "units is metric or imperial.",
    "region": "region is a two-letter country code or null.",
    "file_entry": "Each entry of files is an object.",
    "file_hash_format": "A file is named by its SHA-256 (64 lowercase hex characters).",
    "file_bytes": "A file's size in bytes is above 0.",
    "file_type": "A file is a JPEG, a PNG or a PDF.",
    "file_name": "A file name is a relative path inside the bundle (no .., no leading /, no \\ or :).",
    "file_duplicate": "This file is listed twice.",
    "file_unlisted": "This file is not listed in files.",
    "file_unreferenced": "This file is listed but nothing in the bundle uses it.",
    "panorama_count": "A bundle holds at most 50 panoramas.",
    "panorama_entry": "Each panorama is an object.",
    "duplicate_id": "Ids are unique and not empty.",
    "name_length": "A name is at most 60 characters.",
    "panorama_ratio": "A panorama is twice as wide as it is tall.",
    "panorama_width": "A panorama is 2048, 4096 or 8192 pixels wide.",
    "panorama_type": "A panorama is a JPEG.",
    "panorama_bytes": "A panorama is at most 30 MB.",
    "eye_mm": "eye_mm is [x, y, z] in millimetres.",
    "bearing_range": "Bearings are compass degrees from 0 up to 360.",
    "pitch_range": "Pitch is between -90 and 90 degrees.",
    "hfov_range": "The field of view is above 0 and at most 180 degrees.",
    "hotspot_entry": "Each hotspot is an object.",
    "hotspot_target": "A hotspot leads to another panorama of this bundle.",
    "label_length": "A label is at most 60 characters.",
    "start": "start names a panorama of this bundle.",
    "render_count": "A bundle holds at most 50 renders.",
    "render_entry": "Each render is an object.",
    "render_edge": "A render's long edge is between 1 and 8192 pixels.",
    "render_type": "A render is a JPEG or PNG.",
    "render_bytes": "A render is at most 25 MB.",
    "sheets_entry": "sheets is an object or null.",
    "sheets_type": "The drawings are one PDF.",
    "sheets_bytes": "The drawings PDF is at most 200 MB.",
    "sheets_pages": "The drawings PDF has at least one page.",
    "cover_type": "The cover is a JPEG.",
    "type": "This field is missing or has the wrong type.",
    "empty": "A bundle holds at least one panorama, render or drawing.",
    "file_content": "This file's content does not match the manifest.",
}


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _size(v: Any) -> int:
    """A width or height as the app reads it: a number truncated, else 0."""
    n = _num(v)
    return int(n) if n is not None else 0


def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def schema_major(value: Any) -> int | None:
    m = re.fullmatch(r"truebex-share/(\d+)", value) if isinstance(value, str) else None
    return int(m.group(1)) if m else None


def bad_file_name(name: Any) -> bool:
    """The app's rule (a relative path inside the bundle), and the platform's length bound."""
    if not isinstance(name, str) or not name:
        return True
    return ".." in name or name.startswith("/") or "\\" in name or ":" in name or len(name) > LIMITS["file_name"]


class _Checker:
    def __init__(self) -> None:
        self.errors: list[dict] = []

    def err(self, path: str, rule: str) -> None:
        self.errors.append({"path": path, "rule": rule, "message": MESSAGES[rule]})

    def text(self, obj: dict, key: str, path: str, limit: int | None, rule: str, *, required: bool) -> None:
        """A name the person typed: a string (non-empty when required), at most `limit`."""
        v = obj.get(key)
        if v is None and not required:
            return
        if not isinstance(v, str) or (required and not v.strip()):
            self.err(f"{path}.{key}", "type")
        elif limit is not None and len(v) > limit:
            self.err(f"{path}.{key}", rule)

    def angle(self, obj: dict, key: str, path: str, rule: str, ok, *, required: bool) -> None:
        v = obj.get(key)
        if v is None and not required:
            return
        n = _num(v)
        if n is None or not ok(n):
            self.err(f"{path}.{key}", rule)


def _bearing(n: float) -> bool:
    return 0 <= n < 360


def _pitch(n: float) -> bool:
    return -90 <= n <= 90


def _hfov(n: float) -> bool:
    return 0 < n <= 180


def check(m: Any) -> list[dict]:
    c = _Checker()
    if not isinstance(m, dict):
        c.err("", "json")
        return c.errors
    if schema_major(m.get("schema")) != SCHEMA_MAJOR:
        c.err("schema", "schema")
        return c.errors
    if not isinstance(m.get("bundle_id"), str) or not _HEX32.fullmatch(m["bundle_id"]):
        c.err("bundle_id", "bundle_id")
    if not isinstance(m.get("watermark"), bool):
        c.err("watermark", "type")

    # files: the content-addressed list, each listed once.
    files = m.get("files")
    listed: dict[str, dict] = {}
    if not isinstance(files, list):
        c.err("files", "type")
        files = []
    for i, f in enumerate(files):
        path = f"files[{i}]"
        if not isinstance(f, dict):
            c.err(path, "file_entry")
            continue
        sha = _str(f.get("sha256"))
        if not _SHA.fullmatch(sha):
            c.err(f"{path}.sha256", "file_hash_format")
        size = _num(f.get("bytes"))
        if size is None or size <= 0:
            c.err(f"{path}.bytes", "file_bytes")
        if f.get("content_type") not in FILE_TYPES:
            c.err(f"{path}.content_type", "file_type")
        if bad_file_name(f.get("name")):
            c.err(f"{path}.name", "file_name")
        if sha in listed:
            c.err(path, "file_duplicate")
            continue
        listed[sha] = {**f, "_index": i}

    used: set[str] = set()

    def ref(path: str, value: Any) -> dict | None:
        sha = _str(value)
        used.add(sha)
        if sha not in listed:
            c.err(path, "file_unlisted")
            return None
        return listed[sha]

    def file_bytes(f: dict) -> float:
        return _num(f.get("bytes")) or 0

    project = m.get("project")
    if not isinstance(project, dict):
        c.err("project", "project")
    else:
        title = project.get("title")
        if not isinstance(title, str):
            c.err("project.title", "type")
        elif len(title) > LIMITS["title"]:
            c.err("project.title", "title_length")
        if project.get("units") not in ("metric", "imperial"):
            c.err("project.units", "units")
        region = project.get("region")
        if region is not None and (not isinstance(region, str) or not _REGION.fullmatch(region)):
            c.err("project.region", "region")

    panoramas = m.get("panoramas")
    renders = m.get("renders")
    if not isinstance(panoramas, list):
        c.err("panoramas", "type")
        panoramas = []
    if not isinstance(renders, list):
        c.err("renders", "type")
        renders = []
    pano_ids = {p.get("id") for p in panoramas if isinstance(p, dict) and isinstance(p.get("id"), str) and p.get("id")}
    seen_ids: set[str] = set()

    def ident(obj: dict, path: str) -> None:
        v = obj.get("id")
        if not isinstance(v, str) or not v or v in seen_ids:
            c.err(f"{path}.id", "duplicate_id")
        else:
            seen_ids.add(v)

    if len(panoramas) > LIMITS["pano_count"]:
        c.err("panoramas", "panorama_count")
    for i, p in enumerate(panoramas):
        path = f"panoramas[{i}]"
        if not isinstance(p, dict):
            c.err(path, "panorama_entry")
            continue
        ident(p, path)
        c.text(p, "title", path, LIMITS["name"], "name_length", required=True)
        c.text(p, "storey", path, None, "type", required=False)
        w, h = _size(p.get("width")), _size(p.get("height"))
        if w != 2 * h:
            c.err(f"{path}.width", "panorama_ratio")
        if w not in PANO_WIDTHS:
            c.err(f"{path}.width", "panorama_width")
        f = ref(f"{path}.file", p.get("file"))
        if f is not None:
            if f.get("content_type") not in PANO_TYPES:
                c.err(f"{path}.file", "panorama_type")
            if file_bytes(f) > LIMITS["pano_bytes"]:
                c.err(f"{path}.file", "panorama_bytes")
        eye = p.get("eye_mm")
        if eye is not None and (not isinstance(eye, list) or len(eye) != 3 or any(_num(x) is None for x in eye)):
            c.err(f"{path}.eye_mm", "eye_mm")
        c.angle(p, "center_bearing_deg", path, "bearing_range", _bearing, required=True)
        c.angle(p, "start_bearing_deg", path, "bearing_range", _bearing, required=False)
        c.angle(p, "start_pitch_deg", path, "pitch_range", _pitch, required=False)
        c.angle(p, "start_hfov_deg", path, "hfov_range", _hfov, required=False)
        # PF6 (a MINOR proposal): the followed render set the page shows live.
        live = p.get("live_job_id")
        if live is not None and (not isinstance(live, str) or not _HEX32.fullmatch(live)):
            c.err(f"{path}.live_job_id", "type")
        hotspots = p.get("hotspots", [])
        if not isinstance(hotspots, list):
            c.err(f"{path}.hotspots", "type")
            continue
        for j, hs in enumerate(hotspots):
            hp = f"{path}.hotspots[{j}]"
            if not isinstance(hs, dict):
                c.err(hp, "hotspot_entry")
                continue
            target = hs.get("target")
            if not isinstance(target, str) or target not in pano_ids or target == p.get("id"):
                c.err(f"{hp}.target", "hotspot_target")
            c.angle(hs, "bearing_deg", hp, "bearing_range", _bearing, required=True)
            c.angle(hs, "pitch_deg", hp, "pitch_range", _pitch, required=True)
            c.text(hs, "label", hp, LIMITS["name"], "label_length", required=False)

    start = m.get("start")
    if panoramas and start not in pano_ids:
        c.err("start", "start")
    elif not panoramas and start is not None:
        c.err("start", "start")

    if len(renders) > LIMITS["render_count"]:
        c.err("renders", "render_count")
    for i, r in enumerate(renders):
        path = f"renders[{i}]"
        if not isinstance(r, dict):
            c.err(path, "render_entry")
            continue
        ident(r, path)
        c.text(r, "title", path, LIMITS["name"], "name_length", required=True)
        w, h = _size(r.get("width")), _size(r.get("height"))
        if w <= 0 or h <= 0 or max(w, h) > LIMITS["render_edge"]:
            c.err(f"{path}.width", "render_edge")
        f = ref(f"{path}.file", r.get("file"))
        if f is not None:
            if f.get("content_type") not in RENDER_TYPES:
                c.err(f"{path}.file", "render_type")
            if file_bytes(f) > LIMITS["render_bytes"]:
                c.err(f"{path}.file", "render_bytes")

    sheets = m.get("sheets")
    if sheets is not None:
        if not isinstance(sheets, dict):
            c.err("sheets", "sheets_entry")
        else:
            f = ref("sheets.file", sheets.get("file"))
            if f is not None:
                if f.get("content_type") not in SHEETS_TYPES:
                    c.err("sheets.file", "sheets_type")
                if file_bytes(f) > LIMITS["sheets_bytes"]:
                    c.err("sheets.file", "sheets_bytes")
            pages = sheets.get("pages")
            if pages is not None and ((n := _num(pages)) is None or n < 1):
                c.err("sheets.pages", "sheets_pages")
            titles = sheets.get("titles", [])
            if not isinstance(titles, list) or any(not isinstance(t, str) for t in titles):
                c.err("sheets.titles", "type")

    # 1.1: the link-preview cover, a JPEG of the bundle.
    cover = m.get("cover")
    if cover is not None:
        f = ref("cover", cover)
        if f is not None and f.get("content_type") not in COVER_TYPES:
            c.err("cover", "cover_type")

    for sha, f in listed.items():
        if sha not in used:
            c.err(f"files[{f['_index']}]", "file_unreferenced")

    if not panoramas and not renders and sheets is None:
        c.err("", "empty")
    return c.errors


# --- helpers the share service uses ------------------------------------------------


def files(m: dict) -> list[dict]:
    return [f for f in m.get("files", []) if isinstance(f, dict)]


def total_bytes(m: dict) -> int:
    return sum(int(f.get("bytes") or 0) for f in files(m))


def file_shas(m: dict) -> list[str]:
    return [f["sha256"] for f in files(m)]


def panoramas(m: dict) -> list[dict]:
    return [p for p in m.get("panoramas", []) if isinstance(p, dict)]


def renders(m: dict) -> list[dict]:
    return [r for r in m.get("renders", []) if isinstance(r, dict)]


def start_panorama(m: dict) -> dict | None:
    panos = panoramas(m)
    return next((p for p in panos if p.get("id") == m.get("start")), panos[0] if panos else None)


def cover(m: dict) -> str | None:
    """The 1.1 cover's SHA-256 when it names a listed JPEG, else None."""
    sha = m.get("cover")
    if not isinstance(sha, str):
        return None
    f = next((f for f in files(m) if f.get("sha256") == sha), None)
    return sha if f is not None and f.get("content_type") in COVER_TYPES else None


# The 1.1 keys a share keeps but never shows publicly (5.10 drops them).
PRIVATE_KEYS = ("plan", "app_build")


def public(m: dict) -> dict:
    """The manifest as the page may show it: without `plan` and `app_build`."""
    return {k: v for k, v in m.items() if k not in PRIVATE_KEYS}
