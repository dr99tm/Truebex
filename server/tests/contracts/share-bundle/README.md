# Share-bundle contract fixtures (`contracts/share-bundle.md` 1.1.0, §9)

Copied, never edited: the app side is authoritative for these files (C.9).

This set is PR4's, written by the app's `CadShareBundle::BuildManifest`, from the app repository's
`Docs/roadmap/fixtures/contracts/share-bundle/` on `main` at `7fe6b2c2` (2026-10-14; the folder last changed in
app commit `cc296079`, landed through merge T170 `7caa26aa2` on 2026-10-13). It replaced the set PF5 authored
here on 2026-10-09 (PF5b); PF5's own three-room set, which the viewer tests and PF5's human test use, is now
`server/tests/fixtures/share/`. Re-copy after the app changes the folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sync-contract-fixtures.ps1 -Contract share-bundle
```

The script reads the files as committed on the app's `main` (the app checkout on the owner's PC has
`core.autocrlf=true`, so its working tree holds CRLF copies of these LF files), checks every copy against the
app's git blob id, and keeps this README. The root `.gitattributes` keeps `server/tests/contracts/**` `-text`.
`server/tests/test_share_contract_fixtures.py` checks every file's blob id against the ids below.

| File | App blob | Holds |
|---|---|---|
| `manifest-house.json` | `a453a1c2` | a valid 1.1 manifest in the app's deterministic bytes (keys sorted, `files` by `name`, 2-space indent, LF): three panoramas (all on `pano-2048.jpg`) with hotspots, one render, a two-page PDF, file names with folders (`tour/living-2k.jpg`, `renders/street.jpg`, `drawings/house.pdf`), `cover: null`, `branding`, `plan`, `app_build` and the project card (1 storey, 3 rooms, 72.75 m²) |
| `manifest-invalid.json` | `5f1f9bc3` | ONE case `{errors, manifest, note}`: 422 `manifest_invalid` with exactly these `data.errors[]`, order free: `hotspot_target` at `panoramas[0].hotspots[0].target`, `panorama_ratio` at `panoramas[1].width`, `file_unlisted` at `renders[0].file` |
| `pano-2048.jpg` | `e3f73907` | a 2048 × 1024 equirectangular JPEG (61,772 bytes) |
| `render-640.jpg` | `bf8c1fea` | a 640 × 360 JPEG render (11,595 bytes) |
| `sheets-2p.pdf` | `fd849129` | a two-page PDF (871 bytes) |
| `visits.json` | `7827b9ff` | the visits the app's stub reports for 5.7 (`by_day` as days ago → count, 41 in all; `unique` 17) |
| `qr-stub-link.txt` | `3622438f` | the QR code of `https://stub.invalid/s/k3J9xQ2aTf` (the app's QR encoder test; nothing on the platform reads it) |
