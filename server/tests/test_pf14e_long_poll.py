"""PF14e: the long-poll wake-up tests are proved by the wake-up, not by a clock.

The rewritten tests (PF6's job status and share live view, the PF5 x PF6
published share, PF4's pull, PF12a's /v1 panorama read and the PF9 x PF12
meet) take the `wakeups` fixture (conftest.py): the 1 s re-check is patched
above the wait, the read starts with the route's longest wait_s, the change is
made once the read is inside its wait, and `assert_woken` checks that a notify
ended every wait. These guards show that check catches a missing wake-up: an
answer that carries the change can still come from the deadline (which reads
the job again) or from a read that never waited."""

import pytest

from app.projects import presence, waiters
from app.render import pools, queue

from .conftest import LongPoll
from .project_helpers import Person, create, delta_op, hex32, pull, pushed
from .render_helpers import admin, claimed, heartbeat, issue_worker, job, project, rj, submitted

WAIT_S = 5.0  # short for a guard: the heartbeat lands well inside it even on a starved CPU


@pytest.fixture(autouse=True)
def _clean_state():
    waiters.reset()
    presence.reset()
    pools.DESIRED.clear()
    yield
    waiters.reset()
    presence.reset()


def test_long_poll_without_wakeup_ends_at_its_deadline(client, wakeups, monkeypatch):
    monkeypatch.setattr(waiters, "notify", lambda key: None)  # no wake-up reaches any read
    a = Person(client, "a@example.com")
    pid, head = project(client, a)
    token = issue_worker(client, admin(client))
    rec = submitted(client, rj(a), project_id=pid, at_seq=head)
    c = claimed(client, token)
    rev = job(client, rj(a), rec["job_id"])["rev"]
    key = queue.job_key(rec["job_id"])

    reader = LongPoll(lambda: client.get(f"/jobs/{rec['job_id']}", params={"rev": rev, "wait_s": WAIT_S}, headers=rj(a)))
    wakeups.until_waiting(key)
    assert heartbeat(client, token, c, 0.3).status_code == 200
    res = reader.answer()
    # The answer carries the moved rev all the same: the deadline reads the job again.
    assert res.status_code == 200 and res.json()["rev"] > rev
    # But its one wait ran to the deadline (the patched re-check did not end it early).
    assert wakeups.ended(key) == [False]
    assert reader.took >= WAIT_S - 0.1
    with pytest.raises(AssertionError, match="the read was not woken by the heartbeat"):
        wakeups.assert_woken(key, "the heartbeat")


def test_read_answered_without_waiting_is_not_a_wakeup(client, wakeups):
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()])])

    # The push came first: the pull answers from its read and never waits.
    page = pull(client, a.dev, pid, after=0, wait_s=25)
    assert [op["server_seq"] for op in page["ops"]] == [1]
    assert wakeups.ended(pid) == []
    with pytest.raises(AssertionError, match="the read was not woken by the push"):
        wakeups.assert_woken(pid, "the push")
