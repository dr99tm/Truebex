"""Shared FastAPI dependencies."""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import usage
from .billing.service import effective_plan
from .contract_http import ContractError
from .database import get_db
from .licence.models import Device
from .models import ApiKey, User
from .plans import get_plan
from .security import API_KEY_PREFIX, decode_access_token, hash_api_key

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the signed-in user from the Bearer session token (JWT)."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise invalid

    subject = decode_access_token(creds.credentials)
    if subject is None:
        raise invalid

    try:
        user_id = int(subject)
    except ValueError:
        raise invalid

    user = db.get(User, user_id)
    if user is None:
        raise invalid
    return user


def require_admin(current: User = Depends(get_current_user)) -> User:
    """Admins only (`users.is_admin`, set by hand like "enterprise"): 401
    signed out, 403 others."""
    if not current.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admins only."
        )
    return current


def device_for_token(db: Session, raw: str | None) -> Device | None:
    """The active device behind a `tbx_dev_…` token, or None (unknown,
    removed, signed out, lapsed, or not a device token at all). Read-only:
    telemetry (5.4 replies) only looks the device up."""
    from .licence import clock, devices

    if not raw or not raw.startswith(devices.DEVICE_TOKEN_PREFIX):
        return None
    device = devices.find_by_token(db, raw)
    if device is None or device.deactivated_at is not None:
        return None
    if devices.is_lapsed(device, clock.now()):
        return None
    return device


@dataclass
class ApiCaller:
    user: User
    key: ApiKey


def api_key_auth(
    request: Request,
    response: Response,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ApiCaller:
    """Authenticate a developer API call by key, enforce the monthly quota,
    and meter the request.

    The key is accepted as `Authorization: Bearer tbx_live_…` or `X-API-Key`.
    """
    raw = x_api_key or (creds.credentials if creds else None)
    if not raw or not raw.startswith(API_KEY_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw)))
    if key is None or key.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
        )
    if key.supplier_id:  # PF8: a supplier key feeds its catalogue only
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This is a supplier feed key; create a developer key under Dashboard → API keys.",
        )
    user = db.get(User, key.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    plan = get_plan(effective_plan(db, user))
    used = usage.used_this_month(db, user.id)
    response.headers["X-RateLimit-Limit"] = str(plan.monthly_requests)
    if used >= plan.monthly_requests:
        response.headers["X-RateLimit-Remaining"] = "0"
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Monthly limit of {plan.monthly_requests} requests reached "
                f"for the {plan.name} plan."
            ),
            headers={
                "X-RateLimit-Limit": str(plan.monthly_requests),
                "X-RateLimit-Remaining": "0",
            },
        )

    route = request.scope.get("route")
    endpoint = getattr(route, "path", request.url.path)[:100]
    usage.record(db, user.id, key.id, endpoint)
    key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    response.headers["X-RateLimit-Remaining"] = str(
        max(plan.monthly_requests - used - 1, 0)
    )
    return ApiCaller(user=user, key=key)


# --- Licence API credentials (PF1, contract §4) --------------------------------
# The prefix tells them apart: tbx_dev_ device, tbx_live_ API key (never
# accepted by /licence/*), anything else a session JWT.


@dataclass
class DeviceCaller:
    user: User
    device: Device


@dataclass
class LicenceCaller:
    user: User
    device: Device | None  # None when signed in with a session (the website)


def _unauthenticated(detail: str) -> ContractError:
    return ContractError("unauthenticated", 401, detail, headers={"WWW-Authenticate": "Bearer"})


def _revoked() -> ContractError:
    return ContractError(
        "device_revoked",
        401,
        "This device was signed out. Sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_device(raw: str, db: Session, *, allow_inactive: bool) -> DeviceCaller:
    from .licence import clock, devices

    device = devices.find_by_token(db, raw)
    if device is None or (device.deactivated_at is not None and not allow_inactive):
        raise _revoked()
    now = clock.now()
    if device.deactivated_at is None:
        if devices.is_lapsed(device, now):
            devices.deactivate(db, device, "lapsed", now)
            db.commit()
            raise _revoked()
        device.last_seen_at = now
        db.add(device)
        db.commit()
    user = db.get(User, device.user_id)
    if user is None:
        raise _revoked()
    return DeviceCaller(user=user, device=device)


def get_device(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> DeviceCaller:
    """The calling device, from `Authorization: Bearer tbx_dev_…`."""
    from .licence.devices import DEVICE_TOKEN_PREFIX

    raw = creds.credentials if creds else ""
    if not raw.startswith(DEVICE_TOKEN_PREFIX):
        raise _unauthenticated("This call needs a device token (Authorization: Bearer tbx_dev_…).")
    return _resolve_device(raw, db, allow_inactive=False)


def get_device_any(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> DeviceCaller:
    """Like get_device, but a signed-out device still resolves (5.10 is idempotent)."""
    from .licence.devices import DEVICE_TOKEN_PREFIX

    raw = creds.credentials if creds else ""
    if not raw.startswith(DEVICE_TOKEN_PREFIX):
        raise _unauthenticated("This call needs a device token (Authorization: Bearer tbx_dev_…).")
    return _resolve_device(raw, db, allow_inactive=True)


def get_session_or_device(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> LicenceCaller:
    from .licence.devices import DEVICE_TOKEN_PREFIX

    raw = creds.credentials if creds else ""
    if raw.startswith(DEVICE_TOKEN_PREFIX):
        caller = _resolve_device(raw, db, allow_inactive=False)
        return LicenceCaller(user=caller.user, device=caller.device)
    if raw.startswith(API_KEY_PREFIX):
        raise _unauthenticated("API keys are not accepted here. Sign in instead.")
    return LicenceCaller(user=get_current_user(creds, db), device=None)

