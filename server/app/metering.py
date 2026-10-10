"""Metered quantities per subject, metric and UTC day (PF14 Plumbing; first
user PF6, PF11 next).

    metering.record(db, "user", 42, "cu", Decimal("1.6"))          # adds to today
    metering.total(db, "user", 42, "cu", start, end)                # Decimal
    metering.by_metric(db, "user", 42, "cu.", start, end)          # {"cu.tiles": …}

One `meter_daily` row per (subject, metric, day); `record` is an atomic
upsert on SQLite and Postgres alike, so concurrent completions never lose an
amount. Quantities are decimals with three places (cost units are charged in
tenths). The developer API's request counts stay in `usage_daily`.
"""

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Date, Integer, Numeric, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, dialect_insert

PLACES = Decimal("0.001")


class MeterDaily(Base):
    __tablename__ = "meter_daily"
    __table_args__ = (UniqueConstraint("subject_kind", "subject_id", "metric", "day", name="uq_meter_daily"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # "user" (an "org" with PF3).
    subject_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # "cu" (cost units, PF6) and "cu.<kind>" beside it for the breakdown.
    metric: Mapped[str] = mapped_column(String(48), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=Decimal(0))


def quantize(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(PLACES, rounding=ROUND_HALF_UP)


def utc_day(at: datetime | None = None) -> date:
    return (at or datetime.now(timezone.utc)).astimezone(timezone.utc).date()


def record(
    db: Session, subject_kind: str, subject_id: int | str, metric: str, quantity: Decimal | float, day: date | None = None
) -> None:
    """Add `quantity` to the day's row (the caller commits)."""
    amount = quantize(quantity)
    stmt = dialect_insert(db, MeterDaily).values(
        subject_kind=subject_kind, subject_id=str(subject_id), metric=metric, day=day or utc_day(), quantity=amount
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["subject_kind", "subject_id", "metric", "day"],
        set_={"quantity": MeterDaily.quantity + amount},
    )
    db.execute(stmt)


def _window(subject_kind: str, subject_id: int | str, start: date, end: date):
    return (
        MeterDaily.subject_kind == subject_kind,
        MeterDaily.subject_id == str(subject_id),
        MeterDaily.day >= start,
        MeterDaily.day < end,
    )


def total(db: Session, subject_kind: str, subject_id: int | str, metric: str, start: date, end: date) -> Decimal:
    """Sum over [start, end)."""
    value = db.scalar(
        select(func.coalesce(func.sum(MeterDaily.quantity), 0)).where(
            *_window(subject_kind, subject_id, start, end), MeterDaily.metric == metric
        )
    )
    return quantize(value or 0)


def by_metric(db: Session, subject_kind: str, subject_id: int | str, prefix: str, start: date, end: date) -> dict[str, Decimal]:
    """{metric: sum} for every metric starting with `prefix`, over [start, end)."""
    rows = db.execute(
        select(MeterDaily.metric, func.sum(MeterDaily.quantity))
        .where(*_window(subject_kind, subject_id, start, end), MeterDaily.metric.like(f"{prefix}%"))
        .group_by(MeterDaily.metric)
    ).all()
    return {metric: quantize(q or 0) for metric, q in rows}


def daily(db: Session, subject_kind: str, subject_id: int | str, metric: str, start: date, end: date) -> dict[date, Decimal]:
    rows = db.execute(
        select(MeterDaily.day, MeterDaily.quantity).where(
            *_window(subject_kind, subject_id, start, end), MeterDaily.metric == metric
        )
    ).all()
    return {day: quantize(q or 0) for day, q in rows}


def subjects(db: Session, metric: str, start: date, end: date) -> list[tuple[str, str]]:
    """(subject_kind, subject_id) with any of `metric` in [start, end)."""
    rows = db.execute(
        select(MeterDaily.subject_kind, MeterDaily.subject_id)
        .where(MeterDaily.metric == metric, MeterDaily.day >= start, MeterDaily.day < end)
        .group_by(MeterDaily.subject_kind, MeterDaily.subject_id)
    ).all()
    return [(k, i) for k, i in rows]
