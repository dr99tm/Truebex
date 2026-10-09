"""Organisation background jobs (registered with app.tasks on import)."""

from datetime import datetime

from sqlalchemy.orm import Session

from ..tasks import periodic
from . import audit, seats, service


@periodic("licence.leases.expire", 60)
def expire_leases(db: Session, now: datetime) -> int:
    return seats.expire_leases(db, now)


@periodic("orgs.invites.expire", 24 * 3600)
def expire_invites(db: Session, now: datetime) -> int:
    return service.expire_invites(db, now)


@periodic("audit.purge", 24 * 3600)
def purge_audit(db: Session, now: datetime) -> int:
    return audit.purge(db, now)
