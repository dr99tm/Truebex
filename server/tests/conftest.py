import os
import tempfile

import pytest

# Configure before the app (and its cached settings) is imported.
_tmp = tempfile.mkdtemp(prefix="truebex-test-")
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
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # runs lifespan -> init_db
        yield c


def signup(client, email="dev@example.com", password="password123"):
    res = client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
