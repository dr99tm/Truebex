"""The billing-service interface every payment provider implements.

Routers and other features (PF6 and PF11 overage, PF7 commissions, PF8
listing fees) talk to a provider only through `BillingProvider`, picked by
name from `billing.providers.get_provider`. Adapters: `paddle` (merchant of
record, the default), `stripe` (Stripe Tax; business invoices) and `wayl`
(dormant behind WAYL_ENABLED).
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Payment, ProviderPrice, Subscription, User
from ..plans import FOUNDING
from . import pricing


class ProviderError(Exception):
    """The provider refused or could not be reached; nothing was changed."""


class WebhookError(ValueError):
    """A webhook failed verification (bad signature or stale timestamp)."""


class NotSupported(ProviderError):
    """This provider cannot do that (e.g. Paddle and business invoices)."""


@dataclass(frozen=True)
class Invoice:
    id: str
    number: str | None
    issued_at: datetime | None
    total_minor: int
    tax_minor: int
    currency: str
    status: str
    # A direct URL (Stripe) or None when the PDF is fetched on demand (Paddle).
    pdf_url: str | None


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    amount_minor: int
    currency: str
    quantity: int = 1


class BillingProvider(ABC):
    name: str

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def enabled(self) -> bool:
        """Keys present (and WAYL_ENABLED for Wayl)."""

    def resolve_coupon(self, code: str) -> str | None:
        """The provider's discount id for a customer-entered code, or None."""
        return None

    @abstractmethod
    def create_checkout(
        self,
        db: Session,
        user: User,
        payment: Payment,
        price: ProviderPrice | None,
        seats: int,
        discount: str | None,
    ) -> str:
        """Open a checkout for `payment`; returns the URL the browser opens."""

    @abstractmethod
    def verify_payment(self, db: Session, payment: Payment) -> None:
        """Fetch the provider's own state of a checkout and apply it."""

    @abstractmethod
    def handle_webhook(self, db: Session, body: bytes, headers: Mapping[str, str]) -> str:
        """Verify, de-duplicate by event id and apply. Returns the event type.
        Raises WebhookError when the request is not the provider's."""

    @abstractmethod
    def portal_url(self, db: Session, user: User, sub: Subscription) -> str:
        """The provider's customer portal (cards, cancellation)."""

    def change_subscription(
        self,
        db: Session,
        sub: Subscription,
        *,
        tier: str | None = None,
        interval: str | None = None,
        seats: int | None = None,
    ) -> Subscription:
        """Change tier, interval or seats, prorated now. The new price is the
        catalogue's for the subscription's currency (the founding price when
        the subscription was bought at it). Raises PriceUnavailable."""
        tier = tier or sub.plan
        interval = interval or sub.interval or "month"
        # The founding price follows the subscription to tiers the offer covers.
        founding = bool(sub.founding) and tier in FOUNDING.tiers
        price = pricing.resolve(db, self.name, tier, interval, sub.currency or "USD", founding)
        plan = pricing.plan(tier)
        seats = seats if seats is not None else (sub.seats or 1)
        seats = max(seats, plan.min_seats) if plan.per_seat else 1
        return self._apply_change(db, sub, price, seats)

    @abstractmethod
    def _apply_change(
        self, db: Session, sub: Subscription, price: ProviderPrice, seats: int
    ) -> Subscription:
        """Move the provider subscription to `price` x `seats` and mirror the
        provider's answer."""

    @abstractmethod
    def list_invoices(self, db: Session, user: User) -> list[Invoice]:
        """The customer's invoices, newest first."""

    def invoice_pdf_url(self, db: Session, user: User, invoice_id: str) -> str:
        """A fresh URL of one invoice's PDF."""
        raise NotSupported(f"{self.name} has no invoice PDFs")

    @abstractmethod
    def charge_usage(
        self,
        db: Session,
        sub: Subscription,
        metric: str,
        quantity: int,
        unit_amount_minor: int,
        description: str,
    ) -> str:
        """A one-off charge on the subscription (metered overage, PF6, PF11).
        Returns the provider's id for it."""

    def create_invoice(
        self, db: Session, customer: str, lines: list[InvoiceLine]
    ) -> str:
        """A business invoice (Enterprise, PF7 commissions, PF8 listing fees)."""
        raise NotSupported(f"{self.name} cannot issue business invoices; use stripe")

    def reconcile(self, db: Session, subs: list[Subscription], payments: list[Payment]) -> int:
        """Re-fetch these subscriptions and pending payments (missed webhooks).
        Returns how many were checked."""
        return 0


def str_or_none(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
