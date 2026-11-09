"""Tile manifests and the tile store (contract §6.2; PF6 storage layout).

| Key                              | Holds                                   | Cache                                  |
|----------------------------------|-----------------------------------------|----------------------------------------|
| `tiles/<sha256>.jpg`             | one JPEG tile, shared by every job      | public, immutable, any origin (CDN)    |
| `tiles/<sha256>.png`             | 1.4: a face's `id` (8-bit grey) or `depth` (16-bit grey) PNG at `levels[0]` px | the same       |
| `tiles/<sha256>.json`            | 1.4: a face's `ids` (`truebex-ids/1`) or the manifest's `tour` (`truebex-tour/1`) | the same    |
| `jobs/{job_id}/manifest.json`    | the §6.2 manifest (no `tiles_base`)     | private; served by 5.5                 |
| `jobs/{job_id}/render-log.json`  | per-step and per-face milliseconds      | private                                |
| `jobs/{job_id}/error.json`, `log-tail.txt` | a failure's code and last 64 KiB | private                                |
| `jobs/{job_id}/files/<sha256>`   | a `pack` output file                    | private; signed by 5.5                 |
| `sets/{follow_job_id}/latest.json` | `{rev, job_id, at_seq}` of a set      | no-cache                               |

A worker uploads the tiles of the faces it rendered (share-bundle §5,
purpose `job-output`) into the session its claim opened; completing checks
each against that session, copies it into the public store once (a tile
stored long ago is written again, so the collector sees it as new) and leaves
the upload's copy to `uploads.expire`. Carried faces keep the base manifest's
hashes. `render.tiles.gc` deletes tiles no manifest of the last 90 days, no
set's newest and no running job's base names.

PF6d (render-jobs 1.4.0, PR5's headset faces): a face may name `id`, `ids` and
`depth` files and carry `version` and `op_seq`, the manifest a `tour` file.
One key per extension, beside the colour tiles, published, served and
collected the same way. 5.9 checks each file a rendered face (or the tour)
names: in the upload or already stored; a PNG's signature and IHDR (width =
height = the view's `levels[0]`, grey, 8 bits for `id`, 16 for `depth`; the
pixels are not decoded); `ids` a `truebex-ids/1` list of at most 256 with
`ids[0]` null; the tour `truebex-tour/1` whose every node names a view of the
manifest. The server keeps the numbers: a rendered face is version 1 on a
panorama and the base face's + 1 on a tiles job, with the job's `at_seq` as
`op_seq`; a carried face keeps the base's (a base stored before 1.4: version
1, its `at_seq`). A worker may send them; a value that disagrees is refused,
an omitted one is filled. A carried face keeps the base's files and an update
without a tour keeps the base's.
"""

import copy
import json
import re
import struct
import zlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..storage import get_store
from ..uploads import service as uploads
from ..uploads.models import UploadSession
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
# A reused tile older than this is written again so the collector keeps it.
REFRESH_AFTER = timedelta(days=30)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
_TILE_KEY = re.compile(r"^tiles/([0-9a-f]{64})\.(jpg|png|json)$")
_MANIFEST_KEY = re.compile(r"^jobs/([0-9a-f]{32})/manifest\.json$")
# The public store's files by extension (1.4 added png and json).
MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "json": "application/json"}
# render-jobs 1.4.0: a face's files (key -> extension) and the manifest's tour.
FACE_FILES = {"id": "png", "ids": "json", "depth": "png"}
IDS_SCHEMA = "truebex-ids/1"
TOUR_FORMAT = "truebex-tour/1"
MAX_IDS = 256  # an 8-bit index
MAX_JSON_BYTES = 1024 * 1024
PNG_SIGNATURE = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
PNG_BITS = {"id": 8, "depth": 16}


def tile_key(sha256: str, ext: str = "jpg") -> str:
    return f"tiles/{sha256}.{ext}"


def manifest_key(job_id: str) -> str:
    return f"jobs/{job_id}/manifest.json"


def manifest_job_id(key: str) -> str | None:
    """The job that wrote the manifest at `key` (manifest_key's inverse)."""
    m = _MANIFEST_KEY.match(key or "")
    return m.group(1) if m else None


def job_file_key(job_id: str, name: str) -> str:
    return f"jobs/{job_id}/{name}"


def pack_file_key(job_id: str, sha256: str) -> str:
    return f"jobs/{job_id}/files/{sha256}"


def latest_key(follow_job_id: str) -> str:
    return f"sets/{follow_job_id}/latest.json"


def tiles_base() -> str:
    """Where `<sha256>.jpg` (and 1.4's `.png` / `.json`) is fetched:
    TILES_BASE_URL, else the CDN in front of the bucket, else this API's
    public /tiles route."""
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
            _check_face_keys(e, fp, face)
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
    if "tour" in m and not _is_sha(m["tour"]):
        e.add("tour", "tour", "tour is the SHA-256 of the set's truebex-tour/1 file.")
    return e.items


_FILE_WHAT = {
    "id": "an 8-bit grey PNG of entity indexes",
    "ids": "its truebex-ids/1 JSON",
    "depth": "a 16-bit grey PNG of millimetres",
}


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and _SHA.match(value) is not None


def _check_face_keys(e: _Errors, fp: str, face: dict) -> None:
    """1.4's optional keys of a face: their types only (5.9 reads the files)."""
    for key, what in _FILE_WHAT.items():
        if key in face and not _is_sha(face[key]):
            e.add(f"{fp}.{key}", key, f"{key} is the SHA-256 of {what}.")
    if ("id" in face) != ("ids" in face):
        e.add(fp, "ids", "id and ids come together (ids names the entity of each index in id).")
    if "version" in face and not (_is_int(face["version"]) and face["version"] >= 1):
        e.add(f"{fp}.version", "version", "version is a whole number, 1 or more.")
    if "op_seq" in face and not (_is_int(face["op_seq"]) and face["op_seq"] >= 0):
        e.add(f"{fp}.op_seq", "op_seq", "op_seq is a whole number: the at_seq of the job that last rendered the face.")


def faces_of(m: dict):
    """(view index, view id, face letter, face) for every face."""
    for i, v in enumerate(m.get("views") or []):
        for f in FACES:
            yield i, v["view"], f, v["faces"][f]


def all_tiles(m: dict) -> set[str]:
    return {sha for _, _, _, face in faces_of(m) for row in face["tiles"] for sha in row}


def face_files(face: dict) -> list[tuple[str, str, str]]:
    """(key, SHA-256, extension) of the 1.4 files a face names."""
    return [(key, face[key], ext) for key, ext in FACE_FILES.items() if _is_sha(face.get(key))]


def all_files(m: dict) -> set[str]:
    """Every store key a manifest names: its colour tiles, its faces' 1.4
    files and its tour."""
    keys = {tile_key(sha) for sha in all_tiles(m)}
    keys |= {tile_key(sha, ext) for _, _, _, face in faces_of(m) for _, sha, ext in face_files(face)}
    if _is_sha(m.get("tour")):
        keys.add(tile_key(m["tour"], "json"))
    return keys


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


def declared(db: Session, job: RenderJob) -> set[str]:
    """The files the worker declared into the claim's job-output session."""
    session = db.get(UploadSession, job.output_upload_id) if job.output_upload_id else None
    return {f["sha256"] for f in (session.files if session is not None else [])}


def _base_faces(base: dict | None) -> dict:
    return {(vid, f): face for _, vid, f, face in faces_of(base)} if base else {}


def _version(face: dict | None) -> int:
    v = (face or {}).get("version")
    return v if _is_int(v) and v >= 1 else 1


def expected_version(job: RenderJob, face: dict, before: dict | None, base: dict | None) -> tuple[int, int]:
    """(version, op_seq) a face of this job's output answers: a rendered face
    1 on a panorama, the base face's + 1 on a tiles job, at the job's at_seq;
    a carried face the base's (a base stored before 1.4: 1, its at_seq)."""
    if face["rendered"]:
        return (_version(before) + 1 if job.kind == "tiles" and before is not None else 1), job.at_seq
    seq = (before or {}).get("op_seq")
    return _version(before), seq if _is_int(seq) else (base or {}).get("at_seq", job.at_seq)


def _read_head(store, source: str, n: int) -> bytes:
    with store.open(source) as fh:
        return fh.read(n)


def png_header(head: bytes) -> tuple[int, int, int, int] | None:
    """(width, height, bit depth, colour type) from a PNG's first 33 bytes:
    the signature, then an IHDR chunk whose CRC holds; None otherwise."""
    if len(head) < 33 or head[:8] != PNG_SIGNATURE or head[8:16] != struct.pack(">I", 13) + b"IHDR":
        return None
    if struct.unpack(">I", head[29:33])[0] != zlib.crc32(head[12:29]) & 0xFFFFFFFF:
        return None
    width, height, depth, colour = struct.unpack(">IIBB", head[16:26])
    return width, height, depth, colour


def _check_png(store, source: str, key: str, px: int) -> str | None:
    bits = PNG_BITS[key]
    want = f"{key} is a {bits}-bit grey PNG of {px} x {px} px (the view's levels[0])"
    header = png_header(_read_head(store, source, 33))
    if header is None:
        return f"{want}; this file is not a PNG."
    width, height, depth, colour = header
    if (width, height) != (px, px):
        return f"{want}; this one is {width} x {height} px."
    if colour != 0 or depth != bits:
        return f"{want}; this one is {depth}-bit, colour type {colour}."
    return None


def _read_json(store, source: str, size: int) -> object:
    if size > MAX_JSON_BYTES:
        raise ValueError(f"larger than {MAX_JSON_BYTES} bytes")
    with store.open(source) as fh:
        return json.loads(fh.read(MAX_JSON_BYTES + 1).decode("utf-8"))


def _check_ids(store, source: str, size: int) -> str | None:
    want = f'ids is a {IDS_SCHEMA} file: {{"schema": "{IDS_SCHEMA}", "ids": [null, "<32 hex>", ...]}}, at most {MAX_IDS} ids'
    try:
        doc = _read_json(store, source, size)
    except (ValueError, UnicodeDecodeError) as exc:
        return f"{want}; this file is not JSON ({exc.__class__.__name__})."
    ids = doc.get("ids") if isinstance(doc, dict) else None
    if not isinstance(doc, dict) or doc.get("schema") != IDS_SCHEMA or not isinstance(ids, list):
        return f"{want}; this one is not."
    if not 1 <= len(ids) <= MAX_IDS:
        return f"{want}; this one lists {len(ids)}."
    if ids[0] is not None:
        return f"{want}; ids[0] (nothing seen) is null."
    for n, entity in enumerate(ids[1:], 1):
        if entity is not None and not (isinstance(entity, str) and _HEX32.match(entity)):
            return f"{want}; ids[{n}] is not an entity id."
    return None


def _check_tour(store, source: str, size: int, views: set[str]) -> str | None:
    want = f"tour is a {TOUR_FORMAT} file whose every node names a view of the manifest"
    try:
        doc = _read_json(store, source, size)
    except (ValueError, UnicodeDecodeError) as exc:
        return f"{want}; this file is not JSON ({exc.__class__.__name__})."
    nodes = doc.get("nodes") if isinstance(doc, dict) else None
    if not isinstance(doc, dict) or doc.get("format") != TOUR_FORMAT or not isinstance(nodes, list) or not nodes:
        return f"{want}; this one is not (format {TOUR_FORMAT}, one node or more)."
    for n, node in enumerate(nodes):
        if not isinstance(node, dict) or node.get("view") not in views:
            return f"{want}; nodes[{n}] names no view of the manifest."
    return None


def verify_tiles(db: Session, job: RenderJob, m: dict, base: dict | None) -> tuple[list[dict], dict]:
    """Every rendered tile complete in the claim's output upload (or already
    in the store), every carried face as in the base manifest; 1.4: every
    file a rendered face or the tour names there too and of its format, a
    carried face's files the base's, version and op_seq as the server counts
    them. Returns (errors, the upload's blobs by store key)."""
    e = _Errors()
    store = get_store()
    # Store key -> where it is named: [(path, key, levels[0])]; colour tiles have no check of their own.
    wanted: dict[str, list[tuple[str, str, int]]] = {}
    for i, _, f, face in faces_of(m):
        if not face["rendered"]:
            continue
        for row in face["tiles"]:
            for sha in row:
                wanted.setdefault(tile_key(sha), [])
        for key, sha, ext in face_files(face):
            wanted.setdefault(tile_key(sha, ext), []).append((f"views[{i}].faces.{f}.{key}", key, m["views"][i]["levels"][0]))
    if _is_sha(m.get("tour")):
        wanted.setdefault(tile_key(m["tour"], "json"), []).append(("tour", "tour", 0))
    shas = {_TILE_KEY.match(k).group(1) for k in wanted}
    sent = declared(db, job)
    by_sha = uploads.blobs_by_sha(db, job.account_id, sorted(shas & sent))
    blobs: dict = {}
    views = {v["view"] for v in m["views"]}
    for store_key in sorted(wanted):
        sha = _TILE_KEY.match(store_key).group(1)
        blob = by_sha.get(sha)
        if blob is not None:
            blobs[store_key] = blob
            source, size = blob.storage_key, blob.bytes
        else:
            info = store.stat(store_key)
            if info is None:
                if not wanted[store_key]:
                    e.add("output", "file_missing", "This tile is not complete in the output upload.", sha256=sha)
                for path, _, _ in wanted[store_key]:
                    e.add(path, "file_missing", "This file is not complete in the output upload.", sha256=sha)
                continue
            source, size = store_key, info.size
        checked: dict[tuple[str, int], str | None] = {}
        for path, key, px in wanted[store_key]:
            if (key, px) not in checked:
                if key == "tour":
                    checked[(key, px)] = _check_tour(store, source, size, views)
                elif key == "ids":
                    checked[(key, px)] = _check_ids(store, source, size)
                else:
                    checked[(key, px)] = _check_png(store, source, key, px)
            if checked[(key, px)]:
                e.add(path, key, checked[(key, px)], sha256=sha)
    before_of = _base_faces(base)
    for i, vid, f, face in faces_of(m):
        fp = f"views[{i}].faces.{f}"
        before = before_of.get((vid, f))
        if not face["rendered"]:
            if (before or {}).get("tiles") != face["tiles"]:
                e.add(fp, "carried", "A carried face keeps the base manifest's tiles.")
            for key in FACE_FILES:
                if key in face and face[key] != (before or {}).get(key):
                    e.add(f"{fp}.{key}", "carried", f"A carried face keeps the base manifest's {key}.")
        version, op_seq = expected_version(job, face, before, base)
        if "version" in face and face["version"] != version:
            e.add(f"{fp}.version", "version", f"version is {version}: 1 on the set's first render, + 1 each time a tiles job renders the face.")
        if "op_seq" in face and face["op_seq"] != op_seq:
            e.add(f"{fp}.op_seq", "op_seq", f"op_seq is {op_seq}: the at_seq of the job that last rendered the face.")
    return e.items, blobs


def settled(m: dict, job: RenderJob, base: dict | None) -> dict:
    """The manifest as stored (1.4): every face with its version and op_seq,
    a carried face with the base's files, an update without a tour with the
    base's. Keys the worker sent stay as sent (5.9 checked them)."""
    out = copy.deepcopy(m)
    before_of = _base_faces(base)
    for _, vid, f, face in faces_of(out):
        before = before_of.get((vid, f))
        if not face["rendered"] and before is not None:
            for key in FACE_FILES:
                if key not in face and _is_sha(before.get(key)):
                    face[key] = before[key]
        version, op_seq = expected_version(job, face, before, base)
        face.setdefault("version", version)
        face.setdefault("op_seq", op_seq)
    if "tour" not in out and base is not None and job.kind == "tiles" and _is_sha(base.get("tour")):
        out["tour"] = base["tour"]
    return out


def publish_tiles(db: Session, blobs: dict, now: datetime) -> int:
    """Copy each uploaded file (by its store key: a tile, 1.4's png and json)
    into the public store once (again when the stored copy is old, so a
    running collector cannot take it)."""
    store = get_store()
    copied = 0
    for key, blob in blobs.items():
        info = store.stat(key)
        modified = info.modified_at if info is not None else None
        if modified is not None and modified.tzinfo is None:
            modified = modified.replace(tzinfo=timezone.utc)
        if info is None or (modified is not None and modified < now - REFRESH_AFTER):
            with store.open(blob.storage_key) as fh:
                store.put(key, fh, content_type=MEDIA_TYPES[key.rsplit(".", 1)[1]], cache_control=IMMUTABLE)
            copied += 1
    return copied


def verify_pack(db: Session, job: RenderJob, m: dict) -> tuple[list[dict], dict]:
    e = _Errors()
    shas = [f["sha256"] for f in m["files"]]
    sent = declared(db, job)
    blobs = uploads.blobs_by_sha(db, job.account_id, [s for s in shas if s in sent])
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


# --- render.tiles.gc ---------------------------------------------------------------------


def referenced(db: Session, now: datetime) -> set[str]:
    """The store keys (tiles, 1.4's png and json) named by a manifest of the
    last 90 days or by any set's newest."""
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
    # The bases of jobs not finished yet: their carried faces must survive.
    for base in db.scalars(
        select(RenderJob.base_job_id).where(
            RenderJob.base_job_id.is_not(None), RenderJob.state.in_(("queued", "claimed", "running"))
        )
    ):
        keys.add(manifest_key(base))
    out: set[str] = set()
    for key in keys:
        m = read_json(key)
        if m and m.get("schema", "").startswith("truebex-tiles/"):
            try:
                out |= all_files(m)
            except (KeyError, TypeError, AttributeError):
                continue
    return out


def gc(db: Session, now: datetime) -> int:
    keep = referenced(db, now)
    store = get_store()
    removed = 0
    for info in store.list("tiles/"):
        match = _TILE_KEY.match(info.key)
        if match is None or info.key in keep:
            continue
        if info.modified_at is not None and info.modified_at > now - GC_GRACE:
            continue  # a job may be completing with it right now
        store.delete(info.key)
        removed += 1
    return removed
