"""Admin: growth counts (sign-ups, downloads, trials, checkouts per day)."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..growth.service import MAX_DAYS, METRICS, daily_counts
from ..models import User
from ..schemas import GrowthOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/growth", response_model=GrowthOut)
def growth(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GrowthOut:
    """Daily conversions between `from` and `to` (UTC days, inclusive;
    the last 30 days by default). Counts only, never personal data."""
    end = to or datetime.now(timezone.utc).date()
    start = from_ or end - timedelta(days=29)
    if start > end:
        raise HTTPException(status_code=422, detail="`from` must not be after `to`.")
    if (end - start).days + 1 > MAX_DAYS:
        raise HTTPException(
            status_code=422, detail=f"Ask for at most {MAX_DAYS} days at a time."
        )
    days = daily_counts(db, start, end)
    totals = {m: sum(d[m] for d in days) for m in METRICS}
    return GrowthOut(from_=start, to=end, days=days, totals=totals)
