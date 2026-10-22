"""A stand-in model provider for trying the AI proxy without a provider key (PF11, PF11b).

    cd server
    .venv\\Scripts\\python.exe scripts\\fake_ai_upstream.py --port 8790

It answers the official SDK's `/v1/messages` the way the app's stub does
(contract ai-proxy 1.1.2 §9), from the app's own scripted conversations in
tests/contracts/ai-proxy/: the person's newest words pick the script
(`window`, `paint` or `create` by their `match` words; `echo` answers anything
else), the number of assistant replies since then picks the turn, and
`${wall}` / `${room}` are filled from the tool results the proxy forwards.
`/v1/messages/count_tokens` answers 5120 tokens. Point the local API at it
with `ANTHROPIC_BASE_URL=http://127.0.0.1:8790` and any `ANTHROPIC_API_KEY`
in server/.env; remove both to use the real provider.
"""

import argparse
import sys
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fakes.fake_provider import FakeProvider  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args(argv)
    fake = FakeProvider()
    fake.stub_like = True  # every /v1/messages: the scripted turn the request reaches
    real_init = ThreadingHTTPServer.__init__

    def bind_port(self, address, handler, *rest, **kw):  # the fake binds port 0; use --port
        real_init(self, ("127.0.0.1", args.port), handler, *rest, **kw)

    ThreadingHTTPServer.__init__ = bind_port
    fake.start()
    ThreadingHTTPServer.__init__ = real_init
    print(f"fake model provider on {fake.base_url} (the app's scripted conversations: window, paint, create, echo)", flush=True)
    seen = 0
    try:
        while True:
            for served in fake.served[seen:]:
                print(f"answered {served.file} (turn {served.turn + 1} of {served.script})", flush=True)
            seen = len(fake.served)
            time.sleep(0.5)
    except KeyboardInterrupt:
        fake.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
