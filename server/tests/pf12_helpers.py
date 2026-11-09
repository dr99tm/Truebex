"""Shared helpers for the public API, webhook and package tests (PF12)."""

import hashlib
import json
import shutil
from pathlib import Path

from sqlalchemy import update

from app.database import SessionLocal
from app.models import ApiKey

ROOT = Path(__file__).resolve().parents[2]
PL = {"X-Truebex-Contract": "project-log/1.0"}
SB = {"X-Truebex-Contract": "share-bundle/1.0"}
RJ = {"X-Truebex-Contract": "render-jobs/1.4"}
ALL_SCOPES = [
    "projects:read",
    "projects:write",
    "jobs:write",
    "shares:write",
    "market:read",
    "supplier:feed",
    "webhooks:manage",
]


def make_key(client, session: dict, scopes: list[str] | None = None, name: str = "CI") -> dict:
    body = {"name": name}
    if scopes is not None:
        body["scopes"] = scopes
    res = client.post("/keys", json=body, headers=session)
    assert res.status_code == 201, res.text
    return res.json()


def kh(key: dict | str, **extra) -> dict:
    """Headers for an API key (the full `key` of a 201, or the raw string)."""
    raw = key["key"] if isinstance(key, dict) else key
    return {"Authorization": f"Bearer {raw}", **extra}


def make_legacy(key_id: int) -> None:
    """A key as made before scopes existed (scopes NULL)."""
    with SessionLocal() as db:
        db.execute(update(ApiKey).where(ApiKey.id == key_id).values(scopes=None))
        db.commit()


def node() -> str | None:
    return shutil.which("node")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jdump(obj) -> str:
    return json.dumps(obj, sort_keys=True)
