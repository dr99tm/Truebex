"""What every provider adapter does (contract ai-proxy §6.1).

An adapter translates a checked turn (`validate.Turn`) into its provider's
API and back into the Messages format, carrying `tool_use` inputs and
`tool_result` contents verbatim:

    async with adapter.stream(turn, alias, server) as lines:   # raw SSE lines
        async for line in lines: ...
    message = await adapter.whole(turn, alias, server)        # a Messages JSON object
    tokens = await adapter.count(turn, alias, server)         # input tokens

Upstream failures raise `UpstreamError`, which the proxy answers as §7 says.
"""

from contextlib import AbstractAsyncContextManager
from typing import AsyncIterator, Protocol

from ...contract_http import ContractError

# HTTP timeout to a provider; a streamed turn's events keep it alive.
TIMEOUT_S = 600.0


class UpstreamError(Exception):
    """kind: rejected (422 upstream_rejected), busy (503), failed (502)."""

    def __init__(self, kind: str, message: str = "", *, retry_after_s: int | None = None, status: int | None = None) -> None:
        super().__init__(f"{kind}: {message}"[:300])
        self.kind = kind
        self.provider_message = (message or "")[:300]
        self.retry_after_s = retry_after_s
        self.status = status

    def contract_error(self) -> ContractError:
        if self.kind == "rejected":
            return ContractError(
                "upstream_rejected", 422, "The model provider refused this request.",
                {"provider_message": self.provider_message},
            )
        if self.kind == "busy":
            after = self.retry_after_s or 10
            return ContractError(
                "upstream_busy", 503, "The AI service is busy. Try again in a moment.", {}, retry_after_s=after,
            )
        return ContractError("upstream_failed", 502, "The AI service didn't respond. Please try again.", {})

    def envelope_parts(self) -> tuple[str, int, str, dict, int | None]:
        err = self.contract_error()
        return err.code, err.status, err.detail, err.data or {}, err.retry_after_s


def retry_after(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return max(1, int(float(value)))
    except ValueError:
        return None


class Adapter(Protocol):
    name: str

    def stream(self, turn, alias, server) -> AbstractAsyncContextManager[AsyncIterator[str]]: ...

    async def whole(self, turn, alias, server) -> dict: ...

    async def count(self, turn, alias, server) -> int: ...
