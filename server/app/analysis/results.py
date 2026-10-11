"""Analysis results (contract render-jobs §6.3, `truebex-analysis/1`; PF11).

A worker completes an analysis with the result JSON; its arrays (and the
report PDF) are separate files named by SHA-256 in the claim's `job-output`
upload. `check` applies §6.3's rules (422 `output_invalid` with
`data.errors[]`), `verify` checks every named file is complete in the upload
with the size its declaration implies (a field's `count` × components ×
item size; 16 bytes an entity), `publish` copies the files under
`jobs/{job_id}/files/<sha256>` (private) and 5.5 serves the result with a
signed URL for each (`sign`).

The texture kind's output (`truebex-texture/1`, PF11's proposal) is checked
here too: one PNG per requested map at the requested size.
"""

import math
import re
from datetime import timedelta

from sqlalchemy.orm import Session

from ..licence import clock
from ..render import tiles
from ..render.models import RenderJob
from ..storage import get_store
from ..uploads import service as uploads
from . import kinds, weather

SCHEMA = "truebex-analysis/1"
TEXTURE_SCHEMA = "truebex-texture/1"
ON = ("faces", "spaces", "points")
UNITS = ("1", "Pa", "m/s", "kWh", "kWh/m2", "kWh/m2/y", "W", "W/m2", "degC", "K", "s", "dB", "dB(A)", "class", "%", "m", "m2", "m3/h", "1/h", "lux")
DTYPES = {"float32": 4, "uint8": 1, "uint16": 2, "int32": 4}
MAX_ARRAYS = 64
MAX_COUNT = 5_000_000
MAX_GRID = 4_000
ENERGY_SUMMARY = ("eui_kwh_m2_y", "heating_kwh_y", "cooling_kwh_y")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class _Errors:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, path: str, rule: str, message: str, **extra) -> None:
        if len(self.items) < 100:
            self.items.append({"path": path, "rule": rule, "message": message, **extra})


def _int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA.match(value))


def handles_output(data: dict) -> bool:
    schema = str(data.get("schema", ""))
    return schema.startswith("truebex-analysis/") or schema.startswith("truebex-texture/")


# --- the files a result names and their sizes ------------------------------------------------


def named_files(m: dict) -> dict[str, int | None]:
    """{sha256: expected bytes (None = any)} for every file the output names."""
    out: dict[str, int | None] = {}

    def want(sha: object, size: int | None) -> None:
        if _sha(sha):
            if sha in out and out[sha] is not None and size is not None and out[sha] != size:
                out[sha] = -1  # the same file declared with two sizes: never matches
            else:
                out.setdefault(sha, size)

    if m.get("schema") == TEXTURE_SCHEMA:
        for entry in m.get("maps") or []:
            if isinstance(entry, dict):
                want(entry.get("sha256"), None)
        return out
    for f in m.get("fields") or []:
        if not isinstance(f, dict) or not _int(f.get("count")):
            continue
        item = DTYPES.get(f.get("dtype", "float32"), 4) * (f.get("components", 1) if _int(f.get("components", 1)) else 1)
        want(f.get("values"), f["count"] * item)
        if f.get("entities") is not None:
            want(f.get("entities"), f["count"] * 16)
        if f.get("positions") is not None:
            want(f.get("positions"), f["count"] * 12)
    for g in m.get("grids") or []:
        if not isinstance(g, dict) or not (_int(g.get("nx")) and _int(g.get("ny"))):
            continue
        default = "uint8" if g.get("unit") == "class" else "float32"
        item = DTYPES.get(g.get("dtype", default), 4) * (g.get("components", 1) if _int(g.get("components", 1)) else 1)
        want(g.get("values"), g["nx"] * g["ny"] * item)
    if m.get("report") is not None:
        want(m.get("report"), None)
    return out


# --- §6.3 rules -------------------------------------------------------------------------------


def _check_array_meta(e: _Errors, path: str, a: dict, default_dtype: str) -> None:
    dtype = a.get("dtype", default_dtype)
    if dtype not in DTYPES:
        e.add(f"{path}.dtype", "dtype", f"dtype is one of {', '.join(DTYPES)}.")
    components = a.get("components", 1)
    if not _int(components) or not 1 <= components <= 4:
        e.add(f"{path}.components", "components", "components is 1 to 4.")
    if a.get("unit") not in UNITS:
        e.add(f"{path}.unit", "unit", f"unit is an SI string ({', '.join(UNITS[:6])}, …).")
    if not _sha(a.get("values")):
        e.add(f"{path}.values", "sha256", "values names its array file by SHA-256.")


def _check_texture(e: _Errors, m: dict, job: RenderJob) -> None:
    params = job.params or {}
    if m.get("params") != params:
        e.add("params", "job", "params are the job's, as submitted.")
    maps = m.get("maps")
    if not isinstance(maps, list) or not maps:
        e.add("maps", "type", "maps lists the generated maps.")
        return
    seen = set()
    for i, entry in enumerate(maps):
        path = f"maps[{i}]"
        if not isinstance(entry, dict):
            e.add(path, "type", "a map is an object.")
            continue
        name = entry.get("name")
        if name not in params.get("maps", []) or name in seen:
            e.add(f"{path}.name", "map", "each requested map appears once.")
        seen.add(name)
        if not _sha(entry.get("sha256")):
            e.add(f"{path}.sha256", "sha256", "a map names its PNG by SHA-256.")
        if entry.get("size_px") != params.get("size"):
            e.add(f"{path}.size_px", "size", f"size_px is {params.get('size')}, the job's.")
        if entry.get("content_type", "image/png") != "image/png":
            e.add(f"{path}.content_type", "type", "maps are PNG files.")
    if seen != set(params.get("maps", [])):
        e.add("maps", "map", "every requested map is there.")


def check(m: object, job: RenderJob) -> list[dict]:
    """`data.errors[]` for 422 `output_invalid`: every rule the output breaks."""
    e = _Errors()
    if not isinstance(m, dict):
        e.add("output", "type", "The output is a JSON object (§6.3).")
        return e.items
    want = TEXTURE_SCHEMA if job.kind == kinds.TEXTURE else SCHEMA
    if m.get("schema") != want:
        e.add("schema", "schema", f"schema is {want}.")
        return e.items
    if m.get("kind") != job.kind:
        e.add("kind", "job", f"kind is {job.kind}, the job's.")
    engine = m.get("engine")
    if not isinstance(engine, dict) or not all(isinstance(engine.get(k), str) and engine.get(k) for k in ("name", "version", "image")):
        e.add("engine", "engine", "engine names the solver, its version and the image it ran in.")
    if job.kind == kinds.TEXTURE:
        if m.get("job_id") != job.job_id:
            e.add("job_id", "job", "job_id is this job's id.")
        _check_texture(e, m, job)
        return e.items
    if m.get("project_id") != job.project_id:
        e.add("project_id", "job", "project_id is the job's project (null when it named none).")
    if m.get("at_seq") != job.at_seq:
        e.add("at_seq", "job", f"at_seq is {job.at_seq}, the job's.")
    if m.get("params") != (job.params or {}):
        e.add("params", "job", "params are the job's, as submitted.")
    summary = m.get("summary")
    if not isinstance(summary, dict) or not all(isinstance(k, str) and (_num(v) or isinstance(v, str)) for k, v in summary.items()):
        e.add("summary", "summary", "summary maps names to numbers.")
    elif job.kind == "energy":
        for key in ENERGY_SUMMARY:
            if not _num(summary.get(key)):
                e.add(f"summary.{key}", "energy", f"an energy result's summary has {', '.join(ENERGY_SUMMARY)}.")
    fields = m.get("fields", [])
    grids = m.get("grids", [])
    if not isinstance(fields, list) or not isinstance(grids, list) or len(fields) > MAX_ARRAYS or len(grids) > MAX_ARRAYS:
        e.add("fields", "type", f"fields and grids are lists of at most {MAX_ARRAYS}.")
        return e.items
    if not fields and not grids:
        e.add("fields", "empty", "a result has at least one field or grid.")
    triangles = (job.inputs or {}).get("geometry_triangles")
    names: set[str] = set()
    for i, f in enumerate(fields):
        path = f"fields[{i}]"
        if not isinstance(f, dict):
            e.add(path, "type", "a field is an object.")
            continue
        if not isinstance(f.get("name"), str) or not _NAME.match(f["name"]) or f["name"] in names:
            e.add(f"{path}.name", "name", "a field has a unique lowercase name.")
        names.add(f.get("name"))
        on = f.get("on")
        if on not in ON:
            e.add(f"{path}.on", "on", f"on is one of {', '.join(ON)}.")
        count = f.get("count")
        if not _int(count) or not 1 <= count <= MAX_COUNT:
            e.add(f"{path}.count", "count", f"count is 1 to {MAX_COUNT}.")
        elif on == "faces" and isinstance(triangles, int) and count != triangles:
            e.add(f"{path}.count", "count", f"a field on faces has one value per triangle of the geometry ({triangles}).", expected=triangles)
        _check_array_meta(e, path, f, "float32")
        if on == "faces" and not _sha(f.get("entities")):
            e.add(f"{path}.entities", "entities", "a field on faces names each triangle's entity (16 bytes each).")
        elif f.get("entities") is not None and not _sha(f.get("entities")):
            e.add(f"{path}.entities", "sha256", "entities names its file by SHA-256.")
        keys = f.get("keys")
        if keys is not None and (not isinstance(keys, list) or not _int(count) or len(keys) != count or not all(isinstance(k, str) for k in keys)):
            e.add(f"{path}.keys", "count", "keys has one name per value.")
        if f.get("positions") is not None and not _sha(f.get("positions")):
            e.add(f"{path}.positions", "sha256", "positions names its file by SHA-256.")
    gnames: set[str] = set()
    for i, g in enumerate(grids):
        path = f"grids[{i}]"
        if not isinstance(g, dict):
            e.add(path, "type", "a grid is an object.")
            continue
        if not isinstance(g.get("name"), str) or not _NAME.match(g["name"]) or g["name"] in gnames:
            e.add(f"{path}.name", "name", "a grid has a unique lowercase name.")
        gnames.add(g.get("name"))
        origin = g.get("origin_mm")
        if not isinstance(origin, list) or len(origin) != 3 or not all(_num(v) for v in origin):
            e.add(f"{path}.origin_mm", "origin", "origin_mm is [x, y, z] in millimetres.")
        if not _num(g.get("cell_mm")) or g["cell_mm"] <= 0:
            e.add(f"{path}.cell_mm", "cell", "cell_mm is a positive size in millimetres.")
        nx, ny = g.get("nx"), g.get("ny")
        if not (_int(nx) and _int(ny) and 1 <= nx <= MAX_GRID and 1 <= ny <= MAX_GRID):
            e.add(f"{path}.nx", "size", f"nx and ny are 1 to {MAX_GRID}.")
        _check_array_meta(e, path, g, "uint8" if g.get("unit") == "class" else "float32")
    report = m.get("report")
    if report is not None and not _sha(report):
        e.add("report", "sha256", "report names a PDF by SHA-256, or is null.")
    return e.items


def verify(db: Session, job: RenderJob, m: dict) -> tuple[list[dict], dict]:
    """Every named file complete in the claim's output upload, at its size."""
    e = _Errors()
    wanted = named_files(m)
    sent = tiles.declared(db, job)
    blobs = uploads.blobs_by_sha(db, job.account_id, [s for s in wanted if s in sent])
    for sha, size in wanted.items():
        blob = blobs.get(sha)
        if blob is None:
            e.add("output", "file_missing", "This file is not complete in the output upload.", sha256=sha)
        elif size is not None and int(blob.bytes) != size:
            e.add("output", "file_size", f"This file is {blob.bytes} bytes; its declaration needs {size}.", sha256=sha, expected=size)
    if m.get("report") and m["report"] in blobs and blobs[m["report"]].content_type != "application/pdf":
        e.add("report", "type", "The report is a PDF (application/pdf).")
    return e.items, blobs


def file_key(job_id: str, sha: str) -> str:
    return f"jobs/{job_id}/files/{sha}"


def publish(db: Session, job: RenderJob, m: dict, blobs: dict) -> None:
    store = get_store()
    for sha, blob in blobs.items():
        with store.open(blob.storage_key) as fh:
            store.put(file_key(job.job_id, sha), fh, content_type=blob.content_type)


def sign(job: RenderJob, data: dict, ttl: int) -> None:
    """5.5: a signed URL per file the result names (`urls`), valid `ttl` seconds."""
    store = get_store()
    source = job.output_key.rsplit("/", 1)[0] if job.output_key else f"jobs/{job.job_id}"
    urls = {}
    for sha in named_files(data):
        name = "report.pdf" if sha == data.get("report") else None
        urls[sha] = store.signed_get_url(f"{source}/files/{sha}", expires_in=ttl, filename=name)
    data["urls"] = urls
    data["urls_expire_at"] = clock.rfc3339(clock.now() + timedelta(seconds=ttl))


def platform_inputs(db: Session, job: RenderJob, ttl: int) -> dict:
    """Files the platform adds to a claim's inputs: the energy job's weather."""
    if job.kind == "energy":
        return {"weather": weather.claim_file(db, (job.params or {}).get("weather", ""), ttl)}
    return {}
