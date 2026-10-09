# PF7 — Marketplace backend (launch priority 1)

**Needs merged:** PF1. **Unblocks:** PF8 (its Needs); the real endpoints behind the app's MK1, MK2, MK3, MK4 and PR2's bought themes. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\marketplace-api.md` (v1.0.0, 2026-10-09; the app side is authoritative).

## Status

**Built 2026-10-09** (Autopilot T6, `ap/t6-pf7-marketplace-backend`): contract 5.1–5.10 on `marketplace-api/1.1`, suppliers, products, regional prices and availability, the feed importer engine, search and picture search, orders and quotes with a Stripe Connect checkout (off until GD5), commissions and statements, reviews, the admin tools, and the checkout, orders and admin pages; see As-built. Before this feature (2026-10-09): no marketplace existed (`00-contract.md` P.1; the contract's §11 lists 5.1–5.10 as "PF7: not yet" and the feeds 5.11–5.13 as PF8's). What this builds on, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Money in minor units | `server/app/models.py:141-142` | the contract keeps this rule for every price (§6.3) |
| API keys for supplier systems | `server/app/deps.py:55-67` (key auth), `server/app/security.py:18` | PF8's feed endpoints authenticate this way (contract §4) |
| Provider failure answer | `server/app/routers/billing.py:124-129` (502 with a plain message) | payment calls follow it |
| Stripe adapter | `server/app/billing/providers.py:43` (Checkout), `:101` (signed webhooks) | the order checkout reuses its client and webhook verification |
| From PF1 (Needs) | device tokens, `require_admin`, `contract_http`, `storage`, `tasks`, `ratelimit`; PF2 (when merged) `create_invoice`, `charge_usage` | |

What the owner meant: app-side `00-understanding.md` §9.

## Goal

"A supplier uploads a spreadsheet with a UK and a UAE price list; a designer in Dubai places the sofa and the project's cost shows the UAE price; switching the project region to the UK re-prices everything" (`00-understanding.md` §9). This feature is the catalogue behind that: suppliers, products with variants and placeable geometry filed on the app's own taxonomy, regional prices with tax and delivery, availability, search by text and by picture, orders and requests for quote with a checkout on the platform, commissions, listing fees and reviews, and the admin tools that approve suppliers and products.

## Read first

* **`contracts/marketplace-api.md` v1.0.0** — the law: §4 credentials, §5 the thirteen endpoints, §6.1 the product, §6.2 categories rooted on the app's taxonomy, §6.3 price, availability and the product reference, §6.4 the supplier feed, §7 errors, §8 retry and `Idempotency-Key`, §9 fixtures (copied into `server/tests/contracts/marketplace/`), §10 platform tests, §11 *implemented by*.
* The app's taxonomy `CAD/taxonomy/categories.json` (app repo; copied into `server/app/market/taxonomy/` with its SHA-256, contract §3 and §6.2).
* `guides/GD1-*.md` (the first ten suppliers, the spreadsheet template), `guides/GD5-*.md` (marketplace terms, who sells to whom, VAT on marketplace sales) and `guides/GD7-*.md` (commission and listing fees) are not written yet: placeholders.
* PF2 (the billing interface, `create_invoice` for commission statements and listing fees); PF8 (the portal and the feed endpoints that drive this importer).

## Scope

**In:**
1. The marketplace API of contract §5.1–5.10: categories, regions, search, a product, batch prices with substitutes, a supplier's profile, orders and requests for quote, their list, one order, cancel.
2. Suppliers: a business record (legal name, country, company number, VAT id, website, regions served), members with roles (`owner`, `catalogue`, `orders`, `viewer`; the contract's "catalogue role"), verification states, commission rate and listing plan.
3. Products with variants and BIM geometry: kinds `object`, `material`, `finish`, `theme` (§6.1); variants with options, `dims_mm`, materials and a geometry file (`tbxa`, or a mesh format the app imports) stored by SHA-256; images with a thumbnail.
4. Categories mapped to the app's taxonomy: every path rooted on `CAD/taxonomy/categories.json`, `app_path` the deepest prefix the app knows, `taxonomy_sha256` reported (§6.2).
5. Regional price lists: per supplier and region the currency, tax rule and default delivery; per variant and region the price in minor units, `includes_tax`, `tax_rate_bp`, delivery fee and days (§6.3).
6. Availability per variant and region from feeds or by hand: `in_stock`, `low_stock`, `made_to_order` (with lead time), `out_of_stock`, `discontinued`.
7. The feed importer engine (§6.4 rows → products, variants, prices, availability, with a row-level report) that PF8's endpoints and portal call.
8. Search: text, category subtree, region, price range in minor units, availability, supplier, sort, facets (§5.3); and the AI asset search for images: products found by a picture or by a description through an open image-text embedding model.
9. Orders and leads: an order priced again on the server (409 `price_changed`), split per supplier, paid on a platform checkout page; a request for quote sent to the suppliers as a lead, quoted, accepted into an order or expired after 30 days (§5.7–5.10 states).
10. Commissions accrued on paid orders and invoiced to suppliers monthly; listing fees as supplier subscriptions (plans `from GD7`) through PF2's interface.
11. Reviews: buyers with a delivered order rate a product (1–5, text), moderated before publication, with an average and count.
12. Admin tools: approve or reject suppliers (verification) and products (review queue), hide reviews, see orders, commissions and feed runs.
13. Tests: the contract's §10 platform tests for 5.1–5.10, a pytest per endpoint (happy path, auth failure, validation failure).

**Out (and where it goes):**
* The feed endpoints 5.11–5.13, the spreadsheet template, the supplier web app and its e-mails → PF8.
* Placement, price snapshots in the document, the live cost model, the basket UI → MK1–MK4 (app); buying a theme in the app → PR2 with MK1.
* Supplier contracts, marketplace terms and the VAT treatment of marketplace sales → GD5; commission and listing-fee numbers → GD7; signing the first suppliers → GD1.
* Reviews and image search in the app's browser → a MINOR addition to the contract (proposed below) for MK1 to adopt later.

## Design

### API

Shapes are the contract's; routers `server/app/routers/market.py` (`/market`) and admin routes; service `server/app/market/`.

| # | Endpoint | Platform behaviour |
|---|---|---|
| 5.1 | `GET /market/categories` | from `market_categories`; `ETag`, `Cache-Control: max-age=86400`; product counts of approved, visible products |
| 5.2 | `GET /market/regions` | from `market_regions` (seeded GB: GBP, VAT 2000 bp, prices include tax; AE: AED, VAT 500 bp) |
| 5.3 | `GET /market/search` | approved and visible products; text through the `SearchIndex` interface (SQLite FTS5 now, Postgres full-text after PF14); price and availability of the asked region; facets; opaque cursor; 429 `rate_limited` per address for anonymous reads |
| 5.4 | `GET /market/products/{id}` | the product with every variant's region price, delivery and availability; geometry URL signed 1 h; 410 `product_withdrawn` with `data.substitutes` |
| 5.5 | `POST /market/prices` | ≤ 500 lines in one query per region; `substitutes` (≤ 3 approved, same category, available in the region, nearest price) only for unavailable or discontinued lines; `stale_after` = +24 h |
| 5.6 | `GET /market/suppliers/{id}` | profile of a verified supplier |
| 5.7 | `POST /market/orders` | device or session; `Idempotency-Key`; every line priced again (409 `price_changed` with `data.lines`), availability (409 `unavailable`), region served (422 `region_not_served`); `order` → per-supplier groups, totals, `checkout_url` = `${SITE_URL}/market/checkout/?order=…`, state `awaiting_payment`; `quote` → one lead per supplier, state `submitted` |
| 5.8–5.10 | list, one, cancel | owner of the order only (403 `forbidden`); cancel before any supplier accepts (409 `not_cancellable`) |
| — | `POST /market/checkout/{order_id}` | website session: creates the Stripe Checkout Session for the order (separate charges and transfers, `transfer_group` = order id) and returns its URL |
| — | `POST /market/search/image` | multipart image ≤ 5 MB (+ optional `region`): the nearest products by image embedding; platform-internal until the contract adds it |
| — | `GET`, `POST /market/products/{id}/reviews` | public list of published reviews; a buyer with a delivered order posts one (session) |
| — | `/admin/market/*` | suppliers (verify, suspend, commission rate), product review queue (approve, reject with reason), reviews (hide), orders, commissions, feed runs |

**Decision: order payments go through Stripe Connect** (Express accounts for suppliers, one payment per order with transfers to each supplier after acceptance, minus the commission). Paddle cannot carry them (its policy excludes physical goods, PF2). A supplier not yet onboarded to Connect is quote-only; until the contract carries that flag, 5.7 answers 409 `unavailable` with `data.reason: "quote_only"` for its lines. `MARKET_PAYMENTS_ENABLED` stays off until GD5 signs off the marketplace terms; with it off every supplier is quote-only. Rejected: invoices between buyer and supplier outside the platform (the contract's order states need a platform checkout); one payment per supplier (a basket with three suppliers would need three card entries).

**Decision: the importer is shared and idempotent.** A feed row upserts by (`supplier`, `sku`, `variant_id`, `region`); `replace` mode hides the supplier's products the file omits; every run writes a report with row errors (§5.13 shape). Rejected: one importer per format (the CSV, the JSON and PF8's spreadsheet upload all become §6.4 rows first).

### Data

| Table | Fields | Notes |
|---|---|---|
| `suppliers` | `supplier_id` (32 hex), `name`, `legal_name`, `country`, `company_number`, `vat_id`, `website`, `logo_key`, `status` (`applied`, `verified`, `suspended`), `verified_at`, `commission_bp`, `listing_plan`, `connect_account_id`, `created_at` | |
| `supplier_members` | `supplier_id`, `user_id`, `role` (`owner`, `catalogue`, `orders`, `viewer`) | API keys of `owner` and `catalogue` members feed the catalogue |
| `market_categories` | `path` PK, `label`, `app_path`, `parent_path`, `sort`, `active` | rooted on the copied taxonomy |
| `market_regions` | `region` PK (ISO 3166-1, optional subdivision), `name`, `currency`, `exponent`, `tax_name`, `tax_rate_bp`, `prices_include_tax` | |
| `supplier_regions` | `supplier_id`, `region`, `currency`, `default_delivery_fee`, `delivery_days_min`, `delivery_days_max`, `active` | the regional price list's header |
| `products` | `product_id`, `supplier_id`, `sku` (unique per supplier), `name`, `kind`, `category`, `description`, `images` JSON, `includes` JSON, `status` (`draft`, `pending_review`, `approved`, `rejected`, `hidden`, `withdrawn`), `rating_avg`, `rating_count`, timestamps | |
| `product_variants` | `product_id`, `variant_id`, `options` JSON, `dims_mm` (X width, Y height, Z depth), `materials` JSON, `geometry` JSON (`asset {id, name, rev, kind}`, `format`, `sha256`, `bytes`, `storage_key`), `status` (`active`, `discontinued`, `hidden`) | |
| `variant_prices` | `product_id`, `variant_id`, `region`, `amount`, `currency`, `exponent`, `includes_tax`, `tax_rate_bp`, `delivery_fee`, `delivery_days_min`, `delivery_days_max`, `source` (`feed`, `manual`), `feed_id`, `updated_at` | integers only (§6.3) |
| `variant_availability` | `product_id`, `variant_id`, `region`, `state`, `stock`, `lead_time_days`, `source`, `updated_at` | |
| `product_embeddings` | `product_id`, `model`, `vector` (float32 BLOB) | brute-force cosine below 50 000 products; a vector index after PF14 |
| `market_orders`, `market_order_suppliers`, `market_order_lines` | order (`kind`, `state`, `region`, `currency`, project, contact, delivery, totals, `checkout_session`), per supplier (`state`, subtotal, delivery, tax, `commission`, `transfer_id`), lines (`sku`, `variant_id`, `qty`, the unit price snapshot) | states as §5.7–5.10 |
| `commissions` | `order_id`, `supplier_id`, `rate_bp`, `base`, `amount`, `currency`, `state` (`accrued`, `invoiced`, `paid`), `invoice_ref` | |
| `product_reviews` | `review_id`, `product_id`, `user_id`, `order_id`, `rating`, `text` ≤ 2000, `status` (`pending`, `published`, `hidden`), `created_at` | |
| `feed_runs` | `feed_id`, `supplier_id`, `format`, `mode`, `state`, counts, `errors` JSON, `report_key`, timestamps | written by the importer; PF8 owns the endpoints |

Storage: `market/geometry/{sha256}.{format}`, `market/images/{sha256}.jpg` (thumbnails 512 px made at import), `market/feeds/{feed_id}/source` and `report.json`.

### UI

| Page | What it shows |
|---|---|
| `src/app/market/checkout/page.tsx` (noindex; `?order=` inside `Suspense`) | the order per supplier with lines, delivery, tax and totals in the region's currency; delivery details; Pay → the Stripe Checkout URL; back with `?paid=1` → "Order placed" and each supplier's state |
| `src/app/dashboard/orders/page.tsx` (noindex) | the buyer's orders and requests with each supplier's state |
| `src/app/dashboard/admin/market/` (noindex, admin) | Suppliers (applications, verify, suspend, commission), Products (the review queue with images, geometry thumbnail, category check), Reviews (hide), Orders, Commissions (monthly statements), Feeds (runs and reports) |

### Jobs / workers

| Job | Every | Does |
|---|---|---|
| `market.embeddings` | 60 s | embeds newly approved product images (an open image-text embedding model in the CLIP family, permissive licence, run on CPU through ONNX Runtime; weights fetched by `server/scripts/fetch_models.py`, never in git) |
| `market.quotes.expire` | 24 h | `submitted` or `quoted` requests older than 30 days → `expired` |
| `market.orders.unpaid` | 1 h | `awaiting_payment` older than 48 h → `cancelled` |
| `market.transfers` | 300 s | after a supplier accepts a paid order: the transfer of its subtotal minus commission; a rejection refunds that supplier's part |
| `market.commissions.invoice` | monthly, 1st | one statement per supplier; an invoice through PF2's `create_invoice` (Stripe), or `pending` rows when PF2 is absent |
| `market.availability.stale` | 24 h | marks availability not updated for 7 days as unknown in search ranking |

### Security and privacy

* Catalogue reads are public and rate-limited; writes come only through PF8 (members of a verified supplier) or admins.
* Prices are never taken from the client: 5.7 prices every line again; money stays in integer minor units with ISO 4217 codes.
* Buyer contact details go only to the suppliers of that order or request; suppliers never see other buyers or the project file (only its name when the buyer adds it).
* Stripe Connect: card data stays with Stripe; webhooks verified as `providers.py:101` does; transfers only after a supplier accepts.
* Uploaded geometry and images are stored as data and served with `Content-Disposition: attachment` for geometry; images are re-encoded to JPEG at import (strips metadata and active content).

## Deliverables

- [x] `server/app/market/` (`catalogue.py`, `search.py` with `SearchIndex` and its FTS5 adapter, `prices.py`, `orders.py`, `checkout.py`, `importer.py`, `embeddings.py` with a deterministic stub for tests, `reviews.py`, `commissions.py`, `listing.py`), `server/app/routers/market.py`, admin routes
- [x] `server/app/market/taxonomy/categories.json` (copied from the app repo, never edited) and `regions.json` seed; `listing_plans.json` placeholders `from GD7`
- [x] models, settings (`MARKET_PAYMENTS_ENABLED`, `STRIPE_CONNECT_*`, `EMBEDDING_MODEL`), `.env.example`; `numpy`, `onnxruntime`, `Pillow` pinned; `server/scripts/fetch_models.py`, `server/scripts/seed_market.py`
- [x] `src/app/market/checkout/`, `src/app/dashboard/orders/`, `src/app/dashboard/admin/market/`, `src/lib/market.ts`
- [x] `server/tests/contracts/marketplace/` copied from the app repo's fixtures (copied, never edited)
- [x] contract §11 rows and the MINOR proposals (supplier `orderable`, `rating` on 5.3 and 5.4, `POST /market/search/image`) recorded in As-built

## Tests

The first seven names are the contract's §10 platform tests for this feature's endpoints (the feed tests are PF8's).

| Name | Kind | Asserts |
|---|---|---|
| `test_categories_root_on_app_taxonomy` | pytest | every category's `app_path` exists in the copied `categories.json`; `taxonomy_sha256` matches the file |
| `test_search_filters_and_region_prices` | pytest | filters, facets, sort; prices in the region's currency |
| `test_price_minor_units_and_tax` | pytest | integer minor units; `includes_tax` and `tax_rate_bp` per region |
| `test_batch_prices_and_substitutes` | pytest | 500 items in one call; substitutes only for unavailable lines; 501 → 413 |
| `test_order_split_checkout_and_price_changed` | pytest | one order, two suppliers; `checkout_url`; 409 on a changed price |
| `test_quote_lifecycle` | pytest | `submitted` → `quoted` → `accepted` → an order; 30 days → `expired` |
| `test_contract_header_and_error_envelope` | pytest | header echoed; MAJOR 2 → 400 `contract_version`; envelope with `code` and `request_id` |
| `test_market_reads_rate_limited` | pytest | anonymous reads past the limit → 429 with `retry_after_s` |
| `test_market_search_validation` | pytest | 422 unknown category or region; `limit` 101 → 422 |
| `test_market_product_withdrawn` | pytest | 410 `product_withdrawn` with substitutes |
| `test_market_orders_auth_and_ownership` | pytest | 401 without credential; another account's order → 403; 409 `not_cancellable` after acceptance |
| `test_market_order_idempotency` | pytest | the same key replays the first order |
| `test_market_quote_only_supplier` | pytest | an unonboarded supplier's line in an `order` → 409 `unavailable`, `data.reason` `quote_only`; a `quote` passes |
| `test_market_checkout_webhook_marks_paid` | pytest | a signed `checkout.session.completed` → `paid`; an unsigned one → 400 |
| `test_market_transfers_after_acceptance` | pytest | transfer = subtotal − commission; a rejection refunds that part (Stripe mocked) |
| `test_market_importer_upsert_and_replace` | pytest | rows upsert by key; `replace` hides omitted products; the report counts match |
| `test_market_image_search_stub` | pytest | with the stub embedder the same image returns its own product first; 413 over 5 MB |
| `test_market_reviews_verified_and_moderated` | pytest | only a delivered order may review; `pending` until approved; average and count update |
| `test_market_admin_approvals` | pytest | 403 for non-admins; approving a product makes it searchable; rejecting records the reason |
| `test_site_pf7_checkout_noindex` | build check | `out/market/checkout/index.html` carries `noindex` |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. Local API; in `server/` run `.venv\Scripts\python.exe scripts\seed_market.py --fixture tests\contracts\marketplace` → the fixture's regions (GB, AE), its five products (sofa, coffee table, paint, wallpaper, theme) and their supplier, verified.
2. `curl "http://127.0.0.1:8000/market/search?q=sofa&category=furniture/seating&region=AE" -H "X-Truebex-Contract: marketplace-api/1.0"` → the Oslo sofa with the AED price `products.json` states (integer `amount`, exponent 2, `includes_tax` true, `tax_rate_bp` 500).
3. The same with `region=GB` → the GBP price with VAT 2000 bp; `category=furniture` alone also finds it (subtree).
4. `POST /market/prices` with the sofa's two variants for AE → both priced; the discontinued coffee table returns substitutes.
5. In an MK1 build: open the asset browser's catalogue, search "sofa", switch the region to AE → AED prices.
6. Admin → Market → Products: a pending product from the fixture → Approve → it appears in search.
7. Send a request for quote for the sofa (an MK4 build, or `curl -X POST /market/orders` with `"kind":"quote"` and a device token) → `submitted`; as the supplier, quote it (PF8's inbox, or the admin page) → the buyer sees `quoted`.
8. With `MARKET_PAYMENTS_ENABLED=true` and Stripe test keys: send an `order` → open `checkout_url` → pay with a Stripe test card → the order reads `paid`, each supplier `pending`.

## Risks / traps

* The taxonomy file is the app's: a new category path in the app is a MINOR contract change (§3); the copy is replaced, never edited, and `test_categories_root_on_app_taxonomy` fails until it matches.
* SQLite FTS5 must be compiled into the Python build (it is in the CPython 3.12 Windows installer's SQLite); the `SearchIndex` interface keeps the Postgres swap one adapter.
* Embedding model weights are hundreds of MB: never in git, never downloaded by tests (the stub embedder), fetched once per host.
* Marketplace payments make Truebex a payment facilitator for third-party goods: the flag stays off until GD5's terms, supplier contracts and VAT treatment are signed off.
* Currencies differ in exponent; never format with two decimals by default (use each region's `exponent`).
* Hot spots: `routers/admin.py` (PF1, PF6, PF14 also add admin routes), `models.py`, `DashboardShell.tsx`.

## As-built

* **Date, branch, commits:** 2026-10-09, `ap/t6-pf7-marketplace-backend` from `ap/t1-pf1-licence-api-releases-and-dow` (`fa824cf`). `1e78cea` restores PF1's storage module (deviation 3), then the backend, fixtures and API tests, the importer / admin / review / picture-search tests, the site pages, the pinned dependencies and settings, and the docs; the WIP commits are kept as they are (the owner may squash at merge).
* **Counts:** pytest in the verify gate (on a built `out/`) 68 → 95 passed (27 new: `test_market.py` 17, `test_market_feed.py` 5, `test_market_admin.py` 4, `test_site_pf7.py` 1; every name in the Tests table exists verbatim). Pages in `out/`: 16 → 19 `index.html` (`/market/checkout/`, `/dashboard/orders/`, `/dashboard/admin/market/`, all noindex, none in the sitemap). Self-tests beyond pytest: an end-to-end run against a real uvicorn process (seed → search AE / GB → batch prices with substitutes → admin approves the pending chair → it is searchable → request for quote → admin quotes → `quoted` → an order → `awaiting_payment` with `checkout_url`; Pay without Stripe keys → 503), the real CLIP ViT-B/32 model fetched by `fetch_models.py` (89 MB vision, 65 MB text; the Fjord table's photo finds the Fjord table first, cosine 0.985; about 0.1 s a picture on the CPU), and headless-Edge screenshots of the checkout page (signed in and signed out), the orders page and the admin page against that API.
* **Deviations from Design and why:**
  1. *The contract moved to 1.1.0* (GD1 amended it the same day): routes speak `marketplace-api/1.1` (a 1.0 client is served; only another MAJOR gets 400), 5.4 serves `brand`, `classification`, a variant's `gtin` and `description: ""`, and the importer implements the 1.1.0 header and row rules with all 20 row error codes (`test_market_importer_row_errors`) and GD1's template (`test_market_feed_gd1_template` makes the asserts of the contract's `test_feed_gd1_template`, which PF8 owns).
  2. *Fixtures.* `Docs/roadmap/fixtures/contracts/marketplace/` did not exist in the app repo (MK1 makes it), so PF7 made the first version, as PF1 did for the licence fixtures: `server/scripts/make_market_fixtures.py` writes `products.json` (schema `truebex-market-fixture/1`: the supplier and its products, each variant's §6.3 price, delivery and availability per region under `regions`), `media-map.json` (feed URLs → fixture files), `thumbs/*.png`, `geometry/sofa-oslo.tbxa` (a JSON stand-in with an S1 id until MK1 writes the real O1 asset), `geometry/chair-bergen.glb`, `feed-two-regions.csv` / `.json` (6 rows: the sofa's two variants and a Bergen lounge chair, GB and AE), a byte copy of GD1's template, and this server's own answers as `{request, http_status, body}` (`categories`, `regions`, `prices-gb`, `prices-ae`, `order-awaiting-payment`, `order-quoted`, `feed-report`), made in-process with a fixed clock and fixed ids. `test_market_fixtures_up_to_date` runs `--check` (image URLs masked: they carry the stored JPEG's SHA-256). The catalogue has **six** products, not five: the discontinued Aker coffee table needs a same-category substitute (the Fjord coffee table) for "the coffee table returns substitutes". A `.gitattributes` keeps the folder byte-exact. **Owner at merge:** copy the folder to the app repo's `Docs/roadmap/fixtures/contracts/marketplace/`.
  3. *A base fix:* `server/.gitignore`'s `storage/` also ignored `server/app/storage/`, so PF1's storage interface was never committed and every `from ..storage import` failed on a fresh checkout. The two files are copied verbatim from the PF1 worktree and the pattern is anchored (`/storage/`); PF1 and PF14 hold the same untracked files, so the merge is an add/add of identical content.
  4. *Own files for the hot spots:* the tables are in `market/models.py` (not the shared `models.py`), the admin routes in `routers/market_admin.py` (prefix `/admin/market`, not `routers/admin.py`), and the FTS5 table is created and dropped with the metadata by DDL events; `database.py`, `main.py`, `config.py` and `DashboardShell.tsx` get one block each. `UserOut.is_admin`, `user_out` and `auth.ts`'s `is_admin` are textually PF13's (`master`), so those merge clean. The taxonomy copy is stored byte-exact (`-text`; the app's file has CRLF endings) so its SHA-256 matches on every checkout.
  5. *Routes beyond the design table:* `POST /market/orders/{id}/accept` (the buyer accepts a quote: an order is made from the quoted suppliers' lines), `POST /market/checkout/{id}/refresh` (back from Stripe: the server retrieves the session itself, for a webhook that never arrived), `POST /market/webhooks/stripe` (its own endpoint; `STRIPE_CONNECT_WEBHOOK_SECRET` takes one or more `whsec_` secrets; events `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `account.updated`), `GET /market/media/{images|thumbs}/{sha}.jpg` (public, immutable product pictures), and admin: create a supplier, members, a Connect onboarding link, categories, a feed import for a supplier, statements now, a search-index rebuild, and acting for a supplier (quote, decline, accept, reject, ship, deliver) until PF8's inbox exists. `server/scripts/market_try.py` sends a request for quote or an order for the fixture's sofa as a signed-in buyer (the app's basket until MK4).
  6. *Quotes while payments are off (GD1 Phase A):* accepting a quote makes an order in state `accepted` with `payment: "offline"` (each supplier invoices the buyer; no commission, as GD1 §4.2 says of leads). With payments on and every supplier onboarded it is `awaiting_payment` with a `checkout_url`.
  7. *Order state after payment* follows its suppliers: `paid` → `accepted` (every live part accepted) → `shipped` → `delivered`; `rejected` when every part was declined. A paid order cancelled before any acceptance is refunded in full.
  8. *Money:* the transfer is the supplier's part (goods + delivery + any added tax) minus the commission; the commission is the rate × the goods value excluding tax and delivery, half-even (GD1 §4.2's illustration is a test: 129 900 → 108 250 → 10 825). It is accrued when the transfer is made (a declined part never accrues: it is refunded instead) and listed on a monthly statement made by a daily, idempotent job.
  9. *Error codes beyond §7* (all in the shared envelope): `idempotency_mismatch` 409 (the code MK4 already expects), `not_a_buyer` 403 (reviews), `not_acceptable` 409 (accepting a quote that is not `quoted`), `provider_error` 502, `invalid_signature` 400 (webhook), `conflict` 409 (an admin action in the wrong state), `feed_invalid` 422 (admin import).
  10. *Feeds:* row numbers are as a spreadsheet shows them (the header is row 1; JSON: the price entry's 1-based position); a row with `status=hidden` removes that region's price; an invalid `tax_rate_percent` is `bad_price`; an unknown classification scheme is a warning, not a rejection; in `replace` mode a rejected row still counts as listed (a typo never hides a product); new products wait in `pending_review`, approved products stay approved when prices or stock change; an asset keeps its first id and its `rev` grows when the file's SHA-256 changes.
  11. *Search and prices:* `min`, `max`, `available` and the price sorts need a `region` (422 otherwise: a currency is needed to compare); an optional `kind` filter; each result names the shown (cheapest matching) `variant_id`. 5.5 marks a line `status: not_found | withdrawn | not_sold_in_region` and gives substitutes for every line that cannot be ordered there. 5.4 is 404 for a product never published and 410 for one withdrawn, hidden by a feed or whose supplier is suspended.
  12. *Picture search:* CLIP ViT-B/32 (MIT) as quantised ONNX (Xenova's export) on ONNX Runtime; `tokenizers` (Apache-2.0) is pinned too, so a description is embedded by the text model; `EMBEDDING_MODEL=stub` for tests; with the stub a description goes to the text index.
  13. *Payments status:* the admin page tells "off", "switched on but Stripe not configured" and "on" apart (`payments_enabled`, `stripe_ready`).
* **GD1 / GD5 / GD7 inputs adopted:** GD1 §4.2 (commission on goods excluding tax and delivery, half-even, deducted from the transfer; a monthly statement), §4.6 (quotes valid 30 days; availability not updated for 7 days demoted in search), the two-phase go-live (quote-only until `MARKET_PAYMENTS_ENABLED`), its catalogue template and the 1.1.0 feed rules. GD5's marketplace terms and VAT treatment: not yet, so the flag stays off. GD7 §4 is still the brief: `listing_plans.json` holds two placeholder plans (`founding`, `standard`) at 1000 bp (GD1's illustration rate) and no listing fee; `L`, `c`, `N`, `M` are the owner's to set.
* **Contract §11 rows for the owner to set to "PF7: done" in `contracts/marketplace-api.md`:** `GET /market/categories`, `GET /market/regions`, `GET /market/search`, `GET /market/products/{product_id}`, `POST /market/prices`, `GET /market/suppliers/{supplier_id}`, `POST /market/orders`, `GET /market/orders`, `GET /market/orders/{order_id}`, `POST /market/orders/{order_id}/cancel`. **MINOR proposals** (served already as extra keys or platform routes; readers ignore unknown keys): (a) `orderable` on 5.6, 5.3 and 5.4 (false = quote-only, the state `data.reason: "quote_only"` reports today); (b) `rating {avg, count}` on 5.3 and 5.4 and `GET /market/products/{id}/reviews`; (c) `POST /market/search/image` (multipart `image` ≤ 5 MB or `text`, optional `region` and `limit`; 5.3 results with a `score`); (d) `POST /market/orders/{id}/accept`; (e) `idempotency_mismatch`; (f) 5.5's per-line `status`; (g) 5.3's `kind` filter and per-result `variant_id`; (h) the fixture shapes of deviation 2, as a dated *Changes* line.
* **Carry-over → which feature:** the feed endpoints 5.11–5.13 on `importer.validate` / `queue` / `execute` / `dry_run` / `report_json`, the daily pull, the supplier inbox on `orders.supplier_quote` / `_accept` / `_reject` / `_decline` / `_ship` / `_deliver`, Connect onboarding through `checkout.onboarding_link`, supplier authentication through `catalogue.catalogue_supplier` (403 `not_supplier`), the e-mails and the spreadsheet template → PF8. `create_invoice` for statements (the hook in `commissions._pf2_invoice` runs once PF2's `billing.providers.get_provider` exists) and listing-fee subscriptions → PF2. A Postgres full-text `SearchIndex` adapter, a vector index, `s3` media URLs (the media route already redirects for a non-local store) and the worker → PF14. The terms that let `MARKET_PAYMENTS_ENABLED` go on → GD5; the fee numbers → GD7. The app's catalogue client on these fixtures (and the real `sofa-oslo.tbxa`) → MK1; MK4 adopts `accept` and `idempotency_mismatch`.
* **Owner at merge or before deploy:** `pip install -r requirements.txt` in the API's venv (new: Pillow, numpy, onnxruntime, tokenizers); in Stripe, add the endpoint `https://api.truebex.com/market/webhooks/stripe` (platform events and, for Connect, `account.updated`) and put its secret(s) in `STRIPE_CONNECT_WEBHOOK_SECRET`; optionally run `scripts\fetch_models.py` and set `EMBEDDING_MODEL=clip-vit-b32`; copy the fixtures to the app repo and update the contract's §11.
