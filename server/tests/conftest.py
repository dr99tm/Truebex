import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import pytest

from app.licence import signing as _signing  # no settings at import time

# Configure before the app (and its cached settings) is imported.
_tmp = tempfile.mkdtemp(prefix="truebex-test-")
# TEST_APP_DATABASE_URL runs the whole suite with the app on that database
# (a disposable Postgres: every test drops and recreates the tables).
APP_DATABASE_URL = os.environ.get("TEST_APP_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"

# Licence API (PF1): entitlements are signed with the contract fixtures' TEST
# key; releases with a separate rel-* test key whose seed stays in the tests.
LICENCE_FIXTURES = Path(__file__).parent / "contracts" / "licence"
TEST_KEY = json.loads((LICENCE_FIXTURES / "keys.json").read_text(encoding="utf-8"))["keys"][0]
REL_KID = "rel-test-2026-10"
REL_SEED = _signing.b64url_encode(hashlib.sha256(b"truebex platform tests rel key").digest())
REL_PUBLIC = _signing.public_key_b64url(_signing.private_key_from_seed(REL_SEED))

os.environ.update(
    {
        "DATABASE_URL": APP_DATABASE_URL,
        "SECRET_KEY": "test-secret-key-that-is-long-enough-123456",
        "GOOGLE_CLIENT_ID": "test-client.apps.googleusercontent.com",
        "BILLING_PROVIDER": "paddle",
        "PADDLE_ENV": "sandbox",
        "PADDLE_API_KEY": "pdl_sdbx_apikey_test",
        "PADDLE_WEBHOOK_SECRET": "pdl_ntfset_test_secret",
        "PADDLE_CLIENT_TOKEN": "test_client_token",
        "PADDLE_API_BASE": "",
        "STRIPE_SECRET_KEY": "sk_test_dummy",
        "STRIPE_WEBHOOK_SECRET": "whsec_test_dummy",
        "STRIPE_PRICE_PRO": "price_test_pro",
        "STRIPE_TAX_ENABLED": "false",
        # Wayl is dormant: keyed, but off unless a test turns WAYL_ENABLED on.
        "WAYL_ENABLED": "false",
        "WAYL_API_KEY": "wayl-test-key",
        "WAYL_WEBHOOK_SECRET": "wayl-webhook-secret-123",
        "WAYL_PRICE_PRO_IQD": "130000",
        "LICENCE_SIGNING_KEY": TEST_KEY["private_key"],
        "LICENCE_KEY_ID": TEST_KEY["kid"],
        "RELEASE_PUBLIC_KEYS": f"{REL_KID}:{REL_PUBLIC}",
        "SIGNING_KEYS_EXTRA": "",
        # PF14 plumbing: local files, console mail, no background loop
        # (tests call tasks.run_due themselves).
        "STORAGE_BACKEND": "local",
        "STORAGE_DIR": f"{_tmp}/storage",
        "MAIL_BACKEND": "console",
        "BACKGROUND_TASKS": "off",
        "RATELIMIT_BACKEND": "memory",
        "API_URL": "http://testserver",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app import mail, ratelimit, security, storage, tasks  # noqa: E402
from app.database import Base, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402

# bcrypt at its production cost (12 rounds, 0.3-0.5 s a hash on the owner's PC)
# was a sixth of the suite's time. The tests hash with the same scheme at its
# lowest cost; a hash of either cost verifies the same way.
security._pwd_context.update(bcrypt__rounds=4)

STORAGE_DIR = os.environ["STORAGE_DIR"]
# Set TEST_DATABASE_URL=postgresql+psycopg://user:pass@host:port/db to run the
# tests marked `postgres` (a local container, or the staging VM).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "postgres: needs TEST_DATABASE_URL (a disposable Postgres database)"
    )


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip)


def _reset_plumbing() -> None:
    ratelimit.reset()
    mail.OUTBOX.clear()
    tasks.reset()
    storage.reset_store()
    shutil.rmtree(STORAGE_DIR, ignore_errors=True)


# An empty app database (every table and init_db's seed), made once and copied
# in before each test with SQLite's backup API: the same fresh start as
# dropping every table and letting the app's startup create them again, which
# took 1.5-2 s a test (half the suite's time) on the owner's PC under load.
_EMPTY_DB: list[sqlite3.Connection] = []


def _fresh_database() -> None:
    """Every test that uses `client` starts on an empty database. On Postgres
    every table is dropped and the app's lifespan creates them again."""
    if engine.dialect.name != "sqlite":
        Base.metadata.drop_all(bind=engine)
        return
    engine.dispose()  # pooled connections keep the old file's schema
    path = engine.url.database
    if not _EMPTY_DB:
        Base.metadata.drop_all(bind=engine)
        init_db()
        engine.dispose()
        empty = sqlite3.connect(":memory:", check_same_thread=False)
        with closing(sqlite3.connect(path)) as made:
            made.backup(empty)
        _EMPTY_DB.append(empty)
    with closing(sqlite3.connect(path)) as target:
        _EMPTY_DB[0].backup(target)


@pytest.fixture()
def client():
    _fresh_database()
    _reset_plumbing()
    with TestClient(app) as c:  # runs lifespan -> init_db
        yield c


def signup(client, email="dev@example.com", password="password123"):
    res = client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_admin(email: str) -> None:
    """Admins are set by hand (`users.is_admin`), as the owner does in production."""
    from sqlalchemy import update

    from app.database import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        db.execute(update(User).where(User.email == email).values(is_admin=True))
        db.commit()


# --- Billing (PF2) ----------------------------------------------------------------

CONSENT = {"version": "2026-10-09", "accepted": True}


def checkout_body(tier="pro", interval="month", currency="GBP", seats=1, **extra):
    return {
        "tier": tier,
        "interval": interval,
        "currency": currency,
        "seats": seats,
        "consent": CONSENT,
        **extra,
    }


# Stripe's current state of each subscription, as stripe.Subscription.retrieve
# answers it in tests (webhook handlers re-fetch before applying).
STRIPE_SUBS: dict[str, dict] = {}


@pytest.fixture(autouse=True)
def fake_stripe_subscriptions(monkeypatch):
    import stripe

    STRIPE_SUBS.clear()

    def retrieve(sub_id, **_kw):
        return STRIPE_SUBS[sub_id]

    monkeypatch.setattr(stripe.Subscription, "retrieve", retrieve)
    return STRIPE_SUBS


@pytest.fixture()
def paddle(client, monkeypatch):
    """Paddle's API served in-process by tests/mock_paddle.py, with the
    catalogue's prices synced into provider_prices."""
    from app.billing import providers
    from app.config import get_settings
    from app.database import SessionLocal
    from scripts import sync_prices

    from . import mock_paddle

    mock_paddle.reset()
    monkeypatch.setitem(mock_paddle.WEBHOOK, "send", False)
    monkeypatch.setitem(mock_paddle.CHECKOUT, "style", "paddle")

    def factory(s):
        return TestClient(
            mock_paddle.app,
            base_url=s.paddle_api_url,
            headers={"Authorization": f"Bearer {s.paddle_api_key}", "Paddle-Version": "1"},
        )

    monkeypatch.setattr(providers, "_paddle_client", factory)
    synced = sync_prices.sync_paddle(get_settings())
    with SessionLocal() as db:
        sync_prices.store(db, "paddle", synced)
    return mock_paddle


@pytest.fixture()
def stripe_prices(client):
    """provider_prices rows for Stripe (ids are made up: price_<lookup key>)."""
    from app.database import SessionLocal
    from scripts import sync_prices

    synced = [(t, f"price_{t.lookup_key}", True) for t in sync_prices.targets()]
    with SessionLocal() as db:
        sync_prices.store(db, "stripe", synced)
    return {t.lookup_key: pid for t, pid, _ in synced}


# --- Long-poll wake-ups (PF14e) -----------------------------------------------------
#
# A test of a long poll's wake-up proves it by the wake-up, not by a clock: the
# re-check is patched above the wait (so only a notify or the deadline ends a
# wait), the read starts with the route's longest wait_s, the change is made
# only once the read is inside its wait, and the test asserts that a notify
# ended it. That holds on a starved CPU and fails when the wake-up is missing.
# (PF14b's `timing_window()`, a GC-free sub-second window, is gone with the
# sub-second windows.)

from app.projects import waiters  # noqa: E402

# Above every route's longest wait_s (25 s): with this re-check a wait ends only
# when a notify wakes it or at its own deadline.
RECHECK_OFF_S = 60.0


class Wakeups:
    """Every `Waiter.wait` of the test's long polls, by waiter key (a project id,
    or `queue.job_key(...)`): True when a notify ended it, False when its
    timeout did."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ended: dict[str, list[bool]] = defaultdict(list)
        self._inside: dict[str, int] = defaultdict(int)

    def entered(self, key: str) -> None:
        with self._lock:
            self._inside[key] += 1

    def left(self, key: str, woken: bool) -> None:
        with self._lock:
            self._inside[key] -= 1
            self._ended[key].append(woken)

    def ended(self, key: str) -> list[bool]:
        with self._lock:
            return list(self._ended[key])

    def clear(self) -> None:
        with self._lock:
            self._ended.clear()

    def until_waiting(self, key: str, timeout: float = 20.0) -> None:
        """Until a read waits on `key`: its waiter is registered (PF12a's
        `_until_waiting`) and it is inside `Waiter.wait`, past the read that
        follows the registration. A change made earlier could be answered by
        that read, without any wake-up."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                inside = self._inside[key] > 0
            if inside and waiters.waiting_count(key) >= 1:
                return
            assert time.monotonic() < deadline, f"the read never started waiting on {key}"
            time.sleep(0.01)

    def assert_woken(self, key: str, by: str) -> None:
        ended = self.ended(key)
        assert ended and all(ended), (
            f"the read was not woken by {by}: its waits on {key} ended {ended} "
            "(True = woken by a notify, False = at its deadline, [] = it never waited)"
        )

    def assert_deadline(self, key: str) -> None:
        ended = self.ended(key)
        assert ended and not any(ended), f"only the deadline should end this read: its waits on {key} ended {ended}"


@pytest.fixture()
def wakeups(monkeypatch):
    """Records every `Waiter.wait` (see `Wakeups`), with `waiters.RECHECK_S`
    patched above the wait."""
    log = Wakeups()
    original = waiters.Waiter.wait

    async def wait(waiter, timeout):
        log.entered(waiter.project_id)
        woken = False
        try:
            woken = await original(waiter, timeout)
            return woken
        finally:
            log.left(waiter.project_id, woken)

    monkeypatch.setattr(waiters, "RECHECK_S", RECHECK_OFF_S)
    monkeypatch.setattr(waiters.Waiter, "wait", wait)
    return log


class LongPoll:
    """One request on its own thread, started at once (the test client takes
    calls from any thread); `answer()` joins it with a hang guard."""

    def __init__(self, call) -> None:
        self.res = None
        self.took: float | None = None
        self._error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, args=(call,), daemon=True)
        self._thread.start()

    def _run(self, call) -> None:
        started = time.monotonic()
        try:
            self.res = call()
        except BaseException as exc:  # raised again in the test by answer()
            self._error = exc
        finally:
            self.took = time.monotonic() - started

    def answer(self, guard_s: float = 40.0):
        self._thread.join(guard_s)
        assert not self._thread.is_alive(), f"the long poll had not answered after {guard_s:.0f} s"
        if self._error is not None:
            raise self._error
        return self.res
