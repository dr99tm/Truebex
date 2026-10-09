"""Rate limiting (PF14 Plumbing): token buckets keyed by whatever identifies a caller.

`limit(key_fn, per_minute, burst=..., name=...)` is a router or route
dependency; `check(key, …)` is the same thing for keys known only inside an
endpoint (an install id read from the body); `take(name, key, …)` the bare
bucket. Over the limit → 429 `rate_limited` with `retry_after_s`.

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

from fastapi import Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .contract_http import ContractError
from .database import SessionLocal
from .models import RateLimitBucket
from .tasks import periodic

settings = get_settings()

# Patched by tests to move time (the memory backend).
clock: Callable[[], float] = time.monotonic

_lock = threading.Lock()
_buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, updated)
_MAX_KEYS = 50_000

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _clock() -> float:
    # Shared buckets compare times across processes: wall clock.
    return clock() if settings.ratelimit_backend == "memory" else time.time()


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


def client_ip(request: Request) -> str:
    """The caller's address. Behind the Cloudflare tunnel every request
    arrives from loopback; Cloudflare sets CF-Connecting-IP (and overwrites
    any value a client sends), so it is trusted only from loopback. Behind
    Caddy, uvicorn's `--proxy-headers` has already resolved the peer."""
    peer = request.client.host if request.client else "unknown"
    if peer in _LOOPBACK:
        forwarded = request.headers.get("cf-connecting-ip")
        if forwarded:
            return forwarded.strip()[:64]
    return peer


def client_address(request: Request) -> str | None:
    """`client_ip`, or None (not limited) when the server cannot see one."""
    return client_ip(request) if request.client else None


def _refill(tokens: float, updated: float, now: float, rate: float, burst: float) -> float:
    return min(burst, tokens + max(0.0, now - updated) * rate)


def _spend(tokens: float, rate: float) -> tuple[float, float | None]:
    """(tokens left, None when allowed else seconds until one token is back)."""
    if tokens >= 1.0:
        return tokens - 1.0, None
    return tokens, (1.0 - tokens) / rate if rate > 0 else math.inf


def _take_memory(key: str, rate: float, burst: float) -> float | None:
    now = _clock()
    with _lock:
        tokens, updated = _buckets.get(key, (burst, now))
        left, wait = _spend(_refill(tokens, updated, now, rate, burst), rate)
        _buckets[key] = (left, now)
        if len(_buckets) > _MAX_KEYS:
            # Drop buckets that are full again: they carry no state.
            for k, (t, u) in list(_buckets.items()):
                if _refill(t, u, now, rate, burst) >= burst:
                    del _buckets[k]
    return wait


def _hashed(key: str) -> str:
    secret = (settings.secret_key + ":ratelimit").encode("utf-8")
    return hmac.new(secret, key.encode("utf-8"), hashlib.sha256).hexdigest()


def _take_db(key: str, rate: float, burst: float) -> float | None:
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
            left, wait = _spend(_refill(row.tokens, row.updated, now, rate, burst), rate)
            row.tokens, row.updated = left, now
            try:
                db.commit()
            except IntegrityError:
                # Another process created the same bucket first: take from it.
                db.rollback()
                if attempt:
                    raise
                continue
        return wait
    raise AssertionError("unreachable")  # pragma: no cover


def _take(key: str, rate: float, burst: float) -> float | None:
    if settings.ratelimit_backend == "db":
        return _take_db(key, rate, burst)
    return _take_memory(key, rate, burst)


def take(name: str, key: str, *, per_minute: float, burst: int) -> float | None:
    """Take one token. Returns None when allowed, else seconds until one frees."""
    return _take(f"{name}:{key}", per_minute / 60.0, float(burst))


def check(key: str, *, per_minute: float, burst: int | None = None) -> None:
    """Take one token from `key`'s bucket or raise 429 `rate_limited`.

    The bucket holds `burst` tokens (default `per_minute`, rounded up) and
    refills at `per_minute` tokens a minute: 60 an hour is `per_minute=1,
    burst=60`.
    """
    size = burst if burst is not None else max(1, math.ceil(per_minute))
    wait = _take(key, per_minute / 60.0, float(size))
    if wait is not None:
        raise ContractError(
            "rate_limited",
            429,
            "Too many requests. Try again later.",
            retry_after_s=max(1, math.ceil(wait)),
        )


def limit(
    key_fn: Callable[[Request], str | None] = client_ip,
    per_minute: float = 60.0,
    *,
    burst: int | None = None,
    name: str | None = None,
):
    """Dependency: at most `burst` calls at once, refilled at `per_minute`.

    `burst` defaults to `per_minute` (rounded up), so `limit(per_minute=10/60,
    burst=10)` means "10 per hour". Use it in `dependencies=[…]`.
    """
    size = burst if burst is not None else max(1, math.ceil(per_minute))
    bucket = name or f"bucket-{id(key_fn)}-{per_minute}-{size}"

    def dependency(request: Request) -> None:
        key = key_fn(request)
        if key is not None:
            check(f"{bucket}:{key}", per_minute=per_minute, burst=size)

    return Depends(dependency)


@periodic("ratelimit.purge", seconds=600)
def purge(now: datetime) -> None:
    """Drop shared buckets idle for an hour (every limit here refills by then)."""
    if settings.ratelimit_backend != "db":
        return
    with SessionLocal() as db:
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.updated < time.time() - 3600))
        db.commit()
