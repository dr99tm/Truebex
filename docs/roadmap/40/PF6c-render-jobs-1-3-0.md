# PF6c — The render service follows render-jobs 1.3.0 (CL4's follow sets): output_job_id, a set's tiles jobs name the set in base_job_id, a tiles job's trigger, the render-jobs/1.3 echo, and project-log 1.2.1's action-finish.json (launch priority 2)

**Needs merged:** PF6, PF6a, PF6b, PF11c, PF4b, PF14f (all on `master` 94367b6); CL4 on the app side (the edit-to-panorama pipeline, app task T122, merged on app `main` `bc06615c6` through T190, 2026-10-25). **Unblocks:** CL4's Cloud panoramas tab against the live API (a new picture known without fetching it, another writer's edit stamped T0 / T1, Unfollow cancelling the set's own updates). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\render-jobs.md` **1.3.0** (2026-10-25, wire header `render-jobs/1.3`; its CL4 line was written as 1.2.0 beside AN3's and renumbered at the merge) and `project-log.md` **1.2.1** (2026-10-22, a PATCH: the fixture `action-finish.json`). The app side is authoritative (C.9).

## Status

**Built 2026-10-25** on `ap/t99-pf6c-the-render-service-follows` (Autopilot T99); see As-built. What was behind on `master` 94367b6, checked against app `main` `bc06615c6` before the work:

| # | Where (master 94367b6) | Before |
|---|---|---|
| 1 | `server/app/render/service.py:60-86` `record_json` | no `output_job_id`: the app (`CloudPano.cpp:698-700`) fetched 5.5 again on every new `rev` of a follow set, unable to tell a new picture from an old one |
| 2 | `service.py:82` (`"base_job_id": job.base_job_id`), `sets.py:221` (`base_job_id=row.latest_job_id or row.follow_job_id`), `queue.py:387` (the claim sets it to the newest picture) | a set's second update answered `base_job_id` = the first update, not the set: the app's Unfollow (`CloudPano.cpp:525`) skipped it and `cl4-stub-follow-set` (`CadSelfTest_CL4.cpp:481`, `Tiles1.BaseJobId == SetId`) could not hold |
| 3 | `render/models.py:46-84` (no column), `sets.py:247-267` `enqueue_from_push` (reads each op's `touched` and `server_seq` only), `projects/hooks.py:9-10` (ops as on the wire: no accepted time) | no `trigger`: the app's stage table (`RenderJobsClient.cpp:118-138`) had no T0 / T1 for another writer's edit |
| 4 | `service.py:349` (5.4 on a follow job keeps it `succeeded`, `follow` false), `service.py` `output` (serves any `succeeded` job), `routers/tiles.py:30-35` (public, immutable) | already held: 5.5 on a stopped set and tiles with no header or token (tests only). One gap found: `sets.py` `stop` cancelled only queued updates, so a running one still finished, was charged and moved the stopped set's output |
| 5 | `routers/jobs.py:31`, `workers.py:36` and `:38` (`ECHO`), `analysis.py:23`, `v1/jobs.py:25` on `contract("render-jobs", 1, 2)`; `worker/truebex_worker.py:54`; `src/lib/jobs.ts:9`; `demo_render.py:25`, `demo_analysis.py:38`, `demo_mobile.py:48`; `export_openapi.py:56` (and `API_VERSION` `:34`) | `render-jobs/1.2`; the app sends `render-jobs/1.3` (`RenderJobsClient.cpp` `ContractHeader`) |
| 6 | `server/tests/contracts/project-log/` (8 files), `test_pf4a_project_log_1_1.py:52` `APP_BLOBS`, `test_pf4b_project_log_1_2.py:163` (8 blobs) and `:188`; `src/viewer/selftest.ts:10` (action-move.json only) | no `action-finish.json` (app blob `c136e2dd`, CL4 5bf7ba130) |
| 7 | `server/app/routers/v1/models.py:429` `Job` | the `/v1/jobs` reference (`/developers/jobs/`) named none of `follow`, `base_job_id`, `output_job_id`, `trigger` |

## Goal

The app's Cloud panoramas tab works against the platform the way it works against its own stub: a viewer long-polling a followed set reads which job's picture is current and fetches the output only when that changes, sees each update of the set name the set (so Unfollow and Cancel find them), and reads on each update the operations it was queued for, so it can time another person's edit from the edit to the new picture. Old apps and workers keep working (1.0–1.2 still served), and the phone's paint edit the app published as a fixture is accepted and written the same way by the platform's own mobile client.

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4; `PF6-cloud-render-orchestration.md` (follow sets), `PF6a-render-jobs-1-1-0.md`, `PF11c-render-jobs-1-2-0.md` (the echo tests this task moves), `PF4b-project-log-1-2-0.md` (the fixture pins).
* `render-jobs.md` 1.3.0: the header, *Changes* 2026-10-22 · 1.3.0, §9's "As built (CL4, 1.3.0)" paragraph, §11's rows for 5.2–5.6. `project-log.md` 1.2.1: its change line and §9's `action-finish.json` row.
* App repo, read only (`main` `bc06615c6`): `Plugins/CADTOOL/Source/TruebexSync/Private/RenderJobsClient.cpp:115-138` (`base_job_id`, `output_job_id`, `trigger`), `CloudPano.cpp:525` and `:695-700`, `RenderJobsStub.cpp:118-180` (the stub's record) and `:311-345` (`OnOpsAccepted`), `CadSelfTest_CL4.cpp:481-485`.

## Scope

**In** (nothing was cut):

1. **`output_job_id`** on every record (5.1–5.3, 5.4's answer, the claim, `job.*` webhooks): on a follow job (following, or stopped by 5.4) the job whose manifest 5.5 serves now — its own once its first panorama succeeded, then the set's newest succeeded update (`RenderSet.latest_job_id`); null before the first picture and on every other job.
2. **`base_job_id` = the set's id** on every record of a set's `tiles` job (5.1–5.3, the follow long-poll; a share's live set and `/v1`'s panorama reads name no `base_job_id`). `render_jobs.base_job_id` keeps the newest picture the worker starts from; the claim names it `job.base_manifest_job_id` beside `inputs.base_manifest_url`.
3. **`trigger`** on a `tiles` job: a JSON column (`render_jobs.trigger`, added by `database._migrate`), written by `sets.enqueue`, extended by `sets.coalesce`; `{op_ids, first_seq, last_seq, first_op_at, first_accepted_at, authors}`; absent on other kinds, null on a `tiles` job made by POST /jobs until a push joins it. A restore (every face) names its operation.
4. **5.5 and tiles:** tests (a stopped set still serves; tiles with no header and no token). One fix the tests found: 5.4 on a follow set now also asks its running update to stop.
5. **render-jobs/1.3** on `/jobs`, `/workers` (`ECHO`), `/analysis`, `/v1/jobs`; the worker wrapper, `src/lib/jobs.ts`, the three demo scripts, `export_openapi.py` (`openapi/v1.json` 1.3.0) and the SDKs (regenerated, 1.3.0); 1.0, 1.1, 1.2 and 1.3 served, 2.0 → 400. PF11c's two echo tests moved into `test_pf6c_render_jobs_1_3.py`.
6. **project-log 1.2.1:** the app's `action-finish.json` copied byte for byte, the folder README and the pins; a push of it is accepted; PF9's `fillFace` writes the same tool, args and permission (`src/viewer/selftest.ts`).
7. **The `/v1/jobs` reference** (`/developers/jobs/`, generated from `openapi/v1.json`): the `Job` schema names `follow`, `base_job_id`, `output_job_id` and `trigger` (`JobTrigger`).
8. **`demo_render.py`** gains `jobs`, `show` and `output` (the live run and the human test read the record with them).

**Out (and where it goes):**

* PR5's id and depth tiles (render-jobs, app task T134, still queued): **a later task** once it lands on app `main`.
* A real GPU render, the RTX PC's worker update and the first live follow set: **the owner at deploy** (`api.truebex.com` is down).
* FName case of `kind` and `quality`: **PF14f** (merged first; its `enums.canonical`, `submit` and `list_jobs` kept as they are: in `service.py` only `record_json` (with its import and the module note) changed, and `test_pf14f_fname_case.py` is untouched).
* The app's own fixes (a stopped set's state word, the stub's 5.4 state): **the app half**, through the PATCH lines in As-built.

## Design

### API

| Endpoint | PF6c |
|---|---|
| every render-jobs route | `X-Truebex-Contract: render-jobs/1.3`; 1.0, 1.1, 1.2, 1.3 or no header served; another MAJOR → 400 `contract_version` with `supported` `["render-jobs/1.3"]` |
| 5.1–5.3, 5.4's answer (and `/v1`) | the record gains `output_job_id` (always present) and, on a `tiles` job, `trigger`; a set's `tiles` job answers `base_job_id` = the set (the follow job's id), any other job its own base (a client's `tiles` job: the job it updates; an `airflow` job: its wind job) |
| 5.4 on a follow job | unchanged from PF6: `succeeded`, `follow` false, `rev` moved, `output_job_id` kept; the set's queued updates `cancelled`; **new:** a claimed or running update gets `cancel_requested` ("Stopping…"), so the worker's next heartbeat answers `cancel: true` and it ends `cancelled` at no charge (a completion is refused with 409 `lease_lost`); again → 409 `job_finished` |
| 5.5 | unchanged: a stopped set still serves its last output |
| 5.7 claim | a `tiles` job's `job` adds `base_manifest_job_id` (the job whose manifest `base_manifest_url` is: the set's newest picture at the claim) |
| `GET /tiles/{sha256}.jpg` | unchanged: no token, no contract header, `Cache-Control: public, max-age=31536000, immutable`, `Access-Control-Allow-Origin: *` |

**The trigger** (`server/app/render/trigger.py`), answered as

```json
{"op_ids": ["<32 hex>", "…"], "first_seq": 13, "last_seq": 15, "first_op_at": "2026-10-25T13:02:30.000Z",
 "first_accepted_at": "2026-10-25T13:02:30.642Z", "authors": ["<32 hex author id>", "…"]}
```

* the operations of each push that changed the model (a non-empty `touched`, or a restore), in server order; a push joining a queued update adds its operations (a running update is never extended: the next push gets its own job, as the stub does);
* `first_seq` / `last_seq` the lowest and highest `server_seq`; `first_op_at` the earliest writer's `at` converted to UTC; `first_accepted_at` the earliest accepted time (`project_ops.received_at`); `authors` united in order of first appearance; times RFC 3339 UTC with milliseconds;
* at most 1000 `op_ids` (the earliest); `last_seq`, the times and `authors` still cover every operation.

### Data

One additive column: `render_jobs.trigger` JSON (`database._ADDED_COLUMNS["render_jobs"]`, NULL for every job from before), stored as `{"ops": [[seq, op_id], …], "authors": [[seq, author], …], "last_seq", "first_op_at", "first_accepted_at"}` so a merge keeps server order whatever order two pushes' hooks ran in. No other table changes; `render_jobs.base_job_id` keeps its meaning (what the job starts from).

### Jobs / workers

* `sets.enqueue_from_push` (PF4's push hook) builds the push's trigger once (one `SELECT server_seq, received_at` of the pushed operations, only when the project has an active set) and passes it to `enqueue` → a new job's `trigger`, or `coalesce` → `trigger.merge`.
* `sets.output_job_id` reads the job a follow job's `output_key` names (`jobs/<id>/manifest.json`, `tiles.manifest_job_id`): the job whose manifest 5.5 serves, by construction, with no query per record.
* `sets.stop` (5.4, an account leaving the project, a deleted project) cancels queued updates and asks claimed or running ones to stop.
* The worker wrapper sends `render-jobs/1.3`; it reads `inputs.base_manifest_url` as before (it never read `job.base_job_id`).

### UI

No page change. `src/lib/jobs.ts`: the 1.3 header, `JobRecord` gains `base_job_id`, `output_job_id` and `trigger?: JobTrigger | null`. `/developers/jobs/` lists the four record keys from the regenerated `openapi/v1.json` (field descriptions in `routers/v1/models.py`). `src/viewer/selftest.ts` (PF9) checks the fill against `action-finish.json`.

### Security and privacy

A trigger names operation ids, sequence numbers, times and author ids the record's reader can already pull from the project's log (5.7 needs a membership; a job is visible only to its account). Tiles stay public by content hash (no change). A stopped set no longer charges for an update that was running when it stopped.

## Deliverables

- [x] `server/app/render/trigger.py` (new), `render/{models,service,sets,tiles,queue}.py`, `server/app/database.py` (one column)
- [x] `server/app/routers/{jobs,workers,analysis}.py`, `routers/v1/{jobs,models}.py`; `server/scripts/export_openapi.py`, `openapi/v1.json` (1.3.0), `sdks/` (regenerated by `scripts/gen-sdks.ps1`, versions 1.3.0)
- [x] `worker/truebex_worker.py` (`CONTRACT`), `src/lib/jobs.ts`, `server/scripts/{demo_render,demo_analysis,demo_mobile}.py` (`demo_render.py` gains `jobs`, `show`, `output`)
- [x] `server/tests/contracts/project-log/action-finish.json` (the app's blob) and its README; `src/viewer/selftest.ts`
- [x] tests: `server/tests/test_pf6c_render_jobs_1_3.py` (12); the assertions 1.3 moves (As-built)
- [x] `README.md` (one section at the end), this doc, the PF6c tracker row

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf6c_follow_set_record` | pytest | before its first picture `output_job_id` null; after it, the follow job's own id; a push's update answers `base_job_id` = the set (5.2, 5.3) and `output_job_id` null; its claim starts from the set (`base_manifest_job_id`, the base manifest's `job_id`); after it succeeds the follow job's `output_job_id` is the update (= `RenderSet.latest_job_id`), 5.5 serves its manifest, `/v1`'s panorama read names it; a second update answers the set too while its claim starts from the first update's picture (the internal `base_job_id` too); a plain panorama answers null |
| `test_pf6c_trigger_and_coalesce` | pytest | two pushes by two people before a claim join one update: both `op_ids` in server order, `first_seq` / `last_seq`, `first_op_at` the earlier writer's `at` (written with +03:00), `first_accepted_at` the first push's accepted time (ms), both authors; the claim carries it; a push after the claim gets its own job and trigger, the running one unchanged; a client's tiles job joining the queued one keeps the trigger; a two-operation push extends it; a POST /jobs tiles job: `trigger` null; other kinds: no key |
| `test_pf6c_restore_records_its_op` | pytest | a restore queues an every-face update whose trigger names the restore operation, its sequence, the server's `at`, its accepted time, the person who restored |
| `test_pf6c_trigger_merge_rules` | pytest | the module: server order when the later push's hook ran first, the earliest times, authors by first appearance, ids united, the accepted-time fallback, the 1000-id cap with `last_seq` the highest |
| `test_pf6c_trigger_column_migrated` | pytest | `_migrate` adds `render_jobs.trigger` to a table from before |
| `test_pf6c_stopped_set_still_serves` | pytest | 5.4 on the follow job: `follow` false, `output_job_id` unchanged (5.2, 5.3), 5.5 still the last output, the queued update cancelled, again 409 `job_finished`, a later push queues nothing, nothing to claim |
| `test_pf6c_stop_ends_the_running_update` | pytest | 5.4 while an update renders: "Stopping…", the next heartbeat answers `cancel: true`, the update `cancelled` with no cost, a completion 409 `lease_lost`, the set's output and `output_job_id` unchanged, no cost units used |
| `test_pf6c_tiles_need_no_header_or_token` | pytest | a stopped set's tiles: 200 with no `Authorization` and no `X-Truebex-Contract`, `public, max-age=31536000, immutable`, `*`, `image/jpeg`, the fixture's bytes, no contract echo; an unknown tile 404 `not_found` |
| `test_pf6c_echo_1_3` (PF11c's routes test, moved) | pytest | 1.0, 1.1, 1.2, 1.3 and no header on 5.1–5.6, `/analysis/catalogue`, 5.7 (200 and 204), 5.8, 5.9 (repeat), 5.10, the wind kind's 5.1 and claim, `/v1/jobs` 5.1–5.3 / 5.6 → `render-jobs/1.3`; 2.0 → 400 with `supported` 1.3; `RJ` is what CL4 sends |
| `test_pf6c_clients_and_documents_speak_1_3` (PF11c's documents test, moved) | pytest | the four routers on (1, 3), `ECHO`, the wrapper, `jobs.ts` (and its `JobRecord` keys, `JobKind` airflow), the admin page, the three demos, `export_openapi.py`, `openapi/v1.json` (every jobs operation 1.3, document ≥ 1.3.0, the `Job` keys with descriptions, `JobTrigger`'s six keys), both SDKs' operations and types, PF11c's label and demo flags, `demo_render.py`'s new commands |
| `test_site_pf6c_developers_jobs_names_the_follow_keys` | build check | the built `/developers/jobs/` page names `output_job_id`, `base_job_id`, `trigger`, `JobTrigger`, `first_accepted_at` |
| `test_pf6c_action_finish_fixture` | pytest | the blob id `c136e2dd`, LF, in `APP_BLOBS` and the README; its shape (a `fill` of `wall#<touched>`, left face, paint `#C0392B`, Sam's author id); with the app repo present, the wall is `PR3-pano-rooms.tbxp`'s wall 6 whose centreline bounds the "Living Room" region, and the copy equals the blob at `bc06615c6`; Sam's push of it accepted and pulled back unchanged, its update's trigger names it; `selftest.ts` builds it with `fillFace`, and the built self-test passes ("the app's fill") |
| PF6's, PF6a's, PF6b's, PF11c's, PF11b's, PF12's, PF4a's, PF4b's, PF14f's suites | pytest | green with the moved assertions (As-built) |
| `npm run lint`, `npm run build` | build check | green; `out/viewer/selftest.mjs` passes |

## Human test

About 5 minutes, on this PC, against a local API with the fake render worker (no GPU). Three PowerShell windows; `<WT>` = `X:\Truebex-autopilot\t99-pf6c-the-render-service-follows`.

1. **API (window A).** `cd <WT>\server`, then `.venv\Scripts\python.exe scripts\make_signing_key.py --kind lic` and copy the value after `LICENCE_SIGNING_KEY=` into:
   `Set-Content .env -Encoding ascii -Value 'DATABASE_URL=sqlite:///./pf6c-human.db','SECRET_KEY=pf6c-human-test-0123456789abcdef0123456789abcdef','API_URL=http://127.0.0.1:8000','LICENCE_SIGNING_KEY=<paste>','LICENCE_KEY_ID=lic-2026-10'`
   then `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` → "Uvicorn running on http://127.0.0.1:8000".
2. **Account, device and worker (window B, `cd <WT>\server`).**
   `$S = (Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/register -ContentType 'application/json' -Body '{"email":"pf6c@example.com","password":"pf6c-password"}').access_token`
   `.venv\Scripts\python.exe -m app.admin_cli pf6c@example.com` → "pf6c@example.com: admin on".
   `.venv\Scripts\python.exe scripts\demo_replica.py login --email pf6c@example.com --password pf6c-password --trial` → "Pro trial started", your `author_id` and "device token: tbx_dev_…"; set `$D = '<that token>'`.
   `$W = (Invoke-RestMethod -Method Post http://127.0.0.1:8000/admin/workers -Headers @{Authorization="Bearer $S"} -ContentType 'application/json' -Body '{"name":"pc-local","kinds":["panorama","tiles","pack"],"class":"gpu-std"}').token`
   `$T = "$env:TEMP\pf6c-worker.toml"`
   ``Set-Content $T -Encoding ascii -Value 'api = "http://127.0.0.1:8000"',"token = `"$W`"",'worker_id = "pc-local"','kinds = ["panorama", "tiles", "pack"]','class = "gpu-std"',"app = 'X:\Truebex-autopilot\t99-pf6c-the-render-service-follows\worker\tests\fake_truebex.py'",'app_version = "1.1.0"','doc_version_max = 55',"work_dir = '$env:TEMP\pf6c-jobs'",'keep_work = true','heartbeat_s = 5','wait_s = 2','face_px = 512','tile_px = 256','jpeg_quality = 85'``
3. **A project and a followed set.** `.venv\Scripts\python.exe scripts\demo_replica.py --token $D push` → "pushed: 12 accepted" and "project id: …"; set `$P = '<that id>'`. `.venv\Scripts\python.exe scripts\demo_render.py --token $D submit --project $P --follow` → "panorama job queued at operation 12: estimate 4.5 cu" and "job id: …"; set `$SET = '<that id>'`.
4. **The first picture.** `.venv\Scripts\python.exe ..\worker\truebex_worker.py --config $T --once` → "complete <SET>: 18 faces rendered, 90 files sent". `.venv\Scripts\python.exe scripts\demo_render.py --token $D show --job $SET` → `follow: true`, `base_job_id: None`, `output_job_id: <SET>` (its own picture).
5. **One edit.** `.venv\Scripts\python.exe scripts\demo_replica.py --token $D move --project $P` → "accepted as 13 (head 13)". `.venv\Scripts\python.exe scripts\demo_render.py --token $D jobs --kind tiles` → one line "<id>  tiles  queued … at 13  base_job_id <SET>, trigger 1 op(s) 13-13"; set `$TJ = '<that id>'`. `… show --job $TJ` → `base_job_id: <SET>`, `output_job_id: None` and a trigger with one op id, `first_seq` 13, `last_seq` 13, `first_op_at` (the edit's time, `.000Z`), `first_accepted_at` (a moment later, with milliseconds) and `authors` = the `author_id` step 2 printed.
6. **The update.** Run the worker line of step 4 again → "complete <TJ>: 13 faces rendered, 65 files sent". `… show --job $SET` → `output_job_id: <TJ>`. `… output --job $SET` → "5.5 on <SET>: the manifest of job <TJ> at operation 13, 13 faces rendered, 5 carried".
7. **Stop following, old clients.** `(Invoke-RestMethod -Method Post "http://127.0.0.1:8000/jobs/$SET/cancel" -Headers @{Authorization="Bearer $D"; "X-Truebex-Contract"="render-jobs/1.0"}) | Select-Object state, follow, output_job_id` → `succeeded  False  <TJ>`. `… output --job $SET` → still the manifest of `<TJ>`. `(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/jobs/usage -Headers @{Authorization="Bearer $D"; "X-Truebex-Contract"="render-jobs/1.2"}).Headers["X-Truebex-Contract"]` → `render-jobs/1.3`.
8. **The reference page (window C, `cd <WT>`).** `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → "serving … on http://127.0.0.1:3199/" (use the port it prints). Open `http://127.0.0.1:3199/developers/jobs/`: the job record's fields (for example under "GET /v1/jobs/{job_id}") list `follow`, `base_job_id`, `output_job_id` and `trigger` (`JobTrigger`), each with its description.
9. **Clean up.** Stop uvicorn and the server (Ctrl+C), then delete `server\.env`, `server\pf6c-human.db`, `server\storage`, `$env:TEMP\pf6c-jobs` and `$env:TEMP\pf6c-worker.toml`.
10. **Optional, the owner's:** the app's Shipping release signed in against `https://api.truebex.com` with a render worker: follow a cloud panorama, have a second account edit the project (its row in the stage table shows T0 / T1 stamps), and Unfollow cancels the queued update (needs the API up and a GPU worker).

## Risks / traps

* **Two meanings of `base_job_id`.** The column stays what the job starts from (5.9's carried-face check and tile collection read it); only the record answers the set. Anything new that needs the set reads `set_id` / `sets.record_base`, anything that needs the picture reads the column.
* **A trigger grows while its update waits.** Capped at 1000 ids (a 5.3 page holds up to 100 records and every long poll carries one).
* **The hook's ops are the wire form:** no accepted time in them, so the hook reads `project_ops.received_at` (PF12's webhook observer subscribes to the same hook; its payloads stay unchanged).
* **The verify gate under load:** the whole suite on Postgres in four parallel groups overran one 39-minute call; groups were re-run in smaller parts (As-built).

## As-built

**2026-10-25, Autopilot T99, branch `ap/t99-pf6c-the-render-service-follows`** (base `master` 94367b6, PF14f merged). Commits: 3c877f8 (the tests first), ebefb18 (the record), 6ca5a1d (the 1.3 echo, documents and SDKs), d6a7bb1 (`action-finish.json`, PF9's check), b329185 (5.4 ends a running update), f6564d4 (the doc, tracker row, README), 790c206 (the reference names the trigger's keys), then this As-built's gate line.

* **Counts:** pytest 962 → 972 collected: 12 new in `test_pf6c_render_jobs_1_3.py`, 2 moved out of `test_pf11c_render_jobs_1_2.py`. On the base, the first nine written failed (`KeyError: 'output_job_id'`, no `trigger` module, no column, the echo, the documents, the missing fixture), the tiles test passed (it proves what held), the site test skipped (no `out/`); the later stop test failed there too (`cancel` false at the heartbeat). Verify gate: the last bullet.
* **The base_job_id decision:** the column and the ORM attribute keep the newest-picture base (the claim re-sets it, `queue.complete`'s carried-face check and `tiles.referenced` (the tile collector) read it, PF11c's airflow keeps its wind job there); the record answers `sets.record_base(job)` = `set_id` for a set's `tiles` job. The claim's `job` carries the column as `base_manifest_job_id` (the worker reads only `base_manifest_url`, so `test_pf6a_render_worker.py`, `test_render_worker.py` and `test_pf6a`'s claim assertions are unchanged: on a first update the set and its newest picture are the same job). No column was renamed (not additive).
* **Where trigger's accepted time comes from:** `project_ops.received_at`, read by `sets.enqueue_from_push` by `server_seq` (one query per push to a project with an active set). The hook's op dicts are left in the wire form: PF12's webhook observer gets the same list.
* **output_job_id** is derived from the follow job's `output_key` (`tiles.manifest_job_id`): the job whose manifest 5.5 serves, with no query per record; the test checks it against `RenderSet.latest_job_id`.
* **Which operations a trigger names:** those with a non-empty `touched`, and restores (a push of operations touching nothing queues nothing, as before). Times: RFC 3339 UTC with milliseconds (`first_op_at` converted from the writer's zone). Cap: 1000 ids, the earliest.
* **Beyond the brief (found by the stop tests):** `sets.stop` also asks a claimed or running update to stop; without it a running update finished after 5.4, was charged, and changed the stopped set's `output_job_id`. The app's stub cancels it too.
* **5.4's state on a follow set left as PF6 built it:** `succeeded` with `follow` false (5.5 keeps serving, as 1.3.0 says); the stub answers `cancelled`. PATCH line A.
* **Assertions moved (1.3 only):** `render_helpers.py` and `pf12_helpers.py` `RJ` 1.3 (what CL4 sends); `test_render.py` the echo and `supported` 1.3; `test_pf6b_claim_long_poll.py`, `test_pf12_api.py` the echo 1.3; `test_pf11b_ai_proxy_1_1.py` `demo_analysis.py` on 1.3; `test_pf6a_render_jobs_1_1.py` `ECHO` 1.3, the routers on (1, 3), the wrapper / `jobs.ts` / `demo_render.py` / SDK strings and the README header on 1.3; `test_pf11c_render_jobs_1_2.py` `ECHO` 1.3 (its 5.5 check), `RJ12` kept on 1.2 (AN3's client, still served), and **its two echo tests moved** (not renamed) to `test_pf6c_render_jobs_1_3.py` as `test_pf6c_echo_1_3` (with PF6a's 5.2, 5.4, 5.5 and 5.9 cases) and `test_pf6c_clients_and_documents_speak_1_3`; `test_pf4a_project_log_1_1.py` `APP_BLOBS` +1, `CL1_BLOBS` without it; `test_pf4b_project_log_1_2.py` nine blobs, CL2's commits checked against the eight. Setup only: none.
* **The documents:** `openapi/v1.json` 1.3.0 (it grew: four `Job` keys, `JobTrigger`, the 1.3 header), the SDKs 1.3.0 regenerated with `scripts\gen-sdks.ps1` (its pinned datamodel-code-generator and openapi-typescript installed into `.sdk-tools\`; the generated diff is the new keys alone).
* **project-log 1.2.1:** `action-finish.json` = app blob `c136e2dd7b71e6f40e7647e56d80665cbd391dca` (CL4 5bf7ba130, on `main` bc06615c6), copied with `git cat-file blob` from inside the app checkout (LF). PF4's push takes it unchanged (no `session` / `request_id`); `src/viewer/selftest.ts` `finishBuilder` builds the same fill with `fillFace(ref(wall), "left", {kind: "paint", colour: "#C0392B"})`: tool, args (bytes), permission, touched and the other keys equal (117 checks in the self-test).
* **Postgres 17 (a throwaway cluster, zone Asia/Baghdad):** every test of the suite ran there. Four parallel groups: one finished green (216 passed, 27 skipped); the other three were stopped at the 39-minute window with 521 passed, 6 skipped, 3 failed, and their unfinished files re-ran in four smaller groups (177 passed, 61 skipped). The 3: `test_pf6a_no_router_or_client_left_on_1_0` (the README check, before this README section), `test_billing_pf2.py::test_billing_paddle_webhook_signature` (the second-boundary flake) and `test_pf9_pf12_meet.py::test_key_reads_a_followed_set_after_its_own_edit` (`reader.took < wait_s / 2` with four suites at once); the last two passed alone on the same cluster. After the stop fix and the README: `test_pf6c`, `test_pf6a`, `test_render`, `test_pf6b`, `test_pf4b` 76 passed, 1 skipped (no `out/`).
* **Live run** (a local API on :18099, `demo_replica.py login --trial`, the fake worker with `doc_version_max = 55`; abridged):

  ```
  panorama job 2966c496…: queued, rev 1, at operation 12      follow: true   base_job_id: None   output_job_id: None
  complete 2966c496…: 18 faces rendered, 90 files sent, 0.3 s, 0.1 cu
  panorama job 2966c496…: succeeded, rev 4                    output_job_id: 2966c496bfec837f058fb42369642133
  accepted as 13 (head 13)
  0aa05160…  tiles  queued  rev 1  at 13  base_job_id 2966c496bfec837f058fb42369642133, trigger 1 op(s) 13-13
  trigger: {"op_ids": ["349c0575e47c0005915a57ba541a0928"], "first_seq": 13, "last_seq": 13,
            "first_op_at": "2026-10-25T13:02:07.000Z", "first_accepted_at": "2026-10-25T13:02:08.122Z",
            "authors": ["01a17326f4557bff92596894b053b324"]}
  complete 0aa05160…: 13 faces rendered, 65 files sent, 0.2 s, 0.1 cu
  panorama job 2966c496…: succeeded, rev 5, at operation 13   output_job_id: 0aa05160b9eccf5f3c2980053289fd1a
  5.5 on 2966c496…: the manifest of job 0aa05160… at operation 13, 13 faces rendered, 5 carried
  accepted as 14 / accepted as 15  ->  tiles job 07294164…: queued, rev 2, at operation 15, base_job_id 2966c496…,
            trigger op_ids [4ad5e060…, 3a82b905…], first_seq 14, last_seq 15
  complete 07294164…: 13 faces rendered, 0 files sent   (its base.json: job_id 0aa05160…, the first update's picture)
  panorama job 2966c496…: succeeded, rev 6, at operation 15   output_job_id: 0729416477166d48e0c9c50be5aaacb6
  5.4 -> x-truebex-contract: render-jobs/1.3; succeeded, follow false, output_job_id 07294164…; 5.5 still that manifest
  GET /tiles/<sha>.jpg (no token, no header) -> 200, public, max-age=31536000, immutable, image/jpeg
  ```

  The human test's PowerShell lines were dry-run literally (on another port) with the same answers.
* **Contract, for the app half** (the app's docs are read-only here). §11, the platform cells: `POST /jobs` "PF6 (PF11 for analyses): implemented; 1.3.0 by PF6c 2026-10-25 (`test_submit_estimate_and_idempotency`, `test_pf6c_echo_1_3`)"; `GET /jobs/{job_id}` "PF6, PF6c: implemented 2026-10-25 — `follow`, `base_job_id` = the set on a set's `tiles` job, `output_job_id`, a `tiles` job's `trigger`, long-poll on `rev` (`test_pf6c_follow_set_record`, `test_pf6c_trigger_and_coalesce`)"; `GET /jobs` "PF6, PF6c: implemented 2026-10-25 (`test_pf6c_follow_set_record`)"; `POST /jobs/{job_id}/cancel` "PF6, PF6c: implemented 2026-10-25 (`test_pf6c_stopped_set_still_serves`, `test_pf6c_stop_ends_the_running_update`)"; `GET /jobs/{job_id}/output` "PF6 (PF11, PF11c), PF6c: implemented 2026-10-25 (`test_pf6c_stopped_set_still_serves`, `test_pf6c_tiles_need_no_header_or_token`)"; `GET /jobs/usage` "PF6: implemented (`test_cost_units_and_quota`)". The header's status "platform not yet" → "platform PF6 / PF6a / PF11c / PF6c". project-log §9's `action-finish.json` row: "accepted by PF4's 5.6; PF9's `fillFace` writes the same tool, args and permission (`test_pf6c_action_finish_fixture`, PF6c)". PATCH lines proposed (1.3.1):
  * **A.** 5.4 on a follow set: name the state it leaves. The platform answers `succeeded` with `follow` false and `output_job_id` kept (5.5 keeps serving, a second 5.4 → 409 `job_finished`); the stub answers `cancelled`. `CloudPano.cpp:695` counts a set stopped only on `cancelled`, `expired` or failed-not-following, so against the platform a set another client stopped keeps being polled and reads "done": the app's fix is to read `succeeded` with `follow` false as stopped too.
  * **B.** `base_job_id`'s meanings (5.1 and §2): in a 5.1 request (`tiles`) the job it updates (a finished panorama or update; one of a set joins the set's queued update); in a record, a set's `tiles` job names the set, any other `tiles` job its base, an `airflow` job its wind job.
  * **C.** A restore's trigger names the restore operation (the server's own: `touched` empty, `changed` every face, `at` the server's clock).
  * **D.** A trigger names only the operations that changed the model (a non-empty `touched`, or a restore); the stub names every operation of the call.
  * **E.** `op_ids` lists at most 1000 operations, the earliest; `first_seq`, `last_seq`, the two times and `authors` cover all of them.
  * **F.** The trigger's times are RFC 3339 UTC with milliseconds; `trigger` is absent on other kinds and null on a `tiles` job made by 5.1 until a push joins it (the stub omits the key).
  * **G.** 5.4 on a follow set also stops its running update (the stub cancels it at once; the platform asks it to stop, so it ends `cancelled` at the worker's next heartbeat, at no charge).
  * **H.** 5.7: a `tiles` job's `job` carries `base_manifest_job_id`, the job whose manifest `base_manifest_url` is (additive; the record's `base_job_id` names the set).
* **Carry-over:** PR5's id and depth tiles (app T134) → a later platform task; the real GPU render, the RTX PC's worker update (render-jobs/1.3) and the first live follow set → the owner at deploy; the app's `bStopped` (A) and the stub's 5.4 / trigger rules (A, D–G) → the app half.
  * PR5's id and depth tiles → **PF6d** (`PF6d-render-jobs-1-4-0.md`, 2026-11-09: render-jobs 1.4.0's face files, version and op_seq, the tour).
* **Verify gate** (`scripts\autopilot-verify.ps1`, absolute `-File`): green in 806 s (build compiled in 14.6 s, pytest 737 s): 972 collected, 953 passed + 19 skipped. The first run (1,537 s) failed only `test_site_pf6c_developers_jobs_names_the_follow_keys`: `/developers/jobs/` lists a schema's own fields and not a nested schema's, so `trigger`'s description now names its six keys (790c206).
