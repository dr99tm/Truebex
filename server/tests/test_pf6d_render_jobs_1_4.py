"""PF6d: the render service follows render-jobs 1.4.0 (PR5's headset faces).

PR5 (the app's native headset target, app task T134, on app main 2c842b8f1)
picks and stays current without the model: per face of a 6.2 manifest it reads
`id` (the SHA-256 of an 8-bit grey PNG at levels[0] px, each pixel the index of
the entity seen there), `ids` (its truebex-ids/1 JSON, index -> entity id, 0 =
nothing), `depth` (a 16-bit grey PNG: millimetres from eye_mm), `version` and
`op_seq`, and the manifest's top-level `tour` (a PR3 truebex-tour/1 file whose
nodes name the manifest's views). The platform checks them on 5.9 (the PNG's
signature and IHDR, the JSON's schema; no full decode), stores the files beside
the colour tiles (`tiles/<sha256>.png`, `tiles/<sha256>.json`), serves them
from tiles_base with their extension, keeps them on carried faces and in the
tile collector, fills `version` and `op_seq` itself when the worker leaves them
out (and refuses values that disagree), and every render-jobs route answers
render-jobs/1.4 (PF6c's two echo tests moved here). A 1.3 worker's manifest is
still accepted and gains no file key.
"""

import copy
import hashlib
import importlib.util
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import tasks
from app.render import live, pools, tiles
from app.projects import waiters
from app.storage import get_store

from .analysis_helpers import put_inputs
from .licence_helpers import Clock, error_of
from .pf12_helpers import ALL_SCOPES, PL, kh, make_key
from .project_helpers import UPLOADS, Person, hex32
from .render_helpers import (
    APP_PROJECT,
    FIX,
    MOVED,
    RJ,
    VIEWS,
    admin,
    claimed,
    complete,
    finish,
    fixture_manifest,
    issue_worker,
    job,
    project,
    push_touch,
    rendered_tiles,
    rj,
    submitted,
    upload_outputs,
    wk,
)
from .test_pf11c_render_jobs_1_2 import KINDS as ANALYSIS_KINDS, wind_job_body

ROOT = Path(__file__).resolve().parents[2]
ECHO = "render-jobs/1.4"
SENT = ("render-jobs/1.0", "render-jobs/1.1", "render-jobs/1.2", "render-jobs/1.3", "render-jobs/1.4", None)
# render-jobs.md 1.4.0 (PR5, app task T134), read through the manager's snapshot of app main (the PC's
# checkout is at 37d98cec): the contract's blob, the app commit.
APP_MAIN = "2c842b8f1"
RENDER_JOBS_BLOB = "6a47207a8a0bfc464d3910d4609eff49eb2a4ffd"
FACES = ("n", "e", "s", "w", "u", "d")
NEW_FACE_KEYS = ("id", "ids", "depth", "version", "op_seq")
TRIGGER_KEYS = {"op_ids", "first_seq", "last_seq", "first_op_at", "first_accepted_at", "authors"}
PX = 256  # the app's fixtures: levels [256, 512]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(autouse=True)
def _clean_state():
    waiters.reset()
    pools.DESIRED.clear()
    live.set_share_resolver(None)
    yield
    waiters.reset()
    live.set_share_resolver(None)


@pytest.fixture()
def rig(client):
    """A Pro-trial designer with the app's project (two operations), an admin and a GPU worker."""
    a = Person(client, "a@example.com")
    pid, head = project(client, a, project_id=APP_PROJECT)
    adm = admin(client)
    return {"a": a, "pid": pid, "head": head, "admin": adm, "token": issue_worker(client, adm)}


# --- the 1.4 files, as CL3's worker would write them (CadVrEdits' formats) -------------------------


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png(px: int, bits: int, row_value, *, colour: int = 0, height: int | None = None) -> bytes:
    """A grey (colour 0) or RGB (colour 2) PNG, `px` wide, each row one value."""
    rows = px if height is None else height
    channels = 3 if colour == 2 else 1
    raw = b"".join(b"\x00" + row_value(y).to_bytes(bits // 8, "big") * (px * channels) for y in range(rows))
    ihdr = struct.pack(">IIBBBBB", px, rows, bits, colour, 0, 0, 0)
    return PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def face_files(view: str, face: str, salt: str = "", px: int = PX) -> dict[str, bytes]:
    """One face's id, ids and depth files: a few entities in horizontal bands, a depth ramp."""
    digest = hashlib.sha256(f"{view}/{face}/{salt}".encode()).hexdigest()
    n = 1 + int(digest[:2], 16) % 5
    ids = [None] + [hashlib.md5(f"{digest}/{k}".encode()).hexdigest() for k in range(1, n + 1)]
    start, shift = int(digest[2:5], 16), int(digest[5:7], 16)
    return {
        "id": png(px, 8, lambda y: ((y + shift) * (n + 1) // px) % (n + 1)),
        "ids": json.dumps({"schema": "truebex-ids/1", "ids": ids}, separators=(",", ":")).encode(),
        "depth": png(px, 16, lambda y: 0 if y < px // 8 else 900 + start + 10 * y),
    }


def tour_file(views: list[str]) -> bytes:
    """PR3's truebex-tour/1: a node per view, linked in order."""
    nodes = [{"id": f"node-{i}", "title": f"Room {i}", "view": v, "pos": [i * 400.0, 0.0, 160.0], "room": f"Room {i}"} for i, v in enumerate(views)]
    links = [{"from": f"node-{i - 1}", "to": f"node-{i}", "auto": True} for i in range(1, len(views))]
    return json.dumps({"format": "truebex-tour/1", "project": APP_PROJECT, "start": "node-0", "nodes": nodes, "links": links}).encode()


EXT = {"id": "png", "ids": "json", "depth": "png"}
TYPE = {"png": "image/png", "json": "application/json"}


def headset(m: dict, *, salt: str = "", faces=FACES, tour: bool = True) -> tuple[dict, dict[str, tuple[bytes, str]]]:
    """`m` with id / ids / depth on its rendered faces (of `faces`) and a tour; the files by SHA-256."""
    m = copy.deepcopy(m)
    files: dict[str, tuple[bytes, str]] = {}
    for v in m["views"]:
        for f in faces:
            face = v["faces"][f]
            if not face["rendered"]:
                continue
            for key, data in face_files(v["view"], f, salt).items():
                face[key] = sha(data)
                files[face[key]] = (data, TYPE[EXT[key]])
    if tour:
        data = tour_file([v["view"] for v in m["views"]])
        m["tour"] = sha(data)
        files[m["tour"]] = (data, "application/json")
    return m, files


def upload(client, token: str, c: dict, files: dict[str, tuple[bytes, str]]) -> None:
    """Declare `files` into the claim's job-output session and send them."""
    declared = [{"sha256": s, "bytes": len(d), "content_type": t} for s, (d, t) in files.items()]
    res = client.post(
        "/uploads",
        json={"purpose": "job-output", "upload_id": c["output_upload"]["upload_id"], "files": declared},
        headers={"Authorization": f"Bearer {token}", **UPLOADS},
    )
    assert res.status_code == 201, res.text
    for state in res.json()["files"]:
        if state["state"] in ("present", "complete"):
            continue
        data = files[state["sha256"]][0]
        sent = client.put(
            f"/uploads/{c['output_upload']['upload_id']}/files/{state['sha256']}/parts/0",
            content=data,
            headers={
                "Authorization": f"Bearer {token}", **UPLOADS, "Content-Type": "application/octet-stream",
                "X-Part-Sha256": hashlib.sha256(data).hexdigest(),
            },
        )
        assert sent.status_code == 204, sent.text


def refused(client, token: str, c: dict, m: dict) -> list[dict]:
    res = complete(client, token, c, m)
    body = error_of(res, 422, "output_invalid")
    return body["data"]["errors"]


def has(errors: list[dict], path: str, rule: str) -> bool:
    return any(e["path"] == path and e["rule"] == rule for e in errors)


def output(client, person: Person, job_id: str) -> dict:
    res = client.get(f"/jobs/{job_id}/output", headers=rj(person))
    assert res.status_code == 200, res.text
    return res.json()


def face_of(m: dict, view: str, f: str) -> dict:
    return next(v for v in m["views"] if v["view"] == view)["faces"][f]


def bare(views: list[dict]) -> list[dict]:
    """The views without 1.4's per-face keys."""
    out = copy.deepcopy(views)
    for v in out:
        for face in v["faces"].values():
            for key in NEW_FACE_KEYS:
                face.pop(key, None)
    return out


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# --- 1. checked, stored and served from tiles_base -------------------------------------------------


def test_pf6d_face_files_checked_stored_and_served(client, rig):
    """A worker's panorama with id, ids, depth, version and op_seq on every face
    and a tour: accepted; 5.5 answers them with tiles_base; the files are
    served at <tiles_base>/<sha256>.png and .json like the colour tiles; the
    live share, /v1 and the members' read pass them through."""
    a, token = rig["a"], rig["token"]
    set_id = submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"], views=VIEWS, follow=True)["job_id"]
    c = claimed(client, token)
    m, files = headset(fixture_manifest("manifest-panorama.json", c))
    for v in m["views"]:
        for face in v["faces"].values():
            face["version"], face["op_seq"] = 1, c["job"]["at_seq"]  # a 1.4 worker writes them itself
    upload_outputs(client, token, c, rendered_tiles(m))
    upload(client, token, c, files)
    res = complete(client, token, c, m)
    assert res.status_code == 200, res.text
    out = output(client, a, set_id)
    assert out["tiles_base"] == "http://testserver/tiles" and out["tour"] == m["tour"]
    assert out["views"] == m["views"]
    assert {k: v for k, v in out.items() if k not in ("tiles_base", "rev")} == m

    # The files beside the colour tiles: one key per extension, public and immutable.
    store = get_store()
    one = face_of(m, VIEWS[0], "n")
    for name, ctype in ((f"{one['id']}.png", "image/png"), (f"{one['depth']}.png", "image/png"),
                        (f"{one['ids']}.json", "application/json"), (f"{m['tour']}.json", "application/json")):
        assert store.stat(f"tiles/{name}").content_type == ctype, name
        got = client.get(f"{out['tiles_base']}/{name}", headers={})
        assert got.status_code == 200, (name, got.text)
        assert got.content == files[name.split(".")[0]][0] and hashlib.sha256(got.content).hexdigest() == name.split(".")[0]
        assert got.headers["Content-Type"] == ctype
        assert got.headers["Cache-Control"] == "public, max-age=31536000, immutable"
        assert got.headers["Access-Control-Allow-Origin"] == "*" and got.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Truebex-Contract" not in got.headers
    assert client.get(f"/tiles/{one['tiles'][0][0]}.jpg").headers["Content-Type"] == "image/jpeg"
    # A key per extension: the same hash under another extension is not there.
    assert client.get(f"/tiles/{one['id']}.jpg").status_code == 404
    assert client.get(f"/tiles/{one['tiles'][0][0]}.png").status_code == 404
    assert client.get(f"/tiles/{one['ids']}.png").status_code == 404
    error_of(client.get(f"/tiles/{'0' * 64}.json", headers={}), 404, "not_found")
    assert client.get(f"/tiles/{one['id']}.gif").status_code == 404
    png_head = client.get(f"/tiles/{one['id']}.png").content[:33]
    assert png_head[:8] == PNG_SIGNATURE and struct.unpack(">IIBB", png_head[16:26]) == (PX, PX, 8, 0)

    # The set's other reads pass the stored keys through (the models do not name them).
    live.set_share_resolver(lambda db, slug: {"account_id": a.user_id, "manifest": {"panoramas": [{"id": "p1", "live_job_id": set_id}]}})
    state = client.get("/s/k3J9xQ2aTf/live", headers={"X-Truebex-Contract": "share-bundle/1.1"})
    assert state.status_code == 200, state.text
    assert state.json()["manifest"]["views"] == m["views"] and state.json()["manifest"]["tour"] == m["tour"]
    key = make_key(client, a.session, ["projects:read"])
    v1 = client.get(f"/v1/projects/{rig['pid']}/panoramas/{set_id}", headers=kh(key, **PL))
    assert v1.status_code == 200, v1.text
    assert v1.json()["manifest"]["views"] == m["views"] and v1.json()["manifest"]["tour"] == m["tour"]
    members = client.get(f"/projects/{rig['pid']}/panoramas/{set_id}", headers=a.web)
    assert members.status_code == 200 and members.json()["manifest"]["views"] == m["views"]
    v1_out = client.get(f"/v1/jobs/{set_id}/output", headers=kh(make_key(client, a.session, ALL_SCOPES)))
    assert v1_out.status_code == 200 and v1_out.json()["views"] == m["views"]


# --- 2. 422 output_invalid -------------------------------------------------------------------------


def test_pf6d_output_invalid_face_files(client, rig):
    """Each broken 1.4 field answers 422 output_invalid naming its path; the
    lease survives, and the same output fixed is accepted."""
    a, token = rig["a"], rig["token"]
    submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"], views=VIEWS)
    c = claimed(client, token)
    at = c["job"]["at_seq"]
    good, files = headset(fixture_manifest("manifest-panorama.json", c))
    big_id = png(512, 8, lambda y: 1)                          # levels[1], not levels[0]
    wide_id = png(PX, 8, lambda y: 1, height=PX // 2)            # not square
    deep_id = png(PX, 16, lambda y: 1)                          # 16 bit where 8 belongs
    shallow_depth = png(PX, 8, lambda y: 1)                     # 8 bit where 16 belongs
    rgb_id = png(PX, 8, lambda y: 1, colour=2)                  # not grey
    broken = bytearray(png(PX, 8, lambda y: 2))
    broken[30] ^= 0xFF                                         # the IHDR's CRC no longer matches
    jpeg = (FIX / "tiles" / f"{good['views'][0]['faces']['n']['tiles'][0][0]}.jpg").read_bytes()
    not_ids = json.dumps({"schema": "truebex-ids/2", "ids": [None]}).encode()
    first_named = json.dumps({"schema": "truebex-ids/1", "ids": ["0" * 32, "1" * 32]}).encode()
    bad_entry = json.dumps({"schema": "truebex-ids/1", "ids": [None, "not-an-id"]}).encode()
    too_many = json.dumps({"schema": "truebex-ids/1", "ids": [None] + [f"{i:032x}" for i in range(1, 257)]}).encode()
    not_json = b"\xff not json"
    old_tour = json.dumps({"schema": "truebex-tour/1", "nodes": [{"id": "a", "view": VIEWS[0]}]}).encode()
    stray_tour = json.loads(tour_file(VIEWS))
    stray_tour["nodes"][1]["view"] = "f" * 32
    stray_tour = json.dumps(stray_tour).encode()
    empty_tour = json.dumps({"format": "truebex-tour/1", "nodes": []}).encode()
    bad = {
        name: data for name, data in {
            "big_id": big_id, "wide_id": wide_id, "deep_id": deep_id, "shallow_depth": shallow_depth, "rgb_id": rgb_id,
            "broken": bytes(broken), "not_ids": not_ids, "first_named": first_named, "bad_entry": bad_entry,
            "too_many": too_many, "not_json": not_json, "old_tour": old_tour, "stray_tour": stray_tour, "empty_tour": empty_tour,
        }.items()
    }
    upload_outputs(client, token, c, rendered_tiles(good))
    upload(client, token, c, {**files, **{sha(d): (d, "application/octet-stream") for d in bad.values()}})
    n = "views[0].faces.n"

    def with_face(**changes) -> dict:
        m = copy.deepcopy(good)
        face = m["views"][0]["faces"]["n"]
        for key, value in changes.items():
            if value is ...:
                face.pop(key)
            else:
                face[key] = value
        return m

    def with_top(**changes) -> dict:
        m = copy.deepcopy(good)
        for key, value in changes.items():
            if value is ...:
                m.pop(key)
            else:
                m[key] = value
        return m

    cases = [
        # A face field that is not a SHA-256.
        (with_face(id="nope"), f"{n}.id", "id"),
        (with_face(ids=42), f"{n}.ids", "ids"),
        (with_face(depth=None), f"{n}.depth", "depth"),
        (with_face(depth="A" * 64), f"{n}.depth", "depth"),
        (with_top(tour=["0" * 64]), "tour", "tour"),
        # id and ids come together (ids decodes id).
        (with_face(ids=...), n, "ids"),
        (with_face(id=...), n, "ids"),
        # A file not uploaded in the job's session (and not in the store).
        (with_face(id=sha(b"never sent")), f"{n}.id", "file_missing"),
        (with_face(ids=sha(b"never sent either")), f"{n}.ids", "file_missing"),
        (with_face(depth=sha(b"nor this")), f"{n}.depth", "file_missing"),
        (with_top(tour=sha(b"no tour")), "tour", "file_missing"),
        # An id or depth file that is not a PNG of levels[0] x levels[0] px with the right bit depth.
        (with_face(id=sha(big_id)), f"{n}.id", "id"),
        (with_face(id=sha(wide_id)), f"{n}.id", "id"),
        (with_face(id=sha(deep_id)), f"{n}.id", "id"),
        (with_face(id=sha(rgb_id)), f"{n}.id", "id"),
        (with_face(id=sha(bytes(broken))), f"{n}.id", "id"),
        (with_face(id=sha(jpeg)), f"{n}.id", "id"),
        (with_face(depth=sha(shallow_depth)), f"{n}.depth", "depth"),
        (with_face(depth=face_of(good, VIEWS[0], "n")["id"]), f"{n}.depth", "depth"),
        # An ids file that is not truebex-ids/1, or whose ids[0] is not null.
        (with_face(ids=sha(not_ids)), f"{n}.ids", "ids"),
        (with_face(ids=sha(first_named)), f"{n}.ids", "ids"),
        (with_face(ids=sha(bad_entry)), f"{n}.ids", "ids"),
        (with_face(ids=sha(too_many)), f"{n}.ids", "ids"),
        (with_face(ids=sha(not_json)), f"{n}.ids", "ids"),
        # version < 1, an op_seq that is not an integer, values that disagree with the job.
        (with_face(version=0), f"{n}.version", "version"),
        (with_face(version="1"), f"{n}.version", "version"),
        (with_face(version=True), f"{n}.version", "version"),
        (with_face(version=2), f"{n}.version", "version"),       # a panorama's faces are version 1
        (with_face(op_seq=1.5), f"{n}.op_seq", "op_seq"),
        (with_face(op_seq="2"), f"{n}.op_seq", "op_seq"),
        (with_face(op_seq=-1), f"{n}.op_seq", "op_seq"),
        (with_face(op_seq=at - 1), f"{n}.op_seq", "op_seq"),    # op_seq is the job's at_seq
        # A tour that is not truebex-tour/1, names a view the manifest lacks, or has no node.
        (with_top(tour=sha(old_tour)), "tour", "tour"),
        (with_top(tour=sha(stray_tour)), "tour", "tour"),
        (with_top(tour=sha(empty_tour)), "tour", "tour"),
        (with_top(tour=face_of(good, VIEWS[0], "n")["ids"]), "tour", "tour"),
    ]
    for i, (m, path, rule) in enumerate(cases):
        errors = refused(client, token, c, m)
        assert has(errors, path, rule), (i, path, rule, errors)
        assert all(isinstance(e["message"], str) and e["message"] for e in errors), errors
    # Nothing was stored by a refused output.
    assert get_store().stat(f"tiles/{sha(big_id)}.png") is None and get_store().stat(f"tiles/{face_of(good, VIEWS[0], 'n')['id']}.png") is None
    # The same output, whole: accepted (the lease survived every refusal).
    res = complete(client, token, c, good)
    assert res.status_code == 200 and res.json()["state"] == "succeeded", res.text
    assert get_store().stat(f"tiles/{face_of(good, VIEWS[0], 'n')['id']}.png").content_type == "image/png"
    # Only the files the manifest names were published (the bad uploads stay in the upload).
    assert all(get_store().stat(f"tiles/{sha(d)}.png") is None and get_store().stat(f"tiles/{sha(d)}.json") is None for d in bad.values())


def test_pf6d_check_manifest_rules_alone():
    """check_manifest's shape rules for the new keys, with no file read."""
    m = load("manifest-panorama.json")
    row = SimpleNamespace(job_id=m["job_id"], project_id=m["project_id"], at_seq=m["at_seq"], views=VIEWS, kind="panorama")
    assert tiles.check_manifest(m, row) == []
    face = m["views"][2]["faces"]["u"]
    face.update(id="a" * 64, ids="b" * 64, depth="c" * 64, version=1, op_seq=m["at_seq"])
    m["tour"] = "d" * 64
    assert tiles.check_manifest(m, row) == []
    face.update(version=0, op_seq=None)
    m["tour"] = "d" * 63
    got = {(e["path"], e["rule"]) for e in tiles.check_manifest(m, row)}
    assert got == {("views[2].faces.u.version", "version"), ("views[2].faces.u.op_seq", "op_seq"), ("tour", "tour")}


# --- 3. a 1.3 manifest -----------------------------------------------------------------------------


def test_pf6d_manifest_without_1_4_fields(client, rig):
    """A 1.3 worker's manifest (the app's fixture, no 1.4 key) is accepted and
    answered as it was sent: no id, ids, depth or tour key, no key with null;
    the server adds only version and op_seq (version 1, op_seq the at_seq)."""
    a, token = rig["a"], rig["token"]
    rec = submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"], views=VIEWS)
    c = claimed(client, token)
    sent = fixture_manifest("manifest-panorama.json", c)
    assert not any(k in face for v in sent["views"] for face in v["faces"].values() for k in NEW_FACE_KEYS) and "tour" not in sent
    finish(client, token, c)
    out = output(client, a, rec["job_id"])
    assert set(out) == set(sent) | {"tiles_base", "rev"} and "tour" not in out
    assert {k: out[k] for k in sent if k != "views"} == {k: v for k, v in sent.items() if k != "views"}
    assert bare(out["views"]) == sent["views"]
    for v in out["views"]:
        for f, face in v["faces"].items():
            assert set(face) == {"rendered", "reason", "tiles", "version", "op_seq"}, (v["view"], f)
            assert (face["version"], face["op_seq"]) == (1, rig["head"])
            assert None not in face.values()
    stored = tiles.read_json(tiles.manifest_key(rec["job_id"]))
    assert stored["views"] == out["views"] and "tiles_base" not in stored


# --- 4. a follow set: version and op_seq -----------------------------------------------------------


def test_pf6d_follow_set_versions_and_carried_faces(client, rig):
    """The first render: every face version 1, op_seq its at_seq (filled by the
    server). A tiles job re-renders n and e: they answer version 2 and the
    tiles job's at_seq, with their new files; the carried faces keep the base's
    id, ids, depth, version and op_seq, and the manifest the base's tour. A
    worker's values that disagree are refused. A second update re-renders n:
    version 3; e stays 2."""
    a, token, pid, head = rig["a"], rig["token"], rig["pid"], rig["head"]
    set_id = submitted(client, rj(a), project_id=pid, at_seq=head, views=VIEWS, follow=True)["job_id"]
    c = claimed(client, token)
    first, files = headset(fixture_manifest("manifest-panorama.json", c))
    upload_outputs(client, token, c, rendered_tiles(first))
    upload(client, token, c, files)
    assert complete(client, token, c, first).status_code == 200
    base = output(client, a, set_id)
    for v in base["views"]:
        for face in v["faces"].values():
            assert (face["version"], face["op_seq"]) == (1, head)
    assert bare(base["views"]) == bare(first["views"]) and base["tour"] == first["tour"]

    # The edit: a tiles job that re-renders n and e of every view and carries the rest.
    moved_at = push_touch(client, a, pid, MOVED)
    c2 = claimed(client, token)
    assert c2["job"]["kind"] == "tiles" and c2["job"]["at_seq"] == moved_at > head
    pano, part = load("manifest-panorama.json"), load("manifest-tiles.json")
    update = fixture_manifest("manifest-panorama.json", c2)
    update.update(faces_rendered=2 * len(VIEWS), faces_reused=4 * len(VIEWS))
    for v in update["views"]:
        for f in FACES:
            now = face_of(part, v["view"], f)
            if f in ("n", "e"):
                v["faces"][f] = {"rendered": True, "reason": "changed", "tiles": now["tiles"] if now["rendered"] else face_of(pano, v["view"], f)["tiles"]}
            else:
                v["faces"][f] = {"rendered": False, "reason": "carried", "tiles": face_of(pano, v["view"], f)["tiles"]}
    update, new_files = headset(update, salt="2", faces=("n", "e"), tour=False)
    upload_outputs(client, token, c2, rendered_tiles(update))
    upload(client, token, c2, new_files)
    v0 = update["views"][0]["view"]

    def changed(view_i: int, f: str, **kw) -> dict:
        m = copy.deepcopy(update)
        m["views"][view_i]["faces"][f].update(kw)
        return m

    old = face_of(base, v0, "s")
    for m, path, rule in [
        (changed(0, "s", version=2), "views[0].faces.s.version", "version"),        # a carried face keeps 1
        (changed(0, "s", op_seq=moved_at), "views[0].faces.s.op_seq", "op_seq"),     # ... and the base's op_seq
        (changed(0, "n", version=1), "views[0].faces.n.version", "version"),         # a re-rendered face moves on
        (changed(0, "n", op_seq=head), "views[0].faces.n.op_seq", "op_seq"),         # ... to the tiles job's at_seq
        (changed(0, "s", id=face_of(base, v0, "n")["id"], ids=face_of(base, v0, "n")["ids"]), "views[0].faces.s.id", "carried"),
        (changed(0, "s", depth=face_of(update, v0, "n")["depth"]), "views[0].faces.s.depth", "carried"),
    ]:
        assert has(refused(client, token, c2, m), path, rule), (path, rule)
    # Agreeing values are accepted beside omitted ones (view 0's n and s say them, the rest leave them out).
    good = changed(0, "n", version=2, op_seq=moved_at)
    good["views"][0]["faces"]["s"].update(id=old["id"], ids=old["ids"], depth=old["depth"], version=1, op_seq=head)
    res = complete(client, token, c2, good)
    assert res.status_code == 200, res.text

    after = output(client, a, set_id)
    assert after["job_id"] == c2["job"]["job_id"] and after["tour"] == base["tour"]  # the tour carried
    for v in after["views"]:
        for f in FACES:
            face, was = v["faces"][f], face_of(base, v["view"], f)
            if f in ("n", "e"):
                assert (face["version"], face["op_seq"]) == (2, moved_at), (v["view"], f)
                assert face["depth"] != was["depth"]
                assert face["id"] == face_of(update, v["view"], f)["id"] and face["ids"] == face_of(update, v["view"], f)["ids"]
            else:
                assert {k: face[k] for k in ("id", "ids", "depth", "version", "op_seq", "tiles")} == {
                    k: was[k] for k in ("id", "ids", "depth", "version", "op_seq", "tiles")
                }, (v["view"], f)
    for v in after["views"]:  # every file named is served
        for face in v["faces"].values():
            for key in ("id", "ids", "depth"):
                assert client.get(f"/tiles/{face[key]}.{EXT[key]}").status_code == 200

    # A second update re-renders n only: n version 3, e keeps 2, the rest 1.
    again_at = push_touch(client, a, pid, MOVED[:1])
    c3 = claimed(client, token)
    assert c3["job"]["base_manifest_job_id"] == c2["job"]["job_id"]
    third = copy.deepcopy(fixture_manifest("manifest-panorama.json", c3))
    for v in third["views"]:
        for f in FACES:
            was = face_of(after, v["view"], f)
            v["faces"][f] = {"rendered": f == "n", "reason": "changed" if f == "n" else "carried",
                             "tiles": face_of(pano, v["view"], f)["tiles"] if f == "n" else was["tiles"]}
    third, third_files = headset(third, salt="3", faces=("n",), tour=False)
    upload_outputs(client, token, c3, rendered_tiles(third))
    upload(client, token, c3, third_files)
    assert complete(client, token, c3, third).status_code == 200
    last = output(client, a, set_id)
    for v in last["views"]:
        got = {f: (v["faces"][f]["version"], v["faces"][f]["op_seq"]) for f in FACES}
        assert got == {"n": (3, again_at), "e": (2, moved_at), "s": (1, head), "w": (1, head), "u": (1, head), "d": (1, head)}
    assert job(client, rj(a), set_id)["output_job_id"] == c3["job"]["job_id"]


def test_pf6d_base_from_before_1_4(client, rig):
    """A base stored before PF6d (no version, no files): its carried faces
    answer version 1 and the base's at_seq, the re-rendered ones version 2;
    nothing is invented for the files."""
    a, token, pid, head = rig["a"], rig["token"], rig["pid"], rig["head"]
    set_id = submitted(client, rj(a), project_id=pid, at_seq=head, views=VIEWS, follow=True)["job_id"]
    c = claimed(client, token)
    finish(client, token, c)
    legacy = fixture_manifest("manifest-panorama.json", c)
    tiles.put_json(tiles.manifest_key(set_id), legacy)  # as a 1.3 platform stored it
    moved_at = push_touch(client, a, pid, MOVED)
    c2 = claimed(client, token)
    finish(client, token, c2, "manifest-tiles.json", wall_s=30)
    out = output(client, a, set_id)
    part = load("manifest-tiles.json")
    assert bare(out["views"]) == part["views"] and "tour" not in out
    for v in out["views"]:
        for f, face in v["faces"].items():
            want = (2, moved_at) if face["rendered"] else (1, head)
            assert (face["version"], face["op_seq"]) == want, (v["view"], f)
            assert not {"id", "ids", "depth"} & set(face)


# --- 5. the tile collector -------------------------------------------------------------------------


def test_pf6d_gc_keeps_named_face_files(client, rig, monkeypatch):
    """render.tiles.gc keeps the png and json files a kept manifest names
    (faces and tour) and deletes unnamed ones past the grace, as for jpg tiles."""
    a, token = rig["a"], rig["token"]
    submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"], views=VIEWS)
    c = claimed(client, token)
    m, files = headset(fixture_manifest("manifest-panorama.json", c))
    upload_outputs(client, token, c, rendered_tiles(m))
    upload(client, token, c, files)
    assert complete(client, token, c, m).status_code == 200
    store = get_store()
    named = {info.key for info in store.list("tiles/")}
    assert {k for k in named if k.endswith((".png", ".json"))} == {f"tiles/{s}.{'json' if t == 'application/json' else 'png'}" for s, (_, t) in files.items()}
    assert tiles.all_files(tiles.read_json(tiles.manifest_key(c["job"]["job_id"]))) == named
    orphans = [f"tiles/{'e' * 64}.png", f"tiles/{'f' * 64}.json", f"tiles/{'d' * 64}.jpg"]
    for key in orphans:
        store.put(key, b"orphan", content_type="application/octet-stream")
    clk = Clock(monkeypatch)
    clk.advance(days=2)
    assert tasks.run_due(clk.at, only=["render.tiles.gc"], force=True) == ["render.tiles.gc"]
    assert {info.key for info in store.list("tiles/")} == named
    clk.advance(days=91)
    assert tasks.run_due(clk.at, only=["render.tiles.gc"], force=True) == ["render.tiles.gc"]
    assert store.list("tiles/") == []


# --- 6. render-jobs/1.4 on every route (PF6c's two tests, moved) -----------------------------------


def _versions(send, label: str) -> None:
    """`send(headers)` answers with the 1.4 echo for 1.0 to 1.4 and no
    contract header, and 400 `contract_version` for 2.0."""
    for sent in SENT:
        extra = {} if sent is None else {"X-Truebex-Contract": sent}
        res = send(extra)
        assert res.status_code < 400, (label, sent, res.status_code, res.text)
        assert res.headers["X-Truebex-Contract"] == ECHO, (label, sent)
    body = error_of(send({"X-Truebex-Contract": "render-jobs/2.0"}), 400, "contract_version")
    assert body["data"]["supported"] == [ECHO], label


def test_pf6d_echo_1_4(client, rig):
    a, token, pid, head = rig["a"], rig["token"], rig["pid"], rig["head"]
    dev = {"Authorization": f"Bearer {a.token}"}
    wrk = {"Authorization": f"Bearer {token}"}
    body = {"kind": "panorama", "project_id": pid, "at_seq": head, "views": VIEWS}
    _versions(lambda h: client.post("/jobs", json=body, headers={**dev, **h, "Idempotency-Key": hex32()}), "5.1")
    _versions(lambda h: client.get("/jobs", headers={**dev, **h}), "5.3")
    _versions(lambda h: client.get("/jobs/usage", headers={**dev, **h}), "5.6")
    _versions(lambda h: client.get("/analysis/catalogue", headers={**dev, **h}), "analysis")
    rec = client.get("/jobs", headers=rj(a)).json()["jobs"][0]
    _versions(lambda h: client.get(f"/jobs/{rec['job_id']}", headers={**dev, **h}), "5.2")
    not_ready = client.get(f"/jobs/{rec['job_id']}/output", headers=rj(a))
    assert not_ready.status_code == 409 and not_ready.headers["X-Truebex-Contract"] == ECHO
    queued = [submitted(client, rj(a), **body)["job_id"] for _ in range(len(SENT) + 1)]
    to_cancel = iter(queued)
    _versions(lambda h: client.post(f"/jobs/{next(to_cancel)}/cancel", headers={**dev, **h}), "5.4")
    assert client.post(f"/jobs/{queued[-1]}/cancel", headers=rj(a)).status_code == 200  # the one 2.0 left

    # /workers: a claim's 200 and 204 answers are written by hand (workers.ECHO); 5.1's six jobs are claimed.
    claim_body = {"worker_id": "pc-rtx", "kinds": ["panorama"], "app_version": "1.1.0", "doc_version_max": 38, "wait_s": 0}
    for sent in SENT:
        extra = {} if sent is None else {"X-Truebex-Contract": sent}
        res = client.post("/workers/claim", json=claim_body, headers={**wrk, **extra})
        assert res.status_code == 200 and res.headers["X-Truebex-Contract"] == ECHO, (sent, res.text)
        c = res.json()
        _versions(lambda h: client.post(
            f"/workers/jobs/{c['job']['job_id']}/heartbeat", json={"lease_id": c["lease_id"], "progress": 0.5, "message": "m"},
            headers={**wrk, **h},
        ), "5.8")
        fail = {"lease_id": c["lease_id"], "code": "bad_input", "message": "t", "retryable": False}
        _versions(lambda h: client.post(f"/workers/jobs/{c['job']['job_id']}/fail", json=fail, headers={**wrk, **h}), "5.10")
    nothing = client.post("/workers/claim", json=claim_body, headers=wk(token))
    assert nothing.status_code == 204 and nothing.headers["X-Truebex-Contract"] == ECHO
    error_of(client.post("/workers/claim", json=claim_body, headers={**wrk, "X-Truebex-Contract": "render-jobs/2.0"}), 400, "contract_version")
    submitted(client, rj(a), **body)
    c = claimed(client, token, kinds=["panorama"])
    done = finish(client, token, c)
    assert done["state"] == "succeeded"
    for sent in SENT[:-1]:
        again = client.post(
            f"/workers/jobs/{c['job']['job_id']}/complete",
            json={"lease_id": c["lease_id"], "output": {}, "usage": {"wall_s": 1, "class": "gpu-std"}},
            headers={**wrk, "X-Truebex-Contract": sent},
        )
        assert again.status_code == 200 and again.headers["X-Truebex-Contract"] == ECHO, sent  # 5.9 repeats per lease
    _versions(lambda h: client.get(f"/jobs/{c['job']['job_id']}/output", headers={**dev, **h}), "5.5")

    # The analysis kinds' routes (PF11c's rig) and /v1/jobs (PF12).
    cpu = issue_worker(client, rig["admin"], name="cpu-eu-01", kinds=ANALYSIS_KINDS, cls="cpu-8")
    geometry, ids = (FIX / "wind-geometry.bin").read_bytes(), (FIX / "wind-entities.bin").read_bytes()
    put_inputs(client, a.dev, geometry, ids)
    wind = wind_job_body(geometry, ids)
    _versions(lambda h: client.post("/jobs", json=wind, headers={**dev, **h, "Idempotency-Key": hex32()}), "5.1 wind")
    cpu_claim = client.post(
        "/workers/claim", json={**claim_body, "worker_id": "cpu-eu-01", "kinds": list(ANALYSIS_KINDS), "doc_version_max": 0},
        headers={"Authorization": f"Bearer {cpu}", "X-Truebex-Contract": "render-jobs/1.2"},
    )
    assert cpu_claim.status_code == 200 and cpu_claim.headers["X-Truebex-Contract"] == ECHO, cpu_claim.text
    key = make_key(client, a.session, ALL_SCOPES)
    _versions(lambda h: client.get("/v1/jobs", headers=kh(key, **h)), "v1 5.3")
    _versions(lambda h: client.get("/v1/jobs/usage", headers=kh(key, **h)), "v1 5.6")
    _versions(lambda h: client.get(f"/v1/jobs/{c['job']['job_id']}", headers=kh(key, **h)), "v1 5.2")
    _versions(lambda h: client.post("/v1/jobs", json=body, headers=kh(key, **h, **{"Idempotency-Key": hex32()})), "v1 5.1")
    missing = client.get(f"/jobs/{hex32()}", headers=rj(a))
    assert missing.status_code == 404 and missing.headers["X-Truebex-Contract"] == ECHO
    # RJ, the tests' own header, is what PR5's headset sends (CL4's desktop client sends 1.3, served above).
    assert RJ == {"X-Truebex-Contract": ECHO}


def test_pf6d_clients_and_documents_speak_1_4():
    """The routers, the worker wrapper, the website's client, the demo scripts,
    the developer document and the SDKs speak render-jobs/1.4; the record's
    1.3.0 keys stay documented; the web still names PF11c's airflow kind; the
    site's manifest type names the 1.4 keys; this task's doc pins the app's
    contract (PF6c's documents test, moved)."""
    app_dir = ROOT / "server" / "app"
    for name in ("jobs.py", "workers.py", "analysis.py", "v1/jobs.py"):
        source = (app_dir / "routers" / name).read_text(encoding="utf-8")
        assert 'contract("render-jobs", 1, 4)' in source and not re.search(r'contract\("render-jobs", 1, [0-3]\)', source), name
    assert 'ECHO = {"X-Truebex-Contract": "render-jobs/1.4"}' in (app_dir / "routers" / "workers.py").read_text(encoding="utf-8")
    assert 'CONTRACT = "render-jobs/1.4"' in (ROOT / "worker" / "truebex_worker.py").read_text(encoding="utf-8")
    jobs_ts = (ROOT / "src" / "lib" / "jobs.ts").read_text(encoding="utf-8")
    assert '"X-Truebex-Contract": "render-jobs/1.4"' in jobs_ts and '"airflow"' in jobs_ts.split("export type JobKind", 1)[1].split(";", 1)[0]
    record_ts = jobs_ts.split("export interface JobRecord", 1)[1].split("\n}", 1)[0]
    assert "output_job_id: string | null;" in record_ts and "base_job_id: string | null;" in record_ts and "trigger?: JobTrigger | null;" in record_ts
    face_ts = jobs_ts.split("export interface TileFace", 1)[1].split("\n}", 1)[0]
    for key in ("id?: string;", "ids?: string;", "depth?: string;", "version?: number;", "op_seq?: number;"):
        assert key in face_ts, key
    assert "tour?: string;" in jobs_ts.split("export interface TileManifest", 1)[1].split("\n}", 1)[0]
    assert '"airflow"' in (ROOT / "src" / "app" / "dashboard" / "admin" / "render" / "page.tsx").read_text(encoding="utf-8")
    for script in ("demo_analysis.py", "demo_render.py", "demo_mobile.py"):
        source = (ROOT / "server" / "scripts" / script).read_text(encoding="utf-8")
        assert '"render-jobs/1.4"' in source, script
        assert not re.search(r"render-jobs/1\.[0-3]\b", source), script
    assert '"jobs": "render-jobs/1.4"' in (ROOT / "server" / "scripts" / "export_openapi.py").read_text(encoding="utf-8")
    doc = json.loads((ROOT / "openapi" / "v1.json").read_text(encoding="utf-8"))
    jobs_ops = [op for p, item in doc["paths"].items() if p.startswith("/v1/jobs") for op in item.values()]
    assert jobs_ops and {op["x-truebex-contract"] for op in jobs_ops} == {ECHO}
    assert "airflow" in doc["components"]["schemas"]["JobRequest"]["properties"]["kind"]["enum"]
    assert tuple(int(x) for x in doc["info"]["version"].split(".")) >= (1, 4, 0)  # the document grew
    record = doc["components"]["schemas"]["Job"]["properties"]
    assert {"follow", "base_job_id", "output_job_id", "trigger"} <= set(record)
    for key in ("base_job_id", "output_job_id", "trigger"):
        assert record[key].get("description"), key
    assert set(doc["components"]["schemas"]["JobTrigger"]["properties"]) == TRIGGER_KEYS
    for sdk in (ROOT / "sdks" / "python" / "truebex" / "_operations.py", ROOT / "sdks" / "js" / "src" / "operations.mjs"):
        source = sdk.read_text(encoding="utf-8")
        assert not re.search(r"render-jobs/1\.[0-3]\b", source) and source.count(ECHO) == len(jobs_ops), sdk
    assert "class JobTrigger(" in (ROOT / "sdks" / "python" / "truebex" / "models.py").read_text(encoding="utf-8")
    assert re.search(r"^\s+JobTrigger: \{", (ROOT / "sdks" / "js" / "src" / "schema.d.ts").read_text(encoding="utf-8"), re.M)
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")
    assert 'airflow: "Airflow study"' in constants
    demo = (ROOT / "server" / "scripts" / "demo_analysis.py").read_text(encoding="utf-8")
    assert "--wind-job" in demo and '"entities"' in demo
    render_demo = (ROOT / "server" / "scripts" / "demo_render.py").read_text(encoding="utf-8")
    assert 'add_parser("show"' in render_demo and 'add_parser("output"' in render_demo and "output_job_id" in render_demo
    assert '"tour"' in render_demo and '"version"' in render_demo  # `output` prints the 1.4 keys
    feature = (ROOT / "docs" / "roadmap" / "40" / "PF6d-render-jobs-1-4-0.md").read_text(encoding="utf-8")
    assert APP_MAIN in feature and RENDER_JOBS_BLOB[:8] in feature and "1.4.0" in feature


# --- 7. the worker wrapper uploads the files the renderer writes ----------------------------------


def _load_worker():
    spec = importlib.util.spec_from_file_location("truebex_worker", ROOT / "worker" / "truebex_worker.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["truebex_worker"] = module
    spec.loader.exec_module(module)
    return module


def test_pf6d_worker_uploads_face_files(client, rig, tmp_path, monkeypatch):
    """The wrapper (render-jobs/1.4) uploads the id, ids, depth and tour files
    the renderer writes under out/tiles/ (the fake app with
    FAKE_TRUEBEX_FACE_FILES=1 stands in for CL3's 1.4 worker): the panorama's
    faces answer them, version 1; an edit's update writes new files for the
    faces it renders (version 2) and carries the tour without writing it again."""
    W = _load_worker()
    monkeypatch.setenv("FAKE_TRUEBEX_FACE_FILES", "1")
    a = rig["a"]

    class Transport:
        def request(self, method, url, headers, body, timeout):
            res = client.request(method, url, headers=headers, content=body)
            return W.Response(res.status_code, {k.lower(): v for k, v in res.headers.items()}, res.content)

    cfg = W.Config(
        api="http://testserver", token=rig["token"], worker_id="pc-rtx", app=str(ROOT / "worker" / "tests" / "fake_truebex.py"),
        work_dir=str(tmp_path / "jobs"), app_version="1.1.0", doc_version_max=38, heartbeat_s=0.2, wait_s=0, keep_work=True,
    )
    lines: list[str] = []
    sent_headers: list[str] = []

    class Spy(Transport):
        def request(self, method, url, headers, body, timeout):
            if "/workers/" in url:
                sent_headers.append(headers.get("X-Truebex-Contract"))
            return super().request(method, url, headers, body, timeout)

    runner = W.Runner(cfg, W.Api(cfg, transport=Spy(), sleep=lambda s: None, log=lines.append))
    set_id = submitted(client, rj(a), project_id=rig["pid"], at_seq=rig["head"], views=VIEWS, follow=True)["job_id"]
    assert runner.run_once(wait_s=0) == "succeeded", lines
    assert sent_headers and set(sent_headers) == {"render-jobs/1.4"}
    out = output(client, a, set_id)
    written = Path(cfg.work_dir) / set_id / "out" / "tiles"
    assert isinstance(out.get("tour"), str) and (written / f"{out['tour']}.json").is_file()
    for v in out["views"]:
        for f, face in v["faces"].items():
            assert (face["version"], face["op_seq"]) == (1, rig["head"]) and face["rendered"]
            for key in ("id", "ids", "depth"):
                assert (written / f"{face[key]}.{EXT[key]}").is_file(), (v["view"], f, key)
    one = out["views"][0]["faces"]["n"]
    got = client.get(f"{out['tiles_base']}/{one['depth']}.png")
    assert got.status_code == 200 and got.headers["Content-Type"] == "image/png"
    assert struct.unpack(">IIBB", got.content[16:26]) == (PX, PX, 16, 0)
    ids = client.get(f"{out['tiles_base']}/{one['ids']}.json").json()
    assert ids["schema"] == "truebex-ids/1" and ids["ids"][0] is None
    tour = client.get(f"{out['tiles_base']}/{out['tour']}.json").json()
    assert tour["format"] == "truebex-tour/1" and [n["view"] for n in tour["nodes"]] == VIEWS

    moved_at = push_touch(client, a, rig["pid"], MOVED)
    assert runner.run_once(wait_s=0) == "succeeded", lines
    tiles_job = client.get("/jobs", params={"kind": "tiles"}, headers=rj(a)).json()["jobs"][0]
    update_dir = Path(cfg.work_dir) / tiles_job["job_id"] / "out" / "tiles"
    assert not (update_dir / f"{out['tour']}.json").exists()  # the tour carried, not written again
    after = output(client, a, set_id)
    assert after["job_id"] == tiles_job["job_id"] and after["tour"] == out["tour"]
    for v in after["views"]:
        for f, face in v["faces"].items():
            was = face_of(out, v["view"], f)
            if face["rendered"]:
                assert (face["version"], face["op_seq"]) == (2, moved_at) and face["depth"] != was["depth"]
                assert (update_dir / f"{face['depth']}.png").is_file()
            else:
                assert {k: face[k] for k in NEW_FACE_KEYS} == {k: was[k] for k in NEW_FACE_KEYS}
    assert any("complete" in line and "13 faces rendered" in line for line in lines)


# --- the CDN in front of the bucket holds the same keys ---------------------------------------------


def test_pf6d_cdn_holds_the_same_keys(client, monkeypatch):
    """With STORAGE_BACKEND=s3 and CDN_BASE_URL the files are published to the
    bucket under tiles/<sha256>.<ext> with their media type, and tiles_base
    (the CDN's /tiles) + "/<sha256>.<ext>" is the object's public URL; the
    API's /tiles route redirects there."""
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from app.routers import tiles as tiles_router
    from app.storage.s3 import S3Store

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="truebex-test")
        store = S3Store(
            bucket="truebex-test", endpoint=None, region="us-east-1", access_key_id="testing", secret_access_key="testing",
            cdn_base_url="https://cdn.truebex.test",
        )
        monkeypatch.setattr(tiles, "get_store", lambda: store)
        monkeypatch.setattr(tiles_router, "get_store", lambda: store)
        monkeypatch.setattr(
            tiles, "get_settings",
            lambda: SimpleNamespace(tiles_base_url="", storage_backend="s3", cdn_base_url="https://cdn.truebex.test", api_url="http://testserver"),
        )
        data = face_files(VIEWS[0], "n")
        blobs = {}
        for key, body in data.items():
            store.put(f"uploads/x/{sha(body)}", body, content_type="application/octet-stream")
            blobs[tiles.tile_key(sha(body), EXT[key])] = SimpleNamespace(storage_key=f"uploads/x/{sha(body)}")
        jpeg_body = b"\xff\xd8\xff jpeg"
        store.put("uploads/x/j", jpeg_body, content_type="application/octet-stream")
        blobs[tiles.tile_key(sha(jpeg_body))] = SimpleNamespace(storage_key="uploads/x/j")
        from app.licence import clock

        assert tiles.publish_tiles(None, blobs, clock.now()) == 4
        base = tiles.tiles_base()
        assert base == "https://cdn.truebex.test/tiles"
        for key, body in data.items():
            name = f"{sha(body)}.{EXT[key]}"
            info = store.stat(f"tiles/{name}")
            assert info is not None and info.content_type == TYPE[EXT[key]] and info.cache_control == tiles.IMMUTABLE
            assert store.signed_get_url(f"tiles/{name}") == f"{base}/{name}"
            res = client.get(f"/tiles/{name}", follow_redirects=False)
            assert res.status_code == 307 and res.headers["location"] == f"{base}/{name}"
        assert store.stat(f"tiles/{sha(jpeg_body)}.jpg").content_type == "image/jpeg"
