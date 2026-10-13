# PF7c — Marketplace fixtures re-copied from MK1, and the platform's answers checked against them (launch priority 2)

**Needs merged:** PF7, PF7a, PF8 (all on `master` 9dac34b); MK1 on the app side (landed on the app repo's `main` on 2026-10-13 at 03:42 UTC, app commit 90799860, Autopilot T158). **Unblocks:** MK2 and MK4 against the real API: every reading the two sides disagree on is listed in the As-built with the PATCH line the app side should consider; PF7's As-built deviation 2 is closed. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\marketplace-api.md` 1.1.0 (§9 stub fixtures, §3 *Changes* 2026-10-10 and 2026-10-11; the app side is authoritative, C.9). No platform route or version changes; one 5.4 reading fixed to the contract's text (D15).

## Status

**Built (2026-10-13, branch `ap/t66-pf7c-marketplace-fixtures-re-cop`, Autopilot T66); see As-built.** Checked on `master` 9dac34b before the work began:

| # | Where (master 9dac34b) | Before |
|---|---|---|
| 1 | `server/tests/contracts/marketplace/` | PF7's own set (`truebex-market-fixture/1`: one supplier, six products, answers as `{request, http_status, body}`; PF7 deviation 2: "the app repo had no fixtures yet"). Every shared file differed from MK1's, line endings aside; MK1 also has `geometry/` (four `.tbxa` from the app's serializer, three `.glb`) and other `thumbs/` |
| 2 | `server/app/market/seed.py:32` `load_fixture` | reads only PF7's shape (`supplier`, each variant's `regions`) |
| 3 | `server/scripts/seed_market.py:154` | `--fixture` defaults to `tests/contracts/marketplace`; one supplier |
| 4 | `server/app/market/catalogue.py:308` (5.4 `includes`) | stored values served as they are: `{supplier_id, sku, variant_id}` objects for PF7's theme and for a JSON feed's theme; a feed's product-id strings dropped (`importer.py:647-655`) |
| 5 | readers of the folder | `tests/market_helpers.py:23` (`FIXTURES`, used by `test_market.py`, `test_market_admin.py`, `test_market_feed.py`, `test_market_production.py`, `test_supplier_portal.py`, `supplier_helpers.py` → `test_supplier_feeds.py`), `scripts/make_market_fixtures.py:43` (writes and `--check`s it), `scripts/market_try.py:24`; PF13a's tests read only built pages |

The app's set (README in the folder): `products.json` is the stub's own shape (`truebex-market-stub/1`): 3 suppliers and 9 products written once each, a variant's `prices` and `deliveries` keyed by region and one `availability`, `substitutes` on the product; file URLs are `https://market.truebex.com/files/<path>`; the stub projects them to §6.1's `price` / `delivery` for the asked region.

## Goal

Both sides test against the same files (contract §9): the platform holds MK1's fixtures byte for byte, can seed the app's catalogue for local trials and human tests, and a parity test asks the platform what the stub answers from those files. A reading the two sides disagree on fails a test now, not when MK2 or MK4 first talk to the real API.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4; PF7's doc (Design, As-built deviation 2), PF7a's and PF8's docs (their fixture-dependent tests).
* The app's `contracts/marketplace-api.md` in full and its fixture README (`Docs/roadmap/fixtures/contracts/marketplace/README.md`, copied as `server/tests/contracts/marketplace/README.md`); `Scripts/gen_market_fixtures.py` in the app repo (how the stub's files are made).
* `server/app/market/seed.py`, `catalogue.py`, `prices.py`, `orders.py`, `importer.py`; `server/app/supplier/geometry_check.py`, `server/app/supplier/catalogue.py` (`set_geometry`).

## Scope

**In:**

1. The app's set copied into `server/tests/contracts/marketplace/` from the app's committed blobs (never edited; byte-exact through the root `.gitattributes` `-text` rule). PF7's own catalogue moves to `server/tests/fixtures/market/` (`make_market_fixtures.py` writes and `--check`s it there); every older test keeps its rows and counts by reading it from there.
2. `seed_market.py --fixture` (and `seed.load_catalogue`) reads the app's stub shape as well as PF7's: three suppliers, each product once, per-region prices and deliveries, one availability, substitutes and includes checked against the file; the stub's file URLs are served from the folder.
3. `server/tests/test_market_contract_fixtures.py`: the platform seeded from the app's `products.json` against `categories.json` (5.1), `regions.json` (5.2), `prices-gb.json` / `prices-ae.json` (5.5), `order-awaiting-payment.json` (5.7) and `order-quoted.json` (5.9), and `feed-two-regions.csv` / `.json` through 5.11–5.13 against `feed-report.json`; 5.4, 5.6 and 5.4's 410 substitutes against `products.json`. Only volatile values are masked. Each real difference is either fixed (the contract's text agrees with the app) or asserted as today's behaviour with its number in the As-built and a PATCH line for the app side.
4. The app's geometry byte for byte: every file through the seed and 5.4's geometry link, and through PF8's portal upload, publication and 5.4's link.
5. This doc, the tracker row, PF7's deviation 2 marked re-copied, a README section.

**Out (and where it goes):**

* Changing a public shape beyond what the contract's text says: each such difference stays as the platform answers it and gets a PATCH line (As-built) for the owner to put to the app side.
* Editing the app repo (read-only here): the PATCH lines and the contract's §11 rows are the owner's to apply.
* The `https://truebex.com/market/basket?...` page the contract's 2026-10-11 PR2 line says PF7 owns: not built (no page exists); carry-over.
* Reading a `.tbxa`'s own S1 id as the asset id on upload (D14): a MINOR decision for both sides; carry-over.

## Design

**Folders.**

| Folder | Holds | Made by |
|---|---|---|
| `server/tests/contracts/marketplace/` | MK1's set, 28 files: `README.md`, `categories.json`, `regions.json`, `products.json`, `prices-gb.json`, `prices-ae.json`, `order-awaiting-payment.json`, `order-quoted.json`, `feed-two-regions.csv`, `feed-two-regions.json`, `feed-report.json`, `geometry/` (4 `.tbxa`, 3 `.glb`), `thumbs/` (10 PNG, 512 px) | copied from the app repo's blobs (`git cat-file blob`, app `main` 90799860), every blob id checked |
| `server/tests/fixtures/market/` | PF7's catalogue, unchanged but its README: `products.json` (`truebex-market-fixture/1`), `media-map.json`, PF7's answers, the GD1 template copy, its pictures and stand-in geometry | `scripts/make_market_fixtures.py` (default `--out`; `--check` in `test_market_fixtures_up_to_date`) |

**Seed (`server/app/market/seed.py`).** `load_catalogue(db, folder, *, payments_ready, owner)` reads either shape and returns every supplier; `load_fixture` keeps its signature (PF7's supplier, or the stub's first). For the stub shape:

* Suppliers: `supplier_id`, `name`, `country`, `website`, the logo (stored like a product picture), the regions; `verified` on the platform whatever the stub says (D12); `--payments-ready` marks each one onboarded to Stripe Connect; `--owner` makes the account each supplier's owner.
* Categories the products or the stub's `categories.json` name that the platform's tree lacks are added with the stub's labels, parents first (`furniture/tables/coffee` "Coffee tables", `lighting/wall/sconces` "Sconces"; D2). `market_categories.json` is not changed.
* Products: approved, `approved_at` / `created_at` = the file's earliest price time (2026-10-09T10:00:00Z); pictures fetched through the stub's rule and stored as PF7's are; `includes` kept as the stub's product ids.
* Variants: options, `dims_mm`, materials, GTIN; `discontinued` when the stub's availability says so; geometry stored by SHA-256 and refused when the bytes or size differ from `products.json`; the asset reference kept as the stub writes it (its S1 ids). Each region of `prices` gets a price row (currency checked against the region), the delivery of `deliveries`, and the variant's one availability, with the file's own times.
* `substitutes` and `includes` must name products of the file (else `ValueError`); the platform picks its own substitutes (same category, then app path, orderable in the region, nearest price), and the parity test compares them with the stub's.
* `seed.media_fetcher(folder)`: PF7's `media-map.json` when present, else `StubFetcher`: an https URL whose path holds `/files/` is that file in the folder, never outside it. `MARKET_MEDIA_FIXTURES=tests/contracts/marketplace` therefore serves the app's feed URLs in a local trial.

**`seed_market.py`.** `--fixture` defaults to PF7's catalogue (`tests/fixtures/market`), so PF7a's and PF8's documented trials print what they did. With the app's set it prints the three suppliers and nine products and does not import the app's feed (it is the Oslo sofa already loaded; the CSV has no `classification` column, so an upsert would clear the sofa's).

**Parity (`test_market_contract_fixtures.py`).** Masked: minted ids (`order_id`, `feed_id`), times the server stamps when it answers (5.5 `at` / `stale_after`, but both must be 24 h apart; a feed import's price and availability times) and URLs: the stub's `https://market.truebex.com/files/<path>` against the platform's `{API_URL}/market/media/…` pictures and `{API_URL}/market/geometry/{product_id}/{variant_id}?region=` link (PF8 deviation 5). Platform extras that readers ignore (§3: `qty` echoed by 5.5, `supplier_name`, `thumbnail_url`, `rating`, `orderable`, a variant's `images`) are popped and checked, not ignored. The 5.7 / 5.9 request is the app's own: the sofa `oat-linen`, qty 1, AE, with the stub's AE price as `price_seen`; the quote is answered in PF8's inbox with the stub's quoted amount (AED 1,249.00) and no delivery fee.

**5.4 `includes` (D15, fixed).** `catalogue.includes_json` answers a theme's `includes` as product ids: a stored id passes through; a `{supplier_id, sku, variant_id}` reference (PF7's catalogue, a JSON feed) becomes that product's id; one naming no product is left out. A JSON feed may now name included products by id too (`importer.py`). The contract's 2026-10-11 line says the app reads a theme "as its `includes` (5.4 each)", and 5.4 takes a product id.

**Security and privacy.** Test fixtures only; the seed refuses a file URL that resolves outside the fixture folder (`../`), and `StubFetcher` is only used for a fixture folder (the seed, the tests, `MARKET_MEDIA_FIXTURES` on a local trial).

## Deliverables

- [x] `server/tests/contracts/marketplace/` = MK1's 28 files; `server/tests/fixtures/market/` = PF7's catalogue (moved with `git mv`, README updated)
- [x] `server/app/market/seed.py` (`load_catalogue`, the stub shape, `StubFetcher`, `media_fetcher` for both)
- [x] `server/scripts/seed_market.py` (both shapes, three suppliers), `make_market_fixtures.py` (writes `tests/fixtures/market`), `market_try.py` (PF7's catalogue path), `make_digest_fixture.py` (comment)
- [x] `server/app/market/catalogue.py` (`includes_json`), `server/app/market/importer.py` (ids in a JSON feed's `includes`)
- [x] `server/tests/test_market_contract_fixtures.py` (16 tests), `market_helpers.py` (`FIXTURES`, `CONTRACT_FIXTURES`), `test_supplier_portal.py` (the app's real `.tbxa` in `test_supplier_geometry_checks`)
- [x] this doc, the PF7c tracker row, PF7's deviation 2 marked re-copied, `README.md` section "Marketplace fixtures from MK1 (PF7c)"

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_contract_folder_is_the_apps_copy` | pytest | the folder holds exactly MK1's 28 files, LF only; every geometry file's SHA-256 and size are `products.json`'s; `.tbxa` single-line JSON, `.glb` binary glTF; thumbnails PNG ≥ 512 px |
| `test_seed_reads_the_apps_catalogue` | pytest | `seed_market.main(["--fixture", …])` twice: 3 suppliers verified, 9 products approved; 5.3 lists all nine in GB; each found by its name in GB and AE with a price `products.json` gives it; `q=sofa&region=AE` → the sofa first at AED 1,299.00 |
| `test_categories_like_the_stub` | pytest | 5.1: `taxonomy_sha256`; every stub category with its `app_path`, label (D3) and count (D1, D2); the rest of the tree empty (D4) |
| `test_regions_like_the_stub` | pytest | 5.2 equals `regions.json` |
| `test_batch_prices_like_the_stub[GB]`, `[AE]` | pytest | 5.5 for the stub's request: every line's price, availability and substitute ids equal (D5); `stale_after` = `at` + 24 h |
| `test_order_awaiting_payment_like_the_stub` | pytest | 5.7 (payments on, supplier onboarded) and 5.9: kind, state, groups (supplier, state, lines, delivery), subtotal and total amounts (D7), `checkout_url` (D6) |
| `test_order_quoted_like_the_stub` | pytest | a quote answered in PF8's inbox: 5.9 `quoted`, no `checkout_url`, groups and total as `order-quoted.json` (D7) |
| `test_feed_import_like_the_stub_report[csv]`, `[json]` | pytest | the app's feed through 5.11 → 5.13 as `feed-report.json` but `created` (D8); approved, 5.4 serves the stub's sofa (prices, delivery, availability, geometry; D9) |
| `test_products_and_suppliers_like_the_stub` | pytest | 5.4 for nine products in GB and AE equals the stub's projection (D10); 5.6 for three suppliers (D11, D12) |
| `test_withdrawn_substitutes_like_the_stub` | pytest | 5.4's 410 names the stub's substitutes but Fjord's (D13) |
| `test_app_geometry_through_the_seed_and_the_product_link` | pytest | 16 downloads (8 variants × GB, AE) through 5.4's link: the app's bytes, `products.json`'s SHA-256 |
| `test_app_geometry_survives_the_portal_upload` | pytest | 8 uploads through `POST /supplier/geometry` (no warnings), submit, approve, download through 5.4: the same bytes; the asset id the platform mints (D14) |
| `test_theme_includes_are_product_ids` | pytest | 5.4 `includes` as product ids for PF7's theme, the app's theme and a JSON feed's mixed list (D15) |
| `test_stub_media_fetcher_serves_only_the_files_folder` | pytest | the `/files/` rule; `../`, a missing file, another path, `http` and an oversize read refused; PF7's folder keeps its `MapFetcher` |
| older suites | pytest | `test_market*.py`, `test_supplier_*.py` unchanged in what they assert (on `tests/fixtures/market`); `test_supplier_geometry_checks` also uploads the app's real `.tbxa` |
| `npm run lint`, `npm run build` | build check | green (no page changed) |

## Human test

Window 1, in the worktree: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` serves `out/` (no page changed in this feature; the steps use the local API). Window 2 (PowerShell), in the worktree's `server` folder:

1. A scratch database and the app's catalogue: `$env:DATABASE_URL='sqlite:///./pf7c-try.db'; $env:STORAGE_DIR='./pf7c-try-storage'; $env:API_URL='http://127.0.0.1:8000'; .venv\Scripts\python.exe scripts\seed_market.py --fixture tests\contracts\marketplace` → three lines `supplier Nord Living (4e6f…0001): verified`, `Atelier Lumen`, `Gulf Paints`, then `feed: not imported …` and nine products `approved` (Arc wall light, Palm wallpaper roll, Desert Sand emulsion 5 L, Bergen armchair, Nord sideboard, Oslo 3-seater sofa, Fjord coffee table, Halden coffee table, Calm lounge theme).
2. Same window: `Start-Process -WorkingDirectory $PWD .venv\Scripts\python.exe '-m uvicorn app.main:app --port 8000'` (a new window opens with the API).
3. `curl.exe -s "http://127.0.0.1:8000/market/search?q=sofa&region=AE" -H "X-Truebex-Contract: marketplace-api/1.1"` → `"name":"Oslo 3-seater sofa"` first with `"amount":129900,"currency":"AED","exponent":2,…,"tax_rate_bp":500`, then the Calm lounge theme (its description names the sofa).
4. `curl.exe -s "http://127.0.0.1:8000/market/products/3f6c1e2a9b0d4c8e9a1b2c3d4e5f6a01?region=GB" -H "X-Truebex-Contract: marketplace-api/1.1"` → two variants: `oat-linen` 109900 GBP, delivery 4900, `in_stock` 12; `charcoal-wool` 119900 GBP, `made_to_order` 42 days; each `geometry` with `"format":"tbxa"` and a `url` of `http://127.0.0.1:8000/market/geometry/…?region=GB`.
5. 5.5 with `prices-gb.json`'s request: `.venv\Scripts\python.exe -c "import json; w=json.load(open('tests/contracts/marketplace/prices-gb.json')); json.dump({'region':'GB','items':[{k:i[k] for k in ('supplier_id','sku','variant_id')}|{'qty':1} for i in w['items']]}, open('pf7c-prices.json','w'))"` then `curl.exe -s -X POST http://127.0.0.1:8000/market/prices -H "X-Truebex-Contract: marketplace-api/1.1" -H "Content-Type: application/json" --data-binary "@pf7c-prices.json"` → eight lines with the GBP amounts of `prices-gb.json` (109900, 119900, 54900, 39900, 42900, 12900, 149900, 119900); `TABLE-HALDEN` is `discontinued` with one substitute whose `product_id` is `…6a04` (Fjord).
6. A 5.4 geometry download: `curl.exe -s -L -o pf7c-sofa.tbxa "http://127.0.0.1:8000/market/geometry/3f6c1e2a9b0d4c8e9a1b2c3d4e5f6a01/oat-linen?region=GB"; (Get-FileHash pf7c-sofa.tbxa).Hash.ToLower()` → `30ded40acd98bfe8d1450a7c4c14be0396f5fe42b36ecd2149a330f5bcb46799`, the `sha256` `products.json` gives `oat-linen`.
7. With an MK1 build (app side; not run by this task) started with `-mwmarket=live -mwapi=http://127.0.0.1:8000` instead of `-mwmarket=stub` (`CadMarketClient.cpp`: `mwapi` is the API base, default `https://api.truebex.com`): the asset browser's catalogue lists the same nine products with GB and AE prices as against the stub; switching the region re-prices them. Known differences the app may show are D1 to D14 below (for example "Wall" instead of "Wall lights", the empty categories of the platform's tree, and Gulf Paints verified).
8. Clean up: close the API window; `Remove-Item -Recurse -Force pf7c-try.db, pf7c-try-storage, pf7c-prices.json, pf7c-sofa.tbxa`.

## Risks / traps

* **The app checkout is CRLF.** `T:\unreal5_7_4_projects\truebex_compact` has `core.autocrlf=true` and no `.gitattributes`, and `git archive` there writes CRLF text too. Copy with `git cat-file blob <id>` per file (or PF14d's `scripts/sync-contract-fixtures.ps1` once merged) and compare `git hash-object --no-filters`; a plain file copy differs in every text file.
* **`taxonomy_sha256` is the CRLF checkout's hash** (D16): `7720dcfb…` is the SHA-256 of `CAD/taxonomy/categories.json` as checked out on Windows; the committed blob's is `cb122851…`. Both sides agree today because both copies are the CRLF file; a Linux checkout of either side would disagree.
* **Two fixture sets.** `tests/contracts/marketplace/` is the app's and is never edited; a change goes to the app repo first. PF7's `tests/fixtures/market/` is regenerated with `make_market_fixtures.py`. `seed_market.py` defaults to PF7's.
* **The seed verifies every stub supplier** (D12): Gulf Paints is `verified: false` in the stub but must be verified for its paint to be listed.

## As-built

* **Date, branch, commits:** 2026-10-13, `ap/t66-pf7c-marketplace-fixtures-re-cop` from `master` 9dac34b. `117d254` (the copy, the move, the seed, the 5.4 `includes` fix, the tests), then the docs commit (this doc, the tracker row, PF7's deviation 2, the README section).
* **Copy:** 28 files from the app's `main` 90799860 (last change to the folder: app commit 68c4f20f, 2026-10-10), written from their blobs; every blob id equal to the app's (`git ls-tree` against `git hash-object --no-filters`). PF7's 24 files moved to `tests/fixtures/market/` (`.gitattributes` among them); only its README changed (`make_market_fixtures.py --check` green).
* **Counts:** pytest collected 669 → 685 (16 in `test_market_contract_fixtures.py`). Tests first: on the unchanged code 13 of the 16 failed; the three that passed have nothing to fix (5.2 already equal, PF8's upload already byte-exact, the folder check is about the copy). The marketplace and supplier files (`test_market*.py`, `test_supplier_*.py`, `test_pf8a_*`, `test_routes_unique.py`, `test_pf14c_utc_times.py`): 86 passed, 11 Postgres skipped on SQLite; the whole suite in the verify gate: 668 passed, 17 skipped. **Postgres 17.10** (throwaway cluster, session zone Asia/Baghdad, `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`): `test_market_production.py` + `test_market_contract_fixtures.py` 33 passed (PF7a's 10 `postgres`-marked tests included); `test_market.py`, `test_market_admin.py`, `test_market_feed.py`, `test_supplier_feeds.py`, `test_supplier_portal.py` 47 passed. The verify gate: see the last bullet.
* **Self-test beyond pytest** (a real uvicorn on 127.0.0.1:18066, SQLite in the scratchpad, `seed_market.py --fixture tests\contracts\marketplace` run twice: the same three suppliers and nine products):
  * `curl.exe "/market/search?q=sofa&region=AE"` → 200, `X-Truebex-Contract: marketplace-api/1.1`; Oslo 3-seater sofa, Nord Living, 129900 AED, exponent 2, `tax_rate_bp` 500, `includes_tax` true, `in_stock`; then the Calm lounge theme (0 AED); facets `furniture/seating/sofas` 1, `decoration/themes` 1.
  * `curl.exe "/market/products/3f6c…6a01?region=GB"` → brand Nord Living, classification `uniclass:Pr_40_50_12_81`; `oat-linen` 109900 GBP, delivery 4900, 5–10 days, `in_stock` 12, tbxa `30ded40a…`; `charcoal-wool` 119900 GBP, `made_to_order` 42 days, tbxa `abef464e…`; geometry URLs `http://127.0.0.1:18066/market/geometry/…?region=GB`.
  * `POST /market/prices` with `prices-gb.json`'s request (8 items, qty 1) → 8 of 8 lines equal to the file (price, availability, substitute ids; Halden → `…6a04`); the same for AE: 8 of 8.
  * The 5.4 link for `oat-linen` → 302 to a signed `/files/market/geometry/30ded40a….tbxa` URL → 200, `attachment; filename="SOFA-OSLO-3-oat-linen.tbxa"`, 1,787 bytes, SHA-256 `30ded40acd98bfe8d1450a7c4c14be0396f5fe42b36ecd2149a330f5bcb46799` = `products.json`'s, byte-identical to the app's file.
  * 5.1 → `taxonomy_sha256` equal; 55 categories (the stub lists 16); only `furniture` (6 vs 5) and `lighting/wall` ("Wall lights" vs "Wall") differ among the stub's 16. 5.6 Gulf Paints → `verified: true`, regions `["AE","GB"]`. 5.4 Calm lounge theme → `includes` the three ids of `products.json`.
* **Differences** (each asserted in `test_market_contract_fixtures.py` under its number). "PATCH" = a dated line for the contract's §3 *Changes* the app side should consider (wording; no version change) unless marked MINOR.

  | # | Reading | Stub (app) | Platform | Contract text | Action |
  |---|---|---|---|---|---|
  | D1 | 5.1 `furniture` count | 6 | 5 (products.json files five products under it) | counts products | asserted. PATCH: the app's `categories.json` says `furniture` 5 (the count is typed by hand in `Scripts/gen_market_fixtures.py`) |
  | D2 | 5.1 paths `furniture/tables/coffee`, `lighting/wall/sconces` | used by Halden, Fjord, Arc | not in the platform's tree (it has `furniture/tables/coffee-tables`, no sconces) | §6.2: deeper segments are free under an app path | the seed adds the stub's missing paths with their labels; `market_categories.json` unchanged. PATCH: "the deeper segments are the platform's; 5.1 lists them" (the owner chooses: the platform adopts `coffee` / `sconces`, or the stub uses `coffee-tables`) |
  | D3 | 5.1 label of `lighting/wall` | "Wall lights" | "Wall" (the app's own `CAD/taxonomy/categories.json` label) | silent | asserted. PATCH: "an app path's label is the taxonomy file's" |
  | D4 | 5.1 rows | 16, only those with products | the whole tree (55 after the seed), `products: 0` included | "the category tree" | asserted. PATCH: "5.1 lists every category, empty ones with `products: 0`; a client hides them if it wants" |
  | D5 | 5.5 (and 5.4 410) `substitutes` elements | product ids | objects: `product_id`, `supplier_id`, `supplier_name`, `sku`, `variant_id`, `name`, `category`, `thumbnail_url`, `price`, `availability` | silent ("`substitutes`: []") | asserted. PATCH: "a substitute is that object; a reader that wants ids reads `product_id`" (MK2's parser must take objects) |
  | D6 | 5.7 `checkout_url` | `https://truebex.com/market/checkout/<id>` | `https://truebex.com/market/checkout/?order=<id>` (the static site serves no per-order path) | "`https://truebex.com/…`" | asserted. PATCH: "`checkout_url` is opened as given, never built by the client" |
  | D7 | 5.7 / 5.9 group `subtotal` and order `total` | §6.3 price (`region`, `includes_tax`, `tax_rate_bp`, `at` too) | money `{amount, currency, exponent}`; the order names `region`, each group its `tax` | `{…}` | asserted. PATCH: "`subtotal`, `delivery`, `tax` and `total` are money; a basket mixing tax rates has no one `tax_rate_bp`" |
  | D8 | 5.13 `created` for the app's feed | 1 (the product) | 4 (rows) | §5.13's example adds up: created + updated + unchanged + rejected = rows | asserted (the text agrees with the platform). PATCH: the app's `feed-report.json` says `created` 4 |
  | D9 | the app's feed files | CSV has no `classification` column; JSON has no `materials` | imported as sent: the CSV's sofa has no classification, the JSON's no materials | §6.4's JSON key list names no `materials` ("the same fields nested") | asserted. PATCH: §6.4's JSON variant keys include `materials` (the platform reads it); the app's two feed files carry the same fields |
  | D10 | 5.4 variant without a file (paint, wallpaper, theme) | no `geometry` key | `"geometry": null` | silent | asserted. PATCH: "no file is `geometry: null`" |
  | D11 | 5.6 `regions` order | the supplier's (`["GB","AE"]`) | alphabetical (`["AE","GB"]`) | example `["GB","AE"]` | asserted. PATCH: "`regions` is a set; its order means nothing" |
  | D12 | 5.6 `verified` | Gulf Paints `false`, its paint listed | only verified suppliers are served (5.6 404, products never listed); the seed verifies all three | example `true` | asserted. PATCH: "5.3 / 5.4 list only verified suppliers' products; the stub's Gulf Paints is `verified: true`" |
  | D13 | 5.4 410 substitutes of the Fjord table | `[Halden]` (discontinued) | `[]`: a substitute must be orderable in the region | "only when a line is unavailable" (silent on the substitute's own state) | asserted. PATCH: "a substitute can be ordered in the region" |
  | D14 | `geometry.asset.id` of an uploaded or fed `.tbxa` | the file's S1 id, a hyphenated FGuid (`6f1c0a2e-9b3d-…`) | minted: 32 hex, stable per product variant (`importer.asset_id`); the seeded catalogue keeps the stub's ids | §6.1 `"id": "<32 hex>"` | asserted. PATCH: say which form the id takes; MINOR if the platform must read a `.tbxa`'s own id (carry-over) |
  | D15 | 5.4 theme `includes` | product ids | was `{supplier_id, sku, variant_id}` for PF7's theme and a JSON feed's; now product ids | 2026-10-11 PR2 line: the app reads a theme's includes "5.4 each" | **fixed** (`catalogue.includes_json`; a JSON feed may name ids) |
  | D16 | `taxonomy_sha256` | `7720dcfb…` | `7720dcfb…` | the hash of `CAD/taxonomy/categories.json` | agree today, fragile: it is the CRLF checkout's hash (the blob's is `cb122851…`). PATCH (app repo): `.gitattributes` `CAD/taxonomy/*.json -text`, or hash the LF form |

  Agreed without a difference: 5.2; 5.5 prices, availability and substitute ids in GB and AE (8 of 8 lines each); 5.4 for all nine products in both regions once D10 and the URLs are masked (asset references, GTINs, brands, classification, `dims_mm` `[0, 0, 0]` for finishes, the theme at 0); 5.6 name, country, website; 5.7 state `awaiting_payment`, the group's state, lines, delivery and amounts (144,900 AED); 5.9 `quoted` at 124,900 AED; the feed's rows, errors and state; every geometry file byte for byte through the seed, PF8's upload and 5.4's link (PF8's GLB checks give no warning for the app's boxes).
* **Deviations and why:**
  1. *The seed adds categories* (D2) instead of `market_categories.json` gaining the stub's paths: the stub's `coffee` and the platform's `coffee-tables` would both read "Coffee tables" under Tables, and which name stays is the owner's call.
  2. *The seed does not import the app's feed* (PF7's catalogue still does): the app's CSV has no `classification` column, so an upsert would clear the sofa's classification and make the seeded catalogue differ from the stub.
  3. *`test_supplier_geometry_checks`* now uploads the app's real `sofa-oslo.tbxa` as well as PF7's JSON stand-in (the stand-in was "until MK1 writes the real asset").
  4. *5.4 `includes`* (D15) is the one public reading changed: the contract's PR2 line agrees with the app.
* **Contract:** no §11 row changes (no endpoint). The PATCH lines above are for the owner to put to the app side; MK1's `products.json`, `categories.json` and `feed-report.json` would change with D1, D8 and D12.
* **Carry-over → which feature:**
  * The owner / app side: the PATCH lines D1–D14 and D16 (MK1, MK2's substitutes parser, MK4's order totals and `checkout_url`).
  * PF7 follow-up: the `https://truebex.com/market/basket?region=…&items=…` page the contract's 2026-10-11 PR2 line says PF7 owns (no such page exists); D2's category names; D14 (a `.tbxa`'s own S1 id as the asset id, MINOR).
  * PF14d: once its `scripts/sync-contract-fixtures.ps1` is on `master`, `-Contract marketplace` should re-copy this folder (it has `geometry/` and `thumbs/` subfolders and keeps MK1's README).
* **Verify gate** (`scripts/autopilot-verify.ps1`, on the docs commit): green in 614 s; lint, build, pytest 668 passed + 17 skipped (the Postgres-only tests) of 685 collected in 356 s.
