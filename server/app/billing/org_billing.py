"""Organisation billing (PF3a): organisations buy and change seats through
PF2's providers.

* Who: an organisation's `owner` and `billing` roles buy, change seats or
  plan, open the portal and read invoices; `admin` and `member` get 403 (they
  read the plan through GET /orgs/{id}); someone outside it gets 404 (PF3's
  rule: an organisation's existence is not disclosed).
* How a subscription becomes the organisation's: a checkout for an
  organisation records `payments.organisation_id` and names the organisation
  in Paddle's custom_data or Stripe's metadata. The provider's subscription
  is attached only from that payment row, matched by the provider itself (the
  subscription's originating transaction, our checkout session), never from
  custom_data: Paddle.js lets a buyer set custom_data with the public client
  token. A subscription whose claims name an organisation without such a
  match is applied as PF2 applies it, for the person it names.
* An organisation's tier never reaches its buyer's `users.plan` cache
  (`service.live_subscription` skips organisation rows); its members get it
  through PF3's seats (`seat_source`, named and floating).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..models import Payment, Subscription, User
from ..orgs.models import Organisation, SeatAssignment
from ..plans import rank
from . import service
from .base import InvoiceScope

# The roles that buy for an organisation and manage what it bought.
BILLING_ROLES = ("owner", "billing")


def require_billing(db: Session, org_id: str, user: User) -> Organisation:
    """The organisation when `user` is its owner or billing member; 404 when
    they are not a member (or it does not exist), 403 for any other role."""
    from ..orgs import service as orgs

    org = orgs.get_org(db, org_id)
    member = orgs.membership(db, org.id, user.id)
    if member is None:
        raise ContractError("not_found", 404, "There is no such organisation.")
    if member.role not in BILLING_ROLES:
        raise ContractError(
            "forbidden", 403, f"Only an owner or a billing member of {org.name} can manage its plan and invoices."
        )
    return org


def live_subscription(db: Session, org_id: str) -> Subscription | None:
    """The organisation's best live subscription, of any provider (a hand
    grant from scripts/grant_org_seats.py included): its tier and seats."""
    from ..orgs.service import org_subscription

    return org_subscription(db, org_id)


def managed_subscription(db: Session, org_id: str) -> Subscription | None:
    """The organisation's Paddle or Stripe subscription: the live one if any,
    else the most recently updated (a past-due card still needs the portal)."""
    subs = list(
        db.scalars(
            select(Subscription)
            .where(
                Subscription.organisation_id == org_id,
                Subscription.provider.in_(service.MANAGED_PROVIDERS),
            )
            .order_by(Subscription.updated_at.desc(), Subscription.id.desc())
        )
    )
    live = [s for s in subs if service.is_live(s)]
    if live:
        return max(live, key=lambda s: rank(s.plan))
    return subs[0] if subs else None


def blocking_subscription(db: Session, org_id: str) -> Subscription | None:
    """What stops a second checkout for the organisation: a live
    subscription, or a past-due or paused one waiting for its card."""
    live = live_subscription(db, org_id)
    if live is not None:
        return live
    managed = managed_subscription(db, org_id)
    if managed is not None and managed.status in ("past_due", "paused"):
        return managed
    return None


def assigned(db: Session, org_id: str) -> tuple[int, int]:
    """(named seats assigned, the floating pool size) of an organisation."""
    named = int(
        db.scalar(
            select(func.count())
            .select_from(SeatAssignment)
            .where(SeatAssignment.org_id == org_id, SeatAssignment.kind == "named")
        )
        or 0
    )
    org = db.get(Organisation, org_id)
    return named, int(org.floating_seats or 0) if org is not None else 0


def seats_assigned(db: Session, org_id: str) -> int:
    """Seats of the organisation given to people: every named seat assigned
    plus the floating pool (`organisations.floating_seats`)."""
    named, floating = assigned(db, org_id)
    return named + floating


# --- invoices --------------------------------------------------------------------------


def org_scope(db: Session, org_id: str, provider: str) -> InvoiceScope | None:
    """The organisation's invoices at `provider`: those of its subscriptions,
    under whichever buyer's customer paid them. None when it has none there."""
    subs = list(
        db.scalars(
            select(Subscription).where(
                Subscription.organisation_id == org_id, Subscription.provider == provider
            )
        )
    )
    customers = sorted({s.provider_customer_id for s in subs if s.provider_customer_id})
    if not customers:
        return None
    return InvoiceScope(
        customers=tuple(customers),
        only=frozenset(s.provider_subscription_id for s in subs if s.provider_subscription_id),
    )


def personal_scope(db: Session, user: User, provider: str) -> InvoiceScope | None:
    """The person's own invoices at `provider`: their customer's, without the
    subscriptions and checkouts they paid for organisations."""
    customer = service.customer_id(db, user, provider)
    if not customer:
        return None
    org_subs = db.scalars(
        select(Subscription.provider_subscription_id).where(
            Subscription.provider == provider,
            Subscription.provider_customer_id == customer,
            Subscription.organisation_id.is_not(None),
            Subscription.provider_subscription_id.is_not(None),
        )
    )
    org_checkouts = db.scalars(
        select(Payment.provider_ref).where(
            Payment.provider == provider,
            Payment.user_id == user.id,
            Payment.organisation_id.is_not(None),
            Payment.provider_ref.is_not(None),
        )
    )
    return InvoiceScope(customers=(customer,), exclude=frozenset([*org_subs, *org_checkouts]))


# --- attaching a provider subscription --------------------------------------------------


def awaiting_link(db: Session, provider: str, claims: dict) -> bool:
    """True when a subscription's claims (Paddle custom_data, Stripe
    metadata) name one of our organisation checkouts but the event carries no
    verified link to it. Such a subscription is held back: it is applied when
    the link arrives (the checkout's transaction or session event, the
    return-page refresh or the daily reconcile), never from the claim, so it
    is never its buyer's personal plan in between."""
    if not claims.get("org_id") or not claims.get("reference"):
        return False
    payment = db.scalar(
        select(Payment).where(
            Payment.provider == provider, Payment.reference == str(claims["reference"])[:64]
        )
    )
    return payment is not None and payment.organisation_id is not None


def owner_of(
    existing: Subscription | None, origin: Payment | None
) -> tuple[int, str | None] | None:
    """(user id, organisation id) for a provider subscription from its row or
    its originating payment of ours; None when neither says (the caller then
    reads the person from the provider's claims, without an organisation).

    A row keeps its buyer; an organisation is attached to it only from the
    buyer's own payment, and never changes once set (upsert_subscription)."""
    if origin is not None and (existing is None or existing.user_id == origin.user_id):
        return origin.user_id, origin.organisation_id
    if existing is not None:
        return existing.user_id, None
    return None
