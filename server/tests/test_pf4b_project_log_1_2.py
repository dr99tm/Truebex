"""PF4b: the project service follows project-log 1.2.0 (CL2).

CL2 (the app's "several people in one model") published 1.2.0 with one new
fixture, comments.json, and met only its own stub. Here: the folder is the
app's eight files again; the people in a project pin comments, reply, edit,
resolve, reopen and delete them (5.19-5.22) with §5's roles, every change
bumps the project's comment revision by exactly one (contiguous under
concurrent writers, Postgres included), 5.17 / 5.18 carry `comments_rev`, the
app's own comment round-trips through 5.20 and 5.19, and the routes speak
project-log/1.2 while 1.0 and 1.1 clients keep working. /v1 mirrors 5.19-5.22
for API keys.

The app's stub (SyncStub.cpp, "5.19 - 5.22 comments") is the reference where
the contract is silent: a `state` filter never hides a tombstone, a reply takes
its parent's anchor and hangs under the root, a deleted comment answers 404.
"""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select, text, update

from app.database import SessionLocal
from app.models import User
from app.projects import presence, waiters

from .conftest import signup
from .licence_helpers import error_of
from .pf12_helpers import ROOT, kh, make_key
from .project_helpers import CONTRACT, FIXTURES, Person, create, hex32, invite_and_accept, pull
from .test_pf4a_project_log_1_1 import APP_BLOBS, APP_REPO, git_blob_id

# CL2 added comments.json in app commit 83fdeedad (on app main since the merge
# 8692c6ff9, 2026-10-19); PF4b copied the folder from app main 689da345d.
CL2_COMMIT = "83fdeedadf88f8f90e244069264566611411d93d"
CL2_COPIED_FROM = "689da345dd63fb1c3a2f9058e50cc398c4570193"
COMMENTS_BLOB = "589a9e56fe998619f9dc4a9a449ba1b1b5d07087"
APP_DIR = "Docs/roadmap/fixtures/contracts/project-log"

V12 = {"X-Truebex-Contract": "project-log/1.2"}
WALL = "dc643577cfb582fabd0d7f9edef6b30d"
STOREY = "bc89d041bf8f8b1f8180f89b34234495"
WALL_PIN = {"entity": WALL, "point_mm": None, "view": None}
VIEW_PIN = {"entity": None, "point_mm": None, "view": {"storey": STOREY, "eye_mm": [4200, 1800, 1600], "yaw_deg": 90, "pitch_deg": -10}}
COMMENT_KEYS = [
    "comment_id", "parent_id", "author", "created_at", "edited_at", "text", "state", "resolved_by", "resolved_at", "anchor",
]
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
_ABSENT = object()


@pytest.fixture(autouse=True)
def _clean_project_state():
    presence.reset()
    waiters.reset()
    yield
    presence.reset()
    waiters.reset()


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _is_hex32(value) -> bool:
    return isinstance(value, str) and len(value) == 32 and all(c in "0123456789abcdef" for c in value)


def _name(user_id: int, name: str) -> None:
    with SessionLocal() as db:
        db.execute(update(User).where(User.id == user_id).values(name=name))
        db.commit()


def _team(client):
    """A Pro owner, an editor and a viewer on one project, and a stranger."""
    owner = Person(client, "owner@example.com")
    editor = Person(client, "editor@example.com")
    viewer = Person(client, "viewer@example.com")
    stranger = Person(client, "stranger@example.com")
    pid = create(client, owner.dev, "House", doc_version=55)["project_id"]
    invite_and_accept(client, owner, pid, editor, "editor")
    invite_and_accept(client, owner, pid, viewer, "viewer")
    return owner, editor, viewer, stranger, pid


def post(client, headers: dict, pid: str, text_: str = "Look here", *, anchor=_ABSENT, parent_id=_ABSENT, base: str = "/projects"):
    body: dict = {"text": text_}
    if anchor is not _ABSENT:
        body["anchor"] = anchor
    if parent_id is not _ABSENT:
        body["parent_id"] = parent_id
    return client.post(f"{base}/{pid}/comments", json=body, headers=headers)


def created(client, headers: dict, pid: str, text_: str = "Look here", **kw) -> dict:
    if "parent_id" not in kw and "anchor" not in kw:
        kw["anchor"] = WALL_PIN
    res = post(client, headers, pid, text_, **kw)
    assert res.status_code == 201, res.text
    assert res.headers["X-Truebex-Contract"] == "project-log/1.2"
    body = res.json()
    assert list(body) == COMMENT_KEYS
    return body


def patch(client, headers: dict, pid: str, cid: str, body: dict, base: str = "/projects"):
    return client.patch(f"{base}/{pid}/comments/{cid}", json=body, headers=headers)


def patched(client, headers: dict, pid: str, cid: str, body: dict) -> dict:
    res = patch(client, headers, pid, cid, body)
    assert res.status_code == 200, res.text
    assert list(res.json()) == COMMENT_KEYS
    return res.json()


def delete(client, headers: dict, pid: str, cid: str, base: str = "/projects"):
    return client.delete(f"{base}/{pid}/comments/{cid}", headers=headers)


def fetch(client, headers: dict, pid: str, after_rev: int = 0, state: str | None = None) -> dict:
    params: dict = {"after_rev": after_rev}
    if state is not None:
        params["state"] = state
    res = client.get(f"/projects/{pid}/comments", params=params, headers=headers)
    assert res.status_code == 200, res.text
    assert res.headers["X-Truebex-Contract"] == "project-log/1.2"
    body = res.json()
    assert set(body) == {"comments", "rev"}
    return body


def heartbeat(client, person: Person, pid: str) -> dict:
    res = client.put(f"/projects/{pid}/presence", json={"replica_id": person.replica, "client": "desktop"}, headers=person.dev)
    assert res.status_code == 200, res.text
    return res.json()


def comments_rev(client, person: Person, pid: str) -> int:
    """5.17's and 5.18's comments_rev (they agree)."""
    beat = heartbeat(client, person, pid)
    listed = client.get(f"/projects/{pid}/presence", headers=person.web).json()
    assert beat["comments_rev"] == listed["comments_rev"]
    return beat["comments_rev"]


def stored_revs(pid: str) -> list[int]:
    from app.projects.models import ProjectComment

    with SessionLocal() as db:
        return sorted(db.scalars(select(ProjectComment.rev).where(ProjectComment.project_id == pid)))


# --- the folder is the app's eight files --------------------------------------------------------------


def test_pf4b_fixture_folder_is_the_apps_eight_files():
    """CL2 added comments.json; the other seven are CL1's, unchanged."""
    assert APP_BLOBS["comments.json"] == COMMENTS_BLOB and len(APP_BLOBS) == 8
    files = {p.name for p in FIXTURES.iterdir() if p.is_file()}
    assert files == set(APP_BLOBS) | {"README.md"}
    data = (FIXTURES / "comments.json").read_bytes()
    assert git_blob_id(data) == COMMENTS_BLOB and b"\r" not in data
    readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
    assert CL2_COMMIT[:9] in readme and CL2_COPIED_FROM[:9] in readme and "1.2.0" in readme and "comments.json" in readme
    body = fixture("comments.json")
    assert body["schema"] == "truebex-project-log-comments/1" and len(body["comments"]) == 1
    assert list(body["comments"][0]) == COMMENT_KEYS
    # The comment pins the wall presence.json's Sam is editing.
    assert body["comments"][0]["anchor"]["entity"] == fixture("presence.json")["present"][0]["editing"][0] == WALL
    import shutil
    import subprocess

    git = shutil.which("git")
    if git is None or not (APP_REPO / ".git").exists():
        return
    for commit in (CL2_COMMIT, CL2_COPIED_FROM):
        tree = subprocess.run(
            [git, "-C", str(APP_REPO), "ls-tree", commit, "--", APP_DIR + "/"], capture_output=True, text=True, timeout=60
        )
        if tree.returncode != 0:  # the commit is not in this clone
            continue
        listed = {line.split("\t", 1)[1].rsplit("/", 1)[1]: line.split()[2] for line in tree.stdout.splitlines()}
        assert listed == APP_BLOBS, commit


# --- contract §10: test_comments_roles, test_presence_comments_rev ----------------------------------------


def test_comments_roles(client):
    owner, editor, viewer, stranger, pid = _team(client)

    # A viewer comments and replies: a review role needs it.
    mine = created(client, viewer.dev, pid, "Is this wall load-bearing?")
    assert mine["author"] == {"user_id": viewer.user_id, "name": "viewer"} and mine["state"] == "open"
    reply = created(client, viewer.dev, pid, "And the one beside it?", parent_id=mine["comment_id"])
    assert reply["parent_id"] == mine["comment_id"]
    theirs = created(client, editor.dev, pid, "I moved this 500 mm", anchor=VIEW_PIN)

    # Text: the author only; another editor and the owner get 403.
    edited = patched(client, viewer.dev, pid, mine["comment_id"], {"text": "  Is this wall load-bearing at all?  "})
    assert edited["text"] == "Is this wall load-bearing at all?" and RFC3339_Z.match(edited["edited_at"])
    for who in (editor, owner):
        body = error_of(patch(client, who.dev, pid, mine["comment_id"], {"text": "Mine now"}), 403, "forbidden")
        assert body["data"]["needed"] == "author"
    # State: the author, an editor or the owner; a viewer resolves only their own.
    done = patched(client, editor.web, pid, mine["comment_id"], {"state": "resolved"})
    assert done["state"] == "resolved" and done["resolved_by"] == editor.user_id and RFC3339_Z.match(done["resolved_at"])
    again = patched(client, owner.dev, pid, mine["comment_id"], {"state": "open"})
    assert again["state"] == "open" and again["resolved_by"] is None and again["resolved_at"] is None
    assert patched(client, viewer.dev, pid, mine["comment_id"], {"state": "resolved"})["resolved_by"] == viewer.user_id
    body = error_of(patch(client, viewer.dev, pid, theirs["comment_id"], {"state": "resolved"}), 403, "forbidden")
    assert body["data"]["role"] == "viewer"
    assert patched(client, editor.dev, pid, theirs["comment_id"], {"state": "resolved"})["resolved_by"] == editor.user_id
    assert patched(client, owner.dev, pid, theirs["comment_id"], {"state": "open"})["state"] == "open"
    # Text and state at once, by the author; upper-case ids are the same ids (§6.1).
    both = patched(client, viewer.dev, pid, mine["comment_id"].upper(), {"text": "Settled.", "state": "resolved"})
    assert both["text"] == "Settled." and both["state"] == "resolved" and both["comment_id"] == mine["comment_id"]

    # Delete: the author or the owner.
    error_of(delete(client, editor.dev, pid, mine["comment_id"]), 403, "forbidden")
    error_of(delete(client, viewer.dev, pid, theirs["comment_id"]), 403, "forbidden")
    assert delete(client, viewer.dev, pid, reply["comment_id"]).status_code == 204  # the author
    res = delete(client, owner.dev, pid, theirs["comment_id"])  # the owner, someone else's
    assert res.status_code == 204

    # 404 for a deleted or unknown comment.
    for cid in (reply["comment_id"], theirs["comment_id"], hex32(), "not-a-comment"):
        error_of(patch(client, viewer.dev, pid, cid, {"text": "Hello?"}), 404, "not_found")
        error_of(patch(client, owner.dev, pid, cid, {"state": "open"}), 404, "not_found")
        error_of(delete(client, owner.dev, pid, cid), 404, "not_found")

    # 422: empty text, 4001 characters, no anchor, an unknown or deleted parent.
    for bad in ("", "   \n\t", "x" * 4001):
        body = error_of(post(client, viewer.dev, pid, bad, anchor=WALL_PIN), 422, "validation_failed")
        assert body["data"]["fields"][0]["field"] == "text"
    assert created(client, viewer.dev, pid, " " + "x" * 4000 + "\n")["text"] == "x" * 4000  # trimmed, then 1-4000
    for anchor in (_ABSENT, None, {}, {"entity": None, "point_mm": [1, 2, 3], "view": None}):
        body = error_of(post(client, viewer.dev, pid, "Where?", anchor=anchor), 422, "validation_failed")
        assert body["data"]["fields"][0]["field"] == "anchor"
    for parent in (hex32(), reply["comment_id"], theirs["comment_id"], "not-a-comment"):
        body = error_of(post(client, viewer.dev, pid, "Re", parent_id=parent), 422, "validation_failed")
        assert body["data"]["fields"][0]["field"] == "parent_id"
    for body_ in ({"text": ""}, {"text": "y" * 4001}, {"state": "deleted"}, {"state": "closed"}, {}):
        error_of(patch(client, viewer.dev, pid, mine["comment_id"], body_), 422, "validation_failed")

    # A non-member gets the project's usual answer: 404, as for every project route.
    for res in (
        client.get(f"/projects/{pid}/comments", headers=stranger.dev),
        post(client, stranger.dev, pid, "Hi", anchor=WALL_PIN),
        patch(client, stranger.dev, pid, mine["comment_id"], {"state": "open"}),
        delete(client, stranger.dev, pid, mine["comment_id"]),
    ):
        error_of(res, 404, "not_found")
    error_of(client.get(f"/projects/{pid}/comments", headers=CONTRACT), 401, "unauthenticated")
    error_of(post(client, CONTRACT, pid, "Hi", anchor=WALL_PIN), 401, "unauthenticated")


def test_presence_comments_rev(client):
    owner, editor, viewer, _stranger, pid = _team(client)

    # 0 before any comment; nothing else in 5.17 and 5.18 changes.
    assert comments_rev(client, viewer, pid) == 0
    assert set(heartbeat(client, editor, pid)) == {"ttl_s", "others", "comments_rev"}
    assert set(client.get(f"/projects/{pid}/presence", headers=owner.dev).json()) == {"present", "comments_rev"}
    assert fetch(client, owner.dev, pid) == {"comments": [], "rev": 0}

    root = created(client, editor.dev, pid, "Kitchen still fits?")
    assert comments_rev(client, viewer, pid) == 1
    assert fetch(client, owner.dev, pid, 0) == {"comments": [root], "rev": 1}
    reply = created(client, viewer.dev, pid, "Only just.", parent_id=root["comment_id"])
    assert comments_rev(client, owner, pid) == 2
    assert fetch(client, owner.dev, pid, 1) == {"comments": [reply], "rev": 2}
    edited = patched(client, editor.dev, pid, root["comment_id"], {"text": "Does the kitchen still fit?"})
    assert comments_rev(client, viewer, pid) == 3
    assert fetch(client, viewer.dev, pid, 2) == {"comments": [edited], "rev": 3}
    resolved = patched(client, owner.dev, pid, root["comment_id"], {"state": "resolved"})
    assert comments_rev(client, viewer, pid) == 4
    assert fetch(client, viewer.dev, pid, 3) == {"comments": [resolved], "rev": 4}
    reopened = patched(client, editor.dev, pid, root["comment_id"], {"state": "open"})
    assert comments_rev(client, viewer, pid) == 5
    assert fetch(client, viewer.dev, pid, 4) == {"comments": [reopened], "rev": 5}
    assert delete(client, viewer.dev, pid, reply["comment_id"]).status_code == 204
    assert comments_rev(client, owner, pid) == 6

    # A deleted comment comes back once, as a tombstone: state deleted, empty text.
    tomb = {**reply, "text": "", "state": "deleted"}
    assert fetch(client, owner.dev, pid, 5) == {"comments": [tomb], "rev": 6}
    # From 0: every comment once, in its latest state, oldest change first.
    assert fetch(client, owner.dev, pid, 0) == {"comments": [reopened, tomb], "rev": 6}
    for after in (1, 2, 3, 4):
        assert fetch(client, owner.dev, pid, after)["comments"] == [reopened, tomb]
    # Never again after its rev.
    assert fetch(client, owner.dev, pid, 6) == {"comments": [], "rev": 6}
    assert fetch(client, owner.dev, pid, 60) == {"comments": [], "rev": 6}
    # A state filter never hides a tombstone (the app's stub): state=open still returns it.
    assert fetch(client, owner.dev, pid, 0, "open") == {"comments": [reopened, tomb], "rev": 6}
    assert fetch(client, owner.dev, pid, 0, "resolved") == {"comments": [tomb], "rev": 6}
    again = patched(client, editor.dev, pid, root["comment_id"], {"state": "resolved"})
    assert comments_rev(client, editor, pid) == 7
    assert fetch(client, owner.dev, pid, 0, "open") == {"comments": [tomb], "rev": 7}
    assert fetch(client, owner.dev, pid, 0, "resolved") == {"comments": [tomb, again], "rev": 7}
    assert fetch(client, owner.dev, pid, 0, "all") == fetch(client, owner.dev, pid, 0) == {"comments": [tomb, again], "rev": 7}
    assert fetch(client, owner.dev, pid, 6, "open") == {"comments": [], "rev": 7}
    assert stored_revs(pid) == [6, 7]  # each comment holds its last change's rev

    # The tombstone's text is gone from the database too, not only from the answer.
    from app.projects.models import ProjectComment

    with SessionLocal() as db:
        row = db.get(ProjectComment, reply["comment_id"])
        assert row.state == "deleted" and row.text == ""

    # Comments are platform data: the log never sees them.
    log = pull(client, owner.dev, pid)
    assert log["ops"] == [] and log["head_seq"] == 0
    # 5.19's own validation.
    for params in ({"state": "deleted"}, {"state": "bogus"}, {"after_rev": -1}, {"after_rev": "x"}):
        error_of(client.get(f"/projects/{pid}/comments", params=params, headers=owner.dev), 422, "validation_failed")


# --- the app's comments.json -----------------------------------------------------------------------------


def test_pf4b_apps_comment_round_trips(client):
    """Sam (the editor, user 7) pins comments.json's comment on the fixture
    project; 5.20 and 5.19 answer it with the file's keys and values. Masked:
    `comment_id` and `created_at`, which the server mints."""
    want = fixture("comments.json")["comments"][0]
    project = fixture("project.json")
    ana = Person(client, "ana@example.com")
    for n in range(2, want["author"]["user_id"]):  # Sam is user 7, as in members.json
        signup(client, f"filler{n}@example.com")
    sam = Person(client, "sam@example.com")
    assert sam.user_id == want["author"]["user_id"] == 7
    _name(ana.user_id, "Ana Owner")
    _name(sam.user_id, want["author"]["name"])
    pid = create(client, ana.dev, project["name"], doc_version=project["doc_version"])["project_id"]
    invite_and_accept(client, ana, pid, sam, "editor")

    res = client.post(
        f"/projects/{pid}/comments",
        json={"parent_id": want["parent_id"], "text": want["text"], "anchor": want["anchor"]},
        headers={**sam.dev, "Idempotency-Key": hex32()},
    )
    assert res.status_code == 201, res.text
    answer = fetch(client, ana.dev, pid, 0)
    assert answer["rev"] == 1 and len(answer["comments"]) == 1
    got = answer["comments"][0]
    assert list(got) == list(want)  # §6.6 field for field, in the app's order
    minted = ("comment_id", "created_at")
    assert {k: v for k, v in got.items() if k not in minted} == {k: v for k, v in want.items() if k not in minted}
    assert _is_hex32(got["comment_id"]) and RFC3339_Z.match(got["created_at"])
    assert res.json() == got
    # The raw JSON keeps the app's numbers and nulls as sent.
    assert json.loads(client.get(f"/projects/{pid}/comments", headers=sam.dev).text)["comments"][0]["anchor"] == want["anchor"]


def test_pf4b_reply_takes_its_parents_anchor_and_hangs_under_the_root(client):
    owner, editor, viewer, _stranger, pid = _team(client)
    root = created(client, owner.dev, pid, "This view: the hall feels narrow.", anchor=VIEW_PIN)
    assert root["anchor"] == VIEW_PIN and root["parent_id"] is None
    # A reply's own anchor is ignored (the app sends its local copy): it takes the parent's.
    reply = created(client, viewer.dev, pid, "Agreed.", parent_id=root["comment_id"], anchor=WALL_PIN)
    assert reply["parent_id"] == root["comment_id"] and reply["anchor"] == root["anchor"]
    # A reply to a reply hangs under the root.
    deeper = created(client, editor.dev, pid, "Widened it.", parent_id=reply["comment_id"].upper(), anchor={"entity": "nope"})
    assert deeper["parent_id"] == root["comment_id"] and deeper["anchor"] == VIEW_PIN
    assert [c["comment_id"] for c in fetch(client, owner.dev, pid)["comments"]] == [
        root["comment_id"], reply["comment_id"], deeper["comment_id"]
    ]
    # A reply under a resolved thread starts open; resolving one reply leaves the root alone.
    patched(client, owner.dev, pid, root["comment_id"], {"state": "resolved"})
    late = created(client, viewer.dev, pid, "One more thing.", parent_id=root["comment_id"])
    assert late["state"] == "open" and late["resolved_by"] is None and late["edited_at"] is None
    # An entity pin with a point; a view pin with no storey (outside any storey).
    point = created(client, editor.dev, pid, "This corner.", anchor={"entity": WALL.upper(), "point_mm": [10, 20.5, 0]})
    assert point["anchor"] == {"entity": WALL, "point_mm": [10, 20.5, 0], "view": None}
    outside = {"storey": None, "eye_mm": [0, -5000, 1600], "yaw_deg": 90, "pitch_deg": 0}
    assert created(client, editor.dev, pid, "From the street.", anchor={"view": outside})["anchor"] == {
        "entity": None, "point_mm": None, "view": outside
    }
    # Malformed anchors name their field.
    for anchor, field in (
        ({"entity": "wall#" + WALL}, "anchor.entity"),
        ({"entity": WALL, "point_mm": [1, 2]}, "anchor.point_mm"),
        ({"entity": WALL, "point_mm": [1, 2, "3"]}, "anchor.point_mm"),
        ({"entity": WALL, "point_mm": [1, True, 3]}, "anchor.point_mm"),
        ({"view": {"storey": STOREY}}, "anchor.view.eye_mm"),
        ({"view": {"storey": "x", "eye_mm": [1, 2, 3]}}, "anchor.view.storey"),
        ({"view": {"eye_mm": [1, 2, 3], "yaw_deg": "north"}}, "anchor.view.yaw_deg"),
        ({"view": "front"}, "anchor.view"),
        ("wall", "anchor"),
    ):
        body = error_of(post(client, editor.dev, pid, "Here", anchor=anchor), 422, "validation_failed")
        assert body["data"]["fields"][0]["field"] == field, (anchor, body)
    # A number JSON cannot hold as a finite float (1e999 reads as infinity).
    raw = '{"text": "Here", "anchor": {"view": {"eye_mm": [1, 2, 3], "pitch_deg": 1e999}}}'
    res = client.post(f"/projects/{pid}/comments", content=raw, headers={**editor.dev, "Content-Type": "application/json"})
    assert error_of(res, 422, "validation_failed")["data"]["fields"][0]["field"] == "anchor.view.pitch_deg"


def test_pf4b_comment_idempotency_key(client):
    owner, _editor, viewer, _stranger, pid = _team(client)
    key = hex32()
    headers = {**viewer.dev, "Idempotency-Key": key}
    first = post(client, headers, pid, "Pinned once", anchor=WALL_PIN)
    assert first.status_code == 201, first.text
    again = post(client, headers, pid, "Pinned once", anchor=WALL_PIN)
    assert again.status_code == 201 and again.json() == first.json()
    assert again.headers["X-Truebex-Contract"] == "project-log/1.2"
    assert comments_rev(client, owner, pid) == 1  # the rev moved once
    assert len(fetch(client, owner.dev, pid)["comments"]) == 1
    # The same key with another body: 409; nothing stored, the rev unmoved.
    error_of(post(client, headers, pid, "Pinned twice", anchor=WALL_PIN), 409, "idempotency_mismatch")
    assert comments_rev(client, owner, pid) == 1
    # Another key is another comment.
    other = post(client, {**viewer.dev, "Idempotency-Key": hex32()}, pid, "Pinned once", anchor=WALL_PIN)
    assert other.status_code == 201 and other.json()["comment_id"] != first.json()["comment_id"]
    assert comments_rev(client, owner, pid) == 2
    error_of(post(client, {**viewer.dev, "Idempotency-Key": "short"}, pid, "x", anchor=WALL_PIN), 422, "validation_failed")
    # A refused create keeps no key: the same key with a fixed body goes through.
    retry = hex32()
    error_of(post(client, {**viewer.dev, "Idempotency-Key": retry}, pid, "", anchor=WALL_PIN), 422, "validation_failed")
    assert post(client, {**viewer.dev, "Idempotency-Key": retry}, pid, "Fixed", anchor=WALL_PIN).status_code == 201
    assert comments_rev(client, owner, pid) == 3


def test_pf4b_comment_plan_gate(client):
    """5.20 from the app (a device) checks the caller's plan for collab.live, as
    a push checks cloud.sync; a light client's session and 5.17 / 5.18, 5.19,
    5.21 and 5.22 are not gated."""
    owner = Person(client, "owner@example.com")
    free = Person(client, "free@example.com", trial=False)
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, free, "viewer")
    body = error_of(post(client, free.dev, pid, "Can I comment?", anchor=WALL_PIN), 403, "plan_required")
    assert body["data"] == {"feature": "collab.live", "plan": "free"}
    assert "comment" in body["detail"].lower() and "cloud project" not in body["detail"].lower()
    assert comments_rev(client, free, pid) == 0  # 5.17 / 5.18 ungated; nothing stored
    assert fetch(client, free.dev, pid) == {"comments": [], "rev": 0}
    # The website and the phone (a session) comment with the role checks only (§4).
    mine = created(client, free.web, pid, "From the browser")
    assert patched(client, free.dev, pid, mine["comment_id"], {"text": "Edited in the app"})["text"] == "Edited in the app"
    assert patched(client, free.dev, pid, mine["comment_id"], {"state": "resolved"})["state"] == "resolved"
    assert delete(client, free.dev, pid, mine["comment_id"]).status_code == 204
    assert created(client, owner.dev, pid, "Paid device")["author"]["user_id"] == owner.user_id
    assert comments_rev(client, free, pid) == 5


def test_pf4b_comments_outlive_a_member_not_the_project(client):
    from app.projects import jobs
    from app.projects.models import Project, ProjectComment

    owner, _editor, viewer, _stranger, pid = _team(client)
    _name(viewer.user_id, "Vera Viewer")
    mine = created(client, viewer.dev, pid, "Before I go")
    # A member who leaves keeps their comments, shown with their name.
    assert client.delete(f"/projects/{pid}/members/{viewer.user_id}", headers=viewer.web).status_code == 204
    [kept] = fetch(client, owner.dev, pid)["comments"]
    assert kept["comment_id"] == mine["comment_id"] and kept["author"] == {"user_id": viewer.user_id, "name": "Vera Viewer"}
    error_of(client.get(f"/projects/{pid}/comments", headers=viewer.dev), 404, "not_found")
    # The owner still resolves and deletes it.
    assert patched(client, owner.dev, pid, mine["comment_id"], {"state": "resolved"})["resolved_by"] == owner.user_id
    created(client, owner.dev, pid, "Still here")
    # A deleted project is gone at once and takes its comments with it.
    assert client.delete(f"/projects/{pid}", headers=owner.web).status_code == 204
    error_of(client.get(f"/projects/{pid}/comments", headers=owner.dev), 404, "not_found")
    error_of(post(client, owner.dev, pid, "Hello?", anchor=WALL_PIN), 404, "not_found")
    with SessionLocal() as db:
        jobs.purge_project(db, db.get(Project, pid))
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ProjectComment).where(ProjectComment.project_id == pid)) == 0


def test_pf4b_comments_rev_from_before_pf4b(client, tmp_path):
    """A project from before PF4b (comments_rev NULL) reads 0 and its first
    comment gets 1; init_db adds the column to an existing projects table."""
    from sqlalchemy import create_engine, inspect

    from app.database import _ADDED_COLUMNS, Base, _migrate
    from app.projects.models import Project

    owner, _editor, viewer, _stranger, pid = _team(client)
    with SessionLocal() as db:
        db.execute(update(Project).where(Project.project_id == pid).values(comments_rev=None))
        db.commit()
    assert comments_rev(client, viewer, pid) == 0
    assert fetch(client, owner.dev, pid) == {"comments": [], "rev": 0}
    created(client, viewer.dev, pid)
    assert comments_rev(client, viewer, pid) == 1

    assert ("comments_rev", "BIGINT") in _ADDED_COLUMNS["projects"]
    engine = create_engine(f"sqlite:///{tmp_path / 'before.db'}")
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE projects DROP COLUMN comments_rev"))
        assert "comments_rev" not in {c["name"] for c in inspect(engine).get_columns("projects")}
        _migrate(engine)
        assert "comments_rev" in {c["name"] for c in inspect(engine).get_columns("projects")}
    finally:
        engine.dispose()


# --- every change one revision, under concurrent writers --------------------------------------------------


def test_pf4b_concurrent_comments_get_contiguous_revs(client):
    owner, editor, viewer, _stranger, pid = _team(client)
    people = [owner, editor, viewer] * 3

    def writer(person: Person) -> list[str]:
        made = []
        for n in range(3):
            res = post(client, person.dev, pid, f"note {n}", anchor=WALL_PIN)
            assert res.status_code == 201, res.text
            made.append(res.json()["comment_id"])
        return made

    with ThreadPoolExecutor(max_workers=9) as pool:
        ids = [cid for made in pool.map(writer, people) for cid in made]
    assert len(set(ids)) == 27
    assert stored_revs(pid) == list(range(1, 28))  # 9 writers x 3 comments, no gap, none twice
    assert comments_rev(client, owner, pid) == 27
    assert len(fetch(client, owner.dev, pid)["comments"]) == 27


@pytest.mark.postgres
def test_pf4b_concurrent_comments_postgres():
    """On Postgres (TEST_DATABASE_URL): writers that start together on one
    project get consecutive revisions, never the same or a skipped one; the
    project row's lock orders them as it orders a push."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import init_db
    from app.projects import comments
    from app.projects.models import Project, ProjectComment, ProjectMember

    from .conftest import TEST_DATABASE_URL

    engine = create_engine(TEST_DATABASE_URL, pool_size=10, max_overflow=0)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    init_db(bind=engine)
    make = sessionmaker(bind=engine)
    with make() as db:
        user = User(email="pg@example.com", hashed_password="x")
        db.add(user)
        db.flush()
        project = Project(
            project_id=hex32(), name="PG", owner_user_id=user.id, doc_version=55, head_seq=0, bytes=0,
            server_replica_id=hex32(),
        )
        db.add(project)
        db.flush()
        db.add(ProjectMember(project_id=project.project_id, user_id=user.id, email=user.email, role="owner", state="active"))
        db.commit()
        pid, uid = project.project_id, user.id
    writers = 8
    start = threading.Barrier(writers)

    def writer(n: int) -> list[str]:
        made = []
        start.wait()
        for i in range(4):
            with make() as db:
                body = comments.CommentIn(text=f"writer {n} note {i}", anchor=WALL_PIN)
                made.append(comments.create(db, db.get(Project, pid), db.get(User, uid), body)["comment_id"])
        return made

    try:
        with ThreadPoolExecutor(max_workers=writers) as pool:
            made = [cid for ids in pool.map(writer, range(writers)) for cid in ids]
        total = writers * 4
        with make() as db:
            assert len(set(made)) == total
            assert sorted(db.scalars(select(ProjectComment.rev).where(ProjectComment.project_id == pid))) == list(range(1, total + 1))
            first = made[0]
            first_rev = db.get(ProjectComment, first).rev
        # Two at once, then: both 5.21s on one comment queue on the same lock.
        start2 = threading.Barrier(2)

        def resolver(state: str) -> dict:
            start2.wait()
            with make() as db:
                project = db.get(Project, pid)
                member = db.scalar(select(ProjectMember).where(ProjectMember.project_id == pid))
                return comments.update_comment(db, project, member, first, comments.CommentPatchIn(state=state))

        with ThreadPoolExecutor(max_workers=2) as pool:
            answers = list(pool.map(resolver, ["resolved", "open"]))
        assert {a["state"] for a in answers} == {"resolved", "open"}
        with make() as db:
            revs = sorted(db.scalars(select(ProjectComment.rev).where(ProjectComment.project_id == pid)))
            # The two 5.21s took total + 1 and total + 2; the comment's row holds the later one.
            assert revs == sorted((set(range(1, total + 1)) - {first_rev}) | {total + 2})
            assert db.scalar(select(Project.comments_rev).where(Project.project_id == pid)) == total + 2
            assert comments.current_rev(db, pid) == total + 2
    finally:
        engine.dispose()


# --- project-log/1.2 on the wire; /v1 and the API documents -------------------------------------------------


def test_pf4b_routes_speak_project_log_1_2(client):
    owner = Person(client, "ana@example.com")
    res = client.post("/projects", json={"name": "House", "doc_version": 55}, headers=owner.dev)
    assert res.status_code == 201 and res.headers["X-Truebex-Contract"] == "project-log/1.2"
    pid = res.json()["project_id"]
    key = make_key(client, owner.session, ["projects:read"])
    plain = {"Authorization": f"Bearer {owner.token}"}
    routes = [
        (f"/projects/{pid}", plain),
        (f"/projects/{pid}/comments", plain),
        (f"/projects/{pid}/presence", plain),
        (f"/projects/{pid}/members", plain),
        (f"/projects/{pid}/panoramas", plain),  # PF9's route under the same contract
        (f"/v1/projects/{pid}", kh(key)),
        (f"/v1/projects/{pid}/comments", kh(key)),
        (f"/v1/projects/{pid}/presence", kh(key)),
    ]
    for path, auth in routes:
        # The app's 1.2, a 1.1 and a 1.0 client, a later MINOR and no header: 200, 1.2 echoed.
        for sent in ({}, V12, {"X-Truebex-Contract": "project-log/1.1"}, {"X-Truebex-Contract": "project-log/1.0"},
                     {"X-Truebex-Contract": "project-log/1.9"}):
            got = client.get(path, headers={**auth, **sent})
            assert got.status_code == 200, (path, sent, got.text)
            assert got.headers["X-Truebex-Contract"] == "project-log/1.2", path
        body = error_of(client.get(path, headers={**auth, "X-Truebex-Contract": "project-log/2.0"}), 400, "contract_version")
        assert body["data"]["supported"] == ["project-log/1.2"]
    # A 1.1 client comments too (the routes are additive).
    old = {"Authorization": f"Bearer {owner.token}", "X-Truebex-Contract": "project-log/1.1"}
    assert post(client, old, pid, "From a 1.1 client", anchor=WALL_PIN).status_code == 201


def test_pf4b_v1_comments_mirror(client):
    owner = Person(client, "owner@example.com")
    viewer = Person(client, "viewer@example.com", trial=False)
    outsider = Person(client, "outsider@example.com")
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, viewer, "viewer")
    read = make_key(client, viewer.session, ["projects:read"])
    write = make_key(client, viewer.session, ["projects:read", "projects:write"])
    base = "/v1/projects"

    body = error_of(post(client, kh(read, **V12), pid, "Via a key", anchor=WALL_PIN, base=base), 403, "forbidden")
    assert body["data"]["needed"] == "projects:write"
    res = post(client, kh(write, **V12, **{"Idempotency-Key": hex32()}), pid, "Via a key", anchor=WALL_PIN, base=base)
    assert res.status_code == 201, res.text
    made = res.json()
    assert list(made) == COMMENT_KEYS and made["author"]["user_id"] == viewer.user_id  # the key's owner
    assert "x-ratelimit-remaining" in res.headers and res.headers["X-Truebex-Contract"] == "project-log/1.2"
    listed = client.get(f"{base}/{pid}/comments", params={"after_rev": 0, "state": "open"}, headers=kh(read))
    assert listed.status_code == 200 and listed.json() == {"comments": [made], "rev": 1}
    error_of(patch(client, kh(read), pid, made["comment_id"], {"state": "resolved"}, base=base), 403, "forbidden")
    res = patch(client, kh(write), pid, made["comment_id"], {"text": "Edited through the API"}, base=base)
    assert res.status_code == 200 and res.json()["text"] == "Edited through the API"
    assert delete(client, kh(write), pid, made["comment_id"], base=base).status_code == 204
    beat = client.put(f"{base}/{pid}/presence", json={"replica_id": hex32(), "client": "web"}, headers=kh(write))
    assert beat.status_code == 200 and beat.json()["comments_rev"] == 3
    assert client.get(f"{base}/{pid}/presence", headers=kh(read)).json()["comments_rev"] == 3
    stranger = make_key(client, outsider.session, ["projects:read", "projects:write"])
    error_of(client.get(f"{base}/{pid}/comments", headers=kh(stranger)), 404, "not_found")
    error_of(client.get(f"{base}/{pid}/comments", params={"state": "deleted"}, headers=kh(read)), 422, "validation_failed")


def test_pf4b_api_documents_name_1_2_and_comments():
    """openapi/v1.json (and the SDKs from it) carry 5.19-5.22 and 1.2;
    5.17 / 5.18's answers document comments_rev in both documents."""
    v1 = json.loads((ROOT / "openapi" / "v1.json").read_text(encoding="utf-8"))
    clients = json.loads((ROOT / "openapi" / "clients.json").read_text(encoding="utf-8"))
    assert v1["info"]["version"] == "1.1.0"  # the document grew: MINOR
    want = [
        ("/v1/projects/{project_id}/comments", "get", "projects_list_comments", "projects:read"),
        ("/v1/projects/{project_id}/comments", "post", "projects_create_comment", "projects:write"),
        ("/v1/projects/{project_id}/comments/{comment_id}", "patch", "projects_update_comment", "projects:write"),
        ("/v1/projects/{project_id}/comments/{comment_id}", "delete", "projects_delete_comment", "projects:write"),
    ]
    for path, method, op_id, scope in want:
        op = v1["paths"][path][method]
        assert op["operationId"] == op_id and op["x-truebex-scope"] == scope
        assert op["x-truebex-contract"] == "project-log/1.2"
    query = {p["name"]: p for p in v1["paths"]["/v1/projects/{project_id}/comments"]["get"]["parameters"] if p["in"] == "query"}
    assert set(query) == {"after_rev", "state"} and set(query["state"]["schema"]["enum"]) == {"open", "resolved", "all"}
    schemas = v1["components"]["schemas"]
    assert set(schemas["Comment"]["properties"]) == set(COMMENT_KEYS)  # the export sorts keys
    assert set(schemas["Comment"]["properties"]["state"]["enum"]) == {"open", "resolved", "deleted"}
    assert set(schemas["CommentList"]["properties"]) == {"comments", "rev"}
    for doc, answers in ((v1, ("HeartbeatResult", "PresenceList")), (clients, ("PresenceAnswer", "PresenceList"))):
        for name in answers:
            assert "comments_rev" in doc["components"]["schemas"][name]["properties"], name
    for path, ops in v1["paths"].items():
        for method, op in ops.items():
            if str(op.get("x-truebex-contract", "")).startswith("project-log/"):
                assert op["x-truebex-contract"] == "project-log/1.2", (path, method)
    ops_py = (ROOT / "sdks" / "python" / "truebex" / "_operations.py").read_text(encoding="utf-8")
    for _, _, op_id, _ in want:
        assert f"'{op_id}': {{" in ops_py, op_id
    assert "'query': ['after_rev', 'state']" in ops_py.split("'projects_list_comments'")[1].split("\n")[0]
    ts = (ROOT / "sdks" / "js" / "src" / "schema.d.ts").read_text(encoding="utf-8")
    assert "projects_create_comment: {" in ts and "comments_rev: number" in ts
    for rel in ("sdks/js/package.json", "sdks/python/pyproject.toml", "sdks/python/truebex/_version.py"):
        assert "1.1.0" in (ROOT / rel).read_text(encoding="utf-8"), rel
    assert "comments_rev" in (ROOT / "src" / "lib" / "api-clients.d.ts").read_text(encoding="utf-8")
    assert "commentsRev" in (ROOT / "mobile" / "android" / "lib" / "api" / "gen" / "model" / "presence_answer.dart").read_text(
        encoding="utf-8"
    )
