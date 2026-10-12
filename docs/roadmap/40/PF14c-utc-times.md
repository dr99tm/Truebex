# PF14c — Every API time answered in UTC with Z, and the last Postgres time-zone test fixed (launch priority 2)

**Needs merged:** PF2c (`UtcDateTime`, the billing times), PF7a (the Postgres run that named the failing tests); both on `master` 6ef7928. **Unblocks:** the whole suite on Postgres in any session time zone; any client (site, app, SDK users) reading `/auth/*` and `/keys` times without guessing their zone. **Contract:** none changed. The times now follow the licence contract's rule for every endpoint (`contracts/licence-api.md` §5: "times are RFC 3339 UTC with `Z`"); no `openapi/*.json` changes (the schemas already said `date-time` or `string`).

## Status

**Built (2026-10-12, branch `ap/t55-pf14c-every-api-time-answered-in`, Autopilot T55); see As-built.** Checked on `master` 6ef7928 before the work began:

| # | Where (master 6ef7928) | Before |
|---|---|---|
| 1 | `server/app/schemas.py:33` `UserOut.created_at`; `:79-81` `ApiKeyOut.created_at`, `last_used_at`, `revoked_at` (plain `datetime`) | SQLite answered `2026-10-12T07:35:02.603743` (no zone), Postgres in Asia/Baghdad `2026-10-12T10:41:26.989102+03:00`. These two models reach `/auth/register`, `/auth/login`, `/auth/google`, `/auth/me`, `GET`/`POST`/`DELETE /keys` and the session token inside `/licence/link/poll` |
| 2 | `server/app/routers/v1/__init__.py:41` `/v1/ping` | `datetime.now(timezone.utc).isoformat()`: `…+00:00`, not `Z` |
| 3 | `server/app/routers/shares.py:49` `PatchShareIn.expires_at` (plain `datetime`) | a `+03:00` time stayed `+03:00` in the model. `shares.change` turned it into UTC (`clock.floor_s`) before storing, so the stored value was right, but only because of the service |
| 4 | `server/tests/test_supplier_feeds.py:289` | `row.next_pull_at.replace(tzinfo=timezone.utc)` relabelled Postgres's `05:00+03:00` as `05:00 UTC`; the test failed on Postgres outside UTC although the stored value was right |

How they were found: the app has 314 routes. 20 answer through a Pydantic response model, 236 return a dict and 48 a `Response`. A walk of every response model found item 1. A one-off pytest plugin wrapped FastAPI's `run_endpoint_function` for a whole SQLite run (317 handler functions called) and recorded every `datetime` object and every time string without `Z` that a handler returned: it found items 1 and 2 (`/licence/link/poll` through `UserOut`) and the billing models (already `UtcDateTime`). The 21 dict handlers the suite never calls were read by hand: they build their answers with serializers that already use `licence.clock.rfc3339` (`supplier_admin_json`, `order_json`, `report_json`, `source_json`, `detail_json`, `team_json`, the webhook and project serializers). A handler that returns a `JSONResponse` cannot carry a `datetime` (it would not serialise), and `.isoformat()` was used only for dates, cursors and `/v1/ping`.

Sources: PF2c As-built carry-over ("zone-less times outside billing: `UserOut`, `ApiKeyOut` and the other pre-contract models; `UtcDateTime` is ready to reuse"); PF7a As-built ("the next plan review: the time-zone test failures"; PF2c fixed two of the three).

## Goal

Every time the API answers is RFC 3339 UTC ending in `Z`, on SQLite (this PC, every human test) and on Postgres whatever the session's time zone. A client never has to guess whether a zone-less string means UTC or local time. On Dashboard, API keys, "Created" and "Last used" show the viewer's own local date. A gate fails as soon as a response model gets a plain `datetime` again. The whole suite passes on Postgres in a non-UTC session zone.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4; the As-built of `PF2c-billing-tidy-ups.md` and `PF7a-marketplace-search-production.md`.
* `server/app/schemas.py`, `server/app/licence/clock.py` (`rfc3339`, `aware`), `server/app/telemetry/service.py` (`iso`).
* `server/tests/test_pf2c_billing_tidy.py` (`test_billing_times_are_utc` and its Postgres twin), `server/tests/conftest.py` (`TEST_DATABASE_URL`, `TEST_APP_DATABASE_URL`).
* `src/lib/api.ts` (`parseServerDate`, `formatDate`), `src/app/dashboard/keys/page.tsx`, `src/app/dashboard/page.tsx`.

## Scope

**In:**

1. Every response model the API serves uses `UtcDateTime` for its datetime fields: `UserOut.created_at`; `ApiKeyOut` (and `ApiKeyCreated`) `created_at`, `last_used_at`, `revoked_at`. `UtcDateTime` moves from `schemas.py` to its own module, `server/app/utc.py`, and `schemas.py` imports it, so the billing models keep the same type.
2. Route handlers that return dicts with times in them answer RFC 3339 UTC with `Z`: `/v1/ping` through `licence.clock.rfc3339`; `/licence/link/poll` through `UserOut` (it dumps `Token` to JSON).
3. A gate test walks every route's response model (`app.routes`: `response_model` and the models in `responses`) and fails on a datetime field that is not `UtcDateTime`, naming the field.
4. `test_feed_source_daily_pull` compares aware datetimes (`clock.aware`); its intent is unchanged.
5. The site code that shows these times reads them correctly with `Z`: the API keys page and the dashboard home go through `formatDate` → `parseServerDate`. No copy change.
6. `PatchShareIn.expires_at` accepts any RFC 3339 time (an offset, `Z`, or none = UTC) and holds it in UTC from the model on (`UtcDateTime`), so it is stored in UTC.

**Out (and where it goes):**

* The contract endpoints that already format their times with `licence.clock.rfc3339` or `telemetry.service.iso`: unchanged (whole seconds, `Z`).
* Input models other than `PatchShareIn`, and telemetry's wire models (inputs): unchanged.
* Showing a time of day next to the dates on the API keys page: a copy change, not asked for.
* HTTP header dates and CSV exports: not JSON answers. `/admin/telemetry/export.csv` holds days only; the organisation audit CSV already writes `rfc3339` times.

## Design

**API.** No endpoint, field or status changes; only the wire form of these times:

| Answer | Before (SQLite / Postgres, Asia/Baghdad) | After |
|---|---|---|
| `user.created_at` (`/auth/register`, `/auth/login`, `/auth/google`, `/licence/link/poll` → `token.user`), `/auth/me` `created_at` | `2026-10-12T07:35:02.603743` / `…10:35:02.603743+03:00` | `2026-10-12T07:35:02.603743Z` |
| `/keys` `created_at`, `last_used_at`, `revoked_at` | the same two forms | `…Z`, microseconds kept |
| `/v1/ping` `time` | `2026-10-12T07:35:02.461152+00:00` | `2026-10-12T07:35:02Z` (whole seconds, `rfc3339`) |
| `PATCH /shares/{id}` and `/v1/shares/{id}` `expires_at` in | `+03:00` kept in the model, converted by the service | converted to UTC by the model; the answer unchanged (`rfc3339`) |

`UtcDateTime = Annotated[datetime, AfterValidator(_utc)]`: a naive value (SQLite) is taken as UTC; an aware one (Postgres in the session's zone, or a client's offset) is converted. Pydantic writes a UTC time with `Z`. The JSON schemas do not change (an after-validator adds nothing), so `openapi/v1.json` and `openapi/clients.json` stay current.

**Data.** No migration. Nothing stored changes.

**UI.** None. `parseServerDate` already reads `Z`, an offset and a zone-less time alike; the keys page (`formatDate(k.created_at)`, `k.last_used_at`, `k.revoked_at`) and the dashboard home (`formatDate(user.created_at)`) use it. With `Z` the site no longer depends on its zone-less fallback.

**Security and privacy.** None.

## Deliverables

- [x] `server/app/utc.py`: `UtcDateTime` (moved from `schemas.py`)
- [x] `server/app/schemas.py`: `UserOut`, `ApiKeyOut` on `UtcDateTime`; imports it from `utc.py`
- [x] `server/app/routers/v1/__init__.py`: `/v1/ping` through `clock.rfc3339(clock.now())`
- [x] `server/app/routers/shares.py`: `PatchShareIn.expires_at: UtcDateTime | None`
- [x] `server/tests/test_pf14c_utc_times.py` (7 tests, one Postgres-marked)
- [x] `server/tests/test_supplier_feeds.py`: `test_feed_source_daily_pull` compares aware times
- [x] this doc; the PF14c row in `docs/roadmap/40/README.md`; the "API times in UTC (PF14c)" section at the end of the root `README.md`

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_user_and_key_times_are_utc` | pytest | `UserOut` and `ApiKeyOut` write `2026-11-10T06:47:10.150607Z` from a naive, a `+03:00` and a UTC value; through the API on SQLite, register, login and `/auth/me` answer `user.created_at` in `Z`, the same instant; a key made, used once by `/v1/ping` and listed answers `created_at` ≤ `last_used_at` in `Z`, equal to the stored values; the revoke answers `revoked_at` in `Z` |
| `test_user_and_key_times_are_utc_postgres` | pytest, `postgres` | with `TEST_DATABASE_URL` and the session at `TimeZone=Asia/Baghdad`: the stored `created_at` and `last_used_at` read back `+03:00`, and `/auth/me` and `/keys` answer them in `Z` as the same instants |
| `test_response_models_use_utc_datetime` | pytest (gate) | the walk finds a plain `datetime` at any depth (a model in a list, a dict of lists, `X | None`) and passes `UtcDateTime`; over every `APIRoute` (more than 250) no response model or documented answer has a plain `datetime`; the walk reached `UserOut.created_at`, the three `ApiKeyOut` times and two billing ones |
| `test_dict_routes_answer_utc[/v1/ping]` | pytest | `time` matches RFC 3339 with `Z`, no `+`, within 5 minutes of now |
| `test_dict_routes_answer_utc[/licence/link/poll]` | pytest | the approved poll's `token.user.created_at` ends in `Z` and equals `/auth/me`'s |
| `test_share_expiry_offset_stored_utc` | pytest | `PATCH /shares/{id}` with a `+03:00` `expires_at` answers the UTC time with `Z`; SQLite's stored text is the UTC wall time; a zone-less time is read as UTC; `PatchShareIn` itself holds the value at offset 0 |
| `test_site_pf14c_reads_utc_times` | build check (source + node) | the keys page formats `created_at`, `last_used_at`, `revoked_at` and the dashboard home `user.created_at` with `formatDate`, no `new Date(`; `parseServerDate` (run in node) reads `…Z`, `…+03:00` and zone-less as the same instant, and a viewer in Asia/Baghdad sees `11/11/2026, 01:30:05` for `2026-11-10T22:30:05Z` |
| `test_feed_source_daily_pull` | pytest (changed) | `aware(row.next_pull_at) == nxt + 1 day`: passes on Postgres in Asia/Baghdad |

## Human test

On the served `out/` against a local API on SQLite (run everything in the worktree; port 3155 below is 3100 + the task number, which `autopilot-serve.ps1` prints):

1. In PowerShell: `$env:CORS_ORIGINS='http://127.0.0.1:3155,http://127.0.0.1:3100'; server\run.bat` and leave it running (API on `http://127.0.0.1:8000`; a fresh `server\auth.db`).
2. In a second PowerShell: `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build`, then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1`. It prints `serving … on http://127.0.0.1:3155/`.
3. Open `http://127.0.0.1:3155/signup/`, sign up with a new e-mail and password. **See:** the dashboard; "member since" shows today's date.
4. Dashboard → API keys → create a key named `laptop`. Copy the key it shows once. **See:** the key in the table, Created = today, Last used = "—".
5. In a third PowerShell: `curl.exe http://127.0.0.1:8000/v1/ping -H "Authorization: Bearer <the key>"`. **See:** `{"ok":true,"time":"…Z"}` (ends in `Z`, no `+00:00`).
6. Reload the API keys page. **See:** Last used = today, in your own local date. In the browser's DevTools → Network, the `keys` answer has `"created_at": "…Z"` and `"last_used_at": "…Z"`, and the `me` answer `"created_at": "…Z"`.
7. Optional, to see the zone at work: DevTools → ⋮ → More tools → Sensors → Location → "Other…", set Timezone ID `Pacific/Pago_Pago` (UTC−11), reload. **See:** before 11:00 UTC the dates move to yesterday; after it they stay today. Set `Pacific/Kiritimati` (UTC+14): before 10:00 UTC they stay today, after it they move to tomorrow.
8. Stop the API and the server (Ctrl+C). To start fresh next time, delete `server\auth.db`.

## Risks / traps

* A response model field added later as plain `datetime` answers zone-less again on SQLite: `test_response_models_use_utc_datetime` fails and names it.
* A dict route that formats a time itself (`isoformat()`) is not covered by the gate: use `licence.clock.rfc3339`. PF14c's probe found only `/v1/ping`.
* Clients comparing time strings: microseconds are kept and the instant is unchanged; only `Z` replaces the missing zone (or the `+03:00` on a non-UTC Postgres session). The site's `parseServerDate` reads every form. The SDKs pass times through as strings. The Android app's generated client (`mobile/android/lib/api/gen/`) parses `date-time` fields with Dart's `DateTime.tryParse`, which reads a zone-less time as the phone's local time and `Z` as UTC, so `Z` is what it needs.
* The Postgres twins (`test_billing_times_are_utc_postgres`, `test_user_and_key_times_are_utc_postgres`) assert the session zone is Asia/Baghdad: with `PGTZ=UTC` set they fail on that precondition, not on a time.
* The whole suite on Postgres takes about 25 minutes per third on this PC under load: split it into three groups on separate databases, and keep each foreground call under the 40-minute limit.

## As-built

* **Date, branch, commits:** 2026-10-12, `ap/t55-pf14c-every-api-time-answered-in` from `master` 6ef7928. `93af6ef` (code and tests), then the commit with this doc and the tracker row.
* **Tests first:** on the unchanged code, 5 of the 7 new tests failed for the four defects: `'2026-11-10T06:47:10.150607' == '…Z'`; the gate named `UserOut.created_at`, `ApiKeyOut.created_at`, `last_used_at`, `revoked_at` (and `ApiKeyCreated`'s three); `/v1/ping` answered `2026-10-12T07:35:02.461152+00:00`; `/licence/link/poll` answered `2026-10-12T07:35:02.603743`; `PatchShareIn` held `+03:00`. The site check passed already (`parseServerDate` appends `Z` to a zone-less time), as did the share API's stored value (the service converted it).
* **Counts:**
  * pytest collected 622 → 629 (+7). The verify gate (lint, build, pytest on SQLite on a built `out/`): green, **612 passed, 17 skipped** (the `postgres`-marked tests), 1,786 s under load.
  * **Postgres 17.10** (a throwaway `initdb` cluster in the session scratchpad, port 55455, `timezone = 'Asia/Baghdad'`, removed afterwards):
    * Baseline on the unchanged code: `test_feed_source_daily_pull` failed (`2026-10-14 05:00 UTC` ≠ `2026-10-13 02:00 UTC + 1 day`) and the Postgres twin failed (`/auth/me` answered `…10:41:26.989102+03:00`).
    * With the fix, the whole suite with the app on Postgres (`TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`, three groups in parallel on separate databases): **558 passed, 71 skipped, 0 failed** of 629. The skips: 69 site build checks (`out/` not built for this run; they read no database), `test_ops.py`'s "the app runs on Postgres in this session" and the SQLite-only parameter of the usage upsert test. **No time-zone failure left.** (The third group ran past the 37-minute call limit with 216 of 236 done and none failed; its last 20 tests, `test_sso.py::test_sso_requests_purge_job` and `test_telemetry.py`, ran again on their own: 20 passed.)
    * `pytest -m postgres` with the app on SQLite and `TEST_DATABASE_URL` only: 17 passed.
* **Dict handlers fixed (Scope 2):**
  1. `app.routers.v1.ping` (`GET /v1/ping`): `time` through `clock.rfc3339(clock.now())` instead of `isoformat()` (`+00:00`).
  2. `app.routers.licence.poll_link` (`POST /licence/link/poll`): `token.user.created_at`, fixed through `UserOut` (the handler dumps `Token` with `mode="json"`).
  No other dict handler returned a `datetime` or a time without `Z` (Status: the probe and the hand-read list).
* **Self-test beyond pytest:** the API under uvicorn on a fresh SQLite database (port 18055), `out/` built against it and served (3155), headless Edge over CDP (no browser package). It signed up, made a key, used it once with `/v1/ping`, then opened Dashboard → API keys with the browser's time zone overridden at 09:22 UTC: in `Pacific/Pago_Pago` Created and Last used read "Oct 11, 2026", in `Pacific/Kiritimati` and UTC "Oct 12, 2026"; the dashboard home's "member since" read "Oct 11, 2026" in Pago Pago. Every API time ended in `Z` (`/auth/register`, `/keys` POST and GET, `/auth/me`, `/v1/ping` `2026-10-12T09:22:48Z`). No page errors. 15 of 15 checks passed.
* **Deviations and why:**
  1. *`UtcDateTime` moved to `server/app/utc.py`.* `UserOut` sits above the billing section of `schemas.py`, where PF2c defined the type, and a class annotation needs the name defined first. A module of its own lets routers' own models (here `PatchShareIn`) use it without importing `schemas`; `schemas.UtcDateTime` is still importable.
  2. *The gate also walks the models in `responses`* (the developer API documents its answers there; its handlers return dicts). They hold times as `str` filled by `rfc3339`, so they pass; a documented `datetime` would fail.
  3. *`PatchShareIn.expires_at`* was already stored in UTC by `shares.change`; the model now converts too, so a second caller of the model cannot store an offset wall time in SQLite.
  4. *`/v1/ping`'s `time` is whole seconds now* (`rfc3339`, like every contract endpoint); its OpenAPI type is a plain `string`, so `openapi/v1.json` and the SDKs do not change.
* **Contract:** none changed. Owner, at merge: nothing to apply in the Unreal repo's `contracts\` (no endpoint or shape change).
* **Carry-over → which feature:** none. Showing the time of day next to the dates on the API keys page would be a copy change (the owner, if wanted).
