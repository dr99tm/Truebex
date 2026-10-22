"""Shared helpers for the AI proxy tests (PF11, contract ai-proxy)."""

import json
import secrets

import pytest

from app.ai import aliases, credits
from app.config import get_settings
from app.database import SessionLocal
from app.models import User

from .fakes.fake_provider import FakeProvider, event_name, events_of
from .project_helpers import Person
from .render_helpers import studio

AI = {"X-Truebex-Contract": "ai-proxy/1.1"}
USER_TEXT = "Put a window on the north wall of the study, 1.2 m wide"
SESSION_ID = "5e55100000000000000000000000a001"
WALL = "0199c6a2e00070018000000000000001"
TOOLS = [
    {
        "name": "find",
        "description": "Find entities by kind, room and facing.",
        "input_schema": {"type": "object", "properties": {"kind": {"type": "string"}, "room": {"type": "string"}, "facing": {"type": "string"}}},
    },
    {
        "name": "place",
        "description": "Place an object on a host.",
        "input_schema": {"type": "object", "properties": {"kind": {"type": "string"}, "host": {"type": "string"}, "width_mm": {"type": "integer"}}},
    },
]
SYSTEM = "You are the Truebex assistant. Use the tools to change the model."


@pytest.fixture()
def fake(client, monkeypatch):
    """The fake provider as the Anthropic upstream (and inference server)."""
    provider = FakeProvider().start()
    settings = get_settings()
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-key")
    monkeypatch.setattr(settings, "anthropic_base_url", provider.base_url)
    aliases.reset()
    try:
        yield provider
    finally:
        provider.stop()
        aliases.reset()


def dev(person: Person) -> dict:
    return {"Authorization": f"Bearer {person.token}", **AI}


def key() -> str:
    return secrets.token_hex(16)


def studio_person(client, email: str = "ai@example.com") -> Person:
    """A Studio designer with a device (Studio: 5000 credits a month, placeholder)."""
    p = Person(client, email, trial=False)
    studio(p.user_id)
    return p


def set_remaining(user_id: int, target: int) -> None:
    """Move the account's allowance so `target` credits remain."""
    with SessionLocal() as db:
        user = db.get(User, user_id)
        row = credits.ensure(db, user)
        delta = target - credits.remaining(row)
        if delta:
            credits.adjust(db, user, delta, f"test:{secrets.token_hex(4)}")
        db.commit()


def remaining(user_id: int) -> int:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        row = credits.ensure(db, user)
        db.commit()
        return credits.remaining(row)


def body(messages: list, **kw) -> dict:
    out = {
        "model": "truebex-assist",
        "max_tokens": 8192,
        "stream": True,
        "system": SYSTEM,
        "tools": TOOLS,
        "tool_choice": {"type": "auto"},
        "metadata": {"session_id": SESSION_ID, "app_version": "1.3.0"},
        "messages": messages,
    }
    out.update(kw)
    return out


def first_turn(**kw) -> dict:
    return body([{"role": "user", "content": [{"type": "text", "text": USER_TEXT}]}], **kw)


def send(client, headers: dict, payload: dict | bytes, idem: str | None = None):
    h = {**headers, "Content-Type": "application/json"}
    if idem is not False:
        h["Idempotency-Key"] = idem or key()
    data = payload if isinstance(payload, bytes) else json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    return client.post("/ai/messages", content=data, headers=h)


def assemble(sse: bytes) -> list[dict]:
    """The assistant message's content as the app builds it from the stream."""
    blocks: dict[int, dict] = {}
    partial: dict[int, str] = {}
    for raw in events_of(sse):
        name = event_name(raw)
        data_line = next((ln for ln in raw.split(b"\n") if ln.startswith(b"data:")), b"data: {}")
        data = json.loads(data_line[5:])
        if name == "content_block_start":
            blocks[data["index"]] = dict(data["content_block"])
        elif name == "content_block_delta":
            d = data["delta"]
            b = blocks[data["index"]]
            if d["type"] == "text_delta":
                b["text"] += d["text"]
            elif d["type"] == "signature_delta":
                b["signature"] = d["signature"]
            elif d["type"] == "thinking_delta":
                b["thinking"] += d["thinking"]
            elif d["type"] == "input_json_delta":
                partial[data["index"]] = partial.get(data["index"], "") + d["partial_json"]
    for i, text in partial.items():
        blocks[i]["input"] = json.loads(text) if text else {}
    return [blocks[i] for i in sorted(blocks)]


def names(sse: bytes) -> list[str | None]:
    return [event_name(e) for e in events_of(sse)]


def data_of(sse: bytes, name: str) -> list[dict]:
    out = []
    for raw in events_of(sse):
        if event_name(raw) == name:
            line = next(ln for ln in raw.split(b"\n") if ln.startswith(b"data:"))
            out.append(json.loads(line[5:]))
    return out
