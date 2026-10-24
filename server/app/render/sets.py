"""Followed panorama sets: partial re-render from the log (contract §2, 5.2, §6.4).

A `follow: true` panorama job owns a set. PF4's push hook calls
`enqueue_from_push` after every accepted push to a project: each active set of
that project gets one `tiles` job carrying the pushed `touched` ids, or joins
the set's job that is still queued (`changed` united, `at_seq` the highest),
so a burst of edits costs one render. A restore touches everything (`changed`
empty = every face). Each finished `tiles` job becomes the set's newest
manifest, bumps the follow job's `rev` and replaces its output, so a viewer
long-polls one id. Cancelling the follow job (or it failing) stops the set,
and so does its account leaving the project. A set's queue changes under its
row lock, so concurrent pushes leave at most one queued `tiles` job. When an
edit goes unrendered (its job failed, expired or was cancelled, or the
allowance ran out) the set is `stale` and its next update renders every face.
"""

import logging
import secrets
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..database import SessionLocal
from ..licence import clock
from ..models import User
from ..projects.hooks import on_ops_accepted
from ..projects.models import Project
from ..projects.service import membership
from . import estimates, quotas, tiles
from .models import RenderJob, RenderSet

log = logging.getLogger("truebex.render.sets")
MAX_CHANGED = 10_000


def unite(a: list[str], b: list[str]) -> list[str]:
    """`changed` of two jobs merged; [] (every face) absorbs anything."""
    if not a or not b:
        return []
    merged = sorted(set(a) | set(b))
    return [] if len(merged) > MAX_CHANGED else merged


def create(db: Session, job: RenderJob, now: datetime) -> RenderSet:
    row = RenderSet(
        follow_job_id=job.job_id,
        project_id=job.project_id,
        account_kind=job.account_kind,
        account_id=job.account_id,
        views=list(job.views),
        quality=job.quality,
        latest_job_id=None,
        at_seq=job.at_seq,
        rev=0,
        active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    return row


def lock_set(db: Session, set_id: str) -> RenderSet | None:
    """Begin the write transaction with the set's row locked; returns it fresh."""
    db.execute(update(RenderSet).where(RenderSet.follow_job_id == set_id).values(rev=RenderSet.rev))
    return db.execute(
        select(RenderSet).where(RenderSet.follow_job_id == set_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def has_access(db: Session, account_id: int, project_id: str) -> bool:
    project = db.get(Project, project_id)
    return project is not None and project.deleted_at is None and membership(db, project_id, account_id) is not None


def queued_job(db: Session, set_id: str) -> RenderJob | None:
    return db.scalar(
        select(RenderJob)
        .where(RenderJob.set_id == set_id, RenderJob.kind == "tiles", RenderJob.state == "queued")
        .order_by(RenderJob.queued_at.asc())
        .limit(1)
        .with_for_update()
    )


def coalesce(db: Session, job: RenderJob, changed: list[str], at_seq: int, now: datetime) -> RenderJob:
    from .queue import bump
    from .service import doc_version_needed

    job.changed = unite(list(job.changed or []), changed)
    if at_seq > job.at_seq:
        job.at_seq = at_seq
    # The joined operations may need a newer reader (5.7's doc_version_max).
    job.doc_version_needed = doc_version_needed(db, job.project_id, job.at_seq)
    bump(job, now)
    return job


def _latest_json(row: RenderSet) -> dict:
    return {"rev": row.rev, "job_id": row.latest_job_id, "at_seq": row.at_seq}


def write_latest(row: RenderSet) -> None:
    tiles.put_json(tiles.latest_key(row.follow_job_id), _latest_json(row), cache_control="no-cache")


def on_success(db: Session, job: RenderJob, now: datetime) -> str | None:
    """A job of a set finished: it is the set's newest manifest. Returns the
    follow job's id when its `rev` moved."""
    from .queue import bump

    if not job.set_id:
        return None
    row = db.get(RenderSet, job.set_id)
    if row is None:
        return None
    if job.job_id == row.follow_job_id or job.at_seq >= row.at_seq:
        row.latest_job_id = job.job_id
        row.at_seq = job.at_seq
        row.rev += 1
        row.updated_at = now
        write_latest(row)
    if job.job_id == row.follow_job_id:
        return None
    follow = db.get(RenderJob, row.follow_job_id)
    if follow is None:
        return None
    if row.latest_job_id == job.job_id:
        follow.output_key = job.output_key
        follow.at_seq = job.at_seq
        follow.message = ""
    bump(follow, now)
    return follow.job_id


def stop(db: Session, row: RenderSet, now: datetime, *, reason: str = "") -> None:
    """The set stops following: its queued jobs are cancelled."""
    from .queue import bump

    row.active = False
    row.updated_at = now
    for job in db.scalars(
        select(RenderJob).where(RenderJob.set_id == row.follow_job_id, RenderJob.state == "queued", RenderJob.kind == "tiles")
    ).all():
        job.state = "cancelled"
        job.finished_at = now
        job.message = reason
        bump(job, now)
    follow = db.get(RenderJob, row.follow_job_id)
    if follow is not None and follow.follow:
        follow.follow = False
        bump(follow, now)


def on_ended(db: Session, job: RenderJob, now: datetime) -> None:
    """A job of a set failed, was cancelled or expired. The follow job: the set
    stops. A `tiles` job: its edits went unrendered, the set is stale. (Every
    such end runs this, so PF11c's airflow jobs end with their wind job here.)"""
    from ..analysis import dependents

    dependents.on_ended(db, job, now)
    if not job.set_id:
        return
    row = db.get(RenderSet, job.set_id)
    if row is None or not row.active:
        return
    if job.set_id == job.job_id:
        stop(db, row, now)
    else:
        row.stale = True
        row.updated_at = now


def enqueue(db: Session, row: RenderSet, changed: list[str], at_seq: int, now: datetime) -> RenderJob | None:
    """One `tiles` job for the set (or the queued one joined). None when the
    account can no longer pay for it (the follow job then says so)."""
    from .queue import bump

    follow = db.get(RenderJob, row.follow_job_id)
    user = db.get(User, row.account_id)
    if follow is None or user is None:
        return None
    if not has_access(db, row.account_id, row.project_id):
        stop(db, row, now, reason="Updates stopped: this account is no longer on the project.")
        follow.message = "Updates stopped: you are no longer on this project."
        return None
    if row.stale:
        changed = []  # an earlier edit went unrendered: every face
    joined = queued_job(db, row.follow_job_id)
    if joined is not None:
        row.stale = False
        return coalesce(db, joined, changed, at_seq, now)
    kind = quotas.KINDS["tiles"]
    try:
        plan = quotas.require_feature(db, user, kind)
        estimate = estimates.estimate(db, "tiles", row.quality, max(1, len(row.views)))
        quotas.check(db, user, plan, estimate)
    except ContractError as exc:
        paused = "Updates paused: this month's cloud allowance is used up." if exc.code == "quota_exceeded" else (
            "Updates paused: cloud rendering is not on this account's plan."
        )
        if follow.message != paused:
            follow.message = paused
            bump(follow, now)
        row.stale = True
        return None
    job = RenderJob(
        job_id=secrets.token_hex(16),
        account_kind=row.account_kind,
        account_id=row.account_id,
        kind="tiles",
        worker_class=kind.worker_class,
        state="queued",
        rev=1,
        project_id=row.project_id,
        at_seq=at_seq,
        views=list(row.views),
        changed=changed if len(changed) <= MAX_CHANGED else [],
        base_job_id=row.latest_job_id or row.follow_job_id,
        set_id=row.follow_job_id,
        quality=row.quality,
        follow=False,
        inputs={},
        params={},
        priority=plan.rank,
        doc_version_needed=0,
        created_at=now,
        queued_at=now,
        updated_at=now,
        est_units=max(1, len(row.views)),
        cost_units_estimate=estimate,
    )
    from .service import doc_version_needed

    job.doc_version_needed = doc_version_needed(db, row.project_id, at_seq)
    db.add(job)
    row.stale = False
    if follow.message.startswith("Updates paused"):
        follow.message = ""
        bump(follow, now)
    return job


@on_ops_accepted
def enqueue_from_push(project_id: str, ops: list[dict]) -> None:
    """PF4's push hook: re-render the faces a push touched in every followed set."""
    from .queue import notify_claim, notify_job

    with SessionLocal() as db:
        ids = list(
            db.scalars(
                select(RenderSet.follow_job_id).where(RenderSet.project_id == project_id, RenderSet.active.is_(True))
            )
        )
        db.rollback()
        if not ids:
            return
        everything = any(op.get("kind") == "restore" for op in ops)
        touched: set[str] = set()
        for op in ops:
            touched.update(op.get("touched") or [])
        if not everything and not touched:
            return  # nothing in the model changed
        changed = [] if everything or len(touched) > MAX_CHANGED else sorted(touched)
        at_seq = max(int(op.get("server_seq") or 0) for op in ops)
        now = clock.now()
        affected = []
        for set_id in ids:
            row = lock_set(db, set_id)
            if row is None or not row.active:
                db.rollback()
                continue
            job = enqueue(db, row, changed, at_seq, now)
            affected += [set_id] + ([job.job_id] if job is not None else [])
            db.commit()
    notify_job(*affected)
    notify_claim()
