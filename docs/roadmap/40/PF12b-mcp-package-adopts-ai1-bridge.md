# PF12b — The MCP package and the developer docs adopt the bridge and tools.json AI1 shipped (launch priority 2)

**Needs merged:** PF12 (on `master`), AI1 (app; landed on the app repo's `main` 2026-10-13 03:42 UTC, app commit 90799860, Autopilot T158). **Unblocks:** publishing `@truebex/mcp` (owner). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\agent-interface.md` v1.0.0 as amended by AI1 (§3 *Changes* "AI1 amendments", §4, §5, §6.5, §6.6, §6.7, §7, §9, §10); no change from the platform (the §11 platform cells stay the owner's; proposals in As-built).

## Status

**Built 2026-10-13** on `ap/t63-pf12b-the-mcp-package-and-the-de` (base `master` at 9dac34b): `scripts/sync-mcp.ps1`
copies AI1's layout; `packages/mcp/` is AI1's bridge (`truebex-mcp.mjs`, `lib/`, `tools.json`, `instructions.md`, the app's
fake app and node tests, the three wire fixture scripts) with the platform's own `package.json`, `README.md` and
`LICENSE`; PF12's stand-in and interim scripts are gone; the package tests replay the wire scripts; `/developers/mcp/`
is generated from AI1's `tools.json`. Waiting on others: npm publishing (owner), the app-side questions and contract
proposals in As-built. See As-built.

Before this task the platform served PF12's stand-in, which the real app cannot talk to. Verified on `master` 9dac34b
and the app's `main` 90799860:

| Area | Where | Before |
|---|---|---|
| Sync | `scripts/sync-mcp.ps1:22-26` | throws unless `Tools\mcp\server.js` exists: AI1 ships `truebex-mcp.mjs` + `lib\`, so it could not run |
| Package | `packages/mcp/server.js`, `bin/truebex-mcp.js`, `package.json` (`main: server.js`, `engines >=18`) | relays `tools/call` to `\\.\pipe\truebex-agent-<USERNAME>` with no `hello`; the app has one pipe per instance (`truebex-agent-<pid>`, an instance file, a 32-hex token, wire `truebex-agent-wire/1`) |
| Schema | `packages/mcp/tools.json`, `src/content/tools.json` | the stand-in: 44 `pattern` keys, no `"schema"`, `find` kinds `product`/`view`/`category`, no `dry_run`, no resources |
| Fixtures | `packages/mcp/test/fixtures/*.jsonl` (5), `test/fake-pipe.mjs` | PF12's interim MCP-level request/answer pairs; AI1's are wire-level scripts in `Docs/roadmap/fixtures/contracts/agent/` (3) |
| Docs | `src/lib/constants.ts:2812`, `:2822`, `:2828` (`DEVELOPER_DOCS.pages.mcp`), `src/app/developers/mcp/page.tsx` | `truebex-mcp.exe`; the `npx` form before publishing; "tools only"; grants "always for that client" |
| Tests | `server/tests/test_pf12_mcp_package.py` (6), `test_site_pf12.py::test_docs_generated_from_tools_json` | against the stand-in (`ttlMs` 3 600 000, `capabilities` without `resources`) |

What the owner meant: PF12's As-built *Carry-over* ("AI1 → the real bridge, `tools.json` and the agent fixture scripts
(then `scripts\sync-mcp.ps1`)") and its deviations 1 and 2.

## Goal

The MCP server a developer installs from the platform is exactly the one the app ships, and the developer docs describe
the tools, permissions and install steps the app really has: `node packages\mcp\truebex-mcp.mjs` and (once published)
`npx -y @truebex/mcp` start AI1's bridge, the package tests prove it against the contract's wire scripts without a real
app, and `/developers/mcp/` is generated from the app's own `tools.json`.

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4; PF12's doc (Design: MCP package, Tests; As-built deviations 1, 2, 13).
* `contracts/agent-interface.md` in full (the app side is authoritative, C.9).
* The app's `Tools\mcp\README.md` (install notes), `Tools\mcp\test\fake-app.mjs`, `lib\server.mjs`, `lib\wire.mjs`,
  `Docs\roadmap\fixtures\contracts\agent\*.jsonl`.
* Skills: `truebex-brand-voice`, `truebex-seo` (the changed public page).

## Scope

**In:**
1. `scripts\sync-mcp.ps1` copies the landed layout byte for byte, never editing it: `truebex-mcp.mjs`, `lib\*.mjs`,
   `tools.json`, `instructions.md` into `packages\mcp\` (the package's own `README.md`, `LICENSE`, `package.json`
   kept), `tools.json` also into `src\content\tools.json`, the app's `test\*.mjs` into `packages\mcp\test\`, the wire
   scripts into `packages\mcp\test\fixtures\`; refuses (copying nothing) a missing file, a `tools.json` that does not
   parse or whose `"schema"` is not `truebex-tools/1`; prints what it copied and removed. Run against the app's `main`;
   the copies committed; the stand-in `server.js`, `bin/` and PF12's interim scripts removed.
2. `packages\mcp\package.json`: bin `truebex-mcp` → `truebex-mcp.mjs`, `files` = the bridge only, `engines` node
   `>=20`, no `main`, version = the bridge's `SERVER_VERSION`. `truebex.mcpb` not shipped (why: As-built).
3. Package tests rewritten to the landed bridge, the four contract names kept, plus the sync test, the app's own
   `node --test`, and an `npm pack` / install check of the bin.
4. `/developers/mcp/` generated from `src\content\tools.json`: every tool, class and argument with type and range;
   `feature_absent` for a tool whose `_meta com.truebex/requires` names a feature (no router names); the three resources;
   the off-by-default switch and the per-connection prompt; install notes matching the app's README; `npx` only behind
   `mcpPublished`; no `truebex-mcp.exe` in `src/`, `packages/` or `out/`.
5. Bridge bugs and contract questions recorded for the app half (not fixed here).

**Out (and where it goes):**
* Any change to the bridge, `tools.json`, the fake app or the wire scripts → AI1 in the app repo, then `sync-mcp.ps1`.
* The contract's §11 platform cells → the owner (rows proposed in As-built).
* Publishing `@truebex/mcp` and flipping `mcpPublished` → the owner (PF12 As-built's publishing steps).
* A hosted (remote) MCP server → not planned in roadmap 40 (§4: local by decision).

## Design

### Package

| Item | Decision |
|---|---|
| Layout | `packages/mcp/` = AI1's `Tools/mcp/` minus `README.md`, `manifest.json`, `truebex.mcpb`; plus the platform's `README.md` (npm install notes), `LICENSE` (MIT), `package.json` |
| Entry | `bin: {"truebex-mcp": "truebex-mcp.mjs"}` (the file has `#!/usr/bin/env node`; npm makes the shim), so `npx -y @truebex/mcp` and `node packages\mcp\truebex-mcp.mjs` run the same file; the bridge finds `tools.json` and `instructions.md` beside itself (`import.meta.url`) |
| `files` | `truebex-mcp.mjs`, `lib/*.mjs`, `tools.json`, `instructions.md` (npm adds `README.md`, `LICENSE`, `package.json`); no `test/`, no bundle |
| Engines | node `>=20` (the app's README and `manifest.json` `compatibility.runtimes.node`) |
| Version | `package.json` `version` = `lib/server.mjs` `SERVER_VERSION` (the bridge's `serverInfo.version`); a test fails if they part |

**Decision:** the bin points at the copied entry directly. Rejected: a `bin/` wrapper (one more platform file around a
file the app already made executable, and a second path for the same bridge).

### Sync

`scripts/sync-mcp.ps1 [-AppRepo T:\unreal5_7_4_projects\truebex_compact] [-Root <platform repo>]` (`-Root` lets the test
sync into a scratch tree). It checks the whole layout first (`truebex-mcp.mjs`, `tools.json`, `instructions.md`,
`test\fake-app.mjs`, `test\helpers.mjs`, at least one `lib\*.mjs` and one wire script; `tools.json` parses, has
`"schema": "truebex-tools/1"` and tools), then copies with `Copy-Item` (bytes as they are) and mirrors `lib\`, `test\`
and `test\fixtures\` (a file the app dropped is removed, which is how PF12's `fake-pipe.mjs` and interim scripts went).

### Tests (the harness)

* `server/tests/test_pf12_mcp_package.py` starts `node packages/mcp/truebex-mcp.mjs` with a scratch `LOCALAPPDATA` and
  every `TRUEBEX_AGENT_*` variable removed, so the default instance lookup can never reach a running Truebex.
* `server/tests/mcp_fake_app.mjs` runs the copied `test/fake-app.mjs` as a process (prints its pipe, token and
  instance folder; the test copies its instance file into the scratch `LOCALAPPDATA\Truebex\agent\instances\`).
* `server/tests/mcp_wire_replay.mjs` is §9's "fake pipe that answers the expected lines": it plays the app's side of one
  wire script. Each line the bridge relays must equal the script's `send` (after `${token}` / capture substitution:
  hello's `wire`, `token`, `era`, `client`; a call's `tool` and `args` exactly); it answers with the script's `expect`
  filled out (`"*"` → a stand-in value, `capture` paths → minted refs such as `wall#101`). The pytest side sends the
  script's calls as MCP `tools/call`s and checks each answer against `expect` (`isError`, `structuredContent`, both
  content items, `-32602` for an `rpcError`). The fake prints `MWAGENTREPLAY: script=<s> lines=<n> mismatches=<m>`.

### UI

| Page | What changes |
|---|---|
| `src/app/developers/mcp/page.tsx` | sections: Allow connections in Truebex (the switch and the prompt, numbered), Install (Claude Desktop: the Agent panel's button or `truebex.mcpb`, or the `node` entry in `claude_desktop_config.json`; Claude Code: `claude mcp add --scope user truebex -- node "<install>\MultiWindow\Tools\mcp\truebex-mcp.mjs"`; any stdio client), From npm (only when `mcpPublished`, else "Rolling out"), Several Truebex windows, Tools (generated; a Description column; the `requires` line), Resources, When a call is refused (§7 codes), What it never does |
| `DEVELOPER_DOCS.pages.mcp` (`src/lib/constants.ts`) | the words around the generated tables; `requiresText` maps a `requires` id to a sentence (`PR2` room themes, `PR3` the panorama export), so no plan id or router reaches the page |
| `src/lib/developer-docs.ts` | `Tool` typed to AI1's file (`outputSchema`, the four hints, optional `logSafe`/`requires`); `rulesOf` shows `minLength` too |

### Security and privacy

* The tests never reach a real app (scratch `LOCALAPPDATA`, no inherited `TRUEBEX_AGENT_*`); the app repo is only read.
* The docs say what the app enforces: connections off by default, grants per connection only, the never-list, the audit.

## Deliverables

- [x] `scripts/sync-mcp.ps1` (layout check, byte copies, mirroring, `-Root`)
- [x] `packages/mcp/`: the copied bridge, `lib/`, `tools.json`, `instructions.md`, `test/` (fake app, helpers, node tests, zip reader), `test/fixtures/` (3 wire scripts); `package.json`, `README.md`; `server.js`, `bin/`, `fake-pipe.mjs` and the 5 interim scripts removed
- [x] `src/content/tools.json` (AI1's file), `.gitattributes` keeps it LF
- [x] `server/tests/test_pf12_mcp_package.py` (9), `mcp_fake_app.mjs`, `mcp_wire_replay.mjs`; `test_site_pf12.py` (2 MCP checks)
- [x] `/developers/mcp/` (`page.tsx`, `DEVELOPER_DOCS.pages.mcp`, `developer-docs.ts`)
- [x] this doc, the tracker row, PF12's carry-over marked, a README section

## Tests

The first four names are `agent-interface.md` §10's platform tests.

| Name | Kind | Asserts |
|---|---|---|
| `test_mcp_package_stdio_framing` | pytest (runs node) | one message per line (a pretty-printed request = two parse errors, a batch `-32600`, CRLF accepted, UTF-8 through the pipe and back), nothing but JSON-RPC on stdout, logs on stderr, exit 0 within 1 s of stdin EOF with the app's pipe open |
| `test_mcp_package_discover_and_legacy_initialize` | pytest (runs node) | `server/discover`: `supportedVersions`, `capabilities {tools, resources}`, `instructions` = `instructions.md`, `ttlMs` 60 000, `cacheScope` private, `serverInfo` in `_meta`; `-32022` / `-32602`; `initialize` answered at 2025-11-25 and 2025-06-18 (2024-11-05 → 2025-11-25) with `resources`, no `resultType` |
| `test_mcp_package_tools_list_and_replay` | pytest (runs node) | `tools/list` = `tools.json` minus `router`/`requires`/`surfaces`/`logSafe` (`permission` kept), `ttlMs` 60 000; resources and the template; `app_not_running` (no instance file, a pipe nobody holds, connections off); the copied fake app through a scratch `LOCALAPPDATA` instance file (`find`, `resources/read`); the three wire scripts replayed with 0 mismatches |
| `test_docs_generated_from_tools_json` | build check | `out/developers/mcp/index.html`: every tool, class and argument (type, enum values, range, length, items, default, description, required) of `src/content/tools.json`; the `feature_absent` line on `apply_theme` and `export_panorama` without `PR2`/`PR3`; no router symbol or `com.truebex/` key; the switch, the prompt, the per-connection grant, the install notes; no `npx` while `mcpPublished` is false; no `truebex-mcp.exe` anywhere in `out/` |
| `test_docs_resources_match_the_bridge` | build check (runs node) | the page's resources = the bridge's `resources/list` + `resources/templates/list` |
| `test_sync_mcp_copies_the_landed_bridge` | pytest (runs PowerShell) | in a scratch app + platform tree: byte-equal copies (CRLF and UTF-8 kept), names printed, `README.md`/`LICENSE`/`package.json` kept, the bundle and app README not copied, stale files removed; a missing `truebex-mcp.mjs`, a `truebex-tools/2` schema and a broken `tools.json` are refused with nothing copied |
| `test_tools_json_follows_the_contract` | pytest | §6.5 as amended: `schema`, version, order, classes, router, surfaces, hints, the portable keyword subset (no `pattern`), `additionalProperties: false` on every input object, output schemas require exactly `ok` and accept a §7 error, `request_id` on edit/export, `dry_run` on the log-safe edits, `requires` only on `apply_theme` (PR2) and `export_panorama` (PR3), `find` kinds |
| `test_site_copy_of_tools_json_is_the_package_one` | pytest | same `toolsHash` (SHA-1 without CR, §3) and content |
| `test_mcp_package_install_notes` | pytest | `package.json` (bin, no `main`, engines, `files`, version = `SERVER_VERSION`), the shebang, the stand-in gone, the README's install lines, no `truebex-mcp.exe` in `src/` or `packages/` |
| `test_mcp_package_app_node_tests` | pytest (runs node) | the app's `node --test` on the copied `test/mcp.test.mjs`: 9 pass (all but `mcp-bundle-manifest`) |
| `test_mcp_package_npm_bin_starts_the_bridge` | pytest (runs npm) | `npm pack` holds exactly the bridge + README, LICENSE, package.json; installed offline, the `truebex-mcp` shim answers `server/discover` |

## Human test

Launch: in the worktree, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` (serves
`out/` on `http://127.0.0.1:3163/`). No local API is involved: the page is static and the MCP server is local.

1. Open `http://127.0.0.1:3163/developers/mcp/` → "Allow connections in Truebex" with three numbered steps (the switch is
   off by default; the prompt offers read, read + edit, read + edit + export; the answer lasts for that connection);
   Install shows Claude Desktop (Install in Claude Desktop / `truebex.mcpb`, and a `node` config entry), Claude Code
   (`claude mcp add --scope user truebex -- node "<install>\MultiWindow\Tools\mcp\truebex-mcp.mjs"`), Any MCP client,
   and "Rolling out: @truebex/mcp is being published to npm." with no `npx` line.
2. Tools: eleven sections, each with its class; `apply_theme` and `export_panorama` say "On the roadmap: Answers
   feature_absent until …"; each table lists type, rules and description. Resources: three URIs. Find in page
   "truebex-mcp.exe" → no match.
3. In a terminal: `claude mcp add --scope user truebex -- node "X:\Truebex-autopilot\t63-pf12b-the-mcp-package-and-the-de\packages\mcp\truebex-mcp.mjs"`,
   start `claude`, run `/mcp` → `truebex` is connected with eleven tools; its resources are offered in the `@` menu.
4. With no Truebex running, ask "use the truebex find tool to list the rooms" → the tool answers "Truebex is not
   running, or Agent connections are off …".
5. With an AI1 build (app `main` 90799860 or later) open on a project and Tools > AI > Agent > Allow AI apps to connect
   on, ask "how many walls are on the ground floor?" → Truebex asks "… asks to work on …" → Allow read → Claude answers
   with a count, through `find`.
6. `claude mcp remove --scope user truebex`.

## Risks / traps

* PowerShell 5.1 leaves `$PSScriptRoot` empty in `param()` defaults: `sync-mcp.ps1` sets `-Root`'s default in the body.
* A test bridge with the real `LOCALAPPDATA` would pick up a Truebex the person has open (the newest live instance file):
  every test bridge gets a scratch `LOCALAPPDATA` and no `TRUEBEX_AGENT_*`.
* `packages/` is LF on checkout (`packages/.gitattributes`); `src/content/tools.json` now too, so the site copy stays
  byte-equal to the app's file (the `toolsHash` ignores CR either way). The app's `Tools/mcp/` is LF by its own
  `.gitattributes`, but its `Docs/roadmap/fixtures/contracts/agent/*.jsonl` come out CRLF on the app's Windows checkout:
  `sync-mcp.ps1` copies those bytes and git stores the scripts LF here; both harness sides read either.
* The app's `mcp-bundle-manifest` node test compares `truebex.mcpb` with the `README.md` beside it; here that README is
  the platform's, so the test runs the other nine.
* Writing a backslash-heavy snippet through a Bash heredoc collapses `\\`: edit `constants.ts` with the editor.

## As-built

* **Date, branch, commits:** 2026-10-13, `ap/t63-pf12b-the-mcp-package-and-the-de` (base `master` at 9dac34b); commits
  listed by `git log master..` on the branch: the tests first (failing on the stand-in), then the sync, the copies and
  the package, the site, and this doc with the tracker row.
* **Counts:** pytest 669 → 673 collected (`test_pf12_mcp_package.py` 6 → 9, `test_site_pf12.py` 6 → 7); the package
  and site files: 16 passed in about 10 s. The verify gate (lint, build, pytest on SQLite): GREEN in 1 033 s, 656
  passed and 17 skipped (the Postgres-only tests), pytest 540 s. The run before it failed one test outside this
  feature, `test_billing_pf2.py::test_billing_paddle_webhook_signature` (its `ts=int(time.time()) + 301` lost 0.998 s to
  `int()` and the server read its clock later under load, so the request fell inside the 300 s window); it passed
  three times alone and in the next gate. Left as it is (not this feature's; a timing check under load). `tools.json` 1.0.0 (`truebex-tools/1`, 11 tools, 2 with `requires`); the
  page: 11 tool sections, 83 argument rows, 3 resources, 16 error codes. Copied from the app's `main` 90799860:
  `truebex-mcp.mjs` 1 972 B, `lib/` 4 files (29 946 B), `tools.json` 22 426 B, `instructions.md` 1 286 B, `test/` 4
  files, 3 wire scripts. Removed: `server.js`, `bin/truebex-mcp.js`, `test/fake-pipe.mjs`, 5 interim scripts.
* **Tests first:** on the unchanged branch the 7 new or rewritten package tests failed (the sync test against PF12's
  script: it throws without `server.js`); `test_site_copy_of_tools_json_is_the_package_one` passed on both.
* **Self-test, real processes** (`selftest_bridge.mjs` in the session scratchpad): the copied bridge over stdio, first
  against the copied fake app found through an instance file in a scratch `LOCALAPPDATA`, then with none:

  ```
  -> {"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{…"2026-07-28"…}}}
  <- {"jsonrpc":"2.0","id":1,"result":{"resultType":"complete","supportedVersions":["2026-07-28","2025-11-25","2025-06-18"],"capabilities":{"tools":{},"resources":{}},"instructions":"Truebex is an architectural CAD app …","ttlMs":60000,"cacheScope":"private",…}}
  -> {"jsonrpc":"2.0","id":2,"method":"tools/list",…}
  <- {"jsonrpc":"2.0","id":2,"result":{"resultType":"complete","tools":[{"name":"read_state",…  (15 414 chars, 11 tools)
  -> {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{…,"name":"find","arguments":{"kind":"wall","room":"Study","facing":"n"}}}
     stderr: [truebex-mcp] linked to \\.\pipe\truebex-agent-test-61220-289731347 in 16 ms (session aaaa…)
  <- {"jsonrpc":"2.0","id":3,"result":{"resultType":"complete","content":[{"type":"text","text":"find ok"},{"type":"text","text":"{\"ok\":true,\"text\":\"find ok\"}"}],"isError":false,"structuredContent":{"ok":true,"text":"find ok"},…}}
  -> {"jsonrpc":"2.0","id":4,"method":"resources/read","params":{…,"uri":"truebex://state/digest"}}
  <- {"jsonrpc":"2.0","id":4,"result":{"resultType":"complete","contents":[{"uri":"truebex://state/digest","mimeType":"text/plain","text":"TRUEBEX fake-app tool=3D doc=Riverside Court\n…"}],…}}
  exit 0 22 ms after stdin EOF; the fake app saw 1 hello and the call {"op":"call","id":1,"tool":"find","args":{…}}
  --- no app ---
  <- id 1, 2: the same discover and eleven tools (listed with Truebex closed)
     stderr: [truebex-mcp] cannot link to no instance (app_not_running: no Truebex instance file) after 1 ms
  <- {"jsonrpc":"2.0","id":3,"result":{"resultType":"complete","content":[{"type":"text","text":"Truebex is not running, or Agent connections are off. Ask the person to start Truebex, open a project and turn on Tools > AI > Agent > \"Allow AI apps to connect\", then try again."},…],"isError":true,"structuredContent":{"ok":false,"code":"app_not_running",…}}}
  <- {"jsonrpc":"2.0","id":4,"error":{"code":-32603,"message":"Truebex is not running, or Agent connections are off. …","data":{"code":"app_not_running","uri":"truebex://state/digest"}}}
  exit 0 13 ms after stdin EOF
  ```

  **Headless Edge** (CDP, `serve-out.py` on the built `out/`): `/developers/mcp/` at 1280 × 900 and 390 × 844 — one h1,
  11 tool sections with their classes, 83 argument rows visible, the two `feature_absent` lines, 3 resources, 16 error
  rows, no `npx`, no `truebex-mcp.exe`, no page-wide horizontal scroll on the phone (the argument tables scroll inside
  their box); console errors only the known `__next.*.txt` prefetch 404s of `serve-out.py`. The first pass showed the
  rules column breaking mid-word (`def ault`) and the steps without numbers; fixed on the page (`list-decimal`, tables
  `min-w-[44rem]`, no `break-all`), not in the shared CSS. `npm pack` + an offline install: the `truebex-mcp.cmd` shim
  answers `server/discover` (in `test_mcp_package_npm_bin_starts_the_bridge`).
* **Deviations from the brief and why:**
  1. *The wire scripts replay against a script-driven fake pipe, not the copied `fake-app.mjs`.* The fake app answers
     canned data (`find` → `{"ok": true, "text": "find ok"}`, no matches), so it cannot answer the scripts' `expect`
     lines (`find` with `total: 1` and a wall ref to capture, `explain` of the captured window). §9 asks for "a fake
     pipe that answers the expected lines"; that is `server/tests/mcp_wire_replay.mjs` (Node built-ins only, sharing no
     code with the bridge). The copied fake app is used for framing, discovery, `find` and `resources/read` relays,
     connections off, the scratch-`LOCALAPPDATA` lookup, and the app's own node tests. The harness lives in
     `server/tests/` because `sync-mcp.ps1` mirrors `packages/mcp/test/`.
  2. *Lines the bridge never relays:* `setup` and `prompt` (the app's side of a script) and calls of a tool
     `tools.json` lacks (`fence`'s `delete_project`, `permissions`' `quit`): the bridge answers those `-32602` itself
     (§6.6), the test checks that answer, and the fake does not expect them. Counted: `window-north-study` 6 calls all
     relayed, `permissions` 7 calls / 6 relayed, `fence` 7 calls / 6 relayed (+ the hello each).
  3. *`truebex.mcpb` is not in the npm package.* It is Claude Desktop's install format and ships with the app beside the
     installed bridge (the Agent panel's Install in Claude Desktop opens it); npm users run the bridge through `node` or
     `npx`. The bundle carries the app's `README.md` and a `manifest.json` that declares `"license": "Proprietary"`,
     while the npm package is MIT: shipping both would publish two licences for one set of files. The app's
     `mcp-bundle-manifest` node test is therefore not run here (`manifest.json` is not copied either).
  4. *`additionalProperties`:* §6.5 says "always `false` on objects"; AI1's output schemas leave it out at every level so
     §7's error content (`code`, `detail`, `data`, `request_id`) conforms, as §6.5's last sentence requires, and the app's
     own check (`lib/schema.mjs:140`) closes input schemas only. The test asserts closed input objects, output schemas
     requiring exactly `ok`, and that a §7 error conforms. Proposal below.
  5. *Errors table and "Several Truebex windows":* beyond the brief, in plain words from §7 and the app's README; the
     codes are not in `tools.json`, so they are copy (`DEVELOPER_DOCS.pages.mcp.errors`), not generated. The resources
     are copy too (not in `tools.json`), held to the bridge by `test_docs_resources_match_the_bridge`.
  6. *Status note:* AI1 is merged on the app's `main` but no release with it is on the feed (`src/content/releases.json`
     `latest: null`), so the page keeps "On the roadmap": "The Agent panel, where you turn connections on, arrives in a
     coming Truebex release. Until then every tool call answers app_not_running." Nothing moved into `FEATURES`. The npm
     README does show `npx` (it is only seen on npm, once published).
  7. *Shared files:* `.gitattributes` gains one line at its end (`src/content/tools.json text eol=lf`); the root README's
     PF12 section (which still says "stand-in") is left as it is and a PF12b section at the end supersedes it.
* **Carry-over for the app half (AI1; fix in the app repo first, then `scripts\sync-mcp.ps1`):**
  1. `Tools/mcp/lib/server.mjs:40` (`RESOURCE_PATTERNS`): entity ids must match `[0-9.]+`, so
     `truebex://entity/wall/<32 hex>` answers "Resource not found" in the bridge although §6.2 accepts CL0's 32-hex
     `FCadEntityId` for refs. Widen to `[0-9a-f.]+` when CL0 ids exist, or say in §5.16 that resources take load-local
     ids only.
  2. `Tools/mcp/lib/server.mjs:253`: `resources/read` with no app answers JSON-RPC `-32603` (internal error) with
     `data.code: "app_not_running"`; §6.6 defines `app_not_running` only as a tool error. Fine for clients, but §6.6
     could name this shape.
  3. `Tools/mcp/manifest.json:40` `"license": "Proprietary"` vs the npm package's MIT (`packages/mcp/LICENSE`): the
     owner decides the bridge's licence before publishing.
  4. The app has since moved to agent-interface 1.2.0 (TU1's `get_tunables` / `set_tunable`, AI2's assistant-only `propose_variants`): followed by [PF12c](PF12c-agent-interface-1-2-0.md).
* **Contract proposals (for the owner to write in `agent-interface.md`; nothing changed from here):** §6.5 —
  "`additionalProperties` (always `false` on input-schema objects; output schemas stay open so a §7 error conforms)";
  §9 — `legacy-initialize` and `app-not-running` are node tests (`mcp-legacy-initialize`, `mcp-no-app`), not fixture
  files (`Docs/roadmap/fixtures/contracts/agent/` holds three scripts). **§11 platform cells:** `server/discover`,
  `initialize` (legacy), `tools/list`, `notifications/cancelled`, resources → "PF12b (package): done (AI1's bridge,
  copied by `sync-mcp.ps1`)"; `tools/list` and the eleven tools → "PF12b (docs): done".
* **Owner steps (unchanged from PF12):** `npm login` with the `@truebex` organisation, `npm publish --access public` in
  `packages\mcp`, then `mcpPublished: true` in `src/lib/constants.ts` (the page then shows the `npx` forms).
* **Cut:** nothing from the scope.
