"""Sealing SSO client secrets at rest (Fernet: AES-128-CBC + HMAC-SHA256)."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings


def _fernet() -> Fernet:
    s = get_settings()
    key = s.sso_secret_key.encode("ascii") if s.sso_secret_key else base64.urlsafe_b64encode(
        hashlib.sha256(b"truebex-sso-secrets/1\n" + s.secret_key.encode("utf-8")).digest()
    )
    return Fernet(key)


def seal(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def unseal(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None  # sealed with another key (SSO_SECRET_KEY changed): set it again
