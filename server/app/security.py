"""Password hashing, JWT and API key helpers."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import get_settings

settings = get_settings()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Every key starts with this, so leaked keys are easy to spot in code scans.
API_KEY_PREFIX = "tbx_live_"


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    # Google-only accounts have no password hash.
    if not hashed:
        return False
    return _pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    """Create a signed JWT whose `sub` claim is the user's id (as a string)."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the `sub` claim if the token is valid, else None."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except JWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, display_prefix, sha256_hash) for a new API key."""
    key = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return key, key[: len(API_KEY_PREFIX) + 6], hash_api_key(key)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
