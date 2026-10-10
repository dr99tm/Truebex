"""The organisation audit log: `audit_events` (organisation actions: members,
roles, invites, seats, leases, SSO, policy) unioned with PF1's append-only
`licence_events` of the organisation's members since they joined
(activations, removals, trials). Newest first, filterable by kind (a kind or
a prefix: `lease` matches `lease.taken`), paged by an opaque cursor,
exportable as CSV, kept `AUDIT_RETENTION_DAYS` (24 months).
"""

import base64
import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, false, or_, select, true
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock
from ..licence.models import LicenceEvent
from ..models import User
from .models import AuditEvent, OrgMember

# Order: (at, source rank, id) descending; organisation events rank above
# licence events at the same instant.
_ORG, _LIC = 1, 0
PAGE = 50
CSV_MAX = 50_000


def record(
    db: Session,
    org_id: str,
    kind: str,
    *,
    actor: int | None = None,
    target_kind: str | None = None,
    target_id: str | int | None = None,
    at: datetime | None = None,
    **details,
) -> AuditEvent:
    """Add one organisation event to the session (the caller commits)."""
    event = AuditEvent(
        at=at or clock.now(),
        org_id=org_id,
        actor_user_id=actor,
        kind=kind,
        target_kind=target_kind,
        target_id=None if target_id is None else str(target_id),
        details=details,
    )
    db.add(event)
    return event


def retention_start(now: datetime) -> datetime:
    return now - timedelta(days=get_settings().audit_retention_days)


def purge(db: Session, now: datetime) -> int:
    """The audit.purge job: organisation events older than the retention.
    (licence_events are PF1's and append-only; the view hides older rows.)"""
    result = db.execute(delete(AuditEvent).where(AuditEvent.at < retention_start(now)))
    return result.rowcount or 0


@dataclass(frozen=True)
class Cursor:
    at: datetime
    rank: int
    id: int

    def encode(self) -> str:
        raw = json.dumps({"at": self.at.isoformat(), "r": self.rank, "id": self.id}).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    @classmethod
    def decode(cls, text: str) -> "Cursor":
        try:
            data = json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)))
            return cls(clock.aware(datetime.fromisoformat(data["at"])), int(data["r"]), int(data["id"]))
        except (ValueError, KeyError, TypeError):
            raise ContractError(
                "validation_failed", 422, "cursor: not a cursor from this list",
                {"fields": [{"field": "cursor", "in": "query", "message": "invalid cursor"}]},
            )


def _kind_filter(column, kind: str | None):
    if not kind:
        return true()
    return or_(column == kind, column.like(f"{kind}.%"))


def _before(at_col, id_col, rank: int, cursor: Cursor | None):
    if cursor is None:
        return true()
    if rank == cursor.rank:
        same_instant = and_(at_col == cursor.at, id_col < cursor.id)
    else:
        same_instant = at_col == cursor.at if rank < cursor.rank else false()
    return or_(at_col < cursor.at, same_instant)


def _users(db: Session, ids: set[int]) -> dict[int, User]:
    if not ids:
        return {}
    return {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))}


def events(
    db: Session,
    org_id: str,
    *,
    kind: str | None = None,
    cursor: Cursor | None = None,
    limit: int = PAGE,
    now: datetime | None = None,
) -> tuple[list[dict], str | None]:
    now = now or clock.now()
    since = retention_start(now)
    org_rows = list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.org_id == org_id,
                AuditEvent.at >= since,
                _kind_filter(AuditEvent.kind, kind),
                _before(AuditEvent.at, AuditEvent.id, _ORG, cursor),
            )
            .order_by(AuditEvent.at.desc(), AuditEvent.id.desc())
            .limit(limit + 1)
        )
    )
    lic_rows = list(
        db.scalars(
            select(LicenceEvent)
            .join(
                OrgMember,
                and_(
                    OrgMember.user_id == LicenceEvent.user_id,
                    OrgMember.org_id == org_id,
                    LicenceEvent.at >= OrgMember.joined_at,
                ),
            )
            .where(
                LicenceEvent.at >= since,
                _kind_filter(LicenceEvent.kind, kind),
                _before(LicenceEvent.at, LicenceEvent.id, _LIC, cursor),
            )
            .order_by(LicenceEvent.at.desc(), LicenceEvent.id.desc())
            .limit(limit + 1)
        )
    )
    merged = [(clock.aware(r.at), _ORG, r.id, r) for r in org_rows] + [
        (clock.aware(r.at), _LIC, r.id, r) for r in lic_rows
    ]
    merged.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    page, more = merged[:limit], len(merged) > limit
    users = _users(
        db,
        {r.actor_user_id for _, rank, _, r in page if rank == _ORG and r.actor_user_id}
        | {r.user_id for _, rank, _, r in page if rank == _LIC and r.user_id},
    )
    out = [_json(r, rank, users) for _, rank, _, r in page]
    nxt = Cursor(page[-1][0], page[-1][1], page[-1][2]).encode() if more and page else None
    return out, nxt


def _actor(users: dict[int, User], user_id: int | None) -> dict | None:
    if user_id is None:
        return None
    user = users.get(user_id)
    return {"user_id": user_id, "email": user.email if user else None}


def _json(row, rank: int, users: dict[int, User]) -> dict:
    if rank == _ORG:
        target = {"kind": row.target_kind, "id": row.target_id} if row.target_kind else None
        return {
            "id": f"o{row.id}",
            "at": clock.rfc3339(row.at),
            "actor": _actor(users, row.actor_user_id),
            "kind": row.kind,
            "target": target,
            "details": row.details or {},
        }
    return {
        "id": f"l{row.id}",
        "at": clock.rfc3339(row.at),
        "actor": _actor(users, row.user_id),
        "kind": row.kind,
        "target": {"kind": "device", "id": row.device_id} if row.device_id else None,
        "details": row.details or {},
    }


def all_events(db: Session, org_id: str, *, kind: str | None = None, now: datetime | None = None) -> list[dict]:
    rows: list[dict] = []
    cursor = None
    while len(rows) < CSV_MAX:
        page, nxt = events(db, org_id, kind=kind, cursor=cursor, limit=500, now=now)
        rows.extend(page)
        if not nxt:
            break
        cursor = Cursor.decode(nxt)
    return rows[:CSV_MAX]


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(["at", "actor", "kind", "target", "details"])
    for e in rows:
        actor = (e["actor"] or {}).get("email") or (e["actor"] or {}).get("user_id") or ""
        target = f"{e['target']['kind']}:{e['target']['id']}" if e["target"] else ""
        details = json.dumps(e["details"], sort_keys=True, separators=(",", ":")) if e["details"] else ""
        writer.writerow([_cell(str(v)) for v in (e["at"], actor, e["kind"], target, details)])
    return buf.getvalue()


def _cell(text: str) -> str:
    # A spreadsheet must never read a cell as a formula (CSV injection).
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text
