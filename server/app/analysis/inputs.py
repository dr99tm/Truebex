"""Reading an analysis job's uploaded inputs at submission (PF11).

The estimate needs a little of each file and a bad file is cheaper to refuse
now than after a worker has queued it: a binary STL's triangle count and
bounds, an epJSON model's zones and timesteps, a rooms file's rooms. Files
come from the account's `job-input` blobs (share-bundle §5).
"""

import json
import math
import struct
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..storage import get_store
from ..uploads import service as uploads
from .validation import invalid

MAX_TRIANGLES = 1_000_000
MAX_JSON_BYTES = 64 * 1024 * 1024
_TRI = struct.Struct("<12fH")


@dataclass(frozen=True)
class Mesh:
    triangles: int
    min_xyz: tuple[float, float, float]
    max_xyz: tuple[float, float, float]

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


def read_stl(fh, size: int, field: str) -> Mesh:
    """Bounds of a binary STL (80-byte header, uint32 count, 50 bytes a triangle)."""
    head = fh.read(84)
    if len(head) < 84:
        raise invalid(field, "a binary STL file")
    (n,) = struct.unpack("<I", head[80:84])
    if size != 84 + 50 * n or n == 0:
        raise invalid(field, "a binary STL file (the size does not match its triangle count)")
    if n > MAX_TRIANGLES:
        raise invalid(field, f"at most {MAX_TRIANGLES} triangles", triangles=n)
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    left = n
    while left:
        take = min(left, 20_000)
        chunk = fh.read(50 * take)
        if len(chunk) != 50 * take:
            raise invalid(field, "a binary STL file (it ends early)")
        for i in range(take):
            values = _TRI.unpack_from(chunk, i * 50)
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
        left -= take
    return Mesh(triangles=n, min_xyz=(lo[0], lo[1], lo[2]), max_xyz=(hi[0], hi[1], hi[2]))


def stl(db: Session, account_id: int, sha: str, field: str) -> Mesh:
    blob = blob_of(db, account_id, sha)
    with get_store().open(blob.storage_key) as fh:
        return read_stl(fh, int(blob.bytes), field)


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
