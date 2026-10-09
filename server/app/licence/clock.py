"""Time for the licence API: one patchable `now()` and the wire format.

Contract §5: times are RFC 3339 UTC with `Z` (whole seconds here).
"""

from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    # SQLite hands back naive datetimes; everything stored is UTC.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def floor_s(dt: datetime) -> datetime:
    return aware(dt).astimezone(timezone.utc).replace(microsecond=0)


def rfc3339(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return floor_s(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_rfc3339(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
