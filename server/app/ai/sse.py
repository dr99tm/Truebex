"""Server-sent events as the proxy relays them (contract ai-proxy §5).

The provider's stream is relayed line by line: `EventBuffer` groups raw lines
into events without re-serialising them, so a `tool_use` block reaches the
app byte-equal. `StreamState` reads only what metering needs: the answering
model, `usage`, `stop_reason` and the names of the tools called.
"""

import json
from dataclasses import dataclass, field


@dataclass
class Event:
    name: str | None
    data: str
    lines: list[str]

    @property
    def raw(self) -> bytes:
        return ("\n".join(self.lines) + "\n\n").encode("utf-8")

    def json(self) -> dict | None:
        try:
            value = json.loads(self.data)
        except ValueError:
            return None
        return value if isinstance(value, dict) else None


class EventBuffer:
    """Feed raw lines (without their line ends); a blank line ends an event."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def feed(self, line: str) -> Event | None:
        if line != "":
            self.lines.append(line)
            return None
        if not self.lines:
            return None
        lines, self.lines = self.lines, []
        name = None
        data: list[str] = []
        for item in lines:
            if item.startswith("event:"):
                name = item[6:].strip()
            elif item.startswith("data:"):
                data.append(item[5:][1:] if item[5:].startswith(" ") else item[5:])
        return Event(name=name, data="\n".join(data), lines=lines)


def encode(name: str, payload: dict) -> bytes:
    return f"event: {name}\ndata: {json.dumps(payload, separators=(',', ':'), ensure_ascii=False)}\n\n".encode("utf-8")


PING = encode("ping", {"type": "ping"})
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


@dataclass
class StreamState:
    model: str | None = None
    usage: dict = field(default_factory=dict)
    stop_reason: str | None = None
    tool_names: list[str] = field(default_factory=list)
    started: bool = False
    output_began: bool = False
    finished: bool = False

    def merge_usage(self, usage: object) -> None:
        if isinstance(usage, dict):
            for key in USAGE_KEYS:
                value = usage.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    self.usage[key] = value

    def observe(self, event: Event) -> None:
        kind = event.name
        if kind not in ("message_start", "content_block_start", "content_block_delta", "message_delta", "message_stop"):
            return
        if kind == "message_stop":
            self.finished = True
            return
        if kind == "content_block_delta":
            self.output_began = True
            return
        data = event.json() or {}
        if kind == "message_start":
            self.started = True
            message = data.get("message") or {}
            self.model = message.get("model") or self.model
            self.merge_usage(message.get("usage"))
        elif kind == "content_block_start":
            self.output_began = True
            block = data.get("content_block") or {}
            if block.get("type") == "tool_use" and isinstance(block.get("name"), str):
                self.tool_names.append(block["name"][:64])
        elif kind == "message_delta":
            delta = data.get("delta") or {}
            self.stop_reason = delta.get("stop_reason") or self.stop_reason
            self.merge_usage(data.get("usage"))
