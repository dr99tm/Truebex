"""Shared helpers for the analysis tests (PF11, contract render-jobs §5.1, §6.3)."""

import hashlib
import json
import struct

from .project_helpers import hex32, upload
from .render_helpers import RJ


def octahedron_stl(width_m: float = 10.0, height_m: float = 7.0) -> bytes:
    """A binary STL in metres with 8 triangles (the fixture result's count):
    a 10 m wide, 7 m high double pyramid standing on the ground."""
    w, h = width_m / 2, height_m
    mid = h / 2
    ring = [(w, 0, mid), (0, w, mid), (-w, 0, mid), (0, -w, mid)]
    top, bottom = (0, 0, h), (0, 0, 0)
    tris = []
    for i in range(4):
        a, b = ring[i], ring[(i + 1) % 4]
        tris.append((a, b, top))
        tris.append((b, a, bottom))
    out = bytearray(b"truebex test octahedron".ljust(80, b" "))
    out += struct.pack("<I", len(tris))
    for t in tris:
        out += struct.pack("<3f", 0, 0, 0)
        for v in t:
            out += struct.pack("<3f", *v)
        out += struct.pack("<H", 0)
    return bytes(out)


def entities(n: int = 8) -> bytes:
    return b"".join(bytes.fromhex(f"0199c6a2e000700180000000000000{i:02x}") for i in range(1, n + 1))


def epjson(zones: int = 10, timesteps: int = 4) -> bytes:
    model = {
        "Version": {"Version 1": {"version_identifier": "24.2"}},
        "Timestep": {"Timestep 1": {"number_of_timesteps_per_hour": timesteps}},
        "Zone": {f"{i:032x}": {"direction_of_relative_north": 0} for i in range(1, zones + 1)},
    }
    return json.dumps(model).encode()


def rooms_file() -> bytes:
    def box(x0, y0, z0, x1, y1, z1, a):
        quads = [
            [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0]],
            [[x0, y0, z1], [x0, y1, z1], [x1, y1, z1], [x1, y0, z1]],
            [[x0, y0, z0], [x0, y0, z1], [x1, y0, z1], [x1, y0, z0]],
            [[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]],
            [[x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1]],
            [[x1, y0, z0], [x1, y0, z1], [x1, y1, z1], [x1, y1, z0]],
        ]
        return [{"vertices_m": q, "absorption": a, "scattering": 0.1} for q in quads]

    return json.dumps({
        "schema": "truebex-acoustics-rooms/1",
        "rooms": [{"id": "0199c6a2e00070028000000000000001", "name": "Study", "surfaces": box(0, 0, 0, 4, 3, 2.7, 0.2)}],
    }).encode()


def epw(city: str = "London Heathrow") -> bytes:
    head = f"LOCATION,{city},ENG,GBR,TMYx,037720,51.48,-0.45,0.0,25.0\n"
    return (head + "DESIGN CONDITIONS,0\n" + "1990,1,1,1,0,?,5.0,3.0,80,101000\n" * 24).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put_inputs(client, headers: dict, *files: bytes) -> None:
    upload(client, headers, list(files), purpose="job-input")


def submit(client, headers: dict, body: dict):
    return client.post("/jobs", json=body, headers={**headers, **RJ, "Idempotency-Key": hex32()})


def wind_body(geometry: bytes, **params) -> dict:
    return {
        "kind": "wind",
        "inputs": {"upload_id": None, "files": {"geometry": sha(geometry)}},
        "params": {"speed_ms": 5, "direction_deg": 225, "reference_height_m": 10, "terrain": "suburban", "comfort": "lawson", **params},
    }
