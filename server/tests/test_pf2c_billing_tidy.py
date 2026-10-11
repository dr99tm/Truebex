"""PF2c billing tidy-ups: one Stripe invoice helper, credit packs named in the
payment history, the Stripe pack checkout updating a saved customer, billing
times in UTC, and a gate against a module that defines a name twice.

Paddle is tests/mock_paddle.py served in-process; Stripe calls are
monkeypatched as in test_ai_topup_billing.
"""

import ast
import typing
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import stripe
from pydantic import TypeAdapter
from sqlalchemy import select

from app import schemas
from app.billing import stripe_provider
from app.config import get_settings
from app.database import SessionLocal
from app.models import Payment, Subscription

from .conftest import CONSENT, signup
from .project_helpers import Person
from .test_billing_pf2 import paddle_post
from .test_billing_pf2b import buy

SERVER = Path(__file__).resolve().parents[1]
BAGHDAD = timezone(timedelta(hours=3))


def _pack(client, h, currency: str = "GBP") -> dict:
    res = client.post(
        "/account/ai/top-ups", json={"pack": "credits-5000", "currency": currency, "consent": CONSENT}, headers=h
    )
    assert res.status_code == 201, res.text
    return res.json()


def _utc(text: str) -> datetime:
    """An API time: RFC 3339 with `Z`, parsed aware."""
    assert text.endswith("Z"), text
    dt = datetime.fromisoformat(text)
    assert dt.utcoffset() == timedelta(0)
    return dt


# --- 1. one _invoice_subscription ------------------------------------------------------------


def test_invoice_subscription_shapes():
    f = stripe_provider._invoice_subscription
    # A string id, and an expanded subscription (plain or the SDK's own object).
    assert f({"subscription": "sub_1"}) == "sub_1"
    assert f({"subscription": {"id": "sub_2", "object": "subscription"}}) == "sub_2"
    sdk = stripe.StripeObject.construct_from({"id": "in_3", "subscription": {"id": "sub_3", "object": "subscription"}}, "sk")
    assert f(sdk) == "sub_3"
    # Newer API versions: parent.subscription_details.subscription, an id or expanded.
    newer = {"subscription": None, "parent": {"type": "subscription_details", "subscription_details": {"subscription": "sub_4"}}}
    assert f(newer) == "sub_4"
    assert f({"parent": {"subscription_details": {"subscription": {"id": "sub_5"}}}}) == "sub_5"
    # An empty top-level value is none, so the parent still answers.
    assert f({"subscription": "", "parent": {"subscription_details": {"subscription": "sub_6"}}}) == "sub_6"
    # Missing or empty everywhere: none (a payment-mode invoice of a credit pack).
    for inv in (
        {},
        {"subscription": None},
        {"subscription": ""},
        {"subscription": {}},
        {"subscription": {"id": ""}},
        {"subscription": None, "parent": None},
        {"parent": {"type": "quote_details", "subscription_details": None}},
        {"parent": {"subscription_details": {"subscription": ""}}},
    ):
        assert f(inv) is None, inv


# --- the gate: one definition per name -------------------------------------------------------


def _exempt(node: ast.AST) -> bool:
    """@overload stubs, and decorators that add to an earlier definition
    (`@x.setter`, `@x.register`)."""
    for dec in getattr(node, "decorator_list", []):
        dec = dec.func if isinstance(dec, ast.Call) else dec
        name = dec.attr if isinstance(dec, ast.Attribute) else getattr(dec, "id", "")
        if name == "overload" or (isinstance(dec, ast.Attribute) and name in ("setter", "getter", "deleter", "register")):
            return True
    return False


def _duplicates(tree: ast.Module) -> list[tuple[str, int, int]]:
    """(name, first line, again) for each function or class a module defines
    twice at the top level, or a top-level class defines twice in its body."""
    found = []

    def scan(body: list[ast.stmt], prefix: str) -> None:
        seen: dict[str, int] = {}
        for node in body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or _exempt(node):
                continue
            name = prefix + node.name
            if name in seen:
                found.append((name, seen[name], node.lineno))
            else:
                seen[name] = node.lineno
            if isinstance(node, ast.ClassDef) and not prefix:
                scan(node.body, f"{node.name}.")

    scan(tree.body, "")
    return found


def test_no_duplicate_top_level_defs():
    # The checker itself: a second definition is caught; overloads are not.
    assert _duplicates(ast.parse("def a(): pass\nclass B: pass\ndef a(): pass\n")) == [("a", 1, 3)]
    assert _duplicates(ast.parse("class C:\n def m(self): pass\n def m(self): pass\n")) == [("C.m", 2, 3)]
    stubs = "from typing import overload\n@overload\ndef f(x: int) -> int: ...\n@overload\ndef f(x: str) -> str: ...\ndef f(x): return x\n"
    assert _duplicates(ast.parse(stubs)) == []
    hits = []
    for folder in ("app", "scripts"):
        for path in sorted((SERVER / folder).rglob("*.py")):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            hits += [f"{path.relative_to(SERVER).as_posix()}:{a}/{b} {name}" for name, a, b in _duplicates(tree)]
    assert hits == [], "a later definition silently replaces an earlier one"


# --- 2. one-off items named in the payment history ---------------------------------------------


def test_payments_name_one_off_items(client, paddle):
    h = signup(client)
    co, _ = buy(client, h, paddle)  # Pro, monthly: a plan's row
    pack = _pack(client, h)
    pending = client.get(f"/billing/payments/{pack['reference']}", headers=h).json()
    assert (pending["status"], pending["item"], pending["credits"]) == ("pending", "ai_credits", 5000)
    for ev in paddle.pay(parse_qs(urlparse(pack["url"]).query)["_ptxn"][0], country="GB"):
        assert paddle_post(client, ev).status_code == 200

    rows = {p["reference"]: p for p in client.get("/billing/payments", headers=h).json()}
    assert set(rows) == {co["reference"], pack["reference"]}
    bought = rows[pack["reference"]]
    assert (bought["plan"], bought["status"], bought["item"], bought["credits"]) == ("ai_credits", "paid", "ai_credits", 5000)
    assert bought["interval"] is None
    plan = rows[co["reference"]]
    assert (plan["plan"], plan["interval"], plan["status"]) == ("pro", "month", "paid")
    assert plan["item"] is None and plan["credits"] is None
    # The detail and the return page's refresh say the same.
    assert client.get(f"/billing/payments/{pack['reference']}", headers=h).json()["credits"] == 5000
    refreshed = client.post(f"/billing/payments/{pack['reference']}/refresh", headers=h).json()
    assert (refreshed["item"], refreshed["credits"]) == ("ai_credits", 5000)
    assert client.get(f"/billing/payments/{co['reference']}", headers=h).json()["item"] is None


def test_payments_one_off_item_without_details(client, paddle, monkeypatch):
    """An item with no details hook (or a pack whose top-up row is gone) is
    still named as an item; the site then shows its name without a size."""
    from app.ai.models import AiTopUp
    from app.billing import service

    h = signup(client)
    buy(client, h, paddle)
    pack = _pack(client, h)
    with SessionLocal() as db:
        db.delete(db.get(AiTopUp, pack["reference"]))
        uid = db.scalar(select(Payment.user_id).where(Payment.reference == pack["reference"]))
        db.add(Payment(user_id=uid, provider="paddle", plan="gift_card", reference="tbx_gift", amount=500, currency="GBP"))
        db.commit()
    monkeypatch.setattr(service, "ONE_OFF_ITEMS", service.ONE_OFF_ITEMS | {"gift_card"})
    rows = {p["reference"]: p for p in client.get("/billing/payments", headers=h).json()}
    assert (rows[pack["reference"]]["item"], rows[pack["reference"]]["credits"]) == ("ai_credits", None)
    assert (rows["tbx_gift"]["item"], rows["tbx_gift"]["credits"]) == ("gift_card", None)


# --- 3. the Stripe pack checkout and a saved customer -----------------------------------------


def test_stripe_one_time_checkout_updates_saved_customer(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "billing_provider", "stripe")
    monkeypatch.setattr(s, "stripe_tax_enabled", True)
    sessions: list[dict] = []

    def create(**params):
        sessions.append(params)
        return {"id": f"cs_pack_{len(sessions)}", "url": f"https://checkout.stripe.test/{len(sessions)}"}

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    p = Person(client, "buyer@example.com")  # a Pro trial (holds ai.metered)

    # No Stripe customer yet: Checkout makes one from the e-mail.
    _pack(client, p.session, "USD")
    first = sessions[-1]
    assert first["mode"] == "payment" and first["automatic_tax"] == {"enabled": True}
    assert first["customer_email"] == "buyer@example.com"
    assert "customer" not in first and "customer_update" not in first

    # A saved customer (an earlier Stripe subscription): its address and name
    # are filled in at checkout, so Stripe Tax has an address to work from.
    with SessionLocal() as db:
        db.add(Subscription(user_id=p.user_id, plan="pro", provider="stripe", status="canceled", provider_customer_id="cus_saved"))
        db.commit()
    _pack(client, p.session, "USD")
    second = sessions[-1]
    assert second["customer"] == "cus_saved"
    assert second["customer_update"] == {"address": "auto", "name": "auto"}
    assert "customer_email" not in second
    assert second["automatic_tax"] == {"enabled": True}


# --- 4. billing times in UTC ------------------------------------------------------------------

# Every response model of /billing/* that carries a time.
BILLING_MODELS = (
    schemas.FoundingOut,
    schemas.SubscriptionOut,
    schemas.ExitOut,
    schemas.InvoiceOut,
    schemas.PaymentOut,
)


def _time_fields(model) -> list[str]:
    def has_datetime(tp) -> bool:
        return tp is datetime or any(has_datetime(a) for a in typing.get_args(tp))

    return [name for name, f in model.model_fields.items() if has_datetime(f.annotation)]


def test_billing_times_are_utc(client, paddle):
    # One place: every billing time field is the UTC type, so a naive SQLite
    # value and a Postgres session's +03:00 value both leave as `Z`.
    assert {m.__name__: _time_fields(m) for m in BILLING_MODELS} == {
        "FoundingOut": ["ends_at"],
        "SubscriptionOut": ["current_period_end", "cooling_off_until", "withdrawal_until"],
        "ExitOut": ["requested_at", "effective_at"],
        "InvoiceOut": ["issued_at"],
        "PaymentOut": ["created_at", "paid_at", "key_info_at"],
    }
    instant = datetime(2026, 11, 10, 6, 47, 10, 150607, tzinfo=timezone.utc)
    for model in BILLING_MODELS:
        for name in _time_fields(model):
            field = model.model_fields[name]
            tp = typing.Annotated[(field.annotation, *field.metadata)] if field.metadata else field.annotation
            adapter = TypeAdapter(tp)
            for value in (instant.replace(tzinfo=None), instant.astimezone(BAGHDAD), instant):
                text = adapter.dump_python(adapter.validate_python(value), mode="json")
                assert text == "2026-11-10T06:47:10.150607Z", (model.__name__, name, value, text)
    for value in (instant.replace(tzinfo=None), instant.astimezone(BAGHDAD)):
        out = schemas.SubscriptionOut(
            tier="pro", interval="month", seats=1, status="active", provider="paddle", current_period_end=value,
            cancel_at_period_end=False, founding=False, can_manage=True, withdrawal_until=value,
        )
        body = out.model_dump(mode="json")
        assert body["current_period_end"] == body["withdrawal_until"] == "2026-11-10T06:47:10.150607Z"

    # Through the API (SQLite hands back naive UTC).
    h = signup(client)
    co, _ = buy(client, h, paddle)
    sub = client.get("/billing/subscription", headers=h).json()
    end = _utc(sub["current_period_end"])
    assert timedelta(days=27) < end - datetime.now(timezone.utc) < timedelta(days=32)
    (pay,) = client.get("/billing/payments", headers=h).json()
    assert pay["reference"] == co["reference"]
    assert _utc(pay["paid_at"]) >= _utc(pay["created_at"])
    out = client.post("/billing/cancel", json={"confirm": True}, headers=h).json()
    assert _utc(out["effective_at"]) == end
    assert abs(_utc(out["requested_at"]) - datetime.now(timezone.utc)) < timedelta(minutes=5)
    founding = client.get("/billing/plans").json()["founding"]
    assert founding["ends_at"] is None or _utc(founding["ends_at"])


@pytest.mark.postgres
def test_billing_times_are_utc_postgres(client):
    """On Postgres whose session zone is not UTC (TEST_DATABASE_URL, the
    session set to Asia/Baghdad), the API still answers every billing time in
    UTC with `Z`, the same instant as stored."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.database import get_db, init_db
    from app.main import app

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
        end = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=30)
        paid = datetime.now(timezone.utc).replace(microsecond=0)
        with make() as db:
            assert db.execute(text("SHOW TimeZone")).scalar() == "Asia/Baghdad"
            uid = db.execute(text("SELECT id FROM users WHERE email = 'pg@example.com'")).scalar()
            db.add(Subscription(user_id=uid, plan="pro", provider="wayl", status="active", current_period_end=end))
            db.add(Payment(user_id=uid, provider="wayl", plan="pro", reference="tbx_pg", amount=130000, currency="IQD",
                           status="paid", paid_at=paid))
            db.commit()
        with make() as db:
            stored = db.scalar(select(Subscription.current_period_end).where(Subscription.user_id == uid))
            assert stored.utcoffset() == timedelta(hours=3) and stored == end  # the session's zone
        sub = client.get("/billing/subscription", headers=h).json()
        assert sub["provider"] == "wayl" and _utc(sub["current_period_end"]) == end
        (pay,) = client.get("/billing/payments", headers=h).json()
        assert _utc(pay["paid_at"]) == paid and _utc(pay["created_at"])
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
