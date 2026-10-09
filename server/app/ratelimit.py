"""Rate limiting: token buckets keyed by whatever identifies a caller.

`limit(key_fn, per_minute, burst=...)` is a FastAPI dependency; `check(key, …)`
is the same thing for keys known only inside an endpoint (an install id read
from the body). Over the limit → 429 `rate_limited` with `retry_after_s`.

Backends (RATELIMIT_BACKEND):
* `memory`: per-process buckets; the default while the API runs one process.
* `db`: buckets in `ratelimit_buckets`, shared by several processes. Keys are
  stored only as an HMAC, so no address ever reaches the database.

Addresses live only in the limiter's memory (telemetry.md §6.4).
"""

import hashlib
import hmac
import math
import threading
import time
from collections.abc import Callable
from datetime import datetime

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .contract_http import ContractError
from .database import SessionLocal
from .models import RateLimitBucket
from .tasks import periodic

settings = get_settings()

_lock = threading.Lock()
_buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, updated)
_MAX_KEYS = 50_000


def _clock() -> float:
    return time.monotonic() if settings.ratelimit_backend == "memory" else time.time()


def reset() -> None:
    """Forget every bucket (tests)."""
    with _lock:
        _buckets.clear()
    try:
        with SessionLocal() as db:
            db.execute(delete(RateLimitBucket))
            db.commit()
    except Exception:  # the table may not exist yet
        pass


def client_address(request: Request) -> str | None:
    """The caller's address as uvicorn sees it (behind Caddy, `--proxy-headers`
    resolves it from X-Forwarded-For)."""
    return request.client.host if request.client else None


def _refill(tokens: float, updated: float, now: float, rate: float, burst: float) -> float:
    return min(burst, tokens + max(0.0, now - updated) * rate)


def _take(tokens: float, rate: float) -> tuple[bool, float, int]:
    """(allowed, tokens left, seconds until one token is back)."""
    if tokens >= 1.0:
        return True, tokens - 1.0, 0
    return False, tokens, max(1, math.ceil((1.0 - tokens) / rate))


def _check_memory(key: str, rate: float, burst: float) -> tuple[bool, int]:
    now = _clock()
    with _lock:
        tokens, updated = _buckets.get(key, (burst, now))
        allowed, left, retry = _take(_refill(tokens, updated, now, rate, burst), rate)
        _buckets[key] = (left, now)
        if len(_buckets) > _MAX_KEYS:
            # Drop buckets that are full again: they carry no state.
            for k, (t, u) in list(_buckets.items()):
                if _refill(t, u, now, rate, burst) >= burst:
                    del _buckets[k]
    return allowed, retry


def _hashed(key: str) -> str:
    secret = (settings.secret_key + ":ratelimit").encode("utf-8")
    return hmac.new(secret, key.encode("utf-8"), hashlib.sha256).hexdigest()


def _check_db(key: str, rate: float, burst: float) -> tuple[bool, int]:
    hashed = _hashed(key)
    for attempt in range(2):
        now = _clock()
        with SessionLocal() as db:
            row = db.scalar(
                select(RateLimitBucket).where(RateLimitBucket.key == hashed).with_for_update()
            )
            if row is None:
                row = RateLimitBucket(key=hashed, tokens=burst, updated=now)
                db.add(row)
            allowed, left, retry = _take(_refill(row.tokens, row.updated, now, rate, burst), rate)
            row.tokens, row.updated = left, now
            try:
                db.commit()
            except IntegrityError:
                # Another process created the same bucket first: take from it.
                db.rollback()
                if attempt:
                    raise
                continue
        return allowed, retry
    raise AssertionError("unreachable")  # pragma: no cover


def check(key: str, *, per_minute: float, burst: int | None = None) -> None:
    """Take one token from `key`'s bucket or raise 429 `rate_limited`.

    The bucket holds `burst` tokens (default `per_minute`) and refills at
    `per_minute` tokens a minute: 60 an hour is `per_minute=1, burst=60`.
    """
    rate = per_minute / 60.0
    size = float(burst if burst is not None else per_minute)
    if settings.ratelimit_backend == "db":
        allowed, retry = _check_db(key, rate, size)
    else:
        allowed, retry = _check_memory(key, rate, size)
    if not allowed:
        raise ContractError(
            "rate_limited",
            429,
            "Too many requests. Try again shortly.",
            retry_after_s=retry,
        )


def limit(
    key_fn: Callable[[Request], str | None],
    per_minute: float,
    *,
    burst: int | None = None,
    scope: str = "default",
):
    """FastAPI dependency: `Depends(limit(client_address, 30, scope="health"))`."""

    def dependency(request: Request) -> None:
        key = key_fn(request)
        if key is not None:
            check(f"{scope}:{key}", per_minute=per_minute, burst=burst)

    return dependency


@periodic("ratelimit.purge", seconds=600)
def purge(now: datetime) -> None:
    """Drop shared buckets idle for an hour (every limit here refills by then)."""
    if settings.ratelimit_backend != "db":
        return
    with SessionLocal() as db:
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.updated < time.time() - 3600))
        db.commit()
