"""Licence background jobs (registered with app.tasks on import)."""

from datetime import datetime

from ..database import SessionLocal
from ..tasks import periodic
from . import devices, links


@periodic("licence.links.purge", 600)
def purge_links(now: datetime) -> int:
    with SessionLocal() as db:
        n = links.purge(db, now)
        db.commit()
        return n


@periodic("licence.devices.lapse", 24 * 3600)
def lapse_devices(now: datetime) -> int:
    with SessionLocal() as db:
        n = devices.lapse_unused(db, now)
        db.commit()
        return n
