# PF6a — Cloud render orchestration follows render-jobs 1.1.0 (CL3): the app's own fixtures re-copied, the job file's `snapshot_seq`, `-mwrender` exit codes, the render-jobs/1.1 echo (launch priority 2)

**Needs merged:** PF6 (and PF9, PF10, PF11, PF12, PF12a, PF3b, PF14d, PF14e, all on `master` cc905d3); CL3 on the app side (the headless render service mode, merged on app `main` `ad3aa5c45`, 2026-10-14 21:29 UTC). **Unblocks:** CL3's `Truebex.exe -mwrender=<job.json>` as the worker's app against the real queue; CL4 (the edit-to-panorama loop). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\render-jobs.md` **1.1.0** (2026-10-14; the app side is authoritative, C.9). Every render-jobs route now answers `X-Truebex-Contract: render-jobs/1.1`.

## Status

**Built 2026-10-15** on `ap/t84-pf6a-cloud-render-orchestration` (Autopilot T84); see As-built. What was behind on `master` cc905d3, checked against app `main` `ad3aa5c45` before the work:

| # | Where (master cc905d3) | Before |
|---|---|---|
| 1 | `server/tests/contracts/render-jobs/` | PF6's stand-ins (`server/scripts/make_render_job_fixtures.py`, b2d6127): one drawn view, 40 tiles; every shared file differed from the app's 162 (written by the app's own `-mwcl3fixtures`, folder last changed in app commit `4ed19a00d`); PF6's `claim.json`, `ops-*.json` and PF11's wind set lived in the contract folder although the app publishes none of them |
| 2 | the readers | PF6's ids wired in: `render_helpers.py` (`VIEW` "Living room" `0199c6a2e000700580…`, `WALL`), `test_render*.py`, `worker/tests/fake_truebex.py`, `test_mobile.py`, the PF9 / PF10 / PF12a meet tests, `src/viewer/selftest.ts` (it assumed `views[0]`'s `n` and `e` changed), `mobile/android/test/` (24 tiles) |
| 3 | `worker/truebex_worker.py` `job_file` | no `project.snapshot_seq` (1.1.0: absent = the lowest op sequence minus 1, undefined for an empty `ops` list); `params` written whole for every kind |
| 4 | the same file, a non-zero exit | always `render_crash` without `out_dir/error.json`; 1.1.0 and CL3 fix the codes: 0 ok, 2 `bad_input`, 3 `doc_too_new`, 4 `render_crash`, 5 `out_of_memory`, 6 `timeout`, 7 `engine_error` |
| 5 | `routers/{jobs,workers,analysis}.py`, `routers/v1/jobs.py`, `export_openapi.py`, `openapi/v1.json`, `sdks/`, `src/lib/jobs.ts`, `README.md` | `render-jobs/1.0` everywhere (CL3's client sends 1.1, already accepted: only the MAJOR is checked) |

Already fine, verified only: `render/tiles.py` `REASONS` accepts `light`; view ids are opaque 32 hex (CL3 derives a saved camera's with `CadEntityIds::Derive`); the feature key is `cloud.panoramas` (`test_jobs_submit_requires_feature_and_auth`).

## Goal

The desktop app's own headless renderer (CL3) runs on the platform's workers as it is: the worker hands it the job file 1.1.0 describes, a crash or a refusal reaches the queue as the right failure (a bad project is not retried, a crash is), and the platform's tests are the app's own renders of PR3's three rooms, so what passes here passes with the real app.

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4; `PF6-cloud-render-orchestration.md` (Design, As-built deviation 1, Carry-over "CL3"); `PF5b-share-bundle-1-1-0.md` and `PF7d-…md` (how a fixture set is re-copied and pinned by blob id).
* `render-jobs.md` 1.1.0: *Changes* 2026-10-14, §5.10, §6.1, §6.2, §9, §11.
* App repo, read only: `Docs/roadmap/40/CL3-headless-render-service-mode.md` ("What runs", "Carry-over", human test steps 2–4); `Docs/roadmap/fixtures/contracts/render-jobs/`.

## Scope

**In** (nothing was cut):

1. **The stand-ins first.** `git mv` `claim.json`, `ops-empty.json`, `ops-move-wall.json`, `wind-result.json`, `wind-*.bin` (and the folder's `.gitattributes`) to `server/tests/fixtures/render/`, with a README: the platform's own until AN3 and the app publish theirs. `test_render.py` (`claim.json`), `test_analysis.py` and the stub solver (the wind set) read them there. `make_render_job_fixtures.py` now writes (and `--check`s) only those files there.
2. **The re-copy.** `scripts\sync-contract-fixtures.ps1 -Contract render-jobs` (162 files, every blob id equal); the folder README rewritten for CL3's set; a blob-id check without the app repo (`APP_BLOBS` + the git tree id of `tiles/`).
3. **Every reader on the app's set**: the app's project id, three view ids and the tiles job's nine changed ids; `src/viewer/selftest.ts` computes the changed faces from the manifest.
4. **The wrapper**: `project.snapshot_seq`, `project_id` kept, a pack's `params` as `{items}`, `-mwrender`'s exit codes, `render-jobs/1.1`, `levels` left to the app; `fake_truebex.py` exits with a given code and reads the new set.
5. **The echo**: `contract("render-jobs", 1, 1)` on `/jobs`, `/workers`, `/analysis`, `/v1/jobs`; the claim's literal headers; `export_openapi.py`, `openapi/v1.json`, `sdks/`; `src/lib/jobs.ts`, the README lines. A 1.0 client keeps working.
6. Record only: CL3's measured times (below); `render/estimates.json` unchanged (PF6's rule is 50 real jobs of a kind).

**Out (and where it goes):**

* Analysis fixtures (§6.3, wind / energy): AN3's, later; the stand-ins stay the platform's in `server/tests/fixtures/render/`.
* The platform column of the contract's §11: the app half updates the contract (cells proposed in As-built).
* CL4's edit-to-tiles latency and the app's Cloud panorama command (CL4); GD3's provider and estimate seeds.
* Copying `PR3-pano-rooms.tbxp` into the platform: no test here needs to open it (the optional real-app human test copies it from the app repo).

## Design

### API

No new endpoint. Every render-jobs route serves `render-jobs/1.1`:

| Router | PF6a |
|---|---|
| `routers/jobs.py` (5.1–5.6), `routers/analysis.py` (PF11), `routers/v1/jobs.py` (PF12) | `contract("render-jobs", 1, 1)`: a 1.0 or 1.1 request (or none) is served and answered 1.1; 2.0 gets 400 `contract_version` with `data.supported` `["render-jobs/1.1"]` |
| `routers/workers.py` (5.7–5.10) | the same, and `ECHO` for 5.7's own `JSONResponse` / 204 (a returned Response does not carry the dependency's header) |
| `export_openapi.py` → `openapi/v1.json`, `sdks/python/truebex/_operations.py`, `sdks/js/src/operations.mjs` | the six `/v1/jobs` operations' `x-truebex-contract` `render-jobs/1.1` (regenerated with `export_openapi.py --v1` and `sdks/generate.py`; the schemas and `models.py` / `schema.d.ts` are unchanged) |

### The job file the wrapper writes (§6.1, 1.1.0)

```json
{"schema": "truebex-render-job/1", "job_id": "…", "kind": "tiles", "quality": "standard", "seed": 1,
 "project": {"tbxp": "C:/…/jobs/<id>/project.tbxp", "tbxpack": null, "ops": "C:/…/jobs/<id>/ops.json",
             "at_seq": 13, "snapshot_seq": 12, "project_id": "<32 hex>"},
 "views": ["<32 hex>", …], "changed": ["<32 hex>", …], "base_manifest": "C:/…/jobs/<id>/base.json",
 "face_px": 2048, "tile_px": 512, "jpeg_quality": 85, "out_dir": "C:/…/jobs/<id>/out"}
```

* `project.snapshot_seq` = the claim's `inputs.snapshot.at_seq` (the operations file starts after it, `render/queue.py` `claim_inputs`); absent when the claim has no snapshot (the app then counts from the operations). `project_id` stays (the manifest's).
* Paths stay absolute (1.1.0 resolves only relative paths against the job file's folder).
* `levels` is not written: the app's default (`face_px` halved down to `tile_px`: 512, 1024, 2048 for the worker's 2048 / 512) is what PF6's Design names, and a second source for it would only drift. `params` only for a `pack`, as `{"items": […]}` (1.1.0 names `params.items`); other kinds have none.

### `-mwrender`'s exit codes (5.10 per code)

| Exit, no `out_dir/error.json` | 5.10 `code` | `retryable` |
|---|---|---|
| 2 | `bad_input` | no |
| 3 | `doc_too_new` | no |
| 4 | `render_crash` | yes |
| 5 | `out_of_memory` | yes |
| 6 | `timeout` | yes |
| 7 | `engine_error` | yes |
| any other non-zero | `render_crash` | yes |
| stopped after `job_timeout_s` | `timeout` | yes |

`error.json`'s `code` wins when it names a 5.10 code (an unknown one falls back to the exit code's); `retryable` is "not `bad_input` and not `doc_too_new`" of the code sent; the message says which (`exit 3 without out_dir/error.json (doc_too_new)`). Container mode (PF11's solver images) is unchanged.

### The fake app (`worker/tests/fake_truebex.py`)

Answers from the app's set as CL3 would: relative paths against the job file's folder; `bad_input` (exit 2) for a broken §6.1 file, a missing snapshot, operations or base manifest, or an operation at or before `snapshot_seq`; each job view takes the fixture view with its id (else the one at its place); a `panorama` job gets `manifest-panorama.json`'s faces; a `tiles` job renders the faces `manifest-tiles.json` renders and carries the rest from the base manifest, flipping a rendered face between the two manifests' tiles on every edit (the viewer sees the swap). `FAKE_TRUEBEX_FAIL=<code>` writes `error.json` and exits with the code's number; `FAKE_TRUEBEX_EXIT=<n>` exits `n` (alone: with no `error.json`).

### Data, UI, jobs

No table, column, page or task changes. `src/lib/jobs.ts` sends `render-jobs/1.1`; `demo_render.py` submits the app's three views by default (`--view` repeatable).

### Security and privacy

Nothing changes: the job file names only paths in the job's own work folder; the fixtures are the app's renders of a test project.

## Deliverables

- [x] `server/tests/contracts/render-jobs/` = the app's 162 files (app `main` `ad3aa5c45`, folder last changed in `4ed19a00d`) + the platform's README
- [x] `server/tests/fixtures/render/` (PF6's and PF11's stand-ins, moved, + README); `server/scripts/make_render_job_fixtures.py` (writes and `--check`s only those)
- [x] `worker/truebex_worker.py` (`job_file`, `failure`, `EXIT_CODES`, `CONTRACT`), `worker/tests/fake_truebex.py`, `worker/worker.toml.example`
- [x] `server/app/routers/{jobs,workers,analysis}.py`, `server/app/routers/v1/jobs.py`, `server/app/render/__init__.py` (docstring)
- [x] `server/scripts/export_openapi.py`, `openapi/v1.json`, `sdks/python/truebex/_operations.py`, `sdks/js/src/operations.mjs`
- [x] `src/lib/jobs.ts`, `src/viewer/selftest.ts`; `README.md` (the Cloud rendering lines + a PF6a section at the end)
- [x] `server/scripts/demo_render.py`, `server/scripts/seed_member_usage.py`
- [x] tests: `server/tests/test_pf6a_render_jobs_1_1.py`, `server/tests/test_pf6a_render_worker.py`; readers updated (As-built lists them); `mobile/android/test/{helpers,sync_engine_test,viewer_offline_test}.dart`
- [x] this doc, the PF6a tracker row

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf6a_contract_folder_is_the_apps_copy` | pytest | the folder is the app's 7 files, `tiles/` and the README; each file's git blob id (`sha1(b"blob %d\0" % len + data)`) is `APP_BLOBS`'s, LF; the 155 tiles' git tree id is `APP_TILES_TREE` and each tile's name is its SHA-256; the README names both app commits and every file |
| `test_pf6a_recorded_blobs_are_the_apps_at_the_commit` | pytest (app repo present) | `git ls-tree` / `git rev-parse` at app `ad3aa5c45` agree with `APP_BLOBS` and `APP_TILES_TREE` |
| `test_pf6a_stand_ins_live_in_fixtures_render` | pytest | `tests/fixtures/render/` holds exactly the stand-ins + README (AN3 named); none left in the contract folder; `make_render_job_fixtures.py --check` green |
| `test_pf6a_apps_set_is_pr3s_three_rooms` | pytest | project id, views, sizes, `app_version`; 18 `full` / 90 tiles; 13 rendered (`light` for entry and living, `changed` for bedroom `w`) and 5 carried with the base's hashes, 65 new tiles; both pass `check_manifest`; `job-tiles.json` `snapshot_seq` 0 and relative paths |
| `test_pf6a_followed_panorama_and_update_with_the_apps_manifests` | pytest | the app's project id and three views: 4.5 cu estimate; completes with `manifest-panorama.json`; a push of the nine ids queues one tiles job (`changed` = them, base = the panorama); completes with `manifest-tiles.json`; 5.2 rev moved, 5.5 13 / 5; `/s/{slug}/live` (a real PF5 share) and `/v1/projects/{id}/panoramas/{set}` serve it |
| `test_pf6a_routes_echo_render_jobs_1_1` | pytest | 5.1–5.6, 5.7 (200 and 204), 5.8, 5.9 (repeat), 5.10, `/analysis/catalogue`, `/v1/jobs` (5.1, 5.2, 5.3, 5.6): 1.0, 1.1 and no header served with the 1.1 echo; 2.0 → 400 `contract_version`, `supported` 1.1; errors echo too |
| `test_pf6a_no_router_or_client_left_on_1_0` | pytest | no `render-jobs/1.0` in `server/app`; the four routers on (1, 1); the worker, `jobs.ts`, `demo_render.py`, `openapi/v1.json`, both SDKs and the README on 1.1 |
| `test_pf6a_usage_keys_are_a_subset_of_5_6` | pytest | `usage.json`'s keys, `by_kind` (`tiles`, `panorama`) and `classes` ⊆ the 5.6 answer after a panorama and a tiles job |
| `test_pf6a_fake_app_and_stub_solver_read_the_new_folders` | pytest | the fake reads the contract folder; the stub solver and `test_analysis.py` read `fixtures/render` |
| `test_pf6a_job_file_has_the_snapshot_seq_and_every_key_of_the_apps` | pytest | a snapshot at 2 and a job at 4: `snapshot_seq` 2, ops 3 and 4 only, every key of the app's `job-tiles.json`, no `levels` / `params`; the tiles job: `snapshot_seq` 2, `at_seq` 5, `changed`, 13 / 5 |
| `test_pf6a_job_file_without_a_snapshot_and_for_a_pack` | pytest | no snapshot → no `snapshot_seq`; the app's key order; a pack's `params` = `{items}` only |
| `test_pf6a_exit_code_without_error_json[1-7, 9]` | pytest | the 5.10 body the wrapper sends (code, `retryable`, `exit n` in the message), no `error.json`, the job queued or failed, the stored `error.json` |
| `test_pf6a_error_json_wins_and_a_timeout_is_timeout` | pytest | `error.json` `engine_error` over exit 2 (retryable); `doc_too_new` over exit 4 (failed); the fake's exit 5 for `out_of_memory`; an unknown code → the exit code's (`render_crash`); `job_timeout_s` → `timeout` |
| `test_pf6a_fake_app_answers_the_apps_job_files` | pytest | the app's two job files as they are (relative paths): `bad_input` / exit 2 without the snapshot; then the app's two manifests (all but `app_version`) and their 90 + 65 tiles byte for byte; an operation at `snapshot_seq` refused |
| PF6's, PF9's, PF10's, PF11's, PF12's, PF12a's, PF3b's, PF14e's tests | pytest | green on the app's set (`test_render.py`, `test_render_worker.py`, `test_render_shares.py`, `test_mobile.py`, `test_pf10_clients.py`, `test_analysis.py`, `test_pf12_api.py`, `test_pf12_openapi_sdks.py`, `test_pf12a_v1_panoramas.py`, `test_pf9_pf12_meet.py`, `test_orgs_usage.py`, `test_pf14e_long_poll.py`) |
| `node out/viewer/selftest.mjs` (`test_site_pf9_js_selftests`) | build check | the tile diff per view of the app's set: the changed faces are the manifest's `rendered` ones (13 in all), levels 256 and 512 |
| `flutter test` (`sync_engine_test.dart`, `viewer_offline_test.dart`) | Dart | the bedroom / entry / living titles; 3 views × 6 faces × 4 tiles kept offline; the shown view's 24 tiles from the cache |
| `npm run lint`, `npm run build` | build check | green |

## Human test

About 15 minutes, on this PC, against a local API with the fake app (PF6's live run on the app's set). Four PowerShell windows; `<WT>` = `X:\Truebex-autopilot\t84-pf6a-cloud-render-orchestration`.

1. **API (window A).** `cd <WT>\server`, then `.venv\Scripts\python.exe scripts\make_signing_key.py --kind lic` and copy its `LICENCE_SIGNING_KEY=` and `LICENCE_KEY_ID=` values into:
   `Set-Content .env -Encoding ascii -Value 'DATABASE_URL=sqlite:///./pf6a-human.db','SECRET_KEY=pf6a-human-test-0123456789abcdef0123456789abcdef','API_URL=http://127.0.0.1:8000','CORS_ORIGINS=http://127.0.0.1:3184','LICENCE_SIGNING_KEY=<paste>','LICENCE_KEY_ID=<paste>'`
   then `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` → "Uvicorn running on http://127.0.0.1:8000". (Delete `server\.env` and `pf6a-human.db` afterwards.)
2. **Site (window B, `<WT>`).** `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build` (about 4 min), then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → "serving … on http://127.0.0.1:3184/" (if it prints another port, use that one here and in `CORS_ORIGINS`). Open `http://127.0.0.1:3184/signup/` and sign up (any address, a password of 8+ characters).
3. **Accounts (window C, `<WT>\server`).** `.venv\Scripts\python.exe -m app.admin_cli <you>` → "<you>: admin on". `.venv\Scripts\python.exe scripts\demo_replica.py login --email <you> --password <pw> --trial` → a `tbx_dev_…` device token. `.venv\Scripts\python.exe scripts\demo_replica.py --token <tbx_dev_…> push` → "head 12", "project id: <project>". In the browser reload the dashboard, then Admin → Render → "Issue a worker token": name `pc-rtx`, kinds `panorama` and `tiles`, Issue token → "Token for pc-rtx. It is shown once …" with the `tbx_wrk_…` token.
4. **Worker (window D, `<WT>`).** `Set-Content worker\worker.toml -Encoding ascii -Value 'api = "http://127.0.0.1:8000"','token = "<tbx_wrk_…>"','worker_id = "pc-rtx"','kinds = ["panorama", "tiles"]','app = "worker/tests/fake_truebex.py"','work_dir = "worker/jobs"','keep_work = true','heartbeat_s = 5','wait_s = 5','doc_version_max = 55'`, then `py -3.12 worker\truebex_worker.py --config worker\worker.toml` → "pc-rtx: waiting for app jobs (panorama, tiles) from http://127.0.0.1:8000".
5. **A followed panorama of the app's three views (window C).** `.venv\Scripts\python.exe scripts\demo_render.py --token <tbx_dev_…> submit --project <project> --follow` → "panorama job queued at operation 12: estimate 4.5 cu" and its job id. Window D: "claimed <job> (panorama, 3 views, at 12)", then "complete <job>: 18 faces rendered, 90 files sent, …". `Get-Content worker\jobs\<job>\job.json` (window D) shows `"snapshot_seq": 0` (PF4a's `push` registers the fixture snapshot at 0 only, so the job's `ops.json` holds operations 1-12, `o5/55`), `"at_seq": 12`, three view ids, no `levels`, no `params`.
6. **The Cloud preview.** Dashboard → Cloud: a "Panorama set" row, "follows edits", succeeded with its cost units. Press Preview → "Live panorama" with a View list bedroom / entry / living and "Showing operation 12."; the picture is a lit room (path-traced, grainy) with the sky through the window; drag to look round. Pick **living**.
7. **An edit (window C).** `.venv\Scripts\python.exe scripts\demo_replica.py --token <tbx_dev_…> move --project <project>` → "accepted as 13". Window D: "claimed … (tiles, 3 views, at 13)", "complete …: 13 faces rendered, 65 files sent". Within about 10 s the preview reads "Showing operation 13." and all six faces of the living room change (the fake app swaps in CL3's "wall moved" renders); pick **bedroom**: only its west face differs from before. (Each further `move` flips the faces back and forth.)
8. **Exit codes.** Stop the worker in window D (Ctrl+C) and wait 10 s. Window C: `.venv\Scripts\python.exe scripts\demo_render.py --token <tbx_dev_…> submit --project <project>`. Window D: `$env:FAKE_TRUEBEX_EXIT='3'; py -3.12 worker\truebex_worker.py --config worker\worker.toml --once; Remove-Item Env:FAKE_TRUEBEX_EXIT` → "failed <job>: doc_too_new: exit 3 without out_dir/error.json (doc_too_new)"; Dashboard → Cloud shows that job failed (not retried). Repeat with `'5'` on a new job → "out_of_memory …" and the job back in the queue ("Trying again"); press Cancel on it.
9. **Optional, with the real app (the owner's RTX PC).** In `T:\unreal5_7_4_projects\truebex_compact` (app `main` at `ad3aa5c45` or later) run `buildrelease.bat` → `T:\unreal5_7_4_projects\Truebex_Release\Windows\Truebex.exe` (the release on this PC predates CL3). CL3's own check first (a `cmd` window there): `runrelease.bat -mwrender=Docs\roadmap\fixtures\contracts\render-jobs\job-panorama.json`, `echo %errorlevel%` → 0, no window, `…\render-jobs\out\manifest.json` with 3 views × 6 faces. Then PR3's rooms into the local API (window C): `New-Item -ItemType Directory C:\pf6a-pr3 | Out-Null; Copy-Item T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\fixtures\PR3-pano-rooms.tbxp C:\pf6a-pr3\snapshot-0000.tbxp; Set-Content C:\pf6a-pr3\ops-remote.json '{"ops": []}'; Set-Content C:\pf6a-pr3\project.json '{"name": "PR3 rooms", "doc_version": 55}'` (no operations: CL1's are edits of its own fixture; PF4a's `push` reads both files) and `.venv\Scripts\python.exe scripts\demo_replica.py --token <tbx_dev_…> push --fixture C:\pf6a-pr3 --name "PR3 rooms"` → "head 0" and its project id (the snapshot at 0 and no operation, so the job applies none). In `worker\worker.toml` set `app = 'T:\unreal5_7_4_projects\Truebex_Release\Windows\Truebex.exe'` and add `face_px = 512`, `tile_px = 256`, `job_timeout_s = 1800`; start the worker as in step 4 and submit a panorama of that project (step 5 without `--follow`). Expect: exit 0, "complete …: 18 faces rendered, 90 files sent" after about a minute, and in Dashboard → Cloud → Preview the three rooms as CL3 renders them. (Do not `move` this project: the fixture's operations are not real edits, so CL3 would refuse a tiles job with `bad_input`.)

## Risks / traps

* **Two fixture folders.** `tests/contracts/render-jobs/` is the app's (never edited; re-copy with `scripts\sync-contract-fixtures.ps1 -Contract render-jobs`, then update `APP_BLOBS`, `APP_TILES_TREE` and the commits in `test_pf6a_render_jobs_1_1.py` and the README); `tests/fixtures/render/` is the platform's (`make_render_job_fixtures.py [--check]`).
* **The app checkout is CRLF** (`core.autocrlf=true`): copy blobs (the script does), never the working files.
* **A stopped worker's claim can still take a job.** A claim long-poll (≤ `wait_s`, 20 s at most) keeps waiting on the server after its worker is gone and can take the next job; the job comes back at that worker's next claim (`release_held`) or after the 120 s lease, one attempt spent. Seen in the live run: a job submitted within a just-stopped worker's last long-poll ended with 2 attempts after one failure. PF6's behaviour, not changed here (a claim could check `request.is_disconnected()` first: proposed to PF6's owner). Wait out `wait_s` after stopping a worker before testing exit codes.
* **Beside PF4a (project-log 1.1.0).** PF4a re-copies CL1's project-log fixtures (real `o5/55` deltas) and changes how `demo_replica.py push` registers snapshots. After both merge, a worker needs `doc_version_max` 55 to be handed the pushed project's jobs (the human test's `worker.toml` says so already), and human test step 9 must push PR3's file without CL1's operations (they are edits of CL1's own fixture). `render_helpers.py`, `test_render.py`, `test_mobile.py`, `test_pf9_pf12_meet.py`, `test_pf10_clients.py`, `src/viewer/selftest.ts`, `mobile/android/test/helpers.dart`, `openapi/` and `sdks/` are touched by both: keep both sides. **Merged (T88, 2026-10-15):** `claim.json` regenerated for PF4a's `snapshot-0000.tbxp` (74,505 bytes; `make_render_job_fixtures.py --check` caught it), human test steps 5 and 9 above follow PF4a's `push`; the live run on the merge is green.
* **The fake keeps the fixture's sizes** (512 px faces, 256 px tiles) whatever the job file asks; the real app renders the job's `face_px` (2048 by default: about four times CL3's measured 1024 px time).

## As-built

* **Date, branch, commits:** 2026-10-15, `ap/t84-pf6a-cloud-render-orchestration` (base `master` cc905d3): `1deb080` (fixtures moved and re-copied), `d7e346a` (tests and readers), `bc4a008` (the wrapper and the fake), `2dbd817` (the 1.1 echo, OpenAPI, SDKs, site client, README lines), and the docs commit ticking this row.
* **The copy:** `sync-contract-fixtures.ps1 -Contract render-jobs` from app `main` `ad3aa5c45` (the folder as `4ed19a00d` left it): 162 files, all updated (none equal to PF6's), 40 old tiles removed, every blob id equal; the committed `tiles/` tree is the app's (`3d5a9f35`). The stand-ins moved with `git mv` and `make_render_job_fixtures.py --check` reproduces them byte for byte (the script was cut to them: no Pillow needed).
* **Counts:** pytest 824 → 845 collected (21 new: 9 + 12 with the parametrized exit codes; 20 of 21 failed on cc905d3 — the 21st only cross-checks the recorded ids against the app repo). Web self-test: 94 checks (the new tile diff checks each of the app's three views; on the old fixtures 3 of its 88 failed). Flutter 43 tests (2 failed on the old fixtures). The verify gate: see the last bullet.
* **Readers changed:** `server/tests/render_helpers.py` (`APP_PROJECT`, `VIEW_BEDROOM`/`ENTRY`/`LIVING`, `VIEWS`, `MOVED`, `RENDER_FIXTURES`, `RJ` 1.1, `project(project_id=)`; `VIEW` and `WALL` gone), `test_render.py` (the app's project in `setup`; estimate 1.5 → 4.5 for three views; 2 → 13 faces; 30 → 90 tiles; `claim.json` from `fixtures/render`; the 1.1 echo), `test_render_worker.py` (18 and 13 faces), `test_render_shares.py`, `test_pf12a_v1_panoramas.py`, `test_pf9_pf12_meet.py` (6 → 18, 2 → 13, `MOVED`), `test_analysis.py` and `tests/fakes/stub_solver/run.py` (`fixtures/render`), `pf12_helpers.py`, `test_pf12_api.py`, `test_orgs_usage.py` (1.1); `src/viewer/selftest.ts`; `mobile/android/test/helpers.dart` (comment), `sync_engine_test.dart`, `viewer_offline_test.dart` (24 → 72 offline, titles); `worker/tests/fake_truebex.py`; `server/scripts/demo_render.py`, `seed_member_usage.py`. `test_mobile.py` and `test_pf10_clients.py` read the manifest's own views and needed no change.
* **Self-tests:** the touched suites on SQLite (16 files: 132 passed, 8 skipped for `out/`); on a throwaway PostgreSQL 17 cluster in Asia/Baghdad (9 files: 89 passed, 1 skipped for `out/`; cluster removed). **Live run** (scratchpad `live_selftest.sh` + `cdp_cloud.mjs`): uvicorn on SQLite, the wrapper with `fake_truebex.py`, `demo_replica.py push` (head 12), `demo_render.py submit --follow` (three views, 4.5 cu): job file `snapshot_seq` 12, `at_seq` 12, no `levels` / `params`; "18 faces rendered, 90 files sent"; headless Edge on the served `out/` (built against that API): Dashboard → Cloud → Preview, views bedroom / entry / living, 24 of 24 tiles, "Showing operation 12."; `demo_replica.py move` → one tiles job (`snapshot_seq` 12, `at_seq` 13) "13 faces rendered, 65 files sent"; the preview swapped all six living faces and bedroom's `w` only, 7.0 s after the push, every shown tile the fixture manifest's, no browser error; 5.5 read with a 1.0 header answered `render-jobs/1.1`; a tile `public, max-age=31536000, immutable`; queue empty; `FAKE_TRUEBEX_EXIT=3` → `doc_too_new` failed (1 attempt), `=5` → `out_of_memory` requeued. `node out/viewer/selftest.mjs` 94 checks; `flutter test` 43 passed.
* **Deviations and decisions:**
  1. *The tiles are pinned by their tree id*, not 155 more `APP_BLOBS` lines: `git_tree_id(tiles/)` is built from each tile's blob id, so it equals `git rev-parse ad3aa5c45:…/tiles` exactly when every tile's name and bytes do; each tile's name is also checked against its SHA-256.
  2. *`levels` is not written* (above). *Paths stay absolute.* *No `params` for panorama and tiles jobs* (1.1.0 defines only a pack's); a pack's are `{items}` only.
  3. *Tests that need a submitted job use the app's project id* through `project(…, project_id=APP_PROJECT)` (the platform mints ids, so the helper patches `uuid7_hex` for that one create); `fixture_manifest` still maps `job_id`, `project_id` and `at_seq` for the tests that keep a minted id (`test_render_shares.py`, the PF12a / PF9 × PF12 meets).
  4. *The fake app follows the job's view ids* (the fixture view with that id, else the one at its place) so PF9's `demo_mobile.py` sets (the project-digest's three views) still render; CL3 itself refuses an unknown id with `bad_input`.
  5. *`ops-empty.json` and `ops-move-wall.json`* moved as asked though nothing reads them since PF6's job files went (the app's `ops-tiles.json` replaced them); the stand-ins' README says so.
  6. Left as found: `server/tests/contracts/project-digest/` and `make_digest_fixture.py` still call their first saved view "the render-jobs fixtures' Living room" (the digest is PF9's; its ids are unchanged); `demo_mobile.py` and `demo_analysis.py` still send `render-jobs/1.0` (served, MINOR); README's PF11 section names `render-jobs` v1.0.0 (an existing section, not rewritten).
* **CL3's measured times (record only; `render/estimates.json` unchanged until 50 real jobs of a kind):** a full one-view `standard` job at 1024 px about 21 s (20.95 s, `perf-render3d-l`), a one-face partial 3.80 s, the pick over 10 000 boxes × 6 faces 0.088 ms; the fixture panorama job (3 views, 512 px) 44 s per process in the editor binary (render 14.2 s); Offscreen headless 30.1 s for a child. The seeds (panorama 90 s a view at `standard`, tiles 20 s a view) stay above these.
* **Contract §11 (for the app half to set in `contracts/render-jobs.md`):** every 5.1–5.10 row "PF6: done (2026-10-10, `ap/t11-pf6-cloud-render-orchestration`; render-jobs 1.1 since PF6a, 2026-10-15, `ap/t84-pf6a-cloud-render-orchestration`)"; the job-file row "PF6 (worker image): done — the wrapper writes 1.1.0's job file (`snapshot_seq`, `project_id`, `params.items`) and maps `-mwrender`'s exit codes 2–7 (PF6a); the first run of CL3's build on a worker is the owner's (PF6a human test step 9)". Proposals: the contract's §9 table still describes PF6's stand-in set (one view, 4 carried faces, `wind-result.json`, `claim.json`) beside the 1.1.0 *Changes* line — a PATCH to list the app's 7 files and that `claim.json` and the wind set are the platform's until AN3.
* **PF6's carry-over "CL3: the real `-mwrender`, the fixtures into the app repo, the first measured seconds per kind":** the fixtures are the app's and re-copied (done); the wrapper speaks CL3's job file and exit codes (done); the first real `-mwrender` run on a worker is the owner's (human test step 9, open); measured seconds come from CL3's suites only (recorded above), real per-kind numbers wait for workers (GD3, open).
* **Verify gate** (`scripts\autopilot-verify.ps1`, 2026-10-15): GREEN in 1,010 s: lint, build, pytest 845 collected, 828 passed + 17 skipped (the 17 Postgres-marked tests, which need TEST_DATABASE_URL) in 618 s.
