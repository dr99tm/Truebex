"""A stub solver image (PF11 tests): what an analysis image does, without the solver.

    python run.py <job dir>        (an image runs it with /job)

Reads `<job>/job.json` (`truebex-analysis-job/1`), checks its inputs arrived,
reports progress, and writes the platform's stand-in wind result
(tests/fixtures/render/wind-result.json, `truebex-analysis/1` in render-jobs
1.2.0's wind shape, for the 8-triangle test shape) for this job into `<job>/out/`
with its arrays named by SHA-256. `params.speed_ms` 13 makes it fail the way
a solver does (exit 3 with `out/error.json`).
"""

import hashlib
import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "render"


def main(job_dir: Path) -> int:
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    out = job_dir / "out"
    out.mkdir(exist_ok=True)
    (out / "progress.json").write_text(json.dumps({"progress": 0.5, "message": "solving"}), encoding="utf-8")
    for name, path in job["inputs"].items():
        if not (job_dir / "inputs" / name).is_file() or not path.startswith("/job/inputs/"):
            (out / "error.json").write_text(json.dumps({"code": "bad_input", "message": f"{name} is missing"}), encoding="utf-8")
            return 2
    if (job.get("params") or {}).get("speed_ms") == 13:
        (out / "error.json").write_text(json.dumps({"code": "engine_error", "message": "the solver diverged"}), encoding="utf-8")
        return 3
    result = json.loads((FIXTURES / "wind-result.json").read_text(encoding="utf-8"))
    result.update(kind=job["kind"], project_id=job["project_id"], at_seq=job["at_seq"], params=job["params"])
    result["engine"] = {"name": "stub-solver", "version": "1", "image": "sha256:" + "0" * 64}
    for path in FIXTURES.glob("wind-*.bin"):
        data = path.read_bytes()
        (out / hashlib.sha256(data).hexdigest()).write_bytes(data)
    (out / "result.json").write_text(json.dumps(result), encoding="utf-8")
    print("stub solver: mesh, solve, export done")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "/job")))
