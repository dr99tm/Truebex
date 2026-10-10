"""Worker credentials (contract §4): `tbx_wrk_…` tokens, issued per worker by
an admin, stored as SHA-256 like API keys, scoped to a set of kinds, revocable.

A worker never holds a user's credential: its inputs are URLs signed for the
lease, its outputs go to the `job-output` upload the claim opened, which
belongs to the job's account. `upload_resolver` (installed into
app.uploads.credentials on import) maps a worker token to that account while
the worker holds a lease; a worker holds one lease at a time.
"""

import re
import secrets

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..database import get_db
from ..licence import clock
from ..security import hash_api_key
from ..uploads.credentials import WORKER_TOKEN_PREFIX, UploadCaller, set_worker_resolver
from . import quotas
from .models import RenderJob, Worker

NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_bearer = HTTPBearer(auto_error=False)


def _unauthenticated(detail: str = "This call needs a worker token (Authorization: Bearer tbx_wrk_…).") -> ContractError:
    return ContractError("unauthenticated", 401, detail, headers={"WWW-Authenticate": "Bearer"})


def worker_json(w: Worker) -> dict:
    return {
        "worker_id": w.worker_id,
        "kinds": list(w.kinds or []),
        "class": w.worker_class,
        "pool": w.pool,
        "pool_state": w.pool_state,
        "app_version": w.app_version,
        "doc_version_max": w.doc_version_max,
        "last_heartbeat_at": clock.rfc3339(w.last_heartbeat_at),
        "created_at": clock.rfc3339(w.created_at),
        "revoked_at": clock.rfc3339(w.revoked_at),
    }


def _invalid(field: str, message: str) -> ContractError:
    return ContractError(
        "validation_failed", 422, f"{field}: {message}", {"fields": [{"field": field, "in": "body", "message": message}]}
    )


def issue(db: Session, *, name: str, kinds: list[str], worker_class: str, admin_id: int | None) -> tuple[Worker, str]:
    """A new token for `name` (shown once). A revoked name may be issued again."""
    name = (name or "").strip().lower()
    if not NAME.match(name):
        raise _invalid("name", "1 to 40 lowercase letters, digits and dashes, starting with a letter or digit")
    kinds = sorted(set(kinds or []))
    if not kinds or any(k not in quotas.CONTRACT_KINDS for k in kinds):
        raise _invalid("kinds", f"one or more of {', '.join(quotas.CONTRACT_KINDS)}")
    if worker_class not in quotas.class_weights():
        raise _invalid("class", f"one of {', '.join(quotas.class_weights())}")
    token = WORKER_TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = db.get(Worker, name)
    if row is not None and row.revoked_at is None:
        raise ContractError(
            "conflict", 409, f"A worker named {name} exists. Revoke it first to issue a new token.", {"worker_id": name}
        )
    now = clock.now()
    if row is None:
        row = Worker(worker_id=name, created_at=now)
        db.add(row)
    row.token_hash = hash_api_key(token)
    row.kinds = kinds
    row.worker_class = worker_class
    row.pool = "static"
    row.pool_state = "running"
    row.revoked_at = None
    row.created_by = admin_id
    row.created_at = now
    row.idle_since = now
    row.last_heartbeat_at = None
    db.commit()
    return row, token


def revoke(db: Session, worker_id: str) -> Worker:
    from . import queue

    row = db.get(Worker, worker_id)
    if row is None:
        raise ContractError("not_found", 404, "No such worker.")
    if row.revoked_at is None:
        row.revoked_at = clock.now()
        db.commit()
        # Its leases end now (as lapses) rather than after 120 s.
        for job in db.scalars(
            select(RenderJob).where(RenderJob.worker_id == worker_id, RenderJob.state.in_(("claimed", "running")))
        ).all():
            queue.lapse(db, job.job_id, job.lease_id, force=True)
    return row


def find(db: Session, raw: str) -> Worker | None:
    if not raw or not raw.startswith(WORKER_TOKEN_PREFIX):
        return None
    return db.scalar(select(Worker).where(Worker.token_hash == hash_api_key(raw)))


def authenticate(db: Session, raw: str) -> Worker:
    if not raw or not raw.startswith(WORKER_TOKEN_PREFIX):
        raise _unauthenticated()
    row = find(db, raw)
    if row is None:
        raise _unauthenticated("This worker token is not valid.")
    if row.revoked_at is not None:
        raise ContractError(
            "worker_revoked", 401, "This worker's token was revoked. Ask an admin for a new one.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return row


def get_worker(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> Worker:
    return authenticate(db, creds.credentials if creds else "")


def active_job(db: Session, worker_id: str) -> RenderJob | None:
    return db.scalar(
        select(RenderJob)
        .where(RenderJob.worker_id == worker_id, RenderJob.state.in_(("claimed", "running")))
        .order_by(RenderJob.claimed_at.desc())
        .limit(1)
    )


def upload_resolver(db: Session, raw: str) -> UploadCaller | None:
    """share-bundle §4: a worker uploads into the account of the job it holds."""
    row = find(db, raw)
    if row is None or row.revoked_at is not None:
        return None
    job = active_job(db, row.worker_id)
    if job is None:
        return None
    return UploadCaller(account_id=job.account_id, kind="worker", credential_id=row.worker_id)


set_worker_resolver(upload_resolver)
