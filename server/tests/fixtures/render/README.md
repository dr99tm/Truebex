# The platform's own render-jobs stand-ins (PF6, PF11)

Not the contract's set: that is the app's own (CL3, render-jobs 1.1.0 §9), copied byte for byte into
`../../contracts/render-jobs/`. These are the files the app publishes no copy of, written by
`server/scripts/make_render_job_fixtures.py` (`--check` compares every file; standard library only). PF6
staged them with the whole set on 2026-10-10; PF6a (2026-10-15) moved them here when CL3's set replaced the
rest. AN3 published the app's own wind result with render-jobs 1.2.0 (156 triangles of its export, in
`../../contracts/render-jobs/` since PF11c, 2026-10-24); PF11's stays here for its 8-triangle octahedron test shape,
in 1.2.0's shape (the three pedestrian grids, the four summary keys). Fixture data, never public copy.

| File | Holds | Read by |
|---|---|---|
| `claim.json` | a 5.7 answer (the job record with `changed` and `params`, the lease, the signed inputs, the output upload; URLs are placeholders) | `test_render.py` (the claim's keys) |
| `ops-empty.json`, `ops-move-wall.json` | the project-log 5.7 bodies PF6's own job files named: none, and one "Move wall" of the project-log fixtures' first wall | nothing since PF6a (the app's `ops-tiles.json` replaced them); kept with their history |
| `wind-result.json`, `wind-*.bin` | an analysis result (§6.3, `truebex-analysis/1`, render-jobs 1.2.0's wind shape) whose fields name the project-log fixtures' wall ids, and its five little-endian arrays named by SHA-256 (Cp and ids for 8 triangles, 4 x 4 grids `comfort_lawson`, `speed_ratio`, `velocity`) | `test_analysis.py`, `tests/fakes/stub_solver/run.py` |

The project id and the wall ids are PF4's project-log fixtures' (PF4a re-copied CL1's set over them on 2026-10-15);
`claim.json`'s snapshot SHA-256 and size are those of `../../contracts/project-log/snapshot-0000.tbxp` as it is now.
