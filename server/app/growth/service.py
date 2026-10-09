"""Growth counts for the admin panel: sign-ups, downloads, trials and
checkouts per UTC day, from the platform's own records.

The website runs cookieless page analytics (Cloudflare Web Analytics, page
views only); conversions are never tracked in the browser. They are counted
here from rows the platform already keeps, and the answer holds counts only.

Sources:
- sign-ups: `users.created_at`
- downloads: `download_events.at` (written by `record_download`, which the
  release download endpoint calls; PF1)
- trials: `subscriptions` rows with `provider = "trial"` (PF1, contract 5.6)
- checkouts: `payments.created_at` (every checkout opened)
- paid: `payments.paid_at` of payments marked paid by a verified event
"""

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DownloadEvent, Payment, Subscription, User

METRICS = ("signups", "downloads", "trials", "checkouts", "paid")
MAX_DAYS = 366


def _utc_day(dt: datetime) -> date:
    # SQLite hands back naive datetimes; everything stored is UTC.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.date()


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    lo = datetime(start.year, start.month, start.day)
    hi = datetime(end.year, end.month, end.day) + timedelta(days=1)
    return lo, hi


def record_download(
    db: Session,
    *,
    version: str,
    platform: str,
    channel: str | None = None,
    at: datetime | None = None,
) -> DownloadEvent:
    """Count one installer download (no personal data is stored)."""
    ev = DownloadEvent(
        version=version[:32],
        platform=platform[:16],
        channel=channel[:16] if channel else None,
        at=at or datetime.now(timezone.utc),
    )
    db.add(ev)
    db.commit()
    return ev


def _count(values: Iterable[datetime | None], start: date, end: date) -> dict[date, int]:
    out: dict[date, int] = {}
    for dt in values:
        if dt is None:
            continue
        day = _utc_day(dt)
        if start <= day <= end:
            out[day] = out.get(day, 0) + 1
    return out


def daily_counts(db: Session, start: date, end: date) -> list[dict]:
    """One row per day from `start` to `end` (inclusive), zero-filled."""
    lo, hi = _bounds(start, end)
    # Naive UTC bounds compare correctly with SQLite's naive values; one
    # day of slack either side covers aware/naive drivers, and _count trims.
    lo, hi = lo - timedelta(days=1), hi + timedelta(days=1)

    def col(column, *where):
        return db.scalars(select(column).where(column >= lo, column < hi, *where))

    series = {
        "signups": _count(col(User.created_at), start, end),
        "downloads": _count(col(DownloadEvent.at), start, end),
        "trials": _count(col(Subscription.created_at, Subscription.provider == "trial"), start, end),
        "checkouts": _count(col(Payment.created_at), start, end),
        "paid": _count(col(Payment.paid_at, Payment.status == "paid"), start, end),
    }
    days = []
    day = start
    while day <= end:
        days.append({"day": day, **{m: series[m].get(day, 0) for m in METRICS}})
        day += timedelta(days=1)
    return days
