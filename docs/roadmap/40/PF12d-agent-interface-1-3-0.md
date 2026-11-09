# PF12d — The MCP package and the developer docs follow agent-interface 1.3.0 (launch priority 2)

**Needs merged:** PF12c (on `master` through T78); app: AI5 "creation with AI" (merge T183, app `main` 319fed6f8,
2026-10-21 23:35 UTC; `Tools/mcp/` last changed by b245af49e). **Unblocks:** publishing `@truebex/mcp` with the app's
current tools (owner). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\agent-interface.md`
1.3.0 (app commit b43d108c6: §3 *Changes* 2026-10-21, §5.20–5.26, §6.3, §6.5, §10's `ai5-*` rows, §11) and
`project-log.md` §6.2; no change from the platform (the §11 cells and proposals are in As-built).

## Status

**Built 2026-10-22** on `ap/t95-pf12d-the-mcp-package-and-the-de` (base `master` at fdfa389: d222f29 and the brand folder, docs only). The package and
`src/content/tools.json` are the app's `tools.json` 1.3.0 (21 tools, 20 on the mcp surface); `/developers/mcp/`
documents those 20, AI5's six creation skills and the scoped `remove` among them, with one row per top-level argument
and every nested field listed under its row, and says what a creation call does. The project log still takes only the
six log-safe edits. Waiting on others: the app-side carry-overs and contract proposals in As-built; npm publishing
(owner, unchanged from PF12).

Before this task, verified on `master` fdfa389 (d222f29 plus `docs/brand/`) against the app's `main` 7fdde1e6f (contains 319fed6f8):

| Area | Where | Before |
|---|---|---|
| Copy | `packages/mcp/tools.json`, `src/content/tools.json` | PF12c's copy of app `main` 7fe6b2c2: `tools.json` 1.2.0, 14 tools, 13 on the mcp surface |
| Copy | `packages/mcp/instructions.md`, `test/mcp.test.mjs` | without AI5's line on creating; `tools/list` length 13, no `AI5_TOOLS` |
| Tests | `server/tests/test_pf12_mcp_package.py:33-41`, `:398`, `:609`; `test_site_pf12.py:112`; `test_pf12c_agent_interface.py:129` | a 14-name `CONTRACT_ORDER` and class sets without the seven; "13" and "14" as literals |
| Docs | `src/app/developers/mcp/page.tsx`, `src/lib/developer-docs.ts` | an object's fields as `a.b` rows, an array of objects one `object[]` row with its items' fields nowhere; "thirteen tools" in `DEVELOPER_DOCS.pages.mcp` (`constants.ts:2850`, `:2872`) and `packages/mcp/README.md:7`, `:61` |
| Log | `server/app/projects/ops.py:52` | `LOG_SAFE_TOOLS` = place, move, resize, fill, apply_theme, set_tunable (none of the seven) |

## Goal

The MCP server a developer installs from the platform and the page that documents it say what the app says since
agent-interface 1.3.0: an MCP client sees 20 tools, AI5's `create_layout`, `create_theme`, `create_fills`,
`create_object`, `create_material`, `write_sheet_text` and `remove` among them; the page shows every argument of the
new tools readably, including the room program's rooms and an object's parts, and tells a developer what a creation
call does (nothing without `choose`, one undo step with it, sanity checks that never claim compliance, a `remove`
scoped to what the session made). The count on the page can no longer fall behind the file.

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4, C.9 (the app side is authoritative); PF12b's and PF12c's docs.
* `agent-interface.md` 1.3.0: §3, §5.20–5.26, §6.3, §6.5, §10, §11; `project-log.md` §6.2.
* Here: `scripts/sync-mcp.ps1`, `server/app/projects/ops.py`, `src/lib/developer-docs.ts`,
  `src/app/developers/mcp/page.tsx`, `DEVELOPER_DOCS.pages.mcp` in `src/lib/constants.ts`.
* Skills: `truebex-brand-voice` (the page's words), `truebex-seo` (a public page changes).

## Scope

**In:**
1. `scripts\sync-mcp.ps1` against the app's `main` (319fed6f8 or later; ran at 7fdde1e6f): the copies committed
   byte-equal (`tools.json` into `packages/mcp` and `src/content`, `instructions.md`, `test/mcp.test.mjs`; the rest
   unchanged); `manifest.json` and `truebex.mcpb` still not copied (PF12b deviation 3); `package.json`'s version stays
   the bridge's `SERVER_VERSION` (1.0.0); the copied bridge never edited.
2. Tests first (each failing on the base); the hard-coded 13 and 14 replaced so the next MINOR breaks only §5's list.
3. `/developers/mcp/`: the 20 sections from `tools.json`; nested fields shown readably; the tool count in
   `DEVELOPER_DOCS.pages.mcp` derived from the mcp tools and in `packages/mcp/README.md` checked against them; the
   creation copy where the page says what an agent may and may never do.
4. `ops.py` unchanged (none of the seven is log-safe), checked by a test.
5. A README section at its end, this doc, the tracker row, one line in PF12c's carry-over.
6. Fold-in: the developer docs' header example `project-log/1.1` → `project-log/1.2` (`constants.ts:2732`, PF4b's
   As-built, scope 7).

**Out (and where it goes):**
* AI5's human test and the app's release → the app half and the owner.
* The assistant's creation conversation through the AI proxy → PF11b (sent with this task).
* Creation on the web or Android, and any project-log `touched` key for a creation call → none: none of the seven is
  log-safe, and light clients write only the tools they have UI for (`src/viewer/actions.ts`,
  `mobile/android/lib/actions/actions.dart` unchanged).
* Marketing copy or a roadmap row about creation with AI on the website → the owner's release step.
* Any change to the bridge, `tools.json` or the node tests → the app (AI5), then `sync-mcp.ps1` (carry-overs below).
* Publishing `@truebex/mcp` → the owner (PF12's steps).

## Design

### API

No endpoint changes. `POST /projects/{id}/ops` (and `/v1/projects/{id}/ops`) keeps refusing an `action` whose `tool`
is not one of the six log-safe edits: a `create_layout`, `create_theme`, `create_fills`, `create_object`,
`create_material`, `write_sheet_text` or `remove` action answers 422 `validation_failed`, field `ops[i].action.tool`,
the message listing the six, and a push holding one is stored in no part (all or nothing). `ops.LOG_SAFE_TOOLS` is
unchanged; no generated document or client type changes.

### Data

None. `src/content/tools.json` and `packages/mcp/tools.json` are the app's file (63 635 B, LF).

### UI

| Where | What changes |
|---|---|
| `src/lib/developer-docs.ts` | `argumentRows()` (moved from the page) gives one row per top-level argument; `nestedFields()` lists an object argument's fields, or each item's fields of an array of objects, flat (deeper: `a.b` for an object, `a[].b` for an array of objects); `withToolCount()` fills `{tools}` with the number of tools on the mcp surface |
| `src/app/developers/mcp/page.tsx` | under an argument with nested fields, one row spanning the table: "Its fields:" (an object) or "Each item:" (an array of objects), then one line per field: name, type, "required", rules, description (`tr[data-fields-of]`, `li[data-field]`, `data-required`); the argument row above it loses its bottom border; the meta description, the JSON-LD and the Claude Code note count the tools from the file; `groupMetadata()` takes the computed description |
| `DEVELOPER_DOCS.pages.mcp` | `{tools} tools` in the description (143 characters) and the Claude Code note; `fieldsLabel`, `itemsLabel`, `itemRequired`; three never-list lines (below); `invalid` and `refused` name the creation cases |
| `packages/mcp/README.md` | 20 tools; AI5's seven in the tool list (edit); a creation note |

**Decision (nested fields):** one row per top-level argument, as the table's columns describe it, and every nested
field in a compact list in a full-width row right under its argument. Taken because the AI5 tools are the first with
objects inside arrays (`program.rooms[]`, `parts[]`, `blocks[]`, `cites[]`) and with four nested finish objects each
(`create_theme`, `create_fills`): as `a.b` rows `create_theme` alone had 51 rows and the rooms' fields were nowhere;
now it has 16 rows and 5 lists, and `create_layout`'s `program` row lists the program in one place (`rooms`,
`rooms[].type` … `rooms[].exterior`, `corridor_mm`, `wall_mm`, `ext_wall_mm`). The same applies to PF12b's two nested
objects (`place.product`, `fill.finish`), which move from rows into lists. Rejected: `a.b` rows plus item lists for
arrays only (two styles for one thing, 51-row sections); a list inside the description cell (too narrow at the
table's 44 rem); nested tables (heavy on a phone).

**Decision (the count):** the page's copy holds `{tools}`, filled at build time from the mcp tools of
`src/content/tools.json`, written in digits ("20 tools", the brand voice's numbers-with-units). The package README is
a static file the build cannot fill: `test_mcp_package_install_notes` checks its "N tools" and its tool list against
the file instead.

**The creation copy** (the "What it never does" list, after the tunable rule):
* "The creation tools (create_layout, create_theme, create_fills, create_object, create_material and
  write_sheet_text) take what you want as data, such as a room program, and Truebex makes the result itself. Called
  without choose, a creation tool changes nothing and returns checked candidates; called again with choose (-1 for the
  best), it applies one of them as one undo step. create_theme, create_object and create_material also keep what they
  make in your library."
* "Their checks are sanity rules (for a layout: minimum room areas and widths, door and corridor widths, a window in
  every habitable room, every room reachable), never a building-code check: no result claims compliance. A failed
  check returns its report, so your AI app can repair the request at most 3 times; then the tool stops."
* "The remove tool deletes only what this connection created. Anything else, your own walls or another connection's
  work, is refused and nothing is removed."

### Security and privacy

* The app repository is only read (`sync-mcp.ps1` reads; blob ids compared from inside the worktree).
* The page states what the app enforces (§5.20–5.26, §6.3): no change without `choose`, one undo step, `remove`
  scoped to the session; it never claims compliance.

## Deliverables

- [x] The copies from the app's `main` 7fdde1e6f: `tools.json` (package and site), `instructions.md`, `test/mcp.test.mjs` (the rest unchanged, every file equal to its blob)
- [x] `src/lib/developer-docs.ts` (`argumentRows`, `nestedFields`, `withToolCount`), `src/app/developers/mcp/page.tsx`, `src/components/developers/GroupDocPage.tsx` (`groupMetadata`'s description), `DEVELOPER_DOCS.pages.mcp`, the `project-log/1.2` example
- [x] `packages/mcp/README.md`
- [x] Tests: `test_pf12_mcp_package.py` (6 changed), `test_site_pf12.py` (1 changed), `test_pf12c_agent_interface.py` (1 changed), `test_pf12d_agent_interface.py` (3 new)
- [x] This doc, the tracker row, PF12c's carry-over line, a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_tools_json_follows_the_contract` | pytest | version ≥ 1.3.0 (1.x); §5's order from one `CONTRACT` table (name, class): the 14 of 1.2.0, then `create_layout` … `remove` (21); the seven class edit, `logSafe` false, surfaces exactly `["mcp", "assistant"]`, no `requires`, `dry_run` boolean, `request_id` string ≤ 32, output requires `ok`, no planning id in what a client sees; `destructiveHint` on `create_theme`, `create_fills`, `remove`; the six skills share `seed` (0–1 000 000), `candidates`, `choose` (−1 to candidates − 1, never required); all but `write_sheet_text` take `limits` (auto, UK, US); `program.rooms` 1–16 rooms of §5.20's ten types, areas 1–200, the program's widths; the finishes, furniture and grid of §5.21–5.22; 1–40 parts, profiles of 3–64 points; §5.24's appearance; 1–8 blocks of 1–40 lines, cites; `remove`'s 1–200 refs ≤ 64; the log-safe edits still the six |
| `test_mcp_package_stdio_framing` | pytest (node) | the `tools/list` length is the mcp-surface count and `MCP_ORDER`'s (20), never a literal |
| `test_mcp_package_discover_and_legacy_initialize` | pytest (node) | the legacy list is `MCP_ORDER` |
| `test_mcp_package_tools_list_and_replay` | pytest (node) | `tools/list` is `MCP_ORDER`; with no app `create_layout` and `remove` answer `app_not_running` (not −32602), `propose_variants` −32602; with the app's fake linked `create_layout` reaches it as written (`calls=2`) and `propose_variants` never does |
| `test_mcp_package_app_node_tests` | pytest (node) | every test the copied `mcp.test.mjs` declares but `mcp-bundle-manifest` runs and passes (10), `mcp-tools-json-valid` (AI5's classes, `create_layout`'s argument checks), `mcp-no-app` (20 listed) and `mcp-assistant-only-hidden` among them |
| `test_mcp_package_install_notes` | pytest | the package README says "20 tools" (the mcp count), names every mcp tool, no count in words, never `propose_variants` |
| `test_docs_generated_from_tools_json` | build check | 20 sections in `MCP_ORDER`, AI5's seven among them, none for `propose_variants`; one row per top-level argument (158), its type, required, rules and description; under each object or array of objects its fields (108 in 18 lists), each line name, type, required, rules, description; no "undefined", "[object Object]" or empty type; `create_layout`'s program list field by field; "20 tools" in the meta description and the Claude Code note, `{tools}` in the copy |
| `test_docs_generator_keeps_the_mcp_surface` | pytest (node, types stripped) | `toolsDocument()` gives `MCP_ORDER` |
| `test_project_log_refuses_creation_tools` | pytest | the file marks the seven edit and not log-safe; each refused 422 on `ops[0].action.tool` from a session and a device, `create_layout` and `remove` from an API key on `/v1`; a move beside a `create_layout` refused on `ops[1]` and not stored; `ops.LOG_SAFE_TOOLS` the six |
| `test_docs_generator_lists_nested_fields` | pytest (node, types stripped) | `argumentRows()` top-level only; `nestedFields()` on `program` (nine fields with `rooms[].…`), `parts`, a sample (`b.c`, `d[].e`) and nothing for other schemas; `withToolCount()` |
| `test_docs_creation_copy_follows_the_contract` | build check | the never-list: the six skill names; "Called without choose, a creation tool changes nothing and returns checked candidates"; "with choose (-1 for the best), it applies one of them as one undo step"; "sanity rules", "never a building-code check", "no result claims compliance", "at most 3 times"; "The remove tool deletes only what this connection created … nothing is removed"; the earlier rules kept; `invalid` and `refused` name the creation cases; no compliance claim on the page |

## Human test

Launch: in the worktree, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` (serves
`out/` on `http://127.0.0.1:3195/`, 3100 + the task number). No local API is needed for the page or the MCP server;
step 4 uses the pytest.

1. Open `http://127.0.0.1:3195/developers/mcp/` → the description and the Claude Code note say "20 tools"; under Tools, `tools.json 1.3.0`
   and 20 sections ending `create_layout`, `create_theme`, `create_fills`, `create_object`, `create_material`,
   `write_sheet_text`, `remove`, each "Class: edit" with no "Also travels in the project log". In `create_layout`, the
   `program` row (type `object`, required yes) is followed by "Its fields:" listing `rooms object[] · required · 1–16
   items`, `rooms[].type` with the ten room types, `rooms[].area_m2 number · required · 1 to 200 — target clear floor
   area`, … `ext_wall_mm number · 100 to 800`. In `create_object`, `parts` is followed by "Each item:". Find in page
   "propose_variants" → no match. Scroll to "What it never does" → the three creation lines of Design (no change
   without choose, checked candidates, one undo step; sanity rules, never a building-code check, no compliance claim;
   the remove tool deletes only what this connection created). Narrow the window to phone width → the page does not
   scroll sideways; the tool tables scroll inside their box.
2. In a terminal: `claude mcp add --scope user truebex -- node "X:\Truebex-autopilot\t95-pf12d-the-mcp-package-and-the-de\packages\mcp\truebex-mcp.mjs"`,
   start `claude`, run `/mcp` → `truebex` is connected with 20 tools (`create_layout` … `remove` listed, no
   `propose_variants`).
3. With no Truebex running, ask "use the truebex create_layout tool to lay out a living room of 20 m2 and a bedroom of
   12 m2" → the tool answers "Truebex is not running, or Agent connections are off …" (`app_not_running`). Then
   `claude mcp remove --scope user truebex`.
4. The project log (local API, no browser): in `server\`, `.venv\Scripts\python.exe -m pytest -q tests\test_pf12d_agent_interface.py`
   → 3 passed (`create_layout`, `remove` and the other five refused on `ops[0].action.tool`; the page's creation copy).

## Risks / traps

* The app's `Docs/roadmap/fixtures/contracts/agent/*.jsonl` come out CRLF on its checkout, so a sync leaves the three
  scripts "modified" until `git add` normalises them (same blobs).
* `nestedFields()` flattens: an object inside an array item inside an object reads `a[].b.c`. Deeper schemas stay
  readable but long; the portable subset (§6.5) keeps them shallow today.
* The page's count is filled at build time: a re-sync needs a rebuild (the verify gate builds) before the live site
  shows the new number.
* A Bash heredoc turns `\\n` in a Python test into real line breaks (seen here): write such edits with the Edit tool.

## As-built

* **Date, branch, commits:** 2026-10-22, `ap/t95-pf12d-the-mcp-package-and-the-de` (base `master` at fdfa389); commits
  listed by `git log master..` on the branch: the tests first (9e8f8a5), the copy (6d8d738), the page, copy and README
  (c09a6af), the remove line's wording (9f19c65), this doc with the tracker row and the README section.
* **Copied** by `scripts\sync-mcp.ps1` from the app's `main` 7fdde1e6f (contains 319fed6f8; `Tools/mcp/` last changed
  by b245af49e; the app's working tree had no change there): `tools.json` 1.2.0 → 1.3.0 (32 524 → 63 635 B) into
  `packages/mcp/` and `src/content/`; `instructions.md` (+1 line on creating, 1 535 → 2 175 B); `test/mcp.test.mjs`
  (`AI5_TOOLS`, `MCP_TOOLS`, a 20-tool list, `create_layout`'s argument checks; 14 366 → 15 254 B). Unchanged:
  `truebex-mcp.mjs`, `lib/*.mjs` (`SERVER_VERSION` still 1.0.0), `test/fake-app.mjs`, `helpers.mjs`, `zip.mjs`, the three
  wire scripts. Every copy equals its blob on the app's `main` (`git ls-files -s` against `git ls-tree -r main`; the
  scripts after LF normalisation). The first 14 tools of 1.3.0 equal 1.2.0's (MINOR: seven appended). Not copied:
  `manifest.json`, `truebex.mcpb` (PF12b deviation 3).
* **Counts:** `tools.json` 1.3.0, 21 tools, 20 on the mcp surface, 2 with `requires`; 158 top-level arguments on the
  mcp surface (`dry_run` and `request_id` included). The page: 20 tool sections (PF12c 13), 158 argument rows (one per
  top-level argument; PF12c 92 rows were 82 top-level + 10 `a.b` rows), 18 nested lists with 108 fields (`place.product`
  3, `fill.finish` 7, and the seven new tools' 98), 3 resources, 16 error codes. The app's node tests: 10 passed,
  0 failed (unchanged: 1.3.0 added checks, no test; `mcp-bundle-manifest` still filtered out). pytest 915 → 918
  collected (3 new tests; 6 package tests, 1 site test and 1 PF12c test changed).
* **Tests first:** on `master` fdfa389 (d222f29 plus `docs/brand/`) with `out/` built from it, the four files gave 10 failed, 15 passed:
  `test_mcp_package_stdio_framing` (13 == 20), `test_mcp_package_discover_and_legacy_initialize` and
  `test_mcp_package_tools_list_and_replay` (13 names listed, not `MCP_ORDER`), `test_tools_json_follows_the_contract`
  (1.2.0 < 1.3.0), `test_mcp_package_install_notes` ("thirteen tools", no "20 tools"),
  `test_docs_generated_from_tools_json` (13 sections), `test_docs_generator_keeps_the_mcp_surface` (13 tools ≠
  `MCP_ORDER`), and the three new ones (`KeyError: 'create_layout'`: the 1.2.0 file has none; no `create_layout` for
  the generator; no creation line on the never-list). The refusal itself already held on the base (no AI5 tool was
  log-safe there); the test fails there on its first check, that the file marks the seven edit and not log-safe.
  `test_mcp_package_app_node_tests` passed there and here (10 = the declared tests then and now; it now counts them
  from the copied file instead of a literal).
* **Self-test, real processes:**
  * The copied bridge over stdio (`selftest_bridge_pf12d.mjs`, scratch): `initialize` 2025-06-18 as Claude Code sends
    it, `tools/list` 20 (the last seven AI5's, class edit, no private `_meta`), `create_layout` and `remove` →
    `app_not_running` with no app, `propose_variants` → −32602; with the app's fake linked (2025-11-25), `create_layout`
    and `remove` relayed as written (`fake app saw [create_layout, remove]`), `propose_variants` still −32602; both
    bridges exit 0 within 10 ms of stdin EOF.
  * **Headless Edge** (CDP, `serve-out.py` on the built `out/`; `cdp_pf12d_page.mjs`) at 1280 × 900 and 390 × 844:
    one h1, 20 visible sections (the seven last, class edit), 158 visible argument rows, 18 lists with 108 visible
    field lines, no empty type, no "undefined" or "[object Object]", no `propose_variants` in the DOM, "20 tools" in the
    description and the Claude Code note, the three creation lines; `create_layout`'s program list as wide as its table,
    the ten room types on 2 lines; no page-wide horizontal scroll on the phone (each tool table scrolls in its
    box). Console errors: only `serve-out.py`'s known `__next.*.txt` prefetch 404s. Screenshots checked by eye
    (program list, theme finishes, the never-list).
  * **Postgres 17** (throwaway `initdb` cluster, `timezone = 'Asia/Baghdad'`, `TEST_APP_DATABASE_URL` and
    `TEST_DATABASE_URL`): `test_pf12d_agent_interface.py`, `test_pf12c_agent_interface.py`, `test_projects.py`,
    `test_mobile.py`, `test_pf12_api.py` — 60 passed, 1 failed in 155 s; the failure was the creation-copy build check
    reading an `out/` built before the remove line's rewording (no database), green after the rebuild.
  * **The verify gate** (`scripts\autopilot-verify.ps1`: lint, build, pytest on SQLite, the `out/` check): GREEN in
    739 s, 918 collected, 899 passed and 19 skipped (the Postgres-only tests), pytest 659 s.
* **Deviations from the brief and why:**
  1. *Nested fields:* PF12b's `a.b` rows for nested objects became lists too (Decision above), so `place.product` and
     `fill.finish` read as lists; the brief favoured lists for arrays of objects only. The row count is the brief's 158.
  2. *The README's count* is checked, not derived (a static file); the next MINOR breaks `CONTRACT` and, until its
     words are updated, `test_mcp_package_install_notes`.
  3. *Node test count* is read from the copied file (every declared test but `mcp-bundle-manifest` must pass), not the
     literal 10, so an app test added later is counted without a platform edit.
  4. *Shared files:* `DEVELOPER_DOCS.pages.mcp` edited in place (the page's copy; no new export);
     `src/components/developers/GroupDocPage.tsx` one optional parameter; the root README one section at its end;
     `ops.py` not touched.
* **Not changed, and why:** `server/app/projects/ops.py` (none of the seven is log-safe: the web and Android never write
  them, and light clients write only the tools they have UI for); `src/viewer/actions.ts`,
  `mobile/android/lib/actions/actions.dart`; `openapi/v1.json`, `openapi/clients.json` (the action's `tool` is a plain
  string); `package.json` 1.0.0 (= `SERVER_VERSION`, which did not move); the copied bridge.
* **Carry-over for the app half (fix in the app repo first, then `scripts\sync-mcp.ps1`):**
  1. `lib/server.mjs:21` `SERVER_VERSION` is still 1.0.0 (and `manifest.json` 1.0.0) while `tools.json` went 1.2.0 →
     1.3.0 (PF12c carry-over 4, again): bump it with a MINOR tools change (1.3.0), so `serverInfo.version` and the npm
     version say which tools a bridge serves; `package.json` follows (the test holds them equal).
  2. Differences of the file from §5.20–5.26 (the file is asserted as it is; contract PATCH lines or app fixes):
     `write_sheet_text` takes no `limits` while §5.20–5.25 list `limits` among every skill's common arguments (the
     file looks right: say so in §5.25); `create_object`'s `candidates` is 1–1 and `choose` −1–0 (one candidate) while
     §5.20–5.25 give "the others" `cad.AI5.Candidates` 3 (say so in §5.23); `create_object.size_mm` is optional in the
     file while §5.23 checks the parts' box against it (say what an absent `size_mm` means, or require it).
  3. The repair count is worded two ways: §3's 1.3.0 line "after `cad.AI5.RepairTurns` (3) failed calls … answers
     `refused`", §5.20–5.25 "the 1 + `cad.AI5.RepairTurns`-th failure … answers `refused`"; the page follows
     `instructions.md` ("at most 3 repairs, then the tool stops"). One wording in both places (PATCH).
  4. §1 still says "the eleven tools (thirteen since 1.1.0 …)" and §6.5's example `"version": "1.1.0"` (PATCH).
  5. PF12c's carry-overs 1–3 are unchanged in 1.3.0: `get_tunables` `logSafe: true`, no `ok` in its output schema,
     "roadmap 40 / TU1" in its description. PF12b's carry-overs 1–3 too (the bridge did not change).
  6. Agent-interface 1.4.0 (PL1's `set_properties`, 21 on MCP) is followed by PF12e (`PF12e-agent-interface-1-4-0.md`), which carries 1–5 on.
* **Contract proposals (for the owner to write; nothing changed from here):**
  * **§11 platform cells:** `create_layout` · `create_theme` · `create_fills` · `create_object` · `create_material` ·
    `write_sheet_text` → "PF12d (docs): done"; `remove` → "PF12d (docs): done"; `tools/list` → "PF12d (package, docs):
    done (20 on the mcp surface)". PF12c's cell proposals still stand.
  * `project-log.md` §6.2: none — the seven stay out of the log (`logSafe` false), and no `touched` key is needed.
* **Owner steps (unchanged):** `npm login` with the `@truebex` organisation, `npm publish --access public` in
  `packages\mcp`, then `mcpPublished: true` in `src/lib/constants.ts`.
* **Cut:** nothing from the scope.
