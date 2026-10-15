"""The mobile web client's server side (PF9): the doc's four pytest names
first (author id on /auth/me, web `action` operations through the project
log), then what the client reads that PF9 adds — the snapshot's project
digest (a MINOR proposal for project-log §6.4), members' author ids (to name
who won a conflict) and a project's followed panorama sets for its members —
and `scripts/demo_mobile.py` driven through the human-test path."""

import hashlib
import json
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.projects import presence, waiters
from app.render.models import RenderJob, RenderSet

from .conftest import signup
from .licence_helpers import error_of
from .project_helpers import (
    CONTRACT,
    FIXTURES,
    Person,
    action_op,
    create,
    hex32,
    invite_and_accept,
    pull,
    push,
    pushed,
    upload,
)

DIGESTS = Path(__file__).parent / "contracts" / "project-digest"
RENDER = Path(__file__).parent / "contracts" / "render-jobs"


@pytest.fixture(autouse=True)
def _clean_project_state():
    presence.reset()
    waiters.reset()
    yield
    presence.reset()
    waiters.reset()


def fixture_action() -> dict:
    return json.loads((FIXTURES / "action-move.json").read_text(encoding="utf-8"))


def digest_bytes() -> bytes:
    return (DIGESTS / "digest-house.json").read_bytes()


def snapshot_with_digest(client, headers: dict, pid: str, at_seq: int, digest: bytes | None, *, listed: bool = True):
    tbxp = (FIXTURES / "snapshot-0000.tbxp").read_bytes()
    files = [tbxp] + ([digest] if digest is not None and listed else [])
    upload_id = upload(client, headers, files)
    body = {
        "at_seq": at_seq,
        "doc_version": 38,
        "upload_id": upload_id,
        "files": {
            "tbxp": hashlib.sha256(tbxp).hexdigest(),
            "tbxpack": None,
            "digest": hashlib.sha256(digest).hexdigest() if digest is not None else None,
        },
    }
    return client.post(f"/projects/{pid}/snapshots", json=body, headers={**headers, "Idempotency-Key": hex32()})


# --- the doc's Tests table -------------------------------------------------------------------------


def test_auth_me_includes_author_id(client):
    person = Person(client, "phone@example.com", trial=False)
    me = client.get("/auth/me", headers=person.session)
    assert me.status_code == 200
    author = me.json()["author_id"]
    assert len(author) == 32 and all(c in "0123456789abcdef" for c in author)
    assert author == person.author_id  # what /licence/account (5.7) says
    # Minted once: a fresh account gets one from /auth/me before any device exists.
    fresh = signup(client, "fresh@example.com")
    first = client.get("/auth/me", headers=fresh).json()["author_id"]
    assert len(first) == 32 and client.get("/auth/me", headers=fresh).json()["author_id"] == first
    assert client.get("/auth/me").status_code == 401


def test_web_action_op_accepted_by_project_log(client):
    owner = Person(client, "owner@example.com")
    fixture = fixture_action()  # CL1's bare §6.2 operation: refs `<kind>#<id>`, no session or request_id
    owner.set_author_id(fixture["author"])
    pid = create(client, owner.dev)["project_id"]
    # Twelve other operations of the owner first, from another replica, touching other ids.
    filler = [action_op(owner.author_id, [hex32()]) for _ in range(12)]
    assert pushed(client, owner.web, pid, hex32(), filler)["head_seq"] == 12

    sent = {k: v for k, v in fixture.items() if k not in ("server_seq",)}
    answer = pushed(client, owner.web, pid, fixture["replica_id"], [sent])
    assert answer["results"] == [{"op_id": sent["op_id"], "status": "accepted", "server_seq": 13}]
    got = pull(client, owner.web, pid, after=12)["ops"][0]
    for key, value in sent.items():
        assert got[key] == value, key
    assert got["server_seq"] == 13 and got["kind"] == "action" and got["delta"] is None
    # Sent again (a retry after a lost answer): a duplicate with its number.
    again = pushed(client, owner.web, pid, fixture["replica_id"], [sent])
    assert again["results"][0] == {"op_id": sent["op_id"], "status": "duplicate", "server_seq": 13}


def test_web_action_op_conflict_visible(client):
    owner = Person(client, "owner@example.com")
    sam = Person(client, "sam@example.com")
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, sam, "editor")
    sofa = hex32()
    # Sam moves the sofa on the desktop (a delta from a device) at head 0 …
    from .project_helpers import delta_op

    won = pushed(client, sam.dev, pid, sam.replica, [delta_op(sam.author_id, [sofa], name="Move sofa")])
    assert won["results"][0]["status"] == "accepted"
    # … while the phone, offline at head 0, moved it too: rejected with Sam's as winning.
    mine = action_op(owner.author_id, [sofa], args={"refs": [sofa], "by_mm": [-250, 0, 0]}, base_seq=0)
    later = action_op(owner.author_id, [hex32()], base_seq=0)
    answer = pushed(client, owner.web, pid, owner.replica, [mine, later])
    first, second = answer["results"]
    assert first["status"] == "rejected" and first["reason"] == "conflict"
    assert [w["server_seq"] for w in first["winning"]] == [1]
    assert first["winning"][0]["author"] == sam.author_id and first["winning"][0]["name"] == "Move sofa"
    assert second == {"op_id": later["op_id"], "status": "not_processed"}
    # The client names the winner from the members list (author ids, PF9).
    members = client.get(f"/projects/{pid}/members", headers=owner.web).json()["members"]
    by_author = {m["author_id"]: m["name"] for m in members if m["author_id"]}
    assert by_author[first["winning"][0]["author"]] == "sam"


def test_web_push_requires_editor(client):
    owner = Person(client, "owner@example.com")
    viewer = Person(client, "viewer@example.com", trial=False)
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, viewer, "viewer")
    op = action_op(viewer.author_id, [hex32()])
    res = push(client, viewer.web, pid, viewer.replica, [op])
    body = error_of(res, 403, "forbidden")
    assert body["data"]["needed"] == "editor" and body["data"]["role"] == "viewer"
    # Viewers still read: the record, the log and presence.
    assert client.get(f"/projects/{pid}", headers=viewer.web).json()["role"] == "viewer"
    assert pull(client, viewer.web, pid)["head_seq"] == 0
    # No session at all: 401.
    assert push(client, CONTRACT, pid, viewer.replica, [op]).status_code == 401


# --- the snapshot's project digest (project-log §6.4 MINOR proposal) --------------------------------


def test_snapshot_digest_registered_and_served(client):
    owner = Person(client, "owner@example.com")
    pid = create(client, owner.dev)["project_id"]
    digest = digest_bytes()
    res = snapshot_with_digest(client, owner.dev, pid, 0, digest)
    assert res.status_code == 201, res.text
    files = res.json()["files"]
    assert files["digest"]["sha256"] == hashlib.sha256(digest).hexdigest() and files["digest"]["bytes"] == len(digest)
    latest = client.get(f"/projects/{pid}/snapshots/latest", headers=owner.web)
    assert latest.status_code == 200
    url = latest.json()["files"]["digest"]["url"]
    got = client.get(url.replace("http://testserver", ""))
    assert got.status_code == 200 and got.content == digest
    assert json.loads(got.content)["schema"] == "truebex-project-digest/1"
    # The project's bytes count the digest once.
    record = client.get(f"/projects/{pid}", headers=owner.web).json()
    assert record["bytes"] == len((FIXTURES / "snapshot-0000.tbxp").read_bytes()) + len(digest)
    # A snapshot without one answers `digest: null` (older kernels).
    plain = snapshot_with_digest(client, owner.dev, pid, 0, None)
    assert plain.status_code == 201 and plain.json()["files"]["digest"] is None


def test_snapshot_digest_validation_and_auth(client):
    owner = Person(client, "owner@example.com")
    viewer = Person(client, "viewer@example.com", trial=False)
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, viewer, "viewer")
    # Not JSON, or another schema: 422 on files.digest.
    for bad in (b"not json", json.dumps({"schema": "truebex-project-digest/9"}).encode()):
        res = snapshot_with_digest(client, owner.dev, pid, 0, bad)
        assert error_of(res, 422, "validation_failed")["data"]["fields"][0]["field"] == "files.digest"
    # Named but not uploaded: upload_incomplete, like any snapshot file.
    res = snapshot_with_digest(client, owner.dev, pid, 0, digest_bytes(), listed=False)
    error_of(res, 422, "upload_incomplete")
    # Not 64 hex.
    tbxp = (FIXTURES / "snapshot-0000.tbxp").read_bytes()
    upload_id = upload(client, owner.dev, [tbxp])
    body = {"at_seq": 0, "doc_version": 38, "upload_id": upload_id,
            "files": {"tbxp": hashlib.sha256(tbxp).hexdigest(), "digest": "abc"}}
    res = client.post(f"/projects/{pid}/snapshots", json=body, headers=owner.dev)
    assert error_of(res, 422, "validation_failed")["data"]["fields"][0]["field"] == "files.digest"
    # A viewer cannot register one; nobody unauthenticated can read one.
    assert snapshot_with_digest(client, viewer.web, pid, 0, digest_bytes()).status_code == 403
    assert client.get(f"/projects/{pid}/snapshots/latest", headers=CONTRACT).status_code == 401


def test_snapshot_digest_kept_and_pruned_with_its_snapshot(client):
    from app.projects import snapshots
    from app.storage import get_store

    owner = Person(client, "owner@example.com")
    pid = create(client, owner.dev)["project_id"]
    first = json.loads(digest_bytes())
    for n in range(7):
        body = json.dumps({**first, "note": f"snapshot {n}"}).encode()
        assert snapshot_with_digest(client, owner.dev, pid, 0, body).status_code == 201
    oldest = hashlib.sha256(json.dumps({**first, "note": "snapshot 0"}).encode()).hexdigest()
    newest = hashlib.sha256(json.dumps({**first, "note": "snapshot 6"}).encode()).hexdigest()
    with SessionLocal() as db:
        assert snapshots.prune_project(db, pid) == 2
    store = get_store()
    assert store.stat(snapshots.blob_key(pid, oldest)) is None
    assert store.stat(snapshots.blob_key(pid, newest)) is not None


# --- members carry author ids -------------------------------------------------------------------------


def test_members_carry_author_id(client):
    owner = Person(client, "owner@example.com")
    sam = Person(client, "sam@example.com", trial=False)
    pid = create(client, owner.dev)["project_id"]
    client.post(f"/projects/{pid}/members", json={"email": "later@example.com", "role": "viewer"}, headers=owner.web)
    invite_and_accept(client, owner, pid, sam, "editor")
    members = {m["email"]: m for m in client.get(f"/projects/{pid}/members", headers=sam.web).json()["members"]}
    assert members["owner@example.com"]["author_id"] == owner.author_id
    assert members["sam@example.com"]["author_id"] == sam.author_id
    assert members["later@example.com"]["author_id"] is None  # an invitation has no person yet
    opened = client.get(f"/projects/{pid}", headers=sam.web).json()
    assert {m["author_id"] for m in opened["members"]} >= {owner.author_id, sam.author_id}


# --- a project's followed panorama sets, for its members ----------------------------------------------


def _followed_set(owner_id: int, pid: str, *, rev: int = 1, active: bool = True) -> str:
    """A followed set as PF6 leaves it after its first render (the fixture manifest)."""
    from datetime import datetime, timezone

    from app.render import tiles

    manifest = json.loads((RENDER / "manifest-panorama.json").read_text(encoding="utf-8"))
    from app.storage import get_store

    job_id = hex32()
    key = tiles.manifest_key(job_id)

    get_store().put(key, json.dumps(manifest).encode(), content_type="application/json")
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.add(
            RenderJob(
                job_id=job_id, kind="panorama", worker_class="gpu-std", state="succeeded", rev=rev, project_id=pid, at_seq=0,
                account_kind="user", account_id=owner_id, views=[v["view"] for v in manifest["views"]], changed=[],
                quality="standard", follow=True, set_id=job_id, output_key=key, created_at=now, updated_at=now,
            )
        )
        db.add(
            RenderSet(
                follow_job_id=job_id, project_id=pid, account_kind="user", account_id=owner_id,
                views=[v["view"] for v in manifest["views"]], latest_job_id=job_id, at_seq=0, rev=rev, active=active,
                created_at=now, updated_at=now,
            )
        )
        db.commit()
    assert tiles.tiles_base()
    return job_id


def test_project_panoramas_for_members(client):
    owner = Person(client, "owner@example.com")
    sam = Person(client, "sam@example.com", trial=False)
    stranger = Person(client, "stranger@example.com", trial=False)
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, sam, "viewer")
    set_id = _followed_set(owner.user_id, pid)

    listed = client.get(f"/projects/{pid}/panoramas", headers=sam.web)
    assert listed.status_code == 200, listed.text
    sets = listed.json()["sets"]
    assert [s["set_id"] for s in sets] == [set_id]
    assert sets[0]["following"] is True and sets[0]["mine"] is False and sets[0]["rev"] == 1
    assert client.get(f"/projects/{pid}/panoramas", headers=owner.web).json()["sets"][0]["mine"] is True

    state = client.get(f"/projects/{pid}/panoramas/{set_id}", headers=sam.web)
    assert state.status_code == 200 and state.headers["cache-control"] == "private, no-store"
    body = state.json()
    assert body["rev"] == 1 and body["manifest"]["schema"] == "truebex-tiles/1" and body["manifest"]["tiles_base"]
    # Long-poll: nothing newer than rev 1 within 0.2 s → the same state.
    waited = client.get(f"/projects/{pid}/panoramas/{set_id}", params={"rev": 1, "wait_s": 0.2}, headers=sam.web)
    assert waited.status_code == 200 and waited.json()["rev"] == 1

    # Auth and validation failures.
    assert client.get(f"/projects/{pid}/panoramas", headers=CONTRACT).status_code == 401
    assert client.get(f"/projects/{pid}/panoramas", headers=stranger.web).status_code == 404
    assert client.get(f"/projects/{pid}/panoramas/{set_id}", headers=stranger.web).status_code == 404
    assert client.get(f"/projects/{pid}/panoramas/{hex32()}", headers=sam.web).status_code == 404
    bad = client.get(f"/projects/{pid}/panoramas/{set_id}", params={"rev": 1, "wait_s": 99}, headers=sam.web)
    error_of(bad, 422, "validation_failed")
    # A set of another project is not this project's.
    other = create(client, owner.dev, "Other")["project_id"]
    assert client.get(f"/projects/{other}/panoramas/{set_id}", headers=owner.web).status_code == 404


def test_project_panoramas_hide_sets_of_people_who_left(client):
    owner = Person(client, "owner@example.com")
    sam = Person(client, "sam@example.com")
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, sam, "editor")
    sams = _followed_set(sam.user_id, pid)
    _followed_set(owner.user_id, pid, active=False)  # stopped, but its last render still shows
    assert len(client.get(f"/projects/{pid}/panoramas", headers=owner.web).json()["sets"]) == 2
    assert client.delete(f"/projects/{pid}/members/{sam.user_id}", headers=owner.web).status_code == 204
    left = client.get(f"/projects/{pid}/panoramas", headers=owner.web).json()["sets"]
    assert sams not in [s["set_id"] for s in left] and len(left) == 1 and left[0]["following"] is False
    assert client.get(f"/projects/{pid}/panoramas/{sams}", headers=owner.web).status_code == 404


# --- scripts/demo_mobile.py, as the human test runs it ---------------------------------------------------


def test_demo_mobile_script_human_test_path(client, monkeypatch, capsys):
    import requests

    from scripts import demo_mobile

    def route(method, url, headers=None, timeout=None, **kw):
        return client.request(method, url.replace("http://127.0.0.1:8000", ""), headers=headers, **kw)

    monkeypatch.setattr(requests, "request", route)
    monkeypatch.setattr(requests, "post", lambda url, **kw: route("POST", url, **kw))
    assert demo_mobile.main(["setup", "--email", "alex@example.com", "--password", "password123",
                             "--editor-email", "sam@example.com"]) == 0
    out = capsys.readouterr().out
    pid = out.split("project id: ")[1].split()[0]
    sam_token = out.split("Sam's device token: ")[1].split()[0]
    assert "head 12" in out and "digest at 12" in out and "/app/project/?id=" + pid in out
    # The followed set of the digest's three saved views waits for a worker.
    set_id = out.split("followed panorama set: ")[1].split()[0]
    with SessionLocal() as db:
        job = db.get(RenderJob, set_id)
        assert job.kind == "panorama" and job.follow and job.state == "queued" and len(job.views) == 3

    alex = {"Authorization": "Bearer " + client.post(
        "/auth/login", json={"email": "alex@example.com", "password": "password123"}).json()["access_token"]}
    projects = client.get("/projects", headers={**alex, **CONTRACT}).json()["projects"]
    assert [(p["name"], p["role"]) for p in projects] == [("House", "owner")]
    members = client.get(f"/projects/{pid}/members", headers={**alex, **CONTRACT}).json()["members"]
    assert {(m["name"], m["role"], m["state"]) for m in members} == {("Alex", "owner", "active"), ("Sam", "editor", "active")}
    latest = client.get(f"/projects/{pid}/snapshots/latest", headers={**alex, **CONTRACT}).json()
    assert latest["at_seq"] == 12 and latest["files"]["digest"]["bytes"] == len(digest_bytes())

    # Sam (a device) moves the sofa; the phone's offline edit made at 12 is then rejected.
    digest = json.loads(digest_bytes())
    sofa = next(p["id"] for p in digest["products"] if p["name"].startswith("Oslo"))
    assert demo_mobile.main(["--token", sam_token, "move", "--project", pid, "--entity", sofa]) == 0
    assert "accepted as 13" in capsys.readouterr().out
    me = client.get("/auth/me", headers=alex).json()["author_id"]
    late = action_op(me, [sofa], args={"refs": [sofa], "by_mm": [250, 0, 0]}, base_seq=12)
    answer = pushed(client, {**alex, **CONTRACT}, pid, hex32(), [late])
    assert answer["results"][0]["status"] == "rejected"

    # Running setup again reuses the accounts, the project and the queued set.
    assert demo_mobile.main(["setup", "--email", "alex@example.com", "--password", "password123",
                             "--editor-email", "sam@example.com"]) == 0
    again = capsys.readouterr().out
    assert f"project id: {pid}" in again and f"followed panorama set: {set_id}" in again
    assert len(client.get("/projects", headers={**alex, **CONTRACT}).json()["projects"]) == 1
