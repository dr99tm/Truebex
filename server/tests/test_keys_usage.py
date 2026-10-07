from datetime import date

from app.database import SessionLocal
from app.models import UsageDaily

from .conftest import signup


def _new_key(client, h, name="CI"):
    res = client.post("/keys", json={"name": name}, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def test_key_shown_once_and_hashed(client):
    h = signup(client)
    created = _new_key(client, h)
    assert created["key"].startswith("tbx_live_")
    assert created["key"].startswith(created["prefix"])
    listed = client.get("/keys", headers=h).json()
    assert len(listed) == 1 and "key" not in listed[0]


def test_free_plan_key_limit_and_revoke(client):
    h = signup(client)
    a = _new_key(client, h, "a")
    _new_key(client, h, "b")
    assert client.post("/keys", json={"name": "c"}, headers=h).status_code == 403
    assert client.delete(f"/keys/{a['id']}", headers=h).status_code == 200
    _new_key(client, h, "c")  # room again after revoking


def test_keys_are_private_to_owner(client):
    h1 = signup(client, "one@example.com")
    h2 = signup(client, "two@example.com")
    key = _new_key(client, h1)
    assert client.delete(f"/keys/{key['id']}", headers=h2).status_code == 404


def test_v1_auth_metering_and_headers(client):
    h = signup(client)
    key = _new_key(client, h)["key"]

    assert client.get("/v1/ping").status_code == 401
    assert client.get("/v1/ping", headers={"X-API-Key": "tbx_live_wrong"}).status_code == 401

    r1 = client.get("/v1/ping", headers={"Authorization": f"Bearer {key}"})
    r2 = client.get("/v1/account", headers={"X-API-Key": key})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.headers["X-RateLimit-Limit"] == "1000"
    assert r2.json()["usage"]["used"] == 2  # the /account call itself counts

    summary = client.get("/usage", headers=h).json()
    assert summary["used"] == 2 and summary["limit"] == 1000
    assert summary["by_endpoint"] == {"/v1/ping": 1, "/v1/account": 1}
    assert summary["by_key"] == {"CI": 2}
    assert summary["daily"][-1]["count"] == 2


def test_revoked_key_rejected(client):
    h = signup(client)
    created = _new_key(client, h)
    client.delete(f"/keys/{created['id']}", headers=h)
    res = client.get("/v1/ping", headers={"X-API-Key": created["key"]})
    assert res.status_code == 401


def test_monthly_quota_enforced(client):
    h = signup(client)
    created = _new_key(client, h)
    me = client.get("/auth/me", headers=h).json()
    with SessionLocal() as db:
        db.add(
            UsageDaily(
                user_id=me["id"],
                api_key_id=created["id"],
                day=date.today().replace(day=1),
                endpoint="/v1/ping",
                count=1000,
            )
        )
        db.commit()
    res = client.get("/v1/ping", headers={"X-API-Key": created["key"]})
    assert res.status_code == 429
    assert res.headers["X-RateLimit-Remaining"] == "0"
