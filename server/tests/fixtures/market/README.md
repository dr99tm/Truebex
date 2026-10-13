# PF7's marketplace catalogue (platform tests; marketplace-api.md v1.1.0)

Made by PF7 on 2026-10-09 with `server/scripts/make_market_fixtures.py` (deterministic: re-running
reproduces the text files; `--check` compares them) as the first version of the contract's §9 fixtures.
Since PF7c (2026-10-13) the contract's set is the app's own (MK1), copied byte for byte into
`server/tests/contracts/marketplace/`; this catalogue moved here and stays the platform's: the marketplace
and supplier tests count on its rows. Fixture data, never public copy.

| File | Holds |
|---|---|
| `products.json` | the stub's catalogue: supplier Nord Living (verified, GB and AE) and its products — the Oslo sofa (`oat-linen`, `charcoal-wool`), the discontinued Aker coffee table, the Fjord coffee table that substitutes for it, a paint, a wallpaper and a theme that includes the sofa, the paint and the wallpaper; each variant's §6.3 price, delivery and availability per region under `regions` |
| `geometry/sofa-oslo.tbxa`, `geometry/chair-bergen.glb` | the sofa's object asset (a stand-in with an S1 id until MK1 writes the real one) and the smallest valid GLB for the feed's chair |
| `thumbs/*.png` | one picture per product (≥ 512 px, as §6.4 asks) |
| `media-map.json` | the https URLs the feeds name → these files (nothing is fetched from the internet) |
| `categories.json`, `regions.json` | 5.1 and 5.2 after loading `products.json` |
| `prices-gb.json`, `prices-ae.json` | 5.5 for the sofa's two variants, the Aker table (discontinued: substitutes) and the paint |
| `order-awaiting-payment.json` | 5.7: an order in AE (sofa and paint), payments on and the supplier onboarded |
| `order-quoted.json` | 5.9: a request for quote in AE after the supplier quoted AED 1,180.00 for the sofa |
| `feed-two-regions.csv`, `feed-two-regions.json` | a feed with GB and AE price lists: the sofa's two variants and the Bergen lounge chair (6 rows) |
| `feed-report.json` | 5.13 for `feed-two-regions.csv` imported into an empty catalogue |
| `GD1-supplier-catalogue-template.csv` | a byte copy of `guides/GD1-supplier-catalogue-template.csv` (contract 1.1.0) |

Answers are `{request, http_status, body}` as this server gives them (fixed clock `2026-10-09T10:00:00Z`,
fixed ids). Image URLs carry the SHA-256 of the stored JPEG and are masked when `--check` compares.
