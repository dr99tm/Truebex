"""Shared helpers for the licence and release tests."""

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.licence import clock
from app.licence.jcs import canonical_bytes

CONTRACT = {"X-Truebex-Contract": "licence-api/1.0"}


def fp(name: str) -> str:
    """A fingerprint as the app makes it (contract §6.2), for a named machine."""
    return hashlib.sha256(f"truebex-fp/1\n{name}\nS-1-5-21-1001".encode()).hexdigest()


FP1, FP2, FP3 = fp("machine-1"), fp("machine-2"), fp("machine-3")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **CONTRACT}


def session(headers: dict) -> dict:
    return {**headers, **CONTRACT}


def activate(client, headers, fingerprint=FP1, name="TEST-PC", replace=None):
    body = {
        "fingerprint": fingerprint,
        "device_name": name,
        "os": "windows 10.0.26200",
        "app_version": "1.0.0",
        "replace_device_id": replace,
    }
    return client.post("/licence/activate", json=body, headers=session(headers))


def activated(client, headers, fingerprint=FP1, name="TEST-PC") -> dict:
    res = activate(client, headers, fingerprint, name)
    assert res.status_code in (200, 201), res.text
    return res.json()


def refresh(client, token, fingerprint=FP1):
    return client.post(
        "/licence/entitlement", json={"fingerprint": fingerprint, "app_version": "1.0.1"}, headers=bearer(token)
    )


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def verify_with(public_key_b64: str, doc: dict, signature_b64: str) -> None:
    """Raises InvalidSignature unless the signature is over the JCS bytes."""
    Ed25519PublicKey.from_public_bytes(b64d(public_key_b64)).verify(b64d(signature_b64), canonical_bytes(doc))


def published_key(client, kid: str) -> str:
    keys = client.get("/licence/keys", headers=CONTRACT).json()["keys"]
    return next(k["public_key"] for k in keys if k["kid"] == kid)


def ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


class Clock:
    """Moves the licence API's clock: `clk.advance(seconds=601)`."""

    def __init__(self, monkeypatch, start: datetime | None = None):
        self.at = (start or datetime.now(timezone.utc)).replace(microsecond=0)
        monkeypatch.setattr(clock, "now", lambda: self.at)

    def advance(self, **delta) -> datetime:
        self.at = self.at + timedelta(**delta)
        return self.at


def error_of(res, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert body["code"] == code, body
    assert body["status"] == status
    assert isinstance(body["detail"], str) and body["detail"]
    assert len(body["request_id"]) == 32 and int(body["request_id"], 16) >= 0
    assert res.headers["X-Request-Id"] == body["request_id"]
    return body


def jdump(obj) -> str:
    return json.dumps(obj, sort_keys=True)
