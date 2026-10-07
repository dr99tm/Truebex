"""Shared FastAPI dependencies."""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import usage
from .billing.service import effective_plan
from .database import get_db
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
