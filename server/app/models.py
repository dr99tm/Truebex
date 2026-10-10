"""Database models."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
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
    # Set by hand for the owner (like "enterprise"); gates /admin/*. Nullable
    # because database._ADDED_COLUMNS adds it to existing databases.
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
    # PF8: a supplier key (made in the supplier portal) feeds that supplier's
    # catalogue only (contract marketplace-api 5.11-5.13); None = a developer key.
    supplier_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)


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
    # One row per provider subscription (database._migrate adds it to old files).
    __table_args__ = (
        Index(
            "uq_subscriptions_provider_sub",
            "provider",
            "provider_subscription_id",
            unique=True,
        ),
    )

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
    # PF3: set when an organisation owns this subscription (its tier and seats
    # reach the organisation's members through seat_source, never users.plan);
    # None = the user's own.
    organisation_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)


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
    # The founding price of its tier (a lasting discount). A subscription is a
    # founding one exactly when it pays such a price.
    founding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    """One founding place: held for a checkout (30 minutes) or bought.

    A place covers one subscription, whatever its seats: the founding price
    stays on all of them. `reference` is the checkout's payment reference, or
    `sub:<provider subscription id>` for a founding subscription that did not
    come through our checkout."""

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


# --- Telemetry (PF14, contracts/telemetry.md) -----------------------------------
# No table here holds an IP address or an account id. feedback.email is the
# one personal field, stored only when the person asked for a reply and the
# app sent a valid device token.


class TelemetryEvent(Base):
    """One allow-listed usage event (5.2). Raw rows are kept 13 months."""

    __tablename__ = "telemetry_events"
    __table_args__ = (Index("ix_telemetry_events_at", "at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
    install_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(32), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(16))
    build: Mapped[str | None] = mapped_column(String(16))
    os: Mapped[str | None] = mapped_column(String(64))
    locale: Mapped[str | None] = mapped_column(String(35))
    plan: Mapped[str | None] = mapped_column(String(32))
    hw: Mapped[dict | None] = mapped_column(JSON)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    props: Mapped[dict] = mapped_column(JSON, nullable=False)


class TelemetryDaily(Base):
    """Daily counts per event and app version, kept after the raw rows go
    (6.5). `name` and `app_version` take "*" for the all-events and
    all-versions rows."""

    __tablename__ = "telemetry_daily"
    __table_args__ = (
        UniqueConstraint("day", "name", "app_version", name="uq_telemetry_daily"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    installs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    p50_ms: Mapped[int | None] = mapped_column(Integer)
    p95_ms: Mapped[int | None] = mapped_column(Integer)


class TelemetryBatch(Base):
    """Idempotency for 5.2: a repeated batch_id gets the first answer again."""

    __tablename__ = "telemetry_batches"

    batch_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    install_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
    accepted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dropped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CrashGroup(Base):
    """Crash reports grouped by signature (6.3). A group whose reports moved
    after symbolication stays as an alias (`merged_into`) with count 0, so
    later raw reports of the same build join the corrected group at once."""

    __tablename__ = "crash_groups"

    signature: Mapped[str] = mapped_column(String(16), primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    versions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # new | investigating | fixed | ignored
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    fixed_in: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), default="crash", nullable=False)
    merged_into: Mapped[str | None] = mapped_column(String(16))


class CrashReport(Base):
    """One crash report (5.3), or an API exception (kind "server")."""

    __tablename__ = "crash_reports"

    crash_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
    # crash | hang | gpu_lost | ensure | server
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    install_id: Mapped[str | None] = mapped_column(String(32), index=True)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    os: Mapped[str | None] = mapped_column(String(64))
    hw: Mapped[dict | None] = mapped_column(JSON)
    at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exception: Mapped[dict | None] = mapped_column(JSON)
    signature: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    frames: Mapped[list] = mapped_column(JSON, nullable=False)
    minidump_key: Mapped[str | None] = mapped_column(String(300))
    log_key: Mapped[str | None] = mapped_column(String(300))
    symbolicated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gpu_driver: Mapped[str | None] = mapped_column(String(64))
    uptime_s: Mapped[int | None] = mapped_column(Integer)


class Feedback(Base):
    """Feedback from the app (5.4): text, an optional screenshot and log."""

    __tablename__ = "feedback"

    feedback_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
    install_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # bug | idea | question | praise
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Only with `reply` and a valid device token; the app never types one.
    email: Mapped[str | None] = mapped_column(String(320))
    screenshot_key: Mapped[str | None] = mapped_column(String(300))
    log_key: Mapped[str | None] = mapped_column(String(300))
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    os: Mapped[str | None] = mapped_column(String(64))
    # new | replied | closed
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TelemetryDeletion(Base):
    """A 5.5 request and when it was carried out: proof of the 30-day promise."""

    __tablename__ = "telemetry_deletions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    install_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SymbolFile(Base):
    """A private Breakpad .sym file in storage, never served. Stored in the
    Breakpad layout `symbols/{module}/{debug_id}/{module stem}.sym`."""

    __tablename__ = "symbol_files"
    __table_args__ = (UniqueConstraint("module", "debug_id", name="uq_symbol_module_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module: Mapped[str] = mapped_column(String(200), nullable=False)  # the PDB name
    debug_id: Mapped[str] = mapped_column(String(64), nullable=False)
    code_file: Mapped[str | None] = mapped_column(String(200), index=True)  # DLL / EXE
    version: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(400), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# --- Operations (PF14) ------------------------------------------------------------


class OpsStatus(Base):
    """Named timestamps: the worker heartbeat, the backup markers the host's
    backup scripts write, job progress and alert state."""

    __tablename__ = "ops_status"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)


class RateLimitBucket(Base):
    """Token buckets shared by several API processes (RATELIMIT_BACKEND=db).

    `key` is an HMAC of the limiter key, so no address is ever stored.
    """

    __tablename__ = "ratelimit_buckets"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    tokens: Mapped[float] = mapped_column(Float, nullable=False)
    updated: Mapped[float] = mapped_column(Float, nullable=False)
