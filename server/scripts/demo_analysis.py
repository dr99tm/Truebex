"""Submit and follow analysis jobs as the desktop app does (PF11, PF11c; contract
render-jobs 1.2; the header 1.3 since PF6c, 1.4 since PF6d), for testing beside the app's wind study (AN3).

    cd server
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… catalogue
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… wind [--stl house.stl --entities house.bin] [--speed 5 --direction 225] [--quality draft]
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… airflow --wind-job <id> [--rooms rooms.json] [--speed 5 --direction 225]
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… energy --model house.epJSON --weather <id>
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… watch --job <id>
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… output --job <id> [--json]

`wind` uploads the geometry and its entity ids as `job-input` files
(share-bundle §5; without --stl a 10 m wide, 7 m high closed test shape of
8 triangles and 8 ids) and submits one direction with render-jobs 1.2's
params; the answer prints the estimate in cost units. The app's own export
is in tests/contracts/render-jobs/ (`--stl …/wind-geometry.bin --entities
…/wind-entities.bin`, the app's CL0 project id with `--project-id
f08ffe0283418dea8627d42c7908ab88`). `airflow` uploads a rooms file
(`truebex-airflow-rooms/1`; without --rooms two rooms on the app export's
facades, no cp, so the wind job's Cp applies) and submits the indoor run
on the wind job of the same direction: give it the same --speed,
--direction, --reference-height and --terrain. It waits for that wind job.
`watch` long-polls a job, `output` prints the `truebex-analysis/1` result's
summary, fields, grids and its `files` map (5.5). Get a device token with
`demo_replica.py login … --trial`.
"""

import argparse
import hashlib
import json
import secrets
import struct
import sys
from pathlib import Path

import requests

JOBS = {"X-Truebex-Contract": "render-jobs/1.4"}
UPLOADS = {"X-Truebex-Contract": "share-bundle/1.0"}
# Two rooms of the app's export of Z0-baseline.tbxp (tests/contracts/render-jobs/wind-geometry.bin:
# x -0.15..26.15 m, y -0.15..9.15 m): a south window, a door between them, a north window.
LIVING = "0199c6a2e00070028000000000000011"
HALL = "0199c6a2e00070028000000000000012"
DEMO_ROOMS = {
    "schema": "truebex-airflow-rooms/1",
    "rooms": [
        {"id": LIVING, "name": "Living", "volume_m3": 48.6, "floor_z_m": 0.0},
        {"id": HALL, "name": "Hall", "volume_m3": 20.0, "floor_z_m": 0.0},
    ],
    "openings": [
        {"id": "0199c6a2e000700a8000000000000021", "from": LIVING, "to": "outside", "area_m2": 1.6, "cd": 0.6, "z_m": 1.05,
         "centre_m": [5.0, -0.15, 1.05], "normal": [0.0, -1.0, 0.0]},
        {"id": "0199c6a2e000700a8000000000000022", "from": LIVING, "to": HALL, "area_m2": 1.8, "cd": 0.6, "z_m": 1.05,
         "centre_m": [8.0, 4.5, 1.05], "normal": [1.0, 0.0, 0.0]},
        {"id": "0199c6a2e000700a8000000000000023", "from": "outside", "to": HALL, "area_m2": 1.2, "cd": 0.6, "z_m": 1.05,
         "centre_m": [12.0, 9.15, 1.05], "normal": [0.0, -1.0, 0.0]},
    ],
    "rho_kg_m3": 1.2,
}


def call(args, method: str, path: str, *, headers: dict, ok=(200, 201, 204), **kw):
    h = {**headers, "Authorization": f"Bearer {args.token}"}
    url = path if path.startswith("http") else f"{args.api.rstrip('/')}{path}"
    res = requests.request(method, url, headers=h, timeout=120, **kw)
    if res.status_code not in ok:
        try:
            body = res.json()
            why = f"{body.get('code', res.status_code)}: {body.get('detail')}"
        except ValueError:
            why = res.text[:300]
        raise SystemExit(f"{method} {path} -> {res.status_code} {why}")
    return res.json() if res.content and res.headers.get("content-type", "").startswith("application/json") else None


def test_shape() -> bytes:
    w, h = 5.0, 7.0
    ring = [(w, 0, h / 2), (0, w, h / 2), (-w, 0, h / 2), (0, -w, h / 2)]
    tris = []
    for i in range(4):
        a, b = ring[i], ring[(i + 1) % 4]
        tris += [(a, b, (0, 0, h)), (b, a, (0, 0, 0))]
    out = bytearray(b"truebex demo shape".ljust(80, b" ")) + struct.pack("<I", len(tris))
    for t in tris:
        out += struct.pack("<3f", 0, 0, 0) + b"".join(struct.pack("<3f", *v) for v in t) + struct.pack("<H", 0)
    return bytes(out)


def entity_ids(stl: bytes) -> bytes:
    """16 bytes per triangle (Hi then Lo, big-endian): one demo id each, derived from the file."""
    (n,) = struct.unpack_from("<I", stl, 80)
    seed = hashlib.sha256(stl).digest()[:8]
    return b"".join(seed + struct.pack(">Q", i + 1) for i in range(n))


def upload_input(args, data: bytes, content_type: str = "application/octet-stream") -> str:
    digest = hashlib.sha256(data).hexdigest()
    opened = call(args, "POST", "/uploads", headers=UPLOADS, json={
        "purpose": "job-input", "files": [{"sha256": digest, "bytes": len(data), "content_type": content_type}],
    })
    state = opened["files"][0]
    part = opened["part_bytes"]
    if state["state"] != "present":
        for n in range(state["parts"]):
            chunk = data[n * part : (n + 1) * part]
            call(args, "PUT", f"/uploads/{opened['upload_id']}/files/{digest}/parts/{n}", data=chunk,
                 headers={**UPLOADS, "Content-Type": "application/octet-stream", "X-Part-Sha256": hashlib.sha256(chunk).hexdigest()})
    return digest


def submit(args, body: dict) -> None:
    if args.project_id:
        body.update(project_id=args.project_id, at_seq=args.at_seq)
    body["quality"] = args.quality
    job = call(args, "POST", "/jobs", headers={**JOBS, "Idempotency-Key": secrets.token_hex(16)}, json=body)
    print(f"{job['kind']} job {job['state']} on {job['class']}, {job['quality']}: estimate {job['cost_units_estimate']} cu")
    if job.get("message"):
        print(job["message"])
    print(f"job id: {job['job_id']}")


def site(args) -> dict:
    return {"speed_ms": args.speed, "direction_deg": args.direction, "reference_height_m": args.reference_height, "terrain": args.terrain}


def cmd_wind(args) -> None:
    data = Path(args.stl).read_bytes() if args.stl else test_shape()
    ids = Path(args.entities).read_bytes() if args.entities else entity_ids(data)
    files = {"geometry": upload_input(args, data, "model/stl"), "entities": upload_input(args, ids)}
    submit(args, {
        "kind": "wind", "inputs": {"upload_id": None, "files": files},
        "params": {**site(args), "comfort": "lawson", "pedestrian_height_m": args.pedestrian_height,
                   "grid_cell_mm": args.grid_cell, "turbulence_model": args.turbulence},
    })


def cmd_airflow(args) -> None:
    rooms = Path(args.rooms).read_bytes() if args.rooms else json.dumps(DEMO_ROOMS, indent=2).encode("utf-8")
    files = {"rooms": upload_input(args, rooms, "application/json")}
    submit(args, {
        "kind": "airflow", "inputs": {"upload_id": None, "files": files},
        "params": {"wind_job_id": args.wind_job, **site(args), "velocity_height_m": args.velocity_height},
    })


def cmd_energy(args) -> None:
    files = {"model": upload_input(args, Path(args.model).read_bytes(), "application/json")}
    submit(args, {"kind": "energy", "inputs": {"upload_id": None, "files": files}, "params": {"weather": args.weather, "period": "annual"}})


def cmd_watch(args) -> None:
    rev = -1
    while True:
        job = call(args, "GET", f"/jobs/{args.job}", headers=JOBS, params={"rev": rev, "wait_s": 25})
        if job["rev"] > rev:
            rev = job["rev"]
            cost = job["cost_units"] if job["cost_units"] is not None else f"~{job['cost_units_estimate']}"
            extra = f" {job['message']}" if job["message"] else ""
            if job.get("error"):
                extra += f" {job['error']['code']}: {job['error']['message']}"
            print(f"rev {rev}: {job['state']} {round(job['progress'] * 100)}%, {cost} cu{extra}")
            if job["state"] in ("succeeded", "failed", "cancelled", "expired"):
                return


def cmd_output(args) -> None:
    out = call(args, "GET", f"/jobs/{args.job}/output", headers=JOBS)
    if args.json:
        print(json.dumps(out, indent=2))
        return
    print(f"{out['schema']} {out['kind']} by {out['engine']['name']} {out['engine']['version']} ({out['engine'].get('image')})")
    print(f"project {out.get('project_id')} at sequence {out.get('at_seq')}")
    print("summary:", json.dumps(out.get("summary")))
    for f in out.get("fields") or []:
        print(f"field {f['name']} [{f['unit']}] on {f['on']}: {f['count']} values")
    for g in out.get("grids") or []:
        print(f"grid {g['name']} [{g['unit']}] x{g.get('components', 1)}: {g['nx']} x {g['ny']} cells of {g['cell_mm']} mm, cell (0, 0) centred at {g['origin_mm']}")
    files = out.get("files") or {}
    print(f"files: {len(files)}, signed until {out.get('urls_expire_at')}")
    for sha, f in files.items():
        print(f"  {sha[:16]}…  {f['bytes']} bytes  {f['url'].split('?', 1)[0]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True, help="a device token (tbx_dev_…) or a session token")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalogue")

    def job_args(p):
        p.add_argument("--quality", default="standard", choices=("draft", "standard", "high"))
        p.add_argument("--project-id", help="the cloud project's id, or the document's own (32 hex)")
        p.add_argument("--at-seq", type=int, default=0)

    def site_args(p):
        p.add_argument("--speed", type=float, default=5)
        p.add_argument("--direction", type=float, default=225)
        p.add_argument("--reference-height", type=float, default=10)
        p.add_argument("--terrain", default="suburban", choices=("sea", "lake", "open", "suburban", "urban"))

    w = sub.add_parser("wind")
    w.add_argument("--stl")
    w.add_argument("--entities", help="16 bytes per triangle (default: demo ids)")
    site_args(w)
    w.add_argument("--pedestrian-height", type=float, default=1.5)
    w.add_argument("--grid-cell", type=float, default=1000, help="mm")
    w.add_argument("--turbulence", default="realizable_ke", choices=("realizable_ke", "komega_sst"))
    job_args(w)
    a = sub.add_parser("airflow")
    a.add_argument("--wind-job", required=True, help="the wind job of the same direction")
    a.add_argument("--rooms", help="a truebex-airflow-rooms/1 file (default: two demo rooms)")
    site_args(a)
    a.add_argument("--velocity-height", type=float, default=1.1)
    job_args(a)
    e = sub.add_parser("energy")
    e.add_argument("--model", required=True)
    e.add_argument("--weather", required=True)
    job_args(e)
    sub.add_parser("watch").add_argument("--job", required=True)
    o = sub.add_parser("output")
    o.add_argument("--job", required=True)
    o.add_argument("--json", action="store_true", help="print the whole 5.5 answer")
    args = parser.parse_args(argv)
    if args.cmd == "catalogue":
        print(json.dumps(call(args, "GET", "/analysis/catalogue", headers=JOBS), indent=2))
    else:
        {"wind": cmd_wind, "airflow": cmd_airflow, "energy": cmd_energy, "watch": cmd_watch, "output": cmd_output}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
