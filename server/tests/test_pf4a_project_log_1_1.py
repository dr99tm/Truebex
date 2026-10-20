"""PF4a: the project service follows project-log 1.1.0 (CL1).

CL1 wrote the app's own fixtures (Docs/roadmap/fixtures/contracts/project-log/,
-mwcl1fixtures); scripts/sync-contract-fixtures.ps1 copied them byte for byte
into tests/contracts/project-log/. Here: the folder is the app's set, the
app's 12 operations (real deltas, §6.2's byte form, o5/55) and its web
`action` replay through the real endpoints unchanged, 5.9 answers the snapshot
`?id=` names (a replica that reaches a `restore` downloads the version's
snapshot), every active member carries an author_id (5.13), and the routes
speak project-log/1.1 while a 1.0 client keeps working.
"""

import base64
import gzip
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import User

from .conftest import signup
from .licence_helpers import error_of
from .pf12_helpers import ROOT, kh, make_key
from .project_helpers import (
    FIXTURES,
    Person,
    create,
    dev,
    hex32,
    invite_and_accept,
    pull,
    push,
    pushed,
    snapshot,
    web,
)

# The app commit the folder was copied from, and the app's blob of each file
# there (`git ls-tree`); README.md is the platform's own. The folder last
# changed in CL1's 93bc4cac2 (on app main since 496033be3); copied from main
# ad3aa5c45, where it is the same.
APP_REPO = Path(r"T:\unreal5_7_4_projects\truebex_compact")
APP_COMMIT = "93bc4cac24d365eee0d2649bb4f81390af329ca0"
APP_COPIED_FROM = "ad3aa5c45e63924d77d1210f375fdf2135b12aed"
APP_DIR = "Docs/roadmap/fixtures/contracts/project-log"
APP_BLOBS = {
    "action-move.json": "c1bafb73e39fb6891f821b739214673557a25083",
    # PF4b: CL2 added comments.json (project-log 1.2.0, app 83fdeedad); the
    # other seven are CL1's, unchanged (test_pf4b_project_log_1_2.py).
    "comments.json": "589a9e56fe998619f9dc4a9a449ba1b1b5d07087",
    "members.json": "300dd137d78aa9ca3130063dcde1953e99b2daf6",
    "ops-remote.json": "5fa4a75898adb1cad1874d48ceb67471cbdac153",
    "presence.json": "c8f6dbca3a68f4c61ba6e9e3263fbb7c1c4ad2e8",
    "project.json": "1c8bb88bed4cc94c459b176d9c3ceaec07bfcfba",
    "snapshot-0000.tbxp": "51fec5f5bc890504cfce74e36b52eb82bcda539f",
    "versions.json": "5024595cbd3b79f62894c66c08207fdf90209ef6",
}
V1 = {"X-Truebex-Contract": "project-log/1.1"}
# CL1's commits hold the seven files before comments.json.
CL1_BLOBS = {k: v for k, v in APP_BLOBS.items() if k != "comments.json"}
OLD = {"X-Truebex-Contract": "project-log/1.0"}


def git_blob_id(data: bytes) -> str:
    """`git hash-object --no-filters`: the blob id of these exact bytes."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _null_author_id(user_id: int) -> None:
    with SessionLocal() as db:
        db.execute(update(User).where(User.id == user_id).values(author_id=None))
        db.commit()


def _stored_author_id(user_id: int) -> str | None:
    with SessionLocal() as db:
        return db.scalar(select(User.author_id).where(User.id == user_id))


def _is_hex32(value) -> bool:
    return isinstance(value, str) and len(value) == 32 and all(c in "0123456789abcdef" for c in value)


def _replayed(client):
    """The app's project: its snapshot at 0, the editor's 12 operations on top.
    Returns (owner, editor, project id, the 5.6 answer)."""
    owner = Person(client, "ana@example.com")
    editor = Person(client, "sam@example.com")
    project = fixture("project.json")
    remote = fixture("ops-remote.json")
    pid = create(client, owner.dev, project["name"], doc_version=project["doc_version"])["project_id"]
    assert snapshot(client, owner.dev, pid, 0, (FIXTURES / "snapshot-0000.tbxp").read_bytes()).status_code == 201
    invite_and_accept(client, owner, pid, editor, "editor")
    # A person's operations carry their own author_id (licence 5.7): the editor is the app's Sam.
    members = {m["user_id"]: m for m in fixture("members.json")["members"]}
    editor.set_author_id(members[7]["author_id"])
    owner.set_author_id(members[42]["author_id"])
    ops = remote["ops"]
    # ops-remote.json is truebex-project-log-ops/1: no push-level replica_id, each operation names its own.
    replicas = {op["replica_id"] for op in ops}
    assert len(replicas) == 1
    answer = pushed(client, editor.dev, pid, replicas.pop(), ops)
    return owner, editor, pid, answer


# --- the folder is the app's ------------------------------------------------------------------------


def test_pf4a_fixture_folder_is_the_apps_copy():
    """tests/contracts/project-log/ holds the app's files (CL1's seven, and
    CL2's comments.json since PF4b) and this folder's README, each the app's
    blob byte for byte."""
    files = {p.name for p in FIXTURES.iterdir() if p.is_file()}
    assert files == set(APP_BLOBS) | {"README.md"}
    for name, blob in APP_BLOBS.items():
        data = (FIXTURES / name).read_bytes()
        assert git_blob_id(data) == blob, name
        if name.endswith(".json"):
            assert b"\r" not in data, name  # the blob's LF, not a CRLF checkout
    readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
    assert APP_COMMIT[:9] in readme and APP_COPIED_FROM[:9] in readme and "1.1.0" in readme
    # Where the app repository is on this machine, git agrees: its ls-tree at
    # that commit against `git hash-object --no-filters` of each copy.
    git = shutil.which("git")
    if git is None or not (APP_REPO / ".git").exists():
        return
    for commit in (APP_COMMIT, APP_COPIED_FROM):
        tree = subprocess.run(
            [git, "-C", str(APP_REPO), "ls-tree", commit, "--", APP_DIR + "/"],
            capture_output=True, text=True, timeout=60,
        )
        if tree.returncode != 0:  # the commit is not in this clone
            continue
        listed = {}
        for line in tree.stdout.splitlines():
            meta, path = line.split("\t", 1)
            listed[path.rsplit("/", 1)[1]] = meta.split()[2]
        assert listed == CL1_BLOBS, commit
    for name, blob in APP_BLOBS.items():
        here = subprocess.run(
            [git, "hash-object", "--no-filters", "--", str(FIXTURES / name)], capture_output=True, text=True, timeout=60
        )
        assert here.stdout.strip() == blob, name


def test_pf4a_fixture_shapes_are_cl1s():
    """What the platform's readers now meet: per-operation replica ids and real
    deltas (§6.2's byte form), a bare §6.2 action with `<kind>#<id>` refs,
    members with author ids, a 5.18 presence body."""
    remote = fixture("ops-remote.json")
    assert remote["schema"] == "truebex-project-log-ops/1" and "replica_id" not in remote
    assert len(remote["ops"]) == 12
    for op in remote["ops"]:
        assert op["kind"] == "delta" and op["delta_format"] == "o5/55" and _is_hex32(op["replica_id"])
        body = json.loads(gzip.decompress(base64.b64decode(op["delta"], validate=True)))
        assert body["format"] == "o5/55" and set(body) >= {"ids", "keys", "before", "after"}
    action = fixture("action-move.json")
    assert "op" not in action and action["kind"] == "action"
    assert action["action"] == {
        "tool": "move",
        "args": {"refs": ["wall#" + action["touched"][0]], "by_mm": [0, 600, 0]},
        "permission": "edit",
    }
    assert all(_is_hex32(m["author_id"]) for m in fixture("members.json")["members"])
    assert set(fixture("presence.json")) == {"present"}


# --- the app's operations replay through the real endpoints -------------------------------------


def test_pf4a_ops_remote_replays_byte_for_byte(client):
    owner, _editor, pid, answer = _replayed(client)
    remote = fixture("ops-remote.json")["ops"]
    assert [r["status"] for r in answer["results"]] == ["accepted"] * 12
    assert [r["server_seq"] for r in answer["results"]] == list(range(1, 13)) and answer["head_seq"] == 12
    log = pull(client, owner.dev, pid)
    assert log["head_seq"] == 12 and len(log["ops"]) == 12
    for n, (got, sent) in enumerate(zip(log["ops"], remote), start=1):
        for key, value in sent.items():
            if key == "server_seq":
                continue
            assert got[key] == value, (n, key)
        assert got["server_seq"] == n and got["delta_format"] == "o5/55"
        assert got["action"] is None and got["restore"] is None
        # The delta comes back as the app sent it: the same base64, so the same bytes.
        assert base64.b64decode(got["delta"]) == base64.b64decode(sent["delta"])


def test_pf4a_action_move_replays_unchanged(client):
    """The app's action-move.json (no session, no request_id: the kernel's
    replay never reads them) is accepted on top and pulled back unchanged."""
    owner, editor, pid, _ = _replayed(client)
    action = fixture("action-move.json")
    res = pushed(client, editor.web, pid, action["replica_id"], [action])
    assert res["results"] == [{"op_id": action["op_id"], "status": "accepted", "server_seq": 13}]
    got = pull(client, owner.dev, pid, after=12)["ops"]
    assert len(got) == 1
    assert got[0] == {**action, "server_seq": 13, "delta": None, "delta_format": None, "restore": None}
    assert got[0]["action"] == action["action"] and "session" not in got[0]["action"]
    # Sent again: a duplicate with its number.
    again = pushed(client, editor.web, pid, action["replica_id"], [action])
    assert again["results"] == [{"op_id": action["op_id"], "status": "duplicate", "server_seq": 13}]


def test_pf4a_action_session_and_request_id_checked_when_present(client):
    """Scope 3 (a): `session` and `request_id` are optional (agent-interface
    §6.4 adds them on a live call); when present they are 32 hex."""
    owner = Person(client, "ana@example.com")
    pid = create(client, owner.dev)["project_id"]
    base = fixture("action-move.json")

    def op(**action) -> dict:
        return {**base, "op_id": hex32(), "author": owner.author_id, "replica_id": owner.replica, "action": {**base["action"], **action}}

    ok = pushed(client, owner.web, pid, owner.replica, [op(), op(session=hex32(), request_id=hex32())])
    assert [r["status"] for r in ok["results"]] == ["accepted", "accepted"]
    for key in ("session", "request_id"):
        for bad in ("nope", "", None, 7):
            body = error_of(push(client, owner.web, pid, owner.replica, [op(**{key: bad})]), 422, "validation_failed")
            assert body["data"]["fields"][0]["field"] == f"ops[0].action.{key}"
    # The other checks stand: a log-safe tool, the edit permission.
    body = error_of(push(client, owner.web, pid, owner.replica, [op(tool="delete")]), 422, "validation_failed")
    assert body["data"]["fields"][0]["field"] == "ops[0].action.tool"
    body = error_of(push(client, owner.web, pid, owner.replica, [op(permission="read")]), 422, "validation_failed")
    assert body["data"]["fields"][0]["field"] == "ops[0].action.permission"


# --- 5.9 ?id= ---------------------------------------------------------------------------------------


def _version_then_newer_snapshot(client):
    """The app's project with a version named at 0, the 12 operations, a newer
    snapshot at 12. Returns (owner, editor, pid, the version's snapshot, the newer one, tbxp)."""
    owner, editor, pid, _ = _replayed(client)
    tbxp = (FIXTURES / "snapshot-0000.tbxp").read_bytes()
    first = client.get(f"/projects/{pid}/snapshots/latest", headers=owner.dev).json()
    named = client.post(
        f"/projects/{pid}/versions",
        json={"name": "Baseline", "note": "The house as it was first shared.", "at_seq": 0, "snapshot_id": first["snapshot_id"]},
        headers=owner.dev,
    )
    assert named.status_code == 201, named.text
    newer = snapshot(client, editor.dev, pid, 12, tbxp + b"\n")
    assert newer.status_code == 201, newer.text
    return owner, editor, pid, first, newer.json(), tbxp, named.json()


def test_pf4a_snapshot_by_id_after_a_newer_one(client):
    owner, editor, pid, first, newer, tbxp, version = _version_then_newer_snapshot(client)
    # Without ?id= the answer is unchanged: the newest.
    latest = client.get(f"/projects/{pid}/snapshots/latest", headers=editor.dev)
    assert latest.status_code == 200 and latest.json()["snapshot_id"] == newer["snapshot_id"]
    assert latest.headers["X-Truebex-Contract"] == "project-log/1.2"
    # A restore names the version's snapshot; 5.9 ?id= answers that one, with fresh URLs.
    restored = client.post(f"/projects/{pid}/versions/{version['version_id']}/restore", headers=editor.dev)
    assert restored.status_code == 201, restored.text
    wanted = restored.json()["op"]["restore"]["snapshot_id"]
    assert wanted == first["snapshot_id"]
    for headers in (editor.dev, owner.web, {**editor.dev, **OLD}):
        res = client.get(f"/projects/{pid}/snapshots/latest", params={"id": wanted}, headers=headers)
        assert res.status_code == 200, res.text
        snap = res.json()
        assert snap["snapshot_id"] == wanted and snap["at_seq"] == 0
        assert set(snap) == set(latest.json())
        expires = datetime.fromisoformat(snap["files"]["tbxp"]["url_expires_at"].replace("Z", "+00:00"))
        assert expires > datetime.now(timezone.utc)
        assert client.get(snap["files"]["tbxp"]["url"].replace("http://testserver", "")).content == tbxp
    # Either case reads (§6.1); the newest by its own id too.
    assert client.get(f"/projects/{pid}/snapshots/latest", params={"id": wanted.upper()}, headers=owner.dev).json()["snapshot_id"] == wanted
    by_newest = client.get(f"/projects/{pid}/snapshots/latest", params={"id": newer["snapshot_id"]}, headers=owner.dev)
    assert by_newest.json()["snapshot_id"] == newer["snapshot_id"]


def test_pf4a_snapshot_by_id_not_found(client):
    owner, _editor, pid, first, _newer, tbxp, _ = _version_then_newer_snapshot(client)
    other = create(client, owner.dev, "Elsewhere")["project_id"]
    assert snapshot(client, owner.dev, other, 0, tbxp + b"elsewhere").status_code == 201
    theirs = client.get(f"/projects/{other}/snapshots/latest", headers=owner.dev).json()["snapshot_id"]
    for bad in (theirs, "not-a-snapshot", first["snapshot_id"][:31], first["snapshot_id"] + "0", "", hex32()):
        res = client.get(f"/projects/{pid}/snapshots/latest", params={"id": bad}, headers=owner.dev)
        error_of(res, 404, "not_found")
    # A stranger still learns nothing about the project.
    stranger = Person(client, "stranger@example.com")
    error_of(client.get(f"/projects/{pid}/snapshots/latest", params={"id": first["snapshot_id"]}, headers=stranger.dev), 404, "not_found")
    # No credential: 401, as before.
    error_of(client.get(f"/projects/{pid}/snapshots/latest", params={"id": first["snapshot_id"]}, headers=V1), 401, "unauthenticated")
    # The other project's own route answers its snapshot.
    assert client.get(f"/projects/{other}/snapshots/latest", params={"id": theirs}, headers=owner.dev).status_code == 200


def test_pf4a_v1_snapshot_by_id(client):
    owner, _editor, pid, first, newer, tbxp, _ = _version_then_newer_snapshot(client)
    key = make_key(client, owner.session, ["projects:read"])
    auth = kh(key, **V1)
    latest = client.get(f"/v1/projects/{pid}/snapshots/latest", headers=auth)
    assert latest.status_code == 200 and latest.json()["snapshot_id"] == newer["snapshot_id"]
    assert latest.headers["X-Truebex-Contract"] == "project-log/1.2"
    res = client.get(f"/v1/projects/{pid}/snapshots/latest", params={"id": first["snapshot_id"]}, headers=auth)
    assert res.status_code == 200, res.text
    assert res.json()["snapshot_id"] == first["snapshot_id"] and res.json()["at_seq"] == 0
    assert client.get(res.json()["files"]["tbxp"]["url"].replace("http://testserver", "")).content == tbxp
    other = create(client, owner.dev, "Elsewhere")["project_id"]
    assert snapshot(client, owner.dev, other, 0, tbxp + b"elsewhere").status_code == 201
    theirs = client.get(f"/projects/{other}/snapshots/latest", headers=owner.dev).json()["snapshot_id"]
    for bad in (theirs, "not-a-snapshot", hex32()):
        error_of(client.get(f"/v1/projects/{pid}/snapshots/latest", params={"id": bad}, headers=auth), 404, "not_found")
    # A 1.0 client keeps working.
    assert client.get(f"/v1/projects/{pid}/snapshots/latest", headers=kh(key, **OLD)).status_code == 200


# --- 5.13 author_id ---------------------------------------------------------------------------------


def test_pf4a_active_members_always_carry_an_author_id(client):
    owner = Person(client, "ana@example.com")
    pid = create(client, owner.dev)["project_id"]
    # Sam signed up on the website and accepted; never a device, never /auth/me.
    sam_session = signup(client, "sam@example.com")
    res = client.post(f"/projects/{pid}/members", json={"email": "sam@example.com", "role": "editor"}, headers=owner.web)
    assert res.status_code == 201
    from app import mail

    from .project_helpers import invite_token

    accepted = client.post("/projects/invites/accept", json={"token": invite_token(mail.OUTBOX[-1].text)}, headers=web(sam_session))
    assert accepted.status_code == 200, accepted.text
    sam_id = accepted.json()["member"]["user_id"]
    assert _is_hex32(accepted.json()["member"]["author_id"])
    _null_author_id(sam_id)
    assert _stored_author_id(sam_id) is None
    # An invitation without an account: no author_id (null, the key kept for the generated clients).
    client.post(f"/projects/{pid}/members", json={"email": "later@example.com", "role": "viewer"}, headers=owner.web)

    listed = {m["email"]: m for m in client.get(f"/projects/{pid}/members", headers=owner.dev).json()["members"]}
    sam = listed["sam@example.com"]
    assert sam["state"] == "active" and _is_hex32(sam["author_id"])
    assert _stored_author_id(sam_id) == sam["author_id"]  # minted once, kept
    assert listed["ana@example.com"]["author_id"] == owner.author_id
    assert listed["later@example.com"]["state"] == "invited" and listed["later@example.com"]["user_id"] is None
    assert listed["later@example.com"]["author_id"] is None
    # The same id on every read: 5.13 again, 5.3's members, /auth/me, the licence account.
    again = {m["email"]: m for m in client.get(f"/projects/{pid}/members", headers=web(sam_session)).json()["members"]}
    assert again["sam@example.com"]["author_id"] == sam["author_id"]
    opened = client.get(f"/projects/{pid}", headers=owner.dev).json()
    assert {m["email"]: m["author_id"] for m in opened["members"]}["sam@example.com"] == sam["author_id"]
    assert client.get("/auth/me", headers=sam_session).json()["author_id"] == sam["author_id"]

    # A role change answers the member with it, minted if it was missing.
    _null_author_id(sam_id)
    changed = client.patch(f"/projects/{pid}/members/{sam_id}", json={"role": "viewer"}, headers=owner.web)
    assert changed.status_code == 200 and _is_hex32(changed.json()["author_id"])
    assert _stored_author_id(sam_id) == changed.json()["author_id"]


def test_pf4a_v1_members_carry_author_ids(client):
    owner = Person(client, "ana@example.com")
    pid = create(client, owner.dev)["project_id"]
    sam = Person(client, "sam@example.com", trial=False)
    invite_and_accept(client, owner, pid, sam, "editor")
    _null_author_id(sam.user_id)
    key = make_key(client, owner.session, ["projects:read"])
    members = client.get(f"/v1/projects/{pid}/members", headers=kh(key, **V1)).json()["members"]
    assert all(_is_hex32(m["author_id"]) for m in members if m["state"] == "active") and len(members) == 2


# --- project-log/1.1 on the wire ------------------------------------------------------------------


def test_pf4a_routes_speak_project_log_1_1(client):
    owner = Person(client, "ana@example.com")
    res = client.post("/projects", json={"name": "House", "doc_version": 55}, headers=owner.dev)
    assert res.status_code == 201 and res.headers["X-Truebex-Contract"] == "project-log/1.2"
    pid = res.json()["project_id"]
    key = make_key(client, owner.session, ["projects:read"])
    plain = {"Authorization": f"Bearer {owner.token}"}
    routes = [
        (f"/projects/{pid}", plain),
        (f"/projects/{pid}/members", plain),
        (f"/projects/{pid}/panoramas", plain),  # PF9's route under the same contract
        (f"/v1/projects/{pid}", kh(key)),
        (f"/v1/projects/{pid}/panoramas", kh(key)),
    ]
    for path, auth in routes:
        # The app's 1.1, a 1.0 client, a later MINOR and no header at all: 200, the server's
        # version echoed (1.2 since PF4b).
        for sent in ({}, V1, OLD, {"X-Truebex-Contract": "project-log/1.9"}):
            got = client.get(path, headers={**auth, **sent})
            assert got.status_code == 200, (path, sent, got.text)
            assert got.headers["X-Truebex-Contract"] == "project-log/1.2", path
        body = error_of(client.get(path, headers={**auth, "X-Truebex-Contract": "project-log/2.0"}), 400, "contract_version")
        assert body["data"]["supported"] == ["project-log/1.2"]


def test_pf4a_api_documents_name_1_1_and_id():
    """openapi/v1.json and openapi/clients.json (and so the SDKs and both light
    clients generated from them) carry 1.1, 5.9's `id` and the optional action fields."""
    v1 = json.loads((ROOT / "openapi" / "v1.json").read_text(encoding="utf-8"))
    clients = json.loads((ROOT / "openapi" / "clients.json").read_text(encoding="utf-8"))
    # The routes speak 1.2 since PF4b (v1.json); clients.json names what the
    # light clients send, still 1.1 (they call no comment route).
    for doc, path, action, speaks in (
        (v1, "/v1/projects/{project_id}/snapshots/latest", "AgentAction", "project-log/1.2"),
        (clients, "/projects/{project_id}/snapshots/latest", "OperationAction", "project-log/1.1"),
    ):
        op = doc["paths"][path]["get"]
        assert op["x-truebex-contract"] == speaks
        query = {p["name"]: p for p in op["parameters"] if p["in"] == "query"}
        assert "id" in query and not query["id"].get("required", False)
        schema = doc["components"]["schemas"][action]
        assert {"tool", "args", "permission"} <= set(schema["required"])
        assert "session" not in schema["required"] and "request_id" not in schema["required"]
        assert {"session", "request_id"} <= set(schema["properties"])
    for doc, speaks in ((v1, "project-log/1.2"), (clients, "project-log/1.1")):
        for path, ops in doc["paths"].items():
            for method, op in ops.items():
                if isinstance(op, dict) and str(op.get("x-truebex-contract", "")).startswith("project-log/"):
                    assert op["x-truebex-contract"] == speaks, (path, method)
    ops_py = (ROOT / "sdks" / "python" / "truebex" / "_operations.py").read_text(encoding="utf-8")
    assert "'projects_latest_snapshot': {" in ops_py and "'query': ['id']" in ops_py.split("'projects_latest_snapshot'")[1].split("\n")[0]
    assert "project-log/1.0" not in ops_py
    assert "id?: string" in (ROOT / "src" / "lib" / "api-clients.d.ts").read_text(encoding="utf-8")


def test_pf4a_clients_send_1_1():
    """The web client and the Android app send project-log/1.1 (they read 1.1's
    member author ids); a 1.0 server serves any 1.x, so nothing breaks there."""
    for rel in ("src/lib/app.ts", "src/lib/projects.ts", "mobile/android/lib/api/api.dart"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "project-log/1.1" in text and "project-log/1.0" not in text, rel


# --- scripts/demo_replica.py on the app's set -------------------------------------------------------


def test_pf4a_demo_replica_pushes_the_apps_set(client, monkeypatch, capsys):
    import requests

    from scripts import demo_replica

    def route(method, url, headers=None, timeout=None, **kw):
        return client.request(method, url.replace("http://127.0.0.1:8000", ""), headers=headers, **kw)

    monkeypatch.setattr(requests, "request", route)
    monkeypatch.setattr(requests, "post", lambda url, **kw: route("POST", url, **kw))
    signup(client, "ana@example.com")
    demo_replica.main(["login", "--email", "ana@example.com", "--password", "password123", "--trial"])
    token = capsys.readouterr().out.split("device token: ")[1].split()[0]
    demo_replica.main(["--token", token, "push", "--fixture", str(FIXTURES)])
    out = capsys.readouterr().out
    assert "pushed: 12 accepted" in out and "project House (fixture), head 12" in out
    pid = out.split("project id: ")[1].split()[0]
    remote = fixture("ops-remote.json")["ops"]
    log = pull(client, dev(token), pid)
    # The app's operations as this account: its deltas, names, touched ids and replica.
    assert [op["delta"] for op in log["ops"]] == [op["delta"] for op in remote]
    assert [op["name"] for op in log["ops"]] == [op["name"] for op in remote]
    assert {op["replica_id"] for op in log["ops"]} == {remote[0]["replica_id"]}
    assert {op["delta_format"] for op in log["ops"]} == {"o5/55"}
    record = client.get(f"/projects/{pid}", headers=dev(token)).json()
    # The fixture's snapshot at 0 only: a replica opening the project applies the 12 real deltas on it.
    assert record["doc_version"] == 55 and record["latest_snapshot"]["at_seq"] == 0
    assert "snapshot registered" not in out
    demo_replica.main(["--token", token, "pull", "--project", pid])
    out = capsys.readouterr().out
    assert "12 operations, head 12" in out and out.count("o5/55") == 12
    # `move` writes the app's own action (the fixture's wall, `<kind>#<id>`), which a kernel replica applies.
    demo_replica.main(["--token", token, "move", "--project", pid])
    assert "accepted as 13" in capsys.readouterr().out
    moved = pull(client, dev(token), pid, after=12)["ops"][0]
    wall = fixture("action-move.json")["touched"][0]
    assert moved["kind"] == "action" and moved["touched"] == [wall]
    assert moved["action"] == {"tool": "move", "args": {"refs": [f"wall#{wall}"], "by_mm": [0, 600, 0]}, "permission": "edit"}
