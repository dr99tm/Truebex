# PF6d — The render service follows render-jobs 1.4.0 (PR5's headset faces): the optional id, ids and depth files, version and op_seq per face and the manifest's tour checked, stored, served from tiles_base and carried, the render-jobs/1.4 echo (launch priority 2)

**Needs merged:** PF6, PF6a, PF6b, PF6c (all on `master` 61ac33a); PR5 on the app side (the native headset app target, app task T134, merged on app `main` `2c842b8f1` through T214 with ME3, ME4, ME5 and PL1, 2026-11-09 14:32 UTC). **Unblocks:** PR5's headset against the live API (the entity under the pointer, the hit point for Move, faces that refresh after another person's edit); CL3's worker writing the 1.4 face files (PR5's carry-over). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\render-jobs.md` **1.4.0** (2026-11-09, wire header `render-jobs/1.4`, app blob `6a47207a8a0bfc464d3910d4609eff49eb2a4ffd`): its *Changes* line is the only normative text (§6.2's table did not change). The app side is authoritative (C.9).

## Status

**Built 2026-11-09** on `ap/t102-pf6d-the-render-service-follows` (Autopilot T102); see As-built. What was behind on `master` 61ac33a, checked against app `main` `2c842b8f1` (read through the manager's snapshot, see As-built):

| # | Where (master 61ac33a) | Before |
|---|---|---|
| 1 | `server/app/render/tiles.py:50` `tile_key`, `:46` `_TILE_KEY`, `:116-188` `check_manifest`, `:191-199` `faces_of` / `all_tiles` | the store held only `tiles/<sha256>.jpg`; a face's `id`, `ids`, `depth`, `version`, `op_seq` and the manifest's `tour` were ignored: not checked, the files not copied from the upload, not collected |
| 2 | `server/app/routers/tiles.py:29` `_TILE`, `:45` | only `<sha256>.jpg`, answered `image/jpeg`: the headset's `FetchBlob(Sha, "png")` / `"json"` (`VrSession.cpp:537-552`) got 404 |
| 3 | `queue.complete` stores the manifest as sent | no `version` on any face: the headset reads an absent `version` as 1 (`VrTour.cpp:71-75`) and refetches a face only when its version grows (`VrSession.cpp:721-735`), so after an edit it never showed the re-rendered faces |
| 4 | `routers/jobs.py:31`, `workers.py:36` and `:38` (`ECHO`), `analysis.py:23`, `v1/jobs.py:25` on `contract("render-jobs", 1, 3)`; `worker/truebex_worker.py:54`; `src/lib/jobs.ts:9`; `demo_render.py:33`, `demo_analysis.py:38`, `demo_mobile.py:48`; `export_openapi.py:56` (and `API_VERSION` `:34`, 1.3.0) | `render-jobs/1.3`; the headset sends `render-jobs/1.4` (`VrHttpBackend.cpp:24`) |
| 5 | `worker/truebex_worker.py:448-465` `outputs` | uploads only a rendered face's `.jpg` tiles |

## Goal

The headset app (PR5) can open a cloud panorama set from the platform the way it opens one from its own stub: it fetches a face's id, ids and depth files from `tiles_base` to know which wall, floor or object the pointer is on and where the ray stops, fetches the set's tour, and, when another person's edit re-renders some faces, sees their `version` move and refetches only those. Old workers and clients keep working: a 1.3 worker's manifest is still accepted, gains no file key, and its faces still get a `version`, so the headset stays current even before CL3's worker writes the pick files.

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4, C.9; `PF6-cloud-render-orchestration.md`, `PF6a-render-jobs-1-1-0.md`, `PF6b-claim-long-poll-gone-worker.md`, `PF6c-render-jobs-1-3-0.md` (Scope, As-built: the echo tests this task moves).
* `render-jobs.md` 1.4.0: §3 *Changes* 2026-11-09 · 1.4.0, §5.5, §6.1, §6.2, §11's new 5.5 row.
* App (read only, `main` `2c842b8f1`): `Docs/roadmap/40/PR5-native-headset-app-target.md` (*Data (kernel)*, Carry-over); `Plugins/TruebexVR/Source/TruebexVRCore/Private/VrSession.cpp` (`FetchBlob`, `RequestFace`, `RequestPicks`, `OnManifest`), `VrTour.cpp` (`FVrManifest::FromJson`, `FVrTour::FromJson`: `format` `truebex-tour/1`), `VrStubBackend.cpp` (the stub's manifest and tour); `Plugins/CADTOOL/Source/CadCore/Public/CadVrEdits.h`, `Private/CadVrEdits.cpp` (`EncodeIdTile` / `DecodeIdTile`: an 8-bit grey PNG and `{"schema": "truebex-ids/1", "ids": [null, …]}`; `EncodeDepthTile`: a 16-bit grey PNG; `DecodePick`, `HitPoint`).

## Scope

**In** (nothing was cut):

1. **`tiles.py`:** `check_manifest` takes a face's optional `id`, `ids`, `depth` (each a SHA-256; `id` and `ids` together), `version` (a whole number ≥ 1) and `op_seq` (a whole number ≥ 0), and the manifest's `tour` (a SHA-256). 5.9 checks every file a rendered face or the tour names (below), stores them **one key per extension** beside the colour tiles (`tiles/<sha256>.png`, `tiles/<sha256>.json`), copied from the job's upload session on completion as the `.jpg` tiles are. Carried faces keep the base's files, `version` and `op_seq`; `all_files` names every key a manifest holds for the collector. The docstring table is updated.
2. **`routers/tiles.py`** serves `<sha256>.png` (`image/png`) and `<sha256>.json` (`application/json`) like `.jpg`: no token, no contract header, immutable, any origin, `nosniff`. The CDN path (s3 + `CDN_BASE_URL`) holds the same keys with their media type (`tiles_base` + `/<sha256>.<ext>` is the object's URL).
3. **The reads pass the fields through:** 5.5, `/s/{slug}/live` (`render/live.py`), the members' `/projects/{pid}/panoramas/{set_id}`, `/v1/projects/{pid}/panoramas/{set_id}` and `/v1/jobs/{id}/output` answer the stored manifest. `/v1`'s and the mobile clients' manifest models do not name the new keys (decision, As-built); neither refuses nor drops them.
4. **The worker wrapper** uploads the `id`, `ids` and `depth` files of each rendered face and the `tour` the renderer writes beside its tiles (`out_dir/tiles/<sha256>.png` / `.json`; an update's tour equal to its base's need not be written again). The fake app writes them with `FAKE_TRUEBEX_FACE_FILES=1`.
5. **`render-jobs/1.4`** at every echo site of PF6c's item 5; 1.0–1.4 served, 2.0 → 400. `export_openapi.py` `API_VERSION` 1.4.0 and `"jobs": "render-jobs/1.4"`; `sdks/js/package.json`, `sdks/python/pyproject.toml`, `sdks/python/truebex/_version.py` 1.4.0; `openapi/v1.json` and the SDKs regenerated (`scripts/gen-sdks.ps1`), every `--check` clean.
6. No change to §6.2 beyond 1.4.0 and no new route. Beyond the brief: `src/lib/jobs.ts`'s `TileFace` / `TileManifest` name the 1.4 keys (optional), and `demo_render.py output` prints each face's `version`, `op_seq` and files and the tour.

**Out (and where it goes):**

* CL3's worker rendering `id`, `ids`, `depth` and the tour: **the app half** (PR5's carry-over; the file locations proposed in As-built).
* The headset app's build, APK and device run: **the owner** (GD4).
* Picking or depth in the web viewer, on the share page or on Android: **not this task** (a later PF9 / PF10 follow-up if wanted).
* The RTX PC's worker update to `render-jobs/1.4` and a live run against `api.truebex.com`: **the owner, at deploy**.
* §11's platform cell, §6.2's table and the stub's ID size: **the app half**, through the lines proposed in As-built (the app's docs are read-only here).

## Design

### API

| Endpoint | PF6d |
|---|---|
| every render-jobs route | `X-Truebex-Contract: render-jobs/1.4`; 1.0–1.4 or no header served; another MAJOR → 400 `contract_version` with `supported` `["render-jobs/1.4"]` |
| 5.9 complete | a 1.4 output is checked as below; a broken one answers 422 `output_invalid` with `data.errors[]` `{path, rule, message, sha256?}` (rules `id`, `ids`, `depth`, `version`, `op_seq`, `tour`, `file_missing`, `carried`); the lease survives a refusal |
| 5.5 output | the stored manifest with `tiles_base`: each face's `version` and `op_seq` always, its `id` / `ids` / `depth` and the manifest's `tour` when known; never a key with null |
| `GET /tiles/{sha256}.jpg` · `.png` · `.json` | public, `Cache-Control: public, max-age=31536000, immutable`, `Access-Control-Allow-Origin: *`, `X-Content-Type-Options: nosniff`, `image/jpeg` / `image/png` / `application/json`; one key per extension (a hash under another extension is 404) |

**The checks (5.9).** Shape (`check_manifest`, no file read): each of `id`, `ids`, `depth` a lowercase SHA-256 (null refused), `id` and `ids` together, `version` an integer ≥ 1, `op_seq` an integer ≥ 0 (booleans, strings, floats and null refused), `tour` a SHA-256. Files (`verify_tiles`), for every rendered face and the tour: in the claim's upload session, else already in the public store under its extension (as for `.jpg`), else `file_missing` at the field's path; `id` / `depth`: the PNG signature and the IHDR chunk (length 13, CRC good), width = height = the view's `levels[0]`, colour type 0 (grey), 8 bits for `id`, 16 for `depth` (33 bytes read, **no decode**); `ids`: JSON, `schema` `truebex-ids/1`, `ids` a list of 1 to 256 (an 8-bit index), `ids[0]` null, every other entry null or 32 hex; `tour`: JSON of at most 1 MiB, `format` `truebex-tour/1` (PR3's key, what `FVrTour::FromJson` reads), at least one node, every node's `view` a view of this manifest. A carried face's `id` / `ids` / `depth`, when sent, equal the base face's (`carried`).

**Who sets `version` and `op_seq`: the server.** A rendered face answers 1 on a panorama and the base face's `version` + 1 on a `tiles` job, with the job's `at_seq` as `op_seq`; a carried face keeps the base's (a base stored before PF6d: version 1 and the base's `at_seq`). A worker may send them: a value that disagrees is refused (`version` / `op_seq`), an omitted one is filled. So the headset stays current with today's (1.3) worker.

### Data

No table, no migration. Storage: `tiles/<sha256>.png` (a face's `id` or `depth`) and `tiles/<sha256>.json` (a face's `ids` or the manifest's `tour`) beside `tiles/<sha256>.jpg`, published with their media type and the immutable cache; `jobs/{job_id}/manifest.json` stores the manifest settled (every face's `version` / `op_seq`, a carried face's files from the base, an update with no `tour` keeps the base's). `render.tiles.gc` keeps every key a kept manifest names (`tiles.all_files`: tiles, face files, tour) and deletes unnamed `.jpg`, `.png` and `.json` past the one-day grace, as before for `.jpg`.

### Jobs / workers

The wrapper sends `render-jobs/1.4` and uploads, for each rendered face, its tiles and its `id` / `ids` / `depth` (`image/png`, `application/json`) from `out_dir/tiles/`, and the `tour` (skipped only when the renderer did not write it and it equals the base manifest's, `work/base.json`). The fake app (`FAKE_TRUEBEX_FACE_FILES=1`) writes CadVrEdits' formats at `levels[0]` px (a few entities in bands, a depth ramp with "nothing" at the top), `version` / `op_seq` as the server counts them, a three-node tour on a panorama, the base's on an update.

### UI

No page change. `src/lib/jobs.ts`: the 1.4 header, optional `id`, `ids`, `depth`, `version`, `op_seq` on `TileFace` and `tour` on `TileManifest`. `/developers/sdks/` shows the SDK version 1.4.0 (from `openapi/v1.json`).

### Security and privacy

The new files are public by content hash, like the tiles: an id file holds small indexes, an ids file entity ids of the model the share or set already shows, a depth file distances from a saved view's eye, a tour the views' titles. 5.9 reads at most 33 bytes of a PNG and 1 MiB of a JSON file, so a hostile worker upload cannot make it decode or load a large file; nothing outside the upload or the public store is read.

## Deliverables

- [x] `server/app/render/tiles.py` (checks, `settled`, `all_files`, one key per extension, the docstring table), `render/queue.py` (`complete` stores the settled manifest), `server/app/routers/tiles.py`
- [x] `server/app/routers/{jobs,workers,analysis,v1/jobs}.py` (1.4), `server/scripts/export_openapi.py`, `openapi/v1.json` (1.4.0), `sdks/` (1.4.0, regenerated)
- [x] `worker/truebex_worker.py` (1.4, the face files), `worker/tests/fake_truebex.py` (`FAKE_TRUEBEX_FACE_FILES`), `src/lib/jobs.ts`, `server/scripts/{demo_render,demo_analysis,demo_mobile}.py`
- [x] tests: `server/tests/test_pf6d_render_jobs_1_4.py` (11); the assertions 1.4 moves (As-built)
- [x] `README.md` (one section at the end), this doc, the PF6d tracker row, one carry-over line in PF6c's doc

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf6d_face_files_checked_stored_and_served` | pytest | a panorama whose every face names `id`, `ids`, `depth`, `version` 1, `op_seq` and a tour: accepted, 5.5 answers it exactly with `tiles_base`; `tiles/<sha>.png` / `.json` stored with their media type; `<tiles_base>/<sha>.png` and `.json` answer the bytes (hash = name) with `image/png` / `application/json`, immutable, `*`, `nosniff`, no contract echo; a hash under another extension 404; the PNG's IHDR 256 x 256, 8-bit grey; `/s/{slug}/live`, `/v1`'s panorama read, the members' read and `/v1/jobs/{id}/output` pass the keys through |
| `test_pf6d_output_invalid_face_files` | pytest | 36 broken outputs, each 422 `output_invalid` naming its path and rule: a face field not a SHA-256 (or null, uppercase), `id` without `ids` and back, a file not uploaded (each field and the tour), an `id` PNG of 512 px, not square, 16-bit, RGB, a bad IHDR CRC or a JPEG, a `depth` PNG of 8 bits, an `ids` file of another schema, with `ids[0]` named, a bad entry, 257 ids or not JSON, `version` 0, `"1"`, `true` or 2, `op_seq` 1.5, `"2"`, -1 or another `at_seq`, a tour with `schema` instead of `format`, a stray view, no node, or an ids file as tour; nothing published by a refusal; the same output whole then succeeds and only its files are published |
| `test_pf6d_check_manifest_rules_alone` | pytest | the shape rules without the store: the fixture with the 1.4 keys passes, `version` 0, `op_seq` null and a short tour hash are named |
| `test_pf6d_manifest_without_1_4_fields` | pytest | a 1.3 manifest (the app's fixture) is accepted; 5.5 answers it as sent plus `tiles_base`, `rev` and each face's `version` 1 / `op_seq` = `at_seq`: no `id`, `ids`, `depth` or `tour` key, no null |
| `test_pf6d_follow_set_versions_and_carried_faces` | pytest | the first render: every face 1 / its `at_seq` (filled); a tiles job re-renders n and e of every view: refused when a carried face says version 2 or the tiles job's `at_seq`, a re-rendered one version 1 or the old `op_seq`, a carried face another `id` or `depth`; accepted with agreeing values on some faces and none on others; n and e answer 2 / the tiles job's `at_seq` and their new files, the carried faces the base's `id`, `ids`, `depth`, `version`, `op_seq` and tiles, the manifest the base's tour; a second update re-renders n: n 3, e 2, the rest 1 |
| `test_pf6d_base_from_before_1_4` | pytest | a base stored with no 1.4 key: the update's carried faces answer 1 / the base's `at_seq`, the re-rendered 2 / the update's, no file key invented, no tour |
| `test_pf6d_gc_keeps_named_face_files` | pytest | after a 1.4 panorama the store's `.png` / `.json` keys are exactly its files and `tiles.all_files` names every key; orphan `.png`, `.json`, `.jpg` go after the grace, the named stay; past 90 days all go (a plain panorama) |
| `test_pf6d_echo_1_4` (PF6c's echo test, moved) | pytest | 1.0–1.4 and no header on 5.1–5.6, `/analysis/catalogue`, 5.7 (200 and 204), 5.8, 5.9 (repeat), 5.10, the wind kind's 5.1 and claim, `/v1/jobs` 5.1–5.3 / 5.6 → `render-jobs/1.4`; 2.0 → 400 with `supported` 1.4; `RJ` is what PR5's headset sends |
| `test_pf6d_clients_and_documents_speak_1_4` (PF6c's documents test, moved) | pytest | the four routers on (1, 4) and none on 1.0–1.3, `ECHO`, the wrapper, `jobs.ts` (header, `JobRecord`'s 1.3 keys, the 1.4 keys on `TileFace` / `TileManifest`), the three demos, `export_openapi.py`, `openapi/v1.json` (every jobs operation 1.4, document ≥ 1.4.0, the `Job` keys, `JobTrigger`), both SDKs, PF11c's label and demo flags, `demo_render.py output` printing `version` and `tour`; this doc names app `main` `2c842b8f1` and the contract's blob |
| `test_pf6d_worker_uploads_face_files` | pytest | the wrapper (headers `render-jobs/1.4`) and the fake app with `FAKE_TRUEBEX_FACE_FILES=1`: the panorama's every face has its three files written and served (a 256 px 16-bit depth PNG, a `truebex-ids/1` JSON), version 1, a three-node tour; after an edit the update's 13 re-rendered faces answer version 2 with new depth files written, the 5 carried keep the base's keys, the tour carried and not written again |
| `test_pf6d_cdn_holds_the_same_keys` | pytest | an S3 bucket (moto) with `CDN_BASE_URL`: `publish_tiles` puts `tiles/<sha>.png` / `.json` / `.jpg` with their media type and the immutable cache; `tiles_base()` is the CDN's `/tiles` and each object's public URL is `tiles_base/<sha>.<ext>`; the API's `/tiles/<sha>.png` redirects there |
| PF6's, PF6a's, PF6b's, PF6c's, PF11b's, PF11c's, PF12's, PF12a's, PF10's, PF14f's suites, `test_analysis.py`, `test_mobile.py`, the share tests, `test_uploads.py` | pytest | green with the moved assertions (As-built) |
| `npm run lint`, `npm run build`; `export_openapi.py --v1 --check`, `--clients --check`, `sdks/generate.py --check` | build check | green / current |

## Human test

About 5 minutes, on this PC, against a local API with the fake render worker (no GPU). Three PowerShell windows; `<WT>` = this worktree (`X:\Truebex-autopilot\t102-pf6d-the-render-service-follows`).

1. **API (window A).** `cd <WT>\server`, then `.venv/Scripts/python.exe scripts/make_signing_key.py --kind lic` and copy the value after `LICENCE_SIGNING_KEY=` into:
   `Set-Content .env -Encoding ascii -Value 'DATABASE_URL=sqlite:///./pf6d-human.db','SECRET_KEY=pf6d-human-test-0123456789abcdef0123456789abcdef','API_URL=http://127.0.0.1:8000','LICENCE_SIGNING_KEY=<paste>','LICENCE_KEY_ID=lic-2026-10'`
   then `.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` → "Uvicorn running on http://127.0.0.1:8000".
2. **Account, device and worker (window B, `cd <WT>\server`).**
   `$S = (Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/register -ContentType 'application/json' -Body '{"email":"pf6d@example.com","password":"pf6d-password"}').access_token`
   `.venv/Scripts/python.exe -m app.admin_cli pf6d@example.com` → "pf6d@example.com: admin on".
   `.venv/Scripts/python.exe scripts/demo_replica.py login --email pf6d@example.com --password pf6d-password --trial` → "Pro trial started" and "device token: tbx_dev_…"; set `$D = '<that token>'`.
   `$W = (Invoke-RestMethod -Method Post http://127.0.0.1:8000/admin/workers -Headers @{Authorization="Bearer $S"} -ContentType 'application/json' -Body '{"name":"pc-local","kinds":["panorama","tiles","pack"],"class":"gpu-std"}').token`
   `$T = "$env:TEMP/pf6d-worker.toml"`
   ``Set-Content $T -Encoding ascii -Value 'api = "http://127.0.0.1:8000"',"token = `"$W`"",'worker_id = "pc-local"','kinds = ["panorama", "tiles", "pack"]','class = "gpu-std"',"app = '$((Get-Location).Path)/../worker/tests/fake_truebex.py'",'app_version = "1.1.0"','doc_version_max = 55',"work_dir = '$env:TEMP/pf6d-jobs'",'keep_work = true','heartbeat_s = 5','wait_s = 2','face_px = 512','tile_px = 256','jpeg_quality = 85'``
   `$env:FAKE_TRUEBEX_FACE_FILES = '1'` (the fake app writes the 1.4 files, as CL3's worker will).
3. **A project and a followed set.** `.venv/Scripts/python.exe scripts/demo_replica.py --token $D push` → "pushed: 12 accepted" and "project id: …"; set `$P = '<that id>'`. `.venv/Scripts/python.exe scripts/demo_render.py --token $D submit --project $P --follow` → "job id: …"; set `$SET = '<that id>'`.
4. **The first picture.** `.venv/Scripts/python.exe ../worker/truebex_worker.py --config $T --once` → "complete <SET>: 18 faces rendered, 145 files sent". `.venv/Scripts/python.exe scripts/demo_render.py --token $D output --job $SET` → a `tour:` hash and, under each of the three views (bedroom, entry, living), six faces "version 1, op_seq 12, full; id … ids … depth …".
5. **One edit.** `.venv/Scripts/python.exe scripts/demo_replica.py --token $D move --project $P` → "accepted as 13 (head 13)". Run the worker line of step 4 again → "complete <id>: 13 faces rendered, 104 files sent". The `output` line of step 4 → "the manifest of job <that id> at operation 13, 13 faces rendered, 5 carried", the same `tour:`; bedroom: `w` "version 2, op_seq 13, changed" with new hashes, its other five "version 1, op_seq 12, carried" with the hashes step 4 printed; entry and living: all six "version 2, op_seq 13, light".
6. **The files from tiles_base (curl).**
   `$M = Invoke-RestMethod "http://127.0.0.1:8000/jobs/$SET/output" -Headers @{Authorization="Bearer $D"; "X-Truebex-Contract"="render-jobs/1.4"}; $F = $M.views[0].faces.n; $M.tiles_base`  → `http://127.0.0.1:8000/tiles`.
   `curl.exe -s -D - -o "$env:TEMP/pf6d-depth.png" "$($M.tiles_base)/$($F.depth).png"` → `HTTP/1.1 200 OK`, `content-type: image/png`, `cache-control: public, max-age=31536000, immutable`, `access-control-allow-origin: *` (the file is a 256 x 256 grey PNG; any image viewer shows a dark ramp).
   `curl.exe -s "$($M.tiles_base)/$($F.ids).json"` → `{"schema":"truebex-ids/1","ids":[null,"…32 hex…",…]}`.
   `curl.exe -s "$($M.tiles_base)/$($M.tour).json"` → `{"format": "truebex-tour/1", "start": "node-0", "nodes": [… "view": "ecaf16d7…" …, … "8388104c…" …, … "aee49319…" …], "links": […]}`.
   `curl.exe -s -D - -o NUL "http://127.0.0.1:8000/jobs/usage" -H "Authorization: Bearer $D" -H "X-Truebex-Contract: render-jobs/1.3"` → `x-truebex-contract: render-jobs/1.4` (a 1.3 client is still served).
7. **A 1.3 worker (no pick files).** `Remove-Item Env:FAKE_TRUEBEX_FACE_FILES`, then the `move` line of step 5 and the worker line of step 4 → "accepted as 14", "complete …: 13 faces rendered". The `output` line → bedroom `w` "version 3, op_seq 14, changed; no pick files", entry and living "version 3, op_seq 14, light; no pick files", the five carried bedroom faces still "version 1, op_seq 12" with their hashes: the server counts versions even when the worker sends none.
8. **The site (window C, `cd <WT>`).** `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → "serving … on http://127.0.0.1:…/" (use the port it prints). Open `/developers/sdks/`: the install lines read "version 1.4.0". No other page changed.
9. **Clean up.** Stop uvicorn and the server (Ctrl+C), then delete `server\.env`, `server\pf6d-human.db`, `server\storage`, `$env:TEMP\pf6d-jobs`, `$env:TEMP\pf6d-depth.png` and `$env:TEMP\pf6d-worker.toml`.
10. **Optional, the owner's:** once CL3's worker writes the 1.4 files, run the headset app's PC host (`-mwvrapp`) signed in against a local API: the tour opens on the platform's set, the pointer names the wall it is on, and an edit from the desktop refreshes only the faces it re-rendered.

## Risks / traps

* **Two writers of `version`.** The server is the authority; a worker that counts differently is refused, not corrected. A worker that cannot know the base's numbers sends none.
* **The headset's stub writes ID / depth at `StubIdPx` (256) while its `levels[0]` is 1024**, against the contract's "at `levels[0]` px". The platform follows the contract; a worker written after the stub would be refused with `id` / `depth` "… of 1024 x 1024 px". PATCH line A asks the app half to settle it.
* **`truebex-tour/1`'s key is `format`** (PR3 §Data; `FVrTour::FromJson`), not `schema` as in `truebex-ids/1`: a tour with `schema` is refused (the headset would fall back to a tour from the views).
* **Order trap:** `test_uploads.py` before a render test in a hand-picked list leaves its worker resolver installed ("This worker token is not valid"); alphabetical order never hits it.
* **Escapes:** a heredoc collapsed `\x89PNG…` into raw bytes in `tiles.py` once; the PNG signature is written `bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])` and every written file was scanned for control bytes.

## As-built

**2026-11-09, Autopilot T102, branch `ap/t102-pf6d-the-render-service-follows`** (base `master` 61ac33a). Commits: 454c2b2 (the tests first), 400784c (check, store, serve, carry and collect), 599df72 (render-jobs/1.4 everywhere, the documents and SDKs), 1f7335d (the doc, README, tracker row, PF6c's carry-over line), then this gate line.

* **The app commit, and why the snapshot.** PR5 is on the app's GitHub `main` `2c842b8f1f237027cda897ed53d09b4739fca1e0` (merge T214, 2026-11-09T14:32:07Z, run on the app's cloud runner); the PC's checkout `T:/unreal5_7_4_projects/truebex_compact` is still at `37d98cec` (render-jobs 1.3.0) and was neither fetched nor written. Every app file was read from the manager's export `X:/Truebex/.autopilot/manager/app-main-2c842b8f/` (`git archive`, LF, each blob id in its `SNAPSHOT.txt`): `render-jobs.md` blob `6a47207a`, PR5's doc `92807b4c`, `VrSession.cpp` `5017eacf`, `VrTour.cpp` `76a04592`, `VrStubBackend.cpp` `69cf7513`, `VrHttpBackend.cpp` `b0f795c2`, `CadVrEdits.cpp` `a5c89338`. PR3's tour format (`format`) was read in the PC's checkout (unchanged by PR5). The render-jobs fixture folder did not change (tree `0d5ce75d` on both mains): nothing re-copied, no pin moved; no test reads the app through git.
* **Counts:** pytest 983 → 992 collected: 11 in `test_pf6d_render_jobs_1_4.py` (2 of them PF6c's, moved). On 61ac33a all 11 failed: `tiles/<sha>.png` not stored (the served test), the first broken output accepted (200), `check_manifest` naming nothing, no `version` / `op_seq` (3 tests), the GC naming no `.png` / `.json`, the echo `render-jobs/1.3`, the routers on (1, 3), `tile_key()` taking no extension (CDN), the fake app writing no files (worker).
* **The checks:** as Design; the decision on decoding: **the id PNG is not decoded** (the signature and IHDR only, 33 bytes): so "its largest index < `len(ids)`" is not checked (the headset's `DecodePick` reads an index past `ids` as no entity). `id` and `ids` must come together (`ids` is `id`'s table); `depth` may come alone. Null is refused for every new key (the contract's keys are optional: absent, not null).
* **The store layout:** one key per extension: `tiles/<sha256>.jpg` (colour), `.png` (`id`, `depth`), `.json` (`ids`, `tour`); `tile_key(sha, ext="jpg")`, `MEDIA_TYPES`; the router and the collector match `(jpg|png|json)`; `publish_tiles` takes blobs by store key and puts each with its media type.
* **Who fills `version` and `op_seq`: the server** (the favoured option): computed from the base manifest and the job, filled when omitted, a disagreeing value refused (422 `version` / `op_seq`). A carried face also gets the base's `id` / `ids` / `depth` when it omits them, and an update with no `tour` keeps the base's. A 1.3 manifest is therefore answered as sent **plus** `version` and `op_seq` on each face (never a null, never a file key it did not send): that is what lets the headset refresh re-rendered faces with today's worker (human test step 7).
* **The `/v1` and mobile decision:** **not named in this task.** `routers/v1/models.py` `TileFace` / `TileManifest` and `mobile/clients.py` `TileFace` / `TileManifest` (both `extra="allow"`, and `/v1`'s `doc()` documents rather than validates) are unchanged, so `openapi/v1.json` and `openapi/clients.json` gained no schema; the reads pass the stored keys through (tested on `/v1`'s panorama read, `/v1/jobs/{id}/output`, the members' read and the live share). The headset reads 5.5.
* **Assertions moved (1.4 only):** `render_helpers.py` and `pf12_helpers.py` `RJ` → `render-jobs/1.4` (what PR5's headset sends; CL4's 1.3 stays served); `test_render.py::test_contract_header_and_error_envelope` the echo and `supported` 1.4; `test_pf6b_claim_long_poll.py::test_claim_long_poll_woken_by_a_submit` the 204's echo 1.4; `test_pf12_api.py` `/v1/jobs` 5.1's echo 1.4; `test_pf11b_ai_proxy_1_1.py::test_pf11b_no_route_or_script_left_on_1_0` `demo_analysis.py` on 1.4; `test_pf11c_render_jobs_1_2.py` `ECHO` 1.4 (`RJ12` kept, AN3's 1.2 still served); `test_pf6a_render_jobs_1_1.py`: `ECHO` 1.4; `test_pf6a_no_router_or_client_left_on_1_0` the routers on (1, 4), the wrapper, `jobs.ts`, `demo_render.py`, both SDKs' counts and the README header on 1.4; `test_pf6a_followed_panorama_and_update_with_the_apps_manifests` compares its five view lists (5.5, the claim's base manifest, the update's 5.5, `/s/{slug}/live`, `/v1`'s read) through `as_sent` (without the `version` / `op_seq` the platform adds). **PF6c's two tests moved** to `test_pf6d_render_jobs_1_4.py`: `test_pf6c_echo_1_3` → `test_pf6d_echo_1_4` (`ECHO` 1.4, `SENT` adds 1.4: six versions, six claims), `test_pf6c_clients_and_documents_speak_1_3` → `test_pf6d_clients_and_documents_speak_1_4`: the four routers on (1, 4) (was (1, 3) and not (1, 2)), `ECHO` 1.4, the wrapper's `CONTRACT` 1.4, `jobs.ts`'s header 1.4, the three demos on 1.4 and none on 1.0–1.3, `export_openapi.py`'s `"jobs"` 1.4, every `/v1/jobs` operation 1.4, the document ≥ 1.4.0 (was ≥ 1.3.0), both SDKs' 1.4 count and no 1.0–1.3; kept as they were: `JobRecord`'s three 1.3 keys, `JobKind` airflow, the admin page, `Job`'s keys and descriptions, `JobTrigger`, PF11c's label and demo flags, `demo_render.py`'s `show` / `output`; added: `TileFace` / `TileManifest`'s 1.4 keys, `output` printing `version` / `tour`, this doc's pins. `test_pf6c_render_jobs_1_3.py` lost `ECHO`, `SENT`, `_versions` and five imports. Setup only: none.
* **The documents:** `openapi/v1.json` 1.4.0 (only `info.version` and the six `x-truebex-contract` values changed), the SDKs 1.4.0 regenerated by `scripts/gen-sdks.ps1` (its pinned generators installed into `.sdk-tools/`; the generated diff is the six contract strings), `export_openapi.py --v1 --check`, `--clients --check` and `sdks/generate.py --check` clean.
* **Postgres 17** (a throwaway cluster, `timezone = 'Asia/Baghdad'`, two database pairs): `test_pf6a_render_jobs_1_1`, `test_pf6a_render_worker`, `test_pf6c`, `test_pf6d`, `test_pf12a_v1_panoramas`, `test_pf12_api` (57 passed, 1 skipped: no `out/`) and `test_mobile`, `test_pf6b`, `test_render`, `test_render_shares`, `test_render_worker`, `test_uploads` (67 passed); the 2 failures there were the README / doc checks before this doc existed, green on re-run (the gate line below). SQLite: those files plus PF11b, PF11c, PF10, PF12 SDKs, PF14e/f/g, the meets and the share suites: 307 passed, 5 skipped before the doc.
* **Live run** (a local API on :28102, `demo_replica.py login --trial`, the real wrapper and the fake app with `FAKE_TRUEBEX_FACE_FILES=1`; abridged):

  ```
  panorama job queued at operation 12: estimate 4.5 cu        job id: 5359f8ce6f62263cead21985feeb2785
  complete 5359f8ce…: 18 faces rendered, 145 files sent, 0.2 s, 0.1 cu      (90 tiles + 54 face files + the tour)
  5.5 on 5359f8ce…: the manifest of job 5359f8ce… at operation 12, 18 faces rendered, 0 carried
    tour: 08514237f17da719b7c56e9f32403d60a4290e682a1bac6dc1b514ccfdefef08
    view ecaf16d70fa5862cbba8f2288b9fd593 (bedroom):
      n: version 1, op_seq 12, full; id bc02698dfa62 ids 06401a3f8b00 depth d580b9cc6330
      w: version 1, op_seq 12, full; id a0c326e74ce0 ids d2561f992d58 depth d08b4af61275
  accepted as 13 (head 13)
  f2b24fb9…  tiles  queued  rev 1  at 13  base_job_id 5359f8ce…, trigger 1 op(s) 13-13
  complete f2b24fb9…: 13 faces rendered, 104 files sent, 0.2 s, 0.1 cu     (65 tiles + 39 face files; the tour not re-sent)
  5.5 on 5359f8ce…: the manifest of job f2b24fb9… at operation 13, 13 faces rendered, 5 carried
    tour: 08514237…   (the same)
    view ecaf16d7… (bedroom):
      n: version 1, op_seq 12, carried; id bc02698dfa62 ids 06401a3f8b00 depth d580b9cc6330
      w: version 2, op_seq 13, changed; id 37ac5e7ee5d0 ids 69133b05e0bf depth 01686ada2a86
    view 8388104c… (entry): n: version 2, op_seq 13, light; id 2f63a3ae38fa ids 534adff1ee31 depth 28d82e051bc7 (all six 2 / 13)
  curl GET /jobs/5359f8ce…/output (render-jobs/1.4)       -> HTTP/1.1 200 OK, x-truebex-contract: render-jobs/1.4
     "n": {"rendered": false, "reason": "carried", "id": "bc02698d…", "ids": "06401a3f…", "depth": "d580b9cc…", "version": 1, "op_seq": 12}
  curl <tiles_base>/d580b9cc….png  -> HTTP/1.1 200 OK, cache-control: public, max-age=31536000, immutable,
                                      access-control-allow-origin: *, content-type: image/png; 878 bytes, sha256 ok, IHDR (256, 256, 16, 0)
  curl <tiles_base>/06401a3f….json -> HTTP/1.1 200 OK, (the same cache and origin), content-type: application/json
     {"schema":"truebex-ids/1","ids":[null,"a0bd8f8d7fca8ef893aafc2b0c46a6ec","a84df40c…","2e5a05df…","0bbab26f…","a595d1aa…","563a22e7…"]}
  curl <tiles_base>/08514237….json -> {"format": "truebex-tour/1", "start": "node-0", "nodes": [{"id": "node-0", "title": "bedroom",
     "view": "ecaf16d7…"}, {"id": "node-1", "title": "entry", "view": "8388104c…"}, {"id": "node-2", "title": "living",
     "view": "aee49319…"}], "links": [{"from": "node-0", "to": "node-1", "auto": true}, {"from": "node-1", "to": "node-2", "auto": true}]}
  uvicorn log: no error
  ```

* **Contract, for the app half** (the app's docs are read-only here; the owner applies them at merge). §11, the platform cell of the 1.4 row `GET /jobs/{job_id}/output` *(1.4: …)*: "PF6: not yet" → "**PF6: done (PF6d)** 2026-11-09: checked on 5.9, stored as `tiles/<sha256>.png` / `.json` beside the tiles, served from `tiles_base`, kept on carried faces, `version` / `op_seq` counted by the platform (`test_pf6d_face_files_checked_stored_and_served`, `test_pf6d_output_invalid_face_files`, `test_pf6d_follow_set_versions_and_carried_faces`)"; the header's status gains "PF6d". Proposed lines (1.4.1, PATCH unless noted):
  * **A. §6.2's table lists the 1.4 fields itself** (today only the *Changes* line has them): a face's `id`, `ids`, `depth` (each optional; `id` and `ids` together), `version`, `op_seq`, and the top-level `tour`, with the formats, and that the platform fills `tiles_base` for them too.
  * **B. Who counts `version` / `op_seq`:** the platform (1 on a panorama, the base face's + 1 on a re-render, the job's `at_seq`; a carried face the base's); a worker may send them and must agree; 5.5 always answers them.
  * **C. The ID / depth size:** the contract says `levels[0]` px, but the headset stub writes them at `cad.VrApp.StubIdPx` (256) beside `levels` [1024, 2048]. Either the stub writes them at `levels[0]` or the contract says "square, any size" (the headset's decoders take any square); the platform checks `levels[0]` until the app decides.
  * **D. §6.1 for CL3's worker (PR5's carry-over):** the renderer writes a face's files beside its tiles, `out_dir/tiles/<sha256>.png` (`id` 8-bit grey, `depth` 16-bit grey, at `levels[0]` px) and `out_dir/tiles/<sha256>.json` (`ids`), and the tour as `out_dir/tiles/<sha256>.json` (may be omitted on a `tiles` job whose tour is the base's); a carried face copies the base face's keys. The wrapper (PF6d) uploads exactly those.
  * **E.** `truebex-tour/1`'s format key is `format` (PR3), every node's `view` a view of the manifest; `ids` lists at most 256 entries, `ids[0]` null; a new key is never null (absent instead).
* **Carry-over:** CL3's worker writing the 1.4 files (D) → the app half; the headset's device run and APK → the owner (GD4); the RTX PC's worker update to `render-jobs/1.4` and the first live set → the owner at deploy; the web viewer, share page and Android picking → not planned (a PF9 / PF10 follow-up if wanted); lines A–E → the app half.
* **Verify gate** (`scripts\autopilot-verify.ps1`, absolute `-File`): green in 676 s (lint, the build compiled in 14.5 s, 75 pages; pytest 561 s): 992 collected, 973 passed + 19 skipped. The served build's `/developers/sdks/` reads "version 1.4.0".
