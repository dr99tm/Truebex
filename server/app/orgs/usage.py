"""Usage per member for the admin console (PF3 Scope 9): active devices, last
activity, API requests this month (`usage_daily`), floating-seat hours this
month (from leases), and (PF3b) each member's own cloud storage, panoramas
and AI credits:

* storage_bytes: PF4's `cloud_bytes` figure (`projects.quotas.bytes_used`)
  for the current month; null for any other, since storage is a level and
  no history of it is kept.
* panoramas: the member's `panorama` render jobs (PF6) that reached
  `succeeded` in the month. A followed set's `tiles` updates refresh a
  panorama already counted, so they do not count.
* ai_credits: credits spent in the month (PF11's ledger): `usage` rows
  minus `refund` rows, as a positive number (never below 0).

All three read the member's personal account (account_kind "user"); one
grouped query per column covers every member.
"""

import re
from datetime import date, datetime, time, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..ai.models import AiCreditLedger
from ..contract_http import ContractError
from ..licence import clock, devices
from ..models import UsageDaily, User
from ..projects import quotas
from ..render.models import RenderJob
from ..usage import month_bounds
from .models import FloatingLease, OrgMember, Organisation

ACCOUNT_KIND = "user"

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


def window(month: date) -> tuple[datetime, datetime]:
    """The month's first and last instant, UTC (every column's bounds)."""
    start, end = month_bounds(month)
    return datetime.combine(start, time.min, tzinfo=timezone.utc), datetime.combine(end, time.max, tzinfo=timezone.utc)


def panoramas(db: Session, user_ids: list[int], m_start: datetime, m_end: datetime) -> dict[int, int]:
    """{user_id: panorama jobs that succeeded in [m_start, m_end]}."""
    if not user_ids:
        return {}
    rows = db.execute(
        select(RenderJob.account_id, func.count())
        .where(
            RenderJob.account_kind == ACCOUNT_KIND,
            RenderJob.account_id.in_(user_ids),
            RenderJob.kind == "panorama",
            RenderJob.state == "succeeded",
            RenderJob.finished_at >= m_start,
            RenderJob.finished_at <= m_end,
        )
        .group_by(RenderJob.account_id)
    ).all()
    return {int(uid): int(n) for uid, n in rows}


def ai_credits(db: Session, user_ids: list[int], m_start: datetime, m_end: datetime) -> dict[int, int]:
    """{user_id: credits spent in [m_start, m_end]}: `usage` rows carry a
    negative delta and `refund` rows a positive one, so spent = -sum."""
    if not user_ids:
        return {}
    rows = db.execute(
        select(AiCreditLedger.account_id, func.coalesce(func.sum(AiCreditLedger.delta), 0))
        .where(
            AiCreditLedger.account_kind == ACCOUNT_KIND,
            AiCreditLedger.account_id.in_(user_ids),
            AiCreditLedger.kind.in_(("usage", "refund")),
            AiCreditLedger.at >= m_start,
            AiCreditLedger.at <= m_end,
        )
        .group_by(AiCreditLedger.account_id)
    ).all()
    return {int(uid): max(0, -int(total or 0)) for uid, total in rows}


def per_member(db: Session, org: Organisation, month_text: str | None, now: datetime | None = None) -> dict:
    now = now or clock.now()
    month = parse_month(month_text, now)
    start, end = month_bounds(month)
    m_start, m_end = window(month)
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
    current = month == now.date().replace(day=1)
    storage = quotas.bytes_used_by(db, ids) if current else None
    renders = panoramas(db, ids, m_start, m_end)
    credits = ai_credits(db, ids, m_start, m_end)
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
                "storage_bytes": None if storage is None else storage.get(user.id, 0),
                "panoramas": renders.get(user.id, 0),
                "ai_credits": credits.get(user.id, 0),
            }
        )
    return {"month": month.strftime("%Y-%m"), "members": members}
