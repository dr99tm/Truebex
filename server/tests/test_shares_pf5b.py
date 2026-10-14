"""PF5b: share pages follow share-bundle 1.1.0 (the app's PR4): the app's
file names and rule ids, Update into an existing share (5.4
`replace_share_id`), the share record's `version`, the plan data on 403
`quota_exceeded`, and the page's cover and project card. The app's own
fixtures are checked in test_share_contract_fixtures.py."""

import copy
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from app import plans
from app.config import get_settings
from app.database import SessionLocal
from app.shares import card, manifest, page
from app.shares import service as shares
from app.shares.models import Share, ShareDerivative
from app.storage import get_store
from app.uploads.models import Blob

from .licence_helpers import Clock, activated, error_of
from .pf12_helpers import kh, make_key
from .test_pf12_webhooks import hook, receiver, resolver  # noqa: F401 (fixtures)
from .test_pf12_webhooks import run as run_webhooks
from .share_helpers import (
    CONTRACT,
    CONTRACT_FIXTURES,
    SHARE_FIXTURES,
    app_blobs_by_sha,
    blobs_by_sha,
    contract_json,
    create,
    dev,
    device_token,
    house,
    published,
    upload_files,
    web,
)
from .conftest import signup

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")

BUNDLE_2 = "5" * 32
BUNDLE_Y = "6" * 32
MIB = 1024 * 1024
OTHER = "0" * 63 + "1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rel(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}" if parts.query else parts.path


def _meta(html: str, prop: str) -> str | None:
    m = re.search(rf'<meta (?:property|name)="{re.escape(prop)}" content="([^"]*)"', html)
    return m.group(1) if m else None


def _pairs(errors: list[dict]) -> list[tuple[str, str]]:
    return sorted((e["path"], e["rule"]) for e in errors)


def cover_jpeg(size: tuple[int, int] = (1200, 630)) -> bytes:
    """A link-preview cover as the app writes one (a JPEG, 1200 x 630 by default)."""
    img = Image.new("RGB", size, (190, 120, 60))
    draw = ImageDraw.Draw(img)
    draw.rectangle((size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] * 3 // 4), fill=(30, 60, 90))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def update_of(x: dict, bundle_id: str = BUNDLE_Y) -> tuple[dict, dict[str, bytes]]:
    """Bundle Y for an Update of a share on PF5's house X: X without the hall
    and the drawings, plus the app's render as a second render and a cover.
    Returns Y and the bytes of the files X does not have."""
    m = copy.deepcopy(x)
    m["bundle_id"] = bundle_id
    hall = next(p for p in m["panoramas"] if p["id"] == "p3")
    m["panoramas"] = [p for p in m["panoramas"] if p["id"] != "p3"]
    for p in m["panoramas"]:
        p["hotspots"] = [h for h in p.get("hotspots", []) if h["target"] != "p3"]
    pdf = m["sheets"]["file"]
    m["sheets"] = None
    garden, cover = (CONTRACT_FIXTURES / "render-640.jpg").read_bytes(), cover_jpeg()
    m["renders"].append({"id": "r2", "title": "Garden", "file": sha(garden), "width": 640, "height": 360})
    m["cover"] = sha(cover)
    m["files"] = [f for f in m["files"] if f["sha256"] not in (hall["file"], pdf)] + [
        {"sha256": sha(garden), "bytes": len(garden), "content_type": "image/jpeg", "name": "renders/garden.jpg"},
        {"sha256": sha(cover), "bytes": len(cover), "content_type": "image/jpeg", "name": "cover.jpg"},
    ]
    return m, {sha(garden): garden, sha(cover): cover}


# --- (a) the app's file names and rule ids -------------------------------------------------


def test_pf5b_file_names_with_folders(client):
    """A file name is a relative path inside the bundle (the app's rule): a
    folder is fine; empty, `..`, a leading `/`, `\\` and `:` are refused. Names
    travel to the page; a download is named by the last segment; storage
    never sees a name."""
    m = house()
    m["files"][0]["name"] = "tour/living-2k.jpg"
    assert manifest.check(m) == []
    for bad in ("", "../x.jpg", "/x.jpg", "a\\b.jpg", "c:x.jpg", "tour/../x.jpg", None, 7):
        b = copy.deepcopy(m)
        b["files"][0]["name"] = bad
        assert _pairs(manifest.check(b)) == [("files[0].name", "file_name")], bad

    names = {
        "living-room.jpg": "tour/ground/living-room.jpg",
        "kitchen.jpg": "tour/ground/kitchen.jpg",
        "hall.jpg": "tour/ground/hall.jpg",
        "street-view.jpg": "renders/street view.jpg",
        "drawings.pdf": "drawings/set A/house plans.pdf",
    }
    m = house("7" * 32)
    for f in m["files"]:
        f["name"] = names[f["name"]]
    token, _ = device_token(client)
    share = published(client, token, m)
    data = client.get(f"/s/{share['slug']}", headers=CONTRACT).json()
    assert [f["name"] for f in data["manifest"]["files"]] == list(names.values())
    files = blobs_by_sha()
    for f in data["manifest"]["files"]:
        got = client.get(_rel(f["url"]))
        assert got.status_code == 200 and got.content == files[f["sha256"]], f["name"]
    pdf = next(f for f in data["manifest"]["files"] if f["content_type"] == "application/pdf")
    disposition = client.get(_rel(pdf["url"])).headers["content-disposition"]
    assert disposition == "attachment; filename*=utf-8''house%20plans.pdf"
    assert shares.download_name("drawings/house.pdf") == "house.pdf"
    assert shares.download_name('plans/"A".pdf') == "_A_.pdf"
    assert shares.download_name("set/") == "set" and shares.download_name("") == "file"
    # Files are content-addressed: no name reaches a storage key.
    with SessionLocal() as db:
        keys = [b.storage_key for b in db.scalars(select(Blob))]
    assert len(keys) == 5 and all("tour" not in k and "drawings" not in k and " " not in k for k in keys)
    html = client.get(f"/view/{share['slug']}").text
    assert "drawings/set A" not in html


# Each case: PF5's valid house with one thing broken, and exactly the
# {path, rule} pairs the app's CadShareBundle::Validate answers for it.
def _rule_cases() -> list[tuple[str, object, list[tuple[str, str]]]]:
    def files_set(i, **kw):
        return lambda m: m["files"][i].update(kw)

    def pano_set(i, **kw):
        return lambda m: m["panoramas"][i].update(kw)

    def many(key, n, make):
        return lambda m: m[key].extend(make(m, k) for k in range(n))

    def drop(path):
        def edit(m):
            obj = m
            for k in path[:-1]:
                obj = obj[k]
            del obj[path[-1]]

        return edit

    cover = {"sha256": sha(b"cover"), "bytes": 5, "content_type": "image/jpeg", "name": "cover.jpg"}
    return [
        ("panorama_width", pano_set(0, width=3000, height=1500), [("panoramas[0].width", "panorama_width")]),
        ("panorama_ratio", pano_set(0, height=1000), [("panoramas[0].width", "panorama_ratio")]),
        ("ratio and width", pano_set(1, width=3072), [("panoramas[1].width", "panorama_ratio"), ("panoramas[1].width", "panorama_width")]),
        ("panorama_type", files_set(0, content_type="image/png"), [("panoramas[0].file", "panorama_type")]),
        ("panorama_bytes", files_set(0, bytes=30 * MIB + 1), [("panoramas[0].file", "panorama_bytes")]),
        ("panorama 30 MiB", files_set(0, bytes=30 * MIB), []),
        ("panorama_count", many("panoramas", 48, lambda m, k: {**m["panoramas"][2], "id": f"q{k}"}), [("panoramas", "panorama_count")]),
        ("bearing_range 360", pano_set(0, center_bearing_deg=360), [("panoramas[0].center_bearing_deg", "bearing_range")]),
        ("bearing_range missing", drop(["panoramas", 0, "center_bearing_deg"]), [("panoramas[0].center_bearing_deg", "bearing_range")]),
        ("bearing_range start", pano_set(0, start_bearing_deg=-1), [("panoramas[0].start_bearing_deg", "bearing_range")]),
        ("bearing_range hotspot", lambda m: m["panoramas"][0]["hotspots"][0].update(bearing_deg=400), [("panoramas[0].hotspots[0].bearing_deg", "bearing_range")]),
        ("pitch_range", lambda m: m["panoramas"][0]["hotspots"][1].update(pitch_deg=-95), [("panoramas[0].hotspots[1].pitch_deg", "pitch_range")]),
        ("pitch_range start", pano_set(0, start_pitch_deg=91), [("panoramas[0].start_pitch_deg", "pitch_range")]),
        ("hfov_range", pano_set(0, start_hfov_deg=0), [("panoramas[0].start_hfov_deg", "hfov_range")]),
        ("hfov 180", pano_set(0, start_hfov_deg=180), []),
        ("hfov 5", pano_set(0, start_hfov_deg=5), []),
        ("render_edge", lambda m: m["renders"][0].update(width=9000, height=5000), [("renders[0].width", "render_edge")]),
        ("render_edge zero", lambda m: m["renders"][0].update(height=0), [("renders[0].width", "render_edge")]),
        ("render_type", files_set(3, content_type="application/pdf"), [("renders[0].file", "render_type")]),
        ("render_bytes", files_set(3, bytes=25 * MIB + 1), [("renders[0].file", "render_bytes")]),
        ("render_count", many("renders", 50, lambda m, k: {**m["renders"][0], "id": f"s{k}"}), [("renders", "render_count")]),
        ("sheets_type", files_set(4, content_type="image/png"), [("sheets.file", "sheets_type")]),
        ("sheets_bytes", files_set(4, bytes=200 * MIB + 1), [("sheets.file", "sheets_bytes")]),
        ("sheets_pages", lambda m: m["sheets"].update(pages=0), [("sheets.pages", "sheets_pages")]),
        ("sheets_entry", lambda m: m.update(sheets="drawings"), [("sheets", "sheets_entry"), ("files[4]", "file_unreferenced")]),
        ("file_duplicate", lambda m: m["files"].append(dict(m["files"][0])), [("files[5]", "file_duplicate")]),
        ("file_hash_format", files_set(0, sha256="ABC"),
         [("files[0]", "file_unreferenced"), ("files[0].sha256", "file_hash_format"), ("panoramas[0].file", "file_unlisted")]),
        ("file_bytes", files_set(0, bytes=0), [("files[0].bytes", "file_bytes")]),
        ("file_type", files_set(0, content_type="image/gif"), [("files[0].content_type", "file_type"), ("panoramas[0].file", "panorama_type")]),
        ("file_entry", lambda m: m["files"].append("x"), [("files[5]", "file_entry")]),
        ("file_unlisted", lambda m: m["renders"][0].update(file=OTHER), [("files[3]", "file_unreferenced"), ("renders[0].file", "file_unlisted")]),
        ("file_unreferenced", lambda m: m["files"].append({"sha256": OTHER, "bytes": 10, "content_type": "image/png", "name": "x.png"}),
         [("files[5]", "file_unreferenced")]),
        ("name_length", pano_set(0, title="N" * 61), [("panoramas[0].title", "name_length")]),
        ("name_length render", lambda m: m["renders"][0].update(title="N" * 61), [("renders[0].title", "name_length")]),
        ("title_length", lambda m: m["project"].update(title="T" * 121), [("project.title", "title_length")]),
        ("label_length", lambda m: m["panoramas"][0]["hotspots"][0].update(label="L" * 61), [("panoramas[0].hotspots[0].label", "label_length")]),
        ("duplicate_id", lambda m: m["panoramas"].append(dict(m["panoramas"][2])), [("panoramas[3].id", "duplicate_id")]),
        ("duplicate_id empty", lambda m: m["panoramas"].append({**m["panoramas"][2], "id": ""}), [("panoramas[3].id", "duplicate_id")]),
        ("hotspot_target", lambda m: m["panoramas"][0]["hotspots"][0].update(target="p9"), [("panoramas[0].hotspots[0].target", "hotspot_target")]),
        ("hotspot_target self", lambda m: m["panoramas"][0]["hotspots"][0].update(target="p1"), [("panoramas[0].hotspots[0].target", "hotspot_target")]),
        ("hotspot_entry", lambda m: m["panoramas"][0]["hotspots"].append(5), [("panoramas[0].hotspots[2]", "hotspot_entry")]),
        ("panorama_entry", lambda m: m["panoramas"].append("x"), [("panoramas[3]", "panorama_entry")]),
        ("render_entry", lambda m: m["renders"].append(None), [("renders[1]", "render_entry")]),
        ("project", drop(["project"]), [("project", "project")]),
        ("eye_mm", pano_set(0, eye_mm=[1, 2]), [("panoramas[0].eye_mm", "eye_mm")]),
        ("start", lambda m: m.update(start="r1"), [("start", "start")]),
        ("units", lambda m: m["project"].update(units="feet"), [("project.units", "units")]),
        ("region", lambda m: m["project"].update(region="gbr"), [("project.region", "region")]),
        ("bundle_id", lambda m: m.update(bundle_id="XYZ"), [("bundle_id", "bundle_id")]),
        ("schema", lambda m: m.update(schema="truebex-share/2"), [("schema", "schema")]),
        # 1.1: the cover is a JPEG listed in files, and it counts as a use of that file.
        ("cover", lambda m: (m["files"].append(dict(cover)), m.update(cover=cover["sha256"])), []),
        ("cover is a use", lambda m: m["files"].append(dict(cover)), [("files[5]", "file_unreferenced")]),
        ("cover_type", lambda m: m.update(cover=m["files"][4]["sha256"]), [("cover", "cover_type")]),
        ("cover unlisted", lambda m: m.update(cover=OTHER), [("cover", "file_unlisted")]),
        ("cover null", lambda m: m.update(cover=None), []),
        # The other 1.1 keys are the reader's to ignore.
        ("1.1 keys", lambda m: (m.update(branding={"designed_in": True}, plan="pro", app_build="source"),
                                m["project"].update(storeys=2, rooms=5, floor_area_m2=128.5)), []),
    ]  # fmt: skip


# The app's rule ids (CadShareBundle::Validate, app main 7fe6b2c2). The
# platform answers each of these but total_bytes (it answers 403
# quota_exceeded `share_bytes` instead), plus its own three.
APP_RULES = {
    "json", "schema", "bundle_id", "file_entry", "file_hash_format", "file_bytes", "file_type", "file_name",
    "file_duplicate", "total_bytes", "file_unlisted", "project", "title_length", "units", "region",
    "panorama_count", "panorama_entry", "duplicate_id", "name_length", "panorama_ratio", "panorama_width",
    "panorama_type", "panorama_bytes", "eye_mm", "bearing_range", "pitch_range", "hfov_range", "hotspot_entry",
    "hotspot_target", "label_length", "start", "render_count", "render_entry", "render_edge", "render_type",
    "render_bytes", "sheets_entry", "sheets_type", "sheets_bytes", "sheets_pages", "cover_type", "file_unreferenced",
}  # fmt: skip
PLATFORM_ONLY = {"type", "empty", "file_content"}
OLD_IDS = {
    "pano_size", "pano_type", "pano_bytes", "pano_count", "bearing", "pitch", "hfov", "render_size", "text_length",
    "file_listed", "file_referenced", "file_unique", "sha256", "id_unique",
}  # fmt: skip


@pytest.mark.parametrize("name,edit,want", _rule_cases(), ids=[c[0] for c in _rule_cases()])
def test_pf5b_rule_ids_are_the_apps(name, edit, want):
    m = house()
    edit(m)
    got = manifest.check(m)
    assert _pairs(got) == sorted(want)
    assert all(e["message"] == manifest.MESSAGES[e["rule"]] for e in got)


def test_pf5b_rule_messages_one_per_id():
    assert set(manifest.MESSAGES) == (APP_RULES - {"total_bytes"}) | PLATFORM_ONLY
    assert not set(manifest.MESSAGES) & OLD_IDS
    assert all(isinstance(t, str) and t.endswith(".") for t in manifest.MESSAGES.values())
    assert _pairs(manifest.check([])) == [("", "json")]


def test_pf5b_share_fixtures_up_to_date():
    """PF5's own set moved to tests/fixtures/share/; its script writes and checks it there."""
    assert (SHARE_FIXTURES / "pano-2048-kitchen.jpg").is_file()
    run = subprocess.run(
        [sys.executable, str(ROOT / "server" / "scripts" / "make_share_fixtures.py"), "--check"],
        capture_output=True, text=True, timeout=300, cwd=ROOT / "server",
    )
    assert run.returncode == 0, run.stdout + run.stderr
    cases = json.loads((SHARE_FIXTURES / "manifest-invalid.json").read_text(encoding="utf-8"))["cases"]
    rules = {e["rule"] for c in cases for e in c["expect"]["errors"]}
    assert rules <= set(manifest.MESSAGES) and not rules & OLD_IDS


# --- (b) Update with replace_share_id, and the record's version ---------------------------------


def test_pf5b_update_keeps_the_link(client, monkeypatch):
    Clock(monkeypatch)
    token, session = device_token(client)
    x = house()
    a = published(client, token, x)
    assert a["version"] == 1 and a["bundle_id"] == x["bundle_id"]
    assert client.post(f"/s/{a['slug']}/visits", json={"visitor": "a" * 32}, headers=CONTRACT).status_code == 204
    y, extra = update_of(x)
    data = {**blobs_by_sha(), **extra}
    hall = next(p["file"] for p in x["panoramas"] if p["id"] == "p3")
    pdf = x["sheets"]["file"]

    # 5.4 into share A: the same share_id, slug and url; while Y uploads the
    # share answers as it was (live, version 1, bundle X), as the app's stub does.
    res = create(client, token, y, title="House — revised", replace=a["share_id"])
    assert res.status_code == 201, res.text
    body = res.json()
    s = body["share"]
    assert (s["share_id"], s["slug"], s["url"]) == (a["share_id"], a["slug"], a["url"])
    assert (s["state"], s["version"], s["bundle_id"]) == ("live", 1, x["bundle_id"])
    assert s["title"] == "House — revised"
    states = {f["sha256"]: f["state"] for f in body["upload"]["files"]}
    assert states == {f["sha256"]: "missing" if f["sha256"] in extra else "present" for f in y["files"]}
    # The same request again answers the same share and upload.
    again = create(client, token, y, title="House — revised", replace=a["share_id"])
    assert again.status_code == 200 and again.json()["share"] == s
    assert again.json()["upload"]["upload_id"] == body["upload"]["upload_id"]

    # A stays live on X's files until 5.5 publishes Y.
    page_data = client.get(f"/s/{a['slug']}", headers=CONTRACT).json()
    assert page_data["manifest"]["bundle_id"] == x["bundle_id"] and page_data["version"] == 1
    assert len(page_data["manifest"]["panoramas"]) == 3 and page_data["manifest"]["sheets"]
    err = error_of(client.post(f"/shares/{a['share_id']}/publish", headers=dev(token)), 422, "upload_incomplete")
    assert sorted(err["data"]["missing"]) == sorted(extra)
    got = client.get(f"/shares/{a['share_id']}", headers=web(session)).json()
    assert (got["state"], got["version"], got["bundle_id"]) == ("live", 1, x["bundle_id"])

    assert upload_files(client, token, body["upload"], data=data) == 2
    res = client.post(f"/shares/{a['share_id']}/publish", headers=dev(token))
    assert res.status_code == 200, res.text
    live = res.json()["share"]
    assert (live["share_id"], live["slug"], live["url"]) == (a["share_id"], a["slug"], a["url"])
    assert (live["state"], live["version"], live["bundle_id"]) == ("live", 2, BUNDLE_Y)
    assert live["visits"]["total"] == 1  # the visits are kept
    page_data = client.get(f"/s/{a['slug']}", headers=CONTRACT).json()
    assert page_data["manifest"]["bundle_id"] == BUNDLE_Y and page_data["version"] == 2
    assert [p["id"] for p in page_data["manifest"]["panoramas"]] == ["p1", "p2"]
    assert [r["id"] for r in page_data["manifest"]["renders"]] == ["r1", "r2"] and page_data["manifest"]["sheets"] is None
    for f in page_data["manifest"]["files"]:
        assert client.get(_rel(f["url"])).content == data[f["sha256"]], f["name"]

    # X's files that nothing else references are dropped; the ones Y keeps stay.
    store = get_store()
    with SessionLocal() as db:
        blobs = {b.sha256: b.refs for b in db.scalars(select(Blob))}
        derived = db.scalars(select(ShareDerivative).where(ShareDerivative.share_id == a["share_id"])).all()
        row = db.get(Share, a["share_id"])
        assert row.pending_bundle_id is None and row.pending_manifest is None
    assert hall not in blobs and pdf not in blobs
    assert {f["sha256"]: blobs.get(f["sha256"]) for f in y["files"]} == {f["sha256"]: 1 for f in y["files"]}
    assert {d.source_sha256 for d in derived} == {p["file"] for p in y["panoramas"]}
    assert store.stat(f"shares/{a['share_id']}/derived/{hall}-pano-1024.jpg") is None

    # The page previews Y: its cover, at an image URL preview caches have not seen.
    html = client.get(f"/view/{a['slug']}").text
    image = _meta(html, "og:image")
    assert image == f"{get_settings().share_base}/s/{a['slug']}/card.jpg?v=2"
    assert client.get(urlsplit(image).path).content == extra[y["cover"]]
    assert _meta(html, "og:description") == "2 panoramas and 2 renders."

    # The same request after the publish, and 5.5 again: the same share, version 2.
    after = create(client, token, y, title="House — revised", replace=a["share_id"])
    assert after.status_code == 200 and (after.json()["share"]["share_id"], after.json()["share"]["version"]) == (a["share_id"], 2)
    assert client.post(f"/shares/{a['share_id']}/publish", headers=dev(token)).json()["share"]["version"] == 2


def test_pf5b_update_conflicts(client, monkeypatch):
    """A revoked or expired share answers 409 replace_conflict; another
    account's 404; an Update left pending when the share ends cannot publish."""
    clk = Clock(monkeypatch)
    token, session = device_token(client)
    a = published(client, token)
    y, extra = update_of(house())

    other, _ = device_token(client, email="other@example.com", fingerprint="b" * 64)
    error_of(create(client, other, y, replace=a["share_id"]), 404, "not_found")
    error_of(create(client, token, y, replace="0" * 32), 404, "not_found")
    error_of(create(client, token, y, replace="not-a-share"), 404, "not_found")

    clk.advance(days=30, seconds=1)
    err = error_of(create(client, token, y, replace=a["share_id"]), 409, "replace_conflict")
    assert err["data"] == {"state": "expired", "share_id": a["share_id"]}
    # The same request again answers the same.
    assert error_of(create(client, token, y, replace=a["share_id"]), 409, "replace_conflict")["data"]["state"] == "expired"

    b = published(client, token, house(BUNDLE_2))  # the expired share freed the slot
    client.delete(f"/shares/{b['share_id']}", headers=web(session))
    err = error_of(create(client, token, update_of(house(BUNDLE_2), "9" * 32)[0], replace=b["share_id"]), 409, "replace_conflict")
    assert err["data"]["state"] == "revoked"
    with SessionLocal() as db:
        rows = db.scalars(select(Share)).all()
    assert len(rows) == 2 and all(r.pending_bundle_id is None for r in rows)
    assert {r.bundle_id for r in rows} == {house()["bundle_id"], BUNDLE_2}

    # An Update started, then the share revoked: its publish answers 410.
    c = published(client, token, house("c" * 32))
    res = create(client, token, update_of(house("c" * 32), "d" * 32)[0], replace=c["share_id"])
    assert res.status_code == 201, res.text
    upload_files(client, token, res.json()["upload"], data={**blobs_by_sha(), **extra})
    client.delete(f"/shares/{c['share_id']}", headers=dev(token))
    error_of(client.post(f"/shares/{c['share_id']}/publish", headers=dev(token)), 410, "share_gone")
    error_of(client.get(f"/s/{c['slug']}", headers=CONTRACT), 410, "share_gone")


def test_pf5b_update_of_an_uploading_share(client):
    """An Update of a share that never went live takes the new bundle at once
    (nothing is served yet); its first publish is version 1."""
    token, _ = device_token(client)
    first = create(client, token).json()["share"]
    y, extra = update_of(house())
    res = create(client, token, y, title="House — take two", replace=first["share_id"])
    assert res.status_code == 201, res.text
    s = res.json()["share"]
    assert (s["share_id"], s["state"], s["version"], s["bundle_id"], s["title"]) == (
        first["share_id"], "uploading", 1, BUNDLE_Y, "House — take two")
    upload_files(client, token, res.json()["upload"], data={**blobs_by_sha(), **extra})
    live = client.post(f"/shares/{first['share_id']}/publish", headers=dev(token)).json()["share"]
    assert (live["state"], live["version"], live["bundle_id"]) == ("live", 1, BUNDLE_Y)
    # X's bundle id is free again: the old bundle starts a share of its own.
    with SessionLocal() as db:
        assert db.scalar(select(Share).where(Share.bundle_id == house()["bundle_id"])) is None


def test_pf5b_update_limits(client, monkeypatch):
    """An Update takes no new live-share slot; its bytes and expiry are the
    tier's like any share's."""
    token, _ = device_token(client)
    a = published(client, token)
    error_of(create(client, token, house(BUNDLE_2)), 403, "quota_exceeded")  # Free: one live share
    y, _ = update_of(house())
    err = error_of(create(client, token, y, days=31, replace=a["share_id"]), 422, "expiry_too_far")
    assert err["data"]["max_days"] == 30
    monkeypatch.setattr(get_settings(), "share_max_bytes", 1000)
    err = error_of(create(client, token, y, replace=a["share_id"]), 403, "quota_exceeded")
    assert err["data"]["kind"] == "share_bytes" and err["data"]["used"] == sum(f["bytes"] for f in y["files"])
    monkeypatch.setattr(get_settings(), "share_max_bytes", 1024**3)
    assert create(client, token, y, replace=a["share_id"]).status_code == 201


def test_pf5b_version_in_every_answer(client):
    """`version` (6.2, 1.1): 1 on a new share, in 5.4 to 5.9."""
    token, session = device_token(client)
    res = create(client, token)
    assert res.json()["share"]["version"] == 1  # 5.4
    sid = res.json()["share"]["share_id"]
    upload_files(client, token, res.json()["upload"])
    assert client.post(f"/shares/{sid}/publish", headers=dev(token)).json()["share"]["version"] == 1  # 5.5
    assert [s["version"] for s in client.get("/shares", headers=web(session)).json()["shares"]] == [1]  # 5.6
    assert client.get(f"/shares/{sid}", headers=dev(token)).json()["version"] == 1  # 5.7
    assert client.patch(f"/shares/{sid}", json={"title": "Renamed"}, headers=dev(token)).json()["version"] == 1  # 5.8
    assert client.delete(f"/shares/{sid}", headers=dev(token)).json()["version"] == 1  # 5.9
    # The server speaks share-bundle 1.1 now.
    assert client.get("/shares", headers=web(session)).headers["X-Truebex-Contract"] == "share-bundle/1.1"


def test_pf5b_update_sends_share_published(client, resolver, receiver):
    """PF12's `share.published` webhook fires for an Update's publish too, with version 2."""
    session = signup(client, "owner@example.com")
    hook(client, make_key(client, session, ["shares:write", "webhooks:manage"]), ["share.published"])
    token = activated(client, session)["device_token"]
    a = published(client, token)
    y, extra = update_of(house())
    res = create(client, token, y, replace=a["share_id"])
    upload_files(client, token, res.json()["upload"], data={**blobs_by_sha(), **extra})
    assert client.post(f"/shares/{a['share_id']}/publish", headers=dev(token)).json()["share"]["version"] == 2
    run_webhooks()
    got = [b["data"] for b in receiver.bodies() if b["type"] == "share.published"]
    assert [(d["share_id"], d["version"], d["bundle_id"]) for d in got] == [
        (a["share_id"], 1, house()["bundle_id"]), (a["share_id"], 2, BUNDLE_Y)]


def test_pf5b_v1_update_with_api_key(client):
    """/v1/shares (PF12) takes replace_share_id like 5.4."""
    session = signup(client, "designer@example.com")
    auth = kh(make_key(client, session, ["shares:write"]), **CONTRACT)
    token = activated(client, session)["device_token"]  # the same account's device
    a = published(client, token)
    y, extra = update_of(house())
    res = client.post("/v1/shares", json={"title": "House", "manifest": y, "replace_share_id": a["share_id"]}, headers=auth)
    assert res.status_code == 201, res.text
    assert (res.json()["share"]["share_id"], res.json()["share"]["version"]) == (a["share_id"], 1)
    doc = json.loads((ROOT / "openapi" / "v1.json").read_text(encoding="utf-8"))
    schemas = doc["components"]["schemas"]
    assert {"version", "bundle_id"} <= set(schemas["Share"]["properties"])
    assert "replace_share_id" in schemas["ShareRequest"]["properties"]


# --- (c) the quota data ------------------------------------------------------------------------


def test_pf5b_quota_names_the_plan_that_lifts_it(client, monkeypatch):
    token, _ = device_token(client)
    published(client, token)
    # The catalogue's GD7 placeholders: every plan keeps one live share, so none lifts it.
    err = error_of(create(client, token, house(BUNDLE_2)), 403, "quota_exceeded")
    assert err["data"] == {"kind": "share_links", "limit": 1, "used": 1, "plan": "free", "upgrade_to": None}
    # The lowest plan whose limit admits one more.
    monkeypatch.setitem(plans.PLANS["studio"].limits, "share_links", 10)
    assert error_of(create(client, token, house(BUNDLE_2)), 403, "quota_exceeded")["data"]["upgrade_to"] == "studio"
    monkeypatch.setitem(plans.PLANS["pro"].limits, "share_links", 3)
    assert error_of(create(client, token, house(BUNDLE_2)), 403, "quota_exceeded")["data"]["upgrade_to"] == "pro"
    monkeypatch.setitem(plans.PLANS["pro"].limits, "share_links", None)  # no limit
    assert error_of(create(client, token, house(BUNDLE_2)), 403, "quota_exceeded")["data"]["upgrade_to"] == "pro"

    # Bytes: only a plan whose share_bytes holds the bundle.
    size = sum(f["bytes"] for f in house()["files"])
    monkeypatch.setattr(get_settings(), "share_max_bytes", 1000)
    third, _ = device_token(client, email="third@example.com", fingerprint="d" * 64)
    err = error_of(create(client, third), 403, "quota_exceeded")
    assert err["data"] == {"kind": "share_bytes", "limit": 1000, "used": size, "plan": "free", "upgrade_to": None}
    monkeypatch.setitem(plans.PLANS["team"].limits, "share_bytes", size)
    assert error_of(create(client, third), 403, "quota_exceeded")["data"]["upgrade_to"] == "team"
    monkeypatch.setitem(plans.PLANS["studio"].limits, "share_bytes", 2 * size)
    assert error_of(create(client, third), 403, "quota_exceeded")["data"]["upgrade_to"] == "studio"

    # data.plan is the caller's plan: a Pro trial over Pro's limit is sent to Studio.
    pro, _ = device_token(client, email="pro@example.com", fingerprint="e" * 64)
    trial = client.post("/licence/trial", json={"plan": "pro"}, headers={"Authorization": f"Bearer {pro}"})
    assert trial.status_code == 201, trial.text
    err = error_of(create(client, pro), 403, "quota_exceeded")
    assert (err["data"]["plan"], err["data"]["upgrade_to"]) == ("pro", "studio")


# --- (d) the page: cover and project card ---------------------------------------------------------


def test_pf5b_cover_is_the_link_preview(client):
    token, _ = device_token(client)
    m = house()
    cover = cover_jpeg()
    m["cover"] = sha(cover)
    m["files"].append({"sha256": sha(cover), "bytes": len(cover), "content_type": "image/jpeg", "name": "cover.jpg"})
    share = published(client, token, m, data={**blobs_by_sha(), sha(cover): cover})
    html = client.get(f"/view/{share['slug']}").text
    image = _meta(html, "og:image")
    assert image == f"{get_settings().share_base}/s/{share['slug']}/card.jpg"  # version 1: PF5's URL
    assert client.get(urlsplit(image).path).content == cover  # the cover itself, byte for byte
    assert (_meta(html, "og:image:width"), _meta(html, "og:image:height")) == ("1200", "630")
    assert _meta(html, "twitter:image") == image

    # A cover of another size is fitted to 1200 x 630 (cropped to fill, never stretched).
    for size in ((1600, 1000), (800, 800), (2400, 1260)):
        fitted = Image.open(io.BytesIO(card.from_cover(cover_jpeg(size))))
        assert fitted.size == (1200, 630) and fitted.format == "JPEG"

    # Without a cover the card is PF5's, from the start panorama, byte for byte.
    other, _ = device_token(client, email="other@example.com", fingerprint="b" * 64)
    plain = published(client, other, house(BUNDLE_2), title="Flat")
    pano = Image.open(SHARE_FIXTURES / "pano-2048.jpg").convert("RGB")
    want = card.compose(card.background_for(house(), pano, None), "Flat")
    assert client.get(f"/s/{plain['slug']}/card.jpg").content == want


def test_pf5b_project_card_on_the_page(client):
    m = house()
    m["project"].update(storeys=2, rooms=5, floor_area_m2=128.5)
    token, _ = device_token(client)
    share = published(client, token, m)
    html = client.get(f"/view/{share['slug']}").text
    assert '<p class="tbx-project">2 storeys · 5 rooms · 128.5 m²</p>' in html
    data = client.get(f"/s/{share['slug']}", headers=CONTRACT).json()
    assert {k: data["manifest"]["project"][k] for k in ("storeys", "rooms", "floor_area_m2")} == {
        "storeys": 2, "rooms": 5, "floor_area_m2": 128.5}

    def line(project: dict, units: str = "metric") -> str | None:
        return page.project_line({"project": {"title": "House", "units": units, **project}})

    assert line({"storeys": 1, "rooms": 3, "floor_area_m2": 72.75}) == "1 storey · 3 rooms · 72.75 m²"
    assert line({"storeys": 1, "rooms": 1, "floor_area_m2": 72.75}, "imperial") == "1 storey · 1 room · 783 ft²"
    assert line({"floor_area_m2": 1234.5678}) == "1,234.57 m²"
    assert line({"floor_area_m2": 1234.5678}, "imperial") == "13,289 ft²"
    assert line({"rooms": 3}) == "3 rooms"
    assert line({"storeys": 0, "rooms": -1, "floor_area_m2": 0}) is None
    assert line({"storeys": "2", "rooms": True, "floor_area_m2": float("nan")}) is None
    assert line({}) is None


def _pf5_render_view(*, title, m, url, slug, api, site, card_url, preload_url, first_render_url, pdf_url) -> str:
    """PF5's render_view (master 988334f), the oracle for a 1.0 manifest."""
    _e = page._e
    preload = (
        f'<link rel="preload" as="image" href="{_e(preload_url)}" crossorigin="anonymous" fetchpriority="high">' if preload_url else ""
    )
    noscript = []
    if first_render_url:
        noscript.append(f'<img src="{_e(first_render_url)}" alt="{_e(title)}" width="640">')
    if pdf_url:
        noscript.append(f'<p><a href="{_e(pdf_url)}">{_e(page.DOWNLOAD_PDF)}</a></p>')
    return page._VIEW.substitute(
        title=_e(page.og_title(title)), heading=_e(title), og_title=_e(page.og_title(title)),
        description=_e(page.description(m)), url=_e(url), image=_e(card_url), image_alt=_e(page.og_title(title)),
        preload=preload, site=_e(site), slug=_e(slug), api=_e(api), noscript="\n    ".join(noscript),
        designed_in=_e(page.DESIGNED_IN), get_truebex=_e(page.GET_TRUEBEX),
    )  # fmt: skip


def test_pf5b_one_point_zero_renders_as_before(client):
    """A 1.0 manifest (no cover, no project card) renders exactly as PF5 wrote it."""
    # The template is PF5a's, unchanged (the hash of its LF text on master 988334f).
    view = Path(page.__file__).with_name("templates") / "view.html"
    text = view.read_text(encoding="utf-8")
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == "cd28bea8a3c597e5a63f2648bae3e6e4036a77658ad790a8a70b4f58b4dfd042"
    args = dict(
        title="Flat <b>& garden</b>", m=house(), url="https://api.example/view/AbCdEfGhIj", slug="AbCdEfGhIj",
        api="https://api.example", site="https://truebex.com", card_url="https://api.example/s/AbCdEfGhIj/card.jpg",
        preload_url="https://api.example/files/x?sig=1", first_render_url="https://api.example/files/r?sig=2",
        pdf_url="https://api.example/files/p?sig=3",
    )
    assert page.render_view(**args) == _pf5_render_view(**args)
    for m in (house(), {**house(), "cover": None}):
        assert page.render_view(**{**args, "m": m}) == _pf5_render_view(**args)
    token, _ = device_token(client)
    share = published(client, token)
    html = client.get(f"/view/{share['slug']}").text
    assert "tbx-project" not in html and _meta(html, "og:image").endswith("/card.jpg")


def test_pf5b_plan_and_app_build_never_public(client):
    """The app's 1.1 `plan` and `app_build` are stored, never shown publicly."""
    m = contract_json("manifest-house.json")
    token, session = device_token(client)
    share = published(client, token, m, data=app_blobs_by_sha())
    with SessionLocal() as db:
        stored = db.get(Share, share["share_id"]).manifest
    assert (stored["plan"], stored["app_build"]) == ("pro", "fixture")
    data = client.get(f"/s/{share['slug']}", headers=CONTRACT).json()
    assert "plan" not in data["manifest"] and "app_build" not in data["manifest"]
    assert data["manifest"]["branding"] == {"designed_in": True} and data["designed_in"] == "Truebex"
    for text in (client.get(f"/view/{share['slug']}").text, client.get("/shares", headers=web(session)).text,
                 client.get(f"/shares/{share['share_id']}", headers=dev(token)).text):
        assert "fixture" not in text and '"pro"' not in text


# --- the viewer --------------------------------------------------------------------------------


def test_pf5b_copy_in_step():
    """The server's project-card words are SHARE_PROJECT_CARD's (constants.ts)."""
    text = (ROOT / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")
    block = re.search(r"export const SHARE_PROJECT_CARD = \{(.*?)\n\} as const;", text, re.S).group(1)

    def value(key: str) -> str:
        m = re.search(rf'\b{key}:\s*"((?:[^"\\]|\\.)*)"', block)
        assert m, key
        return json.loads(f'"{m.group(1)}"')

    for key, want in page.PROJECT_CARD.items():
        assert value(key) == want, key
    assert text.rstrip().endswith("} as const;")


@needs_node
def test_pf5b_viewer_project_card_and_download_name():
    """src/viewer/project.ts writes the card the server writes, and names a download by its last segment."""
    cases = [
        ({"storeys": 1, "rooms": 3, "floor_area_m2": 72.75}, "metric"),
        ({"storeys": 1, "rooms": 1, "floor_area_m2": 72.75}, "imperial"),
        ({"storeys": 2, "rooms": 5, "floor_area_m2": 128.5}, "metric"),
        ({"floor_area_m2": 1234.5678}, "metric"),
        ({"floor_area_m2": 1234.5678}, "imperial"),
        ({"rooms": 3}, "metric"),
        ({"storeys": 0, "rooms": -1, "floor_area_m2": 0}, "metric"),
        ({"storeys": "2", "rooms": True}, "metric"),
        ({}, "metric"),
        # Halves: both round half away from zero on the number's shortest decimal form.
        ({"floor_area_m2": 0.125}, "metric"),
        ({"floor_area_m2": 72.755}, "metric"),
        ({"floor_area_m2": 2.5 / 10.763910416709722}, "imperial"),
        ({"storeys": 1200, "rooms": 2.0}, "metric"),
    ]
    script = (
        "import * as p from " + json.dumps((ROOT / "src" / "viewer" / "project.ts").as_uri()) + ";"
        f"const labels = {json.dumps(page.PROJECT_CARD)};"
        f"const cases = {json.dumps(cases)};"
        "const out = { lines: cases.map(([project, units]) => p.projectLine({ title: 'House', units, ...project }, labels)),"
        " names: ['drawings/house.pdf', 'house.pdf', 'set/', '', 'a/b/c d.pdf'].map(p.downloadName) };"
        "process.stdout.write(JSON.stringify(out));"
    )
    run = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=ROOT, env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    want = [page.project_line({"project": {"title": "House", "units": u, **pr}}) for pr, u in cases]
    assert out["lines"] == want
    assert out["lines"][:2] == ["1 storey · 3 rooms · 72.75 m²", "1 storey · 1 room · 783 ft²"]
    assert out["names"] == ["house.pdf", "house.pdf", "set", "file", "c d.pdf"]


@built
def test_pf5b_viewer_bundle_reads_1_1():
    js, css = OUT / "viewer" / "viewer.js", OUT / "viewer" / "viewer.css"
    code = js.read_text(encoding="utf-8")
    assert js.stat().st_size <= 250 * 1024
    assert "share-bundle/1.1" in code and "share-bundle/1.0" not in code
    def escaped(word: str) -> set[str]:  # esbuild writes non-ASCII as a backslash-x or backslash-u escape
        backslash = chr(92)
        formats = [backslash + f for f in ("x{:02X}", "x{:02x}", "u{:04X}", "u{:04x}")]

        def esc(ch: str, fmt: str) -> str:
            return ch if ord(ch) < 128 else fmt.format(ord(ch))

        return {word, *("".join(esc(ch, f) for ch in word) for f in formats)}

    for word in page.PROJECT_CARD.values():
        assert any(f'"{form}"' in code for form in escaped(word)), word
    assert ".tbx-project" in css.read_text(encoding="utf-8")
