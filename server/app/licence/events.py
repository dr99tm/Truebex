"""Append-only licence events (PF3 builds the audit log on them).

Kinds: link.approved, link.denied, device.activated, device.replaced,
device.revoked (details.reason: removed | signed_out | lapsed |
fingerprint_mismatch), trial.started, seat.device_limit. Rows are only ever
inserted; nothing here updates or deletes one. Details never hold tokens,
poll secrets or fingerprints.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from ..models import LicenceEvent
from . import clock


def record(
    db: Session,
    kind: str,
    *,
    user_id: int | None = None,
    device_id: str | None = None,
    at: datetime | None = None,
    **details,
) -> LicenceEvent:
    """Add one event to the session (the caller commits)."""
    event = LicenceEvent(
        at=at or clock.now(), user_id=user_id, device_id=device_id, kind=kind, details=details
    )
    db.add(event)
    return event
