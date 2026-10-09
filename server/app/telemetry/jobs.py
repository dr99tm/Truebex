"""Telemetry jobs (PF14 Jobs table), registered with app.tasks:

| Job                  | Every | Does |
| telemetry.rollup     | 10 min | recomputes telemetry_daily for every day that received events |
| telemetry.retention  | 24 h  | applies contracts/telemetry.md §6.5 |
| telemetry.deletions  | 1 h   | completes pending 5.5 requests (well inside 30 days) |
| crash.symbolicate    | 60 s  | names raw frames with the private symbols; fixes signature and group |
"""

import logging
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select

from ..config import get_settings
from ..database import SessionLocal
from ..models import (
    CrashGroup,
    CrashReport,
    Feedback,
    SymbolFile,
    TelemetryBatch,
    TelemetryDaily,
    TelemetryDeletion,
    TelemetryEvent,
)
from ..ops import mark, read
from ..storage import get_store
from ..tasks import periodic
from . import symbolicate
from .service import add_to_group, crash_signature, resolve_group

log = logging.getLogger("truebex.telemetry.jobs")
settings = get_settings()

RAW_EVENT_MONTHS = 13
CRASH_FILE_DAYS = 180
FEEDBACK_MONTHS = 24
BATCH_ID_DAYS = 30


def months_ago(now: datetime, months: int) -> datetime:
    year, month = divmod(now.year * 12 + (now.month - 1) - months, 12)
    month += 1
    days_in_month = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
                     31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return now.replace(year=year, month=month, day=min(now.day, days_in_month))


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def percentile(values: list[int], q: float) -> int | None:
    """Nearest-rank percentile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# --- rollup ---------------------------------------------------------------------------


def recompute_day(db, day: date) -> None:
    start, end = _day_bounds(day)
    rows = db.execute(
        select(TelemetryEvent.name, TelemetryEvent.app_version, TelemetryEvent.install_id, TelemetryEvent.props)
        .where(TelemetryEvent.at >= start, TelemetryEvent.at < end)
    ).all()
    events: dict[tuple[str, str], int] = defaultdict(int)
    installs: dict[tuple[str, str], set] = defaultdict(set)
    timings: dict[tuple[str, str], list[int]] = defaultdict(list)
    for name, version, install_id, props in rows:
        ms = (props or {}).get("ms")
        for key in ((name, version), (name, "*"), ("*", version), ("*", "*")):
            events[key] += 1
            installs[key].add(install_id)
            if isinstance(ms, int) and not isinstance(ms, bool) and key[0] != "*":
                timings[key].append(ms)
    db.execute(delete(TelemetryDaily).where(TelemetryDaily.day == day))
    for (name, version), count in events.items():
        db.add(
            TelemetryDaily(
                day=day,
                name=name,
                app_version=version,
                events=count,
                installs=len(installs[(name, version)]),
                p50_ms=percentile(timings[(name, version)], 0.5),
                p95_ms=percentile(timings[(name, version)], 0.95),
            )
        )


@periodic("telemetry.rollup", seconds=600)
def rollup(now: datetime) -> int:
    """Recompute the daily rows of every day that received events since the
    last run (with a 5-minute overlap for transactions still in flight)."""
    last = read("telemetry.rollup")
    with SessionLocal() as db:
        query = select(TelemetryEvent.at)
        if last is not None:
            query = query.where(TelemetryEvent.received_at > last.at - timedelta(minutes=5))
        # A day whose raw rows retention has started to delete is final.
        oldest = months_ago(now, RAW_EVENT_MONTHS).date() + timedelta(days=1)
        days = sorted({d for (at,) in db.execute(query) if (d := _aware(at).date()) >= oldest})
        for day in days:
            recompute_day(db, day)
        db.commit()
    mark("telemetry.rollup", now)
    return len(days)


# --- retention (§6.5) ---------------------------------------------------------------


def _delete_files(*keys: str | None) -> None:
    store = get_store()
    for key in keys:
        if key:
            try:
                store.delete(key)
            except Exception:  # noqa: BLE001 - a missing file must not stop retention
                log.exception("could not delete %s", key)


@periodic("telemetry.retention", seconds=24 * 3600)
def retention(now: datetime) -> dict[str, int]:
    rollup(now)  # daily counts first: they outlive the raw rows
    done = {}
    with SessionLocal() as db:
        done["events"] = db.execute(
            delete(TelemetryEvent).where(TelemetryEvent.received_at < months_ago(now, RAW_EVENT_MONTHS))
        ).rowcount
        done["batches"] = db.execute(
            delete(TelemetryBatch).where(TelemetryBatch.received_at < now - timedelta(days=BATCH_ID_DAYS))
        ).rowcount

        old_crashes = db.scalars(
            select(CrashReport).where(
                CrashReport.received_at < now - timedelta(days=CRASH_FILE_DAYS),
                (CrashReport.minidump_key.is_not(None)) | (CrashReport.log_key.is_not(None)),
            )
        ).all()
        for report in old_crashes:
            _delete_files(report.minidump_key, report.log_key)
            report.minidump_key = report.log_key = None
        done["crash_files"] = len(old_crashes)

        old_feedback = db.scalars(
            select(Feedback).where(Feedback.received_at < months_ago(now, FEEDBACK_MONTHS))
        ).all()
        for fb in old_feedback:
            _delete_files(fb.screenshot_key, fb.log_key)
            db.delete(fb)
        done["feedback"] = len(old_feedback)
        db.commit()
    log.info("retention: %s", done)
    return done


# --- deletions (5.5) ------------------------------------------------------------------


@periodic("telemetry.deletions", seconds=3600)
def apply_deletions(now: datetime) -> int:
    with SessionLocal() as db:
        pending = db.scalars(select(TelemetryDeletion).where(TelemetryDeletion.completed_at.is_(None))).all()
        for request in pending:
            install_id = request.install_id
            for report in db.scalars(select(CrashReport).where(CrashReport.install_id == install_id)).all():
                _delete_files(report.minidump_key, report.log_key)
                db.delete(report)
            for fb in db.scalars(select(Feedback).where(Feedback.install_id == install_id)).all():
                _delete_files(fb.screenshot_key, fb.log_key)
                db.delete(fb)
            db.execute(delete(TelemetryEvent).where(TelemetryEvent.install_id == install_id))
            db.execute(delete(TelemetryBatch).where(TelemetryBatch.install_id == install_id))
            # Every other pending request for the same id is answered too.
            for same in pending:
                if same.install_id == install_id:
                    same.completed_at = now
        db.commit()
        return len(pending)


# --- symbolication ----------------------------------------------------------------------

_tables: dict[str, symbolicate.SymbolTable] = {}


def _table(key: str) -> symbolicate.SymbolTable | None:
    if key not in _tables:
        try:
            with get_store().open(key) as fh:
                _tables[key] = symbolicate.parse_sym(fh.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            log.exception("unreadable symbol file %s", key)
            return None
        if len(_tables) > 64:
            _tables.pop(next(iter(_tables)))
    return _tables[key]


def move_report(db, report: CrashReport, frames: list[str], title: str) -> None:
    """Give a report its symbolicated frames and the group they sign."""
    old = report.signature
    new = resolve_group(db, crash_signature(frames, report.exception))
    report.frames = frames
    report.symbolicated = True
    if new == old:
        return
    group = db.get(CrashGroup, old)
    if group is not None:
        group.count = max(0, (group.count or 0) - 1)
        group.merged_into = new
    report.signature = new
    db.flush()
    target = add_to_group(db, report, title)
    if group is not None and target.fixed_in is None and group.fixed_in:
        target.fixed_in, target.status = group.fixed_in, group.status


@periodic("crash.symbolicate", seconds=60)
def symbolicate_pending(now: datetime, limit: int = 50) -> int:
    """Symbolicate reports whose version has symbols. Reports without symbols
    yet stay pending (for 180 days) and are done once the symbols arrive."""
    done = 0
    with SessionLocal() as db:
        reports = db.scalars(
            select(CrashReport)
            .where(
                CrashReport.symbolicated.is_(False),
                CrashReport.kind != "server",
                CrashReport.received_at > now - timedelta(days=CRASH_FILE_DAYS),
            )
            .order_by(CrashReport.received_at)
            .limit(limit)
        ).all()
        for report in reports:
            files = db.scalars(select(SymbolFile).where(SymbolFile.version == report.app_version)).all()
            if not files:
                continue
            frames = None
            if report.minidump_key and symbolicate.stackwalk_available(settings.minidump_stackwalk):
                store = get_store()
                with store.open(report.minidump_key) as fh:
                    dump = fh.read()
                symbols = {}
                for f in files:
                    with store.open(f.key) as fh:
                        symbols[f.key.removeprefix("symbols/")] = fh.read()
                frames = symbolicate.run_stackwalk(settings.minidump_stackwalk, dump, symbols)
            if not frames:
                tables = {}
                for f in files:
                    table = _table(f.key)
                    if table and table.code_file:
                        tables[table.code_file.lower()] = table
                frames, _changed = symbolicate.symbolicate_frames(list(report.frames), tables)
            title = frames[0].split("+0x")[0] if frames else report.signature
            move_report(db, report, frames, title)
            done += 1
        db.commit()
    return done
