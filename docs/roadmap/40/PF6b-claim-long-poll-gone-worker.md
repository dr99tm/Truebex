# PF6b — A stopped worker's claim takes no job: the claim long poll checks its worker is still connected, a job claimed for a gone worker goes back with no attempt spent, and `notify_claim`'s wake-up has a test (launch priority 2)

**Needs merged:** PF6, PF6a (both on `master` 019b331, after T88), PF14e (the `wakeups` recipe). **Unblocks:** stopping or restarting the RTX PC's worker (Ctrl+C, an update, a reboot), and later a cloud pool stopping an idle machine, without a user's job sitting `claimed` for 120 s and losing one of its three attempts. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\render-jobs.md` **1.1.0**, unchanged: 5.7 (the claim, `wait_s` at most 20), §6.4 ("A lease lapses 120 s after the last heartbeat and the job is queued again (at most 3 attempts)"), §7 (5.8-5.10 `409 lease_lost`), §9 (`test_lease_expiry_requeues_three_times`). A PATCH line is proposed in As-built.

## Status

**Built 2026-10-16** on `ap/t89-pf6b-a-stopped-workers-claim-tak` (Autopilot T89); see As-built. Checked on `master` 019b331 before the work:

| # | Where (master 019b331) | Before |
|---|---|---|
| 1 | `server/app/routers/workers.py` `claim` (:93-132) | `checked_in()` (which runs `queue.release_held`), then a loop: `_claim_once` (:78-90, `queue.try_claim` then `queue.prepare_claim`) answers 200 with the payload, or `await waiter.wait(min(RECHECK_S, remaining))` until the deadline, then 204. It never looked at the connection; the endpoint took no `Request`. |
| 2 | `server/app/render/queue.py` `try_claim` (:201-230), `prepare_claim` (:326-372) | `claimed` with a new `lease_id`, `lease_expires_at` = now + 120 s, `worker_id`, `claimed_at`; then maybe `base_job_id` from the followed set, a job-output `UploadSession` (`output_upload_id`), the worker's `idle_since` cleared, `notify_job`. |
| 3 | the same file, `lapse` / `end_attempt` (:91-150), `release_held` (:234-244) | Nothing ended such a claim but the lease lapsing (reap → lapse → `end_attempt(retry=True)`, one attempt, "Trying again (timeout).") or the same worker claiming again (`release_held`, the same path). `MAX_RETRIES = 3`. |
| 4 | `worker/truebex_worker.py` `Api.claim` | `urllib` with `timeout = wait_s + 30` on the main thread. **Found here:** on Windows a blocking socket read ignores Ctrl+C until it returns, so a worker stopped mid claim stayed connected until the API answered (measured below). |
| 5 | tests | No test ran `/workers/claim` with `wait_s` > 0 and a job queued during the wait (PF14e's carry-over). Starlette's TestClient never reports a disconnect while a request is open. |

The middlewares are pure ASGI (`contract_http.RequestIdMiddleware`, `CORSMiddleware`), so Starlette's `await request.is_disconnected()` sees uvicorn's `http.disconnect` (fastapi 0.115.6, starlette 0.41.3, uvicorn 0.34.0 with httptools).

## Goal

When the owner stops the render worker (Ctrl+C, an update, a reboot), or a cloud pool stops a machine that has been idle for 10 minutes, the long poll that worker left behind takes no job. A panorama or tiles job submitted in that window stays queued. The next worker takes it as its first attempt, and it does not sit `claimed` for 120 s with nothing rendering. A job that already failed twice for real is not failed for good by a claim that nobody ran. The claim's wake-up (a job submitted while a worker waits) has a test proved by the wake-up itself, as PF14e asked.

## Read first

* `docs/roadmap/40/00-contract.md` (gates, the P.4 template); `PF6a-render-jobs-1-1-0.md` (Risks: "A stopped worker's claim can still take a job"; human test steps 1-4); `PF14e-long-poll-tests-deterministic.md` (the recipe, "Carry-over").
* `render-jobs.md` 1.1.0: 5.7, §6.4, §7, §9.
* `server/app/routers/workers.py`, `server/app/render/queue.py`, `server/app/projects/waiters.py`, `server/tests/conftest.py` (`wakeups`, `LongPoll`), `tests/test_pf12_openapi_sdks.py` (`live_api`), `worker/truebex_worker.py`.

## Scope

**In** (nothing was cut):

1. **The claim checks its worker is still connected.** `claim` takes the `Request`. Before every try (the first one, and after each wait) it returns at once, without claiming, when `await request.is_disconnected()` is true: 204 (nobody reads it) and one info line naming the worker. `waiter.close()` still runs.
2. **A job claimed for a worker that went away in between goes back with no attempt spent.** After `_claim_once` returns a payload the route checks again; if the worker is gone, `queue.unclaim(db, job_id, lease_id, now)` puts the job back as it was before the claim (Design). It acts only on a job still `claimed` under that lease.
3. **Everything else kept.** A connected worker gets exactly today's 200 or 204. A worker that vanished without closing its connection (a machine powered off, a cut network) is still caught by `release_held` at its next claim or the 120 s lapse: the contract's rule. `test_lease_expiry_requeues_three_times` and every other render test unchanged and green.
4. **The worker side, checked.** A real Ctrl+C on the worker's console did not close the claim's socket until the API answered (Status #4), so the worker changed: the claim runs on a helper thread and the main thread waits in 0.25 s slices (`interruptible`). Ctrl+C now stops it at once and the OS closes the connection. The claim's `timeout = wait_s + 30` is unchanged.
5. **Through Cloudflare**, checked with a throwaway quick tunnel: a closed client connection reaches uvicorn as a disconnect within about 50 ms (As-built). No infrastructure was built for it.
6. **The wake-up test** PF14e left to PF6: a waiting claim is woken by the submit (`assert_woken`), a claim with nothing queued ends at its deadline (`assert_deadline`), and a guard shows it fails without `notify_claim`.

**Out (and where it goes):**

* A cloud pool adapter that refuses claims from a machine it is stopping: GD3 names the provider (the static pool cannot power a machine). With PF6b, a machine whose OS shuts down cleanly closes its worker's connection, so its claim takes nothing.
* Any change to `LEASE_S`, `MAX_RETRIES` or the contract (a §6.4 PATCH is proposed to the app half in As-built).
* A worker that goes away *after* the API has written a 200 to it (the answer was already sent, so the API cannot tell). The lease rule covers it, as before.
* PF14's VM (Cloudflare → Caddy → uvicorn): not run here. Caddy's `reverse_proxy` cancels the upstream request when its client goes, so it should pass the disconnect on; check it on staging when PF14's cutover runs (As-built).

## Design

### API (5.7, no new endpoint, no new field)

| Case | Before (master 019b331) | PF6b |
|---|---|---|
| A connected worker, a job queued or submitted during the wait | 200 with the job | the same |
| A connected worker, nothing until the deadline | 204 | the same |
| The worker's connection closed while its claim waited | the claim kept waiting; a job submitted meanwhile was claimed for it (`claimed`, 120 s, then one attempt) | the claim ends at the next try (the submit's wake-up, or the 1 s re-check): 204, no job taken; log `worker <id> went away while its claim waited; no job taken` |
| The connection closed while a job was being claimed for it | the job stayed `claimed` for the gone worker | `queue.unclaim`: the job is back as before the claim; log `worker <id> went away as job <job> was claimed for it; given back, no attempt spent` |
| The worker vanished without closing (power, network) | `release_held` at its next claim, or the 120 s lapse | unchanged |

The answer to a gone worker is 204 with the render-jobs/1.1 echo; uvicorn writes nothing to a closed connection, so the status only matters to a test. The log is `truebex.render.claim` at INFO (shown when uvicorn runs with `--log-config scripts\log-info.json`).

### `queue.unclaim(db, job_id, lease_id, now) -> bool`

Locks the row (`lock_job`), and acts only when the job is still `claimed` and its `lease_id` is the one given; otherwise it rolls back and returns False. So a heartbeat (`running`), a lapse, a `release_held` or a repeat in between wins.

* `state` → `queued`; `lease_id`, `lease_expires_at`, `worker_id`, `claimed_at` → null; `progress` 0, `message` "" (no "Trying again", no `error`).
* `attempts` and `queued_at` unchanged, so the job keeps its place (`_candidate` orders by `priority`, then `queued_at`).
* The job-output `UploadSession` the claim opened is deleted and `output_upload_id` cleared (nobody was told its id, so it holds no part).
* `base_job_id`: **left for the next claim to set.** `prepare_claim` sets a followed set's newest picture on every claim (a `tiles` job is only claimable once its set has one), and a job without a set never has it changed.
* `rev` bumped, the worker's `idle_since` = now, commit, then `notify_job(job_id)` and `notify_claim()` (another waiting worker may take it at once).
* A cancel asked while the job was claimed (`cancel_requested`, "Stopping…") wins: `end_attempt`'s cancel branch ends it `cancelled` at no charge, no attempt, `ended_lease_id` = that lease (a heartbeat with it answers `cancel: true`).

Left as found: the operations file `claim_inputs` wrote (`jobs/<id>/inputs/ops-<after>-<at_seq>.json`) stays in storage; the next claim writes the same key again. The signed URLs in the lost answer were never sent.

### The worker (`worker/truebex_worker.py`)

`interruptible(call)` runs the claim on a daemon thread named `claim` and waits for it with `join(0.25)` in a loop, re-raising the call's exception or returning its value. Ctrl+C (a flag on Windows) is seen within a slice; `main()` returns 0, the process exits and the OS closes the connection (a reset, seen by uvicorn at once). Only the claim, the one call that sits idle; heartbeats, downloads and uploads belong to a running job, which the lease covers. No new setting; Linux workers (where SIGINT interrupts a read anyway) behave the same.

### Data, UI, jobs, security

No table, column, migration, page or copy. No new task. Nothing reaches a log but the worker id and the job id.

## Deliverables

- [x] `server/app/routers/workers.py`: `claim(request, …)`, the two `is_disconnected()` checks, `_unclaim`, `log` (`truebex.render.claim`), the module docstring
- [x] `server/app/render/queue.py`: `unclaim`, the module docstring
- [x] `worker/truebex_worker.py`: `interruptible`, `Api.claim` through it, the module docstring
- [x] `server/tests/test_pf6b_claim_long_poll.py` (9 tests; its own `live_api` fixture, so `conftest.py` is unchanged)
- [x] this doc; the PF6b row in `docs/roadmap/40/README.md`; the "Stopping a render worker (PF6b)" section at the end of the root `README.md`

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_claim_long_poll_woken_by_a_submit` | pytest (PF14e recipe) | nothing queued: a 1 s claim answers 204 with the echo, ended by its deadline (`assert_deadline`), `took >= 0.9`; then a 20 s claim waiting (`until_waiting(queue.CLAIM_KEY)`) is woken by a submit: 200 with that job, `attempts` 0, `assert_woken(CLAIM_KEY, "the submit")`, `took < 10` |
| `test_claim_without_notify_claim_waits_to_its_deadline` | pytest (guard) | `waiters.notify` drops `CLAIM_KEY`: the 2 s claim gets the job only at its deadline (`took >= 1.9`), its wait recorded `[False]`, and `assert_woken` raises "not woken by the submit" |
| `test_gone_before_the_job_takes_nothing` | pytest (real port) | a raw socket's claim (`wait_s` 10) waits, the socket closes, uvicorn drops the connection, then a submit: the claim is woken (`[True]`) and takes nothing; the job `queued`, `attempts` 0, no lease, worker or `claimed_at`, `rev` 1; one log line with `pc-rtx` and "no job taken"; a claim over `http.client` then gets it with `attempts` 0 |
| `test_gone_after_the_claim_gives_the_job_back` | pytest (real port, the race) | `queue.prepare_claim` wrapped to close the client socket right after the job is claimed and wait until uvicorn drops it: the job `queued`, `attempts` 0, the same `queued_at`, `rev` + 2, no lease, worker, `claimed_at`, message or error, `base_job_id` unchanged, the job-output session gone, the worker idle; one log line with `pc-rtx` and the job id; 5.2 shows no "Trying again"; the next claim gets it as `attempts` 0 on a new lease and upload; 5.8 with the lost lease → 409 `lease_lost` |
| `test_worker_stopped_mid_poll_closes_its_connection` | pytest (subprocess) | the real worker (`main(['--config', …])`, `wait_s` 20) against the live API; once its claim waits, `_thread.interrupt_main()` (Ctrl+C as Windows delivers it: a flag, no wake-up of a blocked read): the worker exits 0 within 10 s, uvicorn drops its connection, a job submitted after stays `queued` with `attempts` 0 |
| `test_connected_worker_over_a_real_port` | pytest (real port) | over `http.client`: a 1 s claim → 204 at its deadline; a 20 s claim woken by a submit → 200 with the job, `assert_woken`; the job `claimed` by `pc-rtx` under that lease |
| `test_connected_run_is_queued_claimed_running_succeeded` | pytest | a long-poll claim woken by the submit, two heartbeats, `finish`: the states seen at every `notify_job` are exactly queued, claimed, running, succeeded; `attempts` 0, no "Trying again" |
| `test_unclaim_only_while_claimed_under_that_lease` | pytest | after a heartbeat (`running`) and after success: False, nothing changed; another lease or an unknown job: False; the claim's own lease: True, then False (once); the job back as new; 5.8 with it → `lease_lost`; the next claim gets it as `attempts` 0 |
| `test_unclaim_after_a_cancel_ends_it_cancelled` | pytest | a cancel while `claimed`, then `unclaim`: `cancelled`, `attempts` 0, no cost, the session gone, 5.8 with that lease → `cancel: true`, the next claim 204 |
| PF6's, PF6a's, PF9's, PF11's, PF12's, PF14e's tests | pytest | green unchanged (`test_render.py` with `test_lease_expiry_requeues_three_times`, `test_render_worker.py`, `test_render_shares.py`, `test_pf6a_*`, `test_analysis.py`, `test_analysis_runners.py`, `test_pf11_pf12_meet.py`, `test_pf12_*`, `test_pf12a_v1_panoramas.py`, `test_pf9_pf12_meet.py`, `test_mobile.py`, `test_orgs_usage.py`, `test_pf14e_long_poll.py`) |
| `starved_pytest.py --runs 5 tests/test_pf6b_claim_long_poll.py` | self-test | each 5/5 on one core shared with a busy loop |
| `npm run lint`, `npm run build`, `pytest -q` | gate | green (`scripts/autopilot-verify.ps1`) |

## Human test

About 10 minutes, on this PC, against a local API with the fake app (PF6a's human test steps 1-4, with the worker's long poll at its full 20 s). Four PowerShell windows; `<WT>` = `X:\Truebex-autopilot\t89-pf6b-a-stopped-workers-claim-tak`.

1. **API (window A).** `cd <WT>\server`, `.venv\Scripts\python.exe scripts\make_signing_key.py --kind lic`, and copy its `LICENCE_SIGNING_KEY=` and `LICENCE_KEY_ID=` values into:
   `Set-Content .env -Encoding ascii -Value 'DATABASE_URL=sqlite:///./pf6b-human.db','SECRET_KEY=pf6b-human-test-0123456789abcdef0123456789abcdef','API_URL=http://127.0.0.1:8000','CORS_ORIGINS=http://127.0.0.1:3189','LICENCE_SIGNING_KEY=<paste>','LICENCE_KEY_ID=<paste>'`
   then `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-config scripts\log-info.json` → "Uvicorn running on http://127.0.0.1:8000" (the log config shows the API's own INFO lines). Delete `server\.env` and `pf6b-human.db` afterwards.
2. **Site (window B, `<WT>`).** `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build` (about 4 min), then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → "serving … on http://127.0.0.1:3189/" (another port: use it here and in `CORS_ORIGINS`). Open `http://127.0.0.1:3189/signup/` and sign up.
3. **Accounts (window C, `<WT>\server`).** `.venv\Scripts\python.exe -m app.admin_cli <you>`; `.venv\Scripts\python.exe scripts\demo_replica.py login --email <you> --password <pw> --trial` → a `tbx_dev_…` token; `.venv\Scripts\python.exe scripts\demo_replica.py --token <tbx_dev_…> push` → "project id: <project>". Reload the dashboard, Admin → Render → "Issue a worker token": `pc-rtx`, kinds `panorama` and `tiles` → the `tbx_wrk_…` token.
4. **Worker (window D, `<WT>`).** `Set-Content worker\worker.toml -Encoding ascii -Value 'api = "http://127.0.0.1:8000"','token = "<tbx_wrk_…>"','worker_id = "pc-rtx"','kinds = ["panorama", "tiles"]','app = "worker/tests/fake_truebex.py"','work_dir = "worker/jobs"','keep_work = true','heartbeat_s = 5','wait_s = 20','doc_version_max = 55'`, then `py -3.12 worker\truebex_worker.py --config worker\worker.toml` → "pc-rtx: waiting for app jobs (panorama, tiles) from http://127.0.0.1:8000".
5. **Stop it mid poll.** Wait about 5 s (its claim now waits on the API), then press **Ctrl+C** in window D. **See:** the prompt comes back at once (before PF6b it came back only when the claim answered, up to 20 s later). Window A, within about a second: `INFO truebex.render.claim: worker pc-rtx went away while its claim waited; no job taken`.
6. **Submit within 20 s (window C).** `.venv\Scripts\python.exe scripts\demo_render.py --token <tbx_dev_…> submit --project <project>` → "panorama job queued at operation 12: estimate 4.5 cu" and "job id: <job>". Then `.venv\Scripts\python.exe scripts\demo_render.py --token <tbx_dev_…> watch --job <job>` → `rev 1: queued 0% at operation 12, ~4.5 cu`, and it waits: nothing took the job.
7. **Start the worker again (window D)**, the same command as step 4. **See:** "claimed <job> (panorama, 3 views, at 12)", then "complete <job>: 18 faces rendered, 90 files sent". Window C's watch prints `rev 2: claimed …`, (`running … rendering`), then `succeeded 100% at operation 12, … cu` and returns. There is **no** `queued … Trying again (timeout).` line (before PF6b there was one, and the job was claimed twice).
8. **The record.** Window C: `(Invoke-RestMethod http://127.0.0.1:8000/jobs/<job> -Headers @{Authorization='Bearer <tbx_dev_…>'}).attempts` → `0` (a first run; one ended claim would be 1). In the browser, Dashboard → Cloud: the "Panorama set" row is Succeeded with its cost and no "Trying again" note.
9. **Optional, a kill instead of Ctrl+C.** Start the worker, wait 5 s, close window D with its X (or `Stop-Process -Name python -Force` only if no other Python runs on this PC), submit again as in step 6 and start a worker in a new window: the same lines (window A logs "went away", the job runs once, `attempts` 0).

## Risks / traps

* **A worker older than PF6b on Windows still loses the job on Ctrl+C**, even against this API: its socket stays open until the claim answers, so the API sees a connected worker and hands it the job. Update `worker/truebex_worker.py` on the RTX PC with the API. (A kill, a closed console or a reboot closes the socket on any version.)
* **Not a disconnect:** a machine that loses power or network sends nothing, so its claim still takes a job that comes back after 120 s with one attempt spent (§6.4). The same for a worker that goes away after the 200 was written.
* **TestClient never disconnects.** Only a real port shows it: the tests start uvicorn in a thread (`live_api`) and close a real socket, then wait until uvicorn drops the connection (`server_state.connections`) before the next step, so the order is deterministic.
* **Ctrl+C in a headless self-test:** a process started from the Autopilot shell inherits "ignore Ctrl+C". A console test must call `SetConsoleCtrlHandler(NULL, FALSE)` before starting the worker, then `GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)` from inside that console (scratchpad `live/console_stop.py`). Run the worker with the base `python.exe`, not the venv's launcher (a kill would leave its child running).
* **`wakeups` patches `RECHECK_S` to 60 s for the whole test:** a gone claim then ends only on a notify or at its deadline, which is why the tests submit a job to end it.

## As-built

* **Date, branch, commits:** 2026-10-16, `ap/t89-pf6b-a-stopped-workers-claim-tak` from `master` 019b331: `93cd420` (tests, 5 of 9 failing on master), `c7fb39c` (the claim's checks and `queue.unclaim`), `ab537f8` (the worker's interruptible claim), `2d4fe9a` (log wording), then the commit with this doc, the tracker row and the README section.
* **Counts:** pytest 877 → 886 collected (9 new). On master 019b331, 5 failed: the two gone-worker tests ("the job is claimed for pc-rtx: a gone worker's claim took it"), the Ctrl+C test ("the worker was still waiting on its claim 10 s after Ctrl+C"), and the two `unclaim` tests (no `queue.unclaim`). 4 passed on master by design: the wake-up test and its guard (`notify_claim` works on master), and the two connected-worker tests (what must not change). **The wake-up test fails without the wake-up:** with `notify_claim`'s body made a `return` (a temporary edit, reverted), `test_claim_long_poll_woken_by_a_submit` and `test_connected_worker_over_a_real_port` failed `the read was not woken by the submit: its waits on render:claim ended [False]`. `starved_pytest.py --no-wakeup` on them: the same 2 failures (21.2 s each, the 20 s deadline), the guard passed.
* **Self-tests:** the new file with the PF6, PF6a, PF9, PF11, PF12, PF12a and PF14e suites on SQLite (17 files): **152 passed, 2 skipped** (site checks, no `out/`). On a throwaway **PostgreSQL 17.10** cluster with `timezone = 'Asia/Baghdad'` (port 55489, removed afterwards), `test_analysis.py`, `test_pf14e_long_poll.py`, `test_pf6a_*`, `test_pf6b_claim_long_poll.py`, `test_render*.py`: **80 passed**. `starved_pytest.py --runs 5 tests/test_pf6b_claim_long_poll.py` (core 5 shared with a busy loop): **45/45**, the slowest call 6.6 s (a full run with uploads).
* **Live run, before and after** (scratchpad `live/live_run.sh`: uvicorn on SQLite with `log-info.json`, `demo_replica.py push`, the worker wrapper with `fake_truebex.py` and `wait_s` 20 under the base Python, stopped while its first claim waits, `demo_render.py submit` of the living room 2 s after the stop, then a second worker `--once`; `demo_render.py watch` recorded every change):

  | Run | Stop | Worker 1 gone after | 3 s after the submit | Changes seen | Claims answered 200 | End |
  |---|---|---|---|---|---|---|
  | master server + master worker | kill | 0.02 s | `claimed` by pc-rtx, a lease | claimed → queued "Trying again (timeout)." → claimed → succeeded | 2 (the first unlogged: uvicorn drops a response to a closed connection) | succeeded, **attempts 1** |
  | PF6b + PF6b | kill | 0.02 s | `queued`, no worker | queued → claimed → running → succeeded | 1 | succeeded, **attempts 0**; API: "worker pc-rtx went away while its claim waited; no job taken", 0.12 s after the kill |
  | master + master | Ctrl+C | **4.78 s** (when the claim answered the submit) | `claimed` by pc-rtx | claimed → queued "Trying again (timeout)." → claimed → succeeded | 2 | succeeded, **attempts 1** |
  | PF6b + PF6b | Ctrl+C | **0.25 s** | `queued` | queued → claimed → succeeded | 1 | succeeded, **attempts 0**; the "went away" line 0.57 s after Ctrl+C |
  | PF6b server + master worker | Ctrl+C | 4.03 s | `claimed` by pc-rtx | claimed → queued "Trying again (timeout)." → claimed → succeeded | 2 | succeeded, **attempts 1**: the worker change is needed |

  PF6a saw "2 attempts after one failure" because its job had also failed for real once (`FAKE_TRUEBEX_EXIT=5`); here the master runs show the gone claim's own share, one ended attempt and the "Trying again" message, for a job that never ran on worker 1. With Ctrl+C sent before the submit and the submit made only after the old worker had exited, master's worker took 16.4 s to exit (its claim's 20 s deadline) and nothing was lost: the bug needs a submit inside that window, which a person makes easily.
* **The worker (scope 4).** A person's Ctrl+C reproduced headlessly (a hidden new console, `SetConsoleCtrlHandler(NULL, FALSE)`, `GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)`): a client blocked in `urllib.request.urlopen` (Python 3.12, Windows 11) got its `KeyboardInterrupt` only when the server answered, 12.25 s after Ctrl+C, and the server saw the connection open throughout. The same request on a helper thread with the main thread in `join(0.25)`: `KeyboardInterrupt` and exit 0.05 s after Ctrl+C, and the server saw a reset at once. The worker's Ctrl+C path (`main()` catches `KeyboardInterrupt` and returns 0) and its `wait_s + 30` timeout were fine and are unchanged.
* **Through Cloudflare (scope 5).** A quick tunnel (`cloudflared` 2026.7.0, `tunnel --url` with an empty `--config` so the owner's `config.yml` is not read; QUIC to edge BGW) in front of a toy Starlette app whose POST waited on `request.is_disconnected()` (no app code, no data; up about a minute, then stopped). Three tries, the client gone 4.0 s after sending: closing a TLS socket → the origin saw the disconnect 3.98 s and 3.94 s after the request arrived; killing a process holding a `urllib` request → 3.20 s (the process's start-up counts in the 4 s). So through `cloudflared` a closed worker connection reaches uvicorn within about 50 ms, and PF6b works for `api.truebex.com` as served today. PF14's VM path (Cloudflare → Caddy → uvicorn) was not run; check it on staging at the cutover. Either way the lease rule covers the rest.
* **Decisions:**
  1. *Answer 204 to a gone worker.* Any status would do; 204 keeps 5.7's own two answers, and uvicorn writes nothing to a closed connection.
  2. *`base_job_id` left for the next claim to set* (Design). *`message` cleared*, as `try_claim` already did: a job that had failed for real before shows "" instead of "Trying again (…)" after a gone claim, until its next claim. *`idle_since` = now* (`_worker_idle`, as every ended attempt does); the old value is not kept.
  3. *A cancel asked while claimed ends the job `cancelled`* rather than queueing a job the user cancelled. Before, it waited for the 120 s lapse to end that way.
  4. *The session row is deleted*, not expired: it cannot hold a part, since its id was never sent.
  5. *The wake-up test waits 20 s, the route's longest* (PF14e's recipe), where the brief said 5: a missed wake-up still fails (at the deadline, `[False]`), and a loaded PC cannot push the submit past the deadline. Passing runs take well under a second either way.
  6. *The live-API fixture is the test file's own* (a `LiveApi` with the uvicorn server, so the tests can wait until it drops a connection); `conftest.py` and `test_pf12_openapi_sdks.py` are unchanged.
  7. *Ctrl+C in pytest is `_thread.interrupt_main()`* in a subprocess running the real `main()`: the same flag Windows sets, and it wakes no blocked read on any OS, so the test fails with the old worker everywhere. The real console Ctrl+C is in the live run above.
* **PF6a's risk "A stopped worker's claim can still take a job": done** for every stop that closes the connection (Ctrl+C with PF6b's worker, a kill, a closed console, a reboot that ends processes, a cloud machine's clean shutdown). It stays open, by the contract's rule, for a machine that vanishes without closing (power, network) and for a worker that goes away after its 200 was written. PF6a's human test step 8 ("wait 10 s") is no longer needed with PF6b's worker; PF6a's doc is not edited here.
* **PF14e's carry-over "the worker claim long poll's wake-up (`notify_claim`) has no test that times it": done** (`test_claim_long_poll_woken_by_a_submit`, its guard, and the real-port twin).
* **Contract:** nothing to change; the lease rule is unchanged. Proposed PATCH for the app half, §6.4 after "(at most 3 attempts)": "A claim whose worker went away before reading the answer is not an attempt: the platform gives the job back as it was (its place and attempts unchanged)." §11: 5.7's row could add "PF6b (2026-10-16): a gone worker's claim takes no job".
* **Verify gate:** see the last commit's report (filled below).
