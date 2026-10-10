"""Organisation background jobs (registered with app.tasks on import)."""

from datetime import datetime

from ..database import SessionLocal
from ..tasks import periodic
from . import audit, seats, service


@periodic("licence.leases.expire", 60)
def expire_leases(now: datetime) -> int:
    with SessionLocal() as db:
        n = seats.expire_leases(db, now)
        db.commit()
        return n


@periodic("orgs.invites.expire", 24 * 3600)
def expire_invites(now: datetime) -> int:
    with SessionLocal() as db:
        n = service.expire_invites(db, now)
        db.commit()
        return n


@periodic("audit.purge", 24 * 3600)
def purge_audit(now: datetime) -> int:
    with SessionLocal() as db:
        n = audit.purge(db, now)
        db.commit()
        return n
