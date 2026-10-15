"""PF6a: the worker wrapper (worker/truebex_worker.py) follows render-jobs
1.1.0, the contract CL3's `-mwrender` runs on: the job file it writes (§6.1,
`project.snapshot_seq`), the failure it reports for each of `-mwrender`'s
exit codes (5.10 per code), and the fake app (worker/tests/fake_truebex.py)
answering the app's own job files with the app's own manifests."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.storage import get_store

from .project_helpers import Person, delta_op, hex32, pushed, snapshot
from .render_helpers import (
    APP_PROJECT,
    FIX,
    MOVED,
    PROJECT_LOG,
    VIEWS,
    admin,
    issue_worker,
    job,
    project,
    push_touch,
    rj,
    submitted,
)

ROOT = Path(__file__).resolve().parents[2]
FAKE = ROOT / "worker" / "tests" / "fake_truebex.py"
# 5.10 per exit code (render-jobs 1.1.0): what the wrapper reports, and whether a retry may help.
EXIT_CODES = {
    2: ("bad_input", False),
    3: ("doc_too_new", False),
    4: ("render_crash", True),
    5: ("out_of_memory", True),
    6: ("timeout", True),
    7: ("engine_error", True),
    1: ("render_crash", True),
    9: ("render_crash", True),
}


def _load_worker():
    spec = importlib.util.spec_from_file_location("truebex_worker_pf6a", ROOT / "worker" / "truebex_worker.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["truebex_worker_pf6a"] = module
    spec.loader.exec_module(module)
    return module


W = _load_worker()


class Recording:
    """The wrapper's HTTP through the test client, keeping every 5.10 body it sends."""

    def __init__(self, client) -> None:
        self.client = client
        self.fails: list[dict] = []

    def request(self, method, url, headers, body, timeout):
        if method == "POST" and url.endswith("/fail"):
            self.fails.append(json.loads(body))
        res = self.client.request(method, url, headers=headers, content=body)
        return W.Response(res.status_code, {k.lower(): v for k, v in res.headers.items()}, res.content)


@pytest.fixture()
def rig(client, tmp_path):
    a = Person(client, "a@example.com")
    pid, head = project(client, a, project_id=APP_PROJECT)
    token = issue_worker(client, admin(client))
    cfg = W.Config(
        api="http://testserver", token=token, worker_id="pc-rtx", app=str(FAKE), work_dir=str(tmp_path / "jobs"),
        app_version="1.0.0", doc_version_max=38, heartbeat_s=0.2, wait_s=0, keep_work=True,
    )
    lines: list[str] = []
    transport = Recording(client)
    api = W.Api(cfg, transport=transport, sleep=lambda s: None, log=lines.append)
    return {"a": a, "pid": pid, "head": head, "runner": W.Runner(cfg, api), "cfg": cfg, "log": lines, "http": transport}


def written(rig, job_id: str) -> dict:
    return json.loads((Path(rig["cfg"].work_dir) / job_id / "job.json").read_text("utf-8"))


def keys(obj: dict, prefix: str = "") -> set[str]:
    out = set()
    for k, v in obj.items():
        out.add(prefix + k)
        if isinstance(v, dict):
            out |= keys(v, f"{prefix}{k}.")
    return out


# --- the job file ------------------------------------------------------------------------------


def test_pf6a_job_file_has_the_snapshot_seq_and_every_key_of_the_apps(client, rig):
    """A project whose newest snapshot before the job is at 2: the job file
    says so (`project.snapshot_seq` 2, the claim's snapshot), its operations
    are 3 and 4 only, and it holds every key of the app's job-tiles.json; the
    fake app, like CL3, refuses operations the snapshot already holds."""
    a, runner, pid = rig["a"], rig["runner"], rig["pid"]
    assert rig["head"] == 2
    res = snapshot(client, a.dev, pid, 2, (PROJECT_LOG / "snapshot-0000.tbxp").read_bytes())
    assert res.status_code == 201, res.text
    head = rig["head"]
    for _ in range(2):
        head = pushed(client, a.dev, pid, a.replica, [delta_op(a.author_id, [hex32()], base_seq=head)])["head_seq"]
    rec = submitted(client, rj(a), project_id=pid, at_seq=head, follow=True)
    assert runner.run_once(wait_s=0) == "succeeded"
    f = written(rig, rec["job_id"])
    assert f["project"]["snapshot_seq"] == 2 and f["project"]["at_seq"] == 4
    assert f["project"]["project_id"] == APP_PROJECT and f["views"] == VIEWS
    ops = json.loads(Path(f["project"]["ops"]).read_text("utf-8"))
    assert [o["server_seq"] for o in ops["ops"]] == [3, 4]
    app_tiles = json.loads((FIX / "job-tiles.json").read_text("utf-8"))
    assert keys(app_tiles) <= keys(f) | {"base_manifest"}
    assert "levels" not in f and "params" not in f  # the app's defaults: face_px halved down to tile_px
    # The edit: a tiles job with the app's touched ids, its base the panorama's manifest.
    push_touch(client, a, pid, MOVED)
    assert runner.run_once(wait_s=0) == "succeeded"
    tiles_job = client.get("/jobs", params={"kind": "tiles"}, headers=rj(a)).json()["jobs"][0]
    t = written(rig, tiles_job["job_id"])
    assert keys(app_tiles) <= keys(t)
    assert t["project"]["snapshot_seq"] == 2 and t["project"]["at_seq"] == 5 and t["changed"] == MOVED
    assert Path(t["base_manifest"]).is_file() and Path(t["out_dir"]).is_absolute() and "\\" not in t["out_dir"]
    out = client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a)).json()
    assert out["job_id"] == tiles_job["job_id"] and (out["faces_rendered"], out["faces_reused"]) == (13, 5)
    assert any("complete" in line and "13 faces rendered" in line for line in rig["log"])


def test_pf6a_job_file_without_a_snapshot_and_for_a_pack(rig, tmp_path):
    """No snapshot in the claim: no `snapshot_seq` (the app counts from the
    operations). A pack's params are its `items` and nothing else."""
    runner = rig["runner"]
    claim = {
        "job": {"job_id": "a" * 32, "kind": "panorama", "quality": "draft", "at_seq": 7, "project_id": APP_PROJECT,
                "views": VIEWS, "changed": [], "params": {}},
        "inputs": {"snapshot": None, "ops_url": "x", "base_manifest_url": None, "files": {}},
    }
    f = runner.job_file(claim, tmp_path, {"ops": "D:/w/ops.json"})
    assert "snapshot_seq" not in f["project"] and f["project"]["at_seq"] == 7 and f["quality"] == "draft"
    assert list(f) == list(json.loads((FIX / "job-panorama.json").read_text("utf-8")))  # the app's order
    claim["inputs"]["snapshot"] = {"at_seq": 5, "tbxp": {"sha256": "0" * 64, "bytes": 1, "url": "x"}, "tbxpack": None}
    assert runner.job_file(claim, tmp_path, {})["project"]["snapshot_seq"] == 5
    pack = {**claim, "job": {**claim["job"], "kind": "pack", "views": [], "params": {"items": ["renders", "boq"], "extra": 1}}}
    assert runner.job_file(pack, tmp_path, {})["params"] == {"items": ["renders", "boq"]}


# --- -mwrender's exit codes ----------------------------------------------------------------------


@pytest.mark.parametrize("exit_code", sorted(EXIT_CODES))
def test_pf6a_exit_code_without_error_json(client, rig, monkeypatch, exit_code):
    """An app that exits non-zero without out_dir/error.json: the wrapper's
    5.10 names the code CL3's exit code stands for (any other: render_crash),
    retryable unless bad_input or doc_too_new."""
    a, runner = rig["a"], rig["runner"]
    rec = submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"])
    monkeypatch.setenv("FAKE_TRUEBEX_EXIT", str(exit_code))
    assert runner.run_once(wait_s=0) == "failed"
    code, retryable = EXIT_CODES[exit_code]
    sent = rig["http"].fails[-1]
    assert (sent["code"], sent["retryable"]) == (code, retryable)
    assert f"exit {exit_code}" in sent["message"]
    assert not (Path(rig["cfg"].work_dir) / rec["job_id"] / "out" / "error.json").exists()
    now = job(client, rj(a), rec["job_id"])
    assert now["state"] == ("queued" if retryable else "failed") and now["attempts"] == 1
    with get_store().open(f"jobs/{rec['job_id']}/error.json") as fh:
        assert json.loads(fh.read())["code"] == code


def test_pf6a_error_json_wins_and_a_timeout_is_timeout(client, rig, monkeypatch):
    """error.json's code wins over the exit code (and decides `retryable`); a
    code 5.10 does not name falls back to the exit code's; an app the wrapper
    stops after job_timeout_s fails `timeout`."""
    a, runner, http = rig["a"], rig["runner"], rig["http"]
    rec = submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"])
    monkeypatch.setenv("FAKE_TRUEBEX_FAIL", "engine_error")
    monkeypatch.setenv("FAKE_TRUEBEX_EXIT", "2")  # error.json says engine_error, the exit says bad_input
    assert runner.run_once(wait_s=0) == "failed"
    assert (http.fails[-1]["code"], http.fails[-1]["retryable"]) == ("engine_error", True)
    monkeypatch.setenv("FAKE_TRUEBEX_FAIL", "doc_too_new")
    monkeypatch.setenv("FAKE_TRUEBEX_EXIT", "4")
    assert runner.run_once(wait_s=0) == "failed"
    assert (http.fails[-1]["code"], http.fails[-1]["retryable"]) == ("doc_too_new", False)
    assert job(client, rj(a), rec["job_id"])["state"] == "failed"
    # The fake's own exit for a code is 5.10's number; an unknown code in error.json reads as the exit code's.
    rec2 = submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"])
    monkeypatch.delenv("FAKE_TRUEBEX_EXIT")
    monkeypatch.setenv("FAKE_TRUEBEX_FAIL", "out_of_memory")
    assert runner.run_once(wait_s=0) == "failed"
    assert http.fails[-1]["code"] == "out_of_memory"
    assert (Path(rig["cfg"].work_dir) / rec2["job_id"] / "app.log").read_text("utf-8", errors="replace").count("exit 5")
    monkeypatch.setenv("FAKE_TRUEBEX_FAIL", "gpu_on_fire")
    assert runner.run_once(wait_s=0) == "failed"
    assert http.fails[-1]["code"] == "render_crash"  # the fake exits 4 for a code it does not know
    monkeypatch.delenv("FAKE_TRUEBEX_FAIL")
    # A timeout: the wrapper stops the app itself.
    monkeypatch.setenv("FAKE_TRUEBEX_SLEEP", "30")
    rig["cfg"].job_timeout_s = 1.0
    assert runner.run_once(wait_s=0) == "failed"
    assert (http.fails[-1]["code"], http.fails[-1]["retryable"]) == ("timeout", True)
    assert "1 s" in http.fails[-1]["message"]
    assert job(client, rj(a), rec2["job_id"])["attempts"] == 3


# --- the fake app reads the app's own job files --------------------------------------------------


def test_pf6a_fake_app_answers_the_apps_job_files(tmp_path):
    """The app's job-panorama.json and job-tiles.json, copied as they are into
    a folder two below a stand-in PR3-pano-rooms.tbxp (their paths are relative
    to the job file's folder, 1.1.0): the fake writes the app's two manifests
    (all but app_version) and their 90 + 65 tiles; without the snapshot,
    `bad_input` and exit 2."""
    j = tmp_path / "fixtures" / "contracts" / "render-jobs"
    j.mkdir(parents=True)
    for name in ("job-panorama.json", "job-tiles.json", "ops-tiles.json"):
        shutil.copyfile(FIX / name, j / name)
    run = lambda name: subprocess.run([sys.executable, str(FAKE), f"-mwrender={j / name}"], capture_output=True, text=True, timeout=120)  # noqa: E731
    res = run("job-panorama.json")
    assert res.returncode == 2, res.stdout + res.stderr
    assert json.loads((j / "out" / "error.json").read_text("utf-8"))["code"] == "bad_input"
    shutil.rmtree(j / "out")
    (tmp_path / "fixtures" / "PR3-pano-rooms.tbxp").write_bytes(b"TBXP stand-in")
    for name, out_dir, manifest, count in (
        ("job-panorama.json", "out", "manifest-panorama.json", 90),
        ("job-tiles.json", "out-tiles", "manifest-tiles.json", 65),
    ):
        res = run(name)
        assert res.returncode == 0, res.stdout + res.stderr
        got = json.loads((j / out_dir / "manifest.json").read_text("utf-8"))
        want = json.loads((FIX / manifest).read_text("utf-8"))
        assert got["app_version"] == "0.0.0-fake"
        assert {k: v for k, v in got.items() if k != "app_version"} == {k: v for k, v in want.items() if k != "app_version"}
        shas = {p.stem for p in (j / out_dir / "tiles").iterdir()}
        assert len(shas) == count
        for sha in shas:
            assert (j / out_dir / "tiles" / f"{sha}.jpg").read_bytes() == (FIX / "tiles" / f"{sha}.jpg").read_bytes()
    # An operation the snapshot already holds is refused, as CL3 refuses it.
    bad = json.loads((j / "job-tiles.json").read_text("utf-8"))
    bad["project"]["snapshot_seq"] = 1
    (j / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    res = run("bad.json")
    assert res.returncode == 2 and "snapshot" in json.loads((j / "out-tiles" / "error.json").read_text("utf-8"))["message"]
