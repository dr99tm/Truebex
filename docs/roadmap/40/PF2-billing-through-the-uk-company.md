# PF2 — Billing through the UK company (launch priority 1)

**Needs merged:** PF1. **Unblocks:** none by Needs; PF6, PF8 and PF11 charge through its interface. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\licence-api.md` (the app sees billing only through the entitlement PF1 signs).

## Status

Stripe subscriptions and Wayl 30-day links exist; no tax handling, one monthly price, no seats, no invoices. Verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Catalogue endpoint | `server/app/routers/billing.py:41` (`catalog`), `:49` (`price_iqd`), `:31` (`_enabled_providers`) | lists `stripe` and `wayl` when keyed |
| Checkout | `server/app/routers/billing.py:91-132`; amount `:107-109` | one `pro` price in USD, or IQD for Wayl |
| Return check | `server/app/routers/billing.py:136`, `:148` | server-side re-check for Wayl only |
| Portal, webhooks | `server/app/routers/billing.py:158`, `:172` (Stripe, signed), `:188` (Wayl) | |
| Stripe adapter | `server/app/billing/providers.py:27` (status map), `:39` (enabled needs `STRIPE_PRICE_PRO`), `:43` (Checkout), `:48` (one line item), `:54` (promotion codes), `:65` (portal), `:101` (webhook verify), `:93` (plan from metadata) | no tax, no annual, no quantity |
| Wayl adapter | `server/app/billing/providers.py:139-215` | IQD links, 30-day periods (`server/app/billing/service.py:20`, `:78`) |
| State rules | `server/app/billing/service.py:4-9`; `:109` (`upsert_stripe_subscription`); `:141` (`stripe_customer_id`) | a plan changes only from a verified event |
| Settings | `server/app/config.py:34-37` (Stripe), `:40-47` (Wayl) | |
| Schemas | `server/app/schemas.py:88` (`Provider = Literal["stripe", "wayl"]`), `:91-98` (`PlanOut.price_iqd` at `:95`), `:106` | |
| Money | `server/app/models.py:125` (`Payment`), `:141-142` (USD cents or whole IQD) | |
| Billing page | `src/app/dashboard/billing/page.tsx:30-33` (provider copy incl. Wayl), `:75` (`startCheckout("pro", …)`), `:121-123`, `:189`, `:198`, `:230` (Wayl strings) | |
| Site client | `src/lib/developer.ts:31` (`Provider`), `:37` (`price_iqd`), `:88-89` (`formatMoney` special-cases USD only) | |
| Copy | `src/lib/constants.ts:340-341` (FAQ "How can I pay?"), `src/app/terms/page.tsx:36-51` ("Paid plans", Wayl at `:44`), `src/app/privacy/page.tsx:73-74`, `README.md:293-329`, brand rule `.claude/skills/truebex-brand-voice/SKILL.md:73` | |
| Tests | `server/tests/test_billing.py:51` (asserts `{stripe, wayl}` and `price_iqd`), `:64-110` (Wayl), `:167-172` (Stripe); `server/tests/conftest.py:13-18` (keys for both) | |

What the owner meant: app-side `00-understanding.md` §1; request lines "by creating uk comapany and open all things from that point so no iraq in the calcualtions" and "i want to sell globally from the launch" (verbatim) (`00-request.md:29`, `:31`).

## Goal

People anywhere buy Free → Pro, Studio, Team (per seat) or Enterprise monthly or annually from the UK company, with the right VAT or sales tax on a proper invoice, the consumer cancellation rules respected at checkout, the founding offer counted down, coupons accepted, and seats, renewals and cancellations kept in step by verified webhooks; Wayl disappears from what people see. Human test seed: "buy Pro on a test card, see the entitlement unlock in the app, download the invoice".

## Read first

* `docs/roadmap/40/00-contract.md` (P.3 item 3: a plan changes only from an event the server verified itself); PF1 (catalogue, `subscriptions.seats`, entitlements, `require_admin`).
* **`contracts/licence-api.md` v1.0.0** (2026-10-09): PF2 adds no app-facing endpoint; what billing changes reaches the app through PF1's entitlement (§6.1: `plan`, `seat_kind`, `plan_period_end`, `trial`) and the Account panel (5.7: `seats {total, assigned}`, `manage_url`); `test_plan_change_reaches_entitlement` (§10) is the joint proof. Contract 5.6 answers 409 `plan_active` to a trial request on a paid plan, so a purchase ends the trial offer.
* `guides/GD5-*.md` (VAT, invoices, consumer rights, the EULA) and `guides/GD7-*.md` (prices, founding seats, discounts) do not exist yet: amounts are placeholders `from GD7`, legal wording `from GD5`.
* Sources for the decision below (read 2026-10-09): Paddle pricing (paddle.com/pricing) and acceptable use policy (paddle.com/support/aup); Stripe UK pricing (stripe.com/gb/pricing) and Stripe Tax pricing (stripe.com/tax/pricing); GOV.UK "VAT registration: when to register" (£90,000); the EU VAT one-stop shop (non-Union scheme) and Council Directive 2006/112/EC Art. 59c (the €10,000 threshold applies only to suppliers established in one Member State); the Consumer Contracts Regulations 2013 reg. 37; the Digital Markets, Competition and Consumers Act 2024 subscription rules (not in force on 2026-10-09; GD5 confirms the date).
* Skills: `truebex-brand-voice` (payments copy), `truebex-seo` (no public page here beyond copy).

## Scope

**In:**
1. One billing-service interface (`BillingProvider`, table below) with adapters `paddle` (new, the default), `stripe` (upgraded) and `wayl` (dormant); `BILLING_PROVIDER` picks the one offered at checkout.
2. Paddle adapter: transactions opened with Paddle.js on `/checkout/`, subscriptions carrying `custom_data` (user, reference, organisation once PF3 lands), webhook signature verification, customer-portal sessions, seat and plan changes with proration, invoice PDFs, discounts.
3. Stripe adapter upgraded: Stripe Tax (`automatic_tax`), billing address and tax-ID collection, monthly and annual prices per tier, quantity = seats, `consent_collection` for the cancellation waiver, invoice listing; the current monthly Pro price keeps working for existing subscribers.
4. Monthly and annual prices per tier and per currency (GBP, USD, EUR; amounts `from GD7`) in `server/app/catalogue.json`, mirrored to provider prices by `server/scripts/sync_prices.py` into `provider_prices`.
5. Seats: per-seat tiers (Team; Studio if GD7 says so) bought with a quantity; `POST /billing/seats` changes it with proration; webhooks write `subscriptions.seats` (PF1) so the Account panel (contract 5.7) and the device limit carry the count.
6. The founding offer: a fixed number of founding seats (`from GD7`) with a lasting discount, counted on the server, held 30 minutes per checkout, the remaining count shown on the billing and pricing pages.
7. Coupons: provider-managed codes accepted at checkout; a `?code=` on links passed through.
8. VAT invoices: `GET /billing/invoices` lists them with a PDF link; the dashboard downloads them.
9. Consumer cancellation consent at checkout: a required, versioned consent and acknowledgement (reg. 37) before the provider page opens, stored on the payment; Stripe's own consent box mirrors it.
10. Webhooks keep subscriptions and seats in step (created, updated, renewed, past due, paused, cancelled, payment failed), idempotent by event id, ordered by event time.
11. The customer portal for cards and cancellation, for both adapters.
12. Wayl removed from the UI and the plan catalogue: `/billing/plans` stops listing `wayl` and `price_iqd`; the billing page, terms, privacy page, FAQ and README drop it; the code stays dormant behind `WAYL_ENABLED=false` with its tests still running under the flag.
13. The pricing page reads the catalogue: `server/app/catalogue.json` at build time and `GET /billing/plans` after load (PF13 lays out the page); checkout links `/dashboard/billing/?tier=team&interval=year&seats=5`.
14. The dashboard billing page rewritten: current plan, interval, seats, next charge, change plan or interval, seat stepper, founding badge, invoices, portal.
15. `charge_usage` and `create_invoice` on the interface for metered overage (PF6, PF11) and B2B invoices (Enterprise, PF7 commissions, PF8 listing fees).
16. Tests for every endpoint and adapter (happy path, auth failure, validation failure, bad signature, replay).

**Out (and where it goes):**
* Pricing page layout, plan copy and JSON-LD → PF13; organisation-owned subscriptions and seat assignment → PF3.
* Metering and the monthly overage run → PF6, PF11 (they call `charge_usage`).
* Marketplace order payments (Stripe Connect behind a flag) → PF7; supplier listing-plan checkout → PF8 (Stripe adapter through this interface).
* VAT registrations, the accountant, legal wording → GD5; prices, founding count, discounts → GD7.
* Renewal reminder notices of the DMCC Act 2024 subscription rules → when GD5 confirms the commencement date (carry-over row in As-built).

## Design

### Provider decision: Stripe UK + Stripe Tax against a merchant of record (Paddle)

| Criterion | Stripe UK + Stripe Tax (Truebex Ltd is the seller) | Paddle (merchant of record; Truebex sells to Paddle) |
|---|---|---|
| Indirect tax | Truebex registers wherever an obligation arises: EU VAT through the non-Union OSS from the first consumer sale (no threshold for a non-EU seller, Directive 2006/112/EC Art. 59c), UK VAT above £90,000 taxable turnover, and every other country with a digital-services regime. Tax Basic (0.5 % per transaction) calculates and collects but does not file; Tax Complete (from £70 a month, one-year contract) adds registrations and filing through partners; the liability stays with Truebex | Paddle registers, collects, files and remits; included in its fee |
| List fees (2026-10-09) | cards 1.5 % + 20p (UK), 2.5 % + 20p (EEA), 3.15 % + 20p (international), + 2 % with currency conversion; Billing 0.7 % of billing volume; disputes £20 each | 5 % + US$0.50 per checkout transaction, covering payment, tax, fraud, chargebacks and buyer billing support |
| Worked example: £40.00 a month, international card (placeholder price) | 3.15 % + 20p + 0.7 % + 0.5 % = £1.94, before conversion, disputes and the cost of filing in each registered country | 5 % = £2.00 + US$0.50, nothing else |
| Invoices | Stripe invoices with tax lines, Truebex's VAT number, customer tax IDs | Paddle invoices as the seller; PDF through its API |
| Chargebacks, fraud, buyer questions | Truebex | Paddle |
| Consumer cancellation rules | Truebex implements consent and confirmation | Paddle's checkout and buyer terms; Truebex still records its own consent |
| Checkout on a static site | hosted Checkout redirect (built: `providers.py:43`) | Paddle.js overlay on a page of the approved domain (`/checkout/`), public client token |
| What it cannot carry | — | physical goods and offerings with no software, e.g. advertising (Paddle AUP): marketplace orders and supplier listing fees cannot go through Paddle |
| Already in the code | yes, tested (`server/tests/test_billing.py:167-183`) | no |

**Decision: Paddle is the default for the five tiers' subscriptions (consumers and self-serve businesses).** A UK company selling to consumers worldwide from the first day owes EU VAT from the first EU sale and faces a registration in every other country with a digital-services tax; one person cannot file those returns, and Paddle files them. Global consumer sales also bring chargebacks, fraud screening and billing questions that Paddle absorbs. The fee gap on an international card (5 % against 4.35 %, i.e. 0.65 percentage points, plus US$0.50 against 20p in the example above) is far below the cost of multi-country filing at launch volume. **Stripe stays** behind the same interface, upgraded with Stripe Tax: Enterprise invoices, supplier listing fees and commission invoices (business customers, reverse charge, outside Paddle's policy), and a switch back when volume makes filing in-house cheaper (a GD5 and GD7 decision, one setting). Rejected: Stripe only (the filing burden from day one); Paddle only (cannot carry PF7 and PF8 money, and throws away tested Stripe code).

### API

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/billing/plans` | none | — | `{tiers: [{id, name, purchasable, per_seat, min_seats, prices: [{interval: month\|year, currency, amount_minor}]}], founding: {enabled, total, remaining, discount_percent, ends_at}, provider: paddle\|stripe\|null}`; no `wayl`, no `price_iqd` |
| POST | `/billing/checkout` | session | `{tier, interval, currency, seats, coupon?, consent: {version, accepted: true}}` | `{url, reference, founding}`; 400 not purchasable; 422 consent missing or seats below `min_seats`; 503 provider off |
| POST | `/billing/payments/{reference}/refresh` | session | — | the payment, re-checked with Paddle or Stripe (Wayl when enabled) |
| GET | `/billing/subscription` | session | — | `{tier, interval, seats, status, provider, current_period_end, cancel_at_period_end, founding, can_manage}` |
| POST | `/billing/seats` | session | `{seats}` | 200 the subscription; 409 below seats assigned (PF3); 422 |
| POST | `/billing/change` | session | `{tier?, interval?}` | 200; 400 not purchasable |
| GET | `/billing/invoices` | session | — | `[{id, number, issued_at, total_minor, tax_minor, currency, status, pdf_url}]` |
| POST | `/billing/portal` | session | — | `{url}`; 404 no subscription |
| POST | `/billing/webhooks/paddle` | `Paddle-Signature` | raw body | `200 {received}`; 400 bad signature or stale timestamp |
| POST | `/billing/webhooks/stripe`, `/wayl` | provider | unchanged | `/wayl` answers 404 unless `WAYL_ENABLED` |

| `BillingProvider` method | Does |
|---|---|
| `enabled(settings)` | keys present (and `WAYL_ENABLED` for Wayl) |
| `create_checkout(db, user, payment, price, seats, discount)` | returns the URL the browser opens |
| `verify_payment(db, payment)` | fetches the provider's state for `refresh` |
| `handle_webhook(db, body, headers)` | verifies, de-duplicates by event id, applies through `service.upsert_subscription` |
| `portal_url(db, user)`, `change_subscription(db, sub, tier=, interval=, seats=)`, `list_invoices(db, user)` | as named |
| `charge_usage(db, sub, metric, quantity, unit_amount_minor, description)` | a one-off charge on the subscription (overage) |
| `create_invoice(db, customer, lines)` | business invoice (Stripe only) |

`service.upsert_stripe_subscription` (`server/app/billing/service.py:109`) becomes `upsert_subscription(provider, provider_subscription_id, user_id, tier, interval, seats, status, current_period_end, cancel_at_period_end)`; the Stripe status map (`providers.py:27`) gains a Paddle twin. Paddle flow on the static site: the server creates a transaction (price id, quantity, customer e-mail, `custom_data`, discount) and returns `https://truebex.com/checkout/?_ptxn=txn_…`; `/checkout/` loads Paddle.js with the client token from `/config` and opens the overlay; `checkout.completed` sends the browser to `/dashboard/billing/?checkout=success&ref=…`; `refresh` asks Paddle's API for the transaction (the pattern of `routers/billing.py:148`), and webhooks do the rest.

### Data

| Table / column | Fields | Notes |
|---|---|---|
| `server/app/catalogue.json` (PF1) | per tier `prices: [{interval, currency, amount_minor}]`, `per_seat`, `min_seats`; top-level `founding: {total, discount_percent, ends_at}` | amounts `from GD7`; a tier with no price renders "Price at launch" (PF13) |
| `provider_prices` (new) | `provider`, `tier`, `interval`, `currency`, `amount_minor`, `provider_price_id`, `active` | written by `sync_prices.py`; replaces `STRIPE_PRICE_PRO` (`server/app/config.py:37`), which stays read for old subscribers |
| `billing_events` (new) | `provider`, `event_id` unique, `type`, `occurred_at`, `received_at`, `status` | replay and order protection |
| `founding_reservations` (new) | `id`, `user_id`, `reference`, `expires_at`, `consumed_at` | 30-minute hold |
| `subscriptions` (+ columns) | `interval`, `currency`, `cancel_at_period_end`, `founding`, `provider_price_id` | `_ADDED_COLUMNS`, nullable |
| `payments` (+ columns) | `interval`, `seats`, `tax_minor`, `consent_version`, `consent_at`, `invoice_id` | amounts in minor units of `currency` from now on |

Settings: `BILLING_PROVIDER=paddle|stripe`, `PADDLE_ENV=sandbox|production`, `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_CLIENT_TOKEN` (public, served by `/config` like the Google client id at `server/app/main.py:54-57`), `STRIPE_TAX_ENABLED`, `WAYL_ENABLED=false`.

### UI

| Page / component | Change |
|---|---|
| `src/app/checkout/page.tsx` (new, noindex) | loads Paddle.js only here, reads `?_ptxn=` inside `Suspense`, opens the overlay, redirects on completion or close |
| `src/app/dashboard/billing/page.tsx` (rewrite) | current plan card; tier picker from `/billing/plans` with a monthly / annual toggle, currency (GBP, USD, EUR; default from the browser locale), seat stepper on per-seat tiers, founding badge "N founding seats left"; the consent checkbox; invoices table with PDF links; Manage card and cancel → portal; payment history keeps the provider label of past rows (Wayl rows are history, not an option) |
| `src/lib/developer.ts` | `Provider = "paddle" \| "stripe"`; new `PlanInfo`; `formatMoney` through `Intl.NumberFormat` for every currency |
| `src/lib/constants.ts` | FAQ "How can I pay?" rewritten from what `/billing/plans` really enables (the brand rule at `SKILL.md:73`); `BILLING.consent` text (versioned, wording from GD5) |
| `src/app/terms/page.tsx` "Paid plans" | annual plans, seats, Paddle as the reseller for card purchases, cancellation; the Wayl item removed |
| `src/app/privacy/page.tsx` processors | Paddle added; Wayl removed |
| `README.md` billing section | Paddle default, Stripe secondary, Wayl dormant and how to re-enable it |

### Jobs / workers

* `billing.founding.expire` every 300 s: releases expired holds (`server/app/tasks.py`, PF14 Plumbing).
* `billing.reconcile` every 24 h: lists provider subscriptions changed in the last 48 h and applies them, covering webhooks missed while the API was down (the PC is off at times until PF14).
* `server/scripts/sync_prices.py --provider paddle|stripe --env sandbox|production`: creates or finds products and prices from the catalogue (idempotent by lookup key), fills `provider_prices`; run by the owner whenever GD7 prices change.

### Security and privacy

* A plan, a seat count or a founding flag changes only from a verified event or a server-side fetch (`server/app/billing/service.py:4-9`); the browser sends only tier, interval, currency and seats, and the server picks the price.
* Paddle webhooks: HMAC-SHA256 over `ts:body` with the endpoint secret, rejected outside a 300 s window; Stripe as today (`providers.py:101`); both de-duplicated by event id, older events never overwrite newer state.
* Card data never reaches Truebex (Paddle overlay frame, Stripe hosted page); the Paddle client token is public by design, the API key lives only in `server/.env`.
* Consent text and version stored with a timestamp per payment; the provider's receipt is the confirmation on a durable medium (GD5 confirms that it suffices).
* Personal data shared with Paddle: e-mail, country, postcode for tax; the privacy page says so.

## Deliverables

- [ ] `server/app/billing/base.py` (`BillingProvider`), `paddle_provider.py`, `stripe_provider.py`, `wayl_provider.py`; `providers.py` kept as the registry re-exporting what the tests patch (`_wayl_client`, `server/tests/test_billing.py:47`)
- [ ] `server/app/billing/service.py`: `upsert_subscription`, founding count, event de-duplication
- [ ] `server/app/routers/billing.py` endpoints above; `schemas.py` new models; settings and `.env.example`
- [ ] `server/scripts/sync_prices.py`; catalogue price fields; `server/tests/mock_paddle.py` (a local stand-in like `mock_wayl.py`)
- [ ] `src/app/checkout/`, billing page rewrite, `src/lib/developer.ts`, copy in `constants.ts`, terms, privacy, README
- [ ] the tests below

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_billing_plans_lists_tiers_without_wayl` | pytest | five tiers, prices per interval and currency, `provider` = `paddle`; no `wayl`, no `price_iqd` |
| `test_billing_plans_wayl_dormant_flag` | pytest | with `WAYL_ENABLED=true` Wayl reappears; the existing Wayl tests (`server/tests/test_billing.py:64-110`) pass under the flag |
| `test_billing_checkout_paddle_creates_transaction` | pytest | mocked Paddle API receives price id, quantity, `custom_data.user_id`; URL is `/checkout/?_ptxn=…` |
| `test_billing_checkout_requires_session_and_consent` | pytest | 401 without session; 422 without `consent.accepted`; 422 seats below `min_seats` |
| `test_billing_checkout_rejects_unpurchasable_and_unknown_price` | pytest | 400 for `enterprise`; 400 for a currency with no price |
| `test_billing_checkout_server_picks_price` | pytest | an `amount` sent by the browser is ignored |
| `test_billing_paddle_webhook_signature` | pytest | valid → 200; wrong secret → 400; timestamp older than 300 s → 400 |
| `test_billing_paddle_subscription_lifecycle` | pytest | created → plan `pro`, seats set; updated (seats 3) → seats 3; canceled → `free` at period end |
| `test_billing_webhook_replay_and_out_of_order` | pytest | the same event twice applies once; an older `updated` after a newer one changes nothing |
| `test_billing_refresh_verifies_with_paddle` | pytest | a completed transaction fetched server-side marks the payment `paid`; a forged `?checkout=success` alone does nothing |
| `test_billing_stripe_tax_and_annual_checkout` | pytest | Checkout params carry `automatic_tax`, `tax_id_collection`, the annual price id and `quantity` |
| `test_billing_stripe_legacy_pro_still_applies` | pytest | an event for the old monthly price keeps the user on `pro` |
| `test_billing_seats_change` | pytest | 200 calls the provider with proration; 401 anonymous; 422 for 0 seats |
| `test_billing_change_interval` | pytest | month → year on the provider; 401; 400 for a non-purchasable tier |
| `test_billing_founding_counts_and_holds` | pytest | `remaining` falls on a paid founding checkout; a hold expires after 30 min; sold out → `founding: false` |
| `test_billing_invoices_list` | pytest | rows with `pdf_url` from the mocked provider; 401 anonymous |
| `test_billing_portal_paddle_and_stripe` | pytest | portal URL per provider; 404 without a subscription |
| `test_billing_charge_usage_interface` | pytest | `charge_usage` calls the Paddle one-off charge with the right amount |
| `test_billing_entitlement_follows_purchase` | pytest | after the webhook the next `POST /licence/entitlement` says `pro` with `plan_period_end`; `/licence/account` shows `seats.total` |
| `test_billing_no_client_side_plan_grant` | pytest | the existing guard (`server/tests/test_billing.py:58`) still holds for every new route |
| `test_site_pf2_checkout_noindex` | build check | `out/checkout/index.html` carries `noindex`; Paddle.js referenced only there |
| `test_site_pf2_no_wayl_in_public_pages` | build check | no "Wayl", "QiCard" or "IQD" in `out/**/*.html` |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. `server/.env`: Paddle sandbox keys, `BILLING_PROVIDER=paddle`, PF1's licence key; in `server/`: `.venv\Scripts\python.exe scripts\sync_prices.py --provider paddle --env sandbox` → prints the created price ids. Start `server\run.bat`; build with `NEXT_PUBLIC_AUTH_URL=http://127.0.0.1:8000`; serve with `scripts/autopilot-serve.ps1`.
2. Sign up → `/dashboard/billing/` lists Pro, Studio, Team with monthly / annual toggle, GBP selected, founding badge with the count; no Wayl anywhere.
3. Choose Pro, monthly; Checkout without the consent box → the button stays disabled with the reason; tick it → `/checkout/` opens the Paddle overlay.
4. Pay with a sandbox test card from Paddle's testing docs → back on billing: "Payment received — your plan is active"; the plan card reads Pro, renews in one month.
5. Dashboard home: Licence "Pro". In an LC1 build, press Refresh licence → the title bar shows Pro and an exported PDF has no watermark (without LC1: `curl -X POST …/licence/entitlement` with PF1's device token and fingerprint → `"plan":"pro"`).
6. Invoices → the PDF opens with the VAT line and the seller's details.
7. Team, 3 seats, annual: checkout, then change seats to 5 → the provider shows a prorated charge; the subscription card reads 5 seats.
8. Manage → portal → cancel → the card reads "Ends on <date>"; `GET /billing/plans` shows no `wayl` and no `price_iqd`.

## Risks / traps

* Paddle approves the seller and the domain before production: the pricing page (PF13), terms, refund wording and privacy page must be live first; sandbox works before that.
* Paddle.js runs only on approved domains: the overlay lives on `/checkout/` of truebex.com (and the sandbox allow-list for local testing).
* Webhooks miss while the PC is off (until PF14): `refresh` on return and the daily reconcile cover it.
* Static export: `/checkout/?_ptxn=` and the billing return read query strings inside `Suspense` (`src/app/dashboard/billing/page.tsx:256-262`).
* `test_catalog_lists_enabled_providers` (`server/tests/test_billing.py:51`) asserts Wayl and `price_iqd` today; it is rewritten, and the Wayl tests keep running with the flag so dormant code does not rot.
* `formatMoney` (`src/lib/developer.ts:88-89`) prints non-USD amounts as raw integers; every currency goes through `Intl.NumberFormat` with its own minor units.
* Consent and waiver wording is legal text: placeholder until GD5; the owner signs it off before production.
* Hot spots: `routers/billing.py`, `schemas.py`, `constants.ts`, `terms`, `privacy` are also touched by PF13 and PF14; edit in own blocks.

## As-built

* Date, branch, commits:
* Counts (pytest before → after):
* Deviations from Design and why:
* GD5 wording and GD7 prices adopted (dates):
* Carry-over → which feature (e.g. DMCC renewal reminders):
