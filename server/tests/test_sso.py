"""SSO for Enterprise organisations (PF3): verified domains, OIDC against
tests/mock_oidc.py, SAML 2.0 against tests/mock_saml_idp.py, just-in-time
membership and the "SSO required" policy with its break-glass code."""

import base64
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from lxml import etree
from sqlalchemy import select

from app import tasks
from app.config import get_settings
from app.database import SessionLocal
from app.routers import auth as auth_router
from app.sso import domains, oidc
from app.sso.models import SsoConnection, SsoRequest

from . import mock_oidc, mock_saml_idp
from .conftest import signup
from .org_helpers import _clean_mail_and_caches, envelope, make_org, me  # noqa: F401

DOMAIN = "northstudio.com"
# This API's public URL (conftest sets API_URL so signed /files URLs reach the TestClient).
API = get_settings().api_url.rstrip("/")
ISSUER = "https://idp.test"
SAML_SSO = "https://idp.test/saml/sso"


@pytest.fixture()
def idp(monkeypatch):
    """The mock OIDC provider as the server's HTTP client; TXT lookups answer from DNS."""
    mock_oidc.reset()
    monkeypatch.setattr(oidc, "http_client", lambda: TestClient(mock_oidc.app, base_url=ISSUER))
    dns: dict[str, list[str]] = {}
    monkeypatch.setattr(domains, "resolve_txt", lambda name: dns.get(name, []))
    yield dns
    mock_oidc.reset()


def _verified_org(client, idp, owner_email=f"owner@{DOMAIN}"):
    h = signup(client, owner_email)
    org = make_org(client, h)
    rec = client.post(f"/orgs/{org['id']}/domains", json={"domain": DOMAIN}, headers=h).json()["txt_record"]
    idp[rec["name"]] = [rec["value"]]
    assert client.post(f"/orgs/{org['id']}/domains/{DOMAIN}/verify", headers=h).status_code == 200
    return h, org


def _oidc(client, h, org, **extra):
    body = {"kind": "oidc", "issuer": ISSUER, "client_id": mock_oidc.CLIENT_ID,
            "client_secret": mock_oidc.CLIENT_SECRET, **extra}
    res = client.put(f"/orgs/{org['id']}/sso", json=body, headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def _saml(client, h, org, **extra):
    body = {"kind": "saml", "idp_metadata_xml": mock_saml_idp.metadata(SAML_SSO), **extra}
    res = client.put(f"/orgs/{org['id']}/sso", json=body, headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def _start(client, email, next_="/dashboard/organisation/"):
    res = client.get("/auth/sso/start", params={"email": email, "next": next_}, follow_redirects=False)
    assert res.status_code == 302, res.text
    return res.headers["location"]


def _authorize(location: str) -> dict:
    """Let the mock provider sign the person in; the callback's query."""
    with TestClient(mock_oidc.app, base_url=ISSUER) as idp_client:
        res = idp_client.get(location, follow_redirects=False)
    assert res.status_code == 302, res.text
    back = urlsplit(res.headers["location"])
    assert f"{back.scheme}://{back.netloc}{back.path}" == f"{API}/auth/sso/oidc/callback"
    return {k: v[0] for k, v in parse_qs(back.query).items()}


def _session_from(location: str) -> tuple[dict, str]:
    parts = urlsplit(location)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://truebex.com/login/sso/"
    assert parts.query == ""  # the session travels only in the fragment
    frag = {k: v[0] for k, v in parse_qs(parts.fragment).items()}
    return {"Authorization": f"Bearer {frag['token']}"}, frag["next"]


def _oidc_login(client, email):
    q = _authorize(_start(client, email))
    res = client.get("/auth/sso/oidc/callback", params=q, follow_redirects=False)
    return res


# --- domains ------------------------------------------------------------------------------


def test_sso_domain_verification(client, idp):
    h = signup(client, f"owner@{DOMAIN}")
    org = make_org(client, h)
    res = client.post(f"/orgs/{org['id']}/domains", json={"domain": "NorthStudio.COM."}, headers=h)
    assert res.status_code == 201
    body = res.json()
    assert body["domain"] == DOMAIN and body["verified_at"] is None
    rec = body["txt_record"]
    assert rec["name"] == f"_truebex-verification.{DOMAIN}" and rec["type"] == "TXT"
    assert rec["value"].startswith("truebex-domain-verification=") and len(rec["value"]) > 40
    # Adding it again is harmless.
    assert client.post(f"/orgs/{org['id']}/domains", json={"domain": DOMAIN}, headers=h).status_code == 200

    body = envelope(client.post(f"/orgs/{org['id']}/domains/{DOMAIN}/verify", headers=h), 409, "txt_mismatch")
    assert body["data"]["expected"] == rec["value"] and body["data"]["found"] == []
    idp[rec["name"]] = ["truebex-domain-verification=someone-elses", "v=spf1 -all"]
    envelope(client.post(f"/orgs/{org['id']}/domains/{DOMAIN}/verify", headers=h), 409, "txt_mismatch")
    idp[rec["name"]].append(rec["value"])
    res = client.post(f"/orgs/{org['id']}/domains/{DOMAIN}/verify", headers=h)
    assert res.status_code == 200 and res.json()["verified_at"] is not None

    # Once verified it belongs to this organisation alone.
    other_h = signup(client, "other@elsewhere.com")
    other = make_org(client, other_h, "Elsewhere")
    envelope(client.post(f"/orgs/{other['id']}/domains", json={"domain": DOMAIN}, headers=other_h), 409, "domain_taken")
    # While pending, several organisations may claim a domain, but only one verifies it.
    pending = client.post(f"/orgs/{other['id']}/domains", json={"domain": "shared.com"}, headers=other_h).json()
    rec2 = client.post(f"/orgs/{org['id']}/domains", json={"domain": "shared.com"}, headers=h).json()["txt_record"]
    idp[rec2["name"]] = [rec2["value"], pending["txt_record"]["value"]]
    assert client.post(f"/orgs/{org['id']}/domains/shared.com/verify", headers=h).status_code == 200
    envelope(client.post(f"/orgs/{other['id']}/domains/shared.com/verify", headers=other_h), 409, "domain_taken")
    assert client.delete(f"/orgs/{org['id']}/domains/shared.com", headers=h).status_code == 204

    envelope(client.post(f"/orgs/{org['id']}/domains", json={"domain": "not a domain"}, headers=h), 422, "validation_failed")
    envelope(client.post(f"/orgs/{org['id']}/domains", json={"domain": DOMAIN}), 401, "unauthenticated")
    envelope(client.post(f"/orgs/{org['id']}/domains", json={"domain": DOMAIN}, headers=other_h), 404, "not_found")
    assert [d["domain"] for d in client.get(f"/orgs/{org['id']}/domains", headers=h).json()] == [DOMAIN]
    assert client.delete(f"/orgs/{org['id']}/domains/{DOMAIN}", headers=h).status_code == 204
    assert client.get(f"/orgs/{org['id']}/domains", headers=h).json() == []


# --- settings ------------------------------------------------------------------------------


def test_sso_settings_owner_only_secret_write_only(client, idp):
    h, org = _verified_org(client, idp)
    out = _oidc(client, h, org)
    assert out["kind"] == "oidc" and out["has_client_secret"] is True and "client_secret" not in out
    assert out["sp"]["oidc_redirect_uri"] == f"{API}/auth/sso/oidc/callback"
    assert mock_oidc.CLIENT_SECRET not in client.get(f"/orgs/{org['id']}/sso", headers=h).text
    with SessionLocal() as db:
        sealed = db.get(SsoConnection, org["id"]).client_secret_enc
        assert sealed and mock_oidc.CLIENT_SECRET not in sealed
    # Saving again without the secret keeps it.
    assert client.put(f"/orgs/{org['id']}/sso", json={"kind": "oidc", "issuer": ISSUER, "client_id": "truebex-local"},
                      headers=h).json()["has_client_secret"] is True

    from .org_helpers import join
    admin = join(client, h, org["id"], f"admin@{DOMAIN}", role="admin")
    envelope(client.get(f"/orgs/{org['id']}/sso", headers=admin), 403, "forbidden")
    envelope(client.put(f"/orgs/{org['id']}/sso", json={"kind": "oidc"}, headers=admin), 403, "forbidden")
    envelope(client.get(f"/orgs/{org['id']}/sso"), 401, "unauthenticated")
    envelope(client.put(f"/orgs/{org['id']}/sso", json={"kind": "oidc", "issuer": "http://idp.example.org",
                                                         "client_id": "x", "client_secret": "y"}, headers=h),
             422, "validation_failed")
    envelope(client.put(f"/orgs/{org['id']}/sso", json={"kind": "ldap"}, headers=h), 422, "validation_failed")
    envelope(client.put(f"/orgs/{org['id']}/sso", json={"kind": "saml", "idp_metadata_xml": "<nope/>"}, headers=h),
             422, "validation_failed")

    # Requiring SSO needs a verified domain.
    bare_h = signup(client, "boss@nodomain.com")
    bare = make_org(client, bare_h, "No Domain")
    _oidc(client, bare_h, bare)
    envelope(client.put(f"/orgs/{bare['id']}/sso", json={"kind": "oidc", "issuer": ISSUER, "client_id": "truebex-local",
                                                          "required": True}, headers=bare_h), 409, "sso_not_ready")


def test_sso_start_unknown_domain(client, idp):
    envelope(client.get("/auth/sso/start", params={"email": "x@nowhere.com", "format": "json"}), 404, "sso_not_found")
    res = client.get("/auth/sso/start", params={"email": "x@nowhere.com"}, headers={"Accept": "text/html"})
    assert res.status_code == 404 and "Single sign-on" in res.text and "https://truebex.com/login/" in res.text
    envelope(client.get("/auth/sso/start"), 422, "validation_failed")


# --- OIDC -----------------------------------------------------------------------------------


def test_sso_oidc_login_jit(client, idp):
    h, org = _verified_org(client, idp)
    _oidc(client, h, org)

    # The site asks for the URL as JSON, then sends the browser there.
    url = client.get("/auth/sso/start", params={"email": f"C@{DOMAIN}", "format": "json"}).json()["url"]
    q = parse_qs(urlsplit(url).query)
    assert url.startswith(f"{ISSUER}/authorize?") and q["code_challenge_method"] == ["S256"]
    assert q["login_hint"] == [f"c@{DOMAIN}"] and q["redirect_uri"] == [f"{API}/auth/sso/oidc/callback"]
    assert len(q["code_challenge"][0]) == 43 and q["scope"] == ["openid email profile"]

    res = _oidc_login(client, f"c@{DOMAIN}")
    assert res.status_code == 302 and res.headers["cache-control"] == "no-store"
    session, next_ = _session_from(res.headers["location"])
    assert next_ == "/dashboard/organisation/"
    user = me(client, session)
    assert user["email"] == f"c@{DOMAIN}" and user["has_password"] is False
    orgs = client.get("/orgs", headers=session).json()
    assert [(o["id"], o["role"]) for o in orgs] == [(org["id"], "member")]

    # The same person again: the same account, still one membership.
    again, _ = _session_from(_oidc_login(client, f"c@{DOMAIN}").headers["location"])
    assert me(client, again)["id"] == user["id"]
    # An existing password account in the verified domain is joined, not duplicated.
    pw = signup(client, f"d@{DOMAIN}")
    linked, _ = _session_from(_oidc_login(client, f"d@{DOMAIN}").headers["location"])
    assert me(client, linked)["id"] == me(client, pw)["id"]
    kinds = [e["kind"] for e in client.get(f"/orgs/{org['id']}/audit?kind=sso", headers=h).json()["events"]]
    assert kinds.count("sso.signin") == 3
    # An unsafe next falls back to the dashboard.
    q = _authorize(_start(client, f"c@{DOMAIN}", next_="//evil.example/x"))
    _, next_ = _session_from(client.get("/auth/sso/oidc/callback", params=q, follow_redirects=False).headers["location"])
    assert next_ == "/dashboard/"


def test_sso_oidc_rejects_bad_state_nonce_audience(client, idp):
    h, org = _verified_org(client, idp)
    _oidc(client, h, org)
    other_key = (mock_saml_idp.FIXTURES / "saml_other_key.pem").read_text(encoding="ascii")

    q = _authorize(_start(client, f"c@{DOMAIN}"))
    envelope(client.get("/auth/sso/oidc/callback", params={**q, "state": "forged"}, follow_redirects=False),
             401, "sso_failed")
    # The real state still works once, then never again.
    assert client.get("/auth/sso/oidc/callback", params=q, follow_redirects=False).status_code == 302
    envelope(client.get("/auth/sso/oidc/callback", params=q, follow_redirects=False), 401, "sso_failed")

    for tweak in (
        {"nonce": "not-the-nonce"},
        {"aud": "someone-else"},
        {"iss": "https://evil.example"},
        {"email_verified": False},
        {"email": "c@gmail.com"},
        {"exp": 1_000_000_000},
        {"_key_pem": other_key},
        {"_kid": "unknown-key"},
    ):
        mock_oidc.TWEAKS.clear()
        mock_oidc.TWEAKS.update(tweak)
        res = _oidc_login(client, f"c@{DOMAIN}")
        envelope(res, 401, "sso_failed")
    mock_oidc.TWEAKS.clear()
    # A browser gets a page with a way back instead of JSON.
    q = _authorize(_start(client, f"c@{DOMAIN}"))
    res = client.get("/auth/sso/oidc/callback", params={**q, "state": "forged"}, headers={"Accept": "text/html"})
    assert res.status_code == 401 and "Back to sign in" in res.text
    envelope(client.get("/auth/sso/oidc/callback", params={"error": "access_denied", "state": "x"}), 401, "sso_failed")


# --- SAML ------------------------------------------------------------------------------------


def _saml_start(client, email=f"c@{DOMAIN}"):
    location = _start(client, email)
    assert location.startswith(f"{SAML_SSO}?")
    q = {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}
    req = mock_saml_idp.parse_authn_request(q["SAMLRequest"])
    return req, q["RelayState"]


def _acs(client, org, response_b64, relay):
    return client.post(
        f"/auth/sso/saml/{org['slug']}/acs", data={"SAMLResponse": response_b64, "RelayState": relay},
        follow_redirects=False,
    )


def _respond(req, **kw):
    kw.setdefault("email", f"c@{DOMAIN}")
    return mock_saml_idp.build_response(acs_url=req["acs_url"], audience=req["issuer"], in_response_to=req["id"], **kw)


def test_sso_saml_login_signed_assertion(client, idp):
    h, org = _verified_org(client, idp)
    out = _saml(client, h, org)
    assert out["kind"] == "saml" and out["idp_entity_id"] == mock_saml_idp.ENTITY_ID and out["idp_sso_url"] == SAML_SSO
    sp = out["sp"]
    assert sp["saml_acs_url"] == f"{API}/auth/sso/saml/studio-north/acs"

    # SP metadata parses and names the entity id and the ACS.
    res = client.get("/auth/sso/saml/studio-north/metadata")
    assert res.status_code == 200 and "samlmetadata+xml" in res.headers["content-type"]
    md = etree.fromstring(res.content)
    ns = {"md": "urn:oasis:names:tc:SAML:2.0:metadata"}
    assert md.get("entityID") == sp["saml_entity_id"]
    acs = md.find("md:SPSSODescriptor/md:AssertionConsumerService", ns)
    assert acs.get("Location") == sp["saml_acs_url"] and acs.get("Binding").endswith("HTTP-POST")
    assert md.find("md:SPSSODescriptor", ns).get("WantAssertionsSigned") == "true"
    envelope(client.get("/auth/sso/saml/nobody/metadata"), 404, "not_found")

    req, relay = _saml_start(client)
    assert req["issuer"] == sp["saml_entity_id"] and req["acs_url"] == sp["saml_acs_url"]
    res = _acs(client, org, _respond(req, name="Cee Example"), relay)
    assert res.status_code == 302, res.text
    session, next_ = _session_from(res.headers["location"])
    user = me(client, session)
    assert user["email"] == f"c@{DOMAIN}" and user["name"] == "Cee Example" and next_ == "/dashboard/organisation/"
    assert [o["id"] for o in client.get("/orgs", headers=session).json()] == [org["id"]]

    # A signed Response (rather than a signed Assertion) is accepted too.
    req, relay = _saml_start(client)
    assert _acs(client, org, _respond(req, sign="response"), relay).status_code == 302


def test_sso_saml_rejects_wrapping_replay_and_audience(client, idp):
    h, org = _verified_org(client, idp)
    _saml(client, h, org)
    now = datetime.now(timezone.utc)

    # Signature wrapping: an unsigned assertion for someone else in front of a signed one.
    req, relay = _saml_start(client)
    signed = _respond(req, email=f"attacker@{DOMAIN}")
    envelope(_acs(client, org, mock_saml_idp.wrap(signed, evil_email=f"ceo@{DOMAIN}"), relay), 401, "sso_failed")
    # The signed assertion edited in place: the digest no longer matches.
    req, relay = _saml_start(client)
    envelope(_acs(client, org, mock_saml_idp.tamper_email(_respond(req), evil_email=f"ceo@{DOMAIN}"), relay),
             401, "sso_failed")
    # Unsigned, and signed by another key.
    req, relay = _saml_start(client)
    envelope(_acs(client, org, _respond(req, sign="none"), relay), 401, "sso_failed")
    req, relay = _saml_start(client)
    envelope(_acs(client, org, _respond(req, key=mock_saml_idp.OTHER_KEY, cert=mock_saml_idp.OTHER_CERT), relay),
             401, "sso_failed")
    # Wrong audience, wrong issuer, expired.
    req, relay = _saml_start(client)
    envelope(_acs(client, org, mock_saml_idp.build_response(
        acs_url=req["acs_url"], audience="https://someone-else.example/sp", in_response_to=req["id"],
        email=f"c@{DOMAIN}"), relay), 401, "sso_failed")
    req, relay = _saml_start(client)
    envelope(_acs(client, org, _respond(req, issuer="https://other-idp.example"), relay), 401, "sso_failed")
    req, relay = _saml_start(client)
    envelope(_acs(client, org, _respond(req, now=now - timedelta(minutes=20),
                                       not_on_or_after=now - timedelta(minutes=10)), relay), 401, "sso_failed")
    # An answer to no request of ours.
    envelope(_acs(client, org, mock_saml_idp.build_response(
        acs_url=req["acs_url"], audience=req["issuer"], in_response_to="_never-asked", email=f"c@{DOMAIN}"), None),
        401, "sso_failed")
    # An address outside the verified domains.
    req, relay = _saml_start(client)
    envelope(_acs(client, org, _respond(req, email="c@gmail.com"), relay), 401, "sso_failed")

    # Replay: the same response twice, and the same assertion id in a new response.
    req, relay = _saml_start(client)
    aid = "_a" + secrets.token_hex(16)
    first = _respond(req, assertion_id=aid)
    assert _acs(client, org, first, relay).status_code == 302
    envelope(_acs(client, org, first, relay), 401, "sso_failed")
    req2, relay2 = _saml_start(client)
    envelope(_acs(client, org, _respond(req2, assertion_id=aid), relay2), 401, "sso_failed")
    # Garbage and a DTD are refused before any parsing of entities.
    envelope(_acs(client, org, base64.b64encode(b"<!DOCTYPE x [<!ENTITY a 'b'>]><x>&a;</x>").decode(), relay2),
             401, "sso_failed")
    envelope(_acs(client, org, "%%%", relay2), 401, "sso_failed")
    envelope(client.post(f"/auth/sso/saml/{org['slug']}/acs", data={}), 422, "validation_failed")


# --- the policy ------------------------------------------------------------------------------


def test_sso_required_blocks_password_and_google(client, idp, monkeypatch):
    h, org = _verified_org(client, idp)
    signup(client, f"m@{DOMAIN}")  # a password account from before the policy
    signup(client, "free@elsewhere.com")
    out = _oidc(client, h, org, required=True)
    code = out.pop("break_glass_code")
    assert out["required"] is True and len(code) == 23 and code.count("-") == 3
    assert "break_glass_code" not in client.get(f"/orgs/{org['id']}/sso", headers=h).json()

    def login(email, **extra):
        return client.post("/auth/login", json={"email": email, "password": "password123", **extra})

    body = envelope(login(f"m@{DOMAIN}"), 401, "sso_required")
    assert "Continue with SSO" in body["detail"] and body["data"]["org_name"] == "Studio North"
    envelope(login(f"owner@{DOMAIN}"), 401, "sso_required")
    envelope(client.post("/auth/register", json={"email": f"new@{DOMAIN}", "password": "password123"}),
             403, "sso_required")
    assert login("free@elsewhere.com").status_code == 200

    monkeypatch.setattr(
        auth_router, "verify_google_credential",
        lambda credential: {"sub": "g-1", "email": f"m@{DOMAIN}", "email_verified": True, "name": "M"},
    )
    envelope(client.post("/auth/google", json={"credential": "x" * 40}), 401, "sso_required")

    # Break-glass: an owner's code works once; a member's attempt with it fails.
    envelope(login(f"m@{DOMAIN}", break_glass_code=code), 401, "sso_required")
    res = login(f"owner@{DOMAIN}", break_glass_code=code.lower().replace("-", " "))
    assert res.status_code == 200 and res.json()["user"]["email"] == f"owner@{DOMAIN}"
    envelope(login(f"owner@{DOMAIN}", break_glass_code=code), 401, "sso_required")
    owner = {"Authorization": f"Bearer {res.json()['access_token']}"}
    fresh = client.post(f"/orgs/{org['id']}/sso/break-glass", headers=owner).json()["break_glass_code"]
    assert fresh != code and login(f"owner@{DOMAIN}", break_glass_code=fresh).status_code == 200
    kinds = [e["kind"] for e in client.get(f"/orgs/{org['id']}/audit?kind=sso", headers=owner).json()["events"]]
    assert "sso.break_glass_used" in kinds and "sso.policy_changed" in kinds and "sso.break_glass_refused" in kinds

    # SSO itself still signs domain users in.
    assert _oidc_login(client, f"m@{DOMAIN}").status_code == 302


def test_sso_requests_purge_job(client, idp):
    h, org = _verified_org(client, idp)
    _oidc(client, h, org)
    _start(client, f"c@{DOMAIN}")
    with SessionLocal() as db:
        assert len(list(db.scalars(select(SsoRequest)))) == 1
    assert "sso.requests.purge" in tasks.run_due(datetime.now(timezone.utc) + timedelta(minutes=11), force=True)
    with SessionLocal() as db:
        assert list(db.scalars(select(SsoRequest))) == []
