"""Project service tables (PF4, contract project-log). Registered with `Base`
by `database.init_db`.

The log is append-only: `project_ops` rows are never updated, and
`op_touched` indexes which entities each operation changed, so the §6.3
conflict query is one indexed lookup per pushed operation.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_owner_updated", "owner_user_id", "updated_at"),)

    project_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # PF3 fills it for organisation-owned projects.
    org_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    doc_version: Mapped[int] = mapped_column(Integer, nullable=False)
    head_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Snapshot blobs and offloaded deltas, maintained on write.
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # The replica_id restore operations carry (5.12).
    server_replica_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectMember(Base):
    """The owner, editors and viewers; invitations wait with `user_id` null."""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_members_user"),
        Index("ix_project_members_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(8), nullable=False)  # owner | editor | viewer
    state: Mapped[str] = mapped_column(String(8), nullable=False)  # active | invited
    # 32 hex, how the owner names an invitation before it has a user_id.
    invite_id: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    # SHA-256 of the 256-bit token in the e-mailed link; cleared on acceptance.
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    invited_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectOp(Base):
    __tablename__ = "project_ops"
    __table_args__ = (UniqueConstraint("project_id", "op_id", name="uq_project_ops_op_id"),)

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True
    )
    server_seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    op_id: Mapped[str] = mapped_column(String(32), nullable=False)
    replica_id: Mapped[str] = mapped_column(String(32), nullable=False)
    author: Mapped[str] = mapped_column(String(32), nullable=False)
    author_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # delta | action | restore
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    # The writer's clock, as sent (shown, never used to order).
    at: Mapped[str] = mapped_column(String(40), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    base_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    touched: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    delta_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # ≤ 64 KiB inline; larger deltas live in storage at delta_key.
    delta: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    delta_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delta_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    restore: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class OpTouched(Base):
    """One row per (operation, entity): answers "who changed X after N"."""

    __tablename__ = "op_touched"
    __table_args__ = (Index("ix_op_touched_lookup", "project_id", "entity_id", "server_seq"),)

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True
    )
    server_seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    entity_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    replica_id: Mapped[str] = mapped_column(String(32), nullable=False)


class ProjectSnapshot(Base):
    __tablename__ = "project_snapshots"
    __table_args__ = (Index("ix_project_snapshots_seq", "project_id", "at_seq"),)

    snapshot_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), index=True, nullable=False
    )
    at_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    doc_version: Mapped[int] = mapped_column(Integer, nullable=False)
    tbxp_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    tbxp_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tbxpack_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tbxpack_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ProjectVersion(Base):
    __tablename__ = "project_versions"

    version_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    at_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Pins its snapshot: projects.snapshots.prune never drops it.
    snapshot_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Presence(Base):
    """Presence when PROJECTS_PRESENCE_BACKEND=db (several API processes)."""

    __tablename__ = "presence"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True
    )
    replica_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    client: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
