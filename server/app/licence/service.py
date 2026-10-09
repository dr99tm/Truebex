"""Entitlement documents, the Account panel and trials (contract 5.5-5.7, §6).

The document's tier comes from `seats.seat_source(user)`; its features and
limits from that tier's catalogue entry; its lifetimes from the seat kind
(§6.1). It is signed over its RFC 8785 bytes with the lic-* key.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..billing.service import TRIAL_PROVIDER, is_live
from ..config import get_settings
from ..contract_http import ContractError
from ..models import Device, Subscription, TrialFingerprint, User
from ..plans import get_plan
from . import clock, devices, events, seats, signing
from .ids import uuid7_hex

SCHEMA = "truebex-entitlement/1"
TRIAL_PLANS = ("pro",)


@dataclass(frozen=True)
class Durations:
    refresh: timedelta
    expires: timedelta


# Contract §6.1. Personal, named, trial and free documents: refresh after 24 h,
# honoured offline for 14 days. Floating seats: 30 min and 2 h.
DEFAULT_DURATIONS = Durations(refresh=timedelta(hours=24), expires=timedelta(days=14))
DURATIONS = {"floating": Durations(refresh=timedelta(minutes=30), expires=timedelta(hours=2))}


def durations_for(seat_kind: str) -> Durations:
    return DURATIONS.get(seat_kind, DEFAULT_DURATIONS)


def ensure_author_id(db: Session, user: User) -> str:
    """The account's project-log author id, minted once (project-log.md §6)."""
    if not user.author_id:
        user.author_id = uuid7_hex()
        db.add(user)
        db.commit()
    return user.author_id


def _signing_key():
    try:
        return signing.licence_private_key()
    except LookupError:
        raise ContractError(
            "unavailable", 503, "Licensing is not set up on this server yet. Try again later."
        )


def build_document(db: Session, user: User, device: Device, now: datetime) -> tuple[dict, seats.Seat]:
    seat = seats.seat_source(db, user)
    tier = get_plan(seat.plan)
    life = durations_for(seat.kind)
    issued = clock.floor_s(now)
    expires = issued + life.expires
    if seat.ends_at is not None:
        expires = min(expires, clock.floor_s(seat.ends_at))
    refresh = min(issued + life.refresh, expires)
    doc = {
        "schema": SCHEMA,
        "plan": tier.id,
        "features": sorted(set(tier.features)),
        "limits": dict(tier.limits),
        "seat_kind": seat.kind,
        "trial": seat.kind == "trial",
        "device_id": device.device_id,
        "fingerprint": device.fingerprint,
        "issued_at": clock.rfc3339(issued),
        "refresh_after": clock.rfc3339(refresh),
        "expires_at": clock.rfc3339(expires),
        "plan_period_end": clock.rfc3339(seat.period_end),
        "nonce": secrets.token_hex(16),
        "account": {
            "user_id": user.id,
            "email": user.email,
            "author_id": ensure_author_id(db, user),
            "org_id": seat.org_id,
        },
    }
    return doc, seat


def issue(db: Session, user: User, device: Device, now: datetime | None = None) -> dict:
    """A fresh signed envelope for this device (also records its seat)."""
    key = _signing_key()
    now = now or clock.now()
    doc, seat = build_document(db, user, device, now)
    device.seat_kind = seat.kind
    device.org_id = seat.org_id
    device.last_seen_at = now
    db.add(device)
    db.commit()
    return signing.sign_envelope(doc, key, get_settings().licence_key_id)


def require_signing() -> None:
    """503 before doing any work when the server cannot sign."""
    _signing_key()


# --- trials (5.6) -------------------------------------------------------------


def _trial_row(db: Session, user: User) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user.id, Subscription.provider == TRIAL_PROVIDER)
        .order_by(Subscription.created_at.desc())
    )


def trial_status(db: Session, user: User) -> dict:
    row = _trial_row(db, user)
    live = row is not None and is_live(row)
    return {
        "used": user.trial_used_at is not None or row is not None,
        "active": live,
        "ends_at": clock.rfc3339(row.current_period_end) if live else None,
    }


def start_trial(db: Session, user: User, device: Device, plan: str, now: datetime) -> tuple[dict, datetime]:
    require_signing()
    used = clock.aware(user.trial_used_at)
    if used is None:
        by_machine = db.get(TrialFingerprint, device.fingerprint)
        if by_machine is not None:
            used = clock.aware(by_machine.used_at)
    if used is not None:
        raise ContractError(
            "trial_used",
            409,
            "The free trial has already been used on this account or this computer.",
            {"used_at": clock.rfc3339(used)},
        )
    seat = seats.seat_source(db, user)
    if seat.kind != "free" and seat.kind != "trial":
        raise ContractError(
            "plan_active", 409, f"You already have {get_plan(seat.plan).name}.", {"plan": seat.plan}
        )
    ends = clock.floor_s(now) + timedelta(days=get_settings().trial_days)
    db.add(
        Subscription(
            user_id=user.id,
            plan=plan,
            provider=TRIAL_PROVIDER,
            status="active",
            current_period_end=ends,
        )
    )
    user.trial_used_at = now
    db.add(user)
    db.add(TrialFingerprint(fingerprint=device.fingerprint, user_id=user.id, used_at=now))
    events.record(db, "trial.started", user_id=user.id, device_id=device.device_id, at=now, plan=plan, ends_at=clock.rfc3339(ends))
    db.commit()
    return issue(db, user, device, now), ends


# --- the Account panel (5.7) ----------------------------------------------------


def account_panel(db: Session, user: User, device: Device) -> dict:
    seat = seats.seat_source(db, user)
    tier = get_plan(seat.plan)
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "avatar_url": user.avatar_url},
        "author_id": ensure_author_id(db, user),
        "plan": tier.id,
        "plan_name": tier.name,
        "trial": trial_status(db, user),
        "seat": {"kind": seat.kind, "org_id": seat.org_id, "org_name": seat.org_name},
        "seats": {"total": seat.seats_total, "assigned": seat.seats_assigned},
        "devices": {"active": devices.count_active(db, user.id), "limit": seat.devices_limit},
        "manage_url": f"{get_settings().site_url.rstrip('/')}/dashboard/billing/",
    }
