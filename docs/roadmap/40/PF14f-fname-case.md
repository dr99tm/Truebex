# PF14f — The platform reads the app's FName-written enum values without case (launch priority 2)

**Needs merged:** PF4b, PF6, PF11c, PF14d (all on `master` 96b79a8). **Unblocks:** a Shipping build's sync push, cloud panorama (and its Unfollow), comment resolve, invite, role change and update check against the live API; PF11c's carry-over "PF6's owner: the render kinds still compare `kind` and `quality` exactly". **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\render-jobs.md` 1.2.0 (5.1, 5.3), `project-log.md` 1.2.0 (5.6, 5.14, 5.15, 5.21), `licence-api.md` (5.13). No version moves: accepting more spellings is additive and every answer keeps the contract's lower-case spelling. The PATCH lines for the app side are in the As-built.

## Status

**Built (2026-10-25, branch `ap/t98-pf14f-the-platform-reads-the-app`, Autopilot T98); see As-built.** Checked on `master` 96b79a8 before the work began:

| # | Where (master 96b79a8) | Before |
|---|---|---|
| 1 | `server/app/render/service.py:160` | `quotas.KINDS.get(kind_name)`: `Panorama` → 422 `kind` (the analysis kinds go to `app.analysis` first and already matched without case, PF11c) |
| 2 | `service.py:171-172` | `body.get("quality") or "standard"`, then exact `in QUALITIES`: `High` → 422; `[]` and `""` were read as "not sent" (standard) |
| 3 | `service.py:304`, `:313`, `:315` (`list_jobs`) | `state` exact (`Queued` → 422); `kind` filtered exactly (`Tiles` lists nothing) |
| 4 | `server/app/projects/ops.py:175`, `:177`, `:192`, `:195`, `:222` | `author_kind not in ("person", "agent")`, the person/author check, `op.kind not in KINDS` and every later `op.kind` comparison: `Delta` / `Person` → 422 |
| 5 | `server/app/routers/v1/projects.py:100` (`_as_agent`) | a key's `author_kind` exact: `Agent` → 422 |
| 6 | `server/app/projects/comments.py:308` | `body.state not in STATES`: `Resolved` → 422 |
| 7 | `server/app/projects/members.py:98` (`_role`, invite and PATCH) | `value not in INVITE_ROLES`: `Editor` → 422 |
| 8 | `server/app/routers/releases.py:17`, `:22` | `channel: Literal["stable", "beta"]`: `Stable` → 422 (found by the audit, Scope 5) |

## Goal

A packaged (Shipping or Game) build of the app can sync, render a cloud panorama, resolve a comment, invite someone and check for updates against the platform. In such a build Unreal 5.7 does not keep an FName's case (`Engine/Source/Runtime/Core/Public/UObject/NameTypes.h:33`: `WITH_CASE_PRESERVING_NAME` is `WITH_EDITORONLY_DATA`), so `FName(TEXT("high")).ToString()` answers whichever spelling the global name table registered first: `Editor`, `Object`, `Team`, `High`, `Warning` are the engine's own (`UnrealNames.inl:48`, `:110`, `:190`, `:192`, `:255`), `Resolved`, `Delta`, `Action` are reflected engine members. The app's suites run with editor binaries and never see it. The platform reads each such value without case, stores and answers the contract's spelling, and still refuses anything else.

## Read first

* `docs/roadmap/40/00-contract.md` (P.2-P.4); `PF14d-telemetry-fixtures-from-op1.md` (As-built change 2, PATCH line A: the precedent); `PF11c-render-jobs-1-2-0.md` (deviation 11, Carry-over "PF6's owner").
* The contracts above; the app's senders (app `main` bc06615c6, read-only): `Plugins/CADTOOL/Source/TruebexSync/Private/RenderJobsClient.cpp`, `CadCore/Private/CadProjectLog.cpp`, `TruebexSync/Private/SyncCollab.cpp`, `SyncClient.cpp`, `CloudPano.cpp`, `TruebexUpdate/Private/TruebexUpdater.cpp`.
* `server/app/render/service.py`, `server/app/projects/{ops,comments,members}.py`, `server/app/routers/releases.py`, `server/app/routers/v1/projects.py`.

## Scope

**In:**

1. `server/app/enums.py`: `canonical(value, allowed)` maps a str to its spelling in `allowed`, matched without (ASCII) case, and answers None for anything else (None, numbers, booleans, lists, objects, unknown words, non-ASCII text). Error messages keep naming the canonical spellings.
2. Render kinds: `kind` and `quality` of POST `/jobs` and `/v1/jobs` (the same `service.submit`) in any case; the row, 5.2, 5.3, the claim and the webhooks carry the canonical spelling; follow, tiles and pack see the canonical kind. 5.3's `kind` and `state` filters (`GET /jobs`, `/v1/jobs`) match without case.
3. Project log: an operation's `kind` and `author_kind` in any case, stored canonical, so pulls, the ops webhook's authors, the conflict check's restore filter and the person/author check work. `restore` stays refused from a client in any case. The `/v1` push's agent check the same.
4. Comments and members: a comment PATCH's `state`, an invitation's and a member PATCH's `role` in any case, stored canonical; `owner` stays refused in any case.
5. The audit of every value the app writes from an FName to a platform route (As-built table), each contract route fixed the same way (the release feed's `channel` was the one more), the rest recorded.
6. `server/scripts/demo_fname_case.py`: the human test's run (each spelling a Shipping build may send, and the words that are none, with the answers checked).

**Out (and where it goes):**

* The app's own fix (writing these values from string literals, not `FName::ToString`): the app half, through the PATCH lines in the As-built.
* Telemetry (PF14d) and the analysis kinds (PF11c): done there; untouched.
* The SDKs and the `/v1` documentation: they already send lower case, and no schema enum blocks a mixed-case value at validation (the `/v1` job and push bodies are read raw; the member and comment bodies inherit `str` fields). No change.
* The billing page's `?plan=` (the app's upgrade link, `CadEntitlement.cpp:831`): a web page, not a contract route; recorded (Carry-over).
* A packaged-build run against the live API: the owner's (Human test, optional step).

## Design

**API.** No new endpoint, no shape change. Each check reads the value through `enums.canonical` and goes on with the canonical spelling:

| Route | Field | Allowed (canonical) | Not one of them |
|---|---|---|---|
| POST `/jobs`, `/v1/jobs` (5.1) | `kind` | `quotas.KINDS` (panorama, tiles, pack and the analysis kinds, which `app.analysis` reads first) | 422 `kind: one of panorama, tiles, pack, …` |
| POST `/jobs`, `/v1/jobs` (5.1) | `quality` | draft, standard, high; null or absent = standard | 422 `quality: one of draft, standard, high` (now also `[]` and `""`, like the analysis kinds' `quality_of`) |
| GET `/jobs`, `/v1/jobs` (5.3) | `state` | the seven job states | 422 `state: one of …` |
| GET `/jobs`, `/v1/jobs` (5.3) | `kind` | `quotas.CONTRACT_KINDS` | listed as given (nothing matches, as before) |
| POST `/projects/{id}/ops`, `/v1/…/ops` (5.6) | `ops[].kind` | delta, action | 422 `ops[i].kind: delta or action (restore is appended by the server)` |
| the same | `ops[].author_kind` | person, agent (a key: agent only) | 422 `ops[i].author_kind: person or agent` |
| PATCH `/projects/{id}/comments/{cid}`, `/v1/…` (5.21) | `state` | open, resolved | 422 `state: open or resolved` |
| POST, PATCH `/projects/{id}/members…`, `/v1/…` (5.14, 5.15) | `role` | editor, viewer | 422 `role: editor or viewer.` (owner too) |
| GET `/releases/feed` (licence-api 5.13) | `channel` | stable, beta; absent = stable | 422 `channel: stable or beta.` (`in: query`) |

ASCII case only: `str.lower()` would also turn the Kelvin sign into "k" (`"pac\u212a".lower() == "pack"`), which no client means.

**Data.** None: rows were always written with the canonical spelling (a mixed-case value never got in), so no migration and no clean-up.

**UI, jobs, security.** None. The change only widens what is accepted; every refusal stays a 422 with the same field.

## Deliverables

- [x] `server/app/enums.py` (`canonical`)
- [x] `server/app/render/service.py` (`submit`, `list_jobs`), `server/app/projects/{ops,comments,members}.py`, `server/app/routers/releases.py`, `server/app/routers/v1/projects.py` (`_as_agent`)
- [x] `server/tests/test_pf14f_fname_case.py` (10 tests)
- [x] `server/scripts/demo_fname_case.py` (the human test's run)
- [x] This doc; the PF14f tracker row; `README.md` (one section at the end); PF11c's carry-over pointed here

## Tests

| Name | Kind | Asserts | On master 96b79a8 |
|---|---|---|---|
| `test_pf14f_canonical_spelling` | pytest | `High` / `HIGH` / `sTaNdArD` → canonical; the tuple's spelling wins (`lit` → `Lit`); None, 7, 7.0, True, `[]`, `["high"]`, `{}`, `""`, padded or longer words → None; the Kelvin sign and the dotted capital I → None | failed (ImportError: no `app.enums`) |
| `test_pf14f_render_kind_and_quality_any_case` | pytest | POST `/jobs` `Panorama` / `High` → 201 `panorama` / `high` in the answer, 5.2, the list and the row; `PANORAMA` / `Draft` with the lower-case spelling's estimate; `STANDARD`; `follow` with `Panorama`; `Pack` with its items; `Panoramas` and `Ultra` → 422 naming the kinds / qualities; `follow` on `Pack` → 422 `follow` | failed (`Panorama` 422) |
| `test_pf14f_followed_set_and_list_filters_any_case` | pytest | the app's cloud panorama: a followed `Panorama` / `High` set claimed (`c.job` `panorama` / `high`), finished, `job.succeeded` webhook `panorama` / `high`; after a push, `GET /jobs?kind=Tiles&state=Queued` lists the set's queued tiles job (`TILES`, `QUEUED`, `Running`, `Panorama&Succeeded` too); `Tile` lists nothing; `Waiting` → 422; a client's `TILES` job against the set joins the queued one | failed (`Panorama` 422; with lower-case submits, `state=Queued` 422 and `kind=Tiles` 0 jobs, checked separately) |
| `test_pf14f_v1_jobs_any_case` | pytest | an API key: `Pack` and `Panorama` / `High` → 201 canonical, 5.2 the same; `GET /v1/jobs?kind=PACK&state=Queued`; `Panoramas` and `state=Done` → 422 | failed (`Pack` 422) |
| `test_pf14f_project_log_kind_and_author_kind_any_case` | pytest | `Delta` / `Person`, `Action` / `PERSON` (a log-safe `move`), `Agent`, a key's `AGENT` accepted; pull and the rows answer `delta` / `action`, `person` / `agent`; the `project.ops_appended` webhook's authors `person`; `Person` with another author → 422 `author`; `restore`, `Restore`, `RESTORE`, `Deltas` → 422 `kind`; `Robot` → 422; a key's `Person` → 422 | failed (`Person` 422) |
| `test_pf14f_comment_state_any_case` | pytest | `Resolved` → resolved (row, `resolved_by`, `resolved_at`, the `state=resolved` list); `Open` reopens; `RESOLVED` with text; `Closed`, `deleted`, `Deleted`, `all` → 422 | failed (`Resolved` 422) |
| `test_pf14f_member_role_any_case` | pytest | an invitation `Editor` accepted as an editor; PATCH `Viewer`, `EDITOR`; invitation `VIEWER`; `/v1` `Editor` and PATCH `Viewer`; `owner`, `Owner`, `OWNER`, `Admin` → 422 on both; the owner's own role → 422 | failed (`Editor` 422) |
| `test_pf14f_release_feed_channel_any_case` | pytest | `Stable`, `STABLE`, `Beta`, `bEtA` → 200 with `channel` canonical and the channel's releases; absent → stable; `nightly`, `Nightly`, `""` → 422 `channel` | failed (`Stable` 422) |
| `test_pf14f_wrong_types_answer_422` | pytest | None, 7, `[]` (and an object, True) in `kind`; 7, `[]`, `""`, `["high"]`, True in `quality` (null = standard); None, 7, `[]` in `ops[].kind`, `ops[].author_kind`, a comment's `state` and an invitation's and a PATCH's `role` → 422 naming the field, never 500 | failed (`quality: []` → 201) |
| `test_pf14f_demo_script_human_test_path` | pytest | `scripts/demo_fname_case.py` in-process (requests routed into the API) after `demo_replica.py login --trial`: exit 0, "13 of 13 answers as expected", one job `panorama` / `high` stored | failed (no script) |
| the 16 suites the task names, plus `test_releases.py`, `test_licence.py`, `test_pf12_webhooks.py`, `test_pf12_openapi_sdks.py` | pytest | unchanged | — (green after, no assertion moved) |
| `npm run lint`, `npm run build`, whole `pytest` | verify gate | green | — |

## Human test

About 5 minutes, local API only (no page changed in this feature, so `scripts\autopilot-serve.ps1` is not needed). Windows PowerShell, from the worktree root (`X:\Truebex-autopilot\t98-pf14f-the-platform-reads-the-app`):

1. Window 1, start a local API with a licence signing key (for the trial) and a fresh database:
   ```powershell
   cd server
   $k = .venv\Scripts\python.exe scripts\make_signing_key.py --kind lic
   $env:LICENCE_SIGNING_KEY = ($k | Select-String '^LICENCE_SIGNING_KEY=').Line.Substring(20)
   $env:LICENCE_KEY_ID = 'lic-2026-10'
   $env:DATABASE_URL = 'sqlite:///./pf14f-human.db'
   $env:STORAGE_DIR = './pf14f-human-storage'
   $env:MAIL_BACKEND = 'console'
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
   → `Uvicorn running on http://127.0.0.1:8000`.
2. Window 2 (worktree root), an account with a device and the Pro trial:
   ```powershell
   cd server
   Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/register -ContentType 'application/json' -Body '{"email":"ana@example.com","password":"correct-horse-9"}' | Out-Null
   $out = .venv\Scripts\python.exe scripts\demo_replica.py login --email ana@example.com --password correct-horse-9 --trial
   $out; $t = ($out | Select-String 'device token: ').Line.Substring(14)
   ```
   → `Pro trial started …`, `plan pro, author_id …`, the device token.
3. `.venv\Scripts\python.exe scripts\demo_fname_case.py --token $t` → 13 lines ending `-- ok`, among them `push kind "Delta", author_kind "Person": 200 accepted as 1`, `pull: 200 kind delta, author_kind person`, `comment PATCH state "Resolved": 200 state resolved, resolved_by 1`, `POST /jobs kind "Panorama", quality "High": 201 job …, kind panorama, quality high, queued`, `invite role "Editor": 201 sam@example.com editor invited`, `GET /releases/feed?channel=Beta: 200 channel beta`, and the refused words (`Restore`, `Closed`, `Panoramas`, `Owner`) each `422 validation_failed`; the last line reads `13 of 13 answers as expected`. Window 1 prints the invitation mail (`--- mail to sam@example.com: ana invited you to "PF14f spellings" on Truebex`).
4. One call by hand, the app's Unfollow filter: `curl.exe -s "http://127.0.0.1:8000/jobs?kind=Panorama&state=Queued" -H "Authorization: Bearer $t" -H "X-Truebex-Contract: render-jobs/1.2"` → one job with `"kind":"panorama"`, `"state":"queued"`, `"quality":"high"`. In a browser, http://127.0.0.1:8000/releases/feed?channel=Beta → `{"schema":"truebex-releases/1","channel":"beta",…}`.
5. Stop window 1 (Ctrl+C) and delete `server\pf14f-human.db` and `server\pf14f-human-storage`.
6. Optional, the owner's (needs `api.truebex.com` up with this feature deployed): the app's Shipping release signed in against the live API saves a project to the cloud (sync push), adds and resolves a comment, invites someone as an editor, starts and stops a cloud panorama, and checks for updates, with no 422 in the app's log.

## Risks / traps

* **ASCII only.** A non-ASCII spelling is refused, never folded (`"pac\u212a".lower() == "pack"` in Python).
* **`quality` `[]` and `""` now answer 422** (they were read as "not sent"); null still means standard. No client sends them (the app's FName default is `standard`; `NAME_None` would leave as `None`, refused before and after).
* **The 5.3 `kind` filter does not validate:** an unknown kind lists nothing, as before (a 422 there would be a behaviour change for any client).
* **PF6c (render-jobs 1.3.0) touches `service.py` too:** this feature's render change is limited to `submit`'s kind and quality lines, `list_jobs`' filter lines and the import.
* **Merge hygiene:** a new module (`enums.py`), one import line per touched module, a new script and a new test file; the tracker row and the README section at the end.

## As-built

* **Date, branch, commits:** 2026-10-25, `ap/t98-pf14f-the-platform-reads-the-app` (base `master` 96b79a8): `87356d0` (the tests, all failing on master), `aeaad28` (the helper and the checks), `9b459f3` (the demo script and its test), and the docs commit (this doc, the tracker row, README's section, PF11c's carry-over pointer).
* **Counts:** pytest 952 → 962 collected (10 new in `test_pf14f_fname_case.py`, every one failing on master first, each for the reason in the Tests table). No existing assertion moved: none pinned an exact-case refusal (`test_projects.py:738`'s `owner` and `:743`'s `boss` stay 422). The 20 suites above on SQLite: 265 passed + 4 skipped (Postgres-only) in 475 s. Postgres 17 (a throwaway cluster, `timezone = 'Asia/Baghdad'`, `SHOW TimeZone` checked): `test_pf14f_fname_case`, `test_render`, `test_pf6a_render_jobs_1_1`, `test_pf11c_render_jobs_1_2`, `test_releases` 79 passed; `test_projects`, `test_projects_orgs`, `test_pf4a_project_log_1_1`, `test_pf4b_project_log_1_2`, `test_pf12_api`, `test_licence` 94 passed; 0 failed. Verify gate: the last bullet.
* **The helper:** `server/app/enums.py` `canonical(value, allowed) -> str | None` (26 lines): a str that is ASCII, lower-cased and compared with each allowed word lower-cased; the allowed word's own spelling is answered. Used at `render/service.py:162` (kind), `:174` (quality), `:309` (5.3 state), `:316` (5.3 kind); `projects/ops.py:179` (author_kind), `:197` (kind; `ParsedOp` carries both); `routers/v1/projects.py:99` (a key's author_kind); `projects/comments.py:310` (state); `projects/members.py:101` (role); `routers/releases.py:26` (channel). PF14d's telemetry (`scanner.canonical_enum`, `service.allowed_index`) and PF11c's analysis kinds (`analysis/kinds.py` `name_of`, `quality_of`, `_choice`, Unicode `lower()`) are left as they are (Scope Out).
* **Live run** (uvicorn on scratch SQLite, a fresh licence key, `demo_replica.py login --trial`; port 18098; `demo_replica.py push` of the app's fixture project first, then a scratch script): push `{"head_seq":13,"results":[{"op_id":"ca832f2db783a2903cdee6e5d5d61fb0","status":"accepted","server_seq":13}]}` for `kind` `Delta`, `author_kind` `Person`; pull `{"server_seq":13,"op_id":"ca832f2db783a2903cdee6e5d5d61fb0","kind":"delta","author_kind":"person","author":"01a172d0c49d7f479f1de71efec26440","delta_format":"o5/55"}`; `Restore` and `Deltas` 422 `ops[0].kind: delta or action (restore is appended by the server)`; comment 201 `{"comment_id":"01a172d0e7037248ba26ae84865cd6ad","state":"open"}`, PATCH `Resolved` 200 `{"state":"resolved","resolved_by":1,"resolved_at":"2026-10-25T11:27:36Z"}`, `Open` 200 `{"state":"open","resolved_by":null,"resolved_at":null}`, `Closed` 422 `state: open or resolved`; POST `/jobs` `Panorama` / `High` 201 `{"job_id":"d4b73a40fabc88b11526cd33e3d56c33","kind":"panorama","quality":"high","state":"queued","class":"gpu-std","cost_units_estimate":12.0}`, 5.2 the same, `GET /jobs?kind=Panorama&state=Queued` 200 with that job, `Panoramas` 422 `kind: one of panorama, tiles, pack, wind, energy, acoustics, airflow`; invite `Editor` 201 `{"email":"sam@example.com","role":"editor","state":"invited"}` (the mail went out), `Owner` 422 `role: editor or viewer.`; `/releases/feed?channel=Beta` 200 `{"channel":"beta","platform":"win64","latest":null}`. Then `scripts/demo_fname_case.py` against a live API from `git archive 96b79a8 server` (master): **4 of 12** answers as expected (every Shipping spelling 422, only the four refusals as they should be; 5.2 skipped, no job); against this branch: **13 of 13**. The human test's PowerShell lines were run literally (Windows PowerShell 5.1, port 18298): 13 of 13, the curl lines as in steps 4.
* **Deviations from the task and why:**
  1. *One more contract route fixed:* the release feed's `channel` (licence-api 5.13; `TruebexUpdater.cpp:533` writes `FName(*S.Channel).ToString()`), found by the audit; Scope 5 says to fix every contract route the same way. It answered FastAPI's `Literal` 422 ("Input should be 'stable' or 'beta'"); it now answers `channel: stable or beta.` with the same code and field.
  2. *`quality` `[]` and `""` now 422* (they were read as standard through `or`), to keep "anything but a word answers 422" (the task's None / 7 / `[]` rule) while null keeps meaning "not sent", as for the analysis kinds and the contract's default.
  3. *The `/v1` push's agent check* (`_as_agent`) reads `author_kind` without case too: it is the same push (Scope 3), and an API key's `Agent` was refused before `parse_push` ran.
  4. *A demo script* (`server/scripts/demo_fname_case.py`) in place of a scratch-only one, so the human test is three commands; it is tested like `demo_replica.py`.
  5. *place's `args.kind` and the log-safe tool name stay exact* (`ops.py:124`, `:129`): the audit found the app writes no `action` operation (Scope 3's condition). Its own operations are always `delta` (`CadProjectLog.cpp:268`); `FCadProjectOp::ActionJson` is an FString re-sent as read (`:106-109`, `:154`); action ops come only from its stubs and fixtures (`CloudPanoStub.cpp:103-105`, `SyncFixtures.cpp:238-240`). agent-interface.md's "names match case-insensitively" (5.5) is `find`'s entity names, not `place`'s `kind`.
* **The audit** (app `main` bc06615c6, `Plugins/` read-only; every JSON field and query parameter the app sends to a platform route that is written with `FName::ToString`; paths under `Plugins/CADTOOL/Source/` unless named; "before" = master 96b79a8):

  | # | App file:line (the FName) | Field | Contract, section | The app's values | Platform before | Now |
  |---|---|---|---|---|---|---|
  | 1 | `TruebexSync/Private/RenderJobsClient.cpp:152` (`FRenderJobRequest::Kind`, `TruebexSync/Public/TruebexRenderJobs.h:88`) | `kind` | render-jobs 5.1 | panorama (`RenderJobsClient.cpp:348`), wind, airflow (`CadAnalysisJobs.cpp:438`, `:457`) | `render/service.py:160` exact (analysis kinds: without case, PF11c) | without case (`service.py:162`) |
  | 2 | `RenderJobsClient.cpp:161` (`Quality`, `TruebexRenderJobs.h:94`) | `quality` | render-jobs 5.1 | draft / standard / high (`CadRenderTunables.cpp:79`, `:148-152`; wind `CadWind.cpp:150`); **`high` → `High` certain** (`UnrealNames.inl:192`) | `service.py:171-172` exact (analysis: `analysis/kinds.py:103`, without case) | without case (`service.py:174`) |
  | 3 | `RenderJobsClient.cpp:233` (`List(…, FName Kind, …)`, `TruebexRenderJobs.h:119`) | `?kind=` | render-jobs 5.3 | tiles (`CloudPano.cpp:522`), panorama (`:605`) | `service.py:313` exact: `Tiles` lists nothing | without case (`service.py:316`) |
  | 4 | `RenderJobsClient.cpp:234` (`FName State`) | `?state=` | render-jobs 5.3 | queued, running (`CloudPano.cpp:519`) | `service.py:304` exact: 422 | without case (`service.py:309`) |
  | 5 | `TruebexSync/Private/CadAnalysisJobs.cpp:448`, `:468` (`FCadWindSettings::Terrain`, `CadCore/Public/CadWindTypes.h:33`) | `params.terrain` | render-jobs 6.5 (1.2.0) | sea / lake / open / suburban / urban | `analysis/kinds.py` `_choice` lower-case (PF11c) | already without case |
  | 6 | `CadAnalysisJobs.cpp:449` (`Criteria`, `CadWindTypes.h:36`) | `params.comfort` | render-jobs 6.5 | lawson | `_choice` (PF11c) | already without case |
  | 7 | `CadCore/Private/CadProjectLog.cpp:100` (`FCadProjectOp::AuthorKind`, `CadCore/Public/CadProjectLog.h:40`) | `ops[].author_kind` | project-log 5.6, §6.2 | person / agent (`CadProjectLog.cpp:262`) | `projects/ops.py:175`, `:177` exact; `/v1` `routers/v1/projects.py:100` | without case (`ops.py:179`, `v1/projects.py:99`) |
  | 8 | `CadProjectLog.cpp:103` (`FCadProjectOp::Kind`, `CadProjectLog.h:43`) | `ops[].kind` | project-log 5.6, §6.2 | delta (`CadProjectLog.cpp:268`); **`Delta` likely** (UMG `SpinBox.h:68`) | `ops.py:192`, `:195`, `:222` exact | without case (`ops.py:197`); restore still refused |
  | 9 | `TruebexSync/Private/SyncCollab.cpp:1242` (`FCommentAction::State`, `TruebexSync/Public/TruebexSyncCollab.h:163`) | `state` (PATCH) | project-log 5.21 | open / resolved (`SCadPeoplePanel.cpp:439`, `:441`); **`Resolved` likely** (`TemplateString.h:29`) | `projects/comments.py:308` exact | without case (`comments.py:310`) |
  | 10 | `TruebexSync/Private/SyncClient.cpp:332` (`Invite(…, FName Role, …)`, `TruebexSyncClient.h:47`) | `role` | project-log 5.14 | editor / viewer (`SCadCloudPanel.cpp:493`); **`editor` → `Editor` certain** (`UnrealNames.inl:48`) | `projects/members.py:98` exact | without case (`members.py:101`) |
  | 11 | `SyncClient.cpp:341` (`SetMemberRole(…, FName Role)`, `TruebexSyncClient.h:49`) | `role` | project-log 5.15 | editor / viewer (`SCadPeoplePanel.cpp:508`) | `members.py:98` exact | without case (`members.py:101`) |
  | 12 | `TruebexUpdate/Private/TruebexUpdater.cpp:533` (`Channel()`, `FName(*P.Channel)` / `FName(*S.Channel)` at `:434-435`) | `?channel=` | licence-api 5.13 | stable / beta | `routers/releases.py:17`, `:22` `Literal`: 422 | without case (`releases.py:26`) |
  | 13 | `TruebexTelemetry/Private/TruebexTelemetry.cpp:214`, `:219`, `:224` | event `name`, prop keys, enum values | telemetry §6.1 | **`warning` / `error` → `Warning` / `Error`, `team` → `Team` certain** | without case (PF14d) | no change |
  | 14 | `TruebexTelemetry.cpp:1182` (`FTelemetryFeedback::Kind`) | feedback `kind` | telemetry 5.4 | bug / idea / question / praise | lower-cased (PF14d) | no change |
  | 15 | `3DCADTOOL/Source/Cad3DTool/Private/Cad3DShare.cpp:721` → `CadCore/Private/CadShareBundle.cpp:299` (`FCadEntitlement::Plan`) | manifest `plan` | share-bundle 1.1 | free / pro / studio / team / enterprise; **`Team` certain** | stored, never shown (`shares/manifest.py:428`), no check | free text, no check |
  | 16 | `Cad3DShare.cpp:344`, `:363`, `:367`, `:372`, `:703` (saved views' FNames) | `panoramas[].id`, hotspot `target` / `label`, `start`, `renders[].title` | share-bundle | the person's own view names | ids, targets and `start` compared with each other only (one FName each, so one spelling) | free text, no check |
  | 17 | `TruebexAgent/Source/TruebexAgent/Private/Assistant/AssistantTools.cpp:97` (`FToolSpec::Name`, `AgentRouter.h:138`) | `tools[].name` | ai-proxy 5.1 | the 21 tool names | `ai/validate.py:32` `[a-zA-Z0-9_-]{1,64}`, any case, passed to the model | already without case |

  Checked and not FNames (or not sent): every id (`FCadEntityId`, `FGuid`), the pack `items` (`TArray<FString>`, never filled: `TruebexRenderJobs.h:96`), the analysis `turbulence_model` (a literal, `CadAnalysisJobs.cpp:452`), the comment list's `state=all` (an FString, `TruebexSyncClient.h:53`), presence's `client` (`"desktop"`, `SyncCollab.cpp:418`), the marketplace, order and licence bodies (FStrings), the telemetry common block's `plan` (lower-cased first, `TruebexTelemetry.cpp:737`), the updater's `SetChannel` and the share's `upgrade_to` (lower-cased). Local only: `collab.json`, the `.tbxp` side-car, audit and wind summary files, stub and self-test code. Inside the `.tbxp` snapshot (uploaded through `/uploads`) FNames are written with `ToString()` too (for example `CadSerialization_AN3.cpp:66-69`), but the platform keeps only the file's hash and size and its worker reads it with the app (FName lookups ignore case). Outside the API: `CadEntitlement.cpp:831` opens `https://truebex.com/dashboard/billing/?plan=<Plan>` (Carry-over).
* **PATCH lines proposed for the app half** (wording only; the platform already behaves so, from this feature on):
  * A. `render-jobs.md` §5.1 / §5.3: `kind`, `quality` and 5.3's `kind` and `state` filters compare without (ASCII) case; the platform stores and answers the lower-case spelling.
  * B. `project-log.md` §6.2 / §5.6: an operation's `kind` and `author_kind` compare without case (`restore` stays the server's); §5.21 a comment's `state` and §5.14 / §5.15 a member's `role` the same (`owner` is never sent); answers carry the lower-case spelling.
  * C. `licence-api.md` §5.13: `channel` compares without case.
  * D. The app writes these values from string literals rather than `FName::ToString` (as PF14d proposed for OP1's telemetry): `FRenderJobRequest::ToJson` and `List`, `OpToJson`, the comment PATCH in `SyncCollab.cpp`, `FClient::Invite` and `SetMemberRole`, the updater's feed URL, the share manifest's `plan`, the upgrade link.
* **Contract §11:** no row moves (no endpoint added); the lines above are PATCH-level.
* **Carry-over:**
  * **PF11c's "PF6's owner: the render kinds still compare `kind` and `quality` exactly":** met here (PF11c's doc points at this one).
  * **The app half:** PATCH lines A-D.
  * **The site (whoever next touches the billing page):** `src/app/dashboard/billing/page.tsx:381` takes `?plan=` exactly, so the app's upgrade link from a Shipping build (`?plan=Team`, `UnrealNames.inl:190`) preselects the first buyable tier instead of Team; lower-casing it there (or the app writing a literal) fixes it.
  * **The owner:** Human test step 6 on a Shipping build against the live API once this is deployed.
* **Verify gate:** `scripts/autopilot-verify.ps1` (absolute `-File` path) green on `2506506`: lint, build (compiled in 63 s), pytest 943 passed + 19 skipped (962 collected) in 736 s, `out/index.html` checked; 1,120 s in all.
