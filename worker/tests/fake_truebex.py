"""A stand-in for `Truebex.exe -mwrender=<job.json>` (CL3) that writes the
render-jobs fixture manifest and tiles, so the worker and the whole loop can
be tested before the app's headless mode lands.

    py -3.12 worker\\tests\\fake_truebex.py -mwrender=D:/w/<job>/job.json

It checks the job file against §6.1 (exit 2 and error.json `bad_input` when it
breaks it), then writes into `out_dir`: `manifest.json` (§6.2), the tiles of
the faces it "rendered" under `tiles/`, `render-log.json` and a
`received-job.json` copy of the job file (for tests). A `panorama` job gets
`manifest-panorama.json`; a `tiles` job re-renders the north and east faces
(the fixture's moved wall) and carries the other four from the base manifest,
toggling the wall between its two positions on every edit so a viewer sees
the tiles swap. A `pack` job writes one small file.

FAKE_TRUEBEX_FAIL=<code> exits 3 with that error code; FAKE_TRUEBEX_SLEEP=<s>
sleeps first (to test cancel and heartbeats). Fixtures:
server/tests/contracts/render-jobs (FAKE_TRUEBEX_FIXTURES overrides).
"""

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(os.environ.get("FAKE_TRUEBEX_FIXTURES") or ROOT / "server" / "tests" / "contracts" / "render-jobs")
JOB_KEYS = ("schema", "job_id", "kind", "quality", "seed", "project", "views", "changed", "base_manifest", "face_px", "tile_px", "jpeg_quality", "out_dir")
RENDERED = ("n", "e")


def fail(out: Path, code: str, message: str, status: int) -> int:
    out.mkdir(parents=True, exist_ok=True)
    (out / "error.json").write_text(json.dumps({"code": code, "message": message}), encoding="utf-8")
    print(f"fake_truebex: {code}: {message}", file=sys.stderr)
    return status


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    arg = next((a for a in argv if a.startswith("-mwrender=")), None)
    if arg is None:
        print("usage: fake_truebex.py -mwrender=<job.json>", file=sys.stderr)
        return 2
    job_path = Path(arg.split("=", 1)[1])
    job = json.loads(job_path.read_text(encoding="utf-8"))
    out = Path(job.get("out_dir") or job_path.parent / "out")
    missing = [k for k in JOB_KEYS if k not in job]
    if missing or job.get("schema") != "truebex-render-job/1":
        return fail(out, "bad_input", f"job file breaks §6.1: missing {missing or 'schema'}", 2)
    project = job["project"]
    if project.get("tbxp") and not Path(project["tbxp"]).is_file():
        return fail(out, "bad_input", "the snapshot is missing", 2)
    ops = json.loads(Path(project["ops"]).read_text(encoding="utf-8")) if project.get("ops") else {"ops": []}
    out.mkdir(parents=True, exist_ok=True)
    (out / "received-job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    print(f"fake_truebex: {job['kind']} {job['job_id']} at {project['at_seq']}, {len(ops.get('ops', []))} operations")
    if os.environ.get("FAKE_TRUEBEX_SLEEP"):
        time.sleep(float(os.environ["FAKE_TRUEBEX_SLEEP"]))
    if os.environ.get("FAKE_TRUEBEX_FAIL"):
        return fail(out, os.environ["FAKE_TRUEBEX_FAIL"], "the fake was told to fail", 3)
    (out / "tiles").mkdir(exist_ok=True)

    if job["kind"] == "pack":
        data = b"Truebex presentation pack (stand-in)\n" + job["job_id"].encode()
        (out / "pack.txt").write_bytes(data)
        manifest = {
            "schema": "truebex-pack/1", "job_id": job["job_id"],
            "files": [{"name": "pack.txt", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "content_type": "text/plain"}],
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return 0

    pano = load("manifest-panorama.json")
    moved = load("manifest-tiles.json")
    view_tpl = pano["views"][0]
    if job["kind"] == "panorama":
        faces = {f: dict(face) for f, face in view_tpl["faces"].items()}
        rendered = list(faces)
    else:
        base = json.loads(Path(job["base_manifest"]).read_text(encoding="utf-8"))
        base_view = {v["view"]: v for v in base["views"]}
        first = base_view.get(job["views"][0]) or base["views"][0]
        # The fixture wall moves back and forth on every edit.
        wall_moved = first["faces"]["n"]["tiles"] == moved["views"][0]["faces"]["n"]["tiles"]
        source = pano if wall_moved else moved
        faces = {}
        for f, face in first["faces"].items():
            if f in RENDERED:
                faces[f] = {"rendered": True, "reason": "changed", "tiles": source["views"][0]["faces"][f]["tiles"]}
            else:
                faces[f] = {"rendered": False, "reason": "carried", "tiles": face["tiles"]}
        rendered = list(RENDERED)
    views = []
    for vid in job["views"]:
        if job["kind"] == "tiles":
            carried = base_view.get(vid) or first
            view_faces = {
                f: (faces[f] if f in RENDERED else {"rendered": False, "reason": "carried", "tiles": carried["faces"][f]["tiles"]})
                for f in faces
            }
        else:
            view_faces = faces
        views.append({**view_tpl, "view": vid, "faces": view_faces})
    for view in views:
        for face in view["faces"].values():
            if face["rendered"]:
                for row in face["tiles"]:
                    for sha in row:
                        shutil.copyfile(FIXTURES / "tiles" / f"{sha}.jpg", out / "tiles" / f"{sha}.jpg")
    manifest = {
        "schema": "truebex-tiles/1",
        "job_id": job["job_id"],
        "project_id": project.get("project_id"),
        "at_seq": project["at_seq"],
        "app_version": "0.0.0-fake",
        "quality": job["quality"],
        "views": views,
        "faces_rendered": len(rendered) * len(views),
        "faces_reused": (6 - len(rendered)) * len(views),
        "ms": {"open": 40, "render": 120 * len(rendered), "encode": 10},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "render-log.json").write_text(
        json.dumps({"steps": manifest["ms"], "faces": {f: 120 for f in rendered}}), encoding="utf-8"
    )
    print(f"fake_truebex: rendered {', '.join(rendered)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
