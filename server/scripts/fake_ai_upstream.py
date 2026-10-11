"""A stand-in model provider for trying the AI proxy without a provider key (PF11).

    cd server
    .venv\\Scripts\\python.exe scripts\\fake_ai_upstream.py --port 8790

It answers the official SDK's `/v1/messages` with the ai-proxy contract
fixtures' window conversation (find, place, end_turn, then again from the
start) and `/v1/messages/count_tokens` with 5120 tokens. Point the local API
at it with `ANTHROPIC_BASE_URL=http://127.0.0.1:8790` and any
`ANTHROPIC_API_KEY` in server/.env; remove both to use the real provider.
"""

import argparse
import sys
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fakes.fake_provider import FakeProvider  # noqa: E402

TURNS = ("window/01-find.sse", "window/02-place.sse", "window/03-end.sse")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args(argv)
    fake = FakeProvider()
    real_init = ThreadingHTTPServer.__init__

    def bind_port(self, address, handler, *rest, **kw):  # the fake binds port 0; use --port
        real_init(self, ("127.0.0.1", args.port), handler, *rest, **kw)

    ThreadingHTTPServer.__init__ = bind_port
    fake.start()
    ThreadingHTTPServer.__init__ = real_init
    print(f"fake model provider on {fake.base_url} (the window conversation, in a loop)", flush=True)
    try:
        while True:
            if len(fake.messages) < 3:
                for name in TURNS:
                    fake.sse(name)
            time.sleep(0.5)
    except KeyboardInterrupt:
        fake.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
