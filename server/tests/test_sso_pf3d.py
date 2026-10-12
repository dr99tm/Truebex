"""PF3d: OpenID Connect sign-in from identity providers that omit
`email_verified` (Microsoft Entra ID is the common case).

`verify_id_token` accepts the ID token's address when `email_verified` is
true, when Entra's `xms_edov` ("email domain owner verified") is true, or when
`email_verified` is absent and the connection's `trust_idp_email` switch is
on. An explicit `email_verified: false` stays refused. Every address must
still be in the organisation's verified domains (`service.sign_in`), so the
switch gives OIDC the trust SAML already has.

The tests play the provider with tests/mock_oidc.py's environment switch
(MOCK_OIDC_EMAIL_VERIFIED=true|false|absent, MOCK_OIDC_XMS_EDOV=1), the way the
human test does, and use test_sso.py's fixture and helpers.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import User
from app.orgs.models import Organisation, OrgMember
from app.sso import oidc, service
from app.sso.models import SsoConnection

from . import mock_oidc, mock_saml_idp
from .conftest import signup
from .org_helpers import _clean_mail_and_caches, envelope, join, make_org, me  # noqa: F401
from .test_sso import (  # noqa: F401  (idp is a fixture)
    DOMAIN,
    ISSUER,
    _acs,
    _authorize,
    _oidc,
    _oidc_login,
    _respond,
    _saml,
    _saml_start,
    _session_from,
    _start,
    _verified_org,
    idp,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
CONSTANTS = ROOT / "src" / "lib" / "constants.ts"
SSO_PAGE = ROOT / "src" / "app" / "dashboard" / "organisation" / "sso" / "page.tsx"
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")


def _site_copy() -> dict[str, str]:
    """SSO_TRUST_EMAIL's strings in src/lib/constants.ts (the site's copy)."""
    source = CONSTANTS.read_text(encoding="utf-8")
    block = source[source.index("export const SSO_TRUST_EMAIL"):]
    block = block[: block.index("} as const;")]
    return dict(re.findall(r'^\s*(\w+):\s*"([^"]+)"', block, re.M))


def _sso_events(client, h, org) -> list[dict]:
    return client.get(f"/orgs/{org['id']}/audit?kind=sso", headers=h).json()["events"]


def _user(email: str) -> User | None:
    with SessionLocal() as db:
        return db.scalar(select(User).where(User.email == email))


def _members(org) -> set[int]:
    with SessionLocal() as db:
        return set(db.scalars(select(OrgMember.user_id).where(OrgMember.org_id == org["id"])))


@pytest.fixture()
def absent(monkeypatch):
    """The mock provider plays Entra ID: no `email_verified` in its ID tokens."""
    monkeypatch.setenv("MOCK_OIDC_EMAIL_VERIFIED", "absent")
    monkeypatch.delenv("MOCK_OIDC_XMS_EDOV", raising=False)


# --- the ID-token rule ------------------------------------------------------------------------


def test_pf3d_absent_email_verified_refused_without_switch(client, idp, absent):
    h, org = _verified_org(client, idp)
    assert _oidc(client, h, org)["trust_idp_email"] is False
    members = _members(org)

    body = envelope(_oidc_login(client, f"c@{DOMAIN}"), 401, "sso_failed")
    assert body["detail"] == oidc.NOT_MARKED_VERIFIED
    # The message names the switch exactly as the SSO tab labels it, and where it is.
    assert f"“{_site_copy()['label']}”" in body["detail"] and "Organisation → SSO" in body["detail"]
    # Nobody is signed in: no account, no membership, no sign-in event.
    assert _user(f"c@{DOMAIN}") is None and _members(org) == members
    assert "sso.signin" not in [e["kind"] for e in _sso_events(client, h, org)]

    # A browser gets the failure page with the same advice.
    q = _authorize(_start(client, f"c@{DOMAIN}"))
    res = client.get("/auth/sso/oidc/callback", params=q, headers={"Accept": "text/html"})
    assert res.status_code == 401 and "Single sign-on did not finish" in res.text
    assert oidc.NOT_MARKED_VERIFIED in res.text and "Back to sign in" in res.text
    assert _user(f"c@{DOMAIN}") is None


def test_pf3d_absent_with_switch_signs_in_jit(client, idp, absent):
    h, org = _verified_org(client, idp)
    assert _oidc(client, h, org, trust_idp_email=True)["trust_idp_email"] is True

    res = _oidc_login(client, f"c@{DOMAIN}")
    assert res.status_code == 302, res.text
    session, next_ = _session_from(res.headers["location"])
    user = me(client, session)
    assert user["email"] == f"c@{DOMAIN}" and user["has_password"] is False and next_ == "/dashboard/organisation/"
    assert [(o["id"], o["role"]) for o in client.get("/orgs", headers=session).json()] == [(org["id"], "member")]
    events = client.get(f"/orgs/{org['id']}/audit", headers=h).json()["events"]
    joined = next(e for e in events if e["kind"] == "member.joined" and e["target"]["id"] == str(user["id"]))
    assert joined["details"]["via"] == "sso.oidc"
    signin = next(e for e in events if e["kind"] == "sso.signin")
    assert signin["details"] == {"protocol": "oidc", "new_account": True}
    # The same person again: the same account.
    again, _ = _session_from(_oidc_login(client, f"c@{DOMAIN}").headers["location"])
    assert me(client, again)["id"] == user["id"]


def test_pf3d_explicit_false_refused_with_switch(client, idp, monkeypatch):
    h, org = _verified_org(client, idp)
    _oidc(client, h, org, trust_idp_email=True)
    monkeypatch.setenv("MOCK_OIDC_EMAIL_VERIFIED", "false")
    body = envelope(_oidc_login(client, f"c@{DOMAIN}"), 401, "sso_failed")
    assert body["detail"] == oidc.NOT_VERIFIED
    # The other ways a provider says "no" are refused too; so is a false
    # beside Entra's xms_edov (the provider contradicts itself).
    monkeypatch.delenv("MOCK_OIDC_EMAIL_VERIFIED")
    for tweak in ({"email_verified": "false"}, {"email_verified": 0}, {"email_verified": "no"},
                  {"email_verified": False, "xms_edov": True}):
        mock_oidc.TWEAKS.clear()
        mock_oidc.TWEAKS.update(tweak)
        assert envelope(_oidc_login(client, f"c@{DOMAIN}"), 401, "sso_failed")["detail"] == oidc.NOT_VERIFIED, tweak
    mock_oidc.TWEAKS.clear()
    assert _user(f"c@{DOMAIN}") is None
    # A JSON null says nothing, like a missing claim: the switch lets it in.
    mock_oidc.TWEAKS.update({"email_verified": None})
    assert _oidc_login(client, f"c@{DOMAIN}").status_code == 302
    mock_oidc.TWEAKS.clear()
    # A missing e-mail keeps its own refusal, switch or not.
    mock_oidc.TWEAKS.update({"_drop": ["email", "email_verified"]})
    body = envelope(_oidc_login(client, f"e@{DOMAIN}"), 401, "sso_failed")
    assert body["detail"] == "The identity provider sent no e-mail address."


def test_pf3d_xms_edov_signs_in_without_switch(client, idp, absent, monkeypatch):
    h, org = _verified_org(client, idp)
    _oidc(client, h, org)  # the switch stays off
    monkeypatch.setenv("MOCK_OIDC_XMS_EDOV", "1")
    res = _oidc_login(client, f"c@{DOMAIN}")
    assert res.status_code == 302, res.text
    session, _ = _session_from(res.headers["location"])
    assert me(client, session)["email"] == f"c@{DOMAIN}"
    # The forms providers send it in: JSON true, "true", "1", 1.
    for value in (True, "true", "1", 1):
        mock_oidc.TWEAKS.clear()
        mock_oidc.TWEAKS.update({"xms_edov": value})
        assert _oidc_login(client, f"c@{DOMAIN}").status_code == 302, value
    # A false one is no confirmation.
    for value in (False, "false", 0):
        mock_oidc.TWEAKS.clear()
        mock_oidc.TWEAKS.update({"xms_edov": value})
        body = envelope(_oidc_login(client, f"c@{DOMAIN}"), 401, "sso_failed")
        assert body["detail"] == oidc.NOT_MARKED_VERIFIED, value
    mock_oidc.TWEAKS.clear()


def test_pf3d_switch_on_outside_verified_domains_refused(client, idp, absent):
    h, org = _verified_org(client, idp)
    _oidc(client, h, org, trust_idp_email=True)
    members = _members(org)
    for email in ("c@gmail.com", f"c@sub.{DOMAIN}", "c@northstudio.com.evil.example"):
        mock_oidc.TWEAKS.clear()
        mock_oidc.TWEAKS.update({"email": email})
        body = envelope(_oidc_login(client, f"c@{DOMAIN}"), 401, "sso_failed")
        assert "outside the organisation's verified domains" in body["detail"], email
        assert _user(email) is None
    mock_oidc.TWEAKS.clear()
    assert _members(org) == members


def test_pf3d_links_existing_account_only_in_verified_domain(client, idp, absent):
    h, org = _verified_org(client, idp)
    _oidc(client, h, org, trust_idp_email=True)
    # The organisation has also claimed a domain it has not verified yet.
    assert client.post(f"/orgs/{org['id']}/domains", json={"domain": "pending.com"}, headers=h).status_code == 201

    # A password account in the verified domain is joined, not duplicated.
    pw = signup(client, f"d@{DOMAIN}")
    res = _oidc_login(client, f"d@{DOMAIN}")
    assert res.status_code == 302, res.text
    linked, _ = _session_from(res.headers["location"])
    assert me(client, linked)["id"] == me(client, pw)["id"]
    assert [o["id"] for o in client.get("/orgs", headers=pw).json()] == [org["id"]]

    # Accounts in a pending domain or another domain are never taken over.
    for email in ("p@pending.com", "someone@gmail.com"):
        other = signup(client, email)
        mock_oidc.TWEAKS.clear()
        mock_oidc.TWEAKS.update({"email": email})
        envelope(_oidc_login(client, f"c@{DOMAIN}"), 401, "sso_failed")
        assert client.get("/orgs", headers=other).json() == []
        assert me(client, other)["id"] not in _members(org)
    mock_oidc.TWEAKS.clear()
    signins = [e for e in _sso_events(client, h, org) if e["kind"] == "sso.signin"]
    assert [e["details"]["new_account"] for e in signins] == [False]


def test_pf3d_saml_unaffected_by_switch(client, idp, absent):
    h, org = _verified_org(client, idp)
    assert _oidc(client, h, org, trust_idp_email=True)["trust_idp_email"] is True

    # The switch is OpenID Connect's: SAML refuses it on.
    body = envelope(
        client.put(f"/orgs/{org['id']}/sso", headers=h, json={
            "kind": "saml", "idp_metadata_xml": mock_saml_idp.metadata("https://idp.test/saml/sso"),
            "trust_idp_email": True,
        }),
        422, "validation_failed",
    )
    assert body["data"]["fields"][0]["field"] == "trust_idp_email"
    # Moving the connection to SAML turns it off, and the log says so.
    out = _saml(client, h, org, trust_idp_email=False)
    assert out["kind"] == "saml" and out["trust_idp_email"] is False
    assert [e["kind"] for e in _sso_events(client, h, org)][:2] == ["sso.trust_email_off", "sso.configured"]

    # SAML signs in and refuses exactly as before, whatever the stored switch says.
    for stored in (False, True):
        with SessionLocal() as db:
            db.get(SsoConnection, org["id"]).trust_idp_email = stored
            db.commit()
        req, relay = _saml_start(client)
        res = _acs(client, org, _respond(req, email=f"s{int(stored)}@{DOMAIN}"), relay)
        assert res.status_code == 302, res.text
        session, _ = _session_from(res.headers["location"])
        assert me(client, session)["email"] == f"s{int(stored)}@{DOMAIN}"
        req, relay = _saml_start(client)
        body = envelope(_acs(client, org, _respond(req, email="c@gmail.com"), relay), 401, "sso_failed")
        assert "outside the organisation's verified domains" in body["detail"]


# --- the setting -------------------------------------------------------------------------------


def test_pf3d_setting_owner_only_and_audited(client, idp):
    h, org = _verified_org(client, idp)
    sso = f"/orgs/{org['id']}/sso"
    assert client.get(sso, headers=h).json()["trust_idp_email"] is False  # nothing configured yet
    assert _oidc(client, h, org)["trust_idp_email"] is False  # off by default
    assert _oidc(client, h, org, trust_idp_email=True)["trust_idp_email"] is True
    assert client.get(sso, headers=h).json()["trust_idp_email"] is True
    # Left out of a save, it keeps its value (as an empty secret keeps the secret);
    # the same value again is no change.
    kept = client.put(sso, json={"kind": "oidc", "issuer": ISSUER, "client_id": mock_oidc.CLIENT_ID}, headers=h)
    assert kept.status_code == 200 and kept.json()["trust_idp_email"] is True
    _oidc(client, h, org, trust_idp_email=True)
    assert _oidc(client, h, org, trust_idp_email=False)["trust_idp_email"] is False
    assert client.get(sso, headers=h).json()["trust_idp_email"] is False

    owner = me(client, h)
    changes = [e for e in _sso_events(client, h, org) if e["kind"].startswith("sso.trust_email")]
    assert [e["kind"] for e in changes] == ["sso.trust_email_off", "sso.trust_email_on"]  # newest first
    for e in changes:
        assert e["actor"] == {"user_id": owner["id"], "email": owner["email"]}
        assert e["target"] == {"kind": "org", "id": org["id"]} and e["details"] == {"protocol": "oidc"}
    csv = client.get(f"/orgs/{org['id']}/audit?kind=sso&format=csv", headers=h).text
    assert "sso.trust_email_on" in csv and "sso.trust_email_off" in csv

    # Only an owner may change it (or read it); an admin cannot.
    admin = join(client, h, org["id"], f"admin@{DOMAIN}", role="admin")
    body = {"kind": "oidc", "issuer": ISSUER, "client_id": mock_oidc.CLIENT_ID, "trust_idp_email": True}
    envelope(client.put(sso, json=body, headers=admin), 403, "forbidden")
    envelope(client.get(sso, headers=admin), 403, "forbidden")
    envelope(client.put(sso, json=body), 401, "unauthenticated")
    envelope(client.put(sso, json={**body, "trust_idp_email": "perhaps"}, headers=h), 422, "validation_failed")
    assert client.get(sso, headers=h).json()["trust_idp_email"] is False
    assert len([e for e in _sso_events(client, h, org) if e["kind"].startswith("sso.trust_email")]) == 2

    # A new connection saved with the switch on is a change too.
    other_h = signup(client, "boss@elsewhere.com")
    other = make_org(client, other_h, "Elsewhere")
    _oidc(client, other_h, other, trust_idp_email=True)
    assert [e["kind"] for e in _sso_events(client, other_h, other)][:2] == ["sso.trust_email_on", "sso.configured"]


def test_pf3d_column_migrated_and_copied(tmp_path):
    """A database from before PF3d gains `sso_connections.trust_idp_email`
    (`_ADDED_COLUMNS`), its old rows read as off, and the Postgres copy
    (scripts/sqlite_to_postgres.py) carries the column with no change."""
    from scripts import sqlite_to_postgres as s2p

    src = f"sqlite:///{tmp_path / 'auth.db'}"
    engine = create_engine(src)
    try:
        init_db(engine, seed=False)
        with Session(engine) as db:
            user = User(email="owner@example.com", hashed_password="x")
            db.add(user)
            db.flush()
            for slug, trust in (("old", None), ("on", True)):
                db.add(Organisation(id=slug.ljust(32, "0"), name=slug, slug=slug, created_by=user.id))
                db.add(SsoConnection(org_id=slug.ljust(32, "0"), kind="oidc", issuer=ISSUER, client_id="x"))
            db.commit()
        with engine.begin() as conn:  # the table as PF3 made it
            conn.execute(text("ALTER TABLE sso_connections DROP COLUMN trust_idp_email"))
        init_db(engine, seed=False)
        with engine.begin() as conn:
            conn.execute(text("UPDATE sso_connections SET trust_idp_email = :t WHERE org_id LIKE 'on%'"), {"t": True})
        with Session(engine) as db:
            rows = {c.org_id.rstrip("0"): c.trust_idp_email for c in db.scalars(select(SsoConnection))}
            assert rows["old"] is None and rows["on"] is True  # NULL from before PF3d = off
            org = db.get(Organisation, "old".ljust(32, "0"))
            assert service.connection_json(db, org)["trust_idp_email"] is False
    finally:
        engine.dispose()

    assert s2p.precheck(src) == []
    report = s2p.copy_database(src, f"sqlite:///{tmp_path / 'copy.db'}")
    assert report.ok, report.render()
    copy = create_engine(f"sqlite:///{tmp_path / 'copy.db'}")
    try:
        with Session(copy) as db:
            rows = {c.org_id.rstrip("0"): c.trust_idp_email for c in db.scalars(select(SsoConnection))}
        assert rows == {"old": None, "on": True}
    finally:
        copy.dispose()


# --- the mock provider's switch ------------------------------------------------------------------


def _mock_claims() -> dict:
    """One ID token from the mock provider, its claims unverified."""
    with TestClient(mock_oidc.app, base_url=ISSUER) as idp_client:
        verifier, challenge = oidc.pkce_pair()
        res = idp_client.get("/authorize", params={
            "response_type": "code", "client_id": mock_oidc.CLIENT_ID, "redirect_uri": "https://api.test/cb",
            "state": "s", "nonce": "n", "code_challenge": challenge, "code_challenge_method": "S256",
            "scope": "openid email", "login_hint": f"c@{DOMAIN}",
        }, follow_redirects=False)
        code = re.search(r"code=([^&]+)", res.headers["location"]).group(1)
        res = idp_client.post("/token", data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": "https://api.test/cb",
            "code_verifier": verifier,
        }, auth=(mock_oidc.CLIENT_ID, mock_oidc.CLIENT_SECRET))
    assert res.status_code == 200, res.text
    return jwt.get_unverified_claims(res.json()["id_token"])


def test_pf3d_mock_oidc_env_switch(monkeypatch):
    mock_oidc.reset()
    monkeypatch.delenv("MOCK_OIDC_EMAIL_VERIFIED", raising=False)
    monkeypatch.delenv("MOCK_OIDC_XMS_EDOV", raising=False)
    claims = _mock_claims()
    assert claims["email_verified"] is True and "xms_edov" not in claims  # the default, as before
    for value, expected in (("true", True), ("FALSE", False), (" false ", False)):
        monkeypatch.setenv("MOCK_OIDC_EMAIL_VERIFIED", value)
        assert _mock_claims()["email_verified"] is expected, value
    monkeypatch.setenv("MOCK_OIDC_EMAIL_VERIFIED", "absent")
    claims = _mock_claims()
    assert "email_verified" not in claims and claims["email"] == f"c@{DOMAIN}"
    monkeypatch.setenv("MOCK_OIDC_XMS_EDOV", "1")
    assert _mock_claims()["xms_edov"] is True
    # The tests' own tweaks still win over the environment.
    mock_oidc.TWEAKS.update({"email_verified": True})
    assert _mock_claims()["email_verified"] is True
    mock_oidc.reset()
    # A typo is loud, not a silent default.
    monkeypatch.setenv("MOCK_OIDC_EMAIL_VERIFIED", "maybe")
    with pytest.raises(AssertionError, match="use true, false or absent"):
        _mock_claims()
    assert "MOCK_OIDC_EMAIL_VERIFIED=maybe" in mock_oidc._env_note()


# --- the site ------------------------------------------------------------------------------------


def test_pf3d_sso_tab_source_sends_the_switch():
    copy = _site_copy()
    assert copy["label"] == "Trust the e-mail address from your identity provider"
    assert "Only addresses in your verified domains can sign in." in copy["help"]
    for name in ("Entra", "Microsoft", "Azure", "Okta", "Google"):  # brand voice: no other vendor named
        assert name not in " ".join(copy.values()), name
    page = SSO_PAGE.read_text(encoding="utf-8")
    assert "SSO_TRUST_EMAIL" in page and "trust_idp_email: trustEmail" in page
    # Sent with the OpenID Connect settings only.
    oidc_body = page[page.index('kind === "oidc"\n'):page.index("idp_metadata_xml: metadata")]
    assert "trust_idp_email" in oidc_body


@built
def test_pf3d_site_sso_tab_chunk_has_checkbox_copy():
    html = (OUT / "dashboard" / "organisation" / "sso" / "index.html").read_text(encoding="utf-8")
    scripts = sorted(set(re.findall(r'"(/_next/static/[^"]+?\.js)"', html)))
    assert scripts, "the SSO tab names no script chunks"
    chunks = {s: (OUT / s.lstrip("/")).read_text(encoding="utf-8", errors="ignore") for s in scripts}
    # The copy ships in the constants chunk and the form that sends the switch
    # in the page's own chunk; both load with the SSO tab.
    copy = _site_copy()
    assert any(copy["label"] in body and copy["help"] in body for body in chunks.values()), \
        "the checkbox copy is in none of the SSO tab's chunks"
    assert any("trust_idp_email" in body for body in chunks.values())
