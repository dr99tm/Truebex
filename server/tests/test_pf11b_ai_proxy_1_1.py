"""PF11b: the AI proxy follows contract ai-proxy 1.1.2 (AI3, 2026-10-21; AI5's
create script, 1.1.1; AI7's tool-less turns, 1.1.2; both 2026-10-22).

* tests/contracts/ai-proxy/ is the app's folder, byte for byte: app commit
  a3fd173a0 (T183, the folder's last commit; app main 7fdde1e6f when copied),
  pinned by its blob ids and its git tree id. PF11's own window turns (cache
  tokens, the proxy's whole stream) moved to tests/fixtures/ai/.
* The proxy plays the app's four scripted conversations (window, paint, echo,
  create) and its streamed refusal through POST /ai/messages, with the fake
  provider serving each `.sse` file as the stub does (tests/fakes/
  fake_provider.py: `${wall}` and `${room}` filled from the capture of the
  tool_result the proxy forwarded; the file's truebex_credits dropped).
* The files' truebex_credits are the stub's (window 21, 16, 9; paint 24, 19,
  11; echo 2; create 38, 12; refusal 3); the proxy charges §6.2 from each
  turn's usage at truebex-assist's rates (window 22, 23, 24; paint 21, 23, 23;
  echo 4; create 26, 29; refusal 6) and says what the ledger holds after it.
* 5.2 answers 1.1.0's `usage_url`: <site>/dashboard/cloud/#ai-usage, the
  Recent turns panel of the Cloud page (the stub's /dashboard/usage/ is the
  site's page of API requests). `top_up_url` stays where packs are bought.
* 1.1.2: a tool-less turn (AI7's run summaries: no tools, no tool_choice) is
  served, streamed or not, and the provider gets neither; a tool_choice
  without tools is 422 `validation_failed` on `tool_choice`.
* Every /ai route answers `X-Truebex-Contract: ai-proxy/1.1`; 1.0 is served.

Masked against the app's error envelopes: `detail` (each side's words) and
`request_id` (minted per request); the rest is compared, `data` by its keys
(the platform's extra keys are named per case; null and {} both carry none).
"""

import hashlib
import json
import re
import secrets
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.ai import adapters, credits, proxy
from app.ai.models import AiTurn, AiUsage
from app.config import get_settings
from app.database import SessionLocal
from app.licence import clock
from app.main import app

from .ai_helpers import assemble, data_of, fake, names, remaining, send, set_remaining, studio_person  # noqa: F401
from .fakes.fake_provider import CONTRACT_FIXTURES, OWN_FIXTURES, contract_bytes, events_of, script_of, without_credits
from .project_helpers import Person

ROOT = Path(__file__).resolve().parents[2]
WIRE = "ai-proxy/1.1"
# The app's folder as copied: the folder's last commit on the app's main
# (T183, contract 1.1.1; 1.1.2 moved no fixture), app main when copied, the
# git tree id of Docs/roadmap/fixtures/contracts/ai-proxy/ at that commit and
# the blob of each file (`git ls-tree -r`). README.md is the platform's own.
APP_REPO = Path(r"T:\unreal5_7_4_projects\truebex_compact")
APP_COMMIT = "a3fd173a076a40dbf90246b713765eecc4e83417"
APP_MAIN = "7fdde1e6f7085b7fa2f5d4f991136ca62835afd1"
APP_TREE = "907992a926585ba8b9fd06b1ba7315fdc090a6cb"
APP_DIR = "Docs/roadmap/fixtures/contracts/ai-proxy"
APP_BLOBS = {
    "balance-empty.json": "ac9c89cdcab70555a7c9002a7a7a39cb29b729cb",
    "balance-low.json": "8c74fb2b0162b4966f0c6f2a9776844cab7264f5",
    "balance-studio.json": "05b32dfec429215e8bcd571413dc9472277be5e4",
    "count.json": "118ed5b92dbf597627d48d04ba96ae6d25ad9763",
    "create/01-layout.sse": "3bfa05afa3884aa9140f4651d49d4af90f5e3f86",
    "create/02-end.sse": "15252faf50e3457fa9fdf96e49c0034b1a2db977",
    "create/script.json": "42bef8f64a4745eaa4596eca260b60da543f0bec",
    "credits-exhausted.json": "9e23f1601191b4e4e0dfda07e01d8200af08d384",
    "echo/01-end.sse": "6ed6ea94dad54ee983dda17cdc76512b48009a8a",
    "echo/script.json": "7202f80e7d7b935c59fd2540c4a7bb97eb30de32",
    "models.json": "a07a371c5cab492d2bf4a3e9449cf590d7353ff1",
    "paint/01-find.sse": "b28ab860f0a90e6cc2cfa701a53a783773bc05a8",
    "paint/02-fill.sse": "7f560c11b94708e67bb0072d71f334a334f76dba",
    "paint/03-end.sse": "c2ae79f39044568bb902925f2351a1ac75d86365",
    "paint/script.json": "474819fbf24031f3ef57c12299982d003278830d",
    "plan-required.json": "9040fdbc3996753396e424ad6976964e7ad8eb7e",
    "rate-limited.json": "395ad7d2d6d70a03955129b68438b893c16ca6c1",
    "refusal.sse": "84652e4e343a0c15aef01648c9b3e245a7a0659e",
    "server-error.json": "16f26fabc4ed2605952173575a9963661b8633a6",
    "too-large.json": "efc2ebb8807fe858916d077c4e6a0acdc034b81b",
    "unauthenticated.json": "b7248d2285609ee643f81d2c533207dbe89a2fc4",
    "upstream-busy.json": "e378565d0fb95354378aa9ade14e3e69cd15a556",
    "window/01-find.sse": "7dc4c39bd016d109f658aca95a030bb301110eb4",
    "window/02-place.sse": "3b74ef186297b06e08b93e25aa914937cb651658",
    "window/03-end.sse": "b542210b4b36d4981916e43fa93f62e552626ffe",
    "window/script.json": "a4109080e256acba86559c11998718d3d978839b",
}
# PF11's own set, kept where a test still reads it.
STAND_INS = {"README.md", "window/01-find.sse", "window/02-place.sse", "window/03-end.sse"}

RATES = {"input": 4000, "output": 20000, "cache_read": 400, "cache_write": 5000}  # truebex-assist (5.1)
# §6.2 at truebex-assist's rates for each turn's usage, and what the files' own
# truebex_credits say (the stub's ledger).
CHARGED = {"window": [22, 23, 24], "paint": [21, 23, 23], "echo": [4], "create": [26, 29], "refusal": [6]}
STUB_CHARGED = {"window": [21, 16, 9], "paint": [24, 19, 11], "echo": [2], "create": [38, 12], "refusal": [3]}

WALL = "0199c6a2e00070018000000000000001"
ROOM = "0199c6a2e00070018000000000000a01"
WINDOW = "0199c6a2e00070018000000000000b01"
CANDIDATE = "0199c6a2e00070018000000000000c01"
SYSTEM = "You are the Truebex assistant. Use the tools to change the model."
TOOLS = [
    {
        "name": "find",
        "description": "Find entities by kind, name, room and facing.",
        "input_schema": {"type": "object", "properties": {"kind": {"type": "string"}, "name": {"type": "string"}, "room": {"type": "string"}, "facing": {"type": "string"}}},
    },
    {
        "name": "place",
        "description": "Place an object on a host.",
        "input_schema": {"type": "object", "properties": {"kind": {"type": "string"}, "host": {"type": "string"}, "width_mm": {"type": "integer"}}},
    },
    {
        "name": "fill",
        "description": "Give an entity's faces a finish.",
        "input_schema": {"type": "object", "properties": {"target": {"type": "string"}, "face": {"type": "string"}, "finish": {"type": "object"}}},
    },
    {
        "name": "create_layout",
        "description": "List candidate layouts of a room program on a plot.",
        "input_schema": {"type": "object", "properties": {"plot": {"type": "string"}, "seed": {"type": "integer"}, "limits": {"type": "string"}, "program": {"type": "object"}}},
    },
]
# Each script: the person's words, the results of its tool calls (one per
# turn that calls one), the placeholders as the fake fills them, and per turn
# the tools called and the stop reason.
CONVERSATIONS = {
    "window": (
        "Put a window on the north wall of the study, 1.2 m wide",
        [{"matches": [{"ref": WALL, "kind": "wall", "room": "Study", "facing": "n"}]}, {"placed": True, "ref": WINDOW}],
        {"wall": WALL},
        [["find"], ["place"], []],
        ["tool_use", "tool_use", "end_turn"],
    ),
    "paint": (
        "Paint the study walls white",
        [{"matches": [{"ref": ROOM, "kind": "room", "name": "Study"}]}, {"filled": 4, "target": ROOM}],
        {"room": ROOM},
        [["find"], ["fill"], []],
        ["tool_use", "tool_use", "end_turn"],
    ),
    "echo": ("Thanks, that is all for now", [], {}, [[]], ["end_turn"]),
    "create": (
        "Create a two-bedroom flat on this plot",
        [{"candidates": [{"id": CANDIDATE, "rank": 1, "rooms": 6, "area_m2": 66}]}],
        {},
        [["create_layout"], []],
        ["tool_use", "end_turn"],
    ),
}
ENVELOPE = {"detail", "code", "status", "request_id", "retry_after_s", "data"}
HEX32 = re.compile(r"^[0-9a-f]{32}$")


def compact(obj) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()


def headers(person: Person, contract: str | None = WIRE) -> dict:
    out = {"Authorization": f"Bearer {person.token}"}
    if contract:
        out["X-Truebex-Contract"] = contract
    return out


def turn_body(messages: list, session: str, **kw) -> dict:
    out = {
        "model": "truebex-assist",
        "max_tokens": 8192,
        "stream": True,
        "system": SYSTEM,
        "tools": TOOLS,
        "tool_choice": {"type": "auto"},
        "metadata": {"session_id": session, "app_version": "1.3.0"},
        "messages": messages,
    }
    out.update(kw)
    return out


def tool_result(tool_use_id: str, result: dict) -> dict:
    return {"type": "tool_result", "tool_use_id": tool_use_id, "is_error": False, "content": [{"type": "text", "text": json.dumps(result)}]}


def usage_of(sse: bytes) -> dict:
    """The usage a turn's stream reports (message_start's, then message_delta's)."""
    usage: dict = {}
    for name in ("message_start", "message_delta"):
        for data in data_of(without_credits(sse), name):
            usage.update((data.get("message") or data).get("usage") or {})
    return usage


def stub_charged(sse: bytes) -> int:
    return int(re.search(rb'event: truebex_credits\ndata: \{"charged":(\d+)', sse).group(1))


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _tree(entries: dict) -> str:
    """A git tree id: names map to blob ids (files) or to dicts (folders)."""
    rows = []
    for name, value in entries.items():
        raw = name.encode("utf-8")
        if isinstance(value, dict):
            rows.append((raw + b"/", b"40000 " + raw + b"\0" + bytes.fromhex(_tree(value))))
        else:
            rows.append((raw, b"100644 " + raw + b"\0" + bytes.fromhex(value)))
    body = b"".join(row for _, row in sorted(rows))
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def tree_of_listing(blobs: dict[str, str]) -> str:
    root: dict = {}
    for path, blob in blobs.items():
        node = root
        *dirs, name = path.split("/")
        for d in dirs:
            node = node.setdefault(d, {})
        node[name] = blob
    return _tree(root)


def folder_files(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


# --- the copy ------------------------------------------------------------------------------------


def test_pf11b_contract_folder_is_the_apps_at_the_recorded_commit():
    """tests/contracts/ai-proxy/ holds the app's 26 files at a3fd173a0 and this
    folder's README, each the app's blob byte for byte (LF, as committed): the
    blob ids and the folder's git tree id. Where the app repo is present, git
    agrees with the recorded listing."""
    files = folder_files(CONTRACT_FIXTURES)
    assert set(files) == set(APP_BLOBS) | {"README.md"}
    for name, blob in APP_BLOBS.items():
        assert git_blob_id(files[name]) == blob, name
        assert b"\r" not in files[name], name
    assert tree_of_listing({n: git_blob_id(d) for n, d in files.items() if n != "README.md"}) == APP_TREE
    assert tree_of_listing(APP_BLOBS) == APP_TREE and len(APP_BLOBS) == 26
    readme = files["README.md"].decode("utf-8")
    assert APP_COMMIT[:9] in readme and APP_MAIN[:9] in readme and APP_TREE[:9] in readme and "1.1.2" in readme
    for name in ("models.json", "count.json", "refusal.sse", "script.json", "window/", "paint/", "echo/", "create/"):
        assert f"`{name}" in readme, name
    if not (APP_REPO / ".git").exists():
        return
    out = subprocess.run(["git", "ls-tree", "-r", APP_COMMIT, "--", f"{APP_DIR}/"], cwd=APP_REPO, capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        pytest.skip(f"git ls-tree failed: {out.stderr.strip()}")
    listed = {}
    for line in out.stdout.splitlines():
        meta, path = line.split("\t", 1)
        listed[path[len(APP_DIR) + 1 :]] = meta.split()[2]
    assert listed == APP_BLOBS
    tree = subprocess.run(["git", "rev-parse", f"{APP_COMMIT}:{APP_DIR}"], cwd=APP_REPO, capture_output=True, text=True, timeout=60)
    assert tree.stdout.strip() == APP_TREE


def test_pf11b_pf11s_own_turns_live_in_fixtures_ai():
    """PF11's three window turns (cache read and write tokens in their usage,
    the proxy's whole stream with served_by) stay the platform's own for §6.2's
    cache arithmetic and the byte-for-byte stream checks of test_ai_proxy.py;
    make_ai_proxy_fixtures.py writes them there and nowhere else."""
    files = folder_files(OWN_FIXTURES)
    assert set(files) == STAND_INS
    assert usage_of(files["window/01-find.sse"])["cache_creation_input_tokens"] == 4096
    assert usage_of(files["window/02-place.sse"])["cache_read_input_tokens"] == 5120
    readme = files["README.md"].decode("utf-8")
    assert "../../contracts/ai-proxy/" in readme and "make_ai_proxy_fixtures.py" in readme
    for name in sorted(STAND_INS - {"README.md"}):
        assert f"`{name}`" in readme, name
    script = ROOT / "server" / "scripts" / "make_ai_proxy_fixtures.py"
    res = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stdout + res.stderr
    text = script.read_text(encoding="utf-8")
    assert '"contracts" / "ai-proxy"' not in text and '"fixtures" / "ai"' in text


# --- the four scripted conversations, the refusal ---------------------------------------------------


@pytest.mark.parametrize("script", ["window", "paint", "echo", "create"])
def test_pf11b_scripted_conversation_through_the_proxy(client, fake, script):
    """One conversation (one metadata.session_id) through POST /ai/messages,
    streamed, the fake provider answering as the app's stub: each turn reaches
    the client byte-equal to its .sse file outside truebex_credits (with the
    placeholders as the fake fills them); the proxy's truebex_credits comes
    just before message_stop, charged by §6.2 from that turn's usage, with
    what the ledger holds after it; every tool_result and the history reach the
    provider byte-equal (§10 test_tool_use_passthrough)."""
    text, results, fills, tools_called, stops = CONVERSATIONS[script]
    turns = script_of(script)["turns"]
    a = studio_person(client)
    set_remaining(a.user_id, 4388)
    ledger = 4388
    session = secrets.token_hex(16)
    messages = [{"role": "user", "content": [{"type": "text", "text": text}]}]
    fake.script(turns=len(turns))  # the stub's own pick, by the person's words
    for i, turn in enumerate(turns):
        res = send(client, headers(a), turn_body(messages, session))
        assert res.status_code == 200, res.text
        assert res.headers["X-Truebex-Contract"] == WIRE
        raw = contract_bytes(f"{script}/{turn['sse']}")
        assert credits.charge_for(usage_of(raw), RATES) == CHARGED[script][i]
        assert stub_charged(raw) == STUB_CHARGED[script][i]
        expected = raw
        for name, value in fills.items():
            expected = expected.replace(f"${{{name}}}".encode(), value.encode())
        expected = without_credits(expected)
        assert b"${" not in expected
        # Byte-equal outside the proxy's own event, which sits before message_stop.
        assert without_credits(res.content) == expected
        assert names(res.content)[-2:] == ["truebex_credits", "message_stop"]
        assert names(res.content).count("truebex_credits") == 1
        ledger -= CHARGED[script][i]
        assert data_of(res.content, "truebex_credits") == [
            {"charged": CHARGED[script][i], "remaining": ledger, "served_by": {"provider": "anthropic", "model": "truebex-assist"}}
        ]
        assert remaining(a.user_id) == ledger
        served = fake.served[-1]
        assert (served.script, served.turn, served.file, served.data) == (script, i, f"{script}/{turn['sse']}", expected)
        sent = fake.of_path("/v1/messages")[-1]
        upstream = sent.json()
        assert upstream["messages"] == messages and "metadata" not in upstream and session.encode() not in sent.body
        assert [t["name"] for t in upstream["tools"]] == [t["name"] for t in TOOLS] and upstream["tool_choice"] == {"type": "auto"}
        for message in messages[1:]:  # the history and every tool_result, byte for byte
            for block in message["content"]:
                assert compact(block) in sent.body, block
        content = assemble(res.content)
        calls = [b for b in content if b["type"] == "tool_use"]
        assert [b["name"] for b in calls] == tools_called[i]
        assert content[0]["type"] == "thinking" and content[0]["signature"].startswith("EqQB")
        messages.append({"role": "assistant", "content": content})
        if calls:
            messages.append({"role": "user", "content": [tool_result(b["id"], results[i]) for b in calls]})
    assert len(fake.of_path("/v1/messages")) == len(turns)
    if script == "window":
        assert messages[3]["content"][-1]["input"] == {"kind": "window", "host": WALL, "width_mm": 1200}
    if script == "paint":
        assert messages[3]["content"][-1]["input"]["target"] == ROOM
    if script == "create":
        assert messages[1]["content"][-1]["input"]["program"]["rooms"][3]["type"] == "bedroom"
    with SessionLocal() as db:
        rows = db.scalars(select(AiUsage).where(AiUsage.session_id == session).order_by(AiUsage.id)).all()
    assert [r.credits for r in rows] == CHARGED[script]
    assert [list(r.tool_names) for r in rows] == tools_called and [r.stop_reason for r in rows] == stops
    assert {(r.alias, r.served_by, r.provider_model, r.outcome, r.stream) for r in rows} == {
        ("truebex-assist", "anthropic", "truebex-assist", "ok", True)
    }


def test_pf11b_streamed_refusal(client, fake):
    """refusal.sse streams through with stop_reason refusal, is charged 6 by
    §6.2 (the file says 3) and the turn is recorded."""
    a = studio_person(client)
    set_remaining(a.user_id, 4388)
    raw = contract_bytes("refusal.sse")
    assert credits.charge_for(usage_of(raw), RATES) == 6 and stub_charged(raw) == 3
    fake.sse(raw)
    session = secrets.token_hex(16)
    res = send(client, headers(a), turn_body([{"role": "user", "content": [{"type": "text", "text": "Something it declines"}]}], session))
    assert res.status_code == 200, res.text
    assert without_credits(res.content) == without_credits(raw)
    assert data_of(res.content, "message_delta")[0]["delta"]["stop_reason"] == "refusal"
    assert names(res.content)[-2:] == ["truebex_credits", "message_stop"]
    assert data_of(res.content, "truebex_credits")[0] == {
        "charged": 6, "remaining": 4382, "served_by": {"provider": "anthropic", "model": "truebex-assist"}
    }
    assert remaining(a.user_id) == 4382
    with SessionLocal() as db:
        row = db.scalars(select(AiUsage).where(AiUsage.session_id == session)).one()
    assert (row.stop_reason, row.credits, row.input_tokens, row.output_tokens, row.outcome, list(row.tool_names)) == (
        "refusal", 6, 1200, 12, "ok", []
    )


# --- 1.1.2: tool-less turns ---------------------------------------------------------------------------


def test_pf11b_tool_less_turn_served(client, fake):
    """AI7's run summaries: one turn, no tools and no tool_choice, answered 200
    and charged 4 by §6.2 for echo/01-end.sse; the provider gets neither key.
    Streamed and whole. (Served on d222f29 already: this is the guard.)"""
    a = studio_person(client)
    set_remaining(a.user_id, 1000)
    summary = {
        "model": "truebex-assist",
        "max_tokens": 1024,
        "stream": True,
        "system": "Summarise this unattended run for the person who started it.",
        "metadata": {"session_id": secrets.token_hex(16), "app_version": "1.3.0"},
        "messages": [{"role": "user", "content": [{"type": "text", "text": "Run 12: 3 checks passed, 1 warning."}]}],
    }
    fake.script("echo")
    res = send(client, headers(a), summary)
    assert res.status_code == 200, res.text
    assert without_credits(res.content) == without_credits(contract_bytes("echo/01-end.sse"))
    assert data_of(res.content, "truebex_credits")[0]["charged"] == 4 and remaining(a.user_id) == 996
    sent = fake.of_path("/v1/messages")[-1].json()
    assert "tools" not in sent and "tool_choice" not in sent and sent["stream"] is True
    fake.message({
        "id": "msg_summary", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": "Noted."}], "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 900, "output_tokens": 4, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
    })
    whole = send(client, headers(a), {**summary, "stream": False})
    assert whole.status_code == 200, whole.text
    assert whole.json()["credits"] == {"charged": 4, "remaining": 992} and whole.json()["stop_reason"] == "end_turn"
    sent = fake.of_path("/v1/messages")[-1].json()
    assert "tools" not in sent and "tool_choice" not in sent and "stream" not in sent


def test_pf11b_tool_choice_without_tools_refused(client, fake):
    """1.1.2: a request without tools may not carry tool_choice: 422
    `validation_failed` on `tool_choice` (5.3 and 5.4), nothing forwarded."""
    a = studio_person(client)
    base = turn_body([{"role": "user", "content": [{"type": "text", "text": "Summarise run 12."}]}], secrets.token_hex(16))
    for choice in ({"type": "auto"}, {"type": "none"}):
        for tools in (None, []):
            payload = {k: v for k, v in base.items() if k != "tools"}
            payload["tool_choice"] = choice
            if tools is not None:
                payload["tools"] = tools
            res = send(client, headers(a), payload)
            assert res.status_code == 422, res.text
            err = res.json()
            assert err["code"] == "validation_failed" and err["data"]["fields"][0]["field"] == "tool_choice"
            count = client.post("/ai/messages/count", json=payload, headers=headers(a))
            assert count.status_code == 422 and count.json()["data"]["fields"][0]["field"] == "tool_choice"
    assert fake.of_path("/v1/messages") == [] and fake.of_path("/v1/messages/count_tokens") == []
    assert remaining(a.user_id) == 5000


# --- 5.1, 5.2, 5.4 ----------------------------------------------------------------------------------------


def _shape(obj: dict) -> dict:
    return {k: type(v) for k, v in obj.items()}


def test_pf11b_balance_has_the_apps_keys_and_types(client):
    """5.2 for a Studio, a low and an empty account: the keys and types of
    balance-studio.json, balance-low.json and balance-empty.json, with the
    platform's own usage_url and top_up_url; the values from its ledger."""
    site = get_settings().site_url.rstrip("/")
    for i, (name, left) in enumerate((("balance-studio.json", 4388), ("balance-low.json", 412), ("balance-empty.json", 0))):
        stub = json.loads(contract_bytes(name))
        assert stub["credits_remaining"] == left
        a = studio_person(client, f"ai{i}@example.com")
        set_remaining(a.user_id, left)
        res = client.get("/ai/balance", headers=headers(a))
        assert res.status_code == 200 and res.headers["X-Truebex-Contract"] == WIRE
        ours = res.json()
        assert set(stub) <= set(ours) and set(ours) - set(stub) == {"allowance_remaining"}, name
        assert {k: _shape(ours)[k] for k in stub} == _shape(stub), name
        assert ours["credits_remaining"] == left == remaining(a.user_id)
        assert (ours["allowance_monthly"], ours["top_up_remaining"], ours["plan"]) == (5000, 0, "studio")
        assert re.fullmatch(r"\d{4}-\d{2}-01T00:00:00Z", ours["resets_at"]) and ours["resets_at"] > clock.rfc3339(clock.now())
        assert ours["usage_url"] == f"{site}/dashboard/cloud/#ai-usage"
        assert ours["top_up_url"] == f"{site}/dashboard/cloud/#ai-credits"


def test_pf11b_models_and_count_have_the_apps_shapes(client, fake):
    """5.1 has models.json's keys and types per model (truebex-assist's entry
    equal; truebex-fast is the stub's alias, not served before GD7); 5.4 has
    count.json's keys and types."""
    a = studio_person(client)
    stub = json.loads(contract_bytes("models.json"))
    ours = client.get("/ai/models", headers=headers(a)).json()
    assert set(ours) == set(stub) and ours["default"] == stub["default"]
    proto = stub["models"][0]
    for m in [*stub["models"], *ours["models"]]:
        assert _shape(m) == _shape(proto), m["alias"]
        assert _shape(m["credits_per_mtok"]) == _shape(proto["credits_per_mtok"]), m["alias"]
    by_alias = {m["alias"]: m for m in stub["models"]}
    assert set(by_alias) == {"truebex-assist", "truebex-fast"}
    assert ours["models"] == [by_alias["truebex-assist"]]
    count = client.post(
        "/ai/messages/count", json=turn_body([{"role": "user", "content": "Put a window on the north wall"}], secrets.token_hex(16)),
        headers=headers(a),
    )
    assert count.status_code == 200, count.text
    assert _shape(count.json()) == _shape(json.loads(contract_bytes("count.json")))
    assert count.json()["input_tokens"] == 5120


# --- §7: the app's error envelopes ------------------------------------------------------------------------


def _matches(name: str, res, extra: set[str] = frozenset()) -> dict:
    """The platform's answer to a case against the app's file: code, status,
    the envelope's keys and data's keys; detail and request_id masked."""
    stub = json.loads(contract_bytes(name))
    ours = res.json()
    assert res.status_code == stub["status"], (name, res.text)
    assert set(ours) == set(stub) == ENVELOPE, name
    assert (ours["code"], ours["status"]) == (stub["code"], stub["status"]), name
    assert set(stub["data"]) <= set(ours["data"] or {}), name
    assert set(ours["data"] or {}) - set(stub["data"]) == set(extra), name
    assert (ours["retry_after_s"] is None) == (stub["retry_after_s"] is None), name
    assert isinstance(ours["detail"], str) and ours["detail"], name
    assert HEX32.match(ours["request_id"]) and res.headers["X-Request-Id"] == ours["request_id"], name
    assert res.headers["X-Truebex-Contract"] == WIRE, name
    if ours["retry_after_s"] is not None:
        assert res.headers["Retry-After"] == str(ours["retry_after_s"]), name
    return ours


class _Broken:
    """An adapter that fails in a way the proxy does not expect."""

    name = "anthropic"

    @asynccontextmanager
    async def stream(self, turn, alias, server=None):
        raise RuntimeError("adapter fell over")
        yield  # pragma: no cover

    async def whole(self, turn, alias, server=None):
        raise RuntimeError("adapter fell over")


def test_pf11b_error_envelopes_match_the_apps(client, fake, monkeypatch):
    """Each of the app's error envelopes against the platform's answer to that
    case. How each is provoked: credits_exhausted = a Studio account with 0
    credits; plan_required = a Free account's device; unauthenticated = no
    token, then a device token that does not exist; rate_limited = two turns in
    flight, then the 60-a-minute bucket (at 1); upstream_busy = the provider's
    529 with retry-after 1; internal_error = the adapter raising an unexpected
    error; too_large = a body over 8 MB."""
    a = studio_person(client)
    first = [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}]

    def turn(person=a, h=None, payload=None, c=client):
        return send(c, h or headers(person), payload if payload is not None else turn_body(first, secrets.token_hex(16)))

    set_remaining(a.user_id, 0)
    _matches("credits-exhausted.json", turn())
    set_remaining(a.user_id, 1000)
    free = Person(client, "free@example.com", trial=False)
    assert _matches("plan-required.json", turn(free), {"plan"})["data"]["plan_needed"] == "pro"
    _matches("unauthenticated.json", turn(h={"X-Truebex-Contract": WIRE}))
    _matches("unauthenticated.json", turn(h={"Authorization": "Bearer tbx_dev_" + "x" * 43, "X-Truebex-Contract": WIRE}))
    with SessionLocal() as db:
        for t in ("a" * 32, "b" * 32):
            db.add(AiTurn(turn_id=t, account_id=a.user_id, started_at=clock.now()))
        db.commit()
    _matches("rate-limited.json", turn(), {"in_flight"})
    with SessionLocal() as db:
        db.execute(delete(AiTurn))
        db.commit()
    from app import ratelimit

    monkeypatch.setattr(proxy, "PER_MINUTE", 1)
    ratelimit.reset()
    fake.script("echo")
    assert turn().status_code == 200
    _matches("rate-limited.json", turn())
    monkeypatch.setattr(proxy, "PER_MINUTE", 60)
    ratelimit.reset()
    fake.error(529, {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}, retry_after=1)
    assert _matches("upstream-busy.json", turn())["retry_after_s"] == 1
    _matches("too-large.json", turn(payload=b" " * (8 * 1024 * 1024 + 1)), {"limit"})
    monkeypatch.setitem(adapters.ADAPTERS, "anthropic", _Broken())
    _matches("server-error.json", turn(c=TestClient(app, raise_server_exceptions=False)))
    assert remaining(a.user_id) == 1000 - 4  # only the one echo turn was charged
    with SessionLocal() as db:
        assert db.scalars(select(AiTurn)).all() == []


# --- the wire header --------------------------------------------------------------------------------------


def test_pf11b_routes_speak_ai_proxy_1_1(client, fake):
    """Every /ai route answers X-Truebex-Contract: ai-proxy/1.1 to ai-proxy/1.0,
    to ai-proxy/1.1 and to no header; ai-proxy/2.0 gets 400 contract_version."""
    assert proxy.CONTRACT == WIRE
    a = studio_person(client)
    first = [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}]
    for sent in ("ai-proxy/1.0", WIRE, None):
        h = headers(a, sent)
        for path in ("/ai/models", "/ai/balance"):
            res = client.get(path, headers=h)
            assert res.status_code == 200 and res.headers["X-Truebex-Contract"] == WIRE, (sent, path)
        count = client.post("/ai/messages/count", json=turn_body(first, secrets.token_hex(16)), headers=h)
        assert count.status_code == 200 and count.headers["X-Truebex-Contract"] == WIRE, sent
        fake.script("echo")
        res = send(client, h, turn_body(first, secrets.token_hex(16)))
        assert res.status_code == 200 and res.headers["X-Truebex-Contract"] == WIRE, sent
    for path in ("/ai/models", "/ai/balance"):
        bad = client.get(path, headers=headers(a, "ai-proxy/2.0"))
        assert bad.status_code == 400 and bad.json()["code"] == "contract_version", path
        assert bad.json()["data"]["supported"] == [WIRE] and bad.headers["X-Truebex-Contract"] == WIRE
    bad = send(client, headers(a, "ai-proxy/2.0"), turn_body(first, secrets.token_hex(16)))
    assert bad.status_code == 400 and bad.json()["code"] == "contract_version"


def test_pf11b_no_route_or_script_left_on_1_0():
    """The /ai routes, the tests' helpers and the demo scripts are on 1.1;
    demo_analysis.py sends render-jobs/1.1 (PF6a's deviation 6)."""
    from . import ai_helpers

    assert ai_helpers.AI == {"X-Truebex-Contract": WIRE}
    for path in (ROOT / "server" / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "ai-proxy/1.0" not in text and 'contract("ai-proxy", 1, 0)' not in text, path
    scripts = ROOT / "server" / "scripts"
    demo_ai = (scripts / "demo_ai.py").read_text(encoding="utf-8")
    assert f'"X-Truebex-Contract": "{WIRE}"' in demo_ai and "ai-proxy/1.0" not in demo_ai
    demo_analysis = (scripts / "demo_analysis.py").read_text(encoding="utf-8")
    assert '"X-Truebex-Contract": "render-jobs/1.1"' in demo_analysis and "render-jobs/1.0" not in demo_analysis
    upstream = (scripts / "fake_ai_upstream.py").read_text(encoding="utf-8")
    assert "stub_like" in upstream and "TURNS" not in upstream


# --- the page usage_url opens -------------------------------------------------------------------------------


def test_pf11b_usage_url_opens_the_recent_turns_panel():
    """usage_url is the Cloud page's Recent turns panel: its fragment is the id
    AiCredits.tsx gives that panel (top_up_url's is the section's own)."""
    usage, top_up = urlsplit(credits.usage_url()), urlsplit(credits.top_up_url())
    assert (usage.path, usage.fragment) == ("/dashboard/cloud/", "ai-usage")
    assert (top_up.path, top_up.fragment) == ("/dashboard/cloud/", "ai-credits")
    source = (ROOT / "src" / "components" / "cloud" / "AiCredits.tsx").read_text(encoding="utf-8")
    assert 'const USAGE_ANCHOR = "ai-usage";' in source and 'const ANCHOR = "ai-credits";' in source
    turns = source.split("function Turns(", 1)[1].split("\n}\n", 1)[0]
    assert "id={USAGE_ANCHOR}" in turns and "scroll-mt-24" in turns and "CLOUD_AI.turns.title" in turns
    page = (ROOT / "src" / "app" / "dashboard" / "cloud" / "page.tsx").read_text(encoding="utf-8")
    assert "<AiCredits" in page
