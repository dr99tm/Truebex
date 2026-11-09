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

FAKE_TRUEBEX_FACE_FILES=1 writes render-jobs 1.4's headset files as CL3's
worker will (PR5; CL3 does not yet): per rendered face an `id` (8-bit grey PNG
at levels[0] px, a few entities in bands), its `ids` (truebex-ids/1) and a
`depth` (16-bit grey PNG, millimetres) under tiles/ as `<sha256>.png` /
`.json`, and the face's `version` (1, then the base face's + 1) and `op_seq`
(the job's at_seq); a carried face keeps the base face's; a panorama writes a
truebex-tour/1 tour (a node per view, linked in order), an update carries the
base's tour without writing it again.

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
import struct
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(os.environ.get("FAKE_TRUEBEX_FIXTURES") or ROOT / "server" / "tests" / "contracts" / "render-jobs")
JOB_KEYS = ("schema", "job_id", "kind", "quality", "seed", "project", "views", "changed", "base_manifest", "face_px", "tile_px", "jpeg_quality", "out_dir")
FACES = ("n", "e", "s", "w", "u", "d")
# -mwrender's exit codes (render-jobs 1.1.0, 5.10 per code).
EXIT = {"bad_input": 2, "doc_too_new": 3, "render_crash": 4, "out_of_memory": 5, "timeout": 6, "engine_error": 7}
PNG_SIGNATURE = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
FACE_KEYS = ("id", "ids", "depth", "version", "op_seq")


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


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def grey_png(px: int, bits: int, row_value) -> bytes:
    """A px x px grey PNG (CadVrEdits' formats: 8-bit id, 16-bit depth), one value a row."""
    raw = b"".join(bytes(1) + row_value(y).to_bytes(bits // 8, "big") * px for y in range(px))
    ihdr = struct.pack(">IIBBBBB", px, px, bits, 0, 0, 0, 0)
    return PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


def put(out: Path, data: bytes, ext: str) -> str:
    sha = hashlib.sha256(data).hexdigest()
    (out / "tiles" / f"{sha}.{ext}").write_bytes(data)
    return sha


def face_files(out: Path, view: str, name: str, face: dict, px: int) -> None:
    """A rendered face's id, ids and depth, from its first tile's hash (a new picture, new files)."""
    seed = hashlib.sha256(f"{view}/{name}/{face['tiles'][0][0]}".encode()).hexdigest()
    n, shift, start = 1 + int(seed[:2], 16) % 6, int(seed[2:4], 16), int(seed[4:7], 16)
    ids = [None] + [hashlib.md5(f"{seed}/{k}".encode()).hexdigest() for k in range(1, n + 1)]
    face["id"] = put(out, grey_png(px, 8, lambda y: ((y + shift) * (n + 1) // px) % (n + 1)), "png")
    face["ids"] = put(out, json.dumps({"schema": "truebex-ids/1", "ids": ids}, separators=(",", ":")).encode(), "json")
    face["depth"] = put(out, grey_png(px, 16, lambda y: 0 if y < px // 8 else 800 + start + 8 * y), "png")


def headset_files(out: Path, job: dict, base: dict | None, views: list[dict], at_seq: int) -> str | None:
    """render-jobs 1.4 on the views (FAKE_TRUEBEX_FACE_FILES): the faces' files and
    numbers; the tour's hash (a panorama writes it, an update carries the base's)."""
    before = {v["view"]: v for v in (base or {}).get("views") or []}
    for view in views:
        for name, face in view["faces"].items():
            was = (before.get(view["view"]) or {}).get("faces", {}).get(name) or {}
            if face["rendered"]:
                face_files(out, view["view"], name, face, view["levels"][0])
                face["version"] = was.get("version", 1) + 1 if job["kind"] == "tiles" else 1
                face["op_seq"] = at_seq
            else:
                face.update({k: was[k] for k in FACE_KEYS if k in was})
    if job["kind"] != "panorama":
        return (base or {}).get("tour")
    nodes = [{"id": f"node-{i}", "title": v.get("title") or v["view"], "view": v["view"]} for i, v in enumerate(views)]
    links = [{"from": f"node-{i - 1}", "to": f"node-{i}", "auto": True} for i in range(1, len(views))]
    tour = {"format": "truebex-tour/1", "start": "node-0", "nodes": nodes, "links": links}
    return put(out, json.dumps(tour).encode(), "json")


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
    tour = headset_files(out, job, base, views, at_seq) if os.environ.get("FAKE_TRUEBEX_FACE_FILES") == "1" else None
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
    if tour:
        manifest["tour"] = tour
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
