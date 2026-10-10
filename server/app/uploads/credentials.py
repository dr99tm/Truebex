"""Who may upload (share-bundle §4): a device token, a website session or a
render worker's token, resolved to the account the session will belong to.

Worker tokens (`tbx_wrk_…`) are issued by PF6 (render-jobs §4). PF6 installs
its lookup with `set_worker_resolver`; until then a worker token is refused
with 401 like any unknown credential.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..database import get_db
from ..deps import get_session_or_device

WORKER_TOKEN_PREFIX = "tbx_wrk_"

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UploadCaller:
    account_id: int
    kind: str  # device | session | worker
    credential_id: str | None = None  # the device id or the worker id


WorkerResolver = Callable[[Session, str], UploadCaller | None]
_worker_resolver: WorkerResolver | None = None


def set_worker_resolver(resolver: WorkerResolver | None) -> None:
    """PF6: map a raw `tbx_wrk_…` token to its caller (kind "worker"), or None."""
    global _worker_resolver
    _worker_resolver = resolver


def get_upload_caller(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> UploadCaller:
    raw = creds.credentials if creds else ""
    if raw.startswith(WORKER_TOKEN_PREFIX):
        caller = _worker_resolver(db, raw) if _worker_resolver else None
        if caller is None or caller.kind != "worker":
            raise ContractError(
                "unauthenticated", 401, "This worker token is not valid.", headers={"WWW-Authenticate": "Bearer"}
            )
        return caller
    found = get_session_or_device(creds, db)
    if found.device is not None:
        return UploadCaller(account_id=found.user.id, kind="device", credential_id=found.device.device_id)
    return UploadCaller(account_id=found.user.id, kind="session")
