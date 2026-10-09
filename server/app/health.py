"""GET /health/deep: what the external uptime checks watch (PF14).

200 `{"db": "ok", "storage": "ok", "worker_heartbeat_s": 12}` when the
database answers, a storage round trip works and (unless BACKGROUND_TASKS=off)
the worker beat within the last 120 s; otherwise 503 with the same body.
Rate-limited per address; `/health` stays the cheap liveness check.
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import ops
from .config import get_settings
from .database import engine
from .ratelimit import client_address, limit
from .storage import get_store

log = logging.getLogger("truebex.health")
settings = get_settings()
router = APIRouter(tags=["meta"])

HEARTBEAT_MAX_S = 120
_PROBE = "health/deep-check.txt"


def check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        log.exception("health: database")
        return False


def check_storage() -> bool:
    """Read a probe object back (written once, so a versioned bucket does
    not collect a new version every minute)."""
    try:
        store = get_store()
        if store.stat(_PROBE) is None:
            store.put(_PROBE, b"ok", content_type="text/plain")
        with store.open(_PROBE) as fh:
            return fh.read() == b"ok"
    except Exception:  # noqa: BLE001
        log.exception("health: storage")
        return False


def heartbeat() -> int | None:
    try:
        return ops.heartbeat_age_s()
    except Exception:  # noqa: BLE001
        return None


@router.get("/health/deep", dependencies=[Depends(limit(client_address, per_minute=30, scope="health"))])
def health_deep() -> JSONResponse:
    db_ok = check_db()
    storage_ok = check_storage()
    beat = heartbeat()
    worker_ok = settings.background_tasks == "off" or (beat is not None and beat <= HEARTBEAT_MAX_S)
    body = {
        "db": "ok" if db_ok else "error",
        "storage": "ok" if storage_ok else "error",
        "worker_heartbeat_s": beat,
    }
    return JSONResponse(
        body,
        status_code=200 if db_ok and storage_ok and worker_ok else 503,
        headers={"Cache-Control": "no-store"},
    )
