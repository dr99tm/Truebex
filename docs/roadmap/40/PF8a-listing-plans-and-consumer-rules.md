# PF8a — Listing plans kept out of the consumer rules, and the listing sync matched by subscription id (launch priority 2)

**Needs merged:** PF2b (the consumer rules, `server/app/billing/consumer.py`), PF8 (the supplier portal's listing plan, `server/app/supplier/listing.py`), PF2d (listing tiers stored as themselves; `Payment.provider_subscription_id` on paid Stripe checkouts). All are on `master` 6ef7928. **Unblocks:** listing fees going live (GD7) with PF2b's switches on, without consumer mails or exits reaching a supplier's business contract. **Contract:** none. No endpoint, field, table or switch is added; `contracts/` is unchanged.

## Status

**Built (2026-10-12, branch `ap/t54-pf8a-listing-plans-kept-out-of-t`, Autopilot T54); see As-built.** These are PF2d's As-built carry-overs to PF2b and PF8. Each gap was checked on the base `6ef7928` before the work began:

| # | Gap | Where (base 6ef7928) | Then |
|---|---|---|---|
| 1 | Renewal reminders | `server/app/billing/consumer.py:282` (`_renewal_reminders` selects every active subscription of `service.MANAGED_PROVIDERS`) | A live `listing_<plan>` subscription on its synced listing price got "Your Truebex Listing_Standard plan renews on …" once `SUBSCRIPTION_NOTICES_ENABLED` was on. |
| 2 | Order confirmation | `consumer.py:374` (`payment_paid` skips only `service.ONE_OFF_ITEMS`) | A paid listing checkout was mailed "Your Truebex order: Listing_Standard" once `LEGAL_WORDING_APPROVED` was on. |
| 3 | The paid checkout behind a subscription | `consumer.py:455` (`checkout_payment`'s fallback: the user's latest paid payment with the provider, excluding `ONE_OFF_ITEMS`) | With a paid Pro checkout and a paid listing checkout, the latest one stood for both subscriptions. The supplier's business payment could then decide the person's EU withdrawal, and the other way round. |
| 4 | The exits and Billing's offers of them | `consumer.py:496` (`_managed_live`, used by `can_cancel`, `cooling_off_until`, `withdrawal_until`) | Asked about a listing plan, all three offered an exit. Billing never asked them about one, because `service.managed_subscription` (`service.py:115`, PF8) skips `listing_*`. |
| 5 | Listing sync | `server/app/supplier/listing.py:248` (`sync`: a row without a subscription id is matched by owner and tier, the newest `listing_<plan>` subscription) | An unpaid second checkout for the same plan became `active` on the first checkout's subscription. A row from before PF2d took the newest subscription even when another checkout's payment named it. |

`service.LISTING_TIER_PREFIX` is at `server/app/billing/service.py:44`.

## Goal

A supplier's listing plan is a business contract between Truebex and the supplier's company, not a consumer subscription. So the consumer rules the owner switches on after the solicitor's sign-off apply to it in no way: no renewal reminder, no consumer order confirmation, no "Cancel subscription", "Cancel and get a refund" or "Withdraw from contract". The supplier owner's own Pro plan keeps every one of them. Each listing checkout follows its own subscription. A second checkout for the same plan that was never paid expires; it does not borrow the paid one's subscription.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* As-built of `PF2b-subscription-consumer-rules.md` (the rules, `ONE_OFF_ITEMS`, the switches), `PF8-supplier-portal-and-app.md` (deviation 2: `listing.sync`, `LISTING_TIER_PREFIX`) and `PF2d-billing-followups.md` (the carry-overs to PF2b and PF8; how its test seeds a listing payment and its `listing_standard` subscription).
* Code: `server/app/billing/{consumer,service}.py`, `server/app/supplier/listing.py`, `server/app/routers/billing.py` (`_subscription_out`, `_live_for_exit`, `cancel`, `withdraw`).
* Tests: `server/tests/test_billing_pf2b.py`, `test_supplier_portal.py`, `test_pf2d_billing_followups.py`.

## Scope

**In:**

1. One helper, `billing.service.is_consumer_plan(plan)`, used by every consumer rule. A `listing_*` plan (a business contract) and a one-off item (`ONE_OFF_ITEMS`, which starts no subscription) are not consumer plans.
2. Renewal reminders skip a listing plan.
3. The order confirmation skips a listing checkout.
4. The paid-checkout fallback keeps listing and app apart: an app plan's checkout is an app plan's payment, and a listing plan's is a payment of its own tier.
5. The listing sync matches a row by its own subscription id, then by the id its paid payment names. Owner and tier remain only as the fallback for a paid payment that names none (rows from before PF2d).
6. Every other consumer path in `consumer.py` checked for `listing_*` and skipped the same way; each is listed in As-built.
7. No change to app-plan behaviour.

**Out (and where it goes):**

* Listing fees, and `listing_<plan>` prices in `scripts/sync_prices.py` → GD7 and the owner (unchanged from PF2d's carry-over).
* The wording of any notice → GD5 and the owner. That includes a supplier-terms text for Stripe's terms box on a listing checkout (see Carry-over).
* A separate Stripe customer for a person's listing plan → GD7 / PF8 when fees go live (see Carry-over).

## Design

**API:** no new endpoint or field. `/billing/subscription`, `/billing/cancel`, `/billing/withdraw` and `/supplier/listing` answer as before for every app plan.

**The helper** (`server/app/billing/service.py`, beside `ONE_OFF_ITEMS`):

```python
def is_consumer_plan(plan: str | None) -> bool:
    return bool(plan) and not plan.startswith(LISTING_TIER_PREFIX) and plan not in ONE_OFF_ITEMS
```

**The consumer rules** (`server/app/billing/consumer.py`):

| Path | Change |
|---|---|
| `_renewal_reminders` (job `billing.subscription_notices`) | A subscription whose plan is not a consumer plan is skipped before its amount is looked up. Nothing is claimed in `subscription_notices` for it and nothing is mailed. |
| `payment_paid` (Paddle's and Stripe's adapters, once a checkout is paid) | Returns False for any payment that is not a consumer plan: a one-off item, as before, or a listing plan. `confirmation_sent_at` stays null. |
| `checkout_payment` (the paid checkout behind a subscription) | It still matches by `provider_subscription_id` first. The fallback (a payment without one, from before PF2b) takes the buyer's latest paid payment with the provider *of the same kind*: a consumer plan's for a consumer plan, and the exact `listing_<plan>` for a listing plan. A one-off item is neither. The rest is unchanged, including the one-day guard against an old payment. |
| `_managed_live` (`can_cancel`, `cooling_off_until`, `withdrawal_until`: the exits and Billing's offers of them) | A live Paddle or Stripe subscription *whose plan is a consumer plan*. Asked about a listing plan, all three answer False or None. |

**The listing sync** (`server/app/supplier/listing.py`): `subscription_of(db, row, payment)` returns the PF2 subscription that pays a listing row:

1. the one the row names (`row.provider_subscription_id`);
2. else, only once the row's payment is **paid**, the one the payment names (`payment.provider_subscription_id`, set when PF2 marks a Stripe checkout paid). A subscription that is not stored yet gives None, and the row waits as `checkout`;
3. else (a paid payment that names none: a row from before PF2d), the owner's newest `listing_<plan>` Stripe subscription that **no other payment and no other listing row names**. It flushes first, so a row matched earlier in the same sync counts.

An unpaid checkout matches nothing and expires after `CHECKOUT_TTL` (24 h) as before. `sync` walks the rows in id order.

**Data:** no table, column or migration. **UI:** none. Billing and the supplier portal read the same endpoints. **Jobs:** `billing.subscription_notices` and `supplier.listing.sync` change as above.

**Security and privacy:** nothing new is read or stored. A subscription still changes only from the provider's verified event (P.3.3). The sync now trusts a subscription id only from our own paid payment row, which PF2 set from the verified session.

## Deliverables

- [x] `server/app/billing/service.py`: `is_consumer_plan()`
- [x] `server/app/billing/consumer.py`: reminders, the confirmation, `checkout_payment`, `_managed_live`; the module docstring
- [x] `server/app/supplier/listing.py`: `subscription_of()`, `_stripe_subscription()`, `sync` through them; the module docstring
- [x] `server/tests/test_pf8a_listing_consumer_rules.py` (8 tests); `server/tests/test_supplier_portal.py`: PF8's listing test seeds the paid payment with its subscription id
- [x] `server/scripts/seed_listing_checkouts.py`, for the human test
- [x] This doc, the PF8a row in `docs/roadmap/40/README.md`, a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_listing_subscription_gets_no_renewal_reminder` | pytest ✉ | The DMCC switch is on. A live `listing_standard` Stripe subscription on its synced listing price is due in 2 days, beside the owner's own Pro, due the same day. The job sends 1 mail, the Pro reminder ("Your Truebex Pro plan renews on …"). `subscription_notices` holds only the Pro row, and a second run sends nothing. |
| `test_listing_checkout_gets_no_order_confirmation` | pytest ✉ | `LEGAL_WORDING_APPROVED` is on, and PF2d's Stripe flow runs (`POST /supplier/listing`, then the refresh with a complete session). The listing payment is paid as `listing_standard`, with no order mail and `confirmation_sent_at` null; a replayed `payment_paid` is False; the portal shows `standard`. The owner's own Pro checkout (the approved consent and key information) then gets exactly one "Your Truebex order: Pro" with its reference and not the listing's, and the owner's plan is `pro`. |
| `test_paid_checkout_fallback_keeps_listing_and_app_apart` | pytest | One person has a paid Pro checkout (DE, consumer), a paid listing checkout (DE, business) and a later credit pack, all on Stripe with no subscription ids. In both orders (the listing paid last, then Pro paid last), `checkout_payment` gives Pro its own payment and the listing its own, and Pro's `withdrawal_until` stays open. |
| `test_listing_sync_matches_by_subscription_id` | pytest | Three checkouts for Standard by one owner: unpaid; paid with `sub_listing_1` stored; paid with `sub_listing_2` not stored yet. Now: only the paid one is `active` on `sub_listing_1`, and the supplier's plan is `standard`. After `CHECKOUT_TTL`: the unpaid one is `expired` ("The checkout was not completed."), and the waiting one is still `checkout`. Once `sub_listing_2` is stored, the waiting one follows it and the first keeps `sub_listing_1`. |
| `test_listing_sync_falls_back_to_owner_and_tier` | pytest | Two paid rows from before PF2d (no ids) and one paid after PF2d (its payment names `sub_new`, the newest). After the sync, the new row is on `sub_new`, and the old rows are on `sub_a` and `sub_b`, one each. The supplier's plan and billing customer are set, and a second sync changes nothing. |
| `test_listing_plan_offers_no_easy_exit` | pytest | A live listing plan (paid from DE, no VAT id): `can_cancel` is False. With only that plan, `/billing/subscription` answers Free with no offers and `POST /billing/cancel` answers 404. Once the owner's Pro is added, `can_cancel` is True for Pro and still False for the listing. Billing offers the cancel, `POST /billing/cancel` cancels `sub_pro` at Stripe, and the one exit row is Pro's. |
| `test_listing_plan_offers_no_cooling_off_refund` | pytest | The DMCC switch is on, and a listing plan billed yearly was renewed yesterday: no `cooling_off_until`, none on Billing, and the refund cancel answers 404. The owner's annual Pro, renewed the same day, is offered it. |
| `test_listing_plan_offers_no_eu_withdrawal` | pytest | `EU_WITHDRAWAL_ENABLED` is on, and a listing plan was paid from DE without a VAT id: no `withdrawal_until`, none on Billing, and `POST /billing/withdraw` answers 404. The owner's Pro, paid the same way, is offered it. |
| PF2b, PF2d, PF8 and the other billing suites | pytest | unchanged and green. PF8's `test_supplier_listing_checkout_via_billing` now marks the payment paid with its subscription id (As-built, deviation 1). |

✉ reads mail (`test_billing_pf2b.need_mail`).

## Human test

This test uses no site build and no provider: the seed script writes what PF2's Stripe webhook would leave, and the worker runs the two jobs. It takes about 3 minutes. Run it in PowerShell, in the worktree's `server\` folder.

1. Set the switches the owner flips after sign-off, plus a scratch database:
   ```
   $env:DATABASE_URL="sqlite:///./pf8a-test.db"; $env:MAIL_BACKEND="console"; $env:LEGAL_WORDING_APPROVED="true"; $env:SUBSCRIPTION_NOTICES_ENABLED="true"; $env:SUBSCRIPTION_RULES_FROM="2020-01-01"
   ```
2. `.venv\Scripts\python.exe scripts\seed_listing_checkouts.py --email pf8a@example.com`
   * It prints one mail, "--- mail to pf8a@example.com: Your Truebex order: Pro". There is **no** "Your Truebex order: Listing_Standard".
   * Then "seeded supplier … paid listing checkout lst_…, unpaid listing checkout lst_…, Pro checkout tbx_…" and "order confirmations sent now: pro".
3. `.venv\Scripts\python.exe scripts\seed_listing_checkouts.py --email pf8a@example.com --show`
   * "listing plan founding (default)", and both listing checkouts read `checkout, subscription -`.
   * "renewal reminders sent: none".
4. `.venv\Scripts\python.exe -m app.worker --run billing.subscription_notices supplier.listing.sync`
   * It prints one mail, "Your Truebex Pro plan renews on <the day after tomorrow>". There is **no** "Listing_Standard plan renews".
   * Then "ran: billing.subscription_notices, supplier.listing.sync".
5. Run step 3's command again.
   * "listing plan standard".
   * The paid checkout reads `(payment paid): active, subscription sub_seed_listing_…`. The unpaid one reads `(payment pending): expired, subscription -`: the listing plan is active once.
   * "renewal reminders sent: pro (renewal_reminder)" and "order confirmations sent: pro".
6. Run step 4 again: no mail is printed. Then step 3: nothing has changed.
7. Optional, on the site:
   1. In the same terminal, start the API on the same database: `$env:CORS_ORIGINS="http://127.0.0.1:3154"; $env:BACKGROUND_TASKS="off"; .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`.
   2. In a second terminal, in the worktree root, build against it: `Remove-Item -Recurse -Force out; $env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; npm run build`. Then serve it: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1`. It prints `http://127.0.0.1:3154/` under Autopilot; use the port it prints.
   3. Sign in at `/login/` as `pf8a@example.com` / `password123`.
   * Supplier portal → Plan and billing: **Standard** is the current plan.
   * Dashboard → Billing: **Pro**, renewing in 2 days. The listing plan is not the app plan.
8. Clean up: stop the API and the server, then delete `server\pf8a-test.db`.

For contrast: on `master` the same steps 2 to 5 print the Listing_Standard order confirmation and its renewal reminder too. Both listing checkouts then read `active, subscription sub_seed_listing_…`, on the same subscription.

## Risks / traps

* **A paid checkout whose subscription is not stored yet waits.** Its row stays `checkout`, and it never expires, because the payment is paid. PF2d's refresh and the daily reconcile fetch the subscription (`awaits_subscription`), and the next sync follows it.
* **Stripe sends `customer.subscription.created` before `checkout.session.completed`.** Between the two, the subscription exists while our payment is still pending. The row now waits for the session event, which marks the payment paid and names the subscription; the portal's return page applies the session itself through the refresh. Before PF8a such a row was matched by owner and tier at once, which is how a second unpaid checkout took the first one's subscription.
* **`SessionLocal` has `autoflush=False`.** `subscription_of` flushes before the fallback query, so a subscription matched to an earlier row in the same sync counts as named.
* **Trials** (`provider='trial'`) are app plans only. `_trial_notices` needs no check.
* Never run `next dev` here (RAM). The optional site step bakes the local API into `out/`; the verify gate rebuilds it against `.env.local`.

## As-built

* **Date, branch, commits:** 2026-10-12, `ap/t54-pf8a-listing-plans-kept-out-of-t` from `master` 6ef7928. `b75ff73` has the code, tests and seed script; the next commit has this doc, the tracker row and the README section.
* **Counts:** pytest collected 622 → 630 (`test_pf8a_listing_consumer_rules.py`: 8 tests). `scripts/autopilot-verify.ps1` green in 1,080 s: lint, the build (74 static pages), and pytest 614 passed and 16 skipped (Postgres-only tests and site checks that need their own build) in 496 s. No public copy, page or route changed.
* **Tests first:** all 8 failed on the unchanged code, each on its gap:
  * the job sent 2 reminders (the listing plan's too);
  * "Your Truebex order: Listing_Standard" was mailed;
  * `checkout_payment` gave Pro the `lst_listing` payment;
  * the sync made all 3 rows active (expected 1);
  * both rows from before PF2d took `sub_new`;
  * `can_cancel` was True, and `cooling_off_until` and `withdrawal_until` were dates, for the listing plan.
* **Postgres:** a throwaway Postgres 17 cluster (`initdb` in the session scratchpad, port 55454, `timezone = 'Asia/Baghdad'`, removed afterwards). With `TEST_APP_DATABASE_URL` and `TEST_DATABASE_URL`, `test_pf8a_listing_consumer_rules.py`, `test_billing_pf2b.py`, `test_supplier_portal.py` and `test_pf2d_billing_followups.py` gave 46 passed and 1 skipped (PF2d's site build check, no `out/`). The fallback's `NOT IN (subquery)` and the id-order walk behave the same on both databases.
* **On SQLite:** the new file, PF2b, PF2d, PF8, PF2, PF2c, PF3a and the AI top-up suites gave 114 passed and 2 skipped (the site check, and one Postgres-only test).
* **Self-test beyond pytest:** real processes on a scratch SQLite database: the seed script, `python -m app.worker --run billing.subscription_notices supplier.listing.sync`, and uvicorn queried with curl.
  * Fixed code: only Pro's order confirmation and renewal reminder were printed. One listing row was `active` on its own subscription and the unpaid one was `expired`; a second run changed nothing.
  * `GET /supplier/listing` answered `standard`, subscription `active`. `GET /billing/subscription` answered Pro (`can_cancel` true with Stripe keyed), and `/auth/me` answered `pro`.
  * The same steps on a copy of the unchanged `server/app` printed "Your Truebex order: Listing_Standard" and "Your Truebex Listing_Standard plan renews on …". Both listing rows were `active` on the same subscription. So the human test tells the two apart.
* **Every consumer path in `consumer.py`, and what was done:**

  | Path | Listing plan before | Done |
  |---|---|---|
  | `_renewal_reminders` (`billing.subscription_notices`) | reminded, once its price was synced | skipped (`is_consumer_plan`) |
  | `_trial_notices` | not reachable: trials are app plans | none |
  | `payment_paid` (the order confirmation) | mailed | skipped (`is_consumer_plan`) |
  | `checkout_payment` (behind the withdrawal window, its refund charge and the acknowledgement's order line) | the latest paid payment of either kind | same kind only |
  | `can_cancel` (easy exit; Billing's "Cancel subscription") | True if asked | False (`_managed_live`) |
  | `cooling_off_until` (renewal refund; "Cancel and get a refund") | a date if asked (annual, renewed) | None (`_managed_live`) |
  | `withdrawal_until` (EU withdrawal; "Withdraw from contract") | a date if asked (EU, no VAT id) | None (`_managed_live`) |
  | `POST /billing/cancel`, `POST /billing/withdraw` (`routers/billing.py:719` `_live_for_exit`) | never reached: `service.managed_subscription` skips `listing_*` (PF8) | unchanged; tested (404 with only a listing plan, Pro's exit acts on `sub_pro` only) |
  | `GET /billing/subscription` exit offers (`routers/billing.py:141`) | never reached: as above | unchanged; tested |
  | `start_exit`, `complete_exit`, `mail_exit`, `retry_exits`, `pending_exit` | act on exits already recorded, and only the two endpoints above record one | none |
  | `rules`, `consent_version`, `key_info_text`, formatting helpers | no subscription | none |

* **Deviations and why:**
  1. *PF8's `test_supplier_listing_checkout_via_billing` changed.* It inserted the listing subscription beside a still-pending payment and expected the sync to follow it by owner and tier. Since PF2b and PF2d, PF2's webhook marks the payment paid and names the subscription in the same step. So the test now does the same: two lines (`payment.status, payment.provider_subscription_id = "paid", "sub_nord"`), and its asserts are unchanged. An unpaid checkout matching by owner and tier is exactly item 4's fault.
  2. *The fallback never takes a named subscription.* The task asked to keep owner and tier as the fallback. The fallback alone still gave two rows from before PF2d, or one of them beside a row after PF2d, the same newest subscription. It now skips subscriptions that another payment or listing row names.
  3. *The exits are guarded at their eligibility.* The guard is in `_managed_live`, not in `start_exit`. Both endpoints that record an exit pick the subscription through `service.managed_subscription`, which already skips listing plans, so `start_exit` cannot reach one.
  4. *A seed script for the human test* (`server/scripts/seed_listing_checkouts.py`). No listing fee exists, so a listing checkout cannot be paid through Stripe locally. The script writes the rows through the app's models and calls `consumer.payment_paid` as the adapters do. `--show` prints the result.
  5. *`sync` walks the rows in id order.* This keeps the fallback deterministic on Postgres.
* **Contract:** none to update.
* **Carry-over → which feature:**
  * **GD7 / owner:** `scripts/sync_prices.py` still has no `listing_<plan>` targets (PF2d's carry-over, unchanged).
  * **GD5 / owner (wording):** Stripe's terms box on a listing checkout shows the consumer consent placeholder. A listing payment has no consent version, so `stripe_provider.py:167` falls back to `consent.STRIPE_MESSAGE` ("I want my plan to start now. I understand that I lose my 14-day right to cancel…"). A supplier-terms text for that box is GD5's wording, so it is left alone here.
  * **PF2 / PF8, when fees go live:** `service.customer_id` (used by `stripe_provider.py:180`) reuses a person's latest Stripe customer for every checkout, so the owner's Pro checkout reuses the listing plan's customer and the other way round. If that customer holds the supplier's VAT id, Stripe's `customer_details.tax_ids` could mark the Pro payment `business` (`stripe_provider.py:264`). That would take the EU withdrawal from the owner's Pro. It is not changed here: it is app-plan behaviour, and no listing fee exists yet. A separate customer for listing plans (`suppliers.billing_customer_id`) would close it.
