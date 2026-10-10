"""The licence API (contract licence-api v1.0, endpoints 5.1-5.12).

Every route echoes `X-Truebex-Contract: licence-api/1.0` and answers errors
with the shared envelope (app/contract_http.py). 5.11 (`POST /licence/release`,
floating seats) is PF3's.
"""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError, contract
from ..database import get_db
from ..deps import DeviceCaller, LicenceCaller, get_current_user, get_device, get_device_any, get_session_or_device
from ..licence import clock, devices, links, seats, service, signing
from ..licence.models import Device
from ..licence.schemas import Activate, EntitlementRequest, LinkApprove, LinkPoll, LinkStart, TrialRequest
from ..models import User
from ..ratelimit import client_ip, limit

router = APIRouter(prefix="/licence", tags=["licence"], dependencies=[contract("licence-api", 1, 0)])


# --- 5.1-5.3 browser sign-in ------------------------------------------------------


@router.post(
    "/link",
    status_code=status.HTTP_201_CREATED,
    dependencies=[limit(client_ip, per_minute=10 / 60, burst=10, name="licence.link")],
)
def start_link(body: LinkStart, db: Session = Depends(get_db)) -> dict:
    """5.1: start a browser sign-in for this device (10 codes per IP per hour)."""
    row, secret = links.start(
        db,
        device_name=body.device_name,
        fingerprint=body.fingerprint,
        app_version=body.app_version,
        now=clock.now(),
    )
    return {
        "link_code": row.link_code,
        "poll_secret": secret,
        "verify_url": links.verify_url(row.link_code),
        "expires_in_s": int(links.LIFETIME.total_seconds()),
        "interval_s": links.INTERVAL_S,
    }


@router.post("/link/poll")
def poll_link(body: LinkPoll, db: Session = Depends(get_db)) -> dict:
    """5.2: pending, or (once) approved with a session token."""
    return links.poll(db, body.poll_secret, clock.now())


@router.post("/link/approve")
def approve_link(
    body: LinkApprove, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """5.3: the signed-in website approves or denies a code."""
    row = links.decide(db, body.link_code, current, body.approve, clock.now())
    return {"status": "approved" if body.approve else "denied", "device_name": row.device_name}


@router.get("/link/{link_code}")
def lookup_link(
    link_code: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Website only (outside the app contract): what /dashboard/link/ shows
    before Approve, so nobody approves a device they cannot see."""
    code = links.normalise_code(link_code)
    if code is None:
        raise ContractError(
            "validation_failed",
            422,
            "link_code: a link code is 8 characters like QX7D-K9MP",
            {"fields": [{"field": "link_code", "in": "path", "message": "malformed link code"}]},
        )
    row = links.lookup(db, code, clock.now())
    return {
        "link_code": row.link_code,
        "device_name": row.device_name,
        "app_version": row.app_version,
        "status": row.status,
        "expires_at": clock.rfc3339(row.expires_at),
    }


# --- 5.4-5.6 activation, entitlements, trial --------------------------------------


@router.post("/activate", status_code=status.HTTP_201_CREATED)
def activate(
    body: Activate,
    response: Response,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """5.4: register this device (session from 5.2 or /auth/login)."""
    service.require_signing()
    now = clock.now()
    seat = seats.seat_source(db, current)
    device, token, created = devices.activate(
        db,
        current,
        fingerprint=body.fingerprint,
        name=body.device_name,
        os=body.os,
        app_version=body.app_version,
        replace_device_id=body.replace_device_id,
        devices_limit=seat.devices_limit,
        now=now,
    )
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return {
        "device_id": device.device_id,
        "device_token": token,
        # A full floating pool does not stop activation: the device gets its
        # token and the personal seat; its next 5.5 asks for a lease again.
        "entitlement": service.issue(db, current, device, now, when_full="free"),
    }


@router.post("/entitlement")
def entitlement(
    body: EntitlementRequest,
    caller: DeviceCaller = Depends(get_device),
    db: Session = Depends(get_db),
) -> dict:
    """5.5: a fresh signed entitlement. POST, so no intermediary caches it."""
    service.require_signing()
    now = clock.now()
    device = caller.device
    if body.fingerprint != device.fingerprint:
        devices.deactivate(db, device, "fingerprint_mismatch", now)
        db.commit()
        raise ContractError(
            "fingerprint_mismatch",
            409,
            "This device token belongs to another computer and has been signed out.",
        )
    if body.app_version:
        device.app_version = body.app_version
    return {"entitlement": service.issue(db, caller.user, device, now)}


@router.post("/trial", status_code=status.HTTP_201_CREATED)
def trial(
    body: TrialRequest, caller: DeviceCaller = Depends(get_device), db: Session = Depends(get_db)
) -> dict:
    """5.6: start the one 14-day Pro trial of this account and this computer."""
    envelope, ends = service.start_trial(db, caller.user, caller.device, body.plan, clock.now())
    return {"entitlement": envelope, "trial_ends_at": clock.rfc3339(ends)}


# --- 5.7-5.10 account, devices, sign-out ------------------------------------------


@router.get("/account")
def account(caller: DeviceCaller = Depends(get_device), db: Session = Depends(get_db)) -> dict:
    """5.7: the app's Account panel."""
    return service.account_panel(db, caller.user, caller.device)


@router.get("/devices")
def list_devices(
    caller: LicenceCaller = Depends(get_session_or_device), db: Session = Depends(get_db)
) -> dict:
    """5.8: the account's active devices; `current` marks the caller."""
    current_id = caller.device.device_id if caller.device else None
    seat = seats.seat_source(db, caller.user)
    return {
        "devices": [devices.device_json(d, current_id) for d in devices.active(db, caller.user.id)],
        "limit": seat.devices_limit,
    }


@router.delete("/devices/{device_id}")
def remove_device(
    device_id: str,
    caller: LicenceCaller = Depends(get_session_or_device),
    db: Session = Depends(get_db),
) -> dict:
    """5.9: remove a device: its slot is freed and its token stops working."""
    device = db.scalar(
        select(Device).where(Device.device_id == device_id, Device.user_id == caller.user.id)
    )
    if device is None:
        raise ContractError("not_found", 404, "That device is not on your account.")
    devices.deactivate(db, device, "removed", clock.now())
    db.commit()
    out = devices.device_json(device, caller.device.device_id if caller.device else None)
    out["deactivated_at"] = clock.rfc3339(device.deactivated_at)
    return out


@router.post("/deactivate")
def deactivate(caller: DeviceCaller = Depends(get_device_any), db: Session = Depends(get_db)) -> dict:
    """5.10: sign this device out (repeating it is harmless)."""
    device = caller.device
    devices.deactivate(db, device, "signed_out", clock.now())
    db.commit()
    return {"device_id": device.device_id, "deactivated_at": clock.rfc3339(device.deactivated_at)}


# --- 5.11 floating seats (PF3) -----------------------------------------------------


@router.post("/release", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def release(caller: DeviceCaller = Depends(get_device), db: Session = Depends(get_db)) -> None:
    """5.11: hand this device's floating seat back at exit (repeating it is
    harmless); 409 `not_floating` when the device's seat does not float."""
    from ..orgs import seats as org_seats

    if not org_seats.release(db, caller.device, clock.now()):
        raise ContractError("not_floating", 409, "This device's seat is not a floating seat.")
    # None: the 204 keeps the X-Truebex-Contract header the router set.


# --- 5.12 published keys ----------------------------------------------------------


@router.get("/keys")
def keys(request: Request) -> dict:
    """5.12: public keys, for tests and the website. The app pins its own."""
    return {"keys": [k.as_json() for k in signing.published_keys()]}
