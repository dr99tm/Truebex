# Analysis runner images (PF11)

Heavy analyses run as Linux containers on the platform's CPU workers (`cpu-8`; GD3: 8 vCPU / 16 GB, Docker).
The worker wrapper (`worker/truebex_worker.py --mode container`, settings in `worker/worker.analysis.toml.example`)
claims a job, writes `<job>/job.json` (`truebex-analysis-job/1`) with the inputs under `<job>/inputs/`, and runs

    docker run --rm --network none --cpus <n> --memory <m> --pids-limit 512 --cap-drop ALL \
      --security-opt no-new-privileges --user 1000:1000 -v <job>:/job truebex-analysis-<kind>:<tag>

The image's entrypoint (`run.sh <kind>`) runs `python3 -m runners.<kind> /job` (`server/app/analysis/runners/`),
which writes `/job/out/result.json` (`truebex-analysis/1`, render-jobs §6.3) with every array as
`/job/out/<sha256>`, or `/job/out/error.json` and a non-zero exit. No network, capped CPU and memory, a non-root
user, only the job's own folder: a job never sees another account's files.

| Image | Engine | Licence | Notes |
|---|---|---|---|
| `truebex-analysis-wind` | OpenFOAM v2406 (`opencfd/openfoam-default:2406`), simpleFoam, k-epsilon | GPL-3.0 | run as a service on the workers, never shipped with the app (the app keeps its own coarse estimate, AN3) |
| `truebex-analysis-energy` | EnergyPlus 24.2 from the official release archive | BSD-3-Clause | the build needs the archive's SHA-256 (`-BuildArg "ENERGYPLUS_SHA256=…"`; confirm the asset at writing time) |
| `truebex-analysis-acoustics` | our own stochastic energy ray tracer (`runners/acoustics.py`) | ours | standard library Python |
| `truebex-analysis-texture` | an open image model (diffusers), seamless by circular padding | the model's licence must allow commercial hosting | `gpu-ai`, `--gpus all`; the platform keeps the kind off until `AI_TEXTURE_ENABLED` |

Build (Docker Desktop with Linux containers on Windows, or Docker on Linux):

    powershell -NoProfile -ExecutionPolicy Bypass -File infra\worker\analysis\wind\build.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File infra\worker\analysis\build.ps1 -Kind energy -BuildArg "ENERGYPLUS_SHA256=<sha>"
    infra/worker/analysis/build.sh acoustics

Images are rebuilt per release and pushed to the private registry GD3 names; the tag the job's profile names
(`server/app/analysis/profiles.json`, `image`) is the one the wrapper runs unless `images` in its settings says
otherwise. Results are reports, never certificates: no number is published before GD2's validation cases pass.
