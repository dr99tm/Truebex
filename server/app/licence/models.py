"""Licence API tables (PF1, contract licence-api): devices, link codes,
trial fingerprints and the append-only licence events. Registered with
`Base` by `database.init_db`.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Device(Base):
    """An activated install of the app. Only a hash of its token is stored."""

    __tablename__ = "devices"
    __table_args__ = (
        # One active row per machine per account.
        Index(
            "uq_devices_user_fingerprint_active",
            "user_id",
            "fingerprint",
            unique=True,
            sqlite_where=text("deactivated_at IS NULL"),
            postgresql_where=text("deactivated_at IS NULL"),
        ),
    )

    device_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # sha256 hex made by the app (contract §6.2), never the raw machine ids.
    fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    os: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    # SHA-256 of the tbx_dev_ token, like API keys.
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # free | personal | trial | named | floating (as last issued)
    seat_kind: Mapped[str] = mapped_column(String(16), default="free", nullable=False)
    org_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # removed | signed_out | replaced | lapsed | fingerprint_mismatch
    deactivated_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)


class LinkCode(Base):
    """A browser sign-in for a device (RFC 8628 pattern, contract 5.1-5.3)."""

    __tablename__ = "link_codes"

    link_code: Mapped[str] = mapped_column(String(9), primary_key=True)
    poll_secret_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    # pending | approved | denied | spent
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    last_poll_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TrialFingerprint(Base):
    """One trial per machine, whichever account asks (contract 5.6)."""

    __tablename__ = "trial_fingerprints"

    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class LicenceEvent(Base):
    """Append-only record of licence events; PF3's audit log reads it."""

    __tablename__ = "licence_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    device_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    # link.approved | link.denied | device.activated | device.replaced |
    # device.revoked | trial.started | seat.device_limit
    kind: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
