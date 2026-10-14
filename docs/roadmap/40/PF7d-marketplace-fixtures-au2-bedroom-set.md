# PF7d — Marketplace fixtures re-copied after AU2's bedroom set (13 products), and the platform's answers checked against them (launch priority 2)

**Needs merged:** PF7c (on `master` since T71; this task started from 988334f); AU2 on the app side (auto furniture layouts by room type: app commit 180b2d53f added the bedroom set to the fixture folder; it reached the app's `main` in the T170 merge 7caa26aa2 at 13:57 UTC on 2026-10-13). **Unblocks:** AU2's `Layout.Products` and MK1's catalogue against the real API with the bedroom set; one new reading (D17) for the owner to put to the app side. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\marketplace-api.md` 1.1.0, unchanged (§9 stub fixtures; the app side is authoritative, C.9). No platform route, shape or version changes.

## Status

**Built (2026-10-14, branch `ap/t75-pf7d-marketplace-fixtures-re-cop`, Autopilot T75); see As-built.** Checked on `master` 988334f before the work began:

| # | Where (master 988334f) | Before |
|---|---|---|
| 1 | `server/tests/contracts/marketplace/` | PF7c's copy of MK1's set from app `main` 90799860: 28 files, 3 suppliers, 9 products. Against the app's folder at 7caa26aa2: 8 files new (`geometry/` and `thumbs/` of `bed-fjell`, `bed-fjell-single`, `wardrobe-nord`, `bedside-fjell`), 5 changed (`README.md`, `categories.json`, `products.json`, `prices-gb.json`, `prices-ae.json`), 23 byte-identical |
| 2 | `server/tests/test_market_contract_fixtures.py:154` | asserts 3 suppliers and 9 products; D1 asserted as 6 vs 5, D2 as the two paths the seed adds; 16 geometry downloads, 8 portal uploads |
| 3 | `server/app/market/taxonomy/market_categories.json` | has `furniture/beds/double-beds`, `furniture/beds/single-beds` and `furniture/storage/wardrobes`; not the stub's `furniture/beds/double`, `furniture/beds/single` or `furniture/storage/bedside`, which PF7c's seed rule (D2) adds |
| 4 | `server/app/market/seed.py` `_load_stub`, `_stub_categories` | reads the stub's shape whatever its product count; adds every missing path with the stub's label |

AU2's four products (all Nord Living, one variant and one GLB each, GB and AE prices, `in_stock`): the **Fjell double bed** (`BED-FJELL-160` / `oak-160`, `furniture/beds/double`, 1600 x 480 x 2000 mm, GBP 799.00 / AED 949.00), the **Fjell single bed** (`BED-FJELL-90` / `oak-90`, `furniture/beds/single`, GBP 499.00 / AED 599.00), the **Nord wardrobe** (`WARDROBE-NORD-120` / `walnut-120`, `furniture/storage/wardrobes`, GBP 999.00 / AED 1,199.00) and the **Fjell bedside table** (`BEDSIDE-FJELL` / `oak`, `furniture/storage/bedside`, GBP 149.00 / AED 179.00). The beds name each other as substitutes; the wardrobe and the bedside table name none.

## Goal

The platform keeps testing against the app's own marketplace files (contract §9) now that AU2 has added a bedroom set to them: the folder is the app's copy again, byte for byte, the seed loads all thirteen products, and every reading PF7c checked is checked for the new products too. A reading the two sides disagree on fails a test and gets a PATCH line, as in PF7c.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4, C.9 (in the app's `00-contract.md`).
* PF7c's doc (`PF7c-marketplace-fixtures-from-mk1.md`): the As-built's Differences table D1–D16 and its Deviations; PF7's and PF7b's docs.
* `server/tests/test_market_contract_fixtures.py`, `server/tests/test_pf7b_pf7c_meet.py`, `server/scripts/seed_market.py`, `scripts/sync-contract-fixtures.ps1`, `server/tests/contracts/marketplace/README.md`.
* Read only: the app's fixture README and `contracts/marketplace-api.md` (§5.5 substitutes, §9, the 2026-10-11 PR2 line on the basket link).

## Scope

**In:**

1. The app's folder re-copied with `scripts\sync-contract-fixtures.ps1 -Contract marketplace` (reads the app repo only), every blob id checked; the copy is never edited.
2. Tests first, each failing on `master` before the copy: the folder's blob ids are the app's (1); the seed reads 3 suppliers and 13 products, twice the same (2); 5.1 like the stub with D1's count and D2's paths updated (3); 5.4 for all 13 products in GB and AE, D10 and the URLs masked (4); 5.5 for every line of the new prices files in GB and AE (5); every geometry file, the four new GLBs included, through the seed, PF8's upload (no warning) and 5.4's link (6); test 7's condition (a theme including a bedroom product) and the bedroom set through PF7b's basket route (7).
3. Only what the tests show is fixed; new differences are D17 on, in PF7c's table form, with PATCH lines for the owner.
4. PF7c's deviation 1 kept: the seed adds the stub's paths, `market_categories.json` unchanged.
5. This doc, the PF7d tracker row, one line of PF7c's doc (its carry-over), a README section.

**Out (and where it goes):**

* Which bed paths stay (the platform's `double-beds` / `single-beds` or the stub's `double` / `single`), and adding `bedside` to the platform's tree: the owner's call, like D2 (carry-over).
* Editing the app repo (read-only here): D1, D2, D17's PATCH lines are the owner's to put to the app side.
* `scripts\try-mobile.ps1` keeps seeding PF7's catalogue (`tests\fixtures\market`, the phone's prices and swaps); the human test seeds the app's catalogue into a scratch database instead (Deviation 4).

## Design

**Folder.** `server/tests/contracts/marketplace/` = the app's `Docs/roadmap/fixtures/contracts/marketplace/` at 180b2d53f (the same tree at `main` 7caa26aa2 and 7fe6b2c21): 36 files, `README.md`, the eleven JSON / CSV files, `geometry/` (4 `.tbxa`, 7 `.glb`), `thumbs/` (14 PNG, 512 px). The folder's `README.md` is the app's own file (MK1 wrote it, AU2 changed it; the script copies it with the rest), so the app commit and the blob ids are kept in the test module (`APP_BLOBS`), this doc and the README section, not in it (Deviation 2).

**Seed.** No change: `seed._load_stub` reads the 13 products; `_stub_categories` adds the five paths the platform's tree lacks, parents first, with the stub's labels.

**Parity.** `test_market_contract_fixtures.py` keeps PF7c's masks (minted ids, server times, URLs) and its D-numbers; the new expectations are written as numbers and SKUs, so each test fails on the old copy. `APP_BLOBS` is `git ls-tree -r` of the app's folder; the test computes each file's blob id the way `git hash-object --no-filters` does (SHA-1 of `blob <size>\0` + the bytes).

**Bedroom set and the basket (`test_pf7d_bedroom_set.py`).** No theme in the new `products.json` includes a bedroom product (the one theme is MK1's Calm lounge: sofa, Halden table, paint), so there is no theme look for PF7b's basket; the test asserting that fails when the app adds one. The bedroom set itself is the look an auto bedroom layout swaps its boxes for: as `<supplier>:<sku>:default:1` lines (the contract's basket link format), PF7b's `POST /market/basket` names the four products and resolves `default` to each one's only variant; 5.5 prices them at `prices-<region>.json`'s amounts; 5.7 orders them on the app's catalogue (one Nord Living group, AED amounts of `products.json`).

**Security and privacy.** Test fixtures only; nothing new is served.

## Deliverables

- [x] `server/tests/contracts/marketplace/` = the app's 36 files at 180b2d53f (8 new, 5 updated, 23 unchanged)
- [x] `server/tests/test_market_contract_fixtures.py` (`APP_BLOBS`, `test_contract_folder_blobs_are_the_apps`, the updated counts, D1, D2, D17)
- [x] `server/tests/test_pf7d_bedroom_set.py` (4 tests)
- [x] `server/scripts/seed_market.py` (docstring: thirteen products)
- [x] this doc, the PF7d tracker row, PF7c's carry-over line, `README.md` section "Marketplace fixtures after AU2's bedroom set (PF7d)"

## Tests

| Name | Kind | Asserts | On `master` 988334f |
|---|---|---|---|
| `test_contract_folder_blobs_are_the_apps` | pytest (new) | every file's git blob id equals the app's `ls-tree` (`APP_BLOBS`, 36 files) | failed: 5 ids differ, 8 files missing |
| `test_contract_folder_is_the_apps_copy` | pytest | exactly the 36 files, LF only; 3 suppliers, 13 products, the four bedroom SKUs Nord Living's; every geometry file's SHA-256 and size as `products.json`; GLB magic; thumbnails ≥ 512 px | failed: the file set |
| `test_seed_reads_the_apps_catalogue` | pytest | `seed_market.main` twice: the same output and rows; 3 suppliers verified, 13 products approved (the bedroom SKUs printed); each found by 5.3 in GB and AE; `q=bed` finds the Fjell double and single beds at `products.json`'s GB and AE prices | failed: `(3, 9) == (3, 13)` |
| `test_categories_like_the_stub` | pytest | 5.1: D2's five added paths and labels; the platform's `double-beds`, `single-beds` (empty) and `wardrobes` kept; every stub row's app path, label (D3) and count; D1 10 vs 9; D4 | failed: two added paths, not five |
| `test_batch_prices_like_the_stub[GB]`, `[AE]` | pytest | 5.5 for the file's request: 12 lines equal (D5 masked), the last four the bedroom set at the file's prices | failed: `8 == 12` |
| `test_products_and_suppliers_like_the_stub` | pytest | 5.4 for all 13 products in GB and AE equals the stub's projection (D10, URLs masked); 5.6 (D11, D12) | failed: no bedroom SKUs |
| `test_withdrawn_substitutes_like_the_stub` | pytest | 5.4's 410 for each of the 13: the stub's substitutes but Fjord's (D13) and the three storage products' (D17); the beds name each other on both sides | failed: no storage SKUs |
| `test_app_geometry_through_the_seed_and_the_product_link` | pytest | 24 downloads (12 variants × GB, AE), the four new GLBs among them: the app's bytes and SHA-256 | failed: `16 == 24` |
| `test_app_geometry_survives_the_portal_upload` | pytest | 12 uploads through `POST /supplier/geometry`, no warnings (the boxes measure as `dims_mm`), approved, downloaded through 5.4: the same bytes; D14 | failed: `8 == 12` |
| `test_no_theme_includes_the_bedroom_set` | pytest (new) | the one theme is THEME-CALM (sofa, Halden, paint); no theme includes a bedroom product | failed: no bedroom SKUs |
| `test_bedroom_set_basket_named_and_priced_like_the_app[GB]`, `[AE]` | pytest (new) | `POST /market/basket` with `default` and with the variant ids: four lines found, names, Nord Living, `only` / `asked`; 5.5 at `prices-<region>.json` | failed: no bedroom SKUs |
| `test_bedroom_set_orders_on_the_apps_catalogue` | pytest (new) | basket → 5.5 → 5.7 in AE: `awaiting_payment`, one group of 4 lines, subtotal AED 2,926.00 + delivery | failed: no bedroom SKUs |
| PF7c's other tests, `test_pf7b_pf7c_meet.py`, the marketplace and supplier suites | pytest | unchanged | passed (10 of the 24 in the three PF7c / PF7d files) |
| `npm run lint`, `npm run build` | build check | green (no page changed) | |

## Human test

Window 1 (PowerShell), in the worktree's `server` folder:

1. A scratch database with the app's catalogue: `$env:DATABASE_URL='sqlite:///./pf7d-try.db'; $env:STORAGE_DIR='./pf7d-try-storage'; $env:API_URL='http://127.0.0.1:8000'; $env:CORS_ORIGINS='http://127.0.0.1:3175,http://127.0.0.1:3100'; .venv\Scripts\python.exe scripts\seed_market.py --fixture tests\contracts\marketplace` → `supplier Nord Living (4e6f72644c6976696e67000000000001): verified`, `Atelier Lumen`, `Gulf Paints`, `feed: not imported …`, then 13 lines `approved`, among them `BED-FJELL-160 Fjell double bed`, `BED-FJELL-90 Fjell single bed`, `BEDSIDE-FJELL Fjell bedside table` and `WARDROBE-NORD-120 Nord wardrobe`. Run the same command again → the same lines.
2. Same window: `Start-Process -WorkingDirectory $PWD .venv\Scripts\python.exe '-m uvicorn app.main:app --host 127.0.0.1 --port 8000'` (a new window opens with the API; it inherits the variables).
3. `curl.exe -s "http://127.0.0.1:8000/market/search?q=bed&region=GB" -H "X-Truebex-Contract: marketplace-api/1.1"` → three results, all Nord Living and `in_stock`: Fjell bedside table `"amount":14900,"currency":"GBP"`, Fjell double bed `79900`, Fjell single bed `49900` (`tax_rate_bp` 2000). With `region=AE` → `17900`, `94900`, `59900` `"currency":"AED"` (`tax_rate_bp` 500).
4. `curl.exe -s "http://127.0.0.1:8000/market/products/3f6c1e2a9b0d4c8e9a1b2c3d4e5f6a0a?region=GB" -H "X-Truebex-Contract: marketplace-api/1.1"` → `"name":"Fjell double bed"`, `"category":"furniture/beds/double"`, one variant `oak-160` (size 160 x 200, Oak; `dims_mm` [1600, 480, 2000]) at 79900 GBP, delivery 5900, 7–14 days, `in_stock` 6, `geometry` `"format":"glb"` with `"sha256":"d1412477ad303e1def61d91a2e25293a7e054f98690bce8b085110621e49bf72"` and a `url` of `http://127.0.0.1:8000/market/geometry/3f6c1e2a9b0d4c8e9a1b2c3d4e5f6a0a/oak-160?region=GB`.
5. The GLB: `curl.exe -s -L -o pf7d-bed.glb "http://127.0.0.1:8000/market/geometry/3f6c1e2a9b0d4c8e9a1b2c3d4e5f6a0a/oak-160?region=GB"; (Get-FileHash pf7d-bed.glb).Hash.ToLower(); (Get-Item pf7d-bed.glb).Length` → `d1412477ad303e1def61d91a2e25293a7e054f98690bce8b085110621e49bf72` and `1620`, the app's `geometry/bed-fjell.glb`.

Window 2 (PowerShell), in the worktree root:

6. `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build` (about 2 min), then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → it prints the port (3175 for T75, 3100 when `AUTOPILOT_TASK_ID` is unset).
7. Open `http://127.0.0.1:<port>/market/basket?region=GB&items=4e6f72644c6976696e67000000000001%3ABED-FJELL-160%3Adefault%3A1%2C4e6f72644c6976696e67000000000001%3ABED-FJELL-90%3Adefault%3A1%2C4e6f72644c6976696e67000000000001%3AWARDROBE-NORD-120%3Adefault%3A1%2C4e6f72644c6976696e67000000000001%3ABEDSIDE-FJELL%3Adefault%3A1` (the bedroom set as the app's basket link) → "Buy this look", "Prices for United Kingdom, in GBP", each with its picture and "In stock": Fjell double bed GBP 799.00 (Nord Living · 160 x 200, Oak), Fjell single bed GBP 499.00 (90 x 200, Oak), Nord wardrobe GBP 999.00 (120 cm, Walnut), Fjell bedside table GBP 149.00 (Oak); Products total GBP 2,446.00; "Sign in" and "Create an account".
8. Change `region=GB` to `region=AE` in the address → "Prices for United Arab Emirates, in AED": AED 949.00, AED 599.00, AED 1,199.00, AED 179.00; Products total AED 2,926.00.
9. Clean up: close the API window and stop the server in window 2 (Ctrl+C); in `server`: `Remove-Item -Recurse -Force pf7d-try.db, pf7d-try-storage, pf7d-bed.glb`; in the root: `Remove-Item -Recurse -Force out` (it points at the local API; the next `autopilot-serve.ps1` rebuilds it against `.env.local`).

Optional, app side (not run by this task): an app build started with `-mwmarket=live -mwapi=http://127.0.0.1:8000` lists the same 13 products in the asset browser's catalogue with GB and AE prices; the differences it may show are PF7c's D1–D16 and D17 below.

## Risks / traps

* **The folder's README is the app's.** `sync-contract-fixtures.ps1` copies it like every other file and its closing hint says to update it: for this folder, don't (the blob check fails). The app commit lives in `APP_BLOBS`' comment and here. The hint's test name, `test_marketplace.py`, does not exist either: the tests are `test_market_contract_fixtures.py`, `test_pf7d_bedroom_set.py` and `test_pf7b_pf7c_meet.py`.
* **5.1 lists "Double beds" and "Single beds" twice under Beds** (D2): the platform's empty `double-beds` / `single-beds` and the stub's `double` / `single` the seed adds. A client hiding empty categories (D4) shows one of each.
* **Search order differs by database.** `q=bed` answers bedside table, double bed, single bed on SQLite, double bed first on Postgres (`ts_rank`); the tests compare sets.
* **The app checkout is CRLF.** Use the script (its `git archive` runs with `core.autocrlf=false`) or `git cat-file blob`, never a file copy; check with `git hash-object --no-filters`.

## As-built

* **Date, branch, commits:** 2026-10-14, `ap/t75-pf7d-marketplace-fixtures-re-cop` from `master` 988334f. `1655de9` (tests first), `b218bb7` (the copy, `seed_market.py`'s docstring), then the docs commit (this doc, the tracker row, PF7c's carry-over line, the README section).
* **Copy:** `scripts\sync-contract-fixtures.ps1 -Contract marketplace` from the app's `main` 7fe6b2c2 ("copied 36 files … each byte-exact to the app's blob"; updated 13, unchanged 23, removed none). The folder's tree is the same at 180b2d53f, 7caa26aa2 and 7fe6b2c21. The staged blob ids equal `git ls-tree -r 7caa26aa2 -- Docs/roadmap/fixtures/contracts/marketplace/` for all 36 files, and `git hash-object --no-filters` of each worktree file equals its staged id.
* **Counts:** pytest collected 718 → 723 (`test_contract_folder_blobs_are_the_apps` and the four tests of `test_pf7d_bedroom_set.py`). **Tests first:** with the old copy, 14 of the 24 tests in `test_market_contract_fixtures.py`, `test_pf7d_bedroom_set.py` and `test_pf7b_pf7c_meet.py` failed (each for its new expectation: the file set, the blob ids, 9 not 13 products, 2 not 5 added paths, 8 not 12 price lines, 16 not 24 downloads, 8 not 12 uploads, the bedroom SKUs missing); 10 passed. **With the copy and no code change, all 24 passed**: nothing in the platform needed fixing. The marketplace and supplier files (`test_market*.py`, `test_supplier_*.py`, `test_pf7*.py`, `test_pf8*.py`, `test_routes_unique.py`, `test_pf14c_utc_times.py`): 111 passed, 12 skipped (Postgres-only) on SQLite. **Postgres 17.10** (throwaway cluster, session zone Asia/Baghdad, `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`): `test_market_contract_fixtures.py`, `test_pf7d_bedroom_set.py`, `test_pf7b_pf7c_meet.py`, `test_market_production.py`, `test_pf7b_basket.py` 50 passed, 1 skipped (`out/` not built); `test_market.py`, `test_market_admin.py`, `test_market_feed.py`, `test_supplier_feeds.py`, `test_supplier_portal.py` 47 passed. The verify gate: see the last bullet.
* **Self-test beyond pytest** (a real uvicorn on 127.0.0.1:18075, `seed_market.py --fixture tests\contracts\marketplace` run twice: the same three suppliers and 13 products, the same output; once on SQLite, once on the Postgres cluster):
  * `curl.exe "/market/search?q=bed&region=GB"` → 200, `X-Truebex-Contract: marketplace-api/1.1`; Fjell bedside table 14900, Fjell double bed 79900, Fjell single bed 49900 GBP (exponent 2, `tax_rate_bp` 2000, `includes_tax` true, `in_stock` 20 / 6 / 9); facets `furniture/beds/double` 1, `furniture/beds/single` 1, `furniture/storage/bedside` 1. AE: 17900, 94900, 59900 AED, `tax_rate_bp` 500.
  * `curl.exe "/market/products/3f6c…6a0a?region=GB"` (Fjell double bed) → `furniture/beds/double`, app path `furniture/beds`, brand Nord Living; `oak-160` 160 x 200, Oak, [1600, 480, 2000] mm, 79900 GBP, delivery 5900, 7–14 days, `in_stock` 6; GLB `d1412477…`, 1,620 bytes. AE: 94900 AED, delivery 20000, 10–21 days. Price, delivery and availability equal to `products.json` in both.
  * Its 5.4 link → 302 to a signed `/files/market/geometry/d1412477….glb` URL → 200, `model/gltf-binary`, `attachment; filename="BED-FJELL-160-oak-160.glb"`, 1,620 bytes, SHA-256 `d1412477ad303e1def61d91a2e25293a7e054f98690bce8b085110621e49bf72`, byte-identical to the app's `geometry/bed-fjell.glb`.
  * 5.1 → 58 rows (55 before AU2's three paths); `furniture` 9, `furniture/storage` 3, `furniture/beds` 2, `wardrobes` 1, `sideboards` 1, `bedside` 1, `double` 1, `single` 1, `double-beds` 0, `single-beds` 0.
  * `POST /market/prices` with `prices-gb.json`'s and `prices-ae.json`'s requests (12 items each) → 12 of 12 lines equal in both (price, availability, substitute ids).
  * The wardrobe withdrawn → 5.4 410 `product_withdrawn`, substitutes `SIDEBOARD-NORD`, `BEDSIDE-FJELL` (D17).
  * **Headless Edge on the served site** (`out/` built against the local API, `scripts/serve-out.py`, a CDP driver): `/market/basket?region=GB&items=<the bedroom set, default>` → "Prices for United Kingdom, in GBP", the four products at GBP 799.00, 499.00, 999.00, 149.00, "In stock", Products total GBP 2,446.00; `region=AE` → AED 949.00, 599.00, 1,199.00, 179.00, total AED 2,926.00; their four thumbnails loaded from the API; no console error or exception.
* **Differences.** PF7c's D1–D16 stand as written in its As-built (D3–D16 unchanged by AU2's set); two moved, one is new. "PATCH" = a dated line for the contract's §3 *Changes* the app side should consider (wording; no version change).

  | # | Reading | Stub (app) | Platform | Contract text | Action |
  |---|---|---|---|---|---|
  | D1 (moved) | 5.1 `furniture` count | 10 (6 before AU2) | 9 (5 before): `products.json` files nine products under it | counts products | asserted. PATCH: the app's `categories.json` says `furniture` 9 (the count is still typed by hand in `Scripts/gen_market_fixtures.py`, one over). The app's README also still says "16 categories"; the file has 21 rows |
  | D2 (moved) | 5.1 paths the seed adds | `furniture/beds/double` "Double beds", `furniture/beds/single` "Single beds", `furniture/storage/bedside` "Bedside tables" (AU2), with MK1's `furniture/tables/coffee`, `lighting/wall/sconces` | the platform's tree has `furniture/beds/double-beds` "Double beds", `furniture/beds/single-beds` "Single beds", no bedside; `furniture/storage/wardrobes` "Wardrobes" on both sides | §6.2: deeper segments are free under an app path | the seed adds the five paths with the stub's labels (PF7c deviation 1 kept); `market_categories.json` unchanged, so Beds lists "Double beds" and "Single beds" twice (the platform's empty). PATCH as PF7c's D2; the owner chooses: the platform adopts `double` / `single` / `bedside`, or the stub uses `double-beds` / `single-beds` and the platform adds a bedside path |
  | D17 (new) | 5.4 410 `substitutes` of the three `furniture/storage` products (MK1's Nord sideboard, AU2's Nord wardrobe and Fjell bedside table) | `[]` for each | the other two, nearest in price first, GB and AE alike: sideboard → wardrobe, bedside table; wardrobe → sideboard, bedside table; bedside table → wardrobe, sideboard | §5.5: "≤ 3, same category" (the stub's own sofa → armchair and double ↔ single bed substitutes are another category under the same app path) | asserted. PATCH: "a substitute is a product of the same category, else of the same app path, orderable in the region, nearest in price"; the app's `products.json` then lists the storage products' substitutes. Or the owner narrows the platform's rule to the category, and the stub drops its app-path substitutes (sofa ↔ armchair, double ↔ single bed) |

  Agreed without a difference for AU2's set: 5.4 for all four in GB and AE once D10 and the URLs are masked (options, `dims_mm`, materials, brand, asset name / rev / kind, delivery fees and days); 5.5 every new line in both regions (12 of 12 with MK1's); 5.4's 410 for the beds (double ↔ single, the platform reaching the other bed through the app path); 5.1 rows, labels and counts for `furniture/storage`, `furniture/beds`, `wardrobes`, `bedside`, `double`, `single`; 5.3 for each by name and for `bed`; every new GLB byte for byte through the seed, PF8's portal upload (PF8's GLB checks give no warning: each box measures as its `dims_mm`) and 5.4's link.
* **Deviations and why:**
  1. *PF7c's deviation 1 kept* (D2): the seed adds the stub's `double`, `single` and `bedside` paths; `market_categories.json` is unchanged. Which bed names stay is the owner's call, like D2.
  2. *The folder's README is not edited:* it is the app's own file (copied by the script like the rest), so editing it would break "every blob id equal". The app commit is in `APP_BLOBS`' comment (`test_market_contract_fixtures.py`), this doc and the README section.
  3. *Test 7:* no theme in the new `products.json` includes a bedroom product, so there is no theme look to put through PF7b's basket. `test_no_theme_includes_the_bedroom_set` records that (it fails when the app adds such a theme); the bedroom set itself goes through PF7b's basket route, 5.5 and 5.7 instead, and the human test opens the basket page with it.
  4. *Human test without `try-mobile.ps1` or a `/market/` search page:* `try-mobile.ps1` seeds PF7's catalogue (`tests\fixtures\market`, the phone's prices and swaps), not the app's, and the site has no catalogue search page (`/market/` holds the basket and checkout pages). The human test seeds the app's catalogue into a scratch database, asks 5.3 for "bed" with `curl.exe` and opens the site's basket page with the bedroom set for GB and AE prices.
* **Contract:** no §11 row changes (no endpoint). The PATCH lines of D1, D2 and D17 are for the owner to put to the app side; the app's `categories.json` (D1) and `products.json` (D17) would change.
* **Carry-over → which feature:**
  * The owner / app side: D1, D2 and D17's PATCH lines (AU2, MK1, MK2's substitutes); PF7c's D3–D16 stand.
  * PF7 follow-up: D2's category names, now `double-beds` / `single-beds` / a bedside path as well as `coffee-tables` / sconces.
  * `scripts/sync-contract-fixtures.ps1` (PF14d's): its closing hint names `test_<contract>.py` and says to update the folder's README; for the marketplace folder the tests are `test_market_contract_fixtures.py` + `test_pf7d_bedroom_set.py` and the README is the app's. A wording fix in the script whenever it is next touched.
  * The next re-copy of this folder: run the script, update `APP_BLOBS` from the app's `git ls-tree`, then the counts the tests name.
* **Verify gate** (`scripts/autopilot-verify.ps1`, on the docs commit ebb6d74): green in 570 s; lint, build, pytest 706 passed + 17 skipped (the Postgres-only tests) of 723 collected in 389 s.
