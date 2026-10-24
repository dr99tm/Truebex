"""Reading an analysis job's uploaded inputs at submission (PF11, PF11c).

The estimate needs a little of each file and a bad file is cheaper to refuse
now than after a worker has queued it: a binary STL's triangle count and
bounds, an epJSON model's zones and timesteps, a rooms file's rooms. Files
come from the account's `job-input` blobs (share-bundle §5).

A wind job's `geometry` (render-jobs 1.2.0 §6.5.2) holds at most 200 000
triangles and must be closed: every undirected edge, by exact vertex
coordinates, lies on an even number of triangles, so nothing is open
(`open_edges`: an edge on one triangle, or on three). An edge on four or more
(`over_shared_edges`) is where closed solids touch, as the kernel massing the
app exports without its 3D tool does (and the app's own wind-geometry.bin:
12 such edges); the mesher takes touching solids, so those are counted, not
refused (PF11c's reading of "every edge on exactly two triangles"). Winding
is the runner's concern. `surroundings` and `terrain` are read as STLs only
(the terrain is an open surface by definition).
"""

import json
import math
import re
import struct
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..storage import get_store
from ..uploads import service as uploads
from .validation import invalid

MAX_TRIANGLES = 1_000_000
MAX_GEOMETRY_TRIANGLES = 200_000
MAX_JSON_BYTES = 64 * 1024 * 1024
_TRI = struct.Struct("<12fH")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
ROOMS_SCHEMA = "truebex-airflow-rooms/1"
MAX_ROOMS = 1000
MAX_OPENINGS = 5000
MAX_VOLUME_M3 = 1_000_000.0
MAX_AREA_M2 = 1000.0
MAX_CP = 10.0
RHO_RANGE = (0.5, 2.0)
COORD_MAX_M = 100_000.0


@dataclass(frozen=True)
class Mesh:
    triangles: int
    min_xyz: tuple[float, float, float]
    max_xyz: tuple[float, float, float]
    open_edges: int = 0
    over_shared_edges: int = 0

    @property
    def height_m(self) -> float:
        return self.max_xyz[2] - self.min_xyz[2]

    @property
    def footprint_m(self) -> float:
        return max(self.max_xyz[0] - self.min_xyz[0], self.max_xyz[1] - self.min_xyz[1])


def blob_of(db: Session, account_id: int, sha: str):
    blob = uploads.blobs_by_sha(db, account_id, [sha]).get(sha)
    if blob is None:
        raise invalid("inputs.files", "every file is uploaded first (purpose job-input)", missing=[sha])
    return blob


def read_stl(fh, size: int, field: str, *, max_triangles: int = MAX_TRIANGLES, closed: bool = False) -> Mesh:
    """Bounds of a binary STL (80-byte header, uint32 count, 50 bytes a triangle);
    with `closed`, its edges are counted too and an open one is refused."""
    head = fh.read(84)
    if len(head) < 84:
        raise invalid(field, "a binary STL file")
    (n,) = struct.unpack("<I", head[80:84])
    if size != 84 + 50 * n or n == 0:
        raise invalid(field, "a binary STL file (the size does not match its triangle count)")
    if n > max_triangles:
        raise invalid(field, f"at most {max_triangles} triangles", triangles=n, limit=max_triangles)
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    vertex_ids: dict[tuple[float, float, float], int] = {}
    edges: dict[int, int] = {}
    left = n
    while left:
        take = min(left, 20_000)
        chunk = fh.read(50 * take)
        if len(chunk) != 50 * take:
            raise invalid(field, "a binary STL file (it ends early)")
        for i in range(take):
            values = _TRI.unpack_from(chunk, i * 50)
            corner = []
            for v in range(3, 12, 3):
                x, y, z = values[v], values[v + 1], values[v + 2]
                if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                    raise invalid(field, "finite vertex coordinates")
                if x < lo[0]:
                    lo[0] = x
                if x > hi[0]:
                    hi[0] = x
                if y < lo[1]:
                    lo[1] = y
                if y > hi[1]:
                    hi[1] = y
                if z < lo[2]:
                    lo[2] = z
                if z > hi[2]:
                    hi[2] = z
                if closed:
                    corner.append(vertex_ids.setdefault((x, y, z), len(vertex_ids)))
            if closed:
                for a, b in ((corner[0], corner[1]), (corner[1], corner[2]), (corner[2], corner[0])):
                    key = a * (4 * max_triangles) + b if a < b else b * (4 * max_triangles) + a
                    edges[key] = edges.get(key, 0) + 1
        left -= take
    open_edges = sum(1 for c in edges.values() if c % 2) if closed else 0
    over_shared = sum(1 for c in edges.values() if c > 2 and not c % 2) if closed else 0
    if open_edges:
        raise invalid(
            field,
            f"one closed surface: {open_edges} edges lie on an odd number of triangles (every edge is on two)",
            open_edges=open_edges, over_shared_edges=over_shared, triangles=n,
        )
    return Mesh(triangles=n, min_xyz=(lo[0], lo[1], lo[2]), max_xyz=(hi[0], hi[1], hi[2]),
                open_edges=open_edges, over_shared_edges=over_shared)


def stl(db: Session, account_id: int, sha: str, field: str, **kw) -> Mesh:
    blob = blob_of(db, account_id, sha)
    with get_store().open(blob.storage_key) as fh:
        return read_stl(fh, int(blob.bytes), field, **kw)


def _json(db: Session, account_id: int, sha: str, field: str) -> dict:
    blob = blob_of(db, account_id, sha)
    if int(blob.bytes) > MAX_JSON_BYTES:
        raise invalid(field, f"at most {MAX_JSON_BYTES // (1024 * 1024)} MB")
    with get_store().open(blob.storage_key) as fh:
        try:
            data = json.loads(fh.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise invalid(field, "a JSON file")
    if not isinstance(data, dict):
        raise invalid(field, "a JSON object")
    return data


def energy_model(db: Session, account_id: int, sha: str, default_tph: int) -> tuple[int, int]:
    """(zones, timesteps per hour) of an epJSON model."""
    model = _json(db, account_id, sha, "inputs.files.model")
    zones = model.get("Zone")
    if not isinstance(zones, dict) or not zones:
        raise invalid("inputs.files.model", "an epJSON model with at least one Zone")
    tph = default_tph
    step = model.get("Timestep")
    if isinstance(step, dict) and step:
        value = next(iter(step.values()))
        if isinstance(value, dict) and isinstance(value.get("number_of_timesteps_per_hour"), int):
            tph = max(1, min(60, value["number_of_timesteps_per_hour"]))
    return len(zones), tph


def rooms(db: Session, account_id: int, sha: str) -> int:
    """The rooms file AN4 writes: {"rooms": [{"id", "surfaces": [{"vertices_m", "absorption"}]}]}."""
    data = _json(db, account_id, sha, "inputs.files.rooms")
    found = data.get("rooms")
    if not isinstance(found, list) or not found:
        raise invalid("inputs.files.rooms", "a rooms file with at least one room")
    for i, room in enumerate(found):
        surfaces = room.get("surfaces") if isinstance(room, dict) else None
        if not isinstance(surfaces, list) or len(surfaces) < 4:
            raise invalid("inputs.files.rooms", f"rooms[{i}] needs at least 4 surfaces")
    return len(found)


def entities_match(db: Session, account_id: int, sha: str, triangles: int) -> None:
    blob = blob_of(db, account_id, sha)
    if int(blob.bytes) != 16 * triangles:
        raise invalid("inputs.files.entities", "16 bytes per triangle of the geometry, in its order", triangles=triangles)


# --- the airflow rooms file (render-jobs 1.2.0 §6.5.3) ------------------------------------------


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _vector(value: object) -> bool:
    return isinstance(value, list) and len(value) == 3 and all(_finite(v) and abs(v) <= COORD_MAX_M for v in value)


def check_rooms(data: object) -> tuple[int, int]:
    """(rooms, openings) of a `truebex-airflow-rooms/1` file, or the first broken
    rule as `ValueError(path, message)`. Rooms: 1 to 1000, unique 32-hex ids,
    volume_m3 above 0 (at most 10^6), floor_z_m a number when given. Openings:
    up to 5000, 32-hex ids; `from` and `to` each a room id or "outside" (the
    app writes side 0 -> side 1, so either may be outside, never both, never the
    same room); area_m2 above 0 (at most 1000), cd in (0, 1], centre_m and
    normal 3 numbers each (|x| <= 10^5 m, the normal not zero), z_m a number
    when given, cp (a number, |cp| <= 10) only where one side is outside.
    rho_kg_m3 defaults to 1.2, else 0.5 to 2."""
    if not isinstance(data, dict):
        raise ValueError("rooms", "a JSON object")
    if data.get("schema") != ROOMS_SCHEMA:
        raise ValueError("schema", ROOMS_SCHEMA)
    rooms = data.get("rooms")
    if not isinstance(rooms, list) or not 1 <= len(rooms) <= MAX_ROOMS:
        raise ValueError("rooms", f"1 to {MAX_ROOMS} rooms")
    ids: set[str] = set()
    for i, room in enumerate(rooms):
        path = f"rooms[{i}]"
        if not isinstance(room, dict):
            raise ValueError(path, "a room object")
        rid = room.get("id")
        if not isinstance(rid, str) or not _HEX32.match(rid):
            raise ValueError(f"{path}.id", "the room's 32-hex entity id")
        if rid in ids:
            raise ValueError(f"{path}.id", "a room id used once")
        ids.add(rid)
        volume = room.get("volume_m3")
        if not _finite(volume) or not 0 < volume <= MAX_VOLUME_M3:
            raise ValueError(f"{path}.volume_m3", f"the air volume in m3, above 0 and at most {MAX_VOLUME_M3:.0f}")
        if "floor_z_m" in room and room["floor_z_m"] is not None and not _finite(room["floor_z_m"]):
            raise ValueError(f"{path}.floor_z_m", "the floor's height in metres")
        if room.get("name") is not None and not isinstance(room.get("name"), str):
            raise ValueError(f"{path}.name", "a name")
    openings = data.get("openings", [])
    if not isinstance(openings, list) or len(openings) > MAX_OPENINGS:
        raise ValueError("openings", f"a list of at most {MAX_OPENINGS} openings")
    for i, op in enumerate(openings):
        path = f"openings[{i}]"
        if not isinstance(op, dict):
            raise ValueError(path, "an opening object")
        if not isinstance(op.get("id"), str) or not _HEX32.match(op["id"]):
            raise ValueError(f"{path}.id", "the opening's 32-hex entity id")
        src, dst = op.get("from"), op.get("to")
        if src != "outside" and src not in ids:
            raise ValueError(f"{path}.from", "a room id of this file, or outside")
        if dst != "outside" and dst not in ids:
            raise ValueError(f"{path}.to", "a room id of this file, or outside")
        if src == "outside" and dst == "outside":
            raise ValueError(f"{path}.from", "a room on one side at least (both sides are outside)")
        if src == dst:
            raise ValueError(f"{path}.to", "the room on the other side (from and to name the same room)")
        area = op.get("area_m2")
        if not _finite(area) or not 0 < area <= MAX_AREA_M2:
            raise ValueError(f"{path}.area_m2", f"the open area in m2, above 0 and at most {MAX_AREA_M2:.0f}")
        cd = op.get("cd")
        if not _finite(cd) or not 0 < cd <= 1:
            raise ValueError(f"{path}.cd", "the discharge coefficient, above 0 and at most 1")
        if not _vector(op.get("centre_m")):
            raise ValueError(f"{path}.centre_m", "[x, y, z] in metres in the export frame")
        normal = op.get("normal")
        if not _vector(normal) or math.sqrt(sum(v * v for v in normal)) < 1e-9:
            raise ValueError(f"{path}.normal", "[x, y, z], the direction from `from` to `to` (not zero)")
        if op.get("z_m") is not None and not _finite(op.get("z_m")):
            raise ValueError(f"{path}.z_m", "the opening's height in metres")
        if "cp" in op and op["cp"] is not None:
            if "outside" not in (src, dst):
                raise ValueError(f"{path}.cp", "only on an opening to outside (an inside opening has no outdoor pressure)")
            if not _finite(op["cp"]) or abs(op["cp"]) > MAX_CP:
                raise ValueError(f"{path}.cp", f"a pressure coefficient from -{MAX_CP:.0f} to {MAX_CP:.0f}")
    rho = data.get("rho_kg_m3", 1.2)
    if not _finite(rho) or not RHO_RANGE[0] <= rho <= RHO_RANGE[1]:
        raise ValueError("rho_kg_m3", f"the air density, {RHO_RANGE[0]} to {RHO_RANGE[1]} kg/m3")
    return len(rooms), len(openings)


def airflow_rooms(db: Session, account_id: int, sha: str) -> tuple[int, int]:
    """(rooms, openings) of an airflow job's rooms file, or 422 on inputs.files.rooms."""
    data = _json(db, account_id, sha, "inputs.files.rooms")
    try:
        return check_rooms(data)
    except ValueError as exc:
        path, message = exc.args
        raise invalid("inputs.files.rooms", f"{path}: {message}", path=path) from None
