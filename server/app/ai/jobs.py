"""AI background jobs (registered with app.tasks on import).

ai.allowance.grant   hourly     accounts whose month turned: unused allowance expires, the new one is granted
ai.servers.scale     every 60 s self-hosted inference servers probed; gpu-ai machines wanted
ai.usage.expire      daily      usage records older than 400 days deleted
ai.keys.expire       every 10 min  Idempotency-Keys older than 10 minutes, stale in-flight turns

The grant also happens lazily the first time an account is seen in a new
month, so a stopped worker never costs anyone their allowance; the ledger is
unique per month, so running both is safe.
"""

from datetime import datetime, timedelta

from sqlalchemy import delete

from ..database import SessionLocal
from ..tasks import periodic
from . import credits, servers, topups  # noqa: F401  (topups: the billing PAID_HOOK)
from .models import AiRequestKey, AiTurn, AiUsage
from .proxy import KEY_WINDOW, TURN_STALE


@periodic("ai.allowance.grant", 3600)
def allowance_grant(now: datetime) -> int:
    with SessionLocal() as db:
        return credits.roll_due(db, now)


@periodic("ai.servers.scale", 60)
def servers_scale(now: datetime) -> dict:
    with SessionLocal() as db:
        return servers.scale(db, now)


@periodic("ai.usage.expire", 24 * 3600)
def usage_expire(now: datetime) -> int:
    with SessionLocal() as db:
        res = db.execute(delete(AiUsage).where(AiUsage.at < now - timedelta(days=credits.retention_days())))
        db.commit()
        return res.rowcount or 0


@periodic("ai.keys.expire", 600)
def keys_expire(now: datetime) -> int:
    with SessionLocal() as db:
        keys = db.execute(delete(AiRequestKey).where(AiRequestKey.created_at < now - KEY_WINDOW)).rowcount or 0
        turns = db.execute(delete(AiTurn).where(AiTurn.started_at < now - TURN_STALE)).rowcount or 0
        db.commit()
        return keys + turns
