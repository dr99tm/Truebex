"""Usage per member for the admin console (PF3 Scope 9): active devices, last
activity, API requests this month (`usage_daily`), floating-seat hours this
month (from leases). Cloud storage, panoramas and AI credits stay null until
PF4, PF6 and PF11 record them through `app.metering`.
"""

import re
from datetime import date, datetime, time, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock, devices
from ..models import UsageDaily, User
from ..usage import month_bounds
from .models import FloatingLease, OrgMember, Organisation

_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def parse_month(text: str | None, now: datetime) -> date:
    if not text:
        return now.date().replace(day=1)
    m = _MONTH.match(text)
    if m is None:
        raise ContractError(
            "validation_failed", 422, "month: expected YYYY-MM, like 2026-10",
            {"fields": [{"field": "month", "in": "query", "message": "expected YYYY-MM"}]},
        )
    return date(int(m.group(1)), int(m.group(2)), 1)


def _metering(subject: str, metric: str, month: date) -> int | None:
    """A metered quantity when `app.metering` exists (PF6 creates it), else None."""
    try:
        from .. import metering  # type: ignore[attr-defined]
    except ImportError:
        return None
    try:
        return int(metering.used(subject, metric, month.strftime("%Y-%m")))
    except Exception:  # noqa: BLE001  (an interface still settling: show nothing)
        return None


def per_member(db: Session, org: Organisation, month_text: str | None, now: datetime | None = None) -> dict:
    now = now or clock.now()
    month = parse_month(month_text, now)
    start, end = month_bounds(month)
    m_start = datetime.combine(start, time.min, tzinfo=timezone.utc)
    m_end = datetime.combine(end, time.max, tzinfo=timezone.utc)
    rows = db.execute(
        select(OrgMember, User).join(User, User.id == OrgMember.user_id).where(OrgMember.org_id == org.id)
    ).all()
    ids = [u.id for _, u in rows]
    requests = dict(
        db.execute(
            select(UsageDaily.user_id, func.coalesce(func.sum(UsageDaily.count), 0))
            .where(UsageDaily.user_id.in_(ids), UsageDaily.day >= start, UsageDaily.day <= end)
            .group_by(UsageDaily.user_id)
        ).all()
    ) if ids else {}
    seconds: dict[int, float] = {}
    leases = db.scalars(
        select(FloatingLease).where(
            FloatingLease.org_id == org.id,
            FloatingLease.leased_at <= m_end,
            or_(FloatingLease.released_at.is_(None), FloatingLease.released_at >= m_start),
        )
    )
    for lease in leases:
        began = max(clock.aware(lease.leased_at), m_start)
        ended = clock.aware(lease.released_at) or min(clock.aware(lease.expires_at), now)
        ended = min(ended, m_end, now)
        if ended > began:
            seconds[lease.user_id] = seconds.get(lease.user_id, 0.0) + (ended - began).total_seconds()
    members = []
    for m, user in sorted(rows, key=lambda r: (r[1].name or r[1].email).lower()):
        active = devices.active(db, user.id)
        last = max((clock.aware(d.last_seen_at) for d in active), default=None)
        subject = f"user:{user.id}"
        members.append(
            {
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "role": m.role,
                "devices": len(active),
                "last_active_at": clock.rfc3339(last),
                "api_requests": int(requests.get(user.id, 0)),
                "floating_hours": round(seconds.get(user.id, 0.0) / 3600, 1),
                "storage_bytes": _metering(subject, "storage_bytes", month),
                "panoramas": _metering(subject, "panoramas", month),
                "ai_credits": _metering(subject, "ai_credits", month),
            }
        )
    return {"month": month.strftime("%Y-%m"), "members": members}
