"""What every supplier-portal module shares: the signed-in member and the
supplier they act for, the role rules, portal links and errors.

Roles (PF7's `supplier_members.role`): `owner` does everything; `catalogue`
edits products, prices and imports; `orders` answers the inbox; `viewer`
reads the catalogue, prices, imports and analytics. Buyer details (the
inbox) are for `owner` and `orders` only.
"""

from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..database import get_db
from ..deps import get_current_user
from ..market.catalogue import ROLES
from ..market.models import Supplier, SupplierMember
from ..models import User

ANY = frozenset(ROLES)
CATALOGUE = frozenset({"owner", "catalogue"})
ORDERS = frozenset({"owner", "orders"})
OWNER = frozenset({"owner"})

ROLE_NAMES = {"owner": "owner", "catalogue": "catalogue editor", "orders": "order handler", "viewer": "viewer"}

# The header the portal sends to pick one of the user's suppliers.
SUPPLIER_HEADER = "X-Truebex-Supplier"


@dataclass
class Member:
    user: User
    supplier: Supplier
    role: str


def not_supplier(detail: str = "You are not a member of a supplier on Truebex. Apply at /supplier/signup/.") -> ContractError:
    return ContractError("not_supplier", 403, detail)


def memberships(db: Session, user: User) -> list[tuple[Supplier, str]]:
    return list(
        db.execute(
            select(Supplier, SupplierMember.role)
            .join(SupplierMember, SupplierMember.supplier_id == Supplier.supplier_id)
            .where(SupplierMember.user_id == user.id)
            .order_by(Supplier.name, Supplier.supplier_id)
        ).tuples()
    )


def resolve(db: Session, user: User, supplier_id: str | None) -> Member:
    """The supplier this request acts for: the one named by the header, or
    the user's first (by name) when it names none."""
    rows = memberships(db, user)
    if supplier_id:
        rows = [(s, r) for s, r in rows if s.supplier_id == supplier_id]
    if not rows:
        raise not_supplier()
    supplier, role = rows[0]
    return Member(user=user, supplier=supplier, role=role)


def member(roles: frozenset[str] = ANY, *, write: bool = False):
    """Route dependency: the member, 403 `forbidden` for a role outside
    `roles`, and 403 `supplier_suspended` for writes of a suspended supplier."""

    def dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        supplier_id: str | None = Header(default=None, alias=SUPPLIER_HEADER, max_length=32),
    ) -> Member:
        m = resolve(db, user, supplier_id)
        if m.role not in roles:
            raise ContractError(
                "forbidden",
                403,
                f"Your role ({ROLE_NAMES.get(m.role, m.role)}) cannot do this. Ask your supplier's owner.",
                {"role": m.role, "allowed": sorted(roles)},
            )
        if write and m.supplier.status == "suspended":
            raise ContractError("supplier_suspended", 403, "This supplier is suspended. Contact Truebex.")
        return m

    return dependency


def require_verified(supplier: Supplier, action: str = "publish products") -> None:
    if supplier.status != "verified":
        raise ContractError(
            "not_verified", 409, f"Your supplier account is under review; you can {action} once it is verified."
        )


def conflict(detail: str, code: str = "conflict", data: dict | None = None) -> ContractError:
    return ContractError(code, 409, detail, data)


# --- Links in e-mails -----------------------------------------------------------------


def portal_url(path: str = "") -> str:
    return f"{get_settings().site_url.rstrip('/')}/supplier/{path.lstrip('/')}"
