"""Licence background jobs (registered with app.tasks on import)."""

from datetime import datetime

from sqlalchemy.orm import Session

from ..tasks import periodic
from . import devices, links


@periodic("licence.links.purge", 600)
def purge_links(db: Session, now: datetime) -> int:
    return links.purge(db, now)


@periodic("licence.devices.lapse", 24 * 3600)
def lapse_devices(db: Session, now: datetime) -> int:
    return devices.lapse_unused(db, now)
