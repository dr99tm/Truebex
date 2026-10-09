"""`Idempotency-Key` for contract POSTs (PF14 §Design Plumbing; first user PF4).

    @router.post("/projects", status_code=201)
    def create(..., idem: Idempotency = idempotent("projects.create")):
        replay = idem.start(db, account=f"user:{user.id}")
        if replay is not None:
            return replay
        ...
        return idem.save(db, 201, body)

The key (32 hex, optional) is kept 24 h per (account, route) in
`idempotency_keys`: the same key and body replay the first answer, the same
key with another body is 409 `idempotency_mismatch`, and a second request
while the first is still running is 409 `idempotency_in_progress` (retry after
1 s). Only successful answers are kept: an error drops the reservation (the
next `start` finds it abandoned), so a retry after an upgrade or a fix runs
again instead of replaying the old error.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .contract_http import CONTRACT_HEADER, ContractError
from .database import Base, SessionLocal
from .tasks import periodic

KEY_HEADER = "Idempotency-Key"
LIFETIME = timedelta(hours=24)
# A reservation older than this belongs to a request that died mid-way.
STALE_AFTER = timedelta(minutes=5)
_KEY = re.compile(r"^[0-9a-fA-F]{32}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("account", "route", "key", name="uq_idempotency_account_route_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(32), nullable=False)
    # "user:42" (an org or a worker later).
    account: Mapped[str] = mapped_column(String(64), nullable=False)
    # Method and path, e.g. "POST /projects/<pid>/versions".
    route: Mapped[str] = mapped_column(String(300), nullable=False)
    body_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # 0 while the first request runs.
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


@dataclass
class Idempotency:
    key: str | None
    route: str
    body_sha256: str
    request: Request | None = field(default=None, repr=False)
    _row_id: int | None = field(default=None, repr=False)

    def _response(self, body, status: int) -> JSONResponse:
        """A JSONResponse that keeps the contract header the route echoes."""
        headers = {}
        name = getattr(self.request.state, "contract", None) if self.request is not None else None
        if name:
            headers[CONTRACT_HEADER] = name
        return JSONResponse(body, status_code=status, headers=headers)

    def start(self, db: Session, *, account: str) -> JSONResponse | None:
        """Reserve the key, or answer with the stored reply. None = go ahead."""
        if self.key is None:
            return None
        now = _utcnow()
        for _ in range(2):
            row = db.scalar(
                select(IdempotencyKey).where(
                    IdempotencyKey.account == account,
                    IdempotencyKey.route == self.route,
                    IdempotencyKey.key == self.key,
                )
            )
            if row is not None:
                age = now - _aware(row.created_at)
                if age > LIFETIME or (row.status == 0 and age > STALE_AFTER):
                    db.delete(row)  # expired, or its request died: start over
                    db.commit()
                    continue
                if row.body_sha256 != self.body_sha256:
                    raise ContractError(
                        "idempotency_mismatch",
                        409,
                        "This Idempotency-Key was already used with a different request.",
                        {"key": self.key},
                    )
                if row.status == 0:
                    raise ContractError(
                        "idempotency_in_progress",
                        409,
                        "The first request with this Idempotency-Key is still running.",
                        {"key": self.key},
                        retry_after_s=1,
                    )
                return self._response(json.loads(row.response or "null"), row.status)
            row = IdempotencyKey(
                key=self.key, account=account, route=self.route, body_sha256=self.body_sha256, status=0, created_at=now
            )
            db.add(row)
            try:
                db.commit()
            except IntegrityError:  # another request reserved it first
                db.rollback()
                continue
            self._row_id = row.id
            return None
        raise ContractError(
            "idempotency_in_progress", 409, "Try this request again in a moment.", {"key": self.key}, retry_after_s=1
        )

    def save(self, db: Session, status: int, body: dict) -> JSONResponse:
        """Keep a successful answer for replay and return it."""
        if self._row_id is not None:
            row = db.get(IdempotencyKey, self._row_id)
            if row is not None:
                row.status = status
                row.response = json.dumps(body, separators=(",", ":"))
                db.commit()
        return self._response(body, status)

    def abandon(self) -> None:
        """Drop the reservation after an error (own session: the caller's may be dirty)."""
        if self._row_id is None:
            return
        with SessionLocal() as db:
            db.execute(delete(IdempotencyKey).where(IdempotencyKey.id == self._row_id, IdempotencyKey.status == 0))
            db.commit()
        self._row_id = None


def idempotent(scope: str):
    """Dependency for a POST that honours `Idempotency-Key` (contract §8)."""

    async def dependency(request: Request, idempotency_key: str | None = Header(default=None)) -> Idempotency:
        key = None
        if idempotency_key is not None:
            key = idempotency_key.strip()
            if not _KEY.match(key):
                raise ContractError(
                    "validation_failed",
                    422,
                    "Idempotency-Key must be 32 hex characters.",
                    {"fields": [{"field": KEY_HEADER, "in": "header", "message": "32 hex characters"}]},
                )
            key = key.lower()
        body = await request.body()
        return Idempotency(
            key=key,
            route=f"{request.method} {request.url.path}"[:300],
            body_sha256=hashlib.sha256(body).hexdigest(),
            request=request,
        )

    dependency.__name__ = f"idempotent_{scope.replace('.', '_')}"
    return Depends(dependency)


@periodic("idempotency.expire", 3600)
def expire(now: datetime) -> int:
    with SessionLocal() as db:
        res = db.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at <= now - LIFETIME))
        db.commit()
        return res.rowcount or 0
