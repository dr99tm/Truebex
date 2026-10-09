# PF14 — Operations: off the home PC, telemetry and crash ingestion (launch priority 1)

**Needs merged:** nothing. **Unblocks:** any paid launch (`00-understanding.md` §12: off the home PC "before any paid launch"); the production adapters behind every feature's storage, mail and background jobs (Plumbing table below); the real endpoints behind the app's OP1. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\telemetry.md` (C.9).

## Status

**Built on branch `ap/t3-pf14-operations-off-the-home-pc` (2026-10-09), awaiting merge, the owner's GD3 choices and the cutover (`infra/CUTOVER.md`); see As-built.** The telemetry contract's five endpoints, the admin dashboard, the jobs, the shared Plumbing, Postgres readiness and `infra/` are in place and tested; the VM does not exist until the owner runs `tofu apply`. Before this task, nothing of the VPS, Postgres, backups, monitoring, infrastructure as code or telemetry existed (`00-contract.md` P.1). What ran then, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| API process | `start-server.bat:18` | uvicorn on `127.0.0.1:8001 --proxy-headers` on the owner's PC |
| Public route | `start-tunnel.bat:6`; `.claude/skills/truebex-deploy/SKILL.md:32` | cloudflared tunnel `win-tunnel` maps `api.truebex.com` → `localhost:8001` |
| Failure mode | `README.md:246`, `:363` | PC or tunnel off → HTTP 530 / error 1033; sign-in, dashboard and billing stop |
| Database | `server/app/config.py:19` | SQLite `sqlite:///./auth.db` |
| SQLite-only code | `server/app/database.py:12-18` (`check_same_thread`), `:23-29` (`PRAGMA foreign_keys`), `server/app/usage.py:6`, `:40-50` (SQLite `insert … on_conflict_do_update`), `server/app/billing/service.py:30-31` (naive datetimes) | |
| Migrations | `server/app/database.py:57-72` | `ALTER TABLE … ADD COLUMN` and `CREATE UNIQUE INDEX IF NOT EXISTS` (both valid on Postgres) |
| Backups | `README.md:218` | "back up `auth.db` first", by hand |
| Health | `server/app/main.py:49-51` | liveness only |
| Processors named to users | `src/app/privacy/page.tsx:66-77` | Google, Stripe, Wayl, Cloudflare, GitHub |
| Telemetry, crash reports, feedback | — | nothing |

What the owner meant: app-side `00-understanding.md` §12.

## Goal

"Opt-in telemetry and crash reports with a privacy page, in-app feedback with a screenshot; the platform moves off the home PC to a VPS with Postgres, backups and monitoring before any paid launch" (`00-understanding.md` §12). Done means: the owner turns the PC off and people still sign in from the app and the site; the database is Postgres with point-in-time recovery and a tested restore; an alert reaches the owner's phone when the API is down; the whole host is rebuilt from `infra/`; the app's opt-in events, crash dumps and feedback land in a small admin dashboard and are deleted on schedule.

## Read first

* `docs/roadmap/40/00-contract.md` (P.1, P.2, P.3 item 5); app-side `00-contract.md` C.9.
* **`contracts/telemetry.md` v1.0.0** (2026-10-09) — the law for the ingestion half: §2 consent (off until the person says yes, on every tier), §4 no account on events and crashes (`install_id` = the first 32 hex of SHA-256 of the installation's secret), §5 the five endpoints, §6.1 the event allow-list (`events_version` 1), §6.3 crash signatures, §6.4 privacy rules and the server's scanner, §6.5 retention, §7 errors, §9 fixtures (copied into `server/tests/contracts/telemetry/`), §10 platform tests, §11 *implemented by*. It shares the wire header and error envelope of every contract (`licence-api.md` §3, §7).
* `guides/GD3-*.md` (cloud cost and infrastructure) is not written yet: provider, VM size, regions and backup retention below are placeholders `from GD3`. `guides/GD5-*.md` (UK GDPR, ICO registration) owns the legal text.
* `.claude/skills/truebex-deploy/SKILL.md` (updated by this task for the VPS), `README.md` "Running in production" (`:238`).
* Every PF doc's Data section: the tables this host must carry, and the Plumbing table here that they code against.

## Scope

**In:**
1. One Linux VM (Ubuntu LTS; size, provider and UK or EU region from GD3) running Docker Compose services `api`, `worker`, `postgres`, `caddy`.
2. Edge: Cloudflare stays in front (proxied DNS); Caddy terminates TLS with a Cloudflare origin certificate (`Full (strict)`); the VM firewall accepts 443 from Cloudflare's published ranges only and SSH by key only.
3. The tunnel retired for the API: `api.truebex.com` points at the VM; `start-server.bat` and `start-tunnel.bat` are kept for local use only and the README and the deploy skill say so.
4. Postgres for every table: `DATABASE_URL=postgresql+psycopg://…`, the `psycopg` driver pinned, `usage.record` made dialect-aware, every model checked on both dialects.
5. Data migration: `server/scripts/sqlite_to_postgres.py` (tables in foreign-key order, ids kept, sequences reset, row counts and per-table checksums compared) and the cutover runbook below.
6. Backups: continuous WAL archiving plus a nightly base backup to S3-compatible storage at a second provider, encrypted, 30 days kept (placeholder from GD3); object storage versioned; a weekly automated restore test into a scratch container with row-count comparison.
7. Monitoring and alerts: external uptime checks of `/health` and the new `/health/deep` every 60 s from several regions; host CPU, RAM, disk, load; container restarts; 5xx rate from Caddy's log; backup freshness; certificate expiry; PF6 queue depth when present; alerts by e-mail and phone push.
8. Infrastructure as code in `infra/`: OpenTofu for Cloudflare DNS (`api`, `api-staging`, `share` for PF5's links, the tiles CDN hostname for PF6, the mail records), buckets and, where the provider has an API, the VM and its firewall; cloud-init + `compose.yaml` + `Caddyfile` for the host; SOPS + age for secrets; `infra/deploy.ps1` and `infra/restore-test.ps1`.
9. `server/Dockerfile` (Python 3.12 slim, non-root, healthcheck) and image publishing to a private registry.
10. The Plumbing every feature codes against (table in Design): storage interface with `local` and `s3` adapters, mail with `console` and `smtp` adapters, background tasks inline or in the `worker` process, rate limiting; PF14 owns the production adapters and the interface definitions.
11. `GET /health/deep` (database and storage round trip, worker heartbeat age).
12. Telemetry ingestion of `contracts/telemetry.md` §5: the config with allow-list, sampling and kill switch (5.1); event batches kept to the allow-list (5.2); crash reports as one multipart request with symbolication against private symbols, signatures and known issues (5.3); feedback with screenshot and log, the account e-mail attached only with `reply` and a device token (5.4); deletion by install secret (5.5); the §6.4 privacy scanner; symbol upload per release.
13. API exceptions recorded into the same crash store (kind `server`), so one inbox covers app and server failures.
14. A simple admin dashboard: installations active per day, version adoption, top events, timings p50 / p95, crash-free sessions, crash groups with known-issue marking and a dump download, the feedback inbox with replies by e-mail; CSV export.
15. Retention exactly as §6.5 and the jobs that apply it; every installation's data deleted within 30 days of a 5.5 request.
16. Privacy: a telemetry, crash and feedback section on `/privacy/` and the processor list updated (VM provider, object storage, mail provider, uptime monitor; Wayl stays only while PF2 has not removed it).
17. Tests below, including a Postgres test run when `TEST_DATABASE_URL` is set.

**Out (and where it goes):**
* The app's telemetry client, the opt-in dialog, the Feedback command and the crash hook → OP1 (app).
* GPU and CPU worker pools for render and analysis jobs → PF6, PF11 (they reuse `infra/` conventions; sizes from GD3).
* Provider choice, VM size, prices and the monthly budget → GD3; the privacy policy's legal wording, ICO registration and processor agreements → GD5.
* Website analytics → PF13.
* Moving the static site off GitHub Pages → not planned (Pages behind Cloudflare stays).

## Design

### Infrastructure

| Component | Decision | Rejected and why |
|---|---|---|
| Host | one Linux VM, 4 vCPU / 8 GB / 160 GB SSD (placeholder from GD3), Docker Compose | Kubernetes or a managed container platform (an operational surface one person cannot carry); the home PC (the launch blocker) |
| Edge | Cloudflare proxy → Caddy (origin certificate, HTTP/2, access log as JSON); firewall: 443 from Cloudflare ranges, 22 by key | keeping cloudflared on the VM (the brief retires the tunnel for the API; an open 443 behind a Cloudflare-only firewall is simpler to debug) |
| Database | Postgres (current major) in a container on the VM disk; WAL archiving | managed Postgres (about twice the cost at this size; GD3 revisits with measured load); SQLite (one writer, no point-in-time recovery) |
| Backups | WAL + nightly base backups with an open-source tool (wal-g class) to a bucket at a second provider | VM snapshots alone (crash-consistent, same provider, no point in time) |
| Object storage | S3-compatible buckets; a CDN hostname in front of the public-cacheable prefixes (`tiles/`, `shares/`, `releases/`) | files on the VM disk (fills up, no CDN) |
| IaC | OpenTofu (MPL-2.0) + cloud-init + Compose; SOPS + age (the owner holds the age key) | Ansible (a second tool for one host); hosted state with a vendor |
| Monitoring | a hosted uptime checker (multi-region, 60 s) + a host metrics agent + Caddy log 5xx rate | self-hosted Prometheus and Grafana on the same VM (RAM, and it cannot report its own death) |
| Errors | API exceptions → the PF14 crash store | a third-party error tracker (another processor; the crash store exists anyway) |

RPO 5 min (WAL), RTO 2 h (fresh VM from `infra/` + restore); both placeholders GD3 confirms.

### Plumbing every feature shares

Interfaces are created by the first task that needs one, exactly as below (same paths, same signatures); PF14 owns the definitions and the production adapters. P.3 item 5 makes this the single swap point.

| Module | Interface | Adapters (owner) | Settings |
|---|---|---|---|
| `server/app/storage/` | `put(key, data, *, content_type, cache_control=None) -> BlobInfo`; `open(key)`; `stat(key) -> BlobInfo \| None`; `delete(key)`; `list(prefix)`; `signed_get_url(key, *, expires_in=900, filename=None)`; `signed_put_url(key, *, expires_in=900, content_type, max_bytes)`; `get_store()` | `local`: files under `STORAGE_DIR`, URLs served by `GET` / `PUT /files/{key}?exp=&sig=` (HMAC-SHA256) — first user (PF1); `s3`: presigned URLs, `CDN_BASE_URL` for public prefixes — PF14 | `STORAGE_BACKEND`, `STORAGE_DIR`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `CDN_BASE_URL` |
| `server/app/mail/` | `send_mail(to, template, data, *, reply_to=None)`; templates `server/app/mail/templates/<name>.subject.txt`, `.txt`, `.html` rendered with `string.Template` | `console` (dev and tests; `mail.OUTBOX`) — first user (PF8 or PF3); `smtp` (provider relay, SPF / DKIM / DMARC records in OpenTofu) — PF14 | `MAIL_BACKEND`, `MAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |
| `server/app/tasks.py` | `@periodic(name, seconds)`; `run_due(now)`; `start_inline(app)` | `inline` (asyncio loop started in `lifespan`, `server/app/main.py:23-26`) — first user (PF1); `worker` (`python -m app.worker`, one process) — PF14 | `BACKGROUND_TASKS=inline\|worker\|off` (tests: `off`, they call `run_due`) |
| `server/app/ratelimit.py` | `limit(key_fn, per_minute)` FastAPI dependency | in-process token bucket — first user (PF1); Postgres-backed buckets when `api` runs more than one process — PF14 | `RATELIMIT_BACKEND` |
| `server/app/metering.py` | `record(subject, metric, qty, day=None)`; `used(subject, metric, period)`; `check(subject, metric, qty) -> Allowed \| Overage \| Blocked` over table `meter_daily` | DB table — PF6 creates (metric `cu`, `render-jobs.md` §6.4); PF11 (`ai_credits`) and PF12 use | — |
| `server/app/contract_http.py` | `contract(name, major, minor)` router dependency (reads and echoes `X-Truebex-Contract`, 400 `contract_version`); `ContractError(code, status, detail, data)` and its handler writing the shared envelope `{detail, code, status, request_id, retry_after_s, data}`; FastAPI's 422 list mapped to `validation_failed` with `data.fields` | first contract router (PF1) | — |
| `server/app/idempotency.py` | `idempotent(scope)` dependency: `Idempotency-Key` (32 hex) kept 24 h in `idempotency_keys` (`key`, `account`, `route`, `body_sha256`, `status`, `response`, `created_at`); same key and body replay, other body 409 `idempotency_mismatch` | first user (PF4, PF6 or PF7) | — |
| `server/app/uploads/` | the resumable, content-addressed upload of `share-bundle.md` §5.1–5.3 (8 MiB parts, per-part and per-file SHA-256, 24 h sessions, `present` files), with purposes `share`, `snapshot`, `job-input`, `job-output` | PF5 (the contract's implementer); PF4 and PF6 reuse it, or create it to the contract if they land first | — |

### API

Shapes are the contract's (`telemetry.md` §5, §6); this is how the platform serves them (`server/app/routers/telemetry.py`, service `server/app/telemetry/`).

| # | Endpoint | Platform behaviour |
|---|---|---|
| 5.1 | `GET /telemetry/config` | from `server/app/telemetry/config.json` (the §6.1 allow-list, sampling, `max_batch` 500, `flush_s` 900) and the kill switch `TELEMETRY_EVENTS_ENABLED`; cache 24 h |
| 5.2 | `POST /telemetry/events` | ≤ 500 events, ≤ 256 KB (413 above); the privacy scanner first (422 `privacy_violation` with `data.field`); unknown names and props dropped and counted; `batch_id` is the idempotency key; 202 `{accepted, dropped}` |
| 5.3 | `POST /telemetry/crashes` | multipart ≤ 21 MB (`report`, `minidump` ≤ 20 MB, `log` ≤ 256 KB); stored, then symbolicated in the worker; `signature` = first 16 hex of SHA-256 over the top five `module!function` frames (§6.3), computed at once from the sent `callstack` and corrected after symbolication; `crash_id` repeats → `duplicate: true`; `known_issue` from the group's `fixed_in` |
| 5.4 | `POST /telemetry/feedback` | multipart ≤ 9 MB; with `reply: true` and a valid device token the account's e-mail is stored, a revoked token → 401; without, no e-mail ever |
| 5.5 | `POST /telemetry/delete` | always 202 `{install_id, complete_by}` (+30 days); the id derives from the secret, nothing is revealed |
| — | `/admin/telemetry/*`, `/admin/feedback/*`, `POST /admin/symbols` | admin (PF1's `require_admin`): summary, crash groups (status, `fixed_in`, note), signed dump download (900 s), feedback inbox with an e-mail reply, symbol upload |
| — | `GET /health/deep` | none, rate-limited: `{db, storage, worker_heartbeat_s}` or 503 |

The rate limit is the contract's: more than 60 requests an hour per installation or address → 429 `rate_limited` with `retry_after_s`; the address lives only in the limiter's memory (`test_no_ip_stored`).

### Data

| Table | Fields | Notes |
|---|---|---|
| `telemetry_events` | `id`, `received_at`, `install_id`, `session_id`, `batch_id`, `app_version`, `channel`, `build`, `os`, `locale`, `plan`, `hw` JSON, `seq`, `at`, `name`, `props` JSON | Postgres: monthly partitions; no address, no account |
| `telemetry_daily` | `day`, `name`, `app_version`, `events`, `installs`, `p50_ms`, `p95_ms` | kept after the raw rows go (§6.5) |
| `telemetry_batches` | `batch_id` PK, `install_id`, `received_at` | idempotency for 5.2 |
| `crash_groups` | `signature` (16 hex) PK, `first_seen`, `last_seen`, `count`, `versions` JSON, `status`, `title`, `fixed_in`, `note` | `known_issue` = `{title, fixed_in}` once set |
| `crash_reports` | `crash_id` PK, `received_at`, `kind` (`crash`, `hang`, `gpu_lost`, `ensure`, or `server`), `install_id`, `app_version`, `os`, `hw` JSON, `signature`, `frames` JSON, `minidump_key`, `log_key`, `symbolicated` | |
| `feedback` | `feedback_id` PK, `received_at`, `install_id`, `kind`, `text`, `reply`, `email` (only with `reply` and a token), `screenshot_key`, `log_key`, `app_version`, `status`, `replied_at` | |
| `telemetry_deletions` | `install_id`, `requested_at`, `completed_at` | proof the 30-day promise was kept |
| `symbol_files` | `module`, `debug_id`, `version`, `key` | Breakpad store layout `symbols/{module}/{debug_id}/{module}.sym` |

Storage keys: `telemetry/crashes/{yyyy}/{mm}/{crash_id}/minidump.dmp` and `log.txt`; `telemetry/feedback/{feedback_id}/screenshot.png` and `log.txt`.

| Data (§6.5) | Kept | Then |
|---|---|---|
| raw events | 13 months | daily counts per event and version stay; rows deleted |
| crash files (minidump, log) | 180 days | signature and counts stay; files deleted |
| feedback | 2 years, or until deletion is asked | deleted with its screenshot and log |
| request logs (Caddy, API) | 14 days | deleted |
| everything of an `install_id` after 5.5 | within 30 days | — |
| database backups | 30 days of WAL and nightly bases (GD3) | rotated; a deletion reaches backups when they rotate out, as the privacy page says |

### UI

* `/dashboard/admin/telemetry/` (noindex, `is_admin` from PF1): tabs Overview (installations per day through the existing `src/components/dashboard/UsageChart.tsx`, versions, top events, timings), Crashes (groups, frames, status, known issue and `fixed_in`, dump download), Feedback (inbox with screenshot preview, reply by e-mail when an address is stored), CSV export per tab.
* `src/app/privacy/page.tsx`: a section "Desktop app: usage events, crash reports and feedback" (what each holds and never holds, consent per kind, retention, "Delete my data") and the processor list.
* `README.md` "Running in production" rewritten for the VM; the "API depends on the host PC" row (`README.md:363`) removed; `.claude/skills/truebex-deploy/SKILL.md` API section rewritten (`infra/deploy.ps1`, health checks, restore test).

### Jobs / workers

| Job | Every | Does |
|---|---|---|
| `telemetry.rollup` | 1 h | aggregates finished hours into `telemetry_daily` |
| `telemetry.retention` | 24 h | applies the §6.5 table (the contract's `test_retention_job`) |
| `telemetry.deletions` | 1 h | completes pending 5.5 requests (well inside 30 days) |
| `crash.symbolicate` | 60 s | runs rust-minidump's `minidump-stackwalk` (MIT / Apache-2.0) against the symbol store; fixes the signature; groups |
| `backup.check` | 15 min | alerts when the last WAL archive is older than 15 min or the last base backup older than 26 h |
| `worker.heartbeat` | 30 s | writes the heartbeat `/health/deep` reports |

Symbols: PF1's `publish_release.py` gains `--symbols <dir>`, which runs `dump_syms` (MIT / Apache-2.0) over the Shipping PDBs from LC2's package gate and uploads the `.sym` files; the symbols are private and never served. Deploys: `infra/deploy.ps1` builds `server/Dockerfile`, pushes the image, runs `docker compose pull && docker compose up -d` over SSH and waits for `/health/deep`.

Cutover runbook (the task writes it to `infra/CUTOVER.md`; the owner runs it):
1. Provision with `tofu apply`; deploy; restore test green; `api-staging.truebex.com` serves the new stack against a copy of the data.
2. Announce a 15-minute window; stop the API window on the PC; copy `auth.db` aside.
3. Run `sqlite_to_postgres.py` against the VM's database through an SSH tunnel; counts and checksums match.
4. Switch the `api` DNS record to the VM in OpenTofu (proxied, so the change is immediate); remove the tunnel's `api` ingress.
5. Smoke: `/health/deep`, sign-in with password and Google, a payment-provider test webhook, the dashboard; the PC API stays off.

### Security and privacy

* SSH by key, no password login; Postgres reachable only on the Compose network; unattended security upgrades with a monthly reboot window.
* Secrets in SOPS files, decrypted at deploy into `server/.env` (mode 0600); one S3 key per role (api and worker read / write their prefixes; backups write-only to the backup bucket).
* Telemetry follows the contract: nothing leaves the app before consent (§2); no account on events and crashes (§4); the server's scanner refuses path separators, e-mail-shaped strings and off-type values (§6.4, 422 `privacy_violation`); the address is never stored; the account e-mail only with `reply`.
* Minidumps hold thread stacks, the module list and the exception record, never process memory (§5.3); still encrypted at rest, admin-only through signed URLs, 180 days. Logs arrive scrubbed (§6.4); the server re-runs the same rules and rejects what slips through.

## Deliverables

- [x] `infra/` (`tofu/` modules for DNS, buckets, VM, firewall; `host/cloud-init.yaml`, `host/compose.yaml`, `host/Caddyfile`; `secrets/*.sops.env`; `deploy.ps1`, `restore-test.ps1`, `CUTOVER.md`)
- [x] `server/Dockerfile`, `.dockerignore`; `psycopg`, `boto3` pinned in `server/requirements.txt`; `moto` and `PyYAML` in `requirements-dev.txt`
- [x] `server/app/usage.py` dialect-aware upsert; `server/scripts/sqlite_to_postgres.py`
- [x] Plumbing: `storage/s3.py`, `mail/smtp.py`, `app/worker.py`, the Postgres rate limiter; the interfaces themselves where no earlier task created them
- [x] `server/app/telemetry/` (`service.py`, `config.json`, `scanner.py`, `symbolicate.py`), `server/app/routers/telemetry.py`, admin routes, `/health/deep`
- [x] `server/tests/contracts/telemetry/` copied from the app repo's fixtures (copied, never edited)
- [x] `src/app/dashboard/admin/telemetry/`, privacy page section, README and deploy-skill updates
- [x] contract §11 rows recorded in As-built

## Tests

The eight `telemetry.md` §10 platform tests come first. Postgres tests carry `@pytest.mark.postgres` and run only when `TEST_DATABASE_URL` is set (a local container or the staging VM); the verify gate on this PC runs SQLite. Build checks read `out/` after the verify gate's build.

| Name | Kind | Asserts |
|---|---|---|
| `test_events_keep_allowlisted_drop_rest` | pytest | unknown names and props dropped and counted in `dropped` |
| `test_privacy_violations_rejected` | pytest | every case of `privacy-violations.json` → 422 naming its field |
| `test_no_ip_stored` | pytest | after a batch no table holds the client address |
| `test_crash_multipart_signature_and_duplicate` | pytest | 202 with a 16-hex signature; the same `crash_id` again → `duplicate` |
| `test_feedback_reply_attaches_account_email` | pytest | with a device token and `reply` the row has the account e-mail; without, none; revoked token → 401 |
| `test_delete_by_install_secret` | pytest | always 202; every row and file of the derived `install_id` gone after `telemetry.deletions` |
| `test_retention_job` | pytest | rows and files past §6.5 removed; daily counts and signatures kept |
| `test_contract_header_and_error_envelope` | pytest | header echoed; MAJOR 2 → 400 `contract_version`; envelope with `code` and `request_id` |
| `test_telemetry_config_kill_switch` | pytest | `enabled: false` when switched off; allow-list equals the fixture `config.json` |
| `test_telemetry_limits_and_rate` | pytest | 413 over 256 KB, 21 MB, 9 MB; 422 unknown `schema`; 429 past 60 an hour |
| `test_telemetry_known_issue_returned` | pytest | a group marked `fixed_in` 1.1.2 → 5.3 answers `known_issue` |
| `test_telemetry_scrub_matches_fixture` | pytest | the server scrubber turns `log-tail-raw.txt` into `log-tail-scrubbed.txt` exactly |
| `test_admin_telemetry_requires_admin` | pytest | 401 anonymous, 403 non-admin on every admin route |
| `test_server_exception_recorded_as_crash` | pytest | an endpoint raising → one `crash_reports` row of kind `server` |
| `test_db_postgres_init_and_migrate_twice` | pytest (postgres) | `create_all` + `_migrate` run twice without error on Postgres |
| `test_usage_record_upsert_sqlite_and_postgres` | pytest (+ postgres) | two calls give `count` 2 on each dialect |
| `test_sqlite_to_postgres_copies_rows_and_sequences` | pytest (postgres) | counts and checksums equal; the next insert gets max(id) + 1 |
| `test_health_deep_ok_and_db_down` | pytest | 200 with all fields; 503 when the engine fails |
| `test_storage_local_put_get_and_signed_urls` | pytest | round trip; tampered `sig` → 403; expired → 403; `../` key → 422 |
| `test_storage_s3_adapter_contract` | pytest | the same contract against `moto`'s in-process S3 |
| `test_mail_console_outbox_and_smtp_adapter` | pytest | console appends to `OUTBOX`; SMTP sends through a mocked `smtplib` |
| `test_tasks_run_due_respects_interval` | pytest | a 60 s task runs once per 60 s of fake time |
| `test_ratelimit_blocks_after_limit` | pytest | the call past the limit → 429 with `retry_after_s` |
| `test_infra_compose_file_shape` | pytest | `infra/host/compose.yaml` parses; every service has a healthcheck; `postgres` publishes no port |
| `test_site_pf14_admin_telemetry_noindex` | build check | `out/dashboard/admin/telemetry/index.html` carries `noindex` |
| `test_site_pf14_privacy_mentions_telemetry` | build check | `out/privacy/index.html` has the telemetry section heading |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. Local first: `docker compose -f infra/host/compose.yaml up` with a test `.env` → `curl http://127.0.0.1/health/deep` returns `{"db":"ok","storage":"ok",…}`.
2. After the owner's cutover: `curl https://api.truebex.com/health/deep` → 200 with a worker heartbeat under 60 s.
3. Turn the home PC off. From a phone: open `https://truebex.com/login/` and sign in → the dashboard shows the same plan, keys and devices as before the move.
4. From the app on a laptop (an LC1 build): sign in → the title bar shows the plan; restart the app → still signed in.
5. Send feedback with a screenshot from an OP1 build (or `curl -F feedback=@tests/contracts/telemetry/feedback.json -F screenshot=@tests/contracts/telemetry/screenshot.png -H "X-Truebex-Contract: telemetry/1.0" https://api.truebex.com/telemetry/feedback`) → it appears in `/dashboard/admin/telemetry/` → Feedback with the screenshot.
6. Upload the fixture crash (`report` + `minidump-stub.dmp` + log) the same way → Crashes shows a group with count 1 and a 16-hex signature; after `publish_release.py --symbols`, its frames read as function names.
7. `docker compose kill api` on the VM → the uptime alert reaches the phone within 3 min; `docker compose up -d api` → a recovery notice follows.
8. Run `infra/restore-test.ps1` → "restore OK", row counts equal to production's.
9. Open `https://truebex.com/privacy/` → the telemetry section with the retention periods of §6.5.

## Risks / traps

* `usage.record` imports the SQLite dialect (`server/app/usage.py:6`, `:40-50`) and fails on Postgres until it is dialect-aware; every later feature must avoid `sqlalchemy.dialects.sqlite` too.
* Postgres enforces `String(n)` lengths and foreign keys that SQLite let through; the copy script lists offending rows before the cutover, never truncates silently.
* Explicit ids copied into Postgres leave sequences behind: `setval` after the copy or the next insert collides.
* SQLite returns naive datetimes (`server/app/billing/service.py:30-31`), Postgres `timestamptz` aware ones; `_aware` and `parseServerDate` (`src/lib/api.ts:99`) already accept both; new code must too.
* Cloudflare's request-body limit (100 MB) stays with the proxy: large uploads use the resumable `/uploads` (8 MiB parts) or presigned URLs, never one big request; crash reports stay under the contract's 21 MB.
* Streaming responses (PF4 pulls, PF6 claims and status long-polls): Caddy must flush immediately, and waits stay at 25 s inside Cloudflare's 100 s idle timeout.
* Split brain: an API left running on the PC with its own `auth.db` after the cutover would accept writes nobody sees; the tunnel ingress for `api` is removed in step 4 of the runbook and the README says so.
* Parallel features add tables against SQLite; drift on Postgres shows only when `TEST_DATABASE_URL` is set, so the owner runs the Postgres job before each deploy.
* One VM is a single point of failure: RPO and RTO are written into `infra/CUTOVER.md` so nobody assumes more.
* Never run `next dev`; deploys are the owner's (P.2).

## As-built

* **Date, branch, commits:** 2026-10-09, `ap/t3-pf14-operations-off-the-home-pc` (base `master` at 744a9f3);
  `ac58ec4` (ingestion, plumbing, Postgres, `infra/`, site), `7d8c901` (docs, operator scripts, this row ticked), `0418574` (jobs on demand, 10-minute rollup) and the commit renaming the local-trial env files to `*.trial`.
* **Counts:** pytest 24 → 61 (`tests/test_telemetry.py` 18, `tests/test_ops.py` 17 (15 tests, two parameterised),
  `tests/test_site_pf14.py` 2). The verify gate on SQLite: 58 passed, 3 Postgres-marked skipped. With
  `TEST_DATABASE_URL` and `TEST_APP_DATABASE_URL` against a local Postgres 16.2 (the whole suite with the app on
  Postgres): 60 passed, 1 skipped (the SQLite-only parameter). `tofu validate` green (OpenTofu 1.13.1, providers
  locked for linux, windows and darwin); cloud-init renders to valid YAML. `out/`: 18 routes (+
  `/dashboard/admin/telemetry/`). A live run (uvicorn, SQLite, inline jobs) took the fixtures through all five
  endpoints, symbolicated the fixture crash within a minute of `scripts.upload_symbols`, and served the signed
  minidump download and the CSV export. Headless Edge on the served `out/` (built against the local API) rendered
  `/dashboard/admin/telemetry/` for an admin: the Telemetry nav link, the Overview stats, chart and tables, the
  symbolicated crash group with its frames and edit form, and the feedback card with its screenshot preview.
  `infra/deploy.ps1` dry-run with stubbed ssh / scp / sops: LF release archive, `bash -n` clean install and host
  scripts, decrypted files removed afterwards.
* **Deviations from Design and why:**
  1. *Fixtures authored here.* The app repo had no `Docs/roadmap/fixtures/contracts/telemetry/` yet, so PF14
     wrote the §9 set to the letter of `telemetry.md` v1.0.0 into `server/tests/contracts/telemetry/` (with a
     README); OP1 copies it to the app repo or replaces it, after which it is re-copied. Byte-exact via
     `.gitattributes` (`-text`).
  2. *Contract details the text left open*, proposed as a 1.0.1 PATCH for the app side to write (`telemetry.md`
     §3): `install_id` = first 32 hex of SHA-256 over the secret's 32 **raw bytes**; the signature joins the top
     five normalised frames with `\n`, a named frame normalises to `Module!Function` (parameter list and
     `+0x…` dropped), a raw `Module+0xOFF` to `Module!0xoff`; sizes are MiB (256 KiB, 21/20/9/8 MiB); `dropped`
     counts dropped events plus dropped props; 5.4 repeats also answer `"duplicate": true`; `privacy_violation`
     carries `data.reason` (`email`, `path`, `type`, `log`) beside `data.field`; feedback `text` is exempt from
     the scanner (the person writes it); a missing `X-Truebex-Contract` is served as the current version; the
     server's log scrubber replaces a whole absolute path ending in `.tbxp` / `.tbxa` / `.tbxpack` with
     `<project>` (it cannot know folder names) and refuses a tail the scrubber would still change.
  3. *PF1 pieces created first*, exactly at the Plumbing paths and signatures: `contract_http.py`, `storage/`
     (`local` and `s3`), `tasks.py`, `ratelimit.py`, `users.is_admin` + `require_admin`, and the `devices` table
     in PF1's full shape with `device_for_token` (PF14 only reads it for 5.4 replies). The PF1 merge keeps one
     copy of each.
  4. `telemetry_events` is a plain table with indexes on `received_at`, `at`, `install_id`; retention deletes by
     `received_at`. Monthly partitions wait for measured volume (they need a composite key SQLite cannot
     auto-increment).
  5. `crash_groups` gained `kind` and `merged_into`: a raw group stays as an alias after symbolication so later
     raw reports of the same build join the symbolicated group at ingest. `known_issue` is answered whenever the
     group has `fixed_in`.
  6. Symbols: `POST /admin/symbols` (≤ 90 MB) and `server/scripts/upload_symbols.py` (runs `dump_syms` on
     `.pdb`, takes `.sym` as is; `upload()` is what PF1's `publish_release.py --symbols` calls). Store layout is
     Breakpad's: `symbols/{module.pdb}/{debug_id}/{module}.sym`. Frames are named by `minidump-stackwalk` when
     the binary is present (it is in the image), otherwise from the sent callstack against the FUNC / PUBLIC
     records.
  7. Monitoring without a separate metrics agent: `infra/host/bin/host-check.sh` (systemd, every minute: disk,
     memory, load, container restarts and health, Caddy 5xx rate from its JSON log, origin-certificate expiry,
     PF6 queue-depth hook) pings the uptime monitor's heartbeat, so a dead host alerts too; the worker's
     `backup.check` reads `pg_stat_archiver` and the `backup.base` marker.
  8. `deploy.ps1` builds the image on the VM by default (this PC has no Docker); `-BuildLocally` builds on a PC
     with Docker, `-Registry` pushes to the private registry and the VM pulls.
  9. `infra/secrets/*.sops.env` cannot exist without the owner's age key: the task ships `.sops.yaml` with a
     placeholder recipient, `*.env.example` templates and `secrets/README.md`; the owner encrypts.
  10. Every FastAPI 422 is now the shared envelope (`code: validation_failed`, `detail` = the first message,
      `data.fields`), which the site's `toError` already reads; other existing errors are unchanged.
  11. Human test step 1 runs `infra/host/compose.local.yaml` (plain HTTP on 127.0.0.1:80, no backups), because
      the production Caddyfile only serves 443 with the origin certificate; it needs Docker Desktop.
  12. `/privacy/` names the new processors by role (server hosting, object storage, email delivery, uptime
      monitoring) until GD3 / GD5 name the companies; Wayl stays.
  13. `telemetry.rollup` runs every 10 minutes instead of every hour (it only recomputes the days that received
      events, so the dashboard is at most 10 minutes behind); `python -m app.worker --run <job> …` runs any job
      at once (operators, the human test).
* **GD3 numbers adopted (placeholders):** Hetzner Cloud `cpx31` (4 vCPU / 8 GB / 160 GB SSD) in `nbg1` (EU; no
  UK region); data bucket at the VM provider's S3-compatible storage, versioned, old versions 30 days; backups
  with wal-g (WAL every ≤ 60 s, nightly base 02:30 UTC, `retain FULL 30`, bucket expiry 37 days, libsodium
  encryption) at a second provider (Backblaze B2 EU in the example); Better Stack for uptime (60 s, four
  regions, e-mail + push, host heartbeat 60 s + 240 s grace); any SMTP relay with DKIM; Postgres 18; RPO 5 min,
  RTO 2 h. All in `infra/tofu/variables.tf`, `terraform.tfvars.example`, `infra/README.md`.
* **Contract §11 rows for the owner to set to "PF14: done" in `contracts/telemetry.md` at merge:**
  `GET /telemetry/config`, `POST /telemetry/events`, `POST /telemetry/crashes`, `POST /telemetry/feedback`,
  `POST /telemetry/delete` — each "PF14: done (2026-10-09, `ap/t3-pf14-operations-off-the-home-pc`)".
* **Carry-over → which feature:**
  * **Owner (before any paid launch):** GD3 choices into `terraform.tfvars`; the age key and the encrypted
    secrets; `tofu import` of the existing `api` (and, later, mail) records; `tofu apply`; `deploy.ps1` against
    staging; the restore test; `infra/CUTOVER.md`; the monitor's phone app; set the §11 rows; re-install the
    server venv (`pip install -r requirements-dev.txt`: psycopg, boto3, moto, PyYAML).
  * **PF1:** `publish_release.py --symbols <dir>` → `scripts.upload_symbols.upload()`; keep one copy of the
    shared files listed in deviation 3.
  * **OP1 (app):** copy the fixtures; adopt deviation 2 in the contract and the client.
  * **GD5:** processor names and the legal wording of the telemetry section on `/privacy/`.
  * **PF5 / PF6:** `share_target` and `cdn_target` in `terraform.tfvars`; PF6's queue depth as
    `/opt/truebex/bin/queue-depth`.
  * **Later:** monthly partitions of `telemetry_events` when volume calls for them. The image's
    `minidump-stackwalk` (0.27.0) and `wal-g` (v3.0.9) builds are first exercised by `deploy.ps1` (no Docker on
    this PC).
