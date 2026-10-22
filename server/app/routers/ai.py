"""The metered assistant proxy (contract ai-proxy 1.1, 5.1-5.4; a 1.0 client is served).

Auth: the desktop app's device token whose entitlement holds `ai.metered`;
session tokens, API keys and worker tokens are refused (403 `forbidden`), no
or a bad token is 401. Every error uses the shared envelope; after a stream
has begun an error arrives in-band as `event: error`.
"""

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..ai import credits, proxy
from ..contract_http import ContractError, contract
from ..database import SessionLocal, get_db
from ..deps import _resolve_device
from ..licence.devices import DEVICE_TOKEN_PREFIX
from ..licence.models import Device
from ..models import User
from ..security import API_KEY_PREFIX, decode_access_token
from ..uploads.credentials import WORKER_TOKEN_PREFIX

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[contract("ai-proxy", 1, 1)])
_bearer = HTTPBearer(auto_error=False)


@dataclass
class AiCaller:
    user: User
    device: Device


def _forbidden() -> ContractError:
    return ContractError("forbidden", 403, "Truebex AI answers the desktop app only: sign in from Truebex.", {})


def authenticate(db: Session, raw: str) -> AiCaller:
    if not raw:
        raise ContractError(
            "unauthenticated", 401, "This call needs the app's device token (Authorization: Bearer tbx_dev_…).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if raw.startswith(DEVICE_TOKEN_PREFIX):
        found = _resolve_device(raw, db, allow_inactive=False)
        return AiCaller(user=found.user, device=found.device)
    if raw.startswith((API_KEY_PREFIX, WORKER_TOKEN_PREFIX)) or decode_access_token(raw) is not None:
        raise _forbidden()
    raise ContractError("unauthenticated", 401, "This token is not valid.", headers={"WWW-Authenticate": "Bearer"})


def get_ai_caller(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> AiCaller:
    return authenticate(db, creds.credentials if creds else "")


def get_ai_ids(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> tuple[int, str]:
    """(user id, device id), from a session closed again at once: a streamed
    turn holds no database connection while it runs."""
    with SessionLocal() as db:
        caller = authenticate(db, creds.credentials if creds else "")
        return caller.user.id, caller.device.device_id


@router.get("/models")
def models(caller: AiCaller = Depends(get_ai_caller), db: Session = Depends(get_db)) -> dict:
    plan = credits.plan_of(db, caller.user)
    return proxy.models_json(plan.id, plan.features)


@router.get("/balance")
def balance(caller: AiCaller = Depends(get_ai_caller), db: Session = Depends(get_db)) -> dict:
    return credits.balance_json(db, caller.user)


def _key(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower()
    if len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
        raise ContractError(
            "validation_failed", 422, "Idempotency-Key must be 32 hex characters.",
            {"fields": [{"field": "Idempotency-Key", "in": "header", "message": "32 hex characters"}]},
        )
    return key


@router.post("/messages")
async def messages(
    request: Request,
    idempotency_key: str | None = Header(default=None),
    ids: tuple[int, str] = Depends(get_ai_ids),
):
    user_id, device_id = ids
    key = _key(idempotency_key)
    raw = await proxy.read_body(request)
    body = proxy.parse_json(raw)
    prepared = await run_in_threadpool(proxy.prepare, user_id, device_id, body, key, proxy.rid_of(request))
    if prepared.turn.stream:
        return await proxy.stream(request, prepared)
    return await proxy.whole(request, prepared)


@router.post("/messages/count")
async def count(request: Request, ids: tuple[int, str] = Depends(get_ai_ids)):
    user_id, device_id = ids
    raw = await proxy.read_body(request)
    body = proxy.parse_json(raw)
    if isinstance(body, dict):
        body = {k: v for k, v in body.items() if k != "stream"}
    prepared = await run_in_threadpool(proxy.prepare, user_id, device_id, body, None, proxy.rid_of(request), counting=True)
    return await proxy.count(request, prepared)
