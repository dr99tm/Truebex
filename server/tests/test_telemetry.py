"""PF14: telemetry ingestion (contracts/telemetry.md §5-§7), the admin
dashboard API, retention and deletion jobs, and API crashes in the crash store.

The first eight tests are the contract's §10 platform tests, run against the
§9 fixtures in tests/contracts/telemetry/.
"""

import copy
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text, update

from app import mail, ratelimit, storage
from app.database import SessionLocal, engine
from app.main import app
from app.models import (
    CrashGroup,
    CrashReport,
    Device,
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
SECRET = "7d4e1f0a9b3c2d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6"
INSTALL = "4a1ffea151643db7fe803e815865e053"


def load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def fixture_bytes(name: str) -> bytes:
    return (FIX / name).read_bytes()


def set_pointer(doc, pointer: str, value):
    """Apply an RFC 6901 JSON Pointer assignment (privacy-violations.json)."""
    parts = [p.replace("~1", "/").replace("~0", "~") for p in pointer.lstrip("/").split("/")]
    node = doc
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    last = parts[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value
    return doc


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
    import secrets

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
    cases = load("privacy-violations.json")["cases"]
    assert len(cases) >= 10
    for case in cases:
        payload = set_pointer(copy.deepcopy(load(case["base"])), case["pointer"], case["value"])
        if case["endpoint"] == "events":
            res = client.post("/telemetry/events", json=payload, headers=H)
        elif case["endpoint"] == "crashes":
            res = post_crash(client, payload)
        else:
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
        assert post_crash(c, log=(FIX / "log-tail-scrubbed.txt").read_text("utf-8")).status_code == 202
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
    res = post_crash(client, report, log=(FIX / "log-tail-scrubbed.txt").read_text("utf-8"))
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["crash_id"] == report["crash_id"]
    assert HEX16.match(body["signature"])
    assert body["signature"] == expected_signature(
        [
            "Truebex-CadCore.dll!0x1a2b3c",
            "Truebex-CadCore.dll!0x1a0f10",
            "Truebex-CadCore.dll!0xc4410",
            "Truebex.exe!GuardedMain",
            "kernel32.dll!BaseThreadInitThunk",
        ]
    )
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


def test_delete_by_install_secret(client):
    assert service.install_id_from_secret(SECRET) == INSTALL
    other = load("events-batch.json")
    other.update(install_id=new_id(), batch_id=new_id())
    assert client.post("/telemetry/events", json=load("events-batch.json"), headers=H).status_code == 202
    assert client.post("/telemetry/events", json=other, headers=H).status_code == 202
    assert post_crash(client, log=(FIX / "log-tail-scrubbed.txt").read_text("utf-8")).status_code == 202
    assert post_feedback(client, log="a scrubbed tail\n").status_code == 202
    store = storage.get_store()
    assert len(store.list("telemetry/")) == 4

    res = client.post("/telemetry/delete", json={"install_secret": SECRET}, headers=H)
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["install_id"] == INSTALL
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
            assert db.scalars(select(model).where(model.install_id == INSTALL)).first() is None
        assert db.scalars(
            select(TelemetryEvent).where(TelemetryEvent.install_id == other["install_id"])
        ).first() is not None
        done = db.scalars(
            select(TelemetryDeletion).where(TelemetryDeletion.install_id == INSTALL)
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
    log = (FIX / "log-tail-scrubbed.txt").read_text("utf-8")
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
        assert daily.events == 4

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
    raw = (FIX / "log-tail-raw.txt").read_text("utf-8")
    scrubbed = (FIX / "log-tail-scrubbed.txt").read_text("utf-8")
    assert scanner.scrub_log(raw) == scrubbed
    assert scanner.scrub_log(scrubbed) == scrubbed

    # The server re-runs the rules: an unscrubbed tail is refused, a scrubbed one kept.
    body = assert_envelope(post_crash(client, log=raw), 422, "privacy_violation")
    assert body["data"]["field"] == "log"
    fb = dict(load("feedback.json"), feedback_id=new_id())
    assert post_feedback(client, fb, log=raw).status_code == 422
    assert post_crash(client, log=scrubbed).status_code == 202


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
    crash = post_crash(client, log=(FIX / "log-tail-scrubbed.txt").read_text("utf-8")).json()
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
    assert top["command.run"] == 2 and top["app.start"] == 1
    timing = {row["name"]: row for row in summary["timings"]}
    assert timing["command.run"]["p50_ms"] == 9 and timing["command.run"]["p95_ms"] == 12
    assert summary["crash_free_sessions"] == 0.0  # one start, one crash

    groups = client.get("/admin/telemetry/crashes", headers=admin).json()
    assert [g["signature"] for g in groups] == [crash["signature"]]
    detail = client.get(f"/admin/telemetry/crashes/{crash['signature']}", headers=admin).json()
    assert detail["reports"][0]["crash_id"] == crash["crash_id"]
    assert detail["reports"][0]["frames"][0] == "Truebex-CadCore.dll+0x1a2b3c"
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
    assert "section cut flickers" in sent.text
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

    first = post_crash(client).json()
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
    again = post_crash(client, dict(load("crash-report.json"), crash_id=new_id())).json()
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
