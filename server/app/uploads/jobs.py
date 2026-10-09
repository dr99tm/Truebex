"""Upload background jobs (registered with app.tasks on import)."""

from datetime import datetime

from sqlalchemy.orm import Session

from ..tasks import periodic
from . import service


@periodic("uploads.expire", 3600)
def expire_uploads(db: Session, now: datetime) -> int:
    return service.expire(db, now)
