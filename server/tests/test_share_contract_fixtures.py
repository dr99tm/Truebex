"""PF5b: the platform against the app's own share-bundle fixtures
(contracts/share-bundle.md 1.1.0 §9). PR4 wrote them in the app repo with
CadShareBundle::BuildManifest (Docs/roadmap/fixtures/contracts/share-bundle/);
scripts/sync-contract-fixtures.ps1 copied them byte for byte into
tests/contracts/share-bundle/ from app main 7fe6b2c2. PF5's own three-room
set, which the older share tests count on, is tests/fixtures/share/.
"""

import hashlib
import io
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from app.shares import manifest

from .licence_helpers import error_of
from .share_helpers import (
    CONTRACT,
    CONTRACT_FIXTURES,
    app_blobs_by_sha,
    contract_json,
    create,
    dev,
    device_token,
    upload_files,
    web,
)

# The app commit the folder was copied from, and the app's blob of each file
# there (`git ls-tree`); README.md is the platform's own.
APP_REPO = Path(r"T:\unreal5_7_4_projects\truebex_compact")
APP_COMMIT = "7fe6b2c21d6e7849398b1cfb73f93c2f4c3083f7"
APP_DIR = "Docs/roadmap/fixtures/contracts/share-bundle"
APP_BLOBS = {
    "manifest-house.json": "a453a1c2784c000d5c24d4d20ab0e00c2825b70e",
    "manifest-invalid.json": "5f1f9bc3048ec55e95acfa41c2ed903f8b4b00a7",
    "pano-2048.jpg": "e3f73907916f3420635d90b3eb9b875faa1fe3d9",
    "qr-stub-link.txt": "3622438f1d974a548da98330928dd51b9809ff15",
    "render-640.jpg": "bf8c1feab4889590fd3719a19015153f03c3cd04",
    "sheets-2p.pdf": "fd8491297fe9f74be95f2b2ff0a7545f483d37c7",
    "visits.json": "7827b9ff20955766dec546d2f63813524ac9bd50",
}


def git_blob_id(data: bytes) -> str:
    """`git hash-object --no-filters`: the blob id of these exact bytes."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _rel(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}" if parts.query else parts.path


def _meta(html: str, prop: str) -> str | None:
    m = re.search(rf'<meta (?:property|name)="{re.escape(prop)}" content="([^"]*)"', html)
    return m.group(1) if m else None


def _pairs(errors: list[dict]) -> list[tuple[str, str]]:
    return sorted((e["path"], e["rule"]) for e in errors)


def test_contract_folder_is_the_apps_copy():
    """tests/contracts/share-bundle/ holds the app's seven files and this
    folder's README, each the app's blob byte for byte."""
    files = {p.name for p in CONTRACT_FIXTURES.iterdir() if p.is_file()}
    assert files == set(APP_BLOBS) | {"README.md"}
    for name, blob in APP_BLOBS.items():
        data = (CONTRACT_FIXTURES / name).read_bytes()
        assert git_blob_id(data) == blob, name
        if name.endswith((".json", ".txt")):
            assert b"\r" not in data, name  # the blob's LF, not a CRLF checkout
    # The README names the commit it was copied from.
    assert APP_COMMIT[:8] in (CONTRACT_FIXTURES / "README.md").read_text(encoding="utf-8")
    # Where the app repository is on this machine, git agrees: its ls-tree at
    # that commit against `git hash-object --no-filters` of each copy.
    git = shutil.which("git")
    if git is None or not (APP_REPO / ".git").exists():
        return
    tree = subprocess.run(
        [git, "-C", str(APP_REPO), "ls-tree", APP_COMMIT, "--", APP_DIR + "/"],
        capture_output=True, text=True, timeout=60,
    )
    if tree.returncode != 0:  # the commit is not in this clone
        return
    listed = {}
    for line in tree.stdout.splitlines():
        meta, path = line.split("\t", 1)
        listed[path.rsplit("/", 1)[1]] = meta.split()[2]
    assert listed == APP_BLOBS
    for name, blob in APP_BLOBS.items():
        here = subprocess.run(
            [git, "hash-object", "--no-filters", "--", str(CONTRACT_FIXTURES / name)],
            capture_output=True, text=True, timeout=60,
        )
        assert here.stdout.strip() == blob, name


def test_apps_house_manifest_passes_the_rules():
    """The manifest the app writes (folders in file names, the 1.1 keys) breaks no rule."""
    m = contract_json("manifest-house.json")
    assert [f["name"] for f in m["files"]] == ["drawings/house.pdf", "renders/street.jpg", "tour/living-2k.jpg"]
    assert manifest.check(m) == []


def test_apps_invalid_manifest_answers_exactly_its_errors(client):
    """manifest-invalid.json: exactly its three {path, rule} pairs, order free,
    from the validator and from 5.4."""
    case = contract_json("manifest-invalid.json")
    want = _pairs(case["errors"])
    assert want == [
        ("panoramas[0].hotspots[0].target", "hotspot_target"),
        ("panoramas[1].width", "panorama_ratio"),
        ("renders[0].file", "file_unlisted"),
    ]
    got = manifest.check(case["manifest"])
    assert _pairs(got) == want
    assert all(e["message"] == manifest.MESSAGES[e["rule"]] for e in got)

    token, _ = device_token(client)
    body = error_of(create(client, token, case["manifest"]), 422, "manifest_invalid")
    assert _pairs(body["data"]["errors"]) == want


def test_apps_bundle_published_through_the_endpoints(client):
    """The app's manifest-house.json through 5.4, the parts of the app's
    pano-2048.jpg, render-640.jpg and sheets-2p.pdf through 5.2, then 5.5:
    live, and its page shows the three panoramas."""
    m = contract_json("manifest-house.json")
    data = app_blobs_by_sha()
    assert {f["sha256"] for f in m["files"]} == set(data)
    token, session = device_token(client)

    res = create(client, token, m, title="House")
    assert res.status_code == 201, res.text
    body = res.json()
    share = body["share"]
    assert share["state"] == "uploading" and share["version"] == 1 and share["bundle_id"] == m["bundle_id"]
    assert sorted(f["sha256"] for f in body["upload"]["files"]) == sorted(data)
    assert upload_files(client, token, body["upload"], data=data) == 3

    res = client.post(f"/shares/{share['share_id']}/publish", headers=dev(token))
    assert res.status_code == 200, res.text
    live = res.json()["share"]
    assert live["state"] == "live" and live["version"] == 1 and live["url"].endswith(f"/view/{live['slug']}")

    page = client.get(f"/s/{live['slug']}", headers=CONTRACT).json()
    pm = page["manifest"]
    assert [p["id"] for p in pm["panoramas"]] == ["p1", "p2", "p3"]
    assert [p["title"] for p in pm["panoramas"]] == ["Living room", "Kitchen", "Bedroom"]
    for p in pm["panoramas"]:
        assert set(p["derivatives"]) == {"pano-4096", "pano-1024"}
        small = client.get(_rel(p["derivatives"]["pano-1024"]["url"]))
        assert Image.open(io.BytesIO(small.content)).size == (1024, 512)
    assert pm["project"]["floor_area_m2"] == 72.75 and pm["project"]["rooms"] == 3
    # Every file opens with its own bytes; the PDF downloads as its last segment.
    for f in pm["files"]:
        got = client.get(_rel(f["url"]))
        assert got.status_code == 200 and got.content == data[f["sha256"]], f["name"]
    pdf = next(f for f in pm["files"] if f["name"] == "drawings/house.pdf")
    assert client.get(_rel(pdf["url"])).headers["content-disposition"] == 'attachment; filename="house.pdf"'

    html = client.get(f"/view/{live['slug']}").text
    assert _meta(html, "og:description") == "3 panoramas, 1 render and the drawings."
    assert "1 storey · 3 rooms · 72.75 m²" in html
    card = client.get(urlsplit(_meta(html, "og:image")).path)
    assert card.status_code == 200 and Image.open(io.BytesIO(card.content)).size == (1200, 630)

    listed = client.get("/shares", headers=web(session)).json()["shares"]
    assert [(s["share_id"], s["version"], s["bundle_id"]) for s in listed] == [(share["share_id"], 1, m["bundle_id"])]
