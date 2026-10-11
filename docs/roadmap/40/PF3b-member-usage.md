# PF3b — Member usage: cloud storage, panoramas and AI credits filled in (launch priority 3)

**Needs merged:** PF3, PF4, PF6, PF11 (all on `master` at 842768e). **Unblocks:** nothing waits on it; an
organisation-owned usage view follows `project-log.md`'s organisation projects. **Contract:** none
(`/orgs/{id}/usage` is a platform route; same keys, no contract change).

## Status

**Done 2026-10-11** on `ap/t40-pf3b-member-usage-cloud-storage` (Autopilot T40): the whole Scope: In, every
test of the Tests table, verify gate green. See As-built. Before this task, on `master` 842768e (verified with
Grep on 2026-10-11):

| Area | Where (master 842768e) | Before |
|---|---|---|
| The three columns | `server/app/orgs/usage.py:34-44` (`_metering`), `:92-94` | called `metering.used(subject, metric, month)`, which `server/app/metering.py` never had (it has `record`, `total`, `by_metric`, `daily`, `subjects`); the `AttributeError` was swallowed, so `storage_bytes`, `panoramas` and `ai_credits` were always `null` |
| Cloud storage | `server/app/projects/quotas.py:79-87` (`bytes_used`) | PF4's figure for the `cloud_bytes` quota: the snapshot blobs and offloaded deltas of the projects a person owns |
| Panoramas | `server/app/render/models.py:24-84` (`render_jobs`) | PF6's queue: `account_kind`, `account_id`, `kind`, `state`, `finished_at` |
| AI credits | `server/app/ai/models.py:49-67` (`ai_credit_ledger`) | PF11's append-only ledger: `usage` rows carry a negative delta, `refund` rows give credits back |
| Site | `src/app/dashboard/organisation/usage/page.tsx:42`, `:90-92` | "Cloud storage, panoramas and AI credits appear here once those services start counting them."; storage as decimal GB with two places; copy inline, not in `constants.ts` |

What the owner meant: PF3 Scope 9 ("columns for cloud storage, panoramas and AI credits filled from `metering`
once PF4, PF6 and PF11 record them") and PF3's As-built carry-over ("Storage, panoramas and AI-credit columns →
PF4, PF6, PF11 via `metering`"). All three merged; none filled them.

## Goal

An organisation's owner or admin opens Dashboard → Organisation → Member usage and sees, for each member, the
cloud storage their projects hold, the panoramas they rendered and the AI credits they spent in the month, next
to the devices, last activity, API requests and floating-seat hours PF3 already shows. Earlier months keep their
panoramas and credits; storage, a level with no history, shows only for the current month.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* As-built of `PF3-organisations-seats-and-sso.md` (deviation 13, carry-over), `PF4-…` (deviation 7: what
  `cloud_bytes` counts), `PF6-…` (deviation 8: followed sets and `tiles` updates), `PF11-…` (deviation 5: the
  ledger).
* Code: `server/app/orgs/usage.py`, `server/app/projects/quotas.py`, `server/app/render/models.py`,
  `server/app/ai/models.py`, `server/app/ai/credits.py`, `src/app/dashboard/organisation/usage/page.tsx`.
* Skills: `truebex-brand-voice` (the page's copy).

## Scope

**In:**
1. Replace `_metering()` with reads from the features' own data, per member, for the month asked
   (`?month=YYYY-MM`, the same UTC bounds as the other columns):
   * `storage_bytes`: the member's current `bytes_used` when the month asked is the current month; `null` for
     any other month (storage is a level and no history of it is kept).
   * `panoramas`: the member's `panorama` jobs that reached `succeeded` in the month (by `finished_at`).
     **Rule:** a followed set's `tiles` updates do not count: they refresh a panorama already counted. A
     followed panorama's first job is a `panorama` job and counts once. Failed, cancelled, expired and
     unfinished jobs do not count; neither do `pack` and analysis jobs.
   * `ai_credits`: credits spent in the month, as a positive number: the member's `usage` rows minus their
     `refund` rows (never below 0). Grants, expiries, top-ups and admin adjustments do not count.
   One grouped query per column for all members, never one query per member.
2. Each member's own account figures, like the API requests column: no organisation pooling, no
   `projects.org_id`, no `account_kind` "org" (organisation-owned projects wait for `project-log.md`).
3. Site: the usage page formats the three columns (storage in MB / GB, panoramas as a count, credits with
   thousands separators), drops "appear here once…" and says storage is shown for the current month only. Copy
   in `constants.ts` (`MEMBER_USAGE`), written with the brand-voice skill.
4. `/orgs/{id}/usage` keeps its keys; the owner / admin-only rule is unchanged.
5. `server/scripts/seed_member_usage.py --email <member>` for the human test: imports `app` before SQLAlchemy
   (PF14a's rule, in `test_fresh_process_never_queries_wmi`) and writes through each feature's own models.

**Out (and where it goes):**
* Organisation-owned projects, panoramas and credits (`account_kind` "org", `projects.org_id`) →
  `project-log.md`'s organisation projects (PF4 / PF3 follow-up), then a pooled row on this tab.
* Storage history per month (a daily level in `meter_daily`) → not planned; add it if an owner asks for past
  months' storage.
* A refund writer: no code writes `refund` ledger rows yet (PF11 names the kind); this tab already subtracts
  them.

## Design

### API

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/orgs/{id}/usage?month=2026-10` | owner or admin (session) | — | unchanged keys: `[{user_id, email, name, role, devices, last_active_at, api_requests, floating_hours, storage_bytes, panoramas, ai_credits}]` |

`storage_bytes` is an integer (bytes) for the current UTC month and `null` otherwise; `panoramas` and
`ai_credits` are integers, `0` when the member has none. 401 without a session, 404 outside the organisation,
403 `forbidden` for billing and member roles, 422 `validation_failed` for a malformed month (all PF3's).

### Data

No table or migration. Three grouped reads (`server/app/orgs/usage.py`):

* `projects.quotas.bytes_used_by(db, ids)`: `SUM(projects.bytes) … WHERE owner_user_id IN ids AND deleted_at
  IS NULL GROUP BY owner_user_id`, the same filter as `bytes_used` (the `cloud_bytes` quota).
* `usage.panoramas(db, ids, m_start, m_end)`: `COUNT(*) FROM render_jobs WHERE account_kind = 'user' AND
  account_id IN ids AND kind = 'panorama' AND state = 'succeeded' AND finished_at BETWEEN … GROUP BY
  account_id`.
* `usage.ai_credits(db, ids, m_start, m_end)`: `-SUM(delta) FROM ai_credit_ledger WHERE account_kind = 'user'
  AND account_id IN ids AND kind IN ('usage', 'refund') AND at BETWEEN … GROUP BY account_id`, floored at 0.

`usage.window(month)` gives the month's first and last instant in UTC, the bounds every column uses.

### UI

`src/app/dashboard/organisation/usage/page.tsx` reads `MEMBER_USAGE` (title, description, month label, column
names, three notes under the table, the storage cell's tooltip for earlier months). `src/lib/memberUsage.ts`:
`formatStorage` (1 024-based as the Projects page; MB below 1 GB, GB from there; one decimal under 10;
thousands separators; "< 0.1 MB" for a few bytes; "—" for `null`) and `formatCount` (en-GB thousands
separators) for API requests, panoramas and credits. The page stays `noindex` (dashboard layout) and out of the
sitemap.

### Jobs / workers

None.

### Security and privacy

Unchanged: only owners and admins of the organisation see the tab; figures are counts and sizes, never project
names, prompts or file contents.

## Deliverables

- [x] `server/app/orgs/usage.py`: `window`, `panoramas`, `ai_credits`; `_metering` removed.
- [x] `server/app/projects/quotas.py`: `bytes_used_by`.
- [x] `server/scripts/seed_member_usage.py`.
- [x] `src/lib/memberUsage.ts`, `src/lib/constants.ts` `MEMBER_USAGE` (at the end), the usage page.
- [x] Tests: `server/tests/test_orgs_usage.py`, `server/tests/test_site_pf3b.py`; `test_orgs.py` and
      `test_ops.py` updated.
- [x] README section "Member usage (PF3b)" (at the end); tracker row PF3b.

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_orgs_usage_storage_panoramas_ai_credits` | pytest | a member with two live projects (152 500 000 bytes; a deleted one not counted), two succeeded panoramas this month (one finished in the month's first second after being queued the month before, one followed), one failed, one running, a `tiles` update, a pack, one succeeded last month and an `org` account's job; AI rows 900 + 400 used, 50 refunded, plus grant, top-up, adjust, expire and an `org` row → exactly (152 500 000, 2, 1250); the owner (1 000, 0, 0); `?month=` this month gives the same; storage equals `quotas.bytes_used`; the keys are unchanged |
| `test_orgs_usage_earlier_month_storage_null` | pytest | last month: (null, 1, 280) for that member (300 used in its last second, 20 refunded), (null, 0, 0) for the others; 2020-01 storage null |
| `test_orgs_usage_no_usage_is_zero` | pytest | a member with nothing gets (0, 0, 0), not null |
| `test_orgs_usage_plain_member_forbidden` | pytest | 403 `forbidden` for plain members (this month and last), 401 without a session, 422 for `2026-1` |
| `test_orgs_usage_one_query_per_column` | pytest | one request for three members runs exactly one statement on `projects`, one on `render_jobs` and one on `ai_credit_ledger` |
| `test_seed_member_usage_script` | pytest | the seed's answer and the endpoint agree (268 435 456, 2, 1250); another member stays (0, 0, 0); last month (null, 0, 0); the balance stays ≥ 0 with two `ai_usage` turns; an unknown address exits naming it |
| `test_fresh_process_never_queries_wmi` (updated) | pytest | `seed_member_usage.py` loaded as `python scripts\…` does reaches no WMI query |
| `test_orgs_usage_per_member` (updated) | pytest | PF3's test: the three columns are 0 for members with nothing (were `null`) |
| `test_site_pf3b_usage_page_source_drops_old_note` | build check | the page source has no "appear here once…" and reads `MEMBER_USAGE` / `formatStorage` |
| `test_site_pf3b_usage_page_drops_old_note` | build check | `out/` (HTML and chunks) has no "appear here once those services start counting them" and carries the current-month-only and panorama notes |
| `test_site_pf3b_formats_usage_columns` | build check | `memberUsage.ts` under the project's TypeScript: 256 MiB → "256 MB", 0 → "0 MB", null → "—", 300 B → "< 0.1 MB", 1.5 GiB → "1.5 GB", 2 048 GiB → "2,048 GB", 1250 → "1,250" |

## Human test

On the served `out/` built against a local API (port 8000):

1. In `server\.env` (`run.bat` copies it from `.env.example` on first run) set
   `SITE_URL=http://127.0.0.1:3140` and add `http://127.0.0.1:3140` to `CORS_ORIGINS`; start the API with
   `server\run.bat` (port 8000). In the worktree: `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run
   build`, then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` and open
   `http://127.0.0.1:3140/`.
2. Sign up as `owner@example.com`; Dashboard → Organisation → type "Studio North" → Create. Invites → invite
   `member@example.com` and `idle@example.com` (role Member, No seat). Each invitation link prints in the API
   console; open it in a private window, sign up with that address and accept. → Members lists three people.
3. In `server\`: `.venv\Scripts\python.exe scripts\seed_member_usage.py --email member@example.com` → prints
   "member@example.com this month: storage 268435456 bytes, 2 panoramas, 1250 AI credits".
4. As the owner, Organisation → Member usage. → member@example.com: Cloud storage **256 MB**, Panoramas **2**,
   AI credits **1,250**; idle@example.com and owner@example.com: **0 MB**, **0**, **0**. Under the table: "Cloud
   storage is what the member's own projects hold now, so it is shown for the current month only." No "appear
   here once…".
5. Month → the previous month. → Cloud storage **—** for everyone (hover: "Shown for the current month only");
   Panoramas and AI credits **0**.
6. Signed in as `member@example.com` (the private window), the navigation has no Member usage, and
   `/dashboard/organisation/usage/` says "Only an owner or admin of Studio North can open this page." (the API
   answers 403).

## Risks / traps

* **SQLite datetimes:** `finished_at` and `at` come back naive; every value stored is UTC and the bounds are
  UTC, so comparisons hold on SQLite and on Postgres (`timestamptz`).
* **Storage is a level:** there is no history of it, so an earlier month shows "—", never 0.
* **Seeded projects** have no snapshot, so PF4's prune and recount never touch their `bytes` (they would
  recount to 0 only after a real snapshot upload).
* Never run `next dev` (RAM); the verify gate rebuilds `out/` against `.env.local`'s API, so rebuild with
  `NEXT_PUBLIC_AUTH_URL` before a click-through.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t40-pf3b-member-usage-cloud-storage` from `master` 0e3b88a
  (842768e plus the setup fix): `af9b393` (tests first), `3aced05` (server and the seed script), `eb1cdc4`
  (site), then the docs commit ticking this row.
* **Counts:** pytest 549 → 558 collected; the verify gate: 553 passed, 5 skipped (the Postgres-marked tests).
  New: `tests/test_orgs_usage.py` 6, `tests/test_site_pf3b.py` 3; `test_orgs.py::test_orgs_usage_per_member`
  now expects 0 for members with nothing, `test_ops.py::test_fresh_process_never_queries_wmi` loads the seed
  script. **Live run:** uvicorn on a scratch SQLite (port 8140), `out/` built against it and served on 3140; an
  owner, "Studio North" and two members invited and accepted over HTTP (invite links from the API console);
  `seed_member_usage.py --email member@example.com` as its own process printed 268435456 bytes, 2 panoramas,
  1250 credits; headless Edge over CDP on `/dashboard/organisation/usage/` showed 256 MB / 2 / 1,250 for the
  member and 0 MB / 0 / 0 for the other two, the three notes, no old note and no browser errors; the month
  picker on September 2026 showed "—" for storage (tooltip "Shown for the current month only") and 0 / 0. A
  plain member got 403 from the API; the member's own `/jobs/usage` showed the seeded 0.4 cu.
* **Deviations from Design and why:**
  1. *Storage only for the current month, not for later months either:* a future month has no level to show,
     so it is `null` like an earlier one.
  2. *Credits never below 0:* a refund in one month for a turn of the month before could make the month's net
     negative; the column shows spending, so it floors at 0. No code writes `refund` rows today.
  3. *`bytes_used_by` lives beside `bytes_used`* in `projects/quotas.py` (one short function), so the column
     and the `cloud_bytes` quota share one definition; a test checks they agree.
  4. *API requests now read "1,234"* through `formatCount` (en-GB) rather than the browser's locale, the same
     rule as the new columns.
  5. *The seed writes through the services where they exist:* PF11's `credits.ensure` / `spend` (plus an
     `adjust` top-up when the balance is short, so it never ends below zero) and `ai_usage` turns; PF6's
     `metering.record` for each job's 0.2 cu, so the member's Cloud page agrees. Each run adds to what is there.
* **Contract rows:** none (a platform route).
* **Carry-over → which feature:** organisation-owned figures (`account_kind` "org", `projects.org_id`) →
  `project-log.md`'s organisation projects, then a pooled row here. A `refund` ledger writer → PF11 (this tab
  already subtracts refunds). PF3's carry-over "Storage, panoramas and AI-credit columns → PF4, PF6, PF11 via
  `metering`" is done here, without `metering` (the figures live in the features' own tables).
