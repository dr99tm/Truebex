"""Share tables (PF5, share-bundle §6.2): shares, their panorama derivatives
and visit counts. Registered with `Base` by `database.init_db`.

Visits keep no address and no user agent: one row per (share, UTC day,
visitor id the page made up and keeps for 24 h).
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Share(Base):
    __tablename__ = "shares"
    __table_args__ = (UniqueConstraint("account_id", "bundle_id", name="uq_shares_account_bundle"),)

    share_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    bundle_id: Mapped[str] = mapped_column(String(32), nullable=False)
    # 10 base62 characters, minted at publish.
    slug: Mapped[str | None] = mapped_column(String(10), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    # uploading | live | expired | revoked
    state: Mapped[str] = mapped_column(String(16), index=True, nullable=False, default="uploading")
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    watermark: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The expiry asked for at 5.4; the clock starts at publish.
    days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    upload_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    card_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Files, derivatives and the card go 7 days after expiry or revoke.
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShareDerivative(Base):
    __tablename__ = "share_derivatives"
    __table_args__ = (UniqueConstraint("share_id", "source_sha256", "kind", name="uq_share_derivative"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_id: Mapped[str] = mapped_column(
        ForeignKey("shares.share_id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # pano-4096 | pano-1024
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ShareVisit(Base):
    __tablename__ = "share_visits"
    __table_args__ = (UniqueConstraint("share_id", "day", "visitor", name="uq_share_visit"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_id: Mapped[str] = mapped_column(
        ForeignKey("shares.share_id", ondelete="CASCADE"), index=True, nullable=False
    )
    day: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD, UTC
    visitor: Mapped[str] = mapped_column(String(32), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
