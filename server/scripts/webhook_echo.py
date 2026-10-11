r"""A local webhook receiver that prints each Truebex event and checks its
signature (PF12), for trying webhooks against a local API.

    cd server
    .venv\Scripts\python.exe scripts\webhook_echo.py --port 9900 [--secret whsec_…]

Register http://127.0.0.1:9900/ as an endpoint with the API started with
WEBHOOKS_ALLOW_HTTP_LOCAL=true (http:// and loopback addresses are refused
otherwise). Without --secret (or TRUEBEX_WEBHOOK_SECRET) it prints events and
says the signature was not checked; with it, each line ends "signature valid"
or "signature INVALID (…)". It answers 204 to a valid (or unchecked) event and
401 to an invalid one, so the delivery log shows both. Standard library only.
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOLERANCE_S = 300


def verify(secret: str, headers, body: bytes, now: float | None = None) -> str | None:
    """None when valid, else why not."""
    msg_id = headers.get("webhook-id")
    stamp = headers.get("webhook-timestamp")
    signatures = headers.get("webhook-signature")
    if not msg_id or not stamp or not signatures:
        return "missing webhook-* headers"
    try:
        ts = int(stamp)
    except ValueError:
        return "bad webhook-timestamp"
    if abs((time.time() if now is None else now) - ts) > TOLERANCE_S:
        return "timestamp more than 5 minutes off"
    key = base64.b64decode(secret[6:] if secret.startswith("whsec_") else secret)
    expected = base64.b64encode(hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
    for item in signatures.split():
        version, _, value = item.partition(",")
        if version == "v1" and hmac.compare_digest(value, expected):
            return None
    return "no matching v1 signature"


def make_handler(secret: str | None):
    class Echo(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server's name
            body = self.rfile.read(int(self.headers.get("content-length") or 0))
            problem = verify(secret, self.headers, body) if secret else None
            try:
                event = json.loads(body)
            except ValueError:
                event = {"type": "(not JSON)", "data": body[:200].decode("utf-8", "replace")}
            check = "signature not checked (no --secret)" if not secret else ("signature valid" if problem is None else f"signature INVALID ({problem})")
            data = json.dumps(event.get("data"), ensure_ascii=False)
            print(
                f"{time.strftime('%H:%M:%S')}  {event.get('type')}  {self.headers.get('webhook-id')}  {check}\n    {data[:400]}",
                flush=True,
            )
            self.send_response(401 if problem else 204)
            self.end_headers()

        def log_message(self, *_args) -> None:  # quiet: the line above says it all
            return

    return Echo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Print and verify Truebex webhooks on a local port.")
    ap.add_argument("--port", type=int, default=9900)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--secret", default=os.environ.get("TRUEBEX_WEBHOOK_SECRET", ""), help="the endpoint's whsec_… secret")
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.secret or None))
    print(f"listening on http://{args.host}:{args.port}/ ({'verifying' if args.secret else 'not verifying'} signatures); Ctrl+C stops", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
