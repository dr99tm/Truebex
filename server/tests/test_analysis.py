"""Analysis jobs on PF6's queue (PF11, contract render-jobs §5.1, §6.3): the
feature and the inputs a kind needs, estimates, the wrapper's container mode
with the stub solver, §6.3 validation, the weather library, texture behind
its flag."""

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from app.analysis import kinds as analysis_kinds
from app.config import get_settings
from app.render import quotas

from .analysis_helpers import (
    entities, epjson, epw, octahedron_stl, put_inputs, rooms_file, sha, submit, wind_body,
)
from .licence_helpers import error_of
from .project_helpers import UPLOADS, Person, hex32
from .render_helpers import RJ, admin, claim, claimed, issue_worker, job, project, rj, wk

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "contracts" / "render-jobs"
FAKE_DOCKER = Path(__file__).parent / "fakes" / "stub_solver" / "fake_docker.py"
ANALYSIS_KINDS = ("wind", "energy", "acoustics")


def _load_worker():
    spec = importlib.util.spec_from_file_location("truebex_worker_pf11", ROOT / "worker" / "truebex_worker.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["truebex_worker_pf11"] = module
    spec.loader.exec_module(module)
    return module


W = _load_worker()


class ClientTransport:
    def __init__(self, client) -> None:
        self.client = client

    def request(self, method, url, headers, body, timeout):
        res = self.client.request(method, url, headers=headers, content=body)
        return W.Response(res.status_code, {k.lower(): v for k, v in res.headers.items()}, res.content)


def _fixture_result(job_rec: dict) -> dict:
    m = copy.deepcopy(json.loads((FIX / "wind-result.json").read_text("utf-8")))
    m.update(kind=job_rec["job"]["kind"], project_id=job_rec["job"]["project_id"], at_seq=job_rec["job"]["at_seq"], params=job_rec["job"]["params"])
    return m


def _bins() -> list[bytes]:
    return [p.read_bytes() for p in sorted(FIX.glob("wind-*.bin"))]


def _send_outputs(client, token: str, c: dict, files: list[bytes], content_type: str = "application/octet-stream") -> None:
    body = {
        "purpose": "job-output",
        "upload_id": c["output_upload"]["upload_id"],
        "files": [{"sha256": sha(d), "bytes": len(d), "content_type": content_type} for d in files],
    }
    opened = client.post("/uploads", json=body, headers={"Authorization": f"Bearer {token}", **UPLOADS}).json()
    for data, state in zip(files, opened["files"]):
        if state["state"] == "present":
            continue
        res = client.put(
            f"/uploads/{opened['upload_id']}/files/{state['sha256']}/parts/0", content=data,
            headers={"Authorization": f"Bearer {token}", **UPLOADS, "Content-Type": "application/octet-stream",
                     "X-Part-Sha256": hashlib.sha256(data).hexdigest()},
        )
        assert res.status_code == 204, res.text


def _complete(client, token: str, c: dict, output: dict, wall_s: float = 120.0):
    return client.post(
        f"/workers/jobs/{c['job']['job_id']}/complete",
        json={"lease_id": c["lease_id"], "output": output, "usage": {"wall_s": wall_s, "class": "cpu-8"}},
        headers=wk(token),
    )


@pytest.fixture()
def rig(client):
    a = Person(client, "a@example.com")  # a Pro trial: holds analysis.reports
    adm = admin(client)
    token = issue_worker(client, adm, name="cpu-eu-01", kinds=ANALYSIS_KINDS, cls="cpu-8")
    stl = octahedron_stl()
    put_inputs(client, a.dev, stl, entities())
    return {"a": a, "admin": adm, "token": token, "stl": stl}


def test_analysis_submit_requires_feature(client, rig):
    a, stl = rig["a"], rig["stl"]
    free = Person(client, "free@example.com", trial=False)
    put_inputs(client, free.dev, stl)
    err = error_of(submit(client, free.dev, wind_body(stl)), 403, "plan_required")
    assert err["data"]["feature"] == "analysis.reports"
    # Without the geometry: 422.
    no_geo = wind_body(stl)
    no_geo["inputs"]["files"] = {}
    err = error_of(submit(client, a.dev, no_geo), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "inputs.files.geometry"
    error_of(client.post("/jobs", json=wind_body(stl), headers=RJ), 401, "unauthenticated")
    # The geometry must be uploaded, binary, with matching entity ids.
    missing = wind_body(b"x" * 300)
    error_of(submit(client, a.dev, missing), 422, "validation_failed")
    ascii_stl = b"solid house\nfacet normal 0 0 1\nendsolid house\n"
    put_inputs(client, a.dev, ascii_stl)
    assert "binary STL" in error_of(submit(client, a.dev, wind_body(ascii_stl)), 422, "validation_failed")["detail"]
    short = entities(7)
    put_inputs(client, a.dev, short)
    bad_ids = wind_body(stl)
    bad_ids["inputs"]["files"]["entities"] = sha(short)
    error_of(submit(client, a.dev, bad_ids), 422, "validation_failed")
    for params in ({"terrain": "forest"}, {"direction_deg": 360}, {"speed_ms": 0}, {"comfort": "davenport"}):
        error_of(submit(client, a.dev, wind_body(stl, **params)), 422, "validation_failed")
    extra = wind_body(stl)
    extra["inputs"]["files"]["model"] = sha(stl)
    error_of(submit(client, a.dev, extra), 422, "validation_failed")
    # The happy path: queued for a cpu-8 worker with GD3's estimate
    # (about 2.06 M cells × 1000 iterations: 420 s + 0.7 s per million = 1861 s -> 7.8 cu).
    ok = wind_body(stl)
    ok["inputs"]["files"]["entities"] = sha(entities())
    res = submit(client, a.dev, ok)
    assert res.status_code == 201, res.text
    rec = res.json()
    assert rec["kind"] == "wind" and rec["state"] == "queued" and rec["class"] == "cpu-8"
    assert rec["cost_units_estimate"] == 7.8 and rec["project_id"] is None
    # With a project: the snapshot reference is checked like a render's.
    pid, head = project(client, a)
    error_of(submit(client, a.dev, {**wind_body(stl), "project_id": pid, "at_seq": head + 5}), 409, "seq_ahead")
    with_project = submit(client, a.dev, {**wind_body(stl), "project_id": pid, "at_seq": head})
    assert with_project.status_code == 201 and with_project.json()["project_id"] == pid
    # Sessions submit too (the website); the 5.1 answer's estimate is the same.
    assert submit(client, a.session, wind_body(stl)).json()["cost_units_estimate"] == 7.8


def test_analysis_stub_solver_round_trip(client, rig, tmp_path):
    a, token, stl = rig["a"], rig["token"], rig["stl"]
    body = wind_body(stl)
    body["inputs"]["files"]["entities"] = sha(entities())
    rec = submit(client, a.dev, body).json()
    # A render worker never takes it; nor can a gpu-std token hold an analysis kind.
    render = issue_worker(client, rig["admin"], name="gpu-eu-01", kinds=("panorama", "tiles"), cls="gpu-std")
    assert claim(client, render, worker_id="gpu-eu-01", kinds=("panorama", "tiles")).status_code == 204
    bad = client.post("/admin/workers", json={"name": "mixed", "kinds": ["wind", "panorama"], "class": "cpu-8"}, headers=rig["admin"])
    assert bad.status_code == 422
    cfg = W.Config(
        api="http://testserver", token=token, worker_id="cpu-eu-01", kinds=list(ANALYSIS_KINDS), worker_class="cpu-8",
        work_dir=str(tmp_path / "jobs"), heartbeat_s=0.2, wait_s=0, keep_work=True, mode="container", docker=str(FAKE_DOCKER),
    )
    lines: list[str] = []
    runner = W.Runner(cfg, W.Api(cfg, transport=ClientTransport(client), sleep=lambda s: None, log=lines.append))
    assert runner.run_once(wait_s=0) == "succeeded", lines
    work = tmp_path / "jobs" / rec["job_id"]
    written = json.loads((work / "job.json").read_text("utf-8"))
    assert written["schema"] == "truebex-analysis-job/1" and written["kind"] == "wind" and written["out_dir"] == "/job/out"
    assert written["inputs"] == {"geometry": "/job/inputs/geometry", "entities": "/job/inputs/entities"}
    assert (work / "inputs" / "geometry").read_bytes() == stl
    assert written["params"] == rec_params(client, a, rec) and written["profile"]["terrain"]["suburban"]["z0_m"] == 0.3
    args = json.loads((work / "docker-args.json").read_text("utf-8"))
    for flag, value in (("--network", "none"), ("--cpus", "4.0"), ("--memory", "12g"), ("--user", "1000:1000")):
        assert args[args.index(flag) + 1] == value
    assert args[-1] == "truebex-analysis-wind:1" and "--rm" in args and "no-new-privileges" in args
    done = job(client, rj(a), rec["job_id"])
    # A fraction of a second on cpu-8 (weight 0.25): the smallest charge.
    assert done["state"] == "succeeded" and done["cost_units"] == 0.1 and done["class"] == "cpu-8"
    out = client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a)).json()
    assert out["schema"] == "truebex-analysis/1" and out["fields"][0]["name"] == "pressure_coefficient"
    assert out["fields"][0]["count"] == 8 and out["grids"][0]["name"] == "comfort_lawson"
    assert set(out["urls"]) == {sha(b) for b in _bins()} and out["urls_expire_at"]
    for digest, url in out["urls"].items():
        got = client.get(url)
        assert got.status_code == 200 and sha(got.content) == digest
    usage = client.get("/jobs/usage", headers=rj(a)).json()
    assert usage["by_kind"]["wind"] == 0.1 and usage["classes"]["cpu-8"] == 0.25
    assert any("complete" in line for line in lines)
    # Measured time is charged at the cpu-8 weight: 600 s -> 600 / 60 × 0.25 = 2.5 cu.
    rec2 = submit(client, a.dev, body).json()
    c = claimed(client, token, worker_id="cpu-eu-01", kinds=ANALYSIS_KINDS)
    assert c["job"]["job_id"] == rec2["job_id"] and c["job"]["profile"]["iterations_max"] == 1000
    assert set(c["inputs"]["files"]) == {"geometry", "entities"}
    _send_outputs(client, token, c, _bins())
    res = _complete(client, token, c, _fixture_result(c), wall_s=600)
    assert res.status_code == 200, res.text
    assert res.json()["cost_units"] == 2.5
    # A solver failure is reported with its code.
    rec3 = submit(client, a.dev, wind_body(stl, speed_ms=13)).json()
    assert runner.run_once(wait_s=0) == "failed"
    failed = job(client, rj(a), rec3["job_id"])
    assert failed["state"] == "queued" and failed["attempts"] == 1 and "engine_error" in failed["message"]


def rec_params(client, a, rec) -> dict:
    return json.loads(json.dumps(analysis_kinds.validate_params("wind", {"speed_ms": 5, "direction_deg": 225, "reference_height_m": 10, "terrain": "suburban", "comfort": "lawson"})))


def test_analysis_result_validation(client, rig):
    a, token, stl = rig["a"], rig["token"], rig["stl"]
    submit(client, a.dev, wind_body(stl))
    c = claimed(client, token, worker_id="cpu-eu-01", kinds=ANALYSIS_KINDS)
    _send_outputs(client, token, c, _bins())
    good = _fixture_result(c)

    def refused(output: dict) -> list[dict]:
        res = _complete(client, token, c, output)
        return error_of(res, 422, "output_invalid")["data"]["errors"]

    # A field whose count differs from its array length (and here from the
    # geometry's 8 triangles too).
    m = copy.deepcopy(good)
    m["fields"][0]["count"] = 9
    assert any(e["rule"] == "count" and e["path"] == "fields[0].count" for e in refused(m))
    # A grid whose size differs from its array's length.
    m = copy.deepcopy(good)
    m["grids"][0]["nx"] = 5
    errors = refused(m)
    assert any(e["rule"] == "file_size" and e["expected"] == 20 for e in errors)
    m = copy.deepcopy(good)
    m["fields"][0]["values"] = "f" * 64
    assert any(e["rule"] == "file_missing" for e in refused(m))
    m = copy.deepcopy(good)
    m["params"] = {**m["params"], "speed_ms": 9}
    assert any(e["path"] == "params" for e in refused(m))
    for key, value, path in (
        ("schema", "truebex-analysis/2", "schema"),
        ("engine", {"name": "x"}, "engine"),
        ("kind", "energy", "kind"),
    ):
        m = copy.deepcopy(good)
        m[key] = value
        assert any(e["path"] == path for e in refused(m)), key
    m = copy.deepcopy(good)
    m["fields"][0]["unit"] = "furlongs"
    m["fields"][0]["on"] = "rooms"
    del m["fields"][0]["entities"]
    paths = {e["path"] for e in refused(m)}
    assert {"fields[0].unit", "fields[0].on"} <= paths
    # The fixture result passes.
    res = _complete(client, token, c, good)
    assert res.status_code == 200, res.text and res.json()["state"] == "succeeded"


def test_analysis_weather_library_and_energy(client, rig):
    a, token, adm = rig["a"], rig["token"], rig["admin"]
    data = epw()
    put = client.put(
        "/admin/analysis/weather/gbr-london-test", content=data, headers=adm,
        params={"name": "London test year", "source": "a synthetic test file", "licence": "CC0-1.0"},
    )
    assert put.status_code == 200, put.text
    entry = put.json()
    assert entry["location"] == "London Heathrow, GBR" and entry["latitude"] == 51.48 and entry["sha256"] == sha(data)
    assert client.put("/admin/analysis/weather/x", content=data, headers=a.session, params={"name": "n", "source": "s", "licence": "l"}).status_code == 403
    error_of(client.put("/admin/analysis/weather/bad-file", content=b"not an epw", headers=adm, params={"name": "n", "source": "s", "licence": "l"}), 422, "validation_failed")
    catalogue = client.get("/analysis/catalogue", headers=rj(a)).json()
    assert [w["weather_id"] for w in catalogue["weather"]] == ["gbr-london-test"]
    assert catalogue["weather"][0]["licence"] == "CC0-1.0" and catalogue["weather"][0]["source"]
    assert [k["kind"] for k in catalogue["kinds"]] == ["wind", "energy", "acoustics"]
    assert {t["id"]: t["z0_m"] for t in catalogue["terrain"]}["urban"] == 1.0
    error_of(client.get("/analysis/catalogue", headers=RJ), 401, "unauthenticated")
    model = epjson(zones=10, timesteps=4)
    put_inputs(client, a.dev, model)
    body = {"kind": "energy", "inputs": {"files": {"model": sha(model)}}, "params": {"weather": "nowhere-test"}}
    error_of(submit(client, a.dev, body), 422, "validation_failed")
    body["params"]["weather"] = "gbr-london-test"
    res = submit(client, a.dev, body)
    assert res.status_code == 201, res.text
    # 10 zones × 4 timesteps an hour × 8760 h = 350 400 zone-timesteps -> 150 s on cpu-8 -> 0.7 cu.
    assert res.json()["cost_units_estimate"] == 0.7
    no_zone = json.dumps({"Zone": {}}).encode()
    put_inputs(client, a.dev, no_zone)
    error_of(submit(client, a.dev, {**body, "inputs": {"files": {"model": sha(no_zone)}}}), 422, "validation_failed")
    c = claimed(client, token, worker_id="cpu-eu-01", kinds=ANALYSIS_KINDS)
    assert set(c["inputs"]["files"]) == {"model", "weather"}
    assert client.get(c["inputs"]["files"]["weather"]["url"]).content == data
    # Energy results need their summary.
    out = {
        "schema": "truebex-analysis/1", "kind": "energy", "project_id": None, "at_seq": 0, "params": c["job"]["params"],
        "engine": {"name": "energyplus", "version": "24.2", "image": "sha256:" + "1" * 64}, "summary": {"eui_kwh_m2_y": 80.5},
        "fields": [{"name": "heating_kwh", "unit": "kWh", "on": "spaces", "count": 2, "values": sha(b"\0" * 8), "keys": ["a", "b"]}],
    }
    _send_outputs(client, token, c, [b"\0" * 8])
    errs = error_of(_complete(client, token, c, out), 422, "output_invalid")["data"]["errors"]
    assert {e["path"] for e in errs} == {"summary.heating_kwh_y", "summary.cooling_kwh_y"}
    out["summary"].update(heating_kwh_y=4200.0, cooling_kwh_y=300.0)
    assert _complete(client, token, c, out).status_code == 200
    assert client.delete("/admin/analysis/weather/gbr-london-test", headers=adm).status_code == 200
    assert client.get("/admin/analysis/weather", headers=adm).json()["weather"] == []


def test_analysis_acoustics_submit(client, rig):
    a = rig["a"]
    rooms = rooms_file()
    put_inputs(client, a.dev, rooms)
    body = {"kind": "acoustics", "inputs": {"files": {"rooms": sha(rooms)}}, "params": {"sources": [{"position_m": [1, 1, 1.2], "power_db": 80}]}}
    res = submit(client, a.dev, body)
    assert res.status_code == 201, res.text
    # 20 000 rays × 1 source = 20 thousand ray-sources: 30 s + 7.5 s each -> 180 s -> 0.8 cu.
    assert res.json()["cost_units_estimate"] == 0.8
    for params in ({"sources": []}, {"sources": [{"position_m": [1, 1]}]}, {"sources": [{"position_m": [1, 1, 1]}], "bands": [100]}, {"sources": [{"position_m": [1, 1, 1]}], "rays": 10}):
        error_of(submit(client, a.dev, {**body, "params": params}), 422, "validation_failed")
    flat = json.dumps({"rooms": [{"surfaces": []}]}).encode()
    put_inputs(client, a.dev, flat)
    error_of(submit(client, a.dev, {**body, "inputs": {"files": {"rooms": sha(flat)}}}), 422, "validation_failed")


def test_texture_kind_behind_flag(client, rig, monkeypatch):
    a, adm = rig["a"], rig["admin"]
    body = {"kind": "texture", "params": {"prompt": "weathered oak floorboards", "size": 512}}
    err = error_of(submit(client, a.dev, body), 422, "validation_failed")
    assert err["data"]["fields"][0]["field"] == "kind" and "texture" not in err["detail"]
    assert "texture" not in quotas.KINDS
    monkeypatch.setattr(get_settings(), "ai_texture_enabled", True)
    analysis_kinds.sync()
    try:
        rec = submit(client, a.dev, body)
        assert rec.status_code == 201, rec.text
        assert rec.json()["class"] == "gpu-ai" and rec.json()["cost_units_estimate"] > 0
        gpu = issue_worker(client, adm, name="gpu-ai-01", kinds=("texture",), cls="gpu-ai")
        c = claimed(client, gpu, worker_id="gpu-ai-01", kinds=("texture",))
        maps = {name: f"{name}-png".encode() for name in ("albedo", "normal", "roughness")}
        _send_outputs(client, gpu, c, list(maps.values()), "image/png")
        output = {
            "schema": "truebex-texture/1", "job_id": c["job"]["job_id"], "kind": "texture", "params": c["job"]["params"],
            "engine": {"name": "image-model", "version": "1", "image": "sha256:" + "2" * 64},
            "maps": [{"name": n, "sha256": sha(d), "size_px": 512, "content_type": "image/png"} for n, d in maps.items()],
        }
        short = {**output, "maps": output["maps"][:2]}
        error_of(client.post(f"/workers/jobs/{c['job']['job_id']}/complete", json={"lease_id": c["lease_id"], "output": short, "usage": {"wall_s": 30, "class": "gpu-ai"}}, headers=wk(gpu)), 422, "output_invalid")
        res = client.post(f"/workers/jobs/{c['job']['job_id']}/complete", json={"lease_id": c["lease_id"], "output": output, "usage": {"wall_s": 60, "class": "gpu-ai"}}, headers=wk(gpu))
        assert res.status_code == 200, res.text
        # One minute on gpu-ai (weight 0.85).
        assert res.json()["cost_units"] == 0.9
        got = client.get(f"/jobs/{c['job']['job_id']}/output", headers=rj(a)).json()
        assert set(got["urls"]) == {sha(d) for d in maps.values()}
    finally:
        monkeypatch.setattr(get_settings(), "ai_texture_enabled", False)
        analysis_kinds.sync()
    assert "texture" not in quotas.KINDS


def test_analysis_admin_overview_lists_cpu_classes(client, rig):
    a, adm, stl = rig["a"], rig["admin"], rig["stl"]
    submit(client, a.dev, wind_body(stl))
    overview = client.get("/admin/render", headers=adm).json()
    wind = next(q for q in overview["queue"] if q["kind"] == "wind")
    assert wind["queued"] == 1
    assert "cpu-8" in [c["class"] for c in overview["pool"]["classes"]]
    assert {w["worker_id"]: w["class"] for w in overview["workers"]}["cpu-eu-01"] == "cpu-8"
    # The cpu-8 pool follows its own queue.
    from app.database import SessionLocal
    from app.licence import clock
    from app.render import pools

    with SessionLocal() as db:
        wanted = pools.autoscale(db, clock.now())
    assert wanted["cpu-8"] >= 1 and hex32()
