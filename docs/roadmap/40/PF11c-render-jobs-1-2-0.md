# PF11c — The analysis service follows render-jobs 1.2.0 (AN3's wind and airflow kinds): the files map on 5.5, the wind job's 1.2 inputs, params and outputs, the airflow kind, the render-jobs/1.2 echo (launch priority 3)

**Needs merged:** PF11, PF6a (and everything on `master` 1a8b577); AN3 on the app side (the wind study, merged on app `main` `bcdd021f1`, 2026-10-24, T186). **Unblocks:** AN3's wind study against the live API (the app's Shipping build with a real cpu-8 worker: GD3 and the owner). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\render-jobs.md` **1.2.0** (2026-10-22; the app side is authoritative, C.9). Every render-jobs route now answers `X-Truebex-Contract: render-jobs/1.2`.

## Status

**Built 2026-10-24** on `ap/t97-pf11c-the-analysis-service-follo` (Autopilot T97); see As-built. What was behind on `master` 1a8b577, checked against app `main` `bcdd021f1` before the work:

| # | Where (master 1a8b577) | Before |
|---|---|---|
| 1 | `server/app/render/service.py` `output` → `analysis/results.py` `sign` | 5.5 answered `urls` {sha: url} and `urls_expire_at`; the app reads a top-level `files` {sha: {url, bytes}} map (`CadAnalysisJobs.cpp` `FetchOutput`), so it found no URL |
| 2 | `analysis/kinds.py`, `submit.py`, `inputs.py` | `entities` optional; the STL read for its count and bounds only (1 000 000 triangles); `surroundings` / `terrain` read but never used; 5 wind params kept, the rest dropped |
| 3 | `analysis/profiles.json` | terrain sea / open 0.01 / country 0.05 / suburban / urban (the app's `open` ran at 0.01 and `lake` got 422); Lawson 2.5 / 4 / 6 / 8 m/s; 1000 iterations, k-epsilon; grid cell and height from the profile |
| 4 | `analysis/submit.py` | quality always `standard`; a `project_id` that was not a cloud project of the caller answered 404 (the app's CL0 document id included); `doc_version_needed` asked of the project |
| 5 | `analysis/runners/wind.py` | the grids' origin was the first cell's corner (half a cell off 6.3); no `velocity` grid (and U stayed in the turned case frame); no `residual` in the summary |
| 6 | `analysis/results.py` | `on` had no `openings`, units no `m3/s` |
| 7 | everywhere | no `airflow` kind (kinds, `quotas.CONTRACT_KINDS`, estimates, `src/lib/jobs.ts`, the render admin) |
| 8 | the four routers, `export_openapi.py`, the SDKs, the demo scripts | `render-jobs/1.1` (and `demo_mobile.py` 1.0) |
| 9 | `server/tests/contracts/render-jobs/` | the app's 162 files at `ad3aa5c45`; the app's folder has 169 since AN3 (`51b5adf01`) |

## Goal

A wind study started in the app (AN3) runs on the platform exactly as the app's stub answers it: the app uploads its watertight export and the entity ids of its triangles, submits one wind job per direction (and an airflow job beside each when indoor storeys are picked), and reads every result back through 5.5's `files` map; the platform checks what 1.2.0 asks of the inputs and of every result, runs the wind case 1.2.0 describes and the orifice network for airflow, and the airflow job waits for its wind job instead of the app sequencing them.

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4; `PF11-analysis-and-ai-services.md` (As-built deviations 7 and 8, Carry-over "AN2 / AN3 / AN4"); `PF6a-render-jobs-1-1-0.md` (how this folder is re-copied and pinned).
* `render-jobs.md` 1.2.0: *Changes* 2026-10-22, 5.1's kinds table and the paragraph after it, 6.3 (the *(1.2)* paragraph), 6.5.1–6.5.4, §9's *(1.2)* stub paragraph, §10's two *(1.2)* rows, §11.
* App repo, read only: `Plugins/CADTOOL/Source/TruebexSync/Private/CadAnalysisJobs.cpp` (`Submit`, `FetchOutput`, `WindProjectRef`), `AnalysisJobsStub.cpp` (`SynthesizeWind`, `SynthesizeAirflow`), `RenderJobsClient.cpp` (`ToJson`, the 1.2 header), `CadCore/Private/CadWindIo.cpp` (`RoomsJson`, `ParseResult`), `CadWindEstimate.cpp` (`BuildNetwork`, `SolveNetwork`), `CadWind.cpp` (tunables), `Cad3DTool/Private/Cad3DWind*.cpp` (the closed wrap).

## Scope

**In** (nothing was cut):

1. **The re-copy.** `scripts\sync-contract-fixtures.ps1 -Contract render-jobs` (169 files, the seven wind files new, every blob id equal; the tiles tree unchanged); the folder README rewritten for 1.2.0; `test_pf6a_render_jobs_1_1.py`'s `APP_COMMIT` / `APP_FOLDER_COMMIT` / `APP_BLOBS` moved. No stand-in was left in the contract folder (PF6a moved them); PF11's octahedron result stays in `tests/fixtures/render/`, in 1.2.0's shape.
2. **5.5's `files` map** for every analysis result, `urls` / `urls_expire_at` kept beside it; a worker's own `files` key is dropped at completion.
3. **Wind inputs:** `entities` required (16 bytes a triangle); `geometry` closed, at most 200 000 triangles (422 on `inputs.files.geometry` with `open_edges` / `over_shared_edges`); no winding check; `surroundings` and `terrain` optional STLs, not checked for closure.
4. **Wind params:** `pedestrian_height_m` (0.5–10, 1.5), `grid_cell_mm` (100–10 000, 1000), `turbulence_model` (`realizable_ke` | `komega_sst`) validated, stored, echoed; terrain the contract's five with their z0; Lawson 1.2.0's five classes.
5. **Quality** kept on every analysis job (draft, standard, high; else 422 on `quality`); the claim's profile carries 6, 10 or 20 cells per building side; the wind estimate follows.
6. **The wind runner** (`runners/wind.py`, checked by unit tests only): realizableKE or kOmegaSST (with `0/omega`), 2000 iterations to 1e-4, the Richards and Hoxey inlet by terrain, rough-wall ground, `surroundings` as obstacles, `terrain` as a second ground surface with the pedestrian points lifted above it, the grids centred on cell (0, 0) at the pedestrian height with cells of `grid_cell_mm`, `speed_ratio` / `velocity` / `comfort_lawson`, the summary's `residual`.
7. **The airflow kind** (cpu-8, `analysis.reports`): params, the rooms file, `geometry` refused, the wait for (and end with) its wind job, the claim's wind geometry and Cp, `runners/airflow.py`, its own image, a small fixed estimate.
8. **The reference (6.5.1):** `project_id` / `at_seq` recorded as given; 409 `seq_ahead` only for a cloud project the caller can view; no snapshot; `doc_version_needed` 0.
9. **render-jobs/1.2** on `/jobs`, `/workers`, `/analysis`, `/v1/jobs`, `export_openapi.py`, `openapi/v1.json` (document 1.2.0, `airflow` in `JobRequest.kind`), the SDKs (1.2.0), the worker wrapper; 1.0 and 1.1 served; 2.0 → 400.
10. **The web:** `JobKind` gains `airflow`; the Cloud page and the render admin label it "Airflow study" (`CLOUD_AIRFLOW`, the end of `constants.ts`); the admin's token form offers the kind.
11. **Fold-ins:** `demo_mobile.py`, `demo_render.py`, `demo_analysis.py` send `render-jobs/1.2`; `demo_analysis.py` sends `entities` (its test shape's, or `--entities`), `--quality`, `--project-id`, and gains `airflow --wind-job <id>` and `output --json`. `make_digest_fixture.py` untouched (the re-copy moved nothing it names).

**Out (and where it goes):**

* Building and publishing the wind and airflow images, the first real OpenFOAM run, measured seconds per kind: **GD3 and the owner**.
* Validation against the COST 732 and AIJ cases, the turbulence-model pick, any public accuracy claim: **GD2**.
* airflow's interior CFD run (`inputs.files.geometry`): **GD2** (refused with 422 until then).
* The annual comfort over every direction: **the app's** (6.5.2).
* PR5's id and depth tiles, CL4's render rows of render-jobs: not in 1.2.0.
* The contract's §11 cells and the PATCH lines below: **the app half** (proposed in As-built).

## Design

### API

| Endpoint | PF11c |
|---|---|
| 5.1 `POST /jobs` (and `/v1/jobs`), kind `wind` | params `speed_ms` (0.5–60, 5), `direction_deg` [0, 360), `reference_height_m` (1–300, 10), `terrain` ∈ sea / lake / open / suburban / urban, `comfort` lawson, `pedestrian_height_m` (0.5–10, 1.5), `grid_cell_mm` (100–10 000, 1000), `turbulence_model` realizable_ke / komega_sst — stored with their defaults; `inputs.files.geometry` + `entities` required, `surroundings` / `terrain` optional; `quality` draft / standard / high |
| 5.1, kind `airflow` | params `wind_job_id` (32 hex), the same four site params as its wind job, `velocity_height_m` (0.3–3, 1.1); `inputs.files.rooms` required; `geometry` → 422 "the interior CFD run is not available yet"; the record's `base_job_id` is the wind job, its `message` "Waits for its wind job to finish." until that job succeeds |
| 5.1, any analysis kind | `project_id` (32 lowercase hex, optional) and `at_seq` (≥ 0) recorded; 409 `seq_ahead` only when `project_id` is a live cloud project the caller is an active member of and `at_seq` is past its head; a kind, quality or enumerated param in another case ("Wind", "Standard") read lower-case |
| 5.5 `GET /jobs/{id}/output` (and `/v1`) | an analysis result gains `files` {sha256: {url, bytes}} for every file it names (the signed URL; `bytes` from the declaration, else the stored blob), beside `urls` {sha256: url} and `urls_expire_at` |
| 5.7 claim | an analysis job: `inputs.snapshot` and `ops_url` null; `job.profile` by kind and quality (wind: `quality`, `cells_per_side`, `cells_per_h`); an airflow job's `inputs.files` gains `wind_geometry` (the wind job's uploaded STL) and `wind_pressure_coefficient` (its published Cp array), signed like the others |
| 5.9 complete | 422 `output_invalid` adds 1.2.0's rules (below) |
| `GET /analysis/catalogue` | `airflow` listed; `required_files` lists all (wind: geometry, entities); terrain the five |

**422 `validation_failed` on `inputs.files.rooms`** (`truebex-airflow-rooms/1`, 6.5.3), the first broken rule with its path in `detail` and `data.path`: a JSON object with the schema; 1 to 300 rooms with unique 32-hex ids, `volume_m3` above 0 (≤ 10⁶), `floor_z_m` a number when given; up to 5000 openings with 32-hex ids, `from` and `to` each a room id or `outside` (never both outside, never the same room), `area_m2` above 0 (≤ 1000), `cd` in (0, 1], `centre_m` and `normal` 3 numbers (|x| ≤ 10⁵ m, the normal not zero), `z_m` a number when given, `cp` (|cp| ≤ 10) only where one side is outside; `rho_kg_m3` 0.5–2 (default 1.2).

**422 on `params.wind_job_id`:** an unknown id, another account's job or a job of another kind all read "a wind job of this account …" with the same `data`; an own wind job whose `speed_ms`, `direction_deg`, `reference_height_m` or `terrain` differs names them in `data.differs`; one that failed, was cancelled or expired gives `data.state`.

**5.9's 1.2.0 rules** (`results.check`): a wind result's `summary` has numeric `max_speed_ms`, `max_speed_ratio`, `iterations`, `residual`; a field `pressure_coefficient` on faces, unit `1`, one value per uploaded triangle; grids `speed_ratio` (`1`, float32), `velocity` (`m/s`, float32, `components` 3), `comfort_lawson` (`class`, uint8), each with `origin_mm`'s z the job's `pedestrian_height_m` and `cell_mm` at least its `grid_cell_mm`. An airflow result has `air_changes` (`1/h`, spaces, one per room), `opening_flow` (`m3/s`, openings, one per opening) with entities, and a `velocity` grid (3 components) when the file has openings. `on` gains `openings`, units `m3/s`.

### Data

No table, column or migration. An airflow job keeps its wind job in `render_jobs.base_job_id` and its room / opening counts in `inputs` (`rooms`, `openings`); a wind job keeps `geometry_triangles` and `geometry_over_shared_edges` there.

### Jobs / workers

* `analysis/dependents.py` (new): `ready(j)` is a clause of the claim's candidate query (an airflow job is a candidate only when its wind job has `succeeded`); `on_ended` (called by `render/sets.on_ended`, which every fail, cancel and expiry runs) ends each waiting airflow job `failed` / `bad_input` with no charge; `on_succeeded` (from `queue.complete`) clears their message and moves their `rev`; both wake those jobs' long polls after the commit. 5.7's own notify wakes the workers.
* `runners/wind.py`: the case as Scope 6; `Frame` keeps the datum (z = 0) and turns velocities back (`vector_to_model`); `SolverLog` follows simpleFoam's initial residuals; `TerrainIndex` gives the terrain's height under a point.
* `runners/airflow.py` (new, standard library): the outside Cp (its `cp`, else the wind job's at the triangle whose centroid is nearest among those facing the opening, any when none faces it), the outdoor pressure Cp × ½ ρ U², Newton on each connected room's mass balance (Q = Cd A sqrt(2 |Δp| / ρ) signed from → to, linear below 1e-4 Pa, a halving line search, ≤ 60 steps to 1e-9 m³/s), `air_changes` = inflow × 3600 / volume, `opening_flow`, and the velocity grid as the app's stub draws it (Q / A along each opening's plan normal in the cell nearest it, 0.5 m cells over the openings plus 2 m, z = `velocity_height_m`, NaN elsewhere). Image `truebex-analysis-airflow:1` (`infra/worker/analysis/airflow/`), engine `truebex-airflow`.
* `server/scripts/local_analysis_docker.py` (new): a `docker` stand-in for a PC without Docker; with `TRUEBEX_WIND_STAND_IN` it answers a wind job on the app's export with the app's arrays.

### UI

`src/lib/jobs.ts` (`JobKind` + `airflow`, the 1.2 header); `src/lib/ai.ts` `kindLabel` reads `CLOUD_AIRFLOW.kinds` after `CLOUD.kinds` and `CLOUD_AI.kinds`; `src/app/dashboard/admin/render/page.tsx` `KINDS` + `airflow`. Account pages only (noindex); public copy unchanged (wind and airflow reports stay "On the roadmap").

### Security and privacy

An airflow job reads only its own account's wind job (another account's id reads as unknown, never revealed); its claim signs that job's geometry and Cp for the lease, as every input. A recorded `project_id` that is not the caller's project gives no hint whether it exists, and no analysis job opens a project or snapshot. `local_analysis_docker.py` has no container isolation and is for a PC without Docker only.

## Deliverables

- [x] `server/tests/contracts/render-jobs/` = the app's 169 files (app `main` `bcdd021f1`, folder last changed in `51b5adf01`) + the platform's README
- [x] `server/app/analysis/{kinds,inputs,submit,results,estimates}.py`, `estimates.json`, `profiles.json`, new `dependents.py`
- [x] `server/app/analysis/runners/{wind,common,__init__}.py`, new `runners/airflow.py`
- [x] `server/app/render/{queue,sets,quotas}.py` (one clause or call each)
- [x] `server/app/routers/{jobs,workers,analysis}.py`, `routers/v1/{jobs,models}.py`; `server/scripts/export_openapi.py`, `openapi/v1.json`, `sdks/` (operations, `JobRequest.kind`, versions 1.2.0)
- [x] `worker/truebex_worker.py` (`CONTRACT`), `worker/worker.analysis.toml.example`; `infra/worker/analysis/airflow/` and the shared build scripts
- [x] `server/scripts/{demo_analysis,demo_render,demo_mobile,make_render_job_fixtures}.py`, new `local_analysis_docker.py`
- [x] `src/lib/{jobs,ai,constants}.ts`, `src/app/dashboard/admin/render/page.tsx`
- [x] tests: `server/tests/test_pf11c_render_jobs_1_2.py` (18); the assertions 1.2 moves (As-built)
- [x] `README.md` (one section at the end), this doc, the PF11c tracker row, PF11's Carry-over pointer

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf11c_contract_folder_is_the_apps_169_files` | pytest | 14 top files + README, the wind blobs, LF JSON, 14 + 155 = 169, the tiles tree `3d5a9f35`, the README names both commits and the seven wind files, the result's `files` names the arrays, 156 triangles = 156 ids |
| `test_pf11c_recorded_blobs_are_the_apps_at_the_commit` | pytest (app repo present) | `git ls-tree` at `bcdd021f1`: 169 entries, `APP_BLOBS`; the folder tree `0d5ce75d` |
| `test_wind_inputs_and_outputs` (§10) | pytest | 422 on `inputs.files.entities` (missing, wrong size), on `inputs.files.geometry` (the octahedron less one triangle: 3 open edges; 200 001 triangles); 1.2's three params stored with defaults and echoed, out of range 422, `country` 422; `lake` z0 0.01 / I and `open` 0.05 / II in the claim's profile; the stub's answer as it is refused (`engine`, the summary keys); a `pressure_coefficient` count of 155 → `output_invalid` (expected 156); a one-component velocity → `output_invalid`; the app's grids centred on cell (0, 0) 3 H beyond the bounds, nx × ny × components values; the app's result with a platform engine and summary completes (2.5 cu); 5.5 `files` = the five arrays with their sizes, each URL fetches its bytes, `urls` kept |
| `test_pf11c_shipping_names_in_any_case` | pytest | "Wind", "Standard", "Suburban", "Lawson", "Realizable_KE" accepted and stored lower-case |
| `test_pf11c_quality_picks_the_mesh` | pytest | draft / standard / high in the record and the claim (6 / 10 / 20 cells per side), estimates 3.1 / 7.8 / 25.1 cu; `ultra` → 422 on `quality`; standard by default |
| `test_pf11c_reference_is_recorded` | pytest | a CL0 id at 0 and at 41, another person's project past its head, a deleted project: recorded, no 404; own cloud project past its head → 409 `seq_ahead`; bad ids 422; no snapshot, no ops; `doc_version_needed` 0; `/v1/jobs?project_id=` lists the job |
| `test_airflow_kind` (§10) | pytest | 20 rooms-file rules (one case each) + not JSON / not an object; `geometry` 422; `rooms` required; four params 422; the two-window room within 1 % of Q = sqrt(2 Δp / ρ) / sqrt(1 / (Cd A₁)² + 1 / (Cd A₂)²), signed from → to (flipped when written from outside); a cp-less opening takes the nearest facing triangle's Cp; `air_changes` per room in order; the runner's result (fields, entities, flows, the 1.1 m grid with Q / A in the door's cell, NaN elsewhere, engine and image) passes §6.3 |
| `test_pf11c_airflow_waits_for_its_wind_job` | pytest | queued beside its wind job (`base_job_id`, a message, 0.3 cu): no airflow claim while the wind job is queued or running; after it succeeds the airflow job's `rev` moves and its message clears; its claim carries `rooms`, `wind_geometry`, `wind_pressure_coefficient` (signed, sizes); the real runner on the downloaded inputs completes it (0.1 cu); 5.5 `files`; usage by kind |
| `test_pf11c_airflow_fails_with_its_wind_job` | pytest | a wind job failed (`bad_input`), cancelled, expired → its airflow job `failed` / `bad_input`, no cost, `rev` moved; nothing left to claim; no airflow charge |
| `test_pf11c_airflow_names_a_matching_wind_job` | pytest | another account's job answers exactly as an unknown id; `differs` for direction, speed, reference height, terrain; a failed wind job → `state` failed |
| `test_pf11c_worker_runs_the_study_without_docker` | pytest | the worker wrapper (container mode) with `local_analysis_docker.py`: the wind stand-in then the real airflow runner, both succeeded with their files maps; a wind job the stand-in cannot answer fails `bad_input` and its airflow job with it |
| `test_pf11c_wind_case_files_by_turbulence_model` | pytest | `realizableKE` with `0/epsilon`, `kOmegaSST` with `0/omega` (`atmBoundaryLayerInletOmega`, `omegaWallFunction`), schemes and solvers by variable; `endTime 2000`; residuals 1e-4; z0 0.01 at the inlet of U, k and the second variable; `nutkAtmRoughWallFunction` on the ground; cells by quality |
| `test_pf11c_wind_ground_grid_velocity_and_summary` | pytest | the grid at `pedestrian_height_m`, cells of `grid_cell_mm`, origin a cell centre, points row by row from the south; a wind from 90 degrees → −x, from 0 → −y; three grids, origins, LDDC classes, NaN / 255, the summary with `residual`; §6.3 passes; the 250 000-point cap coarsens the cell |
| `test_pf11c_wind_solver_log_residuals` | pytest | iteration, converged, the largest last initial residual |
| `test_pf11c_wind_surroundings_and_terrain` | pytest | `surroundings.stl` and `terrain.stl` in snappyHexMesh and every `0/` file, the terrain's rough wall; H the tallest height, the inside point above the terrain; points 1.5 m above a sloped terrain, 1.5 m above z = 0 off it |
| `test_pf11c_routes_echo_render_jobs_1_2` | pytest | 1.0, 1.1, 1.2 and no header on 5.1, 5.3, 5.6, `/analysis/catalogue`, 5.7 (200 and 204), 5.8, 5.10, `/v1/jobs` 5.1 / 5.3 / 5.6 → `render-jobs/1.2`; 2.0 → 400 with `supported` 1.2 |
| `test_pf11c_clients_and_documents_speak_1_2` | pytest | the four routers on (1, 2), workers' `ECHO`, the wrapper, `jobs.ts` (and `JobKind` airflow), the admin page, the three demo scripts, `export_openapi.py`, `openapi/v1.json` (and `airflow` in the enum), both SDKs, the label, the demo's airflow command |
| `test_pf11c_profiles_estimates_and_catalogue` | pytest | the five terrains and categories, LDDC classes, 2000 / 1e-4, the two models, no profile grid keys, GD2's note; airflow's estimate seed and 1000 estimate iterations; the catalogue's files and terrain; airflow's image |
| PF6's, PF6a's, PF6b's, PF11's, PF11b's, PF12's, PF4b's suites | pytest | green with the moved assertions (As-built) |
| `npm run lint`, `npm run build` | build check | green |

## Human test

About 10 minutes, on this PC, against a local API with no Docker and no OpenFOAM (the wind job is answered by the app's own fixture arrays; the airflow job by the real runner). Four PowerShell windows; `<WT>` = `X:\Truebex-autopilot\t97-pf11c-the-analysis-service-follo`.

1. **API (window A).** `cd <WT>\server`, then `.venv\Scripts\python.exe scripts\make_signing_key.py --kind lic` and copy its `LICENCE_SIGNING_KEY=` and `LICENCE_KEY_ID=` values into:
   `Set-Content .env -Encoding ascii -Value 'DATABASE_URL=sqlite:///./pf11c-human.db','SECRET_KEY=pf11c-human-test-0123456789abcdef0123456789abcdef','API_URL=http://127.0.0.1:8000','CORS_ORIGINS=http://127.0.0.1:3197','LICENCE_SIGNING_KEY=<paste>','LICENCE_KEY_ID=<paste>'`
   then `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` → "Uvicorn running on http://127.0.0.1:8000". (Delete `server\.env`, `server\pf11c-human.db` and `server\storage` afterwards.)
2. **Site (window B, `<WT>`).** `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build` (about 4 min), then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → "serving … on http://127.0.0.1:3197/" (another port: use it here and in `CORS_ORIGINS`). Open `http://127.0.0.1:3197/signup/` and sign up (an `example.com` address, a password of 8+ characters).
3. **Accounts (window C, `<WT>\server`).** `.venv\Scripts\python.exe -m app.admin_cli <you>` → "<you>: admin on". `.venv\Scripts\python.exe scripts\demo_replica.py login --email <you> --password <pw> --trial` → "Pro trial started" and a `tbx_dev_…` device token. In the browser reload, then Admin → Render → "Issue a worker token": name `cpu-local`, tick `wind` and `airflow` (the list now ends with `airflow`), class `cpu-8`, Issue token → the `tbx_wrk_…` token, shown once.
4. **Submit the study (window C).** `$F = "tests\contracts\render-jobs"`, then
   `.venv\Scripts\python.exe scripts\demo_analysis.py --token <tbx_dev_…> wind --stl $F\wind-geometry.bin --entities $F\wind-entities.bin --direction 225 --project-id f08ffe0283418dea8627d42c7908ab88` → "wind job queued on cpu-8, standard: estimate 8.7 cu" and its job id; then
   `.venv\Scripts\python.exe scripts\demo_analysis.py --token <tbx_dev_…> airflow --wind-job <wind job id> --direction 225 --project-id f08ffe0283418dea8627d42c7908ab88` → "airflow job queued on cpu-8, standard: estimate 0.3 cu", "Waits for its wind job to finish." and its job id.
5. **The Cloud page, queued.** Dashboard → Cloud → Recent jobs: "Airflow study" (Queued, the line "Waits for its wind job to finish.", "about 0.3") above "Wind study" (Queued, "about 8.7").
6. **The worker (window D, `<WT>`).** `Set-Content worker\worker.local.toml -Encoding ascii -Value 'api = "http://127.0.0.1:8000"','token = "<tbx_wrk_…>"','worker_id = "cpu-local"','kinds = ["wind", "airflow"]','class = "cpu-8"','mode = "container"','docker = "X:/Truebex-autopilot/t97-pf11c-the-analysis-service-follo/server/scripts/local_analysis_docker.py"','work_dir = "worker/jobs"','keep_work = true','heartbeat_s = 5','wait_s = 2'`, then `$env:TRUEBEX_WIND_STAND_IN = "<WT>\server\tests\contracts\render-jobs"` and run `py -3.12 worker\truebex_worker.py --config worker\worker.local.toml --once` twice → first "claimed <wind job> (wind, estimate 8.7 cu)" … "complete <wind job>: 5 files", then "claimed <airflow job> (airflow, estimate 0.3 cu)", "running the airflow solver (truebex-analysis-airflow:1)", "complete <airflow job>: 5 files (5 sent)". (Delete `worker\worker.local.toml` and `worker\jobs` afterwards.)
7. **The answers (window C).** `.venv\Scripts\python.exe scripts\demo_analysis.py --token <tbx_dev_…> output --job <wind job id>` → engine `truebex-stand-in`, project `f08ffe…` at sequence 0, `pressure_coefficient` 156 values on faces, grids `speed_ratio` x1, `velocity` x3 and `comfort_lawson` x1 of 89 x 72 cells of 1000 mm centred at [-30850, -30850, 1500], and "files: 5" with 624, 2496, 25632, 76896 and 6408 bytes. The same for the airflow job → engine `truebex-airflow`, `air_changes` 2 values on spaces, `opening_flow` 3 values on openings, `velocity` x3 at z 1100, "files: 5". (`--json` prints the whole 5.5 answer.)
8. **The Cloud page, done.** Reload Dashboard → Cloud: both rows Done, cost 0.1 each; "By job type" lists Airflow study 0.1 and Wind study 0.1.
9. **Optional, the owner's:** AN3's wind study from the app's Shipping release against `https://api.truebex.com` with a real cpu-8 worker (`infra\worker\analysis\wind\build.ps1` and `airflow\build.ps1` on a Docker host, GD3): a 12-direction study with indoor storeys submits 12 wind and 12 airflow jobs, the airflow ones start as their wind ones finish, and the app colours the facades and draws the comfort grid from each result.

## Risks / traps

* **The app's own fixture geometry is not a 2-manifold.** `wind-geometry.bin` is the kernel massing (the app's export without its 3D tool): closed, but 12 edges lie on four triangles where its solids touch (and 2 triangles coincide). A strict "every edge on exactly two triangles" refuses it; PF11c refuses only open edges (an odd count) and counts the rest (As-built 3).
* **Packaged FNames.** The app writes `kind`, `quality`, `terrain`, `comfort` from FNames; a Shipping build may hand them back in the name table's first case ("Wind"). The analysis kinds read them without case; the render kinds (PF6) still compare exactly (a carry-over note below).
* **Two fixture folders.** `tests/contracts/render-jobs/` is the app's (re-copy with the sync script; then `APP_BLOBS` and the commits in `test_pf6a_render_jobs_1_1.py`, and `test_pf11c_render_jobs_1_2.py`'s `WIND_BLOBS` / commits); `tests/fixtures/render/` is the platform's (`make_render_job_fixtures.py [--check]`; the stand-in's five array names are in `test_pf6a`'s `STAND_INS`).
* **`direction_deg` as a float.** `demo_analysis.py` sends `225.0`; the airflow check compares the four site params as numbers (to 1e-9), so 225 and 225.0 match.
* **The 24 h expiry.** An airflow job whose wind job never ends waits with it; both expire after 24 h queued (and the airflow one fails with its wind job's expiry if that comes first).

## As-built

* **Date, branch, commits:** 2026-10-24, `ap/t97-pf11c-the-analysis-service-follo` (base `master` 1a8b577): `47b8144` (the re-copy and the 17 tests, failing first), `d7f778a` (the implementation, the 18th test, the moved assertions), and the docs commit ticking this row.
* **The copy:** `sync-contract-fixtures.ps1 -Contract render-jobs` from app `main` `bcdd021f1` (the folder as `51b5adf01` left it; folder tree `0d5ce75d3`): 169 files, 7 new (`wind-result.json`, `wind-geometry.bin`, `wind-entities.bin`, `wind-pressure_coefficient.bin`, `wind-speed_ratio.bin`, `wind-velocity.bin`, `wind-comfort_lawson.bin`), 162 unchanged, none removed, every blob id equal; the tiles tree did not move (`3d5a9f35`). `test_pf6a`'s `APP_COMMIT` / `APP_FOLDER_COMMIT` / `APP_BLOBS` follow.
* **Counts:** pytest 934 → 952 collected (18 new). All 18 fail on 1a8b577: the 17 of `47b8144` ran on master's code with the re-copied folder (7 failed, 10 errored at the rig, which cannot issue an `airflow` worker; with a wind-only rig all 17 failed on their own assertions: entities optional, a CL0 id 404, quality ignored, no `airflow` module, no `files`, `kEpsilon`, `render-jobs/1.1` …), and the 18th on an archive of 1a8b577.
* **Decisions and deviations:**
  1. *5.5's files map:* always filled by the platform for every file the result names, `bytes` from the declaration (count × item size; a report's from the stored blob); a worker's own `files` (the app's stub writes role names) is dropped when the result is stored. `urls` and `urls_expire_at` stay beside it (additive): PF11's readers are `test_analysis.py`, `test_pf11_pf12_meet.py` and, before PF11c, `demo_analysis.py` (now prints `files`); the SDKs pass 5.5 through as an open document (`JobOutput`), so no SDK reader moves. The texture kind's answer gains the map too.
  2. *Terrain and Lawson:* `country` dropped (nothing in the contract, the site, the `/v1` docs or the SDKs names it: checked by grep); `lake` 0.01 / I and `open` 0.05 / II added as 1.2.0 lists them, so the app's `open` now runs at 0.05. Lawson: 0 sitting ≤ 4, 1 standing ≤ 6, 2 strolling ≤ 8, 3 business walking ≤ 10 m/s, 4 uncomfortable (LDDC, the instantaneous speed, as the app's `CadWindComfort::InstantClass`); `profiles.json` keeps GD2's placeholder note.
  3. *The closure rule (the manifold check):* an edge is matched by exact vertex coordinates (float32 values; −0 = 0); the geometry is refused when any edge lies on an odd number of triangles (`open_edges`: an open shell, or a fin on three), with `data.open_edges`, `over_shared_edges` and `triangles`. Edges on four or more (an even count) are where closed solids touch: the kernel massing the app exports without its 3D tool, and the app's own `wind-geometry.bin` (12 such edges, 2 coincident triangles), which the task asked to submit in the live run. snappyHexMesh meshes touching closed solids, so these are counted (`inputs.geometry_over_shared_edges`) and accepted; the app's 3D-tool wrap checks itself closed (`Cad3DWindExport`) and sends a failed wrap "as it is", which the platform then refuses only if it is open. The strict reading is one condition in `inputs.read_stl`. No winding check (the runner samples the nearest boundary face either way). PATCH proposed below.
  4. *Quality and the estimate:* the claim's wind profile carries `quality`, `cells_per_side` and the case's `cells_per_h` (6 / 10 / 20: the background mesh, H / n; snappy's two refinement levels stay); the estimate scales the domain's cells the same way and counts GD3's 1000 iterations (`estimates.json` `wind_iterations`; a converged run stops before the 2000-iteration cap); the 8 M-cell clamp (`wind_cells.max`, the 12 GB worker's ceiling) stays and caps `high`. Side by side with the app's pre-submit numbers (`CadWind::CuDraft` / `CuStandard` / `CuHigh`): the octahedron 3.1 / 7.8 / 25.1 cu, the app's export (156 triangles, 26.3 × 9.3 × 10.4 m) 3.3 / 8.7 / 25.1 cu (0.51 M / 2.37 M / 8 M cells); the app 3.0 / 7.6 / 20.0 cu per direction. Airflow: platform 0.3 cu (a fixed 60 s on cpu-8 at 0.25), app `CadWind::CuAirflow()` 1.0 cu; measured, a run took 0.3 s inside the wrapper (charged 0.1 cu). Both seeds yield to the median of 50 real jobs.
  5. *The airflow kind:* `geometry` refused (AN3 sends `rooms` only: `CadAnalysisJobs.cpp` `Submit`, `A.InputFiles = {rooms}`; the stub never reads one). `from` may be `outside` (the app writes side 0 → side 1, so `BuildNetwork` puts `outside` on either side) and `cp` is allowed on any opening with an outside side (6.5.3 says "to outside"): a PATCH below. A cp-less opening's Cp is the nearest centroid among triangles facing it (unit normal · outward ≥ 0.5, as the app's stub), all triangles when none faces it. Zero openings are allowed (the app writes a storey's rooms even without windows): every room 0 1/h, no `opening_flow`, no grid. Limits: 300 rooms (the dense Newton step is O(n³) in pure Python: about 5 s a step at 300; a house's storeys hold tens), 5000 openings. The velocity grid comes from a network, not a field (as the stub draws it: z = `velocity_height_m` above the datum, not above each floor). The image is its own, `truebex-analysis-airflow:1` (the acoustics image's base and entrypoint pattern), so the engine names `truebex-airflow` and that image.
  6. *The claim's names:* the wind job's files reach the airflow runner as `inputs.files.wind_geometry` and `wind_pressure_coefficient` (`results.platform_inputs`, as energy's `weather`); when either is gone the claim fails `bad_input`.
  7. *The wait:* the airflow job keeps its wind job in `base_job_id` (shown in its record); its ending rides `render/sets.on_ended` (one call: every failed, cancelled and expired path already runs it) rather than five call sites. A race where the wind job ends between the airflow submit's check and its commit leaves the airflow job queued until its own 24 h expiry (at no charge).
  8. *The reference:* "a cloud project the caller can view" = a live project with an active membership of the caller (the same test as `open_project`'s viewer role). /dashboard/cloud/ shows no project for any job (kind, id, state, time, cost), so a recorded CL0 id is invisible there; `/v1/jobs` and 5.2 return `project_id` as recorded and `/v1/jobs?project_id=<id>` lists by it. Analysis claims now carry no snapshot even for a cloud project (PF11 sent one) and no deletion or membership check (nothing is opened).
  9. *The terrain ground (not cut):* the terrain is a second wall surface in snappyHexMesh (`terrain`, rough wall with the terrain's z0), the box's bottom drops to the terrain's lowest point, H counts the surroundings' height, and the inside point sits above the terrain; the pedestrian points stand on the highest terrain triangle under them (flat ground at z = 0 off it). An open terrain that does not span the box leaves fluid under its edge: GD2's cases decide whether the app should send a terrain that covers the domain (or a closed one); never run here.
  10. *The case frame keeps the datum* (`Frame.z0` = 0, the contract's z = 0; it was the building's lowest point), and H is the height above it.
  11. *FName case:* `kind`, `quality`, `terrain`, `comfort`, `turbulence_model` of the analysis kinds are read without case and stored lower-case (memory of the telemetry trap: a Shipping build may write "Wind"). Render kinds are PF6's and unchanged.
  12. *The documents:* `openapi/v1.json` document 1.2.0 (it grew: `airflow` in `JobRequest.kind`, the description), the SDKs 1.2.0 (`_operations.py` / `operations.mjs` regenerated by `sdks/generate.py`; the two generated type lines in `models.py` / `schema.d.ts` written as the generators write them, since their tools need a network install).
  13. *PF11's stand-in* (`tests/fixtures/render/wind-result.json`) is in 1.2.0's shape now (the 1.2 params, the four summary keys, `speed_ratio` and `velocity` 4 × 4 grids at 1000 mm), so the stub solver and `test_analysis.py` pass the new rules; `make_render_job_fixtures.py --check` reproduces it.
* **Assertions moved (1.2 changes only):** `test_pf6a_render_jobs_1_1.py`: `APP_COMMIT`, `APP_FOLDER_COMMIT`, `APP_BLOBS` (+7), the LF check on text files only, the stand-in check allows the app's own `wind-result.json`, `STAND_INS` (+2 arrays), `ECHO` 1.2, the routers on (1, 2), the wrapper / `jobs.ts` / `demo_render.py` / SDK strings on 1.2, the README's 1.2 header; `render_helpers.py` and `pf12_helpers.py` `RJ` 1.2 (what the app sends); `test_render.py` the echo and `supported` 1.2; `test_pf6b_claim_long_poll.py`, `test_pf12_api.py` the echo 1.2; `test_pf11b_ai_proxy_1_1.py` `demo_analysis.py` on 1.2; `test_analysis.py` `iterations_max` 2000 and the catalogue's kinds + `airflow`; `test_analysis_runners.py` `endTime 2000`, `RASModel realizableKE`, the LDDC thresholds, `test_wind_sampling_and_result` (velocities into `build_result`, the centred origin −22 000 / −21 000, classes [0, 1, 255, 2, 3, 0], the summary's `residual`), the images loop + `airflow`; `test_pf4b_project_log_1_2.py` the document version at least 1.1.0 and the SDK versions = the document's (they were pinned to 1.1.0). Setup only (no assertion): `analysis_helpers.wind_body` sends the 8 ids of `entities()`, and `test_pf11_pf12_meet.py` uploads them.
* **Self-tests:** the whole suite on SQLite in the verify gate (last bullet); on a throwaway PostgreSQL 17 cluster in Asia/Baghdad (11 files: `test_pf11c_render_jobs_1_2`, `test_analysis`, `test_analysis_runners`, `test_render`, `test_render_worker`, `test_pf6a_render_jobs_1_1`, `test_pf6b_claim_long_poll`, `test_pf11_pf12_meet`, `test_pf4b_project_log_1_2`, `test_pf12_api`, `test_pf11b_ai_proxy_1_1`: 132 passed in 404 s; cluster removed). **Live run** (scratchpad `live_selftest.sh`): uvicorn on SQLite, `demo_replica.py login --trial`, a cpu-8 worker token for wind and airflow; `demo_analysis.py wind --stl …/wind-geometry.bin --entities …/wind-entities.bin --direction 225 --project-id f08ffe0283418dea8627d42c7908ab88` → "estimate 8.7 cu"; `airflow --wind-job …` → "estimate 0.3 cu", "Waits for its wind job to finish."; `worker/truebex_worker.py --once` twice (container mode, `local_analysis_docker.py`, `TRUEBEX_WIND_STAND_IN`): the wind job "5 files (4 sent)" (the entities file was the upload's), then the airflow job "5 files (5 sent), 0.3 s, 0.1 cu"; 5.2 of the airflow job `base_job_id` = the wind job, 6 Newton steps, residual 3e-15 m³/s; `/jobs` with a 1.1 header answered `render-jobs/1.2`; usage by kind airflow 0.1, wind 0.1. The two 5.5 answers (signatures elided):

```json
{"schema": "truebex-analysis/1", "kind": "wind", "project_id": "f08ffe0283418dea8627d42c7908ab88", "at_seq": 0,
 "params": {"speed_ms": 5, "direction_deg": 225.0, "reference_height_m": 10, "terrain": "suburban", "comfort": "lawson",
            "pedestrian_height_m": 1.5, "grid_cell_mm": 1000, "turbulence_model": "realizable_ke"},
 "engine": {"name": "truebex-stand-in", "version": "1", "image": "truebex-analysis-wind:1 (local stand-in)"},
 "summary": {"max_speed_ms": 3.650753, "max_speed_ratio": 0.730151, "iterations": 0, "residual": 0.0},
 "fields": [{"name": "pressure_coefficient", "unit": "1", "on": "faces", "count": 156,
             "values": "5f46ba881bd75079f4b0f3bac1da7158611ca9e617aed3dd3ba5f6a0ba79639d",
             "entities": "f13ab02c907855b7c5682d27e0b11940c7d10302118583d60697ff7be1643902"}],
 "grids": [{"name": "speed_ratio", "unit": "1", "origin_mm": [-30849.998861551285, -30849.998861551285, 1500], "cell_mm": 1000, "nx": 89, "ny": 72,
            "values": "351ea655cdf1339b3b8178d935953fc4da29b7279ccc1e3283a6a007e10c3522"},
           {"name": "velocity", "unit": "m/s", "origin_mm": [-30849.998861551285, -30849.998861551285, 1500], "cell_mm": 1000, "nx": 89, "ny": 72,
            "components": 3, "values": "e59f416ca856877f34aed554b1e456fce8d89ffd799bf2a32ba060f32add9288"},
           {"name": "comfort_lawson", "unit": "class", "origin_mm": [-30849.998861551285, -30849.998861551285, 1500], "cell_mm": 1000, "nx": 89, "ny": 72,
            "values": "26cb0c4f8afb9758de3d7354c4cd850f871a4f6a55e9bb3516cd3d167a3bd1ae"}],
 "report": null,
 "files": {"5f46ba881bd75079f4b0f3bac1da7158611ca9e617aed3dd3ba5f6a0ba79639d": {"url": "http://127.0.0.1:18097/files/jobs/ed5a6e99ff3011ebe6e4071a27774c44/files/5f46ba88…?exp=…&sig=…", "bytes": 624},
           "f13ab02c907855b7c5682d27e0b11940c7d10302118583d60697ff7be1643902": {"url": "…/files/f13ab02c…?exp=…&sig=…", "bytes": 2496},
           "351ea655cdf1339b3b8178d935953fc4da29b7279ccc1e3283a6a007e10c3522": {"url": "…/files/351ea655…?exp=…&sig=…", "bytes": 25632},
           "e59f416ca856877f34aed554b1e456fce8d89ffd799bf2a32ba060f32add9288": {"url": "…/files/e59f416c…?exp=…&sig=…", "bytes": 76896},
           "26cb0c4f8afb9758de3d7354c4cd850f871a4f6a55e9bb3516cd3d167a3bd1ae": {"url": "…/files/26cb0c4f…?exp=…&sig=…", "bytes": 6408}},
 "urls": {"5f46ba88…": "…the same five URLs…"}, "urls_expire_at": "2026-10-24T12:11:40Z", "rev": 3}
```

```json
{"schema": "truebex-analysis/1", "kind": "airflow", "project_id": "f08ffe0283418dea8627d42c7908ab88", "at_seq": 0,
 "params": {"wind_job_id": "ed5a6e99ff3011ebe6e4071a27774c44", "speed_ms": 5, "direction_deg": 225.0, "reference_height_m": 10,
            "terrain": "suburban", "velocity_height_m": 1.1},
 "engine": {"name": "truebex-airflow", "version": "1", "image": "truebex-analysis-airflow:1"},
 "summary": {"rooms": 2, "openings": 3, "iterations": 6, "converged": 1, "max_air_changes": 438.195962, "residual_m3s": 3.10862e-15},
 "fields": [{"name": "air_changes", "unit": "1/h", "on": "spaces", "count": 2,
             "values": "5745f63be563722c16f6abc5b52abaa4a4f8d43dffea77b5c22d822d45e17851",
             "entities": "9b197751829f5508d33cf8d1d228012a0c0e50015590fc16b9641ecfae7b2aef"},
            {"name": "opening_flow", "unit": "m3/s", "on": "openings", "count": 3,
             "values": "6c3635b3d82559fc959d970beb3f10e1c806d7d8b81809ef85b10b39b1ade425",
             "entities": "6c0ccea8c86e2bbfd67bca3f5e1b80070c1f39bbdbe2e75be6fde269186fa6a0"}],
 "grids": [{"name": "velocity", "unit": "m/s", "origin_mm": [3250.0, -1900.0, 1100.0], "cell_mm": 500.0, "nx": 22, "ny": 27,
            "values": "c42023906f8657b57e208e892330e9c33ddaa231a5da557548d1b9e7d7975172", "components": 3}],
 "report": null,
 "files": {"5745f63be563722c16f6abc5b52abaa4a4f8d43dffea77b5c22d822d45e17851": {"url": "http://127.0.0.1:18097/files/jobs/6d8532583890748b1db22932fe98f9cf/files/5745f63b…?exp=…&sig=…", "bytes": 8},
           "9b197751829f5508d33cf8d1d228012a0c0e50015590fc16b9641ecfae7b2aef": {"url": "…/files/9b197751…?exp=…&sig=…", "bytes": 32},
           "6c3635b3d82559fc959d970beb3f10e1c806d7d8b81809ef85b10b39b1ade425": {"url": "…/files/6c3635b3…?exp=…&sig=…", "bytes": 12},
           "6c0ccea8c86e2bbfd67bca3f5e1b80070c1f39bbdbe2e75be6fde269186fa6a0": {"url": "…/files/6c0ccea8…?exp=…&sig=…", "bytes": 48},
           "c42023906f8657b57e208e892330e9c33ddaa231a5da557548d1b9e7d7975172": {"url": "…/files/c4202390…?exp=…&sig=…", "bytes": 7128}},
 "urls": {"5745f63b…": "…the same five URLs…"}, "urls_expire_at": "2026-10-24T12:11:42Z", "rev": 4}
```

  (438 1/h is the demo rooms' wide-open windows at 5 m/s on the stub's Cp: a network sample, not a design figure.)
* **Headless Cloud page** (scratchpad `cloud_check.sh` + `cdp_cloud.mjs`): `out/` built with `NEXT_PUBLIC_AUTH_URL` = the live run's API, served on :3197, headless Edge signed in as the live run's account: Dashboard → Cloud lists "Airflow study · 6d853258 · Done · 0.1" and "Wind study · ed5a6e99 · Done · 0.1", and By job type "Airflow study 0.1", "Wind study 0.1"; no page error (only `serve-out.py`'s RSC-prefetch 404s). The queued state ("Waits for its wind job to finish.") is human test step 5.
* **PF11's carry-over "AN2 / AN3 / AN4: exports and submissions … the first real runs":** met for AN3 on the platform's side (the app's export, entity ids, 1.2 params and the airflow submissions are taken and checked, results come back through the map the app reads); the first real runs and measured seconds per kind stay open (GD3 and the owner). AN2 and AN4 are not touched.
* **Contract §11 (for the app half to set in `contracts/render-jobs.md`):** `POST /jobs` "PF11 for analyses: done 2026-10-10 (PF11); render-jobs 1.2.0's `wind` inputs / params and the `airflow` kind 2026-10-24 (PF11c, `ap/t97-pf11c-the-analysis-service-follo`)"; `GET /jobs/{job_id}` "PF6: done (PF6, long-poll on `rev`); an airflow job's `base_job_id` names its wind job (PF11c)"; `POST /jobs/{job_id}/cancel` "PF6: done; a cancelled wind job ends its waiting airflow jobs `bad_input` (PF11c)"; `GET /jobs/{job_id}/output` "PF6 (PF11): done; the 1.2 `files` map since PF11c"; `GET /jobs/usage` "PF6: done (`by_kind` includes `airflow`)"; `/uploads` purpose `job-input` "PF11: done (PF11, share-bundle §5; the roles `geometry`, `entities`, `surroundings`, `terrain`, `rooms` checked at 5.1 since PF11c)".
* **PATCH proposals (for the app half):**
  1. §9 / 6.3: `wind-result.json` is the stub's answer, so its `engine.image` is null and its `summary` has `max_speed_ms` only, while 6.3 says the engine names its image and 6.5.2 lists four summary keys: say the fixture is a sample of the layout only, or give it a stub image name and the four keys (the platform refuses it as a worker's output).
  2. 6.5.2: "ONE closed, outward-wound 2-manifold (every edge on exactly two triangles)" — the app's own `wind-geometry.bin` (the kernel massing, no 3D tool) has 12 edges on four triangles. Either the app fuses the massing before export, or the contract says "closed: every edge on an even number of triangles (touching closed solids allowed)", which is what PF11c checks; and the tolerance: edges match by exact float32 vertex coordinates (no welding).
  3. 5.5 / 6.3: the platform keeps `urls` {sha256: url} and `urls_expire_at` beside `files` (PF11's additive keys); `files[sha].bytes` for a report is the stored size.
  4. 6.5.3: `from` may be `outside` (the app writes side 0 → side 1), and `cp` may be given on any opening with an outside side; the `normal` then points from outside into the room.
  5. 6.5.3: the airflow `velocity` grid's z is `velocity_height_m` above the datum in the app's stub (one grid for every storey), not above each room's floor.
* **Carry-over → which feature:** **GD3 / the owner:** build and publish `truebex-analysis-wind` and `truebex-analysis-airflow`, the first OpenFOAM run (realizableKE, the terrain surface), measured seconds per kind. **GD2:** COST 732 / AIJ validation, the turbulence model, the terrain extent, the interior CFD (`inputs.files.geometry` for airflow). **The app (AN3):** the PATCH lines above; a `pressure_coefficient` sample for an open terrain. **PF6's owner:** the render kinds still compare `kind` and `quality` exactly (a Shipping FName may differ in case). Met by PF14f (2026-10-25, `PF14f-fname-case.md`): the render kinds, 5.3's filters, the project log, comments and member roles now match without case.
* **Verify gate** (`scripts\autopilot-verify.ps1`, 2026-10-24): GREEN in 739 s: lint, build, pytest 952 collected, 933 passed + 19 skipped (the Postgres-marked tests and the app-repo checks need their environment) in 654 s. The run before it failed one test, `test_pf4b_project_log_1_2.py::test_pf4b_api_documents_name_1_2_and_comments` (it pinned the API document and SDK versions at 1.1.0; moved, above).
