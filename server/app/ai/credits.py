"""Metered credits for the Truebex AI tier (contract ai-proxy §6.2).

* Integer credits per account in two buckets: the month's allowance (the
  entitlement's `limits.ai_credits_month`, reset at 00:00 UTC on the 1st, no
  roll-over) and top-ups bought on the website (PF2), which never expire.
* Charge per turn = ⌈(input × in + output × out + cache_read × cr +
  cache_write × cw) / 10⁶⌉ with the rates of the model that answered.
* Spend order: the allowance, then top-ups. A started turn finishes even if
  it ends below zero: the overrun lands on the allowance and is written off
  at the reset (the ledger's `expire` row says so).
* Refusal: a turn starts only while credits remain and cover its input
  estimate at the input rate (`check_can_start`).
* Every change is an append-only ledger row with a reference; grants,
  expiries and top-ups are unique per reference, so the monthly grant and a
  replayed payment can never count twice.

Placeholders until GD7: credits.json (allowances per tier, the packs).
"""

import json
import math
from datetime import datetime, time, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock
from ..models import User
from ..plans import PLANS, Plan
from ..render import quotas
from .models import AiBalance, AiCreditLedger

CONFIG = json.loads(Path(__file__).with_name("credits.json").read_text(encoding="utf-8"))
ACCOUNT_KIND = "user"
FEATURE = "ai.metered"
# Characters per token for the local input estimate (the refusal check and
# the self-hosted count), and the tokens one image is counted as.
CHARS_PER_TOKEN = 4
IMAGE_TOKENS = 1600


def packs() -> list[dict]:
    return list(CONFIG.get("top_up_packs") or [])


def pack(pack_id: str) -> dict | None:
    return next((p for p in packs() if p["id"] == pack_id), None)


def retention_days() -> int:
    return int(CONFIG.get("usage_retention_days") or 400)


def top_up_url() -> str:
    return f"{get_settings().site_url.rstrip('/')}/dashboard/cloud/#ai-credits"


# --- plans -----------------------------------------------------------------------------


def plan_of(db: Session, user: User) -> Plan:
    return quotas.plan_of(db, user)


def allowance_for(plan: Plan) -> int | None:
    """The month's credits for a tier, or None for no limit."""
    if FEATURE not in plan.features:
        return 0
    if "ai_credits_month" in plan.limits:
        value = plan.limits["ai_credits_month"]
        if value is None:
            return None
        if int(value) > 0:
            return int(value)
    return int((CONFIG.get("allowance_month") or {}).get(plan.id, 0))


def plan_needed(plan: Plan) -> str:
    """The tier to suggest when credits run out: the next one a person can
    buy with a bigger allowance, else their own (top-ups are the answer)."""
    mine = allowance_for(plan)
    better = [
        p for p in PLANS.values()
        if p.rank > plan.rank and p.purchasable and FEATURE in p.features
        and (allowance_for(p) is None or (mine is not None and (allowance_for(p) or 0) > mine))
    ]
    better.sort(key=lambda p: p.rank)
    return better[0].id if better else plan.id


# --- arithmetic -------------------------------------------------------------------------


def charge_for(usage: dict, rates: dict[str, int]) -> int:
    """§6.2: whole credits, rounded up, for the tokens the provider billed."""
    total = (
        int(usage.get("input_tokens") or 0) * rates["input"]
        + int(usage.get("output_tokens") or 0) * rates["output"]
        + int(usage.get("cache_read_input_tokens") or 0) * rates["cache_read"]
        + int(usage.get("cache_creation_input_tokens") or 0) * rates["cache_write"]
    )
    return -(-total // 1_000_000)


def cost_micros(usage: dict, usd_per_mtok: dict[str, float]) -> int:
    """What the provider charges for these tokens, in millionths of a dollar."""
    return int(round(
        int(usage.get("input_tokens") or 0) * usd_per_mtok.get("input", 0.0)
        + int(usage.get("output_tokens") or 0) * usd_per_mtok.get("output", 0.0)
        + int(usage.get("cache_read_input_tokens") or 0) * usd_per_mtok.get("cache_read", 0.0)
        + int(usage.get("cache_creation_input_tokens") or 0) * usd_per_mtok.get("cache_write", 0.0)
    ))


def estimate_input_tokens(text_bytes: int, images: int) -> int:
    return math.ceil(text_bytes / CHARS_PER_TOKEN) + images * IMAGE_TOKENS


# --- months -------------------------------------------------------------------------------


def month_key(at: datetime) -> str:
    at = at.astimezone(timezone.utc)
    return f"{at.year:04d}-{at.month:02d}"


def resets_at(at: datetime) -> datetime:
    _, nxt = quotas.month_bounds(at)
    return datetime.combine(nxt, time.min, tzinfo=timezone.utc)


# --- the balance row ------------------------------------------------------------------------


def remaining(row: AiBalance) -> int:
    return int(row.allowance_remaining) + int(row.top_up_remaining)


def _lock(db: Session, account_id: int) -> AiBalance | None:
    """Begin the write transaction with the account's row locked (SQLite takes
    its single write lock here; Postgres the row lock)."""
    db.execute(
        update(AiBalance)
        .where(AiBalance.account_kind == ACCOUNT_KIND, AiBalance.account_id == account_id)
        .values(updated_at=AiBalance.updated_at)
    )
    return db.execute(
        select(AiBalance)
        .where(AiBalance.account_kind == ACCOUNT_KIND, AiBalance.account_id == account_id)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _ledger(db: Session, row: AiBalance, delta: int, kind: str, bucket: str, ref: str, now: datetime) -> None:
    db.add(
        AiCreditLedger(
            account_kind=ACCOUNT_KIND, account_id=row.account_id, delta=int(delta), kind=kind, bucket=bucket,
            ref=ref[:80], balance_after=remaining(row), at=now,
        )
    )


def _grant(db: Session, row: AiBalance, amount: int, ref: str, now: datetime) -> None:
    if amount <= 0:
        return
    row.allowance_remaining += amount
    row.granted += amount
    _ledger(db, row, amount, "grant", "allowance", ref, now)


def ensure(db: Session, user: User, now: datetime | None = None, *, plan: Plan | None = None) -> AiBalance:
    """The account's balance, locked for this transaction: created on first
    use with the month's allowance, rolled over when the month has turned
    (the unused allowance expires, the plan's new one is granted), topped up
    by the difference when the plan's allowance rose mid-month. The caller
    commits."""
    now = now or clock.now()
    plan = plan or plan_of(db, user)
    limit = allowance_for(plan) or 0
    month = month_key(now)
    for _ in range(2):
        row = _lock(db, user.id)
        if row is not None:
            break
        row = AiBalance(
            account_kind=ACCOUNT_KIND, account_id=user.id, allowance_remaining=0, top_up_remaining=0,
            month=month, granted=0, resets_at=resets_at(now), updated_at=now,
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:  # another request created it first
            db.rollback()
            continue
        _grant(db, row, limit, month, now)
        row.updated_at = now
        return row
    else:  # pragma: no cover - the second lock always finds the row
        raise RuntimeError("could not lock the AI balance")
    if row.month != month:
        if row.allowance_remaining:
            # An overrun (below zero) is written off here too.
            left = int(row.allowance_remaining)
            row.allowance_remaining = 0
            _ledger(db, row, -left, "expire", "allowance", row.month, now)
        row.month = month
        row.granted = 0
        row.resets_at = resets_at(now)
        _grant(db, row, limit, month, now)
    elif limit > row.granted:
        _grant(db, row, limit - int(row.granted), f"{month}:{plan.id}", now)
    row.updated_at = now
    return row


def roll_due(db: Session, now: datetime) -> int:
    """ai.allowance.grant: every account whose month has turned gets its
    expiry and its new grant (idempotent: the ledger is unique per month)."""
    ids = list(db.scalars(select(AiBalance.account_id).where(AiBalance.account_kind == ACCOUNT_KIND, AiBalance.resets_at <= now)))
    db.rollback()
    done = 0
    for account_id in ids:
        user = db.get(User, account_id)
        if user is None:
            continue
        ensure(db, user, now)
        db.commit()
        done += 1
    return done


def spend(db: Session, row: AiBalance, credits: int, ref: str, now: datetime) -> None:
    """Take `credits` (allowance first, then top-ups; an overrun on the allowance)."""
    if credits <= 0:
        return
    from_allowance = min(credits, max(0, int(row.allowance_remaining)))
    from_top_up = min(credits - from_allowance, max(0, int(row.top_up_remaining)))
    from_allowance += credits - from_allowance - from_top_up
    if from_allowance:
        row.allowance_remaining -= from_allowance
        _ledger(db, row, -from_allowance, "usage", "allowance", ref, now)
    if from_top_up:
        row.top_up_remaining -= from_top_up
        _ledger(db, row, -from_top_up, "usage", "top_up", ref, now)
    row.updated_at = now


def add_top_up(db: Session, user: User, credits: int, ref: str, now: datetime | None = None) -> bool:
    """Credit a bought pack once per reference. Returns False when it already was."""
    now = now or clock.now()
    row = ensure(db, user, now)
    seen = db.scalar(
        select(AiCreditLedger.id).where(
            AiCreditLedger.account_kind == ACCOUNT_KIND, AiCreditLedger.account_id == user.id,
            AiCreditLedger.kind == "top_up", AiCreditLedger.ref == ref,
        )
    )
    if seen is not None:
        return False
    row.top_up_remaining += int(credits)
    _ledger(db, row, int(credits), "top_up", "top_up", ref, now)
    return True


def adjust(db: Session, user: User, delta: int, ref: str, *, bucket: str = "allowance", now: datetime | None = None) -> AiBalance:
    """An admin correction (and the tests' way to set a balance)."""
    now = now or clock.now()
    row = ensure(db, user, now)
    if bucket == "top_up":
        row.top_up_remaining += int(delta)
    else:
        row.allowance_remaining += int(delta)
    _ledger(db, row, int(delta), "adjust", bucket, ref, now)
    return row


# --- the refusal and the 5.2 answer ------------------------------------------------------------


def exhausted(plan: Plan, row: AiBalance, detail: str) -> ContractError:
    return ContractError(
        "credits_exhausted", 403, detail,
        {
            "remaining": remaining(row),
            "resets_at": clock.rfc3339(clock.aware(row.resets_at)),
            "plan_needed": plan_needed(plan),
            "top_up_url": top_up_url(),
        },
    )


def check_can_start(plan: Plan, row: AiBalance, input_estimate: int, rates: dict[str, int]) -> None:
    """403 `credits_exhausted` unless credits remain and cover the input estimate."""
    if allowance_for(plan) is None:
        return  # no monthly limit
    left = remaining(row)
    if left <= 0:
        raise exhausted(plan, row, "Your AI credits are used up for this month.")
    need = -(-input_estimate * rates["input"] // 1_000_000)
    if need > left:
        raise exhausted(plan, row, "This request needs more AI credits than are left.")


def balance_json(db: Session, user: User, now: datetime | None = None) -> dict:
    """Contract 5.2 (commits the roll-over, if any)."""
    now = now or clock.now()
    plan = plan_of(db, user)
    row = ensure(db, user, now, plan=plan)
    db.commit()
    limit = allowance_for(plan)
    return {
        "credits_remaining": remaining(row) if limit is not None else None,
        "allowance_monthly": limit,
        "top_up_remaining": int(row.top_up_remaining),
        "resets_at": clock.rfc3339(clock.aware(row.resets_at)),
        "plan": plan.id,
        "top_up_url": top_up_url(),
        # Additive.
        "allowance_remaining": int(row.allowance_remaining),
    }
