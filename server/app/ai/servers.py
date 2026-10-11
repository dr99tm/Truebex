"""Self-hosted inference servers on gpu-ai workers (PF11 Scope 6).

A server is registered by an admin (an id, the alias it serves, its URL).
`ai.servers.scale` (every 60 s) probes each one (`GET <base>/v1/models`, the
OpenAI-compatible list): an answer makes it warm for the next 2 minutes. It
also records how many gpu-ai machines the pool should run: one per
self-hosted alias while turns arrive (the last 15 minutes) or inside GD3's
warm hours, none otherwise. Weights take minutes to load, so while no server
is warm a turn on that alias is answered by its `fallback_alias`.
"""

import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock
from ..render import pools
from . import aliases
from .models import AiServer

WARM_FOR = timedelta(minutes=2)
DEMAND_WINDOW = timedelta(minutes=15)
PROBE_TIMEOUT_S = 5.0
GPU_CLASS = "gpu-ai"
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
# When each alias last had a turn (this process; the table keeps last_turn_at).
LAST_DEMAND: dict[str, datetime] = {}


def server_json(row: AiServer, now: datetime | None = None) -> dict:
    now = now or clock.now()
    warm = row.state == "warm" and row.warm_until is not None and clock.aware(row.warm_until) > now
    return {
        "server_id": row.server_id,
        "alias": row.alias,
        "base_url": row.base_url,
        "state": "warm" if warm else ("stopped" if row.state == "stopped" else "cold"),
        "warm_until": clock.rfc3339(row.warm_until),
        "last_probe_at": clock.rfc3339(row.last_probe_at),
        "last_turn_at": clock.rfc3339(row.last_turn_at),
    }


def register(db: Session, server_id: str, alias: str, base_url: str) -> AiServer:
    server_id = (server_id or "").strip().lower()
    if not _ID.match(server_id):
        raise ContractError("validation_failed", 422, "server_id: lowercase letters, digits and dashes", {"fields": [{"field": "server_id"}]})
    entry = aliases.current().get(alias, include_disabled=True)
    if entry is None or entry.adapter != "selfhosted":
        raise ContractError("validation_failed", 422, "alias: a selfhosted alias of the alias table", {"fields": [{"field": "alias"}]})
    if not re.match(r"^https?://[^\s]+$", base_url or ""):
        raise ContractError("validation_failed", 422, "base_url: an http(s) URL", {"fields": [{"field": "base_url"}]})
    row = db.get(AiServer, server_id)
    if row is None:
        row = AiServer(server_id=server_id, created_at=clock.now())
        db.add(row)
    row.alias = alias
    row.base_url = base_url.rstrip("/")
    row.state = "cold"
    row.warm_until = None
    db.commit()
    return row


def remove(db: Session, server_id: str) -> None:
    row = db.get(AiServer, server_id)
    if row is None:
        raise ContractError("not_found", 404, "No such inference server.")
    db.delete(row)
    db.commit()


def warm_server(db: Session, alias: str, now: datetime) -> AiServer | None:
    rows = db.scalars(
        select(AiServer).where(AiServer.alias == alias, AiServer.state == "warm", AiServer.warm_until > now)
    ).all()
    if not rows:
        return None
    rows.sort(key=lambda r: clock.aware(r.last_turn_at) if r.last_turn_at else datetime.min.replace(tzinfo=timezone.utc))
    return rows[0]  # the least recently used


def note_turn(db: Session, alias: str, server: AiServer | None, now: datetime) -> None:
    LAST_DEMAND[alias] = now
    if server is not None:
        server.last_turn_at = now


def probe(base_url: str) -> bool:
    key = get_settings().selfhosted_api_key
    try:
        res = httpx.get(
            f"{base_url.rstrip('/')}/v1/models", timeout=PROBE_TIMEOUT_S,
            headers={"Authorization": f"Bearer {key}"} if key else {},
        )
    except httpx.HTTPError:
        return False
    return res.status_code == 200


def _in_warm_hours(now: datetime) -> bool:
    hours = (get_settings().render_pool_warm_hours or "").strip()
    first, _, last = hours.partition("-")
    if not (first.strip().isdigit() and last.strip().isdigit()):
        return False
    return int(first) <= now.astimezone(timezone.utc).hour < int(last)


def scale(db: Session, now: datetime) -> dict:
    """ai.servers.scale: probe every server, decide how many gpu-ai machines
    the self-hosted aliases want."""
    table = aliases.current()
    wanted = 0
    for alias in table.aliases.values():
        if alias.adapter != "selfhosted" or not alias.enabled:
            continue
        last = LAST_DEMAND.get(alias.name)
        recent = db.scalar(
            select(AiServer.last_turn_at).where(AiServer.alias == alias.name).order_by(AiServer.last_turn_at.desc()).limit(1)
        )
        if recent is not None and (last is None or clock.aware(recent) > last):
            last = clock.aware(recent)
        if (last is not None and now - last <= DEMAND_WINDOW) or _in_warm_hours(now):
            wanted += 1
    warm = 0
    for row in db.scalars(select(AiServer)).all():
        row.last_probe_at = now
        if probe(row.base_url):
            row.state = "warm"
            row.warm_until = now + WARM_FOR
            warm += 1
        elif row.state != "stopped":
            row.state = "cold"
    pools.DESIRED[GPU_CLASS] = wanted
    db.commit()
    return {"wanted": wanted, "warm": warm}
