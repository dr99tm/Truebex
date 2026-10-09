"""A local SAML 2.0 identity provider for the SSO tests and the human test:
it signs responses with the TEST certificate in tests/fixtures/sso/
(signxml, RSA-SHA256, exclusive c14n), and can build the broken ones the
tests need (unsigned, wrapped, wrong audience, expired, another key).

A person runs it next to the local API (from server/):

    .venv\\Scripts\\python.exe -m uvicorn tests.mock_saml_idp:app --port 8099

pastes http://127.0.0.1:8099/metadata into the SSO tab (SAML), and signs in
with "Continue with SSO": /sso answers the AuthnRequest with a signed
response for the requested address, posted to the ACS by a self-submitting
form (no password: it is a test stand-in).
"""

import base64
import html
import secrets
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from lxml import etree
from signxml import XMLSigner, methods
from signxml.algorithms import CanonicalizationMethod, DigestAlgorithm, SignatureMethod

FIXTURES = Path(__file__).parent / "fixtures" / "sso"
KEY = (FIXTURES / "saml_idp_key.pem").read_bytes()
CERT = (FIXTURES / "saml_idp_cert.pem").read_text(encoding="ascii")
OTHER_KEY = (FIXTURES / "saml_other_key.pem").read_bytes()
OTHER_CERT = (FIXTURES / "saml_other_cert.pem").read_text(encoding="ascii")
ENTITY_ID = "https://idp.test/saml"

P = "urn:oasis:names:tc:SAML:2.0:protocol"
A = "urn:oasis:names:tc:SAML:2.0:assertion"
DS = "http://www.w3.org/2000/09/xmldsig#"
SUCCESS = "urn:oasis:names:tc:SAML:2.0:status:Success"


def _instant(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cert_body(cert_pem: str = CERT) -> str:
    return "".join(l for l in cert_pem.splitlines() if "CERTIFICATE" not in l)


def metadata(sso_url: str, entity_id: str = ENTITY_ID, cert_pem: str = CERT) -> str:
    return (
        '<?xml version="1.0"?>'
        f'<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" '
        f'xmlns:ds="{DS}" entityID="{html.escape(entity_id)}">'
        '<md:IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
        f'<md:KeyDescriptor use="signing"><ds:KeyInfo><ds:X509Data><ds:X509Certificate>{cert_body(cert_pem)}'
        "</ds:X509Certificate></ds:X509Data></ds:KeyInfo></md:KeyDescriptor>"
        '<md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" '
        f'Location="{html.escape(sso_url)}"/>'
        "</md:IDPSSODescriptor></md:EntityDescriptor>"
    )


def _signer() -> XMLSigner:
    return XMLSigner(
        method=methods.enveloped,
        signature_algorithm=SignatureMethod.RSA_SHA256,
        digest_algorithm=DigestAlgorithm.SHA256,
        c14n_algorithm=CanonicalizationMethod.EXCLUSIVE_XML_CANONICALIZATION_1_0,
    )


def assertion_xml(
    *,
    assertion_id: str,
    issuer: str,
    audience: str,
    recipient: str,
    in_response_to: str,
    email: str,
    now: datetime,
    not_before: datetime | None = None,
    not_on_or_after: datetime | None = None,
    name: str | None = None,
    placeholder: bool = True,
) -> str:
    not_before = not_before or now - timedelta(seconds=30)
    not_on_or_after = not_on_or_after or now + timedelta(minutes=5)
    attrs = f'<saml:Attribute Name="name"><saml:AttributeValue>{html.escape(name)}</saml:AttributeValue></saml:Attribute>' if name else ""
    return (
        f'<saml:Assertion xmlns:saml="{A}" xmlns:ds="{DS}" ID="{assertion_id}" Version="2.0" IssueInstant="{_instant(now)}">'
        f"<saml:Issuer>{html.escape(issuer)}</saml:Issuer>"
        + ('<ds:Signature Id="placeholder"></ds:Signature>' if placeholder else "")
        + "<saml:Subject>"
        f'<saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{html.escape(email)}</saml:NameID>'
        '<saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">'
        f'<saml:SubjectConfirmationData InResponseTo="{html.escape(in_response_to)}" '
        f'Recipient="{html.escape(recipient)}" NotOnOrAfter="{_instant(not_on_or_after)}"/>'
        "</saml:SubjectConfirmation></saml:Subject>"
        f'<saml:Conditions NotBefore="{_instant(not_before)}" NotOnOrAfter="{_instant(not_on_or_after)}">'
        f"<saml:AudienceRestriction><saml:Audience>{html.escape(audience)}</saml:Audience></saml:AudienceRestriction>"
        "</saml:Conditions>"
        f'<saml:AuthnStatement AuthnInstant="{_instant(now)}"><saml:AuthnContext>'
        "<saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"
        "</saml:AuthnContextClassRef></saml:AuthnContext></saml:AuthnStatement>"
        f"<saml:AttributeStatement>{attrs}</saml:AttributeStatement>"
        "</saml:Assertion>"
    )


def build_response(
    *,
    acs_url: str,
    audience: str,
    in_response_to: str,
    email: str,
    issuer: str = ENTITY_ID,
    sign: str = "assertion",  # assertion | response | none
    assertion_id: str | None = None,
    now: datetime | None = None,
    not_before: datetime | None = None,
    not_on_or_after: datetime | None = None,
    key: bytes = KEY,
    cert: str = CERT,
    name: str | None = None,
) -> str:
    """A SAML Response, base64-encoded as the HTTP-POST binding carries it."""
    now = now or datetime.now(timezone.utc)
    assertion_id = assertion_id or "_a" + secrets.token_hex(16)
    assertion = etree.fromstring(
        assertion_xml(
            assertion_id=assertion_id, issuer=issuer, audience=audience, recipient=acs_url,
            in_response_to=in_response_to, email=email, now=now, not_before=not_before,
            not_on_or_after=not_on_or_after, name=name, placeholder=sign == "assertion",
        )
    )
    if sign == "assertion":
        assertion = _signer().sign(assertion, key=key, cert=cert, reference_uri=assertion_id)
    response_id = "_r" + secrets.token_hex(16)
    root = etree.fromstring(
        f'<samlp:Response xmlns:samlp="{P}" xmlns:saml="{A}" xmlns:ds="{DS}" ID="{response_id}" Version="2.0" '
        f'IssueInstant="{_instant(now)}" Destination="{html.escape(acs_url)}" InResponseTo="{html.escape(in_response_to)}">'
        f"<saml:Issuer>{html.escape(issuer)}</saml:Issuer>"
        + ('<ds:Signature Id="placeholder"></ds:Signature>' if sign == "response" else "")
        + f'<samlp:Status><samlp:StatusCode Value="{SUCCESS}"/></samlp:Status>'
        "</samlp:Response>"
    )
    root.append(assertion)
    if sign == "response":
        root = _signer().sign(root, key=key, cert=cert, reference_uri=response_id)
    return base64.b64encode(etree.tostring(root)).decode("ascii")


def wrap(signed_b64: str, *, evil_email: str) -> str:
    """Signature wrapping (XSW): an unsigned assertion for `evil_email` takes the
    signed one's place, and the signed original hides inside it."""
    root = etree.fromstring(base64.b64decode(signed_b64))
    original = root.find(f"{{{A}}}Assertion")
    evil = etree.fromstring(etree.tostring(original))
    evil.set("ID", "_evil" + secrets.token_hex(8))
    for sig in evil.findall(f"{{{DS}}}Signature"):
        evil.remove(sig)
    evil.find(f"{{{A}}}Subject/{{{A}}}NameID").text = evil_email
    root.remove(original)
    root.append(evil)
    ext = etree.SubElement(evil, f"{{{A}}}Advice")
    ext.append(original)
    return base64.b64encode(etree.tostring(root)).decode("ascii")


def tamper_email(signed_b64: str, *, evil_email: str) -> str:
    """Change the signed assertion's address in place (the digest no longer matches)."""
    root = etree.fromstring(base64.b64decode(signed_b64))
    root.find(f".//{{{A}}}NameID").text = evil_email
    return base64.b64encode(etree.tostring(root)).decode("ascii")


def parse_authn_request(saml_request: str) -> dict:
    xml = zlib.decompress(base64.b64decode(saml_request), -15)
    root = etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    return {
        "id": root.get("ID"),
        "acs_url": root.get("AssertionConsumerServiceURL"),
        "destination": root.get("Destination"),
        "issuer": root.findtext(f"{{{A}}}Issuer"),
    }


# --- the app for the human test ------------------------------------------------------------

app = FastAPI(title="Mock SAML IdP (tests only)")


@app.get("/metadata")
def idp_metadata(request: Request) -> Response:
    base = str(request.base_url).rstrip("/")
    return Response(metadata(f"{base}/sso", entity_id=ENTITY_ID), media_type="application/samlmetadata+xml")


@app.get("/sso", response_class=HTMLResponse)
def sso(SAMLRequest: str, RelayState: str = "", email: str = "c@example.com") -> str:  # noqa: N803
    req = parse_authn_request(SAMLRequest)
    response = build_response(
        acs_url=req["acs_url"], audience=req["issuer"], in_response_to=req["id"], email=email,
    )
    return (
        "<!doctype html><title>Mock IdP</title><body onload='document.forms[0].submit()'>"
        f"<form method='post' action='{html.escape(req['acs_url'])}'>"
        f"<input type='hidden' name='SAMLResponse' value='{response}'>"
        f"<input type='hidden' name='RelayState' value='{html.escape(RelayState)}'>"
        f"<p>Signing in {html.escape(email)}…</p><button>Continue</button></form>"
    )
