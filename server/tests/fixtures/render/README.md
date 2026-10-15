# The platform's own render-jobs stand-ins (PF6, PF11)

Not the contract's set: that is the app's own (CL3, render-jobs 1.1.0 §9), copied byte for byte into
`../../contracts/render-jobs/`. These are the files the app publishes no copy of, written by
`server/scripts/make_render_job_fixtures.py` (`--check` compares every file; standard library only). PF6
staged them with the whole set on 2026-10-10; PF6a (2026-10-15) moved them here when CL3's set replaced the
rest. They stay the platform's own until AN3 (analysis, the wind result) and the app publish theirs, after
which those files are re-copied into the contract folder and dropped here. Fixture data, never public copy.

| File | Holds | Read by |
|---|---|---|
| `claim.json` | a 5.7 answer (the job record with `changed` and `params`, the lease, the signed inputs, the output upload; URLs are placeholders) | `test_render.py` (the claim's keys) |
| `ops-empty.json`, `ops-move-wall.json` | the project-log 5.7 bodies PF6's own job files named: none, and one "Move wall" of the project-log fixtures' first wall | nothing since PF6a (the app's `ops-tiles.json` replaced them); kept with their history |
| `wind-result.json`, `wind-*.bin` | an analysis result (§6.3, `truebex-analysis/1`) whose fields name the project-log fixtures' wall ids, and its three little-endian arrays named by SHA-256 | `test_analysis.py`, `tests/fakes/stub_solver/run.py` |

The project id and the wall ids are the project-log fixtures' (`../../contracts/project-log/`).
