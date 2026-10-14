# PF5b — Share pages follow share-bundle 1.1.0 (PR4): the app's manifests and rule ids, Update into an existing share, the record's version, cover and project card (launch priority 1)

**Needs merged:** PF5, PF5a (both on `master` 988334f); PR4 on the app side (the app's share link export, landed on the app repo's `main` through merge T170, `7caa26aa2`, 2026-10-13 13:57 UTC). **Unblocks:** PR4 against the real API (`-mwshare=live`): Share, Update and the Upgrade dialog. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\share-bundle.md` **1.1.0** (2026-10-11; the app side is authoritative, C.9). The routers now answer `X-Truebex-Contract: share-bundle/1.1`.

## Status

**Built 2026-10-14** on `ap/t74-pf5b-share-pages-follow-share-bu` (Autopilot T74); see As-built. What broke on `master` 988334f, verified by reading the code against the app's files before the work:

| # | Where (master 988334f) | Before |
|---|---|---|
| 1 | `server/app/shares/manifest.py` rule `file_name` | any `/` in a file name refused, so 5.4 answered 422 `manifest_invalid` to every manifest the app writes (`tour/living-2k.jpg`, `renders/street.jpg`, `drawings/house.pdf`) |
| 2 | the same file, rule ids | PF5's own (`pano_size`, `file_listed`, `file_referenced`, `text_length` …), not the app's (`panorama_ratio`, `file_unlisted`, `file_unreferenced`, `title_length` …, `CadShareBundle::Validate`) |
| 3 | `server/app/shares/service.py` `create`, `routers/shares.py` `CreateShareIn` | `replace_share_id` unknown: an Update opened a second share |
| 4 | `server/app/shares/models.py` `Share` | no `version`; `bundle_id` was the creating bundle's |
| 5 | `manifest.py`, `page.py`, `card.py` | the 1.1 `cover` was not a use of its file (`file_referenced` refused the app's `cover.jpg`); the page and the link preview used neither the cover nor the project card |
| 6 | `service.py` `_check_slots`, `create` | 403 `quota_exceeded` without `data.plan` / `data.upgrade_to` (the app's Upgrade dialog shows the plan that lifts it) |
| 7 | `server/tests/contracts/share-bundle/` | PF5's own set; every file differed from the app's, and `qr-stub-link.txt` was missing |

## Goal

The designer presses Share in the app and the link works against the real API, exactly as it did against the app's stub. Later the designer presses Update: the client's link stays the same and shows the new renders the next time it is opened, with "Updated" and the date in the footer. The preview a messenger shows is the cover the app made, and the page tells the client the size of the project (storeys, rooms, floor area in the project's units).

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4, C.9; `PF5-share-pages.md` (Design, Deviations 7 and 8, As-built), `PF5a-arabic-share-titles.md`; `PF7c-marketplace-fixtures-from-mk1.md` (how a fixture set moves to `tests/fixtures/`), `PF12-…md` (how the OpenAPI document and SDKs are regenerated).
* `share-bundle.md` 1.1.0 in full: §3 *Changes* 2026-10-11, §5.4 `replace_share_id`, §6.1 *1.1 additions* and the deterministic bytes, §6.2 `version` / `bundle_id`, §7 409 `replace_conflict` and the stub's `data.plan` / `data.upgrade_to`, §9, §11.
* App repo, read only: `Docs/roadmap/fixtures/contracts/share-bundle/`; `Plugins/CADTOOL/Source/CadCore/Private/CadShareBundle.cpp` (`Validate`, `BuildManifest`); `Plugins/3DCADTOOL/Source/Cad3DTool/Private/Cad3DShareClient.cpp`, `Cad3DShare.cpp`; `Plugins/TruebexStubs/Source/TruebexStubs/Private/ShareStub.cpp` (`RouteCreateShare`, `RoutePublish`, `Publish`).
* Skills: `truebex-brand-voice` (the project card's words), `truebex-seo` (the share page's preview tags; the page stays `noindex`).

## Scope

**In** (in this order; nothing was cut):

1. **(a) The app's fixtures and the validator.** `scripts/sync-contract-fixtures.ps1 -Contract share-bundle` against app `main`; PF5's three-room set moved to `server/tests/fixtures/share/` (`make_share_fixtures.py` writes and `--check`s it there); `manifest.py` takes the app's `file_name` rule and answers the app's rule ids and paths, one message per id.
2. **(b) Update and `version`.** 5.4 `replace_share_id`; the share's `version` and the pending bundle (`database._ADDED_COLUMNS`, SQLite and Postgres); 409 `replace_conflict`; the unique (`account_id`, `bundle_id`) still holds.
3. **(c) The quota data.** 403 `quota_exceeded` carries `data.plan` and `data.upgrade_to` from the licence plan matrix (GD7 placeholders).
4. **(d) The page.** The cover is the link preview; a 1.1 project card shows under the title; a 1.0 manifest renders as before; `plan` and `app_build` are stored, never shown publicly.
5. The generated OpenAPI document and SDK types for the added keys; this doc, the tracker row, PF5's carry-over line, a README section.

**Out (and where it goes):**

* Editing the app repo (read only here): the contract lines in As-built are the owner's to apply there.
* Showing the share's version to the client as a number: the page says "Updated" with the date; the dashboard shows "Version N".
* Prices per plan and the real share limits: GD7 (the catalogue keeps `share_links: 1` on every tier, so `upgrade_to` is `null` until then).

## Design

### API

| # | Endpoint | PF5b |
|---|---|---|
| 5.4 | `POST /shares` | body may carry `replace_share_id` (≤ 64 characters). Order: the same `bundle_id` (served now, or waiting as an Update) returns that share (200, PF5's idempotency, as the stub); the manifest rules (422); the expiry (422 `expiry_too_far`); the bundle's bytes (403 `share_bytes`); then, with `replace_share_id`, that share: another account's or unknown → 404 `not_found`, revoked or expired → **409 `replace_conflict`** `data: {state, share_id}`; else the Update (201). An Update takes no new live-share slot. |
| 5.4 | Update of a **live** share | the new manifest waits in `pending_*`; the share keeps serving its bundle: `state` `live`, its `version` and `bundle_id`, its files on 5.10 and the page. The new `title` and expiry (`expires_in_days` from now) apply at once, as the stub does. The answer's `upload` is the new bundle's session (files the account holds are `present`). |
| 5.4 | Update of an **uploading** share | nothing is served yet: the share takes the new bundle at once (`bundle_id`, `manifest`); its first publish is version 1, as the stub's. |
| 5.5 | `POST /shares/{id}/publish` | with an Update waiting: every new file complete (422 `upload_incomplete`), the file checks, derivatives of new panoramas, the card (the cover or PF5's); then `manifest`, `bundle_id`, `bytes`, `watermark` swap, `version` + 1, `published_at` now; the old bundle's files lose this share's ref (a blob nobody else holds is deleted) and derivatives of panoramas the new bundle lacks go. `share_id`, `slug`, `url`, `expires_at` and the visits stay. A pending Update of a share that ended answers 410 `share_gone`. Repeating 5.5 is safe. |
| 5.4–5.9 | the share record (6.2) | adds `version` (1, + 1 per published Update; a row from before reads 1) beside PF5's `bundle_id` (now: the bundle the share serves). |
| 5.4 | 403 `quota_exceeded` | `data` adds `plan` (the caller's, `seats.seat_source`) and `upgrade_to`: the lowest-ranked plan above it whose limits admit the request (`share_links`: one more live share; `share_bytes`: the bundle), or `null`. |
| 5.10 | `GET /s/{slug}` | adds `version`; the manifest without `plan` and `app_build`; a PDF's signed URL downloads as the last segment of its name. |
| page | `GET /view/{slug}` | `og:image` / `twitter:image` = `/s/{slug}/card.jpg`, plus `?v=<version>` from version 2 on (a preview cache keyed on the image URL fetches the new one); the card is the cover when the manifest has one; the `<noscript>` gets the project card line. |
| webhooks | `share.published` (PF12) | also sent when an Update is published (`version` > 1), with the share record. |

**Routers:** `contract("share-bundle", 1, 1)` on `shares`, `uploads`, `tiles` (the live view) and `/v1/shares`, `/v1/uploads`; a client sending 1.0 is still served (MINOR).

### Data

`shares` gains (`database._ADDED_COLUMNS`, the PF5b block at its end; checked on a database made by master's models, SQLite and Postgres 17): `version INTEGER` (NULL = 1), `pending_bundle_id VARCHAR(32)`, `pending_manifest JSON`. `upload_id`, `title`, `days` and `expires_at` are reused for an Update. The unique (`account_id`, `bundle_id`) holds: the idempotency lookup also matches `pending_bundle_id`, so a waiting bundle cannot start a second share, and 5.5 answers 409 `replace_conflict` if a race ever made the swap break the constraint. Blobs stay content-addressed (`blobs/{account}/{sha256}`): a file's name (with folders) never reaches a storage key.

### UI

| Piece | PF5b |
|---|---|
| `src/viewer/project.ts` (new) | `projectLine()` ("1 storey · 3 rooms · 72.75 m²"; whole ft² when `units` is `imperial`; positive whole storeys and rooms, a positive area, else left out; `Intl.NumberFormat("en-GB")`) and `downloadName()` (a name's last segment) |
| `src/viewer/main.ts` | the project card under the title (in a `div.tbx-heading`, only when the manifest has one, so a 1.0 header is unchanged); footer "Updated <date>" when `version` > 1; the Download PDF name; `share-bundle/1.1` |
| `src/viewer/types.ts`, `viewer.css` | the 1.1 keys; `.tbx-heading`, `.tbx-project` (wraps, never scrolls sideways) |
| `src/viewer/cube.ts` | the live view clamps a start field of view to 30–110° (1.1 allows up to 180°) |
| `server/app/shares/page.py` | `project_line()` for the `<noscript>` (the same text as the viewer; a test runs both); `PROJECT_CARD` mirrors the copy |
| `src/app/dashboard/shares/page.tsx`, `src/lib/shares.ts` | "Version N" beside the state once a share was updated; `share-bundle/1.1` |
| `src/lib/constants.ts` (end of file) | `SHARE_PROJECT_CARD` (label, storey/storeys, room/rooms, m², ft², Updated), `DASHBOARD_SHARES_VERSION` |

### Jobs / workers

None new. `shares.purge` drops the refs of the bundle a share serves; an Update's files that were never published hold no ref and go with `uploads.expire` after 7 days, like any orphan.

### Security and privacy

* `plan` and `app_build` (1.1) are kept in the stored manifest and never served by 5.10, the page, 5.6–5.9 or the webhook.
* A file name is a relative path inside the bundle (no `..`, no leading `/`, no `\`, no `:`); it is only ever shown, or used as a download name (last segment, quotes and control characters replaced).
* An Update is bound to the caller's account (`_owned`: another account's share is 404, never 409, so share ids are not probed).

## Deliverables

- [x] `server/tests/contracts/share-bundle/` = the app's 7 files (app `main` 7fe6b2c2, each blob id checked) + README; `server/tests/fixtures/share/` = PF5's set (moved; `manifest-invalid.json` regenerated with the app's rule ids)
- [x] `server/app/shares/manifest.py` (the app's rules and ids, `cover`, `public()`), `service.py` (Update, `version`, quota data, `download_name`, the cover card), `card.py` (`from_cover`), `page.py` (`project_line`), `models.py`; `server/app/database.py` (PF5b block)
- [x] `server/app/routers/shares.py`, `uploads.py`, `tiles.py`, `v1/shares.py`, `v1/models.py` (1.1, `replace_share_id`, `version`, `bundle_id`); `server/app/webhooks/observe.py` (Update → `share.published`)
- [x] `server/scripts/make_share_fixtures.py` (`tests/fixtures/share`, `--check`), `demo_share.py` (`--update`, `--cover`), `export_openapi.py` (1.1)
- [x] `openapi/v1.json`, `sdks/python/truebex/{models,_operations}.py`, `sdks/js/src/{schema.d.ts,operations.mjs}`
- [x] `src/viewer/project.ts`, `main.ts`, `types.ts`, `cube.ts`, `live.ts`, `viewer.css`; `src/lib/shares.ts`, `src/lib/constants.ts`; `src/app/dashboard/shares/page.tsx`
- [x] `server/tests/test_share_contract_fixtures.py` (4), `server/tests/test_shares_pf5b.py` (74: 18 tests and 56 parametrized rule cases); `share_helpers.py` (both folders); PF5's tests updated for the folder and the 1.1 header only
- [x] this doc, the PF5b tracker row, PF5's carry-over line, README section "Share links: share-bundle 1.1 (PF5b)"

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_contract_folder_is_the_apps_copy` | pytest | the folder is the app's 7 files + README; each file's git blob id (computed as `git hash-object --no-filters`) equals app `main` 7fe6b2c2's; where the app repo is on the machine, `git ls-tree` at that commit agrees |
| `test_apps_house_manifest_passes_the_rules` | pytest | `manifest.check()` on the app's `manifest-house.json` is `[]` |
| `test_apps_invalid_manifest_answers_exactly_its_errors` | pytest | exactly its three `{path, rule}` pairs, order free, from the validator and from 5.4 |
| `test_apps_bundle_published_through_the_endpoints` | pytest | the app's manifest through 5.4, its three files through 5.2, 5.5: live, version 1; 5.10 lists the three panoramas with derivatives; every file opens; the PDF downloads as `house.pdf`; the page's description and project card |
| `test_pf5b_file_names_with_folders` | pytest | `tour/living-2k.jpg` passes; `""`, `../x.jpg`, `/x.jpg`, `a\b.jpg`, `c:x.jpg`, `tour/../x.jpg`, null and a number answer `file_name`; folders travel to 5.10; the PDF downloads by its last segment; no name reaches a storage key or the page |
| `test_pf5b_rule_ids_are_the_apps[…]` | pytest | 56 cases: PF5's house with one thing broken answers exactly the app's `{path, rule}` pairs (`panorama_width`, `panorama_ratio`, both, `panorama_type`, `panorama_bytes` at 30 MiB + 1, `panorama_count`, `bearing_range` (360, missing, start, hotspot), `pitch_range`, `hfov_range` (0; 5 and 180 pass), `render_edge`, `render_type`, `render_bytes`, `render_count`, `sheets_*`, `file_*`, `name_length`, `title_length`, `label_length`, `duplicate_id`, `hotspot_*`, `*_entry`, `project`, `eye_mm`, `start`, `units`, `region`, `bundle_id`, `schema`, the cover's three cases, the other 1.1 keys ignored) |
| `test_pf5b_rule_messages_one_per_id` | pytest | `MESSAGES` = the app's ids but `total_bytes`, plus `type`, `empty`, `file_content`; no old id; `[]` → `json` |
| `test_pf5b_share_fixtures_up_to_date` | pytest | `make_share_fixtures.py --check` green on `tests/fixtures/share/`; its cases use only current ids |
| `test_pf5b_update_keeps_the_link` | pytest | A on X, 5.4 with `replace_share_id`=A and Y: same `share_id`, slug, url; live, version 1, bundle X while Y uploads (5.4, 5.7, 5.10); the same request again answers the same; 422 `upload_incomplete` names Y's new files; after 5.5: version 2, bundle Y, Y's files on 5.10, visits kept, X's files nobody else holds deleted, Y's at one ref, the hall's derivatives gone; `og:image` = `card.jpg?v=2` = Y's cover; repeating 5.4 and 5.5 changes nothing |
| `test_pf5b_update_conflicts` | pytest | another account's share and unknown ids 404; expired and revoked 409 `replace_conflict` (twice the same); nothing opened; a pending Update of a revoked share: 5.5 410 |
| `test_pf5b_update_of_an_uploading_share` | pytest | the uploading share takes the bundle at once; first publish version 1 |
| `test_pf5b_update_limits` | pytest | no new slot taken; expiry and bytes checked like any share |
| `test_pf5b_version_in_every_answer` | pytest | `version` 1 in 5.4, 5.5, 5.6, 5.7, 5.8, 5.9; the routes echo `share-bundle/1.1` |
| `test_pf5b_update_sends_share_published` | pytest | PF12's webhook for the first publish (version 1, X) and the Update's (version 2, Y) |
| `test_pf5b_v1_update_with_api_key` | pytest | `/v1/shares` takes `replace_share_id`; `openapi/v1.json` names `version`, `bundle_id`, `replace_share_id` |
| `test_pf5b_quota_names_the_plan_that_lifts_it` | pytest | with the catalogue's placeholders `plan` free, `upgrade_to` null; with patched limits the lowest plan that admits one more live share (studio, then pro, then pro with no limit) or the bundle's bytes (team, then studio); a Pro trial over Pro's limit → `pro`, `studio` |
| `test_pf5b_cover_is_the_link_preview` | pytest | with a cover, `og:image` serves the cover byte for byte (1200 × 630); other sizes are cropped to 1200 × 630; without one the card is PF5's, byte for byte |
| `test_pf5b_project_card_on_the_page` | pytest | the `<noscript>` line; 5.10 keeps the keys; metric, imperial (783 ft²), thousands, partial, invalid and absent cases |
| `test_pf5b_one_point_zero_renders_as_before` | pytest | `view.html` unchanged (hash); `render_view` for a 1.0 manifest equals PF5's code (kept in the test as the oracle); no project card, no `?v=` |
| `test_pf5b_plan_and_app_build_never_public` | pytest | stored in the manifest; absent from 5.10, the page, 5.6 and 5.7 |
| `test_pf5b_copy_in_step` | pytest | `page.PROJECT_CARD` = `SHARE_PROJECT_CARD`; it is the end of `constants.ts` |
| `test_pf5b_viewer_project_card_and_download_name` | pytest (Node) | `src/viewer/project.ts` gives the same lines as `page.project_line()` on 13 inputs (halves rounded alike) and the same download names |
| `test_pf5b_viewer_bundle_reads_1_1` | build check | `viewer.js` ≤ 250 KB, sends `share-bundle/1.1`, carries the card's words; `viewer.css` has `.tbx-project` |
| PF5's, PF5a's, PF12's tests | pytest | unchanged but the fixture folder and the 1.1 echo (`test_shares.py`, `test_uploads.py`, `test_site_pf5.py`) |
| `npm run lint`, `npm run build` | build check | green |

## Human test

For the owner. Set-up as PF5's human test step 1 (`PF5-share-pages.md`: a signing key in `server\.env`, the API on the LAN with `--host 0.0.0.0 --port 8000`, `SITE_URL` = the served `out/` on its LAN address, `SHARE_BASE_URL=http://<LAN address>:8000`, that origin in `CORS_ORIGINS`), and `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` serving `out/`.

1. **Share from the app.** Start a PR4 build with `-mwshare=live -mwapi=http://<LAN address>:8000`, signed in to an account of this local API. Open a house with saved views and a sheet, press Share → the dialog uploads, then shows a link `http://<LAN address>:8000/view/<slug>` and its QR code; the Shares tab lists it as live. (Without the app: in `server\`, `.venv\Scripts\python.exe scripts\demo_share.py --email <you> --password <pw> --fixture tests\contracts\share-bundle\manifest-house.json --api http://<LAN address>:8000` → "3 parts sent", "state live, version 1", the `url`.)
2. **Open the link on a phone** (scan the QR code) → the first room's panorama; under the title a line like "1 storey · 3 rooms · 72.75 m²" (the house's own numbers, in m² for a metric project); tabs Panoramas · Renders · Drawings; footer "Designed in Truebex · Get Truebex for Windows" and "Open until …"; nothing scrolls sideways. Paste the link into a messenger chat → the preview image is the app's cover (the first render, else the start room's front view), not a card with the title written on it.
3. **Update.** In the app change something visible (move a light, rename a room, re-render), then in the Shares tab press Update on that share → it uploads only what changed and keeps the same link. (Without the app: run step 1's command again with `--update <share id> --rooms "Lounge, Kitchen, Main bedroom"` → "share … (update, live, version 1)", then "state live, version 2", the same `url`.)
4. **The same link shows the new version.** Reload the page on the phone → the new picture or room names; the footer now also says "Updated <today's date>". Optional: in the website's Dashboard → Shares the share shows "Version 2" and its visits from before the Update (the dashboard needs `out/` built against the local API: stop the serve script, run `$env:NEXT_PUBLIC_AUTH_URL='http://<LAN address>:8000'; npm run build`, serve again).
5. **Ended links cannot be updated.** Dashboard → Shares → End link on that share, then press Update in the app → the app reports the share has ended (409 `replace_conflict`); the phone's reload shows "This link has ended".

## Risks / traps

* **Two fixture sets.** `tests/contracts/share-bundle/` is the app's (never edited: re-copy with `scripts\sync-contract-fixtures.ps1 -Contract share-bundle`); PF5's house with three distinct rooms is `tests/fixtures/share/` (regenerate with `make_share_fixtures.py`). Older README sections and PF5/PF5a human tests name `tests\contracts\share-bundle\manifest-house.json`: that still works, but uploads the app's house (one picture for its three rooms); for PF5's "tap Kitchen → the kitchen" use `tests\fixtures\share\manifest-house.json`.
* **The app checkout is CRLF** (`core.autocrlf=true`): copy the blobs (the sync script does), never the working files.
* **Rounding on the card line** follows `Intl.NumberFormat` (half away from zero on the shortest decimal form: 72.755 → 72.76); `page.py` copies it with `Decimal(repr(x))`, and a Node test keeps the two in step.
* **Test order:** `test_uploads.py` before `test_render_shares.py` leaves PF6's worker resolver replaced (3 errors); the gate runs them alphabetically, so it never happens there. It is master's too (reproduced on 988334f).
* **Preview caches** key on the page URL as well as the image URL: after an Update a messenger may keep showing the old preview for a while; the `?v=` only helps those that key on the image.

## As-built

* **Date, branch, commits:** 2026-10-14, `ap/t74-pf5b-share-pages-follow-share-bu` from `master` 988334f (Claude Autopilot T74): `03ecbd8` (fixtures, validator, Update, version, quota data, cover and project card, OpenAPI and SDKs, tests), `4f74dd4` (this doc, the tracker row, PF5's line, the README section; the viewer build check reads esbuild's escapes), `b4a1ade` (an Update's old files are dropped only after the swap is committed; no upload session is opened for an ended share), then the As-built's counts with the webhook test's order fix.
* **Copy:** `scripts\sync-contract-fixtures.ps1 -Contract share-bundle` from the app's `main` at `7fe6b2c2` (the folder last changed in app commit `cc296079`, landed through T170 `7caa26aa2`): 7 files, every blob id equal (`git ls-tree` against `git hash-object --no-filters`; the committed blobs here are the same ids). PF5's 10 files moved to `server/tests/fixtures/share/`; only `manifest-invalid.json` (the new rule ids) and the README changed; `make_share_fixtures.py --check` reproduces all eight data files byte for byte.
* **Counts:** pytest collected 718 → 796 (78 new: 4 in `test_share_contract_fixtures.py`, 74 in `test_shares_pf5b.py`). **Tests first:** the 78 run on master 988334f's `server/` (with the new tests, helpers and both fixture folders copied in): 60 failed, 16 passed, 1 skipped (the build check, no `out/`). The 16 that passed have nothing to fix: the folder check (about the copy), the 1.0 oracle (a guard), and the 14 rule cases where both sides already used the same id (`render_type`, `render_bytes`, `render_count`, `sheets_type`, `sheets_bytes`, `hotspot_target` twice, `start`, `units`, `region`, `bundle_id`, `schema`, `cover: null`, the other 1.1 keys ignored). On the branch, the share, upload, PF5a, PF12 API/SDK/webhook and live-view files: 152 passed, 4 build checks skipped before `npm run build`, all green after it. The verify gate: see the last bullet.
* **Postgres 17** (throwaway cluster, session zone Asia/Baghdad, `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`), on the last commit: `test_render_shares.py`, `test_share_contract_fixtures.py`, `test_shares_pf5b.py`, `test_shares.py`, `test_shares_pf5a.py`, `test_uploads.py`, `test_pf12_api.py`, `test_pf12_webhooks.py`, `test_routes_unique.py`, `test_pf14c_utc_times.py` in one run: 145 passed. One earlier run failed `test_pf5b_update_sends_share_published` once: PF12 sends 8 deliveries at a time, so the two `share.published` bodies may arrive in either order; the test now compares them sorted. Migration: a database made by master's models, then this branch's `init_db`, on SQLite and on Postgres: the three columns added (`INTEGER`, `VARCHAR(32)`, `JSON`), an old share reads `version` 1, a pending manifest with a folder name round-trips, `init_db` again is a no-op.
* **Self-test** (a real uvicorn on 127.0.0.1:18074 with a scratch SQLite database and storage, `scripts/serve-out.py` serving the built `out/` on 3174, headless Edge 1280 × 900 and 390 × 844 over CDP):
  * `demo_share.py --fixture tests\contracts\share-bundle\manifest-house.json --cover <a 1200 × 630 JPEG>`: create, 4 parts (PDF, render, panorama, cover), publish → live, version 1. The page: title, "1 storey · 3 rooms · 72.75 m²" under it (aria-label "About this project"), three tabs, chips Living room · Kitchen · Bedroom; `og:image` `…/s/<slug>/card.jpg` (1200 × 630) and its bytes equal the cover's; `scrollWidth` = `innerWidth` at both sizes; no console errors. 5.10 has no `plan` or `app_build`; the PDF downloads as `filename="house.pdf"`.
  * `--update <share id> --rooms "Lounge, Kitchen, Main bedroom" --cover <another JPEG>`: "(update, live, version 1)", 1 part (the new cover), publish → version 2, the same url; again → "(existing, live, version 2)", 0 parts. The same page now: chips Lounge · Kitchen · Main bedroom, footer "Updated Oct 14, 2026", `og:image` `card.jpg?v=2` = the new cover byte for byte; the first cover's blob deleted, the other three at one ref; `GET /shares` version 2 with the visits from before. After End link: `--update` answers 409 `replace_conflict` ("That share has ended (revoked)…"), the page 410.
* **Rule ids: PF5 → PF5b (the app's).** Paths are the app's too.

  | PF5 | PF5b | Note |
  |---|---|---|
  | `pano_size` | `panorama_ratio`, `panorama_width` | both when both are broken |
  | `pano_type`, `pano_bytes`, `pano_count` | `panorama_type`, `panorama_bytes`, `panorama_count` | the byte limits are MiB now (30, 25, 200), as the app's (were MB) |
  | `bearing`, `pitch`, `hfov` | `bearing_range`, `pitch_range`, `hfov_range` | bearings [0, 360) (360 was accepted); field of view (0, 180] (was 10–150); a missing or non-number required angle is the range rule (was `type`) |
  | `render_size` | `render_edge` | a missing or non-positive size too (was `type`) |
  | `text_length` | `title_length` (project title), `name_length` (panorama and render titles), `label_length` (hotspot labels) | file names: `file_name` (over 255 characters; was 60, `text_length`); storey names and sheet titles: no length rule (the app writes them unchecked) |
  | `file_listed` | `file_unlisted` | also a reference that is not a hash (was `sha256`) |
  | `file_referenced` | `file_unreferenced` | the cover counts as a use |
  | `file_unique` | `file_duplicate` | path `files[i]` (was `files[i].sha256`) |
  | `sha256` | `file_hash_format` | |
  | `id_unique` | `duplicate_id` | an empty or missing id too (was `type`) |
  | `file_name` | `file_name` | a relative path: folders allowed; empty, `..`, leading `/`, `\`, `:` refused |
  | `type` | `json`, `project`, `file_entry`, `panorama_entry`, `render_entry`, `hotspot_entry`, `sheets_entry`, `file_bytes`, `file_type`, `eye_mm`, `sheets_pages` | where the app has a rule for it; `type` stays for the rest (below) |
  | — (1.1) | `cover_type`, and `file_unlisted` at `cover` | |
  | unchanged | `schema`, `bundle_id`, `units`, `region`, `start`, `hotspot_target`, `render_type`, `render_bytes`, `render_count`, `sheets_type`, `sheets_bytes`, `empty`, `file_content` | |

  *Only the app checks:* `total_bytes` (the platform answers 403 `quota_exceeded` `share_bytes`, the tier's limit); `file_missing`, `file_size`, `file_hash` (`ValidateFolder`, the staged folder; the platform's are 5.2's `file_hash_mismatch` and 5.5's `upload_incomplete` and `file_content`); a missing `start_bearing_deg`, `eye_mm` or `sheets.pages` (the platform accepts them missing; the app always writes them); a `file_type` the app checks on every file, the platform too since PF5b.
  *Only the platform checks:* `type` (`watermark` a boolean; `files`, `panoramas`, `renders`, `hotspots` lists; `project.title` a string; panorama and render titles non-empty strings; storey, label and sheet titles strings; PF6's `live_job_id`), `empty` (no panorama, render or drawing), `file_content` (5.5: magic numbers, image sizes, the cover decodes), render ids unique (the app checks panorama ids only), a file name of at most 255 characters, `region` of exactly two capital letters (the app also takes e.g. `G1`).
* **Deviations from the task text and why:**
  1. *The validator reads `cover`* (the task: "ignores the 1.1 keys, which is right"): the app's `cover.jpg` is listed in `files` and used only by `cover`, so a validator blind to it answers `file_unreferenced` to every share the app makes. It now counts as a use and is checked with the app's two rules (`file_unlisted`, `cover_type`). `branding`, `plan`, `app_build` and the project card stay unchecked.
  2. *Rules relaxed to the app's reading:* storey names and sheet titles have no length rule (the app sends sheet titles as typed), the file-name length bound is 255 (the app sets none), the project title may be empty, MiB byte limits, bearings [0, 360) and field of view (0, 180]. The point is that a manifest the app's validator passes is never refused here. The viewer clamps its field of view, so a 170° start is safe.
  3. *Title and expiry of an Update apply at 5.4* and the files, `bundle_id` and `version` at 5.5, as the app's stub does; the contract is silent (PATCH line below).
  4. *An Update of a share still uploading* takes the new bundle at once (the stub: version 1 at the first publish).
  5. *`og:image` gets `?v=<version>`* from version 2 on; version 1 keeps PF5's URL, so a 1.0 page is byte-identical.
  6. *`share.published` webhook* (PF12) is also sent for an Update's publish, with `version` 2 in its record.
  7. *5.10 adds `version`* (the viewer's "Updated" line) and drops `plan` / `app_build`; 409 `replace_conflict` carries `data: {state, share_id}`.
  8. *Contract header:* the routers answer `share-bundle/1.1`; the viewer, the dashboard, `demo_share.py` and the SDKs send it. PF5's three echo assertions now expect 1.1.
  9. *SDK types:* `openapi/v1.json` by `export_openapi.py --v1` and the operation layer by `sdks/generate.py`; the three added keys were written by hand into `models.py` and `schema.d.ts` in the generators' own form (their pinned tools need a network install; `test_pf12_openapi_sdks.py` is green). The operation and request descriptions were kept unchanged, so the documents differ only by the keys and the contract version.
  10. *The quota's `upgrade_to`* counts every plan ranked above the caller's, Team and Enterprise included; with the catalogue's GD7 placeholders (every tier `share_links: 1`, no `share_bytes`) it is `null` today, where the stub says `studio`.
* **Contract lines for the owner to put to the app side** (`contracts/share-bundle.md`; PATCH = wording, MINOR = additive):
  * **§11 (PATCH):** all eleven rows "PF5: done" (PF5 2026-10-09, PF5b 2026-10-14 for 1.1): `POST /uploads`, `PUT /uploads/{upload_id}/files/{sha256}/parts/{n}`, `GET /uploads/{upload_id}`, `POST /shares` (+ `replace_share_id`), `POST /shares/{share_id}/publish`, `GET /shares`, `GET /shares/{share_id}`, `PATCH /shares/{share_id}`, `DELETE /shares/{share_id}`, `GET /s/{slug}`, `POST /s/{slug}/visits`.
  * **§6.1 (PATCH):** name the rule ids as `CadShareBundle::Validate` answers them (the table above), and say which only one side checks (`total_bytes` → 403 on the platform; `type`, `empty`, `file_content` platform-only); that "names ≤ 60" covers panorama and render titles and hotspot labels (or the app checks storey names and sheet titles too); that the byte limits are MiB.
  * **§5.4 (PATCH), Update while it uploads:** "The share answers as it was — `state` `live`, its `version`, `bundle_id` and files on 5.6–5.10 — until 5.5 publishes the new bundle; the new `title` and expiry apply at once. 5.5 then swaps the files and `bundle_id`, `version` + 1, `published_at` now; `slug`, `url` and visits stay. The same `bundle_id` again (with or without `replace_share_id`) returns that share. An Update of a share still uploading takes the bundle at once (first publish = version 1). A waiting Update of a share that ends answers 5.5 with 410 `share_gone`."
  * **§7 (MINOR):** 403 `quota_exceeded` `data.plan` (the caller's plan) and `data.upgrade_to` (the lowest plan above it whose limit admits the request, or null) become contract keys on the platform too; 409 `replace_conflict` `data.state`, `data.share_id`.
  * **§5.10 / §6.2 (MINOR):** 5.10 `version`; `plan` and `app_build` are never served publicly.
  * **App side (no contract change):** `Cad3DShare.cpp` `ShareProjectName` sends `CurrentFile` as `project.title` (and the default share title): if that is a path rather than a name, §6.1's "no paths" is broken; worth a check in PR4.
* **Carry-over → which feature:** GD7: real `share_links` / `share_bytes` / `share_days` per tier (then `upgrade_to` names a plan). Owner: the contract lines above, the app's human test (steps 1–5 with a PR4 build). A later task, if wanted: redraw PF5's composed card when a share without a cover is renamed (PF5a carry-over, unchanged).
* **Verify gate** (`scripts/autopilot-verify.ps1`, on `b4a1ade`): green in 534 s; lint, build, pytest 779 passed + 17 skipped (the Postgres-only tests) of 796 collected in 452 s. The commit after it changes only the webhook test's comparison (sorted) and this doc.
