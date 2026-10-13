# PF12 — Public API, SDKs, webhooks and the MCP package (launch priority 2)

**Needs merged:** PF4. **Unblocks:** none. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\agent-interface.md` (v1.0.0: the MCP package and the tools reference are PF12's per its §11); the `/v1` mirror follows `project-log.md` §3 ("PF12 later mirrors these paths under `/v1/projects` with the same shapes"), `render-jobs.md` §4 and `marketplace-api.md` §4.

## Status

**Built 2026-10-11** on `ap/t8-pf12-public-api-sdks-webhooks-an` (base `master` at e602d76, with PF4–PF8, PF2a/b and
PF3a merged): key scopes and the burst limit (`server/app/scopes.py`, `deps.py`), the `/v1` mirror
(`server/app/routers/v1/`), webhooks (`server/app/webhooks/`), `openapi/v1.json` and its exporter, the Python and
JavaScript SDKs (`sdks/`), the MCP package (`packages/mcp/`), `/developers/` with seven sub-pages, scopes on
Dashboard → API keys and a Dashboard → Webhooks page. Waiting on others: the app's bridge and `tools.json` (AI1; the
package holds a stand-in written to the contract), cloud save in the app (CL1), the headless render (CL3), and the
owner's PyPI and npm publishing. See As-built.
Merged with master (PF11) on 2026-10-11 (Autopilot T32): an analysis job may name no project through `/v1/jobs` and
the SDKs. See As-built.

Before this task the developer API had two endpoints and no scopes, webhooks, SDKs or MCP package. Verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| `/v1` router | `server/app/routers/v1.py:18`, `:21-24` (`/v1/ping`), `:27-43` (`/v1/account`); `:3-4` promises product endpoints | metered by key |
| Key auth and metering | `server/app/deps.py:55-110` (Bearer or `X-API-Key`, monthly quota, `X-RateLimit-*`), `server/app/main.py:45` (headers exposed) | one quota, no scopes |
| Keys | `server/app/models.py:46-70`, `src/app/dashboard/keys/page.tsx` | name only |
| OpenAPI | `server/app/main.py:29-37` (`title`, `version="2.0.0"`, description) | FastAPI serves `/openapi.json` and `/docs`; nothing generated from it |
| Developer docs page | `src/app/developers/page.tsx:21-24` (`ENDPOINTS`), `:26-30` (`LIMITS`), `:32-36` (`ERRORS`), `:38-46` (TechArticle JSON-LD), `:48` | hand-written for two endpoints |
| From PF4 (Needs) | the project service; from PF5, PF6, PF7, PF8 when merged: shares, jobs, the marketplace, the supplier feeds | the services the mirror exposes |

What the owner meant: app-side `00-understanding.md` §10 (the MCP server for the person's own Claude app) and the request's "public API" line in the PF stream (C.2).

## Goal

Developers and the person's own tools work with Truebex from outside the app: create and read projects, request exports, publish shares and query the marketplace with the API keys they already have; hear about changes through signed webhooks; use typed Python and JavaScript SDKs generated from the API's own description; and install the MCP server that lets their Claude app read and edit the open model, with documentation that is generated from the same sources and so never drifts. Human test seed: "create a project through the API and open it in the app".

## Read first

* **`contracts/agent-interface.md` v1.0.0** — §2 (PF12 publishes the schema and the package, never runs a tool), §4 (stdio to the bridge, a named pipe to the app), §5 and §6.5 (`tools.json`), §6.6 (MCP revision 2026-07-28 served dual-era with 2025-11-25; the stdio framing), §9 (fixture scripts PF12's package tests replay against a fake pipe), §10 (the four platform tests).
* `contracts/project-log.md` §3–§5, `render-jobs.md` §4–§5, `share-bundle.md` §4–§5, `marketplace-api.md` §4–§5: the shapes the mirror exposes unchanged.
* Standard Webhooks specification (github.com/standard-webhooks/standard-webhooks, `spec/standard-webhooks.md`): headers, signature, secret format, retry schedule.
* OpenAPI 3.1 (FastAPI's output); the MCP specification revision 2026-07-28 (modelcontextprotocol.io).
* Skills: `truebex-seo` and `truebex-brand-voice` for the rewritten `/developers/` pages; the `claude-api` skill for the MCP install notes.

## Scope

**In:**
1. The `/v1` API grown to projects: the `project-log.md` endpoints mirrored under `/v1/projects…` with the same shapes and errors, authenticated and metered by API key as today.
2. Exports: `/v1/jobs` mirroring `render-jobs.md` 5.1–5.6 for API keys (§4 allows it) — `pack` jobs give the sheet PDF, renders, panoramas and the bill of quantities; file formats beyond those (IFC, DXF, DWG) as a `render-jobs.md` MINOR addition (`export` kind) once IO2 and IO4 land.
3. Shares: `/v1/uploads` and `/v1/shares` mirroring `share-bundle.md` 5.1–5.9 for API keys (a MINOR addition to its §4, proposed below).
4. Marketplace queries: `marketplace-api.md` 5.1–5.6 documented as part of the developer API; an API key raises the anonymous rate limit and is metered.
5. API keys as today plus scopes: `projects:read`, `projects:write`, `jobs:write`, `shares:write`, `market:read`, `supplier:feed`, `webhooks:manage`; chosen when a key is made; existing keys keep working with every read scope; a per-key burst limit beside the monthly quota.
6. Webhooks: endpoints registered per account, events signed per the Standard Webhooks specification, retried on its schedule, a delivery log, re-send, disable after five days of failures with an e-mail.
7. Python and JavaScript SDKs generated from the OpenAPI document of `/v1` (committed as `openapi/v1.json`, drift-tested), each with a webhook-signature helper; packaged for PyPI (`truebex`) and npm (`@truebex/sdk`); publishing is the owner's.
8. The MCP server published as a package with install docs: the bridge of `agent-interface.md` §6.6 packaged for npm (`@truebex/mcp`, bin `truebex-mcp`) from the app repo's `Tools/mcp/` (copied at an app release, never edited), install notes for Claude Desktop, Claude Code and other MCP clients, and the package tests of the contract.
9. The supplier feed API: the endpoints are PF8's (`marketplace-api.md` 5.11–5.13); PF12 adds the `supplier:feed` scope, SDK methods and documentation.
10. The developer docs rewritten around all of it: `/developers/` and sub-pages for projects, jobs and exports, shares, marketplace, webhooks, SDKs and MCP; reference tables generated at build time from `openapi/v1.json` and `tools.json`.
11. Tests: the contract's four platform tests, a pytest per `/v1` route group (happy path, auth failure, validation failure), webhook signing and retries, OpenAPI drift, build checks for the docs.

**Out (and where it goes):**
* The services behind the mirror → PF4 to PF8; the bridge's code and `tools.json` → AI1 (app); executing tools → the app only (§2).
* A remote, hosted MCP server over cloud projects → not planned in roadmap 40 (the contract's MCP surface is local by decision, §4).
* SDKs in further languages → later, from the same OpenAPI document.
* Publishing to PyPI and npm, the npm organisation and tokens → owner actions.

## Design

### API

The mirror mounts the same service functions as the contract routers under `/v1` with `api_key_auth` (`server/app/deps.py:55-110`), so metering, `X-RateLimit-*` and the monthly quota apply unchanged; contract headers and the error envelope apply too.

| Route group | Scope | Mirrors | Notes |
|---|---|---|---|
| `/v1/projects…` | `projects:read` / `projects:write` | `project-log.md` 5.1–5.18 | delete stays session-only (403 `session_required`, §4); pushes from a key are `author_kind: "agent"` with the key's id as `author` |
| `/v1/jobs…` | `jobs:write` (read with `projects:read`) | `render-jobs.md` 5.1–5.6 | `pack` for exports |
| `/v1/uploads…`, `/v1/shares…` | `shares:write` | `share-bundle.md` 5.1–5.9 | MINOR proposal: API keys in its §4 |
| `/market/…` | `market:read` (optional) | `marketplace-api.md` 5.1–5.6 | a key lifts the anonymous limit |
| `/market/feeds…` | `supplier:feed` | 5.11–5.13 (PF8) | supplier-bound keys |
| `/v1/webhooks` (`GET`, `POST`), `/v1/webhooks/{id}` (`PATCH`, `DELETE`), `/v1/webhooks/{id}/deliveries`, `…/deliveries/{d}/resend`, `…/secret/rotate` | `webhooks:manage` | — | the endpoint's secret is shown at creation and on rotate |
| `/keys` (`POST`) | session | today's `server/app/routers/keys.py:33-58` | gains `scopes` (validated list); old keys read as every `:read` scope |

Webhook events (the payload's `data` is the resource as its contract shapes it):

| Event | When |
|---|---|
| `project.ops_appended` | operations accepted (debounced 30 s per project: first and last `server_seq`, authors) |
| `project.version_created`, `project.member_added` | 5.11, 5.14 |
| `job.succeeded`, `job.failed` | a job of the account ends |
| `share.published`, `share.visits_daily` | 5.5; a daily digest of yesterday's visits |
| `market.order.updated`, `market.feed.completed` | a buyer's order changes state; a supplier's feed run ends |

Signing per Standard Webhooks: headers `webhook-id`, `webhook-timestamp`, `webhook-signature: v1,<base64 HMAC-SHA256 over id.timestamp.body>`; secrets `whsec_<base64>`; receivers should refuse timestamps more than 5 min off. Retries: immediately, 5 s, 5 min, 30 min, 2 h, 5 h, 10 h, 14 h, 20 h, 24 h, with jitter; 2xx within 15 s is success. **Decision:** the published specification over a house scheme, so receivers can use existing verification libraries. Rejected: a Stripe-style scheme of our own (every receiver writes verification code by hand).

### MCP package

| Item | Decision |
|---|---|
| Source | `packages/mcp/` holds `package.json`, `README.md` (install notes) and `bin/truebex-mcp.js`; `server.js` and `tools.json` are copied from the app repo's `Tools/mcp/` at an app release by `scripts/sync-mcp.ps1` (copied, never edited, like contract fixtures) |
| Behaviour | exactly §6.6: stdio, one JSON-RPC message per line, logs on stderr, exit on stdin EOF; answers `server/discover`, `initialize` (2025-11-25) and `tools/list` from `tools.json`; relays `tools/call` to `\.\pipe\truebex-agent-<USERNAME>`; `app_not_running` when no app holds the pipe |
| Install notes | Claude Desktop: an `mcpServers` entry `{"truebex": {"command": "npx", "args": ["-y", "@truebex/mcp"]}}` in its config file, or the installed `truebex-mcp.exe` path the Agent panel shows; Claude Code: `claude mcp add --scope user truebex -- npx -y @truebex/mcp`; any MCP client: the same command over stdio |
| Tests | `test_mcp_package_*` (below) start `node bin/truebex-mcp.js` from pytest against `packages/mcp/test/fake-pipe.mjs`, which answers the contract's fixture scripts line by line |

### Data

| Table / file | Fields | Notes |
|---|---|---|
| `api_keys.scopes` | `TEXT` (JSON list) via `_ADDED_COLUMNS` | null = every read scope (keys made before PF12) |
| `webhook_endpoints` | `endpoint_id`, `account`, `url` (https), `secret_enc` (Fernet, `WEBHOOK_SECRET_KEY`), `events` JSON, `active`, `failing_since`, `created_at` | the secret must be readable to sign, so it is encrypted, not hashed |
| `webhook_events` | `event_id` (`msg_…`), `type`, `account`, `payload` JSON, `created_at` | kept 30 days |
| `webhook_deliveries` | `delivery_id`, `endpoint_id`, `event_id`, `attempt`, `next_attempt_at`, `status`, `response_code`, `response_ms`, `delivered_at` | |
| `openapi/v1.json` | the `/v1` OpenAPI document | regenerated by `server/scripts/export_openapi.py --v1`; drift fails a test |
| `src/content/tools.json` | a copy of the app's `tools.json` | the MCP reference page is generated from it |

### UI

| Page | What it shows |
|---|---|
| `src/app/developers/page.tsx` (rewrite; indexable) | the overview: what the API can do, authentication and scopes, base URL, limits (from the catalogue, not hand-typed), errors (the shared envelope), quick start, links to the sub-pages; TechArticle JSON-LD kept in step |
| `src/app/developers/{projects,jobs,shares,market,webhooks,sdks,mcp}/page.tsx` (indexable) | one h1 each, canonical with trailing slash, reference tables generated at build time from `openapi/v1.json`; `mcp/` lists every tool, class and argument from `src/content/tools.json` and the install notes; `BreadcrumbList` JSON-LD |
| `src/app/dashboard/keys/page.tsx` | scope checkboxes when creating a key; scopes shown per key |
| `src/app/dashboard/webhooks/page.tsx` (noindex) | endpoints, events, secret (reveal, rotate), recent deliveries with status, re-send |

### Jobs / workers

| Job | Every | Does |
|---|---|---|
| `webhooks.deliver` | 5 s | sends due deliveries (timeout 15 s), schedules the next attempt per the retry table |
| `webhooks.digest` | daily, 00:10 UTC | `share.visits_daily` events |
| `webhooks.disable` | 1 h | endpoints failing for 5 days → inactive; an e-mail to the account (`server/app/mail`) |
| `webhooks.purge` | 24 h | events and deliveries older than 30 days |

SDK generation: `scripts/gen-sdks.ps1` runs an open-source OpenAPI client generator for Python (MIT) into `sdks/python/` and a TypeScript types generator (MIT) plus a 100-line fetch client into `sdks/js/`; both packages carry `verify_webhook()` helpers tested against the same vectors.

### Security and privacy

* Scopes are checked on every route; a key never deletes a project and never reaches `/ai/*` (`ai-proxy.md` §4).
* Webhook URLs must be https and resolve to public addresses (checked again at each delivery, against DNS rebinding); payloads carry what the account's own API reads would return, nothing more.
* The MCP package never touches a platform credential: it speaks only to the local app over a per-user pipe (`agent-interface.md` §4).
* SDKs never log keys; examples read them from environment variables, as `src/app/developers/page.tsx` does today.

## Deliverables

- [ ] `server/app/routers/v1/` (`projects.py`, `jobs.py`, `shares.py`, `webhooks.py`), `server/app/webhooks/` (`events.py`, `signing.py`, `delivery.py`), scopes in `deps.py` and `routers/keys.py`
- [ ] `server/scripts/export_openapi.py`, `openapi/v1.json`, `scripts/gen-sdks.ps1`, `sdks/python/`, `sdks/js/`
- [ ] `server/scripts/webhook_echo.py` (a local receiver that verifies signatures) and the setting `WEBHOOKS_ALLOW_HTTP_LOCAL` (default false; lets `http://127.0.0.1` endpoints through for local tests only)
- [ ] `packages/mcp/` (package, launcher, README, `test/fake-pipe.mjs`), `scripts/sync-mcp.ps1`, `src/content/tools.json`
- [ ] `/developers/` and sub-pages, keys page scopes, webhooks page; sitemap entries; `tsconfig.json` `exclude` and `eslint.config.mjs` ignores for `sdks/**` and `packages/**`
- [ ] contract §11 rows (agent-interface) and the MINOR proposals (share-bundle §4 API keys; render-jobs `export` kind) recorded in As-built

## Tests

The first four names are `agent-interface.md` §10's platform tests.

| Name | Kind | Asserts |
|---|---|---|
| `test_mcp_package_stdio_framing` | pytest (runs node) | one message per line, nothing but MCP on stdout, exit on stdin EOF |
| `test_mcp_package_discover_and_legacy_initialize` | pytest (runs node) | `server/discover` and a 2025-11-25 `initialize` both answer |
| `test_mcp_package_tools_list_and_replay` | pytest (runs node) | `tools/list` equals `tools.json`; every fixture script replays against the fake pipe; `app_not_running` with no pipe |
| `test_docs_generated_from_tools_json` | build check | `out/developers/mcp/index.html` lists every tool, class and argument of `src/content/tools.json` |
| `test_v1_projects_mirror_shapes` | pytest | `/v1/projects` create, list, open, push, pull answer the same shapes as the contract routes; metered in `usage_daily` |
| `test_v1_scopes_enforced` | pytest | a `projects:read` key cannot push (403 `forbidden` with `data.needed`); an old scope-less key reads but cannot write |
| `test_v1_key_cannot_delete_project` | pytest | 403 `session_required` |
| `test_v1_jobs_pack_export` | pytest | a `pack` job with `items: ["sheets"]` is accepted with an estimate; 401 without key |
| `test_v1_shares_with_key` | pytest | uploads and shares work with a `shares:write` key; 422 manifest errors pass through |
| `test_v1_burst_limit` | pytest | the per-key burst limit answers 429 with `retry_after_s` before the monthly quota |
| `test_keys_create_with_scopes_validation` | pytest | 422 for an unknown scope; 401 without session |
| `test_webhooks_crud_and_https_only` | pytest | create, list, update, delete; `http://` and private addresses → 422 |
| `test_webhooks_signature_standard_vectors` | pytest | our signer reproduces the specification's test vector; the SDK helpers verify it |
| `test_webhooks_retry_schedule_and_disable` | pytest | failed deliveries follow the schedule; five days of failures disable the endpoint and send one e-mail |
| `test_webhooks_ops_appended_debounced` | pytest | three pushes within 30 s → one event with the first and last numbers |
| `test_openapi_v1_document_current` | pytest | `openapi/v1.json` equals a fresh export (drift fails) |
| `test_site_pf12_developer_pages` | build check | every `out/developers/**/index.html`: one h1, canonical with trailing slash, TechArticle or BreadcrumbList JSON-LD; sitemap lists them |
| `npm run lint`, `npm run build` | build check | green with `sdks/` and `packages/` excluded from the site's type check and lint |

## Human test

1. Local API with PF4 merged (and PF6 for step 6); the build served against it.
2. Dashboard → API keys → create "CI" with `projects:write` and `webhooks:manage` → copy the key.
3. Python: in `sdks/python/` run `python -c "import truebex; c = truebex.Client(api_key='tbx_live_…', base_url='http://127.0.0.1:8000'); print(c.projects.create(name='API House', doc_version=38))"` → a project record with `head_seq` 0.
4. Dashboard → Projects lists "API House"; in a CL1 build, File → Open from cloud → "API House" opens as an empty project.
5. Webhooks: run `server\.venv\Scripts\python.exe scripts\webhook_echo.py --port 9900` (prints and verifies incoming events); register `http://127.0.0.1:9900/` with the local-testing override `WEBHOOKS_ALLOW_HTTP_LOCAL=true` → move a wall in the app (or push with `demo_replica.py`) → within 30 s the echo prints `project.ops_appended` with "signature valid".
6. Request an export: `c.jobs.create(kind='pack', project_id=…, at_seq=…, params={'items': ['sheets']})` → `succeeded` → the output's PDF URL downloads.
7. MCP: `claude mcp add --scope user truebex -- node <repo>\packages\mcp\bin\truebex-mcp.js` → in Claude Code, `/mcp` lists truebex with its eleven tools; with an AI1 build running, "how many walls are on the ground floor?" answers through `find`.
8. Open `/developers/` and `/developers/mcp/` → the reference tables match the API and the tools list.

## Risks / traps

* `tsconfig.json` includes `**/*.ts` (`tsconfig.json:25-32`) and ESLint lints every JS file: `sdks/` and `packages/` must be excluded, or the site's build type-checks Node code and generated clients.
* The bridge's code belongs to AI1: the package only copies it; a fix goes to the app repo first, then `sync-mcp.ps1`.
* Mirrors must not fork logic: the `/v1` routes call the same service functions as the contract routes, or the shapes drift.
* Debounced webhooks need the background worker (PF14's `worker` process on the VM; inline on the home PC); deliveries survive restarts because they live in the database.
* Webhook secrets are encrypted, not hashed (they must sign); losing `WEBHOOK_SECRET_KEY` means rotating every endpoint's secret.
* Publishing packages is an owner action with the owner's tokens; the task only builds them and records the commands in As-built.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t8-pf12-public-api-sdks-webhooks-an` (base `master` at e602d76, merged in
  by Autopilot as 585469b): `c6d1358` (the duplicate uploads router, below), `7721439` (scopes, the `/v1` mirror,
  webhooks, the OpenAPI document and both SDKs), `59b6c2d` (the MCP package), `df3c410` (the document's scopes, events
  and limits), `e9d8f2a` (the site), `aef3712` (`webhook_echo.py`, settings, the Postgres cutover), `4753db6` (PF7's
  sitemap check), `6c7ecb6` (parallel deliveries), and the docs commit ticking this row.
* **Counts:** pytest 429 → 473 collected; the verify gate (lint, build, pytest on SQLite): 468 passed, 5 skipped (the
  Postgres-marked tests). New: `test_pf12_api.py` 10, `test_pf12_webhooks.py` 12, `test_pf12_openapi_sdks.py` 8,
  `test_pf12_mcp_package.py` 6, `test_site_pf12.py` 6, `test_routes_unique.py` 2. `openapi/v1.json` 1.0.0: 52
  operations, 83 schemas. SDKs `truebex` 1.0.0 (PyPI) and `@truebex/sdk` 1.0.0 (npm); `@truebex/mcp` 1.0.0 (npm);
  `tools.json` 1.0.0 (11 tools). **Live run** (uvicorn on SQLite, inline jobs, a throwaway licence key): sign-up, the Pro
  trial through `demo_replica.py login --trial`, a key "CI" with `projects:write` + `webhooks:manage`; the human test's
  line `truebex.Client(…).projects.create(name='API House', doc_version=38)` from `sdks/python` with plain `py -3.12`
  answered the record with `head_seq` 0; an endpoint `http://127.0.0.1:9900/` with `WEBHOOKS_ALLOW_HTTP_LOCAL=true`, two
  `demo_replica.py move` pushes → `webhook_echo.py` printed one `project.ops_appended` (first 1, last 2) 34 s later,
  "signature valid"; a `pack` job with `items: ["sheets"]` through `c.jobs.create` ran on PF6's worker with
  `fake_truebex.py` and its file URL downloaded (the fake app writes a stand-in file, not a PDF).
* **Reconciled on this branch (the merged dependencies):** master's `server/app/main.py` included `uploads.router` twice
  (under `# PF5` and again under `# PF4`, a leftover of landing PF5 on PF4 in T28) and imported `uploads` and
  `_upload_jobs` twice, so POST `/uploads`, GET `/uploads/{upload_id}` and PUT `…/parts/{n}` were registered twice and
  the OpenAPI schema carried duplicate operation ids. `tests/test_routes_unique.py` (written first, failing) checks that
  no (method, path) pair repeats and that FastAPI warns of no duplicate operation id; the second include and the
  duplicate imports are gone (`c6d1358`). Nothing else conflicted: the merged features build, lint and pass together.
* **Deviations from Design and why:**
  1. *The MCP package holds a stand-in.* The app repo has no `Tools/mcp/` yet (AI1), so `packages/mcp/server.js` and
     `tools.json` are written to agent-interface §5, §6.5 and §6.6 here (dual-era: `server/discover` at 2026-07-28,
     `initialize` answered at 2025-11-25 or 2025-06-18, `-32022` with `data.supported` for an unserved revision,
     `tools/list` with `ttlMs` 3 600 000 and `cacheScope` private, `tools/call` relayed over the per-user pipe,
     `app_not_running`, unknown tools `-32602` without reaching the app). `TRUEBEX_AGENT_PIPE` overrides the pipe name
     (the tests use it). `scripts/sync-mcp.ps1` copies the app's `server.js`, `tools.json` and fixture scripts over
     them at an app release and refuses to run until they exist. The `server/discover` result's exact fields are this
     reading of the contract (`supportedVersions`, `capabilities`, `serverInfo`); AI1's bridge is authoritative.
  2. *Interim fixture scripts.* `Docs/roadmap/fixtures/contracts/agent/` does not exist yet, so the five scripts of §9
     (`window-north-study`, `permissions`, `fence`, `legacy-initialize`, `app-not-running`) are written in
     `packages/mcp/test/fixtures/`, one `{"request", "answer"}` per line, `"<masked>"` for a volatile value. The fake
     pipe answers the lines the bridge relays (a `tools/call` of a known tool, a cancellation), in order.
  3. *Webhook event sources without touching other features.* `project.ops_appended` uses PF4's `on_ops_accepted`
     hook; every other event comes from a SQLAlchemy session observer (`webhooks/observe.py`: `after_flush` notes a job
     state becoming `succeeded`/`failed`, a share going `live`, a new version, a new non-owner member, an order or a
     supplier's part of it changing state, a feed run ending; `after_commit` emits from a fresh session;
     `after_rollback` forgets). So no PF4–PF8 module calls into webhooks, and an event is only sent for a saved change.
     `project.member_added` fires on the invitation (5.14), as the design table says. `market.feed.completed` goes to
     every member of the supplier. A `webhook.test` event (`POST …/test`) and a session-only `GET /webhooks/{id}/secret`
     (the dashboard's Reveal) are additions.
  4. *Dashboard routes.* The website manages endpoints through `/webhooks…` with the session (the same service as
     `/v1/webhooks…`), registered by `v1.install(app)` (the one line added to `main.py`), which also adds the shapes the
     document names without a route (`PushRequest`, `JobRequest`).
  5. *Raw bodies stay the contracts'.* `/v1/projects/{id}/ops` and `/v1/jobs` read their body raw and hand it to the
     contract routers' own code, so the 413 and 422 answers are theirs; their request schemas are documented by
     reference. Other `/v1` routes call the contract handlers with an `api_key` caller (`ProjectCaller.key_id` added);
     shares call `app/shares/service.py` (5.4 and 5.5 take a device in the contract router).
  6. *A key's pushes:* `author_kind` and `author` may be left out and are filled in (agent, the key's id as 32 hex,
     shown by `GET /v1/account` as `key.author`); a different value answers 422.
  7. *Scopes outside `/v1`:* PF6's `/jobs` already took API keys; it now checks `jobs:write` for writes and
     `projects:read` for reads. PF8's feeds check `supplier:feed` for developer keys after PF8's own membership rule
     (so a non-member still gets `not_supplier`); keys made before scopes keep PF8's feed access. A key made without
     `scopes` gets the read scopes. `GET /keys/scopes` lists the catalogue for the dashboard. Uploads take the scope of
     their purpose (share → `shares:write`, snapshot → `projects:write`, job-input → `jobs:write`). Two existing tests
     were updated for this: `test_render.py` (its key now asks for `jobs:write`, and a read-only key is refused) and
     `test_supplier_feeds.py` (the owner's developer key asks for `supplier:feed`).
  8. *Burst limit:* `API_KEY_BURST` 60 at once, refilled at `API_KEY_PER_MINUTE` 600, per key, in PF14's rate limiter
     (shared buckets with `RATELIMIT_BACKEND=db`); checked before the monthly quota, so a refused call is not counted.
  9. *Webhook URLs:* https only; hosts must resolve to public addresses only (no loopback, private, link-local,
     reserved or multicast; `.local`/`.internal`/`localhost` names refused), checked at registration and again before
     each delivery; no credentials in the URL; redirects are not followed (a 3xx is a failure). The check before each
     delivery narrows DNS rebinding; the HTTP client resolves the name again (no address pinning).
  10. *Deliveries:* one row per attempt (the delivery log); 8 sent at once within a 30 s budget per run, so a slow
      receiver never stalls the background loop; a run that dies mid-send is retried after 5 minutes. A re-send is one
      attempt without retries. Max 10 endpoints per account.
  11. *SDK generation:* the MIT generators make the types (datamodel-code-generator 0.26.5 → `truebex/models.py`
      TypedDicts; openapi-typescript 7.13.0 → `schema.d.ts`); `sdks/generate.py` (standard library) makes the operation
      layer of both SDKs from the same document, and the hand-written cores are small (`truebex/_http.py`, urllib only;
      `src/index.mjs`, fetch only). A test re-runs `generate.py --check` and checks the types name every schema. Both
      SDKs send the operation's `X-Truebex-Contract` (the document carries it as `x-truebex-contract`; a test checks the
      routes echo the same) and make an `Idempotency-Key` where an operation takes one. SDK and package licence: MIT
      (owner to confirm before publishing).
  12. *The document carries more than operations:* `x-truebex-scopes`, `x-truebex-webhook-events`, `x-truebex-limits`
      and `x-truebex-webhooks` (retry schedule, timeout, disable and keep days, debounce), so the docs pages generate
      those tables too. The marketplace and feed operations (PF7's and PF8's routes) get operation ids, descriptions and
      response schemas in the export, not in their routers.
  13. *Public copy:* the work still on the app's roadmap is labelled on its page (opening API projects in the app,
      cloud rendering for jobs, the Agent panel for MCP, placing products), and the SDK and MCP install lines say
      "Rolling out" until `DEVELOPER_DOCS.sdksPublished` / `mcpPublished` are true. Nothing moved into `FEATURES`. The
      MCP page names Claude Desktop and Claude Code in its install notes, as this doc's design asks (they are where the
      server is installed, not products Truebex is compared with).
  14. *PF7's sitemap check* asserted no `/market/` substring; `/developers/market/` now has one, so it checks the
      `…com/market/` prefix it meant.
* **Merged with master: PF11 (2026-10-11, Autopilot T32, `ap/t32-merge-t8-pf12-public-api-sdks-we`):** verify green
  (lint, build, pytest 516 collected, 511 passed and the 5 Postgres-only skips: master's 468, this feature's 44 and
  the merge's 4). Twelve files conflicted, each where both features append to a shared list (`config.py`,
  `server/.env.example`, `infra/secrets/server.env.example`, the deploy skill's secrets table, the model and job
  imports in `database.py`, `tasks.py` and `sqlite_to_postgres.py`, `main.py`'s router line, `test_ops.py`'s table
  list, `constants.ts`, the README section, the tracker): both sides kept, PF11's first. One fix where they meet:
  PF11 lets an analysis job name no project, but `JobRequest` required `project_id` and `at_seq`, so the Python SDK's
  `jobs.create` could not submit one (and a null `at_seq` is a 422). Both are optional in the document now (the render
  kinds still need them; the contract's 422 says so), `Job.project_id` may be null, and `openapi/v1.json` and both
  SDKs are regenerated (`scripts\gen-sdks.ps1` first reproduced the committed files unchanged).
  `tests/test_pf11_pf12_meet.py` (4): a key uploads a `job-input` through `/v1/uploads` and runs a `wind` job through
  `/v1/jobs` on a cpu-8 worker, the account's endpoint hears `job.succeeded` and the key reads the §6.3 result;
  `jobs:write` on both job routes and `projects:read` on `/analysis/catalogue`; `/ai/*` still refuses keys; the SDK
  submits an analysis with no project. Left as is: `JobRequest.kind` lists the contract's five kinds; PF11's
  `acoustics` and `texture` join it with their MINOR additions to `render-jobs.md` (the handler already takes
  `acoustics`).
* **Contract §11 rows** for the owner to set in `contracts/agent-interface.md` (the platform column): `server/discover`,
  `initialize` (legacy), `tools/list`, `notifications/cancelled` → "PF12 (package): done (stand-in until AI1's bridge is
  copied in)"; `read_state`, `find`, `explain`, `place`, `move`, `resize`, `fill`, `apply_theme`, `export_pdf`,
  `export_panorama`, `undo` → "PF12 (docs): done"; `tools/list` also "(docs): done". **MINOR proposals:**
  `share-bundle.md` §4 — API keys (`/v1/uploads`, `/v1/shares`, 5.1–5.9, `shares:write`; uploads by purpose scope);
  `project-log.md` §4 — the API key row is now served under `/v1/projects…` with `author_kind: "agent"` and the key's id
  as `author`; `render-jobs.md` — the `export` kind for IFC, DXF and DWG once IO2 and IO4 land (not built here);
  `agent-interface.md` §6.6 — the exact `server/discover` result fields, to be fixed by AI1.
* **Owner publishing steps (not done; tokens are the owner's):** after `scripts\gen-sdks.ps1` and a green gate:
  PyPI — `cd sdks\python; py -3.12 -m pip install build twine; py -3.12 -m build; py -3.12 -m twine upload dist/*`
  (project `truebex`); npm — `npm login` with the `@truebex` organisation, then `npm publish --access public` in
  `sdks\js` and in `packages\mcp`. Then set `sdksPublished` and `mcpPublished` to `true` in `src/lib/constants.ts`.
  Production also needs `WEBHOOK_SECRET_KEY` in `server.sops.env` (the deploy skill's secrets table names it).
* **Carry-over:** ~~AI1 → the real bridge, `tools.json` and the agent fixture scripts (then `scripts\sync-mcp.ps1`)~~ done 2026-10-13 by [PF12b](PF12b-mcp-package-adopts-ai1-bridge.md) (Autopilot T63: AI1's bridge copied, the stand-in removed);
  CL1 → API projects open in the app; CL3 → jobs run (the pack's real PDF); IO2/IO4 → the `export` job kind; the owner →
  publishing, `WEBHOOK_SECRET_KEY`, and the licence choice for the SDKs.
