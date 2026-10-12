"""Serve the static export (out/) the way GitHub Pages does for the parts the
share page relies on (PF5): every response says
`Access-Control-Allow-Origin: *`, and .js / .mjs / .css have their web
types, so a share page on the API's origin can load /viewer/viewer.js as a
module from here. Used by scripts/autopilot-serve.ps1.

The listen backlog is 128, not the standard library's 5: a dashboard page
asks for about 100 files at once, and with 5 the rest got a random
ERR_CONNECTION_REFUSED in headless self-tests and human tests (PF5a).

    py -3.12 scripts/serve-out.py <port> [--directory out] [--bind 0.0.0.0]
"""

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".webmanifest": "application/manifest+json",
        ".wasm": "application/wasm",
    }

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


class Server(ThreadingHTTPServer):
    request_queue_size = 128


def make_server(bind: str, port: int, directory: str) -> Server:
    return Server((bind, port), functools.partial(Handler, directory=directory))


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve out/ with CORS like GitHub Pages.")
    parser.add_argument("port", type=int)
    parser.add_argument("--directory", default="out")
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args()
    with make_server(args.bind, args.port, args.directory) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
