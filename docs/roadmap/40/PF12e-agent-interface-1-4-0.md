# PF12e — The MCP package, the developer docs and the project log follow agent-interface 1.4.0 (launch priority 2)

**Needs merged:** PF12d (on `master`), PF4b; app: PL1 "the scripting API and console" (app task T133, merge T214 of
ME3, ME4, ME5, PL1 and PR5, app `main` 2c842b8f1, 2026-11-09 14:32 UTC). **Unblocks:** publishing `@truebex/mcp` with
the app's current tools (owner); a light client that numbers rooms (none planned yet). **Contract:**
`T:/unreal5_7_4_projects/truebex_compact/Docs/roadmap/40/contracts/agent-interface.md` 1.4.0 (blob f74cdb9c: §3
*Changes* 2026-11-09, §5's row 5.27, §5.5's new match fields, §5.27, §10's `pl1-*` rows, §11) and `project-log.md`
1.2.1 §6.2 (unchanged); no change from the platform (the §11 cells and proposals are in As-built).

## Status

**Built 2026-11-09** on `ap/t103-pf12e-the-mcp-package-the-develo` (base `master` at 61ac33a). The package and
`src/content/tools.json` are the app's `tools.json` 1.4.0 (22 tools, 21 on the mcp surface); `/developers/mcp/`
documents those 21, `set_properties` last, and says what a batch does; the project log takes `set_properties` as an
action (`ops.LOG_SAFE_TOOLS`, seven edits). Waiting on others: the app-side carry-overs and contract proposals in
As-built; npm publishing (owner, unchanged from PF12).

Before this task, verified on `master` 61ac33a against the app's `main` 2c842b8f1 (read through the manager's
snapshot, see As-built):

| Area | Where | Before |
|---|---|---|
| Copy | `packages/mcp/tools.json`, `src/content/tools.json` | PF12d's copy of app `main` 7fdde1e6f: `tools.json` 1.3.0, 21 tools, 20 on the mcp surface |
| Copy | `packages/mcp/instructions.md`, `test/mcp.test.mjs` | without PL1's line on numbering rooms; `tools/list` length 20, no `PL1_TOOLS` |
| Log | `server/app/projects/ops.py:54`, `:126` | `LOG_SAFE_TOOLS` = place, move, resize, fill, apply_theme, set_tunable: a `set_properties` action answers 422 on `ops[i].action.tool` |
| Tests | `test_pf12c_agent_interface.py:98`, `test_pf12d_agent_interface.py:32`, `:60`, `test_pf12_mcp_package.py:31-43`, `:632`, `:670`, `test_site_pf12.py:252` | six log-safe edits as literals in four places; `CONTRACT` without `set_properties`; the version check ≥ 1.3.0 |
| Docs | `packages/mcp/README.md:9`, `:62` | "20 tools" written out (the page counts from the file since PF12d: `withToolCount()`) |

## Goal

The MCP server a developer installs from the platform, the page that documents it and the project log say what the
app says since agent-interface 1.4.0: an MCP client sees 21 tools, PL1's `set_properties` last; the page shows its
batch of items readably (each item's target and its props' code, name and type) and tells a developer what a batch
does (rooms' codes, names and types, up to 200 as one undo step, all or nothing) and that it may travel in the
project log; a light client or an agent may write a `set_properties` action to a cloud project's log, and the next
log-safe tool breaks one test line, not four.

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4, C.9 (the app side is authoritative); PF12c's and PF12d's docs.
* `agent-interface.md` 1.4.0: §3, §5.5 (`find`'s new match fields), §5.27, §6.2 (refs), §6.3, §6.5, §10, §11;
  `project-log.md` §6.2.
* Here: `scripts/sync-mcp.ps1` (its `-AppRepo`), `server/app/projects/ops.py`, `src/lib/developer-docs.ts`,
  `src/app/developers/mcp/page.tsx`, `DEVELOPER_DOCS.pages.mcp` in `src/lib/constants.ts`.
* Skills: `truebex-brand-voice` (the page's words), `truebex-seo` (a public page changes).

## Scope

**In:**
1. `scripts/sync-mcp.ps1 -AppRepo X:/Truebex/.autopilot/manager/app-main-2c842b8f`: the copies committed byte-equal
   (`tools.json` into `packages/mcp` and `src/content`, `instructions.md`, `test/mcp.test.mjs`; the rest unchanged);
   `manifest.json` and `truebex.mcpb` still not copied (PF12b deviation 3); `package.json`'s version stays the bridge's
   `SERVER_VERSION` (1.0.0); the copied bridge never edited.
2. `ops.LOG_SAFE_TOOLS` gains `set_properties` after `set_tunable` (§5's order); the push checks its `args.items`
   (Decision below).
3. Tests first (each failing on the base); the log-safe set taken from `tools.json` wherever a test compares the
   platform with the copy, one literal list left (`LOG_SAFE_EDITS`, the order test).
4. `/developers/mcp/`: the `set_properties` section from `tools.json` (its `items` listed through `nestedFields()`),
   the counts from the file, a line on what a batch does where the page says what an agent may and may never do;
   `packages/mcp/README.md` names no count.
5. A README section at its end, this doc, the tracker row, one line in PF12d's carry-over.

**Out (and where it goes):**
* The scripting console (TruebexScript): in-process in the app (§2, §4); nothing on the platform.
* A web or Android UI to number rooms → not this task: the light clients write only the tools they have UI for
  (`src/viewer/actions.ts`, `mobile/android/lib/actions/actions.dart`: move, fill, apply_theme, place; unchanged), so a
  numbering UI needs its own row (PF9 / PF10 follow-up).
* The AI proxy's assistant tool list (22, with `propose_variants`) → none: ai-proxy is unchanged and the proxy pins no
  tool name or count (`server/app/ai/validate.py` `MAX_TOOLS` = 64), so no PF11 carry-over.
* Any change to the bridge, `tools.json` or the node tests → the app (PL1), then `sync-mcp.ps1` (carry-overs below).
* npm publish of `@truebex/mcp` → the owner (PF12's steps).

## Design

### API

`POST /projects/{id}/ops` (and `/v1/projects/{id}/ops`) takes an `action` whose `tool` is `set_properties`, as for the
six earlier log-safe edits: stored as written, pulled back byte-equal, `touched` the writer's (the ids of the rooms,
storeys and openings its targets name, §6.2). An action with any other tool still answers 422 `validation_failed` on
`ops[i].action.tool`, the message listing the seven; `create_layout` and `remove` stay refused (PF12d's test). No
generated document or client type changes (the action's `tool` is a plain string in `openapi/v1.json`).

**Decision (the args check):** the push checks only that `args.items` is a list of 1–200 objects (§5.27's bound,
`ops.SET_PROPERTIES_MAX_ITEMS`); anything else answers 422 on `ops[i].action.args.items`: "set_properties takes 1 to
200 items, each an object". Nothing inside an item is checked: a storey with a `type`, a wall target, an empty or
unknown prop, a `selection` target are accepted and every kernel replica answers them `invalid` alike (a no-op on all
of them, §6.2). Taken because `place`'s kind is the only per-tool check the push makes today and the replica owns the
semantics (§5.27's checks need the document); the item bound keeps a writer's batch to what the tool takes. Rejected:
mirroring the item schema on the server (a second copy of §5.27 that drifts at the next MINOR).

### Data

None. `src/content/tools.json` and `packages/mcp/tools.json` are the app's file (66 077 B, LF; blob a006ae84).

### UI

| Where | What changes |
|---|---|
| `/developers/mcp/` | a 21st section, `set_properties` (class edit, "Also travels in the project log"), generated from the file: rows `items` (`object[]`, required, 1–200 items), `dry_run`, `request_id`; under `items`, "Each item:" `target`, `props`, `props.code`, `props.name`, `props.type` with their lengths and descriptions; "21 tools" in the description and the Claude Code note (`{tools}`, PF12d) |
| `DEVELOPER_DOCS.pages.mcp.safety` | one line after PF12d's remove line (below) |
| `packages/mcp/README.md` | "every tool the app lists in `tools.json`" instead of "20 tools"; `set_properties` in the tool list (edit) and a Batches bullet |

**The copy** (the "What it never does" list, after the remove line):
"set_properties sets the code, name and type of rooms (a room's code is its number, such as G.01), the code and name
of storeys, and the name of doors and windows, in batches of up to 200 as one undo step. It never applies part of a
batch: every item applies, or nothing changes. It is one of the edits that may also travel in the project log."

**Decision (the item list):** the `items` row lists each item's fields as PF12d lists an array argument's items
(`create_object`'s parts): under "Each item:", so the brief's `items[].props.code` reads `props.code` there (the
label stands for `items[]`). Taken because a prefix would repeat the label on every line and change PF12d's
`parts`, `blocks` and `cites` lists; the full path is what `_walk` and the tests check.

### Security and privacy

* The app repository is only read: the manager's snapshot (`git archive`, every file checked against its blob id) and
  a read-only `git log` in the PC's checkout.
* The page states what the app enforces (§5.27): one undo step, all or nothing; it never claims more.

## Deliverables

- [x] The copies from the app's `main` 2c842b8f1 (through the snapshot): `tools.json` (package and site),
  `instructions.md`, `test/mcp.test.mjs` (the rest unchanged, every file equal to its blob)
- [x] `server/app/projects/ops.py` (`LOG_SAFE_TOOLS`, `SET_PROPERTIES_MAX_ITEMS`, the items check)
- [x] `DEVELOPER_DOCS.pages.mcp.safety` (one line), `packages/mcp/README.md`
- [x] Tests: `test_pf12e_agent_interface.py` (8 new), `test_pf12_mcp_package.py` (4 changed), `test_site_pf12.py`
  (1 changed), `test_pf12c_agent_interface.py` (1 changed), `test_pf12d_agent_interface.py` (its log-safe set from the file)
- [x] This doc, the tracker row, PF12d's carry-over line, a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_tools_json_follows_the_contract` | pytest | version ≥ 1.4.0 (1.x); §5's order from `CONTRACT` with `set_properties` last (22); `set_properties` class edit, `logSafe` true, surfaces exactly `["mcp", "assistant"]`, no `requires`, annotations (not read-only, not destructive, idempotent, closed world); `items` 1–200 closed `{target ≤ 64, props}`, `props` closed `{code ≤ 64, name ≤ 80, type ≤ 64}`, none required; `dry_run` boolean, `request_id` ≤ 32; output `ok`, `set`, `changed`, `undo_step`, `text`; no planning id in what a client sees; the log-safe edits in order = `LOG_SAFE_EDITS` (the seven) |
| `test_mcp_package_stdio_framing`, `…_discover_and_legacy_initialize` | pytest (node) | the `tools/list` length is the mcp-surface count and `MCP_ORDER`'s (21), never a literal |
| `test_mcp_package_tools_list_and_replay` | pytest (node) | `tools/list` is `MCP_ORDER`, `set_properties` last; with no app `set_properties` answers `app_not_running` (not −32602); with the app's fake linked it reaches the app as written (`calls=3`) |
| `test_mcp_package_app_node_tests` | pytest (node) | every declared test but `mcp-bundle-manifest` runs and passes (10: 1.4.0 added two asserts, no test) |
| `test_mcp_package_install_notes` | pytest | the package README says "every tool the app lists", any "N tools" equals the mcp count (none today), no count in words, names every mcp tool, says "up to 200", "one undo step", "project log" |
| `test_log_safe_tools_follow_tools_json` (PF12c) | pytest | `ops.LOG_SAFE_TOOLS` = the file's log-safe edits in §5's order = `LOG_SAFE_EDITS` (the one literal list) |
| `test_project_log_refuses_creation_tools` (PF12d) | pytest | unchanged, its log-safe set now read from the file: AI5's seven still refused |
| `test_project_log_accepts_set_properties_action` | pytest (SQLite, Postgres) | a person's (session), an agent's (device, `author_kind` agent, an Arabic name) and an API key's (`/v1`) `set_properties` accepted (seq 1–3), pulled back byte-equal with their `touched` |
| `test_project_log_checks_only_set_properties_items` | pytest (SQLite, Postgres) | no items, an object, `[]`, 201 items, a string item, a null item → 422 on `ops[0].action.args.items` ("1 to 200 … object"), nothing stored; a storey's type, a wall, empty props, an unknown prop, `selection` accepted; 200 items with every string at its maxLength accepted and pulled back (under 64 KiB) |
| `test_project_log_set_properties_conflicts_on_its_rooms` | pytest | two replicas numbering one room from one base: the second rejected, the first winning; another room accepted |
| `test_project_log_still_refuses_creation_beside_set_properties` | pytest | `set_properties` + `create_layout` or `remove` in one push → 422 on `ops[1].action.tool`, nothing stored |
| `test_log_safe_tools_gain_set_properties` | pytest | `LOG_SAFE_TOOLS` ends `set_tunable`, `set_properties`; `SET_PROPERTIES_MAX_ITEMS` = the file's `maxItems` |
| `test_instructions_name_set_properties` | pytest | the copied `instructions.md` names `set_properties`, "up to 200 rooms", "one undo step" |
| `test_docs_generator_lists_set_properties_items` | pytest (node, types stripped) | `argumentRows()` `items` (`object[]`, required, 1–200 items), `dry_run`, `request_id`; `nestedFields(items)` `target`, `props`, `props.code`, `props.name`, `props.type` with types and lengths |
| `test_docs_generated_from_tools_json` | build check | 21 sections in `MCP_ORDER`, `set_properties` last; every row and nested line as the file (161 rows, 113 fields in 19 lists); `set_properties`' `items` row and its "Each item:" list line by line; "Also travels in the project log" exactly on the file's log-safe edits; no "undefined", "[object Object]" or empty type; "21 tools" from `{tools}` |
| `test_docs_set_properties_copy` | build check | the never-list line (code, name and type of rooms; storeys, doors and windows; up to 200 as one undo step; all or nothing; may travel in the project log); PF12d's lines kept; the section says class edit and the project log |

## Human test

Launch: in the worktree, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` (serves
`out/` on `http://127.0.0.1:3203/`, 3100 + the task number). No local API is needed for the page or the MCP server;
step 4 uses the pytest.

1. Open `http://127.0.0.1:3203/developers/mcp/` → the description and the Claude Code note say "21 tools"; under Tools,
   `tools.json 1.4.0` and 21 sections, the last `set_properties` "Set rooms' codes, names and types", "Class: edit ·
   Also travels in the project log". Its table: `items` · `object[]` · yes · 1–200 items, then "Each item:" `target
   string · required · ≤ 64 chars — room#id, storey#id, …`, `props object · required`, `props.code string · ≤ 64
   chars — a room's number (G.01) or a storey's code`, `props.name string · ≤ 80 chars`, `props.type string · ≤ 64
   chars — a room's type …`; then `dry_run`, `request_id`. Scroll to "What it never does" → the line "set_properties
   sets the code, name and type of rooms … in batches of up to 200 as one undo step. It never applies part of a
   batch … may also travel in the project log." Narrow the window to phone width → the page does not scroll sideways.
2. In a terminal: `claude mcp add --scope user truebex -- node "X:\Truebex-autopilot\t103-pf12e-the-mcp-package-the-develo\packages\mcp\truebex-mcp.mjs"`,
   start `claude`, run `/mcp` → `truebex` connected with 21 tools, `set_properties` among them, no `propose_variants`.
3. With no Truebex running, ask "use the truebex set_properties tool to number rooms room#3 and room#4 as G.01 and
   G.02" → the tool answers "Truebex is not running, or Agent connections are off …" (`app_not_running`). Then
   `claude mcp remove --scope user truebex`.
4. The project log (no browser): in `server\`, `.venv\Scripts\python.exe -m pytest -q tests\test_pf12e_agent_interface.py`
   → 8 passed (a `set_properties` action accepted and pulled back byte-equal; 201 items refused on
   `ops[0].action.args.items`; `remove` beside it refused; the page's line).

## Risks / traps

* The PC's app checkout (37d98cec) is behind the app's GitHub `main`: a `sync-mcp.ps1` run without `-AppRepo` would
  copy 1.3.0 back. Re-sync from the snapshot (or from the checkout once it has 2c842b8f1).
* The log's own 64 KiB action cap (`ops.MAX_ACTION_BYTES`, measured on ASCII-escaped JSON; not a contract limit): a
  200-item batch at every maximum fits when its strings are ASCII (65 357 B with 64-character targets), and 200 rooms
  with Arabic names up to 37 characters fit; longer non-ASCII batches (up to 267 957 B) answer 422 on `ops[i].action`.
  A writer splits such a batch (proposal 3 below).
* The page's count is filled at build time: a re-sync needs a rebuild (the verify gate builds) before the site shows it.
* Write a Windows path in a doc with forward slashes or check the bytes: a tool escape has turned a backslash-a into
  BEL before (CLAUDE.md).

## As-built

* **Date, branch, commits:** 2026-11-09, `ap/t103-pf12e-the-mcp-package-the-develo` (base `master` at 61ac33a);
  commits listed by `git log master..` on the branch: the tests first (9821222), the copy (53e66eb), the log, the page
  copy and the package README (904a358), this doc with the tracker row, the README section and PF12d's line.
* **Copied** by `scripts/sync-mcp.ps1 -AppRepo X:/Truebex/.autopilot/manager/app-main-2c842b8f`: the manager's
  read-only export of the app's GitHub `main` 2c842b8f1 (merge T214, 2026-11-09 14:32 UTC; `git archive` with
  `core.autocrlf=false`, run 305). Read through the snapshot because the PC's app checkout is still at 37d98cec
  (2026-10-28, agent-interface 1.3.0) and has no 2c842b8f1 (`git log -1 main` there, read-only); every snapshot file
  equals its `SNAPSHOT.txt` id (`git hash-object --no-filters`), and so does every copy here. `tools.json` 1.3.0 →
  1.4.0 (63 635 → 66 077 B, blob a006ae84) into `packages/mcp/` and `src/content/`; `instructions.md` (+1 line:
  "set_properties numbers, renames or retypes up to 200 rooms … in ONE call and one undo step", 2 175 → 2 334 B,
  blob 42bcd2eb); `test/mcp.test.mjs` (`PL1_TOOLS`, `MCP_TOOLS` with it, the file's order, `tools/list` length 21 in
  two asserts, 15 254 → 15 373 B, blob 15e4cd9c). Unchanged (the script copied them byte-equal): `truebex-mcp.mjs`,
  `lib/*.mjs` (`SERVER_VERSION` still 1.0.0), `test/fake-app.mjs`, `helpers.mjs`, `zip.mjs`, the three wire scripts
  (tree 744f2c7f). The first 21 tools of 1.4.0 equal 1.3.0's (MINOR: one appended). Not copied: `manifest.json`,
  `truebex.mcpb` (PF12b deviation 3).
* **Counts:** `tools.json` 1.4.0, 22 tools, 21 on the mcp surface, 2 with `requires`, 7 log-safe edits; 161 top-level
  arguments on the mcp surface. The page: 21 tool sections (PF12d 20), 161 argument rows (158 + 3), 19 nested lists
  with 113 fields (18 / 108 + `set_properties`' five), 3 resources, 16 error codes, the description 143 characters.
  The app's node tests: 10 passed, 0 failed of 11 declared (`mcp-bundle-manifest` filtered; 1.4.0 added two asserts,
  no test). pytest 983 → 991 collected (8 new; 4 package tests, 1 site test, 1 PF12c test and PF12d's log-safe set
  changed).
* **Tests first:** on `master` 61ac33a with `out/` built from it, the five files gave 16 failed, 17 passed:
  `test_mcp_package_stdio_framing` (20 == 21), `…_discover_and_legacy_initialize` and `…_tools_list_and_replay` (20
  names, not `MCP_ORDER`), `test_tools_json_follows_the_contract` (1.3.0 < 1.4.0), `test_mcp_package_install_notes`
  (no "every tool the app lists"), PF12c's `test_log_safe_tools_follow_tools_json` (six ≠ seven) and
  `test_docs_generator_keeps_the_mcp_surface` (20 tools ≠ `MCP_ORDER`), `test_docs_generated_from_tools_json` (20
  sections), and all eight new ones (the log answers `'set_properties' is not a log-safe tool` on `ops[0].action.tool`;
  `LOG_SAFE_TOOLS` ends `apply_theme`, `set_tunable`; no `set_properties` in `instructions.md`, for the generator or
  on the page). `test_mcp_package_app_node_tests` passed there and here (it counts the copied file's tests).
* **Self-test, real processes:**
  * **Live, a local API** (uvicorn on :28103, scratch SQLite, a throwaway signing key; scratch `selftest.sh` +
    `live_pf12e.py`): `/auth/register` 201; `demo_replica.py login --trial` → "Pro trial started (ends
    2026-11-23T15:28:43Z)", plan pro; `POST /projects` 201; push a person's `set_properties` (G.01) → 200 `accepted`
    seq 1; an agent's batch (G.02 with an Arabic name, G.03 Kitchen) → `accepted` seq 2; an API key on
    `/v1/projects/{id}/ops` → `accepted` seq 3; pull → head 3, each action byte-equal (`byte-equal=True` ×3, touched
    1, 2, 1); then `create_layout` → 422 `ops[0].action.tool: 'create_layout' is not a log-safe tool (place, move,
    resize, fill, apply_theme, set_tunable, set_properties)`; `set_properties` + `remove` → 422 `ops[1].action.tool`;
    201 items and an items object → 422 `ops[0].action.args.items: set_properties takes 1 to 200 items, each an
    object`; head still 3. `LIVE PASS`.
  * **The copied bridge over stdio** as Claude Code drives it (`bridge_pf12e.py`, scratch LOCALAPPDATA):
    `initialize` 2025-06-18 → serverInfo truebex 1.0.0; `tools/list` 21, `set_properties` last, `_meta` only
    `permission`, no `propose_variants`; `tools/call set_properties` → `isError`, `app_not_running` ("Truebex is not
    running, or Agent connections are off …"); exit 0 16 ms after stdin EOF.
  * **Headless Edge** (CDP, `serve-out.py` on the built `out/`; `cdp_pf12e.mjs`) at 1280 × 900 and 390 × 844: 24/24 —
    21 visible sections ending `set_properties`, one h1, "21 tools" in the description, `items` / `dry_run` /
    `request_id` rows, `items` `object[]` · yes · 1–200 items, "Each item:" with the five lines, no empty type, no
    "undefined" or "[object Object]", "Also travels in the project log", the never-list line, the item list as wide
    as its table (768 / 704 px), no page-wide horizontal scroll on the phone (the table scrolls in its box), no
    console errors bar `serve-out.py`'s `__next.*.txt` prefetch 404s. Screenshots checked by eye.
  * **Postgres 17.10** (throwaway `initdb` cluster, `timezone = 'Asia/Baghdad'`, two database pairs,
    `TEST_APP_DATABASE_URL` and `TEST_DATABASE_URL`): `test_pf12e_agent_interface.py`, `test_pf12d_…`, `test_pf12c_…`,
    `test_pf12_mcp_package.py`, `test_site_pf12.py`, `test_pf12_api.py` — 43 passed in 32 s; `test_projects.py`,
    `test_projects_orgs.py`, `test_pf4a_project_log_1_1.py`, `test_pf4b_project_log_1_2.py`, `test_mobile.py` — 73
    passed in 102 s (the app's 92 tables in both databases).
  * **The verify gate** (`scripts/autopilot-verify.ps1` with an absolute `-File` path: lint, build, pytest on SQLite,
    the `out/` check): GREEN in 581 s, 991 collected, 972 passed and 19 skipped (the Postgres-only tests), pytest 529 s.
* **Deviations from the brief and why:**
  1. *The item list* reads `props.code` under the `items` row's "Each item:", not `items[].props.code` (Decision
     above); the tests check the full paths through `_walk` and the page's lines.
  2. *The page copy* went where PF12d's creation lines are ("What it never does"): it says what a batch never does
     (apply part of itself) beside what it does.
  3. *Shared files:* `DEVELOPER_DOCS.pages.mcp.safety` edited in place (one line; no new export); the root README one
     section at its end; no `openapi/` or SDK change.
* **Not changed, and why:** `src/viewer/actions.ts`, `mobile/android/lib/actions/actions.dart` (light clients write
  only the tools they have UI for; none numbers rooms); `src/lib/developer-docs.ts` and the page component
  (`nestedFields()` already reads an object inside an array item); `server/app/ai/` (the proxy pins no tool name or
  count, `MAX_TOOLS` 64 ≥ 22); `package.json` 1.0.0 (= `SERVER_VERSION`, which did not move); the copied bridge.
* **Carry-over for the app half (fix in the app repo first, then `scripts/sync-mcp.ps1`):**
  1. `lib/server.mjs:21` `SERVER_VERSION` is still 1.0.0 (and `manifest.json`) while `tools.json` went 1.2.0 → 1.3.0
     → 1.4.0 (PF12c carry-over 4, PF12d carry-over 1, again): bump it with a MINOR tools change (1.4.0), so
     `serverInfo.version` and the npm version say which tools a bridge serves; `package.json` follows (the test holds
     them equal).
  2. `set_properties` in the file matches §5.27 (no difference found: items 1–200, target ≤ 64, code ≤ 64, name ≤ 80,
     type ≤ 64, all closed; output `ok`, `set`, `changed`, `undo_step`, `text`).
  3. `find` (§5.5): the 1.4.0 match fields (`uid`; a room's `code`, `type`, `area_m2`, `level`; a wall's `width_mm`,
     `length_mm`; a storey's `code`, `level`, `elevation_mm`) are in the contract's text only: the file's `find`
     output schema keeps `matches` as bare objects (they conform) and its description still ends "to pass to explain,
     place, move, resize and fill". Name them in the output schema's `matches.items.properties` (or the description)
     and add `set_properties` to that list (PATCH). (The brief calls this §5.2; the contract numbers `find` 5.5.)
  4. PF12d's carry-overs 2–5 are unchanged in 1.4.0 (`write_sheet_text` without `limits`, `create_object`'s one
     candidate and optional `size_mm`; the repair count worded two ways; §1's "thirteen" and §6.5's `"version":
     "1.1.0"`; PF12c's three `get_tunables` notes).
* **Contract proposals (for the owner to write; nothing changed from here):**
  * **§11 platform cells:** `set_properties` → "PF12e (docs): done"; `tools/list` → "PF12e (package, docs): done (21
    on the mcp surface)"; PF12c's and PF12d's cell proposals still stand.
  * **§3 / `lib/server.mjs`:** carry-over 1 (the `SERVER_VERSION` line: "SERVER_VERSION follows tools.json's MAJOR.MINOR").
  * **`project-log.md` PATCH** (1.2.2): §6.2 could name the log-safe tools it means, "`place` (objects and products),
    `move`, `resize`, `fill`, `apply_theme`, `set_tunable` (1.1.0) and `set_properties` (agent-interface 1.4.0)", and
    say an action is at most 64 KiB of JSON on the platform, so a writer splits a larger `set_properties` batch (see
    Risks). Today §6.2 points at agent-interface §5's log-safe rows, which is enough to follow.
* **Owner steps (unchanged):** `npm login` with the `@truebex` organisation, `npm publish --access public` in
  `packages/mcp`, then `mcpPublished: true` in `src/lib/constants.ts`.
* **Cut:** nothing from the scope.
