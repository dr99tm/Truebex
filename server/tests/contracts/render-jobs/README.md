# Render-jobs contract fixtures (`contracts/render-jobs.md` 1.1.0, §9)

Copied, never edited: the app side is authoritative for these files. This README is the platform's own (the
app's folder has none).

The set is the app's own (CL3, the headless render service mode): `TruebexSync::MakeRenderJobFixtures`
(`-mwcl3fixtures`) writes the job files and the operation, and CL3's own `-mwrender` runs of PR3's
`Docs/roadmap/fixtures/PR3-pano-rooms.tbxp` (path-traced, `standard`) wrote the manifests and the tiles. The
folder last changed in app commit `4ed19a00d` (CL3: `cad.Render.LockedSampling`, fixtures re-rendered); PF6a
copied it from app `main` `ad3aa5c45` (2026-10-15, CL3's merge) with
`scripts\sync-contract-fixtures.ps1 -Contract render-jobs`: every file is the app's blob byte for byte (LF, not
the app checkout's CRLF), checked by `server/tests/test_pf6a_render_jobs_1_1.py` without the app repo
(`APP_BLOBS`, and the git tree id of `tiles/`). To re-copy, run the script again, update `APP_BLOBS`,
`APP_TILES_TREE` and the commits there and here.

The project is PR3's: `project_id` `fd1f65c522298d6fbd318103c6601118`, three saved views (a saved camera's view
id is `CadEntityIds::Derive(project_uid, "Camera/" + lower(name), 0)`, 1.1.0 §6.1): `bedroom`
`ecaf16d70fa5862cbba8f2288b9fd593`, `entry` `8388104cbff98d2dba07fd23c19c83b5`, `living`
`aee49319c0d48a7a953f247b52c948be`. Faces are 512 px, tiles 256 px, levels 256 and 512 (1 + 4 tiles a face),
`app_version` 1.0.0, no `tiles_base` (the platform fills it in 5.5).

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

Not here, because the app publishes none of them: a 5.7 answer and PF6's own two ops files, and the analysis
result (`wind-result.json`, `wind-*.bin`, §6.3: AN3's, later). They are the platform's own stand-ins in
`../../fixtures/render/`.

The platform's tests read the set as it is: `render_helpers.py` (`APP_PROJECT`, `VIEWS`, `MOVED`),
`test_render*.py`, `test_pf6a_*.py`, the PF9 / PF10 / PF12 / PF12a suites, `worker/tests/fake_truebex.py` (the
stand-in for `-mwrender`), `src/viewer/selftest.ts` and `mobile/android/test/`.
