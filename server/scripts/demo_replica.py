"""A scripted replica of a cloud project, for testing PF4 without the app.
It speaks contract project-log v1.1 as the desktop app's cloud save (CL1)
does, with a device token, and pushes the app's own fixture operations.

    cd server
    .venv\\Scripts\\python.exe scripts\\demo_replica.py login --email a@example.com --password … --trial
    .venv\\Scripts\\python.exe scripts\\demo_replica.py --token tbx_dev_… push --fixture tests\\contracts\\project-log
    .venv\\Scripts\\python.exe scripts\\demo_replica.py --token tbx_dev_… pull --project <id>
    .venv\\Scripts\\python.exe scripts\\demo_replica.py --token tbx_dev_… move --project <id> --base 12
    .venv\\Scripts\\python.exe scripts\\demo_replica.py --token tbx_dev_… presence --project <id> --seconds 60

`login` signs in with e-mail and password, activates this "computer" as a
device (licence 5.4) and, with --trial, starts the Pro trial so the device
holds `cloud.sync`; it prints the device token. `push` creates the project
named in project.json (CL1's "House (fixture)"), uploads the fixture snapshot
(share-bundle §5, purpose snapshot), pushes the 12 operations of
ops-remote.json as this account (their `author` becomes the account's
author_id; each keeps its real delta and its own replica_id, unless
--fresh-replica). The only snapshot is the fixture's at 0: the deltas are
real now, so a copy at the head would claim a state they are not in (a
replica opening the project loads snapshot 0 and applies 1-12). `pull` lists the
log with each delta's format and size. `move` pushes the app's own web edit
(action-move.json: `move` of the fixture's wall by 600 mm, refs as
`<kind>#<id>`) made at --base (default the head) from a fresh replica: two
people doing it at the same base show the conflict rule, and a CL1 app
following the project applies it. API: --api (default http://127.0.0.1:8000).
"""

import argparse
import base64
import hashlib
import json
import secrets
import sys
import time
from pathlib import Path

import requests

LOG = {"X-Truebex-Contract": "project-log/1.1"}
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


def register_snapshot(api: Api, pid: str, at_seq: int, data: bytes, doc_version: int) -> dict:
    upload_id, sha = upload_file(api, data)
    return api.call(
        "POST", f"/projects/{pid}/snapshots", headers={**LOG, "Idempotency-Key": secrets.token_hex(16)},
        json={"at_seq": at_seq, "doc_version": doc_version, "upload_id": upload_id, "files": {"tbxp": sha, "tbxpack": None}},
    )


def _runs(ops: list[dict]) -> list[tuple[str, list[dict]]]:
    """A push names one replica: consecutive operations of the same replica_id go together."""
    runs: list[tuple[str, list[dict]]] = []
    for op in ops:
        if runs and runs[-1][0] == op["replica_id"]:
            runs[-1][1].append(op)
        else:
            runs.append((op["replica_id"], [op]))
    return runs


def cmd_push(api: Api, args) -> None:
    _need_token(api)
    fixture = Path(args.fixture)
    # CL1's truebex-project-log-ops/1: each operation names its own replica (no push-level replica_id).
    remote = json.loads((fixture / "ops-remote.json").read_text(encoding="utf-8"))
    tbxp = (fixture / "snapshot-0000.tbxp").read_bytes()
    record = json.loads((fixture / "project.json").read_text(encoding="utf-8"))
    doc_version = record.get("doc_version", 55)
    author = api.call("GET", "/licence/account", headers=LICENCE)["author_id"]
    if args.project:
        pid = args.project
        project = api.call("GET", f"/projects/{pid}", headers=LOG)
    else:
        name = args.name or record.get("name") or "House"
        project = api.call(
            "POST", "/projects", headers={**LOG, "Idempotency-Key": secrets.token_hex(16)},
            json={"name": name, "doc_version": doc_version},
        )
        pid = project["project_id"]
        register_snapshot(api, pid, 0, tbxp, doc_version)
        print(f"created {name} ({pid}) with the fixture snapshot at 0")
    fresh = secrets.token_hex(16)
    ops = []
    for op in remote["ops"]:
        replica = fresh if args.fresh_replica else op.get("replica_id") or fresh
        ops.append(dict(op, author=author, replica_id=replica, op_id=secrets.token_hex(16), base_seq=project["head_seq"]))
    counts: dict[str, int] = {}
    head = project["head_seq"]
    for replica, run in _runs(ops):
        answer = api.call("POST", f"/projects/{pid}/ops", headers=LOG, json={"replica_id": replica, "ops": run})
        head = answer["head_seq"]
        for r in answer["results"]:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("pushed: " + ", ".join(f"{n} {s}" for s, n in counts.items()))
    replicas = sorted({op["replica_id"] for op in ops})
    formats = sorted({op.get("delta_format") or op["kind"] for op in ops})
    print(f"replica {', '.join(r[:8] + '...' for r in replicas)}; deltas {', '.join(formats)}")
    print(f"project {project['name']}, head {head}")
    print(f"project id: {pid}")


def cmd_pull(api: Api, args) -> None:
    _need_token(api)
    after, total = args.after, 0
    while True:
        page = api.call("GET", f"/projects/{args.project}/ops", headers=LOG, params={"after": after, "limit": 1000, "wait_s": args.wait})
        for op in page["ops"]:
            total += 1
            what = op["restore"] and f"restore of version {op['restore']['version_id'][:8]}" or op["kind"]
            if op["kind"] == "delta" and op["delta"]:
                what = f"delta {op['delta_format']}, {len(base64.b64decode(op['delta']))} bytes"
            elif op["kind"] == "action" and op["action"]:
                what = f"action {op['action']['tool']} {' '.join(str(r)[:13] for r in op['action']['args'].get('refs', []))}"
            print(f"{op['server_seq']:>5}  {op['name'] or '(no name)':<16} {what:<28} author {op['author'][:8]}...  touched {len(op['touched'])}")
            after = op["server_seq"]
        if not page["more"]:
            break
    print(f"{total} operations, head {page['head_seq']}")


def cmd_move(api: Api, args) -> None:
    _need_token(api)
    # The app's own web edit (action-move.json): a log-safe `move`, refs `<kind>#<id>`
    # (agent-interface §6.2), which every kernel replica applies through its tool.
    sample = json.loads((Path(args.fixture) / "action-move.json").read_text(encoding="utf-8"))
    entity = (args.entity or sample["touched"][0]).lower()
    author = api.call("GET", "/licence/account", headers=LICENCE)["author_id"]
    if args.base is None:  # made at the head: accepted unless someone pushes first
        args.base = api.call("GET", f"/projects/{args.project}", headers=LOG)["head_seq"]
    replica = secrets.token_hex(16)
    action = sample["action"]
    op = {
        "op_id": secrets.token_hex(16),
        "author": author,
        "author_kind": "person",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "touched": [entity],
        "kind": "action",
        "name": sample.get("name") or "Move wall",
        "base_seq": args.base,
        "action": {**action, "args": {**action["args"], "refs": [f"{args.kind}#{entity}"]}},
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
    p.add_argument("--name", help="the new project's name (default: project.json's)")
    p.add_argument("--project", help="push into this project instead of creating one")
    p.add_argument("--fresh-replica", action="store_true", help="push as one new replica, not the operations' own")
    p = sub.add_parser("pull", help="pull the log")
    p.add_argument("--project", required=True)
    p.add_argument("--after", type=int, default=0)
    p.add_argument("--wait", type=int, default=0, help="long-poll seconds (0-25)")
    p = sub.add_parser("move", help="push the app's Move wall action made at --base")
    p.add_argument("--project", required=True)
    p.add_argument("--base", type=int, help="the sequence it was made at (default: the head)")
    p.add_argument("--entity", help="32-hex entity id (default: action-move.json's wall)")
    p.add_argument("--kind", default="wall", help="the entity's kind in its ref (agent-interface §6.2; default wall)")
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
