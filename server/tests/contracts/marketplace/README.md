# Marketplace stub fixtures (contracts/marketplace-api.md §9)

What `-mwmarket=stub[:price-changed|offline|withdrawn]` answers from (roadmap 40 / MK1,
`Plugins/CADTOOL/Source/TruebexMarket/Private/CadMarketStub.cpp`). The platform copies the same files
into `server/tests/contracts/marketplace/`. Staged loose into every NON-Shipping package
(`TruebexMarket.Build.cs`); the Shipping release carries none.

| File | Holds |
|---|---|
| `categories.json` | 5.1: 16 categories rooted on the app's taxonomy (`app_path` is always a row of `CAD/taxonomy/categories.json`; `taxonomy_sha256` is that file's) |
| `regions.json` | 5.2: GB (GBP, VAT 20 %) and AE (AED, VAT 5 %) |
| `products.json` | the catalogue: 3 suppliers and 15 products -- the **Oslo 3-seater sofa** (two variants, Oat / Charcoal, a `.tbxa` each, GB and AE prices), the Bergen armchair (`.tbxa`), the **discontinued Halden coffee table** (GLB; substitutes: Fjord, Sund, Vik), the Fjord coffee table (GLB), the Arc wall light (GLB, `lighting/wall`: wall-mounted), the Nord sideboard (a parametric `.tbxa`: O1's cabinet recipe; variants 2400 x 900 x 750 and 1800 x 450 x 750), a paint and a wallpaper (`finish`), the Calm lounge **theme** (includes the sofa, the coffee table and the paint), and (roadmap 40 / AU2) the bedroom set `Layout.Products` swaps an auto layout's boxes for: the Fjell double and single beds (1600 / 900 x 2000 x 480), the Nord wardrobe (1200 x 600 x 2200) and the Fjell bedside table (450 x 400 x 560), a GLB each, and (roadmap 40 / MK2) the Sund and Vik coffee tables (GLB), so the discontinued Halden lists three same-category substitutes -- 15 products |
| `geometry/*.tbxa` | the four object assets, each with its S1 id, written by the 2D scenario `mk1-fixture-geometry` from the app's own serializer (single-line JSON, no newline: no checkout can change their sha256) |
| `geometry/*.glb` | nine small box meshes (glTF 2.0, metres, +Y up) |
| `thumbs/*.png` | one 512 px thumbnail per product (the feed's minimum) |
| `prices-gb.json`, `prices-ae.json` | the region's 5.5 price list: every placeable variant (MK2). The stub answers exactly the lines a request names, stamped with the time it answers and `stale_after` = +24 h; a line the list lacks answers with no price (not sold there); more than 500 items is 413 `too_large` |
| `order-awaiting-payment.json`, `order-quoted.json` | 5.7 / 5.9 answers for the MK4 human test's basket (`MK4-living-room-basket.tbxp`, AE: two Oslo sofas + the Fjord coffee table from Nord Living, the Arc wall light from Atelier Lumen; contract 1.2.0 shape with per-supplier `items`). The stub BUILDS its answers from each request (contract §9: it keeps orders per `Idempotency-Key`, a quote is quoted at its second 5.9, an order paid / accepted / shipped / delivered at the 2nd-5th); `order-quoted.json`'s `items[].quoted` are the quotes it gives (else 95 % of `price_seen`) |
| `feed-two-regions.csv`, `feed-two-regions.json`, `feed-report.json` | the Oslo sofa as a supplier feed with a GB and an AE price list, and its expected import report (PF8) |

**products.json is the stub's own shape**: each product is written once, and each variant carries
per-region lists -- `"prices": {"GB": {...}, "AE": {...}}` and `"deliveries"` -- plus `"substitutes"` on
the product. The stub projects them to §6.1's `price` / `delivery` for the region a request names and
drops `substitutes` / `supplier_name` / `thumbnail_url` from 5.4 (5.3 hits carry `supplier_name` and
`thumbnail_url`), so the client only ever sees shapes the contract names. File URLs are
`https://market.truebex.com/files/<path>`; the stub serves any URL whose path holds `/files/` from this
folder.

Variants: `offline` -- every call fails as if the network were down; `withdrawn` -- 5.4 answers 410
`product_withdrawn` with the product's `substitutes`; `price-changed` -- the first 5.7 answers 409.

Regenerate: `python Scripts/gen_market_fixtures.py` (deterministic). After a change to the `.tbxa`
geometry (`CadSelfTest_MK1.cpp` `GeometryFixtures`): delete the file, run `mk1-fixture-geometry` (it
writes it and fails once), then the script again (it re-stamps every `sha256` / `bytes`).
