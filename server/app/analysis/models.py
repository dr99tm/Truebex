"""Analysis tables (PF11). Registered with `Base` through app.ai.models.

`analysis_weather` is the weather library the `energy` kind's
`params.weather` names: one EPW file per id, with where it came from and its
licence recorded for GD2 (the files live in storage under `weather/`).
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisWeather(Base):
    __tablename__ = "analysis_weather"

    weather_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # "London Heathrow, GBR" (the EPW's LOCATION line unless given).
    location: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Where the file came from (a URL or a dataset name) and under which licence.
    source: Mapped[str] = mapped_column(String(300), nullable=False)
    licence: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(200), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
