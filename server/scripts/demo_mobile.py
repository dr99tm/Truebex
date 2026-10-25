"""Set up a shared project for the mobile web client (PF9) the way the desktop
app will leave one, before the app's cloud save (CL1) lands.

    cd server
    .venv\\Scripts\\python.exe scripts\\demo_mobile.py setup --email alex@example.com --password … --editor-email sam@example.com
    .venv\\Scripts\\python.exe scripts\\demo_mobile.py --token tbx_dev_… move --project <id> --entity <id>
    .venv\\Scripts\\python.exe scripts\\demo_mobile.py --token tbx_live_… move --project <id> --entity Oslo

`setup` (run it again at any time; it reuses what exists):
1. signs the owner and the editor up (or in) with e-mail and password, and
   activates a device for each on the Pro trial (`cloud.sync`, cloud panoramas);
2. creates "House" as the owner, uploads the fixture snapshot with its project
   digest (tests/contracts/project-digest, the PF9 proposal for project-log
   §6.4), pushes the 12 fixture operations and registers snapshot + digest at
   the head;
3. makes the editor an active member and gives both accounts a display name
   (straight in the database, like seed_market.py: no invitation e-mail);
4. unless --no-render, submits a followed panorama set of the digest's saved
   views (a worker renders it: PF6's human test, steps 2-3);
5. prints the project id, the phone's address and the editor's device token.

`move` pushes one "Move <name>" operation from a device (the desktop's stand-in),
made at --base (default the head), touching --entity: with the phone offline,
its own edit of the same entity then loses (the visible resolution). With an
API key (`--token tbx_live_…`, scope projects:write) it pushes through `/v1`
as an agent instead (PF12), so the phone names no person ("Someone changed
this first"). --entity is a 32-hex id or the start of a name in the digest
("Oslo" for the sofa). Steps 1
and 3 use server/.env like the API (DATABASE_URL). API: --api (default
http://127.0.0.1:8000); the site for the printed address: --site.
"""

import argparse
import hashlib
import json
import secrets
import sys
import time
from pathlib import Path

import requests

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

from scripts.demo_replica import LICENCE, LOG, UPLOADS, Api  # noqa: E402

JOBS = {"X-Truebex-Contract": "render-jobs/1.3"}
FIXTURES = SERVER / "tests" / "contracts"
DIGEST = FIXTURES / "project-digest" / "digest-house.json"


# --- accounts and devices ------------------------------------------------------------------


def session_for(base: str, email: str, password: str) -> str:
    """Sign up, or sign in when the account exists; returns a session token."""
    res = requests.request("POST", f"{base}/auth/register", json={"email": email, "password": password}, timeout=30)
    if res.status_code == 409:
        res = requests.request("POST", f"{base}/auth/login", json={"email": email, "password": password}, timeout=30)
    if res.status_code not in (200, 201):
        raise SystemExit(f"{email}: {res.status_code} {res.text[:200]}")
    return res.json()["access_token"]


def device_for(base: str, session: str, email: str, name: str) -> str:
    """Activate a device for the account (licence 5.4) on the Pro trial."""
    api = Api(base, session)
    fingerprint = hashlib.sha256(f"truebex-fp/1\ndemo-mobile\n{email}".encode()).hexdigest()
    device = api.call(
        "POST", "/licence/activate", headers=LICENCE,
        json={"fingerprint": fingerprint, "device_name": name, "os": "windows 10.0.26200", "app_version": "1.0.0"},
    )
    token = device["device_token"]
    res = requests.post(
        f"{base}/licence/trial", json={"plan": "pro"}, timeout=30, headers={**LICENCE, "Authorization": f"Bearer {token}"}
    )
    if res.status_code not in (201, 409):
        print(f"{email}: trial not started ({res.json().get('code')})")
    return token


def name_and_join(owner_email: str, owner_name: str, editor_email: str, editor_name: str, pid: str) -> None:
    """Display names, and the editor as an active member (no invitation mail)."""
    import app  # noqa: F401  (before SQLAlchemy: keeps platform off WMI on Windows)
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.licence import clock
    from app.models import User
    from app.projects.models import ProjectMember

    with SessionLocal() as db:
        users = {}
        for email, name in ((owner_email, owner_name), (editor_email, editor_name)):
            user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
            if user is None:
                raise SystemExit(f"no account {email} in this database (is the API using server/.env?)")
            if not user.name:
                user.name = name
            users[email] = user
        editor = users[editor_email]
        member = db.scalar(select(ProjectMember).where(ProjectMember.project_id == pid, ProjectMember.user_id == editor.id))
        if member is None:
            member = db.scalar(
                select(ProjectMember).where(ProjectMember.project_id == pid, func.lower(ProjectMember.email) == editor_email.lower())
            )
        now = clock.now()
        if member is None:
            member = ProjectMember(project_id=pid, email=editor_email.lower(), invited_by=users[owner_email].id, invited_at=now)
            db.add(member)
        member.user_id, member.role, member.state = editor.id, "editor", "active"
        member.invite_id, member.invite_token_hash, member.accepted_at = None, None, member.accepted_at or now
        db.commit()


# --- the project ---------------------------------------------------------------------------


def upload_files(api: Api, files: list[bytes]) -> str:
    """One snapshot upload holding every file (share-bundle §5); returns its id."""
    opened = api.call(
        "POST", "/uploads", headers=UPLOADS,
        json={"purpose": "snapshot", "files": [
            {"sha256": hashlib.sha256(d).hexdigest(), "bytes": len(d), "content_type": "application/octet-stream"} for d in files
        ]},
    )
    part = opened["part_bytes"]
    for data, state in zip(files, opened["files"]):
        if state["state"] == "present":
            continue
        for n in range(state["parts"]):
            if n in state.get("received", []):
                continue
            chunk = data[n * part : (n + 1) * part]
            api.call(
                "PUT", f"/uploads/{opened['upload_id']}/files/{state['sha256']}/parts/{n}", data=chunk,
                headers={**UPLOADS, "Content-Type": "application/octet-stream", "X-Part-Sha256": hashlib.sha256(chunk).hexdigest()},
            )
    return opened["upload_id"]


def snapshot_with_digest(api: Api, pid: str, at_seq: int) -> dict:
    tbxp = (FIXTURES / "project-log" / "snapshot-0000.tbxp").read_bytes()
    digest = DIGEST.read_bytes()
    upload_id = upload_files(api, [tbxp, digest])
    return api.call(
        "POST", f"/projects/{pid}/snapshots", headers={**LOG, "Idempotency-Key": secrets.token_hex(16)},
        json={"at_seq": at_seq, "doc_version": 38, "upload_id": upload_id, "files": {
            "tbxp": hashlib.sha256(tbxp).hexdigest(), "tbxpack": None, "digest": hashlib.sha256(digest).hexdigest()}},
    )


def ensure_project(api: Api, name: str) -> tuple[str, int]:
    """The owner's project called `name` with the fixture's 12 operations and a
    digest snapshot at its head; returns (project id, head)."""
    owned = [p for p in api.call("GET", "/projects", headers=LOG)["projects"] if p["name"] == name and p["role"] == "owner"]
    if owned:
        pid = owned[0]["project_id"]
    else:
        project = api.call(
            "POST", "/projects", headers={**LOG, "Idempotency-Key": secrets.token_hex(16)}, json={"name": name, "doc_version": 38}
        )
        pid = project["project_id"]
        author = api.call("GET", "/licence/account", headers=LICENCE)["author_id"]
        remote = json.loads((FIXTURES / "project-log" / "ops-remote.json").read_text(encoding="utf-8"))
        replica = secrets.token_hex(16)
        ops = [dict(op, author=author, replica_id=replica, op_id=secrets.token_hex(16), base_seq=0) for op in remote["ops"]]
        api.call("POST", f"/projects/{pid}/ops", headers=LOG, json={"replica_id": replica, "ops": ops})
        print(f"created {name} ({pid}) with the fixture's {len(ops)} operations")
    head = api.call("GET", f"/projects/{pid}", headers=LOG)["head_seq"]
    latest = requests.request("GET", f"{api.base}/projects/{pid}/snapshots/latest", timeout=30,
                              headers={**LOG, "Authorization": f"Bearer {api.token}"})
    has_digest = latest.status_code == 200 and (latest.json()["files"].get("digest") is not None)
    if not has_digest or latest.json()["at_seq"] != head:
        snapshot_with_digest(api, pid, head)
    print(f"snapshot with its digest at {head}")
    return pid, head


def ensure_followed_set(api: Api, pid: str, head: int) -> str:
    sets = api.call("GET", f"/projects/{pid}/panoramas", headers=LOG)["sets"]
    following = [s for s in sets if s["following"] and s["mine"]]
    if following:
        return following[0]["set_id"]
    pending = api.call("GET", "/jobs", headers=JOBS, params={"project_id": pid, "kind": "panorama"})["jobs"]
    pending = [j for j in pending if j["follow"] and j["state"] in ("queued", "claimed", "running", "succeeded")]
    if pending:
        return pending[0]["job_id"]
    views = [v["id"] for v in json.loads(DIGEST.read_text(encoding="utf-8"))["views"]]
    job = api.call(
        "POST", "/jobs", headers={**JOBS, "Idempotency-Key": secrets.token_hex(16)},
        json={"kind": "panorama", "project_id": pid, "at_seq": head, "views": views, "follow": True},
    )
    return job["job_id"]


def cmd_setup(args) -> int:
    base = args.api.rstrip("/")
    owner_session = session_for(base, args.email, args.password)
    session_for(base, args.editor_email, args.editor_password)
    owner = Api(base, device_for(base, owner_session, args.email, "DEMO-DESKTOP"))
    pid, head = ensure_project(owner, args.project_name)
    name_and_join(args.email, args.name, args.editor_email, args.editor_name, pid)
    editor_session = session_for(base, args.editor_email, args.editor_password)
    editor_token = device_for(base, editor_session, args.editor_email, "SAM-DESKTOP")
    print(f"{args.editor_name} ({args.editor_email}) is an editor of {args.project_name}")
    if not args.no_render:
        set_id = ensure_followed_set(owner, pid, head)
        print(f"followed panorama set: {set_id} (a worker renders it; PF6's human test steps 2-3)")
    print(f"{args.project_name}, head {head}, digest at {head}")
    print(f"project id: {pid}")
    print(f"{args.editor_name}'s device token: {editor_token}")
    print(f"on the phone, signed in as {args.email}: {args.site.rstrip('/')}/app/project/?id={pid}")
    return 0


def cmd_move(args) -> int:
    api = Api(args.api, args.token)
    digest = json.loads(DIGEST.read_text(encoding="utf-8"))
    names = {e["id"]: e["name"] for key in ("products", "rooms", "openings") for e in digest.get(key, [])}
    entity = args.entity.lower()
    if entity not in names and len(entity) != 32:  # the start of a name ("Oslo")
        entity = next((i for i, n in names.items() if n.lower().startswith(entity)), entity)
    agent = args.token.startswith("tbx_live_")  # PF12: an API key pushes through /v1 as an agent
    prefix = "/v1" if agent else ""
    base = args.base if args.base is not None else api.call("GET", f"{prefix}/projects/{args.project}", headers=LOG)["head_seq"]
    name = f"Move {names.get(entity, 'object')}"[:80]
    raw = b"TBXD" + json.dumps({"stand_in": True, "name": name, "rows": [entity]}).encode()
    import base64

    op = {
        "op_id": secrets.token_hex(16),
        "at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()), "touched": [entity], "kind": "delta",
        "name": name, "base_seq": base, "delta_format": "o5/38", "delta": base64.b64encode(raw).decode("ascii"),
    }
    if not agent:  # a key's operations get the key's own author id from the server
        op.update(author=api.call("GET", "/licence/account", headers=LICENCE)["author_id"], author_kind="person")
    answer = api.call("POST", f"{prefix}/projects/{args.project}/ops", headers=LOG, json={"replica_id": secrets.token_hex(16), "ops": [op]})
    result = answer["results"][0]
    if result["status"] == "accepted":
        print(f"{name}: accepted as {result['server_seq']} (head {answer['head_seq']})")
    else:
        print(f"{name}: {result['status']} {result.get('reason', '')}".rstrip())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="demo_mobile.py", description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--token", help="a device token, tbx_dev_..., or an API key, tbx_live_... (move)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("setup", help="the owner, an editor and a shared House for the phone")
    p.add_argument("--email", required=True, help="the owner (signs in on the phone)")
    p.add_argument("--password", required=True)
    p.add_argument("--name", default="Alex")
    p.add_argument("--editor-email", required=True, help="the second person (the desktop's stand-in)")
    p.add_argument("--editor-password", default="password123")
    p.add_argument("--editor-name", default="Sam")
    p.add_argument("--project-name", default="House")
    p.add_argument("--site", default="http://127.0.0.1:3112", help="the served site, for the printed address")
    p.add_argument("--no-render", action="store_true", help="skip the followed panorama set")
    p = sub.add_parser("move", help="push one Move operation from a device")
    p.add_argument("--project", required=True)
    p.add_argument("--entity", required=True, help="32-hex entity id or the start of its name (the digest's products, rooms, openings)")
    p.add_argument("--base", type=int, help="the sequence it was made at (default: the head)")
    args = parser.parse_args(argv)
    if args.command == "setup":
        return cmd_setup(args)
    if not args.token:
        raise SystemExit("move needs --token tbx_dev_... (setup prints the editor's) or an API key tbx_live_...")
    return cmd_move(args)


if __name__ == "__main__":
    raise SystemExit(main())
