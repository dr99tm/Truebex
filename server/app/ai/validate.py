"""The rules of contract ai-proxy §5 for 5.3 and 5.4 bodies (422 `validation_failed`).

The proxy reads a turn only as far as these rules need: the alias, the
roles and block types, images (count, type, size, pixels), `tool_choice`,
`max_tokens`, `metadata`. Tool definitions, tool inputs and tool results are
passed on untouched; nothing here is stored.
"""

import base64
import binascii
import re
import struct
from dataclasses import dataclass

from ..contract_http import ContractError
from .aliases import Alias, Table

MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_TOOLS = 64
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_EDGE = 1568
MAX_TOKENS_STREAM = 64_000
MAX_TOKENS_WHOLE = 4_096
ROLES = ("user", "assistant")
# The contract's blocks, plus what a turn's own answer may carry back into the
# append-only history: a redacted thinking block and a refusal fallback's marker.
BLOCKS = ("text", "image", "tool_use", "tool_result", "thinking", "redacted_thinking", "fallback")
IMAGE_TYPES = ("image/png", "image/jpeg")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@dataclass
class Turn:
    """What the proxy keeps of a valid body: the alias and the forwardable parts."""

    alias: Alias
    stream: bool
    max_tokens: int
    system: object
    messages: list
    tools: list
    tool_choice: dict | None
    session_id: str | None
    app_version: str | None
    images: int
    text_bytes: int


def invalid(field: str, message: str, **data) -> ContractError:
    return ContractError(
        "validation_failed", 422, f"{field}: {message}",
        {"fields": [{"field": field, "in": "body", "message": message}], **data},
    )


def _image_size(data: bytes, media_type: str) -> tuple[int, int] | None:
    """(width, height) from a PNG's IHDR or a JPEG's SOF marker."""
    if media_type == "image/png":
        if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
            return struct.unpack(">II", data[16:24])
        return None
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        i += 2 + length
    return None


class _Walker:
    def __init__(self) -> None:
        self.images = 0
        self.text_bytes = 0

    def image(self, block: dict, where: str) -> None:
        self.images += 1
        if self.images > MAX_IMAGES:
            raise invalid(where, f"at most {MAX_IMAGES} images per request", limit=MAX_IMAGES)
        source = block.get("source")
        if not isinstance(source, dict) or source.get("type") != "base64":
            raise invalid(f"{where}.source", "a base64 PNG or JPEG")
        media = source.get("media_type")
        if media not in IMAGE_TYPES:
            raise invalid(f"{where}.source.media_type", "image/png or image/jpeg")
        raw = source.get("data")
        if not isinstance(raw, str):
            raise invalid(f"{where}.source.data", "base64 text")
        if len(raw) > (MAX_IMAGE_BYTES * 4) // 3 + 8:
            raise invalid(f"{where}.source.data", "at most 2 MB per image", limit_bytes=MAX_IMAGE_BYTES)
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            raise invalid(f"{where}.source.data", "base64 text")
        if len(data) > MAX_IMAGE_BYTES:
            raise invalid(f"{where}.source.data", "at most 2 MB per image", limit_bytes=MAX_IMAGE_BYTES)
        size = _image_size(data, media)
        if size is None:
            raise invalid(f"{where}.source.data", f"a readable {media.split('/')[1].upper()} file")
        if max(size) > MAX_IMAGE_EDGE:
            raise invalid(f"{where}.source.data", f"the long edge at most {MAX_IMAGE_EDGE} px", width=size[0], height=size[1])

    def blocks(self, content: object, where: str, role: str) -> None:
        if isinstance(content, str):
            self.text_bytes += len(content.encode("utf-8"))
            return
        if not isinstance(content, list) or not content:
            raise invalid(where, "a string or a list of content blocks")
        for i, block in enumerate(content):
            here = f"{where}[{i}]"
            if not isinstance(block, dict) or block.get("type") not in BLOCKS:
                raise invalid(f"{here}.type", f"one of {', '.join(BLOCKS[:5])}")
            kind = block["type"]
            if kind == "image":
                if role != "user":
                    raise invalid(here, "images come from the user")
                self.image(block, here)
            elif kind == "tool_result":
                if role != "user":
                    raise invalid(here, "a tool_result comes from the user")
                if not isinstance(block.get("tool_use_id"), str):
                    raise invalid(f"{here}.tool_use_id", "the id of the tool_use it answers")
                inner = block.get("content")
                if isinstance(inner, list):
                    for j, part in enumerate(inner):
                        if isinstance(part, dict) and part.get("type") == "image":
                            self.image(part, f"{here}.content[{j}]")
                        elif isinstance(part, dict) and isinstance(part.get("text"), str):
                            self.text_bytes += len(part["text"].encode("utf-8"))
                elif isinstance(inner, str):
                    self.text_bytes += len(inner.encode("utf-8"))
            elif kind == "tool_use":
                if role != "assistant":
                    raise invalid(here, "a tool_use comes from the assistant")
                if not isinstance(block.get("id"), str) or not isinstance(block.get("name"), str):
                    raise invalid(here, "a tool_use has an id and a name")
                if not isinstance(block.get("input"), dict):
                    raise invalid(f"{here}.input", "an object")
                self.text_bytes += 64
            elif kind == "text":
                if not isinstance(block.get("text"), str):
                    raise invalid(f"{here}.text", "a string")
                self.text_bytes += len(block["text"].encode("utf-8"))
            elif kind in ("thinking", "redacted_thinking"):
                if role != "assistant":
                    raise invalid(here, "thinking comes from the assistant")


def parse_turn(body: object, table: Table, plan_id: str, *, counting: bool = False) -> Turn:
    """Check a 5.3 (or, with `counting`, a 5.4) body against §5."""
    if not isinstance(body, dict):
        raise invalid("body", "a JSON object")
    name = body.get("model")
    alias = table.get(name) if isinstance(name, str) else None
    if alias is None or (alias.plans and plan_id not in alias.plans):
        usable = [a.name for a in table.usable(plan_id)]
        raise invalid("model", f"one of the aliases of GET /ai/models: {', '.join(usable) or 'none'}", aliases=usable)
    stream = False if counting else body.get("stream", False)
    if not isinstance(stream, bool):
        raise invalid("stream", "true or false")
    max_tokens = body.get("max_tokens")
    cap = min(MAX_TOKENS_STREAM if stream or counting else MAX_TOKENS_WHOLE, alias.max_output_tokens)
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or not 1 <= max_tokens <= cap:
        raise invalid("max_tokens", f"1 to {cap}" + ("" if stream or counting else " when stream is false"), limit=cap)
    choice = body.get("tool_choice")
    if choice is not None and (not isinstance(choice, dict) or choice.get("type") not in ("auto", "none")):
        raise invalid("tool_choice", '{"type": "auto"} or {"type": "none"} only: the model refuses forced tool use')
    tools = body.get("tools") or []
    if not isinstance(tools, list) or len(tools) > MAX_TOOLS:
        raise invalid("tools", f"a list of at most {MAX_TOOLS} tools", limit=MAX_TOOLS)
    for i, tool in enumerate(tools):
        if (
            not isinstance(tool, dict)
            or not isinstance(tool.get("name"), str)
            or not _TOOL_NAME.match(tool["name"])
            or not isinstance(tool.get("input_schema"), dict)
        ):
            raise invalid(f"tools[{i}]", "a name (letters, digits, _ and -) and an input_schema object")
    system = body.get("system")
    walker = _Walker()
    if system is not None:
        if isinstance(system, list):
            if not all(isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str) for b in system):
                raise invalid("system", "a string or a list of text blocks")
            walker.text_bytes += sum(len(b["text"].encode("utf-8")) for b in system)
        elif isinstance(system, str):
            walker.text_bytes += len(system.encode("utf-8"))
        else:
            raise invalid("system", "a string or a list of text blocks")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise invalid("messages", "a list of at least one message")
    for i, message in enumerate(messages):
        if not isinstance(message, dict) or message.get("role") not in ROLES:
            raise invalid(f"messages[{i}].role", "user or assistant")
        walker.blocks(message.get("content"), f"messages[{i}].content", message["role"])
    if messages[0]["role"] != "user":
        raise invalid("messages[0].role", "a conversation starts with the user")
    if walker.images and not alias.vision:
        raise invalid("messages", f"{alias.name} does not read images")
    for tool in tools:
        walker.text_bytes += len(str(tool.get("description") or "").encode("utf-8")) + 200
    meta = body.get("metadata") or {}
    if not isinstance(meta, dict):
        raise invalid("metadata", "an object")
    session_id = meta.get("session_id")
    if session_id is not None and (not isinstance(session_id, str) or not _HEX32.match(session_id)):
        raise invalid("metadata.session_id", "32 lowercase hex characters")
    app_version = meta.get("app_version")
    return Turn(
        alias=alias, stream=stream, max_tokens=max_tokens, system=system, messages=messages, tools=tools,
        tool_choice=choice, session_id=session_id, app_version=str(app_version)[:32] if app_version else None,
        images=walker.images, text_bytes=walker.text_bytes,
    )
