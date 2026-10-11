"""PF14b: outbound requests to an address someone else chose (feed and media
URLs, webhook endpoints, OpenID Connect issuers) connect only to the public
address they were checked against, with no second lookup, and TLS still
verifies the certificate for the host name.

No real network: `FakeNet` answers DNS from a table (`outbound.resolve`), takes
the connections the module would open (`outbound.connect`) to an in-process
TLS server whose certificate names the test hosts, and trusts that server's
test CA (`outbound.tls_context`). The local OpenID Connect provider runs on a
loopback port, as in the human test.
"""

import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import httpcore
import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.market import media
from app.net import outbound
from app.sso import domains, oidc
from app.sso.models import SsoConnection
from app.supplier import feeds
from app.supplier.models import FeedSource
from app.webhooks.models import WebhookDelivery

from . import mock_oidc
from .conftest import signup
from .org_helpers import _clean_mail_and_caches  # noqa: F401  (autouse: SSO caches)
from .pf12_helpers import kh, make_key
from .supplier_helpers import FEED_CSV, key_headers, no_internet, supplier_key, verified
from .test_pf12_webhooks import hook, run
from .test_sso import DOMAIN, _verified_org

PUBLIC = "93.184.216.34"
PUBLIC_2 = "93.184.216.40"
# Names on the test server's certificate (other.example.net is not).
NAMES = [
    "public.example.com", "two.example.com", "cdn.example.com", "img.example.com", "feeds.example.com",
    "hooks.example.com", "idp.example.com",
]
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


# --- a test CA, a certificate for NAMES, and the network --------------------------------------


@pytest.fixture(scope="module")
def tls(tmp_path_factory):
    folder = tmp_path_factory.mktemp("pf14b-tls")
    now = datetime.now(timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PF14b test CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(hours=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    leaf = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, NAMES[0])]))
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(hours=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in NAMES]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    pem = serialization.Encoding.PEM
    (folder / "ca.pem").write_bytes(ca.public_bytes(pem))
    (folder / "leaf.pem").write_bytes(leaf.public_bytes(pem))
    (folder / "leaf.key").write_bytes(
        key.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    return folder


class FakeNet:
    """DNS and the internet as the outbound module sees them.

    `dns[host]` is a list of answers: lookup n of that host gets answer n (the
    last one from then on), so `[[public], [private]]` is a name that rebinds.
    `routes[host]` answers a request: (method, path, headers, body) →
    (status, headers, body). Servers listen on the addresses in `servers`."""

    def __init__(self, monkeypatch, tls_dir) -> None:
        self.dns: dict[str, list[list[str]]] = {}
        self.routes: dict = {}
        self.servers = {PUBLIC, PUBLIC_2}
        self.lookups: list[str] = []
        self.dialled: list[tuple[str, int]] = []
        self.sni: list[str | None] = []
        self.requests: list[dict] = []
        self._server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._server_tls.load_cert_chain(tls_dir / "leaf.pem", tls_dir / "leaf.key")
        self._server_tls.sni_callback = lambda sock, name, ctx: self.sni.append(name)
        self._ca = str(tls_dir / "ca.pem")
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._port = self._listener.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()
        monkeypatch.setattr(outbound, "resolve", self.resolve)
        monkeypatch.setattr(outbound, "connect", self.connect)
        monkeypatch.setattr(outbound, "tls_context", lambda: ssl.create_default_context(cafile=self._ca))

    def close(self) -> None:
        self._listener.close()

    # what the module calls
    def resolve(self, host: str) -> list[str]:
        n = self.lookups.count(host)
        self.lookups.append(host)
        try:
            socket.inet_pton(socket.AF_INET6 if ":" in host else socket.AF_INET, host)
            return [host]  # an address resolves to itself, as getaddrinfo does
        except OSError:
            pass
        if host not in self.dns:
            raise socket.gaierror(socket.EAI_NONAME, "no such host")
        answers = self.dns[host]
        return answers[min(n, len(answers) - 1)]

    def connect(self, address, port, timeout=None, local_address=None, socket_options=None):
        self.dialled.append((address, port))
        if address not in self.servers:
            raise httpcore.ConnectError(f"nothing listens on {address} in these tests")
        return httpcore.SyncBackend().connect_tcp("127.0.0.1", self._port, timeout=timeout)

    # the server
    def _accept(self) -> None:
        while True:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        conn.settimeout(10)
        try:
            with self._server_tls.wrap_socket(conn, server_side=True) as s:
                data = b""
                while b"\r\n\r\n" not in data:
                    chunk = s.recv(65536)
                    if not chunk:
                        return
                    data += chunk
                head, _, body = data.partition(b"\r\n\r\n")
                lines = head.decode("latin-1").split("\r\n")
                method, path, _ = lines[0].split(" ", 2)
                headers = {k.strip().lower(): v.strip() for k, v in (ln.split(":", 1) for ln in lines[1:])}
                while len(body) < int(headers.get("content-length", "0")):
                    body += s.recv(65536)
                host = headers.get("host", "").split(":")[0]
                self.requests.append({"host": host, "method": method, "path": path, "headers": headers, "body": body})
                route = self.routes.get(host, lambda *a: (404, {}, b""))
                status, extra, payload = route(method, path, headers, body)
                out = f"HTTP/1.1 {status} X\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n"
                out += "".join(f"{k}: {v}\r\n" for k, v in extra.items())
                s.sendall(out.encode("latin-1") + b"\r\n" + payload)
        except (OSError, ssl.SSLError, ValueError):
            conn.close()


@pytest.fixture()
def net(monkeypatch, tls):
    n = FakeNet(monkeypatch, tls)
    yield n
    n.close()


def ok(body: bytes = b"ok", **headers):
    return lambda *a: (200, headers, body)


# --- the module ---------------------------------------------------------------------------------

REFUSED = [
    # loopback
    "127.0.0.1", "127.8.9.10", "::1",
    # private networks (RFC 1918, unique local)
    "10.0.0.7", "172.16.0.1", "192.168.1.20", "fc00::1", "fd12:3456::1",
    # link-local (the cloud metadata address among them)
    "169.254.169.254", "fe80::1",
    # multicast (Python counts some of it as global)
    "224.0.0.1", "239.255.255.250", "ff02::1", "ff0e::1",
    # reserved, broadcast, unspecified
    "240.0.0.1", "255.255.255.255", "0.0.0.0", "::", "::10.0.0.1",
    # shared address space (RFC 6598), which Python does not call private
    "100.64.0.1", "100.127.255.254",
    # documentation, benchmarking, IETF protocol assignments
    "192.0.2.1", "198.18.0.1", "192.0.0.8", "2001:db8::1",
    # IPv6 site-local (deprecated; Python counts it as global)
    "fec0::1",
    # IPv4-mapped, NAT64 (well-known and local-use) and 6to4 forms of a non-global IPv4
    "::ffff:127.0.0.1", "::ffff:10.0.0.7", "::ffff:169.254.169.254", "::ffff:100.64.0.1",
    "64:ff9b::7f00:1", "64:ff9b::a00:7", "64:ff9b::a9fe:a9fe", "64:ff9b::6440:1", "64:ff9b:1::a00:7",
    "2002:7f00:1::1", "2002:a00:7::1", "2002:a9fe:a9fe::1", "2002:6440:1::1",
    # Teredo
    "2001:0:4136:e378:8000:63bf:3fff:fdd2",
]
ALLOWED = [
    PUBLIC, "1.1.1.1", "2606:4700::1111", "2a00:1450:4009:81f::200e",
    "::ffff:93.184.216.34", "64:ff9b::5db8:d822", "2002:5db8:d822::1",
]


def test_outbound_refuses_non_global_addresses(net):
    for address in REFUSED:
        assert outbound.is_public(address) is False, address
    for address in ALLOWED:
        assert outbound.is_public(address) is True, address
    assert outbound.is_public("not an address") is False
    assert outbound.is_public("fe80::1%12") is False  # a zone id is ignored, the address still judged

    # Through a client: every refused address, as a name's answer, sends nothing.
    for i, address in enumerate(REFUSED):
        host = f"h{i}.example.com"
        net.dns[host] = [[address]]
        with outbound.client(timeout=5) as c, pytest.raises(outbound.Refused) as exc:
            c.get(f"https://{host}/")
        assert exc.value.reason == outbound.NOT_PUBLIC and exc.value.host == host
    # One private answer among public ones is enough; so is a name that does not resolve.
    net.dns["mixed.example.com"] = [[PUBLIC, "10.0.0.7"]]
    with outbound.client(timeout=5) as c:
        with pytest.raises(outbound.Refused):
            c.get("https://mixed.example.com/")
        with pytest.raises(outbound.Refused) as exc:
            c.get("https://nowhere.example.com/")
        assert exc.value.reason == outbound.UNRESOLVED
        # An address in the URL is checked the same way.
        for url in ("https://127.0.0.1/", "https://[::1]/", "http://169.254.169.254/latest/meta-data/", "https://[::ffff:10.0.0.7]/"):
            with pytest.raises(outbound.Refused):
                c.get(url)
    assert net.dialled == []
    # A Refused is an httpx.ConnectError: code that only knows httpx still treats it as a failure.
    assert issubclass(outbound.Refused, httpx.ConnectError)

    # Local trials opt in to loopback and private networks, never link-local, multicast or unspecified.
    for address in ("127.0.0.1", "::1", "10.0.0.7", "192.168.1.20", "fd12:3456::1", "100.64.0.1", "::ffff:127.0.0.1"):
        assert outbound.allowed(address, private=True), address
    for address in ("169.254.169.254", "fe80::1", "224.0.0.1", "ff02::1", "0.0.0.0", "::", "255.255.255.255"):
        assert not outbound.allowed(address, private=True), address
    assert outbound.check_host("10.0.0.7", private=True) == ["10.0.0.7"]
    # Loopback by name only: localhost may reach loopback, nothing else may.
    net.dns["localhost"] = [["::1", "127.0.0.1"]]
    assert outbound.check_host("localhost", loopback_names=("localhost",)) == ["::1", "127.0.0.1"]
    with pytest.raises(outbound.Refused):
        outbound.check_host("10.0.0.7", loopback_names=("10.0.0.7",))
    assert outbound.public_host(PUBLIC) and not outbound.public_host("localhost")


def test_outbound_connects_to_the_checked_address(net):
    """The first answer is public, every later one 127.0.0.1: the request goes
    to the public address, after exactly one lookup."""
    net.dns["public.example.com"] = [[PUBLIC], ["127.0.0.1"]]
    net.routes["public.example.com"] = ok(b"hello")
    with outbound.client(timeout=5) as c:
        res = c.get("https://public.example.com/a")
    assert res.status_code == 200 and res.content == b"hello"
    assert net.lookups == ["public.example.com"]
    assert net.dialled == [(PUBLIC, 443)]
    # The next connection looks up again, gets 127.0.0.1 and never dials it.
    with outbound.client(timeout=5) as c, pytest.raises(outbound.Refused):
        c.get("https://public.example.com/b")
    assert net.lookups == ["public.example.com", "public.example.com"]
    assert net.dialled == [(PUBLIC, 443)] and len(net.requests) == 1
    # Several public addresses: the first that answers takes the connection.
    net.dns["two.example.com"] = [["93.184.216.99", PUBLIC_2]]
    net.routes["two.example.com"] = ok()
    net.servers.discard("93.184.216.99")
    with outbound.client(timeout=5) as c:
        assert c.get("https://two.example.com/").status_code == 200
    assert net.dialled[-2:] == [("93.184.216.99", 443), (PUBLIC_2, 443)]


def test_tls_name_kept(net):
    """The connection goes to the address; SNI, the certificate check and the
    Host header use the name."""
    net.dns["public.example.com"] = [[PUBLIC]]
    net.dns["other.example.net"] = [[PUBLIC]]
    net.routes["public.example.com"] = ok()
    with outbound.client(timeout=5) as c:
        assert c.get("https://public.example.com/x?y=1").status_code == 200
    assert net.dialled == [(PUBLIC, 443)]
    assert net.sni == ["public.example.com"]
    assert net.requests[0]["headers"]["host"] == "public.example.com" and net.requests[0]["path"] == "/x?y=1"
    # A name the certificate does not carry fails verification, though the address is the same.
    with outbound.client(timeout=5) as c, pytest.raises(httpx.ConnectError) as exc:
        c.get("https://other.example.net/")
    assert not isinstance(exc.value, outbound.Refused)
    assert "certificate" in str(exc.value).lower() or "hostname" in str(exc.value).lower()
    assert len(net.requests) == 1 and net.sni[-1] == "other.example.net"
    # A port in the URL is kept, and travels in the Host header.
    with outbound.client(timeout=5) as c:
        assert c.get("https://public.example.com:8443/").status_code == 200
    assert net.dialled[-1] == (PUBLIC, 8443) and net.requests[-1]["headers"]["host"] == "public.example.com:8443"


# --- the callers --------------------------------------------------------------------------------


def test_media_redirect_to_private_refused(net):
    """Image and geometry URLs: every redirect hop goes through the pinned
    connection; a hop to a private address is refused before it is dialled."""
    net.dns["cdn.example.com"] = [[PUBLIC]]
    net.dns["img.example.com"] = [[PUBLIC_2]]
    net.dns["inside.example.com"] = [["10.0.0.7"]]
    net.dns["rebind.example.com"] = [["192.168.1.20"]]
    net.routes["img.example.com"] = ok(PNG)
    redirects = {"/a.png": "https://img.example.com/a.png", "/b.png": "https://inside.example.com/b.png",
                 "/c.png": "https://169.254.169.254/latest/meta-data/", "/d.png": "http://img.example.com/d.png"}
    net.routes["cdn.example.com"] = lambda m, path, h, b: (302, {"Location": redirects[path]}, b"")
    fetch = media.HttpFetcher()
    assert fetch.get("https://cdn.example.com/a.png", 1000) == PNG  # a public hop is followed
    assert net.dialled == [(PUBLIC, 443), (PUBLIC_2, 443)]
    for path in ("/b.png", "/c.png"):
        with pytest.raises(media.MediaError) as exc:
            fetch.get(f"https://cdn.example.com{path}", 1000)
        assert (exc.value.code, str(exc.value)) == ("bad_url", "the host is not a public internet address"), path
    with pytest.raises(media.MediaError) as exc:
        fetch.get("https://cdn.example.com/d.png", 1000)
    assert exc.value.code == "bad_url"  # https only, on every hop
    # A name that resolves to a private address from the start, and the size cap.
    with pytest.raises(media.MediaError) as exc:
        fetch.get("https://rebind.example.com/e.png", 1000)
    assert exc.value.code == "bad_url"
    with pytest.raises(media.MediaError) as exc:
        fetch.get("https://img.example.com/a.png", 10)
    assert exc.value.code == "too_large"
    assert {a for a, _ in net.dialled} == {PUBLIC, PUBLIC_2}
    # The check the importer and the feed registration use is the module's (one lookup, the same rules).
    assert media._public_address("cdn.example.com") and not media._public_address("inside.example.com")
    assert not media._public_address("100.64.0.1") and not media._public_address("::ffff:10.0.0.7")


def test_feed_pull_rebinding_refused(client, net, monkeypatch):
    """A feed URL checked at registration that later resolves to 127.0.0.1:
    the daily pull fails without connecting, and says why."""
    no_internet(monkeypatch)
    h, sid = verified(client)
    key = supplier_key(client, h)
    net.dns["feeds.example.com"] = [[PUBLIC], [PUBLIC], ["127.0.0.1"]]
    net.routes["feeds.example.com"] = ok(FEED_CSV, ETag='"v1"')

    def put(url):
        return client.put("/market/feeds/source", json={"url": url, "format": "csv", "mode": "upsert"}, headers=key_headers(key))

    net.dns["inside.example.com"] = [["10.0.0.7"]]
    assert put("https://inside.example.com/feed.csv").status_code == 422
    res = put("https://feeds.example.com/feed.csv")  # lookup 1: public
    assert res.status_code == 200, res.text
    nxt = datetime.fromisoformat(res.json()["next_pull_at"].replace("Z", "+00:00"))
    with SessionLocal() as db:
        # Lookup 2: public, so the pull reads the file from the checked address.
        assert feeds.pull_due(db, nxt + timedelta(seconds=5)) == 1
        row = db.get(FeedSource, sid)
        assert row.last_error is None and row.etag == '"v1"', row.last_error
        assert net.dialled == [(PUBLIC, 443)] and net.sni == ["feeds.example.com"]
        # Lookup 3 rebinds to 127.0.0.1: nothing is dialled, the pull fails with the usual reason.
        assert feeds.pull_due(db, nxt + timedelta(days=1, seconds=5)) == 1
        row = db.get(FeedSource, sid)
        assert (row.last_status, row.last_error) == ("failed", "the host is not a public internet address")
    assert net.dialled == [(PUBLIC, 443)] and len(net.requests) == 1
    assert net.lookups.count("feeds.example.com") == 3
    # A redirect to a private address is refused the same way.
    net.dns["feeds.example.com"] = [[PUBLIC]]
    net.routes["feeds.example.com"] = lambda *a: (301, {"Location": "https://inside.example.com/feed.csv"}, b"")
    with pytest.raises(feeds.PullError, match="not a public internet address"):
        feeds.HttpFeedFetcher().get("https://feeds.example.com/feed.csv", None)
    assert "10.0.0.7" not in {a for a, _ in net.dialled}


def test_webhook_delivery_rebinding_refused(client, net):
    """A webhook endpoint checked when saved, delivered to over the pinned
    connection; when its name rebinds to a private address the attempt is
    recorded as refused and no request reaches that address."""
    net.dns["hooks.example.com"] = [[PUBLIC]]
    net.routes["hooks.example.com"] = lambda *a: (204, {}, b"")
    key = make_key(client, signup(client), ["webhooks:manage"])
    made = hook(client, key, ["job.failed"], url="https://hooks.example.com/truebex")
    first = client.post(f"/v1/webhooks/{made['endpoint_id']}/test", headers=kh(key)).json()
    assert run() == 1
    assert net.dialled == [(PUBLIC, 443)] and net.sni == ["hooks.example.com"]
    got = net.requests[0]
    assert (got["method"], got["path"], got["headers"]["host"]) == ("POST", "/truebex", "hooks.example.com")
    assert got["headers"]["webhook-signature"].startswith("v1,") and b"webhook.test" in got["body"]

    net.dns["hooks.example.com"] = [["192.168.1.20"]]  # the name now points inside
    second = client.post(f"/v1/webhooks/{made['endpoint_id']}/test", headers=kh(key)).json()
    run()
    with SessionLocal() as db:
        assert db.get(WebhookDelivery, first["delivery_id"]).status == "succeeded"
        row = db.get(WebhookDelivery, second["delivery_id"])
        assert row.status == "failed" and row.response_code is None
        assert row.error == "refused: a host that resolves to public addresses only"
    assert net.dialled == [(PUBLIC, 443)] and len(net.requests) == 1
    # A name that stops resolving: refused with the save-time wording.
    net.dns.pop("hooks.example.com")
    third = client.post(f"/v1/webhooks/{made['endpoint_id']}/test", headers=kh(key)).json()
    run()
    with SessionLocal() as db:
        assert db.get(WebhookDelivery, third["delivery_id"]).error == "refused: a host that resolves (hooks.example.com does not)"
    assert len(net.requests) == 1


# --- SSO ----------------------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def local_idp():
    """tests/mock_oidc.py on a loopback port (the human test's provider)."""
    import uvicorn

    mock_oidc.reset()
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(mock_oidc.app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started:
        assert time.time() < deadline, "the mock provider did not start"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)
    mock_oidc.reset()


@pytest.fixture()
def txt(monkeypatch):
    records: dict[str, list[str]] = {}
    monkeypatch.setattr(domains, "resolve_txt", lambda name: records.get(name, []))
    return records


def _put_oidc(client, h, org, issuer: str):
    body = {"kind": "oidc", "issuer": issuer, "client_id": mock_oidc.CLIENT_ID, "client_secret": mock_oidc.CLIENT_SECRET}
    return client.put(f"/orgs/{org['id']}/sso", json=body, headers=h)


def _issuer_refused(res) -> None:
    assert res.status_code == 422, res.text
    body = res.json()
    assert body["code"] == "validation_failed" and body["data"]["fields"][0]["field"] == "issuer"


def _start_json(client, email: str):
    return client.get("/auth/sso/start", params={"email": email, "format": "json"})


def test_sso_loopback_issuer_refused_in_production(client, txt, local_idp, net, monkeypatch):
    """With the API on a public address: loopback, private and unresolvable
    issuers are refused when saved (422 on `issuer`) and at sign-in
    (401 sso_failed), and the provider is never called."""
    settings = get_settings()
    assert urlsplit(settings.api_url).hostname == "testserver" and not settings.sso_allow_private_issuers
    assert not oidc.private_issuers_allowed()
    h, org = _verified_org(client, txt)
    net.dns["inside.example.com"] = [["10.0.0.7"]]
    net.dns["localhost"] = [["::1", "127.0.0.1"]]
    for issuer in (local_idp, "http://localhost:8098", "https://127.0.0.1", "https://localhost", "https://[::1]",
                   "https://inside.example.com", "https://nowhere.example.com", "http://idp.example.com"):
        res = _put_oidc(client, h, org, issuer)
        _issuer_refused(res)
        assert "public internet address" in res.json()["data"]["fields"][0]["message"], issuer
    # A public https issuer is accepted ...
    net.dns["idp.example.com"] = [[PUBLIC], ["10.0.0.9"]]
    assert _put_oidc(client, h, org, "https://idp.example.com").status_code == 200
    # ... and when its name later points at a private address, sign-in fails without connecting.
    envelope = _start_json(client, f"c@{DOMAIN}")
    assert envelope.status_code == 401 and envelope.json()["code"] == "sso_failed", envelope.text
    assert net.dialled == []

    # A loopback issuer saved while the API ran on this computer (or before PF14b):
    # the API on a public address refuses it at sign-in.
    monkeypatch.setattr(settings, "api_url", "http://127.0.0.1:8000")
    assert _put_oidc(client, h, org, local_idp).status_code == 200
    monkeypatch.setattr(settings, "api_url", "http://testserver")
    oidc.clear_caches()
    with SessionLocal() as db:
        assert db.scalar(select(SsoConnection.issuer).where(SsoConnection.org_id == org["id"])) == local_idp
    res = _start_json(client, f"c@{DOMAIN}")
    assert res.status_code == 401 and res.json()["code"] == "sso_failed"
    assert "public internet address" in res.json()["detail"]
    page = client.get("/auth/sso/start", params={"email": f"c@{DOMAIN}"}, headers={"Accept": "text/html"})
    assert page.status_code == 401 and "Single sign-on did not finish" in page.text
    assert net.dialled == [] and mock_oidc.SEEN == []


def test_sso_loopback_issuer_allowed_for_local_api(client, txt, local_idp, monkeypatch):
    """With the API on 127.0.0.1 (a local trial), the local mock provider on a
    loopback port is accepted and a person signs in through it, over the
    module's connections; so it is with SSO_ALLOW_PRIVATE_ISSUERS on a LAN address."""
    settings = get_settings()
    monkeypatch.setattr(settings, "api_url", "http://127.0.0.1:8000")
    assert oidc.private_issuers_allowed()
    h, org = _verified_org(client, txt)
    # Plain http only to this computer, even locally.
    res = _put_oidc(client, h, org, "http://192.168.1.20:8098")
    _issuer_refused(res)
    assert "http://127.0.0.1" in res.json()["data"]["fields"][0]["message"]
    assert _put_oidc(client, h, org, local_idp).status_code == 200

    def sign_in(email: str) -> str:
        start = client.get("/auth/sso/start", params={"email": email}, follow_redirects=False)
        assert start.status_code == 302, start.text
        location = start.headers["location"]
        assert location.startswith(f"{local_idp}/authorize?")
        with httpx.Client() as browser:  # the person's browser at the provider
            back = browser.get(location, follow_redirects=False)
        assert back.status_code == 302
        q = {k: v[0] for k, v in parse_qs(urlsplit(back.headers["location"]).query).items()}
        done = client.get("/auth/sso/oidc/callback", params=q, follow_redirects=False)
        assert done.status_code == 302, done.text
        return done.headers["location"]

    landed = sign_in(f"c@{DOMAIN}")
    assert landed.startswith("https://truebex.com/login/sso/#") and "token=" in landed

    # A LAN address for the API refuses the loopback issuer, unless the setting is on.
    monkeypatch.setattr(settings, "api_url", "http://192.168.1.5:8000")
    oidc.clear_caches()
    assert not oidc.private_issuers_allowed()
    assert _start_json(client, f"d@{DOMAIN}").json()["code"] == "sso_failed"
    monkeypatch.setattr(settings, "sso_allow_private_issuers", True)
    assert oidc.private_issuers_allowed()
    assert _put_oidc(client, h, org, local_idp).status_code == 200
    assert "token=" in sign_in(f"d@{DOMAIN}")


def test_try_outbound_script(net, capsys):
    """scripts/try_outbound.py (the human test's probe) shows the lookup, the
    verdict on each address and the address it dials."""
    from scripts import try_outbound

    net.dns["public.example.com"] = [[PUBLIC]]
    net.dns["inside.example.com"] = [["10.0.0.7"]]
    net.routes["public.example.com"] = ok()
    assert try_outbound.main(["https://public.example.com/"]) == 0
    out = capsys.readouterr().out
    assert f"{PUBLIC}: public" in out and f"connect {PUBLIC} port 443" in out
    assert "HTTP 200, Host: public.example.com, certificate checked for public.example.com" in out
    assert try_outbound.main(["https://inside.example.com/"]) == 2
    out = capsys.readouterr().out
    assert "10.0.0.7: NOT public" in out and "nothing was sent" in out and "connect" not in out
    assert try_outbound.main(["--private", "https://inside.example.com/"]) == 1  # allowed, but nothing listens there
    assert "10.0.0.7: not public, allowed by --private" in capsys.readouterr().out
    assert outbound.resolve == net.resolve and outbound.connect == net.connect  # put back
