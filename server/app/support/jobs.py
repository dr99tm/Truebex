"""Support API background jobs (registered with app.tasks on import)."""

from datetime import datetime

from ..database import SessionLocal
from ..tasks import periodic
from . import codes


@periodic("support.codes.purge", 600)
def purge_codes(now: datetime) -> int:
    with SessionLocal() as db:
        n = codes.purge(db, now)
        db.commit()
        return n
