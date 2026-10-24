"""What every runner shares: the job file, the output files, failures (PF11).

A runner is a function `run(job)` that writes its outputs into `job.out_dir`;
`main(run)` loads `/job/job.json`, calls it, and turns an exception into
`out/error.json` and an exit code:

| Exception            | error.json code | exit |
|----------------------|-----------------|------|
| `BadInput`           | bad_input       | 2    |
| `EngineError`, other | engine_error    | 3    |
| `SolverTimeout`      | timeout         | 4    |
| `OutOfMemory`, `MemoryError` | out_of_memory | 5 |

Arrays are little-endian and named by the SHA-256 of their bytes
(`write_array`). Standard library only; Python 3.10 or later.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import threading
import traceback
from collections import deque
from pathlib import Path
from typing import Callable, Iterable

JOB_SCHEMA = "truebex-analysis-job/1"
RESULT_SCHEMA = "truebex-analysis/1"
TEXTURE_SCHEMA = "truebex-texture/1"
DEFAULT_JOB_DIR = "/job"
EXIT_CODES = {"bad_input": 2, "engine_error": 3, "timeout": 4, "out_of_memory": 5}
_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
_F32_MAX = 3.4028234663852886e38


# --- failures ---------------------------------------------------------------------------------


class RunnerError(Exception):
    """A failure with the error.json code it reports."""

    code = "engine_error"


class BadInput(RunnerError):
    """The job's inputs or params cannot be run (not retried)."""

    code = "bad_input"


class EngineError(RunnerError):
    """The engine failed on inputs that looked valid (retried)."""

    code = "engine_error"


class SolverTimeout(RunnerError):
    code = "timeout"


class OutOfMemory(RunnerError):
    code = "out_of_memory"


# --- the job ----------------------------------------------------------------------------------


def local_path(job_dir: Path, path: str) -> Path:
    """A job file path (`/job/inputs/x`) inside `job_dir`, which is `/job` in an
    image and a temporary folder in the tests."""
    if path == DEFAULT_JOB_DIR or path.startswith(DEFAULT_JOB_DIR + "/"):
        rest = [p for p in path[len(DEFAULT_JOB_DIR):].split("/") if p]
        return Path(job_dir).joinpath(*rest)
    p = Path(path)
    return p if p.is_absolute() else Path(job_dir) / p


class Job:
    """`truebex-analysis-job/1` with its paths resolved inside the job folder."""

    def __init__(self, data: dict, job_dir: Path) -> None:
        if not isinstance(data, dict) or data.get("schema") != JOB_SCHEMA:
            raise BadInput(f"job.json is not {JOB_SCHEMA}")
        self.data = data
        self.dir = Path(job_dir)
        self.job_id = str(data.get("job_id") or "")
        self.kind = str(data.get("kind") or "")
        self.project_id = data.get("project_id")
        self.at_seq = data.get("at_seq", 0)
        self.params = data.get("params") or {}
        self.profile = data.get("profile") or {}
        raw_inputs = data.get("inputs") or {}
        if not isinstance(raw_inputs, dict):
            raise BadInput("job.json inputs is not an object")
        self.inputs = {str(k): local_path(self.dir, str(v)) for k, v in raw_inputs.items()}
        self.out_dir = local_path(self.dir, str(data.get("out_dir") or DEFAULT_JOB_DIR + "/out"))

    def input(self, name: str, required: bool = True) -> Path | None:
        """The input file's path; BadInput when a required (or declared) one is missing."""
        path = self.inputs.get(name)
        if path is None:
            if required:
                raise BadInput(f"the job has no '{name}' input file")
            return None
        if not path.is_file():
            raise BadInput(f"the '{name}' input file is missing")
        return path


def load_job(job_dir: str | Path = DEFAULT_JOB_DIR) -> Job:
    job_dir = Path(job_dir)
    try:
        data = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BadInput(f"no job.json in {job_dir}") from None
    except (OSError, ValueError) as exc:
        raise BadInput(f"job.json cannot be read: {exc}") from None
    return Job(data, job_dir)


def read_json(path: Path, what: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise BadInput(f"the {what} file is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise BadInput(f"the {what} file is not a JSON object")
    return data


def is_hex32(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX32.match(value))


# --- output files -----------------------------------------------------------------------------


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_array(out_dir: Path, data: bytes) -> str:
    """Write `out_dir/<sha256>` (once) and return the hex digest."""
    sha = hashlib.sha256(data).hexdigest()
    path = Path(out_dir) / sha
    if not path.is_file() or path.stat().st_size != len(data):
        _atomic_write(path, data)
    return sha


def _f32(value: float) -> float:
    v = float(value)
    if v > _F32_MAX:
        return math.inf
    if v < -_F32_MAX:
        return -math.inf
    return v


def pack_f32(values: Iterable[float]) -> bytes:
    """float32, little-endian (NaN kept; beyond float32's range becomes ±inf)."""
    vals = [_f32(v) for v in values]
    return struct.pack(f"<{len(vals)}f", *vals)


def unpack_f32(data: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(data) // 4}f", data))


def pack_u8(values: Iterable[int]) -> bytes:
    return bytes(max(0, min(255, int(v))) for v in values)


def progress(out_dir: Path, value: float, message: str) -> None:
    """`out/progress.json`, read by the wrapper's heartbeat (never fails the run)."""
    try:
        body = {"progress": round(min(max(float(value), 0.0), 1.0), 4), "message": str(message)[:200]}
        _atomic_write(Path(out_dir) / "progress.json", json.dumps(body).encode("utf-8"))
    except OSError:
        pass
    print(f"[progress {value:.2f}] {message}", flush=True)


def fail(out_dir: Path, code: str, message: str) -> int:
    """Write `out/error.json` and return the exit code for it."""
    code = code if code in EXIT_CODES else "engine_error"
    message = str(message or code)[:2000]
    try:
        _atomic_write(Path(out_dir) / "error.json", json.dumps({"code": code, "message": message}).encode("utf-8"))
    except OSError as exc:
        print(f"error.json could not be written: {exc}", file=sys.stderr)
    print(f"failed: {code}: {message}", file=sys.stderr, flush=True)
    return EXIT_CODES[code]


def write_result(out_dir: Path, result: dict) -> Path:
    try:
        body = json.dumps(result, allow_nan=False, separators=(",", ":"))
    except ValueError:
        raise EngineError("the result holds a non-finite number") from None
    path = Path(out_dir) / "result.json"
    _atomic_write(path, body.encode("utf-8"))
    return path


def engine(name: str, version: str, kind: str | None = None) -> dict:
    """The result's `engine`; `image` is TRUEBEX_IMAGE (set by the Dockerfile)."""
    kind = kind or os.environ.get("TRUEBEX_KIND") or "analysis"
    image = os.environ.get("TRUEBEX_IMAGE") or f"truebex-analysis-{kind}:1"
    return {"name": str(name), "version": str(version) or "unknown", "image": image}


def clean_summary(summary: dict, digits: int = 6) -> dict:
    """Numbers only (bool as 0/1), finite, rounded; non-finite values are left out."""
    out: dict = {}
    for key, value in summary.items():
        if isinstance(value, bool):
            out[key] = int(value)
        elif isinstance(value, int):
            out[key] = value
        elif isinstance(value, float) and math.isfinite(value):
            out[key] = round(value, digits)
        elif isinstance(value, str):
            out[key] = value
    return out


# --- running an engine ------------------------------------------------------------------------


def _cgroup_cpus() -> float | None:
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        return None if quota == "max" else int(quota) / int(period)
    except (OSError, ValueError):
        pass
    try:
        quota = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
        period = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
        return None if quota <= 0 else quota / period
    except (OSError, ValueError):
        return None


def available_cores() -> int:
    """Processes for a parallel run: os.cpu_count() // 2 (hyper-threads), at
    most the container's CPU quota (`docker run --cpus`), at least 1;
    TRUEBEX_CORES overrides."""
    env = os.environ.get("TRUEBEX_CORES", "")
    if env.isdigit() and int(env) > 0:
        return int(env)
    n = max(1, (os.cpu_count() or 2) // 2)
    quota = _cgroup_cpus()
    if quota:
        n = min(n, max(1, int(quota)))
    return n


def run_command(
    cmd: list[str],
    cwd: Path,
    log_path: Path | None = None,
    on_line: Callable[[str], None] | None = None,
    env: dict | None = None,
    timeout: float | None = None,
    echo: bool = True,
) -> list[str]:
    """Run `cmd`, streaming its output to `log_path`, stdout and `on_line`.

    Returns the last 200 lines. A missing executable or a non-zero exit is an
    EngineError; SIGKILL (exit -9/137: the container's OOM killer) is
    OutOfMemory; `timeout` seconds is SolverTimeout.
    """
    name = Path(cmd[0]).name
    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    except FileNotFoundError:
        raise EngineError(f"{name} is not installed in this image") from None
    timed_out = threading.Event()
    timer = None
    if timeout:
        def _kill() -> None:
            timed_out.set()
            proc.kill()
        timer = threading.Timer(timeout, _kill)
        timer.daemon = True
        timer.start()
    tail: deque = deque(maxlen=200)
    log = open(log_path, "ab") if log_path else None
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            if log:
                log.write(raw)
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            tail.append(line)
            if echo:
                print(line, flush=False)
            if on_line:
                on_line(line)
        code = proc.wait()
    finally:
        if timer:
            timer.cancel()
        if log:
            log.close()
        sys.stdout.flush()
    if timed_out.is_set():
        raise SolverTimeout(f"{name} ran longer than {int(timeout or 0)} s")
    if code in (-9, 137):
        raise OutOfMemory(f"{name} was killed (SIGKILL): most likely out of memory")
    if code != 0:
        last = " | ".join(line.strip() for line in list(tail)[-6:] if line.strip())
        raise EngineError(f"{name} failed (exit {code}): {last[-600:]}")
    return list(tail)


# --- entry point ------------------------------------------------------------------------------


def main(run: Callable[[Job], object], argv: list[str] | None = None) -> int:
    """`python3 -m runners.<kind> [/job]`: run, or report the failure in error.json."""
    args = list(sys.argv[1:] if argv is None else argv)
    job_dir = Path(args[0]) if args else Path(DEFAULT_JOB_DIR)
    out_dir = job_dir / "out"
    try:
        job = load_job(job_dir)
        out_dir = job.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        run(job)
    except RunnerError as exc:
        if exc.code == "engine_error":
            traceback.print_exc()
        return fail(out_dir, exc.code, str(exc))
    except MemoryError:
        return fail(out_dir, "out_of_memory", "the runner ran out of memory")
    except Exception as exc:  # noqa: BLE001 - every failure becomes error.json
        traceback.print_exc()
        return fail(out_dir, "engine_error", f"{type(exc).__name__}: {exc}")
    return 0


# --- result parts -----------------------------------------------------------------------------


def entity_bytes(ids: list[str]) -> bytes:
    """16-byte FCadEntityIds (Hi then Lo, big-endian = the 32-hex text's bytes)."""
    return b"".join(bytes.fromhex(i.lower()) for i in ids)


def field(out_dir: Path, name: str, unit: str, on: str, values: list[float], *, entities: bytes | None = None,
          keys: list[str] | None = None) -> dict:
    """A §6.3 field (float32), its values (and entity ids) written as arrays."""
    out = {"name": name, "unit": unit, "on": on, "count": len(values), "values": write_array(out_dir, pack_f32(values))}
    if entities is not None:
        if len(entities) != 16 * len(values):
            raise EngineError(f"{name}: {len(entities) // 16} entity ids for {len(values)} values")
        out["entities"] = write_array(out_dir, entities)
    if keys is not None:
        out["keys"] = list(keys)
    return out


def space_ids(names: list[str]) -> bytes | None:
    """Entity ids for spaces whose names are 32-hex ids (AN2 / AN4 name them so)."""
    return entity_bytes(names) if names and all(is_hex32(n) for n in names) else None


def grid(out_dir: Path, name: str, unit: str, origin_mm: list[float], cell_mm: float, nx: int, ny: int,
         values: list, dtype: str = "float32", components: int = 1) -> dict:
    """A §6.3 grid: `origin_mm` the centre of cell (0, 0), values row by row from
    j = 0 (the south row), i fastest, `components` interleaved per cell."""
    if len(values) != nx * ny * components:
        raise EngineError(f"{name}: {len(values)} values for {nx} x {ny} cells of {components}")
    data = pack_u8(values) if dtype == "uint8" else pack_f32(values)
    out = {"name": name, "unit": unit, "origin_mm": [round(float(v), 1) for v in origin_mm], "cell_mm": float(cell_mm),
           "nx": nx, "ny": ny, "values": write_array(out_dir, data)}
    if components != 1:
        out["components"] = components
    if dtype != ("uint8" if unit == "class" else "float32"):
        out["dtype"] = dtype
    return out


def result(job: Job, engine_info: dict, summary: dict, fields: list[dict], grids: list[dict], report: str | None = None) -> dict:
    return {
        "schema": RESULT_SCHEMA, "kind": job.kind, "project_id": job.project_id, "at_seq": job.at_seq, "params": job.params,
        "engine": engine_info, "summary": clean_summary(summary), "fields": fields, "grids": grids, "report": report,
    }
