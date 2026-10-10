"""Render tables (PF6, contract render-jobs). Registered with `Base` by
`database.init_db` (which imports this module; it also registers PF14's
`meter_daily` from app.metering).

`render_jobs` is the queue itself: a claim is one conditional UPDATE of a
`queued` row (`FOR UPDATE SKIP LOCKED` picks it on Postgres), so two workers
can never hold one job.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .. import metering as _metering  # noqa: F401  (registers meter_daily)
from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RenderJob(Base):
    __tablename__ = "render_jobs"
    __table_args__ = (
        Index("ix_render_jobs_queue", "state", "priority", "queued_at"),
        Index("ix_render_jobs_account", "account_kind", "account_id", "created_at"),
        Index("ix_render_jobs_set", "set_id", "state"),
    )

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # "user" (an "org" once PF3 owns projects); who is charged and who sees it.
    account_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="user")
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    worker_class: Mapped[str] = mapped_column("class", String(16), nullable=False)
    # queued | claimed | running | succeeded | failed | cancelled | expired
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    rev: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    at_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    views: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Entity ids (≤ 10 000); [] = every face.
    changed: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    base_job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # The followed set this job belongs to (the follow panorama's own id).
    set_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quality: Mapped[str] = mapped_column(String(8), nullable=False, default="standard")
    follow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # The tier's rank at submission: Enterprise first, then age.
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    message: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # Ended claims (lapses and failures); the fourth ends the job.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The lease that completed or failed it last (5.9 / 5.10 repeat safely).
    ended_lease_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The newest delta_format in the job's log range (o5/<n> -> n).
    doc_version_needed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_upload_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    # Units the estimate counts (views for panorama and tiles, items for pack).
    est_units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cost_units_estimate: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False, default=Decimal(0))
    cost_units: Mapped[Decimal | None] = mapped_column(Numeric(12, 1), nullable=True)
    wall_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    used_class: Mapped[str | None] = mapped_column(String(16), nullable=True)
    faces_rendered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # jobs/{job_id}/manifest.json (a follow job: its set's newest manifest).
    output_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class RenderSet(Base):
    """A followed panorama set: one per `follow: true` panorama job."""

    __tablename__ = "render_sets"

    follow_job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    account_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="user")
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    views: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    quality: Mapped[str] = mapped_column(String(8), nullable=False, default="standard")
    latest_job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    at_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # An edit was not rendered (its job failed, expired or was cancelled, or the
    # allowance ran out): the next update renders every face.
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Worker(Base):
    """A render worker's credential (`tbx_wrk_…`, stored as SHA-256) and the
    machine behind it, as the pool and the admin page see it."""

    __tablename__ = "workers"

    # The name the admin gave it ("pc-rtx", "gpu-eu-01"); 5.7's `worker_id`.
    worker_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kinds: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    worker_class: Mapped[str] = mapped_column("class", String(16), nullable=False, default="gpu-std")
    # static (registered by hand) or the cloud adapter's name.
    pool: Mapped[str] = mapped_column(String(16), nullable=False, default="static")
    # What the pool wants of the machine: running | stopped.
    pool_state: Mapped[str] = mapped_column(String(8), nullable=False, default="running")
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    doc_version_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When it last held no job (the autoscaler stops machines idle 10 min).
    idle_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OverageCharge(Base):
    """One row per account and month with cost units beyond the allowance,
    accrued as jobs complete (within the cap in force then)."""

    __tablename__ = "overage_charges"
    __table_args__ = (UniqueConstraint("account_kind", "account_id", "month", name="uq_overage_account_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="user")
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    cu: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    provider: Mapped[str | None] = mapped_column(String(16), nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # open (accruing this month, at completions) | pending (no provider can
    # charge: a trial, a dormant provider; the owner settles it) | charged |
    # failed (retried by the next run)
    state: Mapped[str] = mapped_column(String(8), nullable=False, default="pending")
    note: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    charged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OverageCap(Base):
    """How many cost units past the allowance an account allows a month
    (tiers with overage only; 0 = none, the default)."""

    __tablename__ = "render_overage_caps"

    account_kind: Mapped[str] = mapped_column(String(8), primary_key=True, default="user")
    account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cap_cu: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False, default=Decimal(0))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
