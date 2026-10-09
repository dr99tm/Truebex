# PF6 — Cloud render orchestration (launch priority 2)

**Needs merged:** PF4. **Unblocks:** PF9, PF11 (their Needs); the real endpoints behind the app's CL3, CL4 and AN3's job submission. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\render-jobs.md` (v1.0.0, 2026-10-09; the app side is authoritative).

## Status

No jobs, workers, tiles or cloud metering exist (`00-contract.md` P.1; the contract's §11 lists every endpoint as "PF6: not yet"). What this builds on, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Metering pattern | `server/app/usage.py:26` (`used_this_month`), `:38-51` (per-day upsert) | API requests only |
| Limit answers | `server/app/deps.py:88-91` (429 over quota), `server/app/routers/keys.py:45-47` (403 over a plan limit) | the contract answers 403 like the latter |
| Usage UI | `src/components/dashboard/UsageMeter.tsx:4`, `src/components/dashboard/UsageChart.tsx:37`, `src/app/dashboard/usage/page.tsx` | reused for cost units |
| From PF4 (Needs) | projects, snapshots, the operation log, `on_ops_accepted` push hook | the job inputs and the follow trigger |
| From PF5 (when merged) | `server/app/uploads/` (`job-input`, `job-output`) | worker outputs upload through it |
| From PF1 / PF14 Plumbing | device tokens, entitlement `cloud.panoramas`, `limits.cloud_cu_month`, `contract_http`, `idempotency`, `storage`, `tasks`; `metering.py` is created here | |

What the owner meant: app-side `00-understanding.md` §8 ("a job queue with GPU workers, tile storage and a CDN").

## Goal

"On the phone, swap the floor finish; the operation reaches the cloud, the worker re-renders two cube faces, the panorama on the phone and the desktop app both update within seconds" (`00-understanding.md` §8). This feature runs the queue between the edit and the picture: jobs submitted by the app or triggered by the log, GPU workers that run the app headless and render only the faces a change touches, content-addressed tiles behind a CDN, a status the clients long-poll, and every job metered in cost units against the tier's allowance.

## Read first

* **`contracts/render-jobs.md` v1.0.0** — the law: §4 credentials (worker tokens `tbx_wrk_…`), §5 the ten endpoints, §6.1 the job file, §6.2 the tile manifest (faces `n e s w u d`, levels, content-addressed tiles, partial re-render), §6.4 states, leases and cost units, §7 errors, §8 retry, §9 fixtures (copied into `server/tests/contracts/render-jobs/`), §10 platform tests, §11 *implemented by*.
* `contracts/project-log.md` §6.4 (the snapshot reference `project_id` + `at_seq`) and 5.7 (the `ops_url` body); `contracts/share-bundle.md` §5 (job inputs and outputs); `contracts/licence-api.md` §6.3 (`cloud_cu_month`).
* `guides/GD3-*.md` (hardware, prices, scaling numbers) and `guides/GD7-*.md` (allowances, overage price) are not written yet: every number below is a placeholder `from GD3` or `from GD7`.
* App-side CL3 (the `-mwrender=<job.json>` mode the worker runs) and CL4 (the loop it measures).

## Scope

**In:**
1. The job queue of contract §5.1–5.6: submit with an estimate and `Idempotency-Key`, status with a long-poll on `rev`, list, cancel, output with file URLs, usage this month; kinds `panorama`, `tiles`, `pack` here (`wind`, `energy` are PF11's on the same queue).
2. The worker claim protocol of §5.7–5.10: worker tokens issued and revoked by an admin and scoped to kinds, a long-poll claim (`wait_s` ≤ 20) that hands a job only to a worker whose `doc_version_max` reads its log, 120 s leases renewed by 30 s heartbeats, cancel through the heartbeat, complete and fail, three attempts, `queued` jobs expiring after 24 h.
3. GPU workers running the app's headless render mode (CL3): the worker wrapper `worker/` (claim, download inputs, write the §6.1 job file, run `Truebex.exe -mwrender=<job.json>`, upload outputs, complete), the Windows GPU worker image and its bootstrap.
4. Tile storage and CDN: tiles content-addressed at `tiles/<sha256>.jpg`, immutable and cacheable forever, served from `TILES_BASE_URL`; manifests per job; unreferenced tiles collected.
5. Partial re-render on log changes: `follow: true` panorama sets subscribe to PF4's push hook; each accepted push enqueues one `tiles` job with the pushed `touched` ids; queued `tiles` jobs of a set coalesce (`changed` united, `at_seq` the highest); each finished one bumps the follow job's `rev`.
6. Quotas and overage metering per tier: cost units (1 cu = 1 min on `gpu-std`, class weights) charged on success only, `limits.cloud_cu_month` as the allowance, 403 `quota_exceeded` when an estimate exceeds what is left, and for tiers with overage (`from GD7`) a monthly charge through PF2's `charge_usage`.
7. Worker images and a scaling policy from GD3: a `WorkerPool` interface with a `static` pool (machines registered by hand, the owner's RTX PC included) and one cloud adapter once GD3 names the provider; scale on queue depth and oldest wait, stop after idle.
8. The status the clients poll (5.2, 5.3) and an admin view of queue, workers and cost.
9. The live share page: a share manifest panorama may reference a follow set (`live_job_id`), and the share viewer then shows its tiles and refreshes them through `GET /s/{slug}/live` (both a MINOR addition to `share-bundle.md` §5 and §6.1, written there first by the owner, C.9), so the human test's "tiles refresh on the share page" holds.
10. The dashboard's Cloud usage page: cost units used against the allowance, by kind, recent jobs with their cost.
11. Tests: the contract's §10 platform tests with its fixtures, a pytest per endpoint (happy path, auth failure, validation failure), the worker wrapper against a fake app.

**Out (and where it goes):**
* What the app renders, which faces a change touches, the job file reader → CL3 (app); the end-to-end latency measurement → CL4.
* Analysis kinds, CPU solver images and AI models on GPUs → PF11.
* The phone and headset viewers of followed sets → PF9, PF10, PR5; full pixel streaming for Studio and Enterprise → not in roadmap 40 (`00-understanding.md` §8 reserves it).
* Provider choice, instance types, prices and the measured numbers → GD3; allowances and the overage price → GD7.
* A Linux worker image → carry-over to CL3 / GD3 (the app has no Linux target today).

## Design

### API

Shapes are the contract's; routers `server/app/routers/jobs.py` (`/jobs`), `server/app/routers/workers.py` (`/workers`), admin routes in `server/app/routers/admin.py`; service `server/app/render/`.

| # | Endpoint | Platform behaviour |
|---|---|---|
| 5.1 | `POST /jobs` | device, session or API key; feature check (`cloud.panoramas` for render kinds → 403 `plan_required`); `at_seq ≤ head` (409 `seq_ahead`); estimate from the rolling median `wall_s` of the last 50 jobs of the same kind, quality and face count (seeded `from GD3`); 403 `quota_exceeded` when the estimate exceeds the remaining allowance plus the account's overage cap; a `tiles` job joins a queued one of the same set (coalescing) |
| 5.2 | `GET /jobs/{id}` | `async` long-poll: returns when `rev` passes the asked one or after `wait_s` |
| 5.3–5.6 | list, cancel, output, usage | cancel of a running job sets a flag the next heartbeat returns; 409 `job_finished`, 409 `not_ready`; usage from `meter_daily` (metric `cu`) with `classes` weights and `by_kind` |
| 5.7 | `POST /workers/claim` | worker token; one transaction picks the oldest highest-priority queued job of the token's kinds whose log fits `doc_version_max` (`… FOR UPDATE SKIP LOCKED` on Postgres; `BEGIN IMMEDIATE` and `UPDATE … RETURNING` on SQLite); signs the snapshot, `ops_url` and `base_manifest_url` for the lease plus 10 min; opens the `job-output` upload; 204 after `wait_s` with nothing queued |
| 5.8–5.10 | heartbeat, complete, fail | `lease_id` must match (else 409 `lease_lost`); complete checks every file the output names is complete in the upload (422 `output_invalid`), writes the manifest, charges `ceil(wall_s / 60 × weight, 0.1)` cu, bumps the follow set's `rev`; fail requeues while `attempts` < 3 and `retryable` |
| — | `POST /admin/workers`, `DELETE /admin/workers/{id}` | admin: issue a `tbx_wrk_…` token for a name and a set of kinds (shown once, stored as SHA-256); revoke → the next claim gets 401 `worker_revoked` |
| — | `GET /admin/render` | queue depth by kind, oldest wait, workers (version, kinds, last heartbeat), cost by kind this month |

### Queue and claim protocol

| State | Entered by | Left by |
|---|---|---|
| `queued` | 5.1, a requeue, the follow trigger | a claim; 24 h → `expired`; cancel → `cancelled` |
| `claimed` | 5.7 (`lease_expires_at` = now + 120 s) | the first heartbeat → `running`; lapse → requeue |
| `running` | heartbeat | complete → `succeeded`; fail → requeue or `failed`; lapse → requeue (attempts + 1; the fourth lapse → `failed`); cancel flag → the worker stops → `cancelled` |

Priority is the tier's rank (Enterprise first), then age. **Decision:** the jobs table is the queue (`SKIP LOCKED` on Postgres). Rejected: a separate broker such as Redis with a task library (one more service for a few thousand jobs a day; the contract's leases already give at-least-once delivery) and a cloud provider's queue service (ties the platform to a provider GD3 has not picked, and still needs this table for status).

### Tile storage layout

| Key | Holds | Cache |
|---|---|---|
| `tiles/<sha256>.jpg` | one JPEG tile (`tile_px` 512, quality 85) shared by every job and project that produced the same bytes | `public, max-age=31536000, immutable` and `Access-Control-Allow-Origin: *` (WebGL refuses cross-origin textures without CORS) at `TILES_BASE_URL` |
| `jobs/{job_id}/manifest.json` | the §6.2 manifest | private; served by 5.5 |
| `jobs/{job_id}/render-log.json` | per-step and per-face milliseconds (CL3) | private |
| `jobs/{job_id}/error.json`, `log-tail.txt` | a failure's code and the last 64 KiB | private |
| `sets/{follow_job_id}/latest.json` | `{rev, job_id, at_seq}` of the newest finished manifest | `no-cache` |

Per view: levels 512, 1024, 2048 with 512-pixel tiles give 1 + 4 + 16 = 21 tiles a face and 126 a full view. A partial job uploads only the faces it rendered; carried faces keep their hashes. `render.tiles.gc` weekly deletes tiles no manifest of the last 90 days names.

### GPU cost assumptions (placeholders GD3 measures)

| Item | Placeholder | GD3 measures |
|---|---|---|
| `gpu-std` hardware | one data-centre GPU with ray-tracing cores and ≥ 16 GB VRAM, Windows | the instance type in the chosen region |
| on-demand price | £P per hour | the provider's price list on the measurement date |
| boot to first claim | T_boot s | cold starts over 20 boots |
| full `panorama` (6 faces × 2048 px, `standard`) | W_full s | median over 20 projects |
| `tiles` after a one-wall edit | W_partial s | median faces rendered and seconds |
| `pack` | W_pack s | per item |
| tile size | B_tile KB | median of the tile store |
| CDN egress per viewer session | E_view MB | from the CDN's logs |

Cost per job = `wall_s / 3600 × P` (+ boot time amortised over the jobs a machine serves); one cu costs `P / 60`; the overage price per cu and the allowances follow from GD7's margin. The estimate seeds (W_full, W_partial, W_pack) stay in `server/app/render/estimates.json` until 50 real jobs of a kind replace them.

### Data

| Table | Fields | Notes |
|---|---|---|
| `render_jobs` | `job_id`, `account_kind`, `account_id`, `kind`, `class`, `state`, `rev`, `project_id`, `at_seq`, `views` JSON, `changed` (stored blob), `base_job_id`, `quality`, `follow`, `inputs` JSON, `params` JSON, `priority`, `progress`, `message`, `attempts`, `lease_id`, `lease_expires_at`, `worker_id`, `doc_version_needed`, timestamps, `cost_units_estimate`, `cost_units`, `output_key`, `error` JSON | the queue |
| `render_sets` | `follow_job_id`, `project_id`, `views` JSON, `latest_job_id`, `rev` | one per followed set |
| `workers` | `worker_id`, `name`, `token_hash`, `kinds` JSON, `class`, `app_version`, `doc_version_max`, `last_heartbeat_at`, `revoked_at` | |
| `meter_daily` | `subject_kind`, `subject_id`, `metric`, `day`, `quantity` (decimal) | `server/app/metering.py` (PF14 Plumbing), created here |
| `overage_charges` | `account`, `month`, `cu`, `amount_minor`, `currency`, `provider_ref`, `state` | one row per month with overage |

### UI

| Page / component | What it shows |
|---|---|
| `src/app/dashboard/cloud/page.tsx` (noindex) | cost units used against the allowance (`UsageMeter`), by kind, per day (`UsageChart`), recent jobs with state and cost, the overage cap setting where the tier allows overage |
| `src/app/dashboard/admin/render/page.tsx` (noindex, admin) | queue depth and oldest wait by kind, workers, cost by kind, revoke a worker, issue a token (shown once) |
| `src/viewer/` (PF5's viewer) | a cube-tile mode: for a panorama that references a follow set, it loads the set's manifest (faces `n e s w u d`, levels, tiles from `TILES_BASE_URL`), long-polls `GET /s/{slug}/live?rev=` (a share-scoped read of the set's `latest.json`, proposed with the manifest field because 5.2 is owner-only) and swaps only the tiles whose hashes changed |

### Jobs / workers

| Piece | What it does |
|---|---|
| `worker/truebex_worker.py` | the wrapper on each worker: claim → download the snapshot, `ops.json` and base manifest → write the §6.1 job file → run `Truebex.exe -mwrender=<job.json>` with no window → heartbeat every 30 s in a thread, kill the process on `cancel` → upload `out_dir/tiles/*` and the manifest through `/uploads` → complete, or fail with `error.json`'s code; config in `worker.toml` (API URL, token, kinds, class) |
| `infra/worker/` | `bootstrap.ps1` (NVIDIA driver, the Shipping build of the release from `releases/`, Python 3.12, the wrapper as a Windows service under a low-privilege account) and `build-image.ps1` (a golden image per app release on the provider GD3 picks) |
| `server/app/render/pools.py` | `WorkerPool` (`list`, `desired(n)`, `start`, `stop`); adapters `static` (registered machines) and, after GD3, one cloud provider |
| `render.autoscale` | every 30 s: desired workers per class = clamp(ceil(queued / 4) + running, min, max) and one more when the oldest wait exceeds 30 s; a machine idle 10 min is stopped; min, max and the business-hours warm pool `from GD3` |
| `render.leases.reap` | every 15 s: lapsed leases requeue or fail |
| `render.jobs.expire` | every 300 s: `queued` older than 24 h → `expired` |
| `render.tiles.gc` | weekly: tiles named by no manifest of the last 90 days |
| `render.overage.charge` | monthly on the 1st: overage cu × price → PF2's `charge_usage`; without PF2 merged, rows stay `pending` for the owner |

**Decision:** the first worker image is Windows with the same Shipping build the customers run, so CL3 needs no second target. Rejected for now: a Linux container (cheaper hours and faster boots, but the app has no Linux build; carried to CL3 / GD3).

### Security and privacy

* Worker tokens are scoped to kinds, stored hashed, revocable; a worker never holds a user credential: its inputs are URLs signed for the lease, its outputs an upload bound to the job.
* Workers run each job as a fresh process under a low-privilege account; the VM's outbound firewall allows only the API, storage and CDN hosts; machines are re-imaged weekly.
* Tiles are public by hash (the contract's decision: per-request signed tile URLs would defeat the CDN); a hash is unguessable and appears only in manifests served to the job's account or a live share.
* A live share exposes the followed views' current pictures to whoever holds the link; the designer opts in per share and revoking the share stops it.

## Deliverables

- [ ] `server/app/render/` (`service.py`, `queue.py`, `estimates.py` + `estimates.json`, `sets.py`, `pools.py`, `overage.py`), `server/app/routers/jobs.py`, `server/app/routers/workers.py`, admin routes
- [ ] `server/app/metering.py` and `meter_daily` (PF14 Plumbing row), models, settings (`TILES_BASE_URL`, `CU_CLASS_WEIGHTS`, pool limits)
- [ ] `worker/truebex_worker.py`, `worker/worker.toml.example`, `worker/tests/fake_truebex.py` (a stand-in that writes the fixture manifest and tiles)
- [ ] `infra/worker/bootstrap.ps1`, `infra/worker/build-image.ps1`
- [ ] `src/app/dashboard/cloud/`, `src/app/dashboard/admin/render/`, the viewer's cube-tile mode, `src/lib/jobs.ts`
- [ ] `server/tests/contracts/render-jobs/` copied from the app repo's fixtures (copied, never edited)
- [ ] contract §11 rows and the share-bundle MINOR proposal (`live_job_id`, `/s/{slug}/live`) recorded in As-built

## Tests

The first ten names are the contract's §10 platform tests.

| Name | Kind | Asserts |
|---|---|---|
| `test_submit_estimate_and_idempotency` | pytest | 201 with `cost_units_estimate`; the same key replays |
| `test_claim_lease_heartbeat_complete` | pytest | claim → heartbeats → complete → `succeeded` with `cost_units` |
| `test_lease_expiry_requeues_three_times` | pytest | lapsed leases requeue; the fourth lapse is `failed` |
| `test_cancel_reaches_worker` | pytest | `cancel: true` on the next heartbeat; then `cancelled` and no charge |
| `test_worker_token_scoped` | pytest | a worker cannot claim a kind outside its scope |
| `test_follow_set_enqueues_tiles_on_push` | pytest | a push touching a followed project enqueues one `tiles` job with the pushed `touched` ids |
| `test_tiles_jobs_coalesce` | pytest | two queued jobs of a set merge: `changed` united, `at_seq` the highest |
| `test_output_requires_uploaded_files` | pytest | 422 `output_invalid` when a named tile is missing from the upload |
| `test_cost_units_and_quota` | pytest | charge only on success, rounded up to 0.1 cu; 403 `quota_exceeded` past the allowance |
| `test_contract_header_and_error_envelope` | pytest | header echoed; MAJOR 2 → 400 `contract_version`; envelope with `code` and `request_id` |
| `test_jobs_submit_requires_feature_and_auth` | pytest | 403 `plan_required` on Free; 401 without credential |
| `test_jobs_submit_validation` | pytest | 422 for `tiles` without `base_job_id`, 51 views, 10 001 changed ids; 409 `seq_ahead` |
| `test_jobs_status_long_poll_rev` | pytest | a waiting 5.2 returns within 1 s of a heartbeat that bumps `rev` |
| `test_jobs_cancel_finished_and_output_not_ready` | pytest | 409 `job_finished`; 409 `not_ready` |
| `test_jobs_usage_by_kind` | pytest | 5.6 totals, `classes` weights and `by_kind` match `meter_daily` |
| `test_workers_claim_respects_doc_version` | pytest | a worker reading only `o5/38` never gets a job whose log holds `o5/54` |
| `test_workers_revoked_and_lease_lost` | pytest | 401 `worker_revoked`; a stale `lease_id` → 409 `lease_lost` |
| `test_jobs_expire_after_24h` | pytest | `queued` → `expired` |
| `test_jobs_overage_metered_when_allowed` | pytest | a tier with an overage cap is not refused within the cap; the monthly run writes one `overage_charges` row |
| `test_render_autoscale_static_pool` | pytest | queue depth and oldest wait drive `desired`; idle machines stop after 10 min |
| `test_worker_wrapper_runs_job_file` | pytest | `truebex_worker.py` with `fake_truebex.py` claims, writes a valid §6.1 file, uploads, completes |
| `test_tiles_served_immutable` | pytest | a tile URL answers with `immutable` caching and `Access-Control-Allow-Origin: *`; a manifest URL is private |
| `test_site_pf6_cloud_pages_noindex` | build check | `out/dashboard/cloud/` and `out/dashboard/admin/render/` carry `noindex` |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. Local API with PF1, PF4 and PF5 merged; the build served against it. Activate a device on a Pro trial (PF1 steps); push the fixture project (PF4's `demo_replica.py`).
2. Admin → Render → Issue worker token "pc-rtx" for `panorama`, `tiles` → the token shows once.
3. On this PC: `worker\truebex_worker.py --config worker.toml` with that token and the path of a CL3 build (`Truebex.exe`); before CL3 lands, `--app worker\tests\fake_truebex.py` → "waiting for jobs".
4. Submit a followed panorama set: the app's Cloud panorama command (CL4), or `curl -X POST http://127.0.0.1:8000/jobs -H "Authorization: Bearer tbx_dev_…" -H "Idempotency-Key: <32 hex>" -H "X-Truebex-Contract: render-jobs/1.0" -d "{\"kind\":\"panorama\",\"project_id\":\"<id>\",\"at_seq\":12,\"views\":[\"<view id>\"],\"follow\":true}"` → `queued`, an estimate; the worker console shows the claim, faces rendered, "complete".
5. Dashboard → Cloud: the job `succeeded` with its cu; the meter moves.
6. Share the house with the live view (a PR4 build, or `demo_share.py --live <follow job id>`) and open the share on the phone → the living room as tiles.
7. Change a wall from the desktop app (a CL1 build pushes the operation; or `demo_replica.py push-one --touch <wall id>`) → a `tiles` job appears, renders the two faces that see the wall, and within seconds the phone swaps those tiles.
8. Admin → Render: queue empty, the worker's last heartbeat recent, the month's cost by kind.

## Risks / traps

* A claim must be atomic: two workers taking one job would double-charge; `SKIP LOCKED` on Postgres, the single writer on SQLite (`test_claim_lease_heartbeat_complete` runs on both when PF14's Postgres job is set).
* Long-polls (claim, status) are `async`; Cloudflare's 100 s idle limit is why claims wait at most 20 s and status 25 s.
* A tile set is large (126 tiles a view): uploads go through 8 MiB parts, never one request, inside Cloudflare's 100 MB body limit.
* The home PC as a worker shares its GPU with the owner's own work; the static pool is for tests and the first beta, GD3's cloud pool for launch.
* The worker runs project content: a hostile project could try to escape the render process; isolation, the egress allowlist and re-imaging are the guard, not trust.
* The app on the worker must be the version the job's log needs: images are rebuilt per release and `doc_version_max` keeps older workers off newer logs.
* Estimates are guesses until 50 jobs of a kind ran: quotas refuse on estimates, charges use measured time.

## As-built

* Date, branch, commits:
* Counts (pytest before → after); measured seconds per kind on the first worker:
* Deviations from Design and why:
* GD3 numbers adopted (provider, class hardware, prices, pool limits):
* Contract §11 rows for the owner to set to "PF6: done" in `contracts/render-jobs.md`; the share-bundle MINOR proposal:
* Carry-over → which feature:
