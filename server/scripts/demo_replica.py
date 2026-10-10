"""A scripted replica of a cloud project, for testing PF4 before the app's
cloud save (CL1) lands. It speaks contract project-log v1.0 exactly as the
desktop app will, with a device token.

    cd server
    .venv\\Scripts\\python.exe scripts\\demo_replica.py login --email a@example.com --password … --trial
    .venv\\Scripts\\python.exe scripts\\demo_replica.py --token tbx_dev_… push --fixture tests\\contracts\\project-log
    .venv\\Scripts\\python.exe scripts\\demo_replica.py --token tbx_dev_… pull --project <id>
    .venv\\Scripts\\python.exe scripts\\demo_replica.py --token tbx_dev_… move --project <id> --base 12
    .venv\\Scripts\\python.exe scripts\\demo_replica.py --token tbx_dev_… presence --project <id> --seconds 60

`login` signs in with e-mail and password, activates this "computer" as a
device (licence 5.4) and, with --trial, starts the Pro trial so the device
holds `cloud.sync`; it prints the device token. `push` creates the project,
uploads the fixture snapshot (share-bundle §5, purpose snapshot), pushes the
12 operations of ops-remote.json as this account (their `author` becomes the
account's author_id) and registers a snapshot at the new head. `move` pushes
one "Move wall" operation made at --base, touching the fixture's first wall,
from a fresh replica: two people doing it at the same base show the conflict
rule. API: --api (default http://127.0.0.1:8000).
"""

import argparse
import hashlib
import json
import secrets
import sys
import time
from pathlib import Path

import requests

LOG = {"X-Truebex-Contract": "project-log/1.0"}
LICENCE = {"X-Truebex-Contract": "licence-api/1.0"}
UPLOADS = {"X-Truebex-Contract": "share-bundle/1.0"}
DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "project-log"


class Api:
    def __init__(self, base: str, token: str | None) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def call(self, method: str, path: str, *, headers: dict | None = None, ok=(200, 201, 204), **kw):
        h = dict(headers or {})
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        res = requests.request(method, f"{self.base}{path}", headers=h, timeout=60, **kw)
        if res.status_code not in ok:
            try:
                body = res.json()
                why = f"{body.get('code', res.status_code)}: {body.get('detail')}"
            except ValueError:
                why = res.text[:300]
            raise SystemExit(f"{method} {path} -> {res.status_code} {why}")
        return res.json() if res.content else None


def _need_token(api: Api) -> None:
    if not api.token:
        raise SystemExit("this command needs --token tbx_dev_... (get one with the login command)")


def cmd_login(api: Api, args) -> None:
    session = api.call("POST", "/auth/login", json={"email": args.email, "password": args.password})["access_token"]
    api.token = session
    fingerprint = hashlib.sha256(f"truebex-fp/1\ndemo-replica\n{args.email}".encode()).hexdigest()
    device = api.call(
        "POST",
        "/licence/activate",
        headers=LICENCE,
        json={"fingerprint": fingerprint, "device_name": args.device_name, "os": "windows 10.0.26200", "app_version": "1.0.0"},
    )
    api.token = device["device_token"]
    if args.trial:
        res = requests.post(
            f"{api.base}/licence/trial", json={"plan": "pro"}, timeout=30,
            headers={**LICENCE, "Authorization": f"Bearer {api.token}"},
        )
        if res.status_code == 201:
            print(f"Pro trial started (ends {res.json()['trial_ends_at']})")
        else:
            print(f"trial not started: {res.json().get('code')} {res.json().get('detail')}")
    account = api.call("GET", "/licence/account", headers=LICENCE)
    print(f"device {args.device_name} for {account['user']['email']}: plan {account['plan']}, author_id {account['author_id']}")
    print(f"device token: {api.token}")


def upload_file(api: Api, data: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(data).hexdigest()
    opened = api.call(
        "POST", "/uploads", headers=UPLOADS,
        json={"purpose": "snapshot", "files": [{"sha256": sha, "bytes": len(data), "content_type": "application/octet-stream"}]},
    )
    state = opened["files"][0]
    part = opened["part_bytes"]
    if state["state"] != "present":
        for n in range(state["parts"]):
            if n in state["received"]:
                continue
            chunk = data[n * part : (n + 1) * part]
            api.call(
                "PUT", f"/uploads/{opened['upload_id']}/files/{sha}/parts/{n}", data=chunk,
                headers={**UPLOADS, "Content-Type": "application/octet-stream", "X-Part-Sha256": hashlib.sha256(chunk).hexdigest()},
            )
    return opened["upload_id"], sha


def register_snapshot(api: Api, pid: str, at_seq: int, data: bytes) -> dict:
    upload_id, sha = upload_file(api, data)
    return api.call(
        "POST", f"/projects/{pid}/snapshots", headers={**LOG, "Idempotency-Key": secrets.token_hex(16)},
        json={"at_seq": at_seq, "doc_version": 38, "upload_id": upload_id, "files": {"tbxp": sha, "tbxpack": None}},
    )


def cmd_push(api: Api, args) -> None:
    _need_token(api)
    fixture = Path(args.fixture)
    remote = json.loads((fixture / "ops-remote.json").read_text(encoding="utf-8"))
    tbxp = (fixture / "snapshot-0000.tbxp").read_bytes()
    author = api.call("GET", "/licence/account", headers=LICENCE)["author_id"]
    if args.project:
        pid = args.project
        project = api.call("GET", f"/projects/{pid}", headers=LOG)
    else:
        project = api.call(
            "POST", "/projects", headers={**LOG, "Idempotency-Key": secrets.token_hex(16)},
            json={"name": args.name, "doc_version": 38},
        )
        pid = project["project_id"]
        register_snapshot(api, pid, 0, tbxp)
        print(f"created {args.name} ({pid}) with the fixture snapshot at 0")
    replica = secrets.token_hex(16)
    ops = []
    for op in remote["ops"]:
        ops.append(dict(op, author=author, replica_id=replica, op_id=secrets.token_hex(16), base_seq=project["head_seq"]))
    answer = api.call("POST", f"/projects/{pid}/ops", headers=LOG, json={"replica_id": replica, "ops": ops})
    counts: dict[str, int] = {}
    for r in answer["results"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("pushed: " + ", ".join(f"{n} {s}" for s, n in counts.items()))
    register_snapshot(api, pid, answer["head_seq"], tbxp)
    print(f"snapshot registered at {answer['head_seq']}")
    print(f"project {project['name']}, head {answer['head_seq']}")
    print(f"project id: {pid}")


def cmd_pull(api: Api, args) -> None:
    _need_token(api)
    after, total = args.after, 0
    while True:
        page = api.call("GET", f"/projects/{args.project}/ops", headers=LOG, params={"after": after, "limit": 1000, "wait_s": args.wait})
        for op in page["ops"]:
            total += 1
            what = op["restore"] and f"restore of version {op['restore']['version_id'][:8]}" or op["kind"]
            print(f"{op['server_seq']:>5}  {op['name'] or '(no name)':<22} {what:<10} author {op['author'][:8]}...  touched {len(op['touched'])}")
            after = op["server_seq"]
        if not page["more"]:
            break
    print(f"{total} operations, head {page['head_seq']}")


def cmd_move(api: Api, args) -> None:
    _need_token(api)
    remote = json.loads((Path(args.fixture) / "ops-remote.json").read_text(encoding="utf-8"))
    entity = (args.entity or remote["ops"][0]["touched"][0]).lower()
    author = api.call("GET", "/licence/account", headers=LICENCE)["author_id"]
    replica = secrets.token_hex(16)
    op = {
        "op_id": secrets.token_hex(16),
        "author": author,
        "author_kind": "person",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "touched": [entity],
        "kind": "delta",
        "name": "Move wall",
        "base_seq": args.base,
        "delta_format": "o5/38",
        "delta": "VEJYRHsic3RhbmRfaW4iOnRydWV9",  # stand-in bytes: TBXD{"stand_in":true}
    }
    answer = api.call("POST", f"/projects/{args.project}/ops", headers=LOG, json={"replica_id": replica, "ops": [op]})
    result = answer["results"][0]
    if result["status"] == "accepted":
        print(f"accepted as {result['server_seq']} (head {answer['head_seq']})")
    elif result["status"] == "rejected":
        print(f"rejected ({result['reason']}): replaced by")
        for w in result["winning"]:
            mine = " (yours)" if w["author"] == author else ""
            print(f"  {w['server_seq']}  {w['name']}  by author {w['author'][:8]}...{mine}")
        print(f"head {answer['head_seq']}: pull, re-make the move at the new head, push again")
    else:
        print(json.dumps(result))


def cmd_presence(api: Api, args) -> None:
    _need_token(api)
    replica = secrets.token_hex(16)
    body = {"replica_id": replica, "client": "desktop", "selection": [], "editing": []}
    end = time.monotonic() + args.seconds
    try:
        while time.monotonic() < end:
            others = api.call("PUT", f"/projects/{args.project}/presence", headers=LOG, json=body)["others"]
            names = ", ".join(f"{o['name']} ({o['client']})" for o in others) or "nobody else"
            print(f"{time.strftime('%H:%M:%S')} here; also here: {names}")
            time.sleep(min(10, max(0.0, end - time.monotonic())))
    finally:
        api.call("PUT", f"/projects/{args.project}/presence", headers=LOG, json={**body, "leaving": True})
        print("left the project")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="demo_replica.py", description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--token", help="a device token, tbx_dev_...")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("login", help="sign in, activate a device, print its token")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--device-name", default="DEMO-REPLICA")
    p.add_argument("--trial", action="store_true", help="start the 14-day Pro trial (cloud.sync)")
    p = sub.add_parser("push", help="create a project from the fixture and push its operations")
    p.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    p.add_argument("--name", default="House")
    p.add_argument("--project", help="push into this project instead of creating one")
    p = sub.add_parser("pull", help="pull the log")
    p.add_argument("--project", required=True)
    p.add_argument("--after", type=int, default=0)
    p.add_argument("--wait", type=int, default=0, help="long-poll seconds (0-25)")
    p = sub.add_parser("move", help="push one Move wall operation made at --base")
    p.add_argument("--project", required=True)
    p.add_argument("--base", type=int, required=True)
    p.add_argument("--entity", help="32-hex entity id (default: the fixture's first wall)")
    p.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    p = sub.add_parser("presence", help="stay present (heartbeats every 10 s), then leave")
    p.add_argument("--project", required=True)
    p.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args(argv)
    api = Api(args.api, args.token)
    {"login": cmd_login, "push": cmd_push, "pull": cmd_pull, "move": cmd_move, "presence": cmd_presence}[args.command](api, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
