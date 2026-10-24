"""A stand-in for the docker CLI: run an analysis image's runner as a local process (PF11c).

    worker.toml:  mode = "container"
                  docker = "X:/…/server/scripts/local_analysis_docker.py"

The worker wrapper (`worker/truebex_worker.py --mode container`) calls
`docker run [flags] -v <job dir>:/job truebex-analysis-<kind>:<tag>`; this
script takes that call and runs `python -m runners.<kind> <job dir>` with
server/app/analysis on PYTHONPATH and TRUEBEX_IMAGE / TRUEBEX_KIND set as the
image would (no container, no network limit: for a PC without Docker, never a
production worker). `docker kill <name>` does nothing.

No OpenFOAM here: with TRUEBEX_WIND_STAND_IN=<folder> (the app's
tests/contracts/render-jobs/), a `wind` job is answered with that folder's
wind-result.json and arrays instead (the app's stub answer for its export of
Z0-baseline.tbxp at 225 degrees): the job's own kind, project, sequence and
params, engine `truebex-stand-in`, a summary read from the arrays. Only a job
on that export (156 triangles) with the fixture's params is answered; any
other is bad_input. That is a sample of a valid §6.3 result, never physics.
"""

import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

RUNNERS = Path(__file__).resolve().parents[1] / "app" / "analysis"
_IMAGE = re.compile(r"(?:^|/)truebex-analysis-([a-z]+)(?::[\w.-]+)?$")


def fail(out: Path, code: str, message: str, exit_code: int) -> int:
    out.mkdir(parents=True, exist_ok=True)
    (out / "error.json").write_text(json.dumps({"code": code, "message": message}), encoding="utf-8")
    print(f"failed: {code}: {message}", file=sys.stderr)
    return exit_code


def wind_stand_in(job_dir: Path, folder: Path, image: str) -> int:
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    out = job_dir / "out"
    result = json.loads((folder / "wind-result.json").read_text(encoding="utf-8"))
    geometry = (job_dir / "inputs" / "geometry").read_bytes()
    (n,) = struct.unpack_from("<I", geometry, 80)
    if n != result["fields"][0]["count"]:
        return fail(out, "bad_input", f"the wind stand-in answers the app's export only ({result['fields'][0]['count']} triangles, not {n})", 2)
    differs = sorted(k for k, v in result["params"].items() if job["params"].get(k) != v)
    if differs:
        return fail(out, "bad_input", f"the wind stand-in answers the fixture's params only (this job differs in {', '.join(differs)})", 2)
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for sha, entry in result.pop("files").items():
        data = (folder / entry["url"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha
        (out / sha).write_bytes(data)
        files[entry["url"]] = data
    velocity = struct.unpack(f"<{len(files['wind-velocity.bin']) // 4}f", files["wind-velocity.bin"])
    speeds = [math.sqrt(velocity[k] ** 2 + velocity[k + 1] ** 2 + velocity[k + 2] ** 2) for k in range(0, len(velocity), 3)
              if not math.isnan(velocity[k])]
    speed = float(job["params"]["speed_ms"])
    result.update(kind=job["kind"], project_id=job.get("project_id"), at_seq=job.get("at_seq", 0), params=job["params"])
    result["engine"] = {"name": "truebex-stand-in", "version": "1", "image": f"{image} (local stand-in)"}
    result["summary"] = {"max_speed_ms": round(max(speeds), 6), "max_speed_ratio": round(max(speeds) / speed, 6), "iterations": 0, "residual": 0.0}
    (out / "result.json").write_text(json.dumps(result), encoding="utf-8")
    print("wind stand-in: the app's fixture answer for this job")
    return 0


def main(args: list[str]) -> int:
    if not args or args[0] != "run":
        return 0  # kill, rm, …: nothing runs in a container here
    mount = args[args.index("-v") + 1]
    job_dir = Path(mount.rsplit(":/job", 1)[0])
    image = args[-1]
    m = _IMAGE.search(image)
    if m is None:
        return fail(job_dir / "out", "engine_error", f"{image} is not a truebex-analysis image", 3)
    kind = m.group(1)
    stand_in = os.environ.get("TRUEBEX_WIND_STAND_IN")
    if kind == "wind" and stand_in:
        return wind_stand_in(job_dir, Path(stand_in), image)
    env = {**os.environ, "PYTHONPATH": str(RUNNERS), "TRUEBEX_IMAGE": image, "TRUEBEX_KIND": kind, "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, "-m", f"runners.{kind}", str(job_dir)], env=env, cwd=str(job_dir)).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
