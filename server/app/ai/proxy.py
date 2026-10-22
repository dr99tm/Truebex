"""The metered assistant proxy (contract ai-proxy §5.1-5.4, §6, §7, §8).

One model turn: the checks (device token with `ai.metered`, §5's rules, a
repeated `Idempotency-Key`, two turns in flight and 60 a minute per account,
credits that cover the input estimate), then the alias's adapter, then the
answer: a stream relayed line by line with `ping` at least every 15 s and one
`truebex_credits` event before `message_stop`, or one JSON object with
`credits` and `served_by`. The charge comes from the `usage` the provider
reports; nothing is charged when the provider fails before output, and a
stream cut after output began is charged for what was billed. The proxy keeps
no message text, tool input or image: `ai_usage` holds counts, names, credits.
"""

import asyncio
import contextlib
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import timedelta

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from .. import ratelimit
from ..contract_http import CONTRACT_HEADER, ContractError, request_id
from ..database import SessionLocal
from ..licence import clock
from ..models import User
from . import adapters, aliases, credits, servers, validate
from .adapters.base import UpstreamError
from .models import AiRequestKey, AiTurn, AiUsage
from .sse import PING, EventBuffer, StreamState, encode

log = logging.getLogger("truebex.ai")

PING_S = 15.0  # §5: a ping at least every 15 s (tests shorten it)
PEEK_S = 25.0  # wait this long for the first event before committing the 200
IN_FLIGHT_MAX = 2
PER_MINUTE = 60
KEY_WINDOW = timedelta(minutes=10)
TURN_STALE = timedelta(minutes=15)
CONTRACT = "ai-proxy/1.1"
_END = object()


@dataclass
class Prepared:
    turn: validate.Turn
    served: aliases.Alias
    server_id: str | None
    server_url: str | None
    turn_id: str
    key: str | None
    user_id: int
    device_id: str | None
    rid: str
    state: StreamState = field(default_factory=StreamState)
    settled: bool = False


@dataclass
class _Server:
    base_url: str


def _headers(request: Request) -> dict:
    return {CONTRACT_HEADER: getattr(request.state, "contract", CONTRACT)}


def envelope(rid: str, code: str, status: int, detail: str, data: dict | None = None, retry_after_s: int | None = None) -> dict:
    """The shared error envelope (§7), as an in-band `error` event carries it."""
    return {"detail": detail, "code": code, "status": status, "request_id": rid, "retry_after_s": retry_after_s, "data": data}


async def read_body(request: Request) -> bytes:
    length = request.headers.get("content-length")
    too_large = ContractError(
        "too_large", 413, "A request is at most 8 MB.", {"limit": validate.MAX_BODY_BYTES},
    )
    if length and length.isdigit() and int(length) > validate.MAX_BODY_BYTES:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > validate.MAX_BODY_BYTES:
            raise too_large
    return bytes(body)


def parse_json(raw: bytes) -> object:
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise validate.invalid("body", "a JSON object")


def require_feature(plan) -> None:
    if credits.FEATURE not in plan.features:
        raise ContractError(
            "plan_required", 403, "Truebex AI comes with Pro, Studio, Team and the trial. Upgrade to use it.",
            {"feature": credits.FEATURE, "plan": plan.id, "plan_needed": credits.plan_needed(plan)},
        )


def _resolve(db, turn: validate.Turn, table: aliases.Table, now) -> tuple[aliases.Alias, object | None]:
    """The alias that serves the turn: a self-hosted one while a server is
    warm, else its fallback alias."""
    alias = turn.alias
    if alias.adapter != "selfhosted":
        return alias, None
    server = servers.warm_server(db, alias.name, now)
    servers.note_turn(db, alias.name, server, now)
    if server is not None:
        return alias, server
    fallback = table.get(alias.fallback_alias) if alias.fallback_alias else None
    if fallback is None or fallback.adapter == "selfhosted":
        raise UpstreamError("busy", "no inference server is warm", retry_after_s=120).contract_error()
    return fallback, None


def _claim_key(db, user_id: int, key: str, now) -> None:
    old = db.scalar(select(AiRequestKey).where(AiRequestKey.account_kind == credits.ACCOUNT_KIND, AiRequestKey.account_id == user_id, AiRequestKey.key == key))
    if old is not None:
        if clock.aware(old.created_at) > now - KEY_WINDOW:
            raise ContractError(
                "duplicate_request", 409, "This turn was already sent. Send the message again to start a new one.",
                {"key": key},
            )
        db.delete(old)
        db.flush()
    db.add(AiRequestKey(account_kind=credits.ACCOUNT_KIND, account_id=user_id, key=key, created_at=now))


def prepare(user_id: int, device_id: str | None, body: object, key: str | None, rid: str, *, counting: bool = False) -> Prepared:
    """Every check before the provider is called; registers the turn in flight."""
    now = clock.now()
    table = aliases.current()
    with SessionLocal() as db:
        user = db.get(User, user_id)
        plan = credits.plan_of(db, user)
        require_feature(plan)
        turn = validate.parse_turn(body, table, plan.id, counting=counting)
        served, server = _resolve(db, turn, table, now)
        server_id = server.server_id if server is not None else None
        server_url = server.base_url if server is not None else None
        db.commit()
        if counting:
            row = credits.ensure(db, user, now, plan=plan)
            credits.check_can_start(plan, row, credits.estimate_input_tokens(turn.text_bytes, turn.images), served.rates)
            db.commit()
            return Prepared(turn, served, server_id, server_url, "", None, user_id, device_id, rid)
        ratelimit.check(f"ai.turns:{user_id}", per_minute=PER_MINUTE, burst=PER_MINUTE)
        row = credits.ensure(db, user, now, plan=plan)  # locks the account's row
        in_flight = db.scalar(
            select(func.count()).select_from(AiTurn).where(
                AiTurn.account_kind == credits.ACCOUNT_KIND, AiTurn.account_id == user_id, AiTurn.started_at > now - TURN_STALE
            )
        ) or 0
        if in_flight >= IN_FLIGHT_MAX:
            db.rollback()
            raise ContractError(
                "rate_limited", 429, f"At most {IN_FLIGHT_MAX} turns at once. Wait for one to finish.",
                {"in_flight": int(in_flight)}, retry_after_s=2,
            )
        credits.check_can_start(plan, row, credits.estimate_input_tokens(turn.text_bytes, turn.images), served.rates)
        if key:
            _claim_key(db, user_id, key, now)
        turn_id = secrets.token_hex(16)
        db.add(AiTurn(turn_id=turn_id, account_kind=credits.ACCOUNT_KIND, account_id=user_id, started_at=now))
        try:
            db.commit()
        except IntegrityError:  # the same key, sent twice at once
            db.rollback()
            raise ContractError("duplicate_request", 409, "This turn was already sent.", {"key": key})
        return Prepared(turn, served, server_id, server_url, turn_id, key, user_id, device_id, rid)


def release(p: Prepared, *, drop_key: bool) -> None:
    """The turn ended. A turn that failed before output gives its key back, so
    the app's retry (§8) is not refused as a duplicate."""
    if not p.turn_id:
        return
    with SessionLocal() as db:
        db.execute(delete(AiTurn).where(AiTurn.turn_id == p.turn_id))
        if drop_key and p.key:
            db.execute(delete(AiRequestKey).where(AiRequestKey.account_id == p.user_id, AiRequestKey.key == p.key))
        db.commit()


def settle(p: Prepared, outcome: str = "ok") -> tuple[int, int | None]:
    """Charge the turn from the usage the provider reported (once) and keep
    its usage record. Returns (charged, credits remaining)."""
    if p.settled:
        return 0, None
    p.settled = True
    now = clock.now()
    table = aliases.current()
    state = p.state
    model = state.model or p.served.model
    rates = table.rates_for(model, p.served)
    charged = credits.charge_for(state.usage, rates)
    with SessionLocal() as db:
        user = db.get(User, p.user_id)
        row = credits.ensure(db, user, now)
        credits.spend(db, row, charged, p.turn_id, now)
        db.add(
            AiUsage(
                turn_id=p.turn_id, at=now, account_kind=credits.ACCOUNT_KIND, account_id=p.user_id, device_id=p.device_id,
                session_id=p.turn.session_id, alias=p.turn.alias.name, provider_model=model[:80], served_by=p.served.adapter,
                stream=p.turn.stream, stop_reason=(state.stop_reason or None), input_tokens=int(state.usage.get("input_tokens") or 0),
                output_tokens=int(state.usage.get("output_tokens") or 0),
                cache_read_tokens=int(state.usage.get("cache_read_input_tokens") or 0),
                cache_write_tokens=int(state.usage.get("cache_creation_input_tokens") or 0),
                credits=charged, provider_cost_micros=credits.cost_micros(state.usage, table.usd_for(model)),
                tool_names=list(dict.fromkeys(state.tool_names))[:64], outcome=outcome,
            )
        )
        if p.server_id:
            from .models import AiServer

            server = db.get(AiServer, p.server_id)
            if server is not None:
                server.last_turn_at = now
        db.commit()
        left = credits.remaining(row) if credits.allowance_for(credits.plan_of(db, user)) is not None else None
    return charged, left


def served_by(p: Prepared) -> dict:
    return {"provider": p.served.provider, "model": p.state.model or p.served.model}


def credits_event(p: Prepared, charged: int, left: int | None) -> bytes:
    return encode("truebex_credits", {"charged": charged, "remaining": left, "served_by": served_by(p)})


def _upstream_event_error(payload: dict | None) -> UpstreamError:
    err = (payload or {}).get("error") or {}
    kind = err.get("type") if isinstance(err, dict) else None
    message = err.get("message") if isinstance(err, dict) else ""
    if kind in ("overloaded_error", "rate_limit_error"):
        return UpstreamError("busy", str(message or kind))
    if kind == "invalid_request_error":
        return UpstreamError("rejected", str(message or kind))
    return UpstreamError("failed", str(message or kind or "error"))


def _server(p: Prepared):
    return _Server(p.server_url) if p.server_url else None


# --- 5.3 streamed --------------------------------------------------------------------------


async def stream(request: Request, p: Prepared) -> StreamingResponse:
    adapter = adapters.get(p.served.adapter)
    stack = contextlib.AsyncExitStack()
    try:
        lines = await stack.enter_async_context(adapter.stream(p.turn, p.served, _server(p)))
    except UpstreamError as exc:
        await stack.aclose()
        await run_in_threadpool(release, p, drop_key=True)
        raise exc.contract_error()
    except BaseException:
        await stack.aclose()
        await run_in_threadpool(release, p, drop_key=True)
        raise

    queue: asyncio.Queue = asyncio.Queue()

    async def pump() -> None:
        try:
            async for line in lines:
                await queue.put(line)
            await queue.put(_END)
        except UpstreamError as exc:
            await queue.put(exc)
        except Exception as exc:  # noqa: BLE001
            await queue.put(UpstreamError("failed", exc.__class__.__name__))

    task = asyncio.create_task(pump())
    buffer = EventBuffer()

    async def close_upstream() -> None:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
        with contextlib.suppress(BaseException):
            await stack.aclose()

    # Hold the status until the first event (or PEEK_S): a provider that fails
    # before output answers 422 / 502 / 503 with nothing charged.
    first: list = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + PEEK_S
    try:
        while not first:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                item = await asyncio.wait_for(queue.get(), remaining)
            except asyncio.TimeoutError:
                break
            if item is _END:
                raise UpstreamError("failed", "the stream ended before it began")
            if isinstance(item, UpstreamError):
                raise item
            event = buffer.feed(item)
            if event is None:
                continue
            if event.name == "error":
                raise _upstream_event_error(event.json())
            first.append(event)
    except UpstreamError as exc:
        await close_upstream()
        await run_in_threadpool(release, p, drop_key=True)
        raise exc.contract_error()
    except BaseException:
        await close_upstream()
        await run_in_threadpool(release, p, drop_key=True)
        raise

    async def relay():
        error: UpstreamError | None = None
        done = False
        outcome = "ok"
        try:
            pending = list(first)
            while True:
                if pending:
                    event = pending.pop(0)
                else:
                    try:
                        item = await asyncio.wait_for(queue.get(), PING_S)
                    except asyncio.TimeoutError:
                        yield PING
                        continue
                    if item is _END:
                        break
                    if isinstance(item, UpstreamError):
                        error = item
                        break
                    event = buffer.feed(item)
                    if event is None:
                        continue
                if event.name == "error":
                    error = _upstream_event_error(event.json())
                    break
                p.state.observe(event)
                if event.name == "message_stop":
                    charged, left = await run_in_threadpool(settle, p, "ok")
                    yield credits_event(p, charged, left)
                    yield event.raw
                    done = True
                    break
                yield event.raw
            if not done:
                error = error or UpstreamError("failed", "the stream ended early")
                outcome = "upstream_error"
                charged, left = await run_in_threadpool(settle, p, outcome)
                yield credits_event(p, charged, left)
                code, status, detail, data, after = error.envelope_parts()
                yield encode("error", envelope(p.rid, code, status, detail, data, after))
        finally:
            await close_upstream()
            if not p.settled:
                # The app went away mid-stream: charge what the provider billed.
                with contextlib.suppress(Exception):
                    settle(p, "client_gone")
            with contextlib.suppress(Exception):
                release(p, drop_key=False)

    headers = {**_headers(request), "Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(relay(), media_type="text/event-stream", headers=headers)


# --- 5.3 whole -------------------------------------------------------------------------------


async def whole(request: Request, p: Prepared) -> JSONResponse:
    adapter = adapters.get(p.served.adapter)
    try:
        data = await adapter.whole(p.turn, p.served, _server(p))
    except UpstreamError as exc:
        await run_in_threadpool(release, p, drop_key=True)
        raise exc.contract_error()
    except BaseException:
        await run_in_threadpool(release, p, drop_key=True)
        raise
    try:
        p.state.model = data.get("model") or p.served.model
        p.state.merge_usage(data.get("usage"))
        p.state.stop_reason = data.get("stop_reason")
        for block in data.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and isinstance(block.get("name"), str):
                p.state.tool_names.append(block["name"][:64])
        charged, left = await run_in_threadpool(settle, p, "ok")
    finally:
        await run_in_threadpool(release, p, drop_key=False)
    out = dict(data)
    out["model"] = p.turn.alias.name
    out.setdefault("stop_details", None)
    out["credits"] = {"charged": charged, "remaining": left}
    out["served_by"] = served_by(p)
    return JSONResponse(out, headers=_headers(request))


# --- 5.4 --------------------------------------------------------------------------------------


async def count(request: Request, p: Prepared) -> JSONResponse:
    adapter = adapters.get(p.served.adapter)
    try:
        tokens = await adapter.count(p.turn, p.served, _server(p))
    except UpstreamError as exc:
        raise exc.contract_error()
    rates = p.served.rates
    max_credits = -(-(tokens * rates["input"] + p.turn.max_tokens * rates["output"]) // 1_000_000)
    return JSONResponse({"input_tokens": tokens, "max_credits": max_credits}, headers=_headers(request))


# --- 5.1 ------------------------------------------------------------------------------------------


def models_json(plan_id: str, features: tuple[str, ...]) -> dict:
    table = aliases.current()
    usable = table.usable(plan_id) if credits.FEATURE in features else []
    names = [a.name for a in usable]
    return {
        "default": table.default if table.default in names else (names[0] if names else None),
        "models": [
            {
                "alias": a.name,
                "context_tokens": a.context_tokens,
                "max_output_tokens": a.max_output_tokens,
                "vision": a.vision,
                "credits_per_mtok": dict(a.rates),
            }
            for a in usable
        ],
    }


def rid_of(request: Request) -> str:
    return request_id(request)
