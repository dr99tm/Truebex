import os
import shutil
import tempfile

import pytest

# Configure before the app (and its cached settings) is imported.
_tmp = tempfile.mkdtemp(prefix="truebex-test-")
# TEST_APP_DATABASE_URL runs the whole suite with the app on that database
# (a disposable Postgres: every test drops and recreates the tables).
APP_DATABASE_URL = os.environ.get("TEST_APP_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ.update(
    {
        "DATABASE_URL": APP_DATABASE_URL,
        "SECRET_KEY": "test-secret-key-that-is-long-enough-123456",
        "GOOGLE_CLIENT_ID": "test-client.apps.googleusercontent.com",
        "STRIPE_SECRET_KEY": "sk_test_dummy",
        "STRIPE_WEBHOOK_SECRET": "whsec_test_dummy",
        "STRIPE_PRICE_PRO": "price_test_pro",
        "WAYL_API_KEY": "wayl-test-key",
        "WAYL_WEBHOOK_SECRET": "wayl-webhook-secret-123",
        "WAYL_PRICE_PRO_IQD": "130000",
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

from app import mail, ratelimit, storage, tasks  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

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


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
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
