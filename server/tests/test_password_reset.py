"""Password reset by e-mail (POST /auth/password/forgot and /auth/password/reset,
app/password_reset.py): no enumeration, a hashed single-use 30-minute link in
the URL fragment, Google-only accounts, the SSO policy, rate limits, sessions
signed before a reset, and the purge job."""

import hashlib
import logging
import re

from sqlalchemy import func, select

from app import mail, tasks
from app.database import SessionLocal
from app.models import User
from app.password_reset import PasswordResetToken
from app.routers import auth as auth_router

from .conftest import signup
from .licence_helpers import Clock
from .org_helpers import envelope
from .test_sso import DOMAIN, _oidc, _verified_org, idp  # noqa: F401  (idp is a fixture)

LINK = re.compile(r"https://truebex\.com/reset-password/#token=([A-Za-z0-9_-]{43})")


def forgot(client, email):
    return client.post("/auth/password/forgot", json={"email": email})


def reset(client, token, password="new-password-1"):
    return client.post("/auth/password/reset", json={"token": token, "password": password})


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def sent_to(email: str) -> list[mail.Message]:
    return [m for m in mail.OUTBOX if m.to == email and m.template == "password_reset"]


def token_for(email: str) -> str:
    return LINK.search(sent_to(email)[-1].text).group(1)


def test_forgot_answers_the_same_and_mails_only_an_account(client):
    signup(client, "known@example.com")
    with SessionLocal() as db:
        db.add(User(email="google@example.com", hashed_password="", google_sub="g-1"))
        db.commit()
    answers = [forgot(client, e) for e in ("Known@Example.com", "nobody@example.com", "google@example.com")]
    assert [r.status_code for r in answers] == [202, 202, 202]
    assert answers[0].json() == answers[1].json() == answers[2].json() == {"status": "accepted"}
    assert sent_to("nobody@example.com") == []
    msg = sent_to("known@example.com")[0]
    assert msg.subject == "Reset your Truebex password"
    token = token_for("known@example.com")
    assert f"#token={token}" in msg.html and "for 30 minutes" in msg.text and "set a new password" in msg.text
    # A Google-only account is offered a password through its own inbox.
    assert "to set a password." in sent_to("google@example.com")[0].text
    # Stored only as its SHA-256.
    with SessionLocal() as db:
        row = db.get(PasswordResetToken, hashlib.sha256(token.encode()).hexdigest())
        assert row is not None and row.email == "known@example.com" and row.used_at is None
        assert (row.expires_at - row.created_at).total_seconds() == 1800
        assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 2
    assert client.post("/auth/password/forgot", json={"email": "not-an-address"}).status_code == 422


def test_reset_sets_the_password_once_and_signs_in(client, monkeypatch):
    clk = Clock(monkeypatch)
    h = signup(client, "dev@example.com", "old-password")
    forgot(client, "dev@example.com")
    first = token_for("dev@example.com")
    forgot(client, "dev@example.com")
    second = token_for("dev@example.com")
    assert first != second

    envelope(reset(client, second, "short"), 422, "validation_failed")
    res = reset(client, second)
    assert res.status_code == 200, res.text
    session = res.json()
    assert session["user"]["email"] == "dev@example.com" and session["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {session['access_token']}"})
    assert me.status_code == 200
    assert login(client, "dev@example.com", "old-password").status_code == 401
    assert login(client, "dev@example.com", "new-password-1").status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == "dev@example.com")).email_verified_at is not None
    # Single use, and the reset spends every other open link of the account.
    envelope(reset(client, second), 410, "reset_link_invalid")
    envelope(reset(client, first), 410, "reset_link_invalid")
    # A session signed before the reset stays valid until it expires (JWTs
    # are stateless: documented in app/password_reset.py).
    assert client.get("/auth/me", headers=h).status_code == 200

    # 30 minutes, then gone; made-up tokens never work.
    forgot(client, "dev@example.com")
    late = token_for("dev@example.com")
    clk.advance(minutes=31)
    envelope(reset(client, late), 410, "reset_link_invalid")
    envelope(reset(client, "x" * 43), 410, "reset_link_invalid")


def test_google_only_account_can_set_a_password(client, monkeypatch):
    monkeypatch.setattr(
        auth_router, "verify_google_credential",
        lambda credential: {"sub": "g-7", "email": "g@example.com", "email_verified": True, "name": "G"},
    )
    assert client.post("/auth/google", json={"credential": "x" * 40}).status_code == 200
    assert login(client, "g@example.com", "new-password-1").status_code == 401
    forgot(client, "g@example.com")
    res = reset(client, token_for("g@example.com"))
    assert res.status_code == 200, res.text
    assert res.json()["user"]["has_password"] is True and res.json()["user"]["google_linked"] is True
    assert login(client, "g@example.com", "new-password-1").status_code == 200


def test_sso_required_domain_gets_no_link_and_no_reset(client, idp):  # noqa: F811
    h, org = _verified_org(client, idp)
    signup(client, f"m@{DOMAIN}")
    # A link mailed before the organisation required SSO...
    forgot(client, f"m@{DOMAIN}")
    early = token_for(f"m@{DOMAIN}")
    _oidc(client, h, org, required=True)
    body = envelope(reset(client, early), 403, "sso_required")
    assert body["data"]["org_name"] == "Studio North"
    # ...and none after: the same answer, no mail.
    mail.OUTBOX.clear()
    res = forgot(client, f"m@{DOMAIN}")
    assert res.status_code == 202 and res.json() == {"status": "accepted"}
    assert sent_to(f"m@{DOMAIN}") == []


def test_forgot_rate_limits(client, monkeypatch):
    signup(client, "dev@example.com")
    for _ in range(5):
        assert forgot(client, "dev@example.com").status_code == 202
    body = envelope(forgot(client, "dev@example.com"), 429, "rate_limited")
    assert body["retry_after_s"] >= 1
    assert len(sent_to("dev@example.com")) == 5
    # The ceiling on every address together.
    from app import ratelimit

    ratelimit.reset()
    monkeypatch.setattr(auth_router, "FORGOT_ALL", (300, 2))
    assert forgot(client, "a@example.com").status_code == 202
    assert forgot(client, "b@example.com").status_code == 202
    envelope(forgot(client, "c@example.com"), 429, "rate_limited")
    # Per address of the caller: 10 asks in a row.
    ratelimit.reset()
    monkeypatch.setattr(auth_router, "FORGOT_ALL", (300, 100))
    for i in range(10):
        assert forgot(client, f"n{i}@example.com").status_code == 202
    envelope(forgot(client, "n10@example.com"), 429, "rate_limited")


def test_no_token_in_logs_and_purge(client, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    clk = Clock(monkeypatch)
    signup(client, "dev@example.com")
    forgot(client, "dev@example.com")
    token = token_for("dev@example.com")
    reset(client, token)
    forgot(client, "dev@example.com")  # an open link
    assert token not in "\n".join(r.getMessage() for r in caplog.records)
    assert "auth.password_resets.purge" in tasks.registered()
    tasks.run_due(clk.at, only=["auth.password_resets.purge"])
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 1  # the open one
    clk.advance(minutes=31)
    tasks.run_due(clk.at, only=["auth.password_resets.purge"])
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 0
