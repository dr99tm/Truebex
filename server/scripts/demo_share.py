"""Share a bundle the way the app will (share-bundle §5.4, 5.1-5.3, 5.5), for
trying share pages before the app's Share command exists.

    .venv\\Scripts\\python.exe scripts\\demo_share.py --email you@example.com --password ... \\
        --fixture tests\\contracts\\share-bundle\\manifest-house.json [--api http://127.0.0.1:8000]
    (or --token tbx_dev_... instead of --email / --password)

The files are looked up by SHA-256 among the files beside the manifest.
Prints the parts it sent and the share's url. Running it again sends no
part (every file is `present`) and returns the same share. With --email and
--password it signs in and activates a "Share demo" device (licence-api 5.4,
which needs LICENCE_SIGNING_KEY on the server) and prints its token.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import httpx

CONTRACT = {"X-Truebex-Contract": "share-bundle/1.0"}
RETRY = {408, 429, 500, 502, 503, 504, 530}


def call(client: httpx.Client, method: str, url: str, **kw) -> httpx.Response:
    """One request with the contract's retry rules (§8): 1, 2, 4 … s on network errors and RETRY codes."""
    delay = 1.0
    for attempt in range(6):
        try:
            res = client.request(method, url, **kw)
        except httpx.TransportError as exc:
            if attempt == 5:
                raise SystemExit(f"cannot reach {url}: {exc}")
            time.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        if res.status_code not in RETRY or attempt == 5:
            return res
        time.sleep(float(res.headers.get("Retry-After", delay)))
        delay = min(delay * 2, 60)
    return res


def fail(res: httpx.Response) -> None:
    try:
        body = res.json()
        raise SystemExit(f"{res.request.method} {res.request.url.path} -> {res.status_code} {body.get('code')}: {body.get('detail')}\n{json.dumps(body.get('data'), indent=2)}")
    except ValueError:
        raise SystemExit(f"{res.request.method} {res.request.url.path} -> {res.status_code}: {res.text[:300]}")


def device_token(client: httpx.Client, api: str, email: str | None, password: str | None) -> str:
    """Sign in and activate a demo device (what the app does at sign-in)."""
    if not email or not password:
        raise SystemExit("give --token, or --email and --password")
    res = call(client, "POST", f"{api}/auth/login", json={"email": email, "password": password})
    if res.status_code != 200:
        fail(res)
    session = res.json()["access_token"]
    fingerprint = hashlib.sha256(f"truebex-fp/1|share-demo|{email}".encode()).hexdigest()
    res = call(client, "POST", f"{api}/licence/activate",
               headers={"Authorization": f"Bearer {session}", "X-Truebex-Contract": "licence-api/1.0"},
               json={"fingerprint": fingerprint, "device_name": "Share demo", "os": "demo",
                     "app_version": "1.0.0", "replace_device_id": None})
    if res.status_code not in (200, 201):
        fail(res)
    token = res.json()["device_token"]
    print(f"device token {token}")
    return token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload and publish a share bundle.")
    parser.add_argument("--token", help="device token (tbx_dev_...)")
    parser.add_argument("--email", help="sign in with this account instead of --token")
    parser.add_argument("--password")
    parser.add_argument("--fixture", required=True, type=Path, help="the bundle's manifest.json")
    parser.add_argument("--api", default=os.environ.get("TRUEBEX_API", "http://127.0.0.1:8000"))
    parser.add_argument("--title", default=None, help="share title (default: '<project> — client review')")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args(argv)

    manifest = json.loads(args.fixture.read_text(encoding="utf-8"))
    by_sha = {}
    for path in args.fixture.parent.iterdir():
        if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg", ".png", ".pdf"):
            by_sha[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    title = args.title or f"{manifest['project']['title']} — client review"
    api = args.api.rstrip("/")

    with httpx.Client(timeout=120) as client:
        token = args.token or device_token(client, api, args.email, args.password)
        headers = {"Authorization": f"Bearer {token}", **CONTRACT}
        res = call(client, "POST", f"{api}/shares", headers=headers,
                   json={"title": title, "expires_in_days": args.days, "manifest": manifest})
        if res.status_code not in (200, 201):
            fail(res)
        body = res.json()
        share, upload = body["share"], body["upload"]
        print(f"share {share['share_id']} ({'new' if res.status_code == 201 else 'existing'}, {share['state']})")
        sent = 0
        if upload:
            size = upload["part_bytes"]
            for f in upload["files"]:
                if f["state"] in ("present", "complete"):
                    continue
                path = by_sha.get(f["sha256"])
                if path is None:
                    raise SystemExit(f"no file beside the manifest has SHA-256 {f['sha256']}")
                data = path.read_bytes()
                for n in range(math.ceil(len(data) / size)):
                    if n in f.get("received", []):
                        continue
                    part = data[n * size : (n + 1) * size]
                    res = call(client, "PUT", f"{api}/uploads/{upload['upload_id']}/files/{f['sha256']}/parts/{n}",
                               content=part, headers={**headers, "Content-Type": "application/octet-stream",
                                                      "X-Part-Sha256": hashlib.sha256(part).hexdigest()})
                    if res.status_code != 204:
                        fail(res)
                    sent += 1
                    print(f"  sent {path.name} part {n}")
        print(f"{sent} parts sent")
        if share["state"] == "uploading":
            res = call(client, "POST", f"{api}/shares/{share['share_id']}/publish", headers=headers)
            if res.status_code != 200:
                fail(res)
            share = res.json()["share"]
        print(f"state {share['state']}, expires {share['expires_at']}")
        print(f"url {share['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
