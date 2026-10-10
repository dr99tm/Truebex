"""Organisation tables (PF3): organisations, members, invites, seat
assignments, floating-seat leases, e-mail domains and the audit log.
Registered with `Base` by `database.init_db`. The SSO tables live in
`app/sso/models.py`.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organisation(Base):
    __tablename__ = "organisations"

    # 32-hex UUIDv7 (licence contract §6.1: `account.org_id`).
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    # How many of the organisation's seats float (shared by concurrent leases).
    floating_seats: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Domain users must sign in through the organisation's identity provider.
    sso_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # SHA-256 of the owners' one-time break-glass code (shown once).
    break_glass_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Bumped by every floating-seat lease: the write that takes the row lock.
    lease_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrgMember(Base):
    __tablename__ = "org_members"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # owner | admin | billing | member
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class OrgInvite(Base):
    __tablename__ = "org_invites"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    # named | floating | none: the seat given on acceptance.
    seat_kind: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    # SHA-256 of the 256-bit token in the invite link.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    invited_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set by the orgs.invites.expire job.
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SeatAssignment(Base):
    """A member's seat: `named` (theirs alone) or `floating` (may lease from the pool)."""

    __tablename__ = "seat_assignments"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    assigned_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class FloatingLease(Base):
    """One device holding one floating seat. In use = not released and not expired."""

    __tablename__ = "floating_leases"
    __table_args__ = (Index("ix_floating_leases_org_open", "org_id", "released_at", "expires_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    leased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # The floating entitlement document's expires_at (2 h after each renewal).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # When the seat went back to the pool (released, lapsed, seat removed).
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # released | lapsed | seat_changed | device_removed | member_removed
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)


class OrgDomain(Base):
    """An e-mail domain an organisation claims; verified by a DNS TXT record."""

    __tablename__ = "org_domains"
    __table_args__ = (
        # A domain belongs to at most one organisation once verified; pending
        # claims by several organisations are allowed (no squatting).
        Index(
            "uq_org_domains_verified",
            "domain",
            unique=True,
            sqlite_where=text("verified_at IS NOT NULL"),
            postgresql_where=text("verified_at IS NOT NULL"),
        ),
        Index("uq_org_domains_org_domain", "org_id", "domain", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    domain: Mapped[str] = mapped_column(String(253), index=True, nullable=False)
    txt_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    """Organisation events; the audit view unions PF1's licence_events of members."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True, nullable=False)
    org_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    target_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(320), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
