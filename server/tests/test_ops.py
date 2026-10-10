"""PF14 operations: the Plumbing every feature shares (storage, mail, tasks,
rate limiting), /health/deep, Postgres readiness, the SQLite -> Postgres copy
and the shape of the host's Compose file.

Tests marked `postgres` run only when TEST_DATABASE_URL points at a disposable
Postgres database (see conftest.py).
"""

import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app import mail, ratelimit, tasks
from app.contract_http import ContractError
from app.database import Base, SessionLocal, init_db
from app.models import ApiKey, OpsStatus, RateLimitBucket, UsageDaily, User
from app.storage import BlobInfo, InvalidKey
from app.storage.local import LocalStore
from app.usage import record

from .conftest import APP_DATABASE_URL, TEST_DATABASE_URL, signup

REPO = Path(__file__).resolve().parents[2]
SERVER = REPO / "server"


# --- storage ----------------------------------------------------------------------


def test_storage_local_put_get_and_signed_urls(client, tmp_path):
    from app.storage import get_store

    store = get_store()
    assert isinstance(store, LocalStore)
    info = store.put("telemetry/a/b.txt", b"hello", content_type="text/plain")
    assert isinstance(info, BlobInfo) and info.size == 5 and info.content_type == "text/plain"
    with store.open("telemetry/a/b.txt") as fh:
        assert fh.read() == b"hello"
    assert store.stat("telemetry/a/b.txt").size == 5
    assert store.stat("telemetry/a/missing.txt") is None
    assert [b.key for b in store.list("telemetry/")] == ["telemetry/a/b.txt"]

    url = store.signed_get_url("telemetry/a/b.txt", filename="hello.txt")
    assert url.startswith("http://testserver/files/telemetry/a/b.txt?")
    path = url.replace("http://testserver", "")
    res = client.get(path)
    assert res.status_code == 200 and res.content == b"hello"
    assert res.headers["content-type"].startswith("text/plain")
    assert 'filename="hello.txt"' in res.headers["content-disposition"]

    tampered = path.replace("sig=", "sig=0")
    assert client.get(tampered).status_code == 403
    expired = store.signed_get_url("telemetry/a/b.txt", expires_in=-1).replace("http://testserver", "")
    assert client.get(expired).status_code == 403
    assert client.get("/files/telemetry/a/b.txt").status_code == 403

    for bad in ("../secret", "a/../../b", "/abs", "a\\b", "", "a//b"):
        with pytest.raises(InvalidKey):
            store.put(bad, b"x", content_type="text/plain")
    assert client.get("/files/a/..%2F..%2Fsecret?exp=1&sig=00").status_code == 422

    put_url = store.signed_put_url(
        "uploads/u1.bin", content_type="application/octet-stream", max_bytes=8
    ).replace("http://testserver", "")
    assert client.put(put_url, content=b"12345678", headers={"Content-Type": "application/octet-stream"}).status_code == 201
    assert store.stat("uploads/u1.bin").size == 8
    assert client.put(put_url, content=b"123456789", headers={"Content-Type": "application/octet-stream"}).status_code == 413
    # A valid link with the wrong Content-Type: 415 (PF1's /files route).
    assert client.put(put_url, content=b"1", headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.put(put_url.replace("sig=", "sig=f"), content=b"1", headers={"Content-Type": "application/octet-stream"}).status_code == 403

    store.delete("telemetry/a/b.txt")
    assert store.stat("telemetry/a/b.txt") is None
    store.delete("telemetry/a/b.txt")  # deleting twice is fine


def test_storage_s3_adapter_contract(monkeypatch):
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    requests = pytest.importorskip("requests")
    from app.storage.s3 import S3Store

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="truebex-test")
        store = S3Store(
            bucket="truebex-test",
            endpoint=None,
            region="us-east-1",
            access_key_id="testing",
            secret_access_key="testing",
            cdn_base_url="https://cdn.truebex.test",
        )
        info = store.put(
            "telemetry/crashes/x/minidump.dmp", b"MDMP", content_type="application/octet-stream"
        )
        assert info.size == 4 and info.content_type == "application/octet-stream"
        with store.open("telemetry/crashes/x/minidump.dmp") as fh:
            assert fh.read() == b"MDMP"
        assert store.stat("telemetry/crashes/x/minidump.dmp").size == 4
        assert store.stat("telemetry/nothing") is None
        store.put("telemetry/crashes/y/log.txt", b"tail", content_type="text/plain")
        assert [b.key for b in store.list("telemetry/crashes/")] == [
            "telemetry/crashes/x/minidump.dmp",
            "telemetry/crashes/y/log.txt",
        ]

        url = store.signed_get_url("telemetry/crashes/x/minidump.dmp", expires_in=900, filename="dump.dmp")
        query = parse_qs(urlparse(url).query)
        assert query["X-Amz-Expires"] == ["900"] and "X-Amz-Signature" in query
        assert requests.get(url, timeout=5).content == b"MDMP"
        put = store.signed_put_url("uploads/z.bin", content_type="application/octet-stream", max_bytes=10)
        assert "X-Amz-Signature" in put

        # Public, cacheable prefixes go through the CDN hostname instead.
        store.put("tiles/a/0.png", b"png", content_type="image/png", cache_control="public, max-age=31536000")
        assert store.signed_get_url("tiles/a/0.png") == "https://cdn.truebex.test/tiles/a/0.png"

        with pytest.raises(InvalidKey):
            store.put("../x", b"x", content_type="text/plain")
        store.delete("telemetry/crashes/x/minidump.dmp")
        assert store.stat("telemetry/crashes/x/minidump.dmp") is None


# --- mail -----------------------------------------------------------------------


def test_mail_console_outbox_and_smtp_adapter(monkeypatch):
    mail.OUTBOX.clear()
    msg = mail.send_mail(
        "sara@example.com",
        "feedback_reply",
        {"reply": "Fixed in 1.1.2.", "original": "The section cut flickers.", "kind": "bug"},
        reply_to="hello@truebex.com",
    )
    assert mail.OUTBOX == [msg]
    assert msg.to == "sara@example.com" and msg.reply_to == "hello@truebex.com"
    assert msg.subject == "Re: your Truebex feedback"
    assert "Fixed in 1.1.2." in msg.text and "The section cut flickers." in msg.text
    assert "Fixed in 1.1.2." in msg.html
    # Values are escaped in the HTML body.
    hostile = mail.render("feedback_reply", {"reply": "<script>x</script>", "original": "o", "kind": "bug"})
    assert "<script>" not in hostile.html and "&lt;script&gt;" in hostile.html
    with pytest.raises(KeyError):
        mail.render("no_such_template", {})

    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            sent.append(("quit",))

        def starttls(self, context=None):
            sent.append(("starttls",))

        def login(self, user, password):
            sent.append(("login", user, password))

        def send_message(self, message):
            sent.append(("send", message["To"], message["Subject"], message["Reply-To"]))

    from app.mail import smtp

    monkeypatch.setattr(smtp.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mail.settings, "mail_backend", "smtp")
    monkeypatch.setattr(mail.settings, "smtp_host", "smtp.example.net")
    monkeypatch.setattr(mail.settings, "smtp_port", 587)
    monkeypatch.setattr(mail.settings, "smtp_user", "apikey")
    monkeypatch.setattr(mail.settings, "smtp_password", "pw")
    mail.OUTBOX.clear()
    mail.send_mail("ops@example.com", "alert", {"subject": "API down", "body": "health/deep 503"})
    assert mail.OUTBOX == []
    assert sent == [
        ("connect", "smtp.example.net", 587),
        ("starttls",),
        ("login", "apikey", "pw"),
        ("send", "ops@example.com", "[Truebex ops] API down", None),
        ("quit",),
    ]


# --- background tasks ----------------------------------------------------------------


def test_tasks_run_due_respects_interval():
    tasks.reset()
    calls = []

    @tasks.periodic("test.every-minute", seconds=60)
    def every_minute(now):
        calls.append(now)

    try:
        t0 = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
        for offset in (0, 1, 30, 59, 60, 61, 119, 120, 150, 179, 180):
            tasks.run_due(t0 + timedelta(seconds=offset), only=["test.every-minute"])
        assert [int((c - t0).total_seconds()) for c in calls] == [0, 60, 120, 180]

        def broken(now):
            raise RuntimeError("job failed")

        tasks.periodic("test.broken", seconds=10)(broken)
        # A failing job neither stops the others nor the loop.
        ran = tasks.run_due(t0 + timedelta(seconds=240), only=["test.broken", "test.every-minute"])
        assert ran == ["test.broken", "test.every-minute"]
        assert len(calls) == 5
    finally:
        tasks.unregister("test.every-minute")
        tasks.unregister("test.broken")

    names = tasks.registered()
    for job in (
        "telemetry.rollup",
        "telemetry.retention",
        "telemetry.deletions",
        "crash.symbolicate",
        "backup.check",
        "worker.heartbeat",
        "ratelimit.purge",
    ):
        assert job in names


def _fresh_python(code: str, tmp_path) -> str:
    """Run `code` in a new interpreter in server/ (nothing imported yet), as
    the worker container and the copy script start."""
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{tmp_path / 'fresh.db'}", BACKGROUND_TASKS="off")
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=SERVER, env=env, capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="WMI exists only on Windows")
def test_fresh_process_never_queries_wmi(tmp_path):
    # SQLAlchemy calls platform.machine() at import. Python 3.12 answers it with
    # a WMI query that times out on a busy machine; the fallback that follows can
    # kill the process with 0xC000070A (app/__init__.py). No server process may
    # reach WMI, whatever imported `platform` first.
    spy = (
        "import json, _wmi; calls = []; real = _wmi.exec_query; "
        "_wmi.exec_query = lambda q: calls.append(q) or real(q); "
    )
    probe = "; import platform; platform.uname(); platform.processor(); print(json.dumps(calls))"
    for entry in (
        "from scripts import sqlite_to_postgres",  # imports SQLAlchemy before app
        "import platform; from app import tasks",  # platform first, as uvicorn does
        "import app.main",
        # PF3's hand scripts, as `python scripts\<name>.py` loads them (scripts/ first on sys.path).
        "import runpy, sys; sys.path.insert(0, 'scripts'); runpy.run_path('scripts/grant_org_seats.py')",
        "import runpy, sys; sys.path.insert(0, 'scripts'); runpy.run_path('scripts/verify_org_domain.py')",
        # PF7's trial catalogue, the same way.
        "import contextlib, io, runpy, sys; sys.path.insert(0, 'scripts'); g = runpy.run_path('scripts/seed_market.py'); "
        "r = contextlib.redirect_stdout(io.StringIO()); r.__enter__(); g['main'](['--fixture', 'no-such-folder']); "
        "r.__exit__(None, None, None)",
    ):
        assert json.loads(_fresh_python(spy + entry + probe, tmp_path)) == [], entry
    machine = json.loads(_fresh_python("import json, app, platform; print(json.dumps(platform.machine()))", tmp_path))
    assert machine == (os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ["PROCESSOR_ARCHITECTURE"])


def test_worker_process_registers_every_feature_job(tmp_path):
    # The worker imports only app.worker: PF1's, PF2's, PF3's, PF5's and PF7's jobs must still run there.
    names = set(json.loads(_fresh_python("import json; from app import tasks; print(json.dumps(tasks.registered()))", tmp_path)))
    for job in (
        "telemetry.rollup",
        "worker.heartbeat",
        "licence.links.purge",
        "licence.devices.lapse",
        "billing.founding.expire",
        "billing.reconcile",
        "licence.leases.expire",
        "orgs.invites.expire",
        "audit.purge",
        "sso.requests.purge",
        "shares.expire",
        "shares.purge",
        "uploads.expire",
        "market.embeddings",
        "market.quotes.expire",
        "market.orders.unpaid",
        "market.transfers",
        "market.commissions.invoice",
        "market.availability.stale",
    ):
        assert job in names, job


def test_worker_heartbeat_and_check(client, capsys):
    from app import worker

    assert worker.check() == 1  # no heartbeat yet
    now = datetime.now(timezone.utc)
    tasks.run_due(now, only=["worker.heartbeat"])
    with SessionLocal() as db:
        beat = db.get(OpsStatus, "worker.heartbeat")
        assert beat is not None
    assert worker.check() == 0
    # Jobs on demand (operators, the human test): known names only.
    assert worker.main(["--run", "telemetry.rollup", "worker.heartbeat"]) == 0
    assert "ran: telemetry.rollup, worker.heartbeat" in capsys.readouterr().out
    assert worker.main(["--run", "no.such.job"]) == 2
    res = client.get("/health/deep")
    assert res.status_code == 200
    assert 0 <= res.json()["worker_heartbeat_s"] < 60


def test_backup_check_alerts_when_stale(client, monkeypatch):
    from app import ops

    pushed = []
    monkeypatch.setattr(ops, "_push", lambda title, body: pushed.append(title))
    monkeypatch.setattr(ops.settings, "alert_email", "owner@example.com")
    mail.OUTBOX.clear()
    now = datetime.now(timezone.utc)

    # Fresh markers: no alert.
    ops.mark("backup.base", now - timedelta(hours=3))
    ops.mark("backup.wal", now - timedelta(minutes=2))
    assert ops.backup_check(now) == []
    assert mail.OUTBOX == []

    # A base backup older than 26 h alerts once, not every 15 minutes.
    ops.mark("backup.base", now - timedelta(hours=27))
    assert ops.backup_check(now) == ["base backup is 27 h old"]
    ops.mark("backup.wal", now + timedelta(minutes=14))
    assert ops.backup_check(now + timedelta(minutes=15)) == ["base backup is 27 h old"]
    assert [m.subject for m in mail.OUTBOX] == ["[Truebex ops] Backups are stale"]
    assert pushed == ["Backups are stale"]

    # Back to fresh: one recovery notice.
    ops.mark("backup.base", now)
    ops.mark("backup.wal", now + timedelta(minutes=29))
    assert ops.backup_check(now + timedelta(minutes=30)) == []
    assert [m.subject for m in mail.OUTBOX][-1] == "[Truebex ops] Backups are fresh again"

    # A WAL archive older than 15 minutes is stale too.
    assert ops.backup_check(now + timedelta(minutes=50)) == ["last WAL archive is 21 min old"]


# --- rate limiting ---------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["memory", "db"])
def test_ratelimit_blocks_after_limit(client, monkeypatch, backend):
    monkeypatch.setattr(ratelimit.settings, "ratelimit_backend", backend)
    ratelimit.reset()
    clock = [1000.0]
    monkeypatch.setattr(ratelimit, "_clock", lambda: clock[0])

    for _ in range(3):
        ratelimit.check("test:198.51.100.9", per_minute=3)
    with pytest.raises(ContractError) as err:
        ratelimit.check("test:198.51.100.9", per_minute=3)
    assert err.value.status == 429 and err.value.code == "rate_limited"
    assert err.value.retry_after_s == 20
    # Another key has its own bucket; time refills the first.
    ratelimit.check("test:198.51.100.10", per_minute=3)
    clock[0] += 20
    ratelimit.check("test:198.51.100.9", per_minute=3)

    # Through HTTP: /health/deep is limited per address.
    for _ in range(30):
        assert client.get("/health/deep").status_code in (200, 503)
    res = client.get("/health/deep")
    assert res.status_code == 429
    assert res.json()["code"] == "rate_limited" and res.json()["retry_after_s"] >= 1

    if backend == "db":
        with SessionLocal() as db:
            keys = [row.key for row in db.scalars(select(RateLimitBucket))]
        assert keys and all(len(k) == 64 for k in keys)
        assert not any("198.51.100" in k or "testclient" in k for k in keys)


# --- health ---------------------------------------------------------------------------


def test_health_deep_ok_and_db_down(client, monkeypatch, tmp_path):
    res = client.get("/health/deep")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["db"] == "ok" and body["storage"] == "ok"
    assert "worker_heartbeat_s" in body
    assert client.get("/health").json() == {"status": "ok"}

    from app import health

    broken = create_engine(f"sqlite:///{tmp_path}/missing/dir/truebex.db")
    monkeypatch.setattr(health, "engine", broken)
    res = client.get("/health/deep")
    assert res.status_code == 503
    assert res.json()["db"] == "error" and res.json()["storage"] == "ok"

    monkeypatch.undo()
    monkeypatch.setattr(health.settings, "background_tasks", "worker")
    res = client.get("/health/deep")  # tasks on, but no heartbeat yet
    assert res.status_code == 503 and res.json()["worker_heartbeat_s"] is None


# --- databases -----------------------------------------------------------------------


@pytest.fixture()
def pg_engine():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    yield engine
    engine.dispose()


def _user_and_key(db: Session) -> tuple[int, int]:
    user = User(email="pg@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    key = ApiKey(user_id=user.id, name="ci", prefix="tbx_live_ab", key_hash="h" * 64)
    db.add(key)
    db.commit()
    return user.id, key.id


@pytest.mark.parametrize(
    "dialect", ["sqlite", pytest.param("postgresql", marks=pytest.mark.postgres)]
)
def test_usage_record_upsert_sqlite_and_postgres(client, dialect, request):
    if dialect == "sqlite":
        if not APP_DATABASE_URL.startswith("sqlite"):
            pytest.skip("the app runs on Postgres in this session")
        db = SessionLocal()
    else:
        engine = request.getfixturevalue("pg_engine")
        init_db(engine)
        db = Session(engine)
    try:
        assert db.get_bind().dialect.name == dialect
        user_id, key_id = _user_and_key(db)
        record(db, user_id, key_id, "/v1/ping")
        record(db, user_id, key_id, "/v1/ping")
        db.commit()
        row = db.scalars(select(UsageDaily)).one()
        assert row.count == 2
    finally:
        db.close()


@pytest.mark.postgres
def test_db_postgres_init_and_migrate_twice(pg_engine):
    init_db(pg_engine)
    init_db(pg_engine)
    with pg_engine.connect() as conn:
        cols = {
            r[0]
            for r in conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
            )
        }
    assert {"google_sub", "name", "avatar_url", "is_admin"} <= cols
    with Session(pg_engine) as db:
        _user_and_key(db)
        # timestamptz comes back aware; the billing helpers accept both.
        assert db.scalars(select(User)).one().created_at.tzinfo is not None


def _seed_sqlite(url: str) -> None:
    engine = create_engine(url)
    init_db(engine)
    with Session(engine) as db:
        for n in range(3):
            user = User(email=f"user{n}@example.com", hashed_password="x", plan="pro" if n else "free")
            db.add(user)
            db.flush()
            key = ApiKey(user_id=user.id, name=f"k{n}", prefix="tbx_live_x", key_hash=f"{n:064d}")
            db.add(key)
            db.flush()
            db.add(UsageDaily(user_id=user.id, api_key_id=key.id, day=datetime(2026, 10, n + 1).date(), endpoint="/v1/ping", count=n + 1))
        # A gap in the ids, as deleted rows leave behind.
        db.add(User(id=10, email="late@example.com", hashed_password="", name="Late"))
        db.commit()
    engine.dispose()


def test_sqlite_to_postgres_lists_every_feature_table(tmp_path):
    # A fresh process (the cutover runs the script on its own): PF1's, PF3's, PF5's and PF7's tables too.
    code = "import json; from scripts import sqlite_to_postgres as s; print(json.dumps([t.name for t in s._models()]))"
    tables = json.loads(_fresh_python(code, tmp_path))
    for table in (
        "users", "subscriptions", "provider_prices", "devices", "releases", "telemetry_events", "crash_reports",
        "organisations", "org_members", "org_invites", "seat_assignments", "floating_leases", "org_domains",
        "audit_events", "sso_connections", "sso_requests", "sso_assertions_seen",
        "blobs", "upload_sessions", "shares", "share_derivatives", "share_visits",
        "suppliers", "market_categories", "market_regions", "products", "product_variants", "variant_prices",
        "market_orders", "market_order_suppliers", "market_order_lines", "commissions", "product_reviews", "feed_runs",
    ):
        assert table in tables, table
    assert tables.index("users") < tables.index("devices")  # parents first
    assert tables.index("organisations") < tables.index("org_members")
    assert tables.index("suppliers") < tables.index("products") < tables.index("product_variants")


def test_sqlite_to_postgres_on_sqlite_target_and_precheck(tmp_path):
    from scripts import sqlite_to_postgres as s2p

    src = f"sqlite:///{tmp_path / 'auth.db'}"
    dst = f"sqlite:///{tmp_path / 'copy.db'}"
    _seed_sqlite(src)
    report = s2p.copy_database(src, dst)
    assert report.ok, report.render()
    counts = {t.table: (t.source_rows, t.target_rows) for t in report.tables}
    assert counts["users"] == (4, 4) and counts["api_keys"] == (3, 3) and counts["usage_daily"] == (3, 3)
    assert all(t.source_checksum == t.target_checksum for t in report.tables)
    # A second run refuses a target that already holds rows.
    with pytest.raises(s2p.CopyError):
        s2p.copy_database(src, dst)

    # Values Postgres would refuse are listed before anything is copied.
    bad = f"sqlite:///{tmp_path / 'bad.db'}"
    _seed_sqlite(bad)
    engine = create_engine(bad)
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET name = :n WHERE id = 10"), {"n": "x" * 250})
        conn.execute(text("INSERT INTO api_keys (id, user_id, name, prefix, key_hash, created_at) VALUES (99, 777, 'orphan', 'p', :h, '2026-10-09')"), {"h": "9" * 64})
    engine.dispose()
    problems = s2p.precheck(bad)
    assert "users.name id=10: 250 characters > 200" in problems
    assert "api_keys.user_id id=99: no users row 777" in problems
    with pytest.raises(s2p.CopyError):
        s2p.copy_database(bad, f"sqlite:///{tmp_path / 'never.db'}")


@pytest.mark.postgres
def test_sqlite_to_postgres_copies_rows_and_sequences(tmp_path, pg_engine):
    from scripts import sqlite_to_postgres as s2p

    src = f"sqlite:///{tmp_path / 'auth.db'}"
    _seed_sqlite(src)
    report = s2p.copy_database(src, TEST_DATABASE_URL)
    assert report.ok, report.render()
    assert all(t.source_checksum == t.target_checksum for t in report.tables)
    with Session(pg_engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 4
        user = User(email="next@example.com", hashed_password="x")
        db.add(user)
        db.commit()
        assert user.id == 11  # max(id) + 1: the sequence was reset


# --- infrastructure --------------------------------------------------------------------


def test_infra_compose_file_shape():
    yaml = pytest.importorskip("yaml")
    compose = yaml.safe_load((REPO / "infra" / "host" / "compose.yaml").read_text("utf-8"))
    services = compose["services"]
    assert {"api", "worker", "postgres", "caddy"} <= set(services)
    for name, svc in services.items():
        assert "healthcheck" in svc, f"{name} has no healthcheck"
        assert svc.get("restart") == "unless-stopped", name
    assert "ports" not in services["postgres"]
    assert "ports" not in services["api"] and "ports" not in services["worker"]
    assert [str(p) for p in services["caddy"]["ports"]] == ["443:443"]
    assert "app.worker" in " ".join(services["worker"]["command"])

    caddyfile = (REPO / "infra" / "host" / "Caddyfile").read_text("utf-8")
    assert "origin" in caddyfile and "reverse_proxy api:8000" in caddyfile
    assert "flush_interval -1" in caddyfile


def test_dockerfile_runs_as_non_root_with_healthcheck():
    dockerfile = (SERVER / "Dockerfile").read_text("utf-8")
    assert "FROM python:3.12-slim" in dockerfile
    assert "\nUSER " in dockerfile and "HEALTHCHECK" in dockerfile
    ignore = (SERVER / ".dockerignore").read_text("utf-8").split()
    for entry in (".venv", ".env", "*.db", "tests"):
        assert entry in ignore
    reqs = (SERVER / "requirements.txt").read_text("utf-8")
    assert "psycopg[binary]==" in reqs and "boto3==" in reqs
    dev = (SERVER / "requirements-dev.txt").read_text("utf-8")
    assert "moto[s3]==" in dev and "PyYAML==" in dev


def test_no_sqlite_dialect_imports_left():
    """Every module works on both dialects (PF14 Risks): only the dispatching
    helper `database.dialect_insert` may name a dialect."""
    offenders = [
        p.name
        for p in (SERVER / "app").rglob("*.py")
        if "dialects." in p.read_text("utf-8") and p != SERVER / "app" / "database.py"
    ]
    assert offenders == []
