"""AI proxy tables (PF11, contract ai-proxy §6.2). Registered with `Base` by
`database.init_db` (which imports this module; it also registers the
analysis tables, app.analysis.models).

* `ai_balances`: one row per account, the two buckets in integer credits.
* `ai_credit_ledger`: append-only; every balance change has a kind and a
  reference, and grants, expiries and top-ups are unique per reference, so
  the monthly grant and a replayed payment can never count twice.
* `ai_usage`: one row per turn, kept 400 days: token counts, credits, tool
  names. Never message text, tool input or an image.
* `ai_turns`: turns in flight (at most 2 per account), `ai_request_keys`:
  `Idempotency-Key`s seen in the last 10 minutes.
* `ai_servers`: the self-hosted inference servers on gpu-ai workers.
* `ai_top_ups`: credit packs bought on the website (PF2's one-off checkout).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..analysis import models as _analysis_models  # noqa: F401  (registers analysis_weather)
from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AiBalance(Base):
    __tablename__ = "ai_balances"

    account_kind: Mapped[str] = mapped_column(String(8), primary_key=True, default="user")
    account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The month's allowance left (may end below zero after the turn that
    # crossed it; written off at the reset) and the bought credits left.
    allowance_remaining: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    top_up_remaining: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # The month the allowance belongs to ("YYYY-MM") and what was granted for it.
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    granted: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    resets_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AiCreditLedger(Base):
    __tablename__ = "ai_credit_ledger"
    __table_args__ = (
        UniqueConstraint("account_kind", "account_id", "kind", "bucket", "ref", name="uq_ai_ledger_ref"),
        Index("ix_ai_ledger_account", "account_kind", "account_id", "at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="user")
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # grant | expire | top_up | usage | refund | adjust
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    # allowance | top_up
    bucket: Mapped[str] = mapped_column(String(10), nullable=False)
    # The month ("2026-11"), a payment reference, a turn id, an admin note.
    ref: Mapped[str] = mapped_column(String(80), nullable=False)
    # Credits remaining (both buckets) after this row.
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AiUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_account", "account_kind", "account_id", "at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turn_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    account_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="user")
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # metadata.session_id: the assistant conversation (never sent upstream).
    session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    alias: Mapped[str] = mapped_column(String(40), nullable=False)
    # The model that answered (a refusal fallback or a self-hosted fallback
    # names another) and who served it: anthropic | selfhosted.
    provider_model: Mapped[str] = mapped_column(String(80), nullable=False)
    served_by: Mapped[str] = mapped_column(String(16), nullable=False)
    stream: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stop_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    credits: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # What the provider charges for these tokens, in millionths of a US dollar
    # (the admin compares credits with it per alias).
    provider_cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # The names of the tools the model called this turn (never their input).
    tool_names: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # ok | upstream_error | client_gone
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")


class AiTurn(Base):
    """A turn in flight (deleted when it ends; stale rows are ignored)."""

    __tablename__ = "ai_turns"

    turn_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="user")
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AiRequestKey(Base):
    __tablename__ = "ai_request_keys"
    __table_args__ = (UniqueConstraint("account_kind", "account_id", "key", name="uq_ai_request_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="user")
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)


class AiServer(Base):
    """A self-hosted inference server (an OpenAI-compatible endpoint on a
    gpu-ai worker) behind an alias."""

    __tablename__ = "ai_servers"

    server_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    alias: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(300), nullable=False)
    # cold (registered, not answering) | warm (answered its last probe) |
    # stopped (the scaler wants it off)
    state: Mapped[str] = mapped_column(String(8), nullable=False, default="cold")
    warm_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_probe_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_turn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AiTopUp(Base):
    """A credit pack bought through PF2's one-off checkout; credited once,
    when the payment is verified (webhook or refresh)."""

    __tablename__ = "ai_top_ups"

    reference: Mapped[str] = mapped_column(String(64), primary_key=True)  # = payments.reference
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pack: Mapped[str] = mapped_column(String(40), nullable=False)
    credits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # pending | credited | canceled
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
