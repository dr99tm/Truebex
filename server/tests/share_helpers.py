"""Shared helpers for the upload and share tests (contract share-bundle)."""

import copy
import hashlib
import json
import math
from pathlib import Path

from .conftest import signup
from .licence_helpers import FP1, FP2, activated

SHARE_FIXTURES = Path(__file__).parent / "contracts" / "share-bundle"
CONTRACT = {"X-Truebex-Contract": "share-bundle/1.0"}
BINARIES = ("pano-2048.jpg", "pano-2048-kitchen.jpg", "pano-2048-hall.jpg", "render-640.jpg", "sheets-2p.pdf")


def fixture_json(name: str) -> dict:
    return json.loads((SHARE_FIXTURES / name).read_text(encoding="utf-8"))


def blobs_by_sha() -> dict[str, bytes]:
    out = {}
    for name in BINARIES:
        data = (SHARE_FIXTURES / name).read_bytes()
        out[hashlib.sha256(data).hexdigest()] = data
    return out


def house(bundle_id: str | None = None) -> dict:
    m = fixture_json("manifest-house.json")
    if bundle_id:
        m["bundle_id"] = bundle_id
    return m


def without_sheets(m: dict, bundle_id: str) -> dict:
    m = copy.deepcopy(m)
    pdf = m["sheets"]["file"]
    m["sheets"] = None
    m["files"] = [f for f in m["files"] if f["sha256"] != pdf]
    m["bundle_id"] = bundle_id
    return m


def dev(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **CONTRACT}


def web(session_headers: dict) -> dict:
    return {**session_headers, **CONTRACT}


def device_token(client, email: str = "designer@example.com", fingerprint: str = FP1) -> tuple[str, dict]:
    """(device token, website session headers) for a new Free account."""
    session = signup(client, email=email)
    return activated(client, session, fingerprint)["device_token"], session


def second_device(client, session: dict) -> str:
    return activated(client, session, FP2, name="LAPTOP")["device_token"]


def part_bytes() -> int:
    from app.uploads import service

    return service.PART_BYTES


def send_part(client, token: str, upload_id: str, sha: str, n: int, data: bytes, *, claimed: str | None = None):
    size = part_bytes()
    chunk = data[n * size : (n + 1) * size]
    return client.put(
        f"/uploads/{upload_id}/files/{sha}/parts/{n}",
        content=chunk,
        headers={
            **dev(token),
            "Content-Type": "application/octet-stream",
            "X-Part-Sha256": claimed or hashlib.sha256(chunk).hexdigest(),
        },
    )


def upload_files(client, token: str, upload: dict, only: list[str] | None = None) -> int:
    """Send every missing part of the upload's files; returns how many were sent."""
    data = blobs_by_sha()
    sent = 0
    for f in upload["files"]:
        if f["state"] in ("present", "complete") or (only is not None and f["sha256"] not in only):
            continue
        for n in range(math.ceil(len(data[f["sha256"]]) / part_bytes())):
            if n in f.get("received", []):
                continue
            res = send_part(client, token, upload["upload_id"], f["sha256"], n, data[f["sha256"]])
            assert res.status_code == 204, res.text
            sent += 1
    return sent


def create(client, token: str, m: dict | None = None, title: str = "House — client review", days: int = 30):
    return client.post(
        "/shares", json={"title": title, "expires_in_days": days, "manifest": m or house()}, headers=dev(token)
    )


def published(client, token: str, m: dict | None = None, title: str = "House — client review") -> dict:
    res = create(client, token, m, title)
    assert res.status_code in (200, 201), res.text
    body = res.json()
    upload_files(client, token, body["upload"])
    res = client.post(f"/shares/{body['share']['share_id']}/publish", headers=dev(token))
    assert res.status_code == 200, res.text
    return res.json()["share"]


def slug_path(share: dict) -> str:
    return f"/view/{share['slug']}"
