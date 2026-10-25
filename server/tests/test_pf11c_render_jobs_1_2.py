"""PF11c: the analysis service follows render-jobs 1.2.0 (AN3's wind and airflow kinds).

AN3 (the app's wind study, merged on app main bcdd021f1, 2026-10-24) published
render-jobs 1.2.0: §6.5 (the reference, the wind kind's inputs, params and
outputs, a new `airflow` kind, the solver profile PF11 implements), the grid
layout of §6.3 and the `files` map 5.5 answers, with the stub's wind result
and six arrays in the app's fixture folder (last changed in app commit
51b5adf01). scripts/sync-contract-fixtures.ps1 copied the folder (169 files)
into tests/contracts/render-jobs/. These tests hold the platform to 1.2.0:
the copy, the wind job's inputs and params, its result in §6.3's layout and
5.5's files map, the airflow kind (its rooms file, its wait for the wind
job, the orifice network), the reference rules of §6.5.1, quality picking
the mesh, the runners' case files and outputs (never running OpenFOAM), and
the render-jobs/1.2 echo (1.3 since PF6c, its tests in test_pf6c_render_jobs_1_3.py).
Contract §10's two names are among them.
"""

import copy
import hashlib
import json
import math
import struct
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.licence import clock
from app.projects import waiters
from app.render import queue
from app.render.models import RenderJob

from .analysis_helpers import entities, octahedron_stl, put_inputs, sha
from .licence_helpers import error_of
from .pf12_helpers import ALL_SCOPES, kh, make_key
from .project_helpers import Person, hex32
from .render_helpers import FIX, admin, claim, claimed, issue_worker, job, project, rj, wk
from .test_analysis import _complete, _send_outputs
from .test_pf6a_render_jobs_1_1 import APP_BLOBS, APP_TILES, APP_TILES_TREE, git_blob_id, git_tree_id

ROOT = Path(__file__).resolve().parents[2]
APP_REPO = Path(r"T:\unreal5_7_4_projects\truebex_compact")
APP_DIR = "Docs/roadmap/fixtures/contracts/render-jobs"
# The app commit copied from (main, AN3's merge) and the commit that last changed the folder (AN3).
APP_COMMIT = "bcdd021f111cac84a2b0bb38ffa7a274059cb83c"
APP_FOLDER_COMMIT = "51b5adf01a4a7a3634bc417b873337d13ebb5e54"
APP_FOLDER_TREE = "0d5ce75d3d529d9c5e63f923a080d8041b66722c"
WIND_BLOBS = {
    "wind-comfort_lawson.bin": "4a10e0b509b7e7d75263fc4710656b8d6aa85bf1",
    "wind-entities.bin": "1de986d45025d7592cf701a984f596e88ed259ab",
    "wind-geometry.bin": "4fbcad11b769ae4f14296f2ab7d1f5319d9a1d9a",
    "wind-pressure_coefficient.bin": "ef01b71c468dadcfda58ddccd6978755ed6242e9",
    "wind-result.json": "d38d1bdf597aaec4f95bba93ee722b70d2a07bce",
    "wind-speed_ratio.bin": "7b7ba43425dc179a08ceda8b33960bc13a2917bc",
    "wind-velocity.bin": "0a8f4835a563d7d8a2af5537a61912bf45e2cd79",
}
ECHO = "render-jobs/1.3"  # PF6c: every route answers 1.3 since 1.3.0 (CL4)
RJ12 = {"X-Truebex-Contract": "render-jobs/1.2"}  # what AN3's client sends, still served
KINDS = ("wind", "airflow")
# The app's study (CadAnalysisJobs.cpp) sends every 1.2 key; wind-result.json echoes them.
APP_PARAMS = {
    "speed_ms": 5, "direction_deg": 225, "reference_height_m": 10, "terrain": "suburban", "comfort": "lawson",
    "pedestrian_height_m": 1.5, "grid_cell_mm": 1000, "turbulence_model": "realizable_ke",
}
# What a platform worker's engine and summary say (the stub's engine.image is null and its summary has one key).
PLATFORM_ENGINE = {"name": "openfoam", "version": "2406", "image": "truebex-analysis-wind:1"}
PLATFORM_SUMMARY = {"max_speed_ms": 3.651, "max_speed_ratio": 0.730151, "iterations": 1350, "residual": 9.1e-05}
LIVING = "0199c6a2e00070028000000000000011"
HALL = "0199c6a2e00070028000000000000012"
O_SOUTH = "0199c6a2e000700a8000000000000021"
O_DOOR = "0199c6a2e000700a8000000000000022"
O_NORTH = "0199c6a2e000700a8000000000000023"


@pytest.fixture(autouse=True)
def _clean_waiters():
    waiters.reset()
    yield
    waiters.reset()


def app_file(name: str) -> bytes:
    return (FIX / name).read_bytes()


def app_result() -> dict:
    return json.loads(app_file("wind-result.json").decode("utf-8"))


def app_arrays() -> list[bytes]:
    return [app_file(n) for n in ("wind-pressure_coefficient.bin", "wind-entities.bin", "wind-speed_ratio.bin",
                                  "wind-velocity.bin", "wind-comfort_lawson.bin")]


def platform_result(c: dict) -> dict:
    """The app's stub answer with a platform worker's engine and summary; its own
    `files` map (relative names the stub resolves) is left in: the platform drops it."""
    m = app_result()
    m.update(kind=c["job"]["kind"], project_id=c["job"]["project_id"], at_seq=c["job"]["at_seq"], params=c["job"]["params"])
    m["engine"] = dict(PLATFORM_ENGINE)
    m["summary"] = dict(PLATFORM_SUMMARY)
    return m


def wind_job_body(geometry: bytes, ids: bytes | None, **params) -> dict:
    files = {"geometry": sha(geometry)}
    if ids is not None:
        files["entities"] = sha(ids)
    return {"kind": "wind", "inputs": {"upload_id": None, "files": files}, "params": {**APP_PARAMS, **params}}


def send(client, headers: dict, body: dict):
    return client.post("/jobs", json=body, headers={**headers, **RJ12, "Idempotency-Key": hex32()})


def ok(res) -> dict:
    assert res.status_code == 201, res.text
    return res.json()


def field_of(err: dict) -> str:
    return err["data"]["fields"][0]["field"]


def stl_of(tris: list) -> bytes:
    out = bytearray(b"pf11c".ljust(80, b" ")) + struct.pack("<I", len(tris))
    for t in tris:
        out += struct.pack("<3f", 0, 0, 0) + b"".join(struct.pack("<3f", *v) for v in t) + struct.pack("<H", 0)
    return bytes(out)


def tris_of(stl: bytes) -> list:
    n = struct.unpack_from("<I", stl, 80)[0]
    out = []
    for i in range(n):
        v = struct.unpack_from("<12f", stl, 84 + 50 * i)
        out.append((tuple(v[3:6]), tuple(v[6:9]), tuple(v[9:12])))
    return out


def rooms_doc() -> dict:
    """Two rooms on the app geometry's footprint (x -0.15..26.15, y -0.15..9.15):
    a window on the south facade from the living room, a door to the hall, and a
    window on the north facade written as the app writes side 0 -> side 1 (from
    outside into the hall); none carries cp, so the wind job's facade Cp applies."""
    return {
        "schema": "truebex-airflow-rooms/1",
        "rooms": [
            {"id": LIVING, "name": "Living", "volume_m3": 48.6, "floor_z_m": 0.0},
            {"id": HALL, "name": "Hall", "volume_m3": 20.0, "floor_z_m": 0.0},
        ],
        "openings": [
            {"id": O_SOUTH, "from": LIVING, "to": "outside", "area_m2": 1.6, "cd": 0.6, "z_m": 1.05,
             "centre_m": [5.0, -0.15, 1.05], "normal": [0.0, -1.0, 0.0]},
            {"id": O_DOOR, "from": LIVING, "to": HALL, "area_m2": 1.8, "cd": 0.6, "z_m": 1.05,
             "centre_m": [8.0, 4.5, 1.05], "normal": [1.0, 0.0, 0.0]},
            {"id": O_NORTH, "from": "outside", "to": HALL, "area_m2": 1.2, "cd": 0.6, "z_m": 1.05,
             "centre_m": [12.0, 9.15, 1.05], "normal": [0.0, -1.0, 0.0]},
        ],
        "rho_kg_m3": 1.2,
    }


def airflow_body(wind_job_id: str, rooms: bytes, **params) -> dict:
    base = {"wind_job_id": wind_job_id, "speed_ms": 5, "direction_deg": 225, "reference_height_m": 10, "terrain": "suburban",
            "velocity_height_m": 1.1}
    return {"kind": "airflow", "inputs": {"upload_id": None, "files": {"rooms": sha(rooms)}}, "params": {**base, **params}}


def as_bytes(doc: dict) -> bytes:
    return json.dumps(doc).encode("utf-8")


@pytest.fixture()
def rig(client):
    a = Person(client, "a@example.com")  # a Pro trial: holds analysis.reports
    adm = admin(client)
    token = issue_worker(client, adm, name="cpu-eu-01", kinds=KINDS, cls="cpu-8")
    geometry, ids = app_file("wind-geometry.bin"), app_file("wind-entities.bin")
    put_inputs(client, a.dev, geometry, ids)
    return {"a": a, "admin": adm, "token": token, "geometry": geometry, "ids": ids}


def wind_claim(client, token: str, worker_id: str = "cpu-eu-01", kinds=KINDS) -> dict:
    return claimed(client, token, worker_id=worker_id, kinds=kinds, doc_version_max=0)


def complete_wind(client, token: str, c: dict) -> dict:
    _send_outputs(client, token, c, app_arrays())
    res = _complete(client, token, c, platform_result(c), wall_s=600)
    assert res.status_code == 200, res.text
    return res.json()


# --- the folder is the app's 169 files ----------------------------------------------------------


def test_pf11c_contract_folder_is_the_apps_169_files():
    """tests/contracts/render-jobs/ holds the app's 14 files, its 155 tiles and the
    platform's README, each the app's blob at bcdd021f1; the tiles tree did not move."""
    top = {p.name for p in FIX.iterdir() if p.is_file()}
    assert top == set(APP_BLOBS) | {"README.md"} and len(APP_BLOBS) == 14
    assert {k: v for k, v in APP_BLOBS.items() if k.startswith("wind-")} == WIND_BLOBS
    for name, blob in WIND_BLOBS.items():
        data = app_file(name)
        assert git_blob_id(data) == blob, name
        if name.endswith(".json"):
            assert b"\r" not in data, name  # the blob's LF, not the app checkout's CRLF
    assert len(APP_BLOBS) + APP_TILES == 169
    assert git_tree_id(FIX / "tiles") == APP_TILES_TREE == "3d5a9f35f7e47390668218e5934893c7aa3e3d1b"
    readme = (FIX / "README.md").read_text(encoding="utf-8")
    assert APP_COMMIT[:9] in readme and APP_FOLDER_COMMIT[:9] in readme and "1.2.0" in readme
    for name in WIND_BLOBS:
        assert f"`{name}`" in readme, name
    # The arrays are named by role in the folder and by SHA-256 in the result.
    result = app_result()
    names = {hashlib.sha256(app_file(n)).hexdigest(): n for n in WIND_BLOBS if n.endswith(".bin")}
    assert {sha: f["url"] for sha, f in result["files"].items()} == {s: n for s, n in names.items() if n != "wind-geometry.bin"}
    assert len(tris_of(app_file("wind-geometry.bin"))) == 156 == len(app_file("wind-entities.bin")) // 16


@pytest.mark.skipif(not (APP_REPO / ".git").exists(), reason="the app repository is not on this machine")
def test_pf11c_recorded_blobs_are_the_apps_at_the_commit():
    out = subprocess.run(
        ["git", "ls-tree", "-r", APP_COMMIT, "--", f"{APP_DIR}/"], cwd=APP_REPO, capture_output=True, text=True, timeout=60
    )
    if out.returncode != 0:
        pytest.skip(f"git ls-tree failed: {out.stderr.strip()}")
    listed = {}
    for line in out.stdout.splitlines():
        mode_type_id, path = line.split("\t", 1)
        listed[path[len(APP_DIR) + 1 :]] = mode_type_id.split()[2]
    assert len(listed) == 169
    assert {k: v for k, v in listed.items() if not k.startswith("tiles/")} == APP_BLOBS
    tree = subprocess.run(["git", "rev-parse", f"{APP_COMMIT}:{APP_DIR}"], cwd=APP_REPO, capture_output=True, text=True, timeout=60)
    assert tree.stdout.strip() == APP_FOLDER_TREE


# --- contract §10: test_wind_inputs_and_outputs -------------------------------------------------


def test_wind_inputs_and_outputs(client, rig):
    """A wind job needs `entities` (16 bytes a triangle) and one closed geometry of at
    most 200 000 triangles; 1.2's params are stored and echoed; a result whose
    pressure_coefficient count differs from the triangles is refused; the app's own
    result (with a platform worker's engine and summary) passes §6.3's layout, and
    5.5 answers its files map."""
    a, token, geometry, ids = rig["a"], rig["token"], rig["geometry"], rig["ids"]
    octa = octahedron_stl()
    put_inputs(client, a.dev, octa, entities(8), entities(7))
    # entities is required, at 16 bytes per triangle.
    err = error_of(send(client, a.dev, wind_job_body(octa, None)), 422, "validation_failed")
    assert field_of(err) == "inputs.files.entities"
    err = error_of(send(client, a.dev, wind_job_body(octa, entities(7))), 422, "validation_failed")
    assert field_of(err) == "inputs.files.entities" and err["data"]["triangles"] == 8
    # An open geometry: the octahedron with one triangle removed leaves 3 edges on one triangle.
    open_octa = stl_of(tris_of(octa)[:-1])
    put_inputs(client, a.dev, open_octa)
    err = error_of(send(client, a.dev, wind_job_body(open_octa, entities(7))), 422, "validation_failed")
    assert field_of(err) == "inputs.files.geometry" and err["data"]["open_edges"] == 3
    # Over 200 000 triangles (refused by its count, before a triangle is read).
    n = 200_001
    big = b"pf11c big".ljust(80, b" ") + struct.pack("<I", n) + bytes(50 * n)
    put_inputs(client, a.dev, big, entities(1))
    err = error_of(send(client, a.dev, wind_job_body(big, entities(1))), 422, "validation_failed")
    assert field_of(err) == "inputs.files.geometry" and err["data"]["triangles"] == n and "200000" in err["detail"]

    # 1.2's three params: validated, stored with their defaults, echoed to the worker.
    bare = wind_job_body(octa, entities(8))
    for key in ("pedestrian_height_m", "grid_cell_mm", "turbulence_model"):
        bare["params"].pop(key)
    default = ok(send(client, a.dev, bare))
    chosen = ok(send(client, a.dev, wind_job_body(octa, entities(8), pedestrian_height_m=2.0, grid_cell_mm=500, turbulence_model="komega_sst")))
    for params, key in (({"pedestrian_height_m": 0.4}, "pedestrian_height_m"), ({"pedestrian_height_m": 10.5}, "pedestrian_height_m"),
                        ({"grid_cell_mm": 99}, "grid_cell_mm"), ({"grid_cell_mm": 10_001}, "grid_cell_mm"),
                        ({"turbulence_model": "k_epsilon"}, "turbulence_model"), ({"terrain": "country"}, "terrain")):
        err = error_of(send(client, a.dev, wind_job_body(octa, entities(8), **params)), 422, "validation_failed")
        assert field_of(err) == f"params.{key}", params
    # Terrain is EN 1991-1-4's five: 'lake' is category I (z0 0.01), 'open' category II (z0 0.05).
    lake = ok(send(client, a.dev, wind_job_body(octa, entities(8), terrain="lake")))
    open_ = ok(send(client, a.dev, wind_job_body(octa, entities(8), terrain="open")))
    seen = {}
    for _ in range(4):
        c = wind_claim(client, token)
        seen[c["job"]["job_id"]] = c
        client.post(f"/workers/jobs/{c['job']['job_id']}/fail", json={"lease_id": c["lease_id"], "code": "bad_input", "message": "test", "retryable": False}, headers=wk(token))
    p_default = seen[default["job_id"]]["job"]["params"]
    assert (p_default["pedestrian_height_m"], p_default["grid_cell_mm"], p_default["turbulence_model"]) == (1.5, 1000, "realizable_ke")
    p_chosen = seen[chosen["job_id"]]["job"]["params"]
    assert (p_chosen["pedestrian_height_m"], p_chosen["grid_cell_mm"], p_chosen["turbulence_model"]) == (2.0, 500, "komega_sst")
    for rec, terrain, z0, category in ((lake, "lake", 0.01, "I"), (open_, "open", 0.05, "II")):
        c = seen[rec["job_id"]]
        assert c["job"]["params"]["terrain"] == terrain
        assert c["job"]["profile"]["terrain"][terrain] == {"z0_m": z0, "category": category}
    assert set(seen[lake["job_id"]]["job"]["profile"]["terrain"]) == {"sea", "lake", "open", "suburban", "urban"}

    # The app's own export (156 triangles) under the app's CL0 project id at sequence 0.
    result = app_result()
    body = {**wind_job_body(geometry, ids), "project_id": result["project_id"], "at_seq": 0}
    rec = ok(send(client, a.dev, body))
    assert rec["project_id"] == result["project_id"] and rec["at_seq"] == 0
    c = wind_claim(client, token)
    assert c["job"]["job_id"] == rec["job_id"] and c["job"]["params"] == APP_PARAMS
    _send_outputs(client, token, c, app_arrays())
    # The stub's answer as it is: engine.image null, a summary of one key.
    errors = error_of(_complete(client, token, c, {**app_result(), "params": c["job"]["params"]}), 422, "output_invalid")["data"]["errors"]
    paths = {e["path"] for e in errors}
    assert "engine" in paths and {"summary.max_speed_ratio", "summary.iterations", "summary.residual"} <= paths
    # A pressure_coefficient count other than the 156 triangles.
    m = platform_result(c)
    m["fields"][0]["count"] = 155
    errors = error_of(_complete(client, token, c, m), 422, "output_invalid")["data"]["errors"]
    assert any(e["path"] == "fields[0].count" and e.get("expected") == 156 for e in errors)
    # A velocity grid of one component breaks 6.3's layout (3 x float32 a cell).
    m = platform_result(c)
    m["grids"][1]["components"] = 1
    errors = error_of(_complete(client, token, c, m), 422, "output_invalid")["data"]["errors"]
    assert any(e["path"].startswith("grids[1]") for e in errors)
    # The layout the app's grids follow: origin = the centre of cell (0, 0), 3 H beyond the bounds.
    tris = tris_of(geometry)
    lo = [min(v[k] for t in tris for v in t) for k in range(3)]
    hi = [max(v[k] for t in tris for v in t) for k in range(3)]
    margin = 3 * hi[2]
    for g in result["grids"]:
        assert g["cell_mm"] == 1000 and g["origin_mm"][2] == 1500
        assert math.isclose(g["origin_mm"][0], (lo[0] - margin + 0.5) * 1000, abs_tol=1e-3)
        assert math.isclose(g["origin_mm"][1], (lo[1] - margin + 0.5) * 1000, abs_tol=1e-3)
        size = len(app_file({"speed_ratio": "wind-speed_ratio.bin", "velocity": "wind-velocity.bin", "comfort_lawson": "wind-comfort_lawson.bin"}[g["name"]]))
        assert size == g["nx"] * g["ny"] * g.get("components", 1) * (1 if g["unit"] == "class" else 4)
    done = _complete(client, token, c, platform_result(c), wall_s=600)
    assert done.status_code == 200, done.text
    assert done.json()["state"] == "succeeded" and done.json()["cost_units"] == 2.5

    # 5.5: the top-level files map the app reads, {sha256: {url, bytes}} for the five arrays.
    out = client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a))
    assert out.status_code == 200 and out.headers["X-Truebex-Contract"] == ECHO
    data = out.json()
    sizes = {hashlib.sha256(b).hexdigest(): len(b) for b in app_arrays()}
    assert set(data["files"]) == set(sizes)
    for digest, f in data["files"].items():
        assert set(f) == {"url", "bytes"} and f["bytes"] == sizes[digest]
        got = client.get(f["url"])
        assert got.status_code == 200 and hashlib.sha256(got.content).hexdigest() == digest
    assert set(data["urls"]) == set(sizes) and data["urls_expire_at"]  # kept beside it (PF11's readers)
    assert [g["name"] for g in data["grids"]] == ["speed_ratio", "velocity", "comfort_lawson"]
    assert data["engine"] == PLATFORM_ENGINE and data["summary"] == PLATFORM_SUMMARY


def test_pf11c_shipping_names_in_any_case(client, rig):
    """A packaged app writes FNames as the name table holds them ("Wind",
    "Standard", "Suburban"): the analysis kinds read them without case and store
    them lower-case."""
    a = rig["a"]
    body = wind_job_body(rig["geometry"], rig["ids"], terrain="Suburban", comfort="Lawson", turbulence_model="Realizable_KE")
    rec = ok(send(client, a.dev, {**body, "kind": "Wind", "quality": "Standard"}))
    assert rec["kind"] == "wind" and rec["quality"] == "standard"
    c = wind_claim(client, rig["token"])
    assert (c["job"]["params"]["terrain"], c["job"]["params"]["comfort"], c["job"]["params"]["turbulence_model"]) == ("suburban", "lawson", "realizable_ke")


# --- quality picks the mesh -------------------------------------------------------------------------


def test_pf11c_quality_picks_the_mesh(client, rig):
    """draft, standard and high reach the claim's profile as 6, 10 or 20 cells per
    building side and move the estimate; anything else is 422 on quality."""
    a, token = rig["a"], rig["token"]
    octa = octahedron_stl()
    put_inputs(client, a.dev, octa, entities(8))
    estimates = {}
    for quality in ("draft", "standard", "high"):
        rec = ok(send(client, a.dev, {**wind_job_body(octa, entities(8)), "quality": quality}))
        assert rec["quality"] == quality
        estimates[quality] = rec["cost_units_estimate"]
        c = wind_claim(client, token)
        assert c["job"]["quality"] == quality
        assert c["job"]["profile"]["cells_per_side"] == {"draft": 6, "standard": 10, "high": 20}[quality]
        client.post(f"/workers/jobs/{c['job']['job_id']}/fail", json={"lease_id": c["lease_id"], "code": "bad_input", "message": "t", "retryable": False}, headers=wk(token))
    # The octahedron (10 m wide, 7 m high): about 0.44 M, 2.06 M and (capped) 8 M cells at 1000 iterations.
    assert estimates == {"draft": 3.1, "standard": 7.8, "high": 25.1}
    err = error_of(send(client, a.dev, {**wind_job_body(octa, entities(8)), "quality": "ultra"}), 422, "validation_failed")
    assert field_of(err) == "quality"
    assert ok(send(client, a.dev, wind_job_body(octa, entities(8))))["quality"] == "standard"  # the default


# --- §6.5.1 the reference ------------------------------------------------------------------------


def test_pf11c_reference_is_recorded(client, rig):
    """project_id / at_seq name what was computed: a CL0 document id, another
    person's project or a deleted one is recorded as given (no 404, no hint); only
    a cloud project the caller can view is checked against its head (409
    `seq_ahead`). An analysis job never opens a snapshot."""
    a, token, geometry, ids = rig["a"], rig["token"], rig["geometry"], rig["ids"]
    doc_id = hex32()
    rec = ok(send(client, a.dev, {**wind_job_body(geometry, ids), "project_id": doc_id, "at_seq": 0}))
    assert (rec["project_id"], rec["at_seq"]) == (doc_id, 0)
    assert ok(send(client, a.dev, {**wind_job_body(geometry, ids), "project_id": hex32(), "at_seq": 41}))["at_seq"] == 41
    pid, head = project(client, a)
    err = error_of(send(client, a.dev, {**wind_job_body(geometry, ids), "project_id": pid, "at_seq": head + 5}), 409, "seq_ahead")
    assert err["data"]["head_seq"] == head
    mine = ok(send(client, a.dev, {**wind_job_body(geometry, ids), "project_id": pid, "at_seq": head}))
    b = Person(client, "b@example.com")
    b_pid, b_head = project(client, b)
    theirs = send(client, a.dev, {**wind_job_body(geometry, ids), "project_id": b_pid, "at_seq": b_head + 100})
    assert theirs.status_code == 201, theirs.text
    assert theirs.json()["project_id"] == b_pid and theirs.json()["at_seq"] == b_head + 100
    gone, _ = project(client, a)
    assert client.delete(f"/projects/{gone}", headers=a.web).status_code == 204
    assert ok(send(client, a.dev, {**wind_job_body(geometry, ids), "project_id": gone, "at_seq": 0}))["project_id"] == gone
    for bad in ("nope", "F" * 32):
        err = error_of(send(client, a.dev, {**wind_job_body(geometry, ids), "project_id": bad}), 422, "validation_failed")
        assert field_of(err) == "project_id"
    # A worker that reads no document version takes them all: none opens a snapshot.
    claimed_ids = set()
    for _ in range(5):
        c = wind_claim(client, token)
        assert c["inputs"]["snapshot"] is None and c["inputs"]["ops_url"] is None
        assert set(c["inputs"]["files"]) == {"geometry", "entities"}
        claimed_ids.add(c["job"]["job_id"])
        client.post(f"/workers/jobs/{c['job']['job_id']}/fail", json={"lease_id": c["lease_id"], "code": "bad_input", "message": "t", "retryable": False}, headers=wk(token))
    assert {rec["job_id"], mine["job_id"], theirs.json()["job_id"]} <= claimed_ids
    with SessionLocal() as db:
        assert {j.doc_version_needed for j in db.query(RenderJob).filter(RenderJob.kind == "wind")} == {0}
    # /v1 lists the job under the id it was recorded with.
    key = make_key(client, a.session, ALL_SCOPES)
    listed = client.get("/v1/jobs", params={"project_id": doc_id}, headers=kh(key, **RJ12)).json()["jobs"]
    assert [j["job_id"] for j in listed] == [rec["job_id"]]


# --- contract §10: test_airflow_kind ---------------------------------------------------------------


def test_airflow_kind(client, rig, tmp_path):
    """`rooms` is validated (one case per rule), the interior CFD geometry is not
    taken yet, and the orifice network answers: air_changes per room in the rooms'
    order, a two-opening room within 1 % of the hand calculation, an opening without
    cp at the wind job's nearest triangle, opening_flow signed from -> to."""
    from app.analysis.runners import airflow

    a = rig["a"]
    wind = ok(send(client, a.dev, wind_job_body(rig["geometry"], rig["ids"])))
    good = as_bytes(rooms_doc())
    put_inputs(client, a.dev, good)
    assert ok(send(client, a.dev, airflow_body(wind["job_id"], good)))["kind"] == "airflow"

    def broken(edit) -> dict:
        doc = rooms_doc()
        edit(doc)
        data = as_bytes(doc) if isinstance(doc, dict) else doc
        put_inputs(client, a.dev, data)
        return error_of(send(client, a.dev, airflow_body(wind["job_id"], data)), 422, "validation_failed")

    def op(i, **kv):
        return lambda d: d["openings"][i].update(kv)

    def room(i, **kv):
        return lambda d: d["rooms"][i].update(kv)

    cases = {
        "schema": lambda d: d.update(schema="truebex-acoustics-rooms/1"),
        "rooms": lambda d: d.update(rooms=[]),
        "rooms[0].id": room(0, id="living"),
        "rooms[1].id": room(1, id=LIVING),
        "rooms[0].volume_m3": room(0, volume_m3=0),
        "rooms[1].floor_z_m": room(1, floor_z_m="ground"),
        "openings": lambda d: d.update(openings={"a": 1}),
        "openings[0].id": op(0, id="w1"),
        "openings[0].from": op(0, **{"from": hex32()}),
        "openings[1].to": op(1, to="garden"),
        "openings[1].to ": op(1, to=LIVING),
        "openings[2].from ": op(2, to="outside"),
        "openings[0].area_m2": op(0, area_m2=0),
        "openings[1].cd": op(1, cd=0),
        "openings[1].cd ": op(1, cd=1.2),
        "openings[0].centre_m": op(0, centre_m=[5.0, -0.15]),
        "openings[0].normal": op(0, normal=[0.0, 0.0, 0.0]),
        "openings[1].cp": op(1, cp=0.4),
        "openings[0].cp": op(0, cp="high"),
        "rho_kg_m3": lambda d: d.update(rho_kg_m3=0),
    }
    for path, edit in cases.items():
        err = broken(edit)
        assert field_of(err) == "inputs.files.rooms", path
        assert path.strip() in err["detail"], (path, err["detail"])
    for raw in (b"not json", b"[1, 2]"):
        put_inputs(client, a.dev, raw)
        err = error_of(send(client, a.dev, airflow_body(wind["job_id"], raw)), 422, "validation_failed")
        assert field_of(err) == "inputs.files.rooms"
    # The interior CFD run (inputs.files.geometry) is not offered yet; rooms is required.
    with_geo = airflow_body(wind["job_id"], good)
    with_geo["inputs"]["files"]["geometry"] = sha(rig["geometry"])
    err = error_of(send(client, a.dev, with_geo), 422, "validation_failed")
    assert field_of(err) == "inputs.files.geometry" and "not available yet" in err["detail"]
    no_rooms = airflow_body(wind["job_id"], good)
    no_rooms["inputs"]["files"] = {}
    assert field_of(error_of(send(client, a.dev, no_rooms), 422, "validation_failed")) == "inputs.files.rooms"
    for params, key in (({"wind_job_id": "x"}, "wind_job_id"), ({"velocity_height_m": 0.1}, "velocity_height_m"),
                        ({"speed_ms": 0}, "speed_ms"), ({"terrain": "country"}, "terrain")):
        body = airflow_body(wind["job_id"], good)
        body["params"].update(params)
        err = error_of(send(client, a.dev, body), 422, "validation_failed")
        assert field_of(err) == f"params.{key}", params

    # The network: one room, two windows to outside at Cp 0.6 and -0.3, the same Cd and area.
    q = 0.5 * 1.2 * 5.0**2
    one = {
        "schema": "truebex-airflow-rooms/1",
        "rooms": [{"id": LIVING, "name": "Living", "volume_m3": 50.0, "floor_z_m": 0.0}],
        "openings": [
            {"id": O_SOUTH, "from": LIVING, "to": "outside", "area_m2": 1.0, "cd": 0.6, "centre_m": [0, -1, 1], "normal": [0, -1, 0], "cp": 0.6},
            {"id": O_NORTH, "from": LIVING, "to": "outside", "area_m2": 1.0, "cd": 0.6, "centre_m": [0, 1, 1], "normal": [0, 1, 0], "cp": -0.3},
        ],
    }
    net = airflow.network(one)
    assert net.rho == 1.2  # the default
    sol = airflow.solve(net, airflow.outside_cps(net, [], []), q)
    hand = math.sqrt(2 * 0.9 * q / 1.2) / math.sqrt(1 / 0.6**2 + 1 / 0.6**2)
    assert abs(sol.flows[1] - hand) / hand < 0.01  # out through the leeward window: from -> to positive
    assert abs(sol.flows[0] + hand) / hand < 0.01  # in through the windward one: negative from -> to
    assert abs(sol.ach[0] - hand * 3600 / 50.0) / (hand * 3600 / 50.0) < 0.01
    flipped = copy.deepcopy(one)
    flipped["openings"][0].update({"from": "outside", "to": LIVING, "normal": [0, 1, 0]})
    assert math.isclose(airflow.solve(airflow.network(flipped), airflow.outside_cps(airflow.network(flipped), [], []), q).flows[0], -sol.flows[0], rel_tol=1e-6)

    # No cp: the wind job's Cp at the triangle (facing the opening) whose centroid is nearest.
    tris = tris_of(rig["geometry"])
    cp = list(struct.unpack("<156f", app_file("wind-pressure_coefficient.bin")))
    net = airflow.network(rooms_doc())
    cps = airflow.outside_cps(net, tris, cp)
    assert cps[1] is None  # the door is inside
    for i, opening in ((0, rooms_doc()["openings"][0]), (2, rooms_doc()["openings"][2])):
        outward = [-x for x in opening["normal"]] if opening["from"] == "outside" else opening["normal"]
        facing = [k for k, t in enumerate(tris) if _dot(_unit(_normal(t)), outward) >= 0.5] or list(range(len(tris)))
        nearest = min(facing, key=lambda k: _dist2(_centroid(tris[k]), opening["centre_m"]))
        assert cps[i] == cp[nearest]
    sol = airflow.solve(net, cps, q)
    # air_changes in the rooms' order: each room's inflow x 3600 / its volume.
    inflow = [0.0, 0.0]
    for k, (src, dst) in enumerate(((0, None), (0, 1), (None, 1))):
        f = sol.flows[k]
        if f > 0 and dst is not None:
            inflow[dst] += f
        if f < 0 and src is not None:
            inflow[src] -= f
    assert sol.ach == pytest.approx([inflow[0] * 3600 / 48.6, inflow[1] * 3600 / 20.0], rel=1e-9)
    assert sol.converged and abs(sum(sol.flows[k] * s for k, s in ((0, -1), (1, -1)))) < 1e-6  # the living room balances

    # The runner's result: air_changes on spaces, opening_flow on openings, a 1.1 m velocity grid, all through §6.3.
    from app.analysis import results
    from app.analysis.runners import common

    from .test_analysis_runners import _job

    job_dir = tmp_path / "airflow"
    pressure = app_file("wind-pressure_coefficient.bin")
    j = _job(job_dir, "airflow", {"wind_job_id": wind["job_id"], "speed_ms": 5, "direction_deg": 225, "reference_height_m": 10,
                                  "terrain": "suburban", "velocity_height_m": 1.1},
             inputs={"rooms": good, "wind_geometry": rig["geometry"], "wind_pressure_coefficient": pressure})
    assert common.main(airflow.run, [str(job_dir)]) == 0
    result = json.loads((job_dir / "out" / "result.json").read_text("utf-8"))
    assert [(f["name"], f["unit"], f["on"], f["count"]) for f in result["fields"]] == [("air_changes", "1/h", "spaces", 2), ("opening_flow", "m3/s", "openings", 3)]
    assert (job_dir / "out" / result["fields"][0]["entities"]).read_bytes() == bytes.fromhex(LIVING) + bytes.fromhex(HALL)
    assert (job_dir / "out" / result["fields"][1]["entities"]).read_bytes() == b"".join(bytes.fromhex(o) for o in (O_SOUTH, O_DOOR, O_NORTH))
    flows = common.unpack_f32((job_dir / "out" / result["fields"][1]["values"]).read_bytes())
    assert flows == pytest.approx(sol.flows, rel=1e-5, abs=1e-7)
    grid = result["grids"][0]
    assert (grid["name"], grid["unit"], grid["components"], grid["origin_mm"][2]) == ("velocity", "m/s", 3, 1100.0)
    values = common.unpack_f32((job_dir / "out" / grid["values"]).read_bytes())
    assert len(values) == grid["nx"] * grid["ny"] * 3
    door = rooms_doc()["openings"][1]
    i = round((door["centre_m"][0] * 1000 - grid["origin_mm"][0]) / grid["cell_mm"])
    k = round((door["centre_m"][1] * 1000 - grid["origin_mm"][1]) / grid["cell_mm"])
    cell = values[3 * (i + k * grid["nx"]) : 3 * (i + k * grid["nx"]) + 3]
    assert cell == pytest.approx([sol.flows[1] / 1.8, 0.0, 0.0], rel=1e-5)
    assert sum(1 for v in values[0::3] if math.isnan(v)) == grid["nx"] * grid["ny"] - 3
    assert result["engine"]["name"] == "truebex-airflow" and result["engine"]["image"] == "truebex-analysis-airflow:1"
    job_row = type("J", (), {"job_id": wind["job_id"], "kind": "airflow", "project_id": None, "at_seq": 0, "params": j.params,
                             "inputs": {"rooms": 2, "openings": 3}})()
    assert results.check(result, job_row) == []


def _normal(t):
    u = [t[1][k] - t[0][k] for k in range(3)]
    w = [t[2][k] - t[0][k] for k in range(3)]
    return [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _centroid(t):
    return [sum(v[k] for v in t) / 3 for k in range(3)]


def _dist2(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


# --- the airflow job on the queue ---------------------------------------------------------------


def test_pf11c_airflow_waits_for_its_wind_job(client, rig, tmp_path):
    """Submitted beside its queued wind job, an airflow job is claimed only once the
    wind job succeeded; its claim carries the wind job's geometry and Cp, signed;
    the real runner completes it and 5.5 answers its files map."""
    from app.analysis.runners import airflow, common

    a, token = rig["a"], rig["token"]
    rooms = as_bytes(rooms_doc())
    put_inputs(client, a.dev, rooms)
    wind = ok(send(client, a.dev, wind_job_body(rig["geometry"], rig["ids"])))
    air = ok(send(client, a.dev, airflow_body(wind["job_id"], rooms)))
    assert air["state"] == "queued" and air["class"] == "cpu-8" and air["base_job_id"] == wind["job_id"]
    assert air["message"] and air["cost_units_estimate"] == 0.3
    second = issue_worker(client, rig["admin"], name="cpu-eu-02", kinds=("airflow",), cls="cpu-8")
    assert claim(client, second, worker_id="cpu-eu-02", kinds=("airflow",), doc_version_max=0).status_code == 204
    c = wind_claim(client, token)
    assert c["job"]["job_id"] == wind["job_id"]  # the older job, and the only one claimable
    assert client.post(f"/workers/jobs/{c['job']['job_id']}/heartbeat", json={"lease_id": c["lease_id"], "progress": 0.5, "message": "solving"}, headers=wk(token)).status_code == 200
    assert claim(client, second, worker_id="cpu-eu-02", kinds=("airflow",), doc_version_max=0).status_code == 204
    rev = job(client, rj(a), air["job_id"])["rev"]
    complete_wind(client, token, c)
    waiting = job(client, rj(a), air["job_id"])
    assert waiting["state"] == "queued" and waiting["rev"] > rev and waiting["message"] == ""  # told, not yet claimed
    ca = claimed(client, second, worker_id="cpu-eu-02", kinds=("airflow",), doc_version_max=0)
    assert ca["job"]["job_id"] == air["job_id"] and ca["job"]["params"]["wind_job_id"] == wind["job_id"]
    assert ca["job"]["profile"]["image"] == "truebex-analysis-airflow:1"
    files = ca["inputs"]["files"]
    assert set(files) == {"rooms", "wind_geometry", "wind_pressure_coefficient"}
    pressure = app_file("wind-pressure_coefficient.bin")
    assert files["wind_pressure_coefficient"] == {**files["wind_pressure_coefficient"], "sha256": sha(pressure), "bytes": len(pressure)}
    # The worker: download the signed inputs, run the runner, upload, complete.
    job_dir = tmp_path / "job"
    (job_dir / "inputs").mkdir(parents=True)
    (job_dir / "out").mkdir()
    for name, entry in files.items():
        got = client.get(entry["url"])
        assert got.status_code == 200 and sha(got.content) == entry["sha256"]
        (job_dir / "inputs" / name).write_bytes(got.content)
    (job_dir / "job.json").write_text(json.dumps({
        "schema": "truebex-analysis-job/1", "job_id": ca["job"]["job_id"], "kind": "airflow", "project_id": ca["job"]["project_id"],
        "at_seq": ca["job"]["at_seq"], "params": ca["job"]["params"], "profile": ca["job"]["profile"],
        "inputs": {name: f"/job/inputs/{name}" for name in files}, "out_dir": "/job/out",
    }), encoding="utf-8")
    assert common.main(airflow.run, [str(job_dir)]) == 0
    result = json.loads((job_dir / "out" / "result.json").read_text("utf-8"))
    arrays = [p.read_bytes() for p in (job_dir / "out").iterdir() if len(p.name) == 64]
    _send_outputs(client, second, ca, arrays)
    done = _complete(client, second, ca, result, wall_s=12)
    assert done.status_code == 200, done.text
    assert done.json()["state"] == "succeeded" and done.json()["cost_units"] == 0.1
    out = client.get(f"/jobs/{air['job_id']}/output", headers=rj(a)).json()
    assert set(out["files"]) == {sha(b) for b in arrays} and all(f["bytes"] == len(next(b for b in arrays if sha(b) == s)) for s, f in out["files"].items())
    assert [f["name"] for f in out["fields"]] == ["air_changes", "opening_flow"]
    usage = client.get("/jobs/usage", headers=rj(a)).json()
    assert usage["by_kind"] == {"airflow": 0.1, "wind": 2.5}


def test_pf11c_airflow_fails_with_its_wind_job(client, rig):
    """When the wind job fails, is cancelled or expires, the airflow job waiting on
    it ends failed with bad_input, at no charge."""
    a, token = rig["a"], rig["token"]
    rooms = as_bytes(rooms_doc())
    put_inputs(client, a.dev, rooms)

    def pair() -> tuple[dict, dict]:
        wind = ok(send(client, a.dev, wind_job_body(rig["geometry"], rig["ids"])))
        return wind, ok(send(client, a.dev, airflow_body(wind["job_id"], rooms)))

    def ended(air: dict) -> dict:
        rec = job(client, rj(a), air["job_id"])
        assert rec["state"] == "failed" and rec["error"]["code"] == "bad_input" and rec["cost_units"] is None, rec
        assert rec["finished_at"] and rec["rev"] > air["rev"]
        return rec

    # Failed (a bad_input is not retried).
    wind, air = pair()
    c = wind_claim(client, token)
    assert c["job"]["job_id"] == wind["job_id"]
    res = client.post(f"/workers/jobs/{wind['job_id']}/fail", json={"lease_id": c["lease_id"], "code": "bad_input", "message": "open shell", "retryable": False}, headers=wk(token))
    assert res.json()["state"] == "failed"
    assert "failed" in ended(air)["error"]["message"]
    # Cancelled while queued.
    wind, air = pair()
    assert client.post(f"/jobs/{wind['job_id']}/cancel", headers=rj(a)).json()["state"] == "cancelled"
    assert "cancelled" in ended(air)["error"]["message"]
    # Expired: queued for 24 h (its airflow job, younger, is not).
    wind, air = pair()
    with SessionLocal() as db:
        row = db.get(RenderJob, wind["job_id"])
        row.queued_at = clock.now() - timedelta(hours=25)
        db.commit()
        assert queue.expire(db, clock.now()) == 1
    assert job(client, rj(a), wind["job_id"])["state"] == "expired"
    assert "expired" in ended(air)["error"]["message"]
    assert claim(client, token, worker_id="cpu-eu-01", kinds=KINDS, doc_version_max=0).status_code == 204
    assert "airflow" not in client.get("/jobs/usage", headers=rj(a)).json()["by_kind"]


def test_pf11c_airflow_names_a_matching_wind_job(client, rig):
    """wind_job_id names a wind job of the caller's own account with the same speed,
    direction, reference height and terrain that has not failed, been cancelled or
    expired; another account's job reads exactly as an unknown id."""
    a, token = rig["a"], rig["token"]
    rooms = as_bytes(rooms_doc())
    put_inputs(client, a.dev, rooms)
    b = Person(client, "b@example.com")
    put_inputs(client, b.dev, rig["geometry"], rig["ids"])
    theirs = ok(send(client, b.dev, wind_job_body(rig["geometry"], rig["ids"])))
    unknown = error_of(send(client, a.dev, airflow_body(hex32(), rooms)), 422, "validation_failed")
    other = error_of(send(client, a.dev, airflow_body(theirs["job_id"], rooms)), 422, "validation_failed")
    assert field_of(other) == field_of(unknown) == "params.wind_job_id"
    assert other["detail"] == unknown["detail"] and other["data"] == unknown["data"]
    south = ok(send(client, a.dev, wind_job_body(rig["geometry"], rig["ids"], direction_deg=180)))
    err = error_of(send(client, a.dev, airflow_body(south["job_id"], rooms)), 422, "validation_failed")
    assert field_of(err) == "params.wind_job_id" and err["data"]["differs"] == ["direction_deg"]
    for params in ({"speed_ms": 6}, {"reference_height_m": 12}, {"terrain": "urban"}):
        err = error_of(send(client, a.dev, airflow_body(south["job_id"], rooms, direction_deg=180, **params)), 422, "validation_failed")
        assert err["data"]["differs"] == list(params), params
    for _ in range(2):  # b's job and the south one
        c = wind_claim(client, token)
        client.post(f"/workers/jobs/{c['job']['job_id']}/fail", json={"lease_id": c["lease_id"], "code": "bad_input", "message": "t", "retryable": False}, headers=wk(token))
    assert job(client, rj(a), south["job_id"])["state"] == "failed"
    err = error_of(send(client, a.dev, airflow_body(south["job_id"], rooms, direction_deg=180)), 422, "validation_failed")
    assert field_of(err) == "params.wind_job_id" and err["data"]["state"] == "failed"


def test_pf11c_worker_runs_the_study_without_docker(client, rig, tmp_path, monkeypatch):
    """The human test's live run, in process: the worker wrapper in container
    mode with server/scripts/local_analysis_docker.py as its docker completes the
    wind job with the app's arrays (its wind stand-in, no OpenFOAM here) and then
    the airflow job with the real runner."""
    from .test_analysis import W, ClientTransport

    monkeypatch.setenv("TRUEBEX_WIND_STAND_IN", str(FIX))
    a, token = rig["a"], rig["token"]
    rooms = as_bytes(rooms_doc())
    put_inputs(client, a.dev, rooms)
    result = app_result()
    wind = ok(send(client, a.dev, {**wind_job_body(rig["geometry"], rig["ids"]), "project_id": result["project_id"], "at_seq": 0}))
    air = ok(send(client, a.dev, {**airflow_body(wind["job_id"], rooms), "project_id": result["project_id"], "at_seq": 0}))
    cfg = W.Config(
        api="http://testserver", token=token, worker_id="cpu-eu-01", kinds=list(KINDS), worker_class="cpu-8",
        work_dir=str(tmp_path / "jobs"), heartbeat_s=0.2, wait_s=0, keep_work=True, mode="container",
        docker=str(ROOT / "server" / "scripts" / "local_analysis_docker.py"),
    )
    lines: list[str] = []
    runner = W.Runner(cfg, W.Api(cfg, transport=ClientTransport(client), sleep=lambda s: None, log=lines.append))
    assert runner.run_once(wait_s=0) == "succeeded", lines
    assert runner.run_once(wait_s=0) == "succeeded", lines
    assert runner.run_once(wait_s=0) is None
    wind_out = client.get(f"/jobs/{wind['job_id']}/output", headers=rj(a)).json()
    assert wind_out["engine"]["name"] == "truebex-stand-in" and wind_out["project_id"] == result["project_id"]
    assert {f["bytes"] for f in wind_out["files"].values()} == {624, 2496, 25632, 76896, 6408}
    air_out = client.get(f"/jobs/{air['job_id']}/output", headers=rj(a)).json()
    assert air_out["engine"] == {"name": "truebex-airflow", "version": "1", "image": "truebex-analysis-airflow:1"}
    assert [(f["name"], f["count"]) for f in air_out["fields"]] == [("air_changes", 2), ("opening_flow", 3)]
    assert len(air_out["files"]) == 5 and all(client.get(f["url"]).status_code == 200 for f in air_out["files"].values())
    # A wind job the stand-in has no answer for fails bad_input (not retried), and so does its airflow job.
    octa = octahedron_stl()
    put_inputs(client, a.dev, octa, entities(8))
    other = ok(send(client, a.dev, wind_job_body(octa, entities(8))))
    waiting = ok(send(client, a.dev, airflow_body(other["job_id"], rooms)))
    assert runner.run_once(wait_s=0) == "failed"
    assert job(client, rj(a), other["job_id"])["error"]["code"] == "bad_input"
    assert job(client, rj(a), waiting["job_id"])["state"] == "failed"


# --- the runners (never running OpenFOAM) -------------------------------------------------------


def _box(x0, y0, x1, y1, h, z0=0.0) -> list:
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z0 + h), (x1, y0, z0 + h), (x1, y1, z0 + h), (x0, y1, z0 + h)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return [t for a_, b_, c_, d_ in quads for t in ((v[a_], v[b_], v[c_]), (v[a_], v[c_], v[d_]))]


WIND = {"speed_ms": 5, "direction_deg": 270, "reference_height_m": 10, "terrain": "lake", "comfort": "lawson",
        "pedestrian_height_m": 1.5, "grid_cell_mm": 1000, "turbulence_model": "realizable_ke"}


def test_pf11c_wind_case_files_by_turbulence_model(tmp_path):
    """realizable k-epsilon by default or k-omega SST; 2000 iterations to 1e-4; the
    Richards and Hoxey inlet from the terrain's z0; rough-wall functions on the
    ground; the background mesh by the quality's cells per building side."""
    from app.analysis import kinds
    from app.analysis.runners import wind

    from .test_analysis_runners import _job

    for model, ras, second, other in (("realizable_ke", "realizableKE", "epsilon", "omega"), ("komega_sst", "kOmegaSST", "omega", "epsilon")):
        job = _job(tmp_path / model, "wind", {**WIND, "turbulence_model": model}, inputs={"geometry": stl_of(_box(-5, -4, 5, 4, 6))},
                   profile=kinds.profile("wind", "standard"))
        mesh = wind.read_stl(job.input("geometry"))
        frame = wind.Frame.for_wind(mesh, 270)
        case_tris = [tuple(frame.to_case(v) for v in t) for t in mesh.triangles]
        files = wind.case_files(job, case_tris, job.profile)
        assert f"RASModel {ras};" in files["constant/turbulenceProperties"]
        assert f"0/{second}" in files and f"0/{other}" not in files
        inlet = {"epsilon": "atmBoundaryLayerInletEpsilon", "omega": "atmBoundaryLayerInletOmega"}[second]
        assert inlet in files[f"0/{second}"] and f"{second}WallFunction" in files[f"0/{second}"]
        assert f"div(phi,{second})" in files["system/fvSchemes"] and f"(U|k|{second})" in files["system/fvSolution"]
        assert "endTime         2000;" in files["system/controlDict"]
        assert f"p 0.0001; U 0.0001; \"(k|{second})\" 0.0001;" in files["system/fvSolution"]
        for f in ("0/U", "0/k", f"0/{second}"):
            assert "z0              uniform 0.01;" in files[f] and "Uref            5;" in files[f] and "Zref            10;" in files[f], f
        assert "atmBoundaryLayerInletVelocity" in files["0/U"] and "atmBoundaryLayerInletK" in files["0/k"]
        assert "ground   { type nutkAtmRoughWallFunction; z0 uniform 0.01;" in files["0/nut"]
        # H = 6 m at 10 cells per side (standard): cells H / 10 over 5 H + 15 H, 5 H each side, 5 H above.
        assert "(217 114 60)" in files["system/blockMeshDict"]
    cells = {}
    for quality in ("draft", "high"):
        profile = kinds.profile("wind", quality)
        job = _job(tmp_path / quality, "wind", WIND, inputs={"geometry": stl_of(_box(-5, -4, 5, 4, 6))}, profile=profile)
        mesh = wind.read_stl(job.input("geometry"))
        cells[quality] = wind.domain([tuple(v for v in t) for t in mesh.triangles], profile).cells
    assert cells == {"draft": (130, 68, 36), "high": (434, 227, 120)}


def test_pf11c_wind_ground_grid_velocity_and_summary(tmp_path):
    """The pedestrian grids: at pedestrian_height_m with cell grid_cell_mm, origin
    the centre of cell (0, 0); the velocity grid turns the case-frame vectors back
    into x east, y north (a wind from 90 degrees blows towards -x); NaN / 255 where
    nothing was sampled; the summary has residual."""
    from app.analysis import kinds, results
    from app.analysis.runners import common, wind

    from .test_analysis_runners import _job, _passes

    params = {**WIND, "direction_deg": 90, "pedestrian_height_m": 2.0, "grid_cell_mm": 1000}
    job = _job(tmp_path, "wind", params, inputs={"geometry": stl_of(_box(-5, -4, 5, 4, 6))}, profile=kinds.profile("wind", "standard"))
    mesh = wind.read_stl(job.input("geometry"))
    grid = wind.ground_grid(mesh, job.profile, job.params)
    assert grid.cell == 1.0 and grid.height == 2.0
    # 3 H (18 m) beyond the bounds, the first cell's centre half a cell in.
    assert grid.origin == (-5 - 18 + 0.5, -4 - 18 + 0.5)
    assert grid.nx == 46 and grid.ny == 44
    points = grid.points(None)
    assert points[0] == (-22.5, -21.5, 2.0) and points[1] == (-21.5, -21.5, 2.0) and points[grid.nx] == (-22.5, -20.5, 2.0)
    frame = wind.Frame.for_wind(mesh, 90)
    east_wind = frame.vector_to_model((5.0, 0.0, 0.0))  # the case's +x is where this wind goes
    assert east_wind == pytest.approx((-5.0, 0.0, 0.0), abs=1e-9)
    north = wind.Frame.for_wind(mesh, 0).vector_to_model((4.0, 0.0, 0.0))
    assert north == pytest.approx((0.0, -4.0, 0.0), abs=1e-9)
    small = wind.Grid((-1.5, -0.5), 1.0, 3, 2, 2.0)
    vectors = [east_wind, (0.0, 3.0, 0.0), None, (-7.5, 0.0, 0.0), (0.0, -9.0, 0.0), (-3.0, 0.0, 0.0)]
    cp = [0.8, -0.5, -1.2, 0.1, 0.0, -0.3] * 2
    info = {"cells": 120000, "iterations": 640, "converged": True, "residual": 8.2e-05}
    result = wind.build_result(job, mesh, cp, small, vectors, None, job.out_dir, info)
    assert [g["name"] for g in result["grids"]] == ["speed_ratio", "velocity", "comfort_lawson"]
    for g in result["grids"]:
        assert g["origin_mm"] == [-1500.0, -500.0, 2000.0] and g["cell_mm"] == 1000.0 and (g["nx"], g["ny"]) == (3, 2)
    vel = next(g for g in result["grids"] if g["name"] == "velocity")
    assert vel["components"] == 3 and vel["unit"] == "m/s"
    values = common.unpack_f32((job.out_dir / vel["values"]).read_bytes())
    assert values[0:3] == pytest.approx([-5.0, 0.0, 0.0], abs=1e-6) and all(math.isnan(x) for x in values[6:9])
    lawson = next(g for g in result["grids"] if g["name"] == "comfort_lawson")
    # LDDC on the instantaneous speed: <= 4 sitting, 6 standing, 8 strolling, 10 business walking, above uncomfortable.
    assert list((job.out_dir / lawson["values"]).read_bytes()) == [1, 0, 255, 2, 3, 0]
    ratio = common.unpack_f32((job.out_dir / result["grids"][0]["values"]).read_bytes())
    assert ratio[0] == pytest.approx(1.0) and math.isnan(ratio[2])
    assert result["summary"] == {"max_speed_ms": 9.0, "max_speed_ratio": 1.8, "iterations": 640, "residual": 8.2e-05,
                                 "min_cp": -1.2, "max_cp": 0.8, "cells": 120000, "converged": 1}
    _passes(result, job, job.out_dir, geometry_triangles=12)
    assert results.check(result, type("J", (), {"job_id": "a" * 32, "kind": "wind", "project_id": None, "at_seq": 0,
                                                "params": job.params, "inputs": {"geometry_triangles": 12}})()) == []
    # The 250 000-point cap coarsens the cell, and the grid says so.
    wide = wind.read_stl(_write(tmp_path / "wide.stl", stl_of(_box(-300, -300, 300, 300, 6))))
    capped = wind.ground_grid(wide, job.profile, {**params, "grid_cell_mm": 500})
    assert capped.nx * capped.ny <= 250_000 and capped.cell > 0.5


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_pf11c_wind_solver_log_residuals():
    """The summary's residual is the largest of the last iteration's initial residuals."""
    from app.analysis.runners import wind

    log = wind.SolverLog()
    for line in (
        "Time = 1", "smoothSolver:  Solving for Ux, Initial residual = 1, Final residual = 0.05, No Iterations 2",
        "GAMG:  Solving for p, Initial residual = 1, Final residual = 0.08, No Iterations 9",
        "Time = 1349", "smoothSolver:  Solving for Ux, Initial residual = 6.1e-05, Final residual = 4e-06, No Iterations 1",
        "smoothSolver:  Solving for Uy, Initial residual = 7.4e-05, Final residual = 4e-06, No Iterations 1",
        "GAMG:  Solving for p, Initial residual = 9.9e-05, Final residual = 9e-06, No Iterations 3",
        "smoothSolver:  Solving for epsilon, Initial residual = 3.2e-05, Final residual = 2e-06, No Iterations 1",
        "smoothSolver:  Solving for k, Initial residual = 4.0e-05, Final residual = 3e-06, No Iterations 1",
        "SIMPLE solution converged in 1349 iterations",
    ):
        log.on_line(line)
    assert (log.iteration, log.converged) == (1349, True)
    assert log.residual == pytest.approx(9.9e-05)


def test_pf11c_wind_surroundings_and_terrain(tmp_path):
    """surroundings are obstacles in the mesh; terrain is a second ground surface,
    and the pedestrian points stand pedestrian_height_m above the terrain triangle
    under them (flat ground at z = 0 where there is none)."""
    from app.analysis import kinds
    from app.analysis.runners import wind

    from .test_analysis_runners import _job

    slope = [((-40, -40, 0), (40, -40, 4), (40, 40, 4)), ((-40, -40, 0), (40, 40, 4), (-40, 40, 0))]
    job = _job(tmp_path, "wind", WIND, inputs={"geometry": stl_of(_box(-5, -4, 5, 4, 6)), "surroundings": stl_of(_box(20, -4, 26, 4, 9)),
                                               "terrain": stl_of(slope)}, profile=kinds.profile("wind", "standard"))
    mesh = wind.read_stl(job.input("geometry"))
    others = wind.read_stl(job.input("surroundings"))
    ground = wind.read_stl(job.input("terrain"))
    frame = wind.Frame.for_wind(mesh, 270)
    to_case = lambda m: [tuple(frame.to_case(v) for v in t) for t in m.triangles]  # noqa: E731
    files = wind.case_files(job, to_case(mesh), job.profile, surroundings=to_case(others), terrain=to_case(ground))
    snappy = files["system/snappyHexMeshDict"]
    assert "surroundings.stl" in snappy and "terrain.stl" in snappy and "building.stl" in snappy
    for name in ("0/U", "0/p", "0/k", "0/epsilon", "0/nut"):
        assert "surroundings" in files[name] and "terrain" in files[name], name
    assert "terrain  { type nutkAtmRoughWallFunction; z0 uniform 0.01;" in files["0/nut"]
    # H is the tallest height (9 m, the surroundings): the domain grows with it.
    dom = wind.domain(to_case(mesh), job.profile, surroundings=to_case(others), terrain=to_case(ground))
    assert dom.h == 9.0 and dom.inside[2] > 9.0 + 4.0
    # Points over the slope: z = the terrain under them + the pedestrian height.
    grid = wind.Grid((0.0, 0.0), 1.0, 2, 1, 1.5)
    pts = grid.points(ground.triangles)
    assert pts[0] == pytest.approx((0.0, 0.0, 2.0 + 1.5)) and pts[1] == pytest.approx((1.0, 0.0, 2.05 + 1.5))
    assert wind.Grid((100.0, 0.0), 1.0, 1, 1, 1.5).points(ground.triangles)[0] == (100.0, 0.0, 1.5)


# --- render-jobs on every route ---------------------------------------------------------------------
# PF6c moved test_pf11c_routes_echo_render_jobs_1_2 and test_pf11c_clients_and_documents_speak_1_2 to
# test_pf6c_render_jobs_1_3.py as test_pf6c_echo_1_3 and test_pf6c_clients_and_documents_speak_1_3: every
# route answers render-jobs/1.3 since 1.3.0 (CL4) and still takes AN3's 1.2 (RJ12).


def test_pf11c_profiles_estimates_and_catalogue(client, rig):
    """The wind profile: EN 1991-1-4's five terrains, Lawson (LDDC) 4 / 6 / 8 / 10 m/s,
    2000 iterations to 1e-4, realizable k-epsilon by default; airflow is in the
    catalogue with its own image and a small fixed estimate."""
    from app.analysis import estimates, kinds

    wind = kinds.PROFILES["wind"]
    assert {t: v["z0_m"] for t, v in wind["terrain"].items()} == {"sea": 0.003, "lake": 0.01, "open": 0.05, "suburban": 0.3, "urban": 1.0}
    assert [v["category"] for v in wind["terrain"].values()] == ["0", "I", "II", "III", "IV"]
    classes = wind["lawson"]["classes"]
    assert [(c["class"], c["name"], c["max_ms"]) for c in classes] == [
        (0, "sitting", 4.0), (1, "standing", 6.0), (2, "strolling", 8.0), (3, "business_walking", 10.0), (4, "uncomfortable", None)]
    assert (wind["iterations_max"], wind["residual_target"]) == (2000, 0.0001)
    assert wind["turbulence_models"] == {"realizable_ke": "realizableKE", "komega_sst": "kOmegaSST"}
    assert "sample_height_m" not in wind and "grid_cell_mm" not in wind
    assert "GD2" in kinds.PROFILES["source"]
    assert estimates.DATA["kinds"]["airflow"]["fixed_s"] == 60 and estimates.DATA["wind_iterations"] == 1000
    cat = client.get("/analysis/catalogue", headers=rj(rig["a"])).json()
    by_kind = {k["kind"]: k for k in cat["kinds"]}
    assert by_kind["airflow"]["required_files"] == ["rooms"] and by_kind["airflow"]["class"] == "cpu-8"
    assert by_kind["wind"]["required_files"] == ["geometry", "entities"] and by_kind["wind"]["optional_files"] == ["surroundings", "terrain"]
    assert [t["id"] for t in cat["terrain"]] == ["sea", "lake", "open", "suburban", "urban"]
    assert kinds.profile("airflow")["image"] == "truebex-analysis-airflow:1"
