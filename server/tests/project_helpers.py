"""Shared helpers for the project service tests (PF4, contract project-log)."""

import base64
import hashlib
import json
import secrets
from pathlib import Path

from sqlalchemy import update

from app.database import SessionLocal
from app.models import User

from .conftest import signup
from .licence_helpers import activated, fp

CONTRACT = {"X-Truebex-Contract": "project-log/1.0"}
UPLOADS = {"X-Truebex-Contract": "share-bundle/1.0"}
FIXTURES = Path(__file__).parent / "contracts" / "project-log"


def hex32() -> str:
    return secrets.token_hex(16)


def dev(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **CONTRACT}


def web(session: dict) -> dict:
    return {**session, **CONTRACT}


class Person:
    """An account with a session, a device and its author id."""

    def __init__(self, client, email: str, *, trial: bool = True) -> None:
        self.email = email
        self.session = signup(client, email)
        device = activated(client, self.session, fingerprint=fp(email), name=email.split("@")[0].upper())
        self.token = device["device_token"]
        if trial:
            res = client.post("/licence/trial", json={"plan": "pro"}, headers={"Authorization": f"Bearer {self.token}"})
            assert res.status_code == 201, res.text
        account = client.get("/licence/account", headers={"Authorization": f"Bearer {self.token}"}).json()
        self.author_id = account["author_id"]
        self.user_id = account["user"]["id"]
        self.replica = hex32()

    @property
    def dev(self) -> dict:
        return dev(self.token)

    @property
    def web(self) -> dict:
        return web(self.session)

    def set_author_id(self, author_id: str) -> None:
        with SessionLocal() as db:
            db.execute(update(User).where(User.id == self.user_id).values(author_id=author_id))
            db.commit()
        self.author_id = author_id


def delta_op(
    author: str,
    touched: list[str],
    *,
    base_seq: int = 0,
    name: str = "Move wall",
    delta: bytes | None = None,
    op_id: str | None = None,
) -> dict:
    payload = delta if delta is not None else b"TBXD" + json.dumps({"rows": touched}).encode()
    return {
        "op_id": op_id or hex32(),
        "author": author,
        "author_kind": "person",
        "at": "2026-10-10T09:00:00.000Z",
        "touched": sorted(touched),
        "kind": "delta",
        "name": name,
        "base_seq": base_seq,
        "delta_format": "o5/38",
        "delta": base64.b64encode(payload).decode("ascii"),
    }


def action_op(author: str, touched: list[str], *, tool: str = "move", args: dict | None = None, base_seq: int = 0) -> dict:
    return {
        "op_id": hex32(),
        "author": author,
        "author_kind": "person",
        "at": "2026-10-10T09:00:00.000Z",
        "touched": sorted(touched),
        "kind": "action",
        "name": "Move wall",
        "base_seq": base_seq,
        "action": {
            "tool": tool,
            "args": args if args is not None else {"refs": touched, "by_mm": [0, 600, 0]},
            "permission": "edit",
            "session": hex32(),
            "request_id": hex32(),
        },
    }


def create(client, headers: dict, name: str = "House", doc_version: int = 38, **extra) -> dict:
    res = client.post("/projects", json={"name": name, "doc_version": doc_version}, headers={**headers, **extra})
    assert res.status_code == 201, res.text
    return res.json()


def push(client, headers: dict, pid: str, replica: str, ops: list[dict]):
    return client.post(f"/projects/{pid}/ops", json={"replica_id": replica, "ops": ops}, headers=headers)


def pushed(client, headers: dict, pid: str, replica: str, ops: list[dict]) -> dict:
    res = push(client, headers, pid, replica, ops)
    assert res.status_code == 200, res.text
    return res.json()


def pull(client, headers: dict, pid: str, after: int = 0, **params) -> dict:
    res = client.get(f"/projects/{pid}/ops", params={"after": after, **params}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def upload(client, token_or_session: dict, files: list[bytes], purpose: str = "snapshot", send: bool = True) -> str:
    """Open an upload for `files` and (by default) send every part. Returns the upload id."""
    auth = {k: v for k, v in token_or_session.items() if k == "Authorization"}
    body = {
        "purpose": purpose,
        "files": [
            {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "content_type": "application/octet-stream"}
            for data in files
        ],
    }
    res = client.post("/uploads", json=body, headers={**auth, **UPLOADS})
    assert res.status_code == 201, res.text
    opened = res.json()
    if send:
        part = opened["part_bytes"]
        for data, state in zip(files, opened["files"]):
            if state["state"] == "present":
                continue
            for n in range(state["parts"]):
                chunk = data[n * part : (n + 1) * part]
                sent = client.put(
                    f"/uploads/{opened['upload_id']}/files/{state['sha256']}/parts/{n}",
                    content=chunk,
                    headers={
                        **auth,
                        **UPLOADS,
                        "Content-Type": "application/octet-stream",
                        "X-Part-Sha256": hashlib.sha256(chunk).hexdigest(),
                    },
                )
                assert sent.status_code == 204, sent.text
    return opened["upload_id"]


def snapshot(client, headers: dict, pid: str, at_seq: int, tbxp: bytes, tbxpack: bytes | None = None, **extra):
    files = [tbxp] + ([tbxpack] if tbxpack is not None else [])
    upload_id = upload(client, headers, files)
    body = {
        "at_seq": at_seq,
        "doc_version": 38,
        "upload_id": upload_id,
        "files": {
            "tbxp": hashlib.sha256(tbxp).hexdigest(),
            "tbxpack": hashlib.sha256(tbxpack).hexdigest() if tbxpack is not None else None,
        },
    }
    return client.post(f"/projects/{pid}/snapshots", json=body, headers={**headers, **extra})


def invite_and_accept(client, owner: "Person", pid: str, person: "Person", role: str = "editor") -> dict:
    from app import mail

    res = client.post(f"/projects/{pid}/members", json={"email": person.email, "role": role}, headers=owner.web)
    assert res.status_code == 201, res.text
    token = invite_token(mail.OUTBOX[-1].text)
    res = client.post("/projects/invites/accept", json={"token": token}, headers=person.web)
    assert res.status_code == 200, res.text
    return res.json()


def invite_token(text: str) -> str:
    marker = "/invite/project/?t="
    start = text.index(marker) + len(marker)
    return text[start:].split()[0]
