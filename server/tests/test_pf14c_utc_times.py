"""PF14c: every time the API answers leaves as RFC 3339 UTC with `Z`,
whatever the database (SQLite hands back naive UTC, Postgres answers in the
session's zone).

* Response models: every datetime field is `UtcDateTime` (app/utc.py, PF2c's
  type); a gate walks every route's response model.
* Routes that answer a dict: the times go through `licence.clock.rfc3339` (or
  a model dumped to JSON); the two found by PF14c are tested here.
* Input: a share's `expires_at` accepts any RFC 3339 time and is stored in UTC.
"""

import json
import re
import shutil
import subprocess
import typing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import select, text

from app import schemas
from app.database import SessionLocal
from app.licence import clock
from app.main import app
from app.models import ApiKey, User
from app.shares.models import Share
from app.utc import UtcDateTime

from .conftest import signup
from .licence_helpers import CONTRACT, FP1, session
from .share_helpers import device_token, published, web

ROOT = Path(__file__).resolve().parents[2]
BAGHDAD = timezone(timedelta(hours=3))
# Whole seconds (licence.clock.rfc3339) or with a fraction (pydantic), always Z.
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")
_UTC_MARK = typing.get_args(UtcDateTime)[1]


def _utc(value: str) -> datetime:
    """An answered time: RFC 3339 with Z, read as an aware UTC datetime."""
    assert isinstance(value, str) and RFC3339_Z.match(value), value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _near_now(at: datetime) -> bool:
    return abs(at - datetime.now(timezone.utc)) < timedelta(minutes=5)


def _key_and_use(client, h) -> dict:
    """A developer key, used once (GET /v1/ping sets last_used_at)."""
    res = client.post("/keys", json={"name": "laptop"}, headers=h)
    assert res.status_code == 201, res.text
    created = res.json()
    assert client.get("/v1/ping", headers={"X-API-Key": created["key"]}).status_code == 200
    return created


# --- 1. /auth/me and /keys --------------------------------------------------------------


def test_user_and_key_times_are_utc(client):
    # The models write Z from a naive (SQLite), a +03:00 (Postgres in another
    # zone) and a UTC value alike, microseconds kept.
    instant = datetime(2026, 11, 10, 6, 47, 10, 150607, tzinfo=timezone.utc)
    for value in (instant.replace(tzinfo=None), instant.astimezone(BAGHDAD), instant):
        user = schemas.UserOut(id=1, email="a@example.com", created_at=value, plan="free")
        assert user.model_dump(mode="json")["created_at"] == "2026-11-10T06:47:10.150607Z"
        key = schemas.ApiKeyOut(
            id=1, name="k", prefix="tbx_live_ab", created_at=value, last_used_at=value, revoked_at=value
        ).model_dump(mode="json")
        assert key["created_at"] == key["last_used_at"] == key["revoked_at"] == "2026-11-10T06:47:10.150607Z"

    # Through the API (SQLite on this PC and in every human test).
    res = client.post("/auth/register", json={"email": "dev@example.com", "password": "password123"})
    assert res.status_code == 201
    registered = _utc(res.json()["user"]["created_at"])
    h = {"Authorization": f"Bearer {res.json()['access_token']}"}
    me = client.get("/auth/me", headers=h).json()
    assert _utc(me["created_at"]) == registered and _near_now(registered)
    login = client.post("/auth/login", json={"email": "dev@example.com", "password": "password123"}).json()
    assert _utc(login["user"]["created_at"]) == registered

    created = _key_and_use(client, h)
    assert _near_now(_utc(created["created_at"])) and created["last_used_at"] is None
    (key,) = client.get("/keys", headers=h).json()
    made, used = _utc(key["created_at"]), _utc(key["last_used_at"])
    assert made == _utc(created["created_at"]) and made <= used and _near_now(used)
    assert key["revoked_at"] is None
    with SessionLocal() as db:
        row = db.scalar(select(ApiKey).where(ApiKey.id == key["id"]))
        # The same instant as stored, not shifted by any offset.
        assert (clock.aware(row.created_at), clock.aware(row.last_used_at)) == (made, used)
        stored_user = db.scalar(select(User).where(User.email == "dev@example.com"))
        assert clock.aware(stored_user.created_at) == registered
    revoked = client.delete(f"/keys/{key['id']}", headers=h).json()
    assert _near_now(_utc(revoked["revoked_at"])) and _utc(revoked["last_used_at"]) == used


@pytest.mark.postgres
def test_user_and_key_times_are_utc_postgres(client):
    """On Postgres whose session zone is not UTC (TEST_DATABASE_URL, the
    session set to Asia/Baghdad), /auth/me and /keys still answer UTC with
    `Z`, the same instants as stored."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import get_db, init_db

    from .conftest import TEST_DATABASE_URL

    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c TimeZone=Asia/Baghdad"})
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    init_db(bind=engine)
    make = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def pg_db():
        db = make()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = pg_db
    try:
        h = signup(client, "pg@example.com")
        me = client.get("/auth/me", headers=h).json()
        created = _key_and_use(client, h)
        (key,) = client.get("/keys", headers=h).json()
        with make() as db:
            assert db.execute(text("SHOW TimeZone")).scalar() == "Asia/Baghdad"
            user = db.scalar(select(User).where(User.email == "pg@example.com"))
            row = db.get(ApiKey, created["id"])
            # The session's zone: what the old models answered as +03:00.
            assert user.created_at.utcoffset() == row.last_used_at.utcoffset() == timedelta(hours=3)
            assert _utc(me["created_at"]) == user.created_at
            assert (_utc(key["created_at"]), _utc(key["last_used_at"])) == (row.created_at, row.last_used_at)
        assert _near_now(_utc(key["last_used_at"]))
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


# --- 2. the gate: every response model ---------------------------------------------------


def _bare_datetimes(tp, where: str, metadata=(), seen=None) -> tuple[list[str], list[str]]:
    """(datetime fields without UtcDateTime, UtcDateTime fields) reachable from `tp`."""
    seen = set() if seen is None else seen
    bare: list[str] = []
    utc: list[str] = []
    if typing.get_origin(tp) is typing.Annotated:
        base, *extra = typing.get_args(tp)
        return _bare_datetimes(base, where, (*metadata, *extra), seen)
    if tp is datetime:
        (utc if any(m is _UTC_MARK for m in metadata) else bare).append(where)
        return bare, utc
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        if tp in seen:
            return bare, utc
        seen.add(tp)
        for name, field in tp.model_fields.items():
            b, u = _bare_datetimes(field.annotation, f"{tp.__module__}.{tp.__qualname__}.{name}", field.metadata, seen)
            bare += b
            utc += u
        return bare, utc
    for arg in typing.get_args(tp):
        b, u = _bare_datetimes(arg, where, (), seen)
        bare += b
        utc += u
    return bare, utc


def _response_models(route: APIRoute) -> list:
    """The route's response model and the models its documented answers name."""
    models = [route.response_model] if route.response_model is not None else []
    models += [r["model"] for r in route.responses.values() if isinstance(r, dict) and r.get("model") is not None]
    return models


def test_response_models_use_utc_datetime():
    # The walk finds a plain datetime however deep it sits.
    class Inner(BaseModel):
        at: datetime | None

    class Bad(BaseModel):
        ok: UtcDateTime
        maybe: UtcDateTime | None = None
        at: datetime
        items: list[Inner] = []
        by_day: dict[str, list[datetime]] = {}

    bare, utc = _bare_datetimes(list[Bad], "test")
    assert sorted(n.rsplit(".", 2)[-2] + "." + n.rsplit(".", 1)[-1] for n in bare) == [
        "Bad.at", "Bad.by_day", "Inner.at",
    ]
    assert len(utc) == 2

    routes = [r for r in app.routes if isinstance(r, APIRoute)]
    assert len(routes) > 250
    bare, utc, seen = [], [], set()
    for route in routes:
        for model in _response_models(route):
            b, u = _bare_datetimes(model, f"{sorted(route.methods)} {route.path}", (), seen)
            bare += b
            utc += u
    assert bare == [], "answer these as UtcDateTime (app/utc.py): " + ", ".join(bare)
    # The walk reached the models PF14c changed and PF2c's billing ones.
    for name in (
        "app.schemas.UserOut.created_at",
        "app.schemas.ApiKeyOut.created_at",
        "app.schemas.ApiKeyOut.last_used_at",
        "app.schemas.ApiKeyOut.revoked_at",
        "app.schemas.SubscriptionOut.current_period_end",
        "app.schemas.PaymentOut.paid_at",
    ):
        assert name in utc, name


# --- 3. routes that answer a dict ----------------------------------------------------------


@pytest.mark.parametrize("route", ["/v1/ping", "/licence/link/poll"])
def test_dict_routes_answer_utc(client, route):
    if route == "/v1/ping":
        h = signup(client)
        key = client.post("/keys", json={"name": "ping"}, headers=h).json()["key"]
        body = client.get("/v1/ping", headers={"Authorization": f"Bearer {key}"}).json()
        # It used to answer isoformat()'s `+00:00`.
        assert body["ok"] is True and _near_now(_utc(body["time"]))
        assert body["time"].endswith("Z") and "+" not in body["time"]
        return
    # /licence/link/poll hands the app a session token with the user in it.
    h = signup(client)
    link = client.post(
        "/licence/link", json={"device_name": "TEST-PC", "fingerprint": FP1, "app_version": "1.0.0"}, headers=CONTRACT
    ).json()
    approved = client.post("/licence/link/approve", json={"link_code": link["link_code"], "approve": True}, headers=session(h))
    assert approved.status_code == 200, approved.text
    polled = client.post("/licence/link/poll", json={"poll_secret": link["poll_secret"]}, headers=CONTRACT).json()
    assert polled["status"] == "approved"
    me = client.get("/auth/me", headers=h).json()
    assert polled["token"]["user"]["created_at"] == me["created_at"]
    assert _near_now(_utc(polled["token"]["user"]["created_at"]))


# --- 4. a share's expiry is stored in UTC --------------------------------------------------


def test_share_expiry_offset_stored_utc(client):
    token, sess = device_token(client)
    share = published(client, token)
    when = (datetime.now(timezone.utc) + timedelta(days=10)).replace(microsecond=0)
    # Any RFC 3339 time: here 3 hours ahead of UTC.
    res = client.patch(f"/shares/{share['share_id']}", json={"expires_at": when.astimezone(BAGHDAD).isoformat()}, headers=web(sess))
    assert res.status_code == 200, res.text
    assert res.json()["expires_at"] == when.strftime("%Y-%m-%dT%H:%M:%SZ")
    with SessionLocal() as db:
        stored = db.scalar(select(Share.expires_at).where(Share.share_id == share["share_id"]))
        assert clock.aware(stored) == when
        if db.get_bind().dialect.name == "sqlite":
            # SQLite keeps the wall time and drops any offset: it must be UTC's.
            raw = db.execute(text("SELECT expires_at FROM shares WHERE share_id = :s"), {"s": share["share_id"]}).scalar()
            assert raw.startswith(when.strftime("%Y-%m-%d %H:%M:%S")), raw
    # A naive time is read as UTC, the same as before.
    later = when + timedelta(days=1)
    res = client.patch(f"/shares/{share['share_id']}", json={"expires_at": later.replace(tzinfo=None).isoformat()}, headers=web(sess))
    assert res.status_code == 200 and _utc(res.json()["expires_at"]) == later
    # The input model itself turns an offset into UTC.
    from app.routers.shares import PatchShareIn

    parsed = PatchShareIn(expires_at=when.astimezone(BAGHDAD).isoformat()).expires_at
    assert parsed == when and parsed.utcoffset() == timedelta(0)
    assert TypeAdapter(UtcDateTime).validate_python("2026-11-10T09:47:10+03:00").isoformat() == "2026-11-10T06:47:10+00:00"


# --- 5. the site reads the times as UTC ----------------------------------------------------


def test_site_pf14c_reads_utc_times():
    keys = (ROOT / "src" / "app" / "dashboard" / "keys" / "page.tsx").read_text(encoding="utf-8")
    home = (ROOT / "src" / "app" / "dashboard" / "page.tsx").read_text(encoding="utf-8")
    for field in ("k.created_at", "k.last_used_at", "k.revoked_at"):
        assert f"formatDate({field})" in keys, field
    assert "formatDate(user.created_at)" in home
    assert "new Date(" not in keys and "new Date(" not in home
    api = (ROOT / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
    fn = re.search(r"export function parseServerDate\(value: string\): Date \{.*?\n\}", api, re.S)
    assert fn, "parseServerDate moved"
    exe = shutil.which("node")
    if exe is None:
        pytest.skip("node not on PATH")
    script = (
        fn.group(0).replace("export function", "function").replace("(value: string): Date", "(value)")
        + """
const forms = ["2026-11-10T22:30:05.150607Z", "2026-11-11T01:30:05.150607+03:00", "2026-11-10T22:30:05.150607"];
const out = forms.map((v) => parseServerDate(v).getTime());
const local = parseServerDate(forms[0]).toLocaleString("en-GB", { timeZone: "Asia/Baghdad" });
console.log(JSON.stringify({ out, local }));
"""
    )
    res = subprocess.run([exe, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert res.returncode == 0, res.stderr
    got = json.loads(res.stdout)
    instant = int(datetime(2026, 11, 10, 22, 30, 5, 150000, tzinfo=timezone.utc).timestamp() * 1000)
    assert got["out"] == [instant] * 3
    # A viewer in UTC+3 sees the next day, 01:30: their own time, not shifted twice.
    assert got["local"] == "11/11/2026, 01:30:05"
