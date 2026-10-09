# PF1 — Licence API, releases and downloads (launch priority 1)

**Needs merged:** nothing. **Unblocks:** PF2, PF3, PF4, PF5, PF7 (their Needs); the real endpoints behind the app's LC1, LC2, LC3. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\licence-api.md` (v1.0.0, 2026-10-09; the app side is authoritative).

## Status

Nothing of the licence API, the device model or the release feed exists (`00-contract.md` P.1; the contract's §11 lists every endpoint as "PF1: not yet"). The code this feature extends, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Plan catalogue | `server/app/plans.py:11` (`Plan`), `:23-48` (`PLANS`), `:51` (`get_plan`) | `free` / `pro` / `enterprise`: price, API quota, key limit; `:4` says "keep the two in step" with the site by hand |
| Plan resolution | `server/app/billing/service.py:55-65` (`effective_plan`), `:23` (`_RANK`), `:44-52` (`live_subscription`) | highest live subscription wins; `enterprise` set by hand (`:57`) |
| Accounts | `server/app/models.py:22` (`User`), `:36` (`plan` cache) | email + password or Google; no admin flag, no author id |
| Subscriptions | `server/app/models.py:93`, `:107` (`provider` is free text) | a trial fits as `provider="trial"` (contract 5.6) |
| Sessions | `server/app/security.py:32-38` (JWT), `:41-50` (decode), `server/app/config.py:16` (24 h) | cannot be revoked one by one: why the app holds a device token (contract §4) |
| Secrets stored hashed | `server/app/security.py:18`, `:53-60` | `tbx_live_` keys, SHA-256 only |
| Auth dependencies | `server/app/deps.py:21-46` (session), `:55-110` (API key) | no device auth |
| Routers | `server/app/main.py:18`, `:60-64` | auth, keys, usage, billing, v1 |
| Migrations | `server/app/database.py:45-54` (`_ADDED_COLUMNS`, nullable columns only), `:79` (`create_all`) | |
| Dashboard home | `src/app/dashboard/page.tsx:18`; API usage `:51`; plan panel `:65-78`; quick links `:82-99` | API-centred |
| Dashboard nav and guard | `src/components/dashboard/DashboardShell.tsx:12-17`, `:33-37` (redirects to `/login/?next=`) | `/dashboard/link/` inherits the sign-in redirect |
| Links into `/dashboard/keys/` that must keep working | `server/app/main.py:35`, `src/app/developers/page.tsx:64`, `:81`, `src/app/dashboard/page.tsx:83`, `:105` | |
| Sitemap / robots | `src/app/sitemap.ts:9-15`, `src/app/robots.ts:8` | five public URLs |

What the owner meant: app-side `00-understanding.md` §1.

## Goal

"A designer downloads the installer from the dashboard, starts Truebex, signs in with Google, gets a 14-day Pro trial, exports a PDF with no watermark; on day 15 the same export carries the watermark" (`00-understanding.md` §1). The platform half: a device signs in through the browser, is activated against a seat, and receives a signed entitlement it trusts offline; trials start and end by themselves; devices and seats are counted; releases (stable and beta) are published as signed manifests with notes and a 15-minute download link; the website gains Download and Changelog pages; the dashboard opens on Download, licence status and devices.

## Read first

* `docs/roadmap/40/00-contract.md` (P.1, P.3, P.5); app-side `00-contract.md` C.7 (`FCadEntitlement`), C.9, C.9.1.
* **`contracts/licence-api.md` v1.0.0** — the law for every shape here: §4 credentials and the two sign-in flows, §5 the fourteen endpoints, §6 the entitlement document, signature, plans and release manifest, §7 the error envelope and codes, §8 offline rules, §9 fixtures (copied into `server/tests/contracts/licence/`), §10 the platform tests, §11 *implemented by*. This doc adds only what the contract leaves to the platform: storage, tables, admin, pages, jobs.
* `guides/GD7-*.md` is not written yet: the matrix is the contract's placeholder (§6.3), P.5 applies.
* Code: the Status table; `server/tests/conftest.py:8-20` (test env), `:35` (`signup`); `server/tests/test_billing.py:138` (signed Stripe webhook helper).
* Skills: `truebex-brand-voice`, `truebex-seo` (two new public pages), `truebex-deploy` (never run by the task).
* RFC 8628 (the link-code pattern), RFC 8032 (Ed25519), RFC 8785 (JSON Canonicalization Scheme), SemVer 2.0.0.

## Scope

**In:**
1. Browser sign-in for devices (contract 5.1–5.3): link codes from the contract's alphabet, a hashed poll secret, approval on the website page `/dashboard/link/?code=…` (the contract's `verify_url`), a session token handed to the polling app once.
2. Activation (5.4) with a session token from the link flow or from the unchanged `/auth/login`: device rows keyed by fingerprint, device tokens `tbx_dev_…` stored as SHA-256, the same fingerprint reusing its device, `replace_device_id`, 409 `device_limit`.
3. Signed entitlement documents (5.5, §6.1–6.2): the RFC 8785 canonical form of the document signed with Ed25519 (`lic-*` kid), the detached envelope, `POST` refresh, a fingerprint mismatch revoking the token, device tokens lapsing after 90 days unused.
4. Offline grace exactly as §6.1: personal and named seats refresh after 24 h and expire after 14 days; floating seats 30 min and 2 h; trials and fixed terms end no later than their end.
5. Trials (5.6): one 14-day Pro trial per account and per fingerprint, stored as a `subscriptions` row with `provider="trial"`; 409 `trial_used`, 409 `plan_active`.
6. The Account panel (5.7) with the account's `author_id` (new, minted once per user) that `project-log.md` operations carry.
7. Devices and seats: list and remove (5.8, 5.9, by the website or the device), sign-out (5.10), `limits.devices` per seat, `seats {total, assigned}`, and one `seat_source(user)` function PF3 extends with named and floating seats (5.11 is PF3's).
8. Published public keys (5.12) for tests and the website; the app pins its own.
9. Release feed and downloads (5.13, 5.14): `truebex-release/1` manifests signed with a separate `rel-*` key at publish time, stable and beta channels, at most ten newest first, installers in storage, 15-minute download URLs that need no account.
10. Contract plumbing every contract router shares: the `X-Truebex-Contract` header, the §7 envelope with `code` and `request_id`, 400 `contract_version` (`server/app/contract_http.py`, PF14 §Design Plumbing).
11. Licence events recorded append-only (link approved, activation, replacement, revoke, trial, seat limit hit); PF3 builds the audit log on them.
12. Keys and secrets only on the server: the `lic-*` private key in `server/.env`; the `rel-*` private key never on the API host (the publish script reads it from a file the owner keeps); `server/scripts/make_signing_key.py`.
13. The plan catalogue moved to `server/app/catalogue.json`: tiers `free`, `pro`, `studio`, `team`, `enterprise` with the contract's placeholder matrix (§6.3), read by `plans.py`; ranks from the catalogue; existing rows keep working; display names Free, Pro, Studio, Team, Enterprise wherever a plan is named.
14. The installer uploaded per release: `server/scripts/publish_release.py` signs the manifest, stores the file through the storage interface and registers the row; `POST /admin/releases` for files up to 90 MB.
15. Public page `/download/`: requirements, latest stable version, size and date, a direct download (no account, contract 5.14), a sign-up link for the licence.
16. Public page `/changelog/` from the feed, one anchor per version matching the manifest's `notes_url` (`/changelog/#1.1.0`).
17. Dashboard home becomes Download + licence status + devices; API keys and Usage move under a **Developer** group in the dashboard navigation, URLs unchanged.
18. Admin flag `users.is_admin` (set by hand, like `enterprise`) and `require_admin` (PF7 and PF14 reuse it).
19. Tests: the contract's §10 platform tests with the §9 fixtures, a pytest for every endpoint (happy path, auth failure, validation failure) and the build checks below.

**Out (and where it goes):**
* `POST /licence/release` and named and floating seats, organisations, SSO, the audit-log UI → PF3.
* Prices, annual plans, seats bought, Paddle / Stripe, VAT, invoices → PF2.
* The pricing page, plan marketing copy, the home JSON-LD offers, the changelog's SEO layer, history entries and Arabic version → PF13.
* App sign-in UI, credential store, gates, watermark → LC1, LC3 (app); installer build and updater → LC2 (app); code-signing certificate → GD4.
* Object storage and a CDN for launch-scale downloads → PF14 (`s3` storage adapter).
* The matrix values → GD7.

## Design

### API

Request and response shapes are the contract's (§5, §6); this table says how the platform serves each one. Routers: `server/app/routers/licence.py` (`/licence`), `server/app/routers/releases.py` (`/releases`), `server/app/routers/admin.py` (`/admin`); dependencies `get_device`, `get_session_or_device`, `require_admin` in `deps.py`, telling credentials apart by prefix (contract §4).

| # | Endpoint | Platform behaviour |
|---|---|---|
| 5.1 | `POST /licence/link` | 8-character code from `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, dashed; poll secret stored as SHA-256; 600 s life; 429 `rate_limited` past 10 codes per IP per hour (`server/app/ratelimit.py`) |
| 5.2 | `POST /licence/link/poll` | 429 when polled faster than `interval_s`; on approval mints a session with `create_access_token` (`security.py:32-38`) and returns the existing `Token` shape (`server/app/schemas.py:37-40`) once; 410 `link_expired`, 403 `link_denied` |
| 5.3 | `POST /licence/link/approve` | session only; binds the code to the approving user; writes `link.approved` |
| 5.4 | `POST /licence/activate` | session only; finds the device by (`user_id`, `fingerprint`): 200 with a new token (old one revoked) or 201 new; counts active devices against `seat_source(user).devices_limit`; `replace_device_id` deactivates first; 409 `device_limit` with `data.devices` |
| 5.5 | `POST /licence/entitlement` | device token; fingerprint must equal the row's (else revoke, 409 `fingerprint_mismatch`); builds the document from the table below; updates `last_seen_at` |
| 5.6 | `POST /licence/trial` | device token; 409 `plan_active` when `effective_plan` is paid; 409 `trial_used` when `users.trial_used_at` or the fingerprint is already in `trial_fingerprints`; inserts the trial subscription |
| 5.7 | `GET /licence/account` | device token; plan, trial, seat, seats, devices, `manage_url` = `${SITE_URL}/dashboard/billing/` |
| 5.8, 5.9 | `GET /licence/devices`, `DELETE /licence/devices/{device_id}` | session or device; `current` marks the calling device; 404 `not_found` for another account's device |
| 5.10 | `POST /licence/deactivate` | device token; sets `deactivated_at`; idempotent |
| 5.12 | `GET /licence/keys` | the `lic-*` and `rel-*` public keys from settings |
| 5.13 | `GET /releases/feed` | rows of the channel (beta also lists stable), not withdrawn, newest first, ≤ 10; `latest`; manifests and signatures as stored at publish |
| 5.14 | `GET /releases/{version}/download` | no auth; 302 to `signed_get_url` (900 s) or the JSON form with `Accept: application/json`; 404 unknown version or platform |
| — | `GET /licence/link/{link_code}` | website only (session): the device name and app version shown on `/dashboard/link/` before Approve; platform-internal, outside the app contract |
| — | `POST /admin/releases`, `PATCH /admin/releases/{version}` | admin: multipart upload ≤ 90 MB with a manifest signed off-host; withdraw or edit `notes_md` (a new signature is required for a changed manifest) |

Entitlement document (§6.1) — where each key comes from:

| Key | Source |
|---|---|
| `plan`, `features`, `limits` | `seat_source(user)` → tier; the tier's catalogue entry (features sorted, unique) |
| `seat_kind` | `personal` (own subscription), `trial`, `free`; `named` / `floating` from PF3 |
| `device_id`, `fingerprint` | the device row |
| `issued_at`, `refresh_after`, `expires_at` | now; the §6.1 durations for the seat kind; `min(now + 14 d, trial or term end)` |
| `plan_period_end` | the live subscription's `current_period_end` (display only) |
| `trial` | a live `provider="trial"` row |
| `account` | `{user_id, email, author_id, org_id}` (`org_id` null until PF3) |
| `schema`, `nonce` | `truebex-entitlement/1`; 32 random hex |

The envelope is `{"document": …, "signature": {"alg": "Ed25519", "kid": "lic-…", "value": "<base64url>"}}` over the RFC 8785 bytes (`server/app/licence/jcs.py`, a 40-line canonicaliser for the contract's integer-and-string documents, checked against every fixture's `canonical` string).

### Data

| Table / column | Fields | Notes |
|---|---|---|
| `devices` (new) | `device_id` (32 hex UUIDv7) PK, `user_id` FK, `fingerprint` (64 hex), `name`, `os`, `app_version`, `token_hash` unique, `seat_kind`, `org_id`, `activated_at`, `last_seen_at`, `deactivated_at` | unique (`user_id`, `fingerprint`) among active rows; tokens lapse after 90 days unused |
| `link_codes` (new) | `link_code` PK, `poll_secret_hash`, `device_name`, `fingerprint`, `app_version`, `status` pending / approved / denied / spent, `user_id`, `expires_at`, `last_poll_at` | purged after expiry |
| `trial_fingerprints` (new) | `fingerprint` PK, `user_id`, `used_at` | once per machine |
| `licence_events` (new) | `id`, `at`, `user_id`, `device_id`, `kind`, `details` JSON | append-only; PF3 reads it |
| `releases` (new) | `version`, `platform`, `channel`, `manifest` (canonical JSON text), `signature`, `kid`, `storage_key`, `published_at`, `withdrawn_at` | unique (`version`, `platform`) |
| `users.author_id`, `users.is_admin`, `users.trial_used_at` | `VARCHAR(32)`, `BOOLEAN`, `DATETIME` via `_ADDED_COLUMNS` | nullable (`database.py:45-47`); `author_id` minted on first use, unique index |
| `subscriptions.seats` | `INTEGER` via `_ADDED_COLUMNS` | null = 1; PF2 writes it |
| `server/app/catalogue.json` (new) | `{source, tiers: [{id, name, rank, purchasable, features[], limits{}, api{monthly_requests, max_api_keys}}]}` | contract §6.3 placeholders; the site imports it at build time (`tsconfig.json:12`) |

Installers live at `releases/{version}/{platform}/{file}` through `server/app/storage` (PF14 Plumbing; this task creates the `local` adapter if it lands first). Settings: `LICENCE_SIGNING_KEY` (base64url Ed25519 seed), `LICENCE_KEY_ID`, `RELEASE_PUBLIC_KEYS` (kid → public key, for 5.12), `SIGNING_KEYS_EXTRA` (keys kept valid during a rotation, contract §3), `TRIAL_DAYS=14`.

### UI

| Page / component | What it shows | Copy |
|---|---|---|
| `src/app/download/page.tsx` (indexable) | h1 "Download Truebex for Windows"; requirements (the FAQ answer, `src/lib/constants.ts:328-329`); version, size, date from `src/content/releases.json`; a Download button that asks 5.14 for a fresh URL at click time; "Create a free account" for the licence | `DOWNLOAD` in `constants.ts` |
| `src/app/changelog/page.tsx` (indexable) | one section per release, `id` = the version (`#1.1.0`, the manifest's `notes_url`); notes rendered at build time by a small renderer for the contract's subset (headings, bullets, bold, links; HTML escaped) | `CHANGELOG` in `constants.ts` |
| `src/app/dashboard/link/page.tsx` (noindex through `src/app/dashboard/layout.tsx:6`) | reads `?code=` inside `Suspense` (as `src/app/dashboard/billing/page.tsx:256-262`); shows device name and app version from the website-only lookup; Approve / Deny → 5.3; "Only approve a code shown on your own computer" | inline |
| `src/app/dashboard/page.tsx` (rewrite) | Download panel (stable; beta for people who opt in), Licence panel (plan, seat, trial days left, renews / ends, Upgrade → billing), Devices panel (5.8, Remove with confirm → 5.9) | inline |
| `DashboardShell.tsx` `NAV` | Overview, Billing · **Developer**: API keys, Usage, API docs | |
| `src/lib/licence.ts` | typed calls through `api()` (`src/lib/api.ts:71`) | |

The API usage meter and quick start move from the home page to `/dashboard/usage/` and `/dashboard/keys/`. Plan names change at `src/app/dashboard/page.tsx:69`, `:75`, `src/app/dashboard/billing/page.tsx:118`, `src/app/developers/page.tsx:26-30` and `src/lib/constants.ts:239`, `:256`; layout and prices stay for PF2 and PF13. Rejected: moving keys and usage to `/dashboard/developer/…` (breaks the links in Status; a static export has no redirects); a full Markdown library for release notes (a dependency and a raw-HTML surface for four constructs).

### Jobs / workers

| Job or script | When | Does |
|---|---|---|
| `licence.links.purge` | every 600 s (`server/app/tasks.py`, PF14 Plumbing) | deletes expired and spent link codes |
| `licence.devices.lapse` | every 24 h | revokes device tokens unused for 90 days (contract §4) |
| `server/scripts/make_signing_key.py --kind lic\|rel` | by the owner | prints a new seed and its public key; the public half goes to the app's pinned keys first (contract §3: sign with a new kid no earlier than 30 days after the app pins it) |
| `server/scripts/publish_release.py --version --channel --platform --file --notes --key-file` | per release | hashes the installer, writes the `truebex-release/1` manifest, signs it with the `rel-*` key from `--key-file`, stores file and row |
| `scripts/sync-releases.mjs` (`npm run sync:releases`) | by the owner before a deploy | writes `src/content/releases.json` from 5.13; the build never touches the network (rejected: a `prebuild` fetch, which makes builds depend on the live API) |

### Security and privacy

* The contract decides detached Ed25519 over canonical JSON (§6.2) and pinned keys in the app; the platform keeps the `lic-*` seed only in `server/.env` and never holds the `rel-*` seed at all, so a compromised API host can neither ship an installer the updater accepts nor read anything it could not already change.
* Link codes: single use, 600 s, poll secret hashed, approval only by a signed-in browser that shows the device name first (RFC 8628 §5.4 warns of remote phishing).
* Fingerprints are hashes made by the app (`sha256` of a fixed prefix, MachineGuid and the user SID, contract §6.2); the server stores them only to bind tokens and count trials. `src/app/privacy/page.tsx` "What we collect" gains devices: name, OS, app version, fingerprint.
* Download URLs: HMAC over key and expiry (local adapter) or presigned (S3), 900 s.
* Every response carries `request_id`; logs carry it, never tokens or poll secrets.

## Deliverables

- [ ] `server/app/licence/` (`service.py`, `signing.py`, `jcs.py`, `devices.py`, `links.py`, `seats.py`, `ids.py` for UUIDv7), `server/app/routers/licence.py`
- [ ] `server/app/releases/service.py`, `server/app/routers/releases.py`, `server/app/routers/admin.py`
- [ ] `server/app/contract_http.py` (header, envelope, request id) if PF14 has not merged; `storage/`, `tasks.py`, `ratelimit.py` likewise (PF14 Plumbing)
- [ ] `server/app/catalogue.json`; `plans.py` reads it; `billing/service.py` ranks from it
- [ ] models, `_ADDED_COLUMNS`, settings, `.env.example`, `deps.py` dependencies; `cryptography` pinned in `server/requirements.txt`
- [ ] `server/scripts/make_signing_key.py`, `server/scripts/publish_release.py`
- [ ] `server/tests/contracts/licence/` copied from the app repo's `Docs/roadmap/fixtures/contracts/licence/` (copied, never edited)
- [ ] `src/app/download/`, `src/app/changelog/`, `src/app/dashboard/link/`, dashboard home, nav groups, `src/lib/licence.ts`, `src/content/releases.json`, `scripts/sync-releases.mjs`, `package.json` script
- [ ] `sitemap.ts` (+ `/download/`, `/changelog/`), privacy page, README API table
- [ ] contract §11 rows recorded in As-built

## Tests

The first eleven names are the contract's §10 platform tests, run against the §9 fixtures. Build checks are pytest functions in `server/tests/test_site_pf1.py` that read `out/` after the verify gate's build (skipped when `out/` is absent).

| Name | Kind | Asserts |
|---|---|---|
| `test_link_flow_pending_approved_expired` | pytest | 5.1–5.3: pending, approved (token once), spent, expired → 410, denied → 403 |
| `test_activate_signs_entitlement` | pytest | the signature verifies with the published key over the JCS bytes |
| `test_activate_same_fingerprint_reuses_device` | pytest | one row; the old token answers 401 |
| `test_device_limit_and_replace` | pytest | the third device → 409 `device_limit` with `data.devices`; `replace_device_id` → 201 |
| `test_entitlement_revoked_and_fingerprint` | pytest | 401 `device_revoked`; another fingerprint → 409 `fingerprint_mismatch` and the token revoked |
| `test_trial_once_per_account` | pytest | 201 then 409 `trial_used`; a new account on the same fingerprint also 409 |
| `test_plan_change_reaches_entitlement` | pytest | a signed Stripe event changes the next document; the browser cannot (as `server/tests/test_billing.py:58`) |
| `test_canonical_json_matches_fixtures` | pytest | JCS bytes of every fixture document equal its `canonical` |
| `test_release_feed_signed_and_ordered` | pytest | newest first, ≤ 10, beta lists stable too, each signature verifies with the `rel-*` key |
| `test_download_url_expires` | pytest | 302 to a URL that answers 403 after 900 s and when its signature is altered; JSON form with `Accept` |
| `test_contract_header_and_error_envelope` | pytest | `X-Truebex-Contract` echoed; MAJOR 2 → 400 `contract_version`; every error has `code` and `request_id` |
| `test_licence_link_rate_limits` | pytest | the eleventh code per IP per hour → 429; polling under `interval_s` → 429 |
| `test_licence_link_approve_requires_session` | pytest | 401 without session; 404 unknown code; 422 malformed code |
| `test_licence_activate_validation` | pytest | 422 `validation_failed` for a 63-hex fingerprint; 401 with a device token instead of a session |
| `test_licence_trial_plan_active_and_auth` | pytest | 409 `plan_active` on Pro; 401 without a device token; 422 `{"plan": "studio"}` |
| `test_licence_account_panel` | pytest | `author_id` 32 hex and stable; `devices.limit` from the catalogue; 401 without token |
| `test_licence_devices_list_remove_and_deactivate` | pytest | `current` flag; remove frees the slot; another account's id → 404; 5.10 idempotent |
| `test_licence_devices_lapse_after_90_days` | pytest | the lapse job revokes; the token answers 401 `device_revoked` |
| `test_licence_floating_durations_hook` | pytest | a stub `seat_source` returning `floating` yields 30 min / 2 h (PF3 plugs in here) |
| `test_licence_events_recorded` | pytest | approve, activate, replace, revoke and trial each write one row |
| `test_catalogue_matches_contract_placeholder` | pytest | five tiers in rank order; Free keys and limits exactly as §6.3; paid tiers add the §6.3 gate keys |
| `test_catalogue_existing_plans_keep_working` | pytest | `pro` users stay `pro`; unknown ids fall back to `free`; `free` API quotas unchanged (1,000 requests, 2 keys) |
| `test_admin_releases_requires_admin_and_signature` | pytest | 401 anonymous, 403 non-admin, 422 a manifest whose signature fails, 409 duplicate version, 201 valid |
| `test_publish_release_script_registers_row` | pytest | `publish()` stores the file and a row whose manifest states its size and SHA-256 |
| `test_site_pf1_download_page` | build check | `out/download/index.html`: one h1, canonical `/download/`, the version from `releases.json` |
| `test_site_pf1_changelog_anchors` | build check | `out/changelog/index.html` has an element with `id="1.1.0"` for each fixture version; canonical `/changelog/` |
| `test_site_pf1_link_page_noindex` | build check | `out/dashboard/link/index.html` carries `noindex` |
| `test_site_pf1_sitemap_and_no_secrets` | build check | sitemap holds `/download/` and `/changelog/`; no signing seed and no `PRIVATE KEY` under `out/` |
| `npm run lint`, `npm run build` | build check | green in the verify gate (`scripts/autopilot-verify.ps1:25-27`) |

## Human test

1. In `server/`: `.venv\Scripts\python.exe scripts\make_signing_key.py --kind lic` → put the seed into `server/.env` as `LICENCE_SIGNING_KEY`; `--kind rel` → keep the seed in a file outside the repo; add `http://127.0.0.1:31NN` to `CORS_ORIGINS`; start `server\run.bat` (:8000, `server/run.bat:18`) → "Application startup complete".
2. Build with `NEXT_PUBLIC_AUTH_URL=http://127.0.0.1:8000` and serve with `scripts/autopilot-serve.ps1` (port 3100 + task number, `scripts/autopilot-serve.ps1:15-17`).
3. In `server/`: `.venv\Scripts\python.exe scripts\publish_release.py --version 1.1.0 --channel stable --platform win64 --file <any 5 MB file> --notes notes.md --key-file <rel seed file>` → prints version, SHA-256 and storage key.
4. Open `/download/` signed out → one h1, the requirements, Download → the file saves with no sign-in; `certutil -hashfile <file> SHA256` equals step 3. `/changelog/#1.1.0` scrolls to the entry.
5. Sign up → the dashboard home shows Download (1.1.0, size, date), Licence "Free", Devices "No devices yet"; the nav has a Developer group with API keys and Usage.
6. Sign in from the app: in an LC1 build press Sign in → the browser opens `/dashboard/link/?code=…`. Without LC1: `curl -X POST http://127.0.0.1:8000/licence/link -H "Content-Type: application/json" -H "X-Truebex-Contract: licence-api/1.0" -d "{\"device_name\":\"TEST-PC\",\"fingerprint\":\"<64 hex>\",\"app_version\":\"1.0.0\"}"` → `link_code` and `verify_url`; open the URL.
7. The page shows "TEST-PC · 1.0.0"; press Approve → "Approved". The app (or `curl …/licence/link/poll` with the poll secret) receives a session, then calls `/licence/activate` → a device token and an entitlement.
8. Dashboard → Devices lists TEST-PC, last seen just now; `GET /licence/keys` and the envelope's signature verify with `.venv\Scripts\python.exe -m app.licence.signing verify envelope.json` → "valid · plan free · expires <14 days ahead>".
9. Start the trial (LC1 Account panel, or `curl -X POST …/licence/trial -H "Authorization: Bearer tbx_dev_…" -d "{\"plan\":\"pro\"}"`) → the Licence panel reads "Pro trial · 14 days left"; a second trial → 409 `trial_used`.
10. Remove TEST-PC on the dashboard → it disappears; `POST /licence/entitlement` with its token → 401 `device_revoked`.

## Risks / traps

* Static export (`next.config.ts:4`, `:9`): no dynamic segments for runtime ids; `/dashboard/link/` reads `?code=` with `useSearchParams` inside `Suspense`.
* Python 3.12's `uuid` module has no version 7 (the contract's ids are UUIDv7): `server/app/licence/ids.py` builds them (48-bit milliseconds, version and variant bits, random rest), tested for order and format.
* Canonical JSON must match the app byte for byte: the fixtures' `canonical` strings are the referee; never `json.dumps(sort_keys=True)` alone (its escaping of non-ASCII and floats differs from RFC 8785).
* Cloudflare's request-body limit (100 MB on the current plan) applies through the tunnel: installers are published on the host by the script, never uploaded through `api.truebex.com`; downloads through the home tunnel are slow, so launch-scale downloads wait for PF14's object storage and CDN.
* `_RANK` is hard-coded (`server/app/billing/service.py:23`, used at `:49`): a `team` row would rank as `free` unless ranks come from the catalogue.
* `effective_plan` writes the cache on read (`server/app/billing/service.py:61-64`): entitlement issuance inherits that; one commit per request on SQLite.
* Google-only accounts get 401 from `/auth/login` (`server/app/routers/auth.py:44-48`); the app then offers the browser link (contract §4).
* `cryptography` is only transitive today (via `python-jose[cryptography]`, `server/requirements.txt:8`); pin it, `signing.py` imports it.
* Hot spots shared with parallel PF branches: `main.py` include lines, `models.py`, `_ADDED_COLUMNS`, `config.py`, `constants.ts`, `sitemap.ts`, `DashboardShell.tsx`; add in own blocks, the merge task integrates.
* Never run `next dev` (P.2); never deploy from the task.

## As-built

* Date, branch, commits:
* Counts (pytest before → after; pages in `out/`):
* Deviations from Design and why:
* TODO (P.5): GD7 matrix copied into `server/app/catalogue.json` (date, GD7 revision):
* Contract §11 rows for the owner to set to "PF1: done" in `contracts/licence-api.md` at merge:
* Carry-over → which feature:
