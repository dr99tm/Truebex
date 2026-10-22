"""Submit and follow analysis jobs as the desktop app will (PF11, contract
render-jobs 1.1), for testing before the app's Analyse commands (AN2-AN4) land.

    cd server
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… catalogue
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… wind [--stl house.stl] [--speed 5 --direction 225]
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… energy --model house.epJSON --weather <id>
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… watch --job <id>
    .venv\\Scripts\\python.exe scripts\\demo_analysis.py --token tbx_dev_… output --job <id>

`wind` uploads the geometry as a `job-input` (share-bundle §5; without --stl a
10 m wide, 7 m high test shape of 8 triangles) and submits one direction;
the answer prints the estimate in cost units. `watch` long-polls the job,
`output` prints the `truebex-analysis/1` result's summary, fields and grids.
Get a device token with `demo_replica.py login … --trial`.
"""

import argparse
import hashlib
import json
import secrets
import struct
import sys
from pathlib import Path

import requests

JOBS = {"X-Truebex-Contract": "render-jobs/1.1"}
UPLOADS = {"X-Truebex-Contract": "share-bundle/1.0"}


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
    job = call(args, "POST", "/jobs", headers={**JOBS, "Idempotency-Key": secrets.token_hex(16)}, json=body)
    print(f"{job['kind']} job {job['state']} on {job['class']}: estimate {job['cost_units_estimate']} cu")
    print(f"job id: {job['job_id']}")


def cmd_wind(args) -> None:
    data = Path(args.stl).read_bytes() if args.stl else test_shape()
    files = {"geometry": upload_input(args, data)}
    if args.entities:
        files["entities"] = upload_input(args, Path(args.entities).read_bytes())
    submit(args, {
        "kind": "wind", "inputs": {"upload_id": None, "files": files},
        "params": {"speed_ms": args.speed, "direction_deg": args.direction, "reference_height_m": 10, "terrain": args.terrain, "comfort": "lawson"},
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
            print(f"rev {rev}: {job['state']} {round(job['progress'] * 100)}%, {cost} cu{extra}")
            if job["state"] in ("succeeded", "failed", "cancelled", "expired"):
                return


def cmd_output(args) -> None:
    out = call(args, "GET", f"/jobs/{args.job}/output", headers=JOBS)
    print(f"{out['schema']} {out['kind']} by {out['engine']['name']} {out['engine']['version']}")
    print("summary:", json.dumps(out.get("summary")))
    for f in out.get("fields") or []:
        print(f"field {f['name']} [{f['unit']}] on {f['on']}: {f['count']} values")
    for g in out.get("grids") or []:
        print(f"grid {g['name']} [{g['unit']}]: {g['nx']} x {g['ny']} cells of {g['cell_mm']} mm from {g['origin_mm']}")
    print(f"{len(out.get('urls') or {})} files, signed until {out.get('urls_expire_at')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True, help="a device token (tbx_dev_…) or a session token")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalogue")
    w = sub.add_parser("wind")
    w.add_argument("--stl")
    w.add_argument("--entities")
    w.add_argument("--speed", type=float, default=5)
    w.add_argument("--direction", type=float, default=225)
    w.add_argument("--terrain", default="suburban")
    e = sub.add_parser("energy")
    e.add_argument("--model", required=True)
    e.add_argument("--weather", required=True)
    for name in ("watch", "output"):
        sub.add_parser(name).add_argument("--job", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "catalogue":
        print(json.dumps(call(args, "GET", "/analysis/catalogue", headers=JOBS), indent=2))
    else:
        {"wind": cmd_wind, "energy": cmd_energy, "watch": cmd_watch, "output": cmd_output}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
