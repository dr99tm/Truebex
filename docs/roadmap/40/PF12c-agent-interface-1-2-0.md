# PF12c — The MCP package, the developer docs and the project log follow agent-interface 1.2.0 (launch priority 2)

**Needs merged:** PF12b (on `master` through T70), PF4 (the project log); app: TU1 with AI1 (merge T165, app `main`
4937eee6, 2026-10-13 08:57 UTC) and AI2 (merge T170, app `main` 7caa26aa2, 2026-10-13 13:57 UTC). **Unblocks:**
publishing `@truebex/mcp` with the app's current tools (owner). **Contract:**
`T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\agent-interface.md` 1.2.0 (§3 *Changes* 1.1.0 and
1.2.0, §5.17, §5.18, §5.19, §6.3, §6.5, §9, §11) and `project-log.md` §6.2; no change from the platform (the §11 cells
and two proposals are in As-built).

## Status

**Built 2026-10-14** on `ap/t73-pf12c-the-mcp-package-the-develo` (base `master` at 988334f). The package and
`src/content/tools.json` are the app's `tools.json` 1.2.0 (14 tools, 13 on the mcp surface); `/developers/mcp/` documents
those 13 and never `propose_variants`; the project log takes `set_tunable` as a log-safe action. Waiting on others: the
app-side carry-overs and contract proposals in As-built; npm publishing (owner, unchanged from PF12).

Before this task, verified on `master` 988334f against the app's `main` 7fe6b2c2 (its `Tools/mcp/` last changed by
T170's merge commit 976ec950):

| Area | Where | Before |
|---|---|---|
| Copy | `packages/mcp/tools.json`, `src/content/tools.json` | PF12b's copy of app `main` 90799860: `tools.json` 1.0.0, 11 tools (PF12b As-built *Counts*) |
| Bridge | `packages/mcp/lib/schema.mjs`, `instructions.md`, `test/mcp.test.mjs` | no `SURFACES` / `surfacesOf()`; `publicTools()` lists every tool; 9 node tests run here |
| Tests | `server/tests/test_pf12_mcp_package.py:315`, `:565-578` | `len(tools) == 11`; an 11-name `CONTRACT_ORDER`; every tool's surfaces ⊇ {mcp, assistant}; log-safe = the five §5.7–5.11 edits |
| Log | `server/app/projects/ops.py:51` | `LOG_SAFE_TOOLS` = place, move, resize, fill, apply_theme: a `set_tunable` action answers 422 |
| Docs | `src/lib/developer-docs.ts` `toolsDocument()`, `src/app/developers/mcp/page.tsx` | every tool of the file gets a section (`propose_variants` would too); an argument without `type` showed `any`; the never-list said "change settings" flatly; "eleven tools" in `DEVELOPER_DOCS.pages.mcp` and `packages/mcp/README.md` |

## Goal

The MCP server a developer installs from the platform, the page that documents it and the project log all say what
the app says since agent-interface 1.2.0: an MCP client sees 13 tools (TU1's `get_tunables` and `set_tunable` among
them), the page explains the one kind of setting an agent may now change, the in-app assistant's `propose_variants` is
nowhere on MCP or its docs, and a light client may write a `set_tunable` action to the project log.

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4, C.9 (the app side is authoritative); PF12's and PF12b's docs.
* `agent-interface.md` 1.2.0 in full: §3, §5.17–5.19, §6.3, §6.5, §9, §11; `project-log.md` §6.2.
* The app's `Tools/mcp/lib/schema.mjs` (read only). Here: `scripts/sync-mcp.ps1`, `server/app/projects/ops.py`,
  `src/lib/developer-docs.ts`, `src/app/developers/mcp/page.tsx`, `DEVELOPER_DOCS.pages.mcp`.
* Skills: `truebex-brand-voice` (the page's words), `truebex-seo` (a public page changes).

## Scope

**In:**
1. `scripts\sync-mcp.ps1` against the app's `main` (7caa26aa2 or later; ran at 7fe6b2c2): the copies committed
   byte-equal; `manifest.json` and `truebex.mcpb` still not copied (PF12b deviation 3); `package.json`'s version stays
   the bridge's `SERVER_VERSION` (1.0.0).
2. `ops.LOG_SAFE_TOOLS` gains `set_tunable` (agent-interface 1.1.0 §5.18).
3. `/developers/mcp/`: only the tools whose surfaces include `mcp` (absent = both); an argument without a type rendered
   readably; the never-list follows §6.3; the counts follow.
4. Tests first (each failing on `master`), the package README, this doc, the tracker row, one line in PF12b's carry-over,
   a README section.

**Out (and where it goes):**
* Any change to the bridge, `tools.json` or the node tests → the app (AI1 / TU1 / AI2), then `sync-mcp.ps1`
  (carry-overs in As-built).
* A `touched` key for a tunable, `SERVER_VERSION`, the §11 cells → the owner (proposals in As-built).
* `src/viewer/actions.ts`, `mobile/android/lib/actions/actions.dart` → unchanged: light clients write only the tools
  they have UI for, and neither has a tunable control.
* Publishing `@truebex/mcp` → the owner (PF12's steps).

## Design

### API

No endpoint changes. `POST /projects/{id}/ops` (and its `/v1` mirror) accepts an `action` operation whose `tool` is
`set_tunable`, with the same checks as every log action: `args` an object, `permission` `edit`, `session` and
`request_id` 32 hex, at most 64 KiB. `touched` is what the writer sends: the refs in the arguments (§6.2), none for
`set_tunable`, so it is `[]` and never conflicts. The platform does not invent a key (proposal in As-built).
`get_tunables` (a read) and `propose_variants` (`logSafe: false`) stay refused: 422 `validation_failed`,
field `ops[i].action.tool`, the message listing the six log-safe tools. The action's shape is unchanged (`tool` is a
string in `openapi/v1.json` and `openapi/clients.json`), so no generated document or client type changes.

### Data

None. `src/content/tools.json` and `packages/mcp/tools.json` are the app's file (32 524 B, LF).

### UI

| Where | What changes |
|---|---|
| `src/lib/developer-docs.ts` | `Tool._meta` gains the optional `com.truebex/surfaces` (never rendered); `mcpTools()` keeps a tool whose surfaces include `mcp` or that has none; `toolsDocument()` returns only those |
| `src/app/developers/mcp/page.tsx` | `argumentType()`: an argument with no `type` / `enum` / `const` shows `DEVELOPER_DOCS.pages.mcp.untypedTypes["<tool>.<argument>"]`, else `untypedFallback` ("any"); "Also travels in the project log" only for a log-safe **edit** (the app's file marks the read `get_tunables` logSafe) |
| `DEVELOPER_DOCS.pages.mcp` | "thirteen tools" (meta description 149 characters, Claude Code note); `untypedTypes` `{"set_tunable.value": "number \| boolean \| string"}` (§5.18's "a number, a boolean or a string"), `untypedFallback`; the never-list: "run console commands" moves into the first rule, a new rule "It cannot change settings, with one exception: a tunable, which set_tunable sets by name. A tunable is typed and range-checked, a Design tunable (one that changes the picture or the drawing) is one undo step, and setting one is never a console command."; "Every edit to the project is one undo step" (a non-Design tunable is a plain set) |
| `packages/mcp/README.md` | thirteen tools; `get_tunables` (read) and `set_tunable` (edit) in the tool list; the settings exception |

**Decision:** the untyped value's words are page copy keyed by `tool.argument`, like `requiresText`. Rejected: deriving
"number | boolean | string" from the description (free text), and leaving "any" (true of JSON Schema, but less than
§5.18 says).

### Security and privacy

* The app repository is only read (`sync-mcp.ps1` reads; the blob ids were compared from inside the worktree).
* The page states what the app enforces (§6.3): no settings but a tunable, never a console command.

## Deliverables

- [x] The copies from the app's `main` 7fe6b2c2: `tools.json` (package and site), `instructions.md`, `lib/schema.mjs`, `test/mcp.test.mjs` (the rest unchanged, every file equal to its blob)
- [x] `server/app/projects/ops.py` (`LOG_SAFE_TOOLS`)
- [x] `src/lib/developer-docs.ts` (`mcpTools`, `toolsDocument`), `src/app/developers/mcp/page.tsx`, `DEVELOPER_DOCS.pages.mcp`
- [x] `packages/mcp/README.md`
- [x] Tests: `test_pf12_mcp_package.py` (5 changed), `test_site_pf12.py` (1 changed), `test_pf12c_agent_interface.py` (6 new)
- [x] This doc, the tracker row, PF12b's carry-over line, a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_tools_json_follows_the_contract` | pytest | version ≥ 1.2.0 (1.x); §5's 14 names ending `get_tunables`, `set_tunable`, `propose_variants`; classes (read, edit, edit); surfaces absent or a non-empty subset of {mcp, assistant}, `propose_variants` exactly `["assistant"]`, every other tool both; log-safe edits = place, move, resize, fill, apply_theme, set_tunable, each with `dry_run`; `propose_variants` logSafe false; `set_tunable.value` with no `type` and no `pattern`; `get_tunables` limits (40, 80, 1–500 default 200); `requires` only on apply_theme (PR2) and export_panorama (PR3); the portable walk reaches `propose_variants`' nested calls, which are fill / place / move / resize's own arguments minus `dry_run` and `request_id` |
| `test_mcp_package_stdio_framing` | pytest (node) | the `tools/list` length is the mcp-surface count (13), not a literal |
| `test_mcp_package_discover_and_legacy_initialize` | pytest (node) | the legacy list is §5's order without `propose_variants` |
| `test_mcp_package_tools_list_and_replay` | pytest (node) | `tools/list` = the mcp-surface tools without the private `_meta` (13); `propose_variants` → `-32602` with no app and with the fake app linked, which never sees it (`calls=1`) |
| `test_mcp_package_app_node_tests` | pytest (node) | the app's node tests: 10 pass (`mcp-bundle-manifest` filtered out), `mcp-assistant-only-hidden` among them (it covers `propose_variants` unlisted and `-32602` too) |
| `test_docs_generated_from_tools_json` | build check | 13 sections in the file's order, none for `propose_variants`, whose name is in no file under `out/developers/mcp/`; no empty or "undefined" type cell; `set_tunable.value` reads "number \| boolean \| string" beside its description; `get_tunables` limit "1 to 500; default 200", feature ≤ 40 and query ≤ 80 chars; "Also travels in the project log" on the six log-safe edits only |
| `test_project_log_accepts_set_tunable_action` | pytest | `{tool: set_tunable, args: {name: "cad.Light.SunIntensity", value: 7}, permission: edit}` accepted from a session, pulled as written with `touched` `[]`; a `reset` too |
| `test_project_log_refuses_get_tunables_and_propose_variants` | pytest | both refused 422 on `ops[0].action.tool`, nothing stored |
| `test_project_log_set_tunable_touches_nothing` | pytest | two replicas set one knob from base 0: both accepted (no invented key); two moves of one wall from one base: the second rejected |
| `test_log_safe_tools_follow_tools_json` | pytest | `ops.LOG_SAFE_TOOLS` = `tools.json`'s log-safe edits in §5's order |
| `test_docs_generator_keeps_the_mcp_surface` | pytest (node, types stripped) | `mcpTools()` keeps absent / `["mcp"]` / both, drops `["assistant"]` and `[]`; `toolsDocument()` gives the 13 |
| `test_docs_never_list_follows_the_contract` | build check | the never-list: settings off-limits except a tunable through `set_tunable`, typed and range-checked, one undo step for a Design tunable, never a console command; console commands named |

## Human test

Launch: in the worktree, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` (serves
`out/` on `http://127.0.0.1:3173/`). No local API is needed for the page or the MCP server; step 5 uses the pytest.

1. Open `http://127.0.0.1:3173/developers/mcp/` → the description and the Claude Code note say "thirteen tools"; under
   Tools, `tools.json 1.2.0` and 13 sections ending `get_tunables` (List the tunables, Class: read, no "Also travels in
   the project log") and `set_tunable` (Set one tunable, Class: edit · Also travels in the project log). In
   `set_tunable`'s table the `value` row's Type reads `number | boolean | string` and its Description "the new value: a
   number, true / false, an option name or #RRGGBB (exactly one of value, reset)"; in `get_tunables`' table `limit`
   reads `int`, "1 to 500; default 200".
2. Find in page "propose_variants" → no match. Scroll to "What it never does" → "It cannot change settings, with one
   exception: a tunable, which set_tunable sets by name. A tunable is typed and range-checked, a Design tunable (one that
   changes the picture or the drawing) is one undo step, and setting one is never a console command."
3. Narrow the window to phone width (or the browser's device view at 390 px) → the page does not scroll sideways; the
   tool tables scroll inside their box.
4. In a terminal: `claude mcp add --scope user truebex -- node "X:\Truebex-autopilot\t73-pf12c-the-mcp-package-the-develo\packages\mcp\truebex-mcp.mjs"`,
   start `claude`, run `/mcp` → `truebex` is connected with 13 tools (`get_tunables` and `set_tunable` listed, no
   `propose_variants`). With no Truebex running, ask "use the truebex get_tunables tool to list the Light tunables" →
   the tool answers "Truebex is not running, or Agent connections are off …" (`app_not_running`). Then
   `claude mcp remove --scope user truebex`.
5. The project log (local API, no browser): in `server\`, `.venv\Scripts\python.exe -m pytest -q tests\test_pf12c_agent_interface.py`
   → 6 passed (`set_tunable` accepted, `get_tunables` and `propose_variants` refused on `ops[0].action.tool`).

## Risks / traps

* The app's `Tools/mcp/` is LF by its own `.gitattributes`; its `Docs/roadmap/fixtures/contracts/agent/*.jsonl` come
  out CRLF on the app's checkout, so `git status` shows the three scripts modified after a sync until `git add`
  normalises them (same blobs: compared with `git hash-object`).
* `toolsDocument()` filters: a later page that needs the whole file (the assistant's tools) must read it itself.
* The app's file marks `get_tunables` logSafe: anything that reads `logSafe` alone (the page did) would say a read
  travels in the log. Pair it with the class, as the page and `ops.LOG_SAFE_TOOLS` now do.
* PowerShell 5.1 splits a `git commit -m` here-string that contains double quotes into pathspecs: commit with `-F`.

## As-built

* **Date, branch, commits:** 2026-10-14, `ap/t73-pf12c-the-mcp-package-the-develo` (base `master` at 988334f); commits
  listed by `git log master..` on the branch: the tests first, then the sync with the log and the page, the
  project-log line on the page, and this doc with the tracker row.
* **Copied** by `scripts\sync-mcp.ps1` from the app's `main` 7fe6b2c2 (contains 7caa26aa2; `Tools/mcp/` last changed
  by 976ec950, T170's merge; the working tree had no change against `main` there): `tools.json` 1.0.0 → 1.2.0
  (22 426 → 32 524 B) into `packages/mcp/` and `src/content/`, `instructions.md` (+1 line on the tunable tools,
  1 535 B), `lib/schema.mjs` (`SURFACES`, `surfacesOf()`, `publicTools()` filtered by the mcp surface, the surfaces check
  in `toolsFileProblems()`; 7 475 B), `test/mcp.test.mjs` (13 tool names, `mcp-assistant-only-hidden`; 14 366 B).
  Unchanged: `truebex-mcp.mjs`, `lib/jsonrpc.mjs`, `lib/server.mjs`, `lib/wire.mjs`, `test/fake-app.mjs`,
  `test/helpers.mjs`, `test/zip.mjs`, the three wire scripts. Every copy equals its blob on the app's `main`
  (`git hash-object`; the scripts after LF normalisation). Not copied: `manifest.json`, `truebex.mcpb` (PF12b deviation 3).
* **Counts:** `tools.json` 1.2.0, 14 tools, 13 on the mcp surface, 2 with `requires`; the page: 13 tool sections (PF12b
  11), 92 argument rows (PF12b 83; +4 `get_tunables`, +5 `set_tunable`), 3 resources, 16 error codes. The app's node
  tests: 10 passed, 0 failed (PF12b 9; `mcp-bundle-manifest` still filtered out). pytest 718 → 724 collected (the 6 new
  tests; 5 package tests and 1 site test changed). The package, site and PF12c files: 22 passed, then with
  `test_projects.py` and `test_mobile.py` 63 passed + 1 skipped on SQLite.
* **Tests first:** on `master` 988334f with `out/` built from it, 11 failed: `test_mcp_package_discover_and_legacy_initialize`
  (11 names listed, not §5's 14 less `propose_variants`), `test_mcp_package_tools_list_and_replay` (11 == 11 − 1),
  `test_mcp_package_app_node_tests` (9 run), `test_tools_json_follows_the_contract` (1.0.0), `test_docs_generated_from_tools_json`
  (11 sections) and all 6 new ones (`set_tunable` 422 "is not a log-safe tool (place, move, resize, fill, apply_theme)",
  no `mcpTools` export, the never-list without "run console commands"). `test_mcp_package_stdio_framing` passed there
  (11 = the old file's mcp count) and is now a count, not a literal. The project-log line on the page was found by the
  headless run below; its assertion failed on that build before the fix.
* **Self-test, real processes:**
  * The copied bridge over stdio (`selftest_bridge_pf12c.mjs` in the session scratchpad, from T63/T70's): with the
    copied fake app found through a scratch `LOCALAPPDATA` instance file, `tools/list` 13 (ending `get_tunables`,
    `set_tunable`; `value` untyped), `get_tunables {feature: "Light", limit: 20}` and `set_tunable {name:
    "cad.Light.SunIntensity", value: 7, dry_run: true}` relayed (`fake app saw calls=[get_tunables, set_tunable]`),
    `propose_variants` → `{"code": -32602, "message": "Unknown tool: propose_variants"}` and never relayed; with no app,
    the same 13 listed, both tunable calls `app_not_running`, `propose_variants` −32602; both bridges exit 0 within
    40 ms of stdin EOF.
  * **Headless Edge** (CDP, `serve-out.py` on the built `out/`; `cdp_pf12c_page.mjs`) at 1280 × 900 and 390 × 844: one
    h1, 13 visible sections with their classes, 92 visible argument rows, no empty or "undefined" type cell, no
    `propose_variants` in the DOM, the `value` row "number | boolean | string" (2 lines on the desktop, 3 at 390 px, broken
    only at spaces), the settings rule shown, no page-wide horizontal scroll on the phone (the tables scroll in their
    box). Console errors: only `serve-out.py`'s known `__next.*.txt` prefetch 404s. The first run showed "Class: read ·
    Also travels in the project log" on `get_tunables` (fixed above).
  * **Postgres 17** (throwaway `initdb` cluster, `timezone = 'Asia/Baghdad'`, `TEST_APP_DATABASE_URL`):
    `test_pf12c_agent_interface.py`, `test_projects.py`, `test_mobile.py` — 48 passed in 107 s.
* **Deviations from the brief and why:**
  1. *`get_tunables` is marked `logSafe: true` in the app's file* (§5 and 1.1.0's *Changes* line make it read only). The
     contract test asserts the log-safe **edit** tools equal the six and allows only `get_tunables` as a log-safe read;
     `ops.LOG_SAFE_TOOLS` and the page use the edit ones. Carry-over 1.
  2. *`get_tunables`' output schema has no `ok` and requires nothing* (§5.17's result has no `ok`; §6.5 says output
     schemas require exactly `ok`). The test allows that for `get_tunables` only, and still checks a §7 error conforms.
     Carry-over 2.
  3. *`propose_variants` has no `request_id`*: §5.19's signature has none and it never travels over MCP or in the log, so
     the `request_id` check applies to the edit and export tools on the mcp surface.
  4. *The page's project-log line* ("Also travels in the project log") is now shown for log-safe edits only, beyond the
     brief, because the app's `get_tunables` flag would otherwise put a read on it (found by the headless run).
  5. *Untyped arguments*: the type cell reads the page's own words (`untypedTypes`, "number | boolean | string" from
     §5.18), not the description's "any of: …" wording; any other untyped argument would read "any".
  6. *Shared files:* `DEVELOPER_DOCS.pages.mcp` is edited in place (it is the page's copy; no new export);
     `server/app/projects/ops.py` one tuple and its comment; the root README gains one section at its end (PF12b's
     section does not name the tool count and is left as it is).
* **Not changed, and why:** `src/viewer/actions.ts` and `mobile/android/lib/actions/actions.dart` (light clients write
  only the tools they have UI for; neither has a tunable control, and their own checks keep refusing other tools);
  `openapi/v1.json`, `openapi/clients.json`, `src/lib/api-clients.d.ts` (the action's `tool` is a plain string; nothing
  in the shape changed); `package.json` 1.0.0 (= `SERVER_VERSION`, which did not move).
* **Carry-over for the app half (fix in the app repo first, then `scripts\sync-mcp.ps1`):**
  1. `Tools/mcp/tools.json` `get_tunables` `_meta.com.truebex/logSafe: true` → `false` (PATCH): §5 makes it read only and
     a read never travels in the log (`project-log.md` §6.2 names log-safe edits). The platform ignores the flag on a read.
  2. `get_tunables`' result and output schema have no `ok` (§5.17), while §6.5 says output schemas list `ok` as their
     one required key: add `ok: true` and `required: ["ok"]` (MINOR, a result field added), or say in §6.5 that a read's
     result may omit `ok`.
  3. `get_tunables`' description starts "List the runtime knobs (tunables, roadmap 40 / TU1)": a planning id reaches
     every MCP client and the public page (PATCH: drop "roadmap 40 / TU1").
  4. `lib/server.mjs:21` `SERVER_VERSION` is still 1.0.0 (and `manifest.json` `version` 1.0.0) although `tools.json` went
     1.0.0 → 1.2.0 and `tools/list` now filters by surface: bump it with a MINOR tools change (1.2.0, or 1.1.0 for the
     bridge's own change), so `serverInfo.version` and the npm version say which tools a bridge serves.
     `package.json` follows the bridge (the test holds them equal).
  5. PF12b's carry-overs 1–3 (`server.mjs:40` hex entity ids, `-32603` on `resources/read`, `manifest.json`'s licence)
     are unchanged in 1.2.0's bridge.
* **Contract proposals (for the owner to write; nothing changed from here):**
  * `project-log.md` §6.2: `set_tunable` has no ref, so its `touched` is empty and two replicas setting one knob never
    conflict (the later `server_seq` wins on every replica). If they should conflict, give a tunable a `touched` id:
    proposed `tunable#<name>` mapped to 32 hex as `sha256("tunable#" + lower(name))[:32]` (§6.2's `touched` is 32 hex),
    written by every writer and compared by the server unchanged. Or write in §6.2 that tunables are last-writer-wins.
  * **§11 platform cells:** `get_tunables`, `set_tunable` → "PF12c (docs): done"; `tools/list` → "PF12c (package,
    docs): done (13 on the mcp surface)"; `propose_variants` → "— (never on MCP; PF12c: not on /developers/mcp/,
    refused by the project log)". PF12b's §6.5 `additionalProperties` and §9 proposals still stand.
* **Owner steps (unchanged):** `npm login` with the `@truebex` organisation, `npm publish --access public` in
  `packages\mcp`, then `mcpPublished: true` in `src/lib/constants.ts`.
* **Cut:** nothing from the scope.
