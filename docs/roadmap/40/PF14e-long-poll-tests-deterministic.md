# PF14e — Long-poll wake-up tests proved by the wake-up, not by a sub-second clock (launch priority 2)

**Needs merged:** PF4 (the pull's long poll), PF6 (the job status and the share live view), PF12a (the /v1 panorama read and its `_until_waiting`), PF14b (`timing_window()`); all on `master` 55d9c84. **Unblocks:** a verify gate that stays green while another workspace's gate shares the PC (T60, 12 Oct). **Contract:** none. No endpoint, response or app code changes; tests and one test runner only.

## Status

**Built (2026-10-13, branch `ap/t67-pf14e-long-poll-wake-up-tests-pr`, Autopilot T67); see As-built.** Checked on `master` 55d9c84 before the work began. Every long poll loops on `waiter.wait(min(waiters.RECHECK_S, remaining))`, with `RECHECK_S = 1.0` (`server/app/projects/waiters.py:18`): `routers/jobs.py:183` (`get_job`), `routers/tiles.py:100` (`share_live`), `routers/projects.py:237` (`pull_ops`), `routers/mobile.py:89` (`panorama_set`, which `/v1` calls), `routers/workers.py:128` (the worker claim). A deadline answer reads again, so it carries a change made meanwhile.

| Test (master 55d9c84) | What it checked | Why it was weak |
|---|---|---|
| `test_render.py::test_jobs_status_long_poll_rev` | `time.sleep(0.5)`, heartbeat, `got["done"] - sent < 1.0 and got["took"] < 5` (wait_s 10), inside `timing_window()` | The 1 s re-check answers about 0.5 s after `sent` with no notify at all. It passed 10 of 10 runs with `waiters.notify` a no-op. It failed T60's gate when pytest had about 0.4 of a core. |
| `test_render.py::test_share_live_follows_the_set` | reader started, push + claim + finish, `t.join(10)`, rev moved and two faces | The reader was not awaited. Under load `t.join(10)` could end first (`KeyError` on `got["res"]`), or the reader could start after the change and never exercise the wake-up. It also failed T60's gate. It passed with `waiters.notify` a no-op (the re-check found the rev). |
| `test_render_shares.py::test_published_share_follows_the_set` (about line 93) | the same through PF5's real share | the same as above |
| `test_pf9_pf12_meet.py::test_key_reads_a_followed_set_after_its_own_edit` (about line 220) | reader started, finish, `t.join(15)`, rev 2 | the same; passed with `waiters.notify` a no-op |
| `test_projects.py::test_pull_long_poll_wakes_on_push` | waited for the waiter, push, `got["at"] - pushed_at < 1.0`, inside `timing_window()`; an empty pull `0.9 <= t < 3` | With no notify the re-check answers about 1.000 s after the push. It passed 1 of 10 runs with `waiters.notify` a no-op (a coin flip on Windows' 15.6 ms clock). Its sub-second window could stretch under load. |
| `test_pf12a_v1_panoramas.py::test_v1_panorama_set_long_poll` | `RECHECK_S` patched to 30, `_until_waiting` (waiter registered), `got["done"] - sent < 2.0 and got["took"] < 8` (wait_s 10); `time.sleep(0.3)` before the pool check; "answered at once" `< 3` | It caught a missing wake-up (the 10 s deadline is over 8 s), but only by a clock. "Registered" does not mean "waiting": a change made before the read that follows the registration is answered by that read. |

`server/tests/conftest.py:234` `timing_window()` (PF14b) wrapped the two 1 s windows. It removed GC pauses from the window, but not CPU starvation.

## Goal

The server tests that time a long poll's wake-up pass on a starved CPU, and they still fail when the wake-up is missing. Each one proves that the push or the job change itself woke the waiting read, not that the answer came inside a sub-second window. A gate that shares the PC with another workspace's gate no longer fails on these tests. A missing `notify` fails them with a message that says the read was not woken.

## Read first

* `docs/roadmap/40/00-contract.md` (gates, the P.4 template).
* `PF14b-outbound-requests-pinned.md` As-built ("Gate fix": `timing_window()`); `PF6-cloud-render-orchestration.md` Tests (the `test_jobs_status_long_poll_rev` row); `PF12a-v1-panorama-reads.md` (the long-poll test, `RECHECK_S` patched, `_until_waiting`).
* `server/app/projects/waiters.py`; `server/app/routers/jobs.py` `get_job`, `routers/tiles.py` `share_live`, `routers/projects.py` `pull_ops` and `_after_append`, `routers/mobile.py` `panorama_set`, `server/app/render/queue.py` `notify_job`.

## Scope

**In:**

1. One shared helper in `server/tests/conftest.py`: the `wakeups` fixture. It patches `waiters.RECHECK_S` to 60 s (above every route's longest wait, 25 s) and wraps `waiters.Waiter.wait` with monkeypatch, recording each call's result by waiter key (True = woken by a notify, False = timed out). `wakeups.until_waiting(key)` is PF12a's `_until_waiting`, moved and keyed by any waiter key (a project id or `queue.job_key(...)`). `LongPoll` runs one request on its own thread with a hang guard.
2. The six tests in the Status table rewritten to one recipe: the re-check patched above the wait; the read started with the route's longest `wait_s` (25); the change made once the read is inside its wait; a 40 s hang guard that asserts the thread finished; then assert the answer carries the change AND every wait was ended by a wake-up, well before the deadline.
3. Everything else those tests assert is kept (As-built lists each check).
4. Guards: with `waiters.notify` a no-op, a waiting job-status read whose rev moves meanwhile answers the moved rev only at its deadline, and its recorded wait is False. A read answered without waiting records no wait.
5. `timing_window()` removed (nothing uses it after the rewrite).
6. `server/scripts/starved_pytest.py`: runs pytest on one core shared with a busy loop, with `--runs N` and `--no-wakeup`, for the acceptance runs and the human test.

**Out (and where it goes):**

* `test_render_worker.py`'s process-kill timing (`< 6` s after a cancel): left alone, as asked.
* `test_mobile.py::test_project_panoramas_for_members` (`wait_s` 0.2, the same rev back): it times no wake-up.
* The worker claim long poll (`/workers/claim`, `notify_claim`): no test times its wake-up today. A wake-up test for it would be a PF6 follow-up, not a rewrite.
* App code: no test exposed a bug, so nothing changed.

## Design

**API, data, UI:** none.

**The recipe** (each rewritten test):

```python
def test_x(client, wakeups):                      # RECHECK_S is 60 s for this test
    reader = LongPoll(lambda: client.get(url, params={"rev": rev, "wait_s": 25}, headers=h))
    wakeups.until_waiting(key)                    # registered AND inside Waiter.wait
    make_the_change()                             # heartbeat / push / finish the tiles job
    res = reader.answer()                         # join(40); fails if the thread still runs
    assert <res carries the change>
    wakeups.assert_woken(key, "the heartbeat")    # every wait on key ended by a notify
    assert reader.took < 25 / 2                   # well before the deadline
```

* **Why "inside its wait", not only "registered":** a route registers its waiter, then reads, then waits. If the change commits between the registration and that read, the read answers it and no wait happens at all. The behaviour is correct, but no wake-up was exercised (`ended == []`). `until_waiting` therefore returns only when the recorder has seen the read enter `Waiter.wait`. From then on, the change's notify sets the event. Either the wait is running and returns True, or the event is already set when the wait begins and it returns True at once. A notify that lands while the read is between two waits is still seen: the commit came before the notify, so the next read finds it.
* **Why the re-check is patched:** with `RECHECK_S` at 60 s, a wait ends only on a notify or at its own deadline. So a False in the record means "no wake-up" whatever the CPU speed, and a missing wake-up fails at the 25 s deadline instead of passing at the 1 s re-check.
* **Several waits in one read:** a share's reader is woken by the push (the set is notified, its rev is unchanged) and waits again until the finish. `assert_woken` requires every recorded wait to be True, so a missing wake-up on the last change still fails.
* **Messages:** `assert_woken` fails with `the read was not woken by <what>: its waits on <key> ended [False] (True = woken by a notify, False = at its deadline, [] = it never waited)`. `assert_deadline` (used by the "unchanged rev holds" checks) fails if a notify ended the hold.

**The runner** (`server/scripts/starved_pytest.py`): it pins itself to one core with `SetProcessAffinityMask` (Windows) or `sched_setaffinity`. It then starts one busy loop with the base interpreter and runs pytest; both inherit the core. At the end it kills the loop. The loop stops itself after an hour if the runner is killed hard. The default core is the last one (5 on this PC). Only that core is loaded, so other sessions' gates keep the other cores. The module is also the pytest plugin (`-p scripts.starved_pytest`). Through environment variables it repeats the selected tests N times in one process (`--runs`) and makes `waiters.notify` a no-op (`--no-wakeup`). It prints `N/N passed, slowest call` per test.

**Security and privacy:** none.

## Deliverables

- [x] `server/tests/conftest.py`: the PF14e block at the end (`RECHECK_OFF_S`, `Wakeups`, `wakeups`, `LongPoll`); `timing_window()` and its `gc` / `contextlib` imports removed
- [x] `server/tests/test_render.py`, `test_render_shares.py`, `test_pf9_pf12_meet.py`, `test_projects.py`, `test_pf12a_v1_panoramas.py`: the six tests rewritten; PF12a's `_until_waiting` removed
- [x] `server/tests/test_pf14e_long_poll.py`: two guards
- [x] `server/scripts/starved_pytest.py`
- [x] this doc; the PF14e row in `docs/roadmap/40/README.md`; the "Long-poll tests on a starved core (PF14e)" section at the end of the root `README.md`

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_jobs_status_long_poll_rev` | pytest (rewritten) | a heartbeat while a 25 s read waits: 200, rev moved, its wait woken by the notify, answered in under 12.5 s; an unchanged rev waits the whole 1 s (`>= 0.9`), the same rev, its deadline ended it; 422 at `wait_s` 26, 401, 404 |
| `test_share_live_follows_the_set` | pytest (rewritten) | the 404 before the share, the follow state; push + tiles job while a viewer waits 25 s: 200, rev moved, 2 faces, every wait woken, under 12.5 s; another account's set 404; 422 at `wait_s` 30 |
| `test_published_share_follows_the_set` | pytest (rewritten) | PF5's real share: page data, CSP, the live state; the wake-up as above; revoking answers 410 `share_gone` |
| `test_key_reads_a_followed_set_after_its_own_edit` | pytest (rewritten) | a key's agent edit queues one tiles job; the key's 25 s `/v1` read is woken by its finish: rev 2, `at_seq` head + 1, 2 faces, the job id; the viewer's phone and key read the same; session routes refuse the key |
| `test_pull_long_poll_wakes_on_push` | pytest (rewritten) | one waiter registered; the push wakes the 25 s pull: op 1, under 12.5 s, `waiting_count` back to 0; an empty pull holds `0.9 <= t < 30` (far under the patched 60 s re-check) and only its deadline ends it |
| `test_v1_panorama_set_long_poll` | pytest (rewritten) | the tiles job wakes the key's 25 s read: rev 2, 2 faces, `private, no-store`, equal to the session route; on rev 2 a 1.5 s read holds `>= 1.4` s with no pool connection checked out while it waits, ended by its deadline; a passed rev or no rev never waits (`[]`) |
| `test_long_poll_without_wakeup_ends_at_its_deadline` | pytest (guard) | with `waiters.notify` a no-op: the 5 s job-status read still answers the moved rev, but only after `>= 4.9` s, its one wait recorded False; `assert_woken` raises "the read was not woken by the heartbeat" |
| `test_read_answered_without_waiting_is_not_a_wakeup` | pytest (guard) | a push before the pull: the pull answers op 1 without waiting (`[]`); `assert_woken` raises "not woken by the push" |
| `starved_pytest.py --runs 20` | manual / self-test | every test above 20/20 on one core shared with a busy loop |
| `starved_pytest.py --no-wakeup` | manual / self-test | the six rewritten tests fail, each "the read was not woken by …"; the two guards pass |

## Human test

No page or endpoint changed, so there is nothing to click on the served site (`scripts\autopilot-serve.ps1` serves the same `out/` as before). The test is two commands in PowerShell, in the worktree:

1. `cd server`, then `.venv\Scripts\python.exe scripts\starved_pytest.py --runs 3 -p no:warnings`. It takes about 5 minutes (loading the app on a starved core alone takes 2 to 3). **See:** first `core 5 only, shared with a busy loop (pid …); 3 run(s); wake-up on`. Then a `starved runs per test` section with eight lines, each `3/3 passed`. Then `24 passed` and `pytest exit 0 after … s on core 5`. While it runs, Task Manager shows one CPU (CPU 5) at 100 % and the others at their usual load.
2. `.venv\Scripts\python.exe scripts\starved_pytest.py --no-wakeup -p no:warnings`. It takes about 6 minutes, because each of the six reads now waits its whole 25 s. **See:** `wake-up OFF (waiters.notify is a no-op)`, then six failures. Each failure has a line `AssertionError: the read was not woken by the heartbeat` (or `the tiles job`, or `the push`) `: its waits on … ended [False] …`. The summary has `0/1 passed` for the six rewritten tests and `1/1 passed` for the two `test_pf14e_long_poll.py` guards. Then `6 failed, 2 passed` and `pytest exit 1`.
3. Optional: `--core 2` runs on CPU 2 instead. `--runs 20` repeats the self-test's 20-run loop (about 12 minutes).

## Risks / traps

* A test that makes its change before `wakeups.until_waiting(key)` returns can be answered by the read, with no wait. It then fails with `ended []` ("it never waited"). Call `until_waiting` first.
* `wakeups` patches `RECHECK_S` for the whole test. Any other long poll in that test (for example a worker claim with `wait_s` > 0) then ends only on a notify or at its deadline.
* With the wake-up missing, each rewritten test fails only at its 25 s deadline. A no-wake-up run is slow by design.
* `starved_pytest.py` loads one core to 100 %. Never run several runners on different cores at once while other gates run on this PC. If the runner is killed hard, its busy loop ends by itself within the hour.
* Test ids on the runner's command line replace the default list. With none, it runs the PF14e tests (a bare `-p` value is not a test id).

## As-built

* **Date, branch, commits:** 2026-10-13, `ap/t67-pf14e-long-poll-wake-up-tests-pr` from `master` 55d9c84. `6ca1c29` (tests, helper, runner), then the commit with this doc, the tracker row and the README section.
* **Counts:** pytest collected 677 → 679 (+2 guards; six tests rewritten). Test functions 668 → 670. The verify gate: 662 passed + 17 skipped.
* **Baseline: the old versions on the same starvation.** Pytest and one busy loop on core 5 only, 20 runs in a row in one process: each of the six old tests passed 20/20 (545 s). One busy loop on an otherwise idle core does not reproduce T60's failures on its own. T60 failed late in the whole suite, with a large heap (PF14b's GC pauses) on top of about 0.4 of a core. With `waiters.notify` a no-op, the old versions mostly passed:
  * one run: 4 of 6 passed (job status, share live, published share, the /v1 meet);
  * the pull failed `assert (775598.546 - 775597.546) < 1.0`, exactly 1.000 s, the re-check;
  * PF12a failed `assert ((775610.968 - 775601.437) < 2.0)`, the 10 s deadline;
  * 10 more runs: job status passed 10/10 and the pull 1/10, with no wake-up at all.
* **The new versions, starved:** each of the eight tests passed 20/20 in a row on core 5 with one busy loop (624 s). With the core split three ways (pytest and two busy loops), 5 runs: 5/5 each. The slowest reader then took 1.91 s against the 12.5 s bound. The job-status reader took at most 0.11 s and the pull 0.16 s.
* **Acceptance: each rewritten test fails without its wake-up.**
  * *`waiters.notify` a no-op* (`starved_pytest.py --no-wakeup`): this ran once over the whole suite by accident, on the starved core. The runner took `-p no:warnings`'s value for a test id and passed no test list; this was fixed before the commit. Result: **6 failed, 584 passed, 89 skipped** (917 s). The six failures are exactly the rewritten tests, so nothing else in the suite depends on the wake-up for its result. The two guards passed. The messages:
    * `test_jobs_status_long_poll_rev`: `AssertionError: the read was not woken by the heartbeat: its waits on render:job:e33b…da30 ended [False] (True = woken by a notify, False = at its deadline, [] = it never waited)`
    * `test_share_live_follows_the_set`: `… not woken by the tiles job: its waits on render:job:bd57…e1fa ended [False] …`
    * `test_published_share_follows_the_set`: `… not woken by the tiles job: … render:job:2fec…d766 ended [False] …`
    * `test_key_reads_a_followed_set_after_its_own_edit`: `… not woken by the tiles job: … render:job:bc40…109e ended [False] …`
    * `test_pull_long_poll_wakes_on_push`: `… not woken by the push: its waits on 01a1…5c03 ended [False] …`
    * `test_v1_panorama_set_long_poll`: `… not woken by the tiles job: … render:job:f3dd…fe3d ended [False] …`
  * *`notify_job` a no-op*: a temporary `return` as the first line of `app/render/queue.py` `notify_job`, reverted with `git checkout`. The five render-side tests failed, each `the read was not woken by the heartbeat` / `the tiles job … ended [False]`. The pull passed, because its wake-up is the push's own `waiters.notify(project_id)` (`routers/projects.py` `_after_append`). 5 failed, 1 passed, 138 s.
* **Each changed check: what it proved before, what it proves now.**

  | Test | Before | Now |
  |---|---|---|
  | job status | `done - sent < 1.0`, `took < 5` (wait_s 10): an answer within 1 s, which the re-check gave without any notify | wait_s 25, re-check 60 s: `assert_woken` (the heartbeat's notify ended the wait) and `took < 12.5` (well before the deadline); fails without the notify |
  | job status, unchanged rev | `>= 0.9` (it held) | `>= 0.9` kept; plus the same rev back and `assert_deadline` (its deadline ended it, not a notify) |
  | share live (both) and the /v1 meet | `t.join(10)` / `t.join(15)` and a moved rev: the answer had the change, whether from a notify, the re-check or a reader started after the change | the reader is inside its wait before the change; `answer()` asserts the thread finished (40 s guard); rev moved, faces and job id as before; `assert_woken` (every wait ended by a notify); `took < 12.5`; a 200 checked where the old test read the body straight away |
  | pull | waiter registered; `at - pushed_at < 1.0` (passed 1/10 without a notify) | inside its wait; op 1; `assert_woken`; `took < 12.5`; `waiting_count == 1` before and `0` after kept |
  | pull, nothing new | `0.9 <= t < 3`: the upper bound could be reached by load | `0.9 <= t < 30`: far under the patched 60 s re-check, so it still proves the 1 s deadline is honoured, and load cannot reach it; plus `assert_deadline` |
  | PF12a woken read | registered; `done - sent < 2.0`, `took < 8` (wait_s 10) | the shared helper; wait_s 25; `assert_woken`; `took < 12.5`; status, `private, no-store`, rev 2, 2 faces, equal to the session route kept |
  | PF12a hold | `time.sleep(0.3)` after "registered", then `engine.pool.checkedout() == 0`; `took >= 1.4` | the pool check made once the read is inside its wait (no sleep, no race); `took >= 1.4` kept; plus `assert_deadline` |
  | PF12a "answered at once" | two reads (wait_s 10) `< 3` s | two reads (wait_s 25) record no wait at all (`[]`), and `< 12.5` s (a wait would last 25 s) |
  | 401, 404, 422 (`wait_s` above the maximum), the share's account check, the 410 after revoking, the meet's session-route refusals | unchanged | unchanged |

* **PF6's row:** the PF6 Tests table's "`test_jobs_status_long_poll_rev`: a waiting 5.2 returns within 1 s of a heartbeat that bumps `rev`" is now proved by the wake-up itself: the heartbeat's notify ends the wait. PF6's doc is not edited here.
* **`timing_window()`:** removed from `conftest.py` with its `gc` and `contextlib` imports. Its only users were `test_jobs_status_long_poll_rev` and `test_pull_long_poll_wakes_on_push`, and neither has a sub-second window any more.
* **Other wake-up timers found by grep** (`threading` plus `wait_s`): only the six. `test_mobile.py` (`wait_s` 0.2, no thread), `test_render.py`'s claim validation (`wait_s` 21 → 422), the runners in `test_analysis.py` / `test_render_worker.py` (`wait_s=0`), and `test_render_worker.py`'s kill timing are not wake-up tests.
* **Postgres 17.10** (a throwaway `initdb` cluster in the session scratchpad, port 55467, `timezone = 'Asia/Baghdad'`, removed afterwards), the six touched test files with `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`: **83 passed, 1 skipped** (254 s). The skip is `test_pf9_pf12_meet.py`'s site check (`out/` not built for that run).
* **Gate:** `scripts/autopilot-verify.ps1` (lint, build, pytest on SQLite on the built `out/`): green, **662 passed, 17 skipped** (the `postgres`-marked tests) of 679, 662 s in all (pytest 368 s).
* **Deviations and why:**
  1. *`until_waiting` waits for the read to be inside `Waiter.wait`, not only for its waiter to be registered* (PF12a's check). With only the registration, a change could be answered by the read that follows it: correct behaviour, but no wake-up to record. The function is a method of the `wakeups` fixture in `conftest.py`, because the recorder is what knows the read is waiting.
  2. *`LongPoll`* (a thread, `took`, a 40 s hang guard) replaces each test's `got: dict` and `threading.Thread`, so a hung or crashed reader fails the test at once with a clear message, never with a `KeyError`.
  3. *A second guard* (a read that never waited is not a wake-up) next to the one asked for, because the `[]` case is the race in deviation 1.
  4. *The 20 runs in a row are 20 repetitions inside one pytest process* (the runner repeats the selected items). That is harsher than 20 fresh processes, since the heap grows across runs, and it saves 20 imports of the app on a starved core.
  5. *`server/scripts/starved_pytest.py`* gives the human test its two commands. It loads only the one core it pins to, never every core.
* **Contract:** none. Owner, at merge: nothing to apply in the Unreal repo's `contracts\`.
* **Carry-over → which feature:** the worker claim long poll's wake-up (`notify_claim`) has no test that times it. If one is wanted, it is a PF6 follow-up on the same `wakeups` recipe.
* **Later (PF14g, 2026-10-27):** the "well before the deadline" bound now runs from the call that wakes the read (`reader.since(t)`), not from the reader's start (`took`); see `PF14g-timing-bounds-from-the-change.md`.
