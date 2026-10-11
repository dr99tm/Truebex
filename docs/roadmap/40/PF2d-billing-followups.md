# PF2d — Billing follow-ups: a paid Paddle checkout always gets its subscription; the supplier listing checkout returns to the portal (launch priority 2)

**Needs merged:** PF2 (billing), PF3a (organisation billing, `_attach_from_transaction`), PF8 (supplier portal, the listing checkout); all on `master` 842768e. PF2c (T36) is this branch's base: it edits `stripe_provider.py` and the billing page. **Unblocks:** a listing fee set by GD7 (one line in `server/app/market/listing_plans.json`, plus the synced price, see Carry-over); dropping a Paddle webhook by hand in a local trial. **Contract:** none. No `/billing/*` or `/supplier/*` portal endpoint is in a contract document, no endpoint is added, and no switch is added.

## Status

**Built (2026-10-11, branch `ap/t42-pf2d-billing-follow-ups-a-paid-p`, Autopilot T42); see As-built.** These are two carry-overs nobody picked up. Each gap was checked on the base `b3e4f3c` (`master` 842768e + PF2c) before the work began:

| # | Gap | Where (base b3e4f3c) | Then |
|---|---|---|---|
| 1 | A personal Paddle checkout paid without its `subscription.created` | `server/app/billing/paddle_provider.py:339` (`_attach_from_transaction`: `if not payment.organisation_id or not sub_id: return`) | `transaction.completed` marked the payment paid and fetched nothing. The buyer had paid and had no plan. |
| 2 | The return page could not repair it | `server/app/routers/billing.py:558` (`if payment.status == "pending":`) | Once `transaction.completed` had marked the payment paid, the refresh did nothing, even when the buyer did reach the return page. |
| 3 | The reconcile could not repair it | `server/app/billing/jobs.py:63` (`Payment.status == "pending"`) | Only pending payments and subscriptions already stored were re-fetched. |
| 4 | A listing plan's Stripe checkout returned to the wrong page | `server/app/billing/stripe_provider.py:154-155` | `success_url` and `cancel_url` went to `/dashboard/billing/` for every checkout, a `lst_` one included. |
| 5 | The portal ignored the return | `src/app/supplier/billing/page.tsx:21` | The page read only `?connect=done`. It never read `checkout` or `ref`, and never called the refresh. |

Sources: PF3a As-built, carry-over to PF2 ("the personal flow's lost-`subscription.created` gap (deviation 2) could reuse `_attach_from_transaction` for every checkout"); PF8 As-built, deviation 2 ("PF2's Stripe `create_checkout` returns to `/dashboard/billing/`; a `/supplier/billing/` return is a small PF2 follow-up"). Stripe never had gap 1: `checkout.session.completed` retrieves the subscription (`_apply_session`).

## Goal

Someone who pays for Pro on Paddle gets Pro, whichever webhooks arrive and whether or not they wait for the return page. If `subscription.created` never comes and they close the tab, `transaction.completed` alone starts the plan. If both webhooks are lost, the daily reconcile starts it. When GD7 sets a listing fee, a supplier who pays for a listing plan comes back to the supplier portal's Plan and billing page. The page confirms the payment there and shows the plan they now have.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4 (P.3 item 3: a plan changes only from an event the server verified).
* As-built of `PF2-…md` (the provider seam), `PF2b-…md` (`ONE_OFF_ITEMS`, the consumer rules), `PF3a-…md` (deviation 2 and the PF2 carry-over: `_attach_from_transaction`, held-back events, `org_billing.owner_of`), `PF8-…md` (deviation 2: `supplier/listing.py`, `listing.sync`, `LISTING_TIER_PREFIX`) and `PF2c-…md` (`stripe_provider.py`, the billing page).
* Code: `server/app/billing/{paddle_provider,stripe_provider,service,jobs}.py`, `server/app/routers/billing.py` (`refresh_payment`), `server/app/supplier/listing.py`, `src/app/supplier/billing/page.tsx`, `src/lib/developer.ts` (`refreshPayment`), `server/tests/mock_paddle.py`.
* Skill `truebex-brand-voice` (the portal's return copy).

## Scope

**In:**

1. Paddle: when a subscription checkout (personal or organisation) is paid and its subscription is not stored yet, `transaction.completed` fetches the subscription from Paddle, with the payment as its verified origin, as PF3a already did for organisations. One-off items such as AI credit packs have no subscription and fetch nothing. A fetch error is logged, and `subscription.created`, the return-page refresh or the reconcile still follow. The reconcile also catches the case: a payment paid within its window whose `provider_subscription_id` names no stored subscription is re-verified, which fetches the subscription. Either event order gives exactly one subscription row.
2. Stripe listing checkout: a `listing_*` payment's success and cancel URLs go to `/supplier/billing/?checkout=success|canceled&ref=…`. The supplier billing page reads them, calls the existing `POST /billing/payments/{reference}/refresh`, and shows the plan's state. Personal and organisation checkout URLs are unchanged.
3. No contract change, no new switch.

**Out (and where it goes):**

* Listing fees and syncing their prices → GD7 and the owner. `scripts/sync_prices.py` has no `listing_<plan>` targets yet (see Carry-over).
* The consumer order confirmation for a listing payment → PF2b (see Carry-over).
* A real Stripe click-through of the listing return → the owner, once a fee exists. Until then it is covered by pytest, plus a headless run on seeded rows (As-built).

## Design

**API** (no new endpoint, no new field)

* Paddle `transaction.completed` (and `transaction.paid`) of one of our checkouts, once paid: `_attach_from_transaction(db, payment, subscription_id)` runs for every checkout. It fetches `GET /subscriptions/{id}` and applies it with `origin=payment` when `_unattached(db, payment, sub_id)` is true, which means:
  * the transaction names a subscription;
  * the payment is not a one-off item (`service.ONE_OFF_ITEMS`);
  * and the subscription is not stored, or (an organisation checkout) is stored without its organisation, PF3a's case.

  A `ProviderError` is logged (`paddle subscription <id> of <reference> not fetched`). The webhook still answers 200 and is recorded `applied`.
* `PaddleProvider.verify_payment` (the refresh and the reconcile): it applies our transaction as before. It then fetches the subscription only when `_unattached` is still true (the fetch while applying failed), and that error goes to the caller. A subscription already stored is not fetched a second time; the reconcile re-fetches every stored subscription daily anyway.
* `POST /billing/payments/{reference}/refresh` re-verifies a payment that is `pending` (as before) or one where `service.awaits_subscription(db, payment)` is true: a paid payment with a `provider_subscription_id` that names no stored subscription.
* Stripe `create_checkout`: when `payment.plan` starts with `listing_` (`service.LISTING_TIER_PREFIX`), it sends `success_url` `{SITE_URL}/supplier/billing/?checkout=success&ref=lst_…` and `cancel_url` `…?checkout=canceled&ref=lst_…`. Every other checkout keeps `/dashboard/billing/?checkout=…&ref=…`, and organisations keep `&org=<id>`.
* `GET /supplier/listing` (and the listing returned by `POST /supplier/listing`) first syncs that supplier's own `listing_subscriptions` rows from PF2's `subscriptions` (`listing.sync(db, now, supplier_id)`). A plan paid a moment ago is then the current plan on the page at once, not after the 10-minute `supplier.listing.sync` job.

**Data:** no new table or column. Two fixes to `service.upsert_subscription` that the listing flow needs:

* A `listing_*` tier is stored as itself. Before, `tier if tier in PLANS else "pro"` stored a listing subscription as `pro`. The supplier owner would have got Pro, and `listing.sync`, which looks for `listing_<plan>`, never found it.
* A live listing subscription no longer ends its buyer's app trial, as an organisation's subscription does not.

**UI:** `src/app/supplier/billing/page.tsx`, inside its existing `Suspense`, reads `checkout` and `ref`:

* `canceled`: the note "Checkout was cancelled — you haven't been charged. Your listing plan is unchanged."
* `success`: "Confirming your payment…". It calls `refreshPayment(ref)` up to three times (3 s, then 6 s apart, while the payment is pending), then reloads the listing. Then:
  * paid, and the paid plan is now the current plan: "Payment received. {plan} is your listing plan." The plan's card also carries "Current plan".
  * paid, but the listing has not caught up: "Payment received. Your new listing plan shows here once the provider confirms the subscription."
  * cancelled: the cancelled note.
  * still pending: "Payment is still processing. …".
  * an error: "We couldn't confirm the payment yet. …".

Copy: `SUPPLIER_CHECKOUT` (a new export at the end of `src/lib/constants.ts`). It does not name a provider ("once the provider confirms it", as Billing's notices say).

**Jobs / workers:** `billing.reconcile` (daily) passes each enabled provider's checkouts paid within `RECONCILE_WINDOW` (48 h) whose `provider_subscription_id` has no stored subscription, through a correlated `NOT EXISTS`, to `adapter.reconcile` with the pending ones. Paddle and Stripe re-verify each through `verify_payment`. Wayl payments never carry a subscription id.

**Security and privacy:** the subscription is still applied only from Paddle's own API, fetched for our own transaction (the payment row matched by `provider_ref`), so `custom_data` still names only the account. A one-off item never fetches anything. The refresh still answers only the payment's own buyer (404 to anyone else). The portal page shows only what that refresh and the owner-only `GET /supplier/listing` return.

## Deliverables

- [x] `server/app/billing/paddle_provider.py`: `_unattached()`; `_attach_from_transaction` for every checkout; `verify_payment` fetches only what is still missing
- [x] `server/app/billing/service.py`: `awaits_subscription()`; `upsert_subscription` keeps `listing_*` tiers and leaves trials alone for them
- [x] `server/app/billing/jobs.py`: the reconcile's paid-without-subscription payments; `base.py` docstring
- [x] `server/app/routers/billing.py`: the refresh re-verifies `awaits_subscription` payments
- [x] `server/app/billing/stripe_provider.py`: the `/supplier/billing/` return for `listing_*`
- [x] `server/app/supplier/listing.py`: `sync(…, supplier_id=None)`, run by `overview()`
- [x] `src/app/supplier/billing/page.tsx`, `SUPPLIER_CHECKOUT` in `src/lib/constants.ts`
- [x] `server/tests/mock_paddle.py`: `MOCK_PADDLE_DROP`, `MOCK_PADDLE_NO_RETURN` (`drop_list`, `DROP`, `RETURN`, `STATE["dropped"]`)
- [x] `server/tests/test_pf2d_billing_followups.py` (10 tests, 11 with the parametrised order)
- [x] This doc, the PF2d row in `docs/roadmap/40/README.md`, a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_paddle_personal_plan_live_from_transaction_completed_alone` | pytest | mock Paddle, personal Pro, `subscription.created` never sent: after `transaction.completed` alone, `/auth/me` is `pro`. One row (`pro`, `active`, no organisation, customer and period end set), the payment is paid with its subscription id, and there is exactly one `GET /subscriptions/{id}`. `/billing/subscription` is Pro and `/billing/invoices` has 1. A later refresh fetches nothing more. |
| `test_paddle_reconcile_alone_makes_plan_live` | pytest | no webhook at all: `jobs.reconcile` makes the plan Pro, with one row and the payment paid |
| `test_paddle_fetch_error_logged_then_refresh_or_reconcile_attach` | pytest | Paddle answers 404 for the subscription: the error is logged with the id and the reference; the payment is paid, there is no row, the plan is Free, and `awaits_subscription` is true. Then the refresh (one buyer) or `jobs.reconcile` (another) makes it Pro with one row. A checkout paid outside the 48 h window is left alone. |
| `test_paddle_either_event_order_one_subscription_row[transaction_first]`, `[subscription_first]` | pytest | both events, in either order and each delivered twice, plus a late `transaction.paid`, the refresh and the reconcile: one row, `pro`. The events fetch the subscription only while its row is missing (1 or 0 fetches), plus the reconcile's daily re-fetch. |
| `test_paddle_credit_pack_fetches_no_subscription` | pytest | a 5,000-credit pack (one `transaction.completed`, no subscription): paid, `provider_subscription_id` null, `awaits_subscription` false. The event, the refresh and the reconcile make no `GET /subscriptions/…` for it, and the pack is `credited`. |
| `test_paddle_attach_skips_one_off_items` | pytest | a pack's payment naming a subscription id fetches nothing |
| `test_stripe_listing_checkout_returns_to_supplier_billing` | pytest | Stripe mocked, with a synced `listing_standard` price: `POST /supplier/listing` sends `success_url` / `cancel_url` `{SITE_URL}/supplier/billing/?checkout=success\|canceled&ref=lst_…`, and a personal checkout still sends `/dashboard/billing/?checkout=…&ref=tbx_…`. The refresh with a complete session gives a paid payment and a `listing_standard` subscription (not `pro`). `GET /supplier/listing` then says `standard`, `active`, commission 800 bp. The owner's running app trial stays active and stays their plan. |
| `test_stripe_org_checkout_return_unchanged` | pytest | an organisation's Stripe checkout still returns to `/dashboard/billing/?checkout=…&ref=…&org=<id>` |
| `test_mock_paddle_drop_and_no_return_switches` | pytest | `drop_list(" a, b ,")`. With `DROP={"subscription.created"}`, only `transaction.completed` is posted; both events stay in `STATE["sent"]`, and the dropped one is in `STATE["dropped"]`. With `RETURN.to_site` false, the pay page answers 200 "… close this tab"; otherwise it answers 303 to `/dashboard/billing/?checkout=success&ref=…`. |
| `test_site_pf2d_supplier_billing_return_copy` | build check | the supplier billing page's chunks carry `{plan} is your listing plan`, `Confirming your payment`, `Your listing plan is unchanged` and the `/refresh` call. The page source reads `checkout` and `ref` and uses `SUPPLIER_CHECKOUT` and `refreshPayment`. |
| PF2, PF2b, PF2c, PF3a, PF8, PF11 suites | pytest | unchanged and green |

## Human test

Local stack: the Paddle mock dropping `subscription.created`, the API on :8000, and the site built against it. Use an `@example.com` address and the password `password123`. If an earlier test left `server\auth.db` behind, delete it to start fresh.

1. In `server\.env` (`server\run.bat` copies `.env.example` there on first run), set: a long `SECRET_KEY`; `BILLING_PROVIDER=paddle`; `PADDLE_API_KEY=pdl_sdbx_local`; `PADDLE_WEBHOOK_SECRET=pdl_ntfset_mock_secret`; `PADDLE_CLIENT_TOKEN=local`; `PADDLE_API_BASE=http://127.0.0.1:8098`; `SITE_URL=http://127.0.0.1:3142`; `http://127.0.0.1:3142` added to `CORS_ORIGINS`; `MAIL_BACKEND=console`.
2. Terminal 1, in `server\`: `$env:MOCK_PADDLE_DROP="subscription.created"; $env:MOCK_PADDLE_NO_RETURN="1"; .venv\Scripts\python.exe -m uvicorn tests.mock_paddle:app --port 8098`. Terminal 2: `server\run.bat`. Terminal 3, in `server\`: `.venv\Scripts\python.exe -m scripts.sync_prices --provider paddle --env sandbox` → "24 prices, 24 new".
3. In the worktree: `Remove-Item -Recurse -Force out; $env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; npm run build`, then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → "serving … on http://127.0.0.1:3142/".
4. Open `http://127.0.0.1:3142/signup/` and sign up as `pf2d@example.com`. Go to Dashboard → Billing: "Free plan · no card needed", with Pro and Monthly selected. Tick the consent box, then click **Continue to payment** → the mock pay page lists the Pro price.
5. Click **Pay with a test card** → the mock shows "Paid" and "Payment complete. You can close this tab." It does not open the billing page. Terminal 1 prints `mock paddle: subscription.created not sent (MOCK_PADDLE_DROP)`. Close the tab.
6. In a new tab, open `http://127.0.0.1:3142/dashboard/billing/` (no `?checkout=`). Current plan: **Pro**, "Monthly · 1 seat", "Renews on" a date a month away. **Invoices**: one row (number `…-00001`, Total, Tax) with Download. **Payment history**: "Pro · Monthly", Card, Paid. There is no "Payment received" notice, because the page was opened fresh.
7. Optional, the reconcile alone. Stop Terminal 1 and start it again with `$env:MOCK_PADDLE_DROP="subscription.created,transaction.completed"` (keep `MOCK_PADDLE_NO_RETURN`), then run step 2's `sync_prices` again. Sign up as `pf2d-2@example.com` and buy Pro as in steps 4 and 5. Billing, opened fresh, still says Free plan. In `server\`, run `.venv\Scripts\python.exe -m app.worker --run billing.reconcile` → "ran: billing.reconcile". Reload Billing → Pro, with one invoice.
8. The supplier listing return has no step here: a listing fee waits for GD7, so it is covered by pytest (`test_stripe_listing_checkout_returns_to_supplier_billing`, `test_site_pf2d_supplier_billing_return_copy`).
9. Close the three terminals.

## Risks / traps

* **Real Paddle sends `transaction.paid` before the subscription exists** (no `subscription_id`), then `transaction.completed` with it. Only the second one fetches. Both mark the same payment paid, idempotently.
* **Two webhooks at once:** `transaction.completed` can fetch while `subscription.created` is being applied. Each looks the row up by `(provider, provider_subscription_id)`, and `upsert_subscription` retries an `IntegrityError` onto the row the other created. The unique index keeps it to one row.
* **A fetch error is not retried by Paddle:** the webhook answers 200. The refresh and the reconcile pick the payment up through `awaits_subscription`, within the reconcile's 48 h window. After that, a personal checkout's next `subscription.updated` (a renewal, a change) applies it, from Paddle's own event.
* **`GET /supplier/listing` writes:** it syncs the supplier's own listing rows first. The sync is the job's own (expires a checkout older than 24 h, copies the customer), limited to one supplier.
* **The mock's pay page waits for the webhooks before it redirects,** so a person cannot close the tab in between. `MOCK_PADDLE_NO_RETURN=1` plays that buyer. `MOCK_PADDLE_DROP` is read when the mock starts: restart it to change the list (its prices live in memory, so run `sync_prices` again).
* Never run `next dev` here (RAM). The human test's build bakes the local API into `out/`; the verify gate rebuilds against `.env.local`.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t42-pf2d-billing-follow-ups-a-paid-p` from `ap/t36-pf2c-billing-tidy-ups-one-stripe` (`b3e4f3c`, `master` 842768e + PF2c). `3f6e74d` (code, tests, site, mock), then the commit with this doc, the tracker row and the README section.
* **Counts:** pytest collected 557 → 568 (`test_pf2d_billing_followups.py`: 10 tests, 11 items). `scripts/autopilot-verify.ps1` green: lint, build, pytest 562 passed and the 6 Postgres-only skips. The build check ran against the fresh `out/` and passed. No new route in `out/`.
* **Tests first:** on the unchanged code 6 failed: no plan after `transaction.completed`, no log line, one fetch where two were expected, `awaits_subscription` missing, the `/dashboard/billing/` return for `lst_…`, and no mock switches. 4 passed, because they guard behaviour that already worked: the reconcile with both webhooks lost (a pending payment), the subscription-first order, the pack guard, and the organisation's Stripe return. The build check was skipped (no `out/`).
* **Postgres:** a throwaway Postgres 17 cluster (`initdb` in the session scratchpad, port 55442, `timezone = 'Asia/Baghdad'`, removed afterwards). With `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`, `test_pf2d_billing_followups.py`, `test_billing.py`, `test_billing_pf2.py`, `test_billing_orgs.py`, `test_pf2c_billing_tidy.py` and `test_ai_topup_billing.py` gave 80 passed (PF2c's Postgres twin included). `test_supplier_portal.py` and `test_billing_pf2b.py` gave 28 passed. The reconcile's correlated `NOT EXISTS` and the `paid_at` window behave the same on both databases.
* **Self-test beyond pytest:** real processes. `tests/mock_paddle.py` ran under uvicorn with `MOCK_PADDLE_DROP=subscription.created` and `MOCK_PADDLE_NO_RETURN=1`, sending signed webhooks. The API ran under uvicorn on a fresh SQLite database, and `sync_prices` made 24 prices. `out/` was built against that API and served. Headless Edge was driven over CDP.
  * **Paddle, 13 of 13 checks:** sign up; Billing on Free; consent ticked; Continue to payment opens the mock's pay page with the Pro price; Pay keeps the buyer on the mock ("Paid"). Billing, opened fresh, shows Pro, one invoice, "Pro · Monthly … Paid" and no return notice. The API answers `pro`/`active` and 1 invoice. There were no script errors. The mock logged the dropped event, and the API's `billing_events` held only `transaction.completed`, with one subscription row.
  * **The reconcile alone:** the mock was restarted dropping both events. The payment was pending and the plan Free; `python -m app.worker --run billing.reconcile` made it Pro with one row and one invoice.
  * **The supplier return, 8 of 8:** an applied supplier, with a paid `lst_` payment, its stored `listing_standard` Stripe subscription and a `checkout` listing row seeded through the app's models, since no listing fee exists. `?checkout=success&ref=` showed "Payment received. Standard is your listing plan." with Standard as the current plan. `?checkout=canceled` showed the cancelled note. A pending payment showed "Confirming your payment…", then after 9 s "Payment is still processing…". The plain page showed no note. At 375 px there was no sideways scroll, and there were no script errors. The owner's app plan stayed Free.
  * In all, 16 of 16 orchestrator checks passed.
  * Harness notes: Python's `http.server` listen backlog of 5 once refused an image request (PF8's As-built saw the same), so the self-test served `out/` with a backlog of 128 and `serve-out.py`'s own handler. The mock's pay page has no favicon (a 404 there is not the site's).
* **Deviations and why:**
  1. *The refresh repairs it too.* The task says "subscription.created, the refresh or the reconcile still follow". The refresh only looked at pending payments, and `transaction.completed` had already marked this one paid. It now also re-verifies `awaits_subscription` payments.
  2. *`verify_payment` fetches a stored subscription no more.* Before, every refresh and reconcile of a paid checkout fetched its subscription a second time. Now the fetch happens once, when the transaction is applied, and again only if that failed. The reconcile still re-fetches every stored subscription daily.
  3. *`upsert_subscription` keeps `listing_*` tiers and leaves trials alone for them.* The listing test's full flow (checkout, refresh, subscription, portal) found two faults: PF8's listing subscription would have been stored as `pro`, giving the owner Pro and never matching `listing.sync`; and it ended the owner's app trial. Both had been hidden because PF8's test inserted the `listing_standard` row by hand.
  4. *`GET /supplier/listing` syncs that supplier's rows.* Without it, the page would show the old plan until the 10-minute job ran, so it could not "show the plan's state" on return.
  5. *`MOCK_PADDLE_NO_RETURN` besides `MOCK_PADDLE_DROP`.* The mock redirects only after delivering the webhooks, so "close the tab before the return page loads" cannot be done by hand without it.
  6. *Copy as a new export `SUPPLIER_CHECKOUT`* at the end of `constants.ts` (merge hygiene), not inside `SUPPLIER.billing`.
* **Contract:** none to update.
* **Carry-over → which feature:**
  * **GD7 / owner:** `scripts/sync_prices.py` has no `listing_<plan>` targets. With a fee in `listing_plans.json` and no synced Stripe price, `choose()` still records the plan `pending` ("Online payment for this plan isn't set up yet"). Add the listing targets to `sync_prices.py` when GD7 sets the fees; PF8's As-built assumed they existed.
  * **PF2b:** a listing plan would get two consumer notices. `consumer.payment_paid` would mail it the subscription order confirmation once `LEGAL_WORDING_APPROVED` is on. `send_due_notices` would send it renewal reminders once `SUBSCRIPTION_NOTICES_ENABLED` is on, because it selects every live Paddle or Stripe subscription (before this branch it did the same, with the row stored as `pro`). A supplier's listing plan is a business contract, so PF2b's rules should skip `listing_*`, as they skip `ONE_OFF_ITEMS`.
  * **PF8:** `listing.sync` matches a listing row that has no subscription id by owner and tier (the newest `listing_<plan>` subscription). Two checkouts for the same plan by the same owner would both match the one paid subscription. This is harmless while a supplier has one plan, but it is worth matching by the payment's `provider_subscription_id` (now set on paid Stripe checkouts) when listing fees go live.
