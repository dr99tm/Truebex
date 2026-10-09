"""Operations state the API checks itself (PF14).

* `ops_status` rows: named timestamps. `worker.heartbeat` (every 30 s),
  `backup.base` (written by infra/host/bin/backup-base.sh after a nightly base
  backup), `backup.wal` (fallback when pg_stat_archiver is not available).
* `backup.check` (every 15 min) alerts when the last WAL archive is older than
  15 min or the last base backup older than 26 h, once per state change, and
  sends a recovery notice when both are fresh again.
* Alerts go by e-mail (ALERT_EMAIL, the mail adapter) and phone push
  (ALERT_PUSH_URL, an ntfy-style topic URL). Uptime alerts come from the
  hosted monitor, which also watches /health/deep.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text

from .config import get_settings
from .database import SessionLocal, dialect_insert
from .models import OpsStatus
from .tasks import periodic

log = logging.getLogger("truebex.ops")
settings = get_settings()

WAL_MAX_AGE = timedelta(minutes=15)
BASE_MAX_AGE = timedelta(hours=26)


def _aware(dt: datetime | None) -> datetime | None:
    # SQLite hands back naive datetimes; everything stored is UTC.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def mark(name: str, at: datetime | None = None, detail: str | None = None) -> None:
    """Upsert a named timestamp."""
    at = at or datetime.now(timezone.utc)
    with SessionLocal() as db:
        stmt = dialect_insert(db, OpsStatus).values(name=name, at=at, detail=detail)
        stmt = stmt.on_conflict_do_update(index_elements=["name"], set_={"at": at, "detail": detail})
        db.execute(stmt)
        db.commit()


def read(name: str) -> OpsStatus | None:
    with SessionLocal() as db:
        row = db.get(OpsStatus, name)
        if row is not None:
            db.expunge(row)
            row.at = _aware(row.at)
        return row


def heartbeat_age_s(now: datetime | None = None) -> int | None:
    row = read("worker.heartbeat")
    if row is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0, int((now - row.at).total_seconds()))


@periodic("worker.heartbeat", seconds=30)
def heartbeat(now: datetime) -> None:
    mark("worker.heartbeat", now)


def _last_wal_archive() -> datetime | None:
    """Postgres knows when it last archived a WAL segment; elsewhere the
    backup scripts' `backup.wal` marker stands in."""
    with SessionLocal() as db:
        if db.get_bind().dialect.name == "postgresql":
            row = db.execute(text("SELECT last_archived_time FROM pg_stat_archiver")).first()
            if row and row[0]:
                return _aware(row[0])
    marker = read("backup.wal")
    return marker.at if marker else None


def _push(title: str, body: str) -> None:
    if not settings.alert_push_url:
        return
    try:
        httpx.post(
            settings.alert_push_url,
            content=body.encode("utf-8"),
            headers={"Title": title, "Priority": "high", "Tags": "warning"},
            timeout=10,
        )
    except httpx.HTTPError:
        log.exception("alert push failed")


def alert(title: str, body: str) -> None:
    log.warning("ALERT %s: %s", title, body)
    if settings.alert_email:
        from .mail import send_mail

        send_mail(settings.alert_email, "alert", {"subject": title, "body": body})
    _push(title, body)


def backup_check(now: datetime) -> list[str]:
    """Problems with the backups right now (alerting once per change)."""
    problems = []
    base = read("backup.base")
    wal = _last_wal_archive()
    if base is None:
        if settings.backup_expected:
            problems.append("no base backup recorded")
    elif now - base.at > BASE_MAX_AGE:
        problems.append(f"base backup is {int((now - base.at).total_seconds() // 3600)} h old")
    if wal is None:
        if settings.backup_expected:
            problems.append("no WAL archive recorded")
    elif now - wal > WAL_MAX_AGE:
        problems.append(f"last WAL archive is {int((now - wal).total_seconds() // 60)} min old")

    state = read("alert.backup")
    was_failing = bool(state and state.detail)
    if problems and not was_failing:
        alert("Backups are stale", "\n".join(problems))
    elif not problems and was_failing:
        alert("Backups are fresh again", "The base backup and WAL archive are current.")
    mark("alert.backup", now, "\n".join(problems) or None)
    return problems


@periodic("backup.check", seconds=15 * 60)
def _backup_check_job(now: datetime) -> None:
    backup_check(now)


def main(argv: list[str] | None = None) -> int:
    """`python -m app.ops alert TITLE BODY` (the host checks call it) and
    `python -m app.ops mark NAME` (a timestamp, e.g. from a backup script)."""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m app.ops")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("alert")
    a.add_argument("title")
    a.add_argument("body")
    m = sub.add_parser("mark")
    m.add_argument("name")
    args = parser.parse_args(argv)
    if args.command == "alert":
        alert(args.title, args.body)
    else:
        mark(args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
