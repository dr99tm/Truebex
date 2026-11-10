"""The metered assistant proxy (PF11, contract ai-proxy 1.1): the contract's
§10 platform tests first, then 5.1 / 5.2 / 5.4, duplicates and limits. The
upstream is tests/fakes/fake_provider.py, a real HTTP server the official SDK
talks to, serving PF11's own window turns (tests/fixtures/ai/: cache tokens,
the proxy's whole stream). The app's own set (tests/contracts/ai-proxy/) is
played by test_pf11b_ai_proxy_1_1.py."""

import json
import os
import shutil
import time
from datetime import timedelta

from sqlalchemy import select, text

from app.ai import credits, proxy
from app.ai.models import AiCreditLedger, AiTurn, AiUsage
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.licence import clock

from .ai_helpers import (
    AI, SESSION_ID, SYSTEM, TOOLS, USER_TEXT, WALL, assemble, body, data_of, dev, fake, first_turn, key, names,  # noqa: F401
    remaining, send, set_remaining, studio_person,
)
from .fakes.fake_provider import contract_bytes, event_name, events_of, fixture_bytes
from .licence_helpers import error_of
from .project_helpers import Person

TOOL_RESULT = {
    "type": "tool_result",
    "tool_use_id": "toolu_01Tbx0Find00000000000001",
    "is_error": False,
    "content": [{"type": "text", "text": json.dumps({"matches": [{"ref": WALL, "kind": "wall", "room": "Study"}]})}],
}


def _compact(obj) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()


def _window_history(first_answer: bytes) -> list:
    return [
        {"role": "user", "content": [{"type": "text", "text": USER_TEXT}]},
        {"role": "assistant", "content": assemble(first_answer)},
        {"role": "user", "content": [TOOL_RESULT]},
    ]


# --- §10 ---------------------------------------------------------------------------------------


def test_messages_requires_ai_metered(client, fake):
    free = Person(client, "free@example.com", trial=False)
    res = send(client, dev(free), first_turn())
    body_ = error_of(res, 403, "plan_required")
    assert body_["data"]["feature"] == "ai.metered" and body_["data"]["plan"] == "free" and body_["data"]["plan_needed"] == "pro"
    # Session tokens and API keys are refused; no token is 401.
    a = studio_person(client)
    error_of(send(client, {**a.session, **AI}, first_turn()), 403, "forbidden")
    api_key = client.post("/keys", json={"name": "ci"}, headers=a.session).json()["key"]
    error_of(send(client, {"Authorization": f"Bearer {api_key}", **AI}, first_turn()), 403, "forbidden")
    error_of(send(client, AI, first_turn()), 401, "unauthenticated")
    error_of(send(client, {"Authorization": "Bearer nonsense", **AI}, first_turn()), 401, "unauthenticated")
    assert fake.of_path("/v1/messages") == []


def test_tool_use_passthrough(client, fake):
    a = studio_person(client)
    set_remaining(a.user_id, 4388)
    fake.sse("window/01-find.sse")
    first = send(client, dev(a), first_turn())
    assert first.status_code == 200, first.text
    # The stream is the fixture's bytes exactly: tool_use deltas untouched,
    # one truebex_credits event (29 credits, 4359 left) before message_stop.
    assert first.content == fixture_bytes("window/01-find.sse")
    sent = fake.of_path("/v1/messages")[-1]
    upstream = sent.json()
    assert upstream["model"] == "claude-opus-5-5" and upstream["max_tokens"] == 8192 and upstream["stream"] is True
    assert upstream["thinking"] == {"type": "adaptive"} and upstream["output_config"] == {"effort": "high"}
    assert upstream["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in sent.headers["anthropic-beta"]
    assert "metadata" not in upstream and SESSION_ID.encode() not in sent.body
    assert upstream["tools"][-1]["cache_control"] == {"type": "ephemeral"} and "cache_control" not in upstream["tools"][0]
    assert upstream["system"] == [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}]
    assert sent.headers["x-api-key"] == "sk-ant-test-key"

    # Turn 2: the history goes back as received (thinking signature included)
    # and the tool_result reaches the provider byte-equal.
    history = _window_history(first.content)
    assert history[1]["content"][0] == {"type": "thinking", "thinking": "", "signature": "EqQBCkYIBxgCKkDTbx0FixtureSignatureFind0001"}
    assert history[1]["content"][1]["input"] == {"kind": "wall", "room": "Study", "facing": "n"}
    fake.sse("window/02-place.sse")
    second = send(client, dev(a), body(history))
    assert second.status_code == 200, second.text
    assert second.content == fixture_bytes("window/02-place.sse")
    raw = fake.of_path("/v1/messages")[-1].body
    assert _compact(TOOL_RESULT) in raw
    assert _compact(history[1]["content"][0]) in raw and _compact(history[1]["content"][1]) in raw
    place = assemble(second.content)[-1]
    assert place["type"] == "tool_use" and place["input"] == {"kind": "window", "host": WALL, "width_mm": 1200}

    fake.sse("window/03-end.sse")
    third = send(client, dev(a), body([*history, {"role": "assistant", "content": assemble(second.content)}, {
        "role": "user", "content": [{"type": "tool_result", "tool_use_id": place["id"], "content": "{\"placed\": true}"}],
    }]))
    assert third.content == fixture_bytes("window/03-end.sse")
    assert remaining(a.user_id) == 4345


def test_stream_events_and_credits_event(client, fake, monkeypatch):
    a = studio_person(client)
    monkeypatch.setattr(proxy, "PING_S", 0.15)
    # 0.4 s between upstream events: the proxy keeps the stream alive itself.
    fake.sse("window/02-place.sse", delay_s=0.4)
    res = send(client, dev(a), first_turn())
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")
    seen = names(res.content)
    core = [n for n in seen if n != "ping"]
    assert core[0] == "message_start" and seen[-1] == "message_stop"
    # truebex_credits right before message_stop, after message_delta.
    assert seen.count("truebex_credits") == 1 and seen[-2] == "truebex_credits" and core[-3] == "message_delta"
    ours = [e for e in events_of(res.content) if e == b'event: ping\ndata: {"type":"ping"}\n\n']
    assert len(ours) >= 3
    # Without the proxy's pings and credits event, the provider's stream byte for byte.
    upstream = b"".join(e for e in events_of(res.content) if e not in ours and event_name(e) != "truebex_credits")
    expected = b"".join(e for e in events_of(fixture_bytes("window/02-place.sse")) if event_name(e) != "truebex_credits")
    assert upstream == expected
    # The §5 order: every block stops before message_delta.
    assert core.index("message_delta") > max(i for i, n in enumerate(core) if n == "content_block_stop")


def test_credits_charged_from_usage(client, fake):
    rates = {"input": 4000, "output": 20000, "cache_read": 400, "cache_write": 5000}
    usage = {"input_tokens": 5120, "output_tokens": 210, "cache_read_input_tokens": 4096, "cache_creation_input_tokens": 0}
    # (5120 × 4000 + 210 × 20000 + 4096 × 400) / 10⁶ = 26.3184 -> 27
    assert credits.charge_for(usage, rates) == 27
    assert credits.charge_for({"input_tokens": 1}, rates) == 1  # rounded up
    assert credits.charge_for({"cache_creation_input_tokens": 200}, rates) == 1
    assert credits.charge_for({}, rates) == 0
    # A turn: allowance first, then top-ups; the usage record has the counts.
    a = studio_person(client)
    set_remaining(a.user_id, 10)
    with SessionLocal() as db:
        from app.models import User

        credits.add_top_up(db, db.get(User, a.user_id), 100, "test-pack")
        db.commit()
    fake.sse("window/01-find.sse")
    res = send(client, dev(a), first_turn())
    assert data_of(res.content, "truebex_credits")[0]["charged"] == 29
    with SessionLocal() as db:
        rows = db.scalars(select(AiCreditLedger).where(AiCreditLedger.kind == "usage")).all()
        assert sorted((r.bucket, r.delta) for r in rows) == [("allowance", -10), ("top_up", -19)]
        assert len({r.ref for r in rows}) == 1
        u = db.scalars(select(AiUsage)).one()
        assert (u.input_tokens, u.output_tokens, u.cache_read_tokens, u.cache_write_tokens, u.credits) == (1024, 180, 0, 4096, 29)
        assert u.alias == "truebex-assist" and u.provider_model == "claude-opus-5-5" and u.served_by == "anthropic"
        assert u.session_id == SESSION_ID and u.tool_names == ["find"] and u.stop_reason == "tool_use"
        # The provider's list price for these tokens: 1024 × $4 + 180 × $20 + 4096 × $5 per million.
        assert u.provider_cost_micros == 1024 * 4 + 180 * 20 + 4096 * 5
    assert remaining(a.user_id) == 81


def test_refuse_when_credits_empty(client, fake):
    a = studio_person(client)
    set_remaining(a.user_id, 0)
    res = send(client, dev(a), first_turn())
    err = error_of(res, 403, "credits_exhausted")
    assert err["data"]["remaining"] == 0 and err["data"]["plan_needed"] == "studio"
    assert err["data"]["top_up_url"].endswith("/dashboard/cloud/#ai-credits") and err["data"]["resets_at"].endswith("T00:00:00Z")
    assert fake.of_path("/v1/messages") == []
    # A pro trial is pointed at the next tier on sale (Team: Studio is no longer sold).
    p = Person(client, "pro@example.com")
    set_remaining(p.user_id, 0)
    assert error_of(send(client, dev(p), first_turn()), 403, "credits_exhausted")["data"]["plan_needed"] == "team"
    # A started turn finishes below zero; the next one is refused.
    set_remaining(a.user_id, 10)
    fake.sse("window/01-find.sse")
    ok = send(client, dev(a), first_turn())
    assert ok.status_code == 200 and data_of(ok.content, "truebex_credits")[0]["remaining"] == -19
    error_of(send(client, dev(a), first_turn()), 403, "credits_exhausted")
    # More than is left for the input estimate is refused too.
    set_remaining(a.user_id, 1)
    big = first_turn()
    big["messages"][0]["content"][0]["text"] = "x" * 400_000  # about 100 000 tokens = 400 credits of input
    error_of(send(client, dev(a), big), 403, "credits_exhausted")


def test_forced_tool_choice_rejected(client, fake):
    a = studio_person(client)
    for choice in ({"type": "tool", "name": "find"}, {"type": "any"}, "auto"):
        err = error_of(send(client, dev(a), first_turn(tool_choice=choice)), 422, "validation_failed")
        assert err["data"]["fields"][0]["field"] == "tool_choice"
    for choice in ({"type": "auto"}, {"type": "none"}):
        fake.sse("window/03-end.sse")
        assert send(client, dev(a), first_turn(tool_choice=choice)).status_code == 200
    assert len(fake.of_path("/v1/messages")) == 2


def test_upstream_errors_mapped(client, fake):
    a = studio_person(client)
    set_remaining(a.user_id, 1000)
    fake.error(400, {"type": "error", "error": {"type": "invalid_request_error", "message": "messages.1: bad block"}})
    err = error_of(send(client, dev(a), first_turn()), 422, "upstream_rejected")
    assert err["data"]["provider_message"] == "messages.1: bad block"
    fake.error(529, {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}, retry_after=7)
    res = send(client, dev(a), first_turn())
    assert error_of(res, 503, "upstream_busy")["retry_after_s"] == 7 and res.headers["Retry-After"] == "7"
    fake.error(429, retry_after=3)
    assert error_of(send(client, dev(a), first_turn()), 503, "upstream_busy")["retry_after_s"] == 3
    fake.error(500)
    idem = key()
    error_of(send(client, dev(a), first_turn(), idem), 502, "upstream_failed")
    # An error event before any output is a failure before output too.
    fake.sse(b'event: error\ndata: {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}\n\n')
    error_of(send(client, dev(a), first_turn()), 503, "upstream_busy")
    # Nothing charged so far, and a retry with the same key is not a duplicate.
    assert remaining(a.user_id) == 1000
    with SessionLocal() as db:
        assert db.scalars(select(AiUsage)).all() == []
    fake.sse("window/03-end.sse")
    assert send(client, dev(a), first_turn(), idem).status_code == 200
    # The network failing before output: 502.
    get_settings().anthropic_base_url = "http://127.0.0.1:9"
    error_of(send(client, dev(a), first_turn()), 502, "upstream_failed")
    get_settings().anthropic_base_url = fake.base_url
    # A stream cut after output began: an in-band error, charged for what the
    # provider billed (message_start's usage: 1024 in, 4096 cache write, 1 out).
    before = remaining(a.user_id)
    fake.sse("window/01-find.sse", cut_after=6)
    cut = send(client, dev(a), first_turn())
    assert cut.status_code == 200
    seen = names(cut.content)
    assert seen[-2:] == ["truebex_credits", "error"] and "message_stop" not in seen
    assert data_of(cut.content, "error")[0]["code"] == "upstream_failed"
    assert data_of(cut.content, "truebex_credits")[0]["charged"] == 25 and remaining(a.user_id) == before - 25
    # An upstream error event after output began: in-band, mapped.
    events = events_of(fixture_bytes("window/01-find.sse"))[:4]
    fake.sse(b"".join(events) + b'event: error\ndata: {"type":"error","error":{"type":"overloaded_error","message":"x"}}\n\n')
    mid = send(client, dev(a), first_turn())
    assert data_of(mid.content, "error")[0]["code"] == "upstream_busy"


def test_no_content_retained(client, fake):
    a = studio_person(client)
    fake.sse("window/01-find.sse")
    first = send(client, dev(a), first_turn())
    fake.sse("window/02-place.sse")
    send(client, dev(a), body(_window_history(first.content)))
    secrets_ = [USER_TEXT, SYSTEM, "Study", "facing", "matches", "width_mm", "north wall", "FixtureSignature", "Find entities"]
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            for row in conn.execute(select(table)).all():
                dumped = json.dumps([str(v) for v in row])
                for s in secrets_:
                    assert s not in dumped, f"{table.name} holds {s!r}"
    with SessionLocal() as db:
        assert {tuple(u.tool_names) for u in db.scalars(select(AiUsage))} == {("find",), ("place",)}


def test_alias_mapping_server_side(client, fake, tmp_path, monkeypatch):
    from app.ai import aliases

    table = tmp_path / "aliases.json"
    shutil.copy(aliases.DEFAULT_PATH, table)
    monkeypatch.setattr(get_settings(), "ai_aliases_path", str(table))
    a = studio_person(client)
    reply = {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": "Hello"}], "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 1000, "output_tokens": 100, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
    }
    fake.message(reply)
    res = send(client, dev(a), first_turn(stream=False, max_tokens=1024))
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["model"] == "truebex-assist" and out["served_by"] == {"provider": "anthropic", "model": "claude-opus-5-5"}
    assert out["credits"]["charged"] == 6 and out["content"] == reply["content"] and out["stop_details"] is None
    # The owner moves the alias to another model: no client change.
    raw = json.loads(table.read_text("utf-8"))
    raw["aliases"]["truebex-assist"]["model"] = "claude-opus-5"
    table.write_text(json.dumps(raw), "utf-8")
    later = time.time() + 5
    os.utime(table, (later, later))
    fake.message({**reply, "model": "claude-opus-5"})
    out2 = send(client, dev(a), first_turn(stream=False, max_tokens=1024)).json()
    assert fake.of_path("/v1/messages")[-1].json()["model"] == "claude-opus-5"
    assert out2["served_by"] == {"provider": "anthropic", "model": "claude-opus-5"}
    # Charged at that model's own rates (5000 / 25000): 5 + 2.5 -> 8.
    assert out2["credits"]["charged"] == 8


def test_contract_header_and_error_envelope(client, fake):
    a = studio_person(client)
    fake.sse("window/03-end.sse")
    ok = send(client, dev(a), first_turn())
    assert ok.headers["X-Truebex-Contract"] == "ai-proxy/1.1"
    whole = client.get("/ai/models", headers=dev(a))
    assert whole.headers["X-Truebex-Contract"] == "ai-proxy/1.1"
    bad = send(client, {**dev(a), "X-Truebex-Contract": "ai-proxy/2.0"}, first_turn())
    err = error_of(bad, 400, "contract_version")
    assert err["data"]["supported"] == ["ai-proxy/1.1"] and bad.headers["X-Truebex-Contract"] == "ai-proxy/1.1"
    # Unknown alias, a body that is not JSON, a body over 8 MB.
    error_of(send(client, dev(a), first_turn(model="claude-opus-5-5")), 422, "validation_failed")
    error_of(send(client, dev(a), b"{not json"), 422, "validation_failed")
    error_of(send(client, dev(a), b" " * (8 * 1024 * 1024 + 1)), 413, "too_large")
    error_of(send(client, dev(a), first_turn(stream=False, max_tokens=8192)), 422, "validation_failed")
    error_of(send(client, dev(a), first_turn(max_tokens=64_001)), 422, "validation_failed")
    error_of(send(client, dev(a), first_turn(), idem="short"), 422, "validation_failed")
    # In-band errors carry the same envelope, with the response's request id.
    fake.sse("window/01-find.sse", cut_after=3)
    cut = send(client, dev(a), first_turn())
    env = data_of(cut.content, "error")[0]
    assert set(env) == {"detail", "code", "status", "request_id", "retry_after_s", "data"}
    assert env["status"] == 502 and env["request_id"] == cut.headers["X-Request-Id"] and isinstance(env["detail"], str)


# --- 5.1, 5.2, 5.4 ---------------------------------------------------------------------------------


def test_ai_models_balance_and_count(client, fake):
    a = studio_person(client)
    models = client.get("/ai/models", headers=dev(a)).json()
    # The app's models.json (AI3) without the stub's truebex-fast (not served before GD7).
    stub = json.loads(contract_bytes("models.json"))
    assert models == {"default": stub["default"], "models": [m for m in stub["models"] if m["alias"] == "truebex-assist"]}
    free = Person(client, "free@example.com", trial=False)
    assert client.get("/ai/models", headers=dev(free)).json() == {"default": None, "models": []}
    bal = client.get("/ai/balance", headers=dev(a)).json()
    assert bal["allowance_monthly"] == 5000 and bal["credits_remaining"] == 5000 and bal["top_up_remaining"] == 0
    assert bal["plan"] == "studio" and bal["top_up_url"].endswith("/dashboard/cloud/#ai-credits")
    assert set(json.loads(contract_bytes("balance-studio.json"))) <= set(bal)
    start, nxt = credits.quotas.month_bounds()
    assert bal["resets_at"] == f"{nxt.isoformat()}T00:00:00Z"
    assert client.get("/ai/balance", headers=dev(free)).json()["allowance_monthly"] == 0
    fake.input_tokens = 5120
    res = client.post("/ai/messages/count", json=first_turn(), headers=dev(a))
    assert res.status_code == 200, res.text
    # input plus max_tokens at the output rate: (5120 × 4000 + 8192 × 20000) / 10⁶ -> 185
    assert res.json() == {"input_tokens": 5120, "max_credits": 185}
    sent = fake.of_path("/v1/messages/count_tokens")[-1].json()
    assert sent["model"] == "claude-opus-5-5" and "max_tokens" not in sent and "stream" not in sent and "fallbacks" not in sent
    for path in ("/ai/models", "/ai/balance"):
        error_of(client.get(path, headers=AI), 401, "unauthenticated")
    error_of(client.post("/ai/messages/count", json=first_turn(), headers=AI), 401, "unauthenticated")
    error_of(client.post("/ai/messages/count", json=first_turn(), headers=dev(free)), 403, "plan_required")
    error_of(client.post("/ai/messages/count", json=first_turn(model="nope"), headers=dev(a)), 422, "validation_failed")


def test_ai_duplicate_request_and_rate_limits(client, fake, monkeypatch):
    a = studio_person(client)
    idem = key()
    fake.sse("window/03-end.sse")
    assert send(client, dev(a), first_turn(), idem).status_code == 200
    error_of(send(client, dev(a), first_turn(), idem), 409, "duplicate_request")
    # After 10 minutes the key may be used again.
    real = clock.now
    monkeypatch.setattr(clock, "now", lambda: real() + timedelta(minutes=11))
    fake.sse("window/03-end.sse")
    assert send(client, dev(a), first_turn(), idem).status_code == 200
    monkeypatch.setattr(clock, "now", real)
    # Two turns in flight: a third is refused.
    with SessionLocal() as db:
        for t in ("a" * 32, "b" * 32):
            db.add(AiTurn(turn_id=t, account_id=a.user_id, started_at=clock.now()))
        db.commit()
    err = error_of(send(client, dev(a), first_turn()), 429, "rate_limited")
    assert err["retry_after_s"] >= 1
    with SessionLocal() as db:
        db.execute(text("DELETE FROM ai_turns"))
        db.commit()
    # 60 a minute per account (2 here).
    monkeypatch.setattr(proxy, "PER_MINUTE", 2)
    from app import ratelimit

    ratelimit.reset()
    for _ in range(2):
        fake.sse("window/03-end.sse")
        assert send(client, dev(a), first_turn()).status_code == 200
    error_of(send(client, dev(a), first_turn()), 429, "rate_limited")
    # In-flight rows are cleared when turns end.
    with SessionLocal() as db:
        assert db.scalars(select(AiTurn)).all() == []
