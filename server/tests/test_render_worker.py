"""The worker wrapper (worker/truebex_worker.py) against the API in-process and
the fake app (worker/tests/fake_truebex.py) as a real subprocess (PF6)."""

import importlib.util
import json
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.render.models import RenderJob

from .project_helpers import Person, hex32
from .render_helpers import WALL, admin, issue_worker, job, project, push_touch, rj, submitted

ROOT = Path(__file__).resolve().parents[2]
FAKE = ROOT / "worker" / "tests" / "fake_truebex.py"


def _load_worker():
    spec = importlib.util.spec_from_file_location("truebex_worker", ROOT / "worker" / "truebex_worker.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["truebex_worker"] = module
    spec.loader.exec_module(module)
    return module


W = _load_worker()


class ClientTransport:
    """The wrapper's HTTP through the test client (signed URLs included)."""

    def __init__(self, client) -> None:
        self.client = client

    def request(self, method, url, headers, body, timeout):
        res = self.client.request(method, url, headers=headers, content=body)
        return W.Response(res.status_code, {k.lower(): v for k, v in res.headers.items()}, res.content)


@pytest.fixture()
def rig(client, tmp_path):
    a = Person(client, "a@example.com")
    pid, head = project(client, a)
    token = issue_worker(client, admin(client))
    cfg = W.Config(
        api="http://testserver", token=token, worker_id="pc-rtx", app=str(FAKE), work_dir=str(tmp_path / "jobs"),
        app_version="1.1.0", doc_version_max=38, heartbeat_s=0.2, wait_s=0, keep_work=True,
    )
    lines: list[str] = []
    api = W.Api(cfg, transport=ClientTransport(client), sleep=lambda s: None, log=lines.append)
    return {"a": a, "pid": pid, "head": head, "runner": W.Runner(cfg, api), "cfg": cfg, "log": lines}


def test_worker_wrapper_runs_job_file(client, rig):
    a, runner = rig["a"], rig["runner"]
    assert runner.run_once(wait_s=0) is None  # nothing queued
    rec = submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"], follow=True)
    assert runner.run_once(wait_s=0) == "succeeded"
    work = Path(rig["cfg"].work_dir) / rec["job_id"]
    written = json.loads((work / "job.json").read_text("utf-8"))
    # §6.1, field by field.
    assert written["schema"] == "truebex-render-job/1" and written["job_id"] == rec["job_id"]
    assert written["kind"] == "panorama" and written["quality"] == "standard" and written["seed"] == 1
    assert written["project"]["at_seq"] == rig["head"] and written["project"]["tbxpack"] is None
    assert Path(written["project"]["tbxp"]).is_file() and Path(written["project"]["ops"]).is_file()
    assert written["views"] == rec["views"] and written["changed"] == [] and written["base_manifest"] is None
    assert (written["face_px"], written["tile_px"], written["jpeg_quality"]) == (2048, 512, 85)
    assert written["out_dir"].endswith(f"{rec['job_id']}/out") and "\\" not in written["out_dir"]
    assert json.loads((work / "out" / "received-job.json").read_text("utf-8")) == written
    done = job(client, rj(a), rec["job_id"])
    assert done["state"] == "succeeded" and done["cost_units"] is not None and done["cost_units"] > 0
    assert any("complete" in line and "6 faces rendered" in line for line in rig["log"])
    # An edit: the wrapper renders the two faces that see the wall.
    push_touch(client, a, rig["pid"], [WALL])
    assert runner.run_once(wait_s=0) == "succeeded"
    tiles_job = client.get("/jobs", params={"kind": "tiles"}, headers=rj(a)).json()["jobs"][0]
    tiles_file = json.loads((Path(rig["cfg"].work_dir) / tiles_job["job_id"] / "job.json").read_text("utf-8"))
    assert tiles_file["changed"] == [WALL] and Path(tiles_file["base_manifest"]).is_file()
    out = client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a)).json()
    assert out["job_id"] == tiles_job["job_id"] and out["faces_rendered"] == 2
    for face in out["views"][0]["faces"].values():
        for row in face["tiles"]:
            for sha in row:
                assert client.get(f"/tiles/{sha}.jpg").status_code == 200


def test_worker_wrapper_failure_and_cancel(client, rig, monkeypatch):
    a, runner = rig["a"], rig["runner"]
    rec = submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"])
    monkeypatch.setenv("FAKE_TRUEBEX_FAIL", "out_of_memory")
    assert runner.run_once(wait_s=0) == "failed"
    again = job(client, rj(a), rec["job_id"])
    assert again["state"] == "queued" and again["attempts"] == 1
    from app.storage import get_store

    with get_store().open(f"jobs/{rec['job_id']}/error.json") as fh:
        assert json.loads(fh.read())["code"] == "out_of_memory"
    monkeypatch.delenv("FAKE_TRUEBEX_FAIL")
    monkeypatch.setenv("FAKE_TRUEBEX_SLEEP", "8")

    def cancel_soon() -> None:
        time.sleep(1.0)
        client.post(f"/jobs/{rec['job_id']}/cancel", headers=rj(a))

    t = threading.Thread(target=cancel_soon)
    t.start()
    started = time.monotonic()
    assert runner.run_once(wait_s=0) == "cancelled"
    t.join()
    assert time.monotonic() - started < 6  # the app was killed, not waited for
    end = job(client, rj(a), rec["job_id"])
    assert end["state"] == "cancelled" and end["cost_units"] is None
    with SessionLocal() as db:
        assert db.get(RenderJob, rec["job_id"]).worker_id is None


def test_worker_wrapper_revoked_and_config(client, rig, tmp_path):
    example = W.Config.load(ROOT / "worker" / "worker.toml.example")
    assert example.worker_class == "gpu-std" and example.kinds == ["panorama", "tiles", "pack"] and example.wait_s == 20
    client.delete("/admin/workers/pc-rtx", headers=admin(client, "admin2@example.com"))
    assert rig["runner"].loop() == W.EXIT_REVOKED
    assert any("revoked" in line for line in rig["log"])
    # The fake refuses a job file that breaks §6.1.
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "truebex-render-job/1", "out_dir": str(tmp_path / "o")}), encoding="utf-8")
    import subprocess

    res = subprocess.run([sys.executable, str(FAKE), f"-mwrender={bad}"], capture_output=True)
    assert res.returncode == 2
    assert json.loads((tmp_path / "o" / "error.json").read_text("utf-8"))["code"] == "bad_input"
    assert hex32()


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell not available")
def test_worker_image_scripts_parse():
    """infra/worker/*.ps1 install drivers and services, so they are not run
    here: they must at least parse (and keep the one-job-at-a-time wrapper)."""
    import subprocess

    for name in ("bootstrap.ps1", "build-image.ps1"):
        path = ROOT / "infra" / "worker" / name
        cmd = (
            "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
            f"'{path}', [ref]$null, [ref]$e) | Out-Null; $e.Count"
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60)
        assert res.stdout.strip() == "0", (name, res.stdout, res.stderr)
    text = (ROOT / "infra" / "worker" / "bootstrap.ps1").read_text("utf-8")
    assert "truebex_worker.py" in text and "Block" in text and "-ImageOnly" in (ROOT / "infra" / "worker" / "build-image.ps1").read_text("utf-8")
