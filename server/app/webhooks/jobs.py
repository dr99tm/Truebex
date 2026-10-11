"""Webhook jobs (PF12; registered with app.tasks, imported by tasks._load_jobs
and, through the /v1 routers, by main.py). Importing this also installs the
event sources (`observe`)."""

from datetime import datetime

from ..database import SessionLocal
from ..tasks import periodic
from . import delivery, events
from . import observe as _observe  # noqa: F401  (the push hook and the session observer)


@periodic("webhooks.deliver", 5)
def deliver(now: datetime) -> int:
    """Close due `project.ops_appended` windows, then send due deliveries."""
    with SessionLocal() as db:
        events.flush_ops(db, now)
        return delivery.deliver_due(db, now)


# Checked every 10 minutes; sends once a day after 00:10 UTC.
@periodic("webhooks.digest", 600)
def digest(now: datetime) -> int:
    with SessionLocal() as db:
        return events.digest(db, now)


@periodic("webhooks.disable", 3600)
def disable(now: datetime) -> int:
    with SessionLocal() as db:
        return delivery.disable_failing(db, now)


@periodic("webhooks.purge", 24 * 3600)
def purge(now: datetime) -> int:
    with SessionLocal() as db:
        return delivery.purge(db, now)
