"""PF3c: an OpenID Connect provider's endpoints must be https, like its issuer.

discover() refuses a discovery document whose authorization_endpoint,
token_endpoint or jwks_uri is not https (401 sso_failed naming the field):
nothing is cached, and neither the token endpoint nor the keys are called. The
one exception is the issuer's: plain http to this computer (127.0.0.1,
localhost, ::1) while private issuers are allowed (the local mock provider).

The public-issuer tests use test_sso.py's `idp` fixture (the mock provider as
the server's HTTP client, idp.test resolving to a public address); the local
ones run tests/mock_oidc.py on a loopback port over PF14b's pinned connection,
as the human test does.
"""

import ast
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.config import get_settings
from app.net import outbound
from app.sso import oidc

from . import mock_oidc
from .org_helpers import _clean_mail_and_caches, envelope  # noqa: F401  (autouse: SSO caches)
from .test_pf14b_outbound import _put_oidc, local_idp, txt  # noqa: F401  (local_idp, txt: fixtures)
from .test_sso import DOMAIN, _authorize, _oidc, _start, _verified_org, idp  # noqa: F401  (idp: a fixture)

ENDPOINTS = ("authorization_endpoint", "token_endpoint", "jwks_uri")
DISCOVERY = "GET /.well-known/openid-configuration"
SSO_CODE = Path(__file__).resolve().parents[1] / "app"


def _start_json(client, email: str):
    return client.get("/auth/sso/start", params={"email": email, "format": "json"})


def _token_or_keys(calls: list[str]) -> list[str]:
    return [c for c in calls if c in ("POST /token", "GET /jwks")]


def _sign_in(client, issuer: str, email: str) -> str:
    """The whole browser round trip through a provider on a loopback port: the
    site's redirect target after the callback."""
    start = client.get("/auth/sso/start", params={"email": email}, follow_redirects=False)
    assert start.status_code == 302, start.text
    location = start.headers["location"]
    assert location.startswith(f"{issuer}/authorize?")
    with httpx.Client() as browser:  # the person's browser at the provider
        back = browser.get(location, follow_redirects=False)
    assert back.status_code == 302, back.text
    q = {k: v[0] for k, v in parse_qs(urlsplit(back.headers["location"]).query).items()}
    done = client.get("/auth/sso/oidc/callback", params=q, follow_redirects=False)
    assert done.status_code == 302, done.text
    return done.headers["location"]


# --- a public issuer that names an http endpoint ------------------------------------------------


def _http_endpoint_refused(client, idp, monkeypatch, field: str) -> None:
    """https://idp.test (public) signs a person in while its document gives
    https endpoints. A sign-in is started, then the document names `field` as
    http://idp.test/… and the hour's cache runs out: the next start and the
    pending callback both answer 401 sso_failed naming the field, nothing is
    cached, and the provider sees no token or keys request."""
    h, org = _verified_org(client, idp)
    _oidc(client, h, org)
    pending = _authorize(_start(client, f"c@{DOMAIN}"))

    monkeypatch.setattr(mock_oidc, "HTTP_HOST", "idp.test")
    monkeypatch.setattr(mock_oidc, "HTTP_ENDPOINTS", {field})
    oidc.clear_caches()
    mock_oidc.CALLS.clear()

    body = envelope(_start_json(client, f"c@{DOMAIN}"), 401, "sso_failed")
    assert field in body["detail"] and "https" in body["detail"], body
    page = client.get("/auth/sso/start", params={"email": f"c@{DOMAIN}"}, headers={"Accept": "text/html"})
    assert page.status_code == 401 and "Single sign-on did not finish" in page.text and field in page.text
    body = envelope(client.get("/auth/sso/oidc/callback", params=pending, follow_redirects=False), 401, "sso_failed")
    assert field in body["detail"], body

    assert oidc._discovery == {} and oidc._jwks == {}
    assert mock_oidc.CALLS == [DISCOVERY] * 3
    assert _token_or_keys(mock_oidc.CALLS) == []


def test_discovery_refuses_http_token_endpoint(client, idp, monkeypatch):
    _http_endpoint_refused(client, idp, monkeypatch, "token_endpoint")


def test_discovery_refuses_http_jwks_uri(client, idp, monkeypatch):
    _http_endpoint_refused(client, idp, monkeypatch, "jwks_uri")


def test_discovery_refuses_http_authorization_endpoint(client, idp, monkeypatch):
    _http_endpoint_refused(client, idp, monkeypatch, "authorization_endpoint")


# --- the local mock provider ----------------------------------------------------------------------


def test_local_mock_provider_still_signs_in(client, txt, local_idp, monkeypatch):
    """API_URL on loopback (a local trial): the mock provider at
    http://127.0.0.1:<port>, whose endpoints are http on 127.0.0.1 too, signs
    a person in end to end, its token endpoint and keys called over http."""
    settings = get_settings()
    monkeypatch.setattr(settings, "api_url", "http://127.0.0.1:8000")
    assert oidc.private_issuers_allowed() and not settings.sso_allow_private_issuers
    assert local_idp.startswith("http://127.0.0.1:")
    h, org = _verified_org(client, txt)
    assert _put_oidc(client, h, org, local_idp).status_code == 200

    landed = _sign_in(client, local_idp, f"c@{DOMAIN}")
    assert landed.startswith("https://truebex.com/login/sso/#") and "token=" in landed
    meta = oidc.discover(local_idp)
    assert [meta[f] for f in ENDPOINTS] == [f"{local_idp}/authorize", f"{local_idp}/token", f"{local_idp}/jwks"]
    assert _token_or_keys(mock_oidc.CALLS) == ["POST /token", "GET /jwks"]


def test_private_issuers_switch_keeps_http_local_only(client, txt, local_idp, monkeypatch):
    """SSO_ALLOW_PRIVATE_ISSUERS on (the API not on loopback): the loopback
    issuer is accepted, but an http endpoint on a host that is not this
    computer by name is still refused, whether a public name that answers
    127.0.0.1 or a private-network address the pinned client would let
    through; http to localhost stays allowed."""
    settings = get_settings()
    monkeypatch.setattr(settings, "sso_allow_private_issuers", True)
    assert urlsplit(settings.api_url).hostname == "testserver"
    assert oidc.private_issuers_allowed()
    real_resolve = outbound.resolve
    monkeypatch.setattr(
        outbound, "resolve", lambda host: ["127.0.0.1"] if host in ("localtest.me", "localhost") else real_resolve(host)
    )
    h, org = _verified_org(client, txt)
    assert _put_oidc(client, h, org, local_idp).status_code == 200

    for host in ("localtest.me", "192.168.1.20"):
        monkeypatch.setattr(mock_oidc, "HTTP_HOST", host)
        for field in ENDPOINTS:
            monkeypatch.setattr(mock_oidc, "HTTP_ENDPOINTS", {field})
            oidc.clear_caches()
            mock_oidc.CALLS.clear()
            body = envelope(_start_json(client, f"c@{DOMAIN}"), 401, "sso_failed")
            assert field in body["detail"], (host, body)
            assert mock_oidc.CALLS == [DISCOVERY] and oidc._discovery == {}, (host, field)

    # Plain http to this computer by name is the exception, as for the issuer.
    monkeypatch.setattr(mock_oidc, "HTTP_HOST", "localhost")
    monkeypatch.setattr(mock_oidc, "HTTP_ENDPOINTS", {"token_endpoint", "jwks_uri"})
    oidc.clear_caches()
    mock_oidc.CALLS.clear()
    assert "token=" in _sign_in(client, local_idp, f"c@{DOMAIN}")
    port = urlsplit(local_idp).port
    assert oidc.discover(local_idp)["token_endpoint"] == f"http://localhost:{port}/token"
    assert _token_or_keys(mock_oidc.CALLS) == ["POST /token", "GET /jwks"]


# --- the rule and where it applies ----------------------------------------------------------------


def test_endpoint_rule_matches_the_issuer_exception(monkeypatch):
    """https on any host; plain http only to 127.0.0.1, localhost or ::1 and
    only while private issuers are allowed; anything else refused."""
    settings = get_settings()
    always = ["https://idp.example.com/token", "HTTPS://IdP.Example.com:8443/keys?x=1", "https://127.0.0.1/jwks"]
    local_http = ["http://127.0.0.1:8098/token", "http://localhost/jwks", "http://LOCALHOST:8098/authorize",
                  "http://[::1]:8098/token"]
    never = ["http://idp.example.com/token", "http://localtest.me:8098/token", "http://192.168.1.20/jwks",
             "http://127.0.0.1.nip.io/token", "ftp://idp.example.com/keys", "//idp.example.com/token", "/token",
             "https:///token", "", "https://[::1/token", "javascript:alert(1)"]

    monkeypatch.setattr(settings, "api_url", "https://api.example.com")
    monkeypatch.setattr(settings, "sso_allow_private_issuers", False)
    assert not oidc.private_issuers_allowed()
    for url in always:
        assert oidc.endpoint_is_acceptable(url), url
    for url in local_http + never:
        assert not oidc.endpoint_is_acceptable(url), url

    for api_url, switch in (("http://127.0.0.1:8000", False), ("https://api.example.com", True)):
        monkeypatch.setattr(settings, "api_url", api_url)
        monkeypatch.setattr(settings, "sso_allow_private_issuers", switch)
        assert oidc.private_issuers_allowed()
        for url in always + local_http:
            assert oidc.endpoint_is_acceptable(url), (api_url, url)
        for url in never:
            assert not oidc.endpoint_is_acceptable(url), (api_url, url)


def _document_keys(path: Path) -> set[str]:
    """String keys read from a mapping in `path`: x["key"] and x.get("key")."""
    keys: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            keys.add(node.slice.value)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
              and node.args and isinstance(node.args[0], ast.Constant)):
            keys.add(node.args[0].value)
    return {k for k in keys if isinstance(k, str)}


def test_every_endpoint_the_code_calls_is_checked():
    """Every URL the SSO code reads from the discovery document is one
    discover() checks: today the three in oidc.ENDPOINTS. userinfo_endpoint
    and end_session_endpoint are not called; a change that starts calling
    them (or another endpoint) has to add it to oidc.ENDPOINTS first."""
    assert oidc.ENDPOINTS == ENDPOINTS
    files = sorted((SSO_CODE / "sso").glob("*.py")) + [SSO_CODE / "routers" / "sso.py"]
    used = set().union(*(_document_keys(f) for f in files))
    assert {k for k in used if k.endswith(("_endpoint", "_uri", "_url"))} == set(ENDPOINTS), used
    assert not {"userinfo_endpoint", "end_session_endpoint"} & used


@pytest.mark.parametrize("field", ENDPOINTS)
def test_mock_switch_names_an_http_endpoint(field, monkeypatch):
    """tests/mock_oidc.py's MOCK_OIDC_HTTP_ENDPOINT (the human test's switch):
    the named field is http on localtest.me at the mock's port, the others
    stay on the issuer; an unknown name stops the mock from starting."""
    from fastapi.testclient import TestClient

    mock_oidc.reset()
    monkeypatch.setattr(mock_oidc, "HTTP_ENDPOINTS", mock_oidc.endpoint_list(f" {field} ,"))
    with TestClient(mock_oidc.app, base_url="http://127.0.0.1:8098") as provider:
        doc = provider.get("/.well-known/openid-configuration").json()
    assert mock_oidc.CALLS == [DISCOVERY]
    mock_oidc.reset()
    assert doc["issuer"] == "http://127.0.0.1:8098"
    assert doc[field] == f"http://localtest.me:8098{mock_oidc.ENDPOINT_PATHS[field]}"
    for other in set(ENDPOINTS) - {field}:
        assert doc[other] == f"http://127.0.0.1:8098{mock_oidc.ENDPOINT_PATHS[other]}"
    assert mock_oidc.endpoint_list("") == set()
    assert mock_oidc.endpoint_list("token_endpoint,jwks_uri") == {"token_endpoint", "jwks_uri"}
    with pytest.raises(ValueError, match="userinfo_endpoint"):
        mock_oidc.endpoint_list("userinfo_endpoint")
