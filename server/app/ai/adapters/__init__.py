"""Provider adapters behind the alias table: `anthropic` and `selfhosted`."""

from .anthropic import AnthropicAdapter
from .base import UpstreamError
from .selfhosted import SelfHostedAdapter

ADAPTERS = {"anthropic": AnthropicAdapter(), "selfhosted": SelfHostedAdapter()}


def get(name: str):
    return ADAPTERS[name]


__all__ = ["ADAPTERS", "UpstreamError", "get"]
