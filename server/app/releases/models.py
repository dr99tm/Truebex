"""Release feed table (PF1, contract licence-api 5.13). Registered with
`Base` by `database.init_db`; downloads are counted in `download_events`
(app.models.DownloadEvent).
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


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
