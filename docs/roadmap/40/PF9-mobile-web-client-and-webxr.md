# PF9 — Mobile web client and WebXR (launch priority 2)

**Needs merged:** PF4, PF6. **Unblocks:** PF10 (its Needs). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\project-log.md` (v1.0.0; PF9 is a light client that writes `action` operations), with `render-jobs.md` (followed panorama sets) and `agent-interface.md` (the log-safe tools those operations carry).

## Status

No mobile client exists (`00-contract.md` P.1). What this builds on, verified with Grep on 2026-10-09:

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

- [ ] `src/app/app/` (list, project), `src/viewer/xr.ts`, `src/viewer/actions.ts` (the action builder), `src/viewer/outbox.ts`, `src/sw/sw.ts`, `src/lib/app.ts`
- [ ] `src/viewer/selftest.ts` → `out/viewer/selftest.mjs` (bundled by the build): checks the builder against `server/tests/contracts/project-log/action-move.json`, the tile diff and the cache policy
- [ ] `src/app/manifest.ts` (`id`, `start_url`, `scope`, maskable icon), `src/app/layout.tsx` (`appleWebApp`), a maskable icon from `scripts/make_web_assets.py`
- [ ] `server/app/schemas.py` and `server/app/users.py`: `author_id` on `/auth/me`
- [ ] copy in `constants.ts`; `ROADMAP` stays as it is until the tracker row is merged (brand rule)
- [ ] the two contract MINOR proposals recorded in As-built

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

* Date, branch, commits:
* Counts (pytest before → after; `out/app/` page sizes):
* Deviations from Design and why:
* Contract MINOR proposals for the owner (`project-log.md` §6.4 `digest`; `agent-interface.md` §5.7 `replace`) and whether they landed:
* Carry-over → which feature:
