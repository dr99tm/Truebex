"""The Anthropic adapter (contract ai-proxy §6.1; PF11 Design decision).

The official `anthropic` SDK sends the turn; a streamed answer is relayed from
the SDK's streaming-response access to the raw lines, so `tool_use` blocks
reach the app byte-equal and the proxy reads only `usage`. Per request:

* `thinking` adaptive, never disabled (the default model always thinks), and
  the alias's `effort` set explicitly in `output_config`;
* the server-side refusal fallback (`fallbacks: "default"`, beta
  `server-side-fallback-2026-07-01`), so a declined turn can be answered by
  another model (`served_by.model` then names it);
* cache breakpoints at the end of `tools` and `system` (both byte-stable
  within a conversation, contract §5), plus automatic caching of the
  append-only history;
* `metadata` (the app's session id) is never sent upstream; retries are the
  app's (§8), so the SDK's own are off.
"""

import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

from ...config import get_settings
from .base import TIMEOUT_S, UpstreamError, retry_after

FALLBACK_BETA = "server-side-fallback-2026-07-01"
EPHEMERAL = {"type": "ephemeral"}


def _sdk():
    import anthropic  # imported on first use: the proxy is the only user

    return anthropic


def _client():
    s = get_settings()
    if not s.anthropic_api_key:
        raise UpstreamError("failed", "ANTHROPIC_API_KEY is not set on this server.")
    kwargs = {"api_key": s.anthropic_api_key, "max_retries": 0, "timeout": TIMEOUT_S}
    if s.anthropic_base_url:
        kwargs["base_url"] = s.anthropic_base_url
    return _sdk().AsyncAnthropic(**kwargs)


def _with_breakpoint(blocks: list) -> list:
    """A copy whose last block carries the cache breakpoint (the others untouched)."""
    out = list(blocks)
    if out and isinstance(out[-1], dict):
        out[-1] = {**out[-1], "cache_control": EPHEMERAL}
    return out


def params(turn, alias, *, stream: bool, counting: bool = False) -> dict:
    p: dict = {"model": alias.model, "messages": turn.messages, "thinking": {"type": "adaptive"}}
    if not counting:
        p["max_tokens"] = turn.max_tokens
    if alias.effort:
        p["output_config"] = {"effort": alias.effort}
    if turn.tools:
        p["tools"] = _with_breakpoint(turn.tools)
    if turn.tools and turn.tool_choice is not None:
        p["tool_choice"] = turn.tool_choice
    if turn.system is not None:
        system = [{"type": "text", "text": turn.system}] if isinstance(turn.system, str) else turn.system
        p["system"] = _with_breakpoint(system)
    if not counting:
        p["cache_control"] = EPHEMERAL
        if alias.fallbacks:
            p["fallbacks"] = alias.fallbacks
            p["betas"] = [FALLBACK_BETA]
        if stream:
            p["stream"] = True
    return p


def _message(exc) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        msg = err.get("message") if isinstance(err, dict) else None
        if isinstance(msg, str):
            return msg
    return str(getattr(exc, "message", "") or exc.__class__.__name__)


def map_error(exc: Exception) -> UpstreamError:
    """§7: 400 -> upstream_rejected; 429, 529, 503 -> upstream_busy; else upstream_failed."""
    sdk = _sdk()
    if isinstance(exc, UpstreamError):
        return exc
    if isinstance(exc, sdk.APIStatusError):
        status = exc.status_code
        if status in (400, 404, 413, 422):
            return UpstreamError("rejected", _message(exc), status=status)
        if status in (429, 503, 529):
            headers = exc.response.headers if exc.response is not None else {}
            return UpstreamError("busy", _message(exc), retry_after_s=retry_after(headers.get("retry-after")), status=status)
        return UpstreamError("failed", _message(exc), status=status)
    return UpstreamError("failed", exc.__class__.__name__)


async def _lines(response) -> AsyncIterator[str]:
    try:
        async for line in response.iter_lines():
            yield line
    except Exception as exc:  # noqa: BLE001 - a cut connection, a read timeout
        raise UpstreamError("failed", f"the stream broke ({exc.__class__.__name__})") from None


class AnthropicAdapter:
    name = "anthropic"

    @asynccontextmanager
    async def stream(self, turn, alias, server=None):
        client = _client()
        try:
            manager = client.beta.messages.with_streaming_response.create(**params(turn, alias, stream=True))
            try:
                response = await manager.__aenter__()
            except Exception as exc:  # noqa: BLE001
                raise map_error(exc) from None
            try:
                yield _lines(response)
            finally:
                await manager.__aexit__(None, None, None)
        finally:
            await client.close()

    async def whole(self, turn, alias, server=None) -> dict:
        client = _client()
        try:
            try:
                raw = await client.beta.messages.with_raw_response.create(**params(turn, alias, stream=False))
                body = await raw.read()
            except Exception as exc:  # noqa: BLE001
                raise map_error(exc) from None
        finally:
            await client.close()
        try:
            data = json.loads(body)
        except ValueError:
            raise UpstreamError("failed", "the provider's answer was not JSON") from None
        if not isinstance(data, dict):
            raise UpstreamError("failed", "the provider's answer was not a message")
        return data

    async def count(self, turn, alias, server=None) -> int:
        client = _client()
        try:
            try:
                answer = await client.beta.messages.count_tokens(**params(turn, alias, stream=False, counting=True))
            except Exception as exc:  # noqa: BLE001
                raise map_error(exc) from None
        finally:
            await client.close()
        return int(answer.input_tokens)
