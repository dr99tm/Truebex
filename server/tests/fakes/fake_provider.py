"""A fake model provider for the AI proxy's tests (PF11, PF11b).

A real HTTP server on 127.0.0.1 (a thread), so the proxy's adapters run end
to end: the official SDK against `/v1/messages` and `/v1/messages/count_tokens`
(ANTHROPIC_BASE_URL points here), and an OpenAI-compatible inference server's
`/v1/chat/completions` and `/v1/models` for the self-hosted adapter.

    fake = FakeProvider().start()
    fake.sse("window/01-find.sse")            # the next /v1/messages answer: PF11's own turn
                                              # (tests/fixtures/ai/) without its truebex_credits
    fake.sse(contract_bytes("refusal.sse"))   # or any bytes: the app's file, say
    fake.script("window")                     # the app's scripted conversation (§9), one
                                              # answer per turn, as the app's stub plays it
    fake.error(529, {...}, retry_after=7)     # or an error answer
    fake.requests[-1].body                    # the raw bytes the proxy sent
    fake.served                               # what each scripted answer was

Answers are served in order; with none queued, /v1/messages answers 500 (or,
with `stub_like`, the scripted turn the request reaches).

Two fixture sets: the contract's, the app's own (AI3; tests/contracts/
ai-proxy/, byte for byte), and PF11's own window turns (tests/fixtures/ai/:
cache tokens in their usage, the proxy's whole stream in each file).

A scripted answer follows the app's stub (contract ai-proxy §9 and
FastEyeAiProxyStub.cpp): the script is the one whose `match` words the newest
user text holds (window, paint, create; echo answers the rest) unless the
test names it, the turn is the number of assistant replies after that text,
and `${name}` placeholders are filled from the earlier turns' `capture`: the
dotted path read from the tool_result that answered that turn's tool_use, in
the request the proxy forwarded (a value holding a quote or a backslash is
refused, as the stub refuses it). The file's truebex_credits event, the only
place `${remaining}` sits, is dropped: the proxy inserts its own.
"""

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
CONTRACT_FIXTURES = TESTS / "contracts" / "ai-proxy"
OWN_FIXTURES = TESTS / "fixtures" / "ai"
# The stub's order (FastEyeAiProxyStub.cpp); echo answers any other request.
SCRIPTS = ("window", "paint", "create")


def fixture_bytes(name: str) -> bytes:
    """One of PF11's own files (tests/fixtures/ai/)."""
    return (OWN_FIXTURES / name).read_bytes()


def contract_bytes(name: str) -> bytes:
    """One of the app's files (tests/contracts/ai-proxy/)."""
    return (CONTRACT_FIXTURES / name).read_bytes()


def script_of(name: str) -> dict:
    return json.loads(contract_bytes(f"{name}/script.json"))


def events_of(data: bytes) -> list[bytes]:
    """An SSE byte stream split into events (each ends with its blank line)."""
    return [chunk + b"\n\n" for chunk in data.split(b"\n\n") if chunk.strip()]


def event_name(raw: bytes) -> str | None:
    first = raw.split(b"\n", 1)[0]
    return first[6:].strip().decode() if first.startswith(b"event:") else None


def without_credits(data: bytes) -> bytes:
    return b"".join(e for e in events_of(data) if event_name(e) != "truebex_credits")


def tool_use_id(sse: bytes) -> str | None:
    """The id of the first tool_use block a turn's stream starts."""
    for raw in events_of(sse):
        if event_name(raw) == "content_block_start":
            line = next(ln for ln in raw.split(b"\n") if ln.startswith(b"data:"))
            block = json.loads(line[5:]).get("content_block") or {}
            if block.get("type") == "tool_use":
                return block.get("id")
    return None


def _blocks(message: dict) -> list[dict]:
    content = message.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def _newest_user_text(messages: list) -> tuple[int, str]:
    """(index, text) of the newest user message holding a text block."""
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") != "user":
            continue
        for block in reversed(_blocks(messages[i])):
            if block.get("type") == "text":
                return i, str(block.get("text") or "")
    return -1, ""


def result_text(block: dict) -> str:
    inner = block.get("content")
    if isinstance(inner, str):
        return inner
    return "".join(p.get("text", "") for p in inner or [] if isinstance(p, dict) and p.get("type") == "text")


def at(value: object, dotted: str) -> object:
    """`matches.0.ref` read from a JSON value (None when it is not there)."""
    for part in dotted.split("."):
        if isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


@dataclass
class Served:
    """What one scripted answer was: the script, the turn (0-based), its
    file and the bytes sent (placeholders filled, no truebex_credits)."""

    script: str
    turn: int
    file: str
    data: bytes


def scripted_turn(request: dict, name: str | None = None) -> Served:
    """The app's stub's answer to a forwarded /v1/messages body (§9)."""
    messages = [m for m in request.get("messages") or [] if isinstance(m, dict)]
    user_at, words = _newest_user_text(messages)
    replies = sum(1 for m in messages[user_at + 1 :] if m.get("role") == "assistant")
    if name is None:
        lowered = words.lower()
        name = next((s for s in SCRIPTS if any(w.lower() in lowered for w in script_of(s)["match"])), "echo")
    turns = script_of(name)["turns"]
    if replies >= len(turns):  # past a script's end the stub answers echo's turn
        name, turns, replies = "echo", script_of("echo")["turns"], 0
    file = f"{name}/{turns[replies]['sse']}"
    data = contract_bytes(file)
    for earlier in turns[:replies]:
        capture = earlier.get("capture") or {}
        if not capture:
            continue
        wanted = tool_use_id(contract_bytes(f"{name}/{earlier['sse']}"))
        for message in messages[user_at + 1 :]:
            for block in _blocks(message):
                if block.get("type") != "tool_result" or block.get("tool_use_id") != wanted:
                    continue
                try:
                    result = json.loads(result_text(block))
                except ValueError:
                    result = None
                for key, path in capture.items():
                    value = at(result, path)
                    text = "" if value is None else value if isinstance(value, str) else json.dumps(value)
                    if '"' in text or "\\" in text:
                        raise ValueError(f"capture-value: {text!r}")
                    data = data.replace(("${%s}" % key).encode(), text.encode("utf-8"))
    return Served(name, replies, file, without_credits(data))


@dataclass
class Recorded:
    method: str
    path: str
    headers: dict
    body: bytes

    def json(self):
        return json.loads(self.body)


@dataclass
class Answer:
    status: int = 200
    events: list[bytes] = field(default_factory=list)
    body: bytes = b""
    headers: dict = field(default_factory=dict)
    delay_s: float = 0.0
    first_delay_s: float = 0.0
    cut_after: int | None = None
    stream: bool = False
    # A scripted turn, resolved when its request arrives: "" = the script the
    # newest user text picks, a name = that script.
    script: str | None = None


class FakeProvider:
    def __init__(self) -> None:
        self.messages: deque[Answer] = deque()
        self.chat: deque[Answer] = deque()
        self.requests: list[Recorded] = []
        self.served: list[Served] = []
        self.input_tokens = 5120
        self.healthy = True
        # With nothing queued, answer the scripted turn the request reaches.
        self.stub_like = False
        self._server: ThreadingHTTPServer | None = None

    # --- scripting ---------------------------------------------------------------------

    def sse(self, name_or_bytes: str | bytes, *, delay_s: float = 0.0, first_delay_s: float = 0.0, cut_after: int | None = None) -> None:
        data = fixture_bytes(name_or_bytes) if isinstance(name_or_bytes, str) else name_or_bytes
        self.messages.append(
            Answer(events=events_of(without_credits(data)), delay_s=delay_s, first_delay_s=first_delay_s, cut_after=cut_after, stream=True)
        )

    def script(self, name: str | None = None, *, turns: int | None = None) -> None:
        """Queue a scripted conversation: one answer per turn of the named
        script (or `turns` answers by the stub's own pick)."""
        count = turns if turns is not None else len(script_of(name)["turns"]) if name else 1
        for _ in range(count):
            self.messages.append(Answer(stream=True, script=name or ""))

    def message(self, body: dict) -> None:
        self.messages.append(Answer(body=json.dumps(body).encode()))

    def error(self, status: int, body: dict | None = None, *, retry_after: int | None = None) -> None:
        headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
        payload = body or {"type": "error", "error": {"type": "api_error", "message": f"status {status}"}}
        self.messages.append(Answer(status=status, body=json.dumps(payload).encode(), headers=headers))

    def chat_sse(self, chunks: list[dict]) -> None:
        events = [f"data: {json.dumps(c)}\n\n".encode() for c in chunks] + [b"data: [DONE]\n\n"]
        self.chat.append(Answer(events=events, stream=True))

    def chat_json(self, body: dict) -> None:
        self.chat.append(Answer(body=json.dumps(body).encode()))

    def of_path(self, path: str) -> list[Recorded]:
        return [r for r in self.requests if r.path == path]

    def _resolve(self, answer: Answer, rec: Recorded) -> Answer:
        if answer.script is None:
            return answer
        try:
            served = scripted_turn(rec.json(), answer.script or None)
        except (ValueError, KeyError, OSError) as exc:
            message = json.dumps({"type": "error", "error": {"type": "api_error", "message": f"script: {exc}"}})
            return Answer(status=500, body=message.encode())
        self.served.append(served)
        return replace(answer, events=events_of(served.data))

    # --- the server --------------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "FakeProvider":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # quiet
                pass

            def _record(self) -> Recorded:
                length = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(length) if length else b""
                rec = Recorded(self.command, self.path.split("?", 1)[0], {k.lower(): v for k, v in self.headers.items()}, body)
                owner.requests.append(rec)
                return rec

            def _send(self, answer: Answer) -> None:
                if not answer.stream:
                    self.send_response(answer.status)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(answer.body)))
                    for k, v in answer.headers.items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(answer.body)
                    return
                if answer.first_delay_s:
                    time.sleep(answer.first_delay_s)
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("cache-control", "no-cache")
                self.end_headers()
                for i, event in enumerate(answer.events):
                    if answer.cut_after is not None and i >= answer.cut_after:
                        break
                    if i and answer.delay_s:
                        time.sleep(answer.delay_s)
                    self.wfile.write(event)
                    self.wfile.flush()

            def do_GET(self) -> None:
                self._record()
                if self.path.split("?", 1)[0] == "/v1/models" and owner.healthy:
                    self._send(Answer(body=b'{"object":"list","data":[{"id":"truebex-open","object":"model"}]}'))
                else:
                    self._send(Answer(status=503, body=b'{"error":{"message":"loading"}}'))

            def do_POST(self) -> None:
                rec = self._record()
                if rec.path == "/v1/messages/count_tokens":
                    self._send(Answer(body=json.dumps({"input_tokens": owner.input_tokens}).encode()))
                    return
                queue = owner.chat if rec.path == "/v1/chat/completions" else owner.messages
                if queue:
                    answer = queue.popleft()
                elif owner.stub_like and rec.path == "/v1/messages":
                    answer = Answer(stream=True, script="")
                else:
                    answer = Answer(status=500, body=b'{"type":"error","error":{"type":"api_error","message":"nothing scripted"}}')
                self._send(owner._resolve(answer, rec))

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
