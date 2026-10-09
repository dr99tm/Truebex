"""The project service (PF4, contract project-log v1.0): the contract's §10
platform tests first, then PF4's per-endpoint tests (happy path, auth
failure, validation failure on each)."""

import base64
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import mail, tasks
from app.database import SessionLocal
from app.projects import hooks, presence, quotas, waiters
from app.projects.models import Project, ProjectOp, ProjectSnapshot
from app.storage import get_store

from .conftest import signup
from .licence_helpers import Clock, error_of
from .project_helpers import (
    CONTRACT,
    FIXTURES,
    Person,
    action_op,
    create,
    delta_op,
    dev,
    hex32,
    invite_and_accept,
    invite_token,
    pull,
    push,
    pushed,
    snapshot,
    web,
)


@pytest.fixture(autouse=True)
def _clean_project_state():
    presence.reset()
    waiters.reset()
    yield
    presence.reset()
    waiters.reset()


def statuses(answer: dict) -> list[str]:
    return [r["status"] for r in answer["results"]]


# --- contract §10 platform tests ----------------------------------------------------------


def test_push_assigns_contiguous_seq(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    replicas = [hex32() for _ in range(8)]

    def pusher(replica: str) -> list[int]:
        seqs = []
        for round_ in range(4):
            ops = [delta_op(a.author_id, [hex32()]) for _ in range(3)]
            res = push(client, a.dev, pid, replica, ops)
            assert res.status_code == 200, res.text
            assert statuses(res.json()) == ["accepted"] * 3
            seqs += [r["server_seq"] for r in res.json()["results"]]
        return seqs

    with ThreadPoolExecutor(max_workers=8) as pool:
        per_replica = list(pool.map(pusher, replicas))
    every = sorted(s for seqs in per_replica for s in seqs)
    assert every == list(range(1, 97))  # 8 pushers x 4 pushes x 3 operations, no gaps
    for seqs in per_replica:
        assert seqs == sorted(seqs)  # a replica's batches keep their order
    log = pull(client, a.dev, pid, limit=1000)
    assert [op["server_seq"] for op in log["ops"]] == list(range(1, 97))
    assert log["head_seq"] == 96 and log["more"] is False


def test_push_duplicate_op_id(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    batch = [delta_op(a.author_id, [hex32()]) for _ in range(3)]
    first = pushed(client, a.dev, pid, a.replica, batch)
    assert [r["server_seq"] for r in first["results"]] == [1, 2, 3]
    again = pushed(client, a.dev, pid, a.replica, batch)
    assert statuses(again) == ["duplicate"] * 3
    assert [r["server_seq"] for r in again["results"]] == [1, 2, 3] and again["head_seq"] == 3
    # Mixed: a duplicate keeps its first number, the new one gets the next.
    fresh = delta_op(a.author_id, [hex32()])
    mixed = pushed(client, a.dev, pid, a.replica, [batch[1], fresh, fresh])
    assert mixed["results"] == [
        {"op_id": batch[1]["op_id"], "status": "duplicate", "server_seq": 2},
        {"op_id": fresh["op_id"], "status": "accepted", "server_seq": 4},
        {"op_id": fresh["op_id"], "status": "duplicate", "server_seq": 4},
    ]
    # Upper-case op ids are the same ids (§6.1: readers accept either case).
    upper = dict(batch[0], op_id=batch[0]["op_id"].upper())
    assert pushed(client, a.dev, pid, a.replica, [upper])["results"][0] == {
        "op_id": batch[0]["op_id"], "status": "duplicate", "server_seq": 1
    }


def test_conflict_returns_winning_op_and_stops_batch(client):
    a = Person(client, "a@example.com")
    b = Person(client, "b@example.com")
    pid = create(client, a.dev)["project_id"]
    invite_and_accept(client, a, pid, b, "editor")
    wall, door, room = hex32(), hex32(), hex32()
    win = delta_op(a.author_id, [wall], name="Move wall")
    assert pushed(client, a.dev, pid, a.replica, [win])["results"][0]["server_seq"] == 1

    # b made these at base 0, before seeing a's operation.
    first = delta_op(b.author_id, [door])
    clash = delta_op(b.author_id, sorted([wall, room]))
    later = delta_op(b.author_id, [room])
    answer = pushed(client, b.dev, pid, b.replica, [first, clash, later])
    assert statuses(answer) == ["accepted", "rejected", "not_processed"]
    assert answer["results"][0]["server_seq"] == 2 and answer["head_seq"] == 2
    rejected = answer["results"][1]
    assert rejected["reason"] == "conflict" and rejected["more"] is False
    assert [w["op_id"] for w in rejected["winning"]] == [win["op_id"]]
    winning = rejected["winning"][0]
    assert winning["server_seq"] == 1 and winning["author"] == a.author_id and winning["name"] == "Move wall"
    assert winning["replica_id"] == a.replica and winning["delta"] == win["delta"]
    assert answer["results"][2] == {"op_id": later["op_id"], "status": "not_processed"}

    # Rule 1: made after seeing 1 (base_seq 1), the same wall is accepted.
    remade = delta_op(b.author_id, [wall], base_seq=2)
    assert pushed(client, b.dev, pid, b.replica, [remade])["results"][0]["server_seq"] == 3


def test_same_replica_never_conflicts(client):
    a = Person(client, "a@example.com")
    b = Person(client, "b@example.com")
    pid = create(client, a.dev)["project_id"]
    invite_and_accept(client, a, pid, b, "editor")
    wall = hex32()
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [wall])])
    # The same replica again from base 0: its own operation never conflicts.
    again = pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [wall])])
    assert statuses(again) == ["accepted"]
    # Another replica of the same person does conflict.
    other = pushed(client, a.dev, pid, hex32(), [delta_op(a.author_id, [wall])])
    assert statuses(other) == ["rejected"]

    # A restore is always accepted and conflicts with operations made before it.
    snap = snapshot(client, a.dev, pid, 2, b"tbxp at 2").json()
    version = client.post(
        f"/projects/{pid}/versions",
        json={"name": "Two", "at_seq": 2, "snapshot_id": snap["snapshot_id"]},
        headers=a.web,
    ).json()
    pushed(client, b.dev, pid, b.replica, [delta_op(b.author_id, [hex32()], base_seq=2)])  # 3
    restored = client.post(f"/projects/{pid}/versions/{version['version_id']}/restore", headers=b.web)
    assert restored.status_code == 201, restored.text
    assert restored.json()["op"]["server_seq"] == 4
    # Even b's own next operation, made before the restore (base 3), touching nothing a touched.
    late = pushed(client, b.dev, pid, b.replica, [delta_op(b.author_id, [hex32()], base_seq=3)])
    assert statuses(late) == ["rejected"] and late["results"][0]["winning"][0]["kind"] == "restore"


def test_two_client_reconciliation(client):
    a = Person(client, "a@example.com")
    b = Person(client, "b@example.com")
    pid = create(client, a.dev)["project_id"]
    invite_and_accept(client, a, pid, b, "editor")
    rng = random.Random(40)
    walls = [hex32() for _ in range(6)]  # a small pool, so the two often collide

    class Replica:
        def __init__(self, person: Person) -> None:
            self.person = person
            self.replica = hex32()
            self.applied = 0
            self.log: list[str] = []
            self.conflicts = 0

        def sync(self) -> None:
            page = pull(client, self.person.dev, pid, after=self.applied, limit=1000)
            self.log += [op["op_id"] for op in page["ops"]]
            self.applied = page["head_seq"]

        def edit(self) -> None:
            touched = sorted(rng.sample(walls, rng.choice([1, 2])))
            while True:
                op = delta_op(self.person.author_id, touched, base_seq=self.applied)
                answer = pushed(client, self.person.dev, pid, self.replica, [op])
                result = answer["results"][0]
                if result["status"] == "accepted":
                    return
                # Rule 4: catch up, re-make it as a new operation, push again.
                assert result["status"] == "rejected" and result["winning"]
                self.conflicts += 1
                self.sync()

    ra, rb = Replica(a), Replica(b)
    for i in range(50):
        (ra if i % 2 == 0 else rb).edit()
        if rng.random() < 0.3:
            (rb if i % 2 == 0 else ra).sync()
    ra.sync()
    rb.sync()
    assert ra.applied == rb.applied == 50
    assert ra.log == rb.log and len(set(ra.log)) == 50
    assert ra.conflicts + rb.conflicts > 0  # the interleaving did collide


def test_pull_long_poll_wakes_on_push(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    got: dict = {}

    def waiting_pull() -> None:
        got["res"] = client.get(f"/projects/{pid}/ops", params={"after": 0, "wait_s": 10}, headers=a.dev)
        got["at"] = time.monotonic()

    thread = threading.Thread(target=waiting_pull)
    thread.start()
    deadline = time.monotonic() + 5
    while waiters.waiting_count(pid) == 0 and time.monotonic() < deadline:
        time.sleep(0.02)
    assert waiters.waiting_count(pid) == 1
    pushed_at = time.monotonic()
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()])])
    thread.join(timeout=10)
    assert got["res"].status_code == 200, got["res"].text
    assert [op["server_seq"] for op in got["res"].json()["ops"]] == [1]
    assert got["at"] - pushed_at < 1.0
    assert waiters.waiting_count(pid) == 0

    # Nothing new: the pull holds for wait_s, then answers empty.
    started = time.monotonic()
    empty = pull(client, a.dev, pid, after=1, wait_s=1)
    assert empty == {"ops": [], "head_seq": 1, "more": False}
    assert 0.9 <= time.monotonic() - started < 3


def test_roles_enforced(client):
    owner = Person(client, "owner@example.com")
    editor = Person(client, "editor@example.com")
    viewer = Person(client, "viewer@example.com", trial=False)
    stranger = Person(client, "stranger@example.com")
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, editor, "editor")
    invite_and_accept(client, owner, pid, viewer, "viewer")
    snap = snapshot(client, owner.dev, pid, 0, b"tbxp zero").json()
    version = client.post(
        f"/projects/{pid}/versions", json={"name": "Zero", "at_seq": 0, "snapshot_id": snap["snapshot_id"]}, headers=owner.web
    ).json()

    def reads(person: Person) -> list:
        h = person.web
        return [
            client.get(f"/projects/{pid}", headers=h),
            client.get(f"/projects/{pid}/ops", headers=h),
            client.get(f"/projects/{pid}/snapshots/latest", headers=h),
            client.get(f"/projects/{pid}/versions", headers=h),
            client.get(f"/projects/{pid}/members", headers=h),
            client.get(f"/projects/{pid}/presence", headers=h),
            client.put(f"/projects/{pid}/presence", json={"replica_id": person.replica, "client": "web"}, headers=h),
        ]

    def edits(person: Person) -> list:
        h = person.web
        return [
            push(client, h, pid, person.replica, [delta_op(person.author_id, [hex32()])]),
            snapshot(client, h, pid, 0, b"tbxp zero"),
            client.post(f"/projects/{pid}/versions", json={"name": "V", "at_seq": 0, "snapshot_id": snap["snapshot_id"]}, headers=h),
            client.post(f"/projects/{pid}/versions/{version['version_id']}/restore", headers=h),
        ]

    def owner_only(person: Person) -> list:
        h = person.web
        return [
            client.patch(f"/projects/{pid}", json={"name": "Renamed"}, headers=h),
            client.post(f"/projects/{pid}/members", json={"email": "new@example.com", "role": "viewer"}, headers=h),
            client.patch(f"/projects/{pid}/members/{viewer.user_id}", json={"role": "viewer"}, headers=h),
            client.delete(f"/projects/{pid}/members/{editor.user_id if person is not editor else viewer.user_id}", headers=h),
            client.delete(f"/projects/{pid}", headers=h),
        ]

    for res in reads(viewer):
        assert res.status_code == 200, res.text
    for res in edits(viewer):
        assert error_of(res, 403, "forbidden")["data"] == {"role": "viewer", "needed": "editor"}
    for res in owner_only(viewer):
        assert error_of(res, 403, "forbidden")["data"] == {"role": "viewer", "needed": "owner"}

    for res in reads(editor):
        assert res.status_code == 200, res.text
    for res in edits(editor):
        assert res.status_code in (200, 201), res.text
    for res in owner_only(editor):
        assert error_of(res, 403, "forbidden")["data"] == {"role": "editor", "needed": "owner"}

    for res in reads(owner) + edits(owner):
        assert res.status_code in (200, 201), res.text
    # A non-member never learns the project exists.
    for res in reads(stranger) + edits(stranger) + owner_only(stranger):
        error_of(res, 404, "not_found")
    for res in owner_only(owner):
        assert res.status_code in (200, 201, 204), res.text


def test_device_token_cannot_delete_project(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    body = error_of(client.delete(f"/projects/{pid}", headers=a.dev), 403, "session_required")
    assert body["data"] == {"credential": "device"}
    key = client.post("/keys", json={"name": "ci"}, headers=a.session).json()["key"]
    body = error_of(client.delete(f"/projects/{pid}", headers=dev(key)), 403, "session_required")
    assert body["data"] == {"credential": "api_key"}
    error_of(client.delete(f"/projects/{pid}", headers=CONTRACT), 401, "unauthenticated")
    assert client.get(f"/projects/{pid}", headers=a.dev).status_code == 200
    # The website (a session) deletes it: gone at once for everyone.
    assert client.delete(f"/projects/{pid}", headers=a.web).status_code == 204
    error_of(client.get(f"/projects/{pid}", headers=a.dev), 404, "not_found")
    assert client.get("/projects", headers=a.web).json()["projects"] == []


def test_snapshot_requires_complete_upload(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    tbxp, pack = b"the project at 0" * 100, b"embedded assets"
    from .project_helpers import upload

    import hashlib

    upload_id = upload(client, a.dev, [tbxp, pack], send=False)
    body = {
        "at_seq": 0,
        "doc_version": 38,
        "upload_id": upload_id,
        "files": {"tbxp": hashlib.sha256(tbxp).hexdigest(), "tbxpack": hashlib.sha256(pack).hexdigest()},
    }
    res = client.post(f"/projects/{pid}/snapshots", json=body, headers=a.dev)
    assert sorted(error_of(res, 422, "upload_incomplete")["data"]["missing"]) == sorted(body["files"].values())
    # A file the session does not list is missing too.
    other = dict(body, files={"tbxp": "ab" * 32, "tbxpack": None})
    assert error_of(client.post(f"/projects/{pid}/snapshots", json=other, headers=a.dev), 422, "upload_incomplete")["data"] == {
        "missing": ["ab" * 32]
    }
    # Sent in full, the same files register.
    upload_id = upload(client, a.dev, [tbxp, pack])
    res = client.post(f"/projects/{pid}/snapshots", json=dict(body, upload_id=upload_id), headers=a.dev)
    assert res.status_code == 201, res.text
    snap = res.json()
    assert snap["at_seq"] == 0 and snap["files"]["tbxp"]["bytes"] == len(tbxp)
    assert snap["files"]["tbxpack"]["sha256"] == hashlib.sha256(pack).hexdigest()
    # The URL downloads the bytes (15 minutes).
    url = snap["files"]["tbxp"]["url"]
    assert client.get(url.replace("http://testserver", "")).content == tbxp
    # Validation and auth.
    error_of(client.post(f"/projects/{pid}/snapshots", json=dict(body, files={"tbxp": "nothex"}), headers=a.dev), 422, "validation_failed")
    error_of(client.post(f"/projects/{pid}/snapshots", json=body, headers=CONTRACT), 401, "unauthenticated")
    # The upload belongs to the device: the website session cannot use it.
    error_of(client.post(f"/projects/{pid}/snapshots", json=dict(body, upload_id=upload_id), headers=a.web), 404, "not_found")


def test_version_restore_appends_op(client):
    a = Person(client, "a@example.com")
    b = Person(client, "b@example.com")
    pid = create(client, a.dev)["project_id"]
    invite_and_accept(client, a, pid, b, "editor")
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()]) for _ in range(3)])
    snap = snapshot(client, a.dev, pid, 3, b"state at 3").json()
    res = client.post(
        f"/projects/{pid}/versions",
        json={"name": "Planning issue", "note": "Before the stair moved.", "at_seq": 3, "snapshot_id": snap["snapshot_id"]},
        headers=a.dev,
    )
    assert res.status_code == 201, res.text
    version = res.json()
    assert version["name"] == "Planning issue" and version["at_seq"] == 3 and version["created_by"] == a.user_id
    pushed(client, b.dev, pid, b.replica, [delta_op(b.author_id, [hex32()], base_seq=3) for _ in range(2)])

    res = client.post(f"/projects/{pid}/versions/{version['version_id']}/restore", headers=b.dev)
    assert res.status_code == 201, res.text
    op = res.json()["op"]
    assert op["server_seq"] == 6 and op["kind"] == "restore"
    assert op["restore"] == {"version_id": version["version_id"], "at_seq": 3, "snapshot_id": snap["snapshot_id"]}
    assert op["author"] == b.author_id and op["author_kind"] == "person"
    assert op["replica_id"] not in (a.replica, b.replica) and op["touched"] == [] and op["delta"] is None
    assert "Planning issue" in op["name"]
    # Everyone pulls it; operations made before it are rejected with it as winner.
    assert pull(client, a.dev, pid, after=5)["ops"] == [op]
    stale = pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()], base_seq=5)])
    assert stale["results"][0]["status"] == "rejected" and stale["results"][0]["winning"] == [op]
    assert pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()], base_seq=6)])["head_seq"] == 7
    # The versions list names it; an unknown version is 404.
    assert [v["version_id"] for v in client.get(f"/projects/{pid}/versions", headers=b.dev).json()["versions"]] == [
        version["version_id"]
    ]
    error_of(client.post(f"/projects/{pid}/versions/{hex32()}/restore", headers=b.dev), 404, "not_found")


@pytest.mark.parametrize("backend", ["memory", "db"])
def test_presence_expires_after_ttl(client, monkeypatch, backend):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "projects_presence_backend", backend)
    clk = Clock(monkeypatch)
    a = Person(client, "a@example.com")
    b = Person(client, "b@example.com")
    pid = create(client, a.dev)["project_id"]
    invite_and_accept(client, a, pid, b, "viewer")
    beat = json.loads((FIXTURES / "presence.json").read_text(encoding="utf-8"))["heartbeat"]
    res = client.put(f"/projects/{pid}/presence", json=dict(beat, replica_id=b.replica), headers=b.dev)
    assert res.status_code == 200, res.text
    assert res.json() == {"ttl_s": 30, "others": []}
    res = client.put(f"/projects/{pid}/presence", json={"replica_id": a.replica, "client": "web"}, headers=a.web)
    others = res.json()["others"]
    assert len(others) == 1
    sam = others[0]
    assert sam["user_id"] == b.user_id and sam["client"] == "desktop" and sam["editing"] == beat["editing"]
    assert sam["view"]["eye_mm"] == [4200, 1800, 1600] and sam["seen_at"]

    clk.advance(seconds=20)
    client.put(f"/projects/{pid}/presence", json={"replica_id": a.replica, "client": "web"}, headers=a.web)
    clk.advance(seconds=11)  # b silent for 31 s, a for 11 s
    present = client.get(f"/projects/{pid}/presence", headers=a.dev).json()["present"]
    assert [p["user_id"] for p in present] == [a.user_id]
    # `leaving` removes at once.
    res = client.put(f"/projects/{pid}/presence", json={"replica_id": a.replica, "client": "web", "leaving": True}, headers=a.web)
    assert res.json()["others"] == []
    assert client.get(f"/projects/{pid}/presence", headers=a.dev).json() == {"present": []}
    # The sweep drops stale entries from the store itself.
    client.put(f"/projects/{pid}/presence", json={"replica_id": b.replica, "client": "desktop"}, headers=b.dev)
    clk.advance(seconds=31)
    from app.projects import jobs as project_jobs

    assert project_jobs.sweep_presence(clk.at) == 1
    # Validation: unknown client, too many ids.
    error_of(client.put(f"/projects/{pid}/presence", json={"replica_id": a.replica, "client": "tv"}, headers=a.web), 422, "validation_failed")
    many = {"replica_id": a.replica, "client": "web", "selection": [hex32() for _ in range(51)]}
    error_of(client.put(f"/projects/{pid}/presence", json=many, headers=a.web), 422, "validation_failed")
    error_of(client.put(f"/projects/{pid}/presence", json={"replica_id": a.replica, "client": "web"}, headers=CONTRACT), 401, "unauthenticated")


def test_contract_header_and_error_envelope(client):
    a = Person(client, "a@example.com")
    res = client.post("/projects", json={"name": "House", "doc_version": 38}, headers=a.dev)
    assert res.headers["X-Truebex-Contract"] == "project-log/1.0"
    pid = res.json()["project_id"]
    # No header reads as the current version; a newer MINOR is served.
    plain = {"Authorization": f"Bearer {a.token}"}
    assert client.get(f"/projects/{pid}", headers=plain).status_code == 200
    assert client.get(f"/projects/{pid}", headers={**plain, "X-Truebex-Contract": "project-log/1.7"}).status_code == 200
    body = error_of(client.get(f"/projects/{pid}", headers={**plain, "X-Truebex-Contract": "project-log/2.0"}), 400, "contract_version")
    assert body["data"]["supported"] == ["project-log/1.0"]
    error_of(client.get(f"/projects/{hex32()}", headers=a.dev), 404, "not_found")
    error_of(client.get(f"/projects/not-an-id", headers=a.dev), 404, "not_found")
    body = error_of(client.get("/projects", headers=CONTRACT), 401, "unauthenticated")
    assert body["retry_after_s"] is None
    res = client.get(f"/projects/{hex32()}", headers=a.dev)
    assert res.headers["X-Truebex-Contract"] == "project-log/1.0"


# --- PF4 per-endpoint tests ---------------------------------------------------------------------


def test_projects_create_list_open(client):
    a = Person(client, "a@example.com")
    b = Person(client, "b@example.com")
    by_device = create(client, a.dev, "House")
    assert by_device["role"] == "owner" and by_device["head_seq"] == 0 and by_device["members"] == 1
    assert by_device["owner"] == {"user_id": a.user_id, "name": "a"}
    assert by_device["latest_snapshot"] is None and by_device["doc_version"] == 38 and by_device["bytes"] == 0
    assert len(by_device["project_id"]) == 32
    by_web = create(client, a.web, "Studio flat")
    theirs = create(client, b.dev, "Shared office")
    invite_and_accept(client, b, theirs["project_id"], a, "viewer")

    listed = client.get("/projects", headers=a.web).json()
    assert [(p["name"], p["role"]) for p in listed["projects"]] == [
        ("Shared office", "viewer"), ("Studio flat", "owner"), ("House", "owner")
    ]
    assert listed["next_cursor"] is None
    # Cursor pages.
    page = client.get("/projects", params={"limit": 2}, headers=a.dev).json()
    assert len(page["projects"]) == 2 and page["next_cursor"]
    rest = client.get("/projects", params={"limit": 2, "cursor": page["next_cursor"]}, headers=a.dev).json()
    assert [p["name"] for p in rest["projects"]] == ["House"] and rest["next_cursor"] is None
    error_of(client.get("/projects", params={"cursor": "garbage"}, headers=a.dev), 422, "validation_failed")
    # Activity moves a project to the top.
    pushed(client, a.dev, by_device["project_id"], a.replica, [delta_op(a.author_id, [hex32()])])
    assert client.get("/projects", headers=a.web).json()["projects"][0]["name"] == "House"

    opened = client.get(f"/projects/{theirs['project_id']}", headers=a.dev).json()
    assert opened["role"] == "viewer" and opened["owner"]["user_id"] == b.user_id
    assert [(m["email"], m["role"], m["state"]) for m in opened["members"]] == [
        ("b@example.com", "owner", "active"), ("a@example.com", "viewer", "active")
    ]
    assert opened["quota"] == {"bytes": quotas.PLACEHOLDER["pro"]["cloud_bytes"], "bytes_used": 0}

    renamed = client.patch(f"/projects/{by_web['project_id']}", json={"name": "  Studio   flat 2 "}, headers=a.dev)
    assert renamed.status_code == 200 and renamed.json()["name"] == "Studio flat 2"

    error_of(client.post("/projects", json={"name": "House", "doc_version": 38}, headers=CONTRACT), 401, "unauthenticated")
    error_of(client.post("/projects", json={"name": "   ", "doc_version": 38}, headers=a.dev), 422, "validation_failed")
    error_of(client.post("/projects", json={"name": "x" * 121, "doc_version": 38}, headers=a.dev), 422, "validation_failed")
    error_of(client.post("/projects", json={"name": "House"}, headers=a.dev), 422, "validation_failed")
    error_of(client.patch(f"/projects/{by_web['project_id']}", json={"name": ""}, headers=a.web), 422, "validation_failed")
    # An API key is not a project credential here (PF12 mirrors these under /v1).
    key = client.post("/keys", json={"name": "ci"}, headers=a.session).json()["key"]
    error_of(client.get("/projects", headers=dev(key)), 401, "unauthenticated")


def test_projects_push_requires_cloud_sync(client):
    owner = Person(client, "owner@example.com")
    free = Person(client, "free@example.com", trial=False)
    # Creating a cloud project needs the feature, from the app or the website.
    for headers in (free.dev, free.web):
        body = error_of(client.post("/projects", json={"name": "House", "doc_version": 38}, headers=headers), 403, "plan_required")
        assert body["data"] == {"feature": "cloud.sync", "plan": "free"}
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, free, "editor")
    res = push(client, free.dev, pid, free.replica, [delta_op(free.author_id, [hex32()])])
    assert error_of(res, 403, "plan_required")["data"]["feature"] == "cloud.sync"
    res = snapshot(client, free.dev, pid, 0, b"free tbxp")
    assert error_of(res, 403, "plan_required")["data"]["feature"] == "cloud.sync"
    # Pull and presence need no paid feature.
    assert pull(client, free.dev, pid)["head_seq"] == 0
    assert client.put(f"/projects/{pid}/presence", json={"replica_id": free.replica, "client": "desktop"}, headers=free.dev).status_code == 200
    # A light client (session) writes action operations with the same role checks only (§4).
    answer = pushed(client, free.web, pid, free.replica, [action_op(free.author_id, [hex32()])])
    assert statuses(answer) == ["accepted"]


def test_projects_push_validation(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    wall = hex32()
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [wall])])

    def bad(op: dict, field: str) -> None:
        res = push(client, a.dev, pid, a.replica, [op])
        body = error_of(res, 422, "validation_failed")
        assert body["data"]["fields"][0]["field"].startswith(field), body

    unsorted = delta_op(a.author_id, [])
    unsorted["touched"] = ["f" * 32, "a" * 32]
    bad(unsorted, "ops[0].touched")
    dup_ids = dict(delta_op(a.author_id, []), touched=["a" * 32, "a" * 32])
    bad(dup_ids, "ops[0].touched")
    bad(delta_op(a.author_id, [wall], base_seq=2), "ops[0].base_seq")
    bad(delta_op(a.author_id, [wall], delta=b"\0" * (5 * 1024 * 1024)), "ops[0].delta")
    bad(dict(delta_op(a.author_id, [wall]), kind="merge"), "ops[0].kind")
    bad(dict(delta_op(a.author_id, [wall]), kind="restore"), "ops[0].kind")
    bad(action_op(a.author_id, [wall], tool="export_pdf", args={}), "ops[0].action.tool")
    bad(action_op(a.author_id, [wall], tool="place", args={"kind": "wall"}), "ops[0].action.args.kind")
    bad(dict(action_op(a.author_id, [wall]), action={"tool": "move", "args": {}, "permission": "export", "session": hex32(), "request_id": hex32()}), "ops[0].action.permission")
    bad(dict(delta_op(a.author_id, [wall]), delta="not base64!"), "ops[0].delta")
    bad(dict(delta_op(a.author_id, [wall]), delta_format="v54"), "ops[0].delta_format")
    bad(dict(delta_op(a.author_id, [wall]), at="yesterday"), "ops[0].at")
    bad(dict(delta_op(a.author_id, [wall]), op_id="xyz"), "ops[0].op_id")
    bad(delta_op(hex32(), [wall]), "ops[0].author")  # a person pushes as themselves
    bad(dict(delta_op(a.author_id, [wall]), name="n" * 81), "ops[0].name")
    res = push(client, a.dev, pid, "nope", [delta_op(a.author_id, [wall])])
    error_of(res, 422, "validation_failed")
    error_of(push(client, a.dev, pid, a.replica, []), 422, "validation_failed")
    # 201 operations → 413.
    many = [delta_op(a.author_id, [hex32()]) for _ in range(201)]
    assert error_of(push(client, a.dev, pid, a.replica, many), 413, "too_large")["data"]["limit"] == 200
    # Nothing of a failed push is stored; an agent's operation carries its session id; valid actions pass.
    agent = dict(delta_op(hex32(), [hex32()]), author_kind="agent")
    move = action_op(a.author_id, [wall], base_seq=1)
    place = action_op(a.author_id, [hex32()], tool="place", args={"kind": "object", "asset": "Chair", "at_mm": [0, 0, 0]})
    assert statuses(pushed(client, a.dev, pid, a.replica, [agent, move, place])) == ["accepted"] * 3
    assert pull(client, a.dev, pid)["head_seq"] == 4
    # Auth: none → 401.
    error_of(push(client, CONTRACT, pid, a.replica, [delta_op(a.author_id, [wall])]), 401, "unauthenticated")


def test_projects_quota_exceeded(client, monkeypatch):
    monkeypatch.setitem(quotas.PLACEHOLDER, "pro", {"cloud_projects": 1, "cloud_bytes": 100_000, "project_members": 2})
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    body = error_of(client.post("/projects", json={"name": "Two", "doc_version": 38}, headers=a.web), 403, "quota_exceeded")
    assert body["data"] == {"limit": 1, "used": 1, "quota": "cloud_projects"}
    # Members: the owner and one more.
    ok = client.post(f"/projects/{pid}/members", json={"email": "b@example.com", "role": "editor"}, headers=a.web)
    assert ok.status_code == 201
    body = error_of(
        client.post(f"/projects/{pid}/members", json={"email": "c@example.com", "role": "viewer"}, headers=a.web),
        403,
        "quota_exceeded",
    )
    assert body["data"] == {"limit": 2, "used": 2, "quota": "project_members"}
    # Bytes: a 60 kB snapshot fits, a second distinct 60 kB one does not.
    assert snapshot(client, a.dev, pid, 0, b"1" * 60_000).status_code == 201
    body = error_of(snapshot(client, a.dev, pid, 0, b"2" * 60_000), 403, "quota_exceeded")
    assert body["data"] == {"limit": 100_000, "used": 60_000, "quota": "cloud_bytes"}
    # The same file again costs nothing.
    assert snapshot(client, a.dev, pid, 0, b"1" * 60_000).status_code == 201
    # An offloaded delta counts too.
    res = push(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()], delta=b"d" * 70_000)])
    assert error_of(res, 403, "quota_exceeded")["data"]["quota"] == "cloud_bytes"
    # A deleted project frees its place.
    assert client.delete(f"/projects/{pid}", headers=a.web).status_code == 204
    assert client.post("/projects", json={"name": "Two", "doc_version": 38}, headers=a.web).status_code == 201


def test_projects_snapshot_seq_ahead_and_prune(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()]) for _ in range(7)])
    body = error_of(snapshot(client, a.dev, pid, 8, b"ahead"), 409, "seq_ahead")
    assert body["data"] == {"head_seq": 7, "at_seq": 8}
    snaps = []
    for seq in range(1, 8):
        res = snapshot(client, a.dev, pid, seq, f"tbxp at {seq}".encode() * 50)
        assert res.status_code == 201, res.text
        snaps.append(res.json())
    first = snaps[0]
    client.post(f"/projects/{pid}/versions", json={"name": "First", "at_seq": 1, "snapshot_id": first["snapshot_id"]}, headers=a.dev)
    latest = client.get(f"/projects/{pid}/snapshots/latest", headers=a.dev).json()
    assert latest["snapshot_id"] == snaps[-1]["snapshot_id"] and latest["files"]["tbxp"]["url"]
    before = client.get(f"/projects/{pid}", headers=a.dev).json()["bytes"]
    assert before == sum(s["files"]["tbxp"]["bytes"] for s in snaps)

    ran = tasks.run_due(only=["projects.snapshots.prune"], force=True)
    assert ran == ["projects.snapshots.prune"]
    with SessionLocal() as db:
        kept = db.scalars(select(ProjectSnapshot.at_seq).where(ProjectSnapshot.project_id == pid).order_by(ProjectSnapshot.at_seq)).all()
    assert kept == [1, 3, 4, 5, 6, 7]  # the newest five plus the version's
    dropped = snaps[1]["files"]["tbxp"]["sha256"]
    assert get_store().stat(f"projects/{pid}/blobs/{dropped}") is None
    assert get_store().stat(f"projects/{pid}/blobs/{first['files']['tbxp']['sha256']}") is not None
    after = client.get(f"/projects/{pid}", headers=a.dev).json()["bytes"]
    assert after == before - snaps[1]["files"]["tbxp"]["bytes"]
    # 5.9 before any snapshot is 404.
    other = create(client, a.dev, "Empty")["project_id"]
    error_of(client.get(f"/projects/{other}/snapshots/latest", headers=a.dev), 404, "not_found")


def test_projects_version_snapshot_mismatch(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()]) for _ in range(2)])
    snap = snapshot(client, a.dev, pid, 1, b"at one").json()
    res = client.post(f"/projects/{pid}/versions", json={"name": "Two", "at_seq": 2, "snapshot_id": snap["snapshot_id"]}, headers=a.dev)
    assert error_of(res, 422, "snapshot_seq_mismatch")["data"] == {"snapshot_at_seq": 1, "at_seq": 2}
    error_of(client.post(f"/projects/{pid}/versions", json={"name": "X", "at_seq": 1, "snapshot_id": hex32()}, headers=a.dev), 404, "not_found")
    error_of(client.post(f"/projects/{pid}/versions", json={"name": "", "at_seq": 1, "snapshot_id": snap["snapshot_id"]}, headers=a.dev), 422, "validation_failed")
    error_of(client.post(f"/projects/{pid}/versions", json={"name": "One", "at_seq": 1, "snapshot_id": snap["snapshot_id"]}, headers=CONTRACT), 401, "unauthenticated")
    ok = client.post(f"/projects/{pid}/versions", json={"name": "One", "at_seq": 1, "snapshot_id": snap["snapshot_id"]}, headers=a.dev)
    assert ok.status_code == 201


def test_projects_members_invite_flow(client):
    a = Person(client, "a@example.com")
    b = Person(client, "b@example.com", trial=False)
    pid = create(client, a.dev, "House")["project_id"]
    res = client.post(f"/projects/{pid}/members", json={"email": " B@Example.com ", "role": "editor"}, headers=a.dev)
    assert res.status_code == 201, res.text
    invited = res.json()
    assert invited["user_id"] is None and invited["state"] == "invited" and invited["email"] == "b@example.com"
    assert invited["role"] == "editor" and len(invited["invite_id"]) == 32
    msg = mail.OUTBOX[-1]
    assert msg.to == "b@example.com" and "House" in msg.subject and msg.reply_to == "a@example.com"
    token = invite_token(msg.text)
    assert len(token) >= 43 and token in msg.html and "an editor" in msg.text
    # Nobody else sees an invitation as access: b is not a member yet.
    error_of(client.get(f"/projects/{pid}", headers=b.web), 404, "not_found")
    # Accepting needs a session and the token.
    error_of(client.post("/projects/invites/accept", json={"token": token}, headers=b.dev), 403, "session_required")
    error_of(client.post("/projects/invites/accept", json={"token": token}, headers=CONTRACT), 401, "unauthenticated")
    error_of(client.post("/projects/invites/accept", json={"token": "wrong"}, headers=b.web), 404, "not_found")
    error_of(client.post("/projects/invites/accept", json={}, headers=b.web), 422, "validation_failed")
    accepted = client.post("/projects/invites/accept", json={"token": token}, headers=b.web)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["project"]["role"] == "editor" and accepted.json()["member"]["state"] == "active"
    error_of(client.post("/projects/invites/accept", json={"token": token}, headers=b.web), 404, "not_found")
    assert [p["role"] for p in client.get("/projects", headers=b.web).json()["projects"]] == ["editor"]
    # Inviting a member again → 409.
    error_of(client.post(f"/projects/{pid}/members", json={"email": "b@example.com", "role": "viewer"}, headers=a.web), 409, "already_member")
    error_of(client.post(f"/projects/{pid}/members", json={"email": "a@example.com", "role": "viewer"}, headers=a.web), 409, "already_member")
    error_of(client.post(f"/projects/{pid}/members", json={"email": "nobody", "role": "viewer"}, headers=a.web), 422, "validation_failed")
    error_of(client.post(f"/projects/{pid}/members", json={"email": "c@example.com", "role": "owner"}, headers=a.web), 422, "validation_failed")
    # Change a role; the owner's stays.
    res = client.patch(f"/projects/{pid}/members/{b.user_id}", json={"role": "viewer"}, headers=a.web)
    assert res.status_code == 200 and res.json()["role"] == "viewer"
    error_of(client.patch(f"/projects/{pid}/members/{a.user_id}", json={"role": "editor"}, headers=a.web), 422, "validation_failed")
    error_of(client.patch(f"/projects/{pid}/members/{b.user_id}", json={"role": "boss"}, headers=a.web), 422, "validation_failed")
    error_of(client.patch(f"/projects/{pid}/members/999", json={"role": "viewer"}, headers=a.web), 404, "not_found")
    # The owner cannot leave; a member can.
    error_of(client.delete(f"/projects/{pid}/members/{a.user_id}", headers=a.web), 409, "owner_cannot_leave")
    assert client.delete(f"/projects/{pid}/members/{b.user_id}", headers=b.dev).status_code == 204
    error_of(client.get(f"/projects/{pid}", headers=b.web), 404, "not_found")
    # A pending invitation is withdrawn by its invite_id.
    pending = client.post(f"/projects/{pid}/members", json={"email": "c@example.com", "role": "viewer"}, headers=a.web).json()
    assert client.delete(f"/projects/{pid}/members/{pending['invite_id']}", headers=a.web).status_code == 204
    error_of(client.post("/projects/invites/accept", json={"token": invite_token(mail.OUTBOX[-1].text)}, headers=b.web), 404, "not_found")
    members = client.get(f"/projects/{pid}/members", headers=a.dev).json()["members"]
    assert [(m["email"], m["role"]) for m in members] == [("a@example.com", "owner")]


def test_projects_idempotency_key_replay(client):
    a = Person(client, "a@example.com")
    key = hex32()
    first = client.post("/projects", json={"name": "House", "doc_version": 38}, headers={**a.dev, "Idempotency-Key": key})
    again = client.post("/projects", json={"name": "House", "doc_version": 38}, headers={**a.dev, "Idempotency-Key": key})
    assert first.status_code == again.status_code == 201
    assert again.json() == first.json()
    assert len(client.get("/projects", headers=a.dev).json()["projects"]) == 1
    body = error_of(
        client.post("/projects", json={"name": "Other", "doc_version": 38}, headers={**a.dev, "Idempotency-Key": key}),
        409,
        "idempotency_mismatch",
    )
    assert body["data"] == {"key": key}
    error_of(client.post("/projects", json={"name": "House", "doc_version": 38}, headers={**a.dev, "Idempotency-Key": "short"}), 422, "validation_failed")
    # Another account may use the same key.
    b = Person(client, "b@example.com")
    assert client.post("/projects", json={"name": "House", "doc_version": 38}, headers={**b.dev, "Idempotency-Key": key}).json()["project_id"] != first.json()["project_id"]
    # An error is not kept: the retry runs again.
    free = Person(client, "free@example.com", trial=False)
    k2 = hex32()
    error_of(client.post("/projects", json={"name": "F", "doc_version": 38}, headers={**free.dev, "Idempotency-Key": k2}), 403, "plan_required")
    client.post("/licence/trial", json={"plan": "pro"}, headers={"Authorization": f"Bearer {free.token}"})
    assert client.post("/projects", json={"name": "F", "doc_version": 38}, headers={**free.dev, "Idempotency-Key": k2}).status_code == 201
    # 5.11, 5.12 and 5.14 replay too.
    pid = first.json()["project_id"]
    import hashlib

    from .project_helpers import upload

    sbody = {
        "at_seq": 0,
        "doc_version": 38,
        "upload_id": upload(client, a.dev, [b"zero"]),
        "files": {"tbxp": hashlib.sha256(b"zero").hexdigest(), "tbxpack": None},
    }
    k3 = hex32()
    s1 = client.post(f"/projects/{pid}/snapshots", json=sbody, headers={**a.dev, "Idempotency-Key": k3})
    s2 = client.post(f"/projects/{pid}/snapshots", json=sbody, headers={**a.dev, "Idempotency-Key": k3})
    assert s1.status_code == s2.status_code == 201 and s1.json()["snapshot_id"] == s2.json()["snapshot_id"]
    snap = s1.json()
    vbody = {"name": "Zero", "at_seq": 0, "snapshot_id": snap["snapshot_id"]}
    k4 = hex32()
    v1 = client.post(f"/projects/{pid}/versions", json=vbody, headers={**a.dev, "Idempotency-Key": k4}).json()
    v2 = client.post(f"/projects/{pid}/versions", json=vbody, headers={**a.dev, "Idempotency-Key": k4}).json()
    assert v1 == v2 and len(client.get(f"/projects/{pid}/versions", headers=a.dev).json()["versions"]) == 1
    k5 = hex32()
    r1 = client.post(f"/projects/{pid}/versions/{v1['version_id']}/restore", headers={**a.dev, "Idempotency-Key": k5}).json()
    r2 = client.post(f"/projects/{pid}/versions/{v1['version_id']}/restore", headers={**a.dev, "Idempotency-Key": k5}).json()
    assert r1 == r2 and pull(client, a.dev, pid)["head_seq"] == 1
    k6 = hex32()
    inv = {"email": "c@example.com", "role": "viewer"}
    m1 = client.post(f"/projects/{pid}/members", json=inv, headers={**a.dev, "Idempotency-Key": k6})
    m2 = client.post(f"/projects/{pid}/members", json=inv, headers={**a.dev, "Idempotency-Key": k6})
    assert m1.status_code == m2.status_code == 201 and m1.json() == m2.json()
    assert len([m for m in mail.OUTBOX if m.to == "c@example.com"]) == 1
    # Kept 24 h: the expiry job drops older keys.
    from app import idempotency

    from datetime import datetime, timezone

    assert idempotency.expire(datetime.now(timezone.utc) + timedelta(hours=25)) >= 5


def test_projects_fixture_ops_remote_replay(client):
    owner = Person(client, "owner@example.com")
    editor = Person(client, "editor@example.com")
    remote = json.loads((FIXTURES / "ops-remote.json").read_text(encoding="utf-8"))
    action = json.loads((FIXTURES / "action-move.json").read_text(encoding="utf-8"))
    tbxp = (FIXTURES / "snapshot-0000.tbxp").read_bytes()
    project = json.loads((FIXTURES / "project.json").read_text(encoding="utf-8"))
    pid = create(client, owner.dev, project["name"])["project_id"]
    assert snapshot(client, owner.dev, pid, 0, tbxp).status_code == 201
    invite_and_accept(client, owner, pid, editor, "editor")
    editor.set_author_id(remote["ops"][0]["author"])
    owner.set_author_id(action["op"]["author"])

    answer = pushed(client, editor.dev, pid, remote["replica_id"], remote["ops"])
    assert statuses(answer) == ["accepted"] * 12
    assert [r["server_seq"] for r in answer["results"]] == list(range(1, 13)) and answer["head_seq"] == 12
    log = pull(client, owner.dev, pid)
    assert [op["op_id"] for op in log["ops"]] == [op["op_id"] for op in remote["ops"]]
    for got, sent in zip(log["ops"], remote["ops"]):
        assert got["delta"] == sent["delta"] and got["touched"] == sent["touched"] and got["at"] == sent["at"]
        assert got["author"] == sent["author"] and got["name"] == sent["name"] and got["delta_format"] == "o5/38"
    # The web client's action operation lands on top.
    res = pushed(client, owner.web, pid, action["replica_id"], [action["op"]])
    assert res["results"][0] == {"op_id": action["op"]["op_id"], "status": "accepted", "server_seq": 13}
    assert pull(client, editor.dev, pid, after=12)["ops"][0]["action"] == action["op"]["action"]
    # Open = 5.3 → 5.9 → 5.7 from at_seq.
    opened = client.get(f"/projects/{pid}", headers=editor.dev).json()
    assert opened["head_seq"] == 13 and opened["latest_snapshot"]["at_seq"] == 0
    latest = client.get(f"/projects/{pid}/snapshots/latest", headers=editor.dev).json()
    assert client.get(latest["files"]["tbxp"]["url"].replace("http://testserver", "")).content == tbxp


def test_projects_push_hook_called(client):
    a = Person(client, "a@example.com")
    b = Person(client, "b@example.com")
    pid = create(client, a.dev)["project_id"]
    invite_and_accept(client, a, pid, b, "editor")
    seen: list[tuple[str, list[dict]]] = []

    @hooks.on_ops_accepted
    def follow(project_id: str, ops: list[dict]) -> None:
        seen.append((project_id, ops))

    def broken(project_id: str, ops: list[dict]) -> None:
        raise RuntimeError("a subscriber failing never fails the push")

    hooks.on_ops_accepted(broken)
    try:
        wall = hex32()
        first = delta_op(a.author_id, [wall])
        pushed(client, a.dev, pid, a.replica, [first])
        earlier = delta_op(b.author_id, [hex32()])
        pushed(client, b.dev, pid, b.replica, [earlier])
        ok, clash, rest = delta_op(b.author_id, [hex32()]), delta_op(b.author_id, [wall]), delta_op(b.author_id, [hex32()])
        answer = pushed(client, b.dev, pid, b.replica, [earlier, ok, clash, rest])
        assert statuses(answer) == ["duplicate", "accepted", "rejected", "not_processed"]
        assert [(p, [o["op_id"] for o in ops], [o["server_seq"] for o in ops]) for p, ops in seen] == [
            (pid, [first["op_id"]], [1]),
            (pid, [earlier["op_id"]], [2]),
            (pid, [ok["op_id"]], [3]),
        ]
        assert seen[2][1][0]["touched"] == ok["touched"] and seen[2][1][0]["delta"] == ok["delta"]
        # Nothing accepted, no call.
        pushed(client, b.dev, pid, b.replica, [ok])
        assert len(seen) == 3
        # A restore is pushed through the hook too.
        snap = snapshot(client, a.dev, pid, 3, b"three").json()
        vid = client.post(f"/projects/{pid}/versions", json={"name": "V", "at_seq": 3, "snapshot_id": snap["snapshot_id"]}, headers=a.dev).json()["version_id"]
        client.post(f"/projects/{pid}/versions/{vid}/restore", headers=a.dev)
        assert seen[-1][1][0]["kind"] == "restore" and seen[-1][1][0]["server_seq"] == 4
    finally:
        hooks.unsubscribe(follow)
        hooks.unsubscribe(broken)


def test_projects_large_delta_offloaded(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    big = random.Random(4).randbytes(100 * 1024)
    small = b"small delta"
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()], delta=big), delta_op(a.author_id, [hex32()], delta=small)])
    with SessionLocal() as db:
        rows = {r.server_seq: r for r in db.scalars(select(ProjectOp).where(ProjectOp.project_id == pid))}
        assert rows[1].delta is None and rows[1].delta_key == f"projects/{pid}/ops/1.bin" and rows[1].delta_bytes == len(big)
        assert bytes(rows[2].delta) == small and rows[2].delta_key is None
        assert db.get(Project, pid).bytes == len(big)
    with get_store().open(f"projects/{pid}/ops/1.bin") as fh:
        assert fh.read() == big
    log = pull(client, a.dev, pid)
    assert base64.b64decode(log["ops"][0]["delta"]) == big and base64.b64decode(log["ops"][1]["delta"]) == small


# --- more endpoint and job coverage -------------------------------------------------------------


def test_projects_pull_args_and_wait_cap(client, monkeypatch):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()]) for _ in range(5)])
    page = pull(client, a.dev, pid, after=1, limit=2)
    assert [op["server_seq"] for op in page["ops"]] == [2, 3] and page["more"] is True and page["head_seq"] == 5
    for params in ({"limit": 1001}, {"limit": 0}, {"wait_s": 26}, {"after": -1}, {"after": "x"}):
        error_of(client.get(f"/projects/{pid}/ops", params=params, headers=a.dev), 422, "validation_failed")
    error_of(client.get(f"/projects/{pid}/ops", headers=CONTRACT), 401, "unauthenticated")
    # At most N waiting pulls per account (here 0, so the first one to wait is refused).
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "projects_max_waiting_pulls", 0)
    body = error_of(client.get(f"/projects/{pid}/ops", params={"after": 5, "wait_s": 5}, headers=a.dev), 429, "rate_limited")
    assert body["retry_after_s"] == 5
    # A pull with something to return never waits, cap or not.
    assert len(pull(client, a.dev, pid, after=4, wait_s=5)["ops"]) == 1


def test_projects_purge_deleted_after_30_days(client):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()], delta=b"x" * 70_000)])
    assert snapshot(client, a.dev, pid, 1, b"one").status_code == 201
    assert client.delete(f"/projects/{pid}", headers=a.web).status_code == 204
    from datetime import datetime, timezone

    from app.projects import jobs as project_jobs

    now = datetime.now(timezone.utc)
    assert project_jobs.purge_deleted(now + timedelta(days=29)) == 0
    assert get_store().list(f"projects/{pid}/")
    assert project_jobs.purge_deleted(now + timedelta(days=31)) == 1
    assert get_store().list(f"projects/{pid}/") == []
    with SessionLocal() as db:
        assert db.get(Project, pid) is None
        assert db.scalars(select(ProjectOp).where(ProjectOp.project_id == pid)).all() == []


def test_projects_jobs_registered_in_worker():
    names = tasks.registered()
    for job in ("projects.snapshots.prune", "projects.purge_deleted", "projects.presence.sweep", "idempotency.expire", "uploads.expire"):
        assert job in names, job


def test_uploads_snapshot_purpose(client):
    """The upload protocol (share-bundle §5.1-5.3) as snapshots use it: happy
    path, resume, `present`, auth and validation."""
    import hashlib

    from .project_helpers import UPLOADS, upload

    a = Person(client, "a@example.com")
    data = b"snapshot bytes" * 1000
    sha = hashlib.sha256(data).hexdigest()
    auth = {"Authorization": f"Bearer {a.token}", **UPLOADS}
    upload_id = upload(client, a.dev, [data], send=False)
    status = client.get(f"/uploads/{upload_id}", headers=auth).json()
    assert status["files"] == [{"sha256": sha, "state": "missing", "parts": 1, "received": []}]
    bad_part = client.put(
        f"/uploads/{upload_id}/files/{sha}/parts/0", content=data,
        headers={**auth, "Content-Type": "application/octet-stream", "X-Part-Sha256": "0" * 64},
    )
    error_of(bad_part, 422, "part_hash_mismatch")
    upload(client, a.dev, [data])
    # Already stored: a new session answers `present`.
    again = client.post("/uploads", json={"purpose": "snapshot", "files": [{"sha256": sha, "bytes": len(data), "content_type": "application/octet-stream"}]}, headers=auth)
    assert again.status_code == 201 and again.json()["files"][0]["state"] == "present"
    error_of(client.post("/uploads", json={"purpose": "snapshot", "files": []}, headers=auth), 422, "validation_failed")
    error_of(client.post("/uploads", json={"purpose": "holiday", "files": [{"sha256": sha, "bytes": 1, "content_type": "a/b"}]}, headers=auth), 422, "validation_failed")
    error_of(client.post("/uploads", json={"purpose": "snapshot", "files": []}, headers=UPLOADS), 401, "unauthenticated")
    error_of(client.get(f"/uploads/{upload_id}", headers={**a.session, **UPLOADS}), 404, "not_found")


def test_demo_replica_script_human_test_path(client, monkeypatch, capsys):
    """scripts/demo_replica.py as the human test runs it (requests routed into
    the in-process API): login with the trial, push the fixture, pull as the
    invited editor, the conflicting move, presence."""
    import requests

    from scripts import demo_replica

    def route(method, url, headers=None, timeout=None, **kw):
        return client.request(method, url.replace("http://127.0.0.1:8000", ""), headers=headers, **kw)

    monkeypatch.setattr(requests, "request", route)
    monkeypatch.setattr(requests, "post", lambda url, **kw: route("POST", url, **kw))
    signup(client, "a@example.com")
    signup(client, "b@example.com")

    def token_of(email: str) -> str:
        demo_replica.main(["login", "--email", email, "--password", "password123", "--trial"])
        out = capsys.readouterr().out
        assert "Pro trial started" in out and "plan pro" in out
        return out.split("device token: ")[1].split()[0]

    ta, tb = token_of("a@example.com"), token_of("b@example.com")
    demo_replica.main(["--token", ta, "push", "--fixture", str(FIXTURES)])
    out = capsys.readouterr().out
    assert "pushed: 12 accepted" in out and "project House, head 12" in out
    pid = out.split("project id: ")[1].split()[0]
    # The owner invites b in the dashboard; b accepts.
    a_session = client.post("/auth/login", json={"email": "a@example.com", "password": "password123"}).json()["access_token"]
    b_session = client.post("/auth/login", json={"email": "b@example.com", "password": "password123"}).json()["access_token"]
    client.post(f"/projects/{pid}/members", json={"email": "b@example.com", "role": "editor"}, headers=web({"Authorization": f"Bearer {a_session}"}))
    token = invite_token(mail.OUTBOX[-1].text)
    assert client.post("/projects/invites/accept", json={"token": token}, headers=web({"Authorization": f"Bearer {b_session}"})).status_code == 200

    demo_replica.main(["--token", tb, "pull", "--project", pid])
    out = capsys.readouterr().out
    assert "12 operations, head 12" in out
    # Both at head 12: a moves the wall first, then b.
    demo_replica.main(["--token", ta, "move", "--project", pid, "--base", "12"])
    assert "accepted as 13" in capsys.readouterr().out
    demo_replica.main(["--token", tb, "move", "--project", pid, "--base", "12"])
    out = capsys.readouterr().out
    assert "rejected (conflict): replaced by" in out and "13  Move wall" in out
    # The latest snapshot is at 12, ready to be named as a version.
    latest = client.get(f"/projects/{pid}/snapshots/latest", headers=dev(ta)).json()
    assert latest["at_seq"] == 12
    demo_replica.main(["--token", tb, "presence", "--project", pid, "--seconds", "0"])
    assert "left the project" in capsys.readouterr().out
