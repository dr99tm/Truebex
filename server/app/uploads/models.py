"""Upload tables (PF5, share-bundle §5.1-5.3): sessions and content-addressed
blobs. Registered with `Base` by `database.init_db`.

Which parts of a file have arrived is read from the part files themselves
(`uploads/parts/{upload_id}/{sha256}/{n}`), never kept in the session row, so
four parts in flight never race on one JSON value.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    upload_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # device | session | worker: only the same kind of credential (and, for a
    # worker, the same worker) may add parts or read the session.
    credential_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    credential_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    # [{"sha256", "bytes", "content_type"}] as declared at 5.1.
    files: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class Blob(Base):
    """A complete, verified file, stored once per account at blobs/{account}/{sha256}."""

    __tablename__ = "blobs"
    __table_args__ = (UniqueConstraint("account_id", "sha256", name="uq_blobs_account_sha256"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # Shares, snapshots and jobs holding this blob. At 0 it may be dropped
    # (uploads.expire drops one nobody took within 7 days).
    refs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
