# PF7b — The "Buy this look" basket page the app's room themes open (launch priority 2)

**Needs merged:** PF7, PF9 (both on `master`), PR2 (app; landed on the app repo's `main` 2026-10-13, commit 90799860, Autopilot T158). **Unblocks:** the app's "Buy this look" until MK4's order flow (contract 5.7 in the app) replaces the hand-off. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\marketplace-api.md` v1.1.0: §3 *Changes* (the PR2 line of 2026-10-11), 5.2, 5.5, 5.7, §6.3, §7, §8. No contract change.

## Status

**Built 2026-10-13** (Autopilot T64, `ap/t64-pf7b-the-buy-this-look-basket-pa`): `/market/basket/` names and prices a theme's products for the region and sends them through PF7's order flow; see As-built. Before this task (master 9dac34b, verified on 2026-10-13):

| Area | Where (master 9dac34b) | Before |
|---|---|---|
| The page the app opens | the app's `Plugins\CADTOOL\Source\TruebexMarket\Private\CadMarket_PR2.cpp` `BasketUrl` (line 196) | `https://truebex.com/market/basket?region=<r>&items=<supplier hex>:<sku>:<variant>:<qty>,...`, the items value URL-encoded once (`FGenericPlatformHttp::UrlEncode`), `default` for an unknown variant, qty at least 1 |
| The site | `src/app/market/` | `checkout/` only: the exported site answered 404 for `/market/basket/` |
| Prices | 5.5 `POST /market/prices` (`server/app/market/prices.py` `batch`); `src/lib/app.ts:189` calls it | per line: price, availability, substitutes and PF7's `status`, but no product or supplier name and no product id |
| Orders | 5.7 `POST /market/orders` (`server/app/market/orders.py` `place`), `src/lib/market.ts`, `/market/checkout/` (`CheckoutPanel.tsx`), `/dashboard/orders/` | an order or request for quote with `Idempotency-Key`, `price_seen`, contact and delivery (country = the region's); 409 `price_changed` / `unavailable` (`quote_only`), 422 `region_not_served` |
| `default` | contract §6.3 (`variant_id` "`default` for a single variant"); `importer.py:652` | a JSON feed's variant without an id is stored as `default`; a CSV feed must name its variant, so a single-variant product may have any id (the fixture's paint is `2-5l`) |
| Sign-in return | `src/lib/auth.ts` `safeNext`, `AuthForm.tsx` | `/login/?next=` and `/signup/?next=` return to a same-site path with its query |
| Hosting | GitHub Pages behind Cloudflare | `https://truebex.com/login?next=%2Fx&items=a%3Ab%2Cc` → 301 to `/login/?next=%2Fx&items=a%3Ab%2Cc` (checked 2026-10-13): the app's slash-less URL keeps its query; `scripts/serve-out.py` does the same |

## Goal

A designer applies a marketplace room theme in Truebex and clicks "Buy this look". The browser opens truebex.com with the theme's products: each with its name, supplier, version, quantity, current price for their region and whether it is in stock; a discontinued one offers similar products; a product the catalogue no longer lists says so and stays out of the total. They sign in (or create an account), give a delivery address and send one order, then pay on the checkout page; while the suppliers take requests for quote only, the same button sends a request for quote.

## Read first

* `docs/roadmap/40/00-contract.md`; `PF7-marketplace-backend.md` (Design: orders, quote-only suppliers, Stripe Connect; As-built deviations 5, 6, 9, 11); `PF9-mobile-web-client-and-webxr.md` (how the web client prices placed products through 5.5).
* The contract's §3 PR2 line, 5.2, 5.5, 5.7, §6.3, §7 and §8; the app's `Docs/roadmap/40/PR2-room-themes.md` (As-built, "Buy this look", about line 361) and `CadMarket_PR2.cpp` (`Basket`, `BasketUrl`, `ThemeFromProduct`), `CadMarketProduct.cpp` (`DefaultVariant`).
* `.claude/skills/truebex-brand-voice` (every string), `.claude/skills/truebex-seo` (a per-person page: noindex, no sitemap entry, no canonical).

## Scope

**In:**

1. `src/app/market/basket/page.tsx`: static export, the query read in the browser. The `items` value is decoded once (URLSearchParams); an item is rejected when it is not four `:`-separated fields, its supplier id is not 32 hex, its SKU or variant is empty or over 64 characters, or its quantity is not a whole number in 1..99; more than 100 items is refused as a whole. The same product and version twice is one line.
2. Every line named and priced for the region: names and the `default` variant from a platform route (`POST /market/basket`), prices, availability and substitutes from 5.5. An unknown line says so plainly; unknown, withdrawn, unsold, unpriced and unavailable lines are left out of the total; totals per currency. An unavailable or discontinued line shows 5.5's substitutes with "Use this instead"; a product with several versions offers the others.
3. A region the platform does not serve (or none) says so and offers the served regions of 5.2 as links to the same basket.
4. "Place order": sign in or create an account first (back to the same basket afterwards), contact and delivery details, then 5.7 with an `Idempotency-Key` and each line's `price_seen`, then `/market/checkout/?order=<id>`. Quote-only suppliers (payments off until GD5, or a supplier not onboarded): the button reads "Request a quote" and sends a request for quote, which the checkout page and Orders show. 409 `price_changed` (and `unavailable`, 422 `region_not_served`) re-prices the basket and asks again.
5. Per person: `noindex, nofollow`, not in the sitemap, no canonical (the root layout's `/` is dropped). Copy in `MARKET_BASKET` (English: the market pages are English only today).
6. Tests (below), this doc, the tracker row and a README section.

**Out (and where it goes):**

* The app's own order flow (5.7 from the app, its basket panel and quote status) → MK4; it replaces this hand-off.
* Paying for an order → PF7's checkout page, unchanged (Stripe Connect, off until GD5).
* Arabic for the market pages → a later task with the rest of the marketplace in Arabic (LO1 for the app).
* The proposals for the app side (As-built) → the app's owner, through the contract.

## Design

### API

One platform route (not in the contract, like `POST /market/checkout/{order_id}`), `server/app/routers/market_basket.py` → `server/app/market/basket.py`:

`POST /market/basket` — no credential; rate-limited per address with the catalogue reads (`MARKET_READS_PER_MINUTE`, 429 `rate_limited`); errors in the shared envelope.

```json
{"region": "GB", "items": [{"supplier_id": "<32 hex>", "sku": "SOFA-OSLO-3", "variant_id": "default"}]}
{"region": "GB", "items": [{"supplier_id": "…", "sku": "SOFA-OSLO-3", "variant_id": "default", "status": "found",
  "product_id": "<32 hex>", "name": "Oslo 3-seater sofa", "kind": "object", "supplier_name": "Nord Living",
  "thumbnail_url": "https://…", "orderable": false,
  "variant": {"variant_id": "oat-linen", "options": {"colour": "Oat"}, "resolved": "first"},
  "variants": [{"variant_id": "oat-linen", "options": {…}}, {"variant_id": "charcoal-wool", "options": {…}}]}]}
```

* ≤ 100 lines (413 `too_large`, `data.max_items`); 422 `validation_failed` for an unknown region or a malformed line (Id32, SKU and variant 1..64).
* `status`: `found`, `withdrawn` (published once, then withdrawn, hidden or its supplier suspended: 5.4's 410 case, named), `not_found` (never published, back in review, unknown product or version; a never-published product is not named).
* `variant.resolved`: `asked` (the product has that variant, including one named `default`), `only` (`default` and a single visible variant), `first` (`default` and several: the first orderable in the region, else the first, as the app's `FCadProduct::DefaultVariant`).
* `variants` when the product has more than one visible variant (discontinued ones left out unless it is the line's own). `orderable` = the supplier's `payments_ready` (PF7's MINOR proposal (a)).

**Decision: a platform route, not new keys on 5.5.** 5.5's answers are contract fixtures (`prices-gb.json`, `prices-ae.json`, compared byte for byte and copied to the app's stub); names there would change the app's fixtures and need a MINOR change written on the app side first. Rejected: one 5.4 call per line (100 calls against the anonymous limit, and 5.4 needs a product id the URL does not carry).

### Data

None: no table, no migration. The route reads PF7's `suppliers`, `products`, `product_variants`, `variant_prices` and `variant_availability`.

### UI

| File | What |
|---|---|
| `src/app/market/basket/page.tsx` | metadata (`robots` noindex nofollow, `alternates.canonical: null`), h1 "Buy this look", the panel inside `Suspense` |
| `src/components/market/BasketPanel.tsx` | parse → 5.2 → `POST /market/basket` → 5.5 → lines, totals, the order form; data attributes for tests (`data-basket-state`, `data-line-state`, `data-total`, `data-kind`) |
| `src/lib/basket.ts` | pure, no imports (run by Node in pytest): `parseBasket`, `parseBasketQuery`, `basketQuery`, `canOrder`, `totalsByCurrency`, `orderLines`, `variantLabel`, `newIdempotencyKey` |
| `src/lib/basket-api.ts` | `marketRegions` (5.2), `describeBasket`, `priceBasket` (5.5), `placeBasketOrder` (5.7 with `Idempotency-Key`) |
| `src/lib/constants.ts` `MARKET_BASKET` | every string (at the end of the file) |

States: `empty`, `too-many`, `loading`, `error` (Try again), `region` (served regions offered), `ready` / `repricing`. Lines: `ok`, `notFound`, `variantNotFound`, `withdrawn`, `notSold`, `noPrice`, `unavailable`. The order form: full name and e-mail (filled from the account), address, city, postcode, phone, a message; delivery country = the region's country. Kind: `order` when every included line's supplier is `orderable`, else `quote` for the whole basket.

### Jobs / workers

None.

### Security and privacy

* Prices are never taken from the page: 5.7 prices every line again and compares `price_seen`.
* The route reveals only what 5.4 would: published products (and the name of one withdrawn after publication); never a product in review.
* The page keeps nothing: the basket lives in the URL; the session token stays where the site keeps it (`lib/api.ts`). Sign-in returns only to a same-site path (`safeNext`).
* `Idempotency-Key` (32 hex) per attempt: a retried click after a network error replays the first order; a 4xx answer gets a new key.

## Deliverables

- [x] `server/app/market/basket.py`, `server/app/routers/market_basket.py`, one import and one `include_router` line in `server/app/main.py`
- [x] `src/app/market/basket/page.tsx`, `src/components/market/BasketPanel.tsx`, `src/lib/basket.ts`, `src/lib/basket-api.ts`, `MARKET_BASKET` in `src/lib/constants.ts`
- [x] `server/tests/test_pf7b_basket.py`
- [x] this doc, the tracker row, the README section "Buy this look basket (PF7b)"

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_basket_lines_named_and_default_resolved` | pytest | names and supplier; `default` → `first` (first in stock of three, with the choices), `only`, `asked` (a variant named `default`); an explicit variant kept, its siblings offered; withdrawn named; never-published, unknown version and unknown product `not_found`, the unpublished one unnamed |
| `test_basket_lines_orderable_follows_payments` | pytest | `orderable` true for an onboarded supplier with payments on, false for one not onboarded |
| `test_basket_lines_validation` | pytest | 100 lines pass, 101 → 413 `too_large`; unknown region, bad hex, SKU of 65, empty variant → 422; no items → empty answer |
| `test_basket_lines_need_no_credential_and_are_rate_limited` | pytest | no credential needed (a bad token ignored); past the per-address limit → 429 with `retry_after_s` |
| `test_basket_flow_prices_then_orders` | pytest | the page's sequence: names → 5.5 with the resolved variants (two priced, one `not_found`) → 5.7 with `Idempotency-Key` and `price_seen` → `awaiting_payment` with the checkout URL; the same key replays; a changed price → 409 `price_changed` |
| `test_basket_quote_only_supplier_sends_a_request` | pytest | payments off: `orderable` false, a request for quote answers `submitted` |
| `test_basket_parser_items` | pytest (Node) | the app's encoded link (`%2C`, `%3A`); decoded once (`%253A` stays `%3A` in a SKU); upper-case hex accepted and lowered; empty segments skipped; malformed, bad hex (3 chars, 33 hex), SKU and variant 0 / 65 characters, qty 0, 100, 1.5, -1 rejected with their positions; 64 characters accepted; duplicates merged; 100 items read, 101 refused; region forms; `basketQuery` round-trips |
| `test_basket_parser_totals_and_order_lines` | pytest (Node) | totals per currency in first-seen order, excluded and unpriced lines left out; order lines merged with `price_seen`; idempotency keys 32 hex and fresh; `canOrder`; `variantLabel` |
| `test_site_pf7b_basket_noindex` | build check | `out/market/basket/index.html` exists, noindex, one h1 "Buy this look", no canonical link, no basket data in the shell, absent from the sitemap |
| `test_site_pf7b_copy_and_sources` | build check | `MARKET_BASKET` names no other product, engine or payment company, no "!"; the page's metadata; 5.5, 5.7 with `Idempotency-Key` and the basket route in the client; the checkout, login and signup hand-offs; no hard-coded colours |
| `npm run lint`, `npm run build`, `pytest` | gate | green (`scripts/autopilot-verify.ps1`) |

Every test failed on the unchanged code (route 404, `basket.ts`, `MARKET_BASKET` and the page missing); the build check skipped until `out/` was built and then passed.

## Human test

Local API on port 8000 with the trial catalogue, the site built against it and served with `scripts\autopilot-serve.ps1`.

1. In `server\` (PowerShell): `$env:DATABASE_URL='sqlite:///./pf7b-try.db'; $env:API_URL='http://127.0.0.1:8000'; $env:MARKET_PAYMENTS_ENABLED='true'; $env:CORS_ORIGINS='http://127.0.0.1:3100,http://127.0.0.1:3164'` (`API_URL` makes the product pictures load from the local API), then `.venv\Scripts\python.exe scripts\seed_market.py --fixture tests\contracts\marketplace --payments-ready` → "supplier Nord Living (f8afe1ba…): verified" and the products; then `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` (leave it running).
2. In the worktree root, another PowerShell: `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build`, then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → it prints the port (3164 for T64, 3100 when `AUTOPILOT_TASK_ID` is unset).
3. Open `http://127.0.0.1:<port>/market/basket?region=GB&items=f8afe1ba2b0bf97f23ef888f040cf46a%3ASOFA-OSLO-3%3Aoat-linen%3A1%2Cf8afe1ba2b0bf97f23ef888f040cf46a%3APAINT-CHALK%3Adefault%3A4%2Cf8afe1ba2b0bf97f23ef888f040cf46a%3ANOPE-NOT-LISTED%3Adefault%3A1` (no trailing slash, as the app writes it) → the address gains `/market/basket/?…`; "Buy this look"; "Prices for United Kingdom, in GBP"; Oslo 3-seater sofa, Nord Living · 3-seater, Oat, Linen, Qty 1 × GBP 1,299.00, In stock, with a Version list; Chalk White matt emulsion, Qty 4 × GBP 42.00 = GBP 168.00 (the link said `default`); NOPE-NOT-LISTED "Not found in the catalogue. Left out of the total."; Products total GBP 1,467.00; "Sign in" and "Create an account".
4. Click "Create an account", sign up → back on the same basket with "Send the order", your e-mail filled in. Type a name, an address and a city; click "Place order" → the checkout page: "Awaiting payment", the sofa and the paint, delivery GBP 49.00, total GBP 1,516.00, a Pay button (it answers that payments are not configured: Stripe keys are not set locally).
5. Version: change the sofa's Version to "3-seater, Charcoal, Wool" → GBP 1,449.00, "Made to order · 42-day lead time", the total follows. Substitutes: open the same URL with `TABLE-AKER-CT%3Adefault%3A1` as an item → "Discontinued … Left out of the total" and "Similar products: Fjord coffee table … Use this instead"; click it → the Fjord table is in the basket and the total.
6. Region: replace `region=GB` with `region=FR` → "Truebex suppliers do not deliver to FR yet. Choose a region they serve:" with United Kingdom · GBP and United Arab Emirates · AED; click the second → AED prices.
7. Quote only: stop the API, start it again without `MARKET_PAYMENTS_ENABLED` (step 1's other variables kept), reload the basket → the button reads "Request a quote" with the quote note; send it → the checkout page shows "Sent to the supplier" and "This is a request for quote …"; Dashboard → Orders lists it.
8. In the app (a build with PR2 and MK1 pointed at the local API): apply a marketplace theme, click "Buy this look" → the browser shows the theme's products with prices. Or copy the URL the app logs (`MWTHEME basket theme='…' lines=… url=…`), replace `https://truebex.com` with `http://127.0.0.1:<port>` and open it.

## Risks / traps

* **Static export:** the query is read in the browser inside `Suspense`; the shell holds no basket data. Never run `next dev` to try it (RAM): build and serve `out/`.
* **Decode once:** URLSearchParams has decoded the items value; decoding fields again would turn a SKU's literal `%3A` into a separator.
* **Separators in a SKU:** the app joins fields with `:` and `,` without escaping them, so a SKU or variant holding either cannot be read (listed under "Not read from the link"); proposal below.
* **Root canonical:** `src/app/layout.tsx` gives every page `canonical: "/"`; a per-person page must drop it (`alternates: { canonical: null }`), or crawlers are pointed at the home page.
* **Rate limit:** the page makes three anonymous reads per load (5.2, the basket route, 5.5) against `MARKET_READS_PER_MINUTE` (120).
* **The site's API URL is baked in at build time:** a human test against the local API needs a rebuild with `NEXT_PUBLIC_AUTH_URL` and the served origin in `CORS_ORIGINS`.

## As-built

* **Date, branch, commits:** 2026-10-13, `ap/t64-pf7b-the-buy-this-look-basket-pa` from `master` 9dac34b. The tests first (`2fc9e0c`, all failing), then the route, the page and its modules (`89843bf`), then this doc, the tracker row and the README section.
* **Counts:** pytest in the verify gate 669 → 679 collected (652 → 662 passed, 17 Postgres skipped); the gate green in 1,277 s (pytest 741 s); 10 new tests in `test_pf7b_basket.py` (6 API, 2 parser through Node, 2 site). Pages in `out/`: one more `index.html` (`/market/basket/`, noindex, not in the sitemap; the sitemap is unchanged). One platform route (`POST /market/basket`); no table, no setting, no environment key.
* **Self-test beyond pytest** (local API on :18064 with `seed_market.py --payments-ready` and `MARKET_PAYMENTS_ENABLED=true`, `out/` built with `NEXT_PUBLIC_AUTH_URL=http://127.0.0.1:18064`, served by `scripts/serve-out.py` on :3164, headless Edge 155 over CDP, `cdp_pf7b.mjs` in the task's scratchpad), every step on the app's slash-less URL:
  1. Signed out, `region=GB` with the sofa (`oat-linen`), the paint (`default`, qty 4) and `NOPE-NOT-LISTED`: two priced lines (GBP 1,299.00; 4 × GBP 42.00 = GBP 168.00, the paint's `default` resolved to `2-5l`), one "Not found in the catalogue. Left out of the total.", Products total GBP 1,467.00 (`data-total` 146700), Sign in / Create an account.
  2. "Sign in" → `/login/?next=%2Fmarket%2Fbasket%2F%3Fregion%3DGB%26items%3D…` → logged in through the form → back on the same basket, e-mail filled in.
  3. "Place order" → `/market/checkout/?order=<id>`, `awaiting_payment`, total GBP 1,516.00 (GBP 49.00 delivery).
  4. The sofa's GB price raised to 134 900 after the page priced it: "Place order" → 409, the notice "Prices changed since this page loaded…", total re-priced to GBP 1,517.00; "Place order" again → the checkout page, GBP 1,566.00.
  5. `region=FR` → "Truebex suppliers do not deliver to FR yet…" with United Kingdom · GBP and United Arab Emirates · AED; the second → AED 1,299.00.
  6. Sofa `default` → "Comes in 2 versions: the first one in stock is shown", Version Oat; Charcoal chosen → GBP 1,449.00, made to order, 42 days, the list still there. The discontinued Aker table (`default`, qty 2) → "Not available to order now", Similar products: Fjord coffee table GBP 279.00 → "Use this instead" → Fjord in the basket, total GBP 2,007.00.
  7. A bad hex, a quantity 0 and a three-field item → "Not read from the link" with each reason; the sofa still priced.
  8. The supplier not onboarded (`connect_ready` false): "Request a quote" and the quote note → the checkout page shows the request, `submitted`.
  Console: only the 409 of step 4 and `serve-out.py`'s 404s for Next's prefetch files (`__next.*.txt`, known noise). Screenshots checked by eye (dark theme tokens, one column, the form two columns from `sm`).
* **Deviations from the brief and why:**
  1. *A platform route for names and `default`* (Design, Decision): 5.5 answers no names, and putting them there would change the contract's 5.5 fixtures and the app's stub. Prices, availability and substitutes still come from 5.5 itself.
  2. *`default`*: the contract names a single variant `default` (§6.3) and the JSON importer stores it so, but a CSV feed names every variant (the fixture's paint is `2-5l`), so the route maps `default` to the product's only variant, and for several to the first in stock in the region (the app's `DefaultVariant` rule), with the versions offered. 5.5 and 5.7 then get the real variant id: no wire change.
  3. *Every multi-version product offers its versions*, not only a `default` one: after a choice the list must stay, so the person can go back.
  4. *Unavailable lines are left out* of the total and the order like unknown ones (out of stock, discontinued, withdrawn, not sold in the region, no price), each with its reason and 5.5's substitutes; a request for quote could carry an out-of-stock line, but one rule for both kinds is clearer.
  5. *A mixed basket* (some suppliers orderable, some quote-only) goes as one request for quote; the person accepts the quotes from Orders (PF7's accept turns them into an order). Both kinds land on `/market/checkout/?order=<id>`, which shows a request with its quote note. With `MARKET_PAYMENTS_ENABLED` off (the default until GD5) every basket is a request for quote today.
  6. *Contact and delivery are asked on the page* (5.7 requires them; the URL carries none); the delivery country is the region's; `project` is left empty (the URL carries no theme name).
  7. *Duplicates*: the same product and version twice is one line with both quantities (5.7 refuses a line listed twice); two items that resolve to the same variant are merged when the order is sent.
  8. *English only*: the market pages (`/market/checkout/`, Orders) are English only today, so `MARKET_BASKET` has no Arabic.
  9. `og:url` still reads the root's `https://truebex.com/`, as on `/market/checkout/`: it is not a canonical, and the page is noindex.
* **Proposals for the app side** (no wire change here; for the contract's *Changes* when the app adopts them): (a) encode each field before joining (`UrlEncode(sku)` etc.) and mark the link `&v=2`, so a SKU or variant holding `:` or `,` survives; the page would then decode each field once more for `v=2` only. (b) Cap a line's quantity at 99 in `BasketUrl` (the page refuses 0 and anything over 99). (c) Add `&name=<theme name>` so the order carries it as `project.name`. (d) A dated PATCH line in §3: "2026-10-13 · PF7b: `https://truebex.com/market/basket/` is live; `default` names the product's only variant, or the first in stock of several."
* **Contract §11:** no row (the route is platform-internal; 5.2, 5.5 and 5.7 are PF7's rows).
* **Carry-over:** MK4 (the app's own order flow replaces "Buy this look"'s hand-off); an Arabic basket with the other market pages; the proposals above (app side).
