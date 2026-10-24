"""PF6b: a stopped worker's claim takes no job (contract render-jobs 1.1.0, 5.7
and §6.4).

The claim long poll checks that its worker is still connected before every
try. A job claimed for a worker that went away in between goes back to the
queue as it was, with no attempt spent (`queue.unclaim`). A worker stopped
with Ctrl+C mid poll ends at once, so its connection closes. And the claim's
wake-up (`notify_claim`) is proved by the wake-up, on PF14e's recipe
(`wakeups`, `LongPoll`).

Starlette's TestClient never reports a disconnect while a request is open, so
the gone-worker tests run the app on a real port (uvicorn in a thread, as
`test_pf12_openapi_sdks.py`'s `live_api`) and close a real socket.
"""

import http.client
import json
import logging
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.licence import clock
from app.projects import waiters
from app.render import live, pools, queue
from app.render.models import RenderJob, Worker
from app.uploads.models import UploadSession

from .conftest import LongPoll
from .licence_helpers import error_of
from .project_helpers import Person
from .render_helpers import (
    APP_PROJECT,
    RJ,
    admin,
    claim,
    claimed,
    finish,
    heartbeat,
    issue_worker,
    job,
    project,
    rj,
    submitted,
)

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "worker" / "truebex_worker.py"
# render_helpers.claim's body, for the requests sent over a real port.
CLAIM = {"worker_id": "pc-rtx", "kinds": ["panorama", "tiles", "pack"], "app_version": "1.1.0", "doc_version_max": 38}
CLAIM_LOG = "truebex.render.claim"


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
    """A Pro-trial designer with the app's project (two operations) and a worker."""
    a = Person(client, "a@example.com")
    pid, head = project(client, a, project_id=APP_PROJECT)
    token = issue_worker(client, admin(client))
    return {"a": a, "pid": pid, "head": head, "token": token}


def _until(cond, what: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while not cond():
        assert time.monotonic() < deadline, what
        time.sleep(0.01)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LiveApi:
    def __init__(self, server, port: int) -> None:
        self.server = server
        self.port = port
        self.url = f"http://127.0.0.1:{port}"

    def connections(self) -> int:
        """Open HTTP connections: uvicorn drops one when it sees the client go."""
        return len(self.server.server_state.connections)


@pytest.fixture()
def live_api(client):
    """The test app on a real port, so a closed socket reaches it as a disconnect."""
    import uvicorn

    from app.main import app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _until(lambda: server.started, "the live API did not start")
    yield LiveApi(server, port)
    server.should_exit = True
    thread.join(timeout=10)


def _claim_request(token: str, wait_s: float) -> bytes:
    body = json.dumps({**CLAIM, "wait_s": wait_s}).encode()
    head = (
        "POST /workers/claim HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        f"Authorization: Bearer {token}\r\nX-Truebex-Contract: {RJ['X-Truebex-Contract']}\r\n"
        f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
    )
    return head.encode() + body


def http_claim(api: LiveApi, token: str, wait_s: float) -> tuple[int, dict | None]:
    """5.7 over a real connection that stays open until the answer."""
    conn = http.client.HTTPConnection("127.0.0.1", api.port, timeout=wait_s + 30)
    try:
        conn.request(
            "POST", "/workers/claim", body=json.dumps({**CLAIM, "wait_s": wait_s}),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", **RJ},
        )
        res = conn.getresponse()
        data = res.read()
        return res.status, (json.loads(data) if data else None)
    finally:
        conn.close()


def row(job_id: str) -> RenderJob:
    with SessionLocal() as db:
        found = db.get(RenderJob, job_id)
        db.expunge(found)
        return found


def assert_queued_as_new(r: RenderJob) -> None:
    assert r.state == "queued", f"the job is {r.state} for {r.worker_id}: a gone worker's claim took it"
    assert (r.attempts, r.lease_id, r.lease_expires_at, r.worker_id, r.claimed_at) == (0, None, None, None, None)
    assert r.message == "" and r.error is None and r.output_upload_id is None


# --- the wake-up (PF14e's recipe; PF14e's carry-over) ------------------------------------


def test_claim_long_poll_woken_by_a_submit(client, setup, wakeups):
    a, token = setup["a"], setup["token"]
    # Nothing queued: only the deadline ends the claim, with 204.
    empty = LongPoll(lambda: claim(client, token, wait_s=1))
    res = empty.answer()
    assert res.status_code == 204 and res.headers["X-Truebex-Contract"] == "render-jobs/1.2"
    wakeups.assert_deadline(queue.CLAIM_KEY)
    assert empty.took >= 0.9
    wakeups.clear()
    # A job submitted while the claim waits (the route's longest wait) wakes it.
    poll = LongPoll(lambda: claim(client, token, wait_s=queue.CLAIM_WAIT_MAX_S))
    wakeups.until_waiting(queue.CLAIM_KEY)
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    res = poll.answer()
    assert res.status_code == 200, res.text
    assert res.json()["job"]["job_id"] == rec["job_id"] and res.json()["job"]["attempts"] == 0
    wakeups.assert_woken(queue.CLAIM_KEY, "the submit")
    assert poll.took < queue.CLAIM_WAIT_MAX_S / 2


def test_claim_without_notify_claim_waits_to_its_deadline(client, setup, wakeups, monkeypatch):
    """The test above fails without the wake-up: with notify_claim a no-op, the
    waiting claim finds the job only at its deadline, and `assert_woken` says so."""
    a, token = setup["a"], setup["token"]
    plain = waiters.notify
    monkeypatch.setattr(waiters, "notify", lambda key: None if key == queue.CLAIM_KEY else plain(key))
    poll = LongPoll(lambda: claim(client, token, wait_s=2))
    wakeups.until_waiting(queue.CLAIM_KEY)
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    res = poll.answer()
    assert res.status_code == 200 and res.json()["job"]["job_id"] == rec["job_id"]
    assert poll.took >= 1.9
    assert wakeups.ended(queue.CLAIM_KEY) == [False]
    with pytest.raises(AssertionError, match="not woken by the submit"):
        wakeups.assert_woken(queue.CLAIM_KEY, "the submit")


# --- a worker that went away -----------------------------------------------------------


def test_gone_before_the_job_takes_nothing(client, setup, live_api, wakeups, caplog):
    caplog.set_level(logging.INFO, logger=CLAIM_LOG)
    a, token = setup["a"], setup["token"]
    sock = socket.create_connection(("127.0.0.1", live_api.port), timeout=30)
    sock.sendall(_claim_request(token, wait_s=10))
    wakeups.until_waiting(queue.CLAIM_KEY)
    sock.close()  # the worker stops while its claim waits
    _until(lambda: live_api.connections() == 0, "the API never saw the worker go")
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    _until(lambda: waiters.waiting_count(queue.CLAIM_KEY) == 0, "the gone worker's claim never ended")
    assert wakeups.ended(queue.CLAIM_KEY) == [True]  # the submit woke it, and it took nothing
    r = row(rec["job_id"])
    assert_queued_as_new(r)
    assert r.rev == 1  # never touched
    gone = [m for m in caplog.messages if "went away" in m]
    assert len(gone) == 1 and "pc-rtx" in gone[0] and "no job taken" in gone[0], caplog.messages
    # The worker back (or any other): its claim gets the job as a first attempt.
    status, body = http_claim(live_api, token, wait_s=0)
    assert status == 200 and body["job"]["job_id"] == rec["job_id"] and body["job"]["attempts"] == 0
    assert job(client, rj(a), rec["job_id"])["attempts"] == 0


def test_gone_after_the_claim_gives_the_job_back(client, setup, live_api, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=CLAIM_LOG)
    a, token = setup["a"], setup["token"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    before = row(rec["job_id"])
    held: dict = {}
    original = queue.prepare_claim

    def prepare_then_go(db, job_id, worker, now):
        payload = original(db, job_id, worker, now)
        if payload is not None and "sock" in held:
            held["payload"] = payload
            held.pop("sock").close()  # the worker goes right after the job is claimed for it
            _until(lambda: live_api.connections() == 0, "the API never saw the worker go")
        return payload

    monkeypatch.setattr(queue, "prepare_claim", prepare_then_go)
    sock = socket.create_connection(("127.0.0.1", live_api.port), timeout=30)
    held["sock"] = sock
    sock.sendall(_claim_request(token, wait_s=0))
    _until(lambda: "payload" in held and waiters.waiting_count(queue.CLAIM_KEY) == 0, "the claim never ended")
    c = held["payload"]
    assert c["job"]["job_id"] == rec["job_id"]
    r = row(rec["job_id"])
    assert_queued_as_new(r)
    assert clock.aware(r.queued_at) == clock.aware(before.queued_at)  # it keeps its place
    assert r.rev == before.rev + 2  # claimed, then given back
    assert r.base_job_id == before.base_job_id and r.cancel_requested is False
    with SessionLocal() as db:
        assert db.get(UploadSession, c["output_upload"]["upload_id"]) is None
        assert db.get(Worker, "pc-rtx").idle_since is not None
    gone = [m for m in caplog.messages if "went away" in m]
    assert len(gone) == 1 and "pc-rtx" in gone[0] and rec["job_id"] in gone[0], caplog.messages
    rec_now = job(client, rj(a), rec["job_id"])
    assert rec_now["state"] == "queued" and rec_now["attempts"] == 0 and "Trying again" not in rec_now["message"]
    # The next claim gets it as a first attempt, on a new lease and a new upload.
    status, body = http_claim(live_api, token, wait_s=0)
    assert status == 200 and body["job"]["job_id"] == rec["job_id"] and body["job"]["attempts"] == 0
    assert body["lease_id"] != c["lease_id"]
    assert body["output_upload"]["upload_id"] != c["output_upload"]["upload_id"]
    # The lost lease is no lease: 5.8 with it answers lease_lost.
    error_of(heartbeat(client, token, c), 409, "lease_lost")


def test_worker_stopped_mid_poll_closes_its_connection(client, setup, live_api, wakeups, tmp_path):
    """Ctrl+C on the worker while its claim waits: the worker ends at once, so
    its connection closes and the claim takes nothing. `_thread.interrupt_main`
    is Ctrl+C as Windows delivers it: a flag the main thread sees only when it
    runs Python again, never a wake-up of a blocked socket read."""
    a, token = setup["a"], setup["token"]
    (tmp_path / "worker.toml").write_text(
        f'api = "{live_api.url}"\ntoken = "{token}"\nworker_id = "pc-rtx"\nkinds = ["panorama", "tiles", "pack"]\n'
        f'work_dir = "{(tmp_path / "jobs").as_posix()}"\napp_version = "1.1.0"\ndoc_version_max = 38\nwait_s = 20\n',
        encoding="utf-8",
    )
    script = (
        "import importlib.util, sys, threading, time, _thread\n"
        "spec = importlib.util.spec_from_file_location('truebex_worker', sys.argv[1])\n"
        "W = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(W)\n"
        "def press():\n"
        "    sys.stdin.readline()\n"
        "    _thread.interrupt_main()\n"
        "threading.Thread(target=press, daemon=True).start()\n"
        "t0 = time.monotonic()\n"
        "code = W.main(['--config', sys.argv[2]])\n"
        "print(f'worker exit {code} after {time.monotonic() - t0:.1f} s', flush=True)\n"
        "sys.exit(code)\n"
    )
    # The base interpreter: a venv's python.exe is a launcher, whose child would outlive a kill.
    python = getattr(sys, "_base_executable", None) or sys.executable
    proc = subprocess.Popen(
        [python, "-c", script, str(WORKER), str(tmp_path / "worker.toml")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        wakeups.until_waiting(queue.CLAIM_KEY)
        proc.stdin.write("\n")
        proc.stdin.flush()  # Ctrl+C
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pytest.fail("the worker was still waiting on its claim 10 s after Ctrl+C (its socket read ignores it)")
        assert proc.returncode == 0 and "worker exit 0" in out, out
        _until(lambda: live_api.connections() == 0, "the API never saw the worker go")
        rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
        _until(lambda: waiters.waiting_count(queue.CLAIM_KEY) == 0, "the gone worker's claim never ended")
        assert_queued_as_new(row(rec["job_id"]))
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=10)


# --- a worker that stays connected ------------------------------------------------------


def test_connected_worker_over_a_real_port(client, setup, live_api, wakeups):
    a, token = setup["a"], setup["token"]
    status, body = http_claim(live_api, token, wait_s=1)
    assert status == 204 and body is None
    wakeups.assert_deadline(queue.CLAIM_KEY)
    wakeups.clear()
    poll = LongPoll(lambda: http_claim(live_api, token, wait_s=queue.CLAIM_WAIT_MAX_S))
    wakeups.until_waiting(queue.CLAIM_KEY)
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    status, body = poll.answer()
    assert status == 200 and body["job"]["job_id"] == rec["job_id"] and body["job"]["attempts"] == 0
    wakeups.assert_woken(queue.CLAIM_KEY, "the submit")
    r = row(rec["job_id"])
    assert r.state == "claimed" and r.worker_id == "pc-rtx" and r.lease_id == body["lease_id"]


def test_connected_run_is_queued_claimed_running_succeeded(client, setup, wakeups, monkeypatch):
    a, token = setup["a"], setup["token"]
    seen: list[tuple[str, str]] = []
    plain = queue.notify_job

    def notify_job(*job_ids):
        with SessionLocal() as db:
            for job_id in job_ids:
                found = db.get(RenderJob, job_id) if job_id else None
                if found is not None:
                    seen.append((job_id, found.state))
        plain(*job_ids)

    monkeypatch.setattr(queue, "notify_job", notify_job)
    poll = LongPoll(lambda: claim(client, token, wait_s=queue.CLAIM_WAIT_MAX_S))
    wakeups.until_waiting(queue.CLAIM_KEY)
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    res = poll.answer()
    assert res.status_code == 200, res.text
    c = res.json()
    assert heartbeat(client, token, c, 0.4, "face e").status_code == 200
    assert heartbeat(client, token, c, 0.8, "face u").status_code == 200
    finish(client, token, c)
    states = [rec["state"]] + [state for job_id, state in seen if job_id == rec["job_id"]]
    states = [s for i, s in enumerate(states) if i == 0 or s != states[i - 1]]
    assert states == ["queued", "claimed", "running", "succeeded"]
    end = job(client, rj(a), rec["job_id"])
    assert end["state"] == "succeeded" and end["attempts"] == 0 and "Trying again" not in end["message"]


# --- queue.unclaim ----------------------------------------------------------------------


def test_unclaim_only_while_claimed_under_that_lease(client, setup):
    a, token = setup["a"], setup["token"]
    first = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    assert heartbeat(client, token, c).status_code == 200  # running: the worker has it
    with SessionLocal() as db:
        assert queue.unclaim(db, first["job_id"], c["lease_id"], clock.now()) is False
    r = row(first["job_id"])
    assert r.state == "running" and r.lease_id == c["lease_id"] and r.worker_id == "pc-rtx"
    finish(client, token, c)
    with SessionLocal() as db:
        assert queue.unclaim(db, first["job_id"], c["lease_id"], clock.now()) is False  # succeeded
    assert row(first["job_id"]).state == "succeeded"
    second = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c2 = claimed(client, token)
    with SessionLocal() as db:
        assert queue.unclaim(db, second["job_id"], "0" * 32, clock.now()) is False  # another lease
        assert queue.unclaim(db, "f" * 32, c2["lease_id"], clock.now()) is False  # no such job
    r = row(second["job_id"])
    assert r.state == "claimed" and r.lease_id == c2["lease_id"]
    with SessionLocal() as db:
        assert queue.unclaim(db, second["job_id"], c2["lease_id"], clock.now()) is True
        assert queue.unclaim(db, second["job_id"], c2["lease_id"], clock.now()) is False  # once
    assert_queued_as_new(row(second["job_id"]))
    error_of(heartbeat(client, token, c2), 409, "lease_lost")
    again = claimed(client, token)
    assert again["job"]["job_id"] == second["job_id"] and again["job"]["attempts"] == 0


def test_unclaim_after_a_cancel_ends_it_cancelled(client, setup):
    """A cancel asked while the job was claimed wins: the job ends cancelled at
    no charge, not queued again, and no attempt is spent."""
    a, token = setup["a"], setup["token"]
    rec = submitted(client, rj(a), project_id=setup["pid"], at_seq=setup["head"])
    c = claimed(client, token)
    asked = client.post(f"/jobs/{rec['job_id']}/cancel", headers=rj(a))
    assert asked.status_code == 200 and asked.json()["state"] == "claimed"
    with SessionLocal() as db:
        assert queue.unclaim(db, rec["job_id"], c["lease_id"], clock.now()) is True
    end = job(client, rj(a), rec["job_id"])
    assert end["state"] == "cancelled" and end["attempts"] == 0 and end["cost_units"] is None
    with SessionLocal() as db:
        assert db.get(UploadSession, c["output_upload"]["upload_id"]) is None
    assert heartbeat(client, token, c).json()["cancel"] is True  # that lease is told to stop
    assert claim(client, token).status_code == 204
