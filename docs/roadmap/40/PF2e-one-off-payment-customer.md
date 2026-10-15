# PF2e — A person's one-off payments record their provider customer (launch priority 2)

**Needs merged:** PF2 (billing), PF2c (one-off items in the payment history, the Stripe pack checkout), PF3a (`org_scope`, `personal_scope`), PF3e (an organisation's Stripe customer), PF11 (AI credit packs). All are on `master` cc905d3. **Unblocks:** AI credit pack invoices in Billing for people who buy packs without a subscription of their own, and one Stripe customer per person for their packs. **Contract:** none. One nullable column is added (`payments.provider_customer_id`); no endpoint, field or switch, and `contracts/` is unchanged.

## Status

**Built (2026-10-15, branch `ap/t82-pf2e-a-persons-one-off-payments`, Autopilot T82); see As-built.** This was PF3e's carry-over "PF2 / PF11" (PF3e As-built: "a person with no Stripe subscription of their own gets a new Stripe customer for each AI top-up, and their invoice list shows none of them … Recording the customer on the payment would fix it"). Each point was checked on `master` cc905d3; it also held on Paddle, the default provider (`config.py:39`):

| # | Gap | Where (cc905d3) | Then |
|---|---|---|---|
| 1 | Who buys packs | `server/app/ai/topups.py:41` `start`: a pack needs `ai.metered`, "AI credits come with Pro, Studio, Team and the trial". | Team members on a seat and trial users buy packs with no subscription row of their own. |
| 2 | The person's customer | `server/app/billing/service.py:127` `customer_id` read only the person's own subscriptions (not `listing_*`, and on Stripe not an organisation's since PF3e). | None for those people. |
| 3 | Invoices | `org_billing.py:176` `personal_scope` started from `customer_id`; GET `/billing/invoices` (`routers/billing.py:596`, `:612`) skips a provider without a scope. | No pack invoice listed, on Paddle or Stripe. |
| 4 | The PDF link | `routers/billing.py:638` `invoice_pdf` passed scope None for a personal link; `stripe_provider.py:552` and `paddle_provider.py:594` then matched the invoice against `customer_id` only. | Every pack's PDF refused for these people. On Paddle, a personal link signed for a buyer to their organisation's Team invoice (on their own customer) would have opened; no list signs one, so it was a mismatch, not a leak. |
| 5 | Stripe | `stripe_provider.py:214` `create_one_time_checkout` sends `customer_email` with no customer, and Stripe makes a customer for the session (`invoice_creation`); `_apply_session` (`:260-300`) kept amount, tax, invoice, country and business, not `customer`. | A new Stripe customer per pack, never found again. |
| 6 | Paddle | `paddle_provider.py:163` `_customer_id` falls back to POST then GET `/customers?email=`, so packs land on the one e-mail customer; `_apply_transaction` (`:289-330`) did not keep the transaction's `customer_id`. | `personal_scope` still never found it. |
| 7 | Data | `server/app/models.py:184` `Payment` had no customer column. | — |

## Goal

A person who buys AI credit packs without a subscription of their own (a trial user, a Team member on a seat, the buyer of an organisation whose only Stripe subscription is the organisation's) sees every pack's VAT invoice in Billing and can open its PDF. Their second Stripe pack opens on the customer of the first, so each person has one Stripe customer for their packs (and their later Pro), not one per pack. An organisation's invoice list never shows a person's packs.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* `PF3e-organisation-stripe-customer.md`: Design, As-built (deviations 1 and 2, the carry-over), `server/tests/test_pf3e_org_stripe_customer.py` (`_Stripe`, `on_stripe`).
* `PF3a-organisation-billing.md`: `org_scope`, `personal_scope`, attaching an organisation only from our payment row.
* `PF2c-billing-tidy-ups.md`: `service.ONE_OFF_ITEMS`, `ONE_OFF_DETAILS`. PF11: `server/app/ai/topups.py`.
* `server/tests/test_ai_topup_billing.py`, `server/tests/mock_paddle.py` (GET `/transactions` lists by `customer_id`), `server/tests/org_helpers.py`.

## Scope

**In:**

1. **Record the customer.** A nullable `payments.provider_customer_id` (VARCHAR(128)) in its own PF2e block of `_ADDED_COLUMNS` and on the model, filled only from the provider's verified state when a payment is marked paid: Stripe's session `customer` (an id or an expanded object, `_id_of`), Paddle's transaction `customer_id`. Every paid payment records it; Scope 2 decides which rows are read.
2. **The person's own customer.** With no subscription of their own with a customer at a provider, `service.customer_id` answers the customer of their latest paid one-off payment there (plan in `ONE_OFF_ITEMS`, `organisation_id IS NULL`). Never a listing or organisation payment's, and on Stripe never a customer that holds a subscription that is not the person's own (PF3e's invariant). So the Stripe pack checkout, Paddle's `_customer_id`, a later Pro checkout and the portal fallback all get the same answer. A person with their own subscription keeps exactly the answer they had.
3. **Invoices.** `personal_scope` covers the subscription's customer plus every customer recorded on the person's own paid one-off payments there, deduplicated, with PF3a's exclusions kept. The personal PDF link checks the invoice against that same scope. `org_scope` and organisation PDFs are unchanged, so they never include a person's packs.
4. **Rows from before PF2e** are not back-filled (As-built says what such a person sees).
5. A self-test seed, `server/scripts/seed_one_off_customers.py`.

**Out (and where it goes):**

* Back-filling payments from before PF2e → the owner, only if live packs exist (none expected while GD7's prices are placeholders).
* Wayl, which has no invoice list → unchanged.
* A billing e-mail for an organisation, and whether organisation portals open only for the buyer → PF3a / the owner.
* Paddle's one customer per e-mail, and organisation subscriptions on a Paddle buyer's customer (PF3e deviation 1) → unchanged.
* PF8b's optional admin guard on `suppliers.billing_customer_id` → PF7 / PF8 admin. GD7's prices and tier limits → the owner.

## Design

**API:** no new endpoint or field. GET `/billing/invoices` lists more for the people above; GET `/billing/invoices/{id}/pdf` without `o` checks against `personal_scope`; `POST /account/ai/top-ups`, `POST /billing/checkout` and `POST /billing/portal` answer in the same shapes. The customer id is never sent to the browser.

**Recording** (`stripe_provider._apply_session`, `paddle_provider._apply_transaction`), in the paid branch beside `invoice_id` and `provider_subscription_id`:

```python
payment.provider_customer_id = _id_of(session.get("customer")) or payment.provider_customer_id      # Stripe
payment.provider_customer_id = str_or_none(txn.get("customer_id")) or payment.provider_customer_id  # Paddle
```

**`service.one_off_customers(db, user, provider)`:** the recorded customers of the person's own paid payments whose plan is in `ONE_OFF_ITEMS` and `organisation_id IS NULL`, newest first (`paid_at`), deduplicated. On `ORG_CUSTOMER_PROVIDERS` (Stripe) it drops a customer that holds a subscription with an organisation, a listing plan, or another person's.

**`service.customer_id`** keeps its query. When it finds no subscription, it answers `one_off_customers(...)[0]` (or None). Why there and not in each caller: the Stripe pack and Pro checkouts, Paddle's `_customer_id`, `personal_scope` and `portal_url`'s fallback all read it, so they cannot disagree.

**`org_billing.personal_scope`:** `customers = (customer_id, *one_off_customers)` deduplicated; the exclusions (organisation subscriptions on any of those customers, the person's own organisation checkouts) are PF3a's. The adapters' `list_invoices` and `invoice_pdf_url` called without a scope now use `personal_scope` too, so no path matches an invoice against `customer_id` alone.

**`org_billing.org_customer`** also refuses a customer that a payment which is not this organisation's was paid on (a person's pack), as it refuses one shared with another subscription.

**Data:** `payments.provider_customer_id VARCHAR(128) NULL`, added by `_migrate` (SQLite and Postgres), no index (read by `user_id`, which is indexed). **UI:** none (Billing's Invoices panel already lists what the API returns). **Jobs:** none.

**Security and privacy:** the customer id comes only from the provider's verified state (a signed webhook, or a fetch of our own session or transaction). Its only effect is which customer a person's own checkouts open on and which invoices their list shows. The organisation and listing exclusions keep a person's list and PDF links from reaching an organisation's or a supplier's customer. The PDF link now also applies the exclusions, so a Paddle buyer's personal link to their organisation's Team invoice is refused (it opens through the organisation's link).

## Deliverables

- [x] `server/app/models.py` (`Payment.provider_customer_id`), `server/app/database.py` (PF2e `_ADDED_COLUMNS` block)
- [x] `server/app/billing/stripe_provider.py` and `paddle_provider.py`: record the customer; scope-less fallbacks use `personal_scope`
- [x] `server/app/billing/service.py`: `one_off_customers`, `customer_id`'s fallback
- [x] `server/app/billing/org_billing.py`: `personal_scope` over every own customer; `org_customer` refuses a pack's customer
- [x] `server/app/routers/billing.py`: the personal PDF link checks `personal_scope`
- [x] `server/tests/test_pf2e_one_off_customer.py` (7 test functions, 8 tests)
- [x] `server/scripts/seed_one_off_customers.py`
- [x] This doc, the PF2e row in `docs/roadmap/40/README.md`, a README section

## Tests

Paddle is `tests/mock_paddle.py` in-process (the `paddle` fixture). Stripe is PF3e's `_Stripe` subclassed in the test file: a one-off (payment mode) session runs on the customer it names, else on a new `cus_new_N`; the completed session reports its `customer`; a customer's invoice list and `Invoice.retrieve` include its packs' invoices. PF3e's tests are unchanged.

| Name | Kind | Asserts |
|---|---|---|
| `test_paddle_pack_of_a_trial_user_is_on_their_invoices` | pytest | A Pro trial (no subscription row at Paddle) buys a pack; after the signed `transaction.completed` the payment carries the mock's customer for their e-mail, `customer_id` and `personal_scope` name it, GET `/billing/invoices` lists exactly that transaction (its invoice number) and its `pdf_url` redirects (302) to the PDF. Another trial user's pack is on their list only; personal links signed for the other person are refused (404) both ways. |
| `test_paddle_team_members_pack_is_theirs_not_the_organisations` | pytest | The buyer pays Team x3 on Paddle; a member on a named seat buys a pack on their own customer. The member's list is the pack, the organisation's (`?org_id=`) the Team invoice, the buyer's own empty; each listed PDF opens. Personal links to the Team invoice (member's and buyer's, though it is on the buyer's own customer) and the buyer's to the member's pack are refused. |
| `test_stripe_packs_of_an_organisation_buyer_share_one_customer` | pytest | The buyer's only Stripe subscription is the organisation's (on its own customer, PF3e) and they hold a seat. Pack 1 sends `customer_email` and records the new customer; pack 2 opens on it (`customer_update` set, no `customer_email`) and no customer is made. The buyer's list asks Stripe for that customer only and lists both pack invoices, each PDF opens; the organisation's asks for its own customer and lists only its Team invoice; a personal link to it is refused. After the Team ends, the billing member's checkout opens on the organisation's customer, never the packs'. |
| `test_stripe_pack_with_own_pro_opens_on_the_pros_customer` | pytest | Own Pro on `cus_pro`: the pack opens on `cus_pro`, records it, no new customer, and `personal_scope` equals what it was before the pack; the list asks for `cus_pro` only and holds the Pro's and the pack's invoices. |
| `test_stripe_pro_after_a_pack_opens_on_the_packs_customer` | pytest | A trial user's first pack makes their Stripe customer; their Pro checkout and next pack open on it; their list asks for it only and holds both invoices. |
| `test_customer_id_ignores_listing_and_organisation_payments` | pytest | Paid rows of a listing plan, an organisation's Team, a one-off row naming an organisation, a plan's checkout, an unpaid pack, another person's pack and a pack with nothing recorded give no Stripe customer and no scope; a Paddle pack counts on Paddle only. Then the latest of two packs wins and the scope holds both, newest first (exclusions as before). A newer pack on a customer an organisation's subscription uses is ignored on Stripe, and that customer is no longer the organisation's (`org_customer` None). The person's own (ended) Pro on `cus_pro` wins again; the scope is `cus_pro` then both pack customers. |
| `test_pf2e_column_added_by_init_db[sqlite]`, `[postgresql]` | pytest (Postgres: `TEST_DATABASE_URL`) | A database whose `payments` table is master's (the column dropped) gains `provider_customer_id` (nullable, VARCHAR(128)) at `init_db`; the old row reads NULL; a second `init_db` runs no `ALTER`. |
| PF2, PF2a, PF2b, PF2c, PF2d, PF3, PF3a, PF3e, PF8, PF8a, PF8b, AI top-up, marketplace suites | pytest | unchanged and green |

## Human test

**About 10 minutes, no provider keys:** the seed runs the app's own billing code against the Paddle mock (and Stripe's stand-in in-process), the API serves the same database, and Billing shows the invoice row. Use Windows PowerShell; replace nothing unless a step says so.

1. **The Paddle stand-in.** PowerShell window 1, in the worktree's `server\` folder; leave it running:
   ```
   .venv\Scripts\python.exe -m uvicorn tests.mock_paddle:app --port 8098
   ```
2. **The seed.** PowerShell window 2, in `server\`:
   ```
   $env:DATABASE_URL="sqlite:///./pf2e-test.db"; $env:PADDLE_API_BASE="http://127.0.0.1:8098"
   .venv\Scripts\python.exe scripts\seed_one_off_customers.py --email pf2e@example.com
   ```
   It prints (ids, references and the year differ):
   ```
   Paddle, the default provider (http://127.0.0.1:8098)
   trial user pf2e@example.com: Pro trial, no subscription of their own
     AI pack tbx_… (transaction txn_A): paid; the payment records customer ctm_T
   organisation PF2e Studio: Team x3 bought by pf2e.buyer@example.com: paid, subscription sub_… on ctm_B
     pf2e.member@example.com on a named seat: AI pack tbx_… (transaction txn_M): paid; the payment records customer ctm_M
   invoice lists (GET /billing/invoices):
     pf2e@example.com: Paddle asked for ctm_T; listed txn_A (pf2e@example.com's AI pack)
     pf2e.member@example.com: Paddle asked for ctm_M; listed txn_M (pf2e.member@example.com's AI pack)
     PF2e Studio (?org_id=): Paddle asked for ctm_B; listed txn_… (Team for PF2e Studio)
     pf2e.buyer@example.com: Paddle asked for ctm_B; listed none
   Stripe (stood in for in this process)
   pf2e.stripe@example.com: Team x3 for PF2e Stripe Studio on cus_sim_1 (paid), their only Stripe subscription; they hold one of its seats
     first AI pack tbx_…: opens on a new customer (customer_email pf2e.stripe@example.com)
       paid; the payment records customer cus_sim_2
     second AI pack tbx_…: opens on customer cus_sim_2
       paid; the payment records customer cus_sim_2
     pf2e.stripe@example.com's own invoices: Stripe asked for cus_sim_2; listed in_pack_1 (pf2e.stripe@example.com's AI pack), in_pack_2 (pf2e.stripe@example.com's AI pack)
     PF2e Stripe Studio's invoices: Stripe asked for cus_sim_1; listed in_sub_sim_1 (Team for PF2e Stripe Studio)
     PF2e Stripe Studio's Team ended; Team again: opens on customer cus_sim_1
   pf2e.pro@example.com: their own Pro on cus_sim_3 (paid)
     AI pack tbx_…: opens on customer cus_sim_3
       paid; the payment records customer cus_sim_3
     pf2e.pro@example.com's own invoices: Stripe asked for cus_sim_3; listed in_sub_sim_2 (pf2e.pro@example.com's own Pro), in_pack_3 (pf2e.pro@example.com's AI pack)
   Stripe customers made: 3
     cus_sim_1: Team for PF2e Stripe Studio
     cus_sim_2: an AI pack, an AI pack
     cus_sim_3: pf2e.pro@example.com's own Pro, an AI pack
   ```
   Running it again on the same database refuses: "pf2e@example.com already bought a pack: delete the scratch database to run this again".
3. **The API**, in the same window 2 (DATABASE_URL and PADDLE_API_BASE are still set):
   ```
   $env:PADDLE_API_KEY="pdl_mock"; $env:PADDLE_WEBHOOK_SECRET="pdl_ntfset_mock_secret"; $env:BACKGROUND_TASKS="off"; $env:CORS_ORIGINS="http://127.0.0.1:3182,http://127.0.0.1:3100"
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
4. **Over HTTP.** PowerShell window 3 (the parentheses make Windows PowerShell 5.1 list the array):
   ```
   $api = "http://127.0.0.1:8000"
   $t = (Invoke-RestMethod -Method Post "$api/auth/login" -ContentType application/json -Body '{"email":"pf2e@example.com","password":"password123"}').access_token
   (Invoke-RestMethod "$api/billing/invoices" -Headers @{Authorization="Bearer $t"}) | Select-Object number, total_minor, tax_minor, currency, status
   $inv = (Invoke-RestMethod "$api/billing/invoices" -Headers @{Authorization="Bearer $t"})[0]
   curl.exe -s -o NUL -w "%{http_code} %{redirect_url}`n" "$api$($inv.pdf_url)"
   ```
   One invoice: number `<year>-00001`, `720`, `120`, `GBP`, `completed`; then `302 http://127.0.0.1:8098/invoices/txn_….pdf`.
5. **On the site.** Window 4, in the worktree root (the verify gate's `out/` points at the production API, so rebuild; about 3 minutes):
   ```
   Remove-Item -Recurse -Force out -ErrorAction SilentlyContinue; $env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; npm run build
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1
   ```
   It prints the port (`http://127.0.0.1:3182/` under Autopilot T82, `3100` without it; both are in `CORS_ORIGINS`). Open `/login/`, sign in as `pf2e@example.com` / `password123`, then Dashboard → Billing. **Invoices** has one row: today's date, `<year>-00001`, **£7.20**, tax **£1.20**, **Download**. Download opens the mock's one-page PDF "Invoice <year>-00001 … Customer: ctm_…".
   Optional: as `pf2e.member@example.com` the row is `<year>-00003`; as `pf2e.buyer@example.com` their Invoices say "No invoices yet.", and the **Billing** link beside PF2e Studio under "Organisations you buy for" opens the organisation's Billing, whose Invoices list `<year>-00002`, **£4,284.00**.
6. Clean up: stop the API, the mock and the site server; delete `server\pf2e-test.db`. To run the seed again, restart the mock too (it keeps one customer per e-mail).

For contrast, on `master` (cc905d3) step 2 prints "the payment records customer (no such column)", "pf2e@example.com: no customer, so Paddle is not asked; listed none" (the member's likewise), "second AI pack …: opens on a new customer (customer_email pf2e.stripe@example.com)", "pf2e.stripe@example.com's own invoices: no customer, so Stripe is not asked; listed none" and "Stripe customers made: 4". Step 4 lists nothing, and Billing says "No invoices yet."

## Risks / traps

* **Rows from before PF2e** have no customer: see As-built, Scope 4.
* **Stripe for a person whose only Stripe customer was made by a pack:** their next Pro opens on the pack's customer. That is the intent (one customer per person); a VAT id entered at that Pro's checkout is then saved on the same customer as their packs, as it already was for a Pro bought first.
* **Two databases on one Paddle mock:** the mock sends webhooks to `MOCK_PADDLE_WEBHOOK_URL` (default `127.0.0.1:8000`). A seed run against another database while an API on that port serves this one delivers that run's events here, and `custom_data.user_id` names a person of the other database (PF3a's trust model: claims say whom to credit). The self-test met this once; run one seed per mock, and restart the mock between runs.
* Never run `next dev` here (RAM). Step 5 bakes the local API into `out/`; the verify gate rebuilds it.

## As-built

* **Date, branch, commits:** 2026-10-15, `ap/t82-pf2e-a-persons-one-off-payments` from `master` cc905d3.
  * `5187db4`: the 8 tests, failing on the unchanged code.
  * `7720481`: the column and the recording (Scope 1).
  * `e4b830d`: `customer_id`'s fallback, `personal_scope`, the PDF link, `org_customer` (Scopes 2 and 3); it also corrects one assertion of `test_customer_id_ignores_listing_and_organisation_payments`, which had expected no exclusions in a scope that holds the person's organisation checkouts.
  * `dd58d27`: `seed_one_off_customers.py`.
  * The next commit: this doc, the tracker row, the README section and a docstring line in `stripe_provider.py`.
* **Counts:** pytest collected 824 → 832 (`test_pf2e_one_off_customer.py`: 7 test functions, one parametrized in two; test functions 755 → 762). One column, no endpoint, page, public copy or route.
* **Verify gate:** `scripts/autopilot-verify.ps1` green in 1,124 s: lint, the build (75 static pages), and pytest 814 passed and 18 skipped (Postgres-only tests and site checks that need their own build) in 740 s.
* **Tests first:**
  * On the unchanged code: 7 failed, each at its first read or write of `provider_customer_id` (AttributeError, TypeError on `Payment(...)`, and SQLite's "no such column" for the DROP), and the Postgres one skipped (no `TEST_DATABASE_URL`; not run on the unchanged code).
  * With only Scope 1 (`7720481`), the 5 behaviour tests still failed on their gaps: the trial user's `customer_id` None; the member's list `[]`; the second Stripe pack without `customer` (it sent `customer_email`); the Pro after a pack without `customer`; `customer_id(paddle)` None. The own-Pro and migration tests passed there (they are about recording).
* **On SQLite:** the new file with PF3e, PF3a (`test_billing_orgs.py`), PF8b, PF8a, PF2 (`test_billing.py`, `test_billing_pf2.py`), PF2a, PF2b, PF2c, PF2d, the AI top-up, PF8 (`test_supplier_portal.py`), PF3 (`test_orgs.py`, `test_orgs_seats.py`, `test_orgs_usage.py`), `test_market.py` and `test_market_admin.py`: 197 passed, 3 skipped (Postgres-only and PF2d's site check).
* **Postgres:** a throwaway Postgres 17.10 cluster (`initdb` in the session scratchpad, port 55482, `timezone = 'Asia/Baghdad'`, removed afterwards) with `TEST_APP_DATABASE_URL` and `TEST_DATABASE_URL`:
  * the new file (both migration tests ran and passed), PF3e, `test_billing_orgs.py`, PF8b, PF8a, `test_billing_pf2.py`, `test_billing_pf2b.py`, PF2c, PF2d and the AI top-up: 118 passed, 1 skipped (PF2d's site check: "needs the static build in out/");
  * `test_billing.py`, `test_pf2a_prices.py`, `test_supplier_portal.py`, `test_orgs_seats.py`: 45 passed.
* **Self-test beyond pytest:**
  * `seed_one_off_customers.py` on scratch SQLite databases with the mock in-process, on this branch and on `git archive cc905d3 server` with the same script copied in: Human test step 2 and its contrast. Then against `tests.mock_paddle` served by uvicorn (port 18182): the same lines; a second run on the same database refuses.
  * That database served by uvicorn (this branch, port 18082, Paddle only): over HTTP the trial user's `/billing/invoices` is the pack's invoice (`2026-00001`, 720, tax 120), its signed PDF link answers 302 to the mock's PDF (200, `application/pdf`, "Invoice 2026-00001 … Customer: ctm_…"); the member's is their pack; PF2e Studio's is the Team invoice; the buyer's own `[]`. Master's code on its own seeded database (port 18083): both lists `[]`, the trial user's own pack link 404. The Human test's PowerShell lines ran as written (against port 18082).
  * Headless Edge over CDP on `out/` built with `NEXT_PUBLIC_AUTH_URL` (moved to the scratchpad, served by `serve-out.py`): 9 of 9 checks. The trial user's Billing lists `2026-00001 | £7.20 | £1.20 | Download`; Download answers 302 and the PDF opens; the member's lists `2026-00003`; PF2e Studio's (`?org=`) `2026-00002 | £4,284.00`; the buyer's own "No invoices yet."; no browser errors.
  * One run first showed an extra invoice on the buyer's own list: the master contrast seed, run against the same mock while this branch's API listened on the mock's webhook URL, had delivered its `subscription.created` (naming `user_id` 2 of the other database) here. A fresh mock and database gave the results above (Risks).
* **Deviations and why:**
  1. *`org_customer` also refuses a customer a payment that is not this organisation's was paid on.* PF3e's Risks noted that a buyer's top-up on an organisation's customer from before PF3e could not be told apart because payments recorded no customer; from PF2e on they do. A pack's customer is "anything else" in `org_customer`'s rule. The forward flow is unchanged (an organisation's own payments carry its id).
  2. *On Stripe, a recorded customer that holds a listing plan's or another person's subscription is dropped too,* where Scope 2 names organisation subscriptions. Same reason as PF3e deviation 2: the person's customer is only their own.
  3. *The adapters' `list_invoices` and `invoice_pdf_url` without a scope use `personal_scope`,* not only the router's PDF branch, so no path compares an invoice with `customer_id` alone (the supplier statement link always passes its own scope).
  4. *A new seed script, not a `--pf2e` block in `seed_org_checkouts.py`:* the HTTP and site steps need the Paddle mock running as a server, which PF3e's script does not use. It reuses PF3e's `_StripeStandIn`.
  5. *Plan and listing payments record their customer too* (Scope 1 allows it); only one-off rows are read.
* **Rows from before PF2e (Scope 4, not back-filled):** a pack paid before PF2e has no recorded customer.
  * A person with a subscription of their own sees what they saw before: their subscription's customer is listed, and packs paid on it are on it.
  * A trial user, a seat holder or an organisation buyer without their own subscription sees no pack invoices until their next pack; that pack's invoice is then listed. On Stripe that next pack opens on a new customer once more, and every pack after it on that customer.
  * The return-page refresh (POST `/billing/payments/{reference}/refresh`) re-checks only pending payments and paid ones waiting for their subscription (PF2d), and the daily reconcile only those, so neither fills the column for a pack already paid. A pack still pending when PF2e is deployed gets its customer when its webhook or refresh arrives.
  * No live payments are expected while GD7's prices are placeholders.
* **Contract:** none to update.
* **Carry-over → which feature:**
  * **PF3e's "PF2 / PF11" carry-over: done here.**
  * **Owner:** back-filling pack payments from before PF2e, only if live ones exist.
  * **PF3a / owner:** a billing e-mail for an organisation; whether organisation portals open only for the buyer (Paddle, and Stripe rows from before PF3e).
  * **PF7 / PF8 admin (optional):** PF8b's guard on `suppliers.billing_customer_id`, unchanged.
  * **GD7 / owner:** prices and tier limits, unchanged.
