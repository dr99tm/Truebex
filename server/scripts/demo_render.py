"""Submit and follow cloud render jobs as the desktop app will (PF6, contract
render-jobs v1.0), for testing before the app's Cloud panorama command lands.

    cd server
    .venv\\Scripts\\python.exe scripts\\demo_render.py --token tbx_dev_… submit --project <id> --follow
    .venv\\Scripts\\python.exe scripts\\demo_render.py --token tbx_dev_… watch --job <id>
    .venv\\Scripts\\python.exe scripts\\demo_render.py --token tbx_dev_… usage

`submit` reads the project's head and submits a panorama set of one saved view
(the render-jobs fixtures' "Living room" unless --view) at that sequence
number, with an Idempotency-Key; --follow keeps it current from the log.
`watch` long-polls the job's `rev` (5.2) and prints every change. `usage`
prints this month's cost units (5.6). Get a device token with
`demo_replica.py login … --trial`. API: --api (default http://127.0.0.1:8000).
"""

import argparse
import json
import secrets
import sys

import requests

JOBS = {"X-Truebex-Contract": "render-jobs/1.0"}
LOG = {"X-Truebex-Contract": "project-log/1.0"}
VIEW = "0199c6a2e00070058000000000000001"


def call(args, method: str, path: str, *, headers: dict, ok=(200, 201), **kw):
    h = {**headers, "Authorization": f"Bearer {args.token}"}
    res = requests.request(method, f"{args.api.rstrip('/')}{path}", headers=h, timeout=60, **kw)
    if res.status_code not in ok:
        try:
            body = res.json()
            why = f"{body.get('code', res.status_code)}: {body.get('detail')}"
        except ValueError:
            why = res.text[:300]
        raise SystemExit(f"{method} {path} -> {res.status_code} {why}")
    return res.json() if res.content else None


def cmd_submit(args) -> None:
    head = call(args, "GET", f"/projects/{args.project}", headers=LOG)["head_seq"]
    body = {"kind": args.kind, "project_id": args.project, "at_seq": head, "views": [args.view], "follow": args.follow}
    if args.kind == "pack":
        body = {"kind": "pack", "project_id": args.project, "at_seq": head, "params": {"items": ["renders", "boq"]}}
    job = call(args, "POST", "/jobs", headers={**JOBS, "Idempotency-Key": secrets.token_hex(16)}, json=body)
    print(f"{job['kind']} job {job['state']} at operation {job['at_seq']}: estimate {job['cost_units_estimate']} cu")
    print(f"job id: {job['job_id']}")


def cmd_watch(args) -> None:
    rev = -1
    while True:
        job = call(args, "GET", f"/jobs/{args.job}", headers=JOBS, params={"rev": rev, "wait_s": 25})
        if job["rev"] > rev:
            rev = job["rev"]
            cost = job["cost_units"] if job["cost_units"] is not None else f"~{job['cost_units_estimate']}"
            extra = f" {job['message']}" if job["message"] else ""
            print(f"rev {rev}: {job['state']} {round(job['progress'] * 100)}% at operation {job['at_seq']}, {cost} cu{extra}")
            if job["state"] in ("failed", "cancelled", "expired") or (job["state"] == "succeeded" and not job["follow"]):
                return


def cmd_usage(args) -> None:
    print(json.dumps(call(args, "GET", "/jobs/usage", headers=JOBS), indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="demo_render.py", description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True, help="a device token, tbx_dev_...")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("submit", help="submit a panorama set at the project's head")
    p.add_argument("--project", required=True)
    p.add_argument("--follow", action="store_true", help="keep it current from the log")
    p.add_argument("--kind", default="panorama", choices=["panorama", "pack"])
    p.add_argument("--view", default=VIEW)
    p = sub.add_parser("watch", help="print every change of a job (long-poll)")
    p.add_argument("--job", required=True)
    sub.add_parser("usage", help="this month's cost units")
    args = parser.parse_args(argv)
    {"submit": cmd_submit, "watch": cmd_watch, "usage": cmd_usage}[args.command](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
