"""AI credits beyond the proxy (PF11): the monthly grant without roll-over,
top-ups bought through PF2's checkout, the self-hosted adapter and its
fallback, the dashboard's AI section and the AI admin."""

import json
import shutil
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import stripe
from sqlalchemy import select

from app.ai import credits, jobs as ai_jobs
from app.ai.models import AiCreditLedger, AiUsage
from app.config import get_settings
from app.database import SessionLocal
from app.models import Payment, User
from app.render import pools

from .ai_helpers import AI, USER_TEXT, assemble, body, data_of, dev, fake, first_turn, names, send, studio_person  # noqa: F401
from .conftest import CONSENT, make_admin, signup
from .licence_helpers import Clock, error_of
from .project_helpers import Person
from .render_helpers import studio
from .test_billing_pf2 import paddle_post

UTC = timezone.utc


def _user(db, user_id: int) -> User:
    return db.get(User, user_id)


def _ledger(user_id: int) -> list[tuple]:
    with SessionLocal() as db:
        rows = db.scalars(select(AiCreditLedger).where(AiCreditLedger.account_id == user_id).order_by(AiCreditLedger.id)).all()
        return [(r.kind, r.bucket, r.delta, r.ref) for r in rows]


def _balance(user_id: int) -> dict:
    with SessionLocal() as db:
        return credits.balance_json(db, _user(db, user_id))


def test_ai_allowance_grant_and_no_rollover(client, monkeypatch):
    clk = Clock(monkeypatch, start=datetime(2026, 10, 20, 12, 0, tzinfo=UTC))
    a = studio_person(client)
    bal = client.get("/ai/balance", headers=dev(a)).json()
    assert (bal["allowance_monthly"], bal["credits_remaining"], bal["resets_at"]) == (5000, 5000, "2026-11-01T00:00:00Z")
    with SessionLocal() as db:
        user = _user(db, a.user_id)
        credits.adjust(db, user, -1000, "used-in-october")
        credits.add_top_up(db, user, 300, "pack-1")
        db.commit()
    # 00:30 UTC on the 1st: the unused 4000 expire, 5000 are granted, top-ups stay.
    clk.at = datetime(2026, 11, 1, 0, 30, tzinfo=UTC)
    assert ai_jobs.allowance_grant(clk.at) == 1
    bal = _balance(a.user_id)
    assert (bal["allowance_remaining"], bal["top_up_remaining"], bal["credits_remaining"]) == (5000, 300, 5300)
    assert bal["resets_at"] == "2026-12-01T00:00:00Z"
    ledger = _ledger(a.user_id)
    assert ("expire", "allowance", -4000, "2026-10") in ledger and ("grant", "allowance", 5000, "2026-11") in ledger
    # Idempotent: the job again (and a read) changes nothing.
    assert ai_jobs.allowance_grant(clk.at) == 0
    _balance(a.user_id)
    assert _ledger(a.user_id) == ledger
    # A month's overrun is written off at the reset, never carried.
    with SessionLocal() as db:
        credits.adjust(db, _user(db, a.user_id), -5050, "overrun")
        db.commit()
    clk.at = datetime(2026, 12, 1, 0, 0, 1, tzinfo=UTC)
    bal = _balance(a.user_id)  # the lazy roll-over on first sight
    assert (bal["allowance_remaining"], bal["top_up_remaining"]) == (5000, 300)
    assert ("expire", "allowance", 50, "2026-11") in _ledger(a.user_id)
    # A plan that rises mid-month grants the difference once.
    p = Person(client, "trial@example.com")
    assert _balance(p.user_id)["allowance_monthly"] == 2000
    studio(p.user_id)
    assert _balance(p.user_id)["allowance_remaining"] == 5000
    assert _balance(p.user_id)["allowance_remaining"] == 5000
    assert ("grant", "allowance", 3000, "2026-12:studio") in _ledger(p.user_id)


def test_ai_topup_checkout_via_billing(client, paddle):
    p = Person(client, "buyer@example.com")  # a Pro trial (holds ai.metered)
    res = client.post("/account/ai/top-ups", json={"pack": "credits-5000", "currency": "GBP", "consent": CONSENT}, headers=p.session)
    assert res.status_code == 201, res.text
    out = res.json()
    q = parse_qs(urlparse(out["url"]).query)
    assert q["ref"] == [out["reference"]] and q["back"] == ["dashboard-cloud"]
    txn = paddle.STATE["transactions"][q["_ptxn"][0]]
    assert txn["items"][0]["price"]["unit_price"] == {"amount": "600", "currency_code": "GBP"}
    assert txn["custom_data"]["item"] == "ai_credits" and txn["custom_data"]["reference"] == out["reference"]
    with SessionLocal() as db:
        pay = db.scalar(select(Payment).where(Payment.reference == out["reference"]))
        assert (pay.plan, pay.amount, pay.currency, pay.status) == ("ai_credits", 600, "GBP", "pending")
    assert _balance(p.user_id)["top_up_remaining"] == 0
    events = paddle.pay(q["_ptxn"][0])
    assert [e["event_type"] for e in events] == ["transaction.completed"]
    # Only a verified event credits the pack, once.
    forged = client.post("/billing/webhooks/paddle", content=json.dumps(events[0]).encode())
    assert forged.status_code == 400 and _balance(p.user_id)["top_up_remaining"] == 0
    assert paddle_post(client, events[0]).status_code == 200
    assert _balance(p.user_id)["top_up_remaining"] == 5000
    replay = dict(events[0], event_id="evt_replayed")
    assert paddle_post(client, replay).status_code == 200
    assert _balance(p.user_id)["top_up_remaining"] == 5000
    account = client.get("/account/ai", headers=p.session).json()
    assert account["top_ups"][0]["state"] == "credited" and account["balance"]["top_up_remaining"] == 5000
    # Paid without a webhook: the refresh after checkout credits it.
    second = client.post("/account/ai/top-ups", json={"pack": "credits-20000", "currency": "GBP", "consent": CONSENT}, headers=p.session).json()
    paddle.pay(parse_qs(urlparse(second["url"]).query)["_ptxn"][0])
    assert client.post(f"/billing/payments/{second['reference']}/refresh", headers=p.session).json()["status"] == "paid"
    assert _balance(p.user_id)["top_up_remaining"] == 25000
    # Refusals.
    bad = client.post("/account/ai/top-ups", json={"pack": "credits-1", "currency": "GBP", "consent": CONSENT}, headers=p.session)
    assert bad.status_code == 422 and bad.json()["code"] == "validation_failed"
    stale = client.post("/account/ai/top-ups", json={"pack": "credits-5000", "currency": "GBP", "consent": {"version": "old", "accepted": True}}, headers=p.session)
    assert stale.status_code == 422
    free = signup(client, "free@example.com")
    assert client.post("/account/ai/top-ups", json={"pack": "credits-5000", "currency": "GBP", "consent": CONSENT}, headers=free).json()["code"] == "plan_required"
    assert client.post("/account/ai/top-ups", json={"pack": "credits-5000", "currency": "GBP", "consent": CONSENT}).status_code == 401


def test_ai_topup_checkout_stripe(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_provider", "stripe")
    made = {}

    def create(**params):
        made.update(params)
        return {"id": "cs_topup_1", "url": "https://checkout.stripe.test/topup"}

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    p = Person(client, "buyer@example.com")
    out = client.post("/account/ai/top-ups", json={"pack": "credits-5000", "currency": "USD", "consent": CONSENT}, headers=p.session).json()
    assert out["url"] == "https://checkout.stripe.test/topup"
    assert made["mode"] == "payment" and made["client_reference_id"] == out["reference"]
    assert made["line_items"][0]["price_data"] == {"currency": "usd", "unit_amount": 750, "product_data": {"name": "Truebex AI credits (5,000)"}}
    assert made["success_url"].endswith(f"/dashboard/cloud/?topup=success&ref={out['reference']}")
    session = {"id": "cs_topup_1", "client_reference_id": out["reference"], "status": "complete", "payment_status": "paid", "amount_total": 750}
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda *a, **k: session)
    assert client.post(f"/billing/payments/{out['reference']}/refresh", headers=p.session).json()["status"] == "paid"
    assert _balance(p.user_id)["top_up_remaining"] == 5000


def _open_alias(tmp_path, monkeypatch) -> None:
    from app.ai import aliases

    table = tmp_path / "aliases.json"
    shutil.copy(aliases.DEFAULT_PATH, table)
    raw = json.loads(table.read_text("utf-8"))
    raw["aliases"]["truebex-open"]["enabled"] = True
    table.write_text(json.dumps(raw), "utf-8")
    monkeypatch.setattr(get_settings(), "ai_aliases_path", str(table))


def test_ai_selfhosted_adapter_and_fallback(client, fake, tmp_path, monkeypatch):
    _open_alias(tmp_path, monkeypatch)
    admin = signup(client, "admin@example.com")
    make_admin("admin@example.com")
    reg = client.post("/admin/ai/servers", json={"server_id": "gpu-ai-01", "alias": "truebex-open", "base_url": fake.base_url}, headers=admin)
    assert reg.status_code == 201 and reg.json()["state"] == "cold"
    now = datetime.now(UTC)
    assert ai_jobs.servers_scale(now)["warm"] == 1
    a = studio_person(client)
    assert [m["alias"] for m in client.get("/ai/models", headers=dev(a)).json()["models"]] == ["truebex-assist", "truebex-open"]
    fake.chat_sse([
        {"choices": [{"index": 0, "delta": {"role": "assistant", "content": "Placing"}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"content": " the window."}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "place", "arguments": "{\"kind\": \"window\", "}}]}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\"width_mm\": 1200}"}}]}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
        {"choices": [], "usage": {"prompt_tokens": 800, "completion_tokens": 40}},
    ])
    history = [
        {"role": "user", "content": [{"type": "text", "text": USER_TEXT}]},
        {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "tool_use", "id": "toolu_01", "name": "find", "input": {"kind": "wall", "room": "Study"}},
        ]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_01", "content": [{"type": "text", "text": "{\"matches\": 1}"}]}]},
    ]
    res = send(client, dev(a), body(history, model="truebex-open"))
    assert res.status_code == 200, res.text
    seen = names(res.content)
    assert seen[0] == "message_start" and seen[-2:] == ["truebex_credits", "message_stop"] and "message_delta" in seen
    content = assemble(res.content)
    assert content == [
        {"type": "text", "text": "Placing the window."},
        {"type": "tool_use", "id": "call_1", "name": "place", "input": {"kind": "window", "width_mm": 1200}},
    ]
    assert data_of(res.content, "message_delta")[0]["delta"]["stop_reason"] == "tool_use"
    cred = data_of(res.content, "truebex_credits")[0]
    # (800 × 600 + 40 × 2400) / 10⁶ -> 1, served by the inference server.
    assert cred["charged"] == 1 and cred["served_by"] == {"provider": "truebex", "model": "truebex-open"}
    sent = fake.of_path("/v1/chat/completions")[-1].json()
    assert sent["model"] == "truebex-open" and sent["stream"] is True and sent["stream_options"] == {"include_usage": True}
    assert [m["role"] for m in sent["messages"]] == ["system", "user", "assistant", "tool"]
    assert sent["messages"][2]["tool_calls"][0] == {
        "id": "toolu_01", "type": "function", "function": {"name": "find", "arguments": "{\"kind\":\"wall\",\"room\":\"Study\"}"},
    }
    assert sent["messages"][3] == {"role": "tool", "tool_call_id": "toolu_01", "content": "{\"matches\": 1}"}
    assert sent["tools"][1]["function"]["name"] == "place" and sent["tool_choice"] == "auto"
    # A whole answer translates back too.
    fake.chat_json({
        "choices": [{"message": {"role": "assistant", "content": "Done.", "tool_calls": [
            {"id": "call_2", "type": "function", "function": {"name": "place", "arguments": "{\"width_mm\": 900}"}}]}, "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10},
    })
    whole = send(client, dev(a), body(history, model="truebex-open", stream=False, max_tokens=1024)).json()
    assert whole["model"] == "truebex-open" and whole["stop_reason"] == "tool_use"
    assert whole["content"][1] == {"type": "tool_use", "id": "call_2", "name": "place", "input": {"width_mm": 900}}
    assert whole["served_by"] == {"provider": "truebex", "model": "truebex-open"}
    # No warm server: the fallback alias answers.
    fake.healthy = False
    later = datetime.now(UTC)
    scaled = ai_jobs.servers_scale(later)
    assert scaled["warm"] == 0 and scaled["wanted"] == 1 and pools.DESIRED["gpu-ai"] == 1
    fake.sse("window/03-end.sse")
    fallback = send(client, dev(a), first_turn(model="truebex-open"))
    assert data_of(fallback.content, "truebex_credits")[0]["served_by"] == {"provider": "anthropic", "model": "claude-opus-5-5"}
    with SessionLocal() as db:
        last = db.scalars(select(AiUsage).order_by(AiUsage.id.desc())).first()
        assert (last.alias, last.served_by, last.provider_model) == ("truebex-open", "anthropic", "claude-opus-5-5")
    admin_view = client.get("/admin/ai", headers=admin).json()
    assert admin_view["servers"][0]["state"] == "cold" and admin_view["gpu_ai_wanted"] == 1
    assert client.delete("/admin/ai/servers/gpu-ai-01", headers=admin).status_code == 200


def test_ai_account_and_admin(client, fake):
    a = studio_person(client)
    view = client.get("/account/ai", headers=a.session).json()
    assert view["feature"] is True and view["balance"]["allowance_monthly"] == 5000 and view["currency"] == "GBP"
    assert [p["id"] for p in view["packs"]] == ["credits-5000", "credits-20000"] and view["packs"][0]["amount_minor"] == 600
    fake.sse("window/01-find.sse")
    send(client, dev(a), first_turn())
    turns = client.get("/account/ai?currency=USD", headers=a.session).json()
    assert turns["turns"][0]["alias"] == "truebex-assist" and turns["turns"][0]["credits"] == 29
    assert turns["turns"][0]["tool_names"] == ["find"] and turns["packs"][0]["amount_minor"] == 750
    free = signup(client, "free@example.com")
    fv = client.get("/account/ai", headers=free).json()
    assert fv["feature"] is False and fv["balance"] is None and fv["plan_needed"] == "pro"
    assert client.get("/account/ai").status_code == 401
    admin = signup(client, "admin@example.com")
    make_admin("admin@example.com")
    overview = client.get("/admin/ai", headers=admin).json()
    spend = overview["spend"][0]
    assert (spend["alias"], spend["served_by"], spend["turns"], spend["credits"]) == ("truebex-assist", "anthropic", 1, 29)
    assert spend["provider_cost_usd"] == round((1024 * 4 + 180 * 20 + 4096 * 5) / 1e6, 4)
    assert {x["alias"] for x in overview["aliases"]} == {"truebex-assist", "truebex-open"}
    assert client.get("/admin/ai", headers=a.session).status_code == 403
    bad = client.post("/admin/ai/servers", json={"server_id": "x", "alias": "truebex-assist", "base_url": "http://h"}, headers=admin)
    assert bad.status_code == 422
    assert client.get("/ai/balance", headers={**a.session, **AI}).json()["code"] == "forbidden"
    time.sleep(0)
