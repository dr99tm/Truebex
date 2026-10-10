"""Verified e-mail domains: an organisation claims `example.com`, publishes a
TXT record `_truebex-verification.example.com` = `truebex-domain-verification=<token>`
and asks us to check it. Only verified domains route sign-in to an identity
provider or allow just-in-time accounts, and a domain is verified for one
organisation at most (several may claim it while pending, so nobody can
squat on it).
"""

import re
import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from ..orgs import audit
from ..orgs.models import OrgDomain, Organisation

TXT_PREFIX = "_truebex-verification"
TXT_VALUE = "truebex-domain-verification="
_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]$")


def normalise(domain: str) -> str:
    text = (domain or "").strip().lower().rstrip(".")
    if text.startswith("@"):
        text = text[1:]
    try:
        text = text.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    if not _DOMAIN.match(text):
        raise ContractError(
            "validation_failed", 422, "domain: a domain name like example.com",
            {"fields": [{"field": "domain", "in": "body", "message": "not a domain name"}]},
        )
    return text


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower() if "@" in (email or "") else ""


def record_name(domain: str) -> str:
    return f"{TXT_PREFIX}.{domain}"


def domain_json(row: OrgDomain) -> dict:
    return {
        "domain": row.domain,
        "txt_record": {"name": record_name(row.domain), "type": "TXT", "value": TXT_VALUE + row.txt_token},
        "verified_at": clock.rfc3339(row.verified_at),
        "created_at": clock.rfc3339(row.created_at),
    }


def resolve_txt(name: str) -> list[str]:
    """TXT strings published at `name` (tests patch this; no answer = [])."""
    import dns.exception
    import dns.resolver

    try:
        answer = dns.resolver.resolve(name, "TXT", lifetime=5.0)
    except (dns.exception.DNSException, OSError):
        return []
    return [b"".join(r.strings).decode("utf-8", "replace") for r in answer]


def list_for(db: Session, org: Organisation) -> list[OrgDomain]:
    return list(db.scalars(select(OrgDomain).where(OrgDomain.org_id == org.id).order_by(OrgDomain.domain)))


def _verified_elsewhere(db: Session, org: Organisation, domain: str) -> bool:
    return (
        db.scalar(
            select(OrgDomain.id).where(
                OrgDomain.domain == domain, OrgDomain.verified_at.is_not(None), OrgDomain.org_id != org.id
            )
        )
        is not None
    )


def _taken() -> ContractError:
    return ContractError("domain_taken", 409, "Another organisation has already verified this domain.")


def add(db: Session, org: Organisation, actor: int, domain: str, now: datetime) -> tuple[OrgDomain, bool]:
    domain = normalise(domain)
    existing = db.scalar(select(OrgDomain).where(OrgDomain.org_id == org.id, OrgDomain.domain == domain))
    if existing is not None:
        return existing, False
    if _verified_elsewhere(db, org, domain):
        raise _taken()
    row = OrgDomain(org_id=org.id, domain=domain, txt_token=secrets.token_hex(16), created_at=now)
    db.add(row)
    audit.record(db, org.id, "domain.added", actor=actor, target_kind="domain", target_id=domain, at=now)
    db.commit()
    return row, True


def get(db: Session, org: Organisation, domain: str) -> OrgDomain:
    row = db.scalar(
        select(OrgDomain).where(OrgDomain.org_id == org.id, OrgDomain.domain == (domain or "").strip().lower())
    )
    if row is None:
        raise ContractError("not_found", 404, "This organisation has not added that domain.")
    return row


def verify(db: Session, org: Organisation, actor: int, domain: str, now: datetime) -> OrgDomain:
    row = get(db, org, domain)
    if row.verified_at is not None:
        return row
    if _verified_elsewhere(db, org, row.domain):
        raise _taken()
    expected = TXT_VALUE + row.txt_token
    found = [t.strip() for t in resolve_txt(record_name(row.domain))]
    if expected not in found:
        raise ContractError(
            "txt_mismatch",
            409,
            f"The TXT record at {record_name(row.domain)} does not hold {expected} yet. "
            "DNS changes can take a while to appear.",
            {"name": record_name(row.domain), "expected": expected, "found": found[:10]},
        )
    row.verified_at = now
    db.add(row)
    audit.record(db, org.id, "domain.verified", actor=actor, target_kind="domain", target_id=row.domain, at=now)
    try:
        db.commit()
    except IntegrityError:  # verified elsewhere a moment ago
        db.rollback()
        raise _taken()
    return row


def remove(db: Session, org: Organisation, actor: int, domain: str, now: datetime) -> None:
    row = get(db, org, domain)
    db.delete(row)
    audit.record(db, org.id, "domain.removed", actor=actor, target_kind="domain", target_id=row.domain, at=now)
    db.flush()
    if org.sso_required and not any(d.verified_at for d in list_for(db, org)):
        org.sso_required = False  # no verified domain left: nothing to require
        db.add(org)
        audit.record(db, org.id, "sso.policy_changed", actor=actor, target_kind="org", target_id=org.id, at=now,
                     required=False, reason="last verified domain removed")
    db.commit()


def verified_owner(db: Session, email: str) -> Organisation | None:
    """The organisation that verified this address's domain, if any."""
    domain = email_domain(email)
    if not domain:
        return None
    row = db.scalar(select(OrgDomain).where(OrgDomain.domain == domain, OrgDomain.verified_at.is_not(None)))
    if row is None:
        return None
    org = db.get(Organisation, row.org_id)
    return org if org is not None and org.deleted_at is None else None


def is_verified_for(db: Session, org: Organisation, email: str) -> bool:
    domain = email_domain(email)
    return bool(domain) and db.scalar(
        select(OrgDomain.id).where(
            OrgDomain.org_id == org.id, OrgDomain.domain == domain, OrgDomain.verified_at.is_not(None)
        )
    ) is not None
