# PF14g — Long-poll tests bound the time from the change that wakes the read, and the Paddle stale-signature cases leave room for the clock (launch priority 2)

**Needs merged:** PF14e (the `wakeups` recipe and `LongPoll` in `server/tests/conftest.py`), PF2 (the Paddle webhook and `test_billing_pf2.py`); both on `master` 9c2e9f5. **Unblocks:** a verify gate that stays green on a busy PC. Three gates or runs failed on these checks although the code was right: T100's gate (26 Oct), PF12b's gate (13 Oct) and PF6c's Postgres run. **Contract:** none. Only tests change: no endpoint, response or app code, and no contract file moves.

## Status

**Built (2026-10-27, branch `ap/t101-pf14g-the-long-poll-tests-bound`, Autopilot T101); see As-built.** Checked on `master` 9c2e9f5 (the T100 merge; T100 changed none of these files, so every line is the same as at 4859428) before the work began:

* `server/tests/conftest.py:325-343` `LongPoll` starts its clock when the reader thread starts. While the read waits, the test makes its own calls (`wakeups.until_waiting`, `push_touch`, the claim, and `finish`, which uploads the tiles one PUT each and then calls complete). `reader.took` counts all of them.
* `server/app/billing/paddle_provider.py:56` `SIGNATURE_TOLERANCE_S = 300`; `:108` refuses `abs((now or time.time()) - ts) > SIGNATURE_TOLERANCE_S`.

| # | Check (master 9c2e9f5) | Before | After (this branch) |
|---|---|---|---|
| 1 | `test_render.py:409` `test_jobs_status_long_poll_rev` | `reader.took < wait_s / 2`, timed from the reader's start | `t = time.monotonic()` just before the heartbeat; `reader.since(t) < wait_s / 2` |
| 2 | `test_render.py:845` `test_share_live_follows_the_set` | `reader.took < wait_s / 2`. It also counts `until_waiting`, the push, the claim and the tile uploads. It failed T100's gate: 13.672 s against 12.5 s, after `assert_woken` had passed | `finish(..., at=at)` stamps `at["complete"]` just before its complete; `reader.since(at["complete"]) < wait_s / 2` |
| 3 | `test_render_shares.py:101` `test_published_share_follows_the_set` | as 2 | as 2 |
| 4 | `test_pf9_pf12_meet.py:229` `test_key_reads_a_followed_set_after_its_own_edit` | as 2. It failed PF6c's Postgres run with four suites at once (see PF6c's As-built, the "Postgres 17" bullet) and passed alone | as 2 |
| 5 | `test_pf12a_v1_panoramas.py:150` `test_v1_panorama_set_long_poll` | as 2 | as 2 |
| 6 | `test_projects.py:281` `test_pull_long_poll_wakes_on_push` | `reader.took < wait_s / 2` | `t` just before the push; `reader.since(t) < wait_s / 2` |
| 7 | `test_pf6b_claim_long_poll.py:178` `test_claim_long_poll_woken_by_a_submit` | `poll.took < queue.CLAIM_WAIT_MAX_S / 2` | `t` just before the submit; `poll.since(t) < queue.CLAIM_WAIT_MAX_S / 2` |
| 8 | `test_billing_pf2.py:227` (`test_billing_paddle_webhook_signature`) | `ts=int(time.time()) - 301`. It could not flake (the clock only moves forward), but it was the same form as 9 | `ts=int(time.time()) - (paddle_provider.SIGNATURE_TOLERANCE_S + 60)` |
| 9 | `test_billing_pf2.py:228` | `ts=int(time.time()) + 301`. `int()` drops up to 0.999 s, so the signature can be less than 300.1 s ahead of the clock. A request slower than about 0.1 s then falls inside the window and answers 200, not 400. It failed PF12b's gate (13 Oct) and PF6c's Postgres run | `ts=int(time.time()) + (paddle_provider.SIGNATURE_TOLERANCE_S + 60)` |

The lower bounds stay as they were (`test_pf12a_v1_panoramas.py:160` `took >= 1.4`, `test_pf6b_claim_long_poll.py:168` and `:192`, `test_pf14e_long_poll.py:52`). Load only makes a read longer.

## Goal

When the PC is busy, the server tests that time a woken long poll and a stale Paddle signature still pass, because the code is right. They still fail when the wake-up is missing or the window is wrong. A woken read's bound times only the change that wakes it and the answer, not the test's own writes made while it waits. A stale signature is far enough outside the window that `int()` and a slow request cannot bring it back inside. The exact 300 s edge is checked with an explicit clock instead.

## Read first

* `docs/roadmap/40/00-contract.md` (P.2-P.4); `PF14e-long-poll-tests-deterministic.md` (the recipe: the re-check patched to 60 s, `until_waiting`, `assert_woken`); `PF2f-billing-link-plan-case.md` As-built (its "Verify gate" bullet: T100's failure and the load); `PF6c-render-jobs-1-3-0.md` As-built (its "Postgres 17" bullet).
* `server/tests/conftest.py` (`Wakeups`, `wakeups`, `LongPoll`), `server/tests/render_helpers.py` (`finish`, `upload_outputs`, `complete`), `server/scripts/starved_pytest.py`.
* `server/app/billing/paddle_provider.py` (`sign`, `verify_signature`), `server/tests/test_billing_pf2.py` (`paddle_post`).

## Scope

**In:**

1. `server/tests/conftest.py` `LongPoll`: it also records `answered`, the `time.monotonic()` at which its call returned (the same stamp as `took`'s end), and `since(t)` gives the seconds from `t` to that answer. `took` stays, for the lower bounds.
2. The seven tests: `t` is taken just before the one call that sends the notify (the heartbeat, the push, the submit, and for a tiles job its complete), and each whole-time bound becomes `reader.since(t) < wait_s / 2` (the claim: `< queue.CLAIM_WAIT_MAX_S / 2`). Every `assert_woken`, `until_waiting`, answer guard and assertion on the answer's body is kept exactly as it was.
3. `test_billing_pf2.py`: the two HTTP cases sign `SIGNATURE_TOLERANCE_S + 60` either way. A new unit test, `test_billing_paddle_signature_window_edge`, calls `verify_signature` with an explicit `now` (2,000,000,000, far from 0). A signature 300 s old or 300 s ahead is accepted. At 300.5 s and 301 s either way it is refused with "stale Paddle signature".
4. A grep of `server/tests` for every other upper wall-clock bound, each with its verdict (As-built). One was fixed here: `test_render_worker.py`'s 6 s kill check.
5. `server/tests/test_pf14g_timing_bounds.py`: an `ast` guard against any upper bound on a `.took`, an `ast` guard against a Paddle webhook signed within 5 s of the window, and `LongPoll.since`'s own test.

**Out (and where it goes):**

* App code, `waiters.RECHECK_S`, a route's waits and the Paddle tolerance: no change, because the code is right. `verify_signature` reads `now or time.time()`, so `now=0.0` means the real clock. The new test uses a `now` far from 0, and the function is left as it is.
* Retries, reruns (`pytest-rerunfailures`), skips on load or a longer `wait_s`: none. They would hide a missing wake-up.
* The verify gate's script and its time budget: unchanged.
* The other upper wall-clock bounds left alone: listed with their reasons in As-built.

## Design

**API, data, UI, jobs:** none.

**The recipe** (PF14e's, with the bound moved to the change):

```python
reader = LongPoll(lambda: client.get(url, params={"rev": rev, "wait_s": 25}, headers=h))
wakeups.until_waiting(key)                 # registered and inside Waiter.wait
t = time.monotonic()                       # just before the call that sends the notify
assert heartbeat(...).status_code == 200   # the change that wakes the read
res = reader.answer()                      # join(40), the hang guard
assert <res carries the change>
wakeups.assert_woken(key, "the heartbeat") # every wait ended by a notify (re-check at 60 s)
assert reader.since(t) < 25 / 2            # well before the deadline, counted from the change
```

* **Why the bound can move:** `wakeups` patches the re-check to 60 s, above every route's longest wait (25 s), so a wait ends only on a notify or at its deadline. `assert_woken` (every wait True) already proves that the notify ended the read. The bound keeps PF14e's "well before the deadline" without timing the test's own requests: the time to set up the wait, the push, the claim, the uploads.
* **Why `finish` stamps its own complete:** `render_helpers.finish` uploads the tiles (one PUT each), then calls complete. Only complete changes the job and sends the notify; the uploads go into the claim's job-output session and wake nothing. On an idle PC, from the `finish(...)` line to the answer took 2.4-3.5 s, of which the uploads took 1.7-2.8 s and complete 0.7-0.8 s; the answer came about 0.02 s after complete returned. A `t` taken before the `finish(...)` line would still have counted the uploads (in the slow-write demo below, 15.5-16.6 s against 12.5 s). So `finish` takes an optional `at` dict and writes `at["complete"]` just before its complete. Each of those four tests adds one line (`at: dict[str, float] = {}`) and changes two (the `finish` call and the bound).
* **Paddle:** `int(time.time()) ± (SIGNATURE_TOLERANCE_S + 60)` is 359-360 s off the clock, a minute outside the window. Load can only move the server's clock forward, by seconds, and that takes the old case further out and brings the ahead case 60 s closer, never inside. The exact edge is a pure unit test with an explicit `now` and an integer `ts`, so no clock is read.
* **The guards** (`ast`, every `server/tests/*.py`): any comparison that bounds an attribute named `took` from above (`x.took < n`, `<=`, `n > x.took`, chained `a <= x.took < n`), and any `paddle_post(..., ts=...)` or `sign(secret, body, ts)` whose `ts` adds or takes a literal within 5 s of `SIGNATURE_TOLERANCE_S`.

**Security and privacy:** none.

## Deliverables

- [x] `server/tests/conftest.py`: `LongPoll.answered`, `LongPoll.since(t)`; the docstring says which bound each one serves
- [x] `server/tests/render_helpers.py`: `finish(..., at=None)` stamps `at["complete"]`
- [x] the seven tests: the bound from the change (two or three lines each)
- [x] `server/tests/test_billing_pf2.py`: the two stale cases and `test_billing_paddle_signature_window_edge`
- [x] `server/tests/test_render_worker.py`: the kill proved by the app's missing manifest (Scope 4)
- [x] `server/tests/test_pf14g_timing_bounds.py`: two guards, the guard's own form check, `LongPoll.since`
- [x] this doc; the PF14g row in `docs/roadmap/40/README.md`; the "Test time bounds from the change (PF14g)" section at the end of the root `README.md`; one line under PF14e's As-built

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_no_upper_bound_on_a_long_polls_whole_time` | pytest (guard, new) | no comparison in `server/tests/*.py` bounds a `.took` from above; on master it listed the seven lines (#1-7) |
| `test_guard_sees_every_form_of_an_upper_bound` | pytest (new) | the guard finds `<`, `<=`, `>` (mirrored) and a chained bound, and lets `>=` pass |
| `test_no_webhook_signed_at_the_edge_of_the_window` | pytest (guard, new) | no Paddle webhook signed with a literal offset within 5 s of `SIGNATURE_TOLERANCE_S`; on master `test_billing_pf2.py:227` and `:228`; the check flags `+ 301` and `- 298` and passes `+ 360` |
| `test_long_poll_since_measures_from_the_given_time` | pytest (new) | a call that runs 0.2 s by the monotonic clock: `since(before) >= 0.2`, `took >= 0.2` and not above `since(before)`, `0 <= since(end of the call) < 5`, `since(now) <= 0` |
| `test_billing_paddle_signature_window_edge` | pytest (new) | `verify_signature` with `now` 2,000,000,000 ± 0 / 300 s accepts; ± 300.5 s and ± 301 s raise "stale Paddle signature"; inside the window a wrong secret is still "invalid Paddle signature" |
| the seven tests (Status #1-7) | pytest (changed) | as before (status, body, `assert_woken`), and the answer within `wait_s / 2` of the call that sends the notify |
| `test_billing_paddle_webhook_signature` | pytest (changed) | a good signature 200; a wrong secret, a signature a minute past the window either way, and no signature 400 |
| `test_worker_wrapper_failure_and_cancel` | pytest (changed) | after the cancel, `out/manifest.json` (written by the app only after its 8 s sleep) does not exist |
| `starved_pytest.py --runs 20` | self-test | the seven tests and the two Paddle tests 20/20 on one core shared with a busy loop |
| `starved_pytest.py --no-wakeup` | self-test | the seven tests each fail "the read was not woken by …" |

## Human test

No page or endpoint changed, so there is nothing to click on the served site: `scripts\autopilot-serve.ps1` serves the same `out/` as before. The test is one command (about 30 s), plus an optional second one. In PowerShell, in the worktree:

1. `cd server`, then `.venv/Scripts/python.exe -m pytest tests/test_pf14g_timing_bounds.py tests/test_render.py -k 'live or long_poll or pf14g' -q`. **See:** `6 passed, 31 deselected` (the four PF14g tests, `test_jobs_status_long_poll_rev` and `test_share_live_follows_the_set`) and no failure.
2. Optional (about 3 minutes): `.venv/Scripts/python.exe scripts/starved_pytest.py --runs 5 -p no:warnings tests/test_render.py::test_share_live_follows_the_set`. **See:** `core 5 only, shared with a busy loop …; 5 run(s); wake-up on`, then `5/5 passed, slowest call … s  tests/test_render.py::test_share_live_follows_the_set`, `5 passed` and `pytest exit 0`.

## Risks / traps

* The notify-sending call must be the one stamped. A `t` taken earlier puts the test's own writes back into the bound: for a tiles job, use `finish(..., at=at)` and `at["complete"]`, not a `t` before the `finish(...)` line.
* `since(t)` still counts the change's own request (complete took up to about 8 s on a starved core; see As-built). That is the code under test, so the bound keeps it on purpose.
* On Windows, Python 3.12's `time.monotonic()` ticks every 15.6 ms, so `time.sleep(0.05)` measured 0.046 s by it. A lower bound must leave room for one tick, or wait by the monotonic clock itself (as `LongPoll.since`'s test does).
* The `ast` guards read every `server/tests/*.py`, helpers included. A comparison such as `since(before) >= poll.took` is an upper bound on `took` too, and the guard flags it; write `since(before) - poll.took >= 0`.

## As-built

* **Date, branch, commits:** 2026-10-27, `ap/t101-pf14g-the-long-poll-tests-bound` from `master` 9c2e9f5. `beed0c3` (the tests), then the commit with this doc, the tracker row, the README section and PF14e's line.
* **Counts:** pytest collected 978 → 983 (+5: four in `test_pf14g_timing_bounds.py`, one in `test_billing_pf2.py`). No app file changed (`git diff 9c2e9f5 -- server/app worker src` is empty).
* **Tests first, on master 9c2e9f5's tests** (only the new file present): `test_no_upper_bound_on_a_long_polls_whole_time` failed listing `test_pf12a_v1_panoramas.py:150`, `test_pf6b_claim_long_poll.py:178`, `test_pf9_pf12_meet.py:229`, `test_projects.py:281`, `test_render.py:409`, `test_render.py:845`, `test_render_shares.py:101` (and one line of the new test itself, `since(before) >= poll.took >= 0.2`, rewritten before the commit). `test_no_webhook_signed_at_the_edge_of_the_window` failed listing `test_billing_pf2.py:227` and `:228`. `test_long_poll_since_measures_from_the_given_time` failed with `AttributeError: 'LongPoll' object has no attribute 'since'`. `test_guard_sees_every_form_of_an_upper_bound` passed (it checks the guard, not the suite). The boundary unit test passes on master as well: it is new coverage, not a regression test.
* **Where the time goes** (a scratch `-p` plugin wrapping the helpers and `LongPoll._run`, idle PC, never committed). The heartbeat read took 0.08 s and the push 0.06 s. The share live view: the read 3.66 s, of which the push 0.04 s, the claim 0.05 s, the tile uploads 2.80 s and the complete 0.73 s. The published share: 3.16 s (uploads 2.20 s, complete 0.80 s). The `/v1` meet: 2.81 s (uploads 1.95 s, complete 0.82 s). PF12a: 2.56 s (uploads 1.69 s, complete 0.75 s). In each, the answer came within 0.02 s of complete's return.
* **The slow-write demo** (once, scratch only: a `-p` plugin adds a 13 s sleep to `upload_outputs` for a tiles job, the test's own writes before the complete; the master copy was `git archive 9c2e9f5 server worker` in the session's temp folder, deleted afterwards):

  | Test | master 9c2e9f5 (`reader.took`) | this branch (`reader.since(at["complete"])`) | from the `finish(...)` line |
  |---|---|---|---|
  | `test_share_live_follows_the_set` | **failed** `assert 16.67200000002049 < (25 / 2)` | passed, 0.84 s | 16.56 s / 15.81 s |
  | `test_published_share_follows_the_set` | **failed** `assert 16.640999999945052 < (25 / 2)` | passed, 0.75 s | 16.41 s / 15.55 s |
  | `test_key_reads_a_followed_set_after_its_own_edit` | **failed** `assert 15.937000000034459 < (25 / 2)` | passed, 0.81 s | 15.92 s / 15.84 s |
  | `test_v1_panorama_set_long_poll` | **failed** `assert 16.42200000002049 < (25 / 2)` | passed, 0.80 s | 16.03 s / 15.78 s |

  Master: 4 failed in 92.5 s. This branch: 4 passed in 84.5 s. The last column is a `t` taken before the `finish(...)` line, as the brief first put it: it would have failed all four as well.
* **Starved, 20 runs** (`starved_pytest.py --runs 20` on core 5 with one busy loop, while other sessions also loaded the PC): the seven tests, `test_billing_paddle_webhook_signature` and `test_billing_paddle_signature_window_edge`, each **20/20**, 180 passed in 1,784 s (the runner: 1,948 s). The largest values, from a scratch `-p` plugin wrapping `LongPoll.since`:

  | Test | largest `since()` | largest `took` | slowest call |
  |---|---|---|---|
  | `test_key_reads_a_followed_set_after_its_own_edit` | **8.09 s** | **10.77 s** | 23.56 s |
  | `test_share_live_follows_the_set` | 6.67 s | 10.56 s | 22.58 s |
  | `test_v1_panorama_set_long_poll` | 6.14 s | 9.03 s | 26.93 s |
  | `test_published_share_follows_the_set` | 5.19 s | 7.62 s | 9.61 s |
  | `test_jobs_status_long_poll_rev` | 1.05 s | 1.09 s | 4.11 s |
  | `test_pull_long_poll_wakes_on_push` | 0.98 s | 1.00 s | 5.21 s |
  | `test_claim_long_poll_woken_by_a_submit` | 0.95 s | 1.00 s | 2.62 s |

  The two Paddle tests: slowest calls 4.37 s and 0.00 s. The largest `since()`, 8.09 s against 12.5 s, is the complete request itself on a starved core: the change under test, kept in the bound on purpose.
* **Starved, no wake-up** (`starved_pytest.py --no-wakeup` on the seven tests): **7 failed** in 227 s (the runner: 378 s). Each read waited its whole wait, so the wake-up is still proven:
  * `test_jobs_status_long_poll_rev`: `AssertionError: the read was not woken by the heartbeat: its waits on render:job:628b1373852bbf312d4a29a027e6bf6b ended [False] (True = woken by a notify, False = at its deadline, [] = it never waited)`
  * `test_share_live_follows_the_set`: `… not woken by the tiles job: its waits on render:job:18d29308f5c8597cbdc739fbc920e13b ended [False] …`
  * `test_published_share_follows_the_set`: `… not woken by the tiles job: … render:job:9a2e4ea073626ebd43c7b7841a145e2c ended [False] …`
  * `test_key_reads_a_followed_set_after_its_own_edit`: `… not woken by the tiles job: … render:job:bf838d3c95cb66e66a98d52b7ebada04 ended [False] …`
  * `test_pull_long_poll_wakes_on_push`: `… not woken by the push: its waits on 01a17d68a24773dbb6e2d6db7e50c945 ended [False] …`
  * `test_v1_panorama_set_long_poll`: `… not woken by the tiles job: … render:job:8e2021801926ecedfcfeaf7f8b77b9d3 ended [False] …`
  * `test_claim_long_poll_woken_by_a_submit`: `… not woken by the submit: its waits on render:claim ended [False] …`
* **The affected files on SQLite** (the seven files, `test_pf14e_long_poll.py`, `test_pf14g_timing_bounds.py`, `test_billing_pf2.py`, `test_billing.py`, `test_pf2c_billing_tidy.py`, `test_pf2d_billing_followups.py`, `test_render_worker.py`): **164 passed, 5 skipped** (the `postgres`-marked tests and a site check without `out/`) in 294 s.
* **Postgres 17.10** (a throwaway `initdb` cluster in the session's temp folder, port 55471, `timezone = 'Asia/Baghdad'`, stopped and deleted afterwards). The seven files, `test_billing_pf2.py` and `test_pf14g_timing_bounds.py` with `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`: **134 passed, 1 skipped** (`test_pf9_pf12_meet.py`'s site check, `out/` not built) in 477 s.
* **Scope 4: every other upper wall-clock bound in `server/tests`** (grep for `took <`, `elapsed <`, `monotonic() - … <`, `time.time() - … <`, `perf_counter`, plus `datetime.now()` against a `timedelta` and deadline loops):

  | Where (this branch) | What it bounds | Verdict |
  |---|---|---|
  | `test_render_worker.py:117` (`test_worker_wrapper_failure_and_cancel`, master line) `time.monotonic() - started < 6` | `run_once` from its start: the claim, the input download, the fake app's fresh interpreter, the test's own cancel (after 1 s), the heartbeat (0.2 s) and the kill, against the app's 8 s sleep | **Fixed here.** It timed the test's own cancel call and a busy-PC path the code does not promise (a job that reaches the app within 6 s). Now `assert not (work_dir / job_id / "out" / "manifest.json").exists()`: the fake app writes its manifest only after its sleep, and the wrapper waits for the app before it returns. With `Heartbeat.kill` a no-op (a scratch `-p` plugin), the new check fails `assert not True` (the manifest is there). The cut: a kill that comes late but before 8 s is no longer caught. PF14e had left this one alone as asked; this brief's Scope 4 rule covers it |
  | `test_pf12a_v1_panoramas.py:171` `time.monotonic() - started < wait_s / 2` | two reads that must not wait (`rev` passed, no `rev`) | Left alone. It times only the two reads under test (no test write inside), about 0.05 s each against 12.5 s, and `wakeups.ended == []` already proves that no wait happened |
  | `test_projects.py:291` `0.9 <= time.monotonic() - started < 30` | an empty 1 s pull | Left alone. It times only the pull under test. 30 s is far under the patched 60 s re-check, so the upper bound is what proves that the 1 s deadline is honoured, and load cannot reach it (PF14e) |
  | `test_pf12_mcp_package.py:349` `seconds <= 1.0` (`perf_counter`, `:174-181`) | the MCP bridge's exit after stdin EOF | Left alone. It is the contract's own number (agent-interface §6.6, "exit within 1 s of stdin EOF"), timed from the EOF alone with none of the test's calls inside. It has not failed in any of the 105 verify logs under `X:\Truebex\.autopilot\logs` |
  | `test_releases.py:110` `exp - now == approx(900, abs=5)`; `:139` `890 s < left <= 900 s` | a signed download URL's expiry against the test's clock | Left alone. One request sits inside 4 s (after `int()`) and 10 s of slack, and the 900 s expiry is the code's promise. Not seen failing |
  | `test_billing_pf2.py:355` `captured["expires_at"] - time.time() <= 31 * 60 + 5` | the founding checkout session's end | Left alone. Load only makes the left side smaller |
  | `test_plumbing.py:102` (60 s), `test_pf14c_utc_times.py:51` and `test_pf2c_billing_tidy.py:274` (5 min), the day-scale `timedelta` checks (`test_billing.py:95`, `test_billing_pf2.py:256`, `test_pf2c_billing_tidy.py:268`, `test_orgs.py:138`, `test_telemetry.py:349`) | an id's or a time's distance from now | Left alone. A minute or more of slack for one request |
  | `conftest.py:289` (`until_waiting`, 20 s), `test_pf6b_claim_long_poll.py:82` (`_until`, 20 s), `test_pf12_openapi_sdks.py:136` and `test_pf14b_outbound.py:458` (a server starting, 20 s) | waiting for a condition | Left alone. These are hang guards, not a measure of speed: they fail only when the condition never comes |
  | `test_render.py:415`, `test_pf12a_v1_panoramas.py:161`, `test_pf6b_claim_long_poll.py:168` / `:193`, `test_pf14e_long_poll.py:52` | lower bounds | Left alone. Load only makes them easier to meet |

  `test_pf6b_claim_long_poll.py:287-289` (a subprocess's printed exit time) and `test_ai_proxy.py:284` (a file's mtime) assert no bound.
* **Assertions moved:** only those of Status #1-9 and `test_render_worker.py`'s kill check (above). In the four tiles-job tests the `finish(...)` line changed too (`at=at`) and one line was added, so three lines differ instead of two. The reason is in Design ("Why `finish` stamps its own complete").
* **Deviations and why:**
  1. *The tiles-job tests stamp the complete, not the `finish(...)` line.* Measured: the uploads are 1.7-2.8 s of the 2.4-3.5 s, and in the slow-write demo a `t` before the line still failed 4 of 4. `render_helpers.finish` gained an optional `at` dict; its other callers are unchanged.
  2. *`test_render_worker.py`'s 6 s check is fixed, not just listed* (Scope 4's rule; see the table).
  3. *The edge unit test is in `test_billing_pf2.py`*, next to the HTTP cases, as the merge note asks; the guards and `since`'s test are in the new file.
  4. *`LongPoll.since`'s test waits by `time.monotonic()`, not `time.sleep(0.2)`.* On this PC `time.sleep(0.05)` measured 0.046 s by the 15.6 ms monotonic clock, so a strict `>= 0.2` after a sleep could fail by one tick.
* **Other flaky tests:** none seen failing in these runs.
* **Contract:** none. Owner, at merge: nothing to apply in the Unreal repo's `contracts\`.
* **Carry-over:** none.
