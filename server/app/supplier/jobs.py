"""The supplier portal's background jobs (registered with app.tasks; main.py
imports this module, which also registers the e-mail and analytics
listeners on the marketplace's events)."""

from datetime import datetime

from sqlalchemy.orm import Session

from ..tasks import periodic
from . import analytics as _analytics  # noqa: F401  (registers the count listeners)
from . import applications as _applications  # noqa: F401  (registers the decision e-mails)
from . import feeds, imports, listing
from . import notify as _notify  # noqa: F401  (registers the order e-mails)


@periodic("market.feeds.run", 30)
def run_feeds(db: Session, now: datetime) -> int:
    """Queued feed runs (5.11 uploads, portal applies, daily pulls), one per supplier at a time."""
    return len(feeds.run_queued(db))


# Checked every minute; each source is fetched once a day at FEED_PULL_HOUR_UTC.
@periodic("market.feeds.pull", 60)
def pull_feeds(db: Session, now: datetime) -> int:
    return feeds.pull_due(db, now)


@periodic("supplier.imports.purge", 24 * 3600)
def purge_dry_runs(db: Session, now: datetime) -> int:
    return imports.purge(db, now)


@periodic("supplier.listing.sync", 600)
def sync_listing(db: Session, now: datetime) -> int:
    return listing.sync(db, now)
