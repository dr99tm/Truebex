"""Which webhook URLs are allowed (PF12 §Security): https, with a host that
resolves to public addresses only, checked when the endpoint is saved (a clear
422). Each delivery connects over PF14b's pinned connection
(`app.net.outbound`), which resolves the name once more, checks every address
and connects to a checked one: a name that later points at a private address
(DNS rebinding) fails that attempt with the same reason. WEBHOOKS_ALLOW_HTTP_LOCAL
lets `http://127.0.0.1` / `localhost` through, for local testing only."""

import ipaddress
from urllib.parse import urlsplit

from ..config import get_settings
from ..contract_http import ContractError
from ..net import outbound

MAX_URL = 2048
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class UrlRefused(ValueError):
    pass


NOT_PUBLIC = "a host that resolves to public addresses only"


def resolve(host: str) -> list[str]:
    """Every address `host` resolves to (patched in tests)."""
    return outbound.resolve(host)


def _public(address: str) -> bool:
    return outbound.is_public(address)


def unresolved(host: str) -> str:
    return f"a host that resolves ({host} does not)"


def refusal(exc: outbound.Refused) -> str:
    """The save-time reason for a delivery the pinned connection refused."""
    return unresolved(exc.host) if exc.reason == outbound.UNRESOLVED else NOT_PUBLIC


def _local_http_allowed(scheme: str, host: str) -> bool:
    return scheme == "http" and host in LOCAL_HOSTS and get_settings().webhooks_allow_http_local


def check(url: str, *, resolve_host: bool = True) -> str:
    """The URL, cleaned; UrlRefused with a reason otherwise."""
    url = (url or "").strip()
    if not url or len(url) > MAX_URL:
        raise UrlRefused(f"a URL of 1 to {MAX_URL} characters")
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if not host:
        raise UrlRefused("an absolute https:// URL")
    if parts.username or parts.password:
        raise UrlRefused("no user name or password in the URL")
    if _local_http_allowed(scheme, host):
        return url
    if scheme != "https":
        raise UrlRefused("https:// only")
    if host in LOCAL_HOSTS or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
        raise UrlRefused("a public host, not a local one")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not _public(str(literal)):
            raise UrlRefused("a public address, not a private, loopback or reserved one")
        return url
    if resolve_host:
        try:
            addresses = resolve(host)
        except (OSError, UnicodeError):
            raise UrlRefused(unresolved(host))
        if not addresses or not all(_public(a) for a in addresses):
            raise UrlRefused(NOT_PUBLIC)
    return url


def check_or_422(url: str, field: str = "url") -> str:
    try:
        return check(url)
    except UrlRefused as exc:
        raise ContractError(
            "validation_failed",
            422,
            f"{field}: {exc}",
            {"fields": [{"field": field, "in": "body", "message": str(exc)}]},
        )
