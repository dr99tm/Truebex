"""The self-hosted adapter: an open-weight model behind an OpenAI-compatible
inference server on a gpu-ai worker (contract ai-proxy §6.1, PF11 Scope 6).

A Messages turn becomes a chat-completions request (system text, user text
and images, assistant text and tool calls, tool results as `tool` messages,
the tool definitions as functions); the answer comes back as the Messages
format: a whole message, or the Messages stream's events (`message_start`,
text and tool_use blocks with their deltas, `message_delta` with
`stop_reason` and `usage`, `message_stop`). Tool inputs and results are
carried verbatim (an input is the function's `arguments` JSON). Thinking
blocks are not sent: these models do not read them. The input count is the
proxy's local estimate (the API has no count endpoint).
"""

import json
import secrets
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

from ...config import get_settings
from .. import credits
from ..sse import encode
from .base import TIMEOUT_S, UpstreamError, retry_after

STOP = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use", "function_call": "tool_use", "content_filter": "refusal"}


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for part in content or []:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            parts.append(part["text"])
    return "\n".join(parts)


def chat_messages(turn) -> list[dict]:
    out: list[dict] = []
    if turn.system is not None:
        out.append({"role": "system", "content": _text_of(turn.system)})
    for message in turn.messages:
        content = message["content"]
        if isinstance(content, str):
            out.append({"role": message["role"], "content": content})
            continue
        if message["role"] == "assistant":
            text = "".join(b["text"] for b in content if b.get("type") == "text")
            calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b["input"], ensure_ascii=False, separators=(",", ":"))},
                }
                for b in content
                if b.get("type") == "tool_use"
            ]
            entry: dict = {"role": "assistant", "content": text or None}
            if calls:
                entry["tool_calls"] = calls
            out.append(entry)
            continue
        parts: list[dict] = []
        for block in content:
            kind = block.get("type")
            if kind == "tool_result":
                text = _text_of(block.get("content"))
                out.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": text})
            elif kind == "text":
                parts.append({"type": "text", "text": block["text"]})
            elif kind == "image":
                src = block["source"]
                parts.append({"type": "image_url", "image_url": {"url": f"data:{src['media_type']};base64,{src['data']}"}})
        if parts:
            out.append({"role": "user", "content": parts})
    return out


def chat_body(turn, alias, *, stream: bool) -> dict:
    body: dict = {"model": alias.model, "messages": chat_messages(turn), "max_tokens": turn.max_tokens, "stream": stream}
    if turn.tools:
        body["tools"] = [
            {"type": "function", "function": {"name": t["name"], "description": t.get("description") or "", "parameters": t["input_schema"]}}
            for t in turn.tools
        ]
        body["tool_choice"] = (turn.tool_choice or {}).get("type", "auto")
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


def _headers() -> dict:
    key = get_settings().selfhosted_api_key
    return {"Authorization": f"Bearer {key}"} if key else {}


def _url(server) -> str:
    return f"{server.base_url.rstrip('/')}/v1/chat/completions"


def _map_status(res: httpx.Response) -> UpstreamError:
    try:
        detail = str((res.json().get("error") or {}).get("message") or res.text[:200])
    except ValueError:
        detail = res.text[:200]
    if res.status_code in (400, 404, 413, 422):
        return UpstreamError("rejected", detail, status=res.status_code)
    if res.status_code in (429, 503):
        return UpstreamError("busy", detail, retry_after_s=retry_after(res.headers.get("retry-after")), status=res.status_code)
    return UpstreamError("failed", detail, status=res.status_code)


def _usage(raw: dict | None) -> dict:
    raw = raw or {}
    return {"input_tokens": int(raw.get("prompt_tokens") or 0), "output_tokens": int(raw.get("completion_tokens") or 0)}


def _message_id() -> str:
    return f"msg_tbx_{secrets.token_hex(12)}"


class _Translator:
    """Chat-completion chunks -> Messages stream events (as raw SSE lines)."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.index = -1
        self.open: str | None = None  # "text" | "tool:<n>"
        self.finish: str | None = None
        self.usage: dict = {}

    def _lines(self, name: str, payload: dict) -> list[str]:
        return encode(name, payload).decode("utf-8").split("\n")

    def start(self) -> list[str]:
        message = {
            "id": _message_id(), "type": "message", "role": "assistant", "model": self.model, "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0},
        }
        return self._lines("message_start", {"type": "message_start", "message": message})

    def _close(self) -> list[str]:
        if self.open is None:
            return []
        self.open = None
        return self._lines("content_block_stop", {"type": "content_block_stop", "index": self.index})

    def _open(self, key: str, block: dict) -> list[str]:
        out = self._close()
        self.index += 1
        self.open = key
        return out + self._lines("content_block_start", {"type": "content_block_start", "index": self.index, "content_block": block})

    def chunk(self, data: dict) -> list[str]:
        out: list[str] = []
        if data.get("usage"):
            self.usage = _usage(data["usage"])
        for choice in data.get("choices") or []:
            delta = choice.get("delta") or {}
            text = delta.get("content")
            if isinstance(text, str) and text:
                if self.open != "text":
                    out += self._open("text", {"type": "text", "text": ""})
                out += self._lines("content_block_delta", {"type": "content_block_delta", "index": self.index, "delta": {"type": "text_delta", "text": text}})
            for call in delta.get("tool_calls") or []:
                key = f"tool:{call.get('index', 0)}"
                fn = call.get("function") or {}
                if self.open != key:
                    block = {"type": "tool_use", "id": call.get("id") or f"toolu_tbx_{secrets.token_hex(8)}", "name": fn.get("name") or "", "input": {}}
                    out += self._open(key, block)
                args = fn.get("arguments")
                if isinstance(args, str) and args:
                    out += self._lines("content_block_delta", {"type": "content_block_delta", "index": self.index, "delta": {"type": "input_json_delta", "partial_json": args}})
            if choice.get("finish_reason"):
                self.finish = choice["finish_reason"]
        return out

    def end(self) -> list[str]:
        out = self._close()
        stop = STOP.get(self.finish or "stop", "end_turn")
        out += self._lines("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": self.usage})
        out += self._lines("message_stop", {"type": "message_stop"})
        return out


class SelfHostedAdapter:
    name = "selfhosted"

    @asynccontextmanager
    async def stream(self, turn, alias, server):
        client = httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_S, connect=10.0))
        try:
            request = client.build_request("POST", _url(server), json=chat_body(turn, alias, stream=True), headers=_headers())
            try:
                response = await client.send(request, stream=True)
            except httpx.HTTPError as exc:
                raise UpstreamError("failed", exc.__class__.__name__) from None
            try:
                if response.status_code >= 400:
                    await response.aread()
                    raise _map_status(response)
                yield self._events(response, alias.model)
            finally:
                await response.aclose()
        finally:
            await client.aclose()

    async def _events(self, response, model: str) -> AsyncIterator[str]:
        t = _Translator(model)
        for line in t.start():
            yield line
        try:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                except ValueError:
                    continue
                for out in t.chunk(data):
                    yield out
        except httpx.HTTPError as exc:
            raise UpstreamError("failed", f"the stream broke ({exc.__class__.__name__})") from None
        for line in t.end():
            yield line

    async def whole(self, turn, alias, server) -> dict:
        async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_S, connect=10.0)) as client:
            try:
                res = await client.post(_url(server), json=chat_body(turn, alias, stream=False), headers=_headers())
            except httpx.HTTPError as exc:
                raise UpstreamError("failed", exc.__class__.__name__) from None
        if res.status_code >= 400:
            raise _map_status(res)
        try:
            data = res.json()
            message = data["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise UpstreamError("failed", "the inference server's answer was not a chat completion") from None
        content: list[dict] = []
        if isinstance(message.get("content"), str) and message["content"]:
            content.append({"type": "text", "text": message["content"]})
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            content.append({"type": "tool_use", "id": call.get("id") or f"toolu_tbx_{secrets.token_hex(8)}", "name": fn.get("name") or "", "input": args})
        finish = data["choices"][0].get("finish_reason") or "stop"
        return {
            "id": _message_id(), "type": "message", "role": "assistant", "model": alias.model, "content": content,
            "stop_reason": STOP.get(finish, "end_turn"), "stop_sequence": None, "stop_details": None, "usage": _usage(data.get("usage")),
        }

    async def count(self, turn, alias, server=None) -> int:
        return credits.estimate_input_tokens(turn.text_bytes, turn.images)
