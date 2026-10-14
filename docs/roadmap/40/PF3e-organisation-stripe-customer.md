# PF3e — An organisation's Stripe subscription on its own Stripe customer (launch priority 2)

**Needs merged:** PF3a (organisation billing, `org_scope` and `personal_scope`), PF8b (a listing plan on its own customer, the Stripe stand-in), PF2b (the `business` flag and the EU withdrawal). All are on `master` ec32911. **Unblocks:** organisations paying on Stripe with their VAT id without the buyer losing the EU withdrawal on their own plan, and an organisation's portal that a billing member can open without seeing the buyer's own Stripe account. **Contract:** none. No endpoint, field, table, column or switch is added, and `contracts/` is unchanged.

## Status

**Built (2026-10-14, branch `ap/t76-pf3e-an-organisations-stripe-sub`, Autopilot T76); see As-built.** This was PF8b's carry-over "PF3a follow-up" (PF8b As-built, "Item 4, organisations: the same fault exists"). Each point was checked on `master` 988334f; the billing code is the same on ec32911, the branch's base:

| # | Gap | Where (988334f) | Then |
|---|---|---|---|
| 1 | The organisation's checkout | `server/app/billing/stripe_provider.py:186-198` `create_checkout`: only `listing_*` plans got their own customer (`service.listing_customer`). Every other checkout opened on `service.customer_id(db, user, "stripe")`, an organisation's (`payment.organisation_id` set) included, with `customer_update` {address, name: auto} and tax id collection on (`:168`). | Stripe saved the organisation's name, address and VAT id onto the buyer's own customer. |
| 2 | The person's customer | `server/app/billing/service.py:127` `customer_id`: the customer of the person's latest Stripe subscription; it skipped only `listing_*`, so organisation subscriptions counted. Its callers: the subscription checkout, the AI top-up checkout (`stripe_provider.py:235`), `org_billing.personal_scope` (`org_billing.py:136`), the personal invoice PDF link and `portal_url`'s fallback. | The buyer's own Pro and top-ups opened on the organisation's customer whenever its subscription was updated last. |
| 3 | The business flag | `stripe_provider.py:276-277` `_apply_session` marks a payment `business` when its session's customer has tax ids. | The buyer's own Pro came back `business`: PF2b offered no EU withdrawal, and Stripe Tax would treat it as a business sale. PF8b's scratch run printed it: "buyer's own Pro checkout: opens on customer cus_sim_0; … business True". |
| 4 | The portal | `stripe_provider.py:476` `portal_url` opens on `sub.provider_customer_id`; for an organisation's subscription that was the buyer's own customer. `POST /billing/portal {org_id}` (`routers/billing.py:681`). | The organisation's other billing member landed in the buyer's whole Stripe portal: their own Pro, saved cards and invoices (PF3a's Risks). |

## Goal

An organisation's Team plan is the organisation's contract, paid on the organisation's own Stripe customer with its VAT id, company name and address. The person who buys it keeps their own Pro, top-ups and invoices on their own customer, so the organisation's VAT id never makes their own Pro a business purchase and Billing keeps offering them their 14-day EU withdrawal. A billing member who opens the organisation's portal sees the organisation's subscription and invoices, never the buyer's.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* `PF3a-organisation-billing.md`: Design (attaching only from our payment row), Risks ("Paddle customers are one per e-mail"), As-built deviation 8 (`InvoiceScope`).
* `PF8b-listing-stripe-customer.md`: Design, As-built item 4 and the carry-over, the Stripe stand-in, `seed_listing_checkouts.py --pf8b`.
* `PF2b-subscription-consumer-rules.md`: `business` and the EU withdrawal.
* Code: `server/app/billing/{service,org_billing,stripe_provider}.py`, `server/app/routers/billing.py` (checkout, portal, invoices, seats, change), `server/tests/test_pf8b_listing_customer.py` (`_Stripe`), `server/tests/test_billing_orgs.py`.
* Stripe: "Collect tax IDs with Checkout" (docs.stripe.com/tax/checkout/tax-ids): with an existing customer Checkout adds the collected tax id to `customer.tax_ids`, and asks no tax id of a customer that has one; a session's `customer_details` holds the customer's tax ids.

## Scope

**In:**

1. **The organisation's customer.** A checkout for an organisation opens on that organisation's own Stripe customer when it has one (`org_billing.org_customer`). Otherwise it sends no `customer`, sends `customer_email` = the buyer's e-mail, and Stripe makes the customer. It never opens on `service.customer_id` of the buyer. A customer that also holds a subscription that is not this organisation's (a person's own, a listing plan, another organisation's; rows from before PF3e) is never reused.
2. **`service.customer_id` skips organisation subscriptions** on Stripe (`organisation_id IS NULL`), so the person's own checkouts, top-ups, personal invoices and personal portal never take an organisation's customer.
3. **Portal.** `POST /billing/portal {org_id}` opens on the organisation's own customer (its subscription's), and the personal portal on the person's own. Rows from before PF3e are not changed (As-built records what they do).
4. **Invoices.** `GET /billing/invoices?org_id=` lists only the organisation's invoices, and a person's own list leaves them out, also on a customer shared before PF3e (`personal_scope`'s exclusions kept).
5. **Seat and plan changes** for an organisation (`POST /billing/seats` and `/billing/change` with `org_id`) work unchanged on the new customer.
6. A self-test seed, `server/scripts/seed_org_checkouts.py`, that runs the app's own billing code with Stripe's side stood in for.

**Out (and where it goes):**

* **Paddle**, the default provider (`config.py:39`): one customer per e-mail, and it takes the business per transaction. `customer_id` keeps counting organisation subscriptions there (As-built, deviation 1). Whether organisation portals open only for the buyer stays PF3a's owner decision.
* PF8b's optional admin guard on `suppliers.billing_customer_id` (`routers/market_admin.py:165`) → PF7 / PF8 admin, unchanged.
* Migrating customers shared before PF3e → the owner, if any exist (As-built).
* GD5's supplier-terms text and GD7's listing prices → unchanged (PF8a's carry-overs).

## Design

**API:** no new endpoint or field. `POST /billing/checkout`, `POST /account/ai/top-ups`, `POST /billing/portal`, `GET /billing/invoices`, `POST /billing/seats` and `POST /billing/change` answer in the same shapes.

**The checkout** (`stripe_provider.py` `create_checkout`):

```python
if payment.plan.startswith(service.LISTING_TIER_PREFIX):
    customer = service.listing_customer(db, payment)                              # PF8b
elif payment.organisation_id:
    customer = org_billing.org_customer(db, payment.organisation_id, "stripe")  # PF3e: the organisation's, or None
else:
    customer = service.customer_id(db, user, "stripe")                         # the person's own
# then as before: customer + customer_update {address, name: auto}, else customer_email = user.email
```

**`org_billing.org_customer(db, org_id, provider)`:** the customers of the organisation's subscriptions at the provider, newest first. The first one that holds no subscription other than this organisation's is the answer; None makes a new one.

**Why a helper over our rows, not an `organisations.billing_customer_id` column:**
* A subscription reaches an organisation only from our own payment row and Stripe's verified state (PF3a's `owner_of`). Its `provider_customer_id` is already the organisation's customer, so the helper reads one source of truth. A column would be a second copy that has to be filled from the first paid session and kept in step, as PF8b's sync does for suppliers ("one already set wins", a logged difference).
* It finds a customer shared before PF3e with the same rows `personal_scope` already reads, so it refuses to reuse it with no backfill and no migration.
* No schema change: nothing for `_ADDED_COLUMNS`, Postgres or the merge of shared files.
* What a column would add, an admin-set customer for an organisation, nobody asked for. An organisation with no Stripe subscription row left (rows deleted by hand) gets a new customer, which is safe.

**`service.customer_id`** gains `organisation_id IS NULL` for providers in `ORG_CUSTOMER_PROVIDERS = ("stripe",)`. Paddle keeps one customer per e-mail address, so a Paddle organisation subscription is on its buyer's own customer and still counts there (deviation 1).

**The portal** (`portal_url`) opens on the subscription's own customer, as before. For an organisation's subscription from PF3e on, that is the organisation's. Its fallback for a row without a customer (the router answers 404 before it) is now `org_customer` for an organisation's subscription, never the person's.

**Invoices:** unchanged code. `org_scope` lists the customers of the organisation's subscriptions and keeps only those subscriptions' invoices. `personal_scope` takes `customer_id`, now never an organisation's customer, and keeps its exclusions for a customer shared before PF3e.

**Seats and plan changes:** unchanged code. `_apply_change` modifies the Stripe subscription by id. The customer and the organisation of the row stay as they were.

**Data:** no table, column or migration. **UI:** none. **Jobs:** none.

**Security and privacy:** nothing new is stored or sent. The customer an organisation's checkout opens on comes from our own rows. The buyer's own checkouts no longer carry the organisation's name, address and VAT id. An organisation's billing member who opens its portal sees the organisation's Stripe customer, not the buyer's cards and personal invoices.

## Deliverables

- [x] `server/app/billing/org_billing.py`: `org_customer()`; the module docstring
- [x] `server/app/billing/service.py`: `customer_id` skips organisation subscriptions on Stripe (`ORG_CUSTOMER_PROVIDERS`)
- [x] `server/app/billing/stripe_provider.py`: `create_checkout` opens an organisation's checkout on `org_customer`; `portal_url`'s fallback by kind; the module docstring
- [x] `server/tests/test_pf3e_org_stripe_customer.py` (7 test functions, 8 tests)
- [x] `server/scripts/seed_org_checkouts.py`
- [x] This doc, the PF3e row in `docs/roadmap/40/README.md`, a README section

## Tests

`_Stripe` (in the test file) stands in for Stripe's side, as PF8b's does:
* A Checkout Session runs on the customer it names, else on a new one (`cus_new_N`).
* A VAT id entered at checkout is saved onto that customer. Checkout asks no customer that already has one.
* Every session reports its customer's saved tax ids in `customer_details.tax_ids`.
* Subscriptions are in conftest's `STRIPE_SUBS`; `Subscription.modify` changes them there. Portal sessions and invoice lists record the customer they were opened for; a customer's invoices are one per subscription on it.

| Name | Kind | Asserts |
|---|---|---|
| `test_org_checkout_never_opens_on_the_buyers_own_customer` | pytest | The buyer pays their own Pro on `cus_pro`. Their Team checkout for the organisation sends `customer_email` = the buyer's address, no `customer` and no `customer_update`; `cus_pro` appears nowhere; tax id collection is on. Paid with DE123456789, the payment is `business`, the organisation's subscription is on the new customer, the VAT id is saved there only, `customer_id` stays `cus_pro`. |
| `test_org_customer_is_reused_for_the_organisation_and_never_for_another` | pytest | After the organisation's subscription ends (signed `customer.subscription.deleted`), its billing member (not the buyer) buys again: the checkout opens on the organisation's customer with `customer_update`, and Stripe asks no second VAT id. A second organisation bought by the same buyer opens on a new customer, never the first's or `cus_pro`. |
| `test_org_checkout_never_reuses_a_customer_shared_before_pf3e` | pytest | Rows from before PF3e: an organisation's ended Team on the buyer's `cus_shared`, beside the buyer's own Pro; two organisations sharing `cus_two_orgs`. The next checkout of the first, and of one of the two, opens on a new customer, and `org_customer` is None for all three. One whose old customer holds only its own subscription (`cus_alone`) reuses it. On Paddle the buyer's customer still counts an organisation's subscription. |
| `test_org_vat_id_never_makes_the_buyers_pro_business[no-customer-yet]`, `[earlier-pro]` | pytest | PF8b's scratch check, reversed, with PF2b's EU withdrawal switched on: the organisation's Team paid with DE123456789 is `business`. The buyer's own Pro then opens on their own customer (a new one, or their earlier Pro's `cus_pro`), its session reports no tax ids, the payment is not `business`, and `/billing/subscription` answers Pro with a `withdrawal_until`. The AI top-up opens on that same customer. |
| `test_org_portal_opens_on_the_organisations_customer` | pytest | A billing member who is not the buyer opens the organisation's portal on the organisation's customer (return URL `?org=`); so does the buyer. The buyer's personal portal opens on `cus_pro`; the billing member has none (404). A row from before PF3e (another organisation's Team on `cus_pro`) still opens on `cus_pro`. `portal_url`'s fallback for an organisation's row is the organisation's customer. |
| `test_org_and_personal_invoices_are_split` | pytest | The organisation's list asks Stripe for its customer only and lists its subscription's invoice, whose signed PDF link redirects to its PDF; the buyer's own list asks for `cus_pro` only and lists only their Pro's. A customer shared before PF3e still splits: that organisation lists only its invoice, the buyer's list leaves it out. |
| `test_org_seats_and_plan_changes_on_the_organisations_customer` | pytest | On the organisation's customer: seats 3 → 4 by the billing member, Team → Studio → Team (2 seats); each modifies the same Stripe subscription; the row stays the organisation's, on its customer, bought by the buyer; the buyer's own Pro on `cus_pro` is untouched. |
| PF3a, PF8b, PF8a, PF2, PF2b, PF2c, PF2d, AI top-up, PF8 and PF3 suites | pytest | unchanged and green |

## Human test

**Without Stripe keys (about 5 minutes).** `seed_org_checkouts.py` runs the app's own billing code, with Stripe's side stood in for in-process. Run it in PowerShell, in the worktree's `server\` folder.

1. Use a scratch database, with the EU withdrawal switched on:
   ```
   $env:DATABASE_URL="sqlite:///./pf3e-test.db"; $env:EU_WITHDRAWAL_ENABLED="true"
   ```
2. `.venv\Scripts\python.exe scripts\seed_org_checkouts.py --email pf3e@example.com` prints (references and the date differ):
   ```
   buyer pf3e@example.com: no Stripe customer yet; organisation PF3e Studio, billing member pf3e.billing@example.com
   organisation Team checkout tbx_…: opens on a new customer (customer_email pf3e@example.com)
     paid from DE with VAT id DE123456789 on cus_sim_1: business True
   buyer's own Pro checkout tbx_…: opens on a new customer (customer_email pf3e@example.com)
     paid from DE without a VAT id on cus_sim_2 (its saved tax ids: none): business False
     EU withdrawal for the buyer's own Pro: offered until <14 days from today> 23:59 UTC
   buyer's AI top-up checkout tbx_…: opens on customer cus_sim_2
   organisation seats 3 -> 4, by pf3e.billing@example.com: subscription sub_sim_1 on cus_sim_1
   organisation portal opened by pf3e.billing@example.com: customer cus_sim_1 (holds: Team for PF3e Studio)
   buyer's own portal: customer cus_sim_2 (holds: the buyer's own Pro)
   organisation invoices: Stripe asked for cus_sim_1; listed in_sub_sim_1
   buyer's own invoices: Stripe asked for cus_sim_2; listed in_sub_sim_2
   organisation subscription ended; Team again by pf3e.billing@example.com: opens on customer cus_sim_1
     paid from DE on cus_sim_1 (its saved tax ids: DE123456789): business True
   second organisation PF3e Studio South, Team by the buyer: opens on a new customer (customer_email pf3e@example.com)
   Stripe customers: cus_sim_1 (DE123456789); cus_sim_2 (no tax id)
   ```
   Running it again on the same database refuses: "pf3e@example.com already has PF3e Studio: delete the scratch database to run this again".
3. Optional, the API's view of the same database. Start it with placeholder Stripe keys, so the API treats Stripe as on (these reads send nothing to Stripe):
   ```
   $env:STRIPE_SECRET_KEY="sk_test_dummy"; $env:STRIPE_WEBHOOK_SECRET="whsec_dummy"; $env:BACKGROUND_TASKS="off"
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
   Then, in a second PowerShell (Windows PowerShell 5.1 needs the parentheses to list an array):
   ```
   $api = "http://127.0.0.1:8000"
   $t = (Invoke-RestMethod -Method Post "$api/auth/login" -ContentType application/json -Body '{"email":"pf3e@example.com","password":"password123"}').access_token
   $b = (Invoke-RestMethod -Method Post "$api/auth/login" -ContentType application/json -Body '{"email":"pf3e.billing@example.com","password":"password123"}').access_token
   $org = ((Invoke-RestMethod "$api/orgs" -Headers @{Authorization="Bearer $b"}) | Where-Object name -eq "PF3e Studio").id
   Invoke-RestMethod "$api/billing/subscription" -Headers @{Authorization="Bearer $t"} | Select-Object tier, withdrawal_until
   (Invoke-RestMethod "$api/billing/payments" -Headers @{Authorization="Bearer $t"}) | Select-Object plan, status, business
   (Invoke-RestMethod "$api/billing/payments?org_id=$org" -Headers @{Authorization="Bearer $b"}) | Select-Object plan, status, business
   Invoke-RestMethod "$api/billing/subscription?org_id=$org" -Headers @{Authorization="Bearer $b"} | Select-Object tier, seats, status
   ```
   * The buyer: `pro` with a `withdrawal_until` date; payments `ai_credits pending` and `pro paid False`.
   * The organisation: two `team paid True` payments; `team`, 3 seats, `active`.
4. Optional, on the site (about 5 minutes more, a local build). Stop the API, then start it again in `server\` with the approved wording and the served site's origin:
   ```
   $env:LEGAL_WORDING_APPROVED="true"; $env:CORS_ORIGINS="http://127.0.0.1:3176"
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
   In the worktree root, in another PowerShell:
   ```
   Remove-Item -Recurse -Force out; $env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; $env:NEXT_PUBLIC_LEGAL_WORDING_APPROVED="true"; npm run build
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1
   ```
   It prints the port (`http://127.0.0.1:3176/` under Autopilot T76; use the printed one in `CORS_ORIGINS`). Sign in at `/login/` as `pf3e@example.com` / `password123` → Dashboard → Billing: **Pro** with **Withdraw from contract**, and "Organisations you buy for" lists PF3e Studio and PF3e Studio South. Sign in as `pf3e.billing@example.com` and open PF3e Studio's Billing (`/dashboard/billing/?org=…`): **Team**, "Annual · 3 seats · 0 assigned". Don't press Manage: the placeholder keys reach no Stripe (502).
5. Clean up: stop the API and the server, and delete `server\pf3e-test.db`.

For contrast, on `master` (ec32911) step 2 prints:
* "buyer's own Pro checkout …: opens on customer cus_sim_1", "(its saved tax ids: DE123456789): business True", "EU withdrawal for the buyer's own Pro: not offered";
* "buyer's AI top-up checkout …: opens on customer cus_sim_1";
* both portals on cus_sim_1 "(holds: Team for PF3e Studio, the buyer's own Pro)";
* "Team again by pf3e.billing@example.com: opens on a new customer (customer_email pf3e.billing@example.com)", and the second organisation "opens on customer cus_sim_1";
* "Stripe customers: cus_sim_1 (DE123456789); cus_sim_2 (DE123456789)".
In step 3 the buyer reads `pro` with no `withdrawal_until` and `pro paid True`; in step 4 Billing shows Pro without "Withdraw from contract".

## Risks / traps

* **Rows from before PF3e** stay as they are (Scope 3); As-built lists what each does. Production is unlikely to have any: `BILLING_PROVIDER` defaults to Paddle.
* **The new customer carries the buyer's e-mail.** Stripe sends that customer's receipts there, and a later checkout by another billing member on the same customer shows that address. Organisations have no billing e-mail of their own (carry-over).
* **Paddle is unchanged.** One customer per e-mail: an organisation's Paddle subscription is on its buyer's customer, and its portal is the buyer's whole Paddle portal (PF3a's Risks, the owner's decision).
* **A Stripe customer that holds only this organisation's old subscription is reused,** also one from before PF3e (a buyer with no customer then got a new one). If that buyer also paid an AI top-up on it before PF3e, the organisation's Stripe portal shows that receipt: payments don't record their customer, so it can't be told apart.
* Never run `next dev` here (RAM). Step 4 bakes the local API and the approved wording into `out/`; the verify gate rebuilds it against `.env.local`.

## As-built

* **Date, branch, commits:** 2026-10-14, `ap/t76-pf3e-an-organisations-stripe-sub` from `master` ec32911 (its billing code is 988334f's).
  * `9582a5f`: the 8 tests, failing on the unchanged code.
  * `4b9c946`: the code and `seed_org_checkouts.py`; `28109eb`: the seed pays the re-bought Team.
  * The next commit: this doc, the tracker row and the README section.
* **Counts:** pytest collected 733 → 741 (`test_pf3e_org_stripe_customer.py`: 7 test functions, one parametrized in two: 8 tests). No public copy, page, route or schema changed.
* **Verify gate:** `scripts/autopilot-verify.ps1` green in 623 s: lint, the build (75 static pages), and pytest 724 passed and 17 skipped (Postgres-only tests and site checks that need their own build) in 462 s.
* **Tests first:** all 8 failed on the unchanged code, each on its gap:
  * the organisation's checkout named `customer: cus_pro`;
  * the organisation's first checkout ran on `cus_pro` (reuse, portal, invoice and seat tests: `'cus_pro' != 'cus_pro'`);
  * the next checkout of an organisation whose old customer is shared opened on that customer;
  * no customer yet: the buyer's own Pro opened on the organisation's `cus_new_1`.
* **The organisation's customer, how it is found:** a helper over our subscription rows (`org_billing.org_customer`), not an `organisations.billing_customer_id` column. Design gives the reasons.
* **On SQLite:** the new file with PF3a (`test_billing_orgs.py`), PF8b, PF8a, PF2 (`test_billing.py`, `test_billing_pf2.py`), PF2a, PF2b, PF2c, PF2d, the AI top-up, PF8 (`test_supplier_portal.py`), PF3 (`test_orgs.py`, `test_orgs_seats.py`, `test_orgs_usage.py`), `test_market.py` and `test_market_admin.py`: 191 passed and 1 skipped (PF2c's Postgres-only test) with the gate's `out/` built; 190 passed and 2 skipped before it (PF2d's site check too).
* **Postgres:** a throwaway Postgres 17.10 cluster (`initdb` in the session scratchpad, port 55476, `timezone = 'Asia/Baghdad'`, removed afterwards), with `TEST_APP_DATABASE_URL` and `TEST_DATABASE_URL`.
  * The new file, `test_billing_orgs.py`, `test_pf8b_listing_customer.py`, `test_pf8a_listing_consumer_rules.py`, `test_billing_pf2.py`, `test_billing_pf2b.py`, `test_pf2c_billing_tidy.py`, `test_pf2d_billing_followups.py` and `test_ai_topup_billing.py`: 110 passed and 1 skipped (PF2d's site check: "needs the static build in out/").
  * `test_billing.py`, `test_supplier_portal.py`, `test_orgs_seats.py` and PF2d again: 41 passed and 1 skipped (the same).
* **Self-test beyond pytest:**
  * `seed_org_checkouts.py` on scratch SQLite databases, on this branch and on `git archive ec32911 server` with the same script copied in: the lines in Human test step 2 and its contrast, word for word. A second run on the same database refuses.
  * Each database served by uvicorn (this branch, placeholder Stripe keys) and read over HTTP with the PowerShell lines of step 3: this branch's Pro with `withdrawal_until` 2026-10-28T23:59:59Z and `pro paid False`; the unchanged run's Pro with no `withdrawal_until` and `pro paid True`; the organisation's `team` payments `True` in both.
  * Step 4 headless: `out/` built with `NEXT_PUBLIC_AUTH_URL` and `NEXT_PUBLIC_LEGAL_WORDING_APPROVED=true`, served by `serve-out.py`, driven in headless Edge over CDP. This branch's database: the buyer's Billing shows Pro and "Withdraw from contract", "Organisations you buy for" lists both; PF3e Studio's Billing for the billing member shows Team, "Annual · 3 seats · 0 assigned"; no browser errors. The unchanged run's database: no "Withdraw from contract".
* **Deviations and why:**
  1. *Paddle keeps counting organisation subscriptions in `customer_id`* (`ORG_CUSTOMER_PROVIDERS = ("stripe",)`), where Scope 2 names no provider. A Paddle customer is one per e-mail, so there the organisation's subscription is on the buyer's own customer anyway. Skipping it would change nothing in the checkout but an extra customer lookup, and it would empty the personal invoice list of a buyer whose only Paddle subscription is an organisation's (their own top-up invoices are on that customer). Paddle is Out.
  2. *`org_customer` refuses a customer shared with any subscription that is not this organisation's*: a person's own (as Scope 1 asks), but also a listing plan and another organisation's. Two organisations bought by one person before PF3e can share a customer; reusing it would mix their invoices in Stripe's portal.
  3. *`portal_url`'s fallback* for a subscription row without a customer is the organisation's customer for an organisation's row. The router answers 404 before it, so this only keeps the adapter from ever naming the buyer's customer for an organisation.
  4. *A new seed script, not a block in `seed_listing_checkouts.py`*: one command seeds and runs everything, so the human test is one line; the listing script stays PF8a/PF8b's.
* **Rows from before PF3e (Scope 3, recorded, not changed):** an organisation's Stripe subscription on its buyer's own customer.
  * It stays there. Its portal still opens on that customer, so on the buyer's whole Stripe account (PF3a's Risks). Seat and plan changes act on it as before.
  * Its invoices: the organisation's list keeps only its own subscriptions' (`org_scope`), and the buyer's own list leaves them out (`personal_scope`'s exclusions).
  * The organisation's next checkout opens on a new customer, so from its next subscription on it pays on its own.
  * The buyer's own checkouts and top-ups open on their own subscription's customer (the shared one while their own Pro is on it). A buyer whose only Stripe subscription is such an organisation's now has no customer from `customer_id`: their next Pro or top-up opens on a new customer, and their personal invoice list has no Stripe invoices (as for anyone without a Stripe subscription of their own).
* **Contract:** none to update.
* **Carry-over → which feature:**
  * **PF8b's "PF3a follow-up" carry-over: done here.**
  * **Owner (PF3a):** whether organisation portals open only for the buyer, now only for Paddle and for Stripe rows from before PF3e. Migrating shared Stripe customers, if any exist (none expected while Paddle is the default).
  * **PF3a / owner:** a billing e-mail for an organisation, for its new Stripe customer's receipts (now the buyer's).
  * **PF2 / PF11:** a person with no Stripe subscription of their own gets a new Stripe customer for each AI top-up, and their invoice list shows none of them. This was so before for members; it now also holds for a buyer of an organisation. Recording the customer on the payment would fix it.
  * **PF7 / PF8 admin (optional):** PF8b's guard on `suppliers.billing_customer_id` (`market_admin.py:165`), unchanged.
  * **GD7 / owner** (`listing_<plan>` prices) and **GD5 / owner** (the supplier-terms text) are PF8a's, unchanged.
