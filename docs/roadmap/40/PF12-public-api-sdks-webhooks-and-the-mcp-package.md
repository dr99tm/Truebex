# PF12 — Public API, SDKs, webhooks and the MCP package (launch priority 2)

**Needs merged:** PF4. **Unblocks:** none. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\agent-interface.md` (v1.0.0: the MCP package and the tools reference are PF12's per its §11); the `/v1` mirror follows `project-log.md` §3 ("PF12 later mirrors these paths under `/v1/projects` with the same shapes"), `render-jobs.md` §4 and `marketplace-api.md` §4.

## Status

The developer API has two endpoints and no scopes, webhooks, SDKs or MCP package. Verified with Grep on 2026-10-09:

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

* Date, branch, commits:
* Counts (pytest before → after; SDK and package versions):
* Deviations from Design and why:
* Contract §11 rows for the owner to set to "PF12: done" in `contracts/agent-interface.md`; the MINOR proposals:
* Owner publishing steps (PyPI, npm) and their dates:
* Carry-over → which feature:
