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
    # Google account id (the ID token's `sub`), set once the user signs in
    # with Google.
    google_sub: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    # --- PF1 / PF2 columns (added by database._ADDED_COLUMNS, all nullable) ---
    # Seats bought (Team); null = 1. Written only from verified events.
    seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # month | year
    interval: Mapped[str | None] = mapped_column(String(8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    # Cancelled by the customer; the plan stays until current_period_end.
    cancel_at_period_end: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Bought at the founding price (a lasting discount).
    founding: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    provider_price_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Time of the newest provider event applied; older events never overwrite.
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    # Minor units of `currency` (cents, pence; whole dinars for IQD).
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # pending | paid | failed | canceled
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # --- PF2 columns (added by database._ADDED_COLUMNS, all nullable) ---------
    interval: Mapped[str | None] = mapped_column(String(8), nullable=True)
    seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Tax in minor units, from the provider once paid.
    tax_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The cancellation consent accepted before checkout (reg. 37).
    consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invoice_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ProviderPrice(Base):
    """A catalogue price mirrored to a payment provider (scripts/sync_prices.py).

    The amount is part of a row's identity: a GD7 price change adds a row,
    and old rows stay so webhooks for existing subscribers still map their
    price id back to a tier and interval.
    """

    __tablename__ = "provider_prices"
    __table_args__ = (
        UniqueConstraint("provider", "provider_price_id", name="uq_provider_price_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Per seat, in minor units of `currency`.
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_price_id: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class BillingEvent(Base):
    """Every provider event seen: replay and order protection."""

    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_billing_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    # applied | ignored | stale
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class FoundingReservation(Base):
    """Founding seats held for one checkout (30 minutes) or bought."""

    __tablename__ = "founding_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reference: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    seats: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
