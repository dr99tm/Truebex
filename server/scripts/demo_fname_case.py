"""Send the enum values a packaged app build may spell in another case (PF14f).

    cd server
    .venv\\Scripts\\python.exe scripts\\demo_replica.py login --email a@example.com --password … --trial
    .venv\\Scripts\\python.exe scripts\\demo_fname_case.py --token tbx_dev_…

A Shipping (or Game) build of the app writes these values from Unreal FNames,
which keep the case the engine's name table registered first: "Panorama",
"High", "Delta", "Person", "Resolved", "Editor", "Beta". With a device token
(a Pro trial: cloud.sync, cloud.panoramas and collab.live) this creates a
project and sends each value as such a build may, then a word that is none
(still refused), and prints every answer: an operation pushed and pulled
(project-log 5.6, 5.7), a comment resolved and reopened (5.20, 5.21), a
panorama job submitted, read and listed with the app's filters (render-jobs
5.1-5.3), an invitation (5.14) and the release feed (licence-api 5.13). Each
line ends "ok" when the platform answered the contract's lower-case spelling
(or refused the word that is none); the last line counts them. The exit code
is 1 when one is not. API: --api (default http://127.0.0.1:8000).
"""

import argparse
import base64
import json
import secrets
import sys

import requests

LOG = {"X-Truebex-Contract": "project-log/1.2"}
JOBS = {"X-Truebex-Contract": "render-jobs/1.2"}
LICENCE = {"X-Truebex-Contract": "licence-api/1.0"}


class Api:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def call(self, method: str, path: str, *, headers: dict | None = None, **kw) -> tuple[int, dict]:
        h = {"Authorization": f"Bearer {self.token}", "Idempotency-Key": secrets.token_hex(16), **(headers or {})}
        res = requests.request(method, f"{self.base}{path}", headers=h, timeout=60, **kw)
        try:
            body = res.json() if res.content else {}
        except ValueError:
            body = {"detail": res.text[:300]}
        return res.status_code, body


class Checks:
    def __init__(self) -> None:
        self.ok = 0
        self.total = 0

    def line(self, label: str, status: int, shown: str, good: bool) -> None:
        self.total += 1
        self.ok += good
        print(f"{label}: {status} {shown} -- {'ok' if good else 'NOT AS EXPECTED'}")

    def refused(self, label: str, status: int, body: dict) -> None:
        self.line(label, status, f"{body.get('code')} ({body.get('detail')})", status == 422 and body.get("code") == "validation_failed")


def run(api: Api, invite: str) -> int:
    checks = Checks()
    status, account = api.call("GET", "/licence/account", headers=LICENCE)
    if status != 200:
        raise SystemExit(f"GET /licence/account -> {status} {account.get('detail')} (is the token a device token?)")
    author = account["author_id"]
    status, project = api.call("POST", "/projects", headers=LOG, json={"name": "PF14f spellings", "doc_version": 55})
    if status != 201:
        raise SystemExit(f"POST /projects -> {status} {project.get('code')}: {project.get('detail')} (start the Pro trial: demo_replica.py login --trial)")
    pid = project["project_id"]
    print(f"project {project['name']} ({pid}) for {account['user']['email']}, plan {account['plan']}")

    # project-log 5.6 / 5.7: an operation as CadProjectLog.cpp's OpToJson writes it.
    touched = secrets.token_hex(16)
    op = {
        "op_id": secrets.token_hex(16),
        "author": author,
        "author_kind": "Person",
        "at": "2026-10-25T09:00:00.000Z",
        "touched": [touched],
        "kind": "Delta",
        "name": "Move wall",
        "base_seq": 0,
        "delta_format": "o5/55",
        "delta": base64.b64encode(b"TBXD" + json.dumps({"rows": [touched]}).encode()).decode("ascii"),
    }
    replica = secrets.token_hex(16)
    status, pushed = api.call("POST", f"/projects/{pid}/ops", headers=LOG, json={"replica_id": replica, "ops": [op]})
    result = (pushed.get("results") or [{}])[0]
    checks.line('push kind "Delta", author_kind "Person"', status, f"{result.get('status')} as {result.get('server_seq')}", status == 200 and result.get("status") == "accepted")
    status, pulled = api.call("GET", f"/projects/{pid}/ops", headers=LOG, params={"after": 0})
    got = (pulled.get("ops") or [{}])[0]
    checks.line("pull", status, f"kind {got.get('kind')}, author_kind {got.get('author_kind')}", (got.get("kind"), got.get("author_kind")) == ("delta", "person"))
    status, body = api.call("POST", f"/projects/{pid}/ops", headers=LOG, json={"replica_id": replica, "ops": [{**op, "op_id": secrets.token_hex(16), "kind": "Restore", "base_seq": 1}]})
    checks.refused('push kind "Restore"', status, body)

    # project-log 5.20 / 5.21: SyncCollab.cpp's comment PATCH.
    status, comment = api.call("POST", f"/projects/{pid}/comments", headers=LOG, json={"text": "Check this wall", "anchor": {"entity": touched, "point_mm": None, "view": None}})
    if status != 201:
        raise SystemExit(f"POST /projects/{pid}/comments -> {status} {comment.get('code')}: {comment.get('detail')}")
    cid = comment["comment_id"]
    for sent, want in (("Resolved", "resolved"), ("Open", "open")):
        status, body = api.call("PATCH", f"/projects/{pid}/comments/{cid}", headers=LOG, json={"state": sent})
        checks.line(f'comment PATCH state "{sent}"', status, f"state {body.get('state')}, resolved_by {body.get('resolved_by')}", status == 200 and body.get("state") == want)
    status, body = api.call("PATCH", f"/projects/{pid}/comments/{cid}", headers=LOG, json={"state": "Closed"})
    checks.refused('comment PATCH state "Closed"', status, body)

    # render-jobs 5.1-5.3: RenderJobsClient.cpp's FRenderJobRequest::ToJson and List.
    job_body = {
        "kind": "Panorama", "project_id": pid, "at_seq": 1, "views": [secrets.token_hex(16) for _ in range(3)], "changed": [],
        "base_job_id": None, "quality": "High", "follow": False, "inputs": {"upload_id": None, "files": {}}, "params": {},
    }
    status, job = api.call("POST", "/jobs", headers=JOBS, json=job_body)
    checks.line('POST /jobs kind "Panorama", quality "High"', status, f"job {job.get('job_id')}, kind {job.get('kind')}, quality {job.get('quality')}, {job.get('state')}", status == 201 and (job.get("kind"), job.get("quality")) == ("panorama", "high"))
    if status == 201:
        status, again = api.call("GET", f"/jobs/{job['job_id']}", headers=JOBS)
        checks.line("GET /jobs/{job_id}", status, f"kind {again.get('kind')}, quality {again.get('quality')}", status == 200 and (again.get("kind"), again.get("quality")) == ("panorama", "high"))
    status, listed = api.call("GET", "/jobs", headers=JOBS, params={"project_id": pid, "kind": "Panorama", "state": "Queued"})
    jobs = listed.get("jobs") or []
    checks.line("GET /jobs?kind=Panorama&state=Queued", status, f"{len(jobs)} job(s): " + ", ".join(f"{j['kind']} {j['quality']} {j['state']}" for j in jobs), status == 200 and [j["job_id"] for j in jobs] == [job.get("job_id")])
    status, body = api.call("POST", "/jobs", headers=JOBS, json={**job_body, "kind": "Panoramas"})
    checks.refused('POST /jobs kind "Panoramas"', status, body)

    # project-log 5.14: SyncClient.cpp's Invite.
    status, member = api.call("POST", f"/projects/{pid}/members", headers=LOG, json={"email": invite, "role": "Editor"})
    checks.line('invite role "Editor"', status, f"{member.get('email')} {member.get('role')} {member.get('state')}", status == 201 and member.get("role") == "editor")
    status, body = api.call("POST", f"/projects/{pid}/members", headers=LOG, json={"email": "x" + invite, "role": "Owner"})
    checks.refused('invite role "Owner"', status, body)

    # licence-api 5.13: TruebexUpdater.cpp's feed check.
    status, feed = api.call("GET", "/releases/feed", headers=LICENCE, params={"channel": "Beta", "platform": "win64"})
    checks.line('GET /releases/feed?channel=Beta', status, f"channel {feed.get('channel')}, latest {feed.get('latest')}", status == 200 and feed.get("channel") == "beta")

    print(f"{checks.ok} of {checks.total} answers as expected")
    return 0 if checks.ok == checks.total else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="demo_fname_case.py", description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True, help="a device token, tbx_dev_... (demo_replica.py login --trial)")
    parser.add_argument("--invite", default="sam@example.com", help="who the project invites as an editor")
    args = parser.parse_args(argv)
    return run(Api(args.api, args.token), args.invite)


if __name__ == "__main__":
    sys.exit(main())
