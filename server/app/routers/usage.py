"""Usage reporting for the dashboard (session-authenticated)."""

from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..billing.service import effective_plan
from ..database import get_db
from ..deps import get_current_user
from ..models import ApiKey, UsageDaily, User
from ..plans import get_plan
from ..schemas import UsageDay, UsageSummary
from ..usage import month_bounds, utc_today

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageSummary)
def usage_summary(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UsageSummary:
    plan = get_plan(effective_plan(db, current))
    start, end = month_bounds(utc_today())
    rows = db.execute(
        select(UsageDaily, ApiKey.name)
        .join(ApiKey, ApiKey.id == UsageDaily.api_key_id)
        .where(
            UsageDaily.user_id == current.id,
            UsageDaily.day >= start,
            UsageDaily.day <= end,
        )
    ).all()

    per_day: dict = defaultdict(int)
    by_endpoint: dict[str, int] = defaultdict(int)
    by_key: dict[str, int] = defaultdict(int)
    for row, key_name in rows:
        per_day[row.day] += row.count
        by_endpoint[row.endpoint] += row.count
        by_key[key_name] += row.count

    # Every day of the month so far, zeros included, for the chart.
    today = utc_today()
    daily = [
        UsageDay(day=start + timedelta(days=i), count=per_day.get(start + timedelta(days=i), 0))
        for i in range((today - start).days + 1)
    ]
    used = sum(per_day.values())
    return UsageSummary(
        plan=plan.id,
        period_start=start,
        period_end=end,
        used=used,
        limit=plan.monthly_requests,
        remaining=max(plan.monthly_requests - used, 0),
        daily=daily,
        by_endpoint=dict(by_endpoint),
        by_key=dict(by_key),
    )
