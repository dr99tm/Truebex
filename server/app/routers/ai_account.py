"""The website's view of the AI tier (PF11): the dashboard Cloud page's AI
section, and Buy credits through PF2's checkout. Session only.

GET  /account/ai              credits left, allowance, reset date, recent turns, the packs
POST /account/ai/top-ups      start a checkout for a pack -> {url, reference}

GET  /admin/ai                admins: AI spend by alias against provider cost, inference servers
POST /admin/ai/servers        admins: register a self-hosted inference server
DELETE /admin/ai/servers/{id} admins: remove one
"""

from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai import aliases, credits, servers, topups
from ..ai.models import AiServer, AiTopUp, AiUsage
from ..contract_http import enveloped
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..licence import clock, seats
from ..models import User
from ..plans import CURRENCIES
from ..render import pools, quotas

router = APIRouter(tags=["ai"], dependencies=[enveloped()])
RECENT_TURNS = 20


def _currency(db: Session, user: User, asked: str | None) -> str:
    wanted = (asked or "").upper()
    if wanted in CURRENCIES:
        return wanted
    sub = seats.seat_source(db, user).subscription
    if sub is not None and (sub.currency or "").upper() in CURRENCIES:
        return sub.currency.upper()
    return CURRENCIES[0] if CURRENCIES else "GBP"


@router.get("/account/ai")
def account(currency: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    plan = credits.plan_of(db, user)
    has = credits.FEATURE in plan.features
    cur = _currency(db, user, currency)
    turns = db.scalars(
        select(AiUsage)
        .where(AiUsage.account_kind == credits.ACCOUNT_KIND, AiUsage.account_id == user.id)
        .order_by(AiUsage.at.desc())
        .limit(RECENT_TURNS)
    ).all()
    pending = db.scalars(
        select(AiTopUp).where(AiTopUp.user_id == user.id).order_by(AiTopUp.created_at.desc()).limit(10)
    ).all()
    return {
        "feature": has,
        "plan": plan.id,
        "plan_needed": credits.plan_needed(plan),
        "balance": credits.balance_json(db, user) if has else None,
        "turns": [
            {
                "at": clock.rfc3339(t.at),
                "alias": t.alias,
                "credits": int(t.credits),
                "tool_names": list(t.tool_names or []),
                "model": t.provider_model,
                "stop_reason": t.stop_reason,
                "input_tokens": int(t.input_tokens),
                "output_tokens": int(t.output_tokens),
            }
            for t in turns
        ],
        "currency": cur,
        "currencies": list(CURRENCIES),
        "packs": topups.packs_json(cur),
        "top_ups": [
            {"reference": t.reference, "pack": t.pack, "credits": int(t.credits), "state": t.state, "created_at": clock.rfc3339(t.created_at)}
            for t in pending
        ],
    }


class Consent(BaseModel):
    version: str = Field(max_length=32)
    accepted: bool


class TopUpIn(BaseModel):
    pack: str = Field(max_length=40)
    currency: str = Field(max_length=3)
    consent: Consent


@router.post("/account/ai/top-ups", status_code=201)
def top_up(body: TopUpIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    version = body.consent.version if body.consent.accepted else ""
    url, reference = topups.start(db, user, body.pack, body.currency, version)
    return {"url": url, "reference": reference}


# --- admin ----------------------------------------------------------------------------------


class ServerIn(BaseModel):
    server_id: str = Field(max_length=40)
    alias: str = Field(max_length=40)
    base_url: str = Field(max_length=300)


@router.get("/admin/ai")
def admin_overview(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    now = clock.now()
    start, _ = quotas.month_bounds(now)
    since = datetime.combine(start, time.min, tzinfo=timezone.utc)
    rows = db.execute(
        select(
            AiUsage.alias, AiUsage.served_by, func.count(), func.coalesce(func.sum(AiUsage.credits), 0),
            func.coalesce(func.sum(AiUsage.provider_cost_micros), 0), func.coalesce(func.sum(AiUsage.input_tokens), 0),
            func.coalesce(func.sum(AiUsage.output_tokens), 0),
        )
        .where(AiUsage.at >= since)
        .group_by(AiUsage.alias, AiUsage.served_by)
    ).all()
    table = aliases.current()
    return {
        "period_start": quotas.rfc3339_day(start),
        "aliases": [
            {"alias": a.name, "adapter": a.adapter, "model": a.model, "enabled": a.enabled, "credits_per_mtok": dict(a.rates)}
            for a in table.aliases.values()
        ],
        "spend": [
            {
                "alias": alias, "served_by": served, "turns": int(n), "credits": int(cr), "provider_cost_usd": round(int(micros) / 1e6, 4),
                "input_tokens": int(tin), "output_tokens": int(tout),
            }
            for alias, served, n, cr, micros, tin, tout in rows
        ],
        "servers": [servers.server_json(r, now) for r in db.scalars(select(AiServer).order_by(AiServer.server_id)).all()],
        "gpu_ai_wanted": pools.DESIRED.get(servers.GPU_CLASS),
    }


@router.post("/admin/ai/servers", status_code=201)
def add_server(body: ServerIn, _admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return servers.server_json(servers.register(db, body.server_id, body.alias, body.base_url))


@router.delete("/admin/ai/servers/{server_id}")
def delete_server(server_id: str, _admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    servers.remove(db, server_id)
    return {"removed": server_id}
