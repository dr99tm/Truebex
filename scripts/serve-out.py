"""Serve the static export (out/) the way GitHub Pages does for the parts the
share page relies on (PF5): every response says
`Access-Control-Allow-Origin: *`, and .js / .mjs / .css have their web
types, so a share page on the API's origin can load /viewer/viewer.js as a
module from here. Used by scripts/autopilot-serve.ps1.

The listen backlog is 128, not the standard library's 5: a dashboard page
asks for about 100 files at once, and with 5 the rest got a random
ERR_CONNECTION_REFUSED in headless self-tests and human tests (PF5a).

A missing path answers the folder's 404.html with status 404, as GitHub Pages
does (PF13c: the site's own not-found page); a folder without one answers the
standard error page.

    py -3.12 scripts/serve-out.py <port> [--directory out] [--bind 0.0.0.0]
"""

import argparse
import functools
import os
from http import HTTPStatus
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

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        page = self.not_found_page() if code == HTTPStatus.NOT_FOUND else None
        if page is None:
            super().send_error(code, message, explain)
            return
        self.log_error("code %d, message %s", code, message)
        self.send_response(code)
        self.send_header("Connection", "close")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(page)

    def not_found_page(self) -> bytes | None:
        try:
            with open(os.path.join(self.directory, "404.html"), "rb") as f:
                return f.read()
        except OSError:
            return None


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
