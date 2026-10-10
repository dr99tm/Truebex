# PF5 — Share pages (launch priority 1)

**Needs merged:** PF1. **Unblocks:** none by Needs; PF4 (snapshots) and PF6 (job inputs and outputs) reuse its upload protocol. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\share-bundle.md` (v1.0.0, 2026-10-09; the app side is authoritative).

## Status

**Done 2026-10-09** on `ap/t5-pf5-share-pages` (Autopilot T5): all eleven endpoints of share-bundle v1.0.0, the share page `/view/{slug}` with its own preview, the viewer bundle, the dashboard's Shares page and the jobs; see As-built. The text below is the state before the work.

Before: no share pages, uploads or bundles existed (`00-contract.md` P.1; the contract's §11 lists all eleven endpoints as "PF5: not yet"). What this builds on, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Static export | `next.config.ts:4` (`output: "export"`), `:9`, `:15` | one HTML file per route at build time: why a per-share preview needs a server route (contract §6.2) |
| Site-wide link preview | `src/app/layout.tsx:41-61` (Open Graph and Twitter images) | the same card for every page |
| Card generation precedent | `scripts/make_web_assets.py:26` (Pillow), `:137-138` (`og_image`, 1200 × 630) | build-time only; the server has no Pillow (`server/requirements.txt:1-15`) |
| CORS | `server/app/main.py:39-46` | the site's origins only; `expose_headers` lists the rate-limit pair |
| Static host headers | `https://truebex.com/` answers `access-control-allow-origin: *` (checked 2026-10-09) | a page on another origin may load the site's viewer script as a module |
| From PF1 (Needs) | device tokens, entitlement `limits.share_links` and `share.links`, `contract_http.py`, `storage/`, `tasks.py`, `ratelimit.py` | |

What the owner meant: app-side `00-understanding.md` §7.

## Goal

"Save three views, press Share, send the link; the client walks the lit living room on a phone and sees 'Designed in Truebex'" (`00-understanding.md` §7). The app uploads a bundle (panoramas with hotspots, renders, the sheet PDF, the title); the platform stores it, publishes one page per share with its own link preview, counts visits without tracking people, and ends the page at its expiry or when the designer revokes it.

## Read first

* **`contracts/share-bundle.md` v1.0.0** — the law: §4 credentials, §5.1–5.3 the resumable upload (also used by `project-log.md` snapshots and `render-jobs.md` inputs and outputs), §5.4–5.11 shares, page data and visits, §6.1 the manifest rules, §6.2 the share record and the decision that `url` is a server route writing per-share preview tags around the viewer shell, §7 errors, §8 retry, §9 fixtures (copied into `server/tests/contracts/share-bundle/`), §10 platform tests, §11 *implemented by*.
* `contracts/licence-api.md` §4 (device tokens), §6.3 (`share.links`, `limits.share_links`).
* `guides/GD7-*.md` is not written yet: live shares, bytes and the longest expiry per tier are placeholders (30 days, 1 GiB, contract §5.4 and §6.1).
* Specifications: The Open Graph protocol (ogp.me); WHATWG HTML (`<meta>`), Robots Exclusion Protocol (RFC 9309).
* Skills: `truebex-brand-voice` (the footer line and the card), `truebex-seo` (share pages are `noindex`).

## Scope

**In:**
1. The resumable upload of contract §5.1–5.3: sessions for up to 500 files of up to 512 MiB, 8 MiB parts each hashed, files content-addressed per account (`present` when already stored), 24-hour sessions, resume through 5.3; purposes `share`, `snapshot`, `job-input`, `job-output` (the last for worker tokens only).
2. Shares (5.4–5.9): create from a manifest (idempotent by `bundle_id`), publish when every file is complete, list, one share with visits by day, change title or expiry, revoke.
3. The manifest rules of §6.1 checked on create (422 `manifest_invalid` with `data.errors[]`), against `manifest-invalid.json`'s cases.
4. A public page per share: a server route at the share's `url` writes the share's own title, description and image tags around the static viewer shell; the viewer shows the panoramas with hotspots, the renders, the sheet PDF, the project title and "Designed in Truebex" with a link to download Truebex.
5. The page data (5.10): manifest and file URLs signed for 1 h; panorama derivatives (4096 × 2048 and 1024 × 512) made at publish so phones never decode an 8k texture they cannot hold.
6. The OG card per share: a 1200 × 630 JPEG composed at publish from the first panorama around its start bearing, the title and the "Designed in Truebex" mark.
7. Visits counted (5.11): `visitor` id kept by the page for 24 h, unique = distinct (visitor, UTC day), no IP address or user agent stored, 429 past 60 a minute per address.
8. Expiry and revoke: 410 `share_gone` for the data and a "This link has ended" page with status 410 for the HTML; files deleted 7 days after expiry or revoke.
9. Share limits per tier: live shares (`limits.share_links`), bytes per bundle and longest expiry (`share_bytes`, `share_days` proposed as a MINOR addition to `licence-api.md` §6.3; 1 GiB and 30 days until then).
10. Pages that are static-friendly: the viewer is a prerendered static bundle on truebex.com; the bundle comes from the API or object storage; only the small HTML wrapper is rendered per request.
11. The website's Shares list in the dashboard (session auth 5.6–5.9): visits, copy link, extend, revoke.
12. Tests: the contract's §10 platform tests with its fixtures, a pytest for every endpoint (happy path, auth failure, validation failure) and build checks for the viewer bundle.

**Out (and where it goes):**
* Rendering panoramas and renders, the watermark, the Share command and the Shares panel → PR3, LC3, PR4 (app).
* Panoramas re-rendered from the cloud as tiles (live share pages) → PF6, then PF9 shows them.
* Indexing share pages in search → never (they are private links; `noindex`).
* A custom share domain's DNS (`share.truebex.com`) → PF14 (OpenTofu); until then `url` uses `API_URL`.

## Design

### API

Shapes are the contract's. Routers `server/app/routers/uploads.py` and `server/app/routers/shares.py`; services `server/app/uploads/` (PF14 Plumbing row) and `server/app/shares/`.

| # | Endpoint | Platform behaviour |
|---|---|---|
| 5.1–5.3 | `/uploads…` | parts written to `uploads/parts/{upload_id}/{sha256}/{n}` with `X-Part-Sha256` checked; the last part assembles the file and checks size and SHA-256 (422 `file_hash_mismatch` drops its parts); files kept at `blobs/{account_id}/{sha256}`; the `s3` adapter (PF14) maps parts onto S3 multipart uploads |
| 5.4 | `POST /shares` | device token; quota (live shares, bundle bytes) → 403 `quota_exceeded`; §6.1 checks; returns the share (`uploading`) and the upload session; the same `bundle_id` returns the same share |
| 5.5 | `POST /shares/{id}/publish` | every manifest file complete (else 422 `upload_incomplete`); makes derivatives and the card; mints the slug (10 base62 chars); state `live` |
| 5.6–5.9 | `/shares…` | device or session; 404 for another account's share; 422 `expiry_too_far` past the tier's maximum |
| 5.10 | `GET /s/{slug}` | JSON for the viewer: title, dates, `watermark`, `designed_in`, the manifest with every file's URL signed for 1 h and the derivatives' URLs; 410 `share_gone` |
| 5.11 | `POST /s/{slug}/visits` | `{visitor}`; one row per (share, visitor, UTC day); 429 `rate_limited` from the in-memory limiter |
| `url` | `GET /view/{slug}` | the HTML wrapper below; `Cache-Control: public, max-age=300`; 410 page when gone; `X-Robots-Tag: noindex` |

The share `url` is `${SHARE_BASE_URL}/view/{slug}` (`SHARE_BASE_URL` defaults to `API_URL`; PF14 later points `share.truebex.com` at it). **Decision:** the HTML lives at a path of its own. Rejected: content negotiation on `/s/{slug}` (crawlers send different `Accept` headers; one sending `*/*` would get JSON and show no preview).

The wrapper (rendered with `string.Template`, about 2 KB):

| Part | Content |
|---|---|
| `<head>` | `<title>`, `description`, `og:type` website, `og:title` = "<title> — designed in Truebex", `og:description` = "<n> panoramas, <n> renders and the drawings." (≤ 160 chars), `og:image` = the card URL, `og:image:width` 1200, `og:image:height` 630, `og:url` = the share `url`, `twitter:card` `summary_large_image`, `robots` `noindex`, a `<link rel="preload">` for the start panorama's 4096 derivative |
| `<body>` | `<main id="viewer" data-slug data-api>`, a `<noscript>` block with the title, the first render as an `<img>` and the PDF link, and `<script type="module" src="${SITE_URL}/viewer/viewer.js">` |

**Decision:** the viewer is a framework-free TypeScript bundle in `src/viewer/`, built by esbuild after `next build` into `out/viewer/viewer.js` and `viewer.css`, so a page served from the API's origin can load it from truebex.com. Rejected: a Next page wrapped by the API (its runtime loads chunks relative to the serving origin, which is the API); an iframe of a Next page (gyroscope and immersive modes need extra permission-policy grants inside a cross-origin frame); a Cloudflare Worker in front of truebex.com (a second runtime the platform's pytest cannot test, contract test `test_share_url_has_its_own_preview`); `https://truebex.com/s/?k=<slug>` (the contract's rejected alternative).

### Data

| Table | Fields | Notes |
|---|---|---|
| `upload_sessions` | `upload_id`, `account_id`, `credential_kind`, `purpose`, `files` JSON (sha256, bytes, content type, state, received parts), `expires_at` | 24 h |
| `blobs` | `account_id`, `sha256`, `bytes`, `content_type`, `storage_key`, `created_at`, `refs` | content-addressed per account; `refs` counts shares, snapshots, jobs |
| `shares` | `share_id` (32 hex), `account_id`, `bundle_id` unique per account, `slug` unique, `title`, `state`, `manifest` JSON, `bytes`, `watermark`, `card_key`, `created_at`, `published_at`, `expires_at`, `revoked_at`, `purge_after` | |
| `share_derivatives` | `share_id`, `source_sha256`, `kind` (`pano-4096`, `pano-1024`), `storage_key` | made at publish |
| `share_visits` | `share_id`, `day`, `visitor` (32 hex), `count` | unique (`share_id`, `day`, `visitor`); no address, no user agent |

Storage keys: `blobs/{account_id}/{sha256}`, `shares/{share_id}/derived/{sha256}-{kind}.jpg`, `shares/{share_id}/card.jpg`. Settings: `SHARE_BASE_URL`, `SHARE_MAX_DAYS=30`, `SHARE_MAX_BYTES=1073741824`. `Pillow` and `esbuild` (devDependency) are added.

### UI

| Piece | What it does |
|---|---|
| `src/viewer/` (`main.ts`, `pano.ts`, `gallery.ts`, `pdf.ts`, `viewer.css`) | tabs Panoramas · Renders · Drawings; the panorama view through an MIT-licensed WebGL equirectangular viewer (chosen by the task: hotspots, drag and gyroscope control, ≤ 150 KB gzipped, no telemetry), bearings mapped per §6.1 (0 = north, `center_bearing_deg` at the image's middle column); hotspots by `bearing_deg` / `pitch_deg` with labels; the 4096 derivative when `MAX_TEXTURE_SIZE` < 8192 or on a metered connection; renders as a swipe gallery; the PDF through an open-source JavaScript PDF renderer loaded only when Drawings opens, with a Download PDF button; header title; footer "Designed in Truebex · Get Truebex for Windows" → `${SITE_URL}/download/?utm_source=share`; "Update needed" for an unknown manifest MAJOR |
| `scripts/build-viewer.mjs` | esbuild bundle and CSS from the brand tokens of `src/app/globals.css`; `npm run build` = `next build && node scripts/build-viewer.mjs` |
| `src/app/dashboard/shares/page.tsx` (noindex) | live and ended shares, visits (total, unique, by day), copy link, extend, revoke with confirm |
| `src/lib/constants.ts` | `SHARE_PAGE` copy (footer line, ended-page text, Update needed) |

### Jobs / workers

| Job | Every | Does |
|---|---|---|
| `shares.expire` | 300 s | marks shares past `expires_at` as `expired`, sets `purge_after` = +7 days |
| `shares.purge` | 1 h | deletes files, derivatives and cards of shares past `purge_after`; drops blobs whose `refs` reach 0 |
| `uploads.expire` | 1 h | drops sessions and parts older than 24 h |

### Security and privacy

* Slugs are 10 base62 characters (about 59 bits), never sequential; file URLs signed for 1 h; the HTML and the data say `noindex` while the API host's `robots.txt` still allows `/view/`, so link-preview crawlers can read the tags without search engines listing the page.
* Uploads are bound to the credential's account; a worker token may only open `job-output` sessions.
* Visits keep no address or user agent; the limiter holds the address in memory only.
* What travels is what the designer chose to publish (§6.1: no `.tbxp`, no entity ids, no paths); the watermark is reported, never added or removed here.

## Deliverables

- [x] `server/app/uploads/` (`service.py`, `assemble.py`), `server/app/routers/uploads.py`
- [x] `server/app/shares/` (`service.py`, `manifest.py` with the §6.1 rules, `derivatives.py`, `card.py`, `page.py` + `templates/view.html`), `server/app/routers/shares.py`; `Pillow` pinned; Open Sans TTF (OFL) and the mark PNG under `server/app/shares/assets/`
- [x] models, settings, `.env.example`; `robots.txt` route on the API allowing `/view/`
- [x] `src/viewer/`, `scripts/build-viewer.mjs`, `package.json` (`esbuild` devDependency, build script), `src/app/dashboard/shares/`, `src/lib/shares.ts`, copy in `constants.ts`
- [x] `server/scripts/demo_share.py` (uploads the contract's fixture bundle with a device token, for the human test before PR4 lands)
- [x] `server/tests/contracts/share-bundle/` copied from the app repo's fixtures (copied, never edited)
- [x] contract §11 rows and the licence §6.3 MINOR proposal (`share_bytes`, `share_days`) recorded in As-built

## Tests

The first nine names are the contract's §10 platform tests.

| Name | Kind | Asserts |
|---|---|---|
| `test_upload_parts_resume_and_dedup` | pytest | parts in any order, a repeated part, a resumed session, `present` files |
| `test_part_and_file_hash_mismatch` | pytest | 422 `part_hash_mismatch`; 422 `file_hash_mismatch` drops the file's parts |
| `test_share_publish_requires_all_files` | pytest | 422 `upload_incomplete` with `data.missing` |
| `test_manifest_rules` | pytest | every case of `manifest-invalid.json` answers its expected error |
| `test_share_page_data_and_signed_urls` | pytest | 5.10 lists every file with a URL that stops working after 1 h |
| `test_share_expiry_and_revoke_gone` | pytest | 410 `share_gone` after expiry and after revoke, for the data and the HTML |
| `test_visits_unique_per_day` | pytest | two visits by one visitor on one day count once in `unique` |
| `test_share_url_has_its_own_preview` | pytest | the `url` HTML carries this share's `og:title`, `og:image` (1200 × 630) and `noindex` |
| `test_contract_header_and_error_envelope` | pytest | header echoed; MAJOR 2 → 400 `contract_version`; envelope with `code` and `request_id` |
| `test_uploads_auth_and_purpose_scoping` | pytest | 401 without credential; a session cannot add parts to a device's session; a worker token only `job-output` |
| `test_uploads_session_expired_and_out_of_range` | pytest | 410 `upload_expired` after 24 h; 422 `part_out_of_range` |
| `test_shares_quota_exceeded` | pytest | a second live share on Free → 403 with `data.limit` 1; bytes over the tier → 403 |
| `test_shares_create_idempotent_by_bundle` | pytest | the same `bundle_id` returns the same share |
| `test_shares_list_get_patch_revoke_auth` | pytest | device and session work; another account's share → 404; 422 `expiry_too_far` |
| `test_shares_card_and_derivatives_made` | pytest | publish writes a 1200 × 630 card and the 4096 and 1024 derivatives of every panorama |
| `test_shares_files_purged_after_seven_days` | pytest | `shares.purge` removes files and the card; blobs with other refs stay |
| `test_shares_visits_rate_limited_no_ip` | pytest | the sixty-first visit in a minute → 429; `share_visits` holds no address |
| `test_site_pf5_viewer_bundle_built` | build check | `out/viewer/viewer.js` and `viewer.css` exist; `viewer.js` ≤ 250 KB before gzip |
| `test_site_pf5_dashboard_shares_noindex` | build check | `out/dashboard/shares/index.html` carries `noindex` |
| `npm run lint`, `npm run build` | build check | green; the build now runs the viewer step |

## Human test

1. With PF1's signing key in `server/.env` (PF1 human test step 1), and so a phone on the same Wi-Fi reaches both: build with `NEXT_PUBLIC_AUTH_URL=http://<LAN address>:8000` and serve with `scripts/autopilot-serve.ps1`; in `server/.env` set `SITE_URL=http://<LAN address>:31NN` (the wrapper loads `viewer.js` from it), `SHARE_BASE_URL=http://<LAN address>:8000` and add the site's LAN origin to `CORS_ORIGINS`; start the API with `.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000` (`server/run.bat:18` binds 127.0.0.1 only).
2. Upload a bundle from the app: in a PR4 build press Share on the house; without PR4, in `server/` run `.venv\Scripts\python.exe scripts\demo_share.py --token tbx_dev_… --fixture tests\contracts\share-bundle\manifest-house.json` → it prints the parts sent and the `url`.
3. Run step 2 again → "0 parts sent" (every file `present`); the same share and `url` come back.
4. `curl -s -A "facebookexternalhit/1.1" <url>` → the HTML holds this share's `og:title`, `og:image` and `noindex`; opening `og:image` shows the card with the living room, the title and "Designed in Truebex".
5. Open the `url` on the phone → the living room panorama loads; drag and tilt the phone to look around; tap the Kitchen hotspot → the kitchen panorama.
6. Renders tab → swipe the street view; Drawings tab → the PDF's first page, Download PDF works.
7. Footer "Designed in Truebex · Get Truebex for Windows" → `/download/`.
8. Dashboard → Shares → the share shows 1 visit, 1 unique; open it again on the phone → still 1 unique; on the PC → 2 unique.
9. Revoke → the phone's reload shows "This link has ended" (HTTP 410); `curl` of the data → 410 `share_gone`.

## Risks / traps

* A phone may not hold an 8192-wide texture (`MAX_TEXTURE_SIZE` 4096 on older GPUs): the viewer picks the 4096 derivative; never ship the 8k file to a phone by default.
* The wrapper loads `viewer.js` from truebex.com, which answers `access-control-allow-origin: *` today (GitHub Pages behind Cloudflare); if that header ever disappears, module scripts fail: a build check cannot see it, so the human test step 5 is the guard.
* Link-preview crawlers obey `robots.txt` (RFC 9309): the API host's `robots.txt` must allow `/view/` while the page itself says `noindex`.
* Cloudflare's request-body limit (100 MB) is why parts are 8 MiB; a 300 MB bundle through the home tunnel is slow but resumable.
* The viewer's CSS copies the brand tokens of `src/app/globals.css`: the build script reads them from there so they never drift.
* `src/viewer/**/*.ts` is inside `tsconfig.json`'s `**/*.ts` include (`tsconfig.json:25-32`): it must type-check under the site's settings, DOM types only.
* Share pages are the growth surface: Lighthouse on the phone (≤ 3 s to the first panorama on 4G) is checked by hand in the human test.

## As-built

* **Date, branch, commits:** 2026-10-09, `ap/t5-pf5-share-pages` (base `ap/t1-pf1-licence-api-releases-and-dow` at `fa824cf`): `0403ad3` PF1's storage adapter committed, `c1907ce` server (uploads, shares, page, card), `06add42` fixture bytes kept exact (`.gitattributes`), `41a54b3` `demo_share.py`, `0285d9c` site (viewer, dashboard, build step), then the docs commit.
* **Counts:** pytest 64 passed / 4 skipped before (no out/) → 95 passed, 0 skipped after in the verify gate (out/ built, so the 4 PF1 build checks run too) (`test_uploads.py` 6, `test_shares.py` 17, `test_site_pf5.py` 4 with the build present); `viewer.js` 19.9 KB, `viewer.css` 9.7 KB (budget 250 KB); `out/viewer/pdfjs/` 1.8 MB, fetched only when Drawings opens. Self-tested end to end on this PC: local API + `scripts/serve-out.py` + headless Edge (SwiftShader WebGL): the start view faces the manifest's start bearing (E), the Kitchen hotspot sits in the painted doorway at 132.5° / −8° and walks into the kitchen keeping the bearing, Renders and Drawings (PDF.js under the page's CSP, worker through PDF.js's cross-origin wrapper) render, a 412 px phone viewport shows the motion button, visits count once per visitor and day, revoke gives 410 for the page and the data, and the dashboard's Shares page lists the share with visits by day.
* **Deviations from Design and why:**
  1. *PF1's `server/app/storage/` was never committed* (the unanchored `storage/` rule in `server/.gitignore` matched it), so the base did not import. This branch commits PF1's files byte for byte and anchors the rule to `/storage/`, the same fix the PF7 worktree carries, so the merges agree.
  2. *The panorama viewer is written here* (`src/viewer/pano.ts` + `geometry.ts`, WebGL 1, a textured sphere) instead of an MIT library: no third-party code to license or audit for telemetry, 20 KB for the whole viewer, and the gyroscope and bearing maths are unit-tested under Node (`test_site_pf5_viewer_geometry`). Pannellum (MIT) was the alternative; it ships as a global script with its own UI, not as a module.
  3. *PDF renderer:* PDF.js 6.4.299 legacy build (Apache-2.0), copied (not bundled) to `out/viewer/pdfjs/` by `build-viewer.mjs` with its LICENSE, imported on first open of Drawings; `isEvalSupported: false`.
  4. *`og:image` is a stable route* `GET /s/{slug}/card.jpg` (`public, max-age=300`, 410 once ended) rather than a 1-hour signed URL: preview crawlers fetch the image later than the page.
  5. *Which parts arrived* is read from the part files (`uploads/parts/{upload_id}/{sha256}/{n}`), not kept in `upload_sessions.files`, so four parts in flight never race on one JSON value.
  6. *Fixtures are made here* by `server/scripts/make_share_fixtures.py` (the app repo has none yet): three distinct 2048 panoramas (`pano-2048.jpg`, `-kitchen`, `-hall`, with N/E/S/W painted at their true bearings and a doorway where each hotspot points) instead of one, so a hotspot visibly changes room; `manifest-invalid.json` holds 14 cases (the contract's three first; "file not listed" adds a render and "duplicate id" is on renders so no rule cascades); `visits.json` holds visits to replay and the 5.7 result.
  7. *Additive response keys* (MINOR-safe): the share record adds `bundle_id`, `published_at`, `revoked_at`; `visits.by_day[]` adds `unique`; 5.6 adds `limits` (`share_links`, `share_days`, `share_bytes`); 5.10 adds `published_at`, `url` and `panoramas[].derivatives` (`pano-4096`, `pano-1024` with url, width, height); 5.1/5.3 add `purpose` and 5.3 `part_bytes`.
  8. *Error codes beyond §7's table:* 5.4 with `expires_in_days` past the tier's maximum answers 422 `expiry_too_far` (listed for 5.8 only); 5.2 with a part of the wrong length answers 422 `validation_failed` with `expected_bytes`; a worker opening a non-`job-output` purpose (or a device opening `job-output`) answers 403 `forbidden`; publish re-checks the files' bytes (magic numbers, image sizes) and answers 422 `manifest_invalid` with rule `file_content`.
  9. *Upload sessions are bound to the credential kind* as well as the account: a website session of the same account cannot add parts to (or read) a device's session; a worker's session is bound to that worker.
  10. *`pano-4096` never enlarges* a smaller source (a 2048 panorama's "4096" copy is 2048 wide).
  11. *PATCH on an expired share whose files are still kept* brings it back to `live` (the dashboard's Extend), within the live-share limit; a revoked share stays ended (410).
  12. *The share page sends* `Content-Security-Policy` (scripts only from `SITE_URL`), `Referrer-Policy: no-referrer` (the slug is the secret) and `frame-ancestors 'none'`; `/files` responses add `X-Content-Type-Options: nosniff`.
  13. *`scripts/autopilot-serve.ps1`* now serves `out/` through `scripts/serve-out.py`, which adds `Access-Control-Allow-Origin: *` and web MIME types like GitHub Pages; with plain `http.server` a share page on the API's origin cannot load the viewer module.
  14. *`demo_share.py`* also signs in (`--email/--password`) and activates a "Share demo" device itself, so the human test needs no hand-made device token.
  15. *`UsageChart`* takes `noun` and `summary` props so the visits-by-day chart reuses it; the viewer accepts `#renders` / `#drawings` to open that tab first.
  16. *A blob nobody takes a ref on within 7 days* is dropped by `uploads.expire`; PF4 snapshots and PF6 job files must call `uploads.service.add_refs` / `drop_refs`.
* **Contract §11 rows for the owner to set to "PF5: done" in `contracts/share-bundle.md`:** all eleven: `POST /uploads`, `PUT /uploads/{upload_id}/files/{sha256}/parts/{n}`, `GET /uploads/{upload_id}`, `POST /shares`, `POST /shares/{share_id}/publish`, `GET /shares`, `GET /shares/{share_id}`, `PATCH /shares/{share_id}`, `DELETE /shares/{share_id}`, `GET /s/{slug}`, `POST /s/{slug}/visits`. Also copy `server/tests/contracts/share-bundle/` into the app repo's `Docs/roadmap/fixtures/contracts/share-bundle/` (from then on the master copy). **Licence §6.3 MINOR proposal** (a dated line under its *Changes*): `limits.share_days` (integer days, the longest expiry a share link may have; null = no limit) and `limits.share_bytes` (integer bytes per bundle) join the matrix; until GD7 sets them the server uses `SHARE_MAX_DAYS=30` and `SHARE_MAX_BYTES=1073741824`, and `share.links` stays a gate key the platform does not require (Free has `share_links: 1`).
* **Carry-over → which feature:**
  * PF14: the `s3` storage adapter (parts → S3 multipart uploads, presigned file URLs; derivatives are already stored with `immutable` cache headers for a CDN), `share.truebex.com` DNS with `SHARE_BASE_URL`, and Pillow on the API VM (it is in `requirements.txt`).
  * PF6: install the worker-token lookup with `uploads.credentials.set_worker_resolver` and open `job-output` sessions at claim with `uploads.service.open_session`.
  * PF4: snapshots upload through `uploads` (purpose `snapshot`) and take refs on their blobs.
  * PF13 (Arabic): a share title in a script Open Sans lacks is left off the preview card (never drawn as boxes); add Noto with shaping then.
  * GD7: `share_days` / `share_bytes` per tier in `catalogue.json`.
  * App PR4: the Share command and Shares panel against these endpoints and fixtures.
  * Owner: Lighthouse on a phone (≤ 3 s to the first panorama on 4G) and the gyroscope on a real phone (human test steps 5 and 6).
* **Merged together with PF7, PF8, PF2a, PF2b and master (PF2, PF3, PF13, PF14, PF14a) (2026-10-10, Autopilot T28, `ap/t28-merge-t5-t6-t7-t18-t19`):** verify green (lint, build, pytest 330 passed, 3 Postgres-only skipped); a smoke run against one real API process (demo share, trial catalogue, request for quote, worker running every merged job) passed 23/23.
  * PF14's `tasks.py` calls a job as `fn(now)`: `shares.expire`, `shares.purge` and `uploads.expire` open their own session. They are listed in `tasks._load_jobs` (the worker) and PF5's tables in `scripts/sqlite_to_postgres.py`; `test_ops` checks both. The share tests run only PF5's jobs.
  * `storage/__init__.py` is PF14's (the `s3` adapter; `shares/` is one of its CDN prefixes). The `/storage/` ignore fix was master's too.
  * `UsageChart` is master's (`label`, `unit`): the Shares page passes `unit="visits" label={T.byDay}`.
  * `npm run build` is `next build`, then PF13's `postbuild-lang.mjs`, then `build-viewer.mjs`.
  * Deploy skill: the live checks name `/viewer/viewer.js` with `access-control-allow-origin: *`; the secrets table and `infra/secrets/server.env.example` name `SHARE_BASE_URL`, `SHARE_MAX_DAYS` and `SHARE_MAX_BYTES`. Pillow reaches the VM in PF14's image, so the "pip install" note is gone.
  * Synced with master's PF4 and PF3a (T28, second sync): PF4 had copied `server/app/uploads/` and `routers/uploads.py` byte for byte; one copy is kept (master's `uploads/jobs.py`) and one `share_max_bytes` setting (this feature's block). PF4's Projects sits before Shares in the dashboard's first group.
