"""Cloud render orchestration (PF6, contract render-jobs v1.0): the contract's
§10 platform tests first, then PF6's per-endpoint tests (happy path, auth
failure, validation failure on each)."""

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import metering, tasks
from app.config import get_settings
from app.database import SessionLocal
from app.projects import waiters
from app.render import live, overage, pools, queue, quotas
from app.render.models import OverageCharge, RenderJob, Worker

from .conftest import signup
from .licence_helpers import Clock, error_of
from .project_helpers import UPLOADS, Person, hex32
from .render_helpers import (
    FIX,
    RJ,
    VIEW,
    WALL,
    admin,
    claim,
    claimed,
    complete,
    finish,
    fixture_manifest,
    heartbeat,
    issue_worker,
    job,
    project,
    push_touch,
    rendered_tiles,
    rj,
    studio,
    submit,
    submitted,
    tile_bytes,
    upload_outputs,
    wk,
)


@pytest.fixture(autouse=True)
def _clean_state():
    waiters.reset()
    pools.DESIRED.clear()
    live.set_share_resolver(None)
    yield
    waiters.reset()
    live.set_share_resolver(None)


@pytest.fixture()
def setup(client):
    """A Pro-trial designer with a project of two operations, an admin and a worker."""
    a = Person(client, "a@example.com")
    pid, head = project(client, a)
    adm = admin(client)
    token = issue_worker(client, adm)
    return {"a": a, "pid": pid, "head": head, "admin": adm, "token": token}


def run(name: str, now) -> None:
    assert tasks.run_due(now, only=[name], force=True) == [name]


# --- contract §10 platform tests ---------------------------------------------------------


def test_submit_estimate_and_idempotency(client, setup):
    a, pid, head = setup["a"], setup["pid"], setup["head"]
    key = hex32()
    body = {"kind": "panorama", "project_id": pid, "at_seq": head, "views": [VIEW], "follow": False}
    first = client.post("/jobs", json=body, headers={**rj(a), "Idempotency-Key": key})
    assert first.status_code == 201, first.text
    rec = first.json()
    assert rec["state"] == "queued" and rec["rev"] == 1 and rec["attempts"] == 0
    assert rec["cost_units_estimate"] == 1.5  # 90 s seed per view on gpu-std
    assert rec["cost_units"] is None and rec["output_ready"] is False and rec["error"] is None
    for k in ("job_id", "kind", "project_id", "at_seq", "progress", "message", "created_at", "started_at", "finished_at"):
        assert k in rec
    again = client.post("/jobs", json=body, headers={**rj(a), "Idempotency-Key": key})
    assert again.status_code == 201 and again.json()["job_id"] == rec["job_id"]
    other = client.post("/jobs", json={**body, "quality": "high"}, headers={**rj(a), "Idempotency-Key": key})
    error_of(other, 409, "idempotency_mismatch")
    with SessionLocal() as db:
        assert db.query(RenderJob).count() == 1


def test_claim_lease_heartbeat_complete(client, setup):
    a, token = setup["a"], setup["token"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    assert c["job"]["job_id"] == rec["job_id"] and c["job"]["state"] == "claimed"
    assert len(c["lease_id"]) == 32 and c["lease_expires_at"].endswith("Z")
    snap = c["inputs"]["snapshot"]
    assert snap["at_seq"] == 0 and snap["tbxp"]["url"] and snap["tbxpack"] is None
    ops = client.get(c["inputs"]["ops_url"])  # signed: no credential needed
    assert ops.status_code == 200
    body = ops.json()
    assert [o["server_seq"] for o in body["ops"]] == [1, 2] and body["head_seq"] == setup["head"]
    assert client.get(snap["tbxp"]["url"]).content == (FIX.parent / "project-log" / "snapshot-0000.tbxp").read_bytes()
    assert c["inputs"]["base_manifest_url"] is None and c["output_upload"]["part_bytes"] == 8388608
    hb = heartbeat(client, token, c, 0.4, "face e")
    assert hb.status_code == 200 and hb.json()["cancel"] is False
    assert job(client, rj(a), rec["job_id"])["state"] == "running"
    assert heartbeat(client, token, c, 0.8, "face u").status_code == 200
    done = finish(client, token, c)
    assert done["state"] == "succeeded" and done["cost_units"] == 1.5 and done["output_ready"] is True
    assert done["progress"] == 1 and done["finished_at"]
    # 5.9 is idempotent per lease (§8).
    again = complete(client, token, c, fixture_manifest("manifest-panorama.json", c))
    assert again.status_code == 200 and again.json()["rev"] == done["rev"]
    assert client.get("/jobs/usage", headers=rj(a)).json()["used_cu"] == 1.5
    # The claim answer has the fixture's shape (claim.json).
    assert set(json.loads((FIX / "claim.json").read_text("utf-8"))) <= set(c)


def test_lease_expiry_requeues_three_times(client, setup, monkeypatch):
    clk = Clock(monkeypatch)
    a, token = setup["a"], setup["token"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    for attempt in range(1, 5):
        claimed(client, token)
        clk.advance(seconds=121)
        run("render.leases.reap", clk.at)
        now = job(client, rj(a), rec["job_id"])
        assert now["attempts"] == attempt
        if attempt < 4:
            assert now["state"] == "queued", attempt
        else:
            assert now["state"] == "failed" and now["error"]["code"] == "timeout"
    assert claim(client, token).status_code == 204
    # A heartbeat keeps a lease alive.
    rec2 = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    for _ in range(5):
        clk.advance(seconds=90)
        assert heartbeat(client, token, c).status_code == 200
        run("render.leases.reap", clk.at)
    assert job(client, rj(a), rec2["job_id"])["state"] == "running"


def test_cancel_reaches_worker(client, setup):
    a, token = setup["a"], setup["token"]
    queued = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    gone = client.post(f"/jobs/{queued['job_id']}/cancel", headers=rj(a))
    assert gone.status_code == 200 and gone.json()["state"] == "cancelled"
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    assert heartbeat(client, token, c).json()["cancel"] is False
    asked = client.post(f"/jobs/{rec['job_id']}/cancel", headers=rj(a))
    assert asked.status_code == 200 and asked.json()["state"] == "running"
    told = heartbeat(client, token, c)
    assert told.status_code == 200 and told.json()["cancel"] is True
    assert heartbeat(client, token, c).json()["cancel"] is True  # repeated: still stop
    end = job(client, rj(a), rec["job_id"])
    assert end["state"] == "cancelled" and end["cost_units"] is None
    error_of(complete(client, token, c, fixture_manifest("manifest-panorama.json", c)), 409, "lease_lost")
    assert client.get("/jobs/usage", headers=rj(a)).json()["used_cu"] == 0


def test_worker_token_scoped(client, setup):
    a, adm = setup["a"], setup["admin"]
    tiles_only = issue_worker(client, adm, name="tiles-only", kinds=["tiles"])
    submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    assert claim(client, tiles_only, worker_id="tiles-only", kinds=["panorama", "tiles"]).status_code == 204
    error_of(claim(client, tiles_only, worker_id="tiles-only", kinds=["panorama"]), 403, "forbidden")
    # Without a lease, a worker token opens no upload (the worker discards, it does not stop).
    res = client.post(
        "/uploads", json={"purpose": "job-output", "files": [{"sha256": "a" * 64, "bytes": 1, "content_type": "image/jpeg"}]},
        headers={"Authorization": f"Bearer {tiles_only}", **UPLOADS},
    )
    error_of(res, 409, "lease_lost")
    assert claim(client, setup["token"]).status_code == 200


def test_follow_set_enqueues_tiles_on_push(client, setup):
    a, token, pid = setup["a"], setup["token"], setup["pid"]
    follow = submitted(client, rj(a), project_id=pid, at_seq=setup["head"], follow=True)
    assert follow["follow"] is True
    # Pushes while the panorama renders: one tiles job waits for it.
    head = push_touch(client, a, pid, [WALL])
    c = claimed(client, token)
    assert c["job"]["job_id"] == follow["job_id"]  # the waiting tiles job is not claimable yet
    finish(client, token, c)
    tiles_jobs = client.get("/jobs", params={"kind": "tiles"}, headers=rj(a)).json()["jobs"]
    assert len(tiles_jobs) == 1
    t = tiles_jobs[0]
    assert t["state"] == "queued" and t["at_seq"] == head and t["base_job_id"] == follow["job_id"]
    assert t["changed_count"] == 1 and t["views"] == [VIEW]
    with SessionLocal() as db:
        assert db.get(RenderJob, t["job_id"]).changed == [WALL]
    c2 = claimed(client, token)
    assert c2["job"]["job_id"] == t["job_id"] and c2["inputs"]["base_manifest_url"]
    base = client.get(c2["inputs"]["base_manifest_url"]).json()
    assert base["job_id"] == follow["job_id"]
    ops = client.get(c2["inputs"]["ops_url"]).json()
    assert ops["ops"][-1]["touched"] == [WALL]
    rev_before = job(client, rj(a), follow["job_id"])["rev"]
    finish(client, token, c2, "manifest-tiles.json", wall_s=30)
    after = job(client, rj(a), follow["job_id"])
    assert after["rev"] > rev_before and after["state"] == "succeeded" and after["at_seq"] == head
    out = client.get(f"/jobs/{follow['job_id']}/output", headers=rj(a)).json()
    assert out["job_id"] == t["job_id"] and out["faces_rendered"] == 2
    # A push to a project with no followed set enqueues nothing.
    other_pid, _ = project(client, a, ops=0)
    push_touch(client, a, other_pid, [WALL])
    assert len(client.get("/jobs", params={"kind": "tiles"}, headers=rj(a)).json()["jobs"]) == 1


def test_tiles_jobs_coalesce(client, setup):
    a, token, pid = setup["a"], setup["token"], setup["pid"]
    follow = submitted(client, rj(a), project_id=pid, at_seq=setup["head"], follow=True)
    finish(client, token, claimed(client, token))
    w2 = hex32()
    push_touch(client, a, pid, [WALL])
    head = push_touch(client, a, pid, [w2])
    jobs = client.get("/jobs", params={"kind": "tiles", "state": "queued"}, headers=rj(a)).json()["jobs"]
    assert len(jobs) == 1 and jobs[0]["at_seq"] == head
    with SessionLocal() as db:
        assert db.get(RenderJob, jobs[0]["job_id"]).changed == sorted([WALL, w2])
    # A client's tiles job against the set joins it too.
    joined = submitted(client, rj(a), kind="tiles", project_id=pid, at_seq=head, base_job_id=follow["job_id"], changed=[hex32()])
    assert joined["job_id"] == jobs[0]["job_id"] and joined["coalesced"] is True and joined["changed_count"] == 3
    # A restore touches everything: [] = every face.
    from app.database import SessionLocal as S
    from app.render import sets

    with S() as db:
        row = db.get(RenderJob, jobs[0]["job_id"])
        sets.coalesce(db, row, [], head, row.updated_at)
        db.commit()
        assert db.get(RenderJob, jobs[0]["job_id"]).changed == []
    assert sets.unite(["a"], ["b"]) == ["a", "b"] and sets.unite([], ["b"]) == []


def test_output_requires_uploaded_files(client, setup):
    a, token = setup["a"], setup["token"]
    submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    m = fixture_manifest("manifest-panorama.json", c)
    shas = rendered_tiles(m)
    upload_outputs(client, token, c, shas[:-1])
    body = error_of(complete(client, token, c, m), 422, "output_invalid")
    assert body["data"]["errors"][0]["rule"] == "file_missing" and body["data"]["errors"][0]["sha256"] == shas[-1]
    # A manifest that breaks §6.2 names the rule.
    broken = json.loads(json.dumps(m))
    broken["views"][0]["faces"]["n"]["tiles"][1] = broken["views"][0]["faces"]["n"]["tiles"][1][:3]
    body = error_of(complete(client, token, c, broken), 422, "output_invalid")
    assert any(e["rule"] == "tiles" and e["path"].endswith("faces.n.tiles[1]") for e in body["data"]["errors"])
    # A file sent through another session of the account does not count.
    data = tile_bytes(shas[-1])
    other = client.post(
        "/uploads",
        json={"purpose": "job-output", "files": [{"sha256": shas[-1], "bytes": len(data), "content_type": "image/jpeg"}]},
        headers={"Authorization": f"Bearer {token}", **UPLOADS},
    ).json()
    sent = client.put(
        f"/uploads/{other['upload_id']}/files/{shas[-1]}/parts/0",
        content=data,
        headers={
            "Authorization": f"Bearer {token}", **UPLOADS, "Content-Type": "application/octet-stream",
            "X-Part-Sha256": hashlib.sha256(data).hexdigest(),
        },
    )
    assert sent.status_code == 204
    error_of(complete(client, token, c, m), 422, "output_invalid")
    upload_outputs(client, token, c, shas[-1:])
    assert complete(client, token, c, m).status_code == 200


def test_cost_units_and_quota(client, setup):
    a, token = setup["a"], setup["token"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c0 = claimed(client, token)
    m0 = fixture_manifest("manifest-panorama.json", c0)
    upload_outputs(client, token, c0, rendered_tiles(m0))
    res = complete(client, token, c0, m0, wall_s=84.2, cls="cpu-8")  # the token's class is charged
    assert res.status_code == 200, res.text
    done = res.json()
    assert done["cost_units"] == 1.5  # 84.2 s = 1.403 cu on gpu-std, rounded up to 0.1
    assert quotas.cost_units(60, "gpu-std") == Decimal("1.0")
    assert quotas.cost_units(61, "gpu-std") == Decimal("1.1")
    assert quotas.cost_units(240, "cpu-8") == Decimal("1.0")
    # Failed jobs cost nothing.
    failing = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    res = client.post(
        f"/workers/jobs/{failing['job_id']}/fail",
        json={"lease_id": c["lease_id"], "code": "bad_input", "message": "no snapshot", "retryable": False},
        headers=wk(token),
    )
    assert res.status_code == 200 and res.json()["state"] == "failed" and res.json()["cost_units"] is None
    usage = client.get("/jobs/usage", headers=rj(a)).json()
    assert usage["used_cu"] == 1.5 and usage["limit_cu"] == 120 and usage["remaining_cu"] == 118.5
    # Past the allowance: 403 quota_exceeded with the numbers.
    with SessionLocal() as db:
        metering.record(db, "user", a.user_id, "cu", Decimal("118.0"))
        db.commit()
    body = error_of(submit(client, rj(a), project_id=setup["pid"], at_seq=setup["head"]), 403, "quota_exceeded")
    assert body["data"]["limit_cu"] == 120 and body["data"]["used_cu"] == 119.5
    assert body["data"]["resets_at"].endswith("-01T00:00:00Z")
    assert rec["job_id"]


def test_contract_header_and_error_envelope(client, setup):
    a = setup["a"]
    ok = client.get("/jobs/usage", headers=rj(a))
    assert ok.status_code == 200 and ok.headers["X-Truebex-Contract"] == "render-jobs/1.0"
    body = error_of(
        client.get("/jobs/usage", headers={**rj(a), "X-Truebex-Contract": "render-jobs/2.0"}), 400, "contract_version"
    )
    assert body["data"]["supported"] == ["render-jobs/1.0"]
    error_of(
        client.post("/workers/claim", json={}, headers={**wk(setup["token"]), "X-Truebex-Contract": "render-jobs/2.0"}),
        400, "contract_version",
    )
    body = error_of(client.get(f"/jobs/{hex32()}", headers=rj(a)), 404, "not_found")
    assert body["retry_after_s"] is None and "data" in body
    # No header: served as the current version.
    assert client.get("/jobs/usage", headers={"Authorization": f"Bearer {a.token}"}).status_code == 200


# --- 5.1 -----------------------------------------------------------------------------------


def test_jobs_submit_requires_feature_and_auth(client, setup):
    free = Person(client, "free@example.com", trial=False)
    pid, head = setup["pid"], setup["head"]
    body = error_of(submit(client, rj(free), project_id=pid, at_seq=head), 403, "plan_required")
    assert body["data"]["feature"] == "cloud.panoramas"
    error_of(client.post("/jobs", json={"kind": "panorama", "project_id": pid, "at_seq": head, "views": [VIEW]}, headers=RJ), 401, "unauthenticated")
    error_of(submit(client, wk(setup["token"]), project_id=pid, at_seq=head), 401, "unauthenticated")
    # Another account's project is not found.
    b = Person(client, "b@example.com")
    error_of(submit(client, rj(b), project_id=pid, at_seq=head), 404, "not_found")
    # An API key works and is metered like every developer call.
    key = client.post("/keys", json={"name": "ci"}, headers=setup["a"].session).json()["key"]
    res = submit(client, {"Authorization": f"Bearer {key}", **RJ}, project_id=pid, at_seq=head)
    assert res.status_code == 201, res.text
    assert res.headers["X-RateLimit-Remaining"]
    # And the website's session.
    assert submit(client, rj(setup["a"].session), project_id=pid, at_seq=head).status_code == 201


def test_jobs_submit_validation(client, setup):
    a, pid, head = setup["a"], setup["pid"], setup["head"]
    error_of(submit(client, rj(a), kind="tiles", project_id=pid, at_seq=head, changed=[]), 422, "validation_failed")
    error_of(submit(client, rj(a), project_id=pid, at_seq=head, views=[hex32() for _ in range(51)]), 422, "validation_failed")
    rec = submitted(client, rj(a), project_id=pid, at_seq=head)
    big = [f"{i:032x}" for i in range(10_001)]
    body = error_of(submit(client, rj(a), kind="tiles", project_id=pid, at_seq=head, base_job_id=rec["job_id"], changed=big), 422, "validation_failed")
    assert body["data"]["limit"] == 10_000
    body = error_of(submit(client, rj(a), project_id=pid, at_seq=head + 1), 409, "seq_ahead")
    assert body["data"]["head_seq"] == head
    error_of(submit(client, rj(a), kind="wind", project_id=pid, at_seq=head), 422, "validation_failed")
    error_of(submit(client, rj(a), kind="tiles", project_id=pid, at_seq=head, base_job_id=rec["job_id"], changed=[], follow=True), 422, "validation_failed")
    error_of(submit(client, rj(a), kind="pack", project_id=pid, at_seq=head, params={"items": ["movies"]}), 422, "validation_failed")
    error_of(submit(client, rj(a), project_id=pid, at_seq=head, views=[]), 422, "validation_failed")
    error_of(submit(client, rj(a), project_id=pid, at_seq=head, quality="ultra"), 422, "validation_failed")
    # A tiles job needs a finished base, from the last 90 days.
    error_of(submit(client, rj(a), kind="tiles", project_id=pid, at_seq=head, base_job_id=rec["job_id"], changed=[]), 422, "validation_failed")
    finish(client, setup["token"], claimed(client, setup["token"]))
    with SessionLocal() as db:
        row = db.get(RenderJob, rec["job_id"])
        row.finished_at = row.finished_at - timedelta(days=91)
        db.commit()
    body = error_of(
        submit(client, rj(a), kind="tiles", project_id=pid, at_seq=head, base_job_id=rec["job_id"], changed=[]),
        422, "validation_failed",
    )
    assert "90 days" in body["detail"]
    assert submitted(client, rj(a), kind="pack", project_id=pid, at_seq=head, params={"items": ["renders", "boq"]})["cost_units_estimate"] == 4.0


# --- 5.2, 5.3 ------------------------------------------------------------------------------


def test_jobs_status_long_poll_rev(client, setup):
    a, token = setup["a"], setup["token"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    rev = job(client, rj(a), rec["job_id"])["rev"]
    got: dict = {}

    def wait() -> None:
        started = time.monotonic()
        res = client.get(f"/jobs/{rec['job_id']}", params={"rev": rev, "wait_s": 10}, headers=rj(a))
        got["res"], got["done"], got["took"] = res, time.monotonic(), time.monotonic() - started

    t = threading.Thread(target=wait)
    t.start()
    time.sleep(0.5)
    sent = time.monotonic()
    assert heartbeat(client, token, c, 0.3).status_code == 200
    t.join(10)
    assert got["res"].status_code == 200 and got["res"].json()["rev"] > rev
    assert got["done"] - sent < 1.0 and got["took"] < 5
    # An unchanged rev waits the whole wait_s.
    started = time.monotonic()
    same = client.get(f"/jobs/{rec['job_id']}", params={"rev": got["res"].json()["rev"], "wait_s": 1}, headers=rj(a))
    assert same.status_code == 200 and time.monotonic() - started >= 0.9
    error_of(client.get(f"/jobs/{rec['job_id']}", params={"wait_s": 26}, headers=rj(a)), 422, "validation_failed")
    error_of(client.get(f"/jobs/{rec['job_id']}", headers=RJ), 401, "unauthenticated")
    error_of(client.get(f"/jobs/{rec['job_id']}", headers=rj(Person(client, "b@example.com"))), 404, "not_found")


def test_jobs_list_filters_and_cursor(client, setup):
    a = setup["a"]
    ids = [submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])["job_id"] for _ in range(3)]
    page = client.get("/jobs", params={"limit": 2}, headers=rj(a)).json()
    assert [j["job_id"] for j in page["jobs"]] == ids[::-1][:2] and page["next_cursor"]
    rest = client.get("/jobs", params={"limit": 2, "cursor": page["next_cursor"]}, headers=rj(a)).json()
    assert [j["job_id"] for j in rest["jobs"]] == [ids[0]] and rest["next_cursor"] is None
    assert client.get("/jobs", params={"state": "succeeded"}, headers=rj(a)).json()["jobs"] == []
    assert len(client.get("/jobs", params={"project_id": setup["pid"]}, headers=rj(a)).json()["jobs"]) == 3
    assert client.get("/jobs", headers=rj(Person(client, "b@example.com"))).json()["jobs"] == []
    error_of(client.get("/jobs", params={"limit": 0}, headers=rj(a)), 422, "validation_failed")
    error_of(client.get("/jobs", params={"state": "done"}, headers=rj(a)), 422, "validation_failed")
    error_of(client.get("/jobs", params={"cursor": "%%%"}, headers=rj(a)), 422, "validation_failed")
    error_of(client.get("/jobs", headers=RJ), 401, "unauthenticated")


# --- 5.4, 5.5, 5.6 -------------------------------------------------------------------------


def test_jobs_cancel_finished_and_output_not_ready(client, setup):
    a, token = setup["a"], setup["token"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    error_of(client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a)), 409, "not_ready")
    finish(client, token, claimed(client, token))
    error_of(client.post(f"/jobs/{rec['job_id']}/cancel", headers=rj(a)), 409, "job_finished")
    error_of(client.post(f"/jobs/{hex32()}/cancel", headers=rj(a)), 404, "not_found")
    error_of(client.post(f"/jobs/{rec['job_id']}/cancel", headers=RJ), 401, "unauthenticated")
    out = client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a))
    assert out.status_code == 200 and out.json()["tiles_base"] == "http://testserver/tiles"
    assert out.json()["schema"] == "truebex-tiles/1" and out.headers["Cache-Control"] == "private, no-store"
    error_of(client.get(f"/jobs/{rec['job_id']}/output", headers=RJ), 401, "unauthenticated")
    # Cancelling a following set stops it; the job stays succeeded.
    follow = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"], follow=True)
    finish(client, token, claimed(client, token))
    stopped = client.post(f"/jobs/{follow['job_id']}/cancel", headers=rj(a)).json()
    assert stopped["state"] == "succeeded" and stopped["follow"] is False
    push_touch(client, a, setup["pid"], [WALL])
    assert client.get("/jobs", params={"kind": "tiles"}, headers=rj(a)).json()["jobs"] == []
    error_of(client.post(f"/jobs/{follow['job_id']}/cancel", headers=rj(a)), 409, "job_finished")


def test_jobs_usage_by_kind(client, setup):
    a, token, pid = setup["a"], setup["token"], setup["pid"]
    submitted(client, rj(a), project_id=pid, at_seq=setup["head"], follow=True)
    finish(client, token, claimed(client, token), wall_s=84.2)  # 1.5 cu
    push_touch(client, a, pid, [WALL])
    finish(client, token, claimed(client, token), "manifest-tiles.json", wall_s=30)  # 0.5 cu
    usage = client.get("/jobs/usage", headers=rj(a)).json()
    expected = json.loads((FIX / "usage.json").read_text("utf-8"))
    assert set(expected) <= set(usage)
    assert usage["used_cu"] == 2.0 and usage["by_kind"] == {"panorama": 1.5, "tiles": 0.5}
    assert usage["classes"] == {"gpu-std": 1.0, "cpu-8": 0.25}
    assert usage["limit_cu"] == 120 and usage["remaining_cu"] == 118.0
    assert usage["period_start"].endswith("-01T00:00:00Z") and usage["daily"][-1]["cu"] == 2.0
    start, end = quotas.month_bounds()
    with SessionLocal() as db:
        assert metering.total(db, "user", a.user_id, "cu", start, end) == Decimal("2.000")
        assert metering.by_metric(db, "user", a.user_id, "cu.", start, end) == {"cu.panorama": Decimal("1.500"), "cu.tiles": Decimal("0.500")}
    error_of(client.get("/jobs/usage", headers=RJ), 401, "unauthenticated")


# --- 5.7-5.10 --------------------------------------------------------------------------------


def test_workers_claim_respects_doc_version(client, setup):
    a, pid, token = setup["a"], setup["pid"], setup["token"]
    old = submitted(client, rj(a), project_id=pid, at_seq=setup["head"])
    head = push_touch(client, a, pid, [WALL], delta_format="o5/54")
    new = submitted(client, rj(a), project_id=pid, at_seq=head)
    first = claimed(client, token, doc_version_max=38)
    assert first["job"]["job_id"] == old["job_id"]
    finish(client, token, first)
    assert claim(client, token, doc_version_max=38).status_code == 204
    second = claimed(client, token, doc_version_max=54)
    assert second["job"]["job_id"] == new["job_id"]
    with SessionLocal() as db:
        assert db.get(Worker, "pc-rtx").doc_version_max == 54
    # Validation and auth on 5.7.
    error_of(claim(client, token, worker_id="someone-else"), 422, "validation_failed")
    error_of(client.post("/workers/claim", json={"worker_id": "pc-rtx", "kinds": [], "doc_version_max": 38}, headers=wk(token)), 422, "validation_failed")
    error_of(client.post("/workers/claim", json={"worker_id": "pc-rtx", "kinds": ["tiles"], "doc_version_max": 38, "wait_s": 21}, headers=wk(token)), 422, "validation_failed")
    error_of(claim(client, "tbx_wrk_not-a-real-token"), 401, "unauthenticated")
    error_of(client.post("/workers/claim", json={}, headers={"Authorization": f"Bearer {a.token}", **RJ}), 401, "unauthenticated")


def test_workers_revoked_and_lease_lost(client, setup):
    a, adm, token = setup["a"], setup["admin"], setup["token"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    res = client.delete("/admin/workers/pc-rtx", headers=adm)
    assert res.status_code == 200 and res.json()["revoked_at"]
    error_of(heartbeat(client, token, c), 401, "worker_revoked")
    error_of(claim(client, token), 401, "worker_revoked")
    requeued = job(client, rj(a), rec["job_id"])
    assert requeued["state"] == "queued" and requeued["attempts"] == 1
    other = issue_worker(client, adm, name="gpu-eu-01")
    c2 = claimed(client, other, worker_id="gpu-eu-01")
    error_of(heartbeat(client, other, {**c2, "lease_id": hex32()}), 409, "lease_lost")
    error_of(complete(client, other, {**c2, "lease_id": c["lease_id"]}, fixture_manifest("manifest-panorama.json", c2)), 409, "lease_lost")
    error_of(heartbeat(client, other, {**c2, "job": {"job_id": hex32()}}), 404, "not_found")
    # 5.10 validation, then a retryable failure requeues and repeats safely.
    bad = client.post(f"/workers/jobs/{rec['job_id']}/fail", json={"lease_id": c2["lease_id"], "code": "oops"}, headers=wk(other))
    error_of(bad, 422, "validation_failed")
    body = {"lease_id": c2["lease_id"], "code": "render_crash", "message": "GPU reset", "retryable": True, "log_tail": "x" * 70_000}
    first = client.post(f"/workers/jobs/{rec['job_id']}/fail", json=body, headers=wk(other))
    assert first.status_code == 200 and first.json()["state"] == "queued" and first.json()["attempts"] == 2
    again = client.post(f"/workers/jobs/{rec['job_id']}/fail", json=body, headers=wk(other))
    assert again.status_code == 200 and again.json()["attempts"] == 2
    from app.storage import get_store

    tail = get_store().stat(f"jobs/{rec['job_id']}/log-tail.txt")
    assert tail is not None and tail.bytes == 64 * 1024
    # A revoked name can be issued again; a live one cannot.
    error_of(client.post("/admin/workers", json={"name": "gpu-eu-01", "kinds": ["tiles"]}, headers=adm), 409, "conflict")
    assert issue_worker(client, adm, name="pc-rtx") != token


def test_jobs_expire_after_24h(client, setup, monkeypatch):
    clk = Clock(monkeypatch)
    a = setup["a"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    clk.advance(hours=23)
    run("render.jobs.expire", clk.at)
    assert job(client, rj(a), rec["job_id"])["state"] == "queued"
    clk.advance(hours=1, seconds=1)
    run("render.jobs.expire", clk.at)
    end = job(client, rj(a), rec["job_id"])
    assert end["state"] == "expired" and end["finished_at"] and end["cost_units"] is None
    assert claim(client, setup["token"]).status_code == 204


def test_jobs_overage_metered_when_allowed(client, setup, monkeypatch):
    from app.billing import providers

    clk = Clock(monkeypatch)
    a, token = setup["a"], setup["token"]
    studio(a.user_id)
    with SessionLocal() as db:
        metering.record(db, "user", a.user_id, "cu", Decimal("599.0"), clk.at.date())
        db.commit()
    error_of(submit(client, rj(a), project_id=setup["pid"], at_seq=setup["head"]), 403, "quota_exceeded")
    # The cap is a session setting, 0 to 100000.
    error_of(client.put("/jobs/usage/overage", json={"cap_cu": -1}, headers=rj(a.session)), 422, "validation_failed")
    error_of(client.put("/jobs/usage/overage", json={"cap_cu": 50}, headers=rj(a)), 403, "session_required")
    error_of(client.put("/jobs/usage/overage", json={"cap_cu": 50}, headers=RJ), 401, "unauthenticated")
    set_cap = client.put("/jobs/usage/overage", json={"cap_cu": 50}, headers=rj(a.session))
    assert set_cap.status_code == 200 and set_cap.json()["overage"] == {
        "allowed": True, "cap_cu": 50.0, "used_cu": 0.0, "price_minor": 10, "currency": "GBP"
    }
    assert submit(client, rj(a), project_id=setup["pid"], at_seq=setup["head"]).status_code == 201
    finish(client, token, claimed(client, token), wall_s=600)  # 10 cu
    assert client.get("/jobs/usage", headers=rj(a)).json()["overage"]["used_cu"] == 9.0
    calls = []

    class Fake:
        def enabled(self):
            return True

        def charge_usage(self, db, sub, metric, quantity, unit_amount_minor, description):
            calls.append((sub.provider, metric, quantity, unit_amount_minor, description))
            return "txn_overage_1"

    monkeypatch.setattr(providers, "get_provider", lambda name, settings=None: Fake())
    month = clk.at.strftime("%Y-%m")
    start, end = quotas.month_bounds(clk.at)
    clk.at = clk.at.replace(day=1) + timedelta(days=32)  # into the next month
    run("render.overage.charge", clk.at)
    run("render.overage.charge", clk.at)
    with SessionLocal() as db:
        rows = db.scalars(select(OverageCharge)).all()
    assert len(rows) == 1 and calls == [("paddle", "cloud_cu", 9, 10, calls[0][4])]
    row = rows[0]
    assert row.month == month and float(row.cu) == 9.0 and row.amount_minor == 90 and row.currency == "GBP"
    assert row.state == "charged" and row.provider_ref == "txn_overage_1"
    # A Pro trial cannot allow overage.
    b = Person(client, "b@example.com")
    error_of(client.put("/jobs/usage/overage", json={"cap_cu": 5}, headers=rj(b.session)), 403, "plan_required")


def test_overage_pending_without_a_chargeable_provider(client, setup, monkeypatch):
    from app.models import Subscription, User

    clk = Clock(monkeypatch)
    a, token = setup["a"], setup["token"]
    studio(a.user_id)
    with SessionLocal() as db:
        sub = db.scalar(select(Subscription).where(Subscription.user_id == a.user_id, Subscription.plan == "studio"))
        sub.provider = "wayl"  # dormant: cannot charge
        quotas.set_overage_cap(db, db.get(User, a.user_id), Decimal(20))
        metering.record(db, "user", a.user_id, "cu", Decimal("595.0"), clk.at.date())
        db.commit()
    submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    finish(client, token, claimed(client, token), wall_s=630)  # 10.5 cu: 5.5 past 600
    # Lowering the cap afterwards does not rewrite the month already used.
    assert client.put("/jobs/usage/overage", json={"cap_cu": 0}, headers=rj(a.session)).status_code == 200
    clk.at = clk.at.replace(day=1) + timedelta(days=32)
    with SessionLocal() as db:
        assert overage.run(db, clk.at) == 1
        row = db.scalars(select(OverageCharge)).one()
    assert row.state == "pending" and float(row.cu) == 5.5 and row.amount_minor == 60
    with SessionLocal() as db:
        assert overage.run(db, clk.at) == 0  # pending rows wait for the owner


def test_follow_set_stops_when_its_account_leaves_the_project(client, setup):
    from .project_helpers import invite_and_accept

    a, token, pid = setup["a"], setup["token"], setup["pid"]
    b = Person(client, "b@example.com")
    invite_and_accept(client, a, pid, b, role="viewer")
    follow = submitted(client, rj(b), project_id=pid, at_seq=setup["head"], follow=True)
    finish(client, token, claimed(client, token))
    push_touch(client, a, pid, [WALL])
    queued = client.get("/jobs", params={"kind": "tiles", "state": "queued"}, headers=rj(b)).json()["jobs"]
    assert len(queued) == 1
    res = client.delete(f"/projects/{pid}/members/{b.user_id}", headers=a.web)
    assert res.status_code == 204, res.text
    # The queued update fails at its claim and the set stops; later pushes queue nothing.
    assert claim(client, token).status_code == 204
    ended = job(client, rj(b), queued[0]["job_id"])
    assert ended["state"] == "failed" and ended["error"]["code"] == "bad_input"
    push_touch(client, a, pid, [WALL])
    assert client.get("/jobs", params={"kind": "tiles", "state": "queued"}, headers=rj(b)).json()["jobs"] == []
    assert job(client, rj(b), follow["job_id"])["follow"] is False


def test_follow_set_coalesce_keeps_doc_version_and_stale_sets_render_everything(client, setup):
    a, token, pid = setup["a"], setup["token"], setup["pid"]
    submitted(client, rj(a), project_id=pid, at_seq=setup["head"], follow=True)
    finish(client, token, claimed(client, token))
    push_touch(client, a, pid, [WALL])
    push_touch(client, a, pid, [hex32()], delta_format="o5/54")
    queued = client.get("/jobs", params={"kind": "tiles", "state": "queued"}, headers=rj(a)).json()["jobs"]
    assert len(queued) == 1
    with SessionLocal() as db:
        assert db.get(RenderJob, queued[0]["job_id"]).doc_version_needed == 54
    assert claim(client, token, doc_version_max=38).status_code == 204
    # It fails for good: the edits it carried went unrendered, so the next update renders every face.
    c = claimed(client, token, doc_version_max=54)
    res = client.post(
        f"/workers/jobs/{c['job']['job_id']}/fail",
        json={"lease_id": c["lease_id"], "code": "engine_error", "message": "x", "retryable": False},
        headers=wk(token),
    )
    assert res.status_code == 200 and res.json()["state"] == "failed"
    push_touch(client, a, pid, [WALL])
    nxt = client.get("/jobs", params={"kind": "tiles", "state": "queued"}, headers=rj(a)).json()["jobs"]
    assert len(nxt) == 1 and nxt[0]["changed_count"] == 0


def test_render_autoscale_static_pool(client, setup, monkeypatch):
    clk = Clock(monkeypatch)
    assert pools.want(0, 0, 0, 0, 4) == 0
    assert pools.want(5, 0, 10, 0, 4) == 2
    assert pools.want(5, 0, 31, 0, 4) == 3
    assert pools.want(20, 2, 0, 0, 4) == 4
    assert pools.want(0, 0, 0, 1, 4) == 1
    a, adm = setup["a"], setup["admin"]
    issue_worker(client, adm, name="gpu-2")
    issue_worker(client, adm, name="gpu-3")

    def states() -> dict:
        with SessionLocal() as db:
            return {w.worker_id: w.pool_state for w in db.scalars(select(Worker))}

    clk.advance(minutes=11)
    run("render.autoscale", clk.at)
    assert set(states().values()) == {"stopped"} and pools.DESIRED["gpu-std"] == 0
    ids = [submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])["job_id"] for _ in range(5)]
    clk.advance(seconds=31)
    run("render.autoscale", clk.at)
    assert pools.DESIRED["gpu-std"] == 3 and list(states().values()).count("running") == 3
    monkeypatch.setattr(get_settings(), "render_pool_max", 2)
    run("render.autoscale", clk.at)
    assert pools.DESIRED["gpu-std"] == 2
    for job_id in ids:
        client.post(f"/jobs/{job_id}/cancel", headers=rj(a))
    run("render.autoscale", clk.at)
    assert list(states().values()).count("running") == 3  # not idle 10 minutes yet
    clk.advance(minutes=10)
    run("render.autoscale", clk.at)
    assert set(states().values()) == {"stopped"}
    # A stopped hand-run machine that claims is up again.
    claim(client, setup["token"])
    assert states()["pc-rtx"] == "running"
    with pytest.raises(RuntimeError):
        pools.get_pool("cloud")


def test_tiles_served_immutable(client, setup):
    a, token = setup["a"], setup["token"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    finish(client, token, claimed(client, token))
    out = client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a)).json()
    sha = out["views"][0]["faces"]["e"]["tiles"][1][3]
    res = client.get(f"/tiles/{sha}.jpg", headers={"Origin": "https://phone.example"})
    assert res.status_code == 200 and res.content == tile_bytes(sha)
    assert res.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert res.headers["Access-Control-Allow-Origin"] == "*" and res.headers["Content-Type"] == "image/jpeg"
    assert client.get(f"/tiles/{'0' * 64}.jpg").status_code == 404
    assert client.get("/tiles/not-a-tile.png").status_code == 404
    # The manifest is private: only its account reads it, never cached.
    manifest = client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a))
    assert manifest.headers["Cache-Control"] == "private, no-store"
    error_of(client.get(f"/jobs/{rec['job_id']}/output", headers=rj(Person(client, "b@example.com"))), 404, "not_found")
    # The upload's copies went once the tiles were public.
    from app.uploads.models import Blob

    # The upload's copies wait for uploads.expire (nothing holds them).
    shas = {sha for face in out["views"][0]["faces"].values() for row in face["tiles"] for sha in row}
    with SessionLocal() as db:
        kept = db.query(Blob).filter(Blob.sha256.in_(shas)).all()
        assert kept and all(b.refs == 0 for b in kept)


# --- PF6 extras: the claim race, gc, the live share, admin, the queue depth ----------------


def test_claim_is_atomic_under_concurrency(client, setup):
    a, adm = setup["a"], setup["admin"]
    submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    tokens = [(f"gpu-{i}", issue_worker(client, adm, name=f"gpu-{i}")) for i in range(6)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(lambda nt: claim(client, nt[1], worker_id=nt[0]).status_code, tokens))
    assert sorted(codes) == [200] + [204] * 5


@pytest.mark.postgres
def test_claim_is_atomic_postgres():
    """The same race on Postgres (TEST_DATABASE_URL): SKIP LOCKED plus the
    conditional update hand each of 40 jobs to exactly one of 8 workers."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.database import init_db
    from app.licence import clock as lclock

    from .conftest import TEST_DATABASE_URL

    engine = create_engine(TEST_DATABASE_URL, pool_size=10, max_overflow=0)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    init_db(bind=engine)
    make = sessionmaker(bind=engine)
    now = lclock.now()
    with make() as db:
        for i in range(8):
            db.add(Worker(worker_id=f"w{i}", token_hash=f"{i:064x}", kinds=["panorama"], worker_class="gpu-std"))
        for i in range(40):
            db.add(
                RenderJob(
                    job_id=f"{i:032x}", account_id=1, kind="panorama", worker_class="gpu-std", state="queued",
                    views=[VIEW], changed=[], inputs={}, params={}, created_at=now, queued_at=now, updated_at=now,
                )
            )
        db.commit()

    def worker(i: int) -> list[str]:
        got = []
        with make() as db:
            w = db.get(Worker, f"w{i}")
            while (job_id := queue.try_claim(db, w, ["panorama"], 38, now)) is not None:
                got.append(job_id)
        return got

    with ThreadPoolExecutor(max_workers=8) as pool:
        taken = [j for got in pool.map(worker, range(8)) for j in got]
    assert sorted(taken) == [f"{i:032x}" for i in range(40)]
    engine.dispose()


def test_tiles_gc_keeps_named_tiles(client, setup, monkeypatch):
    from app.storage import get_store

    a, token = setup["a"], setup["token"]
    submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    finish(client, token, claimed(client, token))
    store = get_store()
    store.put("tiles/" + "f" * 64 + ".jpg", b"orphan", content_type="image/jpeg")
    named = len(store.list("tiles/")) - 1
    clk = Clock(monkeypatch)
    clk.advance(days=2)
    run("render.tiles.gc", clk.at)
    left = store.list("tiles/")
    assert len(left) == named and all("f" * 64 not in t.key for t in left)
    clk.advance(days=91)
    run("render.tiles.gc", clk.at)
    assert store.list("tiles/") == []


def test_share_live_follows_the_set(client, setup):
    a, token, pid = setup["a"], setup["token"], setup["pid"]
    error_of(client.get("/s/k3J9xQ2aTf/live", headers={"X-Truebex-Contract": "share-bundle/1.0"}), 404, "not_found")
    follow = submitted(client, rj(a), project_id=pid, at_seq=setup["head"], follow=True)
    finish(client, token, claimed(client, token))
    shares = {"k3J9xQ2aTf": {"account_id": a.user_id, "manifest": {"panoramas": [{"id": "p1", "live_job_id": follow["job_id"]}]}}}

    def resolver(db, slug):
        if slug not in shares:
            from app.contract_http import ContractError

            raise ContractError("not_found", 404, "No such share.")
        return shares[slug]

    live.set_share_resolver(resolver)
    first = client.get("/s/k3J9xQ2aTf/live")
    assert first.status_code == 200 and first.headers["Cache-Control"] == "no-store"
    data = first.json()
    assert data["following"] is True and data["job_id"] == follow["job_id"]
    assert data["manifest"]["tiles_base"] == "http://testserver/tiles" and data["manifest"]["faces_rendered"] == 6
    got: dict = {}

    def wait() -> None:
        got["res"] = client.get("/s/k3J9xQ2aTf/live", params={"rev": data["rev"], "wait_s": 10})

    t = threading.Thread(target=wait)
    t.start()
    push_touch(client, a, pid, [WALL])
    finish(client, token, claimed(client, token), "manifest-tiles.json", wall_s=20)
    t.join(10)
    moved = got["res"].json()
    assert moved["rev"] > data["rev"] and moved["manifest"]["faces_rendered"] == 2
    # Only the share's own account's set; another panorama id is not live.
    shares["k3J9xQ2aTf"]["account_id"] = a.user_id + 1000
    error_of(client.get("/s/k3J9xQ2aTf/live"), 404, "not_found")
    error_of(client.get("/s/k3J9xQ2aTf/live", params={"wait_s": 30}), 422, "validation_failed")


def test_admin_render_overview_and_auth(client, setup):
    a, adm, token = setup["a"], setup["admin"], setup["token"]
    submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    view = client.get("/admin/render", headers=adm)
    assert view.status_code == 200
    body = view.json()
    pano = next(q for q in body["queue"] if q["kind"] == "panorama")
    assert pano["queued"] == 1 and pano["oldest_wait_s"] is not None
    assert body["workers"][0]["worker_id"] == "pc-rtx" and "token" not in body["workers"][0]
    finish(client, token, claimed(client, token))
    body = client.get("/admin/render", headers=adm).json()
    assert body["cost_by_kind"] == {"panorama": 1.5} and body["workers"][0]["last_heartbeat_at"]
    pool = body["pool"]["classes"][0]
    assert pool["class"] == "gpu-std" and pool["machines"] == 1 and pool["running"] == 0 and pool["queued"] == 0
    assert client.get("/admin/workers", headers=adm).json()["workers"][0]["kinds"] == ["pack", "panorama", "tiles"]
    assert client.get("/admin/render", headers=a.session).status_code == 403
    assert client.get("/admin/render").status_code == 401
    assert client.post("/admin/workers", json={"name": "x", "kinds": ["tiles"]}, headers=a.session).status_code == 403
    error_of(client.post("/admin/workers", json={"name": "Bad Name!", "kinds": ["tiles"]}, headers=adm), 422, "validation_failed")
    error_of(client.post("/admin/workers", json={"name": "ok", "kinds": ["movies"]}, headers=adm), 422, "validation_failed")
    error_of(client.post("/admin/workers", json={"name": "ok", "kinds": ["tiles"], "class": "gpu-huge"}, headers=adm), 422, "validation_failed")
    error_of(client.delete("/admin/workers/nobody", headers=adm), 404, "not_found")


def test_upload_add_files_only_to_job_output(client, setup):
    a, token = setup["a"], setup["token"]
    submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    snap = client.post(
        "/uploads", json={"purpose": "snapshot", "files": [{"sha256": "b" * 64, "bytes": 3, "content_type": "application/octet-stream"}]},
        headers={**a.dev, **UPLOADS},
    ).json()
    res = client.post(
        "/uploads",
        json={"purpose": "snapshot", "upload_id": snap["upload_id"], "files": [{"sha256": "c" * 64, "bytes": 3, "content_type": "application/octet-stream"}]},
        headers={**a.dev, **UPLOADS},
    )
    error_of(res, 422, "validation_failed")
    # Another credential cannot add to the worker's session.
    res = client.post(
        "/uploads",
        json={"purpose": "job-output", "upload_id": c["output_upload"]["upload_id"], "files": [{"sha256": "c" * 64, "bytes": 3, "content_type": "image/jpeg"}]},
        headers={**a.dev, **UPLOADS},
    )
    error_of(res, 404, "not_found")
    shas = rendered_tiles(fixture_manifest("manifest-panorama.json", c))
    opened = upload_outputs(client, token, c, shas[:2])
    assert [f["sha256"] for f in opened["files"]] == shas[:2]
    status = client.get(f"/uploads/{opened['upload_id']}", headers={"Authorization": f"Bearer {token}", **UPLOADS}).json()
    assert all(f["state"] == "complete" for f in status["files"]) and len(status["files"]) == 2


def test_queue_depth_command_and_host_script(client, setup, capsys):
    from pathlib import Path

    from app.render import depth

    submitted(client, rj(setup["a"]), project_id=setup["pid"], at_seq=setup["head"])
    assert depth.queued() == 1
    assert depth.main() == 0 and capsys.readouterr().out.strip() == "1"
    root = Path(__file__).resolve().parents[2]
    script = (root / "infra" / "host" / "bin" / "queue-depth").read_text("utf-8")
    assert "python -m app.render.depth" in script and "\r" not in script
    deploy = (root / "infra" / "deploy.ps1").read_text("utf-8")
    assert "infra/host/bin/queue-depth" in deploy


def test_fixture_manifests_follow_the_rules():
    from types import SimpleNamespace

    from app.render import tiles

    pano = json.loads((FIX / "manifest-panorama.json").read_text("utf-8"))
    part = json.loads((FIX / "manifest-tiles.json").read_text("utf-8"))
    for m, kind in ((pano, "panorama"), (part, "tiles")):
        job_ = SimpleNamespace(job_id=m["job_id"], project_id=m["project_id"], at_seq=m["at_seq"], views=[VIEW], kind=kind)
        assert tiles.check_manifest(m, job_) == []
    every = tiles.all_tiles(pano) | tiles.all_tiles(part)
    assert every == {p.stem for p in (FIX / "tiles").iterdir()}
    assert len(tiles.all_tiles(pano)) == 30 and part["faces_rendered"] == 2 and part["faces_reused"] == 4
