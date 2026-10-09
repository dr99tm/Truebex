# PF10 — Android native app (launch priority 3)

**Needs merged:** PF9. **Unblocks:** none. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\project-log.md` (v1.0.0; the Android app is a light client that writes `action` operations), with `render-jobs.md` and `agent-interface.md` as PF9.

## Status

No native client exists (`00-contract.md` P.1). What this builds on, verified with Grep on 2026-10-09:

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

- [ ] `mobile/android/` Flutter project: `lib/` (`api/` generated client, `replica/`, `outbox/`, `sync/`, `viewer/` web view host with offline interception, `screens/`), `assets/viewer/` (PF9's built viewer bundle copied at build time), `test/`
- [ ] `server/scripts/export_openapi.py`, `openapi/clients.json`; `scripts/gen-clients.ps1` (TypeScript types for PF9, the Dart client for PF10)
- [ ] `scripts/verify-mobile.ps1`: `flutter analyze`, `flutter test`, `flutter build apk --debug` (a separate gate, so the main verify gate does not need the Flutter SDK)
- [ ] `mobile/android/store/` (icon, feature graphic, screenshots, `listing.en.md`, `data-safety.md`, `content-rating.md`)
- [ ] `eslint.config.mjs` ignores `mobile/**`; README section "Android app"

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

* Date, branch, commits:
* Counts (pytest before → after; flutter tests; APK size):
* Deviations from Design and why:
* GD4 actions done by the owner (Play account, keys, OAuth client):
* Carry-over → which feature (device link flow, iOS):
