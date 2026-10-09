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
    for job in tasks.jobs().values():
        job.next_run = None
    with TestClient(app) as c:  # runs lifespan -> init_db
        yield c


def signup(client, email="dev@example.com", password="password123"):
    res = client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


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
