# PF2a — Catalogue prices per the pricing plan (launch priority 1)

**Needs merged:** PF2, PF13 (both merged with PF1 on `master`, d0129c5). **Unblocks:** a live pricing page (Paddle's seller and domain review asks for one) and the GD6 launch posts. **Contract:** none (no app-facing endpoint changes; `contracts/licence-api.md` sees billing only through PF1's entitlement).

## Status

**Built 2026-10-10 on `ap/t18-pf2a-catalogue-prices-per-the-pr`** (Autopilot T18; verify gate green; see As-built). The table is the state the task started from (`master` d0129c5, verified with Grep):

| Area | Where | Before PF2a |
|---|---|---|
| Prices | `server/app/catalogue.json:3` (`prices_final`), tiers' `prices` | PF2's placeholders (Pro £79 / $99 / €95 a month, Studio £159 / $199 / €189, Team £89 / $109 / €105 per seat a month; annual = 10 × monthly), `prices_final: false` |
| Founding | `server/app/catalogue.json:6` | 100 places, 30 % off every price of Pro, Studio and Team, ending 2027-03-31 |
| Public gate | `src/lib/catalogue.ts:53` (`publicCatalogue`) | while `prices_final` is false every paid tier reads "Price at launch" and the founding block is hidden |
| Price display | `src/components/pricing/TierCards.tsx:167` (annual ÷ 12), `:21` and `src/lib/constants.ts:492` (`perYearMonthly`) | the Monthly view printed 12 × the monthly price ("… a year, paid monthly"), an amount nobody is charged |
| Founding banner | `src/app/pricing/page.tsx:45` | outside the tier cards: no prices, no currency |
| Billing page | `src/app/dashboard/billing/page.tsx:306` | founding price on every interval; a tier without the chosen interval read "Price at launch" |
| Founding rules in the API | `server/scripts/sync_prices.py:68`, `server/app/billing/service.py:444`, `server/app/billing/base.py:114` | a founding price for every interval of a founding tier |
| Tests pinning the placeholders | `server/tests/test_site_pf13.py:319`, `:439`; Team bought monthly in `server/tests/test_billing_pf2.py` (e.g. `:687` `test_billing_entitlement_follows_purchase`) | |

The pricing guide `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\guides\GD7-pricing-and-packaging-guide.md` still carries its stub Status line ("to be written by this task; this file is replaced by the guide", read 2026-10-10), so the owner's numbers in the task are the source.

## Goal

The website and the API sell at the owner's prices: Free; Pro and Studio monthly or annually; Team per seat, annually only, from two seats; Enterprise on request; and 300 founding places at 30 % off the annual prices until 31 January 2027. Every amount a visitor sees is something they are charged, or follows directly from a charge.

## Read first

* `docs/roadmap/40/00-contract.md`; PF2's As-built (prices, founding, `sync_prices.py`, the PF13 merge note on `prices_final`); PF13's As-built (`publicCatalogue()` and the build checks).
* `.claude/skills/truebex-brand-voice/SKILL.md` (prices come from the catalogue, never typed into copy) and `.claude/skills/truebex-seo/SKILL.md` (JSON-LD offers in step).

## Scope

**In:**
1. `server/app/catalogue.json` carries exactly these charged amounts, `prices_final: true`:

   | Tier | Month (USD / GBP / EUR) | Year (USD / GBP / EUR) | Seats |
   |---|---|---|---|
   | Free | $0 | | |
   | Pro | 29.00 / 24.00 / 27.00 | 290.00 / 240.00 / 270.00 | one |
   | Studio | 99.00 / 79.00 / 89.00 | 990.00 / 790.00 / 890.00 | one |
   | Team | none, never monthly | 1,788.00 / 1,190.00 / 1,390.00 per seat | from 2 |
   | Enterprise | Custom (no prices) | | |

   Founding: `total` 300, `discount_percent` 30, tiers Pro, Studio and Team, `ends_at` 2027-01-31T23:59:59Z; founding prices are the annual prices at 30 % off (Pro $203.00 / £168.00 / €189.00, Studio $693.00 / £553.00 / €623.00, Team $1,251.60 / £833.00 / €973.00 per seat).
2. Team's per-month figure, wherever a page shows one (the Monthly view of `/pricing/`, the home teaser, `/ar/`, the billing page), is the annual charge ÷ 12, labelled billed annually: $149.00, £99.17, €115.83 per seat. No page prints a per-month or per-year amount that does not follow from a charge.
3. Team has no monthly price: the billing page's Monthly toggle and a `?tier=team&interval=month` link sell Team annually; `POST /billing/checkout` for team/month answers the existing 400 for a missing price; tests that bought Team monthly buy it annually.
4. `sync_prices.py` regenerates the provider prices (founding included), proven with `--dry-run` for Paddle and Stripe and a real run against `tests/mock_paddle.py`.
5. The pricing page, home teaser, `/developers/` table, JSON-LD offers and `/ar/` read every number from the catalogue; nothing is hard-coded.
6. Build checks: the exact amounts in `out/pricing/index.html` (and no other amount); the PF13 checks moved to the final state; one check that a catalogue with `prices_final: false` still renders "Price at launch" (through `TRUEBEX_CATALOGUE_FILE` and a fixture).

**Out (and where it goes):**
* The pricing guide itself, the entitlement matrix and what sets Studio apart from Pro → GD7 (the matrix is still the contract's §6.3 placeholder).
* Creating the prices in the real Paddle and Stripe accounts → the owner, with `sync_prices.py` per environment (no keys in this workspace).
* Deploying → the owner (`truebex-deploy` skill).

## Design

### Data

`server/app/catalogue.json` gains `founding.intervals` (`["year"]`): the billing intervals with a founding price. Absent, it means every interval, so older catalogues and the fixtures keep their meaning. `server/app/plans.py` `FoundingOffer.intervals` and `covers(tier, interval)` read it; nothing in the database changes. Placeholder-era rows in `provider_prices` stay, inactive, so webhooks for anyone who paid an old price still map to their tier.

### API

No new endpoint.

| Where | Change |
|---|---|
| `GET /billing/plans` | `founding.intervals` added (`["year"]`) |
| `POST /billing/checkout` | holds a founding place only when the offer covers the tier **and** the interval (`service.hold_founding(…, tier, interval)`); team/month → 400 "Team has no monthly price in GBP." (unchanged path) |
| `POST /billing/change` | the founding price follows a subscription only to a tier and interval the offer covers (`BillingProvider.change_subscription`); a move to monthly ends it; team/month → 400 |
| `server/scripts/sync_prices.py` | a founding target only where `FOUNDING.covers(tier, interval)`: 15 list prices + 9 founding prices = 24 |

### UI

| Page / component | Change |
|---|---|
| `src/lib/catalogue.ts` | `intervalFor()` (the interval a tier is shown and sold at: Team → year), `perMonthOfYear()` (charge ÷ 12, nearest minor unit), `foundingCovers()`; `Founding.tiers` / `intervals` |
| `src/components/pricing/TierCards.tsx` | `PriceBlock` (exported for the render checks): Monthly view = the monthly price "per month" and "or {annual} a year, billed annually"; a tier with only an annual price, or the Annual view = annual ÷ 12 "per month, billed annually" and "{annual} a year". The 12 × monthly line is gone. Listed amounts carry `data-amount-minor`, worked-out ones `data-derived`. Checkout links use the interval the tier is sold at (`tier=team&interval=year`). The founding banner renders inside, in the chosen currency |
| `src/components/pricing/FoundingBanner.tsx` | lists the founding prices: "A year at the founding price: Pro £168, Studio £553 and Team £833 per seat." (`data-founding-minor`) |
| `src/lib/pricing.ts` `pricingFaq` | fills `{min}`, `{tiers}`, `{ends}`, `{annualOnly}` from the catalogue; new FAQ "Can I pay for Team monthly?" (`when: "annualOnly"`) |
| `src/app/dashboard/billing/page.tsx` | each tier card at `intervalFor()`; Team in the Monthly view shows (founding) annual ÷ 12 "/ month, billed annually" and the annual charge; checkout and plan changes send the interval the tier is sold at; "Team is billed annually."; founding price only where `foundingCovers()`; the change panel warns "This change ends your founding price, which covers annual billing only." |
| `src/lib/constants.ts` | `PRICING.labels.orYear` (replaces `perYearMonthly`; Arabic too), `PRICING.founding` (annual wording, `prices`, `and`), FAQ answers, `BILLING.choose.billedAnnually` / `annualOnly`, `BILLING.founding.off`, `BILLING.change.foundingEnds`, the home FAQ "How can I pay?", the terms' "Plans" and "Founding seats" |

### Security and privacy

Unchanged: the browser names tier, interval, currency and seats; the server picks the price from the catalogue and `provider_prices`.

## Deliverables

- [x] `server/app/catalogue.json` (prices, founding, `prices_final: true`); `plans.py`, `billing/service.py`, `billing/base.py`, `routers/billing.py`, `schemas.py`, `scripts/sync_prices.py`
- [x] `src/lib/catalogue.ts`, `src/components/pricing/TierCards.tsx`, `FoundingBanner.tsx`, `src/app/pricing/page.tsx`, `src/lib/pricing.ts`, `src/app/dashboard/billing/page.tsx`, `src/lib/developer.ts`, `src/lib/billing-catalog.ts`, `src/lib/constants.ts`, `README.md`
- [x] `scripts/fixtures/catalogue-placeholder.json` (PF2's placeholders, `prices_final: false`); `scripts/fixtures/catalogue-sample.json` gains `founding.tiers`
- [x] `server/tests/test_pf2a_prices.py`, `server/tests/site_render.cjs`, the PF2a checks in `server/tests/test_site_pf13.py`

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf2a_catalogue_prices_per_plan` | pytest | the table above, exactly; Free and Enterprise unpriced; Team per seat, min 2, no monthly price; `PLANS` reads the same |
| `test_pf2a_founding_offer` | pytest | total 300, 30 %, ends 2027-01-31T23:59:59Z, tiers, `intervals: ["year"]`; the nine founding prices; `covers()` year only |
| `test_pf2a_team_per_month_derived` | pytest | annual ÷ 12 = $149.00 / £99.17 / €115.83; £119 and €139 × 12 are not the charges |
| `test_pf2a_plans_endpoint_serves_the_plan` | pytest | `/billing/plans` prices and founding (with `intervals`) |
| `test_pf2a_team_monthly_checkout_is_400` | pytest | team/month → 400, nothing started; team/year → Paddle transaction, 2 seats, founding £833 |
| `test_pf2a_team_change_to_monthly_is_400` | pytest | Team → monthly 400; Pro monthly → Team needs `interval: year` |
| `test_pf2a_founding_is_annual_only` | pytest | Pro monthly pays $29 with no place held; Pro annual pays $203 and holds one |
| `test_pf2a_founding_ends_on_a_move_to_monthly` | pytest | Studio annual founding → monthly: list €89, founding false, the place stays taken |
| `test_pf2a_sync_prices_targets` | pytest | 24 lookup keys, founding annual only, no Team monthly |
| `test_pf2a_sync_prices_paddle_regenerates` | pytest | against `mock_paddle`: `--dry-run` lists 24 (creates none), the sync creates 24 and retires a placeholder row, a second dry run finds all |
| `test_pf2a_sync_prices_stripe_dry_run` | pytest | `--dry-run --provider stripe`: 24 to create on an empty account, 0 when all exist, no create call, no `provider_prices` written |
| `test_pf2a_stripe_prices_cover_the_plan[pro, studio, team]` | pytest | the Stripe price fixture holds every list price |
| `test_site_pf2a_pricing_amounts_exact` | build check | `out/pricing/index.html`: GBP text shows exactly the GBP list prices, £99.17 and the GBP founding prices; no other £ / € amount in the file; the page data carries every list price in every currency; JSON-LD offers = the list prices (Team annual only) + Free 0; Team card and link; founding banner wording |
| `test_site_pf2a_teasers_and_developers` | build check | home teaser and `/ar/`: £24, £240, £99.17, £1,190 and nothing else; `/developers/` lists the five plans and no price |
| `test_site_pf2a_every_interval_and_currency` | render check (Node) | every `PriceBlock` for both intervals and three currencies prints only a charge or charge ÷ 12; founding prices in the banner |
| `test_site_pf13_catalogue_placeholder_shape` | pytest | moved to the final state: `prices_final` true, every purchasable tier priced in every currency per interval |
| `test_site_pf13_placeholder_prices_stay_private` | render check (Node) + build check | `catalogue-placeholder.json` through `TRUEBEX_CATALOGUE_FILE`: "Price at launch", no amounts, no founding, Free-only offers, the "When can I buy" FAQ; `out/` too when built from such a catalogue |
| `npm run lint`, `npm run build`, `scripts/autopilot-verify.ps1` | build check | green |

## Human test

Three PowerShell windows in the worktree. A local API with the mock Paddle, and the site built against it.

1. **Mock Paddle** (window A, in `server\`):
   `$env:MOCK_PADDLE_WEBHOOK_URL="http://127.0.0.1:8000/billing/webhooks/paddle"; .venv\Scripts\python.exe -m uvicorn tests.mock_paddle:app --port 8098`
2. **API** (window B, in `server\`):
   `$env:DATABASE_URL="sqlite:///./pf2a-test.db"; $env:BILLING_PROVIDER="paddle"; $env:PADDLE_ENV="sandbox"; $env:PADDLE_API_KEY="pdl_sdbx_local"; $env:PADDLE_API_BASE="http://127.0.0.1:8098"; $env:PADDLE_WEBHOOK_SECRET="pdl_ntfset_mock_secret"; $env:PADDLE_CLIENT_TOKEN="test"; $env:SITE_URL="http://127.0.0.1:3118"; $env:CORS_ORIGINS="http://127.0.0.1:3118"`
   then `.venv\Scripts\python.exe scripts\sync_prices.py --provider paddle --env sandbox --dry-run` → 24 lines, `24 prices, 24 new`, 9 of them `_founding`, all `year`; the same without `--dry-run` → price ids; `.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`.
3. **Site** (window C, worktree root): `Remove-Item -Recurse -Force out; $env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; $env:AUTOPILOT_TASK_ID="T18"; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → builds, then serves `http://127.0.0.1:3118/`.
4. `/pricing/`, GBP, Monthly → Pro £24 per month, "or £240 a year, billed annually"; Studio £79 / £790; Team £99.17 "per month, billed annually · per seat · from 2 seats" and "£1,190 a year"; Enterprise Custom. Banner: "The first 300 founding seats keep 30 % off annual plans … Offer ends 31 January 2027.", "A year at the founding price: Pro £168, Studio £553 and Team £833 per seat.", "300 of 300 founding seats left".
5. Annual → Pro £20 / £240 a year, Studio £65.83 / £790, Team unchanged. USD → Team $149 / $1,788, Pro $24.17 / $290, banner Pro $203, Studio $693, Team $1,251.60 per seat. EUR + Monthly → Pro €27 or €270, Team €115.83 / €1,390. "Choose Team" always links to `…tier=team&interval=year…`.
6. `/` and `/ar/` pricing teaser → Pro £24 (or £240), Team £99.17 and £1,190. `/developers/` → the plan table names Free, Pro, Studio, Team, Enterprise.
7. Sign up, then open `http://127.0.0.1:3118/dashboard/billing/?tier=team&interval=month&currency=GBP` → Team selected: "£69.42 / month, billed annually", "£833.00 / year" with £1,190.00 struck through; "Total before tax: £1,666.00 / year", "Team is billed annually."; Pro "£24.00 / month". Annual → Pro "£168.00 / year" with £240.00 struck through. Back to Monthly.
8. Tick the consent box → Continue to payment → the mock page lists Team annual per seat (founding) × 2 → Pay with a test card → back on billing: "Payment received — your plan is active", Team, "Annual · 2 seats", Founding price badge.
9. Change plan: pick Pro, press Monthly → "£24.00 / month" and "This change ends your founding price, which covers annual billing only." (no need to apply). `http://127.0.0.1:8000/billing/plans` → Team prices only `"interval":"year"`; `founding.intervals` `["year"]`, `remaining` 299.

## Risks / traps

* The founding wording ("off annual plans", the terms' "on annual billing") follows `founding.intervals`; `test_site_pf2a_pricing_amounts_exact` fails if the banner loses it. A change to the intervals needs the copy, `sync_prices.py` and a provider sync together.
* Changing an amount creates new provider prices: run `sync_prices.py` for each environment before deploying the catalogue, or checkouts answer 503 "not set up yet" until it runs.
* The served `/pricing/` refreshes the founding count from the API it was built against; built against production before the API is deployed, the banner shows production's numbers (or hides while production offers no checkout).
* Headless browsers and visitors outside the UK see USD or EUR first (browser locale); the static HTML and the build checks are GBP.

## As-built

* **Date, branch, commits:** 2026-10-10, `ap/t18-pf2a-catalogue-prices-per-the-pr` (Autopilot T18) on `master` d0129c5. `fa067d6` (implementation and tests), then the docs and layout commit that writes this section (`git log master..ap/t18-pf2a-catalogue-prices-per-the-pr`).
* **Counts:** pytest 116 passed + 24 skipped (no `out/`) → 157 passed with `out/` (+14 in `test_pf2a_prices.py`, +3 PF2a site checks; the PF13 placeholder check now always runs through Node). `out/` routes unchanged. Lint, build and `scripts/autopilot-verify.ps1` green.
* **Self-tests:**
  * `sync_prices.py` as a process against `tests/mock_paddle.py` over HTTP (scratch database): `--dry-run` → 24 `(would create)` including 9 founding (all annual), `24 prices, 24 new`; sync → 24 price ids, `provider_prices` 24 active / 9 founding; second `--dry-run` → `24 prices, 0 new`.
  * `--provider stripe --dry-run` against a local fake Stripe API (`stripe.api_base`; no Stripe key here): 24 to create on an empty account, `24 prices, 0 new` when every lookup key exists, no POST, no database written.
  * Headless Edge over CDP against the local API + mock Paddle, site built with `NEXT_PUBLIC_AUTH_URL` local: 22/22 checks: `/pricing/` in GBP / USD / EUR × Monthly / Annual, the live founding count, Team links; the billing page from `?tier=team&interval=month` (Team £69.42 / month billed annually, £833.00 / year, total £1,666.00 / year), Pro founding only on Annual, checkout → mock pay page (Team annual × 2 at the founding price) → "Payment received", Team · Annual · 2 seats · Founding price; the change panel's founding warning; the API's subscription team / year / 2 / founding.
* **Decisions and deviations:**
  1. **`prices_final` is true** (decided in the task): the PF13 checks that pinned it to false moved to the final state; the placeholder gate is kept by `test_site_pf13_placeholder_prices_stay_private`, which renders `scripts/fixtures/catalogue-placeholder.json` (PF2's old placeholders) through `TRUEBEX_CATALOGUE_FILE` on every run.
  2. **Rendering without a second build:** `server/tests/site_render.cjs` loads the real components (`TierCards`, `PriceBlock`, `FoundingBanner`, `loadCatalogue`, `pricingFaq`, `offersLd`) with the project's TypeScript and `react-dom/server`, so the placeholder gate and every interval / currency are checked in the gate without another `next build` (the static HTML is GBP and Monthly only).
  3. **Founding is annual only** (`founding.intervals: ["year"]`), read from "founding prices are the yearly prices at 30 percent off (Pro $203.00)". Monthly checkouts pay the list price and hold no place; a founding subscriber who moves to monthly loses the founding price (the place stays counted); the billing page warns first. One line to change (see Owner to confirm).
  4. **No twelve-monthly-payments figure:** the Monthly view's second line is now the annual list price ("or £240 a year, billed annually") instead of 12 × monthly ("£288 a year, paid monthly"), which is not a charge and is outside the allowed set. The Annual view keeps PF13's per-month equivalent (annual ÷ 12, billed annually) for every tier, the same rule as Team's.
  5. **The founding banner moved into `TierCards`** so its prices follow the chosen currency; it lists each founding tier's annual founding price.
  6. **Billing page, Team in the Monthly view:** the per-month figure is derived from the annual amount the buyer is charged, so with the founding offer it is £833 ÷ 12 = £69.42 (list £99.17 when the offer is closed).
  7. **`/billing/change`** keeps answering 400 for team/month rather than switching the interval silently; the billing page always sends the interval the tier is sold at.
  8. `/developers/` shows no prices (allowances only), already read from the catalogue; checked to stay price-free.
  9. The billing page keeps PF2's money format (`£24.00`, always with pence); the public pages print pence only when there are any (`£24`, `£99.17`).
* **Owner to confirm:**
  1. **Team per month:** the note said £119 and €139 a month, but 12 × £119 = £1,428 and 12 × €139 = €1,668, not the annual £1,190 and €1,390. The yearly amounts are kept as given and the site shows £99.17 and €115.83 (and $149.00, which does match $1,788). If the monthly figures were the intent, the annual prices would be £1,428 and €1,668.
  2. **Founding on annual plans only.** To extend it to monthly, set `"intervals": ["month", "year"]` (or drop the key) in `server/app/catalogue.json`, adjust the founding copy (`PRICING.founding`, `BILLING.founding.off`, the terms' "Founding seats") and re-run `sync_prices.py`.
  3. **Founding places are per subscription** (PF2 As-built 1): a Team founding purchase takes one of the 300 places whatever its seats.
* **Contract:** none implemented or changed; nothing to record in the Unreal repo's `contracts/`.
* **Carry-over → which feature:**
  * **Owner:** run `server\scripts\sync_prices.py --provider paddle --env sandbox` (and `production`, and Stripe if used) before deploying; the old placeholder prices stay inactive in `provider_prices`. Archive the old placeholder prices in the provider dashboards if any were created.
  * **GD7:** when the guide is written, its prices replace these through `catalogue.json` only, and `test_pf2a_prices.py` / the `PF2A_*` tables in `test_site_pf13.py` move with them.
* **Merged together with PF5, PF7, PF8, PF2b and master (PF2, PF3, PF13, PF14, PF14a) (2026-10-10, Autopilot T28, `ap/t28-merge-t5-t6-t7-t18-t19`):** verify green (lint, build, pytest 330 passed, 3 Postgres-only skipped); a smoke run against one real API process (demo share, trial catalogue, request for quote, worker running every merged job) passed 23/23.
  * The billing page keeps PF2a's selected interval (Team annual only) next to PF2b's key information: the key information names the interval checkout buys and carries the "billed annually" line too.
  * PF2b's Stripe renewal test now takes Pro's annual GBP price from the catalogue (it had the placeholder 790.00).
