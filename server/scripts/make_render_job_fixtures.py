"""Write the render-jobs contract fixtures (contracts/render-jobs.md §9) into
server/tests/contracts/render-jobs/.

    py -3.12 scripts\\make_render_job_fixtures.py      (needs Pillow for the JPEG tiles)

Deterministic: re-running with the same Pillow reproduces the same bytes. CL3
owns the master copy (`Docs/roadmap/fixtures/contracts/render-jobs/` in the app
repo) once it lands; until then PF6 stages this set, written to the letter of
§5.6, §5.7, §6.1, §6.2 and §6.3. The tiles are drawn stand-ins (a coloured
face with its compass letter and a wall), not renders of the house.
"""

import hashlib
import io
import json
import shutil
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "render-jobs"

PROJECT_ID = "0199c6a2f1007a3c8b5e2d4f6a7b8c9d"  # the project-log fixtures' "House"
VIEW_LIVING = "0199c6a2e00070058000000000000001"  # a saved view, "Living room"
WALL_MOVED = "0199c6a2e00070018000000000000001"  # the project-log fixtures' first wall
JOB_PANORAMA = "a11ce000000000000000000000000001"
JOB_TILES = "a11ce000000000000000000000000002"
LEASE_ID = "1ea5e000000000000000000000000001"
UPLOAD_ID = "0b10ad00000000000000000000000001"
APP_VERSION = "1.1.0"
FACES = ("n", "e", "s", "w", "u", "d")
LEVELS = [512, 1024]
TILE_PX = 512
FACE_PX = 1024
COLOURS = {
    "n": (196, 120, 92),
    "e": (92, 150, 196),
    "s": (120, 176, 104),
    "w": (176, 140, 200),
    "u": (232, 228, 214),
    "d": (122, 96, 74),
}
SNAPSHOT = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "project-log" / "snapshot-0000.tbxp"


def dump(obj) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def face_image(face: str, wall_x: int | None) -> Image.Image:
    """A 1024 px face: its colour, a 128 px grid, its letter, and (for the
    side faces) a dark wall whose left edge sits at `wall_x`."""
    img = Image.new("RGB", (FACE_PX, FACE_PX), COLOURS[face])
    draw = ImageDraw.Draw(img)
    r, g, b = COLOURS[face]
    line = (max(r - 40, 0), max(g - 40, 0), max(b - 40, 0))
    for p in range(0, FACE_PX + 1, 128):
        draw.line([(p, 0), (p, FACE_PX)], fill=line, width=3)
        draw.line([(0, p), (FACE_PX, p)], fill=line, width=3)
    if wall_x is not None:
        draw.rectangle([wall_x, 300, wall_x + 220, 900], fill=(48, 44, 40))
    font = ImageFont.load_default(size=260)
    draw.text((FACE_PX // 2, FACE_PX // 2), face.upper(), fill=(255, 255, 255), font=font, anchor="mm")
    return img


def jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=False, progressive=False)
    return buf.getvalue()


def cut(img: Image.Image) -> list[list[bytes]]:
    """Per level, its tiles row by row from the top-left (§6.2)."""
    levels = []
    for size in LEVELS:
        scaled = img if size == FACE_PX else img.resize((size, size), Image.Resampling.LANCZOS)
        n = max(1, size // TILE_PX)
        tiles = []
        for row in range(n):
            for col in range(n):
                box = (col * TILE_PX, row * TILE_PX, (col + 1) * TILE_PX, (row + 1) * TILE_PX)
                tiles.append(jpeg(scaled.crop(box)))
        levels.append(tiles)
    return levels


def store(tiles_dir: Path, levels: list[list[bytes]]) -> list[list[str]]:
    out = []
    for level in levels:
        shas = []
        for data in level:
            sha = hashlib.sha256(data).hexdigest()
            (tiles_dir / f"{sha}.jpg").write_bytes(data)
            shas.append(sha)
        out.append(shas)
    return out


WALL_BEFORE = {"n": 140, "e": 600, "s": None, "w": 380, "u": None, "d": None}
WALL_AFTER = {"n": 520, "e": 260}  # the moved wall shows on the north and east faces


def manifest(job_id: str, at_seq: int, faces: dict, rendered: int, reused: int, ms: dict) -> dict:
    return {
        "schema": "truebex-tiles/1",
        "job_id": job_id,
        "project_id": PROJECT_ID,
        "at_seq": at_seq,
        "app_version": APP_VERSION,
        "quality": "standard",
        "views": [
            {
                "view": VIEW_LIVING,
                "title": "Living room",
                "eye_mm": [4200, 1800, 1600],
                "face_px": FACE_PX,
                "tile_px": TILE_PX,
                "levels": LEVELS,
                "faces": faces,
            }
        ],
        "faces_rendered": rendered,
        "faces_reused": reused,
        "ms": ms,
    }


def job_file(job_id: str, kind: str, at_seq: int, ops: str, changed: list[str], base: str | None) -> dict:
    root = f"Saved/RenderJobs/{job_id}"
    return {
        "schema": "truebex-render-job/1",
        "job_id": job_id,
        "kind": kind,
        "quality": "standard",
        "seed": 1,
        "project": {
            "tbxp": "Docs/roadmap/fixtures/Z0-baseline.tbxp",
            "tbxpack": None,
            "ops": f"Docs/roadmap/fixtures/contracts/render-jobs/{ops}",
            "at_seq": at_seq,
        },
        "views": [VIEW_LIVING],
        "changed": changed,
        "base_manifest": base,
        "face_px": FACE_PX,
        "tile_px": TILE_PX,
        "jpeg_quality": 85,
        "out_dir": f"{root}/out",
    }


def record(job_id: str, kind: str, state: str, at_seq: int, **extra) -> dict:
    base = {
        "job_id": job_id,
        "kind": kind,
        "state": state,
        "rev": 2,
        "project_id": PROJECT_ID,
        "at_seq": at_seq,
        "progress": 0,
        "message": "",
        "created_at": "2026-10-09T11:00:00Z",
        "started_at": None,
        "finished_at": None,
        "attempts": 0,
        "cost_units_estimate": 1.6,
        "cost_units": None,
        "output_ready": False,
        "error": None,
    }
    base.update(extra)
    return base


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    tiles_dir = OUT / "tiles"
    tiles_dir.mkdir(parents=True)

    # A full set: one view, levels 512 and 1024, six faces rendered.
    full = {}
    for face in FACES:
        hashes = store(tiles_dir, cut(face_image(face, WALL_BEFORE[face])))
        full[face] = {"rendered": True, "reason": "full", "tiles": hashes}
    pano = manifest(JOB_PANORAMA, 0, full, 6, 0, {"open": 3100, "render": 21000, "encode": 900})
    (OUT / "manifest-panorama.json").write_bytes(dump(pano))

    # A partial update after the wall moved: two faces rendered, four carried.
    partial = {}
    for face in FACES:
        if face in WALL_AFTER:
            hashes = store(tiles_dir, cut(face_image(face, WALL_AFTER[face])))
            partial[face] = {"rendered": True, "reason": "changed", "tiles": hashes}
        else:
            partial[face] = {"rendered": False, "reason": "carried", "tiles": full[face]["tiles"]}
    tiles = manifest(JOB_TILES, 1, partial, 2, 4, {"open": 3000, "render": 7100, "encode": 300})
    (OUT / "manifest-tiles.json").write_bytes(dump(tiles))

    (OUT / "job-panorama.json").write_bytes(dump(job_file(JOB_PANORAMA, "panorama", 0, "ops-empty.json", [], None)))
    (OUT / "job-tiles.json").write_bytes(
        dump(
            job_file(
                JOB_TILES, "tiles", 1, "ops-move-wall.json", [WALL_MOVED],
                "Docs/roadmap/fixtures/contracts/render-jobs/manifest-panorama.json",
            )
        )
    )
    (OUT / "ops-empty.json").write_bytes(dump({"ops": [], "head_seq": 0, "more": False}))
    move = {
        "op_id": hashlib.sha256(b"render-jobs move wall").hexdigest()[:32],
        "server_seq": 1,
        "replica_id": "5e1d0c0ffee000000000000000000b07",
        "author": "0199c6a2f0007000a000000000000007",
        "author_kind": "person",
        "at": "2026-10-09T11:00:00.000Z",
        "kind": "delta",
        "name": "Move wall",
        "base_seq": 0,
        "touched": [WALL_MOVED],
        "delta_format": "o5/38",
        "delta": "VEJYRHsic3RhbmRfaW4iOnRydWV9",
        "action": None,
        "restore": None,
    }
    (OUT / "ops-move-wall.json").write_bytes(dump({"ops": [move], "head_seq": 1, "more": False}))

    # An analysis result (§6.3): arrays are little-endian files named by SHA-256.
    cp = struct.pack("<8f", -0.8, -0.6, -0.35, 0.1, 0.45, 0.7, 0.9, -0.2)
    ids = b"".join(bytes.fromhex(f"0199c6a2e00070018{n:015x}") for n in range(1, 9))
    comfort = bytes([0, 0, 1, 1, 0, 1, 2, 1, 1, 2, 3, 2, 0, 1, 1, 0])
    arrays = {}
    for data in (cp, ids, comfort):
        sha = hashlib.sha256(data).hexdigest()
        arrays[data] = sha
        (OUT / f"wind-{sha[:12]}.bin").write_bytes(data)
    wind = {
        "schema": "truebex-analysis/1",
        "kind": "wind",
        "project_id": PROJECT_ID,
        "at_seq": 12,
        "params": {"speed_ms": 5, "direction_deg": 225, "reference_height_m": 10, "terrain": "suburban", "comfort": "lawson"},
        "engine": {"name": "cfd-solver", "version": "1", "image": "sha256:" + hashlib.sha256(b"solver image").hexdigest()},
        "summary": {"max_speed_ms": 7.2},
        "fields": [
            {
                "name": "pressure_coefficient", "unit": "1", "on": "faces", "count": 8,
                "values": arrays[cp], "entities": arrays[ids],
            }
        ],
        "grids": [
            {
                "name": "comfort_lawson", "unit": "class", "origin_mm": [-20000, -20000, 1500], "cell_mm": 500,
                "nx": 4, "ny": 4, "values": arrays[comfort],
            }
        ],
        "report": None,
    }
    (OUT / "wind-result.json").write_bytes(dump(wind))

    usage = {
        "period_start": "2026-10-01T00:00:00Z",
        "period_end": "2026-11-01T00:00:00Z",
        "used_cu": 41.2,
        "limit_cu": 600,
        "remaining_cu": 558.8,
        "classes": {"gpu-std": 1.0, "cpu-8": 0.25},
        "by_kind": {"tiles": 30.1, "wind": 11.1},
    }
    (OUT / "usage.json").write_bytes(dump(usage))

    snap = SNAPSHOT.read_bytes()
    claim = {
        "job": record(JOB_TILES, "tiles", "claimed", 1, attempts=0),
        "lease_id": LEASE_ID,
        "lease_expires_at": "2026-10-09T11:02:00Z",
        "inputs": {
            "snapshot": {
                "at_seq": 0,
                "tbxp": {"sha256": hashlib.sha256(snap).hexdigest(), "bytes": len(snap), "url": "https://api.example.invalid/files/snapshot"},
                "tbxpack": None,
            },
            "ops_url": "https://api.example.invalid/files/ops",
            "base_manifest_url": "https://api.example.invalid/files/base-manifest",
            "files": {},
        },
        "output_upload": {"upload_id": UPLOAD_ID, "part_bytes": 8388608},
    }
    (OUT / "claim.json").write_bytes(dump(claim))

    count = len(list(tiles_dir.iterdir()))
    readme = f"""# Render-jobs contract fixtures (`contracts/render-jobs.md` v1.0.0, §9)

Copied, never edited: the app side is authoritative for these files.

On 2026-10-10 the app repository had no `Docs/roadmap/fixtures/contracts/render-jobs/` folder yet (CL3 creates
it), so PF6 wrote this set to the letter of `render-jobs.md` §5.6, §5.7, §6.1, §6.2 and §6.3 with
`server/scripts/make_render_job_fixtures.py` (deterministic for one Pillow version) and staged it here. CL3
copies the folder into the app repo (or replaces it with its own, after which this folder is re-copied).

| File | Holds |
|---|---|
| `job-panorama.json`, `job-tiles.json` | §6.1 job files against `Docs/roadmap/fixtures/Z0-baseline.tbxp` (paths relative to the app repo) |
| `ops-empty.json`, `ops-move-wall.json` | the operations those job files name (a project-log 5.7 body): none, and one "Move wall" |
| `manifest-panorama.json` | a full set: one view ("Living room"), levels 512 and 1024, six faces rendered |
| `manifest-tiles.json` | the partial update after the wall moved: `n` and `e` rendered (`changed`), four faces carried |
| `tiles/` | the {count} JPEG tiles both manifests name, `<sha256>.jpg`, 512 px, quality 85 (drawn stand-ins) |
| `wind-result.json`, `wind-*.bin` | an analysis result (§6.3) whose fields name the project-log fixtures' wall ids |
| `usage.json`, `claim.json` | a 5.6 answer and a 5.7 answer (URLs are placeholders) |

The project id and the wall ids are the project-log fixtures' (`../project-log/`).
"""
    (OUT / "README.md").write_bytes(readme.encode("utf-8"))
    (OUT / ".gitattributes").write_bytes(b"* -text\n")
    print(f"wrote {OUT} ({count} tiles)")


if __name__ == "__main__":
    main()
