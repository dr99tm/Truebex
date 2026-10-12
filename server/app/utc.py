"""Times the API answers: RFC 3339 UTC with `Z`, whatever the database.

PF2c made `UtcDateTime` for the billing models; PF14c moved it here so every
response model uses it (tests/test_pf14c_utc_times.py walks every route's
response model and fails on a plain `datetime`). Routes that answer a dict
format their times with `licence.clock.rfc3339`.
"""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator


def _utc(dt: datetime) -> datetime:
    # SQLite hands back naive UTC; Postgres answers in the session's time zone.
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


# Pydantic writes a UTC time with `Z`; microseconds are kept, so a time read
# back still equals the stored one. On an input model it turns any RFC 3339
# offset into UTC (and reads a zone-less time as UTC).
UtcDateTime = Annotated[datetime, AfterValidator(_utc)]
