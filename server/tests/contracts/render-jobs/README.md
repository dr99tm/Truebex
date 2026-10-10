# Render-jobs contract fixtures (`contracts/render-jobs.md` v1.0.0, §9)

Copied, never edited: the app side is authoritative for these files.

On 2026-10-10 the app repository had no `Docs/roadmap/fixtures/contracts/render-jobs/` folder yet (CL3 creates
it), so PF6 wrote this set to the letter of `render-jobs.md` §5.6, §5.7, §6.1, §6.2 and §6.3 with
`server/scripts/make_render_job_fixtures.py` (deterministic for one Pillow version) and staged it here. CL3
copies the folder into the app repo (or replaces it with its own, after which this folder is re-copied).

| File | Holds |
|---|---|
| `job-panorama.json`, `job-tiles.json` | §6.1 job files against `Docs/roadmap/fixtures/Z0-baseline.tbxp` (paths relative to the app repo) |
| `ops-empty.json`, `ops-move-wall.json` | the operations those job files name (a project-log 5.7 body): none, and one "Move wall" |
| `manifest-panorama.json` | a full set: one view ("Living room"), levels 512 and 1024, six faces rendered |
| `manifest-tiles.json` | the partial update after the wall moved: `n` and `e` rendered (`changed`), four faces carried |
| `tiles/` | the 40 JPEG tiles both manifests name, `<sha256>.jpg`, 512 px, quality 85 (drawn stand-ins) |
| `wind-result.json`, `wind-*.bin` | an analysis result (§6.3) whose fields name the project-log fixtures' wall ids |
| `usage.json`, `claim.json` | a 5.6 answer and a 5.7 answer (URLs are placeholders) |

The project id and the wall ids are the project-log fixtures' (`../project-log/`).
