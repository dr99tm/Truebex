# PF7e — The marketplace follows marketplace-api 1.2.0 (MK4, MK2): each supplier's name, delivery window and items with quoted prices, the order's web page, 5.7's error data, and the app's new marketplace fixtures re-copied (launch priority 2)

**Needs merged:** PF7, PF7b, PF7c, PF7d, PF8 (all on `master`; this task started from faf1686); on the app side MK2 (regional pricing, `f86eb7d11`, T179) and MK4 (orders and leads from the app, `e1b99b61f`, T180), both on the app's `main` since 2026-10-18. **Unblocks:** MK4's carry-over "PF7's live 5.7-5.10" (the platform's side; going live is the owner's); MK4's "Open on the web". **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\marketplace-api.md` 1.2.0 (its two 2026-10-18 Changes lines, 5.5, 5.7-5.10 with their (1.2.0) paragraphs, §7's two (1.2.0) rows, §9 "(1.2.0) The stub's orders", §10 `test_order_idempotency_and_project_filter`). The app side is authoritative (C.9); the PATCH and §11 lines below are for the owner to put there.

## Status

**Built (2026-10-20, branch `ap/t91-pf7e-the-marketplace-follows-mar`, Autopilot T91); see As-built.** Checked on `master` faf1686 against the app's `main` 689da345d before the work began:

| # | Where (master faf1686) | Before |
|---|---|---|
| 1 | `server/tests/contracts/marketplace/` | PF7d's copy (app 180b2d53f, 36 files). The app's folder at 123b88c59 (its last commit on `main`): 40 files; 7 changed (`README.md`, `categories.json`, `products.json`, `prices-gb.json`, `prices-ae.json`, `order-awaiting-payment.json`, `order-quoted.json`), 4 new (`geometry/table-sund.glb`, `geometry/table-vik.glb`, `thumbs/table-sund.png`, `thumbs/table-vik.png`), 29 the same. The brief counted 12; the listing has 11 |
| 2 | `server/app/market/seed.py` `_load_stub` | one `availability` per variant for every region; products.json's per-region `availabilities` (MK2) ignored, so the Oslo sofa (Oat) read in stock in AE |
| 3 | `server/app/market/orders.py` `order_json` | no `web_url`; each supplier group `supplier_name`, `delivery_days {min, max}`, no `items`; the lines top-level with `price` and `quoted_price` |
| 4 | `orders.py` `place` | the 409 `unavailable` quote-only branch sent lines without `availability`; a withdrawn line's availability was its stock row (could read `in_stock`); a line its supplier does not price in a region it serves was 422 `region_not_served` ("does not deliver to …") |
| 5 | `server/app/market/common.py:14`, `server/scripts/export_openapi.py` `CONTRACTS` | `marketplace-api/1.1` |
| 6 | `src/app/dashboard/orders/page.tsx` | the buyer's 5.8 list; reads no query |
| 7 | `server/app/market/taxonomy/categories.json` | the app's `CAD/taxonomy/categories.json` before MD5 (app 83ca33a3c, 2026-10-17, the `outdoor` row: `align` `OnTerrain`, tags `tree`, `shrub`, `bollard`): `test_market.py::test_categories_root_on_app_taxonomy` was already red on this PC on faf1686 (it compares the copy with the app's checkout) |

Already 1.2.0 on faf1686 (built by PF7, T6, `258a50e`): `project.project_uid` stored (`market/models.py:310`, `orders.py:236`) and 5.8's `?project_uid=` (`orders.list_orders`, `routers/market.py:181`); 5.8 newest first; `Idempotency-Key` replays the first answer and another body is 409 `idempotency_mismatch` (PF7's deviation 9); 422 `region_not_served` with `data.suppliers [{supplier_id, name}]`; 409 `price_changed` with `data.lines {supplier_id, sku, variant_id, price}`; 5.5's 413 `too_large` over 500 items and null price and availability for a line it cannot price (MK2's PATCH wording).

## Goal

The app's Orders tab (MK4) talks to the platform the way it talks to its stub: an order or a request for quote answers each supplier's name, delivery window and items with the unit price each line was placed at and, once the supplier quotes in its inbox, the quoted one, so the app shows the platform's own figures; "Open on the web" opens the order on truebex.com; every refusal of 5.7 carries the data the app reads to explain it. The platform keeps testing against the app's own marketplace files, byte for byte.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4; PF7c's and PF7d's docs (the Differences table D1-D17, the masks).
* The contract sections named above; the app's `Plugins/CADTOOL/Source/TruebexMarket/Private/CadOrders.cpp` (`CadMarketParse::OrderJson`, the 409 / 422 branches of `PostLines`) and `CadMarketStub.cpp` (how the stub builds 5.7).
* `server/app/market/orders.py`, `seed.py`, `server/tests/test_market_contract_fixtures.py`, `src/app/dashboard/orders/page.tsx`, `.claude/skills/truebex-brand-voice`.

## Scope

**In:**

1. The fixtures re-copied with `scripts\sync-contract-fixtures.ps1 -Contract marketplace` (the README is the app's, part of the set); `APP_BLOBS` from the app's listing at 123b88c59; the folder pinned by its git tree id.
2. The seed reads `availabilities` per region (the Oslo sofa, Oat, low stock in AE); every test reading the catalogue follows the 15 products; the new tables' geometry and thumbnails through the seed.
3. The order object gains 1.2.0's keys, all additive: `web_url`; per supplier `name`, `days_min`, `days_max`, `items [{sku, variant_id, qty, price_seen, quoted}]`. `created_at`, `region`, `project` checked; §5.7's arithmetic checked.
4. 5.7's error data per §7 (1.2.0): every 409 `unavailable` line carries `availability`, the quote-only branch included.
5. 5.10 checked (200, the whole order, `cancelled`).
6. The wire header `marketplace-api/1.2`; v1.json and the SDK operations regenerated.
7. `/dashboard/orders/?order=<id>`: that order first and highlighted, fetched with 5.9 when not on the first page; signed out, back to the same URL after signing in; an unknown or another account's order: a short note.
8. This doc, the PF7e tracker row, a README section.

**Out (and where it goes):**

* Running the API in production and the app's steps on the release build: the owner (api.truebex.com must be up; MK4's human test steps 1-5 then run on the release build).
* PR2's "Buy this look" basket hand-off: unchanged (PF7b's page).
* Supplier-side changes beyond what Scope 3 needs: PF8 (the inbox's own JSON is unchanged).
* Payment providers and prices: GD7, the owner.
* The light clients' header (PF9's web client, PF10's Android app, `mobile/clients.py` `MARKET`): kept at 1.1 (Deviation 3).

## Design

**API (5.7-5.10, additive).** `orders.order_json` adds:

```json
{"order_id": "…", "kind": "order", "state": "awaiting_payment", "checkout_url": "https://truebex.com/market/checkout/?order=<id>",
 "web_url": "https://truebex.com/dashboard/orders/?order=<id>", "created_at": "…Z", "region": "AE",
 "project": {"name": "MK4-living-room-basket", "project_id": null, "project_uid": "0192f6a13c4d7e5f8a6b1c2d3e4f5a6b"},
 "suppliers": [{"supplier_id": "…", "name": "Nord Living", "state": "pending", "lines": 2,
   "subtotal": {"amount": 309700, "currency": "AED", "exponent": 2}, "delivery": {"amount": 15000, "currency": "AED", "exponent": 2},
   "days_min": 7, "days_max": 14,
   "items": [{"sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "qty": 2, "price_seen": {…§6.3}, "quoted": null}, …],
   "supplier_name": "Nord Living", "tax": {…}, "total": {…}, "delivery_days": {"min": 7, "max": 14}, "quote": null, "reason": null}],
 "lines": [… the platform's own, unchanged], "total": {"amount": 343100, "currency": "AED", "exponent": 2}, …}
```

`web_url` is built from `SITE_URL` like `checkout_url` (`orders.web_url`). `price_seen` is the §6.3 unit price the line was placed at (amount, currency, exponent, region, tax rule, `at` = the price's own time); `quoted` the supplier's quoted unit price as §6.3, `at` = when it quoted, `null` until it quotes (a line of an order made from an accepted quote keeps its quoted price). Nothing is renamed or removed: the web's pages read `supplier_name`, `delivery_days` and the top-level `lines` as before.

**5.7's checks.** In order: a supplier whose active regions lack the order's region → 422 `region_not_served` (`data.suppliers`, `data.lines`); unknown, withdrawn, discontinued, out-of-stock (orders only) lines and a line its supplier does not price in a region it serves → 409 `unavailable`, each line `{supplier_id, sku, variant_id, reason, availability}` (`availability` null for `not_found` and `not_sold_in_region`, `discontinued` for `withdrawn` as 5.5 answers it, else the region's own); quote-only suppliers on an order → 409 `unavailable` with `reason: quote_only`, each line with its availability; then `price_changed`.

**Data.** No table or column. The seed projects `availabilities[<region>]` (else `availability`) into each region's `variant_availability` row; a variant's `discontinued` status still comes from its own `availability`.

**UI.** `/dashboard/orders/` (`page.tsx`) reads `?order=` on the client (Suspense, static export): `src/lib/order-link.ts` (`linkedOrderId`, `linkedOrderToFetch`, `orderLinkView`) puts a listed order first; one not on 5.8's first page (50) is asked of 5.9 and put first; a 404 / 403 / malformed id shows `MARKET_ORDER_LINK.notFound`. The list moved into `src/components/market/OrderList.tsx` (each card `data-order`, the linked one `data-focused`, `aria-current`, an accent ring, `MARKET_ORDER_LINK.linked` above it, scrolled into view). Copy (end of `constants.ts`, brand voice): "The order you opened", "This order is not in this account. Sign in with the account that sent it from Truebex." Signed out, DashboardShell already sends the visitor to `/login/?next=<path + query>` and the login page returns there.

**Security and privacy.** 5.9 keeps its owner check (403 for another account's order); the page shows the same note for 403 and 404, so a link never tells whether another account's order exists. `?order=` is matched against 32 hex before any call.

## Deliverables

- [x] `server/tests/contracts/marketplace/` = the app's 40 files at 123b88c59 (tree `2a1a2ace5d42d95335411c3c5c99576017a7ed23`)
- [x] `server/app/market/seed.py` (`availabilities`), `orders.py` (`web_url`, the 1.2.0 keys, `_availability_of`, the unpriced-line check), `prices.py` (`withdrawn_availability`), `common.py` (1.2), `schemas.py` (comment), `routers/market.py` (docstring), `taxonomy/categories.json` (the app's, after MD5)
- [x] `server/scripts/export_openapi.py` (`CONTRACTS` 1.2), `openapi/v1.json`, `sdks/python/truebex/_operations.py`, `sdks/js/src/operations.mjs`
- [x] `server/scripts/market_try.py` (`--basket mk4`, `--json`, prints `web_url`), `seed_market.py` (docstring); PF7's fixture answers regenerated (`make_market_fixtures.py`)
- [x] `src/app/dashboard/orders/page.tsx`, `src/components/market/OrderList.tsx`, `src/lib/order-link.ts`, `src/lib/market.ts` (types, 1.2), `src/lib/basket-api.ts` (1.2), `MARKET_ORDER_LINK`
- [x] `server/tests/test_pf7e_marketplace_1_2.py` (13), `server/tests/test_site_pf7.py` (2) + `server/tests/orders_render.cjs`; the moved assertions (As-built)
- [x] this doc, the PF7e tracker row, `README.md` section "Marketplace API 1.2.0 (PF7e)"

## Tests

| Name | Kind | Asserts | On faf1686 |
|---|---|---|---|
| `test_pf7e_folder_is_the_apps_at_the_recorded_commit` | pytest | the folder's git tree id = the app's at 123b88c59; `APP_BLOBS` makes the same tree (40 files); 15 products, Halden's three substitutes, the Oat sofa's `availabilities`, the order fixtures' 1.2.0 keys | failed: tree `855840a2…` |
| `test_pf7e_recorded_blobs_are_the_apps_at_the_commit` | pytest (skipped without the app repo) | `git ls-tree -r 123b88c59` = `APP_BLOBS`; `git rev-parse` = the tree id | failed: 11 ids differ |
| `test_order_idempotency_and_project_filter` (§10) | pytest | the same key and body: the same order (the whole 1.2.0 answer, `Idempotency-Replayed`), one row stored; another body 409 `idempotency_mismatch`; 5.8 `?project_uid=` keeps a cloud project's two (newest first) and a local one's one (`project_id` null); another account sees none; the 1.2 header, a 1.1 reader served, 2.0 refused naming 1.2 | failed: header 1.1, no `web_url` |
| `test_order_awaiting_payment_like_the_apps_fixture` | pytest | MK4's basket (AE, payments ready) answers the fixture: each supplier's id, name, state, lines, subtotal (D7), delivery, days; each item's sku, variant, qty, the whole `price_seen`, `quoted` null; the total (AED 3,431.00); masks below; §5.7's arithmetic on both; 5.9 the same | failed: no `name` |
| `test_order_quoted_like_the_apps_fixture` | pytest | the same basket as a quote; Nord Living quotes in the inbox: its items' `quoted` set, Atelier Lumen's still null; then Atelier Lumen: 5.9 = order-quoted.json (quoted at masked), subtotals 281,900 / 14,500, total AED 3,139.00 | failed: no `items` |
| `test_oslo_oat_availability_per_region` | pytest | the Oat sofa low stock (3) in AE, in stock (12) in GB: 5.5 = prices-<region>.json, 5.3's hit, 5.4; the Charcoal variant its one availability | failed: AE `in_stock` |
| `test_batch_prices_new_lists_and_limits[GB]`, `[AE]` | pytest | 5.5 for the new lists (14 lines, Sund and Vik last) as the file; an unknown line price and availability null; 501 items 413 `too_large` | failed: 12 lines |
| `test_unavailable_lines_carry_availability` | pytest | quote-only: every line `reason: quote_only` with its availability (the Oat sofa `low_stock`); discontinued, withdrawn (`discontinued`), unknown (null), not priced in a served region (`not_sold_in_region`, null); a supplier not serving AE 422 `region_not_served` `[{supplier_id, name}]` | failed: no `availability` on quote-only lines |
| `test_price_changed_lines_name_supplier_and_unit_price` | pytest | 409 `price_changed` `{supplier_id, sku, variant_id, price}` (the unit price now); the resend placed, its item's `price_seen` that price | failed: no `items` |
| `test_cancel_answers_the_whole_order[order]`, `[quote]` | pytest | 5.10 → 200, `cancelled`, suppliers cancelled, `web_url`, items; 5.9 the same | failed: no `web_url` |
| `test_totals_where_a_price_excludes_tax` | pytest | a GBP price without tax (the Arc light × 2): subtotal 25,800, delivery 900, the group's total + 5,160 tax; the order's total = Σ (subtotal + delivery) + 5,160 | failed: no `items` |
| `test_site_pf7e_orders_page_shows_the_linked_order` | build check (Node render, `orders_render.cjs`) | real 5.8 / 5.9 answers through `orderLinkView` and `OrderList`: no link as listed; a listed link first, one `data-focused`, "The order you opened"; not on the first page: 5.9 asked, then first; 404 / 403 / malformed: the note, nothing highlighted; an upper-case id matches | failed: no `web_url` (and no component) |
| `test_site_pf7e_orders_page_built_with_the_link_note` | build check (`out/`) | `/dashboard/orders/` noindex; its chunks carry both `MARKET_ORDER_LINK` strings | failed when built (no copy) |
| the 14 suites the brief names | pytest | green after the moves listed in As-built | 1 red on faf1686 (the taxonomy, row 7) |
| `npm run lint`, `npm run build` | build check | green | |

## Human test

About 10 minutes. Window 1 (PowerShell), in the worktree's `server` folder:

1. `$env:DATABASE_URL='sqlite:///./pf7e-try.db'; $env:STORAGE_DIR='./pf7e-try-storage'; $env:API_URL='http://127.0.0.1:8000'; $env:SITE_URL='http://127.0.0.1:3191'; $env:CORS_ORIGINS='http://127.0.0.1:3191'; $env:MARKET_PAYMENTS_ENABLED='true'`, then `Start-Process -WorkingDirectory $PWD .venv\Scripts\python.exe '-m uvicorn app.main:app --host 127.0.0.1 --port 8000'` → a new window with the API (it inherits the variables; keep it open: the supplier mails print there).
2. Two accounts: `foreach ($e in 'buyer@example.com','owner@example.com') { Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/register -ContentType 'application/json' -Body ('{"email":"' + $e + '","password":"password123"}') | Out-Null }` → no output.
3. `.venv\Scripts\python.exe scripts\seed_market.py --fixture tests\contracts\marketplace --owner owner@example.com --payments-ready` → `supplier Nord Living (4e6f…0001): verified`, Atelier Lumen, Gulf Paints, `feed: not imported …`, then 15 lines `approved`, among them `TABLE-SUND Sund coffee table` and `TABLE-VIK Vik coffee table`.
4. `(Invoke-RestMethod -Method Post http://127.0.0.1:8000/market/prices -ContentType 'application/json' -Headers @{'X-Truebex-Contract'='marketplace-api/1.2'} -Body '{"region":"AE","items":[{"supplier_id":"4e6f72644c6976696e67000000000001","sku":"SOFA-OSLO-3","variant_id":"oat-linen"}]}').items[0].availability` → `low_stock 3`. The same with `"region":"GB"` → `in_stock 12`.
5. The order: `.venv\Scripts\python.exe scripts\market_try.py --email buyer@example.com --password password123 --basket mk4 --kind order` → `order <id>: awaiting_payment, total AED 3,431.00`, `Nord Living: pending, 2 lines, delivery in 7-14 days`, `Atelier Lumen: pending, 1 lines, delivery in 5-9 days`, `checkout: …`, `web: http://127.0.0.1:3191/dashboard/orders/?order=<id>`. Keep the `web:` line.
6. The request: the same command with `--kind quote` → `quote <id>: submitted, total AED 3,431.00`, both suppliers `submitted`, `web: …?order=<quote id>`. The API window prints two mails "New request for quote" with `http://127.0.0.1:3191/supplier/inbox/?order=<quote id>`.
7. 1.2.0's keys: `$t = (Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/login -ContentType 'application/json' -Body '{"email":"buyer@example.com","password":"password123"}').access_token; $h = @{Authorization = "Bearer $t"; 'X-Truebex-Contract' = 'marketplace-api/1.2'}; $o = Invoke-RestMethod http://127.0.0.1:8000/market/orders/<order id> -Headers $h; $o.web_url; $o.suppliers | Format-Table name, state, days_min, days_max, @{n='subtotal';e={$_.subtotal.amount}}, @{n='delivery';e={$_.delivery.amount}}; $o.suppliers.items | Format-Table sku, variant_id, qty, @{n='price_seen';e={$_.price_seen.amount}}, quoted; $o.total.amount` → the web URL; Nord Living `pending 7 14 309700 15000`, Atelier Lumen `pending 5 9 15900 2500`; `SOFA-OSLO-3 oat-linen 2 129900`, `TABLE-FJORD oak 1 49900`, `LIGHT-ARC-W brass 1 15900` (quoted empty); `343100`.

Window 2 (PowerShell), in the worktree root:

8. `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build` (about 3 min), then `$env:AUTOPILOT_TASK_ID='T91'; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → `serving … on http://127.0.0.1:3191/`.

Browser:

9. `http://127.0.0.1:3191/login/` → sign in as owner@example.com / password123, then open the mail's link `http://127.0.0.1:3191/supplier/inbox/?order=<quote id>`. In the sidebar's "Supplier" list pick "Nord Living · Owner" (the page reloads) → the request is open: "2 × Oslo 3-seater sofa" (Listed AED 1,299.00), "1 × Fjord coffee table" (AED 499.00). Type `1180.00` and `459.00` under "Your price (each) (AED)", leave the delivery fee at 150.00, click "Send quote" → the request reads "Quoted".
10. Pick "Atelier Lumen · Owner", open the same link, type `145.00` for the Arc wall light, "Send quote" → "Quoted".
11. Sign out (the account menu), then paste the order's `web:` URL from step 5 → the login page; sign in as buyer@example.com / password123 → back on Orders with that order first, in a blue frame, "The order you opened" above "Order · <today> · Project: MK4-living-room-basket", "Awaiting payment"; Nord Living: Oslo 3-seater sofa "Qty 2 × AED 1,299.00 each" AED 2,598.00, Fjord coffee table AED 499.00, "Delivery in 7–14 days" AED 150.00, Total AED 3,247.00; Atelier Lumen: Arc wall light AED 159.00, "Delivery in 5–9 days" AED 25.00, Total AED 184.00; Total AED 3,431.00; "Pay now", "Cancel".
12. Paste the quote's `web:` URL → that request first, framed: "Quoted"; "Qty 2 × AED 1,180.00 each · Quoted", Fjord AED 459.00, Nord Living Total AED 2,969.00; Arc wall light AED 145.00, Total AED 170.00; Total AED 3,139.00; "Accept quote".
13. Change the id in the address to `abababababababababababababababab` → "This order is not in this account. Sign in with the account that sent it from Truebex." above the list, no frame.
14. Window 1: `$q = Invoke-RestMethod http://127.0.0.1:8000/market/orders/<quote id> -Headers $h; $q.suppliers.items | Format-Table sku, qty, @{n='seen';e={$_.price_seen.amount}}, @{n='quoted';e={$_.quoted.amount}}; $q.total.amount` → `118000`, `45900`, `14500`; `313900`. Then `(Invoke-RestMethod -Method Post http://127.0.0.1:8000/market/orders/<order id>/cancel -Headers $h) | Format-List state, checkout_url, web_url` → `cancelled`, empty, the web URL.
15. Clean up: close the API window, Ctrl+C in window 2; in `server`: `Remove-Item -Recurse -Force pf7e-try.db, pf7e-try-storage`; in the root: `Remove-Item -Recurse -Force out` (it points at the local API; the next serve rebuilds it against `.env.local`).

Optional, the app (not run by this task): the MK4 build with `run.bat -mwmarket=live -mwapi=http://127.0.0.1:8000 -mwordersopen -mwproject=<app worktree>\Docs\roadmap\fixtures\MK4-living-room-basket.tbxp` (MK4's human test, without `-mwmarket=stub`; signing in needs the licence API on the same local server, `docs/roadmap/40/PF1-*.md`) sends the same basket; its card's "Open on the web" opens the `web_url` above.

## Risks / traps

* **The folder's README is the app's** (PF7d's trap): never edit it; the app commit and tree id live in `test_pf7e_marketplace_1_2.py` and `APP_BLOBS`' comment.
* **The app's taxonomy file moves without a contract line.** MD5 changed one row on 2026-10-17 and the platform's copy (byte for byte, CRLF as checked out, `-text`) went stale: `test_categories_root_on_app_taxonomy` and 5.1's `taxonomy_sha256` both catch it. Re-copy `CAD\taxonomy\categories.json` from the app's checkout, then `server\scripts\make_market_fixtures.py` (PF7's 5.1 answer carries the hash).
* **Windows PowerShell 5.1 and JSON bodies:** `curl.exe -d '{"…"}'` loses the quotes; the steps use `Invoke-RestMethod -Body` (checked literally on 5.1).
* **`SITE_URL` makes `web_url`:** for the human test it is the served build's origin (3191 for T91); `autopilot-serve.ps1` serves on 3100 when `AUTOPILOT_TASK_ID` is unset, hence step 8 sets it.
* **Headless Edge's launcher detaches its children:** `taskkill /PID <spawned pid> /T` leaves them holding the profile folder; stop them by the profile path in their command line.

## As-built

* **Date, branch, commits:** 2026-10-20, `ap/t91-pf7e-the-marketplace-follows-mar` from `master` faf1686. `4c1a1c1` (tests first), `0632238` (the copy and the change), then the docs commit (this doc, the tracker row, the README section) and the verify-gate line.
* **Copy:** `scripts\sync-contract-fixtures.ps1 -Contract marketplace` from the app's `main` 689da345d ("copied 40 files … each byte-exact to the app's blob"; updated 11, unchanged 29, removed none). The folder's last commit there is **123b88c59** (MK4's As-built; MK2's 77a4c1f31 and MK4's 7f94ccb49 changed it before). The committed tree `git rev-parse HEAD:server/tests/contracts/marketplace` = `2a1a2ace5d42d95335411c3c5c99576017a7ed23` = the app's `123b88c59:Docs/roadmap/fixtures/contracts/marketplace`.
* **Counts:** pytest collected 886 → 901 (13 in `test_pf7e_marketplace_1_2.py`, 2 in `test_site_pf7.py`; `def test_` 809 → 822). **Tests first:** on faf1686 all 15 failed but `test_site_pf7e_orders_page_built_with_the_link_note` (skipped, `out/` not built; it fails on a faf1686 build: no copy); with the change all pass. The 14 suites the brief names plus `test_pf8b_listing_customer.py`, `test_pf12_api.py`, `test_routes_unique.py`, `test_pf14c_utc_times.py`: 152 passed, 14 skipped (the Postgres-only tests and the `out/` build checks) on SQLite; with `out/` built, `test_site_pf7.py` 3 of 3. **Postgres 17.10** (throwaway cluster, session zone Asia/Baghdad, `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`): the PF7e module and the 14 suites 136 passed, 3 skipped (all three `out/` build checks, `out/` not built). `npx tsc --noEmit` and eslint on the changed files clean. The verify gate: the last bullet.
* **The web_url decision:** `https://truebex.com/dashboard/orders/?order=<order_id>` (from `SITE_URL`, like `checkout_url`; D18). The static export cannot serve `/market/orders/<id>`, and the buyer's orders page already lists every order with its suppliers, payment and cancel buttons, so it is the order's page with that order first.
* **Self-test beyond pytest** (`selftest.sh` + `live_checks.py` + `cdp_pf7e.mjs` in the task's scratchpad: uvicorn on 127.0.0.1:18091 with `SITE_URL=http://127.0.0.1:13191` and `MARKET_PAYMENTS_ENABLED=true`, the app's catalogue seeded twice with `--owner --payments-ready` (the same output), `serve-out.py` :13191 on an `out/` built against that API, headless Edge; run on SQLite and again with the API on the Postgres cluster: 8 + 39 + 3 checks green both times). The answers (SQLite run; ids minted):
  * 5.5 / 5.3 the Oslo sofa (Oat): AE `129900 AED`, `{"state": "low_stock", "stock": 3, …}` (search hit the same); GB `109900 GBP`, `in_stock` 12.
  * `market_try.py --basket mk4 --kind order` → `order 41adeeda…dbb07: awaiting_payment, total AED 3,431.00`; 5.9: `web_url` `http://127.0.0.1:13191/dashboard/orders/?order=41adeeda9081ea9250cf4fc9db5dbb07`, `checkout_url` `…/market/checkout/?order=41adeeda…`, `created_at` `2026-10-20T08:22:32Z`, `region` AE, `project` `{"name": "MK4-living-room-basket", "project_id": null, "project_uid": "0192f6a13c4d7e5f8a6b1c2d3e4f5a6b"}`; Nord Living `pending`, 2 lines, subtotal 309700, delivery 15000, days 7-14, items SOFA-OSLO-3/oat-linen × 2 seen 129900 AED (`at` 2026-10-09T10:00:00Z) quoted null, TABLE-FJORD/oak × 1 seen 49900 quoted null; Atelier Lumen `pending`, 1 line, subtotal 15900, delivery 2500, days 5-9, LIGHT-ARC-W/brass × 1 seen 15900 quoted null; total 343100 AED (tax 16337 included). Equal to order-awaiting-payment.json with the masks.
  * `--kind quote` → `quote 12646a15…a0f1: submitted, total AED 3,431.00`; both suppliers quoted in the portal's inbox form (headless: "Your price (each)" 1180.00 / 459.00 for Nord Living, 145.00 for Atelier Lumen, "Send quote"); 5.9: `quoted`, `checkout_url` null; Nord Living `quoted`, subtotal 281900, delivery 15000, days 7-14, quoted 118000 / 45900; Atelier Lumen `quoted`, subtotal 14500, delivery 2500, days 5-9, quoted 14500; total 313900 AED (tax 14947 included). Equal to order-quoted.json with the masks.
  * 5.8 `?project_uid=0192f6a1…` → `[quote 12646a15, order 41adeeda]`, `next_cursor` null; with 50 more requests the plain 5.8's first page holds 50 and a cursor, the order not among them. The same key and body → the same order (`Idempotency-Replayed: true`); another body → 409 `idempotency_mismatch` "This Idempotency-Key was used for a different request. Send a new key."; another account's 5.9 → 403.
  * 5.10 of the order → 200, `cancelled`, both suppliers `cancelled`, `checkout_url` null, the same `web_url` and items.
  * Headless Edge: the order's `web_url` (past the first page: fetched with 5.9) → first, one framed card, "The order you opened", "Awaiting payment", both suppliers, AED 3,431.00, "Pay now"; the quote's → "Quoted", AED 3,139.00, "Accept quote"; a listed order's → first; an unknown id, a malformed one and another account's order → the note, nothing framed; signed out → `/login/?next=%2Fdashboard%2Forders%2F%3Forder%3D41adeeda…`, signed in → back on the same URL with the order first; no console error or exception.
* **Readings.** PF7c's D1-D16 and PF7d's D17 stand as written, but for the moved ones; "PATCH" = a dated line for the contract's §3 *Changes* the app side should consider.

  | # | Reading | Stub (app) | Platform | Action |
  |---|---|---|---|---|
  | D1 (moved) | 5.1 `furniture` count | 12 (10 before MK2) | 11: products.json files eleven products there | asserted; PF7d's PATCH stands with the new numbers |
  | D6 (kept) | `checkout_url` | `/market/checkout/<id>` | `/market/checkout/?order=<id>` | masked, as PF7c |
  | D7 (kept) | a group's `subtotal`, the `total` | a §6.3 price | money `{amount, currency, exponent}` (the app reads either: `includes_tax` defaults to true) | masked, as PF7c |
  | D13 (moved) | 5.4 410 `substitutes` of the Fjord, Sund and Vik tables | the discontinued Halden for each | the other orderable coffee tables, nearest in price, GB and AE alike: Fjord → Vik, Sund; Sund → Fjord, Vik; Vik → Fjord, Sund. Halden's three (Fjord, Sund, Vik) agree | asserted. PATCH: the stub's products.json lists the orderable tables (§5.5 "substitutes … when a line is unavailable": a discontinued product helps no one) |
  | D16 (moved) | 5.1 `taxonomy_sha256` | `57e1159e…` (the app's taxonomy after MD5) | the copy re-copied: `57e1159e…` again (was `7720dcfb…`; red on this PC since MD5) | fixed. PATCH: MD5 (83ca33a3c, 2026-10-17) changed the taxonomy's `outdoor` row without a Changes line; §3 calls that MINOR, so a line saying so (the platform follows the app's file) |
  | D18 (new) | `web_url` | `https://truebex.com/market/orders/<id>` | `https://truebex.com/dashboard/orders/?order=<id>` (a static page) | masked like D6. PATCH: "2026-10-20 · 1.2.0 (no version change, PATCH wording) · PF7e: `web_url` and `checkout_url` are whatever the platform answers; its pages are static, with the order in the query (`https://truebex.com/dashboard/orders/?order=<order_id>`, `/market/checkout/?order=<order_id>`); the examples' paths are the stub's." |
  | D19 (new) | the Oat sofa in AE in the app's feed files | `feed-two-regions.csv` / `.json`: stock 12, in stock (unchanged by MK2) | the feed imports as written: in stock 12; products.json's `availabilities` says low stock 3 | asserted in `test_feed_import_like_the_stub_report`. PATCH: the feed's AE row of `oat-linen` gets `availability` `low_stock` and stock 3 (CSV column `availability`; the JSON feed's per-region entry), or products.json drops the AE entry |
  | D20 (new) | §5.7 `total` with a price that excludes tax | not in the fixtures (GB and AE prices include tax) | `total` = Σ (`subtotal` + `delivery`) + the tax the platform adds (`tax`; the group's `total` too); with tax-inclusive prices the two are equal | asserted (`test_totals_where_a_price_excludes_tax`). PATCH: "§5.7: where a line's price excludes tax, the platform adds it: `total` = Σ (`subtotal` + `delivery`) + the added tax" |

  Fixed to agree with 1.2.0 and the stub's §9: a line its supplier does not price in a region the supplier serves is 409 `unavailable` (`reason` `not_sold_in_region`, `availability` null), not 422; a withdrawn line's availability reads `discontinued` in 5.7's 409 as in 5.5. Agreed without a difference: each supplier's delivery (the highest of its lines' fees) and window (the latest `days_min`, the latest `days_max`) as the stub computes them; `price_seen` byte for byte (its `at` is the catalogue's price time on both); 5.5's 14 lines in GB and AE; the Sund and Vik GLBs byte for byte through the seed, PF8's upload (no warning) and 5.4's link; the Halden's three substitutes.
* **D lines 1.2.0 adopted** (the platform already did these; the contract now says them): PF7's `project.project_uid` and 5.8 `?project_uid=` (PF7 built MK4's planned MINOR, `258a50e`), 5.8 newest first, the `Idempotency-Key` replay and 409 `idempotency_mismatch` (PF7's deviation 9), 422 `region_not_served` `data.suppliers [{supplier_id, name}]`, 409 `price_changed` `data.lines {supplier_id, sku, variant_id, price}` (the platform's `price_seen` beside it stays an extra). Not adopted: PF7c's D6, D7 (kept, masked), D18 is their 1.2.0 sibling.
* **Assertions moved for the re-copied catalogue and the header** (nothing else changed in the existing suites):
  * `test_market_contract_fixtures.py`: `APP_BLOBS` (123b88c59) and its comment; `PER_REGION` / `projected()` projects `availabilities`; `test_contract_folder_is_the_apps_copy` 13 → 15 products, the coffee tables Nord Living's; `test_seed_reads_the_apps_catalogue` (3, 13) → (3, 15), the tables' seed lines; `test_categories_like_the_stub` D1 10 / 9 → 12 / 11; `test_batch_prices_like_the_stub` 12 → 14 lines (the bedroom set at 8-11, Sund and Vik 12-13, the Oat sofa per region); `order_request` → MK4's basket, so `test_order_awaiting_payment_like_the_stub` sums both suppliers and `test_order_quoted_like_the_stub` quotes both at the items' `quoted`; `test_products_and_suppliers_like_the_stub` 13 → 15; `test_withdrawn_substitutes_like_the_stub` D13 for the three tables; `GEOMETRY_VARIANTS` 12 → 14 (Sund and Vik GLBs among the downloads); `test_feed_import_like_the_stub_report` availability against the feed's own (D19).
  * `test_pf7b_pf7c_meet.py`: the Halden's substitutes are three (Fjord, Sund, Vik); "Use this instead" takes the first.
  * `test_market.py`: the 1.2 echo at :113, :367, :370, :372 (requests still send 1.1 and 1.0); `test_categories_root_on_app_taxonomy` unchanged, green again (D16). `test_supplier_feeds.py`: the 1.2 echo at :65, :180, :183, :189.
  * PF7's own fixture answers (`server/tests/fixtures/market/`: `categories.json`'s hash, `order-awaiting-payment.json` and `order-quoted.json` with 1.2.0's keys) regenerated by `make_market_fixtures.py`; its `--check` (in `test_market.py`) green.
* **Deviations and why:**
  1. *An unpriced line of a serving supplier is 409, not 422* (Status row 4): §7 (1.2.0) names `availability` null "not sold in the region" in `unavailable`, and the stub answers it so; "X does not deliver to AE" was wrong for a supplier whose regions include AE. A supplier whose active regions lack the region keeps 422.
  2. *The app's taxonomy re-copied* (not in the brief): master was red on it on this PC since MD5, and 5.1's hash is what the stub's new categories.json carries (D16).
  3. *Header:* the server and the SDK operations (`openapi/v1.json`, `_operations.py`, `operations.mjs`: `market` and `feeds` groups) speak 1.2, because the drift test pairs the SDKs' `x-truebex-contract` with the route's echo; the web's order and basket clients (`market.ts`, `basket-api.ts`) and `market_try.py` send 1.2 (they place or read 5.7-5.10). The light clients (`mobile/clients.py` `MARKET` → `openapi/clients.json`, PF9's `src/lib/app.ts`, PF10's Android `api.dart`) and `supplier.ts` read only 5.1-5.5, unchanged in 1.2.0, so they keep 1.1, which a 1.2 server serves (same MAJOR): `openapi/clients.json` and the generated light clients need no regeneration (`--clients --check` current).
  4. *The orders page's web test is a Node render* of the page's own pieces (`orderLinkView`, `OrderList`) with real 5.8 / 5.9 answers, plus a check of the built chunks; the effects (5.9, scroll) run in the headless self-test above.
* **Contract §11 cells proposed for the platform column** (PF7 proposed 5.1-5.6 and 5.11-5.13): `POST /market/orders` "PF7: implemented by the platform (2026-10-09 PF7 `ap/t6`; 1.2.0 2026-10-20 PF7e `ap/t91`: `web_url`, per supplier `name` / `days_min` / `days_max` / `items`, §7's `data` shapes, `idempotency_mismatch`)"; `GET /market/orders` "PF7: implemented (`?state=`, `?project_uid=`, newest first, 50 a page with `next_cursor`)"; `GET /market/orders/{order_id}` "PF7: implemented (`items[].quoted` from the supplier's inbox quote, PF8)"; `POST /market/orders/{order_id}/cancel` "PF7: implemented (200 the whole order, `cancelled`; 409 `not_cancellable`; a paid order refunded)".
* **Carry-over → which feature:**
  * MK4's carry-over "PF7's live 5.7-5.10": **done on the platform's side** (this task). Going live is the owner's (api.truebex.com up), then MK4's human test steps 1-5 on the release build; accepting a quote happens on the platform (`/dashboard/orders/`, "Accept quote").
  * The owner / app side: the PATCH lines of D1, D13, D16, D18, D19, D20 and the §11 cells above.
  * PF8: the supplier inbox's JSON is unchanged (its lines, `quoted_unit`); nothing needed for 1.2.0.
  * The next re-copy: run the script, update `APP_BLOBS` and `APP_TREE` / `APP_COMMIT` (`test_pf7e_marketplace_1_2.py`), then the counts the tests name; re-copy the taxonomy too when 5.1's hash moves.
* **Merge note:** shares `server/app/market/`, `server/tests/contracts/marketplace/`, the market tests, `src/app/dashboard/orders/`, `src/components/market/`, `openapi/v1.json` and the SDK operations. PF4b (project-log 1.2.0) may regenerate the same generated files: re-run `server\scripts\export_openapi.py --v1` and `sdks\generate.py` after resolving `export_openapi.py`'s `CONTRACTS` instead of hand-merging; README.md and the tracker gain one end-of-file entry each.
* **Verify gate** (`scripts/autopilot-verify.ps1`, on the docs commit e0b7de0): green in 617 s; lint, build, pytest 883 passed + 18 skipped (the Postgres-only tests) of 901 collected in 554 s.
