"""Share a bundle the way the app will (share-bundle §5.4, 5.1-5.3, 5.5), for
trying share pages before the app's Share command exists.

    .venv\\Scripts\\python.exe scripts\\demo_share.py --token tbx_dev_... \\
        --fixture tests\\contracts\\share-bundle\\manifest-house.json [--api http://127.0.0.1:8000]

The files are looked up by SHA-256 among the files beside the manifest.
Prints the parts it sent and the share's url. Running it again sends no
part (every file is `present`) and returns the same share. Get a device
token by signing in from the app, or with POST /licence/activate.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload and publish a share bundle.")
    parser.add_argument("--token", required=True, help="device token (tbx_dev_...)")
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
    headers = {"Authorization": f"Bearer {args.token}", **CONTRACT}
    api = args.api.rstrip("/")

    with httpx.Client(timeout=120) as client:
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
        print(f"state {share['state']} · expires {share['expires_at']}")
        print(f"url {share['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
