"""Submit and follow cloud render jobs as the desktop app does (PF6, contract
render-jobs v1.3 since PF6c: CL4's follow sets), for testing without the app.

    cd server
    .venv\\Scripts\\python.exe scripts\\demo_render.py --token tbx_dev_… submit --project <id> --follow
    .venv\\Scripts\\python.exe scripts\\demo_render.py --token tbx_dev_… watch --job <id>
    .venv\\Scripts\\python.exe scripts\\demo_render.py --token tbx_dev_… jobs --kind tiles
    .venv\\Scripts\\python.exe scripts\\demo_render.py --token tbx_dev_… show --job <id>
    .venv\\Scripts\\python.exe scripts\\demo_render.py --token tbx_dev_… output --job <id>
    .venv\\Scripts\\python.exe scripts\\demo_render.py --token tbx_dev_… usage

`submit` reads the project's head and submits a panorama set of saved views
(the app's render-jobs fixtures' three, PR3's bedroom, entry and living, unless
--view is given, once per view) at that sequence number, with an
Idempotency-Key; --follow keeps it current from the log.
`watch` long-polls the job's `rev` (5.2) and prints every change. `jobs`
lists the account's jobs (5.3, newest first) with the keys CL4 reads. `show`
prints one record (5.2): its state, `follow`, `base_job_id` (a followed set's
tiles job names the set), `output_job_id` (a follow job: the job 5.5 serves
now) and a tiles job's `trigger` (the operations it was queued for). `output`
prints which job's manifest 5.5 serves and its faces. `usage` prints this
month's cost units (5.6). Get a device token with `demo_replica.py login …
--trial`. API: --api (default http://127.0.0.1:8000).
"""

import argparse
import json
import secrets
import sys

import requests

JOBS = {"X-Truebex-Contract": "render-jobs/1.3"}
LOG = {"X-Truebex-Contract": "project-log/1.0"}
# The saved views of the app's fixtures (CL3: PR3-pano-rooms.tbxp): bedroom, entry, living.
VIEWS = ["ecaf16d70fa5862cbba8f2288b9fd593", "8388104cbff98d2dba07fd23c19c83b5", "aee49319c0d48a7a953f247b52c948be"]


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
    body = {"kind": args.kind, "project_id": args.project, "at_seq": head, "views": args.view or VIEWS, "follow": args.follow}
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


def _line(job: dict) -> str:
    extra = []
    if job.get("follow"):
        extra.append("following")
    for key in ("base_job_id", "output_job_id"):
        if job.get(key):
            extra.append(f"{key} {job[key]}")
    trigger = job.get("trigger")
    if trigger:
        extra.append(f"trigger {len(trigger['op_ids'])} op(s) {trigger['first_seq']}-{trigger['last_seq']}")
    return f"{job['job_id']}  {job['kind']:<8} {job['state']:<9} rev {job['rev']:<3} at {job['at_seq']:<4} " + ", ".join(extra)


def cmd_jobs(args) -> None:
    params = {k: v for k, v in (("kind", args.kind), ("state", args.state), ("project_id", args.project)) if v}
    for job in call(args, "GET", "/jobs", headers=JOBS, params=params)["jobs"]:
        print(_line(job))


def cmd_show(args) -> None:
    job = call(args, "GET", f"/jobs/{args.job}", headers=JOBS)
    if args.json:
        print(json.dumps(job, indent=2))
        return
    print(f"{job['kind']} job {job['job_id']}: {job['state']}, rev {job['rev']}, at operation {job['at_seq']}")
    print(f"  follow: {str(job['follow']).lower()}")
    print(f"  base_job_id: {job.get('base_job_id')}")
    print(f"  output_job_id: {job.get('output_job_id')}")
    if job["kind"] == "tiles":
        trigger = job.get("trigger")
        print(f"  trigger: {json.dumps(trigger, indent=4) if trigger else None}")


def cmd_output(args) -> None:
    out = call(args, "GET", f"/jobs/{args.job}/output", headers=JOBS)
    faces = f"{out.get('faces_rendered')} faces rendered, {out.get('faces_reused')} carried"
    print(f"5.5 on {args.job}: the manifest of job {out['job_id']} at operation {out['at_seq']}, {faces}")
    print(f"  tiles_base: {out.get('tiles_base')}")


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
    p.add_argument("--view", action="append", help="a saved view id (repeat for more; default the fixtures' three)")
    p = sub.add_parser("watch", help="print every change of a job (long-poll)")
    p.add_argument("--job", required=True)
    p = sub.add_parser("jobs", help="list the account's jobs (5.3)")
    p.add_argument("--kind")
    p.add_argument("--state")
    p.add_argument("--project")
    p = sub.add_parser("show", help="one job's record (5.2): follow, base_job_id, output_job_id, trigger")
    p.add_argument("--job", required=True)
    p.add_argument("--json", action="store_true", help="print the whole record")
    p = sub.add_parser("output", help="which job's manifest 5.5 serves")
    p.add_argument("--job", required=True)
    sub.add_parser("usage", help="this month's cost units")
    args = parser.parse_args(argv)
    commands = {"submit": cmd_submit, "watch": cmd_watch, "jobs": cmd_jobs, "show": cmd_show, "output": cmd_output, "usage": cmd_usage}
    commands[args.command](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
