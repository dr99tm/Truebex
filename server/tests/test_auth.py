from app.routers import auth as auth_router

from .conftest import signup


def _google(monkeypatch, info=None, error=False):
    def fake(credential):
        if error:
            raise ValueError("bad token")
        return info

    monkeypatch.setattr(auth_router, "verify_google_credential", fake)


GOOGLE_INFO = {
    "sub": "1234567890",
    "email": "Person@Gmail.com",
    "email_verified": True,
    "name": "Person One",
    "picture": "https://example.com/a.png",
}
CRED = "x" * 40


def test_register_login_me(client):
    h = signup(client)
    me = client.get("/auth/me", headers=h).json()
    assert me["email"] == "dev@example.com"
    assert me["plan"] == "free" and me["has_password"] and not me["google_linked"]

    ok = client.post("/auth/login", json={"email": "DEV@example.com", "password": "password123"})
    assert ok.status_code == 200
    bad = client.post("/auth/login", json={"email": "dev@example.com", "password": "nope-nope"})
    assert bad.status_code == 401


def test_duplicate_register(client):
    signup(client)
    res = client.post("/auth/register", json={"email": "dev@example.com", "password": "password123"})
    assert res.status_code == 409


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_google_signup_then_signin_same_user(client, monkeypatch):
    _google(monkeypatch, GOOGLE_INFO)
    first = client.post("/auth/google", json={"credential": CRED})
    assert first.status_code == 200, first.text
    user = first.json()["user"]
    assert user["email"] == "person@gmail.com"
    assert user["google_linked"] and not user["has_password"]
    assert user["name"] == "Person One"

    second = client.post("/auth/google", json={"credential": CRED})
    assert second.json()["user"]["id"] == user["id"]


def test_google_account_cannot_password_login(client, monkeypatch):
    _google(monkeypatch, GOOGLE_INFO)
    client.post("/auth/google", json={"credential": CRED})
    res = client.post("/auth/login", json={"email": "person@gmail.com", "password": "whatever1"})
    assert res.status_code == 401
    assert "Google" in res.json()["detail"]


def test_google_links_existing_password_account(client, monkeypatch):
    signup(client, email="person@gmail.com")
    _google(monkeypatch, GOOGLE_INFO)
    res = client.post("/auth/google", json={"credential": CRED}).json()["user"]
    assert res["google_linked"] and res["has_password"]
    # Password still works after linking.
    ok = client.post("/auth/login", json={"email": "person@gmail.com", "password": "password123"})
    assert ok.status_code == 200


def test_google_rejects_unverified_email(client, monkeypatch):
    _google(monkeypatch, {**GOOGLE_INFO, "email_verified": False})
    assert client.post("/auth/google", json={"credential": CRED}).status_code == 401


def test_google_rejects_invalid_token(client, monkeypatch):
    _google(monkeypatch, error=True)
    assert client.post("/auth/google", json={"credential": CRED}).status_code == 401


def test_public_config_exposes_client_id(client):
    assert client.get("/config").json()["google_client_id"].endswith(".apps.googleusercontent.com")
