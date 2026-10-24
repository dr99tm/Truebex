"""The `wind` runner: one wind direction on the uploaded building (PF11, PF11c).

    python3 -m runners.wind /job

OpenFOAM v2406 (GPL-3.0; run as a service on the platform's workers, never
shipped with the app), simpleFoam, steady RANS, render-jobs 1.2.0 §6.5.4:

1. The building (`inputs/geometry`, binary STL in metres: x east, y north,
   z up, z = 0 the site's ground datum; closed; AN3) is moved to the origin in
   plan and turned so the wind blows along +x (`direction_deg` is where the
   wind comes FROM, clockwise from true north: 0 = from north, 90 = an east
   wind). `inputs/surroundings` (other buildings, closed shells) are obstacles
   in the mesh, sampled for nothing; `inputs/terrain` (an open, upward-wound
   surface) is a second ground (absent: flat ground at z = 0).
2. The case: a box domain 5 H upstream, 15 H downstream, 5 H to each side and
   5 H above the tallest height H (COST Action 732, the AIJ guidelines),
   background cells H / n with n = 6, 10 or 20 cells per building side by the
   job's quality (the claim's profile), refined around the building
   (snappyHexMesh); the inlet after Richards and Hoxey (1993) from `speed_ms`
   at `reference_height_m` over the terrain class's z0 (OpenFOAM's
   atmBoundaryLayerInlet* conditions for U, k and epsilon or omega);
   rough-wall functions (nutkAtmRoughWallFunction) on the ground and the
   terrain, slip top and sides, zero pressure at the outlet;
   `turbulence_model` realizable k-epsilon (default) or k-omega SST;
   converged when every initial residual is below 1e-4, else stopped at 2000
   iterations (the profile).
3. `blockMesh`, `snappyHexMesh -overwrite`, `simpleFoam` (in parallel when
   the container has more than one core), then sampling: the kinematic
   pressure on the uploaded triangles (nearest boundary face) and the velocity
   on a grid of points `pedestrian_height_m` above the ground (above the
   terrain triangle under each point where there is one), 3 H around the
   building, cells of `grid_cell_mm` (coarsened by 1.25 until at most
   250 000 points: the grid's `cell_mm` says so).
4. The result (§6.3, §6.5.2): `pressure_coefficient` on faces (Cp = p /
   (½ Uref²), one value per uploaded triangle in their order, `entities` =
   the uploaded ids); grids `speed_ratio` (|U| / speed_ms, float32),
   `velocity` (3 x float32 a cell, m/s, turned back into x east, y north) and
   `comfort_lawson` (the profile's LDDC classes on the instantaneous speed,
   uint8), each with `origin_mm` the centre of cell (0, 0) (z = the
   pedestrian height), row by row from the south, NaN / 255 where nothing was
   sampled (inside a building, outside the domain); summary max_speed_ms,
   max_speed_ratio, iterations, residual (the largest of the last
   iteration's initial residuals), min_cp, max_cp, cells, converged. No
   winding is checked: a triangle wound inwards samples the same face.
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
RAS = {"realizable_ke": "realizableKE", "komega_sst": "kOmegaSST"}
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


def read_stl(path: Path, what: str = "geometry") -> Mesh:
    data = Path(path).read_bytes()
    if len(data) < 84:
        raise common.BadInput(f"the {what} is not a binary STL file")
    (n,) = struct.unpack_from("<I", data, 80)
    if n == 0 or len(data) != 84 + 50 * n:
        raise common.BadInput(f"the {what} is not a binary STL file (its size does not match its triangle count)")
    tris = []
    for i in range(n):
        v = struct.unpack_from("<12f", data, 84 + 50 * i)
        tris.append(((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])))
    return Mesh(tris)


def write_stl(path: Path, triangles: list, header: str = "truebex wind case") -> None:
    out = bytearray(header.encode("ascii").ljust(80, b" ")) + struct.pack("<I", len(triangles))
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
    datum (z = 0) kept, the wind along +x."""

    cx: float
    cy: float
    z0: float
    angle: float  # radians; case = rotate(model - centre, angle)

    @classmethod
    def for_wind(cls, mesh: Mesh, direction_deg: float) -> "Frame":
        lo, hi = mesh.bounds()
        d = math.radians(direction_deg)
        flow = (-math.sin(d), -math.cos(d))  # where the wind goes
        return cls((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0.0, -math.atan2(flow[1], flow[0]))

    def to_case(self, p) -> tuple[float, float, float]:
        x, y = p[0] - self.cx, p[1] - self.cy
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (x * c - y * s, x * s + y * c, p[2] - self.z0)

    def to_model(self, p) -> tuple[float, float, float]:
        c, s = math.cos(-self.angle), math.sin(-self.angle)
        x, y = p[0] * c - p[1] * s, p[0] * s + p[1] * c
        return (x + self.cx, y + self.cy, p[2] + self.z0)

    def vector_to_model(self, v) -> tuple[float, float, float]:
        """A velocity sampled in the case back into x east, y north (a turn, no shift)."""
        c, s = math.cos(-self.angle), math.sin(-self.angle)
        return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


def log_law_speed(z: float, uref: float, zref: float, z0: float) -> float:
    """The inlet's mean speed at height z (the atmospheric boundary layer's log law)."""
    return uref * math.log((max(z, 0.0) + z0) / z0) / math.log((zref + z0) / z0)


def lawson_class(speed: float, classes: list[dict]) -> int:
    """The profile's Lawson class (LDDC: 0 sitting … 4 uncomfortable), each class up to its speed."""
    for c in classes:
        if c.get("max_ms") is None or speed <= c["max_ms"]:
            return int(c["class"])
    return int(classes[-1]["class"])


def turbulence(params: dict) -> tuple[str, str]:
    """(OpenFOAM's RAS model, its second variable) for `turbulence_model`."""
    model = str(params.get("turbulence_model") or "realizable_ke").lower()
    if model not in RAS:
        raise common.BadInput(f"turbulence_model is one of {', '.join(RAS)}")
    return RAS[model], ("omega" if model == "komega_sst" else "epsilon")


# --- the case -----------------------------------------------------------------------------------


@dataclass
class Domain:
    lo: tuple[float, float, float]
    hi: tuple[float, float, float]
    cells: tuple[int, int, int]
    h: float
    inside: tuple[float, float, float]


def _span(tris: list | None, i: int) -> tuple[float, float]:
    values = [v[i] for t in tris or () for v in t]
    return (min(values), max(values)) if values else (math.inf, -math.inf)


def domain(case_tris: list, profile: dict, *, surroundings: list | None = None, terrain: list | None = None) -> Domain:
    """5 H upstream, 15 H downstream, 5 H to the sides and above the tallest height
    H (the building's or a surrounding's, above the ground); the ground at z = 0,
    or below where the terrain dips."""
    lo = [min(v[i] for t in case_tris for v in t) for i in range(3)]
    hi = [max(v[i] for t in case_tris for v in t) for i in range(3)]
    ground = min(0.0, _span(terrain, 2)[0])
    top = max(hi[2], _span(surroundings, 2)[1], _span(terrain, 2)[1])
    h = max(max(hi[2], _span(surroundings, 2)[1]) - 0.0, 3.0)
    d = profile.get("domain_h") or {"upstream": 5, "downstream": 15, "sides": 5, "top": 5}
    dlo = (lo[0] - d["upstream"] * h, lo[1] - d["sides"] * h, ground)
    dhi = (hi[0] + d["downstream"] * h, hi[1] + d["sides"] * h, top + d["top"] * h)
    cell = h / float(profile.get("cells_per_h", 10))
    cells = tuple(max(1, math.ceil((dhi[i] - dlo[i]) / cell)) for i in range(3))
    # A point in the fluid, upstream of the building, above every obstacle and the terrain, never on a cell face.
    z_in = max(h * 2, _span(terrain, 2)[1] + h)
    inside = (lo[0] - 2.5 * h + 0.0137 * cell, (lo[1] + hi[1]) / 2 + 0.0213 * cell, z_in + 0.0311 * cell)
    return Domain(dlo, dhi, cells, h, inside)


def _vec(v) -> str:
    return "(" + " ".join(f"{x:.6g}" for x in v) + ")"


def _patches(entries: dict[str, str]) -> str:
    return "".join(f"    {name:<8} {{ {body} }}\n" for name, body in entries.items())


def case_files(job: common.Job, case_tris: list, profile: dict, *, surroundings: list | None = None,
               terrain: list | None = None) -> dict[str, str]:
    """Every text file of the OpenFOAM case, by path inside the case."""
    p = job.params
    ras, second = turbulence(p)
    dom = domain(case_tris, profile, surroundings=surroundings, terrain=terrain)
    rough = (profile.get("terrain") or {}).get(p.get("terrain", "suburban")) or {"z0_m": 0.3}
    z0 = float(rough["z0_m"])
    uref, zref = float(p.get("speed_ms", 5)), float(p.get("reference_height_m", 10))
    iterations = int(profile.get("iterations_max", 2000))
    residual = float(profile.get("residual_target", 1e-4))
    levels = list(profile.get("refinement_levels") or [2, 3])
    ground_wf = str(profile.get("ground_wall_function") or "nutkAtmRoughWallFunction")
    ustar = KAPPA * uref / math.log((zref + z0) / z0)
    (x0, y0, z0d), (x1, y1, z1d) = dom.lo, dom.hi
    nx, ny, nz = dom.cells
    walls = ["building"] + (["surroundings"] if surroundings else [])
    grounds = ["ground"] + (["terrain"] if terrain else [])
    abl = (
        f"flowDir (1 0 0); zDir (0 0 1);\n        Uref            {uref:.6g};\n"
        f"        Zref            {zref:.6g};\n        z0              uniform {z0:.6g};\n        d               uniform 0;"
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
    surfaces = {"building": f"level ({levels[0]} {levels[-1]})"}
    if surroundings:
        surfaces["surroundings"] = f"level ({levels[0]} {levels[0]})"
    if terrain:
        surfaces["terrain"] = f"level ({levels[0]} {levels[0]})"
    geometry = "".join(f"    {name}.stl {{ type triSurfaceMesh; name {name}; }}\n" for name in surfaces)
    refinement = " ".join(f"{name} {{ {lv}; patchInfo {{ type wall; }} }}" for name, lv in surfaces.items())
    files["system/snappyHexMeshDict"] = HEADER.format(cls="dictionary", obj="snappyHexMeshDict") + f"""
castellatedMesh true;
snap            true;
addLayers       false;
geometry
{{
{geometry}}}
castellatedMeshControls
{{
    maxLocalCells 4000000;
    maxGlobalCells 8000000;
    minRefinementCells 10;
    nCellsBetweenLevels 3;
    features ();
    refinementSurfaces {{ {refinement} }}
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
    files["system/fvSchemes"] = HEADER.format(cls="dictionary", obj="fvSchemes") + f"""
ddtSchemes      {{ default steadyState; }}
gradSchemes     {{ default cellLimited Gauss linear 1; }}
divSchemes
{{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,{second}) bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}}
laplacianSchemes {{ default Gauss linear limited corrected 0.33; }}
interpolationSchemes {{ default linear; }}
snGradSchemes   {{ default limited corrected 0.33; }}
wallDist        {{ method meshWave; }}
"""
    files["system/fvSolution"] = HEADER.format(cls="dictionary", obj="fvSolution") + f"""
solvers
{{
    p {{ solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.1; }}
    "(U|k|{second})" {{ solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }}
}}
SIMPLE
{{
    nNonOrthogonalCorrectors 1;
    consistent      true;
    residualControl {{ p {residual:.3g}; U {residual:.3g}; "(k|{second})" {residual:.3g}; }}
}}
relaxationFactors {{ equations {{ U 0.9; "(k|{second})" 0.7; }} fields {{ p 0.9; }} }}
"""
    files["system/decomposeParDict"] = HEADER.format(cls="dictionary", obj="decomposeParDict") + """
numberOfSubdomains __CORES__;
method          scotch;
"""
    files["constant/transportProperties"] = HEADER.format(cls="dictionary", obj="transportProperties") + f"""
transportModel  Newtonian;
nu              {NU_AIR};
"""
    files["constant/turbulenceProperties"] = HEADER.format(cls="dictionary", obj="turbulenceProperties") + f"""
simulationType  RAS;
RAS {{ RASModel {ras}; turbulence on; printCoeffs on; }}
"""
    # Richards and Hoxey (1993): U = u*/kappa ln((z + z0) / z0), k = u*^2 / sqrt(Cmu),
    # epsilon = u*^3 / (kappa (z + z0)), omega = epsilon / (Cmu k), at the reference height inside.
    k_in = ustar * ustar / math.sqrt(CMU)
    eps_in = ustar ** 3 / (KAPPA * (zref + z0))
    omega_in = eps_in / (CMU * k_in)
    def field_file(cls: str, obj: str, dims: str, internal: str, inlet: str, outlet: str, wall: str, ground: str,
                   side: str = "type slip;") -> str:
        entries = {"inlet": inlet, "outlet": outlet}
        entries.update({g: ground for g in grounds})
        entries.update({w: wall for w in walls})
        entries.update({"top": side, "sides": side})
        return HEADER.format(cls=cls, obj=obj) + f"""
dimensions      {dims};
internalField   {internal};
boundaryField
{{
{_patches(entries)}}}
"""

    files["0/U"] = field_file(
        "volVectorField", "U", "[0 1 -1 0 0 0 0]", f"uniform ({uref:.6g} 0 0)",
        f"type atmBoundaryLayerInletVelocity;\n        {abl}", f"type inletOutlet; inletValue uniform (0 0 0); value uniform ({uref:.6g} 0 0);",
        "type noSlip;", "type noSlip;",
    )
    files["0/p"] = field_file(
        "volScalarField", "p", "[0 2 -2 0 0 0 0]", "uniform 0",
        "type zeroGradient;", "type fixedValue; value uniform 0;", "type zeroGradient;", "type zeroGradient;",
    )
    files["0/k"] = field_file(
        "volScalarField", "k", "[0 2 -2 0 0 0 0]", f"uniform {k_in:.6g}",
        f"type atmBoundaryLayerInletK;\n        {abl}", f"type inletOutlet; inletValue uniform {k_in:.6g}; value uniform {k_in:.6g};",
        f"type kqRWallFunction; value uniform {k_in:.6g};", f"type kqRWallFunction; value uniform {k_in:.6g};",
    )
    if second == "epsilon":
        files["0/epsilon"] = field_file(
            "volScalarField", "epsilon", "[0 2 -3 0 0 0 0]", f"uniform {eps_in:.6g}",
            f"type atmBoundaryLayerInletEpsilon;\n        {abl}", f"type inletOutlet; inletValue uniform {eps_in:.6g}; value uniform {eps_in:.6g};",
            f"type epsilonWallFunction; value uniform {eps_in:.6g};", f"type epsilonWallFunction; value uniform {eps_in:.6g};",
        )
    else:
        files["0/omega"] = field_file(
            "volScalarField", "omega", "[0 0 -1 0 0 0 0]", f"uniform {omega_in:.6g}",
            f"type atmBoundaryLayerInletOmega;\n        {abl}", f"type inletOutlet; inletValue uniform {omega_in:.6g}; value uniform {omega_in:.6g};",
            f"type omegaWallFunction; value uniform {omega_in:.6g};", f"type omegaWallFunction; value uniform {omega_in:.6g};",
        )
    files["0/nut"] = field_file(
        "volScalarField", "nut", "[0 2 -1 0 0 0 0]", "uniform 0",
        "type calculated; value uniform 0;", "type calculated; value uniform 0;",
        "type nutkWallFunction; value uniform 0;", f"type {ground_wf}; z0 uniform {z0:.6g}; value uniform 0;",
        side="type calculated; value uniform 0;",
    )
    return files


# --- sampling ------------------------------------------------------------------------------------


@dataclass
class Grid:
    origin: tuple[float, float]  # model x, y of the centre of cell (0, 0) (m)
    cell: float  # m
    nx: int
    ny: int
    height: float  # m above the ground (the pedestrian height)

    def points(self, terrain: list | None) -> list[tuple[float, float, float]]:
        """Cell centres row by row from j = 0 (the south row), i fastest, `height`
        above the terrain triangle under each (else above the datum, z = 0)."""
        under = TerrainIndex(terrain, self.cell) if terrain else None
        out = []
        for j in range(self.ny):
            y = self.origin[1] + j * self.cell
            for i in range(self.nx):
                x = self.origin[0] + i * self.cell
                z = under.z(x, y) if under is not None else None
                out.append((x, y, (z if z is not None else 0.0) + self.height))
        return out


class TerrainIndex:
    """The terrain's triangles bucketed by plan cell: `z(x, y)` is the height of
    the (highest) triangle whose plan holds the point, or None."""

    def __init__(self, tris: list, cell: float) -> None:
        self.tris = tris
        self.size = max(cell * 4, 1e-3)
        self.buckets: dict[tuple[int, int], list[int]] = {}
        for k, t in enumerate(tris):
            xs, ys = [v[0] for v in t], [v[1] for v in t]
            for bx in range(int(min(xs) // self.size), int(max(xs) // self.size) + 1):
                for by in range(int(min(ys) // self.size), int(max(ys) // self.size) + 1):
                    self.buckets.setdefault((bx, by), []).append(k)

    def z(self, x: float, y: float) -> float | None:
        best = None
        for k in self.buckets.get((int(x // self.size), int(y // self.size)), ()):
            a, b, c = self.tris[k]
            det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(det) < 1e-12:
                continue  # a vertical triangle has no plan
            l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
            l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
            l3 = 1.0 - l1 - l2
            if min(l1, l2, l3) < -1e-9:
                continue
            z = l1 * a[2] + l2 * b[2] + l3 * c[2]
            best = z if best is None else max(best, z)
        return best


def ground_grid(mesh: Mesh, profile: dict, params: dict) -> Grid:
    """The pedestrian grid: 3 H beyond the building's bounds (H its height above
    the datum, at least 3 m), cells of `grid_cell_mm` (coarser, by 1.25 steps,
    while more than the profile's 250 000 points)."""
    lo, hi = mesh.bounds()
    h = max(hi[2], 3.0)
    extent = float(profile.get("grid_extent_h", 3)) * h
    cell = float(params.get("grid_cell_mm", 1000)) / 1000.0
    cap = int(profile.get("grid_points_max", 250_000))
    x0, y0 = lo[0] - extent, lo[1] - extent

    def size(c: float) -> tuple[int, int]:
        return max(1, math.ceil((hi[0] + extent - x0) / c - 1e-9)), max(1, math.ceil((hi[1] + extent - y0) / c - 1e-9))

    nx, ny = size(cell)
    while nx * ny > cap:  # keep the sampled cloud bounded
        cell *= 1.25
        nx, ny = size(cell)
    return Grid((x0 + cell / 2, y0 + cell / 2), cell, nx, ny, float(params.get("pedestrian_height_m", 1.5)))


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


def grid_vectors(points: list, rows: list, cell: float) -> list[tuple[float, float, float] | None]:
    """U at each grid point in the case frame (None where the cloud dropped it:
    inside a building or outside the domain), matched to the nearest sample."""
    out: list[tuple[float, float, float] | None] = []
    for p, r in zip(points, match_nearest(points, rows, cell)):
        if r is None or (r[0] - p[0]) ** 2 + (r[1] - p[1]) ** 2 + (r[2] - p[2]) ** 2 > (cell / 4) ** 2:
            out.append(None)
        else:
            out.append((r[3], r[4], r[5]))
    return out


def grid_speeds(points: list, rows: list, cell: float) -> list[float | None]:
    """|U| at each grid point (None where nothing was sampled)."""
    return [None if v is None else math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) for v in grid_vectors(points, rows, cell)]


def model_velocities(frame: Frame, vectors: list) -> list[tuple[float, float, float] | None]:
    """The case's velocities turned back into the model frame (x east, y north)."""
    return [None if v is None else frame.vector_to_model(v) for v in vectors]


class SolverLog:
    """simpleFoam's log as it streams: the iteration, convergence, and the
    initial residual of every equation in the latest iteration."""

    _TIME = re.compile(r"^Time = (\d+)")
    _RESIDUAL = re.compile(r"Solving for (\w+), Initial residual = ([-+0-9.eE]+)")

    def __init__(self) -> None:
        self.iteration = 0
        self.converged = False
        self.current: dict[str, float] = {}
        self.last: dict[str, float] = {}

    def on_line(self, line: str) -> None:
        m = self._TIME.match(line)
        if m:
            if self.current:
                self.last = self.current
            self.current = {}
            self.iteration = int(m.group(1))
            return
        m = self._RESIDUAL.search(line)
        if m:
            try:
                self.current[m.group(1)] = float(m.group(2))
            except ValueError:
                pass
        elif "SIMPLE solution converged" in line:
            self.converged = True

    @property
    def residual(self) -> float:
        """The largest initial residual of the last iteration (NaN before one)."""
        latest = self.current or self.last
        return max(latest.values()) if latest else math.nan


def centroid(tri) -> tuple[float, float, float]:
    return tuple(sum(v[i] for v in tri) / 3 for i in range(3))


def newest(dir_: Path, pattern: str) -> Path | None:
    found = sorted(dir_.glob(pattern), key=lambda p: p.stat().st_mtime) if dir_.exists() else []
    return found[-1] if found else None


# --- the result ------------------------------------------------------------------------------------


def build_result(job: common.Job, mesh: Mesh, cp: list[float], grid: Grid, velocities: list,
                 entities: bytes | None, out_dir: Path, info: dict) -> dict:
    """§6.3 / §6.5.2's wind result; `velocities` per grid cell in the model frame (or None)."""
    if len(cp) != mesh.count:
        raise common.EngineError(f"{len(cp)} pressure values for {mesh.count} triangles")
    if len(velocities) != grid.nx * grid.ny:
        raise common.EngineError(f"{len(velocities)} velocities for {grid.nx} x {grid.ny} cells")
    uref = float(job.params.get("speed_ms", 5))
    classes = (job.profile.get("lawson") or {}).get("classes") or [
        {"class": 0, "max_ms": 4.0}, {"class": 1, "max_ms": 6.0}, {"class": 2, "max_ms": 8.0}, {"class": 3, "max_ms": 10.0}, {"class": 4, "max_ms": None},
    ]
    speeds = [None if v is None else math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) for v in velocities]
    lawson = [NO_CLASS if s is None else lawson_class(s, classes) for s in speeds]
    ratio = [math.nan if s is None else s / uref for s in speeds]
    vector = [x for v in velocities for x in ((math.nan,) * 3 if v is None else v)]
    origin = [grid.origin[0] * 1000, grid.origin[1] * 1000, grid.height * 1000]
    fields = [common.field(out_dir, "pressure_coefficient", "1", "faces", cp, entities=entities or bytes(16 * mesh.count))]
    grids = [
        common.grid(out_dir, "speed_ratio", "1", origin, grid.cell * 1000, grid.nx, grid.ny, ratio),
        common.grid(out_dir, "velocity", "m/s", origin, grid.cell * 1000, grid.nx, grid.ny, vector, components=3),
        common.grid(out_dir, "comfort_lawson", "class", origin, grid.cell * 1000, grid.nx, grid.ny, lawson, "uint8"),
    ]
    known = [s for s in speeds if s is not None]
    finite_cp = [c for c in cp if math.isfinite(c)]
    residual = float(info.get("residual", math.nan))
    summary = {
        "max_speed_ms": max(known) if known else math.nan,
        "max_speed_ratio": max(known) / uref if known else math.nan,
        "iterations": int(info.get("iterations", 0)),
        "residual": residual,
        "min_cp": min(finite_cp) if finite_cp else math.nan,
        "max_cp": max(finite_cp) if finite_cp else math.nan,
        **{k: v for k, v in info.items() if k not in ("iterations", "residual")},
    }
    result = common.result(job, common.engine("openfoam", VERSION, "wind"), summary, fields, grids)
    if math.isfinite(residual):
        result["summary"]["residual"] = float(f"{residual:.6g}")  # a small number: significant digits, not decimals
    return result


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
    turbulence(job.params)
    mesh = read_stl(job.input("geometry"))
    entities_path = job.input("entities", required=False)
    entities = entities_path.read_bytes() if entities_path else None
    if entities is not None and len(entities) != 16 * mesh.count:
        raise common.BadInput("the entities file needs 16 bytes per triangle of the geometry")
    others = job.input("surroundings", required=False)
    others = read_stl(others, "surroundings") if others else None
    ground = job.input("terrain", required=False)
    ground = read_stl(ground, "terrain") if ground else None
    frame = Frame.for_wind(mesh, float(job.params.get("direction_deg", 0)))

    def to_case(m: Mesh | None) -> list | None:
        return [tuple(frame.to_case(v) for v in t) for t in m.triangles] if m is not None else None

    case_tris, case_others, case_ground = to_case(mesh), to_case(others), to_case(ground)
    case = job.dir / "case"
    shutil.rmtree(case, ignore_errors=True)
    cores = common.available_cores()
    for rel, text in case_files(job, case_tris, profile, surroundings=case_others, terrain=case_ground).items():
        path = case / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.replace("__CORES__", str(cores)), encoding="utf-8")
    write_stl(case / "constant" / "triSurface" / "building.stl", case_tris)
    if case_others:
        write_stl(case / "constant" / "triSurface" / "surroundings.stl", case_others, "truebex wind surroundings")
    if case_ground:
        write_stl(case / "constant" / "triSurface" / "terrain.stl", case_ground, "truebex wind terrain")
    log = case / "log"
    common.progress(out, 0.05, "meshing")
    common.run_command(["blockMesh"], cwd=case, log_path=log)
    common.run_command(["snappyHexMesh", "-overwrite"], cwd=case, log_path=log)
    iterations = int(profile.get("iterations_max", 2000))
    solver = SolverLog()

    def on_line(line: str) -> None:
        before = solver.iteration
        solver.on_line(line)
        if solver.iteration != before and solver.iteration % 25 == 0:
            common.progress(out, 0.2 + 0.7 * solver.iteration / iterations, f"solving, iteration {solver.iteration}")

    common.progress(out, 0.2, "solving")
    if cores > 1:
        common.run_command(["decomposePar", "-force"], cwd=case, log_path=log)
        common.run_command(["mpirun", "-np", str(cores), "simpleFoam", "-parallel"], cwd=case, log_path=log, on_line=on_line)
        common.run_command(["reconstructPar", "-latestTime"], cwd=case, log_path=log)
    else:
        common.run_command(["simpleFoam"], cwd=case, log_path=log, on_line=on_line)
    common.progress(out, 0.92, "sampling")
    grid = ground_grid(mesh, profile, job.params)
    points_case = [frame.to_case(p) for p in grid.points(ground.triangles if ground else None)]
    (case / "system" / "truebexSample").write_text(sample_dict(points_case), encoding="utf-8")
    common.run_command(["postProcess", "-latestTime", "-dict", "system/truebexSample"], cwd=case, log_path=log)
    surface = newest(case / "postProcessing" / "buildingSurface", "*/*.raw")
    cloud = newest(case / "postProcessing" / "groundPoints", "*/*")
    if surface is None or cloud is None:
        raise common.EngineError("OpenFOAM wrote no samples")
    p_rows = parse_raw(surface.read_text(encoding="utf-8", errors="replace"), 1)
    u_rows = parse_raw(cloud.read_text(encoding="utf-8", errors="replace"), 3)
    uref = float(job.params.get("speed_ms", 5))
    dom = domain(case_tris, profile, surroundings=case_others, terrain=case_ground)
    p_match = match_nearest([centroid(t) for t in case_tris], p_rows, dom.h / 10)
    cp = [math.nan if r is None else r[3] / (0.5 * uref * uref) for r in p_match]
    velocities = model_velocities(frame, grid_vectors(points_case, u_rows, grid.cell))
    info = {"cells": _cells(case), "iterations": solver.iteration, "converged": solver.converged, "residual": solver.residual}
    result = build_result(job, mesh, cp, grid, velocities, entities, out, info)
    common.write_result(out, result)
    common.progress(out, 1.0, "done")


if __name__ == "__main__":
    sys.exit(common.main(run))
