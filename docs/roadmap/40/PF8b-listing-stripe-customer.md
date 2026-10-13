# PF8b — A supplier's listing plan on its own Stripe customer (launch priority 2)

**Needs merged:** PF8a (the listing sync by subscription id, `is_consumer_plan`), PF2b (the `business` flag and the EU withdrawal), PF7 (`suppliers.billing_customer_id`, the commission statements' invoices). All are on `master` 9dac34b. **Unblocks:** listing fees going live (GD7, an ops step with no code change) without the supplier's VAT id reaching the owner's own plan. **Contract:** none. No endpoint, field, table or switch is added, and `contracts/` is unchanged.

## Status

**Built (2026-10-13, branch `ap/t62-pf8b-a-suppliers-listing-plan-on`, Autopilot T62); see As-built.** This was PF8a's carry-over "PF2 / PF8, when fees go live". Each point was checked on `master` 9dac34b before the work began:

| # | Gap | Where (base 9dac34b) | Then |
|---|---|---|---|
| 1 | One customer for every checkout | `server/app/billing/service.py:127` `customer_id(db, user, provider)`: the customer of the person's most recently updated subscription there, of any plan. `live_subscription` (line 74) and `managed_subscription` (line 105) skip `listing_*`; `customer_id` did not. | A listing checkout reused the customer of the owner's Pro, and a Pro checkout reused the listing plan's customer, whichever had been updated last. |
| 2 | Its callers | `stripe_provider.py:180` (`create_checkout`, the subscription checkout that `supplier/listing.py` `choose` opens a paid listing plan through, line 215), `stripe_provider.py:223` (the AI top-up's one-off checkout), `org_billing.py:136` `personal_scope` (the person's invoice list) and, without a scope, `stripe_provider.py` `list_invoices` / `invoice_pdf_url` (the person's invoice PDF link, and the supplier portal's statement invoice) | All took that one customer. |
| 3 | The VAT id lands on that customer | Every subscription checkout sets `tax_id_collection: {enabled: True}` and, with a saved customer, `customer_update` address and name `auto` (`stripe_provider.py:160-185`). `_apply_session` sets `payment.business = True` whenever `customer_details.tax_ids` is non-empty (line 264). | Stripe saves a tax id collected at checkout onto the customer, and reports a customer's saved tax ids on its later sessions. So the supplier's VAT id marked the owner's next Pro payment `business`, and PF2b took the EU withdrawal away. |
| 4 | Commission invoices | `supplier/listing.py:302` `sync` copies the listing subscription's customer into `suppliers.billing_customer_id`, which PF7's statements invoice (`market/commissions.py:122` `_pf2_invoice`). | A listing checkout opened by an owner who already had Pro put the supplier's commission invoices on the owner's personal customer. |

`suppliers.billing_customer_id` is at `server/app/market/models.py:76`. The admin sets it at `server/app/routers/market_admin.py:165`, or the sync does.

## Goal

A supplier's listing plan is the supplier company's contract, paid on the company's own Stripe customer with its VAT id. The owner's own Pro plan, top-ups and invoices stay on the owner's own customer. The company's VAT id never makes the owner's own Pro a business purchase, so Billing keeps offering the owner their 14-day EU withdrawal. The commission statements go to the company's customer.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* `PF8a-listing-plans-and-consumer-rules.md`: Design, As-built deviations 2 and 3, the consumer-path table, the carry-over.
* `PF8-supplier-portal-and-app.md` (Scope 7, As-built deviation 2: the listing plan through PF2), `PF2b-subscription-consumer-rules.md` (`business`, the EU withdrawal), `PF3a-organisation-billing.md` (organisations share their buyer's customer; `personal_scope`).
* Code: `server/app/billing/{service,stripe_provider,org_billing}.py`, `server/app/supplier/listing.py`, `server/app/market/commissions.py`.
* Stripe: "Collect tax IDs with Checkout" (docs.stripe.com/tax/checkout/tax-ids). With an existing customer, Checkout "adds the collected tax ID to customer.tax_ids", and "if the customer has one or more saved tax IDs, Checkout doesn't display the tax ID collection form". The session's `customer_details` holds "the customer's tax IDs".

## Scope

**In:**

1. **The listing checkout's customer.** A `listing_*` payment's Stripe checkout opens on the supplier's `billing_customer_id` when it is set. Otherwise it opens on no saved customer (`customer_email`, so Stripe makes a new one). It never takes `service.customer_id`'s answer. PF2's `create_checkout(db, user, payment, price, seats, discount)` call is unchanged for every caller.
2. **The app plan's customer.** `service.customer_id` skips `listing_*` subscriptions, as `live_subscription` and `managed_subscription` do. So do its callers: the subscription checkout, the top-up checkout, `personal_scope` and the person's invoice PDF link.
3. **The sync** copies the listing subscription's customer, now always the supplier's own, into an empty `billing_customer_id`. A billing customer already set wins over a different one.
4. **Organisations (PF3a)** checked for the same fault, and not changed. The finding is a carry-over (As-built).
5. **Paddle** is untouched: listing plans are Stripe only.
6. The supplier portal's statement invoice PDF opens on the supplier's own customer. It was found while doing item 2: see As-built, deviation 3.

**Out (and where it goes):**

* Organisation checkouts that save the organisation's VAT id on the buyer's customer → PF3a follow-up (As-built carry-over).
* Listing fees and `listing_<plan>` prices in `scripts/sync_prices.py` → GD7 and the owner (PF8a's carry-over, unchanged).
* The supplier-terms text in Stripe's terms box on a listing checkout → GD5 and the owner (PF8a's carry-over, unchanged).

## Design

**API:** no new endpoint or field. `POST /supplier/listing`, `POST /billing/checkout`, `POST /account/ai/top-ups`, `GET /billing/invoices` and `GET /supplier/statements/{id}/invoice` answer in the same shapes.

**The checkout** (`server/app/billing/stripe_provider.py` `create_checkout`):

```python
if payment.plan.startswith(service.LISTING_TIER_PREFIX):
    customer = service.listing_customer(db, payment)   # the supplier's own, or None
else:
    customer = service.customer_id(db, user, "stripe")  # the person's own, never a listing plan's
# then as before: customer + customer_update {address, name: auto}, else customer_email = user.email
```

`service.listing_customer(db, payment)` finds the supplier through the `listing_subscriptions` row whose `payment_ref` is the payment's reference, and returns its `billing_customer_id`. `supplier/listing.py` `choose` now writes that row's `payment_ref` and flushes before it opens the checkout (`SessionLocal` does not autoflush). A provider error rolls both back, as before.

**Why the lookup and not a `customer=` argument.** PF8's portal test stands in for PF2's provider with a `create_checkout(self, db, user, payment, price, seats, discount)` of exactly six arguments. The task kept that suite unchanged, and a keyword argument would break it. The lookup also leaves PF2's provider interface as it was, and it reads the customer from our own rows, never from a caller.

**Whose e-mail opens a new listing customer:** the member's (`user.email`, the owner who opens the checkout). Suppliers have no billing e-mail. `suppliers.contact_email` is where leads and orders go: it is the sales inbox from the application, not the payer. Stripe prefills the e-mail and sends its receipts there. Stripe allows several customers with one e-mail, so this makes a new customer and never reuses the person's own.

**`customer_id`** gains one condition, `~Subscription.plan.startswith(LISTING_TIER_PREFIX)`. Organisation subscriptions still count (PF3a: an organisation's subscription lives under its buyer's customer by design).

**No second guard on `customer_id`.** It does not also refuse a customer that is some supplier's `billing_customer_id`. The query would be cheap, but:
* After items 1 and 3, a supplier's customer is shared with a person's own plan only if the admin set `billing_customer_id` to that person's customer by hand.
* The guard would also hide that person's own invoices from `personal_scope`, and refuse their own PDF links.
* No production row shares a customer today, because no listing fee exists.

A guard at the admin's `PATCH` is the better place (carry-over).

**The sync** (`supplier/listing.py` `sync`):
* An empty `billing_customer_id` takes the listing subscription's customer.
* One already set (by the admin, or by an earlier checkout) wins over a different customer. Listing checkouts open on it, so a new subscription differs from it only after the admin changed it, for example to invoice another company of the group.
* The difference is logged once, when the row first follows that subscription: `truebex.supplier` WARNING "supplier … listing subscription … is on …; statements stay on …".
* Before PF8b, the sync overwrote the admin's value every 10 minutes.

**The statement invoice** (`supplier/listing.py` `invoice_url`) asks PF2's `invoice_pdf_url` with `InvoiceScope(customers=(supplier.billing_customer_id,))`. So any owner of the supplier opens it, whichever customer they pay their own plan on. An invoice on another customer stays a 404. `billing_interface()` also returns `InvoiceScope`. A stand-in interface without it (PF8's portal test) gets the member-scoped call it had before.

**Data:** no table, column or migration. **UI:** none. **Jobs:** `supplier.listing.sync` as above.

**Security and privacy:** nothing new is stored or sent. The customer a listing checkout opens on comes from our own rows. A person's own checkouts no longer carry a company's customer, and with it the company's name, address and VAT id. A statement PDF still needs an owner of the statement's supplier, and Stripe's answer must name the supplier's customer.

## Deliverables

- [x] `server/app/billing/service.py`: `customer_id` skips `listing_*`; `listing_customer()`
- [x] `server/app/billing/stripe_provider.py`: `create_checkout` picks the customer by kind; the module docstring
- [x] `server/app/supplier/listing.py`: `choose` names the payment on its row before the checkout; `sync` keeps a billing customer already set; `invoice_url` on the supplier's customer; `billing_interface()` returns `InvoiceScope`; the module docstring
- [x] `server/tests/test_pf8b_listing_customer.py` (8 tests)
- [x] `server/scripts/seed_listing_checkouts.py`: a separate PF8b block (`--pf8b`, `--checkouts`, `--stripe-price`)
- [x] This doc, the PF8b row in `docs/roadmap/40/README.md`, PF8a's carry-over marked done, a README section

## Tests

`_Stripe` (in the test file) stands in for Stripe's side:
* A session runs on the customer it names, else on a new one (`cus_new_N`).
* A VAT id entered at checkout is saved onto that customer. Checkout asks no customer that already has one.
* Every session reports its customer's saved tax ids in `customer_details.tax_ids`.

`stripe.checkout.Session.create` is patched to capture its params, as `test_billing_pf2.py:324` does.

| Name | Kind | Asserts |
|---|---|---|
| `test_listing_checkout_never_takes_the_owners_pro_customer` | pytest | The owner pays Pro on `cus_pro`, and the supplier has no billing customer. `POST /supplier/listing` opens a checkout with `customer_email` = the owner's address, no `customer` and no `customer_update`. `cus_pro` appears nowhere in the params, and tax id collection is on. |
| `test_listing_checkout_uses_the_suppliers_billing_customer` | pytest | The admin set `cus_sup` (`PATCH /admin/market/suppliers/{id}`). The listing checkout uses `customer: cus_sup` with `customer_update` address and name `auto`, and no `customer_email`. The row names the payment whose `provider_ref` is the session. With Stripe unreachable, the answer is 502 and neither a second row nor a second payment is left. |
| `test_app_checkouts_never_take_the_listing_customer` | pytest | The listing plan on `cus_sup` was updated after the owner's ended Pro on `cus_pro`, and a Pro trial runs. `POST /billing/checkout` and `POST /account/ai/top-ups` both use `customer: cus_pro`, and `customer_id` is `cus_pro`. With the Pro row gone (no app plan with a customer), both use `customer_email`, never `cus_sup`, and `customer_id` is None. |
| `test_listing_vat_id_never_makes_the_owners_pro_business` | pytest | `EU_WITHDRAWAL_ENABLED` is on, and the owner's earlier Pro on `cus_pro` has ended. The listing plan is paid from GB with VAT id GB123456789 on a new customer: that payment is `business`, the VAT id is saved there, and the sync makes it the billing customer. The owner's Pro checkout then opens on `cus_pro`, and its session reports no tax ids. Paid from DE, it is not `business`, and `/billing/subscription` answers Pro with a `withdrawal_until`. |
| `test_listing_sync_copies_the_listing_customer_not_the_owners` | pytest | The owner pays Pro on `cus_pro`. After the first listing checkout and `GET /supplier/listing` (which syncs), `billing_customer_id` is the new customer, not `cus_pro`. The next listing checkout opens on it. |
| `test_listing_sync_keeps_the_billing_customer_already_set` | pytest | The admin's `cus_admin` beside a paid listing subscription on `cus_sup`: the sync activates the row and the plan, and keeps `cus_admin`. One WARNING names both customers; a second sync changes nothing and logs nothing. |
| `test_personal_invoices_are_the_app_plan_customers` | pytest | Pro on `cus_pro`, and a listing plan on `cus_sup` updated later. `personal_scope` is `("cus_pro",)`. `GET /billing/invoices` asks Stripe for `cus_pro` only and lists its invoice, and that invoice's signed PDF link redirects to its PDF. |
| `test_statement_invoice_is_opened_on_the_suppliers_customer` | pytest | Two statements, invoiced on `cus_sup` (the billing customer) and on `cus_other`. The first opens for the owner who pays Pro on `cus_pro`, and for a second owner with no customer at all. The second is a 404 for both. |
| PF8a, PF2, PF2b, PF2c, PF2d, PF3a, AI top-up and PF8 suites | pytest | unchanged and green |

## Human test

**A. Without Stripe keys (about 3 minutes).** The seed script's PF8b block runs the app's own checkout code, with Stripe's side stood in for in-process. Run it in PowerShell, in the worktree's `server\` folder.

1. Use a scratch database, with the EU withdrawal switched on:
   ```
   $env:DATABASE_URL="sqlite:///./pf8b-test.db"; $env:EU_WITHDRAWAL_ENABLED="true"
   ```
2. `.venv\Scripts\python.exe scripts\seed_listing_checkouts.py --email pf8b@example.com --pf8b`
   * It prints "seeded supplier … (PF8b Listing) for pf8b@example.com, Pro ended on cus_seed_pro".
3. `.venv\Scripts\python.exe scripts\seed_listing_checkouts.py --email pf8b@example.com --checkouts`
   * "listing checkout lst_…: opens on **a new customer (customer_email pf8b@example.com)**".
   * "paid from GB with VAT id GB123456789 on cus_sim_1: business True", then "supplier billing customer after the sync: cus_sim_1".
   * "Pro checkout tbx_…: opens on **customer cus_seed_pro**".
   * "paid from DE without a VAT id on cus_seed_pro (its saved tax ids: none): business False".
   * "EU withdrawal: offered until <14 days from today> 23:59 UTC".
   * "Stripe customers: cus_seed_pro (no tax id); cus_sim_1 (GB123456789)". These are the two customers.
4. Optional, the API's view of the same database. Start it with placeholder Stripe keys, so the API treats Stripe as on (nothing is sent to Stripe by these reads):
   ```
   $env:STRIPE_SECRET_KEY="sk_test_dummy"; $env:STRIPE_WEBHOOK_SECRET="whsec_dummy"; $env:BACKGROUND_TASKS="off"
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
   Then, in a second PowerShell:
   ```
   $t = (Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/login -ContentType application/json -Body '{"email":"pf8b@example.com","password":"password123"}').access_token
   Invoke-RestMethod http://127.0.0.1:8000/billing/subscription -Headers @{Authorization="Bearer $t"} | Select-Object tier, withdrawal_until
   Invoke-RestMethod http://127.0.0.1:8000/billing/payments -Headers @{Authorization="Bearer $t"} | Select-Object reference, plan, business
   ```
   * `pro` with a `withdrawal_until` date.
   * The `pro` payment has `business` False, and the `listing_standard` one True.
5. Clean up: stop the API and delete `server\pf8b-test.db`.

For contrast, on `master` (9dac34b) steps 2 and 3 print:
* "listing checkout …: opens on customer cus_seed_pro", and "paid … on cus_seed_pro: business True";
* "supplier billing customer after the sync: cus_seed_pro";
* "Pro checkout …: opens on customer cus_seed_pro", "(its saved tax ids: GB123456789): business True", "EU withdrawal: not offered";
* "Stripe customers: cus_seed_pro (GB123456789)": one customer.

**B. With Stripe's test mode (owner only, about 15 minutes).** It needs the owner's Stripe test keys and a listing price. Don't commit these local changes.

1. In Stripe's test-mode dashboard, create a recurring price of GBP 49.00 a month (product "Truebex Listing Standard"), and note its `price_…` id.
2. In `server\app\market\listing_plans.json`, give Standard GD7's fee locally: `"monthly_fee": {"GBP": 4900}`. Revert this after the test.
3. In terminal A, in `server\`:
   ```
   $env:DATABASE_URL="sqlite:///./pf8b-stripe.db"; $env:BILLING_PROVIDER="stripe"; $env:STRIPE_SECRET_KEY="sk_test_…"; $env:STRIPE_WEBHOOK_SECRET="whsec_…"
   $env:LEGAL_WORDING_APPROVED="true"; $env:EU_WITHDRAWAL_ENABLED="true"; $env:CONSENT_VARIANT="service"; $env:CORS_ORIGINS="http://127.0.0.1:3162"; $env:BACKGROUND_TASKS="off"
   .venv\Scripts\python.exe scripts\sync_prices.py --provider stripe --env sandbox
   .venv\Scripts\python.exe scripts\seed_listing_checkouts.py --email pf8b@example.com --pf8b --stripe-price price_…
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
   * The webhook secret can be the one `stripe listen --forward-to http://127.0.0.1:8000/billing/webhooks/stripe` prints, or any value: the portal's and Billing's return pages apply each checkout themselves.
4. In terminal B, in the worktree root:
   ```
   Remove-Item -Recurse -Force out; $env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; $env:NEXT_PUBLIC_LEGAL_WORDING_APPROVED="true"; npm run build
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1
   ```
   It prints the port (`http://127.0.0.1:3162/` under Autopilot T62).
5. Sign in at `/login/` as `pf8b@example.com` / `password123`. Open Supplier portal → Plan and billing → choose **Standard**.
   * In Stripe Checkout:
     * pay with card 4242 4242 4242 4242;
     * use a United Kingdom billing address;
     * tick "I'm purchasing as a business": name "PF8b Listing Ltd", VAT GB123456789.
   * Back on the portal, the plan is **Standard**.
6. Open Dashboard → Billing, and buy **Pro** monthly in GBP: tick the two boxes and continue.
   * Stripe Checkout shows the e-mail, but no saved business name or VAT id.
   * Pay with a **Germany** billing address, without ticking business.
   * Back on Billing: **Pro**, and **Withdraw from contract** ("Open until …", 14 days from today).
7. In the Stripe test dashboard → Customers there are **two** customers for `pf8b@example.com`:
   * one holds the GB123456789 tax id and the listing subscription;
   * the other has no tax id and holds the Pro subscription.
   The Pro payment on its invoice has no reverse charge.
8. Clean up: stop the API and the server, revert `listing_plans.json`, delete `server\pf8b-stripe.db`, and cancel the two test subscriptions in Stripe.

On `master`, step 6's checkout opens on the listing customer. It shows the saved business details, and the payment comes back `business`, with no "Withdraw from contract".

## Risks / traps

* **Rows from before PF8b.** None exist in production, because there is no listing fee yet. A test-mode database where a listing plan was bought before PF8b on the owner's own customer has that customer in `billing_customer_id`, and it now wins. Set the supplier's own customer by hand (`PATCH /admin/market/suppliers/{id}`) before the next listing checkout.
* **The admin can still set a person's own customer** as a supplier's `billing_customer_id`, and the listing checkout then opens on it. Nothing refuses it (carry-over).
* **`choose` must flush the row before the checkout:** `SessionLocal` has `autoflush=False`, and `listing_customer` reads the row.
* **Listing invoices are not in the owner's personal Billing any more.** Before PF8b they showed there only when the listing plan happened to be updated last. The portal lists commission statements' invoices. Stripe sends the listing plan's own receipts to the member's e-mail when the account sends receipts (carry-over).
* **Paddle is untouched.** `customer_id`'s new condition changes nothing there, because no listing subscription is on Paddle. `choose` always opens the listing checkout through `get_provider("stripe")`.
* Never run `next dev` here (RAM). Part B bakes the local API and the approved wording into `out/`. The verify gate rebuilds it against `.env.local`.

## As-built

* **Date, branch, commits:** 2026-10-13, `ap/t62-pf8b-a-suppliers-listing-plan-on` from `master` 9dac34b.
  * `bf85fb1`: the code and the 8 tests.
  * `75bccc1` and `0b190b1`: the seed script's PF8b block.
  * The next commit: this doc, the tracker row, PF8a's carry-over and the README section.
* **Counts:** pytest collected 669 → 677 (`test_pf8b_listing_customer.py`: 8 tests). No public copy, page or route changed.
* **Verify gate:** `scripts/autopilot-verify.ps1` green in 1,340 s: lint, the build (74 static pages), and pytest 660 passed and 17 skipped (Postgres-only tests and site checks that need their own build) in 860 s.
* **Tests first:** all 8 failed on the unchanged code, each on its gap:
  * the listing checkout named `customer: cus_pro`;
  * with `cus_sup` set, it still used `cus_pro`;
  * the Pro checkout and the top-up used `cus_sup`;
  * the listing ran on `cus_pro`, so the Pro payment would have been `business`;
  * the sync copied `cus_pro`;
  * the sync overwrote `cus_admin` with `cus_sup`;
  * `personal_scope` was `("cus_sup",)`;
  * the statement PDF was a 404 for the owner who also pays Pro.
* **On SQLite:** the new file, and unchanged PF8a, PF2 (`test_billing.py`, `test_billing_pf2.py`), PF2b, PF2c, PF2d, the AI top-up, PF3a, PF8 and the four `test_market*.py` suites: 147 passed and 12 skipped (Postgres-only tests and site checks that need their own build).
* **Postgres:** a throwaway Postgres 17 cluster (`initdb` in the session scratchpad, port 55462, `timezone = 'Asia/Baghdad'`, removed afterwards), with `TEST_APP_DATABASE_URL` and `TEST_DATABASE_URL`.
  * The new file, `test_pf8a_listing_consumer_rules.py` and `test_supplier_portal.py`: 28 passed.
  * `test_billing_pf2.py`, `test_billing_orgs.py`, `test_ai_topup_billing.py`, `test_pf2d_billing_followups.py` and `test_billing_pf2b.py`: 79 passed and 1 skipped (PF2d's site build check, no `out/`).
* **Self-test beyond pytest:** real processes on scratch SQLite databases. A scratchpad runner (`pf8b_selftest.ps1`) ran `seed_listing_checkouts.py --pf8b` then `--checkouts` on this branch, and on a copy of `server/` from 9dac34b with the same script.
  * Fixed code:
    ```
    listing checkout lst_…: opens on a new customer (customer_email pf8b@example.com)
      paid from GB with VAT id GB123456789 on cus_sim_1: business True
      supplier billing customer after the sync: cus_sim_1
    Pro checkout tbx_…: opens on customer cus_seed_pro
      paid from DE without a VAT id on cus_seed_pro (its saved tax ids: none): business False
      EU withdrawal: offered until 2026-10-27 23:59 UTC
    Stripe customers: cus_seed_pro (no tax id); cus_sim_1 (GB123456789)
    ```
  * Unchanged code:
    ```
    listing checkout lst_…: opens on customer cus_seed_pro
      paid from GB with VAT id GB123456789 on cus_seed_pro: business True
      supplier billing customer after the sync: cus_seed_pro
    Pro checkout tbx_…: opens on customer cus_seed_pro
      paid from DE without a VAT id on cus_seed_pro (its saved tax ids: GB123456789): business True
      EU withdrawal: not offered
    Stripe customers: cus_seed_pro (GB123456789)
    ```
  * Each database was then served by uvicorn (this branch, placeholder Stripe keys) and read over HTTP:
    * the fixed run's: `/billing/subscription` Pro, `withdrawal_until` 2026-10-27T23:59:59Z; payments `pro` business False, `listing_standard` True;
    * the unchanged run's: Pro with no `withdrawal_until`; both payments business True.
  * A second `--checkouts` on the same database refuses. A `--stripe-price` seed writes that price and no Pro, and `--checkouts` refuses it.
* **Deviations and why:**
  1. *The listing checkout's customer is looked up, not passed in.* `service.listing_customer` reads it through the `listing_subscriptions` row whose `payment_ref` is the payment's reference. Design gives the reason. So `choose` writes the row before the checkout, not after.
  2. *`billing_customer_id` is filled only when empty* (item 3's decision): one already set wins, and a difference is logged once. Before, the sync overwrote it on every run.
  3. *The statement invoice PDF opens on the supplier's customer.* It was not in the task's list, but item 2 would have broken it. `invoice_url` called `invoice_pdf_url` without a scope, which checks the invoice's customer against `service.customer_id` of the member asking. That worked only while the member's listing subscription was their most recently updated one, and never for a second owner or an admin-set customer. Skipping listing plans there would have made it a 404 for every statement. It now passes `InvoiceScope(customers=(billing_customer_id,))`. A stand-in interface without `InvoiceScope` (PF8's portal test, kept unchanged) gets the old call.
  4. *No second guard in `customer_id`* against a supplier's billing customer (item 2's question). Design gives the reasons.
  5. *A seed-script block, not only a scratch script.* Part A of the human test needs the scratch script's equivalent in the repo. `--checkouts` is that equivalent, and the scratchpad runner calls it for both trees.
* **Item 4, organisations: the same fault exists.**
  * An organisation checkout is a non-listing payment, so `stripe_provider.py:192` opens it on `service.customer_id` (`service.py:127`): the buyer's latest customer, or a new one from the buyer's e-mail. Tax id collection is on (`stripe_provider.py:168`), and with a saved customer, `customer_update` saves the business name onto it. So Stripe saves the organisation's VAT id onto the buyer's own customer.
  * `customer_id` deliberately keeps organisation subscriptions (PF3a). The buyer's own later Pro checkout therefore opens on that customer, its session reports the organisation's VAT id, and `_apply_session` (`stripe_provider.py:277`) marks the Pro payment `business`. The buyer loses the EU withdrawal on their own plan. Stripe Tax would also treat the person's own Pro as a business sale.
  * A scratch check through the app's code with the same Stripe stand-in printed:
    ```
    organisation Team checkout: opens on a new customer (customer_email buyer@example.com); paid … with VAT id DE123456789: business True
    buyer's own Pro checkout: opens on customer cus_sim_0; paid on cus_sim_0 (saved tax ids: DE123456789): business True
      EU withdrawal for the buyer's own Pro: not offered
    ```
  * Organisation billing is not changed here, as the task asked (carry-over below). Paddle's organisation checkouts were not checked: Paddle takes the business per transaction, and PF3a notes its customers are one per e-mail.
* **Contract:** none to update.
* **Carry-over → which feature:**
  * **PF3a follow-up (organisation billing):** an organisation's own Stripe customer, so its VAT id stays off the buyer's customer. For example, `organisations.billing_customer_id`, used as `listing_customer` is here, with `customer_id` then skipping organisation subscriptions. Until then, an EU buyer who pays for an organisation with its VAT id loses the withdrawal on their own later Pro (`stripe_provider.py:192`, `service.py:127`, `stripe_provider.py:277`).
  * **PF7 / PF8 admin (optional):** refuse a `billing_customer_id` that is the customer of a person's own subscription (`market_admin.py:165`). Nothing refuses it today.
  * **PF8, when fees go live:** the supplier portal lists commission statements' invoices, but not the listing plan's own monthly invoices. Stripe's receipts go to the member's e-mail.
  * **GD7 / owner** (`listing_<plan>` prices) and **GD5 / owner** (the supplier-terms text in Stripe's box) are PF8a's, unchanged.
