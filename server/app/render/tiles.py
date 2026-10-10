"""Tile manifests and the tile store (contract §6.2; PF6 storage layout).

| Key                              | Holds                                   | Cache                                  |
|----------------------------------|-----------------------------------------|----------------------------------------|
| `tiles/<sha256>.jpg`             | one JPEG tile, shared by every job      | public, immutable, any origin (CDN)    |
| `jobs/{job_id}/manifest.json`    | the §6.2 manifest (no `tiles_base`)     | private; served by 5.5                 |
| `jobs/{job_id}/render-log.json`  | per-step and per-face milliseconds      | private                                |
| `jobs/{job_id}/error.json`, `log-tail.txt` | a failure's code and last 64 KiB | private                                |
| `jobs/{job_id}/files/<sha256>`   | a `pack` output file                    | private; signed by 5.5                 |
| `sets/{follow_job_id}/latest.json` | `{rev, job_id, at_seq}` of a set      | no-cache                               |

A worker uploads the tiles of the faces it rendered (share-bundle §5,
purpose `job-output`); completing copies each into the public store once and
drops the upload's copy. Carried faces keep their hashes. `render.tiles.gc`
deletes tiles no manifest of the last 90 days (and no set's newest) names.
"""

import json
import re
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..storage import get_store
from ..uploads import service as uploads
from .models import RenderJob, RenderSet

FACES = ("n", "e", "s", "w", "u", "d")
REASONS = ("changed", "light", "carried", "full")
IMMUTABLE = "public, max-age=31536000, immutable"
SCHEMA = "truebex-tiles/1"
PACK_SCHEMA = "truebex-pack/1"
MAX_TILES = 20_000
MAX_PACK_FILES = 500
GC_KEEP = timedelta(days=90)
GC_GRACE = timedelta(days=1)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TILE_KEY = re.compile(r"^tiles/([0-9a-f]{64})\.jpg$")


def tile_key(sha256: str) -> str:
    return f"tiles/{sha256}.jpg"


def manifest_key(job_id: str) -> str:
    return f"jobs/{job_id}/manifest.json"


def job_file_key(job_id: str, name: str) -> str:
    return f"jobs/{job_id}/{name}"


def pack_file_key(job_id: str, sha256: str) -> str:
    return f"jobs/{job_id}/files/{sha256}"


def latest_key(follow_job_id: str) -> str:
    return f"sets/{follow_job_id}/latest.json"


def tiles_base() -> str:
    """Where `<sha256>.jpg` is fetched: TILES_BASE_URL, else the CDN in front
    of the bucket, else this API's public /tiles route."""
    s = get_settings()
    if s.tiles_base_url:
        return s.tiles_base_url.rstrip("/")
    if s.storage_backend == "s3" and s.cdn_base_url:
        return f"{s.cdn_base_url.rstrip('/')}/tiles"
    return f"{s.api_url.rstrip('/')}/tiles"


def put_json(key: str, obj: dict, *, cache_control: str | None = None) -> None:
    data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    get_store().put(key, data, content_type="application/json", cache_control=cache_control)


def read_json(key: str) -> dict | None:
    store = get_store()
    if store.stat(key) is None:
        return None
    with store.open(key) as fh:
        return json.loads(fh.read().decode("utf-8"))


# --- §6.2 rules ----------------------------------------------------------------------


class _Errors:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, path: str, rule: str, message: str, **extra) -> None:
        if len(self.items) < 100:
            self.items.append({"path": path, "rule": rule, "message": message, **extra})


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check_manifest(m: object, job: RenderJob) -> list[dict]:
    """`data.errors[]` for 422 `output_invalid`: every §6.2 rule the output breaks."""
    e = _Errors()
    if not isinstance(m, dict):
        e.add("output", "type", "The output is a JSON object (§6.2).")
        return e.items
    schema = m.get("schema")
    if not isinstance(schema, str) or not schema.startswith("truebex-tiles/") or schema.split("/")[-1].split(".")[0] != "1":
        e.add("schema", "schema", f"schema is {SCHEMA}.")
    if m.get("job_id") != job.job_id:
        e.add("job_id", "job", "job_id is this job's id.")
    if m.get("project_id") != job.project_id:
        e.add("project_id", "job", "project_id is this job's project.")
    if m.get("at_seq") != job.at_seq:
        e.add("at_seq", "job", f"at_seq is {job.at_seq}, the job's.")
    views = m.get("views")
    if not isinstance(views, list) or not views:
        e.add("views", "type", "views lists the job's views.")
        return e.items
    seen: set[str] = set()
    total = 0
    for i, v in enumerate(views):
        path = f"views[{i}]"
        if not isinstance(v, dict):
            e.add(path, "type", "a view is an object.")
            continue
        vid = v.get("view")
        if vid not in job.views or vid in seen:
            e.add(f"{path}.view", "view", "each of the job's views appears once.")
        seen.add(vid)
        face_px, tile_px, levels = v.get("face_px"), v.get("tile_px"), v.get("levels")
        if not _is_int(face_px) or face_px < 1 or not _is_int(tile_px) or tile_px < 1:
            e.add(path, "type", "face_px and tile_px are positive whole numbers.")
            continue
        if (
            not isinstance(levels, list)
            or not levels
            or not all(_is_int(x) and x > 0 for x in levels)
            or levels != sorted(set(levels))
            or levels[-1] != face_px
        ):
            e.add(f"{path}.levels", "levels", "levels ascend and end at face_px.")
            continue
        counts = [max(1, lv // tile_px) ** 2 for lv in levels]
        faces = v.get("faces")
        if not isinstance(faces, dict) or set(faces) != set(FACES):
            e.add(f"{path}.faces", "faces", "faces holds n, e, s, w, u and d.")
            continue
        for f in FACES:
            fp = f"{path}.faces.{f}"
            face = faces[f]
            if not isinstance(face, dict) or not isinstance(face.get("rendered"), bool):
                e.add(fp, "type", "a face has rendered (true or false), reason and tiles.")
                continue
            reason = face.get("reason")
            if reason not in REASONS or (reason == "carried") == face["rendered"]:
                e.add(f"{fp}.reason", "reason", "reason is changed, light or full when rendered, carried when not.")
            if job.kind == "panorama" and not face["rendered"]:
                e.add(f"{fp}.rendered", "full", "a panorama job renders every face.")
            tiles = face.get("tiles")
            if not isinstance(tiles, list) or len(tiles) != len(levels):
                e.add(f"{fp}.tiles", "tiles", "tiles has one list per level.")
                continue
            for level, (row, want) in enumerate(zip(tiles, counts)):
                if not isinstance(row, list) or len(row) != want or not all(isinstance(s, str) and _SHA.match(s) for s in row):
                    e.add(f"{fp}.tiles[{level}]", "tiles", f"level {level} lists {want} tiles by SHA-256.")
                else:
                    total += want
    if seen != set(job.views):
        e.add("views", "view", "the manifest covers every view of the job.")
    if total > MAX_TILES:
        e.add("views", "too_many", f"A manifest names at most {MAX_TILES} tiles.")
    return e.items


def faces_of(m: dict):
    """(view index, view id, face letter, face) for every face."""
    for i, v in enumerate(m.get("views") or []):
        for f in FACES:
            yield i, v["view"], f, v["faces"][f]


def all_tiles(m: dict) -> set[str]:
    return {sha for _, _, _, face in faces_of(m) for row in face["tiles"] for sha in row}


def check_pack(m: object, job: RenderJob) -> list[dict]:
    """A `pack` output: `{"schema": "truebex-pack/1", "job_id", "files": [{name, sha256, bytes, content_type}]}`."""
    e = _Errors()
    if not isinstance(m, dict) or m.get("schema") != PACK_SCHEMA:
        e.add("schema", "schema", f"schema is {PACK_SCHEMA}.")
        return e.items
    if m.get("job_id") != job.job_id:
        e.add("job_id", "job", "job_id is this job's id.")
    files = m.get("files")
    if not isinstance(files, list) or not files or len(files) > MAX_PACK_FILES:
        e.add("files", "type", f"files lists 1 to {MAX_PACK_FILES} files.")
        return e.items
    for i, f in enumerate(files):
        if (
            not isinstance(f, dict)
            or not isinstance(f.get("name"), str)
            or not 0 < len(f["name"]) <= 120
            or "/" in f["name"]
            or "\\" in f["name"]
            or not isinstance(f.get("sha256"), str)
            or not _SHA.match(f["sha256"])
        ):
            e.add(f"files[{i}]", "type", "a file has a name (no folder) and a SHA-256.")
    return e.items


# --- storing a completed output ---------------------------------------------------------


def verify_tiles(db: Session, job: RenderJob, m: dict, base: dict | None) -> tuple[list[dict], dict]:
    """Every rendered tile complete in the job's output upload (or already in
    the store), every carried face as in the base manifest. Returns (errors,
    the upload's blobs by SHA-256)."""
    e = _Errors()
    rendered = {sha for _, _, _, face in faces_of(m) if face["rendered"] for row in face["tiles"] for sha in row}
    blobs = uploads.blobs_by_sha(db, job.account_id, sorted(rendered))
    store = get_store()
    for sha in sorted(rendered - set(blobs)):
        if store.stat(tile_key(sha)) is None:
            e.add("output", "file_missing", "This tile is not complete in the output upload.", sha256=sha)
    base_faces = {(vid, f): face["tiles"] for _, vid, f, face in faces_of(base)} if base else {}
    for i, vid, f, face in faces_of(m):
        if face["rendered"]:
            continue
        if base_faces.get((vid, f)) != face["tiles"]:
            e.add(f"views[{i}].faces.{f}", "carried", "A carried face keeps the base manifest's tiles.")
    return e.items, blobs


def publish_tiles(db: Session, blobs: dict) -> int:
    """Copy each uploaded tile into the public store once; drop the upload's copy."""
    store = get_store()
    copied = 0
    for sha, blob in blobs.items():
        key = tile_key(sha)
        if store.stat(key) is None:
            with store.open(blob.storage_key) as fh:
                store.put(key, fh, content_type="image/jpeg", cache_control=IMMUTABLE)
            copied += 1
    _drop(db, blobs)
    return copied


def verify_pack(db: Session, job: RenderJob, m: dict) -> tuple[list[dict], dict]:
    e = _Errors()
    shas = [f["sha256"] for f in m["files"]]
    blobs = uploads.blobs_by_sha(db, job.account_id, shas)
    for i, sha in enumerate(shas):
        if sha not in blobs:
            e.add(f"files[{i}]", "file_missing", "This file is not complete in the output upload.", sha256=sha)
    return e.items, blobs


def publish_pack(db: Session, job: RenderJob, m: dict, blobs: dict) -> None:
    store = get_store()
    for f in m["files"]:
        blob = blobs[f["sha256"]]
        f["bytes"] = blob.bytes
        f["content_type"] = blob.content_type
        with store.open(blob.storage_key) as fh:
            store.put(pack_file_key(job.job_id, f["sha256"]), fh, content_type=blob.content_type)
    _drop(db, blobs)


def _drop(db: Session, blobs: dict) -> None:
    """The upload's copies were only for this output: delete those nothing holds."""
    store = get_store()
    for blob in blobs.values():
        if blob.refs <= 0:
            store.delete(blob.storage_key)
            db.delete(blob)


# --- render.tiles.gc ---------------------------------------------------------------------


def referenced(db: Session, now: datetime) -> set[str]:
    """Tiles named by a manifest of the last 90 days or by any set's newest."""
    keys = set(
        db.scalars(
            select(RenderJob.output_key).where(
                RenderJob.output_key.is_not(None),
                or_(RenderJob.finished_at >= now - GC_KEEP, RenderJob.updated_at >= now - GC_KEEP),
            )
        )
    )
    for latest in db.scalars(select(RenderSet.latest_job_id).where(RenderSet.latest_job_id.is_not(None))):
        keys.add(manifest_key(latest))
    out: set[str] = set()
    for key in keys:
        m = read_json(key)
        if m and m.get("schema", "").startswith("truebex-tiles/"):
            try:
                out |= all_tiles(m)
            except (KeyError, TypeError):
                continue
    return out


def gc(db: Session, now: datetime) -> int:
    keep = referenced(db, now)
    store = get_store()
    removed = 0
    for info in store.list("tiles/"):
        match = _TILE_KEY.match(info.key)
        if match is None or match.group(1) in keep:
            continue
        if info.modified_at is not None and info.modified_at > now - GC_GRACE:
            continue  # a job may be completing with it right now
        store.delete(info.key)
        removed += 1
    return removed
