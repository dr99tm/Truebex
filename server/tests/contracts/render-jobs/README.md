# Render-jobs contract fixtures (`contracts/render-jobs.md` 1.2.0, §9)

Copied, never edited: the app side is authoritative for these files. This README is the platform's own (the
app's folder has none).

Two sets of the app's own, in one folder:

* **Renders** (1.1.0, CL3, the headless render service mode): `TruebexSync::MakeRenderJobFixtures`
  (`-mwcl3fixtures`) writes the job files and the operation, and CL3's own `-mwrender` runs of PR3's
  `Docs/roadmap/fixtures/PR3-pano-rooms.tbxp` (path-traced, `standard`) wrote the manifests and the tiles. PF6a
  copied them from app `main` `ad3aa5c45` (2026-10-15; the files as app commit `4ed19a00d` left them).
* **Analysis** (1.2.0, AN3, the wind study): `TruebexSync::MakeWindFixtures` (`wind-fixtures-current`) writes the
  stub's answer for the export of `Docs/roadmap/fixtures/Z0-baseline.tbxp` at 225 degrees, 5 m/s, `suburban`,
  1.5 m, 1000 mm cells, `realizable_ke` (§9: a deterministic stand-in synthesized from the upload, never a solver;
  the platform reads it as a sample of a valid §6.3 result, not as physics).

The folder last changed in app commit `51b5adf01` (AN3: wind and airflow); PF11c copied it from app `main`
`bcdd021f1` (2026-10-24, AN3's merge) with `scripts\sync-contract-fixtures.ps1 -Contract render-jobs`: 169 files
(14 at the top, 155 tiles), every one the app's blob byte for byte (LF, not the app checkout's CRLF), checked by
`server/tests/test_pf6a_render_jobs_1_1.py` (`APP_BLOBS`, and the git tree id of `tiles/`, unchanged since PF6a)
and `server/tests/test_pf11c_render_jobs_1_2.py` without the app repo. To re-copy, run the script again, update
`APP_BLOBS`, `APP_COMMIT`, `APP_FOLDER_COMMIT` there (and `APP_TILES_TREE` if the tiles moved) and the commits here.

The renders' project is PR3's: `project_id` `fd1f65c522298d6fbd318103c6601118`, three saved views (a saved
camera's view id is `CadEntityIds::Derive(project_uid, "Camera/" + lower(name), 0)`, 1.1.0 §6.1): `bedroom`
`ecaf16d70fa5862cbba8f2288b9fd593`, `entry` `8388104cbff98d2dba07fd23c19c83b5`, `living`
`aee49319c0d48a7a953f247b52c948be`. Faces are 512 px, tiles 256 px, levels 256 and 512 (1 + 4 tiles a face),
`app_version` 1.0.0, no `tiles_base` (the platform fills it in 5.5). The wind result's `project_id`
`f08ffe0283418dea8627d42c7908ab88` is `Z0-baseline.tbxp`'s own CL0 project id at `at_seq` 0 (a document never
saved to the cloud, 1.2.0 §6.5.1).

| File | Holds |
|---|---|
| `job-panorama.json` | a §6.1 `panorama` job of the three views at `at_seq` 0, `ops` null; its paths are relative to its own folder (1.1.0): `tbxp` `../../PR3-pano-rooms.tbxp` (the app repo's `Docs/roadmap/fixtures/`), `out_dir` `out` |
| `job-tiles.json` | the `tiles` job after one operation: `project.snapshot_seq` 0, `at_seq` 1, `ops` `ops-tiles.json`, `base_manifest` `out/manifest.json` (the panorama job's output), the nine `changed` ids the operation touched, `out_dir` `out-tiles` |
| `ops-tiles.json` | that operation, a project-log 5.7 body: `server_seq` 1, "Move" (the living room's west wall 300 mm west), `delta_format` `o5/55` |
| `manifest-panorama.json` | the panorama job's §6.2 manifest: 3 views x 6 faces rendered (`full`), 90 tiles; `faces_rendered` 18, `faces_reused` 0, `ms` |
| `manifest-tiles.json` | the tiles job's: `entry` and `living` all six faces `light` (the wall bounds both rooms: CL3's room rule), `bedroom` `w` `changed` (it sees the wall through the door) and `n e s u d` `carried` with the panorama's tiles; 65 new tiles; `faces_rendered` 13, `faces_reused` 5 |
| `tiles/` | the 155 JPEG tiles both manifests name, `<sha256>.jpg` (90 + 65, about 28 KB each) |
| `usage.json` | a 5.6 answer (`by_kind` `tiles` and `panorama`) |
| `.gitignore` | the app's: `out/` and `out-*/` (where a `-mwrender` run of the job files writes) stay out of git |
| `wind-result.json` | the stub's §6.3 `truebex-analysis/1` answer of a `wind` job: 1.2's params, `engine` `truebex-stub` with `image` null, `summary` `max_speed_ms` only, field `pressure_coefficient` (156 faces, the upload's `entities`), grids `speed_ratio`, `velocity` (`components` 3) and `comfort_lawson`, 89 x 72 cells of 1000 mm from `origin_mm` (the centre of cell (0, 0)) at z 1500, and the stub's own `files` map (role names the stub resolves; a worker omits it and the platform fills its own in 5.5) |
| `wind-geometry.bin` | the upload's `geometry`: a binary STL of 156 triangles in metres (the kernel massing, the app's export without the 3D tool: closed, but 12 edges lie on four triangles where its solids touch) |
| `wind-entities.bin` | the upload's `entities`: 16 bytes per triangle, Hi then Lo big-endian, in the STL's order (2 496 bytes) |
| `wind-pressure_coefficient.bin` | the field's float32 values, one per triangle (624 bytes) |
| `wind-speed_ratio.bin` | the `speed_ratio` grid's float32 values, NaN inside the building (25 632 bytes) |
| `wind-velocity.bin` | the `velocity` grid's float32 x, y, z per cell in m/s (76 896 bytes) |
| `wind-comfort_lawson.bin` | the `comfort_lawson` grid's uint8 classes, 255 inside the building (6 408 bytes) |

Not here, because the app publishes none of them: a 5.7 answer, PF6's own two ops files, and PF11's 8-triangle
wind result for its octahedron test shape. They are the platform's own stand-ins in `../../fixtures/render/`.

The platform's tests read the set as it is: `render_helpers.py` (`APP_PROJECT`, `VIEWS`, `MOVED`),
`test_render*.py`, `test_pf6a_*.py`, `test_pf11c_render_jobs_1_2.py` (the wind set), the PF9 / PF10 / PF12 / PF12a
suites, `worker/tests/fake_truebex.py` (the stand-in for `-mwrender`), `src/viewer/selftest.ts`,
`mobile/android/test/`, and `server/scripts/local_analysis_docker.py` (its wind stand-in).
