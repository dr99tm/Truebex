"""Share background jobs (registered with app.tasks on import)."""

from datetime import datetime

from sqlalchemy.orm import Session

from ..tasks import periodic
from . import service


@periodic("shares.expire", 300)
def expire_shares(db: Session, now: datetime) -> int:
    return service.expire(db, now)


@periodic("shares.purge", 3600)
def purge_shares(db: Session, now: datetime) -> int:
    return service.purge(db, now)
