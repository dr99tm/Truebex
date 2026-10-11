# PF12a — /v1 panorama reads for API keys (launch priority 2)

**Needs merged:** PF9, PF12 (both on `master` at 842768e, with PF10 and PF11). **Unblocks:** none (a developer's own viewer or pipeline can follow a project's live panoramas). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\render-jobs.md` (v1.0.0; §4 lists API keys, §5 gains the members' reads by PF9's MINOR proposal, 5.2's `rev` long-poll), with `project-log.md` §4 (API keys under `/v1/projects…` only) and §11.

## Status

**Built 2026-10-11** on `ap/t37-pf12a-v1-panorama-reads-for-api` (base `master` at 842768e): `GET /v1/projects/{pid}/panoramas`
and `GET /v1/projects/{pid}/panoramas/{set_id}` for API keys with `projects:read` (`server/app/routers/v1/projects.py`),
their documented shapes (`server/app/routers/v1/models.py`), `openapi/v1.json` and both SDKs regenerated, the
`/developers/projects/` reference generated with them. Waiting on others: the owner's contract rows and the MINOR
proposal (As-built), the real render worker (CL3; the sets render with PF6's stand-in app until then). See As-built.

Before this task an API key could not read a project's followed panorama sets. Verified with Grep on `master` 842768e:

| Area | Where | Before |
|---|---|---|
| Members' reads (PF9) | `server/app/routers/mobile.py:30-39` (list), `:52-89` (one set, long-poll), `server/app/mobile/panoramas.py` | `Depends(get_project_caller)`: a session or a device token; an API key 401 (`server/app/projects/caller.py:4-5`, `:47`) |
| The `/v1` mirror (PF12) | `server/app/routers/v1/projects.py` (242 lines: 5.1–5.18) | no panorama route |
| Document and SDKs | `openapi/v1.json` (52 operations, 83 schemas), `sdks/python/`, `sdks/js/` | no panorama operation; `server/tests/test_pf9_pf12_meet.py:194` (`test_panoramas_stay_off_v1`) asserted it |
| Carry-over | PF9 As-built (T33 merge notes), the PF9 tracker row | "the panorama routes stay off `/v1` (a PF12 carry-over)" |

What the owner meant: PF9's carry-over to PF12 and `render-jobs.md` §5's MINOR proposal for the members' reads, which
names these routes.

## Goal

A developer with an API key follows a project's live panoramas the way the phone does: list the project's followed
panorama sets, read a set's newest tile manifest, and wait on its `rev` until the next render lands, with the same
answers, roles and errors as the app's own routes, metered like every other `/v1` read.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* As-built of `PF12-…md` (the mirror hands calls to the contract handlers with an `api_key` caller), `PF9-…md` (deviation
  1: the members' reads; T33's merge notes) and `PF6-…md` (followed sets, the 5.2 long-poll).
* `contracts/render-jobs.md` §4, §5 (5.2), §6.2; `contracts/project-log.md` §4, §11; `contracts/agent-interface.md` §5
  and §11 (the tools the MCP package lists).
* `server/app/mobile/panoramas.py`, `server/app/routers/mobile.py`, `server/app/routers/v1/common.py` and `models.py`.

## Scope

**In:**
1. `GET /v1/projects/{pid}/panoramas` and `GET /v1/projects/{pid}/panoramas/{set_id}` with `projects:read`, in
   `server/app/routers/v1/projects.py`, handing each call to PF9's handlers so the shapes, the viewer-role rule, 404 for
   a non-member, the `rev` + `wait_s` long-poll (`wait_s` ≤ `queue.STATUS_WAIT_MAX_S`, no database connection held while
   waiting) and `Cache-Control: private, no-store` match the session routes; metering and the burst limit as every
   `/v1` read (`deps.api_key_auth`).
2. Pydantic models with docstrings in `server/app/routers/v1/models.py`; operation ids `projects_panoramas_list` and
   `projects_panoramas_get` with `doc("projects:read", …)` errors.
3. `openapi/v1.json` by `server/scripts/export_openapi.py --v1`, the SDKs by `scripts/gen-sdks.ps1`;
   `openapi/clients.json` unchanged (`--clients --check`); the `/developers/` reference (generated, not hand-listed).
4. `packages/mcp`: no tool (agent-interface names none for this read).
5. The contract rows and the MINOR proposal for the owner (As-built).

**Out (and where it goes):**
* Changing the session routes or `server/app/mobile/panoramas.py` → not needed (PF9's rules are the rules here).
* A webhook event for a set's new render → not planned; a key long-polls the set (`job.succeeded` already reaches the
  account whose job it is).
* An MCP tool for cloud panoramas → only if `agent-interface.md` names one (AI1's `tools.json`).
* Publishing the SDKs → the owner (PF12 As-built).

## Design

### API

| Method | Path | Scope | Answers |
|---|---|---|---|
| GET | `/v1/projects/{pid}/panoramas` | `projects:read` | 200 `PanoramaSetList`; 401, 403 (`forbidden`, `data.needed`), 404 (not a member), 429 |
| GET | `/v1/projects/{pid}/panoramas/{set_id}?rev=&wait_s=` | `projects:read` | 200 `PanoramaSetState`; 401, 403, 404 (no such set in this project, or not a member), 422 (`wait_s` outside 0–25), 429 |

Both carry `X-Truebex-Contract: project-log/1.0` (the `/v1/projects` group, as PF9's routes do) and
`Cache-Control: private, no-store`. Any role reads (viewer and up); a set is served while its account is an active
member. With `rev` and `wait_s` the read returns when the set's `rev` passes `rev` (PF6 bumps it as each `tiles` job
of the set finishes) or after `wait_s`.

```json
GET /v1/projects/01a1…/panoramas
{"sets": [{"set_id": "6e67…", "rev": 2, "at_seq": 13, "views": ["0199…0001", "0199…0002", "0199…0003"],
           "following": true, "mine": true, "updated_at": "2026-10-11T07:25:01Z"}]}

GET /v1/projects/01a1…/panoramas/6e67…?rev=1&wait_s=25
{"rev": 2, "job_id": "<the tiles job>", "follow_job_id": "6e67…", "at_seq": 13, "following": true,
 "manifest": {"schema": "truebex-tiles/1", "job_id": "…", "at_seq": 13, "tiles_base": "https://…/tiles", "views": […],
              "faces_rendered": 6, "faces_reused": 12}}
```

**Decision:** the `/v1` routes call PF9's route handlers (`app/routers/mobile.py`) with `project_caller(api)`, the way
every `/v1/projects` route calls the contract router's handler. Rejected: moving the logic into a new service module (two
callers of one handler already share it, and a copy would let the long-poll drift).

### Data

None: no table, column or migration. The sets are PF6's `render_sets`; the manifests PF6's tile storage.

### UI

No page changes: `/developers/projects/` generates a section per operation from `openapi/v1.json`, so both reads appear
there with their parameters, answers and errors. No new copy in `src/lib/constants.ts` (nothing is listed by hand).

### Jobs / workers

None. PF6's worker renders the sets; PF4's push hook queues their `tiles` jobs.

### Security and privacy

* `projects:read` on both; the key's account must be an active member (404 otherwise, never 403, so a project's
  existence does not leak); sets of members who left are not served.
* Answers are never cached (`private, no-store`); tile URLs are public by content hash (PF6) as for the phone.
* The long-poll holds no database connection while it waits, so idle keys cannot drain the pool.

## Deliverables

- [x] `server/app/routers/v1/projects.py`: `projects_panoramas_list`, `projects_panoramas_get`
- [x] `server/app/routers/v1/models.py`: `PanoramaSet`, `PanoramaSetList`, `PanoramaSetState`, `TileManifest`, `TileView`, `TileFace`
- [x] `openapi/v1.json` (54 operations, 89 schemas), `sdks/python/truebex/{models,_operations}.py`, `sdks/js/src/{schema.d.ts,operations.mjs,operations.d.ts}`
- [x] `server/tests/test_pf12a_v1_panoramas.py`; `server/tests/test_pf9_pf12_meet.py` (a key reads the set its own edit re-rendered)
- [x] docstrings: `server/app/routers/mobile.py`, `server/app/routers/v1/__init__.py`; the `projects` tag text in `server/scripts/export_openapi.py`
- [x] this doc, the tracker row, a README section; the contract rows and the MINOR proposal in As-built

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_v1_panoramas_list_with_key` | pytest | the list and the set answer the same bodies as the session routes for the same account; `private, no-store`, `project-log/1.0`, `X-RateLimit-*`; a viewer's key reads the owner's set (`mine` false); metered per route in `usage_daily` |
| `test_v1_panoramas_need_projects_read` | pytest | a `jobs:write` key → 403 `forbidden` with `data.needed` `projects:read`; no key, a wrong key, a session or a device token → 401; a key from before scopes reads; the session routes still refuse a key |
| `test_v1_panorama_set_long_poll` | pytest | PF6's loop with a worker: a read waiting on `rev` 1 wakes when a push's `tiles` job finishes (rev 2, two faces) and equals the session route; on `rev` 2 it returns at `wait_s` with no pool connection checked out meanwhile; a passed `rev` or no `rev` answers at once |
| `test_v1_panoramas_non_member_404` | pytest | a stranger's key, an unknown project, an unknown or malformed set, another project's set → 404; a set of someone who left is hidden, and their key reads nothing |
| `test_v1_panoramas_validation` | pytest | `wait_s` 99, 25.5, −1 → 422 envelope with `data.fields` `wait_s` in query, equal to the session route's; non-numbers → the envelope; 25 is allowed |
| `test_v1_panoramas_documented` | pytest | the two operations with their ids, scope, contract, tags, answers and errors; the six schemas with descriptions; no renamed key in the Python types; the SDK methods exist |
| `test_v1_panoramas_python_sdk` | pytest (live API) | `c.projects.panoramas_list` / `panoramas_get` with `rev` and `wait_s`; 422 and 404 as `TruebexError` |
| `test_v1_panoramas_burst_limit` | pytest | past the per-key burst → 429 `rate_limited` (`data.limit` burst), the refused call not counted |
| `test_key_reads_a_followed_set_after_its_own_edit` | pytest (`test_pf9_pf12_meet.py`) | a key's agent push through `/v1` queues the set's `tiles` job; the key's waiting read wakes with rev 2 at the pushed sequence; a viewer's phone reads the same through the session route; the document lists the pair |
| `test_openapi_v1_document_current`, `test_sdk_operations_current`, `test_sdk_types_cover_every_schema`, `test_openapi_clients_document_current` | pytest (existing drift tests) | `openapi/v1.json`, both SDKs and `openapi/clients.json` current |
| `test_site_pf12_*` | build check (existing) | `/developers/projects/` lists every operation of its group, the two new ones included |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. Terminal 1, in the worktree: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\try-mobile.ps1` → after a
   few minutes it prints "Ready", the House's `project id: …` and keeps the API (:8000) and the render worker running.
   (It builds `out/` against :8000; `-NoBuild` skips that when `out/` is already built so.)
2. Terminal 2: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → open the printed
   address, Sign in as `alex@example.com` / `password123` → Dashboard → API keys → create "Panoramas" with
   `projects:read` and `projects:write` → copy the key (shown once).
3. Terminal 3: `$k = 'tbx_live_…'; $p = '<project id>'` then
   `curl.exe -s -H "Authorization: Bearer $k" http://127.0.0.1:8000/v1/projects/$p/panoramas` → one set with
   `"following": true`, `"mine": true` and a `rev` of 1 or more (the worker rendered it); note `set_id` and `rev`.
4. `curl.exe -s -i -H "Authorization: Bearer $k" http://127.0.0.1:8000/v1/projects/$p/panoramas/<set_id>` → 200 with
   `Cache-Control: private, no-store` and a `manifest` with `"schema": "truebex-tiles/1"` and `tiles_base`.
5. Long-poll: `curl.exe -s -H "Authorization: Bearer $k" "http://127.0.0.1:8000/v1/projects/$p/panoramas/<set_id>?rev=<rev>&wait_s=25"`
   (it waits); in terminal 4 (set `$k` and `$p` there too), `cd server; .venv\Scripts\python.exe scripts\demo_mobile.py --token $k move --project $p --entity Oslo`
   → "Move Oslo 3-seater sofa: accepted as …"; within a few seconds terminal 3 prints the set with `rev` one higher.
   Run the step-5 call again without moving anything → it answers after 25 s with the same `rev`.
6. `curl.exe -s http://127.0.0.1:8000/v1/projects/$p/panoramas` (no key) → 401 `unauthenticated`;
   `…/panoramas/<set_id>?wait_s=99` with the key → 422 `validation_failed` "wait_s: 0 to 25.".
7. Python SDK: `cd sdks\python; py -3.12 -c "import truebex; c = truebex.Client(api_key='tbx_live_…', base_url='http://127.0.0.1:8000'); print(c.projects.panoramas_list('<project id>'))"`
   → the same set as step 3.
8. In the browser, `/developers/projects/` → the Reference lists "GET /v1/projects/{project_id}/panoramas" and
   "…/panoramas/{set_id}" with scope `projects:read`; Dashboard → Usage → By endpoint counts the calls under those two routes.

## Risks / traps

* `curl` in Windows PowerShell 5.1 is `Invoke-WebRequest`: the human test says `curl.exe`.
* The Python SDK's type generator renames a property called `schema` to `schema_` (a TypedDict key that is not on the
  wire), so `TileManifest` names `schema` in its description only; `test_v1_panoramas_documented` fails on any renamed
  key.
* `scripts\gen-sdks.ps1` makes `.sdk-tools\venv` on its first run; on this PC its first `pip install` hung (the Python
  3.12 WMI race that `autopilot-setup.ps1` guards against for `server\.venv`). Stopping it and running the script again
  went through.
* The long-poll waits on PF6's in-process wake-up plus a 1 s re-check, like 5.2; a second API process only sees a new
  `rev` on the re-check.
* The sets render with PF6's stand-in app (`worker/tests/fake_truebex.py`) until CL3: a re-render redraws the stand-in's
  faces, not the edited room.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t37-pf12a-v1-panorama-reads-for-api` (base `master` 842768e): `c21b2e9`
  (routes, models, the regenerated document and SDKs, tests) and the docs commit ticking this row.
* **Counts:** pytest 548 → 557 collected; the verify gate (lint, build, pytest on SQLite): 552 passed, 5 skipped (the
  Postgres-marked tests). New: `test_pf12a_v1_panoramas.py` 9; `test_pf9_pf12_meet.py` 7 → 7 (`test_panoramas_stay_off_v1`
  replaced by `test_key_reads_a_followed_set_after_its_own_edit`). `openapi/v1.json` 52 → 54 operations, 83 → 89
  schemas; `openapi/clients.json` unchanged (`export_openapi.py --clients --check`: current).
  **Live run** (uvicorn on SQLite with inline jobs on :8137, PF6's worker with `fake_truebex.py`, `demo_mobile.py
  setup`, keys made through `POST /keys` as the dashboard does, `curl.exe` and the Python SDK from `sdks/python` with
  plain `py -3.12`): 13 of 13 — the House's set read with the key (rev 1, 18 faces), `private, no-store`,
  `X-RateLimit-Remaining`, a manifest tile downloads as JPEG, the key's list equals the session route's, the editor's key
  lists the owner's set with `mine` false; a read waiting on rev 1 woke 1.2 s after `demo_mobile.py --token tbx_live_…
  move --entity Oslo` (rev 2, the worker's `tiles` job); `wait_s=3` on rev 2 returned after 3.1 s unchanged; 401 without a
  key, 403 `data.needed` `projects:read` for a `jobs:write` key, 422 "wait_s: 0 to 25.", 404 for an unknown project;
  `c.projects.panoramas_list` / `panoramas_get` answered the set at rev 2; Dashboard → Usage's `by_endpoint` counted
  both routes.
* **Deviations and decisions:**
  1. *The handlers are reused, not moved:* `/v1` calls `app/routers/mobile.py`'s `list_panoramas` and `panorama_set`
     with `project_caller(api)` (as `/v1/projects` calls `app/routers/projects.py`), so `server/app/mobile/panoramas.py`
     and the session routes are unchanged. The handler closes the request's session before it waits, and that is the
     same session `api_key_auth` metered with (FastAPI shares `get_db` within a request), so the wait holds no
     connection; the test checks the pool.
  2. *Operation ids* are the task's `projects_panoramas_list` and `projects_panoramas_get` (SDK: `c.projects.panoramas_list`,
     `panoramas_get`; JS `panoramasList`, `panoramasGet`), not the verb-first style of 5.10–5.13 (`projects_list_versions`).
  3. *Shapes:* `PanoramaSetState.manifest` is typed as `TileManifest` (views, faces, levels, `tiles_base`) rather than
     the open `JobOutput`; `schema` stays out of its fields (Risks). Response models remain documentation only, so a
     field PF6 adds reaches callers first.
  4. *`API_VERSION` stays 1.0.0* (`export_openapi.py` asks for a MINOR bump when the document grows): nothing is
     published yet, as T32 and T33 left it; the first published SDKs carry these reads. Bump to 1.1.0 if 1.0.0 has
     reached PyPI or npm by merge time.
  5. *Docs:* no copy added to `src/lib/constants.ts`: `/developers/projects/` lists operations from `openapi/v1.json`, so
     the two sections and their descriptions (the route docstrings) come with the document. The `projects` tag text names
     the sets.
  6. *MCP:* no tool added to `packages/mcp`. `agent-interface.md` §5 names no tool that reads a cloud project's panorama
     sets (`export_panorama`, 5.13, exports from the open model in the app) and the package is a contract stand-in until
     AI1, so its `tools.json` and `test_pf12_mcp_package.py` are untouched.
  7. *The session routes still answer an API key 401* (`get_project_caller`): `project-log.md` §4 keeps keys on
     `/v1/projects…`.
* **Contract rows for the owner** (the Unreal repo is read-only here; C.9: write them there first):
  * `render-jobs.md` §5 (MINOR, PF9's proposal now with API keys): two rows —
    `5.11 | GET | /projects/{pid}/panoramas | project member (device, session), API key under /v1 (projects:read) | the project's followed sets of active members`
    and `5.12 | GET | /projects/{pid}/panoramas/{set_id} | the same | a set's newest manifest; long-poll on rev with wait_s ≤ 25`;
    §4's API key row gains "and the members' panorama reads under `/v1/projects…`".
  * `render-jobs.md` §11: `GET /projects/{pid}/panoramas` and `GET /projects/{pid}/panoramas/{set_id}` → app "— (PF9, PF10
    are clients)", platform "PF9: done (session, device); PF12a: done (`/v1`, API key)".
  * `project-log.md` §11: the same two rows under the `/v1/projects…` mirror → "PF12a: done" (PF9's rows "PF9: done", as its
    As-built asks).
* **Carry-over:** the owner → the contract rows above; publishing the SDKs with these operations (PF12's steps). CL3 → real
  renders behind the sets. AI1 → an MCP tool only if `tools.json` gains one.
