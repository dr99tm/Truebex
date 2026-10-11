"""Requests to addresses someone else chose (PF14b): feed, image and geometry
URLs (suppliers), webhook endpoints (accounts) and OpenID Connect issuers
(organisation admins).

`client()` is an httpx.Client whose every TCP connection resolves the host
once, refuses it (`Refused`, before anything is sent) unless every address is
public (`is_public`), and connects to one of those checked addresses. There is
no second lookup, so a DNS answer that changes between the check and the
connection (rebinding) cannot reach this machine's own network. TLS still
verifies the certificate for the host name, which travels in SNI and in the
Host header. The client follows no redirects: callers that follow them send
each hop through it, so every hop (and any retry) is checked the same way.

Public means global unicast: Python's `is_global`, and explicitly not
loopback, link-local, multicast, reserved, unspecified, private, IPv6
site-local or 100.64.0.0/10 (shared address space). An IPv4-mapped
(::ffff:0:0/96), NAT64 (64:ff9b::/96) or 6to4 (2002::/16) address is judged by
the IPv4 address it reaches.

`resolve`, `connect` and `tls_context` are the seams the tests patch.
"""

import ipaddress
import socket
import ssl
import time
from collections.abc import Iterable

import httpcore
import httpx

SHARED = ipaddress.ip_network("100.64.0.0/10")  # RFC 6598, carrier-grade NAT
NAT64 = ipaddress.ip_network("64:ff9b::/96")  # RFC 6052, the well-known prefix
# The addresses of one name tried in turn, when one does not answer.
MAX_ADDRESSES = 4

UNRESOLVED = "does not resolve"
NOT_PUBLIC = "resolves to an address that is not public"

Address = ipaddress.IPv4Address | ipaddress.IPv6Address


class Refused(httpx.ConnectError):
    """Nothing was sent: the host does not resolve (`UNRESOLVED`), or one of
    its addresses is not one this server may connect to (`NOT_PUBLIC`). An
    httpx.ConnectError, so code that knows only httpx still sees a failure."""

    def __init__(self, host: str, reason: str) -> None:
        super().__init__(f"{host} {reason}")
        self.host = host
        self.reason = reason


def _parse(address: object) -> Address | None:
    """The address to judge: an IPv6 form of an IPv4 address is that IPv4
    address (a zone id is dropped)."""
    try:
        ip = ipaddress.ip_address(str(address).split("%", 1)[0])
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped
        if ip in NAT64:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if ip.sixtofour is not None:
            return ip.sixtofour
    return ip


def is_public(address: object) -> bool:
    """A global unicast address: the only kind a user-chosen URL may reach."""
    ip = _parse(address)
    if ip is None:
        return False
    if isinstance(ip, ipaddress.IPv4Address) and ip in SHARED:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.is_site_local:
        return False
    return ip.is_global and not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def allowed(address: object, *, private: bool = False, loopback: bool = False) -> bool:
    """`is_public`; with `private`, also loopback and private-network unicast
    (never link-local, multicast, reserved or unspecified); with `loopback`,
    also loopback."""
    if is_public(address):
        return True
    ip = _parse(address)
    if ip is None:
        return False
    if ip.is_loopback:
        return private or loopback
    if not private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    return ip.is_private or (isinstance(ip, ipaddress.IPv4Address) and ip in SHARED)


def resolve(host: str) -> list[str]:
    """Every address `host` resolves to, in the resolver's order (patched in tests)."""
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def check_host(host: str, *, private: bool = False, loopback_names: Iterable[str] = ()) -> list[str]:
    """Resolve `host` once: its addresses when every one is `allowed`, else
    Refused. `loopback_names` may reach loopback (WEBHOOKS_ALLOW_HTTP_LOCAL)."""
    try:
        addresses = resolve(host)
    except (OSError, UnicodeError, ValueError):
        raise Refused(host, UNRESOLVED) from None
    if not addresses:
        raise Refused(host, UNRESOLVED)
    loopback = host.lower() in {name.lower() for name in loopback_names}
    if not all(allowed(a, private=private, loopback=loopback) for a in addresses):
        raise Refused(host, NOT_PUBLIC)
    return addresses


def public_host(host: str) -> bool:
    """True when every address `host` resolves to is public (one lookup)."""
    try:
        check_host(host)
    except Refused:
        return False
    return True


def connect(
    address: str,
    port: int,
    timeout: float | None = None,
    local_address: str | None = None,
    socket_options: Iterable | None = None,
) -> httpcore.NetworkStream:
    """A TCP connection to an address that was checked: a literal address,
    so no lookup happens here (patched in tests)."""
    return httpcore.SyncBackend().connect_tcp(
        address, port, timeout=timeout, local_address=local_address, socket_options=socket_options
    )


def tls_context() -> ssl.SSLContext:
    """httpx's default: the certifi CA bundle, the host name checked (patched in tests)."""
    return httpx.create_ssl_context()


class _PinnedBackend(httpcore.NetworkBackend):
    """Lookup, check and connect in one step, for every connection the pool opens."""

    def __init__(self, private: bool, loopback_names: tuple[str, ...]) -> None:
        self.private = private
        self.loopback_names = loopback_names

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable | None = None,
    ) -> httpcore.NetworkStream:
        addresses = check_host(host, private=self.private, loopback_names=self.loopback_names)
        failure: Exception | None = None
        for address in addresses[:MAX_ADDRESSES]:
            try:
                return connect(address, port, timeout, local_address, socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                failure = exc
        raise failure  # type: ignore[misc]  # at least one address was tried

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class PinnedTransport(httpx.HTTPTransport):
    """httpx's transport over a pool whose connections go through
    `_PinnedBackend`. HTTPTransport takes no network backend, so the pool is
    built here; its request handling and closing only use `self._pool`. No
    proxy: a proxy would resolve the name itself."""

    def __init__(self, *, private: bool = False, loopback_names: Iterable[str] = (), retries: int = 0) -> None:
        self._pool = httpcore.ConnectionPool(
            ssl_context=tls_context(),
            retries=retries,
            network_backend=_PinnedBackend(private, tuple(loopback_names)),
        )


def client(
    *, timeout: float, private: bool = False, loopback_names: Iterable[str] = (), retries: int = 0
) -> httpx.Client:
    """An httpx.Client for a URL someone else chose: pinned, checked
    connections; no redirects followed; no proxy or .netrc from the environment.
    `private` lets loopback and private networks through (local trials only)."""
    return httpx.Client(
        transport=PinnedTransport(private=private, loopback_names=loopback_names, retries=retries),
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    )
