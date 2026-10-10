"""Who is calling a project route (contract §4).

A device token (`tbx_dev_…`, the desktop app and the headset target) or a
session token (the website, PF9, PF10). API keys are for `/v1/projects…`
(PF12) and are refused here with 401, except on 5.5, which answers every
non-session credential 403 `session_required`.
"""

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..database import get_db
from ..deps import get_session_or_device
from ..licence.models import Device
from ..models import ApiKey, User
from ..security import API_KEY_PREFIX, hash_api_key
from ..uploads.credentials import UploadCaller

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class ProjectCaller:
    user: User
    kind: str  # device | session | api_key (5.5 only)
    device: Device | None = None

    @property
    def is_device(self) -> bool:
        return self.kind == "device"

    def upload_caller(self) -> UploadCaller:
        """The same credential as the upload protocol sees it (share-bundle §4)."""
        if self.device is not None:
            return UploadCaller(account_id=self.user.id, kind="device", credential_id=self.device.device_id)
        return UploadCaller(account_id=self.user.id, kind="session")


def get_project_caller(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> ProjectCaller:
    if creds is None:
        raise ContractError(
            "unauthenticated", 401, "Sign in to use projects.", headers={"WWW-Authenticate": "Bearer"}
        )
    found = get_session_or_device(creds, db)
    if found.device is not None:
        return ProjectCaller(user=found.user, kind="device", device=found.device)
    return ProjectCaller(user=found.user, kind="session")


def get_any_caller(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> ProjectCaller:
    """Like get_project_caller, but a valid API key resolves (kind api_key)."""
    raw = creds.credentials if creds else ""
    if raw.startswith(API_KEY_PREFIX):
        key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw)))
        user = db.get(User, key.user_id) if key is not None and key.revoked_at is None else None
        if user is None:
            raise ContractError(
                "unauthenticated", 401, "Invalid or revoked API key.", headers={"WWW-Authenticate": "Bearer"}
            )
        return ProjectCaller(user=user, kind="api_key")
    return get_project_caller(creds, db)


def require_session(caller: ProjectCaller, action: str = "delete a project") -> None:
    if caller.kind != "session":
        raise ContractError(
            "session_required",
            403,
            f"Sign in on truebex.com to {action}. The app and API keys cannot.",
            {"credential": caller.kind},
        )
