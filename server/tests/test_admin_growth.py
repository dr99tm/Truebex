"""PF13: GET /admin/growth, the conversions the site counts from the
platform's own records (no analytics cookies, no personal data)."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import inspect

from app.database import SessionLocal, engine
from app.growth.service import record_download
from app.models import Payment, Subscription, User

from .conftest import signup


def _make_admin(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).one().id


def test_admin_growth_counts(client):
    admin = signup(client, "admin@example.com")
    _make_admin("admin@example.com")
    signup(client, "maker@example.com")
    signup(client, "other@example.com")
    uid = _user_id("maker@example.com")

    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)
    with SessionLocal() as db:
        record_download(db, version="1.0.0", platform="win64")
        record_download(db, version="1.0.0", platform="win64")
        record_download(db, version="1.0.0", platform="win64", at=yesterday)
        db.add(Subscription(user_id=uid, plan="pro", provider="trial", status="active",
                            current_period_end=today + timedelta(days=14)))
        # A Stripe subscription is not a trial.
        db.add(Subscription(user_id=uid, plan="pro", provider="stripe", status="active"))
        db.add(Payment(user_id=uid, provider="stripe", plan="pro", reference="tbx_a",
                       amount=1, currency="GBP"))
        db.add(Payment(user_id=uid, provider="stripe", plan="pro", reference="tbx_b",
                       amount=1, currency="GBP", status="paid", paid_at=today))
        db.commit()

    d0 = (yesterday.date()).isoformat()
    d1 = today.date().isoformat()
    res = client.get(f"/admin/growth?from={d0}&to={d1}", headers=admin)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["from"] == d0 and body["to"] == d1
    days = {d["day"]: d for d in body["days"]}
    assert list(days) == [d0, d1]
    assert days[d1] == {"day": d1, "signups": 3, "downloads": 2, "trials": 1,
                        "checkouts": 2, "paid": 1}
    assert days[d0] == {"day": d0, "signups": 0, "downloads": 1, "trials": 0,
                        "checkouts": 0, "paid": 0}
    assert body["totals"] == {"signups": 3, "downloads": 3, "trials": 1,
                              "checkouts": 2, "paid": 1}
    # Counts only: no e-mail address or user id reaches the answer.
    assert "@" not in res.text and "example.com" not in res.text


def test_admin_growth_requires_admin(client):
    assert client.get("/admin/growth").status_code == 401
    user = signup(client, "plain@example.com")
    res = client.get("/admin/growth", headers=user)
    assert res.status_code == 403
    assert "admin" in res.json()["detail"].lower()


def test_admin_growth_validation(client):
    admin = signup(client, "admin2@example.com")
    _make_admin("admin2@example.com")
    assert client.get("/admin/growth?from=2026-10-09&to=2026-10-01", headers=admin).status_code == 422
    assert client.get("/admin/growth?from=2024-01-01&to=2026-10-01", headers=admin).status_code == 422
    assert client.get("/admin/growth?from=yesterday", headers=admin).status_code == 422


def test_admin_growth_default_range_zero_filled(client):
    admin = signup(client, "admin3@example.com")
    _make_admin("admin3@example.com")
    body = client.get("/admin/growth", headers=admin).json()
    assert len(body["days"]) == 30
    today = datetime.now(timezone.utc).date()
    assert body["to"] == today.isoformat()
    assert body["from"] == (today - timedelta(days=29)).isoformat()
    assert [d["day"] for d in body["days"]] == sorted(d["day"] for d in body["days"])
    assert body["days"][0]["signups"] == 0


def test_me_reports_admin_flag(client):
    h = signup(client, "flag@example.com")
    assert client.get("/auth/me", headers=h).json()["is_admin"] is False
    _make_admin("flag@example.com")
    assert client.get("/auth/me", headers=h).json()["is_admin"] is True


def test_download_events_hold_no_personal_data(client):
    cols = {c["name"] for c in inspect(engine).get_columns("download_events")}
    assert cols == {"id", "at", "version", "platform", "channel"}
    with SessionLocal() as db:
        ev = record_download(db, version="1.1.0", platform="win64", channel="beta")
        assert ev.at.date() <= date.today() + timedelta(days=1)


def test_admin_cli_sets_flag(client):
    from app.admin_cli import main

    h = signup(client, "cli@example.com")
    assert main(["nobody@example.com"]) == 1
    assert main(["cli@example.com"]) == 0
    assert client.get("/admin/growth", headers=h).status_code == 200
    assert main(["cli@example.com", "--off"]) == 0
    assert client.get("/admin/growth", headers=h).status_code == 403
