"""Database models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
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
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    # Subscription plan: "free" until a Gammal Tech payment is delivered.
    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False)
    # Last delivered Gammal Tech payment id, for traceability.
    last_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
