# PF10 — Android native app (launch priority 3)

**Needs merged:** PF9. **Unblocks:** none. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\project-log.md` (v1.0.0; the Android app is a light client that writes `action` operations), with `render-jobs.md` and `agent-interface.md` as PF9.

## Status

**Built 2026-10-11** on `ap/t13-pf10-android-native-app` (on PF9's branch with master merged: PF4, PF6, PF7, PF9,
PF11 …): the Flutter app `com.truebex.app` in `mobile/android/` (replica, outbox, WorkManager sync, PF9's viewer in a
web view served from the phone's tile cache, Keystore session, Google through Credential Manager), the light clients'
OpenAPI document `openapi/clients.json` with both clients generated from it (`src/lib/api-clients.d.ts` for PF9,
`mobile/android/lib/api/gen/` for PF10), the mobile gate `scripts/verify-mobile.ps1`, the store listing in
`mobile/android/store/`, and a live run on an Android 16 emulator (debug and release builds). Waiting on others:
CL1 / CL4 applying `action` operations on the desktop, CL3's real renders (the screenshots show the stand-in
renderer), and the owner's GD4 actions (Play account, upload key, Android OAuth client). See As-built.

Before this task no native client existed (`00-contract.md` P.1). What this builds on, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Google sign-in | `server/app/routers/auth.py:57-68` (ID token verified against the one Web client id, `:66-67`), `:71-112` | an Android Sign in with Google token minted for that Web client id (as the server client id) passes unchanged |
| Google Cloud setup | `README.md:263-271` | one Web client; an Android OAuth client (package name + signing certificate SHA-1) is an owner action in the same project (GD4) |
| Privacy policy URL | `src/app/privacy/page.tsx:5-9` (`/privacy/`) | the Play listing links to it |
| From PF9 (Needs) | the `action` builder and its fixture test, `/auth/me` with `author_id`, the shared viewer (`src/viewer/`, cube tiles, hotspots), the contract MINOR proposals (`digest`, `place.replace`) | |
| From PF4, PF6 | pull and push, presence; followed sets and tiles | |

What the owner meant: app-side `00-understanding.md` §8 ("then an Android native app and the headset target"; "Android before iOS (assumed)").

## Goal

The same light client as PF9, native on Android and built to work without a network: the project log kept on the phone, the last panoramas cached, edits made offline and synced in the background, the same edits as the web client, and a Play Store listing ready to submit. Human test seed: "install the APK, edit offline, reconnect and see the desktop catch up".

## Read first

* **`contracts/project-log.md` v1.0.0** — §4 (the Android app uses a session token; "PF10 may adopt the device link flow later"), §5.6–5.7 (push, pull), §6.2–6.3 (operations and the conflict rule), §8 (retry and backoff), §9 fixtures (`action-move.json`, `ops-remote.json`).
* `contracts/agent-interface.md` §5.7–5.11, §6.4; `contracts/render-jobs.md` §5.2, §6.2.
* PF9 (the web client this mirrors) and PF12 (the OpenAPI document the SDKs come from).
* `guides/GD4-*.md` (store accounts, the Android toolchain, signing, store forms) is not written yet: the Play Console account, the upload key and the target API level are owner actions there.
* Skills: `truebex-brand-voice` (the store listing text: no other product named, only shipped features).

## Scope

**In:**
1. A Flutter app (`mobile/android/`), Android first, package `com.truebex.app`, signed for release with the owner's upload key (GD4), debug APKs for testing.
2. An offline-first replica of the project log: every pulled operation stored on the phone (the delta kept as an opaque blob, never decoded), `head_seq` per project, the outbox of the phone's own operations, the snapshot digests; history readable offline (who changed what, when).
3. Panoramas: the followed sets' tiles through the same viewer bundle as PF9, hosted in an in-app web view whose requests the app answers from its tile cache when offline.
4. The same light edits as PF9 (move, swap product, room theme, floor and wall finish) built as `action` operations by a Dart port of PF9's builder, checked against the same fixture.
5. Background sync: Android WorkManager through its Flutter plugin — a periodic job (15 min, the platform's minimum) and a one-off job when the network returns: push the outbox, pull after `head_seq`, refresh digests, prefetch tiles of starred projects on unmetered networks; the §6.3 rejection shown as a notification and in the history.
6. Sign-in with e-mail and password (`/auth/login`) or Google (Android Credential Manager, the Web client id as server client id, then `/auth/google`); the session kept in Android's encrypted storage; silent Google re-sign-in when the 24 h session lapses.
7. Shares the API client with PF9: both generated from one OpenAPI document of the endpoints they call (TypeScript for PF9, Dart for PF10), with the contract fixtures as shared test vectors.
8. Store listing assets: icon 512 × 512, feature graphic 1024 × 500, phone screenshots (portrait, 2–8), short description (≤ 80 characters), full description (≤ 4000 characters), the privacy policy URL, answers for the Data safety form and the content rating questionnaire, all under `mobile/android/store/`.
9. Tests: Flutter unit and widget tests, a pytest for the OpenAPI document, and a mobile gate script.

**Out (and where it goes):**
* The headset app → PR5 (the Unreal target of the app repo, `00-understanding.md` §8).
* iOS → not in roadmap 40 ("Android before iOS (assumed)", §8 Ask); the Flutter code keeps platform calls behind interfaces so it can follow.
* The device link flow for light clients (a longer-lived credential) → carry-over: needs a fingerprint rule for Android in `licence-api.md` §6.2 first.
* Play Console account, signing keys, store review → GD4 (owner).

## Design

### API

No new server endpoint. The app calls the same routes as PF9 (`/auth/login`, `/auth/google`, `/auth/me`, `/projects…`, `/projects/{pid}/ops`, `/projects/{pid}/presence` with `client: "android"`, `/jobs…`, `/market/prices`). **Decision:** "shares the API client with PF9" means one OpenAPI document and two generated clients. `server/scripts/export_openapi.py` writes `openapi/clients.json` (the paths both clients call, from FastAPI's schema); PF9's TypeScript types and PF10's Dart client are generated from it with an open-source OpenAPI generator (Apache-2.0), and both run the contract fixtures as test vectors. Rejected: sharing source code (TypeScript and Dart cannot share it) and a hand-written Dart client (it would drift from the server).

### Data (on the phone)

| Store | Holds | Notes |
|---|---|---|
| SQLite (a Dart persistence package, drift class) `projects` | record, role, region, `head_seq`, starred | |
| `ops` | `project_id`, `server_seq`, `op_id`, `author`, `kind`, `name`, `at`, `touched`, `delta` (opaque blob), `action` JSON | the replica of the log; pulled pages of ≤ 1000 |
| `outbox` | the phone's `action` operations with `base_seq`, state `pending`, `accepted`, `rejected` (+ winning op ids) | survives restarts; never re-sends a rejected `op_id` |
| `digests`, `manifests` | the newest snapshot digest and followed-set manifests per project | |
| files `tiles/<sha256>.jpg` | the tile cache, 500 MB least recently used out | content-addressed like the server |
| Android Keystore-backed encrypted preferences | the session token, `replica_id` per project | cleared on sign-out |

### UI

| Screen | What it shows |
|---|---|
| Sign in | e-mail + password; Continue with Google |
| Projects | owned and shared projects, star to keep offline, sync state ("Synced 2 min ago", "3 edits waiting") |
| Project | the panorama full screen (web view, the shared viewer); a bottom sheet with Rooms, Edit, History (operations with authors), People |
| Settings | storage used, clear cache, sign out, privacy policy |

Copy follows the brand rules; strings live in the Flutter app's localisation file (English; Arabic follows LO1's word list when it lands).

### Jobs / workers

| Worker | When | Does |
|---|---|---|
| `SyncWorker` (WorkManager, periodic) | every 15 min with network | push outbox (≤ 200 a request), pull, refresh digests |
| `SyncNow` (one-off) | network returns; an edit is made online | the same at once |
| `Prefetch` (one-off) | starred project changed, unmetered network, charging | tiles of the followed sets' newest manifests |

Retry and backoff follow `project-log.md` §8 (1, 2, 4 … 60 s ± 20 %, `Retry-After`, never retry 409 or 422 as sent).

### Security and privacy

* The session token lives in Keystore-backed encrypted storage, never in plain preferences or logs; backups of the app's data exclude it.
* Network security config: HTTPS only (cleartext allowed only in the debug build for the LAN test server).
* The cache holds only projects the person opened; signing out wipes the database, the tiles and the token.
* The Data safety answers: account e-mail and name (account management), no tracking, no data sold, data encrypted in transit, deletion through the privacy page's address.

## Deliverables

- [x] `mobile/android/` Flutter project: `lib/` (`api/` generated client, `replica/`, `outbox/`, `sync/`, `viewer/` web view host with offline interception, `screens/`), `assets/viewer/` (PF9's built viewer bundle copied at build time), `test/`
- [x] `server/scripts/export_openapi.py`, `openapi/clients.json`; `scripts/gen-clients.ps1` (TypeScript types for PF9, the Dart client for PF10)
- [x] `scripts/verify-mobile.ps1`: `flutter analyze`, `flutter test`, `flutter build apk --debug` (a separate gate, so the main verify gate does not need the Flutter SDK)
- [x] `mobile/android/store/` (icon, feature graphic, screenshots, `listing.en.md`, `data-safety.md`, `content-rating.md`)
- [x] `eslint.config.mjs` ignores `mobile/**`; README section "Android app"
- [x] Beyond the list: `server/app/mobile/clients.py` (the answers the document describes), `src/viewer/native.ts` +
  `scripts/build-mobile-viewer.mjs` (the viewer's host page), `scripts/make_android_assets.py` (launcher, status and
  store icons, screenshots, feature graphic), `scripts/try-android.ps1` + `scripts/android_relay.py` (the human test),
  the privacy page's Android section (`ANDROID_APP_PRIVACY`)

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_openapi_clients_document_current` | pytest | `openapi/clients.json` equals a fresh export of the routes both clients call (schema drift fails the gate) |
| `test_android_google_token_audience` | pytest | an ID token whose audience is the Web client id signs in through `/auth/google` (verifier mocked, as `server/tests/test_auth.py:6-12` does) |
| `test_android_presence_client_kind` | pytest | presence with `client: "android"` is accepted and listed |
| `action_builder_matches_fixture` | flutter test | the Dart builder's operation equals `action-move.json` field for field |
| `outbox_reconcile_rules` | flutter test | `accepted`, `duplicate`, `rejected` (+ winning) and `not_processed` handled per §6.3; a rejected `op_id` never re-sent |
| `replica_pull_pages_and_head` | flutter test | pulling `ops-remote.json` in pages gives `head_seq` 12 and the history in order |
| `sync_backoff_matches_contract` | flutter test | waits of 1, 2, 4 … 60 s within ± 20 %; `Retry-After` honoured; 409 and 422 not retried |
| `tile_cache_lru_budget` | flutter test | past 500 MB the least recently used tiles go first |
| `viewer_offline_interception` | flutter widget test | with the network off, tile requests are answered from the cache |
| `scripts/verify-mobile.ps1` | build check | analyze, tests and a debug APK green (run by the task; results in As-built) |
| `npm run lint`, `npm run build`, `pytest -q` | build check | the main verify gate stays green |

## Human test

1. Install the Flutter SDK and the Android toolchain per GD4; run `scripts/verify-mobile.ps1` → green and `build/app/outputs/flutter-apk/app-debug.apk`.
2. Local API with PF4 and PF6 merged and a worker running; the API on the PC's LAN address (debug builds allow cleartext to it).
3. `adb install app-debug.apk` → open Truebex → sign in with Google → the project list shows House; star it.
4. Open House → the living room panorama; switch to airplane mode → it stays; open Rooms → Kitchen → Wall finish → choose a colour → "Waiting for connection"; close the app.
5. Reconnect Wi-Fi without opening the app → within 15 min (or at once when the system runs the one-off job) a notification-free sync pushes the edit; the history shows it accepted.
6. On the desktop (a CL1 build) the kitchen wall shows the new colour; the phone's panorama swaps the kitchen tiles after the worker's `tiles` job.
7. Make a conflicting edit offline (the same wall changed on the desktop meanwhile) → on reconnect a notification "Sam changed this first — your edit was replaced" and the history marks it.

## Risks / traps

* Light clients never apply deltas: the phone's "replica" is the log plus digests and tiles; the state shown comes from the newest digest and the tiles, labelled with their time.
* Android limits background work: WorkManager's periodic minimum is 15 minutes and the system may defer it further on battery saver; the one-off job on reconnect and the sync on app open cover the human test.
* The viewer bundle inside the app must match the server's tile manifest version: the app ships the bundle of its own release and refuses a manifest MAJOR it does not know ("Update needed", as the share viewer).
* Google sign-in needs an Android OAuth client with the release key's SHA-1 in the same Google Cloud project; a debug key needs its own entry (GD4).
* The Flutter toolchain is not on the verify machine by default: the separate mobile gate keeps every other task's gate independent of it.
* Play's target API level moves every year: GD4 tracks the current requirement before submission.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t13-pf10-android-native-app`, made from T12's branch (PF9). Autopilot's
  merge of master stopped on three conflicts, resolved by keeping both sides in `564d323` (README: PF9's "Mobile web
  client" and PF11's "Analysis and AI services" sections; `server/app/main.py`: both routers; `constants.ts`: `APP`
  and `CLOUD_AI` / `ADMIN_AI`). Nothing else needed reconciling: on the merged tree `pip install -r
  requirements-dev.txt`, lint, build and pytest (480 passed, 5 skipped) were green before any PF10 change. Commits:
  `a6032ae` (the app, the document, both clients, the tests), `6653498` (store, icons, try-android, privacy, fixes
  from the emulator run) and the docs commit ticking this row.
* **Counts:** pytest 480 → 489 passed (5 skipped): `tests/test_pf10_clients.py` 9 — the doc's three names, the
  generated clients come from this document (`SPEC_SHA256`, the `.d.ts` header, a Dart method per operation), the
  real routes answer exactly the documented shapes (one project walked through all 16 operations; no key the
  document lacks), the contract fixtures are the shared vectors, the store assets (sizes, lengths, brand words),
  the app's strings, the mobile gate and the lint ignore. Flutter: 39 tests (`flutter analyze` clean) — the doc's six
  names (`action_builder_matches_fixture`, `outbox_reconcile_rules` on the in-memory and the SQLite store,
  `replica_pull_pages_and_head`, `sync_backoff_matches_contract`, `tile_cache_lru_budget`,
  `viewer_offline_interception`) plus the sync engine end to end (an offline edit sent by the background job; a
  conflict notified as "Sam changed this first …"; "on another device"; silent Google renewal; prefetch of a starred
  project; every view of an opened project kept for offline hotspots; an unshared project leaving the phone;
  sign-out wiping; presence as `android`) and the screens.
  `scripts/verify-mobile.ps1` green in 159 s. APKs: debug 186.4 MB (all ABIs); release, split per ABI: arm64-v8a
  21.1 MB, armeabi-v7a 18.7 MB, x86_64 22.4 MB. The viewer bundle: 7.0 KB.
  **Live run** (Android 16 emulator `Medium_Phone_API_36`, x86_64, headless and read-only; the local API with PF6's
  worker and `fake_truebex.py`, `demo_mobile.py setup`, `seed_market.py`; reached through `adb reverse` and a relay):
  sign-in by e-mail; "House (Owner)" listed and starred; the panorama drawn by PF9's viewer from the app's loopback
  server, its Bedroom hotspot switching views; rooms by storey with "£1,299.00" from `/market/prices`; airplane mode +
  relay down → Kitchen → West wall → Sage green reads "Waiting for connection"; app closed (home + process kill);
  reconnect → WorkManager's `truebex.sync.now` (blocked only on CONNECTIVITY) sent it **17 s** later with the app
  closed (operation 13, `fill`), no notification; the worker's `tiles` job → the open panorama read "Panorama at
  operation 14 · 6 faces updated"; an offline edit of the same wall while Sam's device moved it (`demo_mobile.py
  move`) → reconnect with the app closed → the notification "Edit replaced · House — Wall finish: Chalk white
  (Kitchen, West wall): Sam changed this first — your edit was replaced" **15 s** later, the replaced edit never in
  the log, the History tab listing it with Dismiss beside Sam's operation; Sam's `GET …/presence` listing Alex as
  `client: "android"` with storey, eye and bearing; relaunch with no network → the cached panorama and the Offline
  banner; Settings "Projects 92 KB · Panorama tiles 530 KB"; sign-out → 0 tiles, the Keystore-backed store an empty
  map, the sign-in screen. The **release** x86_64 build (R8) repeated sign-in, the panorama and the closed-app
  conflict (notification in 9 s). Not run on a physical phone here (none attached), and Google sign-in not run live
  (no OAuth client, GD4): the human test does both.
* **Deviations from Design and why:**
  1. *The document is enriched, not only cut from FastAPI's schema.* PF4's and PF6's routes return dicts and 5.6
     reads its body itself, so FastAPI's schema names no answer. `server/app/mobile/clients.py` holds Pydantic models
     of the answers (and the existing `PushIn`, `PresenceIn`, `PricesRequest` for bodies); the export puts them into the
     schema of the same routes, and `test_routes_answer_the_documented_shapes` fails on any key a route sends that the
     document lacks (the marketplace models name only what the clients read). Every model allows unknown keys.
  2. *One export script, PF12's CLI shape.* T8's `server/scripts/export_openapi.py` (PF12, `--v1`) is not in this
     tree; this one has the same shape (`render()`, `--out`, `--check`, a `DOCUMENTS` table of flag → (file, builder))
     with `--clients`. Merging the two: keep T8's `build()` and its constants, add `CLIENTS_OUT`, `build_clients()` and
     the `--clients` flag, and put `"v1": (OUT, build)` in `DOCUMENTS` beside `"clients"`. Each document keeps its own
     drift test (`test_pf12_openapi_sdks.py`, `test_pf10_clients.py`). `scripts/gen-clients.ps1` stays separate from
     T8's `scripts/gen-sdks.ps1`; both pin openapi-typescript 7.13.0.
  3. *Generators:* the Dart client by OpenAPI Generator 7.26.0 (`dart`, Apache-2.0; the jar is fetched into
     `mobile/.tools/` and checked against Maven Central's SHA-1); PF9's types by openapi-typescript (MIT), as PF12 does
     for its SDK, since PF9 needs types, not a second fetch layer. PF9 now reads `Me`, the snapshot, `PanoramaSet`,
     5.6's and 5.7's answers, prices, search and product through `src/lib/api-clients.d.ts`; `src/viewer/outbox.ts`'s
     `PushResult` accepts `null` where the document says the server may send it. The generated Dart code is in
     `lib/api/gen/` (outside the analyzer) and carries the document's SHA-256.
  4. *"Offline interception" is an in-app loopback server.* `webview_flutter` exposes no request interception, so the
     page and every tile come from `TileServer` on 127.0.0.1 (a random port and a random path; another app on the phone
     cannot read through it): cache first, then the manifest's `tiles_base`, with the bytes checked against the tile's
     name. The release network security config allows cleartext only to 127.0.0.1; debug builds allow it everywhere
     (the LAN test server).
  5. *The replica:* pulled from operation 0 so the whole history is readable offline; a delta is kept as the base64
     text that arrived (never decoded); `base_seq` is the highest operation the phone holds (PF9 uses its head the
     same way). Rejected and failed edits the person dismisses stay as tombstones, so their `op_id` can never be queued
     again.
  6. *Notifications:* every rejection is notified once, also while the app is open (and listed in the history); an
     accepted edit makes none. The status icon is a white mark (`ic_stat_truebex`).
  7. *Robustness found on the device:* a push that finds no network sets the project offline at once ("Waiting for
     connection"); empty long-polls are at least 2 s apart, so a server that answers at once never spins the loops;
     presence carries the view on screen; an opened project's other views are fetched one at a time while online (as
     PF9 does), so a hotspot opens offline too. The project list refreshes explicitly (after a sync, a star, a project
     closing) instead of a database watch.
  8. *Toolchain:* Kotlin incremental compilation is off (`kotlin.incremental=false`; the pub cache on C: and the
     checkout on X: break its caches). `workmanager_android` 0.10.9 still applies the Kotlin Gradle plugin; Flutter
     warns that a future release will refuse it (carry-over below). Release signing reads `android/key.properties`
     (git-ignored); without it a release build is signed with the debug key and is not for the store.
  9. *The human test path:* the phone reaches the local API through `adb reverse` (PF9's `try-mobile.ps1` binds
     127.0.0.1); `adb reverse` keeps working in airplane mode, so `scripts/try-android.ps1` routes it through
     `scripts/android_relay.py`, and going offline is airplane mode **and** stopping the relay.
  10. *Also changed outside `mobile/`:* the privacy page gains "Android app: what stays on your phone"
      (`ANDROID_APP_PRIVACY`, appended to `constants.ts`; Play requires the policy to cover the app); `eslint.config.mjs`
      ignores `mobile/**`; README gains the "Android app" section.
  11. *Store assets* were captured on the emulator: the panorama shows the stand-in renderer's test faces, so
      `mobile/android/store/listing.en.md` lists a retake (and CL1 / CL4) before submission.
* **GD4 actions by the owner (none done here):** the Play Console account; the upload key and
  `mobile/android/android/key.properties`; an Android OAuth client for `com.truebex.app` with the upload key's SHA-1
  (and the debug key's for test builds) in the Google Cloud project of the Web client id, then builds with
  `--dart-define=GOOGLE_SERVER_CLIENT_ID=<the Web client id>`; Play's current target API level; the Data safety and
  content-rating forms from `mobile/android/store/`.
* **Carry-over → which feature:** the device link flow for light clients (a longer-lived credential) → needs a
  fingerprint rule for Android in `licence-api.md` §6.2 first (owner, then a platform task); iOS → not in roadmap 40
  (platform calls are behind interfaces: `SecretStore`, `GoogleTokens`, `SyncScheduler`, `Notifier`, `ViewerSurface`);
  Arabic strings → LO1 (`lib/l10n/`); applying `action` operations and re-rendering → CL1, CL4; real renders for the
  screenshots → CL3; `workmanager_android`'s built-in Kotlin migration → upgrade when the plugin ships it.
  Contracts: PF10 is a client only — no §11 rows and no new proposals (it uses PF9's `digest`, `place.replace`,
  members' `author_id` and the members' panorama read).
