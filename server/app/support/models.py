"""Support API tables: one-time e-mail codes and the verifications they buy.
Registered with `Base` by `database.init_db`.

Neither table holds a secret in the clear: a code is kept as an HMAC-SHA256
under a key derived from SECRET_KEY (six digits are too few for a bare hash),
a verification id as its SHA-256 (32 random bytes).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupportEmailCode(Base):
    """A six-digit code sent to an address: 10 minutes, 5 tries, used once."""

    __tablename__ = "support_email_codes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # Lower-case; any address, with or without an account (no enumeration).
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # The Desk's hash of the contact who asked (never a phone number).
    contact_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    # Set when the code is accepted, replaced by a newer one or out of tries.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupportVerification(Base):
    """Proof that a contact controls an address, for one sign-up (15 minutes)."""

    __tablename__ = "support_verifications"

    id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    contact_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
