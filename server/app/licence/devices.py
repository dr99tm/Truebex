"""Devices: activation, device tokens, removal and the 90-day lapse.

A device token is `tbx_dev_` + 43 random characters, shown to the app once
and stored as SHA-256 (like API keys). One active row per (account,
fingerprint): activating the same machine again keeps its device_id and
rotates the token, so the old token stops working at once.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..models import User
from .models import Device
from . import clock, events
from .ids import uuid7_hex

DEVICE_TOKEN_PREFIX = "tbx_dev_"
# Contract §4: a device token lapses after 90 days unused.
LAPSE_AFTER = timedelta(days=90)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_token() -> tuple[str, str]:
    token = DEVICE_TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, hash_token(token)


def find_by_token(db: Session, raw: str) -> Device | None:
    return db.scalar(select(Device).where(Device.token_hash == hash_token(raw)))


def active(db: Session, user_id: int) -> list[Device]:
    return list(
        db.scalars(
            select(Device)
            .where(Device.user_id == user_id, Device.deactivated_at.is_(None))
            .order_by(Device.activated_at)
        )
    )


def count_active(db: Session, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(Device.device_id)).where(
                Device.user_id == user_id, Device.deactivated_at.is_(None)
            )
        )
        or 0
    )


def is_lapsed(device: Device, now: datetime) -> bool:
    return now - clock.aware(device.last_seen_at) > LAPSE_AFTER


def deactivate(db: Session, device: Device, reason: str, now: datetime) -> bool:
    """Revoke a device's token and free its slot. False if it already was."""
    if device.deactivated_at is not None:
        return False
    device.deactivated_at = now
    device.deactivated_reason = reason
    db.add(device)
    if reason != "replaced":  # a replacement is recorded as device.replaced
        events.record(db, "device.revoked", user_id=device.user_id, device_id=device.device_id, at=now, reason=reason)
    return True


def device_json(device: Device, current_id: str | None = None) -> dict:
    return {
        "device_id": device.device_id,
        "name": device.name,
        "os": device.os,
        "app_version": device.app_version,
        "activated_at": clock.rfc3339(device.activated_at),
        "last_seen_at": clock.rfc3339(device.last_seen_at),
        "current": device.device_id == current_id,
    }


def activate(
    db: Session,
    user: User,
    *,
    fingerprint: str,
    name: str,
    os: str,
    app_version: str,
    replace_device_id: str | None,
    devices_limit: int | None,
    now: datetime,
) -> tuple[Device, str, bool]:
    """Register this machine for `user`. Returns (device, token, created)."""
    existing = db.scalar(
        select(Device).where(
            Device.user_id == user.id,
            Device.fingerprint == fingerprint,
            Device.deactivated_at.is_(None),
        )
    )
    replaced: Device | None = None
    if replace_device_id and (existing is None or replace_device_id != existing.device_id):
        replaced = db.scalar(
            select(Device).where(
                Device.device_id == replace_device_id,
                Device.user_id == user.id,
                Device.deactivated_at.is_(None),
            )
        )
        if replaced is None:
            raise ContractError("not_found", 404, "That device is not active on your account.")
        deactivate(db, replaced, "replaced", now)
        db.flush()  # the session does not autoflush; the count below must see it

    token, digest = new_token()
    if existing is not None:
        existing.token_hash = digest
        existing.name, existing.os, existing.app_version = name, os, app_version
        existing.last_seen_at = now
        db.add(existing)
        events.record(db, "device.activated", user_id=user.id, device_id=existing.device_id, at=now, new=False)
        return existing, token, False

    if devices_limit is not None and count_active(db, user.id) >= devices_limit:
        listed = [
            {"device_id": d.device_id, "name": d.name, "os": d.os, "app_version": d.app_version,
             "last_seen_at": clock.rfc3339(d.last_seen_at)}
            for d in active(db, user.id)
        ]
        db.rollback()  # keep nothing of this call but the event
        events.record(db, "seat.device_limit", user_id=user.id, at=now, limit=devices_limit, active=len(listed))
        db.commit()
        noun = "device is" if devices_limit == 1 else "devices are"
        raise ContractError(
            "device_limit",
            409,
            f"{devices_limit} {noun} active on this seat. Remove one to continue.",
            {"limit": devices_limit, "devices": listed},
        )

    device = Device(
        device_id=uuid7_hex(),
        user_id=user.id,
        fingerprint=fingerprint,
        name=name,
        os=os,
        app_version=app_version,
        token_hash=digest,
        activated_at=now,
        last_seen_at=now,
    )
    db.add(device)
    events.record(db, "device.activated", user_id=user.id, device_id=device.device_id, at=now, new=True)
    if replaced is not None:
        events.record(
            db, "device.replaced", user_id=user.id, device_id=device.device_id, at=now,
            replaced_device_id=replaced.device_id,
        )
    return device, token, True


def lapse_unused(db: Session, now: datetime) -> int:
    """The licence.devices.lapse job: revoke tokens unused for 90 days."""
    cutoff = now - LAPSE_AFTER
    stale = list(
        db.scalars(
            select(Device).where(Device.deactivated_at.is_(None), Device.last_seen_at < cutoff)
        )
    )
    for device in stale:
        deactivate(db, device, "lapsed", now)
    return len(stale)
