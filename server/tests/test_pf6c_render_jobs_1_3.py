"""PF6c: the render service follows render-jobs 1.3.0 (CL4's follow sets) and
the project service holds project-log 1.2.1's action-finish.json.

CL4 (the app's edit-to-panorama pipeline, app main bc06615c6) reads three
things of a job record the platform did not answer: `output_job_id` on a follow
set (the job whose output 5.5 serves now, so a viewer knows a new picture
without fetching it), `base_job_id` = the set's id on the set's tiles jobs (its
Unfollow cancels them by it, CloudPano.cpp:525) and a tiles job's `trigger`
(the operations it was queued for: CL4's stage table stamps another writer's
edit T0 / T1 from it). The worker keeps starting from the newest picture: the
claim names it `base_manifest_job_id`. Every render-jobs route answers
render-jobs/1.3 and still takes 1.0-1.2 (PF11c's two echo tests moved here; PF6d moved
them on to test_pf6d_render_jobs_1_4.py with render-jobs/1.4).
"""

import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.database import SessionLocal
from app.licence import clock
from app.projects import waiters
from app.projects.models import ProjectOp
from app.render import live, pools, tiles
from app.render.models import RenderJob, RenderSet

from .licence_helpers import error_of
from .pf12_helpers import PL, kh, make_key
from .project_helpers import FIXTURES as PROJECT_LOG, Person, delta_op, hex32, invite_and_accept, pull, pushed
from .render_helpers import (
    APP_PROJECT,
    FIX,
    MOVED,
    VIEWS,
    admin,
    claim,
    claimed,
    finish,
    heartbeat,
    issue_worker,
    job,
    project,
    push_touch,
    rj,
    submitted,
)
from .test_pf4a_project_log_1_1 import APP_BLOBS, git_blob_id

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
APP_REPO = Path(r"T:\unreal5_7_4_projects\truebex_compact")
TRIGGER_KEYS = {"op_ids", "first_seq", "last_seq", "first_op_at", "first_accepted_at", "authors"}
# project-log 1.2.1 (CL4, app 5bf7ba130, on app main bc06615c6): the phone's fill.
CL4_COMMIT = "5bf7ba130"
APP_MAIN = "bc06615c6"
FINISH_BLOB = "c136e2dd7b71e6f40e7647e56d80665cbd391dca"
PR3_TBXP = "Docs/roadmap/fixtures/PR3-pano-rooms.tbxp"
SAM = "019a2b3c4d5e7000a000000000000007"  # members.json's editor (user 7)
RFC3339_MS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


@pytest.fixture(autouse=True)
def _clean_state():
    waiters.reset()
    pools.DESIRED.clear()
    live.set_share_resolver(None)
    yield
    waiters.reset()
    live.set_share_resolver(None)


@pytest.fixture()
def rig(client):
    """A Pro-trial designer with the app's project (two operations), an admin and a GPU worker."""
    a = Person(client, "a@example.com")
    pid, head = project(client, a, project_id=APP_PROJECT)
    adm = admin(client)
    return {"a": a, "pid": pid, "head": head, "admin": adm, "token": issue_worker(client, adm)}


def jobs_of(client, person: Person, **params) -> list[dict]:
    res = client.get("/jobs", params=params, headers=rj(person))
    assert res.status_code == 200, res.text
    return res.json()["jobs"]


def followed(client, rig) -> str:
    """A follow set whose first panorama has finished: its id."""
    a, token = rig["a"], rig["token"]
    set_id = submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"], views=VIEWS, follow=True)["job_id"]
    c = claimed(client, token)
    assert c["job"]["job_id"] == set_id
    finish(client, token, c)
    return set_id


def touch_op(person: Person, touched: list[str], *, at: str, base_seq: int) -> dict:
    op = delta_op(person.author_id, touched, base_seq=base_seq)
    op["at"] = at
    return op


def push_one(client, person: Person, pid: str, op: dict) -> int:
    answer = pushed(client, person.dev, pid, person.replica, [op])
    assert answer["results"][0]["status"] == "accepted", answer
    return answer["results"][0]["server_seq"]


def head_of(client, person: Person, pid: str) -> int:
    return client.get(f"/projects/{pid}", headers=person.dev).json()["head_seq"]


def ms(dt: datetime) -> str:
    """RFC 3339 UTC with milliseconds: how a trigger's times are answered."""
    dt = clock.aware(dt).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def accepted_at(pid: str, op_id: str) -> datetime:
    with SessionLocal() as db:
        return db.scalar(select(ProjectOp.received_at).where(ProjectOp.project_id == pid, ProjectOp.op_id == op_id))


# --- output_job_id and the set's base_job_id ---------------------------------------------------------


def test_pf6c_follow_set_record(client, rig):
    a, token, pid = rig["a"], rig["token"], rig["pid"]
    pending = submitted(client, rj(a), project_id=pid, at_seq=rig["head"], views=VIEWS, follow=True)
    set_id = pending["job_id"]
    # Before its first panorama: following, nothing to serve yet.
    assert pending["follow"] is True and pending["output_job_id"] is None and pending["base_job_id"] is None
    assert pending.get("trigger") is None
    finish(client, token, claimed(client, token))
    first = job(client, rj(a), set_id)
    assert first["output_ready"] is True and first["output_job_id"] == set_id  # its own picture

    # A push: the set's tiles job names the set (RenderJobsStub.cpp: T.BaseJobId = SetId).
    push_touch(client, a, pid, MOVED)
    (t1,) = jobs_of(client, a, kind="tiles")
    assert t1["base_job_id"] == set_id and t1["output_job_id"] is None and t1["follow"] is False
    assert job(client, rj(a), t1["job_id"])["base_job_id"] == set_id
    assert job(client, rj(a), set_id)["output_job_id"] == set_id  # nothing new shown yet
    c1 = claimed(client, token)
    assert c1["job"]["job_id"] == t1["job_id"] and c1["job"]["base_job_id"] == set_id
    # What the worker starts from keeps its own name: the set's newest picture.
    assert c1["job"]["base_manifest_job_id"] == set_id
    assert client.get(c1["inputs"]["base_manifest_url"]).json()["job_id"] == set_id
    finish(client, token, c1, "manifest-tiles.json", wall_s=30)

    # 5.2 on the follow job: its output is now the update's; 5.5 serves that job's manifest.
    after = job(client, rj(a), set_id)
    assert after["output_job_id"] == t1["job_id"] and after["follow"] is True and after["rev"] > first["rev"]
    with SessionLocal() as db:
        assert db.get(RenderSet, set_id).latest_job_id == t1["job_id"]
    out = client.get(f"/jobs/{set_id}/output", headers=rj(a))
    assert out.status_code == 200, out.text
    assert out.json()["job_id"] == after["output_job_id"] == t1["job_id"]
    done1 = job(client, rj(a), t1["job_id"])
    assert done1["state"] == "succeeded" and done1["base_job_id"] == set_id and done1["output_job_id"] is None
    # /v1's panorama read names the same job.
    key = make_key(client, a.session, ["projects:read"])
    v1 = client.get(f"/v1/projects/{pid}/panoramas/{set_id}", headers=kh(key, **PL)).json()
    assert v1["job_id"] == after["output_job_id"]

    # A second push: its tiles job names the set too, while the worker starts from the first update's picture.
    push_touch(client, a, pid, [hex32()])
    (t2,) = jobs_of(client, a, kind="tiles", state="queued")
    assert t2["base_job_id"] == set_id
    listed = {j["job_id"]: j["base_job_id"] for j in jobs_of(client, a, project_id=pid, kind="tiles")}
    assert listed == {t1["job_id"]: set_id, t2["job_id"]: set_id}
    c2 = claimed(client, token)
    assert c2["job"]["job_id"] == t2["job_id"] and c2["job"]["base_job_id"] == set_id
    assert c2["job"]["base_manifest_job_id"] == t1["job_id"]
    assert client.get(c2["inputs"]["base_manifest_url"]).json()["job_id"] == t1["job_id"]
    with SessionLocal() as db:
        assert db.get(RenderJob, t2["job_id"]).base_job_id == t1["job_id"]  # the internal base, as before
    finish(client, token, c2, "manifest-tiles.json", wall_s=30)
    assert job(client, rj(a), set_id)["output_job_id"] == t2["job_id"]
    assert client.get(f"/jobs/{set_id}/output", headers=rj(a)).json()["job_id"] == t2["job_id"]
    assert job(client, rj(a), t2["job_id"])["base_job_id"] == set_id

    # Every other job answers null: a panorama that does not follow, before and after it finishes.
    plain = submitted(client, rj(a), project_id=pid, at_seq=head_of(client, a, pid), views=VIEWS)
    assert plain["output_job_id"] is None and plain["base_job_id"] is None and "trigger" not in plain
    finish(client, token, claimed(client, token))
    assert job(client, rj(a), plain["job_id"])["output_job_id"] is None


# --- the trigger -----------------------------------------------------------------------------------------


def test_pf6c_trigger_and_coalesce(client, rig):
    a, token, pid = rig["a"], rig["token"], rig["pid"]
    b = Person(client, "b@example.com")
    invite_and_accept(client, a, pid, b, "editor")
    set_id = followed(client, rig)

    # Two pushes by two people before a claim: one queued tiles job.
    op1 = touch_op(a, [hex32()], at="2026-10-25T09:00:05.120Z", base_seq=head_of(client, a, pid))
    s1 = push_one(client, a, pid, op1)
    # b's clock says earlier (written with an offset): the trigger's T0 is b's.
    op2 = touch_op(b, [hex32()], at="2026-10-25T11:59:00.250+03:00", base_seq=s1)
    s2 = push_one(client, b, pid, op2)
    (t,) = jobs_of(client, a, kind="tiles", state="queued")
    tr = t["trigger"]
    assert set(tr) == TRIGGER_KEYS
    assert tr["op_ids"] == [op1["op_id"], op2["op_id"]]
    assert (tr["first_seq"], tr["last_seq"]) == (s1, s2) and s1 < s2
    assert tr["first_op_at"] == "2026-10-25T08:59:00.250Z"
    first_accepted = accepted_at(pid, op1["op_id"])
    assert tr["first_accepted_at"] == ms(first_accepted) and first_accepted <= accepted_at(pid, op2["op_id"])
    assert RFC3339_MS.match(tr["first_accepted_at"])
    assert tr["authors"] == [a.author_id, b.author_id]
    assert t["at_seq"] == s2 and t["base_job_id"] == set_id
    assert job(client, rj(a), t["job_id"])["trigger"] == tr

    # Claimed: a running job is never extended; the next push gets a job of its own.
    c = claimed(client, token)
    assert c["job"]["job_id"] == t["job_id"] and c["job"]["trigger"] == tr
    op3 = touch_op(a, [hex32()], at="2026-10-25T09:05:00.000Z", base_seq=s2)
    s3 = push_one(client, a, pid, op3)
    (t3,) = jobs_of(client, a, kind="tiles", state="queued")
    assert t3["job_id"] != t["job_id"] and t3["base_job_id"] == set_id
    assert t3["trigger"] == {
        "op_ids": [op3["op_id"]], "first_seq": s3, "last_seq": s3, "first_op_at": "2026-10-25T09:05:00.000Z",
        "first_accepted_at": ms(accepted_at(pid, op3["op_id"])), "authors": [a.author_id],
    }
    assert job(client, rj(a), t["job_id"])["trigger"] == tr
    # A client's tiles job against the set joins the queued one: the trigger stays the pushes'.
    joined = submitted(client, rj(a), kind="tiles", project_id=pid, at_seq=s3, base_job_id=set_id, changed=[hex32()])
    assert joined["job_id"] == t3["job_id"] and joined["coalesced"] is True and joined["trigger"] == t3["trigger"]

    # A push of two operations by one person: both in server order, one author.
    op4 = touch_op(b, [hex32()], at="2026-10-25T09:06:00.000Z", base_seq=s3)
    op5 = touch_op(b, [hex32()], at="2026-10-25T09:06:01.000Z", base_seq=s3)
    answer = pushed(client, b.dev, pid, b.replica, [op4, op5])
    s4, s5 = (r["server_seq"] for r in answer["results"])
    tr3 = job(client, rj(a), t3["job_id"])["trigger"]
    assert tr3["op_ids"] == [op3["op_id"], op4["op_id"], op5["op_id"]] and (tr3["first_seq"], tr3["last_seq"]) == (s3, s5)
    assert tr3["authors"] == [a.author_id, b.author_id] and tr3["first_op_at"] == "2026-10-25T09:05:00.000Z"
    assert tr3["first_accepted_at"] == t3["trigger"]["first_accepted_at"] and s4 < s5

    # A tiles job submitted by POST /jobs (no set) has none; no other kind carries the key.
    heartbeat(client, token, c)
    finish(client, token, c, "manifest-tiles.json", wall_s=30)
    plain = submitted(client, rj(a), project_id=pid, at_seq=s5, views=VIEWS)
    assert "trigger" not in plain
    c_plain = claimed(client, token, kinds=["panorama"])  # t3 is next for a tiles worker
    assert c_plain["job"]["job_id"] == plain["job_id"]
    finish(client, token, c_plain)
    own = submitted(client, rj(a), kind="tiles", project_id=pid, at_seq=s5, base_job_id=plain["job_id"], changed=[hex32()])
    assert own["coalesced"] is False and "trigger" in own and own["trigger"] is None
    assert own["base_job_id"] == plain["job_id"] and own["output_job_id"] is None
    assert "trigger" not in job(client, rj(a), set_id)


def test_pf6c_restore_records_its_op(client, rig):
    """A restore (changed = every face) still names its operation in the trigger."""
    a, pid = rig["a"], rig["pid"]
    set_id = followed(client, rig)
    snap = client.get(f"/projects/{pid}/snapshots/latest", headers=a.dev)
    assert snap.status_code == 200, snap.text
    version = client.post(
        f"/projects/{pid}/versions",
        json={"name": "Baseline", "note": "", "at_seq": 0, "snapshot_id": snap.json()["snapshot_id"]},
        headers=a.dev,
    )
    assert version.status_code == 201, version.text
    res = client.post(f"/projects/{pid}/versions/{version.json()['version_id']}/restore", headers=a.dev)
    assert res.status_code == 201, res.text
    op = res.json()["op"]
    assert op["kind"] == "restore" and op["touched"] == []
    (t,) = jobs_of(client, a, kind="tiles", state="queued")
    assert t["base_job_id"] == set_id and t["changed_count"] == 0  # every face
    with SessionLocal() as db:
        assert db.get(RenderJob, t["job_id"]).changed == []
    assert t["trigger"] == {
        "op_ids": [op["op_id"]], "first_seq": op["server_seq"], "last_seq": op["server_seq"],
        "first_op_at": ms(clock.parse_rfc3339(op["at"])), "first_accepted_at": ms(accepted_at(pid, op["op_id"])),
        "authors": [a.author_id],
    }


def test_pf6c_trigger_merge_rules():
    """The trigger module: server order whatever order the hooks ran in, the
    earliest `at` and accepted time, authors by first appearance, at most
    MAX_OPS op ids (the earliest; last_seq still the highest)."""
    from app.render import trigger

    t0 = datetime(2026, 10, 25, 9, 0, 0, tzinfo=timezone.utc)

    def op(seq: int, author: str, at: str) -> dict:
        return {"op_id": f"{seq:032x}", "server_seq": seq, "author": author, "at": at, "touched": [hex32()], "kind": "delta"}

    ana, sam = "a" * 32, "b" * 32
    late = trigger.from_ops(
        [op(7, sam, "2026-10-25T09:00:07.000Z"), op(8, ana, "2026-10-25T09:00:08.000Z")],
        {7: t0 + timedelta(seconds=7), 8: t0 + timedelta(seconds=8)}, t0,
    )
    early = trigger.from_ops([op(5, ana, "2026-10-25T12:00:09.999+03:00")], {5: t0 + timedelta(seconds=5)}, t0)
    merged = trigger.public(trigger.merge(late, early))  # the later push's hook ran first
    assert merged == {
        "op_ids": [f"{5:032x}", f"{7:032x}", f"{8:032x}"], "first_seq": 5, "last_seq": 8,
        "first_op_at": "2026-10-25T09:00:07.000Z", "first_accepted_at": "2026-10-25T09:00:05.000Z", "authors": [ana, sam],
    }
    # The accepted time falls back to now when the operation's row is not found; ids are united.
    again = trigger.merge(trigger.merge(late, early), trigger.from_ops([op(8, ana, "2026-10-25T09:00:08.000Z")], {}, t0))
    assert trigger.public(again)["op_ids"] == merged["op_ids"]
    assert trigger.public(trigger.from_ops([op(9, ana, "2026-10-25T09:00:01.000Z")], {}, t0))["first_accepted_at"] == ms(t0)
    assert trigger.merge(None, None) is None and trigger.public(None) is None and trigger.from_ops([], {}, t0) is None
    # The cap: the earliest MAX_OPS ids, last_seq the highest of all.
    many = trigger.from_ops([op(s, ana, "2026-10-25T09:00:00.000Z") for s in range(1, trigger.MAX_OPS + 51)], {}, t0)
    out = trigger.public(many)
    assert len(out["op_ids"]) == trigger.MAX_OPS and out["op_ids"][0] == f"{1:032x}"
    assert out["first_seq"] == 1 and out["last_seq"] == trigger.MAX_OPS + 50


def test_pf6c_trigger_column_migrated(tmp_path):
    """init_db adds render_jobs.trigger to a table from before PF6c."""
    from sqlalchemy import create_engine, inspect

    from app.database import _ADDED_COLUMNS, Base, _migrate

    assert ("trigger", "JSON") in _ADDED_COLUMNS["render_jobs"]
    engine = create_engine(f"sqlite:///{tmp_path / 'before.db'}")
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE render_jobs DROP COLUMN \"trigger\""))
        assert "trigger" not in {c["name"] for c in inspect(engine).get_columns("render_jobs")}
        _migrate(engine)
        assert "trigger" in {c["name"] for c in inspect(engine).get_columns("render_jobs")}
    finally:
        engine.dispose()


# --- 5.4 on a follow set, 5.5 after it stopped ----------------------------------------------------


def test_pf6c_stopped_set_still_serves(client, rig):
    a, token, pid = rig["a"], rig["token"], rig["pid"]
    set_id = followed(client, rig)
    push_touch(client, a, pid, MOVED)
    c1 = claimed(client, token)
    finish(client, token, c1, "manifest-tiles.json", wall_s=30)
    t1 = c1["job"]["job_id"]
    assert job(client, rj(a), set_id)["output_job_id"] == t1
    push_touch(client, a, pid, [hex32()])
    (queued,) = jobs_of(client, a, kind="tiles", state="queued")
    before = job(client, rj(a), set_id)

    # 5.4 on the follow job stops the set.
    res = client.post(f"/jobs/{set_id}/cancel", headers=rj(a))
    assert res.status_code == 200, res.text
    stopped = res.json()
    assert stopped["follow"] is False and stopped["output_job_id"] == t1 and stopped["rev"] > before["rev"]
    now = job(client, rj(a), set_id)
    assert now["follow"] is False and now["output_job_id"] == t1 and now["output_ready"] is True
    # 5.5 still serves the last output.
    out = client.get(f"/jobs/{set_id}/output", headers=rj(a))
    assert out.status_code == 200, out.text
    assert out.json()["job_id"] == t1
    # The set's queued tiles job went with it.
    assert job(client, rj(a), queued["job_id"])["state"] == "cancelled"
    assert next(j for j in jobs_of(client, a, project_id=pid) if j["job_id"] == set_id)["output_job_id"] == t1
    # Again: 409 job_finished (the app's Unfollow reads it as already stopped); a push queues nothing.
    error_of(client.post(f"/jobs/{set_id}/cancel", headers=rj(a)), 409, "job_finished")
    push_touch(client, a, pid, [hex32()])
    assert jobs_of(client, a, kind="tiles", state="queued") == []
    assert claim(client, token).status_code == 204


def test_pf6c_stop_ends_the_running_update(client, rig):
    """5.4 on a follow set while its update renders: the update is asked to
    stop (the app's stub cancels it too), ends cancelled at no charge, and the
    stopped set keeps answering the output it had."""
    a, token, pid = rig["a"], rig["token"], rig["pid"]
    set_id = followed(client, rig)
    used = client.get("/jobs/usage", headers=rj(a)).json()["used_cu"]
    push_touch(client, a, pid, MOVED)
    c = claimed(client, token)
    assert heartbeat(client, token, c).json()["cancel"] is False
    stopped = client.post(f"/jobs/{set_id}/cancel", headers=rj(a)).json()
    assert stopped["follow"] is False and stopped["output_job_id"] == set_id
    assert job(client, rj(a), c["job"]["job_id"])["message"] == "Stopping…"
    # The worker learns it at its next heartbeat; a completion instead is refused.
    assert heartbeat(client, token, c).json()["cancel"] is True
    ended = job(client, rj(a), c["job"]["job_id"])
    assert ended["state"] == "cancelled" and ended["cost_units"] is None
    error_of(finish_raw(client, token, c), 409, "lease_lost")
    assert job(client, rj(a), set_id)["output_job_id"] == set_id
    assert client.get(f"/jobs/{set_id}/output", headers=rj(a)).json()["job_id"] == set_id
    assert client.get("/jobs/usage", headers=rj(a)).json()["used_cu"] == used


def finish_raw(client, token: str, c: dict):
    """Upload the update's tiles and send 5.9 (the answer as it is)."""
    from .render_helpers import complete, fixture_manifest, rendered_tiles, upload_outputs

    m = fixture_manifest("manifest-tiles.json", c)
    try:
        upload_outputs(client, token, c, rendered_tiles(m))
    except AssertionError:
        pass  # the lease already ended: the upload is refused too
    return complete(client, token, c, m, wall_s=30)


def test_pf6c_tiles_need_no_header_or_token(client, rig):
    a = rig["a"]
    set_id = followed(client, rig)
    out = client.get(f"/jobs/{set_id}/output", headers=rj(a)).json()
    shas = sorted(tiles.all_tiles(out))
    assert shas and out["tiles_base"] == "http://testserver/tiles"
    client.post(f"/jobs/{set_id}/cancel", headers=rj(a))  # a stopped set's tiles stay public
    for sha in (shas[0], shas[-1]):
        res = client.get(f"/tiles/{sha}.jpg", headers={})
        assert res.status_code == 200, res.text
        assert "authorization" not in {k.lower() for k in res.request.headers}
        assert "x-truebex-contract" not in {k.lower() for k in res.request.headers}
        assert res.headers["Cache-Control"] == "public, max-age=31536000, immutable"
        assert res.headers["Access-Control-Allow-Origin"] == "*" and res.headers["Content-Type"] == "image/jpeg"
        assert res.content == (FIX / "tiles" / f"{sha}.jpg").read_bytes()
        assert "X-Truebex-Contract" not in res.headers  # no contract on a tile
    missing = client.get(f"/tiles/{'0' * 64}.jpg", headers={})
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


# --- render-jobs/1.3 on every route (PF11c's two tests, moved) ----------------------------------------
# PF6d moved test_pf6c_echo_1_3 and test_pf6c_clients_and_documents_speak_1_3 on to
# test_pf6d_render_jobs_1_4.py as test_pf6d_echo_1_4 and test_pf6d_clients_and_documents_speak_1_4: every
# route answers render-jobs/1.4 since 1.4.0 (PR5) and still takes CL4's 1.3.


@pytest.mark.skipif(not (OUT / "developers" / "jobs" / "index.html").exists(), reason="out/ not built (run npm run build)")
def test_site_pf6c_developers_jobs_names_the_follow_keys():
    """The /v1/jobs reference lists the record's 1.3.0 keys."""
    html = (OUT / "developers" / "jobs" / "index.html").read_text(encoding="utf-8")
    for key in ("output_job_id", "base_job_id", "trigger", "JobTrigger", "first_accepted_at"):
        assert key in html, key


# --- project-log 1.2.1: the phone's fill (action-finish.json) ----------------------------------------


def _app_blob(rev_path: str) -> bytes | None:
    git = shutil.which("git")
    if git is None or not (APP_REPO / ".git").exists():
        return None
    run = subprocess.run([git, "-C", str(APP_REPO), "cat-file", "-p", rev_path], capture_output=True, timeout=60)
    return run.stdout if run.returncode == 0 else None


def test_pf6c_action_finish_fixture(client):
    """The app's action-finish.json (project-log 1.2.1, CL4) is its blob; PF4's
    push takes it as an action op (a fill on a wall of PR3-pano-rooms.tbxp's
    living room, touched = the wall) and queues a follow set's update with it
    in the trigger; PF9's builder writes the same tool, args and permission."""
    data = (PROJECT_LOG / "action-finish.json").read_bytes()
    assert git_blob_id(data) == FINISH_BLOB == APP_BLOBS["action-finish.json"] and b"\r" not in data
    readme = (PROJECT_LOG / "README.md").read_text(encoding="utf-8")
    assert "action-finish.json" in readme and "1.2.1" in readme and CL4_COMMIT in readme and APP_MAIN in readme
    op = json.loads(data)
    wall = op["touched"][0]
    assert op["kind"] == "action" and op["author"] == SAM and op["author_kind"] == "person"
    assert op["action"] == {
        "tool": "fill",
        "args": {"target": f"wall#{wall}", "face": "left", "finish": {"kind": "paint", "colour": "#C0392B"}},
        "permission": "edit",
    }
    members = json.loads((PROJECT_LOG / "members.json").read_text(encoding="utf-8"))["members"]
    assert {m["user_id"]: m["author_id"] for m in members}[7] == SAM
    # Where the app repository is here: the wall bounds PR3-pano-rooms.tbxp's living room.
    tbxp = _app_blob(f"main:{PR3_TBXP}")
    if tbxp is not None:
        doc = json.loads(tbxp)
        assert doc["projectUid"] == APP_PROJECT
        (row,) = [w for w in doc["walls"] if w["uid"] == wall]
        (living,) = [r for r in doc["regions"] if r["name"] == "Living Room"]
        assert row["centerline"] in {edge["el"] for edge in living["cycle"]}
        listed = _app_blob(f"{APP_MAIN}:Docs/roadmap/fixtures/contracts/project-log/action-finish.json")
        assert listed is None or listed == data

    # The push: Ana's project (PR3's id), Sam the editor (his author id), a follow set waiting on it.
    ana = Person(client, "ana@example.com")
    sam = Person(client, "sam@example.com")
    pid, head = project(client, ana, project_id=APP_PROJECT)
    invite_and_accept(client, ana, pid, sam, "editor")
    sam.set_author_id(SAM)
    token = issue_worker(client, admin(client))
    set_id = submitted(client, rj(ana), project_id=pid, at_seq=head, views=VIEWS, follow=True)["job_id"]
    finish(client, token, claimed(client, token))
    sent = {**op, "base_seq": head}
    answer = pushed(client, sam.web, pid, op["replica_id"], [sent])
    assert answer["results"] == [{"op_id": op["op_id"], "status": "accepted", "server_seq": head + 1}]
    (got,) = pull(client, ana.dev, pid, after=head)["ops"]
    assert got == {**sent, "server_seq": head + 1, "delta": None, "delta_format": None, "restore": None}
    assert got["touched"] == [wall]
    (t,) = jobs_of(client, ana, kind="tiles", state="queued")
    assert t["base_job_id"] == set_id and t["changed_count"] == 1
    assert t["trigger"]["op_ids"] == [op["op_id"]] and t["trigger"]["authors"] == [SAM]
    assert t["trigger"]["first_op_at"] == op["at"] == "2026-10-22T10:40:00.000Z"

    # PF9's builder (src/viewer/actions.ts fillFace), checked by its self-test against this file.
    selftest = (ROOT / "src" / "viewer" / "selftest.ts").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert 'import finishFixture from "../../server/tests/contracts/project-log/action-finish.json";' in selftest
    assert "fillFace(" in selftest.split("function finishBuilder", 1)[1].split("\n}\n", 1)[0]
    script = OUT / "viewer" / "selftest.mjs"
    node = shutil.which("node")
    if node and script.is_file():
        run = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stdout + run.stderr
        assert "checks passed" in run.stdout and "the app's fill" in run.stdout
