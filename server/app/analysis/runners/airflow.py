"""The `airflow` runner: natural ventilation between rooms (PF11c).

    python3 -m runners.airflow /job

render-jobs 1.2.0 §6.5.3 / §6.5.4: the orifice network, our own (standard
library only, no third-party solver), as the app's estimate and AN3's stub
run it. Inputs:

    inputs/rooms                       truebex-airflow-rooms/1 (the job's upload)
    inputs/wind_geometry               the wind job's geometry (binary STL; the platform's)
    inputs/wind_pressure_coefficient   the wind job's Cp, one float32 per triangle (the platform's)

1. An opening to (or from) outside takes its `cp`; without one, the wind
   job's Cp at the triangle whose centroid is nearest its `centre_m` among
   those facing it (unit normal . outward >= 0.5; all triangles when none
   faces it). Outward is `normal` when `to` is outside, else -`normal`.
2. The outdoor pressure there is Cp x ½ ρ U_ref² (U_ref = `speed_ms`, the
   wind job's reference speed; ρ the file's `rho_kg_m3`, 1.2 by default).
3. Each room connected to outside gets a pressure from Newton on its mass
   balance (inflow = outflow), the flow through an opening Q = Cd A
   sqrt(2 |Δp| / ρ) signed from `from` to `to` (linear below 1e-4 Pa so the
   Jacobian stays finite), a halving line search, at most 60 steps, to
   1e-9 m3/s; rooms with no path to outside carry no flow.
4. The result (§6.3): field `air_changes` (1/h, on spaces, the rooms' order,
   `entities` = their ids) = each room's inflow x 3600 / volume_m3; field
   `opening_flow` (m3/s, on openings, the openings' order, positive from
   `from` to `to`); grid `velocity` (m/s, 3 components) at
   `velocity_height_m`, drawn as the app's stub draws it: Q / A along each
   opening's normal in the cell nearest its centre (0.5 m cells over the
   openings' extent plus 2 m), NaN elsewhere. That grid comes from a
   network, not a field (the interior CFD run is not offered yet). Summary:
   rooms, openings, iterations, residual_m3s, converged, max_air_changes.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "runners"

from . import common
from .wind import read_stl

VERSION = "1"
SCHEMA = "truebex-airflow-rooms/1"
OUTSIDE = -1
MAX_GRID = 4000


@dataclass
class Room:
    id: str
    name: str
    volume_m3: float
    floor_z_m: float


@dataclass
class Opening:
    id: str
    src: int  # room index, or OUTSIDE
    dst: int
    area_m2: float
    cd: float
    centre_m: tuple[float, float, float]
    normal: tuple[float, float, float]
    cp: float | None

    @property
    def exterior(self) -> bool:
        return self.src == OUTSIDE or self.dst == OUTSIDE

    def outward(self) -> tuple[float, float, float]:
        sign = 1.0 if self.dst == OUTSIDE else -1.0
        return (sign * self.normal[0], sign * self.normal[1], sign * self.normal[2])


@dataclass
class Network:
    rooms: list[Room]
    openings: list[Opening]
    rho: float


@dataclass
class Solution:
    pressures: list[float]
    flows: list[float]
    ach: list[float]
    iterations: int
    residual: float
    converged: bool


def _num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _vec3(value: object, what: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3 or not all(_num(v) for v in value):
        raise common.BadInput(f"{what} is not [x, y, z]")
    return (float(value[0]), float(value[1]), float(value[2]))


def network(data: dict) -> Network:
    """The rooms file as a network (the platform validated it at submission;
    this re-checks what the solve needs)."""
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise common.BadInput(f"the rooms file is not {SCHEMA}")
    index: dict[str, int] = {}
    rooms = []
    for i, r in enumerate(data.get("rooms") or []):
        if not isinstance(r, dict) or not common.is_hex32(r.get("id")) or not _num(r.get("volume_m3")) or r["volume_m3"] <= 0:
            raise common.BadInput(f"rooms[{i}] needs a 32-hex id and a volume_m3 above 0")
        index[r["id"].lower()] = len(rooms)
        rooms.append(Room(r["id"].lower(), str(r.get("name") or ""), float(r["volume_m3"]), float(r.get("floor_z_m") or 0.0)))
    if not rooms:
        raise common.BadInput("the rooms file has no rooms")

    def side(value: object, what: str) -> int:
        if value == "outside":
            return OUTSIDE
        if isinstance(value, str) and value.lower() in index:
            return index[value.lower()]
        raise common.BadInput(f"{what} names no room of the file")

    openings = []
    for i, o in enumerate(data.get("openings") or []):
        if not isinstance(o, dict) or not common.is_hex32(o.get("id")):
            raise common.BadInput(f"openings[{i}] needs a 32-hex id")
        src, dst = side(o.get("from"), f"openings[{i}].from"), side(o.get("to"), f"openings[{i}].to")
        if src == dst:
            raise common.BadInput(f"openings[{i}] joins a side to itself")
        if not _num(o.get("area_m2")) or o["area_m2"] <= 0 or not _num(o.get("cd")) or not 0 < o["cd"] <= 1:
            raise common.BadInput(f"openings[{i}] needs area_m2 above 0 and cd in (0, 1]")
        cp = o.get("cp")
        openings.append(Opening(
            o["id"].lower(), src, dst, float(o["area_m2"]), float(o["cd"]), _vec3(o.get("centre_m"), f"openings[{i}].centre_m"),
            _vec3(o.get("normal"), f"openings[{i}].normal"), float(cp) if _num(cp) else None,
        ))
    rho = data.get("rho_kg_m3", 1.2)
    return Network(rooms, openings, float(rho) if _num(rho) and rho > 0 else 1.2)


# --- the outdoor pressure coefficients ---------------------------------------------------------


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n) if n > 0 else (0.0, 0.0, 0.0)


def outside_cps(net: Network, tris: list, cp: list[float], facing_min: float = 0.5) -> list[float | None]:
    """Per opening: its Cp when it opens to outside (None for an inside one)."""
    need = [o for o in net.openings if o.exterior and o.cp is None]
    if need and (not tris or len(cp) != len(tris)):
        raise common.BadInput("an opening to outside without cp needs the wind job's geometry and pressure coefficients")
    centroids, normals = [], []
    for t in tris if need else ():
        centroids.append(tuple(sum(v[k] for v in t) / 3 for k in range(3)))
        u, w = _sub(t[1], t[0]), _sub(t[2], t[0])
        normals.append(_unit((u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])))
    out: list[float | None] = []
    for o in net.openings:
        if not o.exterior:
            out.append(None)
            continue
        if o.cp is not None:
            out.append(o.cp)
            continue
        outward = _unit(o.outward())
        facing = [k for k, n in enumerate(normals) if n[0] * outward[0] + n[1] * outward[1] + n[2] * outward[2] >= facing_min]
        pool = facing or range(len(centroids))
        best = min(pool, key=lambda k: sum((centroids[k][i] - o.centre_m[i]) ** 2 for i in range(3)))
        out.append(float(cp[best]) if math.isfinite(cp[best]) else 0.0)
    return out


# --- the network -------------------------------------------------------------------------------


def _flow(dp: float, cda: float, rho: float, linear: float) -> float:
    if abs(dp) < linear:
        return cda * math.sqrt(2.0 * linear / rho) * dp / linear
    return math.copysign(cda * math.sqrt(2.0 * abs(dp) / rho), dp)


def _flow_deriv(dp: float, cda: float, rho: float, linear: float) -> float:
    if abs(dp) < linear:
        return cda * math.sqrt(2.0 * linear / rho) / linear
    return cda / math.sqrt(2.0 * rho * abs(dp))


def _solve_linear(a: list[list[float]], b: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting (a and b are consumed)."""
    n = len(b)
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-300:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        b[col], b[pivot] = b[pivot], b[col]
        inv = 1.0 / a[col][col]
        row = a[col]
        for r in range(col + 1, n):
            f = a[r][col] * inv
            if f:
                other = a[r]
                for c in range(col, n):
                    other[c] -= f * row[c]
                b[r] -= f * b[col]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = b[r] - sum(a[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / a[r][r]
    return x


def solve(net: Network, cps: list[float | None], q_pa: float, *, max_iter: int = 60, tol: float = 1e-9,
          linear_pa: float = 1e-4) -> Solution:
    rho = net.rho
    n_rooms = len(net.rooms)
    adjacent: list[list[int]] = [[] for _ in range(n_rooms)]
    connected = [False] * n_rooms
    queue: list[int] = []
    for o in net.openings:
        if o.exterior:
            r = o.src if o.src != OUTSIDE else o.dst
            if not connected[r]:
                connected[r] = True
                queue.append(r)
        else:
            adjacent[o.src].append(o.dst)
            adjacent[o.dst].append(o.src)
    for r in queue:
        for nb in adjacent[r]:
            if not connected[nb]:
                connected[nb] = True
                queue.append(nb)
    var = [-1] * n_rooms
    n = 0
    for r in range(n_rooms):
        if connected[r]:
            var[r] = n
            n += 1
    outdoor = [(cp or 0.0) * q_pa if o.exterior else 0.0 for o, cp in zip(net.openings, cps)]

    def pressure(p: list[float], room: int, k: int) -> float:
        if room == OUTSIDE:
            return outdoor[k]
        return p[var[room]] if var[room] >= 0 else 0.0

    def residual(p: list[float]) -> tuple[list[float], float]:
        f = [0.0] * n
        for k, o in enumerate(net.openings):
            q = _flow(pressure(p, o.src, k) - pressure(p, o.dst, k), o.cd * o.area_m2, rho, linear_pa)
            if o.src != OUTSIDE and var[o.src] >= 0:
                f[var[o.src]] -= q
            if o.dst != OUTSIDE and var[o.dst] >= 0:
                f[var[o.dst]] += q
        return f, max((abs(x) for x in f), default=0.0)

    # Start at the mean of the outdoor pressures each room sees.
    total, count = [0.0] * n, [0] * n
    for k, o in enumerate(net.openings):
        if o.exterior:
            r = o.src if o.src != OUTSIDE else o.dst
            if var[r] >= 0:
                total[var[r]] += outdoor[k]
                count[var[r]] += 1
    mean = sum(total) / max(1, sum(count))
    p = [total[i] / count[i] if count[i] else mean for i in range(n)]
    f, res = residual(p)
    iterations = 0
    while n and res > tol and iterations < max_iter:
        iterations += 1
        jac = [[0.0] * n for _ in range(n)]
        for k, o in enumerate(net.openings):
            d = _flow_deriv(pressure(p, o.src, k) - pressure(p, o.dst, k), o.cd * o.area_m2, rho, linear_pa)
            a = var[o.src] if o.src != OUTSIDE else -1
            b = var[o.dst] if o.dst != OUTSIDE else -1
            if a >= 0:
                jac[a][a] -= d
                if b >= 0:
                    jac[a][b] += d
            if b >= 0:
                jac[b][b] -= d
                if a >= 0:
                    jac[b][a] += d
        step = _solve_linear(jac, [-x for x in f])
        if step is None:
            break
        lam, trial, f_trial, res_trial = 1.0, p, f, res
        for _ in range(30):
            trial = [p[i] + lam * step[i] for i in range(n)]
            f_trial, res_trial = residual(trial)
            if res_trial < res:
                break
            lam *= 0.5
        if res_trial >= res:
            break
        p, f, res = trial, f_trial, res_trial
    flows = [_flow(pressure(p, o.src, k) - pressure(p, o.dst, k), o.cd * o.area_m2, rho, linear_pa) for k, o in enumerate(net.openings)]
    inflow = [0.0] * n_rooms
    for o, q in zip(net.openings, flows):
        if q > 0 and o.dst != OUTSIDE:
            inflow[o.dst] += q
        if q < 0 and o.src != OUTSIDE:
            inflow[o.src] -= q
    ach = [inflow[r] * 3600.0 / room.volume_m3 for r, room in enumerate(net.rooms)]
    pressures = [p[var[r]] if var[r] >= 0 else 0.0 for r in range(n_rooms)]
    return Solution(pressures, flows, ach, iterations, res, res <= max(tol, 1e-6))


# --- the velocity grid and the result ------------------------------------------------------------


def velocity_grid(net: Network, flows: list[float], height_m: float, cell_m: float = 0.5, margin_m: float = 2.0) -> dict | None:
    """Q / A along each opening's normal (in plan) in the cell nearest its centre, NaN elsewhere."""
    if not net.openings:
        return None
    xs = [o.centre_m[0] for o in net.openings]
    ys = [o.centre_m[1] for o in net.openings]
    x0, y0 = min(xs) - margin_m, min(ys) - margin_m
    width, depth = max(xs) + margin_m - x0, max(ys) + margin_m - y0
    while max(width, depth) / cell_m > MAX_GRID:
        cell_m *= 2
    nx, ny = max(1, math.ceil(width / cell_m - 1e-9)), max(1, math.ceil(depth / cell_m - 1e-9))
    ox, oy = x0 + cell_m / 2, y0 + cell_m / 2
    values = [math.nan] * (nx * ny * 3)
    for o, q in zip(net.openings, flows):
        i = min(nx - 1, max(0, round((o.centre_m[0] - ox) / cell_m)))
        j = min(ny - 1, max(0, round((o.centre_m[1] - oy) / cell_m)))
        plan = math.hypot(o.normal[0], o.normal[1])
        speed = q / o.area_m2
        k = 3 * (i + j * nx)
        values[k:k + 3] = [speed * o.normal[0] / plan, speed * o.normal[1] / plan, 0.0] if plan > 0 else [0.0, 0.0, 0.0]
    return {"origin_mm": [ox * 1000, oy * 1000, height_m * 1000], "cell_mm": cell_m * 1000, "nx": nx, "ny": ny, "values": values}


def build_result(job: common.Job, net: Network, sol: Solution, grid: dict | None, out_dir: Path) -> dict:
    ids = common.entity_bytes([r.id for r in net.rooms])
    fields = [common.field(out_dir, "air_changes", "1/h", "spaces", sol.ach, entities=ids)]
    if net.openings:
        fields.append(common.field(out_dir, "opening_flow", "m3/s", "openings", sol.flows,
                                   entities=common.entity_bytes([o.id for o in net.openings])))
    grids = []
    if grid is not None:
        grids.append(common.grid(out_dir, "velocity", "m/s", grid["origin_mm"], grid["cell_mm"], grid["nx"], grid["ny"],
                                 grid["values"], components=3))
    summary = {
        "rooms": len(net.rooms),
        "openings": len(net.openings),
        "iterations": sol.iterations,
        "converged": sol.converged,
        "max_air_changes": max(sol.ach) if sol.ach else 0.0,
    }
    result = common.result(job, common.engine("truebex-airflow", VERSION, "airflow"), summary, fields, grids)
    result["summary"]["residual_m3s"] = float(f"{sol.residual:.6g}")
    return result


def run(job: common.Job) -> None:
    out = job.out_dir
    profile = job.profile or {}
    net = network(common.read_json(job.input("rooms"), "rooms"))
    needs_wind = any(o.exterior and o.cp is None for o in net.openings)
    tris, cp = [], []
    geometry = job.input("wind_geometry", required=needs_wind)
    pressure = job.input("wind_pressure_coefficient", required=needs_wind)
    if needs_wind:
        tris = read_stl(geometry, "wind job's geometry").triangles
        cp = common.unpack_f32(pressure.read_bytes())
        if len(cp) != len(tris):
            raise common.BadInput(f"{len(cp)} pressure coefficients for the wind geometry's {len(tris)} triangles")
    common.progress(out, 0.2, "the outdoor pressures")
    cps = outside_cps(net, tris, cp, float(profile.get("facing_dot_min", 0.5)))
    speed = float(job.params.get("speed_ms", 5))
    common.progress(out, 0.5, "the network")
    sol = solve(net, cps, 0.5 * net.rho * speed * speed, max_iter=int(profile.get("newton_max_iter", 60)),
                tol=float(profile.get("tolerance_m3s", 1e-9)), linear_pa=float(profile.get("linear_below_pa", 1e-4)))
    grid = velocity_grid(net, sol.flows, float(job.params.get("velocity_height_m", 1.1)),
                         float(profile.get("velocity_cell_mm", 500)) / 1000.0, float(profile.get("velocity_margin_m", 2.0)))
    common.write_result(out, build_result(job, net, sol, grid, out))
    common.progress(out, 1.0, "done")


if __name__ == "__main__":
    sys.exit(common.main(run))
