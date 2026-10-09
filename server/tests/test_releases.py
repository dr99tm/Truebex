"""Release feed, downloads, admin upload and the publish script (5.13, 5.14, §6.4)."""

import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.licence import signing
from app.models import DownloadEvent, User
from app.releases.models import Release
from app.releases import service
from app.storage import get_store, local

from .conftest import REL_KID, REL_PUBLIC, REL_SEED, TEST_KEY, signup
from .licence_helpers import CONTRACT, error_of, published_key, session, verify_with

SERVER = Path(__file__).resolve().parents[1]
REL_KEY = signing.private_key_from_seed(REL_SEED)


def _publish(tmp_path: Path, version: str, channel: str, *, data: bytes | None = None, at: datetime | None = None):
    data = data if data is not None else f"installer {version}\n".encode() * 10
    path = tmp_path / f"Truebex-Setup-{version}.exe"
    path.write_bytes(data)
    with SessionLocal() as db:
        return service.publish(
            db, get_store(), version=version, channel=channel, platform="win64", file_path=path,
            notes_md=f"### {version}\n* Notes for **{version}**.\n", private_key=REL_KEY, kid=REL_KID,
            published_at=at,
        )


def _admin(client, email="admin@example.com"):
    h = signup(client, email=email)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        user.is_admin = True
        db.commit()
    return h


def _relative(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


def test_release_feed_signed_and_ordered(client, tmp_path):
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    stable = [f"1.0.{i}" for i in range(10)] + ["1.1.0"]
    for i, v in enumerate(reversed(stable)):  # published out of order on purpose
        _publish(tmp_path, v, "stable", at=base + timedelta(days=i))
    _publish(tmp_path, "1.2.0-beta.1", "beta", at=base + timedelta(days=20))
    _publish(tmp_path, "1.2.0-beta.2", "beta", at=base + timedelta(days=21))

    feed = client.get("/releases/feed?channel=stable&platform=win64", headers=CONTRACT).json()
    assert feed["schema"] == "truebex-releases/1" and feed["channel"] == "stable" and feed["platform"] == "win64"
    versions = [r["manifest"]["version"] for r in feed["releases"]]
    assert versions == ["1.1.0"] + [f"1.0.{i}" for i in range(9, 0, -1)]  # newest first, at most 10
    assert feed["latest"] == "1.1.0"

    beta = client.get("/releases/feed?channel=beta", headers=CONTRACT).json()
    bversions = [r["manifest"]["version"] for r in beta["releases"]]
    assert bversions[:3] == ["1.2.0-beta.2", "1.2.0-beta.1", "1.1.0"] and len(bversions) == 10
    assert beta["latest"] == "1.2.0-beta.2"

    rel_public = published_key(client, REL_KID)
    assert rel_public == REL_PUBLIC
    for entry in feed["releases"] + beta["releases"]:
        m, sig = entry["manifest"], entry["signature"]
        assert sig["alg"] == "Ed25519" and sig["kid"] == REL_KID and len(sig["value"]) == 86
        verify_with(rel_public, m, sig["value"])
        assert m["schema"] == "truebex-release/1" and m["platform"] == "win64"
        assert m["notes_url"] == f"https://truebex.com/changelog/#{m['version']}"
        assert entry["download"] == f"/releases/{m['version']}/download?platform=win64"
        assert set(m) == service.MANIFEST_KEYS
    assert all(r["manifest"]["channel"] == "stable" for r in feed["releases"])

    # The entitlement key does not sign releases.
    assert TEST_KEY["kid"] not in {r["signature"]["kid"] for r in feed["releases"]}

    # A withdrawn release drops out of the feed.
    admin = _admin(client)
    res = client.patch("/admin/releases/1.1.0", json={"withdrawn": True}, headers=admin)
    assert res.status_code == 200 and res.json()["withdrawn_at"]
    assert client.get("/releases/feed", headers=CONTRACT).json()["latest"] == "1.0.9"

    error_of(client.get("/releases/feed?platform=mac", headers=CONTRACT), 422, "validation_failed")
    empty = client.get("/releases/feed", headers=CONTRACT).json()
    assert empty["releases"] and empty["releases"][0]["manifest"]["version"] == "1.0.9"


def test_download_url_expires(client, tmp_path, monkeypatch):
    data = b"\x00TRUEBEX" * 1024
    _publish(tmp_path, "1.1.0", "stable", data=data)

    res = client.get("/releases/1.1.0/download?platform=win64", headers=CONTRACT, follow_redirects=False)
    assert res.status_code == 302 and res.headers["X-Truebex-Contract"] == "licence-api/1.0"
    url = res.headers["location"]
    assert url.startswith("https://api.truebex.com/files/releases/1.1.0/win64/Truebex-Setup-1.1.0.exe?")
    query = parse_qs(urlsplit(url).query)
    assert int(query["exp"][0]) - datetime.now(timezone.utc).timestamp() == pytest.approx(900, abs=5)

    # No account needed: the URL alone downloads the file.
    got = client.get(_relative(url))
    assert got.status_code == 200 and got.content == data
    assert "attachment" in got.headers["content-disposition"] and "Truebex-Setup-1.1.0.exe" in got.headers["content-disposition"]
    part = client.get(_relative(url), headers={"Range": "bytes=0-7"})
    assert part.status_code == 206 and part.content == data[:8]

    # An altered signature, expiry or file name is refused.
    path = urlsplit(url).path
    for field, value in (("sig", query["sig"][0][:-1] + ("A" if query["sig"][0][-1] != "A" else "B")),
                         ("exp", str(int(query["exp"][0]) + 60)), ("fn", "other.exe")):
        altered = {k: v[0] for k, v in query.items()} | {field: value}
        assert client.get(f"{path}?{urlencode(altered)}").status_code == 403, field

    # 900 s later the same URL has expired.
    real = local.clock
    monkeypatch.setattr(local, "clock", lambda: real() + 901)
    error_of(client.get(_relative(url)), 403, "forbidden")
    monkeypatch.setattr(local, "clock", real)

    # The JSON form.
    js = client.get("/releases/1.1.0/download?platform=win64", headers={**CONTRACT, "Accept": "application/json"})
    assert js.status_code == 200
    body = js.json()
    assert set(body) == {"url", "expires_at", "bytes", "sha256"}
    assert body["bytes"] == len(data) and body["sha256"] == hashlib.sha256(data).hexdigest()
    left = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00")) - datetime.now(timezone.utc)
    assert timedelta(seconds=890) < left <= timedelta(seconds=900)
    assert client.get(_relative(body["url"])).content == data

    error_of(client.get("/releases/9.9.9/download", headers=CONTRACT), 404, "not_found")
    error_of(client.get("/releases/not-a-version/download", headers=CONTRACT), 404, "not_found")
    error_of(client.get("/releases/1.1.0/download?platform=mac", headers=CONTRACT), 422, "validation_failed")
    with SessionLocal() as db:
        events = list(db.scalars(select(DownloadEvent)))
        assert len(events) == 2 and {(e.version, e.platform, e.channel) for e in events} == {("1.1.0", "win64", "stable")}


def _form(manifest: dict, signature: dict, data: bytes):
    return {
        "data": {"manifest": json.dumps(manifest), "signature": json.dumps(signature)},
        "files": {"file": (manifest["installer"]["file"], data, "application/octet-stream")},
    }


def test_admin_releases_requires_admin_and_signature(client, monkeypatch):
    data = b"admin upload " * 100
    manifest = service.build_manifest(
        version="2.0.0", channel="stable", platform="win64", file_name="Truebex-Setup-2.0.0.exe",
        size=len(data), sha256=hashlib.sha256(data).hexdigest(), notes_md="### 2.0.0\n* Notes.\n",
    )
    good = signing.sign(manifest, REL_KEY, REL_KID)

    error_of(client.post("/admin/releases", **_form(manifest, good, data)), 401, "unauthenticated")
    user = signup(client)
    error_of(client.post("/admin/releases", **_form(manifest, good, data), headers=user), 403, "forbidden")
    error_of(client.get("/admin/releases", headers=user), 403, "forbidden")

    admin = _admin(client)
    # Signed by a key that is not a published rel-* key (here the entitlement key).
    lic_sig = signing.sign(manifest, signing.private_key_from_seed(TEST_KEY["private_key"]), REL_KID)
    error_of(client.post("/admin/releases", **_form(manifest, lic_sig, data), headers=admin), 422, "invalid_signature")
    # A manifest edited after signing.
    edited = {**manifest, "mandatory": True}
    error_of(client.post("/admin/releases", **_form(edited, good, data), headers=admin), 422, "invalid_signature")
    # A file that is not the one the manifest describes.
    error_of(client.post("/admin/releases", **_form(manifest, good, data + b"x"), headers=admin), 422, "installer_mismatch")
    bad = {**manifest, "channel": "stable", "version": "2.0.0-beta.1"}
    error_of(client.post("/admin/releases", **_form(bad, signing.sign(bad, REL_KEY, REL_KID), data), headers=admin), 422, "validation_failed")

    res = client.post("/admin/releases", **_form(manifest, good, data), headers=admin)
    assert res.status_code == 201, res.text
    assert res.json()["sha256"] == manifest["installer"]["sha256"] and res.json()["storage_key"] == "releases/2.0.0/win64/Truebex-Setup-2.0.0.exe"
    error_of(client.post("/admin/releases", **_form(manifest, good, data), headers=admin), 409, "conflict")
    assert [r["version"] for r in client.get("/admin/releases", headers=admin).json()["releases"]] == ["2.0.0"]

    # New notes need a new signature.
    renoted = {**manifest, "notes_md": "### 2.0.0\n* Better notes.\n"}
    error_of(client.patch("/admin/releases/2.0.0", json={"manifest": renoted, "signature": good}, headers=admin), 422, "invalid_signature")
    moved = {**renoted, "installer": {**manifest["installer"], "bytes": 1}}
    error_of(client.patch("/admin/releases/2.0.0", json={"manifest": moved, "signature": signing.sign(moved, REL_KEY, REL_KID)}, headers=admin), 422, "validation_failed")
    ok = client.patch("/admin/releases/2.0.0", json={"manifest": renoted, "signature": signing.sign(renoted, REL_KEY, REL_KID)}, headers=admin)
    assert ok.status_code == 200
    entry = client.get("/releases/feed", headers=CONTRACT).json()["releases"][0]
    assert entry["manifest"]["notes_md"] == "### 2.0.0\n* Better notes.\n"
    verify_with(REL_PUBLIC, entry["manifest"], entry["signature"]["value"])
    error_of(client.patch("/admin/releases/9.9.9", json={"withdrawn": True}, headers=admin), 404, "not_found")
    error_of(client.patch("/admin/releases/2.0.0", json={"withdrawn": True}, headers=user), 403, "forbidden")

    # The 90 MB cap (lowered here so the test stays small).
    monkeypatch.setattr(service, "MAX_UPLOAD_BYTES", 10)
    small = service.build_manifest(
        version="2.0.1", channel="stable", platform="win64", file_name="T.exe", size=len(data),
        sha256=hashlib.sha256(data).hexdigest(), notes_md="",
    )
    error_of(client.post("/admin/releases", **_form(small, signing.sign(small, REL_KEY, REL_KID), data), headers=admin), 413, "too_large")


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, SERVER / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_publish_release_script_registers_row(client, tmp_path, capsys):
    data = bytes(range(256)) * 20
    installer = tmp_path / "Truebex-Setup-1.1.0.exe"
    installer.write_bytes(data)
    notes = tmp_path / "notes.md"
    notes.write_text("### What's new\n* First signed feed entry.\n", encoding="utf-8")
    key_file = tmp_path / "rel.json"
    key_file.write_text(json.dumps({"kid": REL_KID, "private_key": REL_SEED}), encoding="utf-8")

    script = _script("publish_release")
    code = script.main([
        "--version", "1.1.0", "--channel", "stable", "--platform", "win64", "--file", str(installer),
        "--notes", str(notes), "--key-file", str(key_file),
    ])
    assert code == 0
    out = capsys.readouterr().out
    sha = hashlib.sha256(data).hexdigest()
    assert "1.1.0" in out and sha in out and "releases/1.1.0/win64/Truebex-Setup-1.1.0.exe" in out

    with SessionLocal() as db:
        row = db.scalar(select(Release).where(Release.version == "1.1.0"))
        manifest = json.loads(row.manifest)
    assert manifest["installer"] == {"file": "Truebex-Setup-1.1.0.exe", "bytes": len(data), "sha256": sha}
    assert manifest["notes_md"] == "### What's new\n* First signed feed entry.\n"
    assert signing.verify(manifest, {"alg": "Ed25519", "kid": row.kid, "value": row.signature}, {REL_KID: REL_PUBLIC})
    info = get_store().stat(row.storage_key)
    assert info.bytes == len(data) and info.sha256 == sha

    # Publishing the same version again is refused.
    assert script.main([
        "--version", "1.1.0", "--channel", "stable", "--file", str(installer), "--notes", str(notes),
        "--key-file", str(key_file),
    ]) == 1


def test_make_signing_key_script(tmp_path, capsys):
    script = _script("make_signing_key")
    out_file = tmp_path / "rel.json"
    assert script.main(["--kind", "rel", "--kid", "rel-2027-01", "--out", str(out_file)]) == 0
    printed = capsys.readouterr().out
    key = json.loads(out_file.read_text(encoding="utf-8"))
    assert key["kid"] == "rel-2027-01" and key["use"] == "release"
    assert signing.public_key_b64url(signing.private_key_from_seed(key["private_key"])) == key["public_key"]
    assert f"RELEASE_PUBLIC_KEYS=rel-2027-01:{key['public_key']}" in printed
    assert "LICENCE_SIGNING_KEY" not in printed
    assert script.main(["--kind", "lic"]) == 0
    assert "LICENCE_SIGNING_KEY=" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        script.main(["--kind", "rel", "--kid", "lic-oops"])


def test_semver_precedence():
    from app.releases import semver

    ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
               "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "1.1.0", "2.0.0"]
    assert sorted(reversed(ordered), key=semver.key) == ordered
    assert semver.is_prerelease("1.2.0-beta.3") and not semver.is_prerelease("1.2.0+build.5")
    assert not semver.is_valid("1.0") and not semver.is_valid("01.0.0") and not semver.is_valid("v1.0.0")


def test_release_fixtures_verify_with_test_key():
    fixtures = SERVER / "tests" / "contracts" / "licence"
    stub = (fixtures / "installer-stub.bin").read_bytes()
    assert len(stub) == 4096
    keys = {TEST_KEY["kid"]: TEST_KEY["public_key"]}
    for name in ("releases-stable.json", "releases-beta.json"):
        feed = json.loads((fixtures / name).read_text(encoding="utf-8"))["body"]
        assert feed["latest"] == feed["releases"][0]["manifest"]["version"]
        for entry in feed["releases"]:
            m = entry["manifest"]
            assert service.manifest_errors(m) == []
            assert signing.verify(m, entry["signature"], keys)
            assert m["installer"]["bytes"] == len(stub) and m["installer"]["sha256"] == hashlib.sha256(stub).hexdigest()
            assert m["notes_url"].endswith(f"#{m['version']}")


def test_releases_not_on_the_website_session_paths(client):
    # The feed and downloads need no account; a session is simply ignored.
    h = signup(client)
    assert client.get("/releases/feed", headers=session(h)).status_code == 200
