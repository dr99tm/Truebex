import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from app.licence import signing as _signing  # no settings at import time

# Configure before the app (and its cached settings) is imported.
_tmp = tempfile.mkdtemp(prefix="truebex-test-")

# Licence API (PF1): entitlements are signed with the contract fixtures' TEST
# key; releases with a separate rel-* test key whose seed stays in the tests.
LICENCE_FIXTURES = Path(__file__).parent / "contracts" / "licence"
TEST_KEY = json.loads((LICENCE_FIXTURES / "keys.json").read_text(encoding="utf-8"))["keys"][0]
REL_KID = "rel-test-2026-10"
REL_SEED = _signing.b64url_encode(hashlib.sha256(b"truebex platform tests rel key").digest())
REL_PUBLIC = _signing.public_key_b64url(_signing.private_key_from_seed(REL_SEED))

os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-123456",
        "GOOGLE_CLIENT_ID": "test-client.apps.googleusercontent.com",
        "STRIPE_SECRET_KEY": "sk_test_dummy",
        "STRIPE_WEBHOOK_SECRET": "whsec_test_dummy",
        "STRIPE_PRICE_PRO": "price_test_pro",
        "WAYL_API_KEY": "wayl-test-key",
        "WAYL_WEBHOOK_SECRET": "wayl-webhook-secret-123",
        "WAYL_PRICE_PRO_IQD": "130000",
        "LICENCE_SIGNING_KEY": TEST_KEY["private_key"],
        "LICENCE_KEY_ID": TEST_KEY["kid"],
        "RELEASE_PUBLIC_KEYS": f"{REL_KID}:{REL_PUBLIC}",
        "SIGNING_KEYS_EXTRA": "",
        "BACKGROUND_TASKS": "off",
        "STORAGE_DIR": f"{_tmp}/storage",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app import ratelimit, tasks  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    ratelimit.reset()
    for job in tasks.JOBS.values():
        job.last_run = None
    with TestClient(app) as c:  # runs lifespan -> init_db
        yield c


def signup(client, email="dev@example.com", password="password123"):
    res = client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
