"""Sign-up and verification: a company applies from a new or an existing
account, uploads a company document (a PDF ≤ 10 MB), and stays `applied`
until an admin verifies it (PF7's admin); the decision is e-mailed.

Unverified suppliers can prepare products but not publish them
(`common.require_verified`).
"""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..market import hooks
from ..market.catalogue import add_member, create_supplier, set_supplier_regions
from ..market.common import invalid, new_id, now, rfc3339
from ..market.models import Supplier
from ..market.taxonomy import active_regions
from ..models import User
from ..storage import get_store
from . import notify
from .common import memberships, portal_url
from .models import SupplierApplication
from .schemas import ApplicationIn

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_DOCUMENTS = 5


def application_of(db: Session, supplier_id: str) -> SupplierApplication | None:
    return db.scalar(
        select(SupplierApplication)
        .where(SupplierApplication.supplier_id == supplier_id)
        .order_by(SupplierApplication.created_at.desc())
    )


def application_json(app: SupplierApplication | None) -> dict | None:
    if app is None:
        return None
    return {
        "application_id": app.application_id,
        "supplier_id": app.supplier_id,
        "state": app.state,
        "fields": app.fields or {},
        "documents": [
            {k: d.get(k) for k in ("sha256", "bytes", "name", "uploaded_at")} for d in (app.document_keys or [])
        ],
        "reason": app.reason,
        "created_at": rfc3339(app.created_at),
        "decided_at": rfc3339(app.decided_at),
    }


def apply(db: Session, user: User, body: ApplicationIn) -> SupplierApplication:
    """409 `already_applied` when this account already applied or owns a supplier."""
    if db.scalar(select(SupplierApplication.application_id).where(SupplierApplication.submitted_by == user.id)):
        raise ContractError("already_applied", 409, "This account has already applied. Open the supplier portal.")
    if any(role == "owner" for _s, role in memberships(db, user)):
        raise ContractError("already_applied", 409, "This account already owns a supplier. Open the supplier portal.")
    known = active_regions(db)
    regions = {}
    for code in body.regions:
        if code.upper() not in known:
            raise invalid("regions", f"{code!r} is not a region Truebex serves ({', '.join(known)})", "body")
        regions[code.upper()] = known[code.upper()]
    supplier = create_supplier(
        db,
        name=body.name,
        legal_name=body.legal_name,
        country=body.country.upper(),
        company_number=body.company_number,
        vat_id=body.vat_id,
        website=body.website,
        contact_email=str(body.contact.email),
        status="applied",
    )
    set_supplier_regions(db, supplier, regions)
    add_member(db, supplier, user, "owner")
    fields = body.model_dump(mode="json")
    fields["country"] = fields["country"].upper()
    fields["regions"] = sorted(regions)
    fields["address"]["country"] = fields["address"]["country"].upper()
    app = SupplierApplication(
        application_id=new_id(),
        supplier_id=supplier.supplier_id,
        submitted_by=user.id,
        fields=fields,
        document_keys=[],
        state="applied",
        created_at=now(),
    )
    db.add(app)
    db.commit()
    to = [str(body.contact.email)]
    if user.email.lower() != str(body.contact.email).lower():
        to.append(user.email)
    notify.send(to, "supplier_application_received", {"supplier_name": supplier.name, "portal_url": portal_url()})
    return app


def add_document(db: Session, supplier: Supplier, data: bytes, filename: str) -> dict:
    """Store a company document; never rendered on the server."""
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ContractError("too_large", 413, "A document is at most 10 MB.")
    if not data.startswith(b"%PDF-"):
        raise ContractError("not_pdf", 422, "Upload the company document as a PDF.")
    app = application_of(db, supplier.supplier_id)
    if app is None:
        raise ContractError("not_found", 404, "Apply first, then upload the company document.")
    sha = hashlib.sha256(data).hexdigest()
    docs = list(app.document_keys or [])
    if not any(d["sha256"] == sha for d in docs):
        if len(docs) >= MAX_DOCUMENTS:
            raise ContractError("too_many", 409, f"At most {MAX_DOCUMENTS} documents per application.")
        key = f"market/suppliers/{supplier.supplier_id}/docs/{sha}.pdf"
        get_store().put(key, data, content_type="application/pdf")
        safe = "".join(ch if ch.isalnum() or ch in " -_.()" else "-" for ch in (filename or "document.pdf"))[:120]
        docs.append({"key": key, "sha256": sha, "bytes": len(data), "name": safe or "document.pdf", "uploaded_at": rfc3339(now())})
        app.document_keys = docs
        db.add(app)
        db.commit()
    return next(
        {k: d.get(k) for k in ("sha256", "bytes", "name", "uploaded_at")} for d in docs if d["sha256"] == sha
    )


def admin_json(db: Session, supplier: Supplier) -> dict:
    """The application with short-lived links to its documents (admins only)."""
    app = application_of(db, supplier.supplier_id)
    out = application_json(app) or {"state": None, "fields": {}, "documents": []}
    store = get_store()
    links = []
    for d in (app.document_keys if app else []) or []:
        url = store.signed_get_url(d["key"], expires_in=900, filename=d.get("name") or "document.pdf")
        links.append({k: d.get(k) for k in ("sha256", "bytes", "name", "uploaded_at")} | {"url": url})
    out["documents"] = links
    return out


# --- The admin's decision (PF7's PATCH /admin/market/suppliers/{id}) -------------------------


@hooks.on("supplier.status_changed")
def decided(db: Session, supplier: Supplier, old: str, new: str, reason: str | None = None, admin: User | None = None) -> None:
    app = application_of(db, supplier.supplier_id)
    if new == "verified" and old != "verified":
        if app is not None and app.state != "verified":
            app.state, app.decided_at, app.reason = "verified", now(), None
            app.decided_by = admin.id if admin else None
            db.add(app)
            db.commit()
        notify.send(
            notify.recipients(db, supplier),
            "supplier_verified",
            {"supplier_name": supplier.name, "portal_url": portal_url()},
        )
    elif new == "suspended" and old == "applied" and app is not None and app.state == "applied":
        app.state, app.decided_at, app.reason = "declined", now(), reason
        app.decided_by = admin.id if admin else None
        db.add(app)
        db.commit()
        notify.send(
            notify.recipients(db, supplier),
            "supplier_declined",
            {
                "supplier_name": supplier.name,
                "reason": reason or "(no reason given)",
                "support_email": get_settings().support_email,
            },
        )
