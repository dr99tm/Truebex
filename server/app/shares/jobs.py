"""Share background jobs (registered with app.tasks on import)."""

from datetime import datetime

from ..database import SessionLocal
from ..tasks import periodic
from . import service


@periodic("shares.expire", 300)
def expire_shares(now: datetime) -> int:
    with SessionLocal() as db:
        n = service.expire(db, now)
        db.commit()
        return n


@periodic("shares.purge", 3600)
def purge_shares(now: datetime) -> int:
    with SessionLocal() as db:
        n = service.purge(db, now)
        db.commit()
        return n
