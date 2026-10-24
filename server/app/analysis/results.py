"""Analysis results (contract render-jobs §6.3, `truebex-analysis/1`; PF11, PF11c).

A worker completes an analysis with the result JSON; its arrays (and the
report PDF) are separate files named by SHA-256 in the claim's `job-output`
upload. `check` applies §6.3's rules (422 `output_invalid` with
`data.errors[]`), `verify` checks every named file is complete in the upload
with the size its declaration implies (a field's `count` × components ×
item size; 16 bytes an entity), `publish` copies the files under
`jobs/{job_id}/files/<sha256>` (private) and 5.5 serves the result with a
signed URL for each (`sign`).

1.2.0 (AN3) adds the kinds' own rules: a wind result's summary
(max_speed_ms, max_speed_ratio, iterations, residual), its field
pressure_coefficient on faces and its three pedestrian grids (speed_ratio,
velocity with 3 components, comfort_lawson) at the job's pedestrian height
with a cell of grid_cell_mm or coarser; an airflow result's air_changes on
spaces (one per room), opening_flow on openings (one per opening) and its
velocity grid. 5.5 answers the top-level `files` map the app reads
({sha256: {"url", "bytes"}}, §6.3; a worker's own `files` key is dropped at
completion) with PF11's `urls` and `urls_expire_at` kept beside it.

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
ON = ("faces", "spaces", "points", "openings")
UNITS = ("1", "Pa", "m/s", "kWh", "kWh/m2", "kWh/m2/y", "W", "W/m2", "degC", "K", "s", "dB", "dB(A)", "class", "%", "m", "m2", "m3/h", "1/h", "lux", "m3/s")
DTYPES = {"float32": 4, "uint8": 1, "uint16": 2, "int32": 4}
MAX_ARRAYS = 64
MAX_COUNT = 5_000_000
MAX_GRID = 4_000
ENERGY_SUMMARY = ("eui_kwh_m2_y", "heating_kwh_y", "cooling_kwh_y")
WIND_SUMMARY = ("max_speed_ms", "max_speed_ratio", "iterations", "residual")
# §6.5.2's pedestrian grids: unit, components, item type.
WIND_GRIDS = {"speed_ratio": ("1", 1, "float32"), "velocity": ("m/s", 3, "float32"), "comfort_lawson": ("class", 1, "uint8")}
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
    elif job.kind == "wind":
        for key in WIND_SUMMARY:
            if not _num(summary.get(key)):
                e.add(f"summary.{key}", "wind", f"a wind result's summary has {', '.join(WIND_SUMMARY)} (§6.5.2).")
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
    if job.kind == "wind":
        _check_wind(e, fields, grids, job.params or {})
    elif job.kind == "airflow":
        _check_airflow(e, fields, grids, job.inputs or {})
    return e.items


def _named(items: list) -> dict:
    return {x.get("name"): (i, x) for i, x in enumerate(items) if isinstance(x, dict)}


def _check_grid(e: _Errors, i: int, g: dict, name: str, unit: str, components: int, dtype: str) -> None:
    if g.get("unit") != unit:
        e.add(f"grids[{i}].unit", "layout", f"{name}'s unit is {unit}.")
    if g.get("components", 1) != components:
        e.add(f"grids[{i}].components", "layout", f"{name} holds {components} value(s) a cell.")
    if g.get("dtype", "uint8" if g.get("unit") == "class" else "float32") != dtype:
        e.add(f"grids[{i}].dtype", "layout", f"{name} is {dtype}.")


def _check_wind(e: _Errors, fields: list, grids: list, params: dict) -> None:
    """§6.5.2: pressure_coefficient on faces; speed_ratio, velocity and
    comfort_lawson at the pedestrian height (origin_mm's z), each cell
    grid_cell_mm or coarser (a runner may coarsen a grid too large to sample)."""
    found = _named(fields).get("pressure_coefficient")
    if found is None:
        e.add("fields", "wind", "a wind result has the field pressure_coefficient (unit 1, on faces).")
    elif found[1].get("on") != "faces" or found[1].get("unit") != "1":
        e.add(f"fields[{found[0]}]", "wind", "pressure_coefficient is on faces, unit 1.")
    by_name = _named(grids)
    height_mm = float(params.get("pedestrian_height_m", 1.5)) * 1000
    cell_mm = float(params.get("grid_cell_mm", 1000))
    for name, (unit, components, dtype) in WIND_GRIDS.items():
        if name not in by_name:
            e.add("grids", "wind", f"a wind result has the grid {name} (§6.5.2).")
            continue
        i, g = by_name[name]
        _check_grid(e, i, g, name, unit, components, dtype)
        origin = g.get("origin_mm")
        if isinstance(origin, list) and len(origin) == 3 and _num(origin[2]) and abs(origin[2] - height_mm) > 1.0:
            e.add(f"grids[{i}].origin_mm", "layout", f"origin_mm's z is the sampling height, the job's pedestrian_height_m ({height_mm:g} mm).")
        if _num(g.get("cell_mm")) and g["cell_mm"] < cell_mm - 1e-6:
            e.add(f"grids[{i}].cell_mm", "layout", f"cell_mm is the job's grid_cell_mm ({cell_mm:g}) or coarser.")


def _check_airflow(e: _Errors, fields: list, grids: list, meta: dict) -> None:
    """§6.5.3: air_changes on spaces (one per room, in the rooms' order),
    opening_flow on openings (one per opening) and the velocity grid."""
    by_name = _named(fields)
    for name, unit, on, key in (("air_changes", "1/h", "spaces", "rooms"), ("opening_flow", "m3/s", "openings", "openings")):
        n = meta.get(key)
        if name not in by_name:
            if n != 0:
                e.add("fields", "airflow", f"an airflow result has the field {name} ({unit}, on {on}).")
            continue
        i, f = by_name[name]
        if f.get("on") != on or f.get("unit") != unit:
            e.add(f"fields[{i}]", "airflow", f"{name} is on {on}, unit {unit}.")
        if isinstance(n, int) and f.get("count") != n:
            e.add(f"fields[{i}].count", "count", f"{name} has one value per {key[:-1]} of the rooms file ({n}).", expected=n)
        if not _sha(f.get("entities")):
            e.add(f"fields[{i}].entities", "entities", f"{name} names each {key[:-1]} (16 bytes each).")
    grid = _named(grids).get("velocity")
    if grid is None:
        if meta.get("openings") != 0:
            e.add("grids", "airflow", "an airflow result has the grid velocity (m/s, 3 components).")
    else:
        _check_grid(e, grid[0], grid[1], "velocity", "m/s", 3, "float32")


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
    """5.5: the `files` map {sha256: {"url", "bytes"}} for every file the result
    names (§6.3, what the app reads), and PF11's `urls` {sha256: url} beside it
    (PF11's own readers: demo_analysis.py and the tests), valid `ttl` seconds."""
    store = get_store()
    source = job.output_key.rsplit("/", 1)[0] if job.output_key else f"jobs/{job.job_id}"
    files, urls = {}, {}
    for sha, size in named_files(data).items():
        key = f"{source}/files/{sha}"
        urls[sha] = store.signed_get_url(key, expires_in=ttl, filename="report.pdf" if sha == data.get("report") else None)
        if size is None or size < 0:
            info = store.stat(key)
            size = info.bytes if info is not None else None
        files[sha] = {"url": urls[sha], "bytes": size}
    data["files"] = files
    data["urls"] = urls
    data["urls_expire_at"] = clock.rfc3339(clock.now() + timedelta(seconds=ttl))


def stored(output: dict) -> dict:
    """The result as the platform keeps it: a worker's own `files` key goes (the
    platform fills the map in 5.5; §6.3 says the worker omits it)."""
    out = dict(output)
    out.pop("files", None)
    return out


def platform_inputs(db: Session, job: RenderJob, ttl: int) -> dict:
    """Files the platform adds to a claim's inputs: the energy job's weather; an
    airflow job's wind geometry and the wind job's pressure_coefficient values
    (None when gone: the claim then fails `bad_input`)."""
    if job.kind == "energy":
        return {"weather": weather.claim_file(db, (job.params or {}).get("weather", ""), ttl)}
    if job.kind == "airflow":
        return _wind_files(db, job, ttl)
    return {}


def _wind_files(db: Session, job: RenderJob, ttl: int) -> dict:
    store = get_store()
    out: dict = {"wind_geometry": None, "wind_pressure_coefficient": None}
    wind = db.get(RenderJob, job.base_job_id) if job.base_job_id else None
    if wind is None or wind.state != "succeeded" or wind.output_key is None or wind.account_id != job.account_id:
        return out
    geometry = ((wind.inputs or {}).get("files") or {}).get("geometry")
    blob = uploads.blobs_by_sha(db, wind.account_id, [geometry]).get(geometry) if geometry else None
    if blob is not None:
        out["wind_geometry"] = {"sha256": geometry, "bytes": int(blob.bytes), "url": store.signed_get_url(blob.storage_key, expires_in=ttl)}
    result = tiles.read_json(wind.output_key) or {}
    cp = next((f for f in result.get("fields") or [] if isinstance(f, dict) and f.get("name") == "pressure_coefficient"), None)
    if cp is not None and _sha(cp.get("values")):
        key = f"{wind.output_key.rsplit('/', 1)[0]}/files/{cp['values']}"
        info = store.stat(key)
        if info is not None:
            out["wind_pressure_coefficient"] = {"sha256": cp["values"], "bytes": info.bytes, "url": store.signed_get_url(key, expires_in=ttl)}
    return out
