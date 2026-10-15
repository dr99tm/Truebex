"""A stand-in for `Truebex.exe -mwrender=<job.json>` (CL3) that answers a job
from the app's own render-jobs fixtures (contract render-jobs 1.1.0 §9: CL3's
renders of PR3's three rooms), so the worker and the whole loop can be tested
without a GPU.

    py -3.12 worker\\tests\\fake_truebex.py -mwrender=D:/w/<job>/job.json

Like CL3 it reads the job file (§6.1; a relative path resolves against the job
file's folder) and fails `bad_input` (exit 2, out_dir/error.json) when the file
breaks §6.1, names a snapshot, operations or base manifest that is not there,
or hands it an operation the snapshot already holds (`project.snapshot_seq`;
absent: the lowest operation's sequence minus 1, else `at_seq`). Otherwise it
writes into out_dir: manifest.json (§6.2), the tiles of the faces it
"rendered" under tiles/, render-log.json and a received-job.json copy of the
job file (for tests). Each of the job's views takes the fixture view with its
id (PR3's bedroom, entry and living), else the fixture view at its place in
the list. A `panorama` job gets manifest-panorama.json's faces. A `tiles` job
renders the faces manifest-tiles.json renders (the living room's west wall
moved: entry and living all six `light`, bedroom `w` `changed`) and carries the
rest from the base manifest; the wall goes back and forth on every edit (a
rendered face flips between the two manifests' tiles), so a viewer sees the
tiles swap. The fixture's sizes stand whatever the job file asks (512 px
faces, 256 px tiles, levels 256 and 512); a job file without
`project.project_id` gets the fixture's (CL3 reads it from the snapshot). A
`pack` job writes one small file.

FAKE_TRUEBEX_FAIL=<code> fails with that 5.10 code: error.json and the code's
exit (2 bad_input, 3 doc_too_new, 4 render_crash, 5 out_of_memory, 6 timeout,
7 engine_error; 4 for any other); FAKE_TRUEBEX_EXIT=<n> exits n (alone: with
no error.json, an app that died); FAKE_TRUEBEX_SLEEP=<s> sleeps first (cancel,
heartbeats, the wrapper's timeout). Fixtures: server/tests/contracts/render-jobs
(FAKE_TRUEBEX_FIXTURES overrides).
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
FACES = ("n", "e", "s", "w", "u", "d")
# -mwrender's exit codes (render-jobs 1.1.0, 5.10 per code).
EXIT = {"bad_input": 2, "doc_too_new": 3, "render_crash": 4, "out_of_memory": 5, "timeout": 6, "engine_error": 7}


def fail(out: Path, code: str, message: str, status: int | None = None) -> int:
    status = EXIT.get(code, 4) if status is None else status
    out.mkdir(parents=True, exist_ok=True)
    (out / "error.json").write_text(json.dumps({"code": code, "message": message}), encoding="utf-8")
    print(f"fake_truebex: {code}: {message} (exit {status})", file=sys.stderr)
    return status


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def template(templates: list[dict], vid: str, i: int) -> dict:
    """The fixture view with this id, else the one at the same place."""
    return next((v for v in templates if v["view"] == vid), templates[i % len(templates)])


def render(job: dict, base: dict | None) -> tuple[list[dict], int, int, dict]:
    """The manifest's views, the faces rendered and reused, and the fixture's `ms`."""
    pano, moved = load("manifest-panorama.json"), load("manifest-tiles.json")
    views = []
    if job["kind"] == "panorama":
        for i, vid in enumerate(job["views"]):
            views.append({**template(pano["views"], vid, i), "view": vid})
        return views, 6 * len(views), 0, pano["ms"]
    base_views = (base or {}).get("views") or []
    rendered = 0
    for i, vid in enumerate(job["views"]):
        full, after = template(pano["views"], vid, i), template(moved["views"], vid, i)
        before = next((v for v in base_views if v["view"] == vid), None) or (base_views[i] if i < len(base_views) else full)
        faces = {}
        for f in FACES:
            if after["faces"][f]["rendered"]:
                # The wall moves back when the base already shows it moved.
                back = before["faces"][f]["tiles"] == after["faces"][f]["tiles"]
                tiles = full["faces"][f]["tiles"] if back else after["faces"][f]["tiles"]
                faces[f] = {"rendered": True, "reason": after["faces"][f]["reason"], "tiles": tiles}
                rendered += 1
            else:
                faces[f] = {"rendered": False, "reason": "carried", "tiles": before["faces"][f]["tiles"]}
        views.append({**after, "view": vid, "faces": faces})
    return views, rendered, 6 * len(views) - rendered, moved["ms"]


def run(job_path: Path, job: dict) -> int:
    def path(p: str | None) -> Path | None:
        if not p:
            return None
        q = Path(p)
        return q if q.is_absolute() else job_path.parent / q

    out = path(job.get("out_dir")) or job_path.parent / "out"
    missing = [k for k in JOB_KEYS if k not in job]
    if missing or job.get("schema") != "truebex-render-job/1":
        return fail(out, "bad_input", f"job file breaks §6.1: missing {missing or 'schema'}")
    project = job["project"]
    tbxp = path(project.get("tbxp"))
    if tbxp is not None and not tbxp.is_file():
        return fail(out, "bad_input", f"the snapshot is missing ({project['tbxp']})")
    ops_path = path(project.get("ops"))
    if ops_path is not None and not ops_path.is_file():
        return fail(out, "bad_input", f"the operations are missing ({project['ops']})")
    ops = json.loads(ops_path.read_text(encoding="utf-8")).get("ops", []) if ops_path is not None else []
    seqs = [int(o["server_seq"]) for o in ops]
    at_seq = int(project["at_seq"])
    snapshot_seq = project.get("snapshot_seq")
    if snapshot_seq is None:
        snapshot_seq = min(seqs) - 1 if seqs else at_seq
    if any(s <= snapshot_seq or s > at_seq for s in seqs):
        return fail(out, "bad_input", f"operations {seqs} are not after the snapshot ({snapshot_seq}) up to {at_seq}")
    base = None
    if job["kind"] == "tiles":
        base_path = path(job.get("base_manifest"))
        if base_path is None or not base_path.is_file():
            return fail(out, "bad_input", "a tiles job needs its base manifest")
        base = json.loads(base_path.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "received-job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    print(f"fake_truebex: {job['kind']} {job['job_id']} at {at_seq} (snapshot {snapshot_seq}), {len(ops)} operations")
    if os.environ.get("FAKE_TRUEBEX_SLEEP"):
        time.sleep(float(os.environ["FAKE_TRUEBEX_SLEEP"]))
    if os.environ.get("FAKE_TRUEBEX_FAIL"):
        told = os.environ.get("FAKE_TRUEBEX_EXIT")
        return fail(out, os.environ["FAKE_TRUEBEX_FAIL"], "the fake was told to fail", int(told) if told else None)
    if os.environ.get("FAKE_TRUEBEX_EXIT"):
        status = int(os.environ["FAKE_TRUEBEX_EXIT"])
        print(f"fake_truebex: exit {status} without error.json", file=sys.stderr)
        return status
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

    views, rendered, reused, ms = render(job, base)
    for view in views:
        for face in view["faces"].values():
            if face["rendered"]:
                for row in face["tiles"]:
                    for sha in row:
                        shutil.copyfile(FIXTURES / "tiles" / f"{sha}.jpg", out / "tiles" / f"{sha}.jpg")
    manifest = {
        "schema": "truebex-tiles/1",
        "job_id": job["job_id"],
        "project_id": project.get("project_id") or load("manifest-panorama.json")["project_id"],
        "at_seq": at_seq,
        "app_version": "0.0.0-fake",
        "quality": job["quality"],
        "views": views,
        "faces_rendered": rendered,
        "faces_reused": reused,
        "ms": ms,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    faces_ms = [{"view": v["view"], "face": f, "rendered": x["rendered"], "reason": x["reason"]} for v in views for f, x in v["faces"].items()]
    (out / "render-log.json").write_text(
        json.dumps({"schema": "truebex-render-log/1", "job_id": job["job_id"], "app_version": "0.0.0-fake", "ms": ms, "faces": faces_ms}),
        encoding="utf-8",
    )
    print(f"fake_truebex: {rendered} faces rendered, {reused} carried")
    return 0


def main(argv: list[str]) -> int:
    arg = next((a for a in argv if a.startswith("-mwrender=")), None)
    if arg is None:
        print("usage: fake_truebex.py -mwrender=<job.json>", file=sys.stderr)
        return 2
    job_path = Path(arg.split("=", 1)[1])
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return fail(job_path.parent / "out", "bad_input", f"cannot read the job file: {exc}")
    return run(job_path, job)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
