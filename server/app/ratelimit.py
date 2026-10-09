"""Rate limiting (PF14 §Design Plumbing; first user PF1).

`limit(key_fn, per_minute)` is a FastAPI dependency backed by in-process
token buckets (RATELIMIT_BACKEND=memory). PF14 swaps in Postgres-backed
buckets when the API runs more than one process. A refused call answers 429
`rate_limited` with `retry_after_s`.
"""

import math
import threading
import time
from collections.abc import Callable

from fastapi import Depends, Request

from .contract_http import ContractError

# Patched by tests to move time.
clock: Callable[[], float] = time.monotonic

_lock = threading.Lock()
# (bucket name, key) -> (tokens, last refill time)
_buckets: dict[tuple[str, str], tuple[float, float]] = {}

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def reset() -> None:
    with _lock:
        _buckets.clear()


def client_ip(request: Request) -> str:
    """The caller's address. Behind the Cloudflare tunnel every request
    arrives from loopback; Cloudflare sets CF-Connecting-IP (and overwrites
    any value a client sends), so it is trusted only from loopback."""
    peer = request.client.host if request.client else "unknown"
    if peer in _LOOPBACK:
        forwarded = request.headers.get("cf-connecting-ip")
        if forwarded:
            return forwarded.strip()[:64]
    return peer


def take(name: str, key: str, *, per_minute: float, burst: int) -> float | None:
    """Take one token. Returns None when allowed, else seconds until one frees."""
    rate = per_minute / 60.0
    now = clock()
    with _lock:
        tokens, last = _buckets.get((name, key), (float(burst), now))
        tokens = min(float(burst), tokens + (now - last) * rate)
        if tokens >= 1.0:
            _buckets[(name, key)] = (tokens - 1.0, now)
            return None
        _buckets[(name, key)] = (tokens, now)
        return (1.0 - tokens) / rate if rate > 0 else math.inf


def limit(
    key_fn: Callable[[Request], str] = client_ip,
    per_minute: float = 60.0,
    *,
    burst: int | None = None,
    name: str | None = None,
):
    """Dependency: at most `burst` calls at once, refilled at `per_minute`.

    `burst` defaults to `per_minute` (rounded up), so `limit(per_minute=10/60,
    burst=10)` means "10 per hour".
    """
    size = burst if burst is not None else max(1, math.ceil(per_minute))
    bucket = name or f"bucket-{id(key_fn)}-{per_minute}-{size}"

    def dependency(request: Request) -> None:
        wait = take(bucket, key_fn(request), per_minute=per_minute, burst=size)
        if wait is not None:
            retry = max(1, math.ceil(wait))
            raise ContractError(
                "rate_limited",
                429,
                "Too many requests. Try again later.",
                retry_after_s=retry,
            )

    return Depends(dependency)
