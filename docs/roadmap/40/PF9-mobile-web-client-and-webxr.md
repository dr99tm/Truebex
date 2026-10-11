# PF9 — Mobile web client and WebXR (launch priority 2)

**Needs merged:** PF4, PF6. **Unblocks:** PF10 (its Needs). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\project-log.md` (v1.0.0; PF9 is a light client that writes `action` operations), with `render-jobs.md` (followed panorama sets) and `agent-interface.md` (the log-safe tools those operations carry).

## Status

**Built 2026-10-11** on `ap/t12-pf9-mobile-web-client-and-webxr` (on master after T30 landed PF6 beside PF4, PF5, PF7,
PF8): the installable app under `/app/` (`src/app/app/`, `src/components/app/`), the light client's modules in
`src/viewer/` (`actions.ts`, `outbox.ts`, `tilediff.ts`, `cachepolicy.ts`, `orientation.ts`, `xr.ts`, hotspots in
`cube.ts`), the service worker `src/sw/sw.ts` → `out/sw.js`, and on the server `author_id` on `/auth/me`, the
snapshot's project digest, members' author ids and members' read of a project's followed sets
(`server/app/mobile/`, `server/app/routers/mobile.py`). Waiting on others: the kernel writing the digest (CL1, after
the owner adds it to the contract), applying `action` operations (CL1, CL4), presence badges on the desktop (CL2), a
real render worker (CL3). See As-built.
Merged with master (PF11, PF12) on 2026-10-11 (Autopilot T33): `/v1` documents the snapshot's `files.digest` and
members' `author_id`; the panorama routes stay off `/v1` (a PF12 carry-over). See As-built.

Before this task no mobile client existed (`00-contract.md` P.1). What this builds on, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Web app manifest | `src/app/manifest.ts:7-8` (names), `:10` (`start_url: "/"`), `:11` (`display: "standalone"`), `:14` (icons 192 and 512) | installable in principle; no service worker, no app routes |
| Icons | `public/icon-192.png`, `public/icon-512.png`, `src/app/apple-icon.png` | no maskable icon |
| Site metadata | `src/app/layout.tsx:19-69` | no `appleWebApp` settings |
| Session in the browser | `src/lib/api.ts:21-38` (`localStorage`), `server/app/config.py:16` (24 h tokens) | the web client's credential (`project-log.md` §4) |
| Account read | `server/app/routers/auth.py:115-120` (`/auth/me`), `server/app/schemas.py:24-34` (`UserOut`) | gains `author_id` (PF1 mints it) so web operations carry the person's author id |
| From PF4, PF6 (Needs) | projects, pull and push, members; followed sets, tiles at `TILES_BASE_URL`, `/jobs` long-poll | |
| From PF5 | `src/viewer/` (framework-free viewer, cube-tile mode from PF6) | the panorama view is shared, not rewritten |

What the owner meant: app-side `00-understanding.md` §8 ("a mobile web client with WebXR, then an Android native app and the headset target").

## Goal

"On the phone, swap the floor finish; the operation reaches the cloud, the worker re-renders two cube faces, the panorama on the phone and the desktop app both update within seconds" (`00-understanding.md` §8). This is the first mobile version of Truebex: an installable web app for Android and iOS home screens that opens the projects a person owns or that are shared with them, walks their panoramas, lists rooms and placed products, makes light edits that travel as operations in the project log, keeps the last panoramas for offline use, and switches to an immersive view on a headset browser.

## Read first

* **`contracts/project-log.md` v1.0.0** — §4 (the web client uses a session token), §5 (open, pull, push, presence), §6.2 (an `action` operation), §6.3 (a rejection and its visible resolution), §6.5 (presence with `client: "web"`), §8 (retry), §9 `action-move.json` (the shape PF9 writes).
* `contracts/agent-interface.md` v1.0.0 §5.7–5.11 (log-safe `place` for products, `move`, `resize`, `fill`, `apply_theme`), §6.2 (refs and units), §6.4 (`FTruebexAgentAction` on the wire).
* `contracts/render-jobs.md` v1.0.0 §5.2 (status long-poll), §6.2 (faces, levels, tiles), §6.4 (follow sets).
* Specifications: W3C WebXR Device API (https://www.w3.org/TR/webxr/), W3C Web Application Manifest (https://www.w3.org/TR/appmanifest/), W3C Service Workers (https://www.w3.org/TR/service-workers/), W3C DeviceOrientation Event (https://www.w3.org/TR/orientation-event/), the Background Synchronization draft (WICG).
* Skills: `truebex-brand-voice` (app copy), `truebex-seo` (the app pages are `noindex`).

## Scope

**In:**
1. A progressive web app under `/app/`: a web app manifest with `id` and `start_url` `/app/`, a maskable icon, iOS home-screen metadata, and a service worker; installable on Android and iOS home screens; labelled the first mobile version.
2. Open a shared or owned project: the list of `GET /projects` (owned and shared with me, role shown), open one (record, members, the followed panorama sets of PF6).
3. Walk its panoramas: the followed sets' tiles through the shared viewer (`src/viewer/` cube-tile mode), hotspots between views, drag and device-orientation look-around, tiles swapped as `rev` changes.
4. Browse rooms and products: rooms by storey, the products placed in each with their names and prices for the project's region (PF7's `POST /market/prices`), themes applied; the data from the snapshot's project digest (a MINOR addition to `project-log.md` §6.4 proposed below).
5. Light edits through the project log, as `action` operations with log-safe tools: move (`move` with `by_mm` or `along_mm`), swap product (`place` of a product replacing another, which needs a MINOR addition to `agent-interface.md` §5.7: an optional `replace` ref), change theme (`apply_theme` on a room) and change a floor or wall finish (`fill`); each with a role check (editor), a pending state until accepted, and the §6.3 visible resolution on a rejection.
6. Offline cache of the last panoramas: the tiles of the last viewed sets (150 MB budget, least recently used out), their manifests and the digests; edits made offline queued and pushed on reconnect.
7. WebXR mode on headsets: an immersive-vr session that shows the current view's cube tiles around the person, controller rays for hotspots, a floating menu for theme and finish changes; offered only when `isSessionSupported("immersive-vr")` says so.
8. Presence: the phone shows up in the desktop app as `client: "web"` with its view (CL2), and others' presence is listed in the project.
9. Tests: build checks for the manifest, the service worker and the pages, and JavaScript self-tests (the action builder against the contract fixture, the tile diff, the cache policy) run through the verify gate.

**Out (and where it goes):**
* Rendering the changed faces and following sets → PF6; applying `action` operations in the kernel → CL1, CL4 (app) and the workers that run the app.
* The native Android app → PF10; the native headset target → PR5 (app).
* Full modelling, deleting entities and sheets on the phone → not planned (light edits only, `00-understanding.md` §8).
* A longer-lived web credential (the 24 h session) → carry-over to `project-log.md` §4 ("PF10 may adopt the device link flow later" applies to the web client too).

## Design

### API

PF9 adds almost nothing to the server; it is a client of PF4, PF6 and PF7.

| Call | From | Use |
|---|---|---|
| `GET /auth/me` | PF1's route, `author_id` added to `UserOut` | the `author` of every operation the web client writes |
| `GET /projects`, `GET /projects/{pid}` | `project-log.md` 5.2, 5.3 | the list and the record |
| `GET /projects/{pid}/snapshots/latest` | 5.9 | the digest file of the newest snapshot (MINOR proposal below) |
| `GET /projects/{pid}/ops?after=&wait_s=25` | 5.7 | follow `head_seq` (the client never applies deltas, it tracks numbers and its own operations' fate) |
| `POST /projects/{pid}/ops` | 5.6 | push `action` operations (≤ 200 a request) |
| `PUT /projects/{pid}/presence` | 5.17 | `client: "web"` every 10 s while visible |
| `GET /jobs?project_id=&kind=panorama`, `GET /jobs/{follow_id}?rev=&wait_s=25`, `GET /jobs/{id}/output` | `render-jobs.md` 5.3, 5.2, 5.5 | find the followed set, wait for new tiles, read the manifest |
| `POST /market/prices` | `marketplace-api.md` 5.5 | prices of the placed products for the project's region |

An `action` operation as PF9 writes it (fields of `project-log.md` §6.2; the action of `agent-interface.md` §6.4):

```json
{"op_id": "<32 hex>", "author": "<author_id>", "author_kind": "person", "at": "2026-10-09T12:00:00.000Z", "replica_id": "<32 hex>",
 "base_seq": 1203, "kind": "action", "name": "Floor finish", "touched": ["<room ref>"],
 "action": {"tool": "fill", "args": {"target": "<room ref>", "face": "floor", "finish": {"kind": "paint", "colour": "#C8B79E"}},
            "permission": "edit", "session": "<32 hex>", "request_id": "<32 hex>"}}
```

`replica_id` is minted once per browser installation and project and kept in IndexedDB; `touched` is the sorted, unique set of refs in `args`; `name` is the undo-step name the desktop shows.

Contract changes this feature needs (written in the app repo's contracts first by the owner, C.9; recorded in As-built):

| Contract | Change (MINOR) | Why |
|---|---|---|
| `project-log.md` §6.4 | a snapshot may carry `digest` (`truebex-project-digest/1`: storeys; rooms with id, name, storey, area and centroid; saved views; placed products with entity id, `FCadProductRef` and room; themes per room), written by the kernel replica that uploads the snapshot | a light client cannot read `.tbxp`; it needs names and refs to offer edits |
| `agent-interface.md` §5.7 | `place` gains `replace` (a product's ref) for `kind: "product"`, log-safe | "swap product" without a delete tool |

### Data (client side)

| Store | Holds | Limit |
|---|---|---|
| Cache Storage `tiles-v1` | tiles by URL (immutable, content-addressed) | 150 MB, least recently used out |
| Cache Storage `shell-v1` | `/_next/static/*` (hashed, cache-first), `/app/` HTML (network-first) | |
| IndexedDB `truebex-app` | projects, digests, manifests by job, `replica_id` per project, pending operations (outbox), last `head_seq` | outbox kept until accepted or rejected |

`navigator.storage.persist()` is requested after the first project opens, so the browser does not evict the cache under pressure. API responses are never cached by the service worker.

### UI

| Route (static, noindex, `?id=` read inside `Suspense`) | What it shows |
|---|---|
| `src/app/app/page.tsx` | sign-in prompt or the project list; an Install button where `beforeinstallprompt` fires; iOS "Add to Home Screen" hint |
| `src/app/app/project/page.tsx` | the panorama full screen; a bottom sheet with Rooms (by storey, products, theme), Edit (move nudges ± 50 / 250 mm, swap product from same-category suggestions, room theme, floor and wall finish), People (presence); a pending badge per edit; Enter VR when supported |
| `src/viewer/xr.ts` | the immersive mode on the WebXR Device API through an MIT-licensed WebGL 3D library with WebXR support, loaded only on Enter VR |
| `src/sw/sw.ts` → `out/sw.js` | the service worker, bundled by PF5's esbuild step; registered by the `/app/` layout with scope `/` |
| `src/app/manifest.ts`, `src/app/layout.tsx` | `id` and `start_url` `/app/`, `scope` `/` (sign-in pages stay inside the installed window), a maskable 512 icon; `appleWebApp` metadata |

Copy (`src/lib/constants.ts` `APP`): the install hints, the offline banner, the conflict line "Sam changed this first — your edit was replaced", the pending and failed states.

### Jobs / workers

None on the server. On the client: the outbox flushes on reconnect (`online` event), on app start, and through Background Sync where the browser has it; a rejected operation is shown, dropped and never re-sent (§6.3 rule 4).

### Security and privacy

* The session token stays where the site keeps it (`src/lib/api.ts:21-38`); the service worker never sees or caches authenticated responses.
* Edits need the editor role on the server (`project-log.md` §4); the client only hides what the role forbids.
* Tiles are public by hash (PF6); the offline cache holds only what the person viewed and is cleared on sign-out.
* WebXR asks the browser's own permission; device orientation on iOS asks once through `DeviceOrientationEvent.requestPermission()` from a tap.

## Deliverables

- [x] `src/app/app/` (list, project), `src/viewer/xr.ts`, `src/viewer/actions.ts` (the action builder), `src/viewer/outbox.ts`, `src/sw/sw.ts`, `src/lib/app.ts` — plus `src/components/app/` (the screens, `useProject.ts`), `src/viewer/{tilediff,cachepolicy,orientation}.ts` and hotspots / `look()` in `src/viewer/cube.ts`
- [x] `src/viewer/selftest.ts` → `out/viewer/selftest.mjs` (bundled by the build, `scripts/build-app.mjs`): checks the builder against `server/tests/contracts/project-log/action-move.json`, the tile diff and the cache policy (and the outbox and the orientation maths: 76 checks)
- [x] `src/app/manifest.ts` (`id`, `start_url`, `scope`, maskable icon), `src/app/layout.tsx` (`appleWebApp`), a maskable icon from `scripts/make_web_assets.py` (`--icons`, `public/icon-maskable-512.png`)
- [x] `server/app/schemas.py` and `server/app/users.py`: `author_id` on `/auth/me`
- [x] copy in `constants.ts` (`APP`); `ROADMAP` stays as it is until the tracker row is merged (brand rule)
- [x] the two contract MINOR proposals recorded in As-built (and three more the build needed)

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_auth_me_includes_author_id` | pytest | `/auth/me` returns the same 32-hex `author_id` as `/licence/account`; 401 without session |
| `test_web_action_op_accepted_by_project_log` | pytest | an `action` operation built like the fixture, pushed with a session token, is accepted and pulled back unchanged |
| `test_web_action_op_conflict_visible` | pytest | a web `action` touching an entity another replica changed after `base_seq` → `rejected` with `winning` |
| `test_web_push_requires_editor` | pytest | a viewer's session → 403 `forbidden` with `data.needed` `editor` |
| `test_site_pf9_manifest_installable` | build check | `out/manifest.webmanifest` has `id` and `start_url` `/app/`, `display` `standalone`, a 512 maskable icon |
| `test_site_pf9_service_worker_built` | build check | `out/sw.js` exists, registers no API path for caching, ≤ 30 KB |
| `test_site_pf9_app_pages_noindex` | build check | `out/app/index.html` and `out/app/project/index.html` carry `noindex` |
| `test_site_pf9_js_selftests` | build check | `node out/viewer/selftest.mjs` exits 0 (action builder, tile diff, cache policy) |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. Local API with PF4 and PF6 merged, a worker running (PF6 human test steps 2–4) and a followed set on the fixture house; build with `NEXT_PUBLIC_AUTH_URL` and the API on the PC's LAN address; serve with `scripts/autopilot-serve.ps1`.
2. On an Android phone open `http://<lan>:31NN/app/` → sign in → Install → Truebex opens from the home screen without browser chrome; on an iPhone, Share → Add to Home Screen does the same.
3. The project list shows House (Owner); open it → the living room panorama as tiles; drag and tilt to look around; tap the Kitchen hotspot.
4. Rooms → Living room → Floor finish → choose oak → the edit shows "Pending"; within seconds the worker's `tiles` job renders the floor faces and the panorama swaps those tiles; the desktop app (a CL1 build) shows the new floor too.
5. Edit → Move the sofa 250 mm left → accepted; at the same time move the same sofa on the desktop → whichever arrived second shows "Sam changed this first — your edit was replaced".
6. Airplane mode → close and reopen the app → the last panoramas still show with an Offline banner; change the wall finish → "Waiting for connection"; airplane mode off → the edit is sent and accepted.
7. On a headset browser open the same URL → Enter VR → the living room surrounds you; point at the Kitchen hotspot and select → you are in the kitchen; open the floating menu → change the theme.

## Risks / traps

* The tiles' CDN must send CORS headers, or WebGL refuses them as textures (PF6's tile layout says so); the share viewer and the app share the same code and the same failure.
* iPhone browsers may offer no immersive WebXR session and no Background Sync: feature detection decides (never a user-agent check), the magic-window view and a flush-on-open outbox cover them; browsers may clear a site's storage after long disuse, so persistence is requested and missing tiles simply download again.
* The 24 h session (`server/app/config.py:16`) signs phone users out daily; the carry-over row asks `project-log.md` §4 for the device link flow on light clients.
* Static export: `/app/project/?id=` (no dynamic segment); the service worker must not cache the HTML of other routes cache-first, or a deploy would leave installed apps on stale chunks.
* `public/` and `src/sw/` code is linted by the site's ESLint: browser-only globals (`self`, `clients`) need the service worker's own lint environment.
* The light client never decodes deltas: everything it shows comes from digests, manifests and its own pending operations; a stale digest between snapshots is expected and labelled with its time.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t12-pf9-mobile-web-client-and-webxr`. The first start ran on PF6's branch
  tip; the manager stopped it before any commit and queued it behind T30, and Autopilot merged master (PF4, PF5, PF6,
  PF7, PF8, PF2a, PF2b, PF3, PF3a, PF11) in `bfbb2dd`. Reconciling that combination needed nothing: on the merged tree
  `npm ci`, the venv's new pins, lint, build and pytest (424 passed, 5 skipped) were green before any PF9 change.
  Commits: `bd3319b` (server), `cef2186` (site), `4048ec0` (fixes from the live run), and the docs commit ticking this
  row.
* **Counts:** pytest 424 → 441 passed (5 skipped, the Postgres-marked ones): `tests/test_mobile.py` 11 (the doc's four
  names; the digest registered, served, validated and pruned; members' author ids; the members' panorama read, its
  auth and validation; `demo_mobile.py` through the human-test path) and `tests/test_site_pf9.py` 6 build checks (the
  doc's four names; the 3D library only in a lazy chunk; the copy and the framework-free modules). The JS self-test:
  76 checks. Sizes: `out/app/index.html` 20 KB, `out/app/project/index.html` 16 KB, `out/sw.js` 4.9 KB (25 files
  precached), `out/viewer/selftest.mjs` 32 KB; the project page loads 809 KB of scripts before gzip against the
  site's 760–769 KB baseline (PF9's own: 63 KB); the 3D library is a 722 KB chunk fetched only when the headset view
  starts.
  **Live run** (uvicorn on SQLite with inline jobs, PF6's worker with `fake_truebex.py`, `demo_mobile.py setup`,
  `seed_market.py`, the site built against that API and served by `scripts/serve-out.py`, headless Edge 154 over CDP
  at 412×915 with touch): 35 of 35 checks — signed-out prompt; the list shows "House (Owner)" and "First mobile
  version"; the service worker controls the page; 24 tiles; hotspots Kitchen and Bedroom; drag turns the view; the
  Kitchen hotspot switches view; rooms by storey with products and "GBP 1,299.00" from `/market/prices`; "Rooms as of
  operation 12"; Floor finish → Warm sand listed at once, "Saved" in 335 ms, the worker's `tiles` job re-rendered two
  faces and the panorama swapped them **769 ms after the tap** (set rev 1 → 2); the log holds `fill` by the person's
  author id; People lists Sam on the desktop app and Sam's `demo_replica.py presence` lists "Alex (web)"; offline
  reload shows the cached panorama with the Offline banner; a wall finish and a sofa move wait ("Waiting for
  connection"); Sam's desktop move lands first; back online the wall finish is saved and the move shows "Sam changed
  this first — your edit was replaced" and never enters the log; caches hold 32 tiles and 25 shell files and no API
  answer; sign-out empties both. **Headset** (headless Edge has no XR device, so `navigator.xr`, `XRWebGLLayer` and an
  input source were mocked in the page): "View in headset" appears only when `isSessionSupported("immersive-vr")` is
  true; the session runs its frame loop; the six faces were composed from 24 tiles; a controller ray on the Kitchen
  hotspot switched the view; the floating menu's "Warm minimal" wrote `apply_theme` on the kitchen and it was saved.
  The same 35 checks passed again on the human test's own path: `scripts/try-mobile.ps1` (API on :8000, worker,
  setup, market seed, build) served by `scripts/autopilot-serve.ps1`. Not run on a real phone or headset (no device
  here): the owner's human test does.
* **Deviations from Design and why:**
  1. *Followed sets are read through the project, not `/jobs`.* 5.2, 5.3 and 5.5 are owner-only (a job belongs to the
     account that submitted it), so an editor's or viewer's phone could never open the owner's set. New
     `GET /projects/{pid}/panoramas` (the project's sets of active members, newest first, `mine` marked) and
     `GET /projects/{pid}/panoramas/{set_id}?rev=&wait_s=` (the state `render.live.state` builds for the live share,
     long-polled on `rev` like 5.2), viewer role, `Cache-Control: private, no-store`
     (`server/app/mobile/panoramas.py`, `server/app/routers/mobile.py`, one line in `main.py`).
  2. *The digest travels as a third snapshot file*, `files.digest` (64 hex) in 5.8, uploaded in the same `snapshot`
     upload as the `.tbxp`, checked to be JSON of `truebex-project-digest/1` and ≤ 1 MiB (422 `validation_failed` on
     `files.digest` otherwise), counted in the project's bytes, pruned with its snapshot, and served by 5.9 as
     `files.digest` with a signed URL like the others (the data bucket's CORS rule already allows GET from any
     origin). Two nullable columns on `project_snapshots` (PF9 block in `database._ADDED_COLUMNS`). The fixture is
     `server/tests/contracts/project-digest/digest-house.json` (`scripts/make_digest_fixture.py`, PF4's ids, two
     products of the marketplace fixture's supplier, region GB) in its own folder so PF4's staged set is untouched.
  3. *Members carry `author_id`* (5.13, null for an invitation), so the phone names who won a conflict ("Sam changed
     this first …"); a winner with the person's own id reads "You changed this first on another device …".
  4. *The head is followed with 5.7 at `limit=1`* (the client never reads deltas; it needs `head_seq` and the wake-up),
     and the digest is re-read at most every 30 s while the head moves.
  5. *Background Sync never gives the token to the service worker.* A `sync` event wakes an open app page, which
     sends its own outbox; with no page open the outbox goes out on the next start or reconnect. The rejected
     operation stays listed with its winner until dismissed and is never sent again; `not_processed` ones are sent
     again unchanged (same `op_id`, same `base_seq`), so a stale offline edit of something someone else changed is
     rejected and shown, never silently applied.
  6. *Wall finish is per wall.* The digest lists each room's walls with the face that looks into the room; the phone
     picks one wall and writes one `fill` with that face (`agent-interface.md` §5.10 has no "every wall of a room"
     face). Moves are nudges of 50 / 250 mm left, right, away or closer relative to where the person looks
     (`by_mm`), and doors and windows slide along their wall (`along_mm`).
  7. *Copy:* the button reads "View in headset", not "Enter VR" (brand voice avoids "VR"); `FEATURES` and `ROADMAP`
     are untouched. The installed app's manifest keeps the site's name and description.
  8. *Shared code touched, additively:* `src/viewer/cube.ts` gains hotspots, `look()`, `yawDeg` / `pitchDeg` and an
     `onTurn` option (the share viewer is unchanged); the site navbar returns nothing under `/app/`; `logout()` also
     deletes the app's IndexedDB stores and the tile cache; `Member` gains `author_id`; `make_web_assets.py` gains
     `--icons` and the maskable icon; `package.json` runs `scripts/build-app.mjs` after PF5's viewer step and adds
     `three` 0.186.1 (MIT) and `@types/three`.
  9. *Service worker details:* the precache list (the two app pages, the hashed files they reference, the manifest
     and icons) is written into `sw.js` at build time, so a deploy installs a new worker and drops the old build's
     files; tiles are fetched with CORS (an opaque response would count megabytes against the quota) and their LRU
     index is kept in memory per worker life and written in one batch a second later (writing it once per tile
     starved the page's IndexedDB on a first visit: a tap took 38 s to save; now 0.3 s).
  10. *A local trial script*, `scripts/try-mobile.ps1` (not in the Design): the API on :8000 with its own SQLite
      database under `server/try-mobile/` (gitignored, one line at the end of `server/.gitignore`), the contract
      fixtures' TEST licence key, a worker token issued through the admin route, PF6's worker with `fake_truebex.py`,
      `demo_mobile.py setup`, `seed_market.py`, and `out/` built against :8000 — so the human test needs no `.env`.
  11. *Next's segment prefetch* asks for `/app/__next.app.__PAGE__.txt` and gets 404 (the export writes
      `__next.app/__PAGE__.txt`); Next falls back to the full payload. It happens on every exported page, not only
      PF9's.
* **Merged with master: PF11 and PF12 (2026-10-11, Autopilot T33, `ap/t33-merge-t12-pf9-mobile-web-client`):** verify
  green (lint, build, pytest 534 passed and the 5 Postgres-only skips: master's 511, this feature's 17 and the
  merge's 6). Three files conflicted, each where both sides append to the end (`main.py`'s router lines,
  `constants.ts`, the README section): both sides kept, master's first. `main.py` keeps PF12's single
  `uploads.router` include and `v1.install(app)` and adds PF9's `mobile_router` once at the end; `schemas.py`
  (`UserOut.author_id` beside PF12's key scopes) and `database.py` (both `_ADDED_COLUMNS` blocks) merged cleanly.
  The venv took PF11's pins (`anthropic` 1.13.0); `package.json` and the lock were unchanged on master, so `three`
  0.186.1, `@types/three` and the `build-app.mjs` step stand. PF11's rule that a worker token claims only kinds of its
  class keeps `try-mobile.ps1`'s `panorama` + `tiles` on `gpu-std` valid. **One fix where they meet:** PF12's `/v1`
  mirror passed PF9's `files.digest` and members' `author_id` through at runtime (its response models allow extra
  fields) but `openapi/v1.json`, the SDK types and the `/developers/` reference did not name them, and the request's
  `SnapshotFilesIn` already had `digest`, so the drift test failed. `SnapshotFiles` gains
  `digest: SnapshotFileUrl | None` (required and nullable like `tbxpack`: the server always answers it), `Member`
  gains `author_id`, and both snapshot-file models a description naming the digest (it shows in the reference's
  `files` rows); `openapi/v1.json` and both SDKs regenerated with `scripts\gen-sdks.ps1`, `API_VERSION` left at 1.0.0
  as T32 did (nothing is published yet). `tests/test_pf9_pf12_meet.py` (6): a key's `/v1` snapshot with a digest
  round-trips (and a bad one is the contract's 422 on `files.digest`); an API key's agent edit beats a phone edit
  of the same sofa, rejected with the agent's operation as winning (no member's `author_id`, so the phone reads
  "Someone changed this first …"), and the key pulls the phone's later edit; the document and both SDKs' types name
  the fields; the Python SDK registers and reads a digest; the panorama routes refuse a key (401) and are not in the
  document; the built `/developers/projects/` names the digest. **Live run** on the human test's path
  (`try-mobile.ps1`, out/ served on :3133, headless Edge at 412×915): 25 of 25 — `/v1` and the SDK read the House's
  digest and members' author ids; the phone lists and opens the House (24 tiles, rooms as of operation 12, a GBP
  price); a floor finish is saved and the key pulls it through `/v1`; offline, a sofa move waits while the key's
  agent moves the sofa through `/v1`; back online the phone shows "Someone changed this first — your edit was
  replaced" and its move never enters the log; with the service worker in control `/developers/projects/` names
  the digest, Dashboard → API keys lists the key with its scopes, Dashboard → Cloud shows AI credits, the site navbar
  is back outside `/app/`, and the caches hold app files and 24 tiles but no API answer and no page outside `/app/`.
  **Carry-over → PF12:** a `/v1` mirror of `GET /projects/{pid}/panoramas[/{set_id}]` (with the `render-jobs.md` §5
  MINOR proposal); today they take a session or a device token and answer an API key 401. **→ PF9 / PF10:** a winner
  with `author_kind: "agent"` could read as the assistant rather than "Someone" (new copy, not added here).
* **Contract proposals for the owner** (written in the app repo's contracts first, C.9; none has landed yet):
  * `project-log.md` §6.4 (MINOR): a snapshot may carry `digest` — `truebex-project-digest/1`: storeys; rooms with id,
    name, storey, `area_m2`, `centroid_mm`, bounding walls (`id`, `name`, `face`), theme and floor finish; saved views
    with `eye_mm` and `yaw_deg`; placed products with entity id, `FCadProductRef`, category and room; openings with
    their host; themes; the market `region` — written by the kernel replica that uploads the snapshot, registered as
    `files.digest` in 5.8 and served in 5.9 (deviation 2).
  * `agent-interface.md` §5.7 (MINOR): `place` gains `replace` (a placed product's ref) for `kind: "product"`,
    log-safe; with it the light client sends `room` (the replaced product's room) too, so a 1.0 reader's required
    `room` or `at_mm` still holds.
  * `project-log.md` §5.13 (MINOR): members carry `author_id` (deviation 3).
  * `render-jobs.md` §5 (MINOR): `GET /projects/{pid}/panoramas` and `…/panoramas/{set_id}` for project members
    (deviation 1).
  * `/auth/me` (the site's account route, no contract): returns the same `author_id` as licence 5.7, minted on first
    read.
  * Contract §11 rows: `project-log.md` lists PF9 as a client only (no endpoint rows); the rows to add are the two
    reads of deviation 1, "PF9: done".
* **Carry-over → which feature:** **CL1** — write the digest beside each snapshot and apply `action` operations
  (`fill`, `apply_theme`, `move`, `place` with `replace`) deterministically; **CL4** — the edit → tiles loop with a real
  render; **CL2** — show `client: "web"` presence (view with storey, eye and bearing) and the soft-lock badges;
  **CL3** — the real `-mwrender` (the live run used `fake_truebex.py`, which re-renders the north and east faces on
  every edit); **PF10** — reuse `src/viewer/actions.ts` and the outbox rules, and the device link flow for a longer
  credential; the **24 h session** signs phone users out daily (`project-log.md` §4 carry-over row: the device link
  flow for light clients); **PR2** — the theme catalogue the digest's `themes` list should come from; **PR5** — the
  native headset target. **The owner** — the proposals above; a real Android phone, iPhone and headset run of the
  human test (HTTPS or `adb reverse`: service workers, install and WebXR need a secure context).
