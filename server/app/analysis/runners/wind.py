"""The `wind` runner: one wind direction on the uploaded building (PF11).

    python3 -m runners.wind /job

OpenFOAM v2406 (GPL-3.0; run as a service on the platform's workers, never
shipped with the app), steady RANS with k-epsilon (simpleFoam):

1. The building (`inputs/geometry`, binary STL in metres, watertight; AN3) is
   moved to the origin and turned so the wind blows along +x
   (`direction_deg` is where the wind comes FROM: 0 = from north, +Y).
2. The case: a box domain 5 H upstream, 15 H downstream, 5 H to each side and
   5 H above the building (H = its height), background cells H / 10, refined
   around the building (snappyHexMesh), an atmospheric boundary layer at the
   inlet from `speed_ms` at `reference_height_m` over the terrain class's
   roughness length, a rough ground, slip top and sides, zero pressure at the
   outlet; the residual target and iteration cap from the job's profile (GD2).
3. `blockMesh`, `snappyHexMesh -overwrite`, `simpleFoam` (in parallel when the
   container has more than one core), then sampling: the kinematic pressure on
   the uploaded triangles (nearest boundary face) and the velocity on a grid
   of points 1.5 m above the ground, ±3 H around the building.
4. The result: `pressure_coefficient` on faces (Cp = p / (½ Uref²), one value
   per uploaded triangle, `entities` = the uploaded ids or zeros), grids
   `comfort_lawson` (class 0-4 from the profile's thresholds, 255 inside the
   building) and `speed_ratio` (|U| / speed_ms, NaN inside), summary
   max_speed_ms, max_speed_ratio, min_cp, max_cp, cells, iterations, converged.
"""

from __future__ import annotations

import math
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "runners"

from . import common

VERSION = "2406"
NU_AIR = 1.5e-5
KAPPA = 0.41
CMU = 0.09
NO_CLASS = 255
HEADER = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    object      {obj};
}}
"""


@dataclass
class Mesh:
    triangles: list  # [((x, y, z), (x, y, z), (x, y, z))]

    @property
    def count(self) -> int:
        return len(self.triangles)

    def bounds(self) -> tuple[list[float], list[float]]:
        lo = [math.inf] * 3
        hi = [-math.inf] * 3
        for tri in self.triangles:
            for v in tri:
                for i in range(3):
                    lo[i] = min(lo[i], v[i])
                    hi[i] = max(hi[i], v[i])
        return lo, hi


def read_stl(path: Path) -> Mesh:
    data = Path(path).read_bytes()
    if len(data) < 84:
        raise common.BadInput("the geometry is not a binary STL file")
    (n,) = struct.unpack_from("<I", data, 80)
    if n == 0 or len(data) != 84 + 50 * n:
        raise common.BadInput("the geometry is not a binary STL file (its size does not match its triangle count)")
    tris = []
    for i in range(n):
        v = struct.unpack_from("<12f", data, 84 + 50 * i)
        tris.append(((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])))
    return Mesh(tris)


def write_stl(path: Path, triangles: list) -> None:
    out = bytearray(b"truebex wind case".ljust(80, b" ")) + struct.pack("<I", len(triangles))
    for a, b, c in triangles:
        u = [b[i] - a[i] for i in range(3)]
        w = [c[i] - a[i] for i in range(3)]
        n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        length = math.sqrt(sum(x * x for x in n)) or 1.0
        out += struct.pack("<3f", *(x / length for x in n))
        for v in (a, b, c):
            out += struct.pack("<3f", *v)
        out += struct.pack("<H", 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))


# --- the wind frame -----------------------------------------------------------------------------


@dataclass
class Frame:
    """Model coordinates <-> the case's: centred on the footprint, the ground
    at z = 0, the wind along +x."""

    cx: float
    cy: float
    z0: float
    angle: float  # radians; case = rotate(model - centre, angle)

    @classmethod
    def for_wind(cls, mesh: Mesh, direction_deg: float) -> "Frame":
        lo, hi = mesh.bounds()
        d = math.radians(direction_deg)
        flow = (-math.sin(d), -math.cos(d))  # where the wind goes
        return cls((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2], -math.atan2(flow[1], flow[0]))

    def to_case(self, p) -> tuple[float, float, float]:
        x, y = p[0] - self.cx, p[1] - self.cy
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (x * c - y * s, x * s + y * c, p[2] - self.z0)

    def to_model(self, p) -> tuple[float, float, float]:
        c, s = math.cos(-self.angle), math.sin(-self.angle)
        x, y = p[0] * c - p[1] * s, p[0] * s + p[1] * c
        return (x + self.cx, y + self.cy, p[2] + self.z0)


def log_law_speed(z: float, uref: float, zref: float, z0: float) -> float:
    """The inlet's mean speed at height z (the atmospheric boundary layer's log law)."""
    return uref * math.log((max(z, 0.0) + z0) / z0) / math.log((zref + z0) / z0)


def lawson_class(speed: float, classes: list[dict]) -> int:
    """The profile's Lawson class (0 = frequent sitting … 4 = uncomfortable)."""
    for c in classes:
        if c.get("max_ms") is None or speed <= c["max_ms"]:
            return int(c["class"])
    return int(classes[-1]["class"])


# --- the case -----------------------------------------------------------------------------------


@dataclass
class Domain:
    lo: tuple[float, float, float]
    hi: tuple[float, float, float]
    cells: tuple[int, int, int]
    h: float
    inside: tuple[float, float, float]


def domain(case_tris: list, profile: dict) -> Domain:
    lo = [min(v[i] for t in case_tris for v in t) for i in range(3)]
    hi = [max(v[i] for t in case_tris for v in t) for i in range(3)]
    h = max(hi[2] - lo[2], 3.0)
    d = profile.get("domain_h") or {"upstream": 5, "downstream": 15, "sides": 5, "top": 5}
    dlo = (lo[0] - d["upstream"] * h, lo[1] - d["sides"] * h, 0.0)
    dhi = (hi[0] + d["downstream"] * h, hi[1] + d["sides"] * h, hi[2] + d["top"] * h)
    cell = h / float(profile.get("cells_per_h", 10))
    cells = tuple(max(1, math.ceil((dhi[i] - dlo[i]) / cell)) for i in range(3))
    # A point in the fluid, upstream of the building, never on a cell face.
    inside = (lo[0] - 2.5 * h + 0.0137 * cell, (lo[1] + hi[1]) / 2 + 0.0213 * cell, h * 2 + 0.0311 * cell)
    return Domain(dlo, dhi, cells, h, inside)


def _vec(v) -> str:
    return "(" + " ".join(f"{x:.6g}" for x in v) + ")"


def case_files(job: common.Job, case_tris: list, profile: dict) -> dict[str, str]:
    """Every text file of the OpenFOAM case, by path inside the case."""
    p = job.params
    dom = domain(case_tris, profile)
    terrain = (profile.get("terrain") or {}).get(p.get("terrain", "suburban")) or {"z0_m": 0.3}
    z0 = float(terrain["z0_m"])
    uref, zref = float(p.get("speed_ms", 5)), float(p.get("reference_height_m", 10))
    iterations = int(profile.get("iterations_max", 1000))
    residual = float(profile.get("residual_target", 1e-4))
    levels = list(profile.get("refinement_levels") or [2, 3])
    ustar = KAPPA * uref / math.log((zref + z0) / z0)
    (x0, y0, z0d), (x1, y1, z1d) = dom.lo, dom.hi
    nx, ny, nz = dom.cells
    abl = (
        f"        flowDir         (1 0 0);\n        zDir            (0 0 1);\n        Uref            {uref:.6g};\n"
        f"        Zref            {zref:.6g};\n        z0              uniform {z0:.6g};\n        d               uniform 0;\n"
    )
    files: dict[str, str] = {}
    files["system/blockMeshDict"] = HEADER.format(cls="dictionary", obj="blockMeshDict") + f"""
scale 1;
vertices
(
    ({x0:.6g} {y0:.6g} {z0d:.6g}) ({x1:.6g} {y0:.6g} {z0d:.6g}) ({x1:.6g} {y1:.6g} {z0d:.6g}) ({x0:.6g} {y1:.6g} {z0d:.6g})
    ({x0:.6g} {y0:.6g} {z1d:.6g}) ({x1:.6g} {y0:.6g} {z1d:.6g}) ({x1:.6g} {y1:.6g} {z1d:.6g}) ({x0:.6g} {y1:.6g} {z1d:.6g})
);
blocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1) );
boundary
(
    inlet  {{ type patch; faces ((0 4 7 3)); }}
    outlet {{ type patch; faces ((1 2 6 5)); }}
    ground {{ type wall;  faces ((0 3 2 1)); }}
    top    {{ type patch; faces ((4 5 6 7)); }}
    sides  {{ type patch; faces ((0 1 5 4) (3 7 6 2)); }}
);
"""
    near = 1.5 * dom.h
    files["system/snappyHexMeshDict"] = HEADER.format(cls="dictionary", obj="snappyHexMeshDict") + f"""
castellatedMesh true;
snap            true;
addLayers       false;
geometry
{{
    building.stl {{ type triSurfaceMesh; name building; }}
}}
castellatedMeshControls
{{
    maxLocalCells 4000000;
    maxGlobalCells 8000000;
    minRefinementCells 10;
    nCellsBetweenLevels 3;
    features ();
    refinementSurfaces {{ building {{ level ({levels[0]} {levels[-1]}); patchInfo {{ type wall; }} }} }}
    resolveFeatureAngle 30;
    refinementRegions {{ building {{ mode distance; levels (({near:.6g} {levels[0]})); }} }}
    locationInMesh {_vec(dom.inside)};
    allowFreeStandingZoneFaces true;
}}
snapControls {{ nSmoothPatch 3; tolerance 2.0; nSolveIter 50; nRelaxIter 5; nFeatureSnapIter 10; }}
addLayersControls {{ relativeSizes true; layers {{ }} expansionRatio 1.0; finalLayerThickness 0.3; minThickness 0.1; }}
meshQualityControls
{{
    maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80; minVol 1e-13;
    minTetQuality -1e30; minArea -1; minTwist 0.02; minDeterminant 0.001; minFaceWeight 0.05;
    minVolRatio 0.01; minTriangleTwist -1; nSmoothScale 4; errorReduction 0.75;
}}
mergeTolerance 1e-6;
"""
    files["system/controlDict"] = HEADER.format(cls="dictionary", obj="controlDict") + f"""
application     simpleFoam;
startFrom       latestTime;
stopAt          endTime;
endTime         {iterations};
deltaT          1;
writeControl    timeStep;
writeInterval   {iterations};
purgeWrite      1;
writeFormat     binary;
writePrecision  8;
runTimeModifiable false;
"""
    files["system/fvSchemes"] = HEADER.format(cls="dictionary", obj="fvSchemes") + """
ddtSchemes      { default steadyState; }
gradSchemes     { default cellLimited Gauss linear 1; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,epsilon) bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited corrected 0.33; }
interpolationSchemes { default linear; }
snGradSchemes   { default limited corrected 0.33; }
wallDist        { method meshWave; }
"""
    files["system/fvSolution"] = HEADER.format(cls="dictionary", obj="fvSolution") + f"""
solvers
{{
    p {{ solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.1; }}
    "(U|k|epsilon)" {{ solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }}
}}
SIMPLE
{{
    nNonOrthogonalCorrectors 1;
    consistent      true;
    residualControl {{ p {residual:.3g}; U {residual:.3g}; "(k|epsilon)" {residual:.3g}; }}
}}
relaxationFactors {{ equations {{ U 0.9; "(k|epsilon)" 0.7; }} fields {{ p 0.9; }} }}
"""
    files["system/decomposeParDict"] = HEADER.format(cls="dictionary", obj="decomposeParDict") + """
numberOfSubdomains __CORES__;
method          scotch;
"""
    files["constant/transportProperties"] = HEADER.format(cls="dictionary", obj="transportProperties") + f"""
transportModel  Newtonian;
nu              {NU_AIR};
"""
    files["constant/turbulenceProperties"] = HEADER.format(cls="dictionary", obj="turbulenceProperties") + """
simulationType  RAS;
RAS { RASModel kEpsilon; turbulence on; printCoeffs on; }
"""
    k_in = ustar * ustar / math.sqrt(CMU)
    common_bc = "    top    { type slip; }\n    sides  { type slip; }\n"
    files["0/U"] = HEADER.format(cls="volVectorField", obj="U") + f"""
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform ({uref:.6g} 0 0);
boundaryField
{{
    inlet    {{ type atmBoundaryLayerInletVelocity;
{abl}    }}
    outlet   {{ type inletOutlet; inletValue uniform (0 0 0); value uniform ({uref:.6g} 0 0); }}
    ground   {{ type noSlip; }}
    building {{ type noSlip; }}
{common_bc}}}
"""
    files["0/p"] = HEADER.format(cls="volScalarField", obj="p") + """
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{
    inlet    { type zeroGradient; }
    outlet   { type fixedValue; value uniform 0; }
    ground   { type zeroGradient; }
    building { type zeroGradient; }
    top    { type slip; }
    sides  { type slip; }
}
"""
    files["0/k"] = HEADER.format(cls="volScalarField", obj="k") + f"""
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform {k_in:.6g};
boundaryField
{{
    inlet    {{ type atmBoundaryLayerInletK;
{abl}    }}
    outlet   {{ type inletOutlet; inletValue uniform {k_in:.6g}; value uniform {k_in:.6g}; }}
    ground   {{ type kqRWallFunction; value uniform {k_in:.6g}; }}
    building {{ type kqRWallFunction; value uniform {k_in:.6g}; }}
{common_bc}}}
"""
    eps_in = ustar ** 3 / (KAPPA * (zref + z0))
    files["0/epsilon"] = HEADER.format(cls="volScalarField", obj="epsilon") + f"""
dimensions      [0 2 -3 0 0 0 0];
internalField   uniform {eps_in:.6g};
boundaryField
{{
    inlet    {{ type atmBoundaryLayerInletEpsilon;
{abl}    }}
    outlet   {{ type inletOutlet; inletValue uniform {eps_in:.6g}; value uniform {eps_in:.6g}; }}
    ground   {{ type epsilonWallFunction; value uniform {eps_in:.6g}; }}
    building {{ type epsilonWallFunction; value uniform {eps_in:.6g}; }}
{common_bc}}}
"""
    files["0/nut"] = HEADER.format(cls="volScalarField", obj="nut") + f"""
dimensions      [0 2 -1 0 0 0 0];
internalField   uniform 0;
boundaryField
{{
    inlet    {{ type calculated; value uniform 0; }}
    outlet   {{ type calculated; value uniform 0; }}
    ground   {{ type nutkAtmRoughWallFunction; z0 uniform {z0:.6g}; value uniform 0; }}
    building {{ type nutkWallFunction; value uniform 0; }}
    top    {{ type calculated; value uniform 0; }}
    sides  {{ type calculated; value uniform 0; }}
}}
"""
    return files


# --- sampling ------------------------------------------------------------------------------------


@dataclass
class Grid:
    origin: tuple[float, float]  # model x, y of the first cell's corner (m)
    cell: float  # m
    nx: int
    ny: int
    height: float  # m above the ground

    def centres(self, ground_z: float) -> list[tuple[float, float, float]]:
        return [
            (self.origin[0] + (i + 0.5) * self.cell, self.origin[1] + (j + 0.5) * self.cell, ground_z + self.height)
            for j in range(self.ny)
            for i in range(self.nx)
        ]


def ground_grid(mesh: Mesh, profile: dict) -> Grid:
    lo, hi = mesh.bounds()
    h = max(hi[2] - lo[2], 3.0)
    extent = float(profile.get("grid_extent_h", 3)) * h
    cell = float(profile.get("grid_cell_mm", 500)) / 1000.0
    x0, y0 = lo[0] - extent, lo[1] - extent
    nx = max(1, math.ceil((hi[0] + extent - x0) / cell))
    ny = max(1, math.ceil((hi[1] + extent - y0) / cell))
    while nx * ny > 250_000:  # keep the sampled cloud bounded
        cell *= 1.25
        nx = max(1, math.ceil((hi[0] + extent - x0) / cell))
        ny = max(1, math.ceil((hi[1] + extent - y0) / cell))
    return Grid((x0, y0), cell, nx, ny, float(profile.get("sample_height_m", 1.5)))


def sample_dict(points: list) -> str:
    pts = "\n".join(f"            {_vec(p)}" for p in points)
    return HEADER.format(cls="dictionary", obj="truebexSample") + f"""
functions
{{
    buildingSurface
    {{
        type            surfaces;
        libs            (sampling);
        surfaceFormat   raw;
        fields          (p);
        interpolationScheme cell;
        surfaces
        {{
            building {{ type meshedSurface; surface building.stl; source boundaryFaces; interpolate false; }}
        }}
    }}
    groundPoints
    {{
        type            sets;
        libs            (sampling);
        setFormat       raw;
        fields          (U);
        interpolationScheme cellPoint;
        sets
        {{
            ground
            {{
                type    cloud;
                axis    xyz;
                points
                (
{pts}
                );
            }}
        }}
    }}
}}
"""


def parse_raw(text: str, width: int) -> list[tuple[float, ...]]:
    """OpenFOAM `raw` sample output: `x y z v…` per line, `#` comments."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3 + width:
            continue
        try:
            rows.append(tuple(float(x) for x in parts[: 3 + width]))
        except ValueError:
            continue
    return rows


def match_nearest(targets: list, rows: list, cell: float) -> list:
    """For each target point, the row whose (x, y, z) is nearest (a spatial hash)."""
    buckets: dict[tuple[int, int, int], list[int]] = {}
    for i, r in enumerate(rows):
        buckets.setdefault((int(r[0] // cell), int(r[1] // cell), int(r[2] // cell)), []).append(i)
    out = []
    for t in targets:
        key = (int(t[0] // cell), int(t[1] // cell), int(t[2] // cell))
        best, best_d = None, math.inf
        for reach in (1, 3):
            for dx in range(-reach, reach + 1):
                for dy in range(-reach, reach + 1):
                    for dz in range(-reach, reach + 1):
                        for i in buckets.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                            r = rows[i]
                            d = (r[0] - t[0]) ** 2 + (r[1] - t[1]) ** 2 + (r[2] - t[2]) ** 2
                            if d < best_d:
                                best, best_d = r, d
            if best is not None:
                break
        out.append(best)
    return out


def grid_speeds(points: list, rows: list, cell: float) -> list[float | None]:
    """|U| at each grid point (None where the cloud dropped it: inside the
    building or outside the domain), matched to the nearest sampled point."""
    out: list[float | None] = []
    for p, r in zip(points, match_nearest(points, rows, cell)):
        if r is None or (r[0] - p[0]) ** 2 + (r[1] - p[1]) ** 2 + (r[2] - p[2]) ** 2 > (cell / 4) ** 2:
            out.append(None)
        else:
            out.append(math.sqrt(r[3] ** 2 + r[4] ** 2 + r[5] ** 2))
    return out


def centroid(tri) -> tuple[float, float, float]:
    return tuple(sum(v[i] for v in tri) / 3 for i in range(3))


def newest(dir_: Path, pattern: str) -> Path | None:
    found = sorted(dir_.glob(pattern), key=lambda p: p.stat().st_mtime) if dir_.exists() else []
    return found[-1] if found else None


# --- the result ------------------------------------------------------------------------------------


def build_result(job: common.Job, mesh: Mesh, cp: list[float], grid: Grid, speeds: list[float | None],
                 entities: bytes | None, out_dir: Path, info: dict) -> dict:
    if len(cp) != mesh.count:
        raise common.EngineError(f"{len(cp)} pressure values for {mesh.count} triangles")
    uref = float(job.params.get("speed_ms", 5))
    classes = (job.profile.get("lawson") or {}).get("classes") or [
        {"class": 0, "max_ms": 2.5}, {"class": 1, "max_ms": 4.0}, {"class": 2, "max_ms": 6.0}, {"class": 3, "max_ms": 8.0}, {"class": 4, "max_ms": None},
    ]
    lawson = [NO_CLASS if s is None else lawson_class(s, classes) for s in speeds]
    ratio = [math.nan if s is None else s / uref for s in speeds]
    lo, _hi = mesh.bounds()
    origin = [grid.origin[0] * 1000, grid.origin[1] * 1000, (lo[2] + grid.height) * 1000]
    fields = [common.field(out_dir, "pressure_coefficient", "1", "faces", cp, entities=entities or bytes(16 * mesh.count))]
    grids = [
        common.grid(out_dir, "comfort_lawson", "class", origin, grid.cell * 1000, grid.nx, grid.ny, lawson, "uint8"),
        common.grid(out_dir, "speed_ratio", "1", origin, grid.cell * 1000, grid.nx, grid.ny, ratio),
    ]
    known = [s for s in speeds if s is not None]
    finite_cp = [c for c in cp if math.isfinite(c)]
    summary = {
        "max_speed_ms": max(known) if known else math.nan,
        "max_speed_ratio": max(known) / uref if known else math.nan,
        "min_cp": min(finite_cp) if finite_cp else math.nan,
        "max_cp": max(finite_cp) if finite_cp else math.nan,
        **info,
    }
    return common.result(job, common.engine("openfoam", VERSION, "wind"), summary, fields, grids)


# --- running OpenFOAM --------------------------------------------------------------------------------


def _cells(case: Path) -> int:
    owner = case / "constant" / "polyMesh" / "owner"
    try:
        head = owner.read_bytes()[:2000].decode("latin-1")
    except OSError:
        return 0
    m = re.search(r"nCells:\s*(\d+)", head)
    return int(m.group(1)) if m else 0


def run(job: common.Job) -> None:
    out = job.out_dir
    profile = job.profile or {}
    mesh = read_stl(job.input("geometry"))
    entities_path = job.input("entities", required=False)
    entities = entities_path.read_bytes() if entities_path else None
    if entities is not None and len(entities) != 16 * mesh.count:
        raise common.BadInput("the entities file needs 16 bytes per triangle of the geometry")
    frame = Frame.for_wind(mesh, float(job.params.get("direction_deg", 0)))
    case_tris = [tuple(frame.to_case(v) for v in t) for t in mesh.triangles]
    case = job.dir / "case"
    shutil.rmtree(case, ignore_errors=True)
    cores = common.available_cores()
    for rel, text in case_files(job, case_tris, profile).items():
        path = case / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.replace("__CORES__", str(cores)), encoding="utf-8")
    write_stl(case / "constant" / "triSurface" / "building.stl", case_tris)
    log = case / "log"
    common.progress(out, 0.05, "meshing")
    common.run_command(["blockMesh"], cwd=case, log_path=log)
    common.run_command(["snappyHexMesh", "-overwrite"], cwd=case, log_path=log)
    iterations = int(profile.get("iterations_max", 1000))
    state = {"iteration": 0, "converged": False}

    def on_line(line: str) -> None:
        m = re.match(r"^Time = (\d+)", line)
        if m:
            state["iteration"] = int(m.group(1))
            if state["iteration"] % 25 == 0:
                common.progress(out, 0.2 + 0.7 * state["iteration"] / iterations, f"solving, iteration {state['iteration']}")
        elif "SIMPLE solution converged" in line:
            state["converged"] = True

    common.progress(out, 0.2, "solving")
    if cores > 1:
        common.run_command(["decomposePar", "-force"], cwd=case, log_path=log)
        common.run_command(["mpirun", "-np", str(cores), "simpleFoam", "-parallel"], cwd=case, log_path=log, on_line=on_line)
        common.run_command(["reconstructPar", "-latestTime"], cwd=case, log_path=log)
    else:
        common.run_command(["simpleFoam"], cwd=case, log_path=log, on_line=on_line)
    common.progress(out, 0.92, "sampling")
    grid = ground_grid(mesh, profile)
    points_model = grid.centres(mesh.bounds()[0][2])
    points_case = [frame.to_case(p) for p in points_model]
    (case / "system" / "truebexSample").write_text(sample_dict(points_case), encoding="utf-8")
    common.run_command(["postProcess", "-latestTime", "-dict", "system/truebexSample"], cwd=case, log_path=log)
    surface = newest(case / "postProcessing" / "buildingSurface", "*/*.raw")
    cloud = newest(case / "postProcessing" / "groundPoints", "*/*")
    if surface is None or cloud is None:
        raise common.EngineError("OpenFOAM wrote no samples")
    p_rows = parse_raw(surface.read_text(encoding="utf-8", errors="replace"), 1)
    u_rows = parse_raw(cloud.read_text(encoding="utf-8", errors="replace"), 3)
    uref = float(job.params.get("speed_ms", 5))
    dom = domain(case_tris, profile)
    p_match = match_nearest([centroid(t) for t in case_tris], p_rows, dom.h / 10)
    cp = [math.nan if r is None else r[3] / (0.5 * uref * uref) for r in p_match]
    speeds = grid_speeds(points_case, u_rows, grid.cell)
    info = {"cells": _cells(case), "iterations": state["iteration"], "converged": state["converged"]}
    result = build_result(job, mesh, cp, grid, speeds, entities, out, info)
    common.write_result(out, result)
    common.progress(out, 1.0, "done")


if __name__ == "__main__":
    sys.exit(common.main(run))
