# Share-bundle contract fixtures (share-bundle.md v1.0.0, §9)

Made by PF5 on 2026-10-09 with `server/scripts/make_share_fixtures.py` (the JSON is deterministic; the
JPEGs and the PDF are too with the same Pillow build). From the merge on, the master copy is the app repo's
`Docs/roadmap/fixtures/contracts/share-bundle/`; the platform keeps a copy here, copied, never edited.

| File | Holds |
|---|---|
| `pano-2048.jpg`, `pano-2048-kitchen.jpg`, `pano-2048-hall.jpg` | 2048 × 1024 equirectangular rooms (living room, kitchen, hall). N / E / S / W are painted at their true bearings and a doorway sits where each hotspot points, so a viewer's bearings can be checked by eye. The kitchen's `center_bearing_deg` is 90 (its middle column faces east); the others' is 0 |
| `render-640.jpg` | the 640 × 360 "Street view" render |
| `sheets-2p.pdf` | a two-page vector PDF (A-101 plan, A-102 sections) using the standard Helvetica fonts |
| `manifest-house.json` | a valid `truebex-share/1` manifest: three panoramas with hotspots, one render, one PDF |
| `manifest-invalid.json` | `cases[]`: `manifest-house.json` with one thing broken and the `expect`ed 422 `manifest_invalid` with `data.errors[]` (`path`, `rule`). The first three are the contract's (a 3:1 panorama, a hotspot to a missing id, a file not listed) |
| `visits.json` | visits to replay (`visitor`, `at`) and the 5.7 `visits` object they produce at `now` |

The contract's §9 table names one `pano-2048.jpg`; three distinct rooms are shipped so a hotspot visibly
changes the room (the human test's "tap the Kitchen hotspot → the kitchen panorama").
