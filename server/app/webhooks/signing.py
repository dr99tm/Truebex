"""Standard Webhooks signing (github.com/standard-webhooks/standard-webhooks,
`spec/standard-webhooks.md`), so receivers can use the specification's own
verification libraries or the SDK helpers.

* Headers: `webhook-id` (the event id, the same on every attempt),
  `webhook-timestamp` (Unix seconds of this attempt), `webhook-signature`
  (`v1,<base64 HMAC-SHA256>`; several space-separated during a rotation).
* Signed content: `<webhook-id>.<webhook-timestamp>.<body>`.
* Secret: `whsec_` + base64 of 24 random bytes; the HMAC key is the decoded bytes.
* Receivers refuse timestamps more than 5 minutes off.

Secrets are sealed at rest with Fernet under WEBHOOK_SECRET_KEY (derived from
SECRET_KEY when unset, like SSO_SECRET_KEY).
"""

import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings

SECRET_PREFIX = "whsec_"
TOLERANCE_S = 5 * 60


class SignatureError(ValueError):
    pass


def new_secret() -> str:
    return SECRET_PREFIX + base64.b64encode(secrets.token_bytes(24)).decode("ascii")


def _key(secret: str) -> bytes:
    raw = secret[len(SECRET_PREFIX):] if secret.startswith(SECRET_PREFIX) else secret
    return base64.b64decode(raw)


def sign(secret: str, msg_id: str, timestamp: int, body: bytes) -> str:
    content = f"{msg_id}.{int(timestamp)}.".encode() + body
    digest = hmac.new(_key(secret), content, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode("ascii")


def headers(secret: str, msg_id: str, timestamp: int, body: bytes) -> dict[str, str]:
    return {
        "webhook-id": msg_id,
        "webhook-timestamp": str(int(timestamp)),
        "webhook-signature": sign(secret, msg_id, timestamp, body),
    }


def verify(
    secret: str, sent: Mapping[str, str], body: bytes, *, tolerance_s: int = TOLERANCE_S, now: float | None = None
) -> None:
    """Raise SignatureError unless one `v1` signature matches and the timestamp is fresh."""
    lower = {k.lower(): v for k, v in sent.items()}
    msg_id, stamp, signatures = lower.get("webhook-id"), lower.get("webhook-timestamp"), lower.get("webhook-signature")
    if not msg_id or not stamp or not signatures:
        raise SignatureError("missing webhook-id, webhook-timestamp or webhook-signature")
    try:
        ts = int(stamp)
    except ValueError:
        raise SignatureError("bad webhook-timestamp")
    current = time.time() if now is None else now
    if abs(current - ts) > tolerance_s:
        raise SignatureError("timestamp outside the tolerance")
    expected = sign(secret, msg_id, ts, body).split(",", 1)[1]
    for item in signatures.split():
        version, _, value = item.partition(",")
        if version == "v1" and hmac.compare_digest(value, expected):
            return
    raise SignatureError("no matching signature")


# --- sealing --------------------------------------------------------------------------------


def _fernet() -> Fernet:
    s = get_settings()
    key = s.webhook_secret_key.encode("ascii") if s.webhook_secret_key else base64.urlsafe_b64encode(
        hashlib.sha256(b"truebex-webhook-secrets/1\n" + s.secret_key.encode("utf-8")).digest()
    )
    return Fernet(key)


def seal(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def unseal(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None  # sealed under another WEBHOOK_SECRET_KEY: rotate the endpoint's secret
