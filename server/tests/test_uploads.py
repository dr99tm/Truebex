"""The resumable upload (share-bundle §5.1-5.3), contract §10 platform tests and
PF5's per-endpoint tests: parts, resume, de-duplication, hashes, scoping."""

import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.storage import get_store
from app.uploads import credentials
from app.uploads import service as upload_service
from app.uploads.credentials import UploadCaller
from app.uploads.models import Blob, UploadSession

from .licence_helpers import Clock, error_of
from .share_helpers import CONTRACT, SHARE_FIXTURES, blobs_by_sha, dev, device_token, send_part, web

PANO = (SHARE_FIXTURES / "pano-2048.jpg").read_bytes()
PDF = (SHARE_FIXTURES / "sheets-2p.pdf").read_bytes()
PANO_SHA = hashlib.sha256(PANO).hexdigest()
PDF_SHA = hashlib.sha256(PDF).hexdigest()


@pytest.fixture()
def small_parts(monkeypatch):
    """10 kB parts, so the fixture panorama arrives in many parts."""
    monkeypatch.setattr(upload_service, "PART_BYTES", 10_000)
    return 10_000


def _open(client, headers, files=None, purpose="share"):
    files = files or [
        {"sha256": PANO_SHA, "bytes": len(PANO), "content_type": "image/jpeg"},
        {"sha256": PDF_SHA, "bytes": len(PDF), "content_type": "application/pdf"},
    ]
    return client.post("/uploads", json={"purpose": purpose, "files": files}, headers=headers)


def _states(body) -> dict:
    return {f["sha256"]: f for f in body["files"]}


def test_upload_parts_resume_and_dedup(client, small_parts):
    token, _ = device_token(client)
    res = _open(client, dev(token))
    assert res.status_code == 201, res.text
    body = res.json()
    assert res.headers["X-Truebex-Contract"] == "share-bundle/1.0"
    assert body["part_bytes"] == small_parts and len(body["upload_id"]) == 32
    parts = -(-len(PANO) // small_parts)
    assert _states(body)[PANO_SHA] == {"sha256": PANO_SHA, "state": "missing", "parts": parts, "received": []}
    upload_id = body["upload_id"]

    # Any order, one part repeated, one held back.
    order = [n for n in reversed(range(parts)) if n != 3] + [0]
    for n in order:
        assert send_part(client, token, upload_id, PANO_SHA, n, PANO).status_code == 204
    # Resume: the session says what arrived.
    status = client.get(f"/uploads/{upload_id}", headers=dev(token))
    assert status.status_code == 200
    pano = _states(status.json())[PANO_SHA]
    assert pano["state"] == "partial" and pano["received"] == [n for n in range(parts) if n != 3]
    assert _states(status.json())[PDF_SHA]["state"] == "missing"

    assert send_part(client, token, upload_id, PANO_SHA, 3, PANO).status_code == 204
    assert send_part(client, token, upload_id, PDF_SHA, 0, PDF).status_code == 204
    status = client.get(f"/uploads/{upload_id}", headers=dev(token)).json()
    assert {f["state"] for f in status["files"]} == {"complete"}
    # A repeated part of a complete file is harmless.
    assert send_part(client, token, upload_id, PANO_SHA, 1, PANO).status_code == 204

    with SessionLocal() as db:
        blobs = db.scalars(select(Blob)).all()
        assert sorted(b.sha256 for b in blobs) == sorted([PANO_SHA, PDF_SHA])
        stored = next(b for b in blobs if b.sha256 == PANO_SHA)
        assert stored.storage_key == f"blobs/{stored.account_id}/{PANO_SHA}" and stored.bytes == len(PANO)
    with get_store().open(stored.storage_key) as fh:
        assert fh.read() == PANO
    # The parts are gone once the file is assembled.
    assert get_store().stat(f"uploads/parts/{upload_id}/{PANO_SHA}/0") is None

    # A new session for the same files: both present, nothing to send.
    again = _open(client, dev(token)).json()
    assert {f["state"] for f in again["files"]} == {"present"}
    assert _states(again)[PANO_SHA]["received"] == list(range(parts))


def test_part_and_file_hash_mismatch(client, small_parts):
    token, _ = device_token(client)
    upload_id = _open(client, dev(token)).json()["upload_id"]

    bad = send_part(client, token, upload_id, PANO_SHA, 0, PANO, claimed="0" * 64)
    error_of(bad, 422, "part_hash_mismatch")
    res = client.put(
        f"/uploads/{upload_id}/files/{PANO_SHA}/parts/0", content=PANO[:small_parts],
        headers={**dev(token), "Content-Type": "application/octet-stream"},
    )
    error_of(res, 422, "validation_failed")  # no X-Part-Sha256
    short = client.put(
        f"/uploads/{upload_id}/files/{PANO_SHA}/parts/0", content=PANO[:100],
        headers={**dev(token), "X-Part-Sha256": hashlib.sha256(PANO[:100]).hexdigest()},
    )
    assert error_of(short, 422, "validation_failed")["data"]["expected_bytes"] == small_parts

    # Declared as one file, sent as another: every part hashes fine, the file does not.
    other = PANO[:-1] + bytes([PANO[-1] ^ 0xFF])
    declared = hashlib.sha256(other).hexdigest()
    upload_id = _open(client, dev(token), [{"sha256": declared, "bytes": len(other), "content_type": "image/jpeg"}]).json()["upload_id"]
    parts = -(-len(PANO) // small_parts)
    for n in range(parts - 1):
        assert send_part(client, token, upload_id, declared, n, PANO).status_code == 204
    last = send_part(client, token, upload_id, declared, parts - 1, PANO)
    assert error_of(last, 422, "file_hash_mismatch")["data"]["sha256"] == declared
    # The file's parts were dropped: it starts again from nothing.
    f = client.get(f"/uploads/{upload_id}", headers=dev(token)).json()["files"][0]
    assert f["state"] == "missing" and f["received"] == []
    with SessionLocal() as db:
        assert db.scalar(select(Blob).where(Blob.sha256 == declared)) is None


def test_uploads_auth_and_purpose_scoping(client, monkeypatch):
    error_of(_open(client, CONTRACT), 401, "unauthenticated")
    error_of(_open(client, {"Authorization": "Bearer tbx_live_nope", **CONTRACT}), 401, "unauthenticated")
    token, session = device_token(client)
    other_token, _ = device_token(client, email="someone@example.com")

    upload_id = _open(client, dev(token)).json()["upload_id"]
    # Another account, and the same account's website session, cannot touch a device's session.
    for headers in (dev(other_token), web(session)):
        error_of(client.get(f"/uploads/{upload_id}", headers=headers), 404, "not_found")
        res = client.put(
            f"/uploads/{upload_id}/files/{PDF_SHA}/parts/0", content=PDF,
            headers={**headers, "X-Part-Sha256": PDF_SHA},
        )
        error_of(res, 404, "not_found")
    # A website session may open its own upload.
    assert _open(client, web(session)).status_code == 201

    # job-output is for render workers only.
    error_of(_open(client, dev(token), purpose="job-output"), 403, "forbidden")
    error_of(_open(client, dev(token), purpose="anything"), 422, "validation_failed")

    worker_token = "tbx_wrk_test-worker-token"
    error_of(_open(client, {"Authorization": f"Bearer {worker_token}", **CONTRACT}, purpose="job-output"), 401, "unauthenticated")
    owner = client.get("/auth/me", headers=session).json()["id"]

    def resolve(db, raw):
        return UploadCaller(account_id=owner, kind="worker", credential_id="gpu-01") if raw == worker_token else None

    credentials.set_worker_resolver(resolve)
    try:
        worker = {"Authorization": f"Bearer {worker_token}", **CONTRACT}
        error_of(_open(client, worker, purpose="share"), 403, "forbidden")
        error_of(_open(client, worker, purpose="snapshot"), 403, "forbidden")
        res = _open(client, worker, purpose="job-output")
        assert res.status_code == 201, res.text
        worker_upload = res.json()["upload_id"]
        assert client.get(f"/uploads/{worker_upload}", headers=worker).status_code == 200
        # Even the same account's device cannot add parts to a worker's session.
        error_of(client.get(f"/uploads/{worker_upload}", headers=dev(token)), 404, "not_found")
        error_of(_open(client, {"Authorization": "Bearer tbx_wrk_other", **CONTRACT}, purpose="job-output"), 401, "unauthenticated")
    finally:
        credentials.set_worker_resolver(None)


def test_uploads_session_expired_and_out_of_range(client, monkeypatch, small_parts):
    clk = Clock(monkeypatch)
    token, _ = device_token(client)
    body = _open(client, dev(token)).json()
    upload_id = body["upload_id"]
    parts = _states(body)[PANO_SHA]["parts"]

    res = send_part(client, token, upload_id, PANO_SHA, parts, PANO + b"x" * small_parts)
    assert error_of(res, 422, "part_out_of_range")["data"]["parts"] == parts
    error_of(send_part(client, token, upload_id, "f" * 64, 0, PANO), 404, "not_found")
    assert send_part(client, token, upload_id, PANO_SHA, 0, PANO).status_code == 204

    # Validation of 5.1.
    error_of(_open(client, dev(token), [{"sha256": "xyz", "bytes": 1, "content_type": "image/jpeg"}]), 422, "validation_failed")
    error_of(_open(client, dev(token), [{"sha256": PANO_SHA, "bytes": 0, "content_type": "image/jpeg"}]), 422, "validation_failed")
    error_of(_open(client, dev(token), [{"sha256": PANO_SHA, "bytes": 10, "content_type": "text/html"}]), 422, "validation_failed")
    huge = [{"sha256": PANO_SHA, "bytes": 512 * 1024 * 1024 + 1, "content_type": "image/jpeg"}]
    error_of(_open(client, dev(token), huge), 413, "too_large")
    many = [{"sha256": f"{i:064x}", "bytes": 1, "content_type": "image/png"} for i in range(501)]
    error_of(_open(client, dev(token), many), 422, "validation_failed")
    error_of(client.post("/uploads", json={"files": []}, headers=dev(token)), 422, "validation_failed")

    clk.advance(hours=24, seconds=1)
    error_of(send_part(client, token, upload_id, PANO_SHA, 1, PANO), 410, "upload_expired")
    error_of(client.get(f"/uploads/{upload_id}", headers=dev(token)), 410, "upload_expired")

    # uploads.expire drops the session and its parts; a new session resumes by file.
    with SessionLocal() as db:
        upload_service.expire(db, clk.at)
        assert db.get(UploadSession, upload_id) is None
    assert get_store().stat(f"uploads/parts/{upload_id}/{PANO_SHA}/0") is None


def test_uploads_orphan_blobs_dropped_after_seven_days(client, monkeypatch):
    clk = Clock(monkeypatch)
    token, _ = device_token(client)
    body = _open(client, dev(token), [{"sha256": PDF_SHA, "bytes": len(PDF), "content_type": "application/pdf"}]).json()
    assert send_part(client, token, body["upload_id"], PDF_SHA, 0, PDF).status_code == 204
    with SessionLocal() as db:
        upload_service.expire(db, clk.advance(days=6))
        blob = db.scalar(select(Blob).where(Blob.sha256 == PDF_SHA))
        assert blob is not None and blob.refs == 0
        key = blob.storage_key
        upload_service.expire(db, clk.advance(days=1, seconds=1))
        assert db.scalar(select(Blob).where(Blob.sha256 == PDF_SHA)) is None
    assert get_store().stat(key) is None


def test_upload_fixture_bytes_known():
    # The helpers' map covers every file manifest-house.json names.
    from .share_helpers import house

    assert {f["sha256"] for f in house()["files"]} == set(blobs_by_sha())
    assert timedelta(hours=24) == upload_service.SESSION_LIFETIME
