"""Upload background jobs (registered with app.tasks on import)."""

from datetime import datetime

from ..database import SessionLocal
from ..tasks import periodic
from . import service


@periodic("uploads.expire", 3600)
def expire_uploads(now: datetime) -> int:
    with SessionLocal() as db:
        return service.expire(db, now)
