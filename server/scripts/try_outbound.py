"""What PF14b's pinned connection does with a URL (the human test's probe):
the one lookup, the verdict on each address, the address it connects to and
the answer. Real DNS and network; one GET, nothing else is sent.

    cd server
    .venv\\Scripts\\python.exe scripts\\try_outbound.py https://example.com/
    .venv\\Scripts\\python.exe scripts\\try_outbound.py https://127.0.0.1.nip.io/
    .venv\\Scripts\\python.exe scripts\\try_outbound.py --private http://127.0.0.1:8098/.well-known/openid-configuration

Exit code 0 = an answer came back, 2 = refused before anything was sent,
1 = the connection failed (TLS, timeout, nothing listening).
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.net import outbound  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Send one GET over the API's pinned outbound connection.")
    ap.add_argument("url")
    ap.add_argument(
        "--private", action="store_true",
        help="also allow loopback and private networks, as SSO does when the API runs on 127.0.0.1",
    )  # fmt: skip
    args = ap.parse_args(argv)
    resolve, connect = outbound.resolve, outbound.connect

    def shown_resolve(host: str) -> list[str]:
        try:
            addresses = resolve(host)
        except OSError as exc:
            print(f"lookup  {host}: does not resolve ({exc})")
            raise
        print(f"lookup  {host} -> {', '.join(addresses) or 'nothing'}")
        for a in addresses:
            if outbound.is_public(a):
                verdict = "public"
            elif outbound.allowed(a, private=args.private):
                verdict = "not public, allowed by --private"
            else:
                verdict = "NOT public"
            print(f"        {a}: {verdict}")
        return addresses

    def shown_connect(address, port, *rest):
        print(f"connect {address} port {port} (the checked address; no second lookup)")
        return connect(address, port, *rest)

    outbound.resolve, outbound.connect = shown_resolve, shown_connect
    try:
        with outbound.client(timeout=15.0, private=args.private) as client:
            res = client.get(args.url, headers={"User-Agent": "Truebex-Outbound-Probe/1"})
    except outbound.Refused as exc:
        print(f"refused {exc}: nothing was sent")
        return 2
    except httpx.HTTPError as exc:
        print(f"failed  {type(exc).__name__}: {exc}")
        return 1
    finally:
        outbound.resolve, outbound.connect = resolve, connect
    host = urlsplit(args.url).hostname
    tls = f", certificate checked for {host} (SNI {host})" if urlsplit(args.url).scheme == "https" else ""
    print(f"answer  HTTP {res.status_code}, Host: {res.request.headers['host']}{tls}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
