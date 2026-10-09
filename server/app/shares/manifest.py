"""The bundle manifest `truebex-share/1` and its rules (share-bundle §6.1).

`check(manifest)` returns `data.errors[]` for 422 `manifest_invalid`: one
`{"path", "rule", "message"}` per broken rule, in manifest order. Rule ids,
one per row of the contract's table:

    schema        `schema` is truebex-share/1 (a MAJOR this server reads)
    type          a field is missing or has the wrong type
    pano_size     width = 2 x height and width 2048, 4096 or 8192
    pano_type     a panorama's file is a JPEG
    pano_bytes    a panorama's file is at most 30 MB
    pano_count    at most 50 panoramas
    bearing       compass degrees 0..360
    pitch         degrees -90..90
    hfov          start field of view 10..150 degrees
    hotspot_target  a hotspot names another panorama of the bundle
    render_size   a render's long edge is at most 8192 px
    render_type   a render is a JPEG or PNG
    render_bytes  a render's file is at most 25 MB
    render_count  at most 50 renders
    sheets_type   the sheets file is a PDF
    sheets_bytes  the sheets file is at most 200 MB
    text_length   the project title at most 120 characters, other names 60
    file_listed   every referenced file is listed in `files`
    file_referenced  every listed file is used (nothing else travels)
    file_unique   a file is listed once
    file_name     a file name carries no folder
    sha256        64 lowercase hex
    id_unique     panorama and render ids are unique
    start         `start` names a panorama
    units, region, bundle_id, empty
"""

import math
import re
from typing import Any

SCHEMA = "truebex-share/1"
SCHEMA_MAJOR = 1
PANO_WIDTHS = (2048, 4096, 8192)
MB = 1000 * 1000
LIMITS = {
    "pano_bytes": 30 * MB,
    "pano_count": 50,
    "render_edge": 8192,
    "render_bytes": 25 * MB,
    "render_count": 50,
    "sheets_bytes": 200 * MB,
    "title": 120,
    "name": 60,
}
PANO_TYPES = ("image/jpeg",)
RENDER_TYPES = ("image/jpeg", "image/png")
SHEETS_TYPES = ("application/pdf",)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_REGION = re.compile(r"^[A-Z]{2}$")

MESSAGES = {
    "schema": "This bundle was written for a newer share format. Update the server or write truebex-share/1.",
    "type": "This field is missing or has the wrong type.",
    "pano_size": "A panorama is twice as wide as it is tall, 2048, 4096 or 8192 pixels wide.",
    "pano_type": "A panorama is a JPEG.",
    "pano_bytes": "A panorama is at most 30 MB.",
    "pano_count": "A bundle holds at most 50 panoramas.",
    "bearing": "Bearings are compass degrees from 0 to 360.",
    "pitch": "Pitch is between -90 and 90 degrees.",
    "hfov": "The field of view is between 10 and 150 degrees.",
    "hotspot_target": "A hotspot leads to another panorama of this bundle.",
    "render_size": "A render's long edge is at most 8192 pixels.",
    "render_type": "A render is a JPEG or PNG.",
    "render_bytes": "A render is at most 25 MB.",
    "render_count": "A bundle holds at most 50 renders.",
    "sheets_type": "The drawings are one PDF.",
    "sheets_bytes": "The drawings PDF is at most 200 MB.",
    "text_length": "This text is too long (the title 120 characters, names 60).",
    "file_listed": "This file is not listed in files.",
    "file_referenced": "This file is listed but nothing in the bundle uses it.",
    "file_unique": "This file is listed twice.",
    "file_name": "A file name carries no folder.",
    "sha256": "A file is named by its SHA-256 (64 lowercase hex characters).",
    "id_unique": "Panorama and render ids are unique.",
    "start": "start names a panorama of this bundle.",
    "units": "units is metric or imperial.",
    "region": "region is a two-letter country code or null.",
    "bundle_id": "bundle_id is 32 lowercase hex characters.",
    "empty": "A bundle holds at least one panorama, render or drawing.",
    "file_content": "This file's content does not match the manifest.",
}


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _int(v: Any) -> int | None:
    if isinstance(v, bool) or not isinstance(v, int):
        return None
    return v


def schema_major(value: Any) -> int | None:
    m = re.fullmatch(r"truebex-share/(\d+)", value) if isinstance(value, str) else None
    return int(m.group(1)) if m else None


class _Checker:
    def __init__(self) -> None:
        self.errors: list[dict] = []

    def err(self, path: str, rule: str) -> None:
        self.errors.append({"path": path, "rule": rule, "message": MESSAGES[rule]})

    def text(self, obj: dict, key: str, path: str, limit: int, *, required: bool = True) -> None:
        v = obj.get(key)
        if v is None and not required:
            return
        if not isinstance(v, str) or (required and not v.strip()):
            self.err(f"{path}.{key}" if path else key, "type")
        elif len(v) > limit:
            self.err(f"{path}.{key}" if path else key, "text_length")

    def angle(self, obj: dict, key: str, path: str, rule: str, lo: float, hi: float, *, required: bool = True) -> None:
        v = obj.get(key)
        if v is None and not required:
            return
        n = _num(v)
        if n is None:
            self.err(f"{path}.{key}", "type")
        elif not lo <= n <= hi:
            self.err(f"{path}.{key}", rule)


def check(m: Any) -> list[dict]:
    c = _Checker()
    if not isinstance(m, dict):
        c.err("", "type")
        return c.errors
    major = schema_major(m.get("schema"))
    if major != SCHEMA_MAJOR:
        c.err("schema", "schema")
        return c.errors
    if not isinstance(m.get("bundle_id"), str) or not _HEX32.match(m["bundle_id"]):
        c.err("bundle_id", "bundle_id")
    if not isinstance(m.get("watermark"), bool):
        c.err("watermark", "type")

    project = m.get("project")
    if not isinstance(project, dict):
        c.err("project", "type")
    else:
        c.text(project, "title", "project", LIMITS["title"])
        if project.get("units") not in ("metric", "imperial"):
            c.err("project.units", "units")
        region = project.get("region")
        if region is not None and (not isinstance(region, str) or not _REGION.match(region)):
            c.err("project.region", "region")

    # files: listed once, named by hash, no folders.
    files = m.get("files")
    listed: dict[str, dict] = {}
    if not isinstance(files, list):
        c.err("files", "type")
        files = []
    for i, f in enumerate(files):
        path = f"files[{i}]"
        if not isinstance(f, dict):
            c.err(path, "type")
            continue
        sha = f.get("sha256")
        if not isinstance(sha, str) or not _SHA.match(sha):
            c.err(f"{path}.sha256", "sha256")
            continue
        if sha in listed:
            c.err(f"{path}.sha256", "file_unique")
            continue
        size = _int(f.get("bytes"))
        if size is None or size < 1:
            c.err(f"{path}.bytes", "type")
        if not isinstance(f.get("content_type"), str):
            c.err(f"{path}.content_type", "type")
        name = f.get("name")
        if not isinstance(name, str) or not name.strip():
            c.err(f"{path}.name", "type")
        elif "/" in name or "\\" in name or ":" in name or name in (".", ".."):
            c.err(f"{path}.name", "file_name")
        elif len(name) > LIMITS["name"]:
            c.err(f"{path}.name", "text_length")
        listed[sha] = {**f, "_index": i}

    used: set[str] = set()

    def ref(obj: dict, key: str, path: str) -> dict | None:
        sha = obj.get(key)
        if not isinstance(sha, str) or not _SHA.match(sha):
            c.err(f"{path}.{key}", "sha256")
            return None
        used.add(sha)
        if sha not in listed:
            c.err(f"{path}.{key}", "file_listed")
            return None
        return listed[sha]

    panoramas = m.get("panoramas")
    renders = m.get("renders")
    if not isinstance(panoramas, list):
        c.err("panoramas", "type")
        panoramas = []
    if not isinstance(renders, list):
        c.err("renders", "type")
        renders = []
    pano_ids = {p.get("id") for p in panoramas if isinstance(p, dict) and isinstance(p.get("id"), str)}
    seen_ids: set[str] = set()

    def ident(obj: dict, path: str) -> None:
        v = obj.get("id")
        if not isinstance(v, str) or not v.strip() or len(v) > LIMITS["name"]:
            c.err(f"{path}.id", "type")
        elif v in seen_ids:
            c.err(f"{path}.id", "id_unique")
        else:
            seen_ids.add(v)

    if len(panoramas) > LIMITS["pano_count"]:
        c.err("panoramas", "pano_count")
    for i, p in enumerate(panoramas):
        path = f"panoramas[{i}]"
        if not isinstance(p, dict):
            c.err(path, "type")
            continue
        ident(p, path)
        c.text(p, "title", path, LIMITS["name"])
        c.text(p, "storey", path, LIMITS["name"], required=False)
        w, h = _int(p.get("width")), _int(p.get("height"))
        if w is None or h is None:
            c.err(f"{path}.width", "type")
        elif w != 2 * h or w not in PANO_WIDTHS:
            c.err(f"{path}.width", "pano_size")
        f = ref(p, "file", path)
        if f is not None:
            if f.get("content_type") not in PANO_TYPES:
                c.err(f"{path}.file", "pano_type")
            elif (_int(f.get("bytes")) or 0) > LIMITS["pano_bytes"]:
                c.err(f"{path}.file", "pano_bytes")
        eye = p.get("eye_mm")
        if eye is not None and (not isinstance(eye, list) or len(eye) != 3 or any(_num(x) is None for x in eye)):
            c.err(f"{path}.eye_mm", "type")
        c.angle(p, "center_bearing_deg", path, "bearing", 0, 360)
        c.angle(p, "start_bearing_deg", path, "bearing", 0, 360, required=False)
        c.angle(p, "start_pitch_deg", path, "pitch", -90, 90, required=False)
        c.angle(p, "start_hfov_deg", path, "hfov", 10, 150, required=False)
        hotspots = p.get("hotspots", [])
        if not isinstance(hotspots, list):
            c.err(f"{path}.hotspots", "type")
            continue
        for j, hs in enumerate(hotspots):
            hp = f"{path}.hotspots[{j}]"
            if not isinstance(hs, dict):
                c.err(hp, "type")
                continue
            target = hs.get("target")
            if not isinstance(target, str) or target not in pano_ids or target == p.get("id"):
                c.err(f"{hp}.target", "hotspot_target")
            c.angle(hs, "bearing_deg", hp, "bearing", 0, 360)
            c.angle(hs, "pitch_deg", hp, "pitch", -90, 90)
            c.text(hs, "label", hp, LIMITS["name"], required=False)

    if len(renders) > LIMITS["render_count"]:
        c.err("renders", "render_count")
    for i, r in enumerate(renders):
        path = f"renders[{i}]"
        if not isinstance(r, dict):
            c.err(path, "type")
            continue
        ident(r, path)
        c.text(r, "title", path, LIMITS["name"])
        w, h = _int(r.get("width")), _int(r.get("height"))
        if w is None or h is None or w < 1 or h < 1:
            c.err(f"{path}.width", "type")
        elif max(w, h) > LIMITS["render_edge"]:
            c.err(f"{path}.width", "render_size")
        f = ref(r, "file", path)
        if f is not None:
            if f.get("content_type") not in RENDER_TYPES:
                c.err(f"{path}.file", "render_type")
            elif (_int(f.get("bytes")) or 0) > LIMITS["render_bytes"]:
                c.err(f"{path}.file", "render_bytes")

    sheets = m.get("sheets")
    if sheets is not None:
        if not isinstance(sheets, dict):
            c.err("sheets", "type")
        else:
            f = ref(sheets, "file", "sheets")
            if f is not None:
                if f.get("content_type") not in SHEETS_TYPES:
                    c.err("sheets.file", "sheets_type")
                elif (_int(f.get("bytes")) or 0) > LIMITS["sheets_bytes"]:
                    c.err("sheets.file", "sheets_bytes")
            pages = sheets.get("pages")
            if pages is not None and (_int(pages) is None or pages < 1):
                c.err("sheets.pages", "type")
            titles = sheets.get("titles", [])
            if not isinstance(titles, list) or any(not isinstance(t, str) for t in titles):
                c.err("sheets.titles", "type")
            else:
                for k, t in enumerate(titles):
                    if len(t) > LIMITS["name"]:
                        c.err(f"sheets.titles[{k}]", "text_length")

    start = m.get("start")
    if panoramas and start not in pano_ids:
        c.err("start", "start")
    elif not panoramas and start is not None:
        c.err("start", "start")

    for sha, f in listed.items():
        if sha not in used:
            c.err(f"files[{f['_index']}]", "file_referenced")

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
