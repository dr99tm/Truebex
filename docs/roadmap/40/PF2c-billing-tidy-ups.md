# PF2c — Billing tidy-ups: one Stripe invoice helper, packs named in the history, Stripe pack checkout, billing times in UTC (launch priority 1)

**Needs merged:** PF2 (billing), PF11 (AI credit packs as one-off items); both on `master` 842768e. **Unblocks:** Stripe credit packs with Stripe Tax on; Postgres runs of the billing tests in any session time zone; a gate that fails on a name defined twice. **Contract:** none. No `/billing/*` endpoint is in a contract document. The times now follow the licence contract's rule for new endpoints (`contracts/licence-api.md` §5: "times are RFC 3339 UTC with `Z`").

## Status

**Built (2026-10-11, branch `ap/t36-pf2c-billing-tidy-ups-one-stripe`, Autopilot T36); see As-built.** Four defects that the merges left behind. Each was checked on `master` 842768e before the work began:

| # | Defect | Where (master 842768e) | Then |
|---|---|---|---|
| 1 | `_invoice_subscription` defined twice | `server/app/billing/stripe_provider.py:78` and `:96` | The second definition replaced the first. An empty-string `subscription` no longer fell back to `parent.subscription_details`. |
| 2 | A credit pack named by its plan id | `src/app/dashboard/billing/page.tsx:871` (`cat.tiers.find((t) => t.id === p.plan)?.name ?? p.plan`) | The payment history said `ai_credits` |
| 3 | Stripe one-off checkout without `customer_update` | `stripe_provider.py:228-232` (the subscription checkout has it at `:185-189`) | With `STRIPE_TAX_ENABLED` and a saved customer that has no address, Stripe refuses the session |
| 4 | `test_billing.py::test_wayl_checkout_and_verified_webhook` fails on Postgres in a non-UTC zone | `server/tests/test_billing.py:93`; the billing models in `server/app/schemas.py` used plain `datetime` | The API answered `2026-11-10T09:47:10.150607+03:00` (Postgres, session zone Asia/Baghdad) and the zone-less `2026-11-10T06:47:10.150607` (SQLite). The test then called `.replace(tzinfo=utc)` on the `+03:00` value. |

Sources: PF11 As-built (the T31 merge's "Left as found" and its "Stripe packs" carry-over); the Postgres runs in PF3's and PF4's As-built.

## Goal

The billing code holds one helper for each job, and the gate now fails on a name defined twice. A credit pack bought on the Cloud page shows up in Billing's payment history as "5,000 AI credits · One-off", next to "Pro · Monthly", never as `ai_credits`. A returning Stripe customer can buy a pack with Stripe Tax on. Every billing time the API answers is UTC with `Z`, whether the database is SQLite or Postgres and whatever zone the database session uses.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* As-built of `PF2-…md` (the provider seam, `stripe_provider.py`), `PF2b-…md` (consumer rules and `ONE_OFF_ITEMS`), `PF3a-…md` (organisation payment history), `PF11-…md` (`PAID_HOOKS`, `ONE_OFF_ITEMS`, `ai/topups.py`, the T31 merge notes).
* `server/tests/mock_paddle.py`; the Stripe test helpers `tests/test_billing.py::stripe_post` and the `fake_stripe_subscriptions` fixture in `tests/conftest.py`.
* `contracts/licence-api.md` §5 (time format); PF14's Postgres readiness (`TEST_APP_DATABASE_URL`, `TEST_DATABASE_URL`, the `postgres` marker).
* Skill `truebex-brand-voice` (the history copy).

## Scope

**In:**

1. One `_invoice_subscription` that handles every shape: a string id, an expanded subscription object, `parent.subscription_details.subscription` (newer Stripe API versions, id or expanded), and an empty or missing value as none.
2. One-off items named in the payment history. `PaymentOut` gains the additive keys `item` and `credits`. A feature registers what its item's payments bought in `billing.service.ONE_OFF_DETAILS`; `ai/topups.py` registers `credits` from `ai_top_ups`. The Billing page reads the name from `BILLING.history.items` in `src/lib/constants.ts`.
3. The Stripe one-off checkout passes `customer_update {"address": "auto", "name": "auto"}` when it reuses a saved customer, as the subscription checkout does. Without a saved customer it passes `customer_email`.
4. Billing times in UTC. Every time field of the `/billing/*` response models (`FoundingOut`, `SubscriptionOut`, `ExitOut`, `InvoiceOut`, `PaymentOut`) is the one type `UtcDateTime`, so the API answers RFC 3339 UTC with `Z` whatever the database hands back. The tests compare aware datetimes.
5. A pytest that walks `server/app` (and `server/scripts`) with `ast` and fails when a module defines a top-level function or class twice (`@overload` excepted; methods of top-level classes too). Equivalent duplicates are fixed. There were no others.

**Out (and where it goes):** the QS-17 wording and a confirmation mail for packs (the owner, PF11 carry-over; packs keep the provider's receipt). Times on non-billing endpoints that still answer zone-less (the licence contract's note on "the existing API's zone-less times"): each feature's own follow-up. `parseServerDate` on the site keeps reading both forms.

## Design

**API**

* `GET /billing/payments` (also `?org_id=`), `GET /billing/payments/{reference}` and `POST /billing/payments/{reference}/refresh` answer each payment with two new keys. Both are null for a plan's payment:
  ```json
  {"reference": "tbx_…", "provider": "paddle", "plan": "ai_credits", "amount": 720, "currency": "GBP",
   "status": "paid", "created_at": "2026-10-11T07:20:55.667950Z", "paid_at": "2026-10-11T07:20:56.494334Z",
   "interval": null, "seats": 1, "item": "ai_credits", "credits": 5000, "…": "…"}
  ```
  `item` is the payment's plan when that plan is in `ONE_OFF_ITEMS`. `credits` comes from the pack's `ai_top_ups` row, and is null if that row is missing.
* Every billing time (`current_period_end`, `cooling_off_until`, `withdrawal_until`, `requested_at`, `effective_at`, `issued_at`, `created_at`, `paid_at`, `key_info_at`, the founding offer's `ends_at`) is `UtcDateTime = Annotated[datetime, AfterValidator(_utc)]` in `schemas.py`. A naive value (SQLite) is taken as UTC; an aware one (Postgres in the session's zone) is converted. Pydantic writes UTC with `Z`. Microseconds are kept, so a time read back still equals the stored one.
* Stripe: `create_one_time_checkout` with a saved customer sends `customer` and `customer_update {"address": "auto", "name": "auto"}`; without one it sends `customer_email`.

**Data:** no new table or column. `billing.service.ONE_OFF_DETAILS` sits beside `PAID_HOOKS` and `ONE_OFF_ITEMS`: `item -> fn(db, payments) -> {reference: {field: value}}`, one query per item for the whole history page.

**UI:** `src/app/dashboard/billing/page.tsx` `paymentName()`. A plan's payment shows its tier ("Pro · Monthly", unchanged). A one-off item shows `BILLING.history.items[item].sized` with the credits formatted ("5,000 AI credits"), or `.name` ("AI credits") when the size is unknown, followed by `BILLING.history.once` ("One-off") where a plan shows its interval. An item without its own name shows `BILLING.history.otherItem` ("Purchase"). The `Payment` type in `src/lib/developer.ts` gains `item` and `credits`.

**Jobs / workers:** none.

**Security and privacy:** nothing new is exposed. `credits` is read from the caller's own top-up rows, and only for payments the endpoint already returns. The pack's price and credits still come from the server, never the browser.

## Deliverables

- [x] `server/app/billing/stripe_provider.py`: one `_invoice_subscription`; `customer_update` in `create_one_time_checkout`
- [x] `server/app/billing/service.py`: `ONE_OFF_DETAILS`, `one_off_details()`
- [x] `server/app/ai/topups.py`: `details()` registered for `ai_credits`
- [x] `server/app/routers/billing.py`: `_payments_out()` for the history, the detail and the refresh
- [x] `server/app/schemas.py`: `UtcDateTime` on every billing time; `PaymentOut.item`, `PaymentOut.credits`
- [x] `src/lib/constants.ts` `BILLING.history.items`, `.otherItem`, `.once`; `src/lib/developer.ts` `Payment`; `src/app/dashboard/billing/page.tsx`
- [x] `server/tests/test_pf2c_billing_tidy.py` (7 tests, one Postgres-marked); a build check in `server/tests/test_site_pf2.py`; aware comparisons in `test_billing.py` and `test_billing_pf2.py`
- [x] This doc and the PF2c row in `docs/roadmap/40/README.md`

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_invoice_subscription_shapes` | pytest | a string id, an expanded object (a dict and the SDK's `StripeObject`), `parent.subscription_details` (id or expanded), an empty top-level value falling back to the parent; an empty invoice, a `subscription` of `None`, `""`, `{}` or `{"id": ""}`, a `quote_details` parent → none |
| `test_no_duplicate_top_level_defs` | pytest | the checker catches `def a` twice and a method twice and lets `@overload` stubs pass; no module under `server/app` or `server/scripts` defines a name twice |
| `test_payments_name_one_off_items` | pytest | after Pro and a 5000-credit pack on the Paddle mock: the pack's row has `item` `ai_credits` and `credits` 5000 (pending and paid; history, detail and refresh), and the Pro row is unchanged (`pro`, `month`, `item` and `credits` null) |
| `test_payments_one_off_item_without_details` | pytest | a pack whose top-up row is gone, and an item with no details hook: `item` set, `credits` null |
| `test_stripe_one_time_checkout_updates_saved_customer` | pytest | with `STRIPE_TAX_ENABLED`: no saved customer → `customer_email`, no `customer` or `customer_update`; a saved customer → `customer` plus `customer_update {"address": "auto", "name": "auto"}`, no `customer_email`, `automatic_tax` on |
| `test_billing_times_are_utc` | pytest | the billing models' time fields are exactly the ten listed above, and each writes `…Z` from a naive, a `+03:00` and a UTC value; through the API on SQLite, `current_period_end`, `created_at`, `paid_at`, the cancel's `requested_at` and `effective_at` end in `Z` and compare as aware times |
| `test_billing_times_are_utc_postgres` | pytest, `postgres` | with `TEST_DATABASE_URL` and the session at `TimeZone=Asia/Baghdad`: a stored period end reads back `+03:00`, and the API answers it, and the payment's times, in `Z` as the same instant |
| `test_site_pf2c_billing_history_names_credit_packs` | build check | the Billing page's chunks carry `{credits} AI credits` and `One-off`; the page uses `BILLING.history.items`, and the plan-id fallback is gone |
| `test_wayl_checkout_and_verified_webhook`, `test_billing_paddle_subscription_lifecycle` | pytest (changed) | `current_period_end` ends in `Z`, and is compared to now as an aware time |

## Human test

Local stack: the Paddle mock, the API on :8000, and the site built against it. Use an `@example.com` address and the password `password123`.

1. In `server\.env` (`server\run.bat` copies `.env.example` there on first run), set: a long `SECRET_KEY`; `BILLING_PROVIDER=paddle`; `PADDLE_API_KEY=pdl_sdbx_local`; `PADDLE_WEBHOOK_SECRET=pdl_ntfset_mock_secret`; `PADDLE_CLIENT_TOKEN=local`; `PADDLE_API_BASE=http://127.0.0.1:8098`; `SITE_URL=http://127.0.0.1:3136`; `http://127.0.0.1:3136` added to `CORS_ORIGINS`; `MAIL_BACKEND=console`.
2. Terminal 1, in `server\`: `.venv\Scripts\python.exe -m uvicorn tests.mock_paddle:app --port 8098`. Terminal 2: `server\run.bat`. Terminal 3, in `server\`: `.venv\Scripts\python.exe -m scripts.sync_prices --provider paddle --env sandbox` → "24 prices, 24 new". Then, in the worktree: `Remove-Item -Recurse -Force out; $env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; npm run build`, then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → "serving … on http://127.0.0.1:3136/".
3. Open `http://127.0.0.1:3136/signup/` and sign up as `pack@example.com`. Go to Dashboard → Billing. Pro and Monthly are selected. Tick the consent box, then click **Continue to payment** → the mock pay page lists the Pro price. Click **Pay with a test card** → back on Billing: "Payment received — your plan is active.", and the current plan is Pro.
4. Dashboard → Cloud, AI credits section: choose **5,000 credits**, tick "I want the credits added now…", then click **Buy credits** → the mock pay page → **Pay with a test card** → back on Cloud: "Credits added.", and Bought credits left shows 5,000.
5. Dashboard → Billing → **Payment history** has two rows:
   * Top: "**5,000 AI credits** · One-off", Card, £7.20 (US$9.00 in a US-English browser: the price plus the mock's 20 % VAT), Paid.
   * Below: "**Pro** · Monthly", Card, £28.80, Paid.

   No row says `ai_credits`.
6. Optional: open DevTools → Network, then reload Billing and open the `payments` response. The pack shows `"item": "ai_credits"` and `"credits": 5000`; the Pro row shows `"item": null`. Every `created_at` and `paid_at` ends in `Z`. In the `subscription` response, `current_period_end` ends in `Z` too.
7. Close the three terminals. To start fresh next time, delete `server\auth.db`.

## Risks / traps

* `UtcDateTime` is a validator. A billing time added later as plain `datetime` would answer zone-less again, so `test_billing_times_are_utc` lists the ten fields exactly, and a new field fails it until it gets the type.
* Changing a time's wire form can break clients that compare strings. The site's `parseServerDate` reads `Z`, offsets and zone-less times alike. No `openapi/*.json` export (PF10, PF12) includes `/billing/*`. Microseconds are kept, so tests that compare a parsed time to the stored one still match.
* The duplicate-definition gate looks only at the module level and at the bodies of top-level classes. A name defined twice inside an `if` or `try` block (a legitimate fallback) is not flagged. `@x.setter`, `@x.register` and `@overload` are exempt.
* `customer_update` needs a saved customer. Stripe refuses it with `customer_email`, so it is sent only alongside `customer`.
* Never run `next dev` here (RAM). The human test's build bakes the local API into `out/`. The verify gate rebuilds against `.env.local`.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t36-pf2c-billing-tidy-ups-one-stripe` from `master` 842768e. `26caf1b` (code, tests, site), then the commit with this doc and the tracker row.
* **Counts:** pytest collected 549 → 557 (`test_pf2c_billing_tidy.py` 7, one of them Postgres-only; `test_site_pf2.py` +1). `scripts/autopilot-verify.ps1` green: lint, build, pytest 551 passed and 6 Postgres-only skips. No new route in `out/`.
* **Tests first:** the six SQLite tests failed on the unchanged code for the four defects (an empty top-level `subscription` returned none; the gate named `app/billing/stripe_provider.py:78/96 _invoice_subscription`; no `item` key; no `customer_update`; `2026-11-10T06:47:10.150607` without `Z`). With `UtcDateTime` reverted, both UTC tests failed again, on SQLite and on Postgres.
* **Postgres (a local Postgres 17 is installed here):** a throwaway cluster made with `initdb` in the session scratchpad (port 55436, `timezone = 'Asia/Baghdad'`, removed afterwards), run with `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`.
  * On the unchanged code, `test_billing.py`: `test_wayl_checkout_and_verified_webhook` failed (`current_period_end` answered `…09:47:10.150607+03:00`). The billing set (`test_billing*.py`, `test_ai_topup_billing.py`, `test_ai_credits.py`, 83 tests) also failed `test_billing_pf2b.py::test_eu_withdrawal_flow`: the withdrawal's `requested_at` came back `+03:00`, so its `%H:%M` did not match the mail's correct UTC time. That second failure had not been reported before.
  * After the fix, the billing set plus `test_pf2c_billing_tidy.py` gave 90 passed, the Postgres twin included.
  * The whole suite on that Postgres, in the Baghdad zone: 554 passed, 1 skipped by design (`test_ops.py`, "the app runs on Postgres in this session") and 2 failed, neither of them billing:
    * `test_supplier_feeds.py::test_feed_source_daily_pull` (PF8) has the same test-side `next_pull_at.replace(tzinfo=utc)` on a `+03:00` value. It passes with `PGTZ=UTC`.
    * `test_market.py::test_search_filters_and_region_prices` (PF7): `search(q="linen")` with no region finds nothing. It fails with `PGTZ=UTC` too, so it is not a time-zone fault. It may come from this cluster's `--locale=C` or from Postgres's case-sensitive `LIKE`. This branch does not touch the market code.

    Both are left for their features (carry-over below).
* **Self-test beyond pytest:** an end-to-end run in headless Edge over CDP, against real processes: `tests/mock_paddle.py` (sending signed webhooks), the API under uvicorn on a fresh SQLite database (`sync_prices`: 24 prices), and `out/` built against that API and served. The run signed up, bought Pro monthly on the mock's pay page, then bought a 5,000-credit pack from the Cloud page ("Credits added."). In Billing's payment history the rows read "5,000 AI credits · One-off · Card · US$9.00 · Paid" and "Pro · Monthly · Card · US$34.80 · Paid", and no row said `ai_credits`. The API answered `item` and `credits` for the pack and null for Pro, and every time ended in `Z`. There were no JS errors. 16 of 16 checks passed. The only 404s were Next's RSC prefetch files (`__next.*.txt`), which the plain static server does not serve; they predate this task.
* **Deviations and why:**
  1. *`item` and `credits`, both.* `item` lets the page name any one-off item without knowing plan ids; `credits` is the pack's size. A feature that sells another item registers its own fields in `ONE_OFF_DETAILS`. The page falls back to "Purchase" until `BILLING.history.items` has its name.
  2. *The serialisation fix covers every billing response model,* not only `current_period_end`. On Postgres, `ExitOut.requested_at` had the same fault (the EU withdrawal test above), and the task asked for one place for every billing time.
  3. *The duplicate gate also walks `server/scripts` and the methods of top-level classes.* Both were clean, and a method defined twice is the same bug.
  4. *`test_billing_pf2.py::test_billing_paddle_subscription_lifecycle`* had the same `.replace(tzinfo=utc)`. It passed on Postgres only because its window is five days wide, so it now compares aware times too.
* **Duplicates left in place:** none. Under `server/app` and `server/scripts` the only one was `_invoice_subscription`.
* **Contract:** none to update (no `/billing/*` row in any contract document).
* **Noted, not changed:** `npm run sync:roadmap -- <app tracker> docs/roadmap/40/README.md --check` reports `exchange: planned -> in_progress` and `developers: planned -> shipped` on `master` as well. The owner runs `sync:roadmap` at deploy (PF14a), and the `PF2c` id is not a roadmap item (the script reads `[A-Z]{2}\d{1,2}` ids only, like PF2a and PF2b).
* **Carry-over → which feature:** PF8: `test_feed_source_daily_pull` should compare aware times (Postgres outside UTC). PF7: `test_search_filters_and_region_prices` on Postgres (a text query without a region). QS-17 wording and a pack's own confirmation mail → the owner (PF11 carry-over, unchanged). Zone-less times outside billing (`UserOut`, `ApiKeyOut` and the other pre-contract models) → each feature's own follow-up; `UtcDateTime` is ready to reuse.
