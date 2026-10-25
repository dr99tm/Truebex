"""PF14f: the platform reads the enum values the app writes from FNames without case.

A packaged (Shipping or Game) Unreal 5.7 build does not keep an FName's case
(Engine/Source/Runtime/Core/Public/UObject/NameTypes.h: WITH_CASE_PRESERVING_NAME
is WITH_EDITORONLY_DATA), so `FName(TEXT("high")).ToString()` answers whichever
spelling the global name table registered first: "High", "Editor" and "Team"
are the engine's own (UnrealNames.inl), "Resolved", "Delta" and "Action" are
reflected engine members. The app's suites run with editor binaries and never
see it. The app (main bc06615c6) writes these from FNames:

* render-jobs 5.1 `kind` and `quality` (RenderJobsClient.cpp:152, :161) and
  5.3's `kind` and `state` filters (:233, :234; CloudPano.cpp:519-525 lists a
  followed set's queued and running tiles jobs to cancel them on Unfollow);
* project-log 5.6 an operation's `author_kind` and `kind` (CadProjectLog.cpp:100, :103);
* project-log 5.21 a comment's `state` (SyncCollab.cpp:1242);
* project-log 5.14 and 5.15 a member's `role` (SyncClient.cpp:332, :341);
* licence-api 5.13 the release feed's `channel` (TruebexUpdater.cpp:533).

The platform matches each without case (ASCII) and stores and answers the
contract's lower-case spelling (app.enums.canonical); anything else answers
422 as before, naming the canonical spellings. Telemetry (PF14d) and the
analysis kinds (PF11c) already did so.
"""

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.projects import presence, waiters
from app.projects.models import ProjectComment, ProjectMember, ProjectOp
from app.render import live, pools
from app.render.models import RenderJob

from .licence_helpers import CONTRACT as LICENCE
from .licence_helpers import error_of
from .pf12_helpers import PL, RJ, kh, make_key
from .project_helpers import Person, action_op, create, delta_op, hex32, invite_and_accept, pull, push
from .render_helpers import (
    APP_PROJECT,
    MOVED,
    VIEWS,
    admin,
    claimed,
    finish,
    issue_worker,
    job,
    project,
    push_touch,
    rj,
    submit,
    submitted,
)
from .test_pf12_webhooks import hook, receiver, resolver, run  # noqa: F401  (the fixtures)
from .test_releases import _publish

V12 = {"X-Truebex-Contract": "project-log/1.2"}
WALL_PIN = {"entity": "dc643577cfb582fabd0d7f9edef6b30d", "point_mm": None, "view": None}
WRONG_TYPES = [None, 7, []]
KELVIN = chr(0x212A)  # K, the Kelvin sign
DOTTED_I = chr(0x130)  # the dotted capital I


@pytest.fixture(autouse=True)
def _clean_state():
    waiters.reset()
    presence.reset()
    pools.DESIRED.clear()
    live.set_share_resolver(None)
    yield
    waiters.reset()
    presence.reset()
    live.set_share_resolver(None)


@pytest.fixture()
def setup(client):
    """A Pro-trial designer with the app's project (two operations), an admin and a worker."""
    a = Person(client, "a@example.com")
    pid, head = project(client, a, project_id=APP_PROJECT)
    token = issue_worker(client, admin(client))
    return {"a": a, "pid": pid, "head": head, "token": token}


def _row(job_id: str) -> RenderJob:
    with SessionLocal() as db:
        return db.get(RenderJob, job_id)


def _field(res) -> str:
    return res.json()["data"]["fields"][0]["field"]


# --- the helper -------------------------------------------------------------------------------------


def test_pf14f_canonical_spelling():
    from app import enums

    allowed = ("draft", "standard", "high")
    assert enums.canonical("High", allowed) == "high"
    assert enums.canonical("HIGH", allowed) == "high"
    assert enums.canonical("high", allowed) == "high"
    assert enums.canonical("sTaNdArD", allowed) == "standard"
    # The canonical spelling comes from the tuple, whatever its case.
    assert enums.canonical("lit", ("Lit", "Unlit")) == "Lit"
    for value in (None, 7, 7.0, True, [], ["high"], {"high": 1}, "", " high", "high ", "highs", "Hi"):
        assert enums.canonical(value, allowed) is None, value
    # ASCII only: str.lower() maps the Kelvin sign to "k" (and the dotted capital I to "i" + a dot).
    assert enums.canonical("pac" + KELVIN, ("pack",)) is None
    assert ("pac" + KELVIN).lower() == "pack"
    assert enums.canonical("H" + DOTTED_I + "GH", allowed) is None


# --- render-jobs 5.1 and 5.3 ------------------------------------------------------------------------


def test_pf14f_render_kind_and_quality_any_case(client, setup):
    a, pid, head = setup["a"], setup["pid"], setup["head"]
    rec = submitted(client, rj(a), kind="Panorama", quality="High", project_id=pid, at_seq=head, views=VIEWS)
    assert (rec["kind"], rec["quality"], rec["class"]) == ("panorama", "high", "gpu-std")
    assert (job(client, rj(a), rec["job_id"])["kind"], job(client, rj(a), rec["job_id"])["quality"]) == ("panorama", "high")
    row = _row(rec["job_id"])
    assert (row.kind, row.quality, row.worker_class) == ("panorama", "high", "gpu-std")

    # Upper case and the other qualities; the estimate is the lower-case spelling's.
    shouted = submitted(client, rj(a), kind="PANORAMA", quality="Draft", project_id=pid, at_seq=head, views=VIEWS)
    plain = submitted(client, rj(a), kind="panorama", quality="draft", project_id=pid, at_seq=head)
    assert (shouted["kind"], shouted["quality"]) == ("panorama", "draft")
    assert shouted["cost_units_estimate"] == plain["cost_units_estimate"]
    assert submitted(client, rj(a), kind="Panorama", quality="STANDARD", project_id=pid, at_seq=head, views=VIEWS)["quality"] == "standard"
    # The follow rule sees the canonical kind (only a panorama set follows the log).
    followed = submitted(client, rj(a), kind="Panorama", project_id=pid, at_seq=head, views=VIEWS, follow=True)
    assert followed["follow"] is True and followed["quality"] == "standard"
    # A pack job with its items.
    pack = submitted(client, rj(a), kind="Pack", project_id=pid, at_seq=head, params={"items": ["sheets", "boq"]})
    assert pack["kind"] == "pack" and _row(pack["job_id"]).params == {"items": ["sheets", "boq"]}

    listed = client.get("/jobs", params={"project_id": pid}, headers=rj(a)).json()["jobs"]
    assert {j["job_id"]: (j["kind"], j["quality"]) for j in listed}[rec["job_id"]] == ("panorama", "high")
    assert {j["kind"] for j in listed} == {"panorama", "pack"}

    # Unknown words still answer 422, naming the canonical spellings.
    err = error_of(submit(client, rj(a), kind="Panoramas", project_id=pid, at_seq=head, views=VIEWS), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "kind" and "one of panorama, tiles, pack" in err["detail"]
    err = error_of(submit(client, rj(a), kind="Panorama", quality="Ultra", project_id=pid, at_seq=head, views=VIEWS), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "quality" and "one of draft, standard, high" in err["detail"]
    err = error_of(submit(client, rj(a), kind="Pack", project_id=pid, at_seq=head, follow=True, params={"items": ["sheets"]}), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "follow"


def test_pf14f_followed_set_and_list_filters_any_case(client, setup, resolver, receiver):  # noqa: F811
    a, pid, head, token = setup["a"], setup["pid"], setup["head"], setup["token"]
    key = make_key(client, a.session, ["projects:read", "webhooks:manage"])
    hook(client, key, ["job.succeeded"])
    # The app's cloud panorama: a followed set, then the tiles the next push makes.
    follow = submitted(client, rj(a), kind="Panorama", quality="High", project_id=pid, at_seq=head, views=VIEWS, follow=True)
    c = claimed(client, token)
    assert c["job"]["job_id"] == follow["job_id"] and (c["job"]["kind"], c["job"]["quality"]) == ("panorama", "high")
    finish(client, token, c)
    assert run() == 1
    sent = receiver.bodies()[0]
    assert sent["type"] == "job.succeeded" and (sent["data"]["kind"], sent["data"]["quality"]) == ("panorama", "high")
    head = push_touch(client, a, pid, MOVED)

    # Unfollow lists the set's queued and running tiles jobs as the app spells the filters.
    queued = client.get("/jobs", params={"project_id": pid, "kind": "Tiles", "state": "Queued"}, headers=rj(a))
    assert queued.status_code == 200, queued.text
    tiles = queued.json()["jobs"]
    assert len(tiles) == 1 and tiles[0]["kind"] == "tiles" and tiles[0]["state"] == "queued"
    assert tiles[0]["base_job_id"] == follow["job_id"] and tiles[0]["quality"] == "high"
    assert client.get("/jobs", params={"kind": "TILES"}, headers=rj(a)).json()["jobs"][0]["job_id"] == tiles[0]["job_id"]
    assert [j["job_id"] for j in client.get("/jobs", params={"state": "QUEUED"}, headers=rj(a)).json()["jobs"]] == [tiles[0]["job_id"]]
    assert client.get("/jobs", params={"kind": "Tiles", "state": "Running"}, headers=rj(a)).json()["jobs"] == []
    assert client.get("/jobs", params={"kind": "Panorama", "state": "Succeeded"}, headers=rj(a)).json()["jobs"][0]["job_id"] == follow["job_id"]
    # A kind nobody runs lists nothing (as before); a state that is none answers 422.
    assert client.get("/jobs", params={"kind": "Tile"}, headers=rj(a)).json()["jobs"] == []
    err = error_of(client.get("/jobs", params={"state": "Waiting"}, headers=rj(a)), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "state" and "queued, claimed, running" in err["detail"]

    # A client's tiles job against the set, spelled as a Shipping build may, joins the queued one.
    joined = submitted(client, rj(a), kind="TILES", project_id=pid, at_seq=head, base_job_id=follow["job_id"], changed=[hex32()])
    assert joined["job_id"] == tiles[0]["job_id"] and joined["coalesced"] is True and joined["kind"] == "tiles"
    assert _row(joined["job_id"]).kind == "tiles"


def test_pf14f_v1_jobs_any_case(client):
    owner = Person(client, "owner@example.com")
    pid, head = project(client, owner)
    key = make_key(client, owner.session, ["projects:read", "jobs:write"])
    post = lambda body: client.post("/v1/jobs", json=body, headers=kh(key, **RJ, **{"Idempotency-Key": hex32()}))  # noqa: E731
    res = post({"kind": "Pack", "project_id": pid, "at_seq": head, "params": {"items": ["sheets"]}})
    assert res.status_code == 201, res.text
    pack = res.json()
    assert pack["kind"] == "pack" and pack["quality"] == "standard"
    res = post({"kind": "Panorama", "quality": "High", "project_id": pid, "at_seq": head, "views": VIEWS})
    assert res.status_code == 201, res.text
    pano = res.json()
    assert (pano["kind"], pano["quality"]) == ("panorama", "high")
    got = client.get(f"/v1/jobs/{pano['job_id']}", headers=kh(key, **RJ)).json()
    assert (got["kind"], got["quality"]) == ("panorama", "high")
    listed = client.get("/v1/jobs", params={"kind": "PACK", "state": "Queued"}, headers=kh(key, **RJ))
    assert listed.status_code == 200, listed.text
    assert [j["job_id"] for j in listed.json()["jobs"]] == [pack["job_id"]]
    err = error_of(post({"kind": "Panoramas", "project_id": pid, "at_seq": head, "views": VIEWS}), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "kind"
    err = error_of(client.get("/v1/jobs", params={"state": "Done"}, headers=kh(key, **RJ)), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "state"


# --- project-log 5.6 ---------------------------------------------------------------------------------


def test_pf14f_project_log_kind_and_author_kind_any_case(client, resolver, receiver):  # noqa: F811
    a = Person(client, "a@example.com")
    key = make_key(client, a.session, ["projects:read", "projects:write", "webhooks:manage"])
    hook(client, key, ["project.ops_appended"])
    pid = create(client, a.dev)["project_id"]

    # A Shipping build's delta: kind "Delta", author_kind "Person".
    op = delta_op(a.author_id, [hex32()])
    op.update(kind="Delta", author_kind="Person")
    res = push(client, a.dev, pid, a.replica, [op])
    assert res.status_code == 200, res.text
    assert res.json()["results"][0]["status"] == "accepted"
    # An action in any case, and an agent's operation.
    act = action_op(a.author_id, [hex32()], base_seq=1)
    act.update(kind="Action", author_kind="PERSON")
    agent = delta_op(hex32(), [hex32()], base_seq=1)
    agent["author_kind"] = "Agent"
    res = push(client, a.dev, pid, a.replica, [act, agent])
    assert res.status_code == 200, res.text
    assert [r["status"] for r in res.json()["results"]] == ["accepted", "accepted"]
    # A key pushes as an agent, "Agent" included.
    keyed = delta_op(a.author_id, [hex32()], base_seq=3)
    keyed["author_kind"] = "AGENT"
    del keyed["author"]
    res = client.post(f"/v1/projects/{pid}/ops", json={"replica_id": hex32(), "ops": [keyed]}, headers=kh(key, **PL))
    assert res.status_code == 200, res.text
    assert res.json()["results"][0]["status"] == "accepted"

    ops = pull(client, a.dev, pid)["ops"]
    assert [(o["kind"], o["author_kind"]) for o in ops] == [("delta", "person"), ("action", "person"), ("delta", "agent"), ("delta", "agent")]
    assert ops[0]["delta"] and ops[1]["action"]["tool"] == "move" and ops[1]["delta"] is None
    with SessionLocal() as db:
        stored = db.execute(select(ProjectOp.kind, ProjectOp.author_kind).where(ProjectOp.project_id == pid).order_by(ProjectOp.server_seq)).all()
    assert [tuple(r) for r in stored] == [("delta", "person"), ("action", "person"), ("delta", "agent"), ("delta", "agent")]
    # The ops webhook's authors carry the canonical author_kind.
    from datetime import timedelta

    from app.licence import clock

    assert run(clock.now() + timedelta(seconds=31)) == 1
    authors = receiver.bodies()[0]["data"]["authors"]
    assert {"author": a.author_id, "author_kind": "person"} in authors
    assert all(x["author_kind"] in ("person", "agent") for x in authors)

    # The person check reads the canonical author_kind: "Person" with someone else's author id is refused.
    other = delta_op(hex32(), [hex32()], base_seq=4)
    other["author_kind"] = "Person"
    err = error_of(push(client, a.dev, pid, a.replica, [other]), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "ops[0].author"
    # restore stays the server's in any case; unknown words still answer 422.
    for kind in ("restore", "Restore", "RESTORE", "Deltas", "deltaaction"):
        bad = delta_op(a.author_id, [hex32()], base_seq=4)
        bad["kind"] = kind
        err = error_of(push(client, a.dev, pid, a.replica, [bad]), 422, "validation_failed")
        assert err["data"]["fields"][0]["field"] == "ops[0].kind" and "delta or action" in err["detail"], kind
    bad = delta_op(a.author_id, [hex32()], base_seq=4)
    bad["author_kind"] = "Robot"
    err = error_of(push(client, a.dev, pid, a.replica, [bad]), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "ops[0].author_kind" and "person or agent" in err["detail"]
    # A key cannot push as a person, in any case.
    keyed = delta_op(a.author_id, [hex32()], base_seq=4)
    keyed["author_kind"] = "Person"
    del keyed["author"]
    err = error_of(client.post(f"/v1/projects/{pid}/ops", json={"replica_id": hex32(), "ops": [keyed]}, headers=kh(key, **PL)), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "ops[0].author_kind"
    assert pull(client, a.dev, pid)["head_seq"] == 4


# --- project-log 5.21, 5.14, 5.15 ------------------------------------------------------------------------


def test_pf14f_comment_state_any_case(client):
    owner = Person(client, "owner@example.com")
    pid = create(client, owner.dev, "House", doc_version=55)["project_id"]
    headers = {**owner.dev, **V12}
    res = client.post(f"/projects/{pid}/comments", json={"text": "Look here", "anchor": WALL_PIN}, headers=headers)
    assert res.status_code == 201, res.text
    cid = res.json()["comment_id"]

    res = client.patch(f"/projects/{pid}/comments/{cid}", json={"state": "Resolved"}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["state"] == "resolved" and body["resolved_by"] is not None and body["resolved_at"]
    with SessionLocal() as db:
        assert db.get(ProjectComment, cid).state == "resolved"
    listed = client.get(f"/projects/{pid}/comments", params={"state": "resolved"}, headers=headers).json()["comments"]
    assert [c["comment_id"] for c in listed] == [cid]

    res = client.patch(f"/projects/{pid}/comments/{cid}", json={"state": "Open"}, headers=headers)
    assert res.status_code == 200, res.text
    assert (res.json()["state"], res.json()["resolved_by"], res.json()["resolved_at"]) == ("open", None, None)
    res = client.patch(f"/projects/{pid}/comments/{cid}", json={"state": "RESOLVED", "text": "Fixed"}, headers=headers)
    assert res.status_code == 200 and (res.json()["state"], res.json()["text"]) == ("resolved", "Fixed")
    with SessionLocal() as db:
        assert db.get(ProjectComment, cid).state == "resolved"
    for word in ("Closed", "deleted", "Deleted", "all"):
        err = error_of(client.patch(f"/projects/{pid}/comments/{cid}", json={"state": word}, headers=headers), 422, "validation_failed")
        assert err["data"]["fields"][0]["field"] == "state" and "open or resolved" in err["detail"], word
    with SessionLocal() as db:
        assert db.get(ProjectComment, cid).state == "resolved"


def test_pf14f_member_role_any_case(client):
    a = Person(client, "a@example.com")
    b = Person(client, "b@example.com")
    pid = create(client, a.dev)["project_id"]
    # The app invites from the cloud panel (SyncClient.cpp:332): "Editor".
    invite_and_accept(client, a, pid, b, "Editor")
    with SessionLocal() as db:
        member = db.scalar(select(ProjectMember).where(ProjectMember.project_id == pid, ProjectMember.user_id == b.user_id))
        assert (member.role, member.state) == ("editor", "active")
    # SetMemberRole (SyncClient.cpp:341): "Viewer", then back.
    res = client.patch(f"/projects/{pid}/members/{b.user_id}", json={"role": "Viewer"}, headers=a.dev)
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "viewer"
    res = client.patch(f"/projects/{pid}/members/{b.user_id}", json={"role": "EDITOR"}, headers=a.dev)
    assert res.status_code == 200 and res.json()["role"] == "editor"
    pending = client.post(f"/projects/{pid}/members", json={"email": "c@example.com", "role": "VIEWER"}, headers=a.dev)
    assert pending.status_code == 201, pending.text
    assert pending.json()["role"] == "viewer"
    # /v1 the same.
    key = make_key(client, a.session, ["projects:read", "projects:write"])
    res = client.post(f"/v1/projects/{pid}/members", json={"email": "d@example.com", "role": "Editor"}, headers=kh(key, **PL, **{"Idempotency-Key": hex32()}))
    assert res.status_code == 201, res.text
    assert res.json()["role"] == "editor"
    res = client.patch(f"/v1/projects/{pid}/members/{res.json()['invite_id']}", json={"role": "Viewer"}, headers=kh(key, **PL))
    assert res.status_code == 200 and res.json()["role"] == "viewer"
    roles = {m["email"]: m["role"] for m in client.get(f"/projects/{pid}/members", headers=a.dev).json()["members"]}
    assert roles == {"a@example.com": "owner", "b@example.com": "editor", "c@example.com": "viewer", "d@example.com": "viewer"}

    # The owner stays the only owner, in any case; unknown roles still answer 422.
    for word in ("owner", "Owner", "OWNER", "Admin"):
        err = error_of(client.post(f"/projects/{pid}/members", json={"email": "e@example.com", "role": word}, headers=a.dev), 422, "validation_failed")
        assert err["data"]["fields"][0]["field"] == "role" and "editor or viewer" in err["detail"], word
        err = error_of(client.patch(f"/projects/{pid}/members/{b.user_id}", json={"role": word}, headers=a.dev), 422, "validation_failed")
        assert err["data"]["fields"][0]["field"] == "role", word
    err = error_of(client.patch(f"/projects/{pid}/members/{a.user_id}", json={"role": "Editor"}, headers=a.dev), 422, "validation_failed")
    assert "owner" in err["detail"]
    with SessionLocal() as db:
        roles = dict(db.execute(select(ProjectMember.email, ProjectMember.role).where(ProjectMember.project_id == pid)).all())
    assert roles == {"a@example.com": "owner", "b@example.com": "editor", "c@example.com": "viewer", "d@example.com": "viewer"}


# --- licence-api 5.13 --------------------------------------------------------------------------------------


def test_pf14f_release_feed_channel_any_case(client, tmp_path):
    _publish(tmp_path, "1.1.0", "stable")
    _publish(tmp_path, "1.2.0-beta.1", "beta")
    for spelled, channel, versions in (
        ("Stable", "stable", ["1.1.0"]),
        ("STABLE", "stable", ["1.1.0"]),
        ("Beta", "beta", ["1.2.0-beta.1", "1.1.0"]),
        ("bEtA", "beta", ["1.2.0-beta.1", "1.1.0"]),
    ):
        res = client.get("/releases/feed", params={"channel": spelled, "platform": "win64"}, headers=LICENCE)
        assert res.status_code == 200, (spelled, res.text)
        feed = res.json()
        assert feed["channel"] == channel and [r["manifest"]["version"] for r in feed["releases"]] == versions, spelled
    assert client.get("/releases/feed", headers=LICENCE).json()["channel"] == "stable"
    for word in ("nightly", "Nightly", ""):
        err = error_of(client.get("/releases/feed", params={"channel": word}, headers=LICENCE), 422, "validation_failed")
        assert err["data"]["fields"][0]["field"] == "channel" and "stable or beta" in err["detail"], word


# --- what is not a word still answers 422 ------------------------------------------------------------------


def test_pf14f_wrong_types_answer_422(client, setup):
    a, pid, head = setup["a"], setup["pid"], setup["head"]
    for value in WRONG_TYPES + [{"kind": "panorama"}, True]:
        res = client.post("/jobs", json={"kind": value, "project_id": pid, "at_seq": head, "views": VIEWS}, headers={**rj(a), "Idempotency-Key": hex32()})
        assert res.status_code == 422 and _field(res) == "kind", (value, res.text)
    # quality: null is "not sent" (standard, as for the analysis kinds); anything but a word is refused.
    assert submitted(client, rj(a), project_id=pid, at_seq=head, quality=None)["quality"] == "standard"
    for value in (7, [], "", ["high"], True):
        res = submit(client, rj(a), project_id=pid, at_seq=head, quality=value)
        assert res.status_code == 422 and _field(res) == "quality", (value, res.text)

    project_id = create(client, a.dev, "House", doc_version=55)["project_id"]
    for field in ("kind", "author_kind"):
        for value in WRONG_TYPES:
            op = delta_op(a.author_id, [hex32()])
            op[field] = value
            res = push(client, a.dev, project_id, a.replica, [op])
            assert res.status_code == 422 and _field(res) == f"ops[0].{field}", (field, value, res.text)

    headers = {**a.dev, **V12}
    cid = client.post(f"/projects/{project_id}/comments", json={"text": "Look here", "anchor": WALL_PIN}, headers=headers).json()["comment_id"]
    for value in WRONG_TYPES:
        res = client.patch(f"/projects/{project_id}/comments/{cid}", json={"state": value}, headers=headers)
        assert res.status_code == 422, (value, res.text)
        assert _field(res) in ("state", "text"), (value, res.text)  # null alone: "send text, state or both"

    b = Person(client, "b@example.com")
    invite_and_accept(client, a, project_id, b, "viewer")
    for value in WRONG_TYPES:
        res = client.post(f"/projects/{project_id}/members", json={"email": "c@example.com", "role": value}, headers=a.dev)
        assert res.status_code == 422 and _field(res) == "role", (value, res.text)
        res = client.patch(f"/projects/{project_id}/members/{b.user_id}", json={"role": value}, headers=a.dev)
        assert res.status_code == 422 and _field(res) == "role", (value, res.text)
