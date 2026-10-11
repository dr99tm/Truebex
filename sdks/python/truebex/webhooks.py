"""Verify a Truebex webhook (Standard Webhooks): `verify_webhook(secret,
headers, body)` returns the parsed event or raises WebhookVerificationError.

    event = truebex.verify_webhook(os.environ["TRUEBEX_WEBHOOK_SECRET"], request.headers, request.body)

Pass the raw body exactly as received (bytes or str), before any JSON parsing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from typing import Any

TOLERANCE_S = 5 * 60


class WebhookVerificationError(ValueError):
    pass


def _key(secret: str) -> bytes:
    raw = secret[6:] if secret.startswith("whsec_") else secret
    return base64.b64decode(raw)


def sign(secret: str, msg_id: str, timestamp: int, body: bytes) -> str:
    """`v1,<base64 HMAC-SHA256 of "id.timestamp.body">` (for tests of your own receiver)."""
    content = f"{msg_id}.{int(timestamp)}.".encode() + body
    return "v1," + base64.b64encode(hmac.new(_key(secret), content, hashlib.sha256).digest()).decode()


def verify_webhook(
    secret: str,
    headers: Mapping[str, str],
    body: bytes | str,
    *,
    tolerance_s: int = TOLERANCE_S,
    now: float | None = None,
) -> Any:
    raw = body.encode("utf-8") if isinstance(body, str) else bytes(body)
    lower = {str(k).lower(): v for k, v in headers.items()}
    msg_id = lower.get("webhook-id")
    stamp = lower.get("webhook-timestamp")
    signatures = lower.get("webhook-signature")
    if not msg_id or not stamp or not signatures:
        raise WebhookVerificationError("missing webhook-id, webhook-timestamp or webhook-signature")
    try:
        ts = int(stamp)
    except ValueError:
        raise WebhookVerificationError("bad webhook-timestamp") from None
    if abs((time.time() if now is None else now) - ts) > tolerance_s:
        raise WebhookVerificationError("timestamp too old or too new")
    expected = sign(secret, msg_id, ts, raw).split(",", 1)[1]
    for item in signatures.split():
        version, _, value = item.partition(",")
        if version == "v1" and hmac.compare_digest(value, expected):
            try:
                return json.loads(raw)
            except ValueError:
                raise WebhookVerificationError("the body is not JSON") from None
    raise WebhookVerificationError("no matching signature")
