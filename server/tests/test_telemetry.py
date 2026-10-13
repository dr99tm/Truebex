"""PF14: telemetry ingestion (contracts/telemetry.md §5-§7), the admin
dashboard API, retention and deletion jobs, and API crashes in the crash store.

The first eight tests are the contract's §10 platform tests, run against the
§9 fixtures in tests/contracts/telemetry/ (PF14d: the app's own set, copied
from OP1 with scripts/sync-contract-fixtures.ps1 -Contract telemetry).
"""

import copy
import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text, update

from app import mail, ratelimit, storage
from app.database import SessionLocal, engine
from app.main import app
from app.licence.models import Device
from app.models import (
    CrashGroup,
    CrashReport,
    Feedback,
    TelemetryBatch,
    TelemetryDaily,
    TelemetryDeletion,
    TelemetryEvent,
    User,
)
from app.security import hash_api_key
from app.telemetry import jobs, scanner, service

from .conftest import make_admin, signup

FIX = Path(__file__).parent / "contracts" / "telemetry"
SYMBOLS = Path(__file__).parent / "fixtures" / "symbols"
H = {"X-Truebex-Contract": "telemetry/1.0"}
HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")
# The installation every body of the app's fixtures names.
INSTALL = "3f2a9c1e7b4d4e0f8a6b5c4d3e2f1a0b"
# An install secret and its id as the app derives it (§4; OP1's LoadInstall /
# MintSecret and its stub's 5.5): the first 32 hex of SHA-256 over the 64 hex
# characters of the secret.
SECRET = "7d4e1f0a9b3c2d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6"
SECRET_INSTALL = "116cea6cd6478818630f1281498f01ca"
# The app's crash-report.json callstack, normalised for the signature (§6.3).
APP_FRAMES = [
    "Truebex-Win64-Shipping!0x1a2b3c",
    "Truebex-Win64-Shipping!0x1a2a10",
    "Truebex-Win64-Shipping!0x88f201",
    "KERNEL32!0x2ccb7",
    "ntdll!0xaad6c",
]


def load(name: str):
    return json.loads(fixture_bytes(name).decode("utf-8"))


def fixture_bytes(name: str) -> bytes:
    return (FIX / name).read_bytes()


def fixture_text(name: str) -> str:
    """A text fixture exactly as stored (no newline translation)."""
    return fixture_bytes(name).decode("utf-8")


def app_multipart(parts: list[tuple[str, str, str, bytes]]) -> tuple[bytes, str]:
    """A multipart/form-data body byte for byte as the app writes it
    (OP1's TelemetryMultipart::Build in TelemetryPlatform.cpp): a
    `truebex-<24 hex>` boundary, every part with a filename and a type."""
    boundary = "truebex-" + secrets.token_hex(12)
    body = bytearray()
    for name, content_type, filename, data in parts:
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        body += f"Content-Type: {content_type}\r\n\r\n".encode()
        body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def post_crash(client, report=None, *, minidump=None, log=None, headers=H):
    report = report if report is not None else load("crash-report.json")
    files = {"report": ("report.json", json.dumps(report), "application/json")}
    if minidump is not False:
        files["minidump"] = (
            "minidump.dmp",
            minidump if minidump is not None else fixture_bytes("minidump-stub.dmp"),
            "application/octet-stream",
        )
    if log is not None:
        files["log"] = ("log.txt", log, "text/plain; charset=utf-8")
    return client.post("/telemetry/crashes", files=files, headers=headers)


def post_feedback(client, fb=None, *, screenshot=None, log=None, headers=H):
    fb = fb if fb is not None else load("feedback.json")
    files = {"feedback": ("feedback.json", json.dumps(fb), "application/json")}
    if screenshot is not False:
        files["screenshot"] = (
            "screenshot.png",
            screenshot if screenshot is not None else fixture_bytes("screenshot.png"),
            "image/png",
        )
    if log is not None:
        files["log"] = ("log.txt", log, "text/plain; charset=utf-8")
    return client.post("/telemetry/feedback", files=files, headers=headers)


def new_id() -> str:
    return secrets.token_hex(16)


def at_address(host: str):
    """The app as seen from another client address (the rate limiter keys on it)."""

    async def wrapped(scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope, client=(host, 40000))
        await app(scope, receive, send)

    return wrapped


def expected_signature(frames: list[str]) -> str:
    return hashlib.sha256("\n".join(frames).encode("utf-8")).hexdigest()[:16]


def assert_envelope(res, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert body["code"] == code
    assert body["status"] == status
    assert isinstance(body["detail"], str) and body["detail"]
    assert HEX32.match(body["request_id"])
    assert "retry_after_s" in body and "data" in body
    assert res.headers["X-Request-Id"] == body["request_id"]
    return body


def admin_headers(client, email="owner@example.com"):
    h = signup(client, email)
    make_admin(email)
    return h


def add_device(email: str, token: str, *, revoked: bool = False) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        db.add(
            Device(
                device_id=new_id(),
                user_id=user.id,
                fingerprint="f" * 64,
                name="TEST-PC",
                os="windows 10.0.26200",
                app_version="1.1.0",
                token_hash=hash_api_key(token),
                deactivated_at=datetime.now(timezone.utc) if revoked else None,
            )
        )
        db.commit()


# --- contract §10 ---------------------------------------------------------------


def test_events_keep_allowlisted_drop_rest(client):
    body = load("events-batch.json")
    sent = len(body["events"])
    body["events"].append(
        {"seq": 9, "at": "2026-10-09T12:21:00Z", "name": "room.renamed", "props": {"count": 1}}
    )
    body["events"][2]["props"]["selection"] = 4  # not in command.run's allow-list

    res = client.post("/telemetry/events", json=body, headers=H)
    assert res.status_code == 202, res.text
    assert res.json() == {"accepted": sent, "dropped": 2}

    with SessionLocal() as db:
        rows = db.scalars(select(TelemetryEvent).order_by(TelemetryEvent.seq)).all()
        assert len(rows) == sent
        assert {r.name for r in rows} <= set(load("config.json")["allowed"])
        wall = rows[2]
        assert wall.name == "command.run" and wall.props == {"command": "Wall", "ms": 12}
        assert wall.install_id == INSTALL and wall.app_version == "1.1.0"

    # The same batch_id again is a replay: same answer, nothing stored twice.
    again = client.post("/telemetry/events", json=body, headers=H)
    assert again.status_code == 202 and again.json() == {"accepted": sent, "dropped": 2}
    with SessionLocal() as db:
        assert len(db.scalars(select(TelemetryEvent)).all()) == sent


def test_privacy_violations_rejected(client):
    # The app's shape (telemetry.md 1.0.1, §9): {"cases": [{name, endpoint, field, payload}]}.
    cases = load("privacy-violations.json")["cases"]
    assert len(cases) >= 9
    assert {"path-in-callstack", "email-in-feedback-text"} <= {c["name"] for c in cases}
    for case in cases:
        payload = case["payload"]
        if case["endpoint"] == "events":
            res = client.post("/telemetry/events", json=payload, headers=H)
        elif case["endpoint"] == "crashes":
            res = post_crash(client, payload)
        else:
            assert case["endpoint"] == "feedback", case["name"]
            res = post_feedback(client, payload)
        body = assert_envelope(res, 422, "privacy_violation")
        assert body["data"]["field"] == case["field"], case["name"]

    with SessionLocal() as db:
        assert db.scalars(select(TelemetryEvent)).first() is None
        assert db.scalars(select(CrashReport)).first() is None
        assert db.scalars(select(Feedback)).first() is None


def test_no_ip_stored(client, monkeypatch):
    address = "203.0.113.77"
    # Even the database-backed limiter must not keep the address.
    monkeypatch.setattr(ratelimit.settings, "ratelimit_backend", "db")
    with TestClient(at_address(address)) as c:
        assert c.post("/telemetry/events", json=load("events-batch.json"), headers=H).status_code == 202
        assert post_crash(c, log=fixture_text("log-tail-scrubbed.txt")).status_code == 202
        assert post_feedback(c).status_code == 202

    hits = []
    with engine.connect() as conn:
        for table in inspect(engine).get_table_names():
            for row in conn.execute(text(f'SELECT * FROM "{table}"')):
                if any(address in str(value) for value in row):
                    hits.append(table)
    assert hits == []


def test_crash_multipart_signature_and_duplicate(client):
    report = load("crash-report.json")
    res = post_crash(client, report, log=fixture_text("log-tail-scrubbed.txt"))
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["crash_id"] == report["crash_id"]
    assert HEX16.match(body["signature"])
    assert body["signature"] == expected_signature(APP_FRAMES)
    assert body["duplicate"] is False and body["known_issue"] is None

    again = post_crash(client, report)
    assert again.status_code == 202
    assert again.json()["duplicate"] is True
    assert again.json()["signature"] == body["signature"]

    store = storage.get_store()
    with SessionLocal() as db:
        rows = db.scalars(select(CrashReport)).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.kind == "crash" and row.install_id == INSTALL
        month = row.received_at.strftime("%Y/%m")
        assert row.minidump_key == f"telemetry/crashes/{month}/{report['crash_id']}/minidump.dmp"
        assert row.log_key == f"telemetry/crashes/{month}/{report['crash_id']}/log.txt"
        assert store.stat(row.minidump_key).size == len(fixture_bytes("minidump-stub.dmp"))
        group = db.get(CrashGroup, body["signature"])
        assert group.count == 1 and group.versions == ["1.1.0"]


def test_feedback_reply_attaches_account_email(client):
    signup(client, "sara@example.com")
    token = "tbx_dev_" + "a" * 43
    revoked = "tbx_dev_" + "b" * 43
    add_device("sara@example.com", token)
    add_device("sara@example.com", revoked, revoked=True)

    fb = load("feedback.json")
    fb["reply"] = True
    res = post_feedback(client, fb, headers={**H, "Authorization": f"Bearer {token}"})
    assert res.status_code == 202, res.text
    assert res.json()["feedback_id"] == fb["feedback_id"]

    no_token = dict(fb, feedback_id=new_id())
    assert post_feedback(client, no_token).status_code == 202
    no_reply = dict(fb, feedback_id=new_id(), reply=False)
    assert (
        post_feedback(client, no_reply, headers={**H, "Authorization": f"Bearer {token}"}).status_code
        == 202
    )

    with SessionLocal() as db:
        assert db.get(Feedback, fb["feedback_id"]).email == "sara@example.com"
        assert db.get(Feedback, no_token["feedback_id"]).email is None
        assert db.get(Feedback, no_reply["feedback_id"]).email is None
        assert db.get(Feedback, no_reply["feedback_id"]).reply is False

    gone = dict(fb, feedback_id=new_id())
    res = post_feedback(client, gone, headers={**H, "Authorization": f"Bearer {revoked}"})
    assert_envelope(res, 401, "unauthenticated")
    res = post_feedback(client, gone, headers={**H, "Authorization": "Bearer tbx_dev_unknown"})
    assert_envelope(res, 401, "unauthenticated")
    with SessionLocal() as db:
        assert db.get(Feedback, gone["feedback_id"]) is None


def test_feedback_reply_with_a_device_from_the_licence_api(client):
    # Where PF1 meets PF14: the device token the licence API issued, then
    # its sign-out (5.10), decide whether a feedback reply carries the e-mail.
    from .licence_helpers import activated, bearer

    h = signup(client, "lina@example.com")
    device = activated(client, h)
    token = device["device_token"]

    fb = dict(load("feedback.json"), feedback_id=new_id(), reply=True)
    res = post_feedback(client, fb, headers={**H, "Authorization": f"Bearer {token}"})
    assert res.status_code == 202, res.text
    with SessionLocal() as db:
        assert db.get(Feedback, fb["feedback_id"]).email == "lina@example.com"

    assert client.post("/licence/deactivate", headers=bearer(token)).status_code == 200
    after = dict(fb, feedback_id=new_id())
    res = post_feedback(client, after, headers={**H, "Authorization": f"Bearer {token}"})
    assert_envelope(res, 401, "unauthenticated")


def test_delete_by_install_secret(client):
    # The id the app puts on everything it sends is the one 5.5 derives (PF14d:
    # SHA-256 over the secret's 64 hex characters, as OP1 does).
    assert service.install_id_from_secret(SECRET) == SECRET_INSTALL
    mine = dict(load("events-batch.json"), install_id=SECRET_INSTALL)
    other = dict(load("events-batch.json"), install_id=new_id(), batch_id=new_id())
    assert client.post("/telemetry/events", json=mine, headers=H).status_code == 202
    assert client.post("/telemetry/events", json=other, headers=H).status_code == 202
    crash = dict(load("crash-report.json"), install_id=SECRET_INSTALL)
    assert post_crash(client, crash, log=fixture_text("log-tail-scrubbed.txt")).status_code == 202
    fb = dict(load("feedback.json"), install_id=SECRET_INSTALL)
    assert post_feedback(client, fb, log="a scrubbed tail\n").status_code == 202
    store = storage.get_store()
    assert len(store.list("telemetry/")) == 4

    res = client.post("/telemetry/delete", json={"install_secret": SECRET}, headers=H)
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["install_id"] == SECRET_INSTALL
    complete_by = datetime.fromisoformat(body["complete_by"].replace("Z", "+00:00"))
    assert timedelta(days=29) < complete_by - datetime.now(timezone.utc) <= timedelta(days=30)

    # An installation nobody has heard of gets the same answer.
    unknown = client.post("/telemetry/delete", json={"install_secret": "0" * 64}, headers=H)
    assert unknown.status_code == 202 and HEX32.match(unknown.json()["install_id"])
    assert_envelope(
        client.post("/telemetry/delete", json={"install_secret": "xyz"}, headers=H),
        422,
        "validation_failed",
    )

    jobs.apply_deletions(datetime.now(timezone.utc))

    with SessionLocal() as db:
        for model in (TelemetryEvent, TelemetryBatch, CrashReport, Feedback):
            assert db.scalars(select(model).where(model.install_id == SECRET_INSTALL)).first() is None
        assert db.scalars(
            select(TelemetryEvent).where(TelemetryEvent.install_id == other["install_id"])
        ).first() is not None
        done = db.scalars(
            select(TelemetryDeletion).where(TelemetryDeletion.install_id == SECRET_INSTALL)
        ).one()
        assert done.completed_at is not None
    assert store.list("telemetry/") == []


def test_retention_job(client):
    now = datetime.now(timezone.utc)
    old_batch = load("events-batch.json")
    new_batch = dict(load("events-batch.json"), batch_id=new_id())
    assert client.post("/telemetry/events", json=old_batch, headers=H).status_code == 202
    assert client.post("/telemetry/events", json=new_batch, headers=H).status_code == 202

    old_crash = load("crash-report.json")
    new_crash = dict(old_crash, crash_id=new_id())
    log = fixture_text("log-tail-scrubbed.txt")
    assert post_crash(client, old_crash, log=log).status_code == 202
    assert post_crash(client, new_crash, log=log).status_code == 202

    old_fb = load("feedback.json")
    new_fb = dict(old_fb, feedback_id=new_id())
    assert post_feedback(client, old_fb).status_code == 202
    assert post_feedback(client, new_fb).status_code == 202

    with SessionLocal() as db:
        db.execute(
            update(TelemetryEvent)
            .where(TelemetryEvent.batch_id == old_batch["batch_id"])
            .values(received_at=now - timedelta(days=13 * 31 + 2))
        )
        db.execute(
            update(CrashReport)
            .where(CrashReport.crash_id == old_crash["crash_id"])
            .values(received_at=now - timedelta(days=181))
        )
        db.execute(
            update(Feedback)
            .where(Feedback.feedback_id == old_fb["feedback_id"])
            .values(received_at=now - timedelta(days=2 * 366 + 1))
        )
        db.commit()
        old_crash_row = db.get(CrashReport, old_crash["crash_id"])
        old_keys = [old_crash_row.minidump_key, old_crash_row.log_key]
        old_fb_key = db.get(Feedback, old_fb["feedback_id"]).screenshot_key

    jobs.rollup(now)
    jobs.retention(now)

    store = storage.get_store()
    with SessionLocal() as db:
        events = db.scalars(select(TelemetryEvent)).all()
        assert {e.batch_id for e in events} == {new_batch["batch_id"]}
        # Daily counts outlive the raw rows: both batches are still counted.
        daily = db.scalars(
            select(TelemetryDaily).where(
                TelemetryDaily.name == "command.run", TelemetryDaily.app_version == "*"
            )
        ).one()
        assert daily.events == 2  # one command.run in each of the two batches

        old_row = db.get(CrashReport, old_crash["crash_id"])
        assert old_row is not None and old_row.minidump_key is None and old_row.log_key is None
        assert db.get(CrashReport, new_crash["crash_id"]).minidump_key is not None
        assert db.get(CrashGroup, old_row.signature).count == 2

        assert db.get(Feedback, old_fb["feedback_id"]) is None
        assert db.get(Feedback, new_fb["feedback_id"]) is not None
    for key in old_keys + [old_fb_key]:
        assert store.stat(key) is None


def test_contract_header_and_error_envelope(client):
    res = client.get("/telemetry/config", headers=H)
    assert res.status_code == 200
    assert res.headers["X-Truebex-Contract"] == "telemetry/1.0"
    assert HEX32.match(res.headers["X-Request-Id"])

    body = assert_envelope(
        client.get("/telemetry/config", headers={"X-Truebex-Contract": "telemetry/2.0"}),
        400,
        "contract_version",
    )
    assert body["data"]["supported"] == ["telemetry/1.0"]
    assert_envelope(
        client.get("/telemetry/config", headers={"X-Truebex-Contract": "licence-api/1.0"}),
        400,
        "contract_version",
    )
    # A MINOR the server does not know yet is still served (additive).
    assert client.get("/telemetry/config", headers={"X-Truebex-Contract": "telemetry/1.4"}).status_code == 200

    bad = client.post(
        "/telemetry/events", content=b"{not json", headers={**H, "Content-Type": "application/json"}
    )
    body = assert_envelope(bad, 422, "validation_failed")
    assert bad.headers["X-Truebex-Contract"] == "telemetry/1.0"


# --- platform tests --------------------------------------------------------------


def test_telemetry_config_kill_switch(client, monkeypatch):
    on = client.get("/telemetry/config", headers=H)
    assert on.status_code == 200
    assert on.json() == load("config.json")
    assert "max-age=86400" in on.headers["Cache-Control"]

    monkeypatch.setattr(service.settings, "telemetry_events_enabled", False)
    off = client.get("/telemetry/config", headers=H).json()
    assert off == load("config-off.json")
    batch = load("events-batch.json")
    res = client.post("/telemetry/events", json=batch, headers=H)
    assert res.status_code == 202 and res.json() == {"accepted": 0, "dropped": len(batch["events"])}
    # Crash reports and feedback still go with consent.
    assert post_crash(client).status_code == 202
    assert post_feedback(client).status_code == 202

    monkeypatch.setattr(service.settings, "telemetry_ingestion_enabled", False)
    assert_envelope(client.get("/telemetry/config", headers=H), 503, "unavailable")


def test_telemetry_limits_and_rate(client):
    batch = load("events-batch.json")
    big = dict(batch, events=[dict(batch["events"][2], seq=i) for i in range(1, 400)])
    big["events"][0]["props"] = {"command": "W" * 60, "ms": 1}
    padding = {"command": "Wall", "ms": 1}
    huge = dict(batch, events=[{"seq": i, "at": "2026-10-09T12:00:00Z", "name": "command.run",
                                "props": dict(padding, **{f"k{j}": 1 for j in range(100)})}
                               for i in range(1, 450)])
    assert len(json.dumps(huge)) > 256 * 1024
    assert_envelope(client.post("/telemetry/events", json=huge, headers=H), 413, "too_large")
    too_many = dict(batch, events=[dict(batch["events"][2], seq=i) for i in range(1, 502)])
    assert_envelope(client.post("/telemetry/events", json=too_many, headers=H), 413, "too_large")
    assert client.post("/telemetry/events", json=big, headers=H).status_code == 202

    assert_envelope(
        client.post("/telemetry/events", json=dict(batch, schema="truebex-telemetry/9"), headers=H),
        422,
        "validation_failed",
    )
    missing = dict(batch)
    del missing["session_id"]
    body = assert_envelope(client.post("/telemetry/events", json=missing, headers=H), 422, "validation_failed")
    assert "session_id" in json.dumps(body["data"])

    report = dict(load("crash-report.json"), crash_id=new_id())
    assert_envelope(post_crash(client, report, minidump=b"\0" * (21 * 1024 * 1024 + 1)), 413, "too_large")
    assert_envelope(post_crash(client, report, log="x" * (256 * 1024 + 1)), 413, "too_large")
    assert_envelope(post_crash(client, dict(report, schema="truebex-crash/2")), 422, "validation_failed")
    assert_envelope(
        client.post("/telemetry/crashes", files={"minidump": ("m.dmp", b"MDMP", "application/octet-stream")}, headers=H),
        422,
        "validation_failed",
    )
    fb = dict(load("feedback.json"), feedback_id=new_id())
    assert_envelope(post_feedback(client, fb, screenshot=b"\x89PNG" + b"\0" * (9 * 1024 * 1024)), 413, "too_large")
    assert_envelope(post_feedback(client, dict(fb, text="x" * 5001)), 422, "validation_failed")
    assert_envelope(post_feedback(client, dict(fb, kind="rant")), 422, "validation_failed")
    assert_envelope(post_feedback(client, fb, screenshot=b"GIF89a not a png"), 422, "validation_failed")

    # 60 requests an hour per address ...
    ratelimit.reset()
    for _ in range(60):
        assert client.get("/telemetry/config", headers=H).status_code == 200
    res = client.get("/telemetry/config", headers=H)
    body = assert_envelope(res, 429, "rate_limited")
    assert body["retry_after_s"] >= 1 and int(res.headers["Retry-After"]) >= 1

    # ... and per installation, whatever address it comes from.
    ratelimit.reset()
    for n in range(60):
        ok = TestClient(at_address(f"198.51.100.{n}")).post(
            "/telemetry/events", json=dict(batch, batch_id=new_id()), headers=H
        )
        assert ok.status_code == 202, (n, ok.text)
    res = TestClient(at_address("198.51.100.200")).post(
        "/telemetry/events", json=dict(batch, batch_id=new_id()), headers=H
    )
    assert_envelope(res, 429, "rate_limited")


def test_telemetry_known_issue_returned(client):
    admin = admin_headers(client)
    first = post_crash(client)
    signature = first.json()["signature"]
    res = client.patch(
        f"/admin/telemetry/crashes/{signature}",
        json={"status": "fixed", "fixed_in": "1.1.2", "title": "Wall rebuild crash"},
        headers=admin,
    )
    assert res.status_code == 200, res.text

    again = post_crash(client, dict(load("crash-report.json"), crash_id=new_id()))
    assert again.status_code == 202
    assert again.json()["known_issue"] == {"title": "Wall rebuild crash", "fixed_in": "1.1.2"}
    assert again.json()["signature"] == signature
    assert post_crash(client).json()["known_issue"]["fixed_in"] == "1.1.2"  # duplicate too


def test_telemetry_scrub_matches_fixture(client):
    raw = fixture_text("log-tail-raw.txt")
    scrubbed = fixture_text("log-tail-scrubbed.txt")
    # The machine the app wrote the raw tail on (telemetry.md 1.0.1, §9): with it
    # the server's scrubber gives the app's expected output exactly.
    context = scanner.ScrubContext.from_json(load("scrub-context.json"))
    assert scanner.scrub_log(raw, context) == scrubbed
    # Line endings stay as they were (the app's checkout holds these files with CRLF).
    lf, crlf = chr(10), chr(13) + chr(10)
    assert scanner.scrub_log(raw.replace(lf, crlf), context) == scrubbed.replace(lf, crlf)
    assert scanner.scrub_log(scrubbed, context) == scrubbed

    # Production knows no machine: the context-free scrubber leaves the app's
    # scrubbed tail alone and would still change the raw one.
    assert scanner.scrub_log(scrubbed) == scrubbed
    assert scanner.scrub_log(raw) != raw

    # The server re-runs the rules: an unscrubbed tail is refused, a scrubbed one kept.
    body = assert_envelope(post_crash(client, log=raw), 422, "privacy_violation")
    assert body["data"]["field"] == "log"
    fb = dict(load("feedback.json"), feedback_id=new_id())
    body = assert_envelope(post_feedback(client, fb, log=raw), 422, "privacy_violation")
    assert body["data"]["field"] == "log"
    assert post_crash(client, log=scrubbed).status_code == 202
    assert post_feedback(client, fb, log=scrubbed).status_code == 202


def test_telemetry_scrub_rules_follow_the_app():
    """OP1's TelemetryPrivacy::Scrub rule by rule (TelemetryPrivacy.cpp)."""
    scrub = scanner.scrub_log
    ctx = scanner.ScrubContext(
        profile_dir=r"C:\Users\sara", user_name="sara", host_name="WS-01", project_dirs=(r"E:\Jobs\Villa",)
    )
    # 1. emails, with the sentence's full stop left outside
    assert scrub("mail sara.k@studio.co.uk.") == "mail <email>."
    assert scrub("not one: a@b.c, x@host.c0m, @example.com") == "not one: a@b.c, x@host.c0m, @example.com"
    # 2. the profile folder, either separator, any case; without a context any
    #    X:/Users/<name> except the shared ones
    assert scrub("C:/USERS/SARA/AppData/x.ini", ctx) == "%USERPROFILE%/AppData/x.ini"
    assert scrub(r"C:\Users\omar\AppData") == r"%USERPROFILE%\AppData"
    shared = r"C:\Users\Public\Documents and C:/Users/Default/NTUSER.DAT"
    assert scrub(shared) == shared
    # 3. a path ending in a project or export file, from its root, or a bare file name
    assert scrub(r"wrote \\nas\share\Villa A.dwg ok") == "wrote <project> ok"
    assert scrub(r"Saved (%USERPROFILE%\Desktop\v2.TBXP)") == "Saved (<project>)"
    assert scrub("imported kitchen.glb and plan.PDF; kept dark.json") == "imported <project> and <project>; kept dark.json"
    assert scrub("file=out/Sheets A1.pdf") == "file=out/Sheets <project>"
    assert scrub("x.tbxpack y.tbxpacks") == "<project> y.tbxpacks"
    # 4. the known project folders, 5. the machine and 6. the user, whole words only
    assert scrub("E:/jobs/villa/textures on WS-01 for sara, not sarah", ctx) == (
        "<project>/textures on <host> for <user>, not sarah"
    )
    # Names shorter than three characters are left (they would hit ordinary words).
    assert scrub("al at PC", scanner.ScrubContext(user_name="al", host_name="PC")) == "al at PC"

    # The production check refuses exactly the tails the context-free scrubber changes.
    tails = [
        fixture_text("log-tail-raw.txt"),
        fixture_text("log-tail-scrubbed.txt"),
        shared,
        "a.pdf " * 3000,
        "<project>.pdf <email> %USERPROFILE%/x",
        r"C:\Users\omar",
        "mail me@x.io",
        "kept dark.json",
    ]
    for tail in tails:
        assert (scanner.scan_log(tail) is not None) == (scrub(tail) != tail), tail[:40]


ADMIN_ROUTES = [
    ("get", "/admin/telemetry/summary"),
    ("get", "/admin/telemetry/crashes"),
    ("get", "/admin/telemetry/crashes/0123456789abcdef"),
    ("patch", "/admin/telemetry/crashes/0123456789abcdef"),
    ("get", f"/admin/telemetry/reports/{'0' * 32}/minidump"),
    ("get", f"/admin/telemetry/reports/{'0' * 32}/log"),
    ("get", "/admin/telemetry/export.csv"),
    ("get", "/admin/feedback"),
    ("patch", f"/admin/feedback/{'0' * 32}"),
    ("get", f"/admin/feedback/{'0' * 32}/screenshot"),
    ("get", f"/admin/feedback/{'0' * 32}/log"),
    ("post", f"/admin/feedback/{'0' * 32}/reply"),
    ("get", "/admin/symbols"),
    ("post", "/admin/symbols"),
]


def test_admin_telemetry_requires_admin(client):
    user = signup(client, "someone@example.com")
    for method, path in ADMIN_ROUTES:
        kwargs = {"json": {}} if method in ("patch", "post") else {}
        assert getattr(client, method)(path, **kwargs).status_code == 401, path
        assert getattr(client, method)(path, headers=user, **kwargs).status_code == 403, path
    admin = admin_headers(client)
    for path in ("/admin/telemetry/summary", "/admin/telemetry/crashes", "/admin/feedback", "/admin/symbols"):
        assert client.get(path, headers=admin).status_code == 200, path
    assert client.get("/auth/me", headers=admin).json()["is_admin"] is True
    assert client.get("/auth/me", headers=user).json()["is_admin"] is False


def test_server_exception_recorded_as_crash(client):
    async def boom():
        raise RuntimeError("database fell over")

    app.add_api_route("/__test/boom", boom, methods=["GET"])
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            res = c.get("/__test/boom")
            body = assert_envelope(res, 500, "internal_error")
            assert "fell over" not in body["detail"]
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/__test/boom"]

    with SessionLocal() as db:
        rows = db.scalars(select(CrashReport)).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.kind == "server" and row.install_id is None
        assert HEX16.match(row.signature)
        assert any("boom" in frame for frame in row.frames)
        assert db.get(CrashGroup, row.signature).count == 1


def test_telemetry_admin_flow(client):
    admin = admin_headers(client)
    assert client.post("/telemetry/events", json=load("events-batch.json"), headers=H).status_code == 202
    crash = post_crash(client, log=fixture_text("log-tail-scrubbed.txt")).json()
    fb = dict(load("feedback.json"), reply=True)
    signup(client, "sara@example.com")
    add_device("sara@example.com", "tbx_dev_" + "c" * 43)
    assert post_feedback(
        client, fb, log="tail\n", headers={**H, "Authorization": "Bearer tbx_dev_" + "c" * 43}
    ).status_code == 202
    quiet = dict(load("feedback.json"), feedback_id=new_id(), kind="idea", text="Add a north arrow.")
    assert post_feedback(client, quiet, screenshot=False).status_code == 202

    jobs.rollup(datetime.now(timezone.utc))
    summary = client.get("/admin/telemetry/summary?days=3650", headers=admin).json()
    assert summary["installs_per_day"][-1]["day"] >= "2026-10-09"
    assert {"day": "2026-10-09", "count": 1} in summary["installs_per_day"]
    assert summary["versions"] == [{"version": "1.1.0", "installs": 1}]
    top = {row["name"]: row["events"] for row in summary["top_events"]}
    assert top["command.run"] == 1 and top["app.start"] == 1
    timing = {row["name"]: row for row in summary["timings"]}
    assert timing["command.run"]["p50_ms"] == 12 and timing["command.run"]["p95_ms"] == 12
    assert summary["crash_free_sessions"] == 0.0  # one start, one crash

    groups = client.get("/admin/telemetry/crashes", headers=admin).json()
    assert [g["signature"] for g in groups] == [crash["signature"]]
    detail = client.get(f"/admin/telemetry/crashes/{crash['signature']}", headers=admin).json()
    assert detail["reports"][0]["crash_id"] == crash["crash_id"]
    assert detail["reports"][0]["frames"][0] == "Truebex-Win64-Shipping+0x1a2b3c"
    assert client.get("/admin/telemetry/crashes/ffffffffffffffff", headers=admin).status_code == 404
    assert client.patch(
        f"/admin/telemetry/crashes/{crash['signature']}", json={"status": "sideways"}, headers=admin
    ).status_code == 422

    link = client.get(f"/admin/telemetry/reports/{crash['crash_id']}/minidump", headers=admin).json()
    assert link["url"].startswith("http://testserver/files/")
    dump = client.get(link["url"].replace("http://testserver", ""))
    assert dump.status_code == 200 and dump.content == fixture_bytes("minidump-stub.dmp")

    inbox = client.get("/admin/feedback", headers=admin).json()
    assert {item["feedback_id"] for item in inbox} == {fb["feedback_id"], quiet["feedback_id"]}
    loud = next(i for i in inbox if i["feedback_id"] == fb["feedback_id"])
    assert loud["email"] == "sara@example.com" and loud["has_screenshot"] and loud["has_log"]
    shot = client.get(f"/admin/feedback/{fb['feedback_id']}/screenshot", headers=admin).json()
    png = client.get(shot["url"].replace("http://testserver", ""))
    assert png.status_code == 200 and png.content == fixture_bytes("screenshot.png")
    assert client.get(f"/admin/feedback/{quiet['feedback_id']}/screenshot", headers=admin).status_code == 404

    res = client.post(
        f"/admin/feedback/{fb['feedback_id']}/reply", json={"text": "Fixed in 1.1.2, thank you."}, headers=admin
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "replied" and res.json()["replied_at"]
    assert len(mail.OUTBOX) == 1
    sent = mail.OUTBOX[0]
    assert sent.to == "sara@example.com" and "Fixed in 1.1.2" in sent.text
    assert "gap at the corner" in sent.text
    assert client.post(
        f"/admin/feedback/{quiet['feedback_id']}/reply", json={"text": "Thanks"}, headers=admin
    ).status_code == 409
    assert client.post(
        f"/admin/feedback/{fb['feedback_id']}/reply", json={"text": ""}, headers=admin
    ).status_code == 422
    assert client.patch(
        f"/admin/feedback/{quiet['feedback_id']}", json={"status": "closed"}, headers=admin
    ).json()["status"] == "closed"

    for tab, needle in (("overview", "command.run"), ("crashes", crash["signature"]), ("feedback", "north arrow")):
        csv = client.get(f"/admin/telemetry/export.csv?tab={tab}&days=3650", headers=admin)
        assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
        assert needle in csv.text
        assert "sara@example.com" not in csv.text
    assert client.get("/admin/telemetry/export.csv?tab=secrets", headers=admin).status_code == 422


def cadcore_report(**changes) -> dict:
    """PF14's own crash in a DLL, whose .sym is tests/fixtures/symbols/Truebex-CadCore.sym
    (the app's fixture crashes in the Shipping executable; see
    test_telemetry_app_crash_end_to_end)."""
    return dict(
        load("crash-report.json"),
        exception={"code": "0xC0000005", "module": "Truebex-CadCore.dll", "offset": "0x1a2b3c"},
        callstack=[
            "Truebex-CadCore.dll+0x1a2b3c",
            "Truebex-CadCore.dll+0x1a0f10",
            "Truebex-CadCore.dll+0xc4410",
            "Truebex.exe!GuardedMain+0x1c",
            "kernel32.dll!BaseThreadInitThunk+0x14",
            "ntdll.dll!RtlUserThreadStart+0x21",
        ],
        **changes,
    )


def test_symbols_upload_and_symbolicate_regroups(client):
    admin = admin_headers(client)
    sym = (SYMBOLS / "Truebex-CadCore.sym").read_bytes()
    res = client.post(
        "/admin/symbols",
        data={"version": "1.1.0"},
        files={"file": ("Truebex-CadCore.sym", sym, "text/plain")},
        headers=admin,
    )
    assert res.status_code == 201, res.text
    info = res.json()
    assert info["module"] == "Truebex-CadCore.pdb"
    assert info["code_file"] == "Truebex-CadCore.dll"
    assert info["key"] == "symbols/Truebex-CadCore.pdb/4C1D9A0E5B7F4A3C9E2D1F0A8B7C6D5E1/Truebex-CadCore.sym"
    assert storage.get_store().stat(info["key"]) is not None
    bad = client.post(
        "/admin/symbols", data={"version": "1.1.0"}, files={"file": ("x.sym", b"hello", "text/plain")}, headers=admin
    )
    assert bad.status_code == 422

    first = post_crash(client, cadcore_report()).json()
    assert jobs.symbolicate_pending(datetime.now(timezone.utc)) == 1

    symbolic = expected_signature(
        [
            "Truebex-CadCore.dll!FCadWall::RebuildMesh",
            "Truebex-CadCore.dll!FCadWallSystem::Tick",
            "Truebex-CadCore.dll!FCadDocument::ApplyEdit",
            "Truebex.exe!GuardedMain",
            "kernel32.dll!BaseThreadInitThunk",
        ]
    )
    with SessionLocal() as db:
        row = db.get(CrashReport, first["crash_id"])
        assert row.symbolicated is True
        assert row.frames[0] == "Truebex-CadCore.dll!FCadWall::RebuildMesh(FCadWallBuildContext&)+0x3c"
        assert row.signature == symbolic
        # The raw group stays as an alias so later raw reports join the right group.
        alias = db.get(CrashGroup, first["signature"])
        assert alias.count == 0 and alias.merged_into == symbolic
        assert db.get(CrashGroup, symbolic).count == 1
    # Later reports of the same crash land in the corrected group at once.
    again = post_crash(client, cadcore_report(crash_id=new_id())).json()
    assert again["signature"] == symbolic
    listed = client.get("/admin/telemetry/crashes", headers=admin).json()
    assert [(g["signature"], g["count"]) for g in listed] == [(symbolic, 2)]


def test_stackwalk_json_parsing():
    from app.telemetry import symbolicate

    data = {
        "crash_info": {"type": "EXCEPTION_ACCESS_VIOLATION_READ", "crashing_thread": 0},
        "crashing_thread": {
            "frames": [
                {"module": "Truebex-CadCore.dll", "function": "FCadWall::RebuildMesh(FCadWallBuildContext&)",
                 "function_offset": "0x3c", "module_offset": "0x1a2b3c"},
                {"module": "Truebex-CadCore.dll", "function": None, "module_offset": "0x1a0f10"},
                {"module": None, "offset": "0x7ff6"},
            ]
        },
    }
    assert symbolicate.parse_stackwalk_json(data) == [
        "Truebex-CadCore.dll!FCadWall::RebuildMesh(FCadWallBuildContext&)+0x3c",
        "Truebex-CadCore.dll+0x1a0f10",
        "unknown+0x7ff6",
    ]


def test_upload_symbols_and_make_admin_scripts(client, tmp_path, capsys):
    from scripts import make_admin, upload_symbols

    folder = tmp_path / "Shipping"
    folder.mkdir()
    (folder / "Truebex-CadCore.sym").write_bytes((SYMBOLS / "Truebex-CadCore.sym").read_bytes())
    (folder / "readme.txt").write_text("not a symbol file")
    assert upload_symbols.main(["--version", "1.1.0", str(folder)]) == 0
    assert "symbols/Truebex-CadCore.pdb/4C1D9A0E5B7F4A3C9E2D1F0A8B7C6D5E1/Truebex-CadCore.sym" in capsys.readouterr().out
    with SessionLocal() as db:
        from app.models import SymbolFile

        row = db.scalars(select(SymbolFile)).one()
        assert row.version == "1.1.0" and row.code_file == "Truebex-CadCore.dll"
    # A .pdb needs dump_syms; without it the script says so instead of skipping silently.
    (folder / "Truebex.pdb").write_bytes(b"MSF")
    assert upload_symbols.main(["--version", "1.1.0", "--dump-syms", str(tmp_path / "missing.exe"), str(folder)]) == 1

    signup(client, "boss@example.com")
    assert make_admin.main(["boss@example.com"]) == 0
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == "boss@example.com")).is_admin is True
    assert make_admin.main(["boss@example.com", "--revoke"]) == 0
    assert make_admin.main(["nobody@example.com"]) == 1


# --- PF14d: the app's payloads end to end (OP1's fixtures, sent as OP1 sends them) ---


def set_in(doc: dict, path: list, value) -> dict:
    """A copy of `doc` with the value at `path` (keys and list indexes) replaced."""
    doc = copy.deepcopy(doc)
    node = doc
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    return doc


def test_telemetry_feedback_text_email_refused(client):
    case = next(c for c in load("privacy-violations.json")["cases"] if c["name"] == "email-in-feedback-text")
    assert (case["endpoint"], case["field"]) == ("feedback", "text")
    # The app's case as it stands (no app or os block): the scanner answers first.
    body = assert_envelope(post_feedback(client, case["payload"]), 422, "privacy_violation")
    assert body["data"] == {"field": "text", "reason": "email"}

    # The address in a whole message, with "reply to me" and a device token too:
    # refused before the account's e-mail is looked up, and nothing stored.
    signup(client, "sara@example.com")
    token = "tbx_dev_" + "d" * 43
    add_device("sara@example.com", token)
    with_token = {**H, "Authorization": f"Bearer {token}"}
    fb = dict(load("feedback.json"), text="Please write to alex.morgan@example.com", reply=True)
    body = assert_envelope(post_feedback(client, fb, headers=with_token), 422, "privacy_violation")
    assert body["data"]["field"] == "text"
    with SessionLocal() as db:
        assert db.scalars(select(Feedback)).first() is None

    # What OP1 sends: its scrubber has turned the address into <email>. The reply
    # flow is unchanged: the account's e-mail is attached from the token.
    scrubbed = dict(fb, text="Please write to <email>")
    assert post_feedback(client, scrubbed, headers=with_token).status_code == 202
    # 6.4's separator rule is for prop values: a person's message may hold a slash.
    slashes = dict(fb, feedback_id=new_id(), reply=False, text=r"The 1/2 wall and/or the \ key do nothing")
    assert post_feedback(client, slashes).status_code == 202
    with SessionLocal() as db:
        assert db.get(Feedback, fb["feedback_id"]).email == "sara@example.com"
        assert db.get(Feedback, slashes["feedback_id"]).text == slashes["text"]


def test_telemetry_scanner_platform_cases(client):
    """Rules the app's privacy-violations.json leaves out (PF14's own former
    cases), on the app's valid bodies."""
    events, crash, fb = load("events-batch.json"), load("crash-report.json"), load("feedback.json")
    cases = [
        ("events", set_in(events, ["events", 2, "props", "note"], "ask sara@example.com"), "events[2].props.note"),
        ("events", set_in(events, ["hw", "gpu"], "sara@example.com"), "hw.gpu"),
        ("events", set_in(events, ["events", 3, "props", "kind"], "Ground floor plan"), "events[3].props.kind"),
        ("events", set_in(events, ["events", 6, "props", "clean"], "yes"), "events[6].props.clean"),
        ("crashes", set_in(crash, ["exception", "module"], r"C:\Users\sara\Truebex.exe"), "exception.module"),
        ("crashes", set_in(crash, ["gpu_driver"], "sara@example.com"), "gpu_driver"),
        ("feedback", set_in(fb, ["os"], "windows 10.0.26200 sara@example.com"), "os"),
    ]
    for endpoint, payload, field in cases:
        if endpoint == "events":
            res = client.post("/telemetry/events", json=payload, headers=H)
        elif endpoint == "crashes":
            res = post_crash(client, payload)
        else:
            res = post_feedback(client, payload)
        body = assert_envelope(res, 422, "privacy_violation")
        assert body["data"]["field"] == field, field


def test_telemetry_app_events_batch_end_to_end(client):
    raw = fixture_bytes("events-batch.json")
    sent = json.loads(raw)
    res = client.post("/telemetry/events", content=raw, headers={**H, "Content-Type": "application/json"})
    assert res.status_code == 202, res.text
    assert res.json() == {"accepted": len(sent["events"]), "dropped": 0}
    with SessionLocal() as db:
        rows = db.scalars(select(TelemetryEvent).order_by(TelemetryEvent.seq)).all()
        assert [(r.seq, r.name, r.props) for r in rows] == [(e["seq"], e["name"], e["props"]) for e in sent["events"]]
        for row, event in zip(rows, sent["events"]):
            assert service.iso(row.at) == event["at"]
            assert (row.install_id, row.session_id, row.batch_id) == (
                sent["install_id"], sent["session_id"], sent["batch_id"]
            )
            assert (row.app_version, row.channel, row.build, row.os, row.locale, row.plan) == (
                "1.1.0", "stable", "shipping", "windows 10.0.26200", "en-GB", "pro"
            )
            assert row.hw == sent["hw"]

    # A Shipping build spells an FName as the engine first registered it (names
    # are case-preserving only with editor data, UE's NameTypes.h), so the same
    # events may arrive spelled like this: kept, in the contract's spelling.
    shipping = json.loads(raw)
    shipping["batch_id"] = new_id()
    ev = shipping["events"]
    ev[1]["name"] = "Tool.Open"
    ev[2]["props"] = {"Command": "Wall", "MS": 12}
    ev[3]["props"]["kind"] = "PDF"
    ev[4]["props"]["mode"] = "lit"
    ev[5]["props"] = {"Category": "LogCad3D", "Verbosity": "Warning", "Count": 2}
    res = client.post("/telemetry/events", json=shipping, headers=H)
    assert res.status_code == 202, res.text
    assert res.json() == {"accepted": len(ev), "dropped": 0}
    with SessionLocal() as db:
        rows = db.scalars(
            select(TelemetryEvent)
            .where(TelemetryEvent.batch_id == shipping["batch_id"])
            .order_by(TelemetryEvent.seq)
        ).all()
        assert [(r.name, r.props) for r in rows] == [(e["name"], e["props"]) for e in sent["events"]]


def test_telemetry_app_crash_end_to_end(client):
    admin = admin_headers(client)
    report = fixture_bytes("crash-report.json")
    dump = fixture_bytes("minidump-stub.dmp")
    log = fixture_bytes("log-tail-scrubbed.txt")
    sent = json.loads(report)
    parts = [
        ("report", "application/json", "report.json", report),
        ("minidump", "application/octet-stream", "minidump.dmp", dump),
        ("log", "text/plain; charset=utf-8", "log.txt", log),
    ]
    body, content_type = app_multipart(parts)
    res = client.post("/telemetry/crashes", content=body, headers={**H, "Content-Type": content_type})
    assert res.status_code == 202, res.text
    assert res.json() == {
        "crash_id": sent["crash_id"],
        "signature": expected_signature(APP_FRAMES),
        "duplicate": False,
        "known_issue": None,
    }
    store = storage.get_store()
    with SessionLocal() as db:
        row = db.get(CrashReport, sent["crash_id"])
        assert (row.kind, row.install_id, row.app_version, row.os) == ("crash", INSTALL, "1.1.0", sent["os"])
        assert row.frames == sent["callstack"] and row.exception == sent["exception"]
        assert (row.uptime_s, row.gpu_driver, row.hw) == (sent["uptime_s"], sent["gpu_driver"], sent["hw"])
        assert service.iso(row.at) == sent["at"]
        with store.open(row.minidump_key) as fh:
            assert fh.read() == dump
        with store.open(row.log_key) as fh:
            assert fh.read() == log

    # The app sends a report again at the next start until it is answered: a duplicate.
    body, content_type = app_multipart(parts)
    again = client.post("/telemetry/crashes", content=body, headers={**H, "Content-Type": content_type})
    assert again.status_code == 202 and again.json()["duplicate"] is True

    # OP1 names a module without its extension (FPaths::GetBaseFilename:
    # "Truebex-Win64-Shipping"); the symbols name the executable it was built as.
    sym = (SYMBOLS / "Truebex-Win64-Shipping.sym").read_bytes()
    res = client.post(
        "/admin/symbols",
        data={"version": "1.1.0"},
        files={"file": ("Truebex-Win64-Shipping.sym", sym, "text/plain")},
        headers=admin,
    )
    assert res.status_code == 201, res.text
    assert res.json()["code_file"] == "Truebex-Win64-Shipping.exe"
    assert jobs.symbolicate_pending(datetime.now(timezone.utc)) == 1
    with SessionLocal() as db:
        row = db.get(CrashReport, sent["crash_id"])
        assert row.symbolicated is True
        assert row.frames == [
            "Truebex-Win64-Shipping!FCadWall::RebuildMesh(FCadWallBuildContext&)+0x3c",
            "Truebex-Win64-Shipping!FCadWallSystem::Tick(float)+0x10",
            "Truebex-Win64-Shipping!FCadDocument::ApplyEdit(FCadEdit const&)+0x101",
            "KERNEL32+0x2ccb7",
            "ntdll+0xaad6c",
        ]
        assert row.signature == expected_signature(
            [
                "Truebex-Win64-Shipping!FCadWall::RebuildMesh",
                "Truebex-Win64-Shipping!FCadWallSystem::Tick",
                "Truebex-Win64-Shipping!FCadDocument::ApplyEdit",
                "KERNEL32!0x2ccb7",
                "ntdll!0xaad6c",
            ]
        )


def test_telemetry_app_feedback_end_to_end(client):
    feedback = fixture_bytes("feedback.json")
    shot = fixture_bytes("screenshot.png")
    log = fixture_bytes("log-tail-scrubbed.txt")
    sent = json.loads(feedback)
    parts = [
        ("feedback", "application/json", "feedback.json", feedback),
        ("screenshot", "image/png", "screenshot.png", shot),
        ("log", "text/plain; charset=utf-8", "log.txt", log),
    ]
    body, content_type = app_multipart(parts)
    res = client.post("/telemetry/feedback", content=body, headers={**H, "Content-Type": content_type})
    assert res.status_code == 202, res.text
    answer = res.json()
    assert answer["feedback_id"] == sent["feedback_id"] and answer["received_at"].endswith("Z")
    store = storage.get_store()
    with SessionLocal() as db:
        row = db.get(Feedback, sent["feedback_id"])
        assert (row.kind, row.text, row.reply, row.email) == ("bug", sent["text"], False, None)
        assert (row.install_id, row.app_version, row.os) == (INSTALL, "1.1.0", sent["os"])
        with store.open(row.screenshot_key) as fh:
            assert fh.read() == shot
        with store.open(row.log_key) as fh:
            assert fh.read() == log

    # Feedback that waited offline goes again at the next start: a duplicate.
    body, content_type = app_multipart(parts)
    again = client.post("/telemetry/feedback", content=body, headers={**H, "Content-Type": content_type})
    assert again.status_code == 202 and again.json()["duplicate"] is True

    # The kind is an FName in the app too: a Shipping build may send "Bug".
    shipping = json.dumps(dict(sent, feedback_id=new_id(), kind="Bug")).encode()
    body, content_type = app_multipart([("feedback", "application/json", "feedback.json", shipping)])
    res = client.post("/telemetry/feedback", content=body, headers={**H, "Content-Type": content_type})
    assert res.status_code == 202, res.text
    with SessionLocal() as db:
        assert db.get(Feedback, res.json()["feedback_id"]).kind == "bug"
