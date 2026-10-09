"""Database models."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    # Empty string for accounts created with Google that never set a password.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    # Cached plan id ("free", "pro", ...). Billing keeps it in sync with the
    # user's active subscription; see billing.service.effective_plan.
    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False)
    # Google account id (the ID token's `sub`), set once the user signs in
    # with Google.
    google_sub: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # --- PF1 (licence API) ---
    # 32-hex UUIDv7 carried by project-log operations; minted on first use.
    author_id: Mapped[str | None] = mapped_column(
        String(32), unique=True, index=True, nullable=True
    )
    # Set by hand, like the "enterprise" plan. Gates /admin.
    is_admin: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    # When the account's one trial started (contract 5.6).
    trial_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ApiKey(Base):
    """A developer API key. Only a hash of the secret is stored."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # First characters of the key, shown in the dashboard ("tbx_live_ab12…").
    prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    # SHA-256 of the full key. Keys are high-entropy, so a fast hash is fine.
    key_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UsageDaily(Base):
    """Request counter per key, per endpoint, per UTC day."""

    __tablename__ = "usage_daily"
    __table_args__ = (
        UniqueConstraint("api_key_id", "day", "endpoint", name="uq_usage_key_day_ep"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    api_key_id: Mapped[int] = mapped_column(
        ForeignKey("api_keys.id", ondelete="CASCADE"), index=True, nullable=False
    )
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Subscription(Base):
    """A user's paid plan, from any payment provider.

    Stripe rows mirror a recurring Stripe subscription. Wayl has no
    subscriptions, so each Wayl payment adds a prepaid period.
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    # active | past_due | canceled
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_customer_id: Mapped[str | None] = mapped_column(String(128))
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(128), index=True
    )
    # Seats bought (PF2 writes it); None = 1.
    seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class Payment(Base):
    """One checkout attempt and its outcome."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    # Our id, sent to the provider (Wayl referenceId / Stripe client_reference_id).
    reference: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    provider_ref: Mapped[str | None] = mapped_column(String(128), index=True)
    # Minor units for USD (cents); whole dinars for IQD.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # pending | paid | failed | canceled
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- Licence API (PF1, contract licence-api) ----------------------------------


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


class Release(Base):
    """A published installer: its signed truebex-release/1 manifest and file."""

    __tablename__ = "releases"
    __table_args__ = (
        UniqueConstraint("version", "platform", name="uq_releases_version_platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    channel: Mapped[str] = mapped_column(String(8), nullable=False)
    # The manifest's canonical JSON text, exactly as signed at publish time.
    manifest: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)
    kid: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReleaseDownload(Base):
    """One download URL handed out (5.14). No personal data; PF13 counts them."""

    __tablename__ = "release_downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
