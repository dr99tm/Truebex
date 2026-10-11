"""Where webhook events come from (PF12), without the features that cause them
calling in:

* PF4's push hook (`projects.hooks.on_ops_accepted`) → the 30 s window of
  `project.ops_appended` (`events.note_ops`).
* A session observer. `after_flush` notes the rows that matter: a render job
  whose state became `succeeded` or `failed`, a share that went `live`, a new
  version, a new (non-owner) project member, an order or a supplier's part of
  one changing state, a feed run that ended. `after_commit` builds each event
  from the committed rows in a session of its own; `after_rollback` forgets
  them. So an event is only sent for a change that was saved, and a failing
  event never undoes the change (it is logged and recorded instead).

`enabled = False` stops the observer (bulk copies such as
scripts/sqlite_to_postgres.py).
"""

import logging

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..projects import hooks

log = logging.getLogger("truebex.webhooks")

enabled = True
_KEY = "pf12_webhook_changes"


def _changed_to(obj, attr: str) -> object | None:
    hist = inspect(obj).attrs[attr].history
    return hist.added[0] if hist.added else None


def _note(session: Session, item: tuple) -> None:
    pending = session.info.setdefault(_KEY, [])
    if item not in pending:
        pending.append(item)


def _collect(session: Session, _flush_context) -> None:
    if not enabled:
        return
    from ..market.models import FeedRun, MarketOrder, MarketOrderSupplier
    from ..projects.models import ProjectMember, ProjectVersion
    from ..render.models import RenderJob
    from ..shares.models import Share

    try:
        for obj in session.new:
            if isinstance(obj, ProjectVersion):
                _note(session, ("version", obj.version_id))
            elif isinstance(obj, ProjectMember) and obj.role != "owner":
                _note(session, ("member", obj.id))
            elif isinstance(obj, MarketOrder):
                _note(session, ("order", obj.order_id))
            elif isinstance(obj, Share) and obj.state == "live":
                _note(session, ("share", obj.share_id))
        for obj in session.dirty:
            if isinstance(obj, RenderJob):
                state = _changed_to(obj, "state")
                if state in ("succeeded", "failed"):
                    _note(session, ("job", obj.job_id, state))
            elif isinstance(obj, Share):
                if _changed_to(obj, "state") == "live":
                    _note(session, ("share", obj.share_id))
            elif isinstance(obj, MarketOrder):
                if _changed_to(obj, "state") is not None:
                    _note(session, ("order", obj.order_id))
            elif isinstance(obj, MarketOrderSupplier):
                if _changed_to(obj, "state") is not None:
                    _note(session, ("order", obj.order_id))
            elif isinstance(obj, FeedRun):
                if _changed_to(obj, "state") in ("done", "failed") and not obj.dry_run:
                    _note(session, ("feed", obj.feed_id))
    except Exception:  # noqa: BLE001 - never fail the flush of someone else's change
        log.exception("webhook observer (flush)")


def _forget(session: Session, *_args) -> None:
    session.info.pop(_KEY, None)


def _after_commit(session: Session) -> None:
    pending = session.info.pop(_KEY, None)
    if not pending or not enabled:
        return
    try:
        with SessionLocal() as db:
            for item in pending:
                try:
                    _emit(db, item)
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    log.exception("webhook event %s", item[0])
                    _record(exc, item[0])
    except Exception as exc:  # noqa: BLE001
        log.exception("webhook observer (commit)")
        _record(exc, "commit")


def _record(exc: Exception, what: str) -> None:
    try:
        from ..telemetry.service import record_server_exception

        record_server_exception(exc, route=f"webhooks:{what}")
    except Exception:  # noqa: BLE001
        pass


def _emit(db: Session, item: tuple) -> None:
    from . import events

    kind = item[0]
    if kind == "job":
        from ..render.models import RenderJob
        from ..render.service import record_json

        job = db.get(RenderJob, item[1])
        if job is not None and job.account_kind == "user":
            events.emit(db, [job.account_id], f"job.{item[2]}", record_json(job))
    elif kind == "share":
        from ..shares.models import Share
        from ..shares.service import share_json

        share = db.get(Share, item[1])
        if share is not None and share.state == "live":
            events.emit(db, [share.account_id], "share.published", share_json(share))
    elif kind == "version":
        from ..projects.models import ProjectVersion
        from ..projects.versions import version_json

        version = db.get(ProjectVersion, item[1])
        if version is not None:
            data = {"project_id": version.project_id, **version_json(version)}
            events.emit(db, events.project_accounts(db, version.project_id), "project.version_created", data)
    elif kind == "member":
        from ..projects.members import member_json
        from ..projects.models import ProjectMember

        member = db.get(ProjectMember, item[1])
        if member is not None:
            data = {"project_id": member.project_id, **member_json(db, member)}
            events.emit(db, events.project_accounts(db, member.project_id), "project.member_added", data)
    elif kind == "order":
        from ..market.models import MarketOrder
        from ..market.orders import order_json

        order = db.get(MarketOrder, item[1])
        if order is not None and events.subscribed(db, order.user_id, "market.order.updated"):
            events.emit(db, [order.user_id], "market.order.updated", order_json(db, order))
    elif kind == "feed":
        from ..market.importer import report_json
        from ..market.models import FeedRun

        run = db.get(FeedRun, item[1])
        if run is not None:
            events.emit(db, events.supplier_accounts(db, run.supplier_id), "market.feed.completed", report_json(run))


def _on_ops(project_id: str, ops: list[dict]) -> None:
    if not enabled:
        return
    from . import events

    with SessionLocal() as db:
        events.note_ops(db, project_id, ops)


event.listen(Session, "after_flush", _collect)
event.listen(Session, "after_commit", _after_commit)
event.listen(Session, "after_rollback", _forget)
hooks.on_ops_accepted(_on_ops)
