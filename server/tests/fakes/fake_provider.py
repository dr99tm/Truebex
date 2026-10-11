"""A fake model provider for the AI proxy's tests (PF11).

A real HTTP server on 127.0.0.1 (a thread), so the proxy's adapters run end
to end: the official SDK against `/v1/messages` and `/v1/messages/count_tokens`
(ANTHROPIC_BASE_URL points here), and an OpenAI-compatible inference server's
`/v1/chat/completions` and `/v1/models` for the self-hosted adapter.

    fake = FakeProvider().start()
    fake.sse("window/01-find.sse")            # the next /v1/messages answer: the fixture's
                                              # bytes without its truebex_credits event
    fake.error(529, {...}, retry_after=7)     # or an error answer
    fake.requests[-1].body                    # the raw bytes the proxy sent

Answers are served in order; with none queued, /v1/messages answers 500.
"""

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "contracts" / "ai-proxy"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def events_of(data: bytes) -> list[bytes]:
    """An SSE byte stream split into events (each ends with its blank line)."""
    return [chunk + b"\n\n" for chunk in data.split(b"\n\n") if chunk.strip()]


def event_name(raw: bytes) -> str | None:
    first = raw.split(b"\n", 1)[0]
    return first[6:].strip().decode() if first.startswith(b"event:") else None


def without_credits(data: bytes) -> bytes:
    return b"".join(e for e in events_of(data) if event_name(e) != "truebex_credits")


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


class FakeProvider:
    def __init__(self) -> None:
        self.messages: deque[Answer] = deque()
        self.chat: deque[Answer] = deque()
        self.requests: list[Recorded] = []
        self.input_tokens = 5120
        self.healthy = True
        self._server: ThreadingHTTPServer | None = None

    # --- scripting ---------------------------------------------------------------------

    def sse(self, name_or_bytes: str | bytes, *, delay_s: float = 0.0, first_delay_s: float = 0.0, cut_after: int | None = None) -> None:
        data = fixture_bytes(name_or_bytes) if isinstance(name_or_bytes, str) else name_or_bytes
        self.messages.append(
            Answer(events=events_of(without_credits(data)), delay_s=delay_s, first_delay_s=first_delay_s, cut_after=cut_after, stream=True)
        )

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
                answer = queue.popleft() if queue else Answer(status=500, body=b'{"type":"error","error":{"type":"api_error","message":"nothing scripted"}}')
                self._send(answer)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
