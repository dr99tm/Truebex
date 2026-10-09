"""Presence (contract 5.17, 5.18, §6.5): who is in a project, where they look
and what they are editing.

Heartbeats every 10-30 s keep an entry; one older than 30 s is gone, and
`leaving: true` removes it at once. `editing` is a soft lock, shown and never
enforced (§6.3 decides). PROJECTS_PRESENCE_BACKEND picks where entries live:
`memory` (this process) or `db` (the `presence` table, for several API
processes). Times come from `licence.clock` so tests can move them.
"""

import threading
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..licence import clock
from ..models import User
from .models import Presence
from .service import display_name, is_hex32

TTL_S = 30
CLIENTS = ("desktop", "web", "android", "headset", "worker")
MAX_IDS = 50


def _ids(values: list[str]) -> list[str]:
    out = [v.lower() for v in values]
    if not all(is_hex32(v) for v in out):
        raise ValueError("32 hex characters each")
    return out


class ViewIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    storey: str | None = None
    eye_mm: list[float] | None = Field(default=None, min_length=3, max_length=3)
    yaw_deg: float | None = None

    @field_validator("storey")
    @classmethod
    def _storey(cls, v: str | None) -> str | None:
        if v is not None and not is_hex32(v.lower()):
            raise ValueError("32 hex characters")
        return v.lower() if v else v


class PresenceIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    replica_id: str = Field(max_length=32)
    client: str = Field(max_length=16)
    view: ViewIn | None = None
    selection: list[str] = Field(default_factory=list, max_length=MAX_IDS)
    editing: list[str] = Field(default_factory=list, max_length=MAX_IDS)
    leaving: bool = False

    @field_validator("replica_id")
    @classmethod
    def _replica(cls, v: str) -> str:
        if not is_hex32(v.lower()):
            raise ValueError("32 hex characters")
        return v.lower()

    @field_validator("client")
    @classmethod
    def _client(cls, v: str) -> str:
        if v not in CLIENTS:
            raise ValueError(f"one of {', '.join(CLIENTS)}")
        return v

    @field_validator("selection", "editing")
    @classmethod
    def _id_list(cls, v: list[str]) -> list[str]:
        return _ids(v)


def _entry(user: User, body: PresenceIn, now: datetime) -> dict:
    return {
        "user_id": user.id,
        "name": display_name(user),
        "replica_id": body.replica_id,
        "client": body.client,
        "seen_at": clock.rfc3339(now),
        "view": body.view.model_dump() if body.view else None,
        "selection": body.selection,
        "editing": body.editing,
    }


def _fresh(seen: datetime, now: datetime) -> bool:
    return now - clock.aware(seen) <= timedelta(seconds=TTL_S)


class MemoryPresence:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[tuple[str, str], tuple[datetime, dict]] = {}

    def put(self, db: Session, project_id: str, entry: dict, now: datetime) -> None:
        with self._lock:
            self._entries[(project_id, entry["replica_id"])] = (now, entry)

    def remove(self, db: Session, project_id: str, replica_id: str) -> None:
        with self._lock:
            self._entries.pop((project_id, replica_id), None)

    def present(self, db: Session, project_id: str, now: datetime) -> list[dict]:
        with self._lock:
            return [e for (pid, _), (seen, e) in self._entries.items() if pid == project_id and _fresh(seen, now)]

    def drop_project(self, db: Session, project_id: str) -> None:
        with self._lock:
            for key in [k for k in self._entries if k[0] == project_id]:
                del self._entries[key]

    def sweep(self, db: Session, now: datetime) -> int:
        with self._lock:
            stale = [k for k, (seen, _) in self._entries.items() if not _fresh(seen, now)]
            for key in stale:
                del self._entries[key]
            return len(stale)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class DbPresence:
    def put(self, db: Session, project_id: str, entry: dict, now: datetime) -> None:
        row = db.get(Presence, (project_id, entry["replica_id"]))
        if row is None:
            row = Presence(project_id=project_id, replica_id=entry["replica_id"])
            db.add(row)
        row.user_id = entry["user_id"]
        row.client = entry["client"]
        row.payload = entry
        row.seen_at = now
        db.commit()

    def remove(self, db: Session, project_id: str, replica_id: str) -> None:
        db.execute(delete(Presence).where(Presence.project_id == project_id, Presence.replica_id == replica_id))
        db.commit()

    def present(self, db: Session, project_id: str, now: datetime) -> list[dict]:
        rows = db.scalars(
            select(Presence).where(Presence.project_id == project_id, Presence.seen_at >= now - timedelta(seconds=TTL_S))
        ).all()
        return [dict(r.payload) for r in rows]

    def drop_project(self, db: Session, project_id: str) -> None:
        db.execute(delete(Presence).where(Presence.project_id == project_id))
        db.commit()

    def sweep(self, db: Session, now: datetime) -> int:
        res = db.execute(delete(Presence).where(Presence.seen_at < now - timedelta(seconds=TTL_S)))
        db.commit()
        return res.rowcount or 0

    def clear(self) -> None:
        pass


_memory = MemoryPresence()
_db = DbPresence()


def backend() -> MemoryPresence | DbPresence:
    return _db if get_settings().projects_presence_backend == "db" else _memory


def heartbeat(db: Session, project_id: str, user: User, body: PresenceIn) -> dict:
    now = clock.now()
    store = backend()
    if body.leaving:
        store.remove(db, project_id, body.replica_id)
    else:
        store.put(db, project_id, _entry(user, body, now), now)
    others = [e for e in store.present(db, project_id, now) if e["replica_id"] != body.replica_id]
    return {"ttl_s": TTL_S, "others": others}


def present(db: Session, project_id: str) -> dict:
    return {"present": backend().present(db, project_id, clock.now())}


def reset() -> None:
    _memory.clear()
