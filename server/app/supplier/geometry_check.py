"""Checks on a geometry upload (PF8 `POST /supplier/geometry`), on the bytes
only: nothing is rendered or executed.

* The format comes from the file's first bytes, never from its name: a GLB
  starts `glTF`, an FBX `Kaydara FBX Binary` (or `; FBX` as text), a glTF or
  Truebex object (`tbxa`) is JSON, an OBJ is text with `v` / `f` lines. A
  ZIP (or anything else) renamed to `.glb` is refused; so is a name whose
  extension disagrees with the bytes.
* GLB and glTF: triangles counted from the accessors in the JSON (every
  mesh instance in the default scene), refused above 500 000; the bounding
  box from the POSITION accessors' min / max through the node transforms,
  in millimetres (glTF is in metres, +Y up, front +Z: X width, Y height,
  Z depth as contract §6.1's `dims_mm`), compared with the variant's
  `dims_mm`: more than 5 % apart on any side is a warning, not a refusal.
* Meshes compressed with an extension the app cannot read
  (`KHR_draco_mesh_compression`, `EXT_meshopt_compression`) are refused.
* OBJ: triangles counted from the faces; the size is not compared (OBJ
  carries no unit). FBX and tbxa: the app checks them when it imports.
"""

import json
import struct
from dataclasses import dataclass, field

import numpy as np

from ..market.media import GEOMETRY_FORMATS

MAX_BYTES = 100 * 1024 * 1024
MAX_TRIANGLES = 500_000
SIZE_TOLERANCE = 0.05
REFUSED_EXTENSIONS = ("KHR_draco_mesh_compression", "EXT_meshopt_compression")
# Node instances walked at most (a node graph that repeats itself is refused).
MAX_NODE_VISITS = 200_000


class GeometryRefused(Exception):
    def __init__(self, code: str, detail: str, data: dict | None = None) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.data = data or {}


@dataclass
class Checked:
    format: str
    triangles: int | None = None
    # [X width, Y height, Z depth] in millimetres, when the file says.
    measured_mm: list[int] | None = None
    warnings: list[dict] = field(default_factory=list)

    def json(self) -> dict:
        return {
            "format": self.format,
            "triangles": self.triangles,
            "measured_mm": self.measured_mm,
            "warnings": self.warnings,
        }


def sniff(data: bytes) -> str | None:
    """The format the bytes are, or None."""
    head = data[:64]
    if head.startswith(b"glTF"):
        return "glb"
    if head.startswith(b"Kaydara FBX Binary"):
        return "fbx"
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"\x1f\x8b", b"Rar!", b"7z\xbc\xaf", b"%PDF", b"MZ")):
        return None
    text = data[:4096].lstrip(b"\xef\xbb\xbf").lstrip()
    if text.startswith(b"; FBX"):
        return "fbx"
    if text.startswith(b"{"):
        try:
            doc = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError):
            return None
        if isinstance(doc, dict) and isinstance(doc.get("asset"), dict) and "version" in doc["asset"]:
            return "gltf"
        if isinstance(doc, dict) and ("assetDef" in doc or "assetVersion" in doc):
            return "tbxa"
        # Another JSON object: a Truebex object only when it is named .tbxa.
        return "json" if isinstance(doc, dict) else None
    try:
        sample = data[:65536].decode("utf-8")
    except UnicodeDecodeError:
        try:
            sample = data[:65535].decode("utf-8")  # a multi-byte character cut at the end
        except UnicodeDecodeError:
            return None
    starts = {line.split(None, 1)[0] for line in sample.splitlines() if line.strip() and not line.startswith("#")}
    if "v" in starts and starts <= {"v", "vt", "vn", "vp", "f", "o", "g", "s", "l", "p", "usemtl", "mtllib", "cstype", "deg", "curv", "parm", "end"}:
        return "obj"
    return None


def extension_of(filename: str) -> str | None:
    name = (filename or "").lower().rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1] if "." in name else None


# --- glTF -------------------------------------------------------------------------------


def _glb_json(data: bytes) -> dict:
    if len(data) < 20:
        raise GeometryRefused("bad_geometry_format", "The GLB file is cut short.")
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if version != 2:
        raise GeometryRefused("bad_geometry_format", f"GLB version {version}; export glTF 2.0.")
    chunk_len, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A or 20 + chunk_len > len(data):  # "JSON"
        raise GeometryRefused("bad_geometry_format", "The GLB file has no JSON chunk.")
    try:
        return json.loads(data[20 : 20 + chunk_len].decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise GeometryRefused("bad_geometry_format", "The GLB file's JSON cannot be read.")


def _node_matrix(node: dict) -> np.ndarray:
    if isinstance(node.get("matrix"), list) and len(node["matrix"]) == 16:
        return np.array(node["matrix"], dtype=float).reshape(4, 4).T  # column-major
    t = np.array(node.get("translation") or [0, 0, 0], dtype=float)
    x, y, z, w = (node.get("rotation") or [0, 0, 0, 1])[:4]
    r = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )
    s = np.diag(np.array(node.get("scale") or [1, 1, 1], dtype=float))
    m = np.eye(4)
    m[:3, :3] = r @ s
    m[:3, 3] = t
    return m


def _primitive_triangles(prim: dict, accessors: list) -> tuple[int, list | None, list | None]:
    mode = prim.get("mode", 4)
    pos = (prim.get("attributes") or {}).get("POSITION")
    pos_acc = accessors[pos] if isinstance(pos, int) and 0 <= pos < len(accessors) else None
    idx = prim.get("indices")
    count = None
    if isinstance(idx, int) and 0 <= idx < len(accessors):
        count = int(accessors[idx].get("count", 0))
    elif pos_acc is not None:
        count = int(pos_acc.get("count", 0))
    count = count or 0
    if mode == 4:
        tris = count // 3
    elif mode in (5, 6):
        tris = max(count - 2, 0)
    else:
        tris = 0  # points and lines draw no surface
    lo = pos_acc.get("min") if pos_acc else None
    hi = pos_acc.get("max") if pos_acc else None
    return tris, lo, hi


def check_gltf(doc: dict) -> Checked:
    required = set(doc.get("extensionsRequired") or [])
    refused = sorted(required & set(REFUSED_EXTENSIONS))
    if refused:
        raise GeometryRefused(
            "unsupported_extension", f"Export without mesh compression ({', '.join(refused)}).", {"extensions": refused}
        )
    accessors = doc.get("accessors") or []
    meshes = doc.get("meshes") or []
    nodes = doc.get("nodes") or []
    per_mesh = []
    for mesh in meshes:
        prims = [_primitive_triangles(p, accessors) for p in (mesh.get("primitives") or []) if isinstance(p, dict)]
        per_mesh.append(prims)

    triangles = 0
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    visits = 0

    def visit(index: int, parent: np.ndarray, depth: int) -> None:
        nonlocal triangles, lo, hi, visits
        visits += 1
        if visits > MAX_NODE_VISITS:
            raise GeometryRefused("bad_geometry_format", "The file's node tree is too large to check.")
        if depth > 64 or not (0 <= index < len(nodes)):
            return
        node = nodes[index]
        world = parent @ _node_matrix(node)
        mesh = node.get("mesh")
        if isinstance(mesh, int) and 0 <= mesh < len(per_mesh):
            for tris, pmin, pmax in per_mesh[mesh]:
                triangles += tris
                if pmin and pmax and len(pmin) >= 3 and len(pmax) >= 3:
                    corners = np.array(
                        [[x, y, z, 1.0] for x in (pmin[0], pmax[0]) for y in (pmin[1], pmax[1]) for z in (pmin[2], pmax[2])]
                    )
                    moved = (world @ corners.T).T[:, :3]
                    lo = np.minimum(lo, moved.min(axis=0))
                    hi = np.maximum(hi, moved.max(axis=0))
        for child in node.get("children") or []:
            if isinstance(child, int):
                visit(child, world, depth + 1)

    scenes = doc.get("scenes") or []
    scene = doc.get("scene", 0)
    if scenes and isinstance(scene, int) and 0 <= scene < len(scenes):
        for root in scenes[scene].get("nodes") or []:
            if isinstance(root, int):
                visit(root, np.eye(4), 0)
    else:  # no scene: every mesh once, untransformed
        for prims in per_mesh:
            for tris, pmin, pmax in prims:
                triangles += tris
                if pmin and pmax and len(pmin) >= 3 and len(pmax) >= 3:
                    lo = np.minimum(lo, np.array(pmin[:3], dtype=float))
                    hi = np.maximum(hi, np.array(pmax[:3], dtype=float))
    measured = None
    if np.all(np.isfinite(lo)) and np.all(np.isfinite(hi)):
        measured = [int(round(v)) for v in (hi - lo) * 1000.0]  # metres → mm
    return Checked(format="glb", triangles=triangles, measured_mm=measured)


def check_obj(data: bytes) -> Checked:
    triangles = 0
    for line in data.splitlines():
        if line.startswith(b"f ") or line.startswith(b"f\t"):
            triangles += max(len(line.split()) - 3, 0)
    return Checked(format="obj", triangles=triangles)


def check(data: bytes, filename: str, dims_mm: list[int] | None) -> Checked:
    """Raises GeometryRefused (422) or returns the checks with warnings."""
    if len(data) > MAX_BYTES:
        raise GeometryRefused("too_large", "A 3D file is at most 100 MB.")
    fmt = sniff(data)
    if fmt is None:
        raise GeometryRefused(
            "bad_geometry_format",
            "This is not a GLB, glTF, FBX, OBJ or Truebex object file (the format is read from the file itself).",
        )
    ext = extension_of(filename)
    if fmt == "json":
        if ext != "tbxa":
            raise GeometryRefused("bad_geometry_format", "This JSON file is neither glTF nor a Truebex object (.tbxa).")
        fmt = "tbxa"
    if ext and ext in GEOMETRY_FORMATS and ext != fmt:
        raise GeometryRefused(
            "bad_geometry_format", f"The file is named .{ext} but is a {fmt.upper()} file.", {"named": ext, "found": fmt}
        )
    if fmt == "glb":
        result = check_gltf(_glb_json(data))
    elif fmt == "gltf":
        result = check_gltf(json.loads(data.decode("utf-8-sig")))
        result.format = "gltf"
    elif fmt == "obj":
        result = check_obj(data)
    else:
        result = Checked(format=fmt)
    if result.triangles is not None and result.triangles > MAX_TRIANGLES:
        raise GeometryRefused(
            "too_many_triangles",
            f"{result.triangles:,} triangles; a product has at most {MAX_TRIANGLES:,}.",
            {"triangles": result.triangles, "max": MAX_TRIANGLES},
        )
    if result.format in ("glb", "gltf"):
        if result.measured_mm is None:
            result.warnings.append({"code": "no_mesh", "detail": "The file has no mesh with a known size."})
        elif dims_mm and len(dims_mm) == 3:
            off = [
                axis
                for axis, got, want in zip(("width", "height", "depth"), result.measured_mm, dims_mm)
                if want > 0 and abs(got - want) / want > SIZE_TOLERANCE
            ]
            if off:
                result.warnings.append(
                    {
                        "code": "size_differs",
                        "detail": f"The 3D file measures {' × '.join(map(str, result.measured_mm))} mm; "
                        f"the variant says {' × '.join(map(str, dims_mm))} mm ({', '.join(off)} more than 5 % apart).",
                        "measured_mm": result.measured_mm,
                        "dims_mm": list(dims_mm),
                    }
                )
    return result
