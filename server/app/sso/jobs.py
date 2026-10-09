"""SSO background jobs (registered with app.tasks on import)."""

from datetime import datetime

from sqlalchemy.orm import Session

from ..tasks import periodic
from . import service


@periodic("sso.requests.purge", 600)
def purge_requests(db: Session, now: datetime) -> int:
    return service.purge(db, now)
