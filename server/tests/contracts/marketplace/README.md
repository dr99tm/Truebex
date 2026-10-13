# Marketplace stub fixtures (contracts/marketplace-api.md §9)

What `-mwmarket=stub[:price-changed|offline|withdrawn]` answers from (roadmap 40 / MK1,
`Plugins/CADTOOL/Source/TruebexMarket/Private/CadMarketStub.cpp`). The platform copies the same files
into `server/tests/contracts/marketplace/`. Staged loose into every NON-Shipping package
(`TruebexMarket.Build.cs`); the Shipping release carries none.

| File | Holds |
|---|---|
| `categories.json` | 5.1: 16 categories rooted on the app's taxonomy (`app_path` is always a row of `CAD/taxonomy/categories.json`; `taxonomy_sha256` is that file's) |
| `regions.json` | 5.2: GB (GBP, VAT 20 %) and AE (AED, VAT 5 %) |
| `products.json` | the catalogue: 3 suppliers and 9 products -- the **Oslo 3-seater sofa** (two variants, Oat / Charcoal, a `.tbxa` each, GB and AE prices), the Bergen armchair (`.tbxa`), the **discontinued Halden coffee table** (GLB; substitute: Fjord), the Fjord coffee table (GLB), the Arc wall light (GLB, `lighting/wall`: wall-mounted), the Nord sideboard (a parametric `.tbxa`: O1's cabinet recipe; variants 2400 x 900 x 750 and 1800 x 450 x 750), a paint and a wallpaper (`finish`), and the Calm lounge **theme** (includes the sofa, the coffee table and the paint) |
| `geometry/*.tbxa` | the four object assets, each with its S1 id, written by the 2D scenario `mk1-fixture-geometry` from the app's own serializer (single-line JSON, no newline: no checkout can change their sha256) |
| `geometry/*.glb` | three small box meshes (glTF 2.0, metres, +Y up) |
| `thumbs/*.png` | one 512 px thumbnail per product (the feed's minimum) |
| `prices-gb.json`, `prices-ae.json` | 5.5 answers: every placeable variant re-priced for the region (MK2) |
| `order-awaiting-payment.json`, `order-quoted.json` | 5.7 / 5.9 answers (MK4) |
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
