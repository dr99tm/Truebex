"""Database models."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
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
    # PF1 (licence API):
    # 32-hex UUIDv7 carried by project-log operations; minted on first use.
    author_id: Mapped[str | None] = mapped_column(
        String(32), unique=True, index=True, nullable=True
    )
    # When the account's one trial started (contract 5.6).
    trial_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Google account id (the ID token's `sub`), set once the user signs in
    # with Google.
    google_sub: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Set by hand (like "enterprise"); unlocks the /admin routes.
    is_admin: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)


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
    # PF3: set when an organisation owns this subscription (its tier and seats
    # reach the organisation's members through seat_source, never users.plan);
    # None = the user's own.
    organisation_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
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


class DownloadEvent(Base):
    """One installer download, counted for the admin Growth panel.

    No personal data: no user, no IP address, no user agent; only when,
    which version, which platform and channel.
    """

    __tablename__ = "download_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(16), nullable=True)
