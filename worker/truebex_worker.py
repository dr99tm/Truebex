"""The Truebex render worker: claims render jobs and runs the app headless on them.

    py -3.12 worker\\truebex_worker.py --config worker.toml
    py -3.12 worker\\truebex_worker.py --config worker.toml --app worker\\tests\\fake_truebex.py --once

For each job (contract render-jobs 1.1.0, 5.7-5.10): claim (a long-poll of up
to 20 s) -> download the snapshot, the operations and the base manifest from
the claim's signed URLs, checking each SHA-256 -> write the job file (§6.1,
with `project.snapshot_seq`, the sequence the snapshot stands at) -> run
`Truebex.exe -mwrender=<job.json>` (CL3) with no window, sending a heartbeat
every 30 s from a thread and killing the app when the platform answers
`cancel` or `lease_lost` -> upload `out_dir/tiles/*` (and a pack's files)
through the job-output upload the claim opened (share-bundle §5, 8 MiB parts,
resumable) -> complete with the measured wall time, or fail with the code the
app wrote in `out_dir/error.json`, else the code its exit code stands for
(5.10 per code: 2 bad_input, 3 doc_too_new, 4 render_crash, 5 out_of_memory,
6 timeout, 7 engine_error; any other render_crash), and the last 64 KiB of
its log.

`--mode container` (PF11) runs analysis jobs instead: the job file
`truebex-analysis-job/1` goes to `<work>/job.json` with the inputs under
`<work>/inputs/`, and the kind's solver image runs as
`docker run --rm --network none --cpus <n> --memory <m> --user <uid:gid>
-v <work>:/job <image>`; the image reads `/job/job.json`, writes
`/job/out/result.json` (`truebex-analysis/1`, contract §6.3) and its arrays
named by SHA-256, and the wrapper uploads them and completes with the
measured wall time (charged at the token's class, `cpu-8`).

Network errors and 408, 429, 500, 502, 503, 504 and 530 are retried with
backoff 1, 2, 4 ... 60 s (±20 %), honouring Retry-After (§8); a revoked token
stops the worker. Ctrl+C stops it at once, even mid claim (PF6b): the claim
waits on a helper thread, so its connection closes with the process and the
platform's long poll takes no job for a worker that is gone. Standard library
only (Python 3.12), so the worker image needs nothing else. Config:
worker.toml (see worker.toml.example).
"""

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

CONTRACT = "render-jobs/1.2"
UPLOADS = "share-bundle/1.0"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504, 530}
NOT_RETRYABLE = {"bad_input", "doc_too_new"}
FAIL_CODES = {"bad_input", "render_crash", "out_of_memory", "timeout", "engine_error", "doc_too_new"}
# -mwrender's exit codes (render-jobs 1.1.0, 5.10 per code): the failure an exit
# means when the app wrote no out_dir/error.json. 0 is success.
EXIT_CODES = {2: "bad_input", 3: "doc_too_new", 4: "render_crash", 5: "out_of_memory", 6: "timeout", 7: "engine_error"}
LOG_TAIL = 64 * 1024
UPLOAD_BATCH = 500
EXIT_REVOKED = 3


@dataclass
class Config:
    api: str
    token: str
    worker_id: str
    kinds: list[str] = field(default_factory=lambda: ["panorama", "tiles", "pack"])
    worker_class: str = "gpu-std"
    app: str = r"C:\Program Files\Truebex\Truebex.exe"
    work_dir: str = "jobs"
    app_version: str = "1.0.0"
    doc_version_max: int = 38
    heartbeat_s: float = 30.0
    job_timeout_s: float = 3600.0
    wait_s: float = 20.0
    face_px: int = 2048
    tile_px: int = 512
    jpeg_quality: int = 85
    keep_work: bool = False
    # PF11: "app" (render jobs, the packaged app) or "container" (analysis
    # jobs, a solver image per kind). `docker` may be a .py stand-in (tests).
    mode: str = "app"
    docker: str = "docker"
    images: dict = field(default_factory=dict)
    cpus: float = 4.0
    memory: str = "12g"
    container_user: str = "1000:1000"
    pids_limit: int = 512

    @classmethod
    def load(cls, path: str | Path, **overrides) -> "Config":
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        raw = {("worker_class" if k == "class" else k): v for k, v in raw.items()}
        raw.update({k: v for k, v in overrides.items() if v is not None})
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


# --- HTTP -----------------------------------------------------------------------------------


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes

    def json(self):
        return json.loads(self.body.decode("utf-8")) if self.body else None


class Transport:
    """urllib, so the worker needs no third-party package."""

    def request(self, method: str, url: str, headers: dict, body: bytes | None, timeout: float) -> Response:
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return Response(res.status, {k.lower(): v for k, v in res.headers.items()}, res.read())
        except urllib.error.HTTPError as err:
            return Response(err.code, {k.lower(): v for k, v in (err.headers or {}).items()}, err.read() or b"")


def interruptible(call):
    """Run `call` on a helper thread and wait for it in short slices (PF6b).

    On Windows a blocking socket read ignores Ctrl+C until it returns: a worker
    stopped mid claim stayed connected until the platform answered (measured:
    12 s after Ctrl+C, with the answer), and an answer that was a job went to a
    worker about to exit, so the job lost an attempt to the 120 s lease. Here
    Ctrl+C raises within a slice; the process then exits and the OS closes the
    connection, which the platform's claim sees before it takes a job."""
    box: dict = {}

    def run() -> None:
        try:
            box["value"] = call()
        except BaseException as exc:  # noqa: BLE001 - raised again in the caller
            box["error"] = exc

    helper = threading.Thread(target=run, name="claim", daemon=True)
    helper.start()
    while helper.is_alive():
        helper.join(0.25)
    if "error" in box:
        raise box["error"]
    return box["value"]


class HttpError(Exception):
    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(f"{status} {code}: {detail}")
        self.status = status
        self.code = code
        self.detail = detail


class Api:
    def __init__(self, cfg: Config, transport: Transport | None = None, sleep=time.sleep, log=None) -> None:
        self.cfg = cfg
        self.base = cfg.api.rstrip("/")
        self.transport = transport or Transport()
        self.sleep = sleep
        self.log = log or (lambda msg: print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True))

    def call(
        self, method: str, path: str, *, json_body=None, data: bytes | None = None, headers: dict | None = None,
        contract: str | None = CONTRACT, auth: bool = True, timeout: float = 60.0, retries: int = 8,
    ) -> Response:
        url = path if path.startswith(("http://", "https://")) else f"{self.base}{path}"
        h = dict(headers or {})
        if contract:
            h["X-Truebex-Contract"] = contract
        if auth:
            h["Authorization"] = f"Bearer {self.cfg.token}"
        body = data
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            h["Content-Type"] = "application/json"
        delay = 1.0
        for attempt in range(retries + 1):
            try:
                res = self.transport.request(method, url, h, body, timeout)
            except (OSError, urllib.error.URLError) as exc:
                if attempt == retries:
                    raise HttpError(0, "network", str(exc)) from exc
                self.log(f"network error ({exc}); retrying in {delay:.0f} s")
                self._wait(delay)
                delay = min(delay * 2, 60.0)
                continue
            if res.status < 400:
                return res
            if res.status in RETRY_STATUSES and attempt < retries:
                after = res.headers.get("retry-after")
                self._wait(float(after) if after and after.isdigit() else delay)
                delay = min(delay * 2, 60.0)
                continue
            try:
                err = res.json() or {}
            except ValueError:
                err = {}
            raise HttpError(res.status, err.get("code") or f"http_{res.status}", str(err.get("detail") or res.body[:200]))
        raise HttpError(0, "network", "gave up")  # pragma: no cover

    def _wait(self, seconds: float) -> None:
        self.sleep(seconds * random.uniform(0.8, 1.2))

    # --- 5.7-5.10 ---

    def claim(self, wait_s: float) -> dict | None:
        body = {
            "worker_id": self.cfg.worker_id, "kinds": list(self.cfg.kinds), "app_version": self.cfg.app_version,
            "doc_version_max": self.cfg.doc_version_max, "wait_s": wait_s,
        }
        res = interruptible(lambda: self.call("POST", "/workers/claim", timeout=wait_s + 30, json_body=body))
        return None if res.status == 204 else res.json()

    def heartbeat(self, job_id: str, lease_id: str, progress: float, message: str) -> dict:
        return self.call(
            "POST", f"/workers/jobs/{job_id}/heartbeat", retries=2,
            json_body={"lease_id": lease_id, "progress": progress, "message": message[:200]},
        ).json()

    def complete(self, job_id: str, lease_id: str, output: dict, wall_s: float, render_log) -> dict:
        body = {"lease_id": lease_id, "output": output, "usage": {"wall_s": round(wall_s, 3), "class": self.cfg.worker_class}}
        if render_log is not None:
            body["render_log"] = render_log
        return self.call("POST", f"/workers/jobs/{job_id}/complete", json_body=body, timeout=300).json()

    def fail(self, job_id: str, lease_id: str, code: str, message: str, retryable: bool, log_tail: str) -> dict:
        return self.call(
            "POST", f"/workers/jobs/{job_id}/fail",
            json_body={"lease_id": lease_id, "code": code, "message": message[:2000], "retryable": retryable, "log_tail": log_tail[-LOG_TAIL:]},
        ).json()

    # --- inputs and outputs ---

    def download(self, url: str, dest: Path, sha256: str | None = None) -> Path:
        res = self.call("GET", url, contract=None, auth=False, timeout=600)
        if sha256 and hashlib.sha256(res.body).hexdigest() != sha256:
            raise InputError(f"{dest.name} did not arrive intact (SHA-256 mismatch)")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(res.body)
        return dest

    def upload(self, upload_id: str, files: list[Path], content_types: dict[str, str]) -> int:
        """Declare `files` into the claim's job-output session and send what is missing."""
        by_sha: dict[str, Path] = {}
        for path in files:
            by_sha.setdefault(sha256_file(path), path)
        shas = list(by_sha)
        sent = 0
        for i in range(0, len(shas), UPLOAD_BATCH):
            batch = shas[i : i + UPLOAD_BATCH]
            declared = [
                {"sha256": s, "bytes": by_sha[s].stat().st_size, "content_type": content_types.get(s, "image/jpeg")}
                for s in batch
            ]
            opened = self.call(
                "POST", "/uploads", contract=UPLOADS,
                json_body={"purpose": "job-output", "upload_id": upload_id, "files": declared},
            ).json()
            part = int(opened["part_bytes"])
            for state in opened["files"]:
                if state["state"] in ("present", "complete"):
                    continue
                data = by_sha[state["sha256"]].read_bytes()
                for n in range(state["parts"]):
                    if n in state.get("received", []):
                        continue
                    chunk = data[n * part : (n + 1) * part]
                    self.call(
                        "PUT", f"/uploads/{upload_id}/files/{state['sha256']}/parts/{n}", data=chunk, contract=UPLOADS,
                        headers={"Content-Type": "application/octet-stream", "X-Part-Sha256": hashlib.sha256(chunk).hexdigest()},
                    )
                sent += 1
        return sent


class InputError(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


# --- the heartbeat thread ------------------------------------------------------------------


class Heartbeat(threading.Thread):
    """Every `heartbeat_s`: extend the lease, report progress (from the app's
    optional `out_dir/progress.json`), stop the app on cancel or a lost lease."""

    def __init__(self, api: Api, job_id: str, lease_id: str, out_dir: Path, interval: float) -> None:
        super().__init__(daemon=True)
        self.api, self.job_id, self.lease_id, self.out_dir, self.interval = api, job_id, lease_id, out_dir, interval
        self.stopped = threading.Event()
        self.cancelled = False
        self.lost = False
        self.proc: subprocess.Popen | None = None
        # Container mode: stopping the docker client does not stop the container.
        self.on_kill = None

    def progress(self) -> tuple[float, str]:
        try:
            p = json.loads((self.out_dir / "progress.json").read_text(encoding="utf-8"))
            return float(p.get("progress", 0.1)), str(p.get("message", "rendering"))
        except (OSError, ValueError, TypeError):
            return 0.1, "rendering"

    def beat(self) -> None:
        progress, message = self.progress()
        try:
            res = self.api.heartbeat(self.job_id, self.lease_id, min(max(progress, 0.0), 1.0), message)
        except HttpError as err:
            if err.status in (401, 404, 409):
                self.lost = True
                self.kill()
            return
        if res.get("cancel"):
            self.cancelled = True
            self.kill()

    def kill(self) -> None:
        if self.on_kill is not None:
            self.on_kill()
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()

    def run(self) -> None:
        while not self.stopped.wait(self.interval):
            self.beat()


# --- one job ----------------------------------------------------------------------------------


class Runner:
    def __init__(self, cfg: Config, api: Api | None = None) -> None:
        self.cfg = cfg
        self.api = api or Api(cfg)
        self.log = self.api.log

    def job_file(self, c: dict, work: Path, inputs: dict) -> dict:
        """§6.1 as render-jobs 1.1.0 has it. Paths are absolute (1.1.0 resolves
        only relative ones against the job file's folder); `levels` is left
        to the app (`face_px` halved down to `tile_px`)."""
        job = c["job"]
        project = {
            "tbxp": inputs.get("tbxp"),
            "tbxpack": inputs.get("tbxpack"),
            "ops": inputs.get("ops"),
            "at_seq": job["at_seq"],
        }
        snap = (c.get("inputs") or {}).get("snapshot")
        if snap and snap.get("at_seq") is not None:
            # The sequence the snapshot stands at: the operations file starts after it.
            project["snapshot_seq"] = snap["at_seq"]
        project["project_id"] = job.get("project_id")  # the manifest's project_id
        out = {
            "schema": "truebex-render-job/1",
            "job_id": job["job_id"],
            "kind": job["kind"],
            "quality": job.get("quality") or "standard",
            "seed": 1,
            "project": project,
            "views": job.get("views") or [],
            "changed": job.get("changed") or [],
            "base_manifest": inputs.get("base_manifest"),
            "face_px": self.cfg.face_px,
            "tile_px": self.cfg.tile_px,
            "jpeg_quality": self.cfg.jpeg_quality,
            "out_dir": (work / "out").resolve().as_posix(),
        }
        if job["kind"] == "pack":
            out["params"] = {"items": list((job.get("params") or {}).get("items") or [])}
        return out

    def failure(self, code: int | None, out: Path) -> tuple[str, str]:
        """The 5.10 code and message of a run that did not exit 0: the code
        out_dir/error.json names, else the one the exit code stands for (any
        other non-zero exit: render_crash; stopped after job_timeout_s: timeout)."""
        try:
            err = json.loads((out / "error.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            err = None
        err = err if isinstance(err, dict) else {}
        if code is None:
            fallback, said = "timeout", f"stopped after {self.cfg.job_timeout_s:g} s (job_timeout_s)"
        else:
            fallback = EXIT_CODES.get(code, "render_crash")
            said = f"exit {code} " + ("with out_dir/error.json" if err else "without out_dir/error.json") + f" ({fallback})"
        name = err.get("code") if err.get("code") in FAIL_CODES else fallback
        message = str(err.get("message") or "")
        return name, f"{message} ({said})" if message else said

    def fetch_inputs(self, c: dict, work: Path) -> dict:
        got: dict = {}
        ins = c["inputs"]
        snap = ins.get("snapshot")
        if snap:
            for key, ext in (("tbxp", "tbxp"), ("tbxpack", "tbxpack")):
                f = snap.get(key)
                if f:
                    got[key] = self.api.download(f["url"], work / f"project.{ext}", f["sha256"]).resolve().as_posix()
        if ins.get("ops_url"):
            got["ops"] = self.api.download(ins["ops_url"], work / "ops.json").resolve().as_posix()
        if ins.get("base_manifest_url"):
            got["base_manifest"] = self.api.download(ins["base_manifest_url"], work / "base.json").resolve().as_posix()
        for name, f in (ins.get("files") or {}).items():
            got.setdefault("files", {})[name] = self.api.download(f["url"], work / "inputs" / name, f["sha256"]).resolve().as_posix()
        return got

    def command(self, job_json: Path) -> list[str]:
        app = self.cfg.app
        arg = f"-mwrender={job_json.resolve().as_posix()}"
        if app.endswith(".py"):
            return [sys.executable, app, arg]
        return [app, arg, "-nosplash", "-unattended"]

    def run_app(self, job_json: Path, work: Path, hb: Heartbeat) -> tuple[int | None, float, str]:
        log_path = work / "app.log"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        started = time.monotonic()
        with log_path.open("wb") as log:
            proc = subprocess.Popen(self.command(job_json), stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
            hb.proc = proc
            try:
                code = proc.wait(timeout=self.cfg.job_timeout_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                code = None
        wall = time.monotonic() - started
        tail = log_path.read_bytes()[-LOG_TAIL:].decode("utf-8", errors="replace")
        return code, wall, tail

    def outputs(self, kind: str, out: Path) -> tuple[dict, list[Path], dict[str, str]]:
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        files: list[Path] = []
        types: dict[str, str] = {}
        if kind == "pack":
            for f in manifest.get("files", []):
                path = out / f["name"]
                files.append(path)
                types[f["sha256"]] = f.get("content_type") or "application/octet-stream"
        else:
            for view in manifest.get("views", []):
                for face in view.get("faces", {}).values():
                    if face.get("rendered"):
                        files += [out / "tiles" / f"{sha}.jpg" for row in face.get("tiles", []) for sha in row]
        missing = [p.name for p in files if not p.is_file()]
        if missing:
            raise InputError(f"the app named {len(missing)} files it did not write, e.g. {missing[0]}")
        return manifest, list(dict.fromkeys(files)), types

    def run_job(self, c: dict) -> str:
        if self.cfg.mode == "container":
            return self.run_container_job(c)
        job, lease = c["job"], c["lease_id"]
        job_id = job["job_id"]
        work = Path(self.cfg.work_dir) / job_id
        shutil.rmtree(work, ignore_errors=True)
        (work / "out").mkdir(parents=True)
        self.log(f"claimed {job_id} ({job['kind']}, {len(job.get('views') or [])} views, at {job['at_seq']})")
        hb = Heartbeat(self.api, job_id, lease, work / "out", self.cfg.heartbeat_s)
        hb.start()
        try:
            try:
                inputs = self.fetch_inputs(c, work)
            except InputError as exc:
                self.api.fail(job_id, lease, "bad_input", str(exc), False, "")
                self.log(f"failed {job_id}: {exc}")
                return "failed"
            except HttpError as exc:
                retry = exc.status not in (403, 404, 410)
                self.api.fail(job_id, lease, "timeout" if retry else "bad_input", f"input download: {exc}", retry, "")
                self.log(f"failed {job_id}: {exc}")
                return "failed"
            job_json = work / "job.json"
            job_json.write_text(json.dumps(self.job_file(c, work, inputs), indent=2), encoding="utf-8")
            if hb.cancelled or hb.lost:
                self.log(f"{job_id} ended before the render started")
                return "cancelled" if hb.cancelled else "lost"
            self.log("running Truebex")
            code, wall, tail = self.run_app(job_json, work, hb)
            if hb.cancelled:
                self.log(f"cancelled {job_id}: outputs discarded")
                return "cancelled"
            if hb.lost:
                self.log(f"lease lost on {job_id}: outputs discarded")
                return "lost"
            if code != 0:
                code_name, message = self.failure(code, work / "out")
                self.api.fail(job_id, lease, code_name, message, code_name not in NOT_RETRYABLE, tail)
                self.log(f"failed {job_id}: {code_name}: {message}")
                return "failed"
            try:
                manifest, files, types = self.outputs(job["kind"], work / "out")
            except (InputError, OSError, ValueError) as exc:
                self.api.fail(job_id, lease, "engine_error", f"output: {exc}", True, tail)
                self.log(f"failed {job_id}: {exc}")
                return "failed"
            render_log = None
            try:
                render_log = json.loads((work / "out" / "render-log.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            try:
                sent = self.api.upload(c["output_upload"]["upload_id"], files, types)
                done = self.api.complete(job_id, lease, manifest, wall, render_log)
            except HttpError as exc:
                if exc.code == "worker_revoked":
                    raise
                if exc.code == "output_invalid":
                    self.api.fail(job_id, lease, "engine_error", f"the platform refused the output: {exc.detail}", False, tail)
                    self.log(f"failed {job_id}: {exc.detail}")
                    return "failed"
                if hb.cancelled or exc.code == "lease_lost" or exc.status in (401, 404, 409, 410):
                    # Cancelled or the lease ended while uploading: discard, claim the next job.
                    self.log(f"{'cancelled' if hb.cancelled else 'lease lost on'} {job_id}: outputs discarded")
                    return "cancelled" if hb.cancelled else "lost"
                raise
            rendered = manifest.get("faces_rendered", "?")
            self.log(f"complete {job_id}: {rendered} faces rendered, {sent} files sent, {wall:.1f} s, {done.get('cost_units')} cu")
            return "succeeded"
        finally:
            hb.stopped.set()
            hb.join(5)
            if not self.cfg.keep_work:
                shutil.rmtree(work, ignore_errors=True)

    # --- container mode (PF11 analysis kinds) ----------------------------------------------

    def analysis_job_file(self, c: dict, inputs: dict) -> dict:
        job = c["job"]
        return {
            "schema": "truebex-analysis-job/1",
            "job_id": job["job_id"],
            "kind": job["kind"],
            "project_id": job.get("project_id"),
            "at_seq": job.get("at_seq", 0),
            "params": job.get("params") or {},
            "profile": job.get("profile") or {},
            "inputs": {name: f"/job/inputs/{name}" for name in (inputs.get("files") or {})},
            "out_dir": "/job/out",
        }

    def container_name(self, job_id: str) -> str:
        return f"truebex-{job_id}"

    def container_command(self, job: dict, work: Path) -> list[str]:
        kind = job["kind"]
        image = self.cfg.images.get(kind) or (job.get("profile") or {}).get("image") or f"truebex-analysis-{kind}:1"
        args = [
            "run", "--rm", "--name", self.container_name(job["job_id"]), "--network", "none",
            "--cpus", str(self.cfg.cpus), "--memory", self.cfg.memory, "--pids-limit", str(self.cfg.pids_limit),
            "--security-opt", "no-new-privileges", "--cap-drop", "ALL", "--user", self.cfg.container_user,
            "-v", f"{work.resolve()}:/job", image,
        ]
        return self._docker(args)

    def _docker(self, args: list[str]) -> list[str]:
        docker = self.cfg.docker
        return [sys.executable, docker, *args] if docker.endswith(".py") else [docker, *args]

    def stop_container(self, job_id: str) -> None:
        try:
            subprocess.run(self._docker(["kill", self.container_name(job_id)]), capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass

    def run_container(self, cmd: list[str], work: Path, hb: Heartbeat, job_id: str) -> tuple[int | None, float, str]:
        log_path = work / "solver.log"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        started = time.monotonic()
        hb.on_kill = lambda: self.stop_container(job_id)
        with log_path.open("wb") as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
            hb.proc = proc
            try:
                code = proc.wait(timeout=self.cfg.job_timeout_s)
            except subprocess.TimeoutExpired:
                self.stop_container(job_id)
                proc.kill()
                proc.wait()
                code = None
        wall = time.monotonic() - started
        tail = log_path.read_bytes()[-LOG_TAIL:].decode("utf-8", errors="replace")
        return code, wall, tail

    @staticmethod
    def result_files(result: dict, out: Path) -> tuple[list[Path], dict[str, str]]:
        """The files a result names, from `out/<sha256>`, and their content types."""
        shas: dict[str, str] = {}
        for f in result.get("fields") or []:
            for key in ("values", "entities", "positions"):
                if f.get(key):
                    shas.setdefault(f[key], "application/octet-stream")
        for g in result.get("grids") or []:
            if g.get("values"):
                shas.setdefault(g["values"], "application/octet-stream")
        if result.get("report"):
            shas[result["report"]] = "application/pdf"
        for m in result.get("maps") or []:
            if m.get("sha256"):
                shas[m["sha256"]] = m.get("content_type") or "image/png"
        files = [out / sha for sha in shas]
        missing = [p.name for p in files if not p.is_file()]
        if missing:
            raise InputError(f"the solver named {len(missing)} files it did not write, e.g. {missing[0]}")
        return files, shas

    def run_container_job(self, c: dict) -> str:
        job, lease = c["job"], c["lease_id"]
        job_id = job["job_id"]
        work = Path(self.cfg.work_dir) / job_id
        shutil.rmtree(work, ignore_errors=True)
        (work / "out").mkdir(parents=True)
        self.log(f"claimed {job_id} ({job['kind']}, estimate {job.get('cost_units_estimate')} cu)")
        hb = Heartbeat(self.api, job_id, lease, work / "out", self.cfg.heartbeat_s)
        hb.start()
        try:
            try:
                inputs = self.fetch_inputs(c, work)
            except InputError as exc:
                self.api.fail(job_id, lease, "bad_input", str(exc), False, "")
                self.log(f"failed {job_id}: {exc}")
                return "failed"
            except HttpError as exc:
                retry = exc.status not in (403, 404, 410)
                self.api.fail(job_id, lease, "timeout" if retry else "bad_input", f"input download: {exc}", retry, "")
                self.log(f"failed {job_id}: {exc}")
                return "failed"
            (work / "job.json").write_text(json.dumps(self.analysis_job_file(c, inputs), indent=2), encoding="utf-8")
            if hb.cancelled or hb.lost:
                return "cancelled" if hb.cancelled else "lost"
            cmd = self.container_command(job, work)
            self.log(f"running the {job['kind']} solver ({cmd[-1]})")
            code, wall, tail = self.run_container(cmd, work, hb, job_id)
            if hb.cancelled or hb.lost:
                self.log(f"{'cancelled' if hb.cancelled else 'lease lost on'} {job_id}: outputs discarded")
                return "cancelled" if hb.cancelled else "lost"
            if code != 0:
                default = "timeout" if code is None else ("out_of_memory" if code == 137 else "engine_error")
                err = {"code": default, "message": f"exit {code}"}
                try:
                    err.update(json.loads((work / "out" / "error.json").read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    pass
                code_name = err.get("code") if err.get("code") in FAIL_CODES else "engine_error"
                self.api.fail(job_id, lease, code_name, str(err.get("message", "")), code_name not in NOT_RETRYABLE, tail)
                self.log(f"failed {job_id}: {code_name} {err.get('message', '')}")
                return "failed"
            try:
                result = json.loads((work / "out" / "result.json").read_text(encoding="utf-8"))
                files, types = self.result_files(result, work / "out")
            except (InputError, OSError, ValueError) as exc:
                self.api.fail(job_id, lease, "engine_error", f"output: {exc}", True, tail)
                self.log(f"failed {job_id}: {exc}")
                return "failed"
            try:
                sent = self.api.upload(c["output_upload"]["upload_id"], files, types)
                done = self.api.complete(job_id, lease, result, wall, None)
            except HttpError as exc:
                if exc.code == "worker_revoked":
                    raise
                if exc.code == "output_invalid":
                    self.api.fail(job_id, lease, "engine_error", f"the platform refused the output: {exc.detail}", False, tail)
                    self.log(f"failed {job_id}: {exc.detail}")
                    return "failed"
                if hb.cancelled or exc.code == "lease_lost" or exc.status in (401, 404, 409, 410):
                    self.log(f"{'cancelled' if hb.cancelled else 'lease lost on'} {job_id}: outputs discarded")
                    return "cancelled" if hb.cancelled else "lost"
                raise
            self.log(f"complete {job_id}: {len(files)} files ({sent} sent), {wall:.1f} s, {done.get('cost_units')} cu")
            return "succeeded"
        finally:
            hb.stopped.set()
            hb.join(5)
            if not self.cfg.keep_work:
                shutil.rmtree(work, ignore_errors=True)

    def run_once(self, wait_s: float | None = None) -> str | None:
        c = self.api.claim(self.cfg.wait_s if wait_s is None else wait_s)
        if c is None:
            return None
        return self.run_job(c)

    def loop(self, once: bool = False) -> int:
        self.log(f"{self.cfg.worker_id}: waiting for {self.cfg.mode} jobs ({', '.join(self.cfg.kinds)}) from {self.cfg.api}")
        idle_said = True
        while True:
            try:
                outcome = self.run_once()
            except HttpError as exc:
                if exc.code == "worker_revoked":
                    self.log("this worker's token was revoked; stopping")
                    return EXIT_REVOKED
                if exc.status in (401, 403) and exc.code in ("unauthenticated", "forbidden", "validation_failed"):
                    self.log(f"the platform refused this worker: {exc}")
                    return 2
                self.log(f"error: {exc}; trying again in 10 s")
                time.sleep(10)
                continue
            except Exception as exc:  # noqa: BLE001 - a bad job must not stop the worker
                self.log(f"error: {exc!r}; trying again in 10 s")
                time.sleep(10)
                continue
            if outcome is None:
                if not idle_said:
                    self.log("waiting for jobs")
                    idle_said = True
                continue
            idle_said = False
            if once:
                return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="truebex_worker.py", description=__doc__.split("\n")[0])
    parser.add_argument("--config", default="worker.toml")
    parser.add_argument("--app", help="the app to run (Truebex.exe, or a .py stand-in)")
    parser.add_argument("--once", action="store_true", help="run one job, then exit")
    parser.add_argument("--mode", choices=("app", "container"), help="app: render jobs; container: analysis jobs (PF11)")
    args = parser.parse_args(argv)
    cfg = Config.load(args.config, app=args.app, mode=args.mode)
    if not cfg.token.startswith("tbx_wrk_"):
        print("worker.toml: token must be a worker token (tbx_wrk_…) from Admin → Render", file=sys.stderr)
        return 2
    os.makedirs(cfg.work_dir, exist_ok=True)
    try:
        return Runner(cfg).loop(once=args.once)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
