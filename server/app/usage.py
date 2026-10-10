"""Usage metering for the developer API."""

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import dialect_insert
from .models import UsageDaily


def month_bounds(today: date) -> tuple[date, date]:
    """First and last day of `today`'s calendar month."""
    start = today.replace(day=1)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    return start, date.fromordinal(nxt.toordinal() - 1)


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def used_this_month(db: Session, user_id: int, today: date | None = None) -> int:
    start, end = month_bounds(today or utc_today())
    total = db.scalar(
        select(func.coalesce(func.sum(UsageDaily.count), 0)).where(
            UsageDaily.user_id == user_id,
            UsageDaily.day >= start,
            UsageDaily.day <= end,
        )
    )
    return int(total or 0)


def record(db: Session, user_id: int, api_key_id: int, endpoint: str) -> None:
    """Add one request to today's counter (an atomic upsert on SQLite and
    Postgres alike)."""
    stmt = dialect_insert(db, UsageDaily).values(
        user_id=user_id,
        api_key_id=api_key_id,
        day=utc_today(),
        endpoint=endpoint,
        count=1,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["api_key_id", "day", "endpoint"],
        set_={"count": UsageDaily.count + 1},
    )
    db.execute(stmt)
