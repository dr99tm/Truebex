"""SAML 2.0 Web Browser SSO, SP-initiated: an AuthnRequest over HTTP-Redirect,
the Response over HTTP-POST to the ACS, signed assertions required.

Verification reads only what `signxml` returns as signed (the Response or
the Assertion the signature covers), against the certificate configured for
the organisation, which defeats signature wrapping (Somorovsky et al.,
USENIX Security 2012); a document holding more than one Assertion is refused
outright. Then: Issuer, Audience (our entity id), Recipient (the ACS URL),
NotBefore / NotOnOrAfter within 120 s, InResponseTo naming a pending
request, and one use per assertion id. Encrypted assertions are not
accepted (v1 requires TLS and signed, unencrypted assertions).
"""

import base64
import secrets
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from xml.sax.saxutils import escape, quoteattr

from cryptography import x509
from lxml import etree
from signxml import XMLVerifier
from signxml.exceptions import InvalidCertificate, InvalidDigest, InvalidInput, InvalidSignature

from ..config import get_settings
from ..contract_http import ContractError
from ..orgs.models import Organisation

NS = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "md": "urn:oasis:names:tc:SAML:2.0:metadata",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}
BINDING_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
BINDING_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
NAMEID_EMAIL = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
STATUS_SUCCESS = "urn:oasis:names:tc:SAML:2.0:status:Success"
SKEW = timedelta(seconds=120)
MAX_RESPONSE_BYTES = 512 * 1024
EMAIL_ATTRIBUTES = (
    "email",
    "mail",
    "emailaddress",
    "urn:oid:0.9.2342.19200300.100.1.3",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
)
NAME_ATTRIBUTES = ("name", "displayname", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name")


def fail(detail: str) -> ContractError:
    return ContractError("sso_failed", 401, detail)


def _parser() -> etree.XMLParser:
    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)


def parse_xml(data: bytes) -> etree._Element:
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise ValueError("DTDs are not accepted")
    return etree.fromstring(data, parser=_parser())


# --- our side: entity id, ACS, metadata --------------------------------------------


def sp_entity_id(org: Organisation) -> str:
    return get_settings().saml_sp_entity_id or metadata_url(org)


def _base(org: Organisation) -> str:
    return f"{get_settings().api_url.rstrip('/')}/auth/sso/saml/{org.slug}"


def metadata_url(org: Organisation) -> str:
    return f"{_base(org)}/metadata"


def acs_url(org: Organisation) -> str:
    return f"{_base(org)}/acs"


def sp_metadata(org: Organisation) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<md:EntityDescriptor xmlns:md="{NS["md"]}" entityID={quoteattr(sp_entity_id(org))}>'
        f'<md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" '
        f'protocolSupportEnumeration="{NS["samlp"]}">'
        f"<md:NameIDFormat>{NAMEID_EMAIL}</md:NameIDFormat>"
        f'<md:AssertionConsumerService Binding="{BINDING_POST}" Location={quoteattr(acs_url(org))} '
        'index="0" isDefault="true"/>'
        "</md:SPSSODescriptor></md:EntityDescriptor>\n"
    ).encode("utf-8")


# --- their side: IdP metadata --------------------------------------------------------


@dataclass(frozen=True)
class IdpConfig:
    entity_id: str
    sso_url: str
    cert_pem: str


def cert_pem_from_text(text: str) -> str:
    """A PEM certificate from PEM text or bare base64 (as metadata carries it)."""
    body = "".join(text.replace("-----BEGIN CERTIFICATE-----", "").replace("-----END CERTIFICATE-----", "").split())
    der = base64.b64decode(body, validate=True)
    cert = x509.load_der_x509_certificate(der)
    from cryptography.hazmat.primitives.serialization import Encoding

    return cert.public_bytes(Encoding.PEM).decode("ascii")


def parse_idp_metadata(xml_text: str) -> IdpConfig:
    try:
        root = parse_xml(xml_text.encode("utf-8"))
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise _bad_metadata(f"not readable XML ({exc.__class__.__name__})")
    entity = root if root.tag == f"{{{NS['md']}}}EntityDescriptor" else root.find(".//md:EntityDescriptor", NS)
    if entity is None:
        raise _bad_metadata("no EntityDescriptor")
    idp = entity.find("md:IDPSSODescriptor", NS)
    if idp is None:
        raise _bad_metadata("no IDPSSODescriptor")
    sso = next(
        (s.get("Location") for s in idp.findall("md:SingleSignOnService", NS) if s.get("Binding") == BINDING_REDIRECT),
        None,
    )
    if not sso:
        raise _bad_metadata("no SingleSignOnService with the HTTP-Redirect binding")
    certs = [
        kd.find(".//ds:X509Certificate", NS)
        for kd in idp.findall("md:KeyDescriptor", NS)
        if kd.get("use") in (None, "signing")
    ]
    certs = [c.text for c in certs if c is not None and c.text]
    if not certs:
        raise _bad_metadata("no signing certificate")
    try:
        pem = cert_pem_from_text(certs[0])
    except (ValueError, TypeError):
        raise _bad_metadata("the signing certificate does not load")
    return IdpConfig(entity_id=entity.get("entityID") or "", sso_url=sso, cert_pem=pem)


def _bad_metadata(why: str) -> ContractError:
    return ContractError(
        "validation_failed", 422, f"idp_metadata_xml: {why}",
        {"fields": [{"field": "idp_metadata_xml", "in": "body", "message": why}]},
    )


# --- AuthnRequest (HTTP-Redirect) ---------------------------------------------------


def _instant(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_request_id() -> str:
    return "_" + secrets.token_hex(20)


def authn_request_url(org: Organisation, idp_sso_url: str, request_id: str, relay_state: str, now: datetime) -> str:
    xml = (
        f'<samlp:AuthnRequest xmlns:samlp="{NS["samlp"]}" xmlns:saml="{NS["saml"]}" '
        f'ID="{request_id}" Version="2.0" IssueInstant="{_instant(now)}" '
        f"Destination={quoteattr(idp_sso_url)} AssertionConsumerServiceURL={quoteattr(acs_url(org))} "
        f'ProtocolBinding="{BINDING_POST}">'
        f"<saml:Issuer>{escape(sp_entity_id(org))}</saml:Issuer>"
        f'<samlp:NameIDPolicy Format="{NAMEID_EMAIL}" AllowCreate="true"/>'
        "</samlp:AuthnRequest>"
    )
    deflater = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = deflater.compress(xml.encode("utf-8")) + deflater.flush()
    query = urlencode({"SAMLRequest": base64.b64encode(raw).decode("ascii"), "RelayState": relay_state})
    sep = "&" if "?" in idp_sso_url else "?"
    return f"{idp_sso_url}{sep}{query}"


# --- the Response (HTTP-POST to the ACS) ---------------------------------------------


@dataclass(frozen=True)
class Assertion:
    id: str
    in_response_to: str
    email: str
    name: str | None
    not_on_or_after: datetime


def _time(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.strip().replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        raise fail("The SAML response carries a malformed time.")


def _verified_assertion(data: bytes, cert_pem: str) -> etree._Element:
    try:
        doc = parse_xml(data)
    except (etree.XMLSyntaxError, ValueError):
        raise fail("The SAML response is not readable XML.")
    if doc.tag != f"{{{NS['samlp']}}}Response":
        raise fail("This is not a SAML response.")
    if doc.find(".//saml:EncryptedAssertion", NS) is not None:
        raise fail("Encrypted assertions are not supported; send a signed, unencrypted assertion.")
    if len(doc.findall(".//saml:Assertion", NS)) != 1 or doc.find("saml:Assertion", NS) is None:
        raise fail("The SAML response must hold exactly one assertion.")
    status = doc.find("samlp:Status/samlp:StatusCode", NS)
    if status is None or status.get("Value") != STATUS_SUCCESS:
        raise fail("The identity provider did not sign you in.")
    try:
        result = XMLVerifier().verify(data, x509_cert=cert_pem)
    except (InvalidSignature, InvalidDigest, InvalidInput, InvalidCertificate, etree.XMLSyntaxError, ValueError):
        raise fail("The SAML response is not signed by your identity provider.")
    signed = result.signed_xml
    # Only the signed element is read from here on.
    if signed is not None and signed.tag == f"{{{NS['saml']}}}Assertion":
        assertion = signed
    elif signed is not None and signed.tag == f"{{{NS['samlp']}}}Response":
        found = signed.findall("saml:Assertion", NS)
        if len(found) != 1:
            raise fail("The signed SAML response must hold exactly one assertion.")
        assertion = found[0]
    else:
        raise fail("The SAML signature covers neither the response nor its assertion.")
    # The element the signature covers must be the one in place, not a copy
    # hidden elsewhere (signature wrapping).
    in_place = doc.find("saml:Assertion", NS)
    if in_place.get("ID") != assertion.get("ID"):
        raise fail("The signed assertion is not the response's assertion.")
    return assertion


def verify_response(
    org: Organisation,
    *,
    saml_response_b64: str,
    idp_entity_id: str,
    cert_pem: str,
    now: datetime,
) -> Assertion:
    try:
        data = base64.b64decode(saml_response_b64, validate=False)
    except (ValueError, TypeError):
        raise fail("The SAML response is not base64.")
    if not data or len(data) > MAX_RESPONSE_BYTES:
        raise fail("The SAML response is empty or too large.")
    assertion = _verified_assertion(data, cert_pem)

    issuer = assertion.findtext("saml:Issuer", namespaces=NS)
    if (issuer or "").strip() != idp_entity_id:
        raise fail("The SAML assertion comes from another identity provider.")

    conditions = assertion.find("saml:Conditions", NS)
    if conditions is None:
        raise fail("The SAML assertion has no Conditions.")
    not_before = _time(conditions.get("NotBefore"))
    not_after = _time(conditions.get("NotOnOrAfter"))
    if not_before is not None and now + SKEW < not_before:
        raise fail("The SAML assertion is not valid yet (check the clocks).")
    if not_after is None or now - SKEW >= not_after:
        raise fail("The SAML assertion has expired.")
    audiences = [a.text.strip() for a in conditions.findall("saml:AudienceRestriction/saml:Audience", NS) if a.text]
    if sp_entity_id(org) not in audiences:
        raise fail("The SAML assertion is meant for another service.")

    subject = assertion.find("saml:Subject", NS)
    if subject is None:
        raise fail("The SAML assertion has no Subject.")
    confirmed = None
    for sc in subject.findall("saml:SubjectConfirmation", NS):
        data_el = sc.find("saml:SubjectConfirmationData", NS)
        if sc.get("Method") != "urn:oasis:names:tc:SAML:2.0:cm:bearer" or data_el is None:
            continue
        if data_el.get("Recipient") != acs_url(org):
            continue
        sc_after = _time(data_el.get("NotOnOrAfter"))
        if sc_after is None or now - SKEW >= sc_after:
            continue
        confirmed = data_el
        break
    if confirmed is None:
        raise fail("The SAML assertion is not addressed to this sign-in (Recipient or time).")
    in_response_to = confirmed.get("InResponseTo") or ""
    if not in_response_to:
        raise fail("Sign-ins started at the identity provider are not supported; start from Truebex.")

    email = None
    name_id = subject.find("saml:NameID", NS)
    if name_id is not None and name_id.text and "@" in name_id.text:
        email = name_id.text.strip()
    attrs: dict[str, str] = {}
    for attr in assertion.findall("saml:AttributeStatement/saml:Attribute", NS):
        value = attr.findtext("saml:AttributeValue", namespaces=NS)
        if value:
            attrs[(attr.get("Name") or "").lower()] = value.strip()
    if email is None:
        email = next((attrs[k] for k in EMAIL_ATTRIBUTES if k in attrs and "@" in attrs[k]), None)
    if not email:
        raise fail("The identity provider sent no e-mail address.")
    name = next((attrs[k] for k in NAME_ATTRIBUTES if k in attrs), None)
    if name is None and ("givenname" in attrs or "surname" in attrs):
        name = " ".join(filter(None, (attrs.get("givenname"), attrs.get("surname")))) or None
    assertion_id = assertion.get("ID") or ""
    if not assertion_id:
        raise fail("The SAML assertion has no ID.")
    return Assertion(
        id=assertion_id, in_response_to=in_response_to, email=email.lower(), name=name, not_on_or_after=not_after
    )
