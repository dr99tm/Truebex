"""PF6a: cloud render orchestration follows render-jobs 1.1.0 (CL3).

CL3, the app's headless render service mode (`Truebex.exe -mwrender=<job.json>`),
published render-jobs 1.1.0 with the app's own fixtures, written by the app's
code (`-mwcl3fixtures`) in `Docs/roadmap/fixtures/contracts/render-jobs/`
(last changed in app commit 4ed19a00d; on app main ad3aa5c45).
scripts/sync-contract-fixtures.ps1 copied them byte for byte into
tests/contracts/render-jobs/; PF6's and PF11's own stand-ins (claim.json, the
two ops files, the wind result) moved to tests/fixtures/render/. These tests
hold the platform to the app's set: the blobs, a followed panorama of PR3's
three saved views and its partial update end to end, every render-jobs
route's 1.1 echo, the clients' header and 5.6's keys. The wrapper's side
(the job file, `-mwrender`'s exit codes) is test_pf6a_render_worker.py.
"""

import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.projects import waiters
from app.render import live, pools, tiles

from .licence_helpers import error_of
from .pf12_helpers import ALL_SCOPES, PL, kh, make_key
from .project_helpers import Person, hex32
from .render_helpers import (
    APP_PROJECT,
    FIX,
    MOVED,
    RENDER_FIXTURES,
    RJ,
    VIEW_BEDROOM,
    VIEW_ENTRY,
    VIEW_LIVING,
    VIEWS,
    admin,
    claim,
    claimed,
    finish,
    heartbeat,
    issue_worker,
    job,
    project,
    push_touch,
    rj,
    submitted,
    wk,
)
from .share_helpers import CONTRACT as SHARE, house, published

ROOT = Path(__file__).resolve().parents[2]
# The app commit the folder was copied from, the commit that last changed the
# folder there, and the app's blob of each file (`git ls-tree`); README.md is
# the platform's own. PF11c re-copied it at AN3's merge (render-jobs 1.2.0: the
# seven wind files joined, nothing else moved). The 155 tiles are pinned by their folder's git tree id
# (built from each tile's blob id, so it equals `git rev-parse
# <commit>:<folder>/tiles` exactly when every tile's bytes and name do).
APP_REPO = Path(r"T:\unreal5_7_4_projects\truebex_compact")
APP_COMMIT = "bcdd021f111cac84a2b0bb38ffa7a274059cb83c"
APP_FOLDER_COMMIT = "51b5adf01a4a7a3634bc417b873337d13ebb5e54"
APP_DIR = "Docs/roadmap/fixtures/contracts/render-jobs"
APP_BLOBS = {
    ".gitignore": "91101218e231f80c83d4348b1fdee91b1573c795",
    "job-panorama.json": "0d14d1dd9797ddd5f902670d7c99b0e76e4c63e9",
    "job-tiles.json": "bde25aaf50cba1a7be5e559a8ccb743e617036a2",
    "manifest-panorama.json": "5e9960a7303f106d370c7246220e29932c8894ef",
    "manifest-tiles.json": "d1c8c6bb3a9bc1148f91c7e2deeea56eedfd2959",
    "ops-tiles.json": "fe15ca313306c39d1e19806ec6e7d73f8809eb68",
    "usage.json": "5dc29ddb5730d44bced9c84edffe627e36b4b38f",
    "wind-comfort_lawson.bin": "4a10e0b509b7e7d75263fc4710656b8d6aa85bf1",
    "wind-entities.bin": "1de986d45025d7592cf701a984f596e88ed259ab",
    "wind-geometry.bin": "4fbcad11b769ae4f14296f2ab7d1f5319d9a1d9a",
    "wind-pressure_coefficient.bin": "ef01b71c468dadcfda58ddccd6978755ed6242e9",
    "wind-result.json": "d38d1bdf597aaec4f95bba93ee722b70d2a07bce",
    "wind-speed_ratio.bin": "7b7ba43425dc179a08ceda8b33960bc13a2917bc",
    "wind-velocity.bin": "0a8f4835a563d7d8a2af5537a61912bf45e2cd79",
}
APP_TILES_TREE = "3d5a9f35f7e47390668218e5934893c7aa3e3d1b"
APP_TILES = 155
# PF6's and PF11's stand-ins, now the platform's own (tests/fixtures/render/).
STAND_INS = {
    ".gitattributes", "README.md", "claim.json", "ops-empty.json", "ops-move-wall.json", "wind-result.json",
    "wind-07e4728b5d56.bin", "wind-c7eb3214dcb7.bin", "wind-eafe2a993e63.bin",
    # PF11c: render-jobs 1.2.0's speed_ratio and velocity grids of the octahedron's stand-in.
    "wind-de7db596decf.bin", "wind-5db088a3486c.bin",
}
FACES = ("n", "e", "s", "w", "u", "d")


@pytest.fixture(autouse=True)
def _clean_state():
    waiters.reset()
    pools.DESIRED.clear()
    live.set_share_resolver(None)  # PF5's real shares
    yield
    waiters.reset()


def git_blob_id(data: bytes) -> str:
    """`git hash-object --no-filters`: the blob id of these exact bytes."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def git_tree_id(folder: Path) -> str:
    """The git tree id of a folder of plain files (mode 100644), as git builds it."""
    body = b"".join(
        b"100644 " + p.name.encode("utf-8") + b"\0" + bytes.fromhex(git_blob_id(p.read_bytes()))
        for p in sorted(folder.iterdir(), key=lambda p: p.name.encode("utf-8"))
    )
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def fixture(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def by_view(m: dict) -> dict:
    return {v["view"]: v for v in m["views"]}


def faces(m: dict, view: str) -> dict:
    return {f: (face["rendered"], face["reason"]) for f, face in by_view(m)[view]["faces"].items()}


# --- the folder is the app's ---------------------------------------------------------------


def test_pf6a_contract_folder_is_the_apps_copy():
    """tests/contracts/render-jobs/ holds the app's 14 files (7 since PF11c's
    re-copy: AN3's wind set), its 155 tiles and this folder's README, each the
    app's blob byte for byte."""
    top = {p.name for p in FIX.iterdir() if p.is_file()}
    assert top == set(APP_BLOBS) | {"README.md"}
    assert {p.name for p in FIX.iterdir() if p.is_dir()} == {"tiles"}
    for name, blob in APP_BLOBS.items():
        data = (FIX / name).read_bytes()
        assert git_blob_id(data) == blob, name
        if not name.endswith(".bin"):  # 1.2.0's arrays are binary
            assert b"\r" not in data, name  # the blob's LF, not the app checkout's CRLF
    names = sorted((FIX / "tiles").iterdir())
    assert len(names) == APP_TILES and all(p.is_file() and p.suffix == ".jpg" for p in names)
    assert git_tree_id(FIX / "tiles") == APP_TILES_TREE
    for p in names:  # content-addressed: each name is its bytes' SHA-256
        assert hashlib.sha256(p.read_bytes()).hexdigest() == p.stem, p.name
    readme = (FIX / "README.md").read_text(encoding="utf-8")
    assert APP_COMMIT[:9] in readme and APP_FOLDER_COMMIT[:9] in readme and "1.1.0" in readme
    for name in [*APP_BLOBS, "tiles/"]:
        assert f"`{name}`" in readme, name


@pytest.mark.skipif(not (APP_REPO / ".git").exists(), reason="the app repository is not on this machine")
def test_pf6a_recorded_blobs_are_the_apps_at_the_commit():
    """Where the app repo is present, `git ls-tree` at the recorded commit agrees."""
    out = subprocess.run(
        ["git", "ls-tree", "-r", APP_COMMIT, "--", f"{APP_DIR}/"], cwd=APP_REPO, capture_output=True, text=True, timeout=60
    )
    if out.returncode != 0:
        pytest.skip(f"git ls-tree failed: {out.stderr.strip()}")
    listed = {}
    for line in out.stdout.splitlines():
        mode_type_id, path = line.split("\t", 1)
        listed[path[len(APP_DIR) + 1 :]] = mode_type_id.split()[2]
    assert {k: v for k, v in listed.items() if not k.startswith("tiles/")} == APP_BLOBS
    assert len([k for k in listed if k.startswith("tiles/")]) == APP_TILES
    tree = subprocess.run(
        ["git", "rev-parse", f"{APP_COMMIT}:{APP_DIR}/tiles"], cwd=APP_REPO, capture_output=True, text=True, timeout=60
    )
    assert tree.stdout.strip() == APP_TILES_TREE


def test_pf6a_stand_ins_live_in_fixtures_render():
    """PF6's claim.json and ops files and PF11's wind result are the platform's
    own until AN3 and the app publish theirs; make_render_job_fixtures.py
    writes them there and nowhere else."""
    assert {p.name for p in RENDER_FIXTURES.iterdir()} == STAND_INS
    # Since 1.2.0 the app publishes a wind-result.json of its own there (AN3's, not PF11's stand-in).
    assert not [n for n in STAND_INS - {"README.md"} if (FIX / n).exists() and git_blob_id((FIX / n).read_bytes()) != APP_BLOBS.get(n)]
    readme = (RENDER_FIXTURES / "README.md").read_text(encoding="utf-8")
    assert "AN3" in readme and "../../contracts/render-jobs/" in readme
    for name in sorted(STAND_INS - {"README.md", ".gitattributes"}):
        if not name.startswith("wind-") or name == "wind-result.json":
            assert f"`{name}`" in readme, name
    res = subprocess.run(
        [sys.executable, str(ROOT / "server" / "scripts" / "make_render_job_fixtures.py"), "--check"],
        capture_output=True, text=True, timeout=120,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    script = (ROOT / "server" / "scripts" / "make_render_job_fixtures.py").read_text(encoding="utf-8")
    assert '"contracts" / "render-jobs"' not in script


def test_pf6a_apps_set_is_pr3s_three_rooms():
    """What the readers count on: PR3's project and three saved views at 512 px
    faces and 256 px tiles; 18 faces rendered, then 13 after the wall moved and
    5 carried with the base's tiles; both manifests pass §6.2 as they are."""
    pano, part = fixture("manifest-panorama.json"), fixture("manifest-tiles.json")
    job_pano, job_tiles = fixture("job-panorama.json"), fixture("job-tiles.json")
    assert job_pano["views"] == job_tiles["views"] == VIEWS == [v["view"] for v in pano["views"]] == [v["view"] for v in part["views"]]
    assert {v["view"]: v["title"] for v in pano["views"]} == {VIEW_BEDROOM: "bedroom", VIEW_ENTRY: "entry", VIEW_LIVING: "living"}
    for m in (pano, part):
        assert m["project_id"] == APP_PROJECT and m["app_version"] == "1.0.0" and "tiles_base" not in m
        assert {(v["face_px"], v["tile_px"], tuple(v["levels"])) for v in m["views"]} == {(512, 256, (256, 512))}
        assert set(m["ms"]) == {"open", "render", "encode"}
    assert (pano["faces_rendered"], pano["faces_reused"]) == (18, 0) and len(tiles.all_tiles(pano)) == 90
    assert all(r == (True, "full") for v in VIEWS for r in faces(pano, v).values())
    assert (part["faces_rendered"], part["faces_reused"]) == (13, 5)
    assert faces(part, VIEW_ENTRY) == faces(part, VIEW_LIVING) == {f: (True, "light") for f in FACES}
    assert faces(part, VIEW_BEDROOM) == {f: (True, "changed") if f == "w" else (False, "carried") for f in FACES}
    for vid, f, face in [(v, f, x) for _, v, f, x in tiles.faces_of(part)]:
        same = face["tiles"] == by_view(pano)[vid]["faces"][f]["tiles"]
        assert same == (not face["rendered"]), (vid, f)  # carried keep the base's hashes; rendered are new
    assert len(tiles.all_tiles(part) - tiles.all_tiles(pano)) == 65
    assert tiles.all_tiles(pano) | tiles.all_tiles(part) == {p.stem for p in (FIX / "tiles").iterdir()}
    for m, kind in ((pano, "panorama"), (part, "tiles")):
        row = SimpleNamespace(job_id=m["job_id"], project_id=m["project_id"], at_seq=m["at_seq"], views=VIEWS, kind=kind)
        assert tiles.check_manifest(m, row) == []
    # The tiles job file: the operation after the snapshot, relative paths (resolved against its folder).
    assert job_tiles["project"]["snapshot_seq"] == 0 and job_tiles["project"]["at_seq"] == part["at_seq"] == 1
    assert (job_tiles["project"]["ops"], job_tiles["base_manifest"]) == ("ops-tiles.json", "out/manifest.json")
    assert job_tiles["project"]["tbxp"] == "../../PR3-pano-rooms.tbxp" and job_tiles["changed"] == MOVED
    ops = fixture("ops-tiles.json")
    assert [o["server_seq"] for o in ops["ops"]] == [1] and ops["ops"][0]["touched"] == MOVED
    assert "levels" not in job_pano and "params" not in job_pano  # 1.1.0 defaults


# --- a followed panorama of the app's three views, and its update ------------------------------


def as_sent(views: list[dict]) -> list[dict]:
    """The views as the worker sent them: without the `version` and `op_seq` the
    platform fills on every face (PF6d, render-jobs 1.4.0)."""
    out = copy.deepcopy(views)
    for v in out:
        for face in v["faces"].values():
            face.pop("version", None)
            face.pop("op_seq", None)
    return out


def live_house(job_id: str) -> dict:
    m = copy.deepcopy(house("6" * 32))
    m["panoramas"][0]["live_job_id"] = job_id  # p1, the start panorama
    return m


def test_pf6a_followed_panorama_and_update_with_the_apps_manifests(client):
    """The app's project and three view ids through the queue: the panorama
    completes with manifest-panorama.json, the push of job-tiles.json's ids
    queues one tiles job that completes with manifest-tiles.json (13 faces
    rendered, `light` among them, 5 carried with the base's tiles); 5.2, 5.5,
    /s/{slug}/live and /v1's panorama read serve it."""
    a = Person(client, "a@example.com")
    pid, head = project(client, a, project_id=APP_PROJECT)
    token = issue_worker(client, admin(client))
    follow = submitted(client, rj(a), project_id=pid, at_seq=head, views=VIEWS, follow=True)
    assert follow["views"] == VIEWS and follow["cost_units_estimate"] == 4.5  # 90 s a view on gpu-std
    c = claimed(client, token)
    assert c["job"]["views"] == VIEWS and c["job"]["project_id"] == APP_PROJECT
    done = finish(client, token, c)
    assert done["state"] == "succeeded" and done["output_ready"] is True
    out = client.get(f"/jobs/{follow['job_id']}/output", headers=rj(a)).json()
    pano = fixture("manifest-panorama.json")
    assert out["project_id"] == APP_PROJECT == pano["project_id"] and out["faces_rendered"] == 18
    assert as_sent(out["views"]) == pano["views"] and out["tiles_base"] == "http://testserver/tiles"
    for sha in sorted(tiles.all_tiles(out))[:5]:
        assert client.get(f"/tiles/{sha}.jpg").content == (FIX / "tiles" / f"{sha}.jpg").read_bytes()

    # The app's edit: job-tiles.json's operation touched these ids.
    moved_at = push_touch(client, a, pid, MOVED)
    queued = client.get("/jobs", params={"kind": "tiles", "state": "queued"}, headers=rj(a)).json()["jobs"]
    assert len(queued) == 1 and queued[0]["views"] == VIEWS and queued[0]["changed_count"] == len(MOVED)
    c2 = claimed(client, token)
    assert c2["job"]["changed"] == MOVED and c2["job"]["base_job_id"] == follow["job_id"]
    assert as_sent(client.get(c2["inputs"]["base_manifest_url"]).json()["views"]) == pano["views"]
    assert [o["touched"] for o in client.get(c2["inputs"]["ops_url"]).json()["ops"]][-1] == MOVED
    rev = job(client, rj(a), follow["job_id"])["rev"]
    finish(client, token, c2, "manifest-tiles.json", wall_s=30)

    # 5.2: the follow job's rev moved; 5.5: the update's manifest, carried faces as the base's.
    after = job(client, rj(a), follow["job_id"])
    assert after["rev"] > rev and after["state"] == "succeeded" and after["at_seq"] == moved_at
    part = fixture("manifest-tiles.json")
    now = client.get(f"/jobs/{follow['job_id']}/output", headers=rj(a)).json()
    assert now["job_id"] == c2["job"]["job_id"] and as_sent(now["views"]) == part["views"]
    assert (now["faces_rendered"], now["faces_reused"]) == (13, 5)
    assert faces(now, VIEW_LIVING)["n"] == (True, "light") and faces(now, VIEW_BEDROOM)["w"] == (True, "changed")

    # The live share page's read and /v1's panorama read serve the same manifest.
    share = published(client, a.token, live_house(follow["job_id"]))
    state = client.get(f"/s/{share['slug']}/live", params={"panorama": "p1"}, headers=SHARE)
    assert state.status_code == 200, state.text
    assert as_sent(state.json()["manifest"]["views"]) == part["views"] and state.json()["job_id"] == c2["job"]["job_id"]
    key = make_key(client, a.session, ["projects:read"])
    v1 = client.get(f"/v1/projects/{pid}/panoramas/{follow['job_id']}", headers=kh(key, **PL))
    assert v1.status_code == 200, v1.text
    assert as_sent(v1.json()["manifest"]["views"]) == part["views"] and v1.json()["manifest"]["faces_rendered"] == 13


# --- render-jobs/1.1 on every route ------------------------------------------------------------


# PF11c: every route answers render-jobs/1.2 since 1.2.0 (AN3), PF6c 1.3 since 1.3.0 (CL4), PF6d 1.4 since 1.4.0
# (PR5); 1.0 and 1.1 are still served.
ECHO = "render-jobs/1.4"


def _versions(send, label: str) -> None:
    """`send(headers)` answers with the echo for a 1.0, a 1.1 and no
    contract header, and 400 `contract_version` for 2.0."""
    for sent in ("render-jobs/1.0", "render-jobs/1.1", None):
        extra = {} if sent is None else {"X-Truebex-Contract": sent}
        res = send(extra)
        assert res.status_code < 400, (label, sent, res.status_code, res.text)
        assert res.headers["X-Truebex-Contract"] == ECHO, (label, sent)
    body = error_of(send({"X-Truebex-Contract": "render-jobs/2.0"}), 400, "contract_version")
    assert body["data"]["supported"] == [ECHO], label


def test_pf6a_routes_echo_render_jobs_1_1(client):
    a = Person(client, "a@example.com")
    pid, head = project(client, a, project_id=APP_PROJECT)
    adm = admin(client)
    token = issue_worker(client, adm)
    dev = {"Authorization": f"Bearer {a.token}"}
    wrk = {"Authorization": f"Bearer {token}"}
    body = {"kind": "panorama", "project_id": pid, "at_seq": head, "views": VIEWS}

    # /jobs (5.1-5.6).
    _versions(lambda h: client.post("/jobs", json=body, headers={**dev, **h, "Idempotency-Key": hex32()}), "5.1")
    _versions(lambda h: client.get("/jobs", headers={**dev, **h}), "5.3")
    _versions(lambda h: client.get("/jobs/usage", headers={**dev, **h}), "5.6")
    rec = client.get("/jobs", headers=rj(a)).json()["jobs"][0]
    _versions(lambda h: client.get(f"/jobs/{rec['job_id']}", headers={**dev, **h}), "5.2")
    error_of(client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a)), 409, "not_ready")
    assert client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a)).headers["X-Truebex-Contract"] == ECHO
    queued = [submitted(client, rj(a), project_id=pid, at_seq=head)["job_id"] for _ in range(4)]
    to_cancel = iter(queued)
    _versions(lambda h: client.post(f"/jobs/{next(to_cancel)}/cancel", headers={**dev, **h}), "5.4")
    assert client.post(f"/jobs/{queued[-1]}/cancel", headers=rj(a)).status_code == 200  # the one 2.0 left

    # /workers (5.7-5.10): a claim's 200 and 204 answers are written by hand.
    claim_body = {"worker_id": "pc-rtx", "kinds": ["panorama"], "app_version": "1.0.0", "doc_version_max": 38, "wait_s": 0}
    for sent in ("render-jobs/1.0", "render-jobs/1.1", None):
        extra = {} if sent is None else {"X-Truebex-Contract": sent}
        res = client.post("/workers/claim", json=claim_body, headers={**wrk, **extra})
        assert res.status_code == 200 and res.headers["X-Truebex-Contract"] == ECHO, (sent, res.text)
        c = res.json()
        _versions(lambda h: client.post(
            f"/workers/jobs/{c['job']['job_id']}/heartbeat", json={"lease_id": c["lease_id"], "progress": 0.5, "message": "face e"},
            headers={**wrk, **h},
        ), "5.8")
        fail = {"lease_id": c["lease_id"], "code": "bad_input", "message": "no snapshot", "retryable": False}
        _versions(lambda h: client.post(f"/workers/jobs/{c['job']['job_id']}/fail", json=fail, headers={**wrk, **h}), "5.10")
    nothing = client.post("/workers/claim", json=claim_body, headers=wk(token))
    assert nothing.status_code == 204 and nothing.headers["X-Truebex-Contract"] == ECHO
    error_of(client.post("/workers/claim", json=claim_body, headers={**wrk, "X-Truebex-Contract": "render-jobs/2.0"}), 400, "contract_version")
    submitted(client, rj(a), project_id=pid, at_seq=head)
    c = claimed(client, token)
    assert heartbeat(client, token, c).headers["X-Truebex-Contract"] == ECHO
    done = finish(client, token, c)
    assert done["state"] == "succeeded"
    again = client.post(
        f"/workers/jobs/{c['job']['job_id']}/complete",
        json={"lease_id": c["lease_id"], "output": {}, "usage": {"wall_s": 1, "class": "gpu-std"}},
        headers={**wrk, "X-Truebex-Contract": "render-jobs/1.0"},
    )
    assert again.status_code == 200 and again.headers["X-Truebex-Contract"] == ECHO  # 5.9 repeats per lease

    # /analysis (PF11's catalogue on the same contract) and /v1/jobs (PF12).
    _versions(lambda h: client.get("/analysis/catalogue", headers={**dev, **h}), "analysis")
    key = make_key(client, a.session, ALL_SCOPES)
    _versions(lambda h: client.get("/v1/jobs", headers=kh(key, **h)), "v1 5.3")
    _versions(lambda h: client.get("/v1/jobs/usage", headers=kh(key, **h)), "v1 5.6")
    _versions(lambda h: client.get(f"/v1/jobs/{c['job']['job_id']}", headers=kh(key, **h)), "v1 5.2")
    _versions(lambda h: client.post("/v1/jobs", json=body, headers=kh(key, **h, **{"Idempotency-Key": hex32()})), "v1 5.1")
    # Errors carry the echo too.
    missing = client.get(f"/jobs/{hex32()}", headers=rj(a))
    assert missing.status_code == 404 and missing.headers["X-Truebex-Contract"] == ECHO


def test_pf6a_no_router_or_client_left_on_1_0():
    """The routers, the worker wrapper, the website's client, the developer
    document and the SDKs all speak render-jobs/1.1 (1.2 since PF11c, 1.3 since PF6c, 1.4 since PF6d)."""
    app_dir = ROOT / "server" / "app"
    for path in app_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert 'contract("render-jobs", 1, 0)' not in text and "render-jobs/1.0" not in text, path
    for name in ("jobs.py", "workers.py", "analysis.py", "v1/jobs.py"):
        assert 'contract("render-jobs", 1, 4)' in (app_dir / "routers" / name).read_text(encoding="utf-8"), name
    assert 'CONTRACT = "render-jobs/1.4"' in (ROOT / "worker" / "truebex_worker.py").read_text(encoding="utf-8")
    assert '"X-Truebex-Contract": "render-jobs/1.4"' in (ROOT / "src" / "lib" / "jobs.ts").read_text(encoding="utf-8")
    assert '"render-jobs/1.4"' in (ROOT / "server" / "scripts" / "demo_render.py").read_text(encoding="utf-8")
    doc = json.loads((ROOT / "openapi" / "v1.json").read_text(encoding="utf-8"))
    jobs_ops = [op for p, item in doc["paths"].items() if p.startswith("/v1/jobs") for op in item.values()]
    assert jobs_ops and {op["x-truebex-contract"] for op in jobs_ops} == {ECHO}
    for sdk in (ROOT / "sdks" / "python" / "truebex" / "_operations.py", ROOT / "sdks" / "js" / "src" / "operations.mjs"):
        text = sdk.read_text(encoding="utf-8")
        assert "render-jobs/1.0" not in text and text.count("render-jobs/1.4") == len(jobs_ops), sdk
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "render-jobs/1.0" not in readme and "`X-Truebex-Contract: render-jobs/1.4`" in readme
    # RJ, the tests' own header, is what the app sends (PR5's headset since PF6d).
    assert RJ == {"X-Truebex-Contract": ECHO}


# --- 5.6 -------------------------------------------------------------------------------------


def test_pf6a_usage_keys_are_a_subset_of_5_6(client):
    """usage.json (the app's 5.6) names only keys the platform's 5.6 answers,
    `by_kind` and `classes` included, once a panorama and a tiles job ran."""
    a = Person(client, "a@example.com")
    pid, head = project(client, a, project_id=APP_PROJECT)
    token = issue_worker(client, admin(client))
    submitted(client, rj(a), project_id=pid, at_seq=head, follow=True)
    finish(client, token, claimed(client, token), wall_s=84.2)  # 1.5 cu
    push_touch(client, a, pid, MOVED)
    finish(client, token, claimed(client, token), "manifest-tiles.json", wall_s=30)  # 0.5 cu
    usage = client.get("/jobs/usage", headers=rj(a)).json()
    expected = fixture("usage.json")
    assert set(expected) <= set(usage)
    assert set(expected["by_kind"]) == {"tiles", "panorama"} <= set(usage["by_kind"])
    assert set(expected["classes"]) <= set(usage["classes"])
    assert usage["by_kind"] == {"panorama": 1.5, "tiles": 0.5}
    for k in ("period_start", "period_end"):
        assert re.fullmatch(r"\d{4}-\d\d-01T00:00:00Z", usage[k]) and re.fullmatch(r"\d{4}-\d\d-01T00:00:00Z", expected[k])
    assert claim(client, token).status_code == 204


def test_pf6a_fake_app_and_stub_solver_read_the_new_folders():
    """The fake app reads the app's set; PF11's stub solver and analysis tests
    read the wind result from tests/fixtures/render/."""
    fake = (ROOT / "worker" / "tests" / "fake_truebex.py").read_text(encoding="utf-8")
    assert '"contracts" / "render-jobs"' in fake and "manifest-tiles.json" in fake
    solver = (ROOT / "server" / "tests" / "fakes" / "stub_solver" / "run.py").read_text(encoding="utf-8")
    assert '"fixtures" / "render"' in solver and '"contracts" / "render-jobs"' not in solver
    analysis = (ROOT / "server" / "tests" / "test_analysis.py").read_text(encoding="utf-8")
    assert '"fixtures" / "render"' in analysis
