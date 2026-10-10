"""Serve the static export (out/) the way GitHub Pages does for the parts the
share page relies on (PF5): every response says
`Access-Control-Allow-Origin: *`, and .js / .mjs / .css have their web
types, so a share page on the API's origin can load /viewer/viewer.js as a
module from here. Used by scripts/autopilot-serve.ps1.

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve out/ with CORS like GitHub Pages.")
    parser.add_argument("port", type=int)
    parser.add_argument("--directory", default="out")
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args()
    handler = functools.partial(Handler, directory=args.directory)
    with ThreadingHTTPServer((args.bind, args.port), handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
