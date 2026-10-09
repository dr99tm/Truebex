"""Shared plumbing PF1 creates (PF14 owns the production adapters): storage,
rate limits, background tasks, UUIDv7 ids, the signing CLI and fixtures."""

import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from app import ratelimit, tasks
from app.licence import ids, signing
from app.storage import InvalidKey, check_key, get_store, local

from .conftest import LICENCE_FIXTURES, TEST_KEY

SERVER = Path(__file__).resolve().parents[1]


def _rel(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


def test_storage_local_put_get_and_signed_urls(client, monkeypatch):
    store = get_store()
    data = b"hello storage" * 100
    info = store.put("tests/a/b.bin", io.BytesIO(data), content_type="application/x-test")
    assert info.bytes == len(data) and info.sha256 == hashlib.sha256(data).hexdigest()
    assert store.stat("tests/a/b.bin").content_type == "application/x-test"
    with store.open("tests/a/b.bin") as fh:
        assert fh.read() == data
    assert [b.key for b in store.list("tests/a/")] == ["tests/a/b.bin"]

    url = store.signed_get_url("tests/a/b.bin", expires_in=60, filename="b.bin")
    assert client.get(_rel(url)).content == data
    assert client.get(_rel(url).replace("sig=", "sig=x")).status_code == 403
    real = local.clock
    monkeypatch.setattr(local, "clock", lambda: real() + 61)
    assert client.get(_rel(url)).status_code == 403
    monkeypatch.setattr(local, "clock", real)

    put = store.signed_put_url("tests/up.txt", content_type="text/plain", max_bytes=10)
    assert client.put(_rel(put), content=b"0123456789", headers={"Content-Type": "text/plain"}).status_code == 201
    assert store.stat("tests/up.txt").bytes == 10
    assert client.put(_rel(put), content=b"0123456789!", headers={"Content-Type": "text/plain"}).status_code == 413
    assert client.put(_rel(put), content=b"x", headers={"Content-Type": "image/png"}).status_code == 415
    assert client.put(_rel(put).replace("max=10", "max=99"), content=b"x", headers={"Content-Type": "text/plain"}).status_code == 403

    for bad in ("../etc/passwd", "/abs", "a//b", "a/./b", "a\\b", "", "x.meta.json"):
        with pytest.raises(InvalidKey):
            check_key(bad)
    assert client.get("/files/..%2F..%2Fsecret?exp=1&sig=x").status_code in (403, 404, 422)
    store.delete("tests/a/b.bin")
    assert store.stat("tests/a/b.bin") is None


def test_ratelimit_blocks_after_limit(monkeypatch):
    ratelimit.reset()
    now = [1000.0]
    monkeypatch.setattr(ratelimit, "clock", lambda: now[0])
    for _ in range(3):
        assert ratelimit.take("t", "ip", per_minute=3, burst=3) is None
    wait = ratelimit.take("t", "ip", per_minute=3, burst=3)
    assert wait == pytest.approx(20.0)
    assert ratelimit.take("t", "other-ip", per_minute=3, burst=3) is None
    now[0] += 20
    assert ratelimit.take("t", "ip", per_minute=3, burst=3) is None


def test_tasks_run_due(client):
    calls = []

    @tasks.periodic("test.job", 60)
    def job(db, now):
        calls.append(now)

    try:
        from datetime import datetime, timedelta, timezone

        t0 = datetime(2026, 10, 9, tzinfo=timezone.utc)
        assert "test.job" in tasks.run_due(t0)
        assert "test.job" not in tasks.run_due(t0 + timedelta(seconds=30))
        assert "test.job" in tasks.run_due(t0 + timedelta(seconds=60))
        assert len(calls) == 2
    finally:
        tasks.JOBS.pop("test.job", None)


def test_uuid7_ids_ordered_and_formatted():
    made = [ids.uuid7_hex() for _ in range(500)]
    assert made == sorted(made) and len(set(made)) == 500
    for value in made[:20]:
        assert re.fullmatch(r"[0-9a-f]{32}", value)
        assert value[12] == "7" and value[16] in "89ab"
    # The first 48 bits are Unix milliseconds.
    import time

    assert abs(int(made[-1][:12], 16) - time.time() * 1000) < 60_000
    assert ids.is_id(made[0]) and not ids.is_id("x" * 32)


def test_signing_cli_verify(tmp_path, capsys):
    fixture = LICENCE_FIXTURES / "entitlement-pro.json"
    keys = LICENCE_FIXTURES / "keys.json"
    assert signing._cli(["verify", str(fixture), "--keys", str(keys)]) == 0
    assert capsys.readouterr().out.startswith("valid · plan pro · expires 2026-10-23T11:00:00Z")
    assert signing._cli(["verify", str(LICENCE_FIXTURES / "entitlement-tampered.json"), "--keys", str(keys)]) == 1
    assert "INVALID" in capsys.readouterr().out
    feed = json.loads((LICENCE_FIXTURES / "releases-stable.json").read_text(encoding="utf-8"))
    entry = tmp_path / "entry.json"
    entry.write_text(json.dumps(feed["body"]["releases"][0]), encoding="utf-8")
    assert signing._cli(["verify", str(entry), "--keys", str(keys)]) == 0
    assert capsys.readouterr().out.startswith("valid · release 1.1.0")
    # With the server's own keys (5.12) the TEST-signed fixture is valid too.
    assert signing._cli(["verify", str(fixture)]) == 0
    assert TEST_KEY["kid"] in signing.keys_by_use("entitlement")


def test_licence_fixtures_up_to_date():
    spec = importlib.util.spec_from_file_location("make_licence_fixtures", SERVER / "scripts" / "make_licence_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    built = module.build()
    on_disk = {p.name: p.read_bytes() for p in LICENCE_FIXTURES.iterdir() if p.is_file()}
    assert set(built) == set(on_disk)
    for name, data in built.items():
        assert on_disk[name] == data, f"{name} was edited by hand (fixtures are copied, never edited)"
