"""Webhook tables (PF12)."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WebhookEndpoint(Base):
    """A receiver an account registered. The signing secret must be readable to
    sign, so it is sealed (Fernet, WEBHOOK_SECRET_KEY), never hashed."""

    __tablename__ = "webhook_endpoints"

    endpoint_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    description: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    secret_enc: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # The first failed attempt since the last success; five days → disabled.
    failing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # failing (the disable job) | owner (switched off by its account)
    disabled_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class WebhookEvent(Base):
    """One event for one account: the body every endpoint of it receives."""

    __tablename__ = "webhook_events"

    # msg_<32 hex>: the `webhook-id` header, the same on every attempt.
    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    # {"type", "timestamp", "data"}: sent as is.
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True, nullable=False)


class WebhookDelivery(Base):
    """One attempt to deliver an event to an endpoint (the delivery log)."""

    __tablename__ = "webhook_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(
        ForeignKey("webhook_endpoints.endpoint_id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("webhook_events.event_id", ondelete="CASCADE"), index=True, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # pending | sending (a runner holds it) | succeeded | failed | cancelled
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # A re-send asked for by the account: one attempt, no retries.
    manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True, nullable=False)

    endpoint: Mapped[WebhookEndpoint] = relationship(lazy="joined")
    event: Mapped[WebhookEvent] = relationship(lazy="joined")


class WebhookPendingOps(Base):
    """`project.ops_appended`, debounced: the first push opens a 30 s window,
    later pushes widen it, the deliver job sends one event when it closes."""

    __tablename__ = "webhook_pending_ops"

    project_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    first_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # [{"author", "author_kind"}], first appearance order.
    authors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
