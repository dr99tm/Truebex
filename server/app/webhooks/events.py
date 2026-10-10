"""Webhook events (PF12): the types, `emit`, and the two that are built over
time (the debounced `project.ops_appended` and the daily visits digest).

An event's body is `{"type", "timestamp", "data"}`; `data` is the resource as
its contract shapes it, what the account's own API reads would return.
"""

import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..licence import clock
from ..licence.ids import uuid7_hex
from .models import WebhookDelivery, WebhookEndpoint, WebhookEvent, WebhookPendingOps

log = logging.getLogger("truebex.webhooks")

EVENT_TYPES: tuple[str, ...] = (
    "project.ops_appended",
    "project.version_created",
    "project.member_added",
    "job.succeeded",
    "job.failed",
    "share.published",
    "share.visits_daily",
    "market.order.updated",
    "market.feed.completed",
)
TEST_EVENT = "webhook.test"
DESCRIPTIONS: dict[str, str] = {
    "project.ops_appended": "Operations were accepted (one event per 30 s per project: first and last numbers, authors).",
    "project.version_created": "A version was named.",
    "project.member_added": "Someone was invited to a project.",
    "job.succeeded": "A render job of the account succeeded.",
    "job.failed": "A render job of the account failed.",
    "share.published": "A share went live.",
    "share.visits_daily": "Yesterday's visits to the account's shares (00:10 UTC).",
    "market.order.updated": "An order or request for quote of the account changed state.",
    "market.feed.completed": "A catalogue feed run of the account's supplier ended.",
}
OPS_DEBOUNCE = timedelta(seconds=30)
MAX_AUTHORS = 50


def new_event_id() -> str:
    return "msg_" + uuid7_hex()


def _iso(dt: datetime) -> str:
    return clock.rfc3339(dt)


def subscribed(db: Session, account_id: int, event_type: str) -> list[WebhookEndpoint]:
    rows = db.scalars(
        select(WebhookEndpoint).where(WebhookEndpoint.account_id == account_id, WebhookEndpoint.active.is_(True))
    ).all()
    return [e for e in rows if event_type in (e.events or [])]


def emit(
    db: Session,
    account_ids,
    event_type: str,
    data: dict,
    *,
    now: datetime | None = None,
    endpoints: list[WebhookEndpoint] | None = None,
) -> list[WebhookEvent]:
    """One event per account with a subscribed endpoint, and one pending
    delivery per such endpoint (due now). Commits. Accounts without one get
    nothing stored."""
    now = now or clock.now()
    made: list[WebhookEvent] = []
    for account_id in dict.fromkeys(a for a in account_ids if a is not None):
        targets = endpoints if endpoints is not None else subscribed(db, account_id, event_type)
        targets = [e for e in targets if e.account_id == account_id]
        if not targets:
            continue
        event = WebhookEvent(
            event_id=new_event_id(),
            type=event_type,
            account_id=account_id,
            payload={"type": event_type, "timestamp": _iso(now), "data": data},
            created_at=now,
        )
        db.add(event)
        for endpoint in targets:
            db.add(
                WebhookDelivery(
                    delivery_id=secrets.token_hex(16),
                    endpoint_id=endpoint.endpoint_id,
                    event_id=event.event_id,
                    attempt=1,
                    status="pending",
                    next_attempt_at=now,
                    created_at=now,
                )
            )
        made.append(event)
    if made:
        db.commit()
        log.info("webhook %s for %d account(s)", event_type, len(made))
    return made


# --- who hears about what ---------------------------------------------------------------


def project_accounts(db: Session, project_id: str) -> list[int]:
    from ..projects.models import ProjectMember

    return [
        uid
        for uid in db.scalars(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project_id, ProjectMember.state == "active", ProjectMember.user_id.is_not(None)
            )
        )
    ]


def supplier_accounts(db: Session, supplier_id: str) -> list[int]:
    from ..market.models import SupplierMember

    return list(db.scalars(select(SupplierMember.user_id).where(SupplierMember.supplier_id == supplier_id)))


def any_endpoint(db: Session, account_ids: list[int], event_type: str) -> bool:
    if not account_ids:
        return False
    return any(subscribed(db, a, event_type) for a in dict.fromkeys(account_ids))


# --- project.ops_appended (debounced 30 s) -----------------------------------------------


def note_ops(db: Session, project_id: str, ops: list[dict], *, now: datetime | None = None) -> None:
    """Widen the project's open window (or open one) with these accepted operations."""
    if not ops:
        return
    now = now or clock.now()
    seqs = [int(o["server_seq"]) for o in ops if o.get("server_seq")]
    if not seqs:
        return
    authors = [{"author": o.get("author"), "author_kind": o.get("author_kind")} for o in ops]
    for attempt in range(2):
        row = db.get(WebhookPendingOps, project_id)
        if row is None:
            if not any_endpoint(db, project_accounts(db, project_id), "project.ops_appended"):
                return
            row = WebhookPendingOps(
                project_id=project_id,
                first_seq=min(seqs),
                last_seq=max(seqs),
                count=0,
                authors=[],
                first_at=now,
                due_at=now + OPS_DEBOUNCE,
            )
            db.add(row)
        row.first_seq = min(row.first_seq, *seqs)
        row.last_seq = max(row.last_seq, *seqs)
        row.count = (row.count or 0) + len(seqs)
        known = list(row.authors or [])
        for a in authors:
            if a not in known and len(known) < MAX_AUTHORS:
                known.append(a)
        row.authors = known
        try:
            db.commit()
            return
        except IntegrityError:
            db.rollback()  # another push opened the window first: widen it
            if attempt:
                raise


def flush_ops(db: Session, now: datetime | None = None) -> int:
    """Send `project.ops_appended` for every window that has closed."""
    from ..projects.models import Project

    now = now or clock.now()
    due = list(db.scalars(select(WebhookPendingOps).where(WebhookPendingOps.due_at <= now)))
    sent = 0
    for row in due:
        project = db.get(Project, row.project_id)
        data = {
            "project_id": row.project_id,
            "name": project.name if project else None,
            "first_seq": row.first_seq,
            "last_seq": row.last_seq,
            "count": row.count,
            "head_seq": project.head_seq if project else row.last_seq,
            "authors": row.authors or [],
            "first_at": _iso(row.first_at),
        }
        accounts = project_accounts(db, row.project_id) if project is not None and project.deleted_at is None else []
        db.execute(delete(WebhookPendingOps).where(WebhookPendingOps.project_id == row.project_id))
        db.commit()
        if accounts:
            sent += len(emit(db, accounts, "project.ops_appended", data, now=now))
    return sent


# --- share.visits_daily ------------------------------------------------------------------


DIGEST_AT = (0, 10)  # 00:10 UTC
DIGEST_MARK = "webhooks.digest"


def digest(db: Session, now: datetime | None = None, *, force: bool = False) -> int:
    """Once a day after 00:10 UTC: each subscribed account's shares with visits
    yesterday (UTC), one event per account."""
    from ..models import OpsStatus
    from ..shares.models import Share, ShareVisit
    from ..shares.service import share_url

    now = now or clock.now()
    day = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if not force and (now.hour, now.minute) < DIGEST_AT:
        return 0
    mark = db.get(OpsStatus, DIGEST_MARK)
    if mark is not None and mark.detail == day and not force:
        return 0
    accounts = sorted(
        {
            e.account_id
            for e in db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.active.is_(True)))
            if "share.visits_daily" in (e.events or [])
        }
    )
    sent = 0
    for account_id in accounts:
        rows = db.execute(
            select(Share.share_id, Share.title, Share.slug, func.sum(ShareVisit.count), func.count(ShareVisit.id))
            .join(ShareVisit, ShareVisit.share_id == Share.share_id)
            .where(Share.account_id == account_id, ShareVisit.day == day)
            .group_by(Share.share_id, Share.title, Share.slug)
            .order_by(Share.share_id)
        ).all()
        if not rows:
            continue
        shares = [
            {"share_id": sid, "title": title, "url": share_url(slug), "visits": int(total or 0), "unique": int(unique or 0)}
            for sid, title, slug, total, unique in rows
        ]
        data = {"day": day, "visits": sum(s["visits"] for s in shares), "unique": sum(s["unique"] for s in shares), "shares": shares}
        sent += len(emit(db, [account_id], "share.visits_daily", data, now=now))
    if mark is None:
        mark = OpsStatus(name=DIGEST_MARK, at=now, detail=day)
        db.add(mark)
    mark.at, mark.detail = now, day
    db.commit()
    return sent
