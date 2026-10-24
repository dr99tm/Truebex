"""Solver runners: the code each analysis image runs (PF11).

The worker wrapper (`worker/truebex_worker.py --mode container`) starts a
kind's image with the job folder mounted at `/job`; the image's entrypoint
(`infra/worker/analysis/run.sh <kind>`) runs

    python3 -m runners.<kind> /job

with `/opt/truebex` on PYTHONPATH. A runner reads `/job/job.json`
(`truebex-analysis-job/1`), runs its engine on `/job/inputs/*` and writes
`/job/out/result.json` (`truebex-analysis/1`, or `truebex-texture/1`) with
every array as `/job/out/<sha256 of its bytes>`; on failure
`/job/out/error.json` `{"code", "message"}` and a non-zero exit.
`/job/out/progress.json` `{"progress": 0..1, "message"}` is read by the
wrapper's heartbeat every 30 s.

| Module      | Engine                                   | Licence of the engine            |
|-------------|------------------------------------------|----------------------------------|
| `wind`      | OpenFOAM v2406, simpleFoam (realizable k-epsilon or k-omega SST) | GPL-3.0, run as a service |
| `energy`    | EnergyPlus                               | BSD-3-Clause                     |
| `acoustics` | our stochastic energy ray tracer         | ours                             |
| `airflow`   | our orifice network on the wind job's Cp (PF11c) | ours                     |
| `texture`   | an open image model (diffusers)           | must allow commercial hosting    |

`common` holds what they share. The package is standard library only (the
texture runner imports torch, diffusers, numpy and Pillow lazily inside its
image) and runs on Python 3.10 (the OpenFOAM and EnergyPlus images are Ubuntu
22.04), so it is imported both as `app.analysis.runners` (the platform's
tests) and as `runners` (the images): imports between modules are relative.
"""
