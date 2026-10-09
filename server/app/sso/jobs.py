"""SSO background jobs (registered with app.tasks on import)."""

from datetime import datetime

from ..database import SessionLocal
from ..tasks import periodic
from . import service


@periodic("sso.requests.purge", 600)
def purge_requests(now: datetime) -> int:
    with SessionLocal() as db:
        n = service.purge(db, now)
        db.commit()
        return n
