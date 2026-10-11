"""The `acoustics` runner: room acoustics by stochastic energy ray tracing (PF11).

    python3 -m runners.acoustics /job

Our own tracer (no third-party solver; standard library only, deterministic
for a seed). The rooms file AN4 writes (`inputs/rooms`):

    {"schema": "truebex-acoustics-rooms/1",
     "rooms": [{"id": "<32 hex>", "name": "Study",
                "surfaces": [{"vertices_m": [[x, y, z], …], "absorption": 0.2 | [per band], "scattering": 0.1}]}]}

Per room and per source inside it (`params.sources`, by the room's bounds):
`params.rays` rays leave the source in uniformly random directions; at each
surface a ray's energy per band is multiplied by (1 − α) and it reflects
specularly, or, with the surface's scattering probability, in a cosine
(Lambert) direction; it stops after the profile's reflections or below
−60 dB. Receivers are spheres (the profile's radius) on a grid at
`receiver_height_m` above the room's floor: each segment through one adds
energy × chord length to the receiver's 1 ms histogram at its arrival time.
From the histograms: the Schroeder decay per band, T30 (−5 to −35 dB, else
T20) and EDT (0 to −10 dB), and the sound pressure level from the sources'
power levels (energy density = Σ W·e·chord / (N·c·V_receiver)), A-weighted.

Result: fields on spaces `t30_<band>` and `edt_<band>` (s, one per room;
`keys` = room names, `entities` when ids are 32 hex), grid `spl_dba` (dB(A),
NaN outside rooms) over the rooms at receiver height; summary t30_500_s,
rooms, rays.
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

if __package__ in (None, ""):  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "runners"

from . import common

RHO = 1.204
P_REF = 2e-5
W_REF = 1e-12
BIN_S = 0.001
EPS = 1e-9
A_WEIGHT = {63: -26.2, 125: -16.1, 250: -8.6, 500: -3.2, 1000: 0.0, 2000: 1.2, 4000: 1.0, 8000: -1.1}
MAX_RECEIVERS = 200


# --- geometry -----------------------------------------------------------------------------------


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    length = math.sqrt(_dot(a, a))
    return (a[0] / length, a[1] / length, a[2] / length) if length > 0 else a


@dataclass
class Tri:
    v0: tuple
    e1: tuple
    e2: tuple
    normal: tuple
    alpha: list[float]
    scattering: float
    area: float


@dataclass
class Room:
    key: str
    name: str
    tris: list[Tri]
    lo: tuple
    hi: tuple
    volume: float
    area: float
    receivers: list[tuple] = dc_field(default_factory=list)


def _alpha(value, bands: list[int], where: str) -> list[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        values = [float(value)] * len(bands)
    elif isinstance(value, list) and len(value) == len(bands):
        values = [float(v) for v in value]
    else:
        raise common.BadInput(f"{where}: absorption is a number or one per band ({len(bands)})")
    if not all(0.0 <= v <= 1.0 for v in values):
        raise common.BadInput(f"{where}: absorption is 0 to 1")
    return values


def room_from(raw: dict, bands: list[int], index: int) -> Room:
    surfaces = raw.get("surfaces")
    if not isinstance(surfaces, list) or len(surfaces) < 4:
        raise common.BadInput(f"rooms[{index}] needs at least 4 surfaces")
    tris: list[Tri] = []
    for j, s in enumerate(surfaces):
        verts = s.get("vertices_m") if isinstance(s, dict) else None
        if not isinstance(verts, list) or len(verts) < 3:
            raise common.BadInput(f"rooms[{index}].surfaces[{j}] needs at least 3 vertices")
        pts = [tuple(float(c) for c in v) for v in verts]
        alpha = _alpha(s.get("absorption", 0.1), bands, f"rooms[{index}].surfaces[{j}]")
        scattering = min(1.0, max(0.0, float(s.get("scattering", 0.1))))
        for k in range(1, len(pts) - 1):
            e1, e2 = _sub(pts[k], pts[0]), _sub(pts[k + 1], pts[0])
            n = _cross(e1, e2)
            area = math.sqrt(_dot(n, n)) / 2
            if area > EPS:
                tris.append(Tri(pts[0], e1, e2, _norm(n), alpha, scattering, area))
    lo = tuple(min(t.v0[i] + min(0.0, t.e1[i], t.e2[i]) for t in tris) for i in range(3))
    hi = tuple(max(t.v0[i] + max(0.0, t.e1[i], t.e2[i]) for t in tris) for i in range(3))
    volume = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])  # the bounds' (informative)
    key = str(raw.get("id") or raw.get("name") or f"room-{index + 1}")
    return Room(key=key, name=str(raw.get("name") or key), tris=tris, lo=lo, hi=hi, volume=volume, area=sum(t.area for t in tris))


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def place_receivers(room: Room, spacing: float, height: float, radius: float) -> None:
    z = room.lo[2] + height
    while True:
        xs = _steps(room.lo[0] + radius, room.hi[0] - radius, spacing)
        ys = _steps(room.lo[1] + radius, room.hi[1] - radius, spacing)
        if len(xs) * len(ys) <= MAX_RECEIVERS:
            break
        spacing *= 1.25
    room.receivers = [(x, y, z) for y in ys for x in xs]


def _steps(a: float, b: float, step: float) -> list[float]:
    if b <= a:
        return [(a + b) / 2]
    n = max(1, int((b - a) // step) + 1)
    start = (a + b) / 2 - (n - 1) * step / 2
    return [start + i * step for i in range(n)]


def hit(origin, d, tris: list[Tri]) -> tuple[float, Tri | None]:
    """The nearest surface along the ray (Möller–Trumbore)."""
    best, found = math.inf, None
    for t in tris:
        p = _cross(d, t.e2)
        det = _dot(t.e1, p)
        if -EPS < det < EPS:
            continue
        inv = 1.0 / det
        s = _sub(origin, t.v0)
        u = _dot(s, p) * inv
        if u < 0.0 or u > 1.0:
            continue
        q = _cross(s, t.e1)
        v = _dot(d, q) * inv
        if v < 0.0 or u + v > 1.0:
            continue
        dist = _dot(t.e2, q) * inv
        if 1e-7 < dist < best:
            best, found = dist, t
    return best, found


def _random_unit(rng: random.Random) -> tuple:
    z = rng.uniform(-1.0, 1.0)
    a = rng.uniform(0.0, 2 * math.pi)
    r = math.sqrt(1 - z * z)
    return (r * math.cos(a), r * math.sin(a), z)


def _lambert(n: tuple, rng: random.Random) -> tuple:
    """A cosine-weighted direction around the normal n."""
    u1, u2 = rng.random(), rng.random()
    r, phi = math.sqrt(u1), 2 * math.pi * u2
    local = (r * math.cos(phi), r * math.sin(phi), math.sqrt(max(0.0, 1 - u1)))
    helper = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    t = _norm(_cross(helper, n))
    b = _cross(n, t)
    return _norm(tuple(local[0] * t[i] + local[1] * b[i] + local[2] * n[i] for i in range(3)))


# --- tracing ------------------------------------------------------------------------------------


def trace_room(room: Room, sources: list[dict], bands: list[int], rays: int, profile: dict, seed: int = 1) -> list[list[list[float]]]:
    """Histograms [receiver][band][1 ms bin] of energy × chord (per unit
    source power and ray), summed over the room's sources weighted by their
    power per band (W)."""
    c = float(profile.get("speed_of_sound_ms", 343.0))
    radius = float(profile.get("receiver_radius_m", 0.3))
    max_refl = int(profile.get("max_reflections", 60))
    r2 = radius * radius
    nb = len(bands)
    hists = [[[] for _ in range(nb)] for _ in room.receivers]
    for si, src in enumerate(sources):
        rng = random.Random(seed * 1_000_003 + si)
        power = src["power_w"]
        pos0 = tuple(float(v) for v in src["position_m"])
        weight = [power[b] / rays for b in range(nb)]
        for _ in range(rays):
            pos, d = pos0, _random_unit(rng)
            energy = [1.0] * nb
            travelled = 0.0
            for _refl in range(max_refl + 1):
                dist, tri = hit(pos, d, room.tris)
                if tri is None:
                    break  # a leak through an open face
                for ri, rc in enumerate(room.receivers):
                    v = _sub(rc, pos)
                    along = _dot(v, d)
                    if along <= 0.0 or along >= dist + radius:
                        continue
                    miss = _dot(v, v) - along * along
                    if miss >= r2:
                        continue
                    chord = 2.0 * math.sqrt(r2 - miss)
                    k = int((travelled + along) / c / BIN_S)
                    for b in range(nb):
                        h = hists[ri][b]
                        if len(h) <= k:
                            h.extend([0.0] * (k + 1 - len(h)))
                        h[k] += energy[b] * chord * weight[b]
                travelled += dist
                pos = tuple(pos[i] + d[i] * dist for i in range(3))
                energy = [energy[b] * (1.0 - tri.alpha[b]) for b in range(nb)]
                if max(energy) < 1e-6:
                    break
                n = tri.normal if _dot(tri.normal, d) < 0 else (-tri.normal[0], -tri.normal[1], -tri.normal[2])
                if rng.random() < tri.scattering:
                    d = _lambert(n, rng)
                else:
                    k2 = 2.0 * _dot(d, n)
                    d = _norm((d[0] - k2 * n[0], d[1] - k2 * n[1], d[2] - k2 * n[2]))
                pos = tuple(pos[i] + n[i] * 1e-6 for i in range(3))
    return hists


def decay_times(hist: list[float], bin_s: float = BIN_S) -> tuple[float, float]:
    """(T30 or T20, EDT) in seconds from one energy–time histogram (Schroeder)."""
    total = sum(hist)
    if total <= 0:
        return math.nan, math.nan
    curve, acc = [], total
    for value in hist:
        curve.append(10 * math.log10(acc / total) if acc > 0 else -200.0)
        acc -= value

    def fit(top: float, bottom: float) -> float:
        pts = [(i * bin_s, db) for i, db in enumerate(curve) if bottom <= db <= top]
        if len(pts) < 4:
            return math.nan
        n = len(pts)
        mx = sum(p[0] for p in pts) / n
        my = sum(p[1] for p in pts) / n
        sxx = sum((p[0] - mx) ** 2 for p in pts)
        if sxx <= 0:
            return math.nan
        slope = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
        return -60.0 / slope if slope < 0 else math.nan

    t30 = fit(-5.0, -35.0) if min(curve) <= -35.0 else math.nan
    if not math.isfinite(t30):
        t30 = fit(-5.0, -25.0) if min(curve) <= -25.0 else math.nan
    return t30, fit(0.0, -10.0)


def spl(hist_energy: float, receiver_volume: float, c: float) -> float:
    """dB from Σ W·e·chord (stationary energy density w = Σ/(c·V), p² = w·ρ·c²)."""
    w = hist_energy / (c * receiver_volume)
    p2 = w * RHO * c * c
    return 10 * math.log10(p2 / (P_REF * P_REF)) if p2 > 0 else math.nan


def power_w(src: dict, bands: list[int]) -> list[float]:
    level = src.get("power_db", 94)
    levels = level if isinstance(level, list) else [level] * len(bands)
    return [W_REF * 10 ** (float(lv) / 10) for lv in levels]


# --- the result ------------------------------------------------------------------------------------


def analyse(rooms: list[Room], sources: list[dict], params: dict, profile: dict, *, rays: int | None = None, seed: int = 1) -> dict:
    bands = list(params["bands"])
    c = float(profile.get("speed_of_sound_ms", 343.0))
    radius = float(profile.get("receiver_radius_m", 0.3))
    v_rec = 4.0 / 3.0 * math.pi * radius ** 3
    n_rays = int(rays or params.get("rays", 20000))
    per_room = []
    for room in rooms:
        place_receivers(room, float(params.get("receiver_grid_m", 1.0)), float(params.get("receiver_height_m", 1.2)), radius)
        inside = [
            {"position_m": s["position_m"], "power_w": power_w(s, bands)}
            for s in sources
            if all(room.lo[i] <= float(s["position_m"][i]) <= room.hi[i] for i in range(3))
        ]
        if not inside:
            per_room.append({"room": room, "t30": [math.nan] * len(bands), "edt": [math.nan] * len(bands), "spl_dba": [math.nan] * len(room.receivers)})
            continue
        hists = trace_room(room, inside, bands, n_rays, profile, seed)
        t30 = []
        edt = []
        for b in range(len(bands)):
            times = [decay_times(h[b]) for h in hists]
            ok30 = [t for t, _ in times if math.isfinite(t)]
            ok_edt = [e for _, e in times if math.isfinite(e)]
            t30.append(sum(ok30) / len(ok30) if ok30 else math.nan)
            edt.append(sum(ok_edt) / len(ok_edt) if ok_edt else math.nan)
        dba = []
        for h in hists:
            total = 0.0
            for b, band in enumerate(bands):
                level = spl(sum(h[b]), v_rec, c)
                if math.isfinite(level):
                    total += 10 ** ((level + A_WEIGHT.get(band, 0.0)) / 10)
            dba.append(10 * math.log10(total) if total > 0 else math.nan)
        per_room.append({"room": room, "t30": t30, "edt": edt, "spl_dba": dba})
    return {"bands": bands, "rooms": per_room, "rays": n_rays}


def build_result(job: common.Job, analysis: dict, out_dir: Path) -> dict:
    bands = analysis["bands"]
    rooms = analysis["rooms"]
    keys = [r["room"].key for r in rooms]
    names = [r["room"].name for r in rooms]
    ids = common.space_ids(keys)
    fields = []
    for b, band in enumerate(bands):
        fields.append(common.field(out_dir, f"t30_{band}", "s", "spaces", [r["t30"][b] for r in rooms], entities=ids, keys=names))
        fields.append(common.field(out_dir, f"edt_{band}", "s", "spaces", [r["edt"][b] for r in rooms], entities=ids, keys=names))
    # The receivers of every room on one grid at receiver height.
    cell = float(job.params.get("receiver_grid_m", 1.0))
    lo_x = min(r["room"].lo[0] for r in rooms)
    lo_y = min(r["room"].lo[1] for r in rooms)
    hi_x = max(r["room"].hi[0] for r in rooms)
    hi_y = max(r["room"].hi[1] for r in rooms)
    nx = max(1, math.ceil((hi_x - lo_x) / cell))
    ny = max(1, math.ceil((hi_y - lo_y) / cell))
    while nx * ny > 1_000_000:
        cell *= 2
        nx, ny = max(1, math.ceil((hi_x - lo_x) / cell)), max(1, math.ceil((hi_y - lo_y) / cell))
    values = [math.nan] * (nx * ny)
    for r in rooms:
        for (x, y, _z), level in zip(r["room"].receivers, r["spl_dba"]):
            i = min(nx - 1, max(0, int((x - lo_x) / cell)))
            j = min(ny - 1, max(0, int((y - lo_y) / cell)))
            values[j * nx + i] = level
    z = min(r["room"].lo[2] for r in rooms) + float(job.params.get("receiver_height_m", 1.2))
    grids = [common.grid(out_dir, "spl_dba", "dB(A)", [lo_x * 1000, lo_y * 1000, z * 1000], cell * 1000, nx, ny, values)]
    pick = bands.index(500) if 500 in bands else 0
    t500 = [r["t30"][pick] for r in rooms if math.isfinite(r["t30"][pick])]
    summary = {f"t30_{bands[pick]}_s": sum(t500) / len(t500) if t500 else math.nan, "rooms": len(rooms), "rays": analysis["rays"]}
    return common.result(job, common.engine("truebex-raytracer", "1", "acoustics"), summary, fields, grids)


def run(job: common.Job) -> None:
    out = job.out_dir
    data = common.read_json(job.input("rooms"), "rooms")
    bands = list(job.params.get("bands") or (job.profile.get("bands_default") or [125, 250, 500, 1000, 2000, 4000]))
    raw_rooms = data.get("rooms")
    if not isinstance(raw_rooms, list) or not raw_rooms:
        raise common.BadInput("the rooms file has no rooms")
    rooms = [room_from(r, bands, i) for i, r in enumerate(raw_rooms)]
    sources = job.params.get("sources") or []
    if not sources:
        raise common.BadInput("params.sources is empty")
    common.progress(out, 0.1, f"tracing {len(rooms)} rooms")
    analysis = analyse(rooms, sources, {**job.params, "bands": bands}, job.profile or {})
    result = build_result(job, analysis, out)
    common.write_result(out, result)
    common.progress(out, 1.0, "done")


if __name__ == "__main__":
    sys.exit(common.main(run))
