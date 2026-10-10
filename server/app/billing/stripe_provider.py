"""Stripe: card subscriptions through Stripe Checkout, with Stripe Tax, and
business invoices (Enterprise, PF7 commissions, PF8 listing fees).

Truebex Ltd is the seller here: Stripe Tax calculates and collects, the
registrations and returns stay with the company (see PF2's provider
decision). The original monthly Pro price (STRIPE_PRICE_PRO) keeps mapping
to Pro for existing subscribers.

An organisation (PF3a, `metadata.org_id`) is attached only from our payment
row, matched by our own Checkout Session (`client_reference_id` and the
session id we stored), never from metadata alone (billing/org_billing.py).
"""

import logging
import time
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Payment, ProviderPrice, Subscription, User
from ..plans import PLANS
from . import consent, consumer, org_billing, service
from .base import (
    BillingProvider,
    Invoice,
    InvoiceLine,
    InvoiceScope,
    ProviderError,
    Refund,
    WebhookError,
    parse_time,
    refund_amount,
    str_or_none,
)

log = logging.getLogger("truebex.billing.stripe")

# A founding checkout stays payable a little past its 30-minute hold (Stripe's
# shortest session life is 30 minutes).
FOUNDING_SESSION_S = 31 * 60

# Stripe subscription status -> ours.
_STATUS = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "unpaid": "past_due",
    "incomplete": "past_due",
    "canceled": "canceled",
    "incomplete_expired": "canceled",
    "paused": "paused",
}

_SUBSCRIPTION_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.paused",
    "customer.subscription.resumed",
}

# A paid renewal invoice opens the renewal cooling-off (PF2b).
_INVOICE_EVENTS = {"invoice.paid", "invoice.payment_succeeded"}


def _id_of(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, Mapping):
        return str_or_none(value.get("id"))
    return None


def _invoice_subscription(inv: Any) -> str | None:
    # Newer API versions moved it under parent.subscription_details.
    sub = inv.get("subscription")
    if not sub:
        sub = ((inv.get("parent") or {}).get("subscription_details") or {}).get("subscription")
    return _id_of(sub)


def _period_end(sub: Any) -> datetime | None:
    # Newer Stripe API versions moved current_period_end onto the items.
    ts = sub.get("current_period_end")
    if ts is None:
        items = (sub.get("items") or {}).get("data") or []
        if items:
            ts = items[0].get("current_period_end")
    return parse_time(ts)


def _invoice_subscription(inv: Any) -> str | None:
    # Newer Stripe API versions moved it under parent.subscription_details.
    sub = inv.get("subscription")
    if sub is None:
        details = (inv.get("parent") or {}).get("subscription_details") or {}
        sub = details.get("subscription")
    if isinstance(sub, Mapping):
        sub = sub.get("id")
    return str_or_none(sub)


def _tax(inv: Any) -> int:
    if inv.get("tax") is not None:
        return int(inv["tax"])
    rows = inv.get("total_taxes") or inv.get("total_tax_amounts") or []
    return sum(int(r.get("amount") or 0) for r in rows)


class StripeProvider(BillingProvider):
    name = "stripe"

    def enabled(self) -> bool:
        s = self.settings
        return bool(s.stripe_secret_key and s.stripe_webhook_secret)

    @property
    def _key(self) -> str:
        return self.settings.stripe_secret_key

    # --- Checkout -----------------------------------------------------------------

    def resolve_coupon(self, code: str) -> str | None:
        found = stripe.PromotionCode.list(api_key=self._key, code=code, active=True, limit=1)
        rows = found.get("data") or []
        return rows[0]["id"] if rows else None

    def create_checkout(
        self,
        db: Session,
        user: User,
        payment: Payment,
        price: ProviderPrice | None,
        seats: int,
        discount: str | None,
    ) -> str:
        if price is None:
            raise ProviderError("Stripe checkout needs a provider price")
        s = self.settings
        founding = service.is_founding_reference(db, payment.reference)
        meta = {
            "user_id": str(user.id),
            "plan": payment.plan,
            "interval": payment.interval or "",
            "reference": payment.reference,
            "founding": "1" if founding else "0",
        }
        back = f"&ref={payment.reference}"
        if payment.organisation_id:
            # PF3a: shown in Stripe and echoed back; attaching reads our payment row.
            meta["org_id"] = payment.organisation_id
            back += f"&org={payment.organisation_id}"
        params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price.provider_price_id, "quantity": seats}],
            "client_reference_id": payment.reference,
            "success_url": f"{s.site_url}/dashboard/billing/?checkout=success{back}",
            "cancel_url": f"{s.site_url}/dashboard/billing/?checkout=canceled{back}",
            "metadata": meta,
            "subscription_data": {"metadata": meta},
            "automatic_tax": {"enabled": bool(s.stripe_tax_enabled)},
            "billing_address_collection": "required",
            "tax_id_collection": {"enabled": True},
            # Stripe's own box mirrors the consent given on our billing page.
            "consent_collection": {"terms_of_service": "required"},
            "custom_text": {
                # The text the buyer accepted on our page (GD5 7.4's box once approved).
                "terms_of_service_acceptance": {
                    "message": consumer.consent_text(payment.consent_version) or consent.STRIPE_MESSAGE
                }
            },
        }
        if discount:
            params["discounts"] = [{"promotion_code": discount}]
        elif founding:
            # One discount per checkout: no codes on top of the founding price,
            # and the session ends with its hold.
            params["expires_at"] = int(time.time()) + FOUNDING_SESSION_S
        else:
            params["allow_promotion_codes"] = True
        customer = service.customer_id(db, user, "stripe")
        if customer:
            params["customer"] = customer
            # Tax ids and the address are saved onto the existing customer.
            params["customer_update"] = {"address": "auto", "name": "auto"}
        else:
            params["customer_email"] = user.email
        try:
            session = stripe.checkout.Session.create(api_key=self._key, **params)
        except stripe.StripeError as exc:
            raise ProviderError(str(exc)) from exc
        payment.provider_ref = session["id"]
        return session["url"]

    # --- Applying Stripe state --------------------------------------------------------

    def _apply_session(self, db: Session, session: Any, event_at: datetime | None) -> None:
        payment = db.scalar(
            select(Payment).where(
                Payment.reference == session.get("client_reference_id"),
                Payment.provider == "stripe",
            )
        )
        meta = session.get("metadata") or {}
        if payment is not None:
            if session.get("status") == "complete" and session.get("payment_status") in (
                "paid",
                "no_payment_required",
            ):
                if session.get("amount_total") is not None:
                    payment.amount = int(session["amount_total"])
                details = session.get("total_details") or {}
                if details.get("amount_tax") is not None:
                    payment.tax_minor = int(details["amount_tax"])
                payment.invoice_id = _id_of(session.get("invoice")) or payment.invoice_id
                # PF2b: who bought it and where (cancellation rights depend on both).
                details = session.get("customer_details") or {}
                country = (details.get("address") or {}).get("country")
                if country:
                    payment.country = str(country).upper()[:2]
                if details.get("tax_ids"):
                    payment.business = True
                payment.provider_subscription_id = (
                    _id_of(session.get("subscription")) or payment.provider_subscription_id
                )
                service.mark_payment_paid(db, payment)
                db.commit()
                # Sessions are created only by this server, so its metadata holds.
                if meta.get("founding") == "1":
                    service.count_founding(db, payment.reference, payment.user_id)
                consumer.payment_paid(db, payment)
            elif session.get("status") == "expired" and payment.status == "pending":
                payment.status = "canceled"
                db.add(payment)
                db.commit()
        sub_id = session.get("subscription")
        if session.get("status") == "complete" and sub_id:
            if isinstance(sub_id, str):
                sub = stripe.Subscription.retrieve(sub_id, api_key=self._key)
            else:
                sub = sub_id
            # Our own session (its id is the one this server created for the
            # payment) links the payment to the subscription it started.
            ours = payment is not None and session.get("id") == payment.provider_ref
            self._apply_subscription(db, sub, event_at, payment if ours else None)

    def _apply_subscription(
        self, db: Session, sub: Any, event_at: datetime | None, origin: Payment | None = None
    ) -> Subscription | None:
        meta = sub.get("metadata") or {}
        existing = service.find_subscription(db, "stripe", sub["id"])
        owner = org_billing.owner_of(existing, origin)
        if owner is not None:
            user_id, organisation_id = owner
        else:
            try:
                user_id = int(meta.get("user_id"))
            except (TypeError, ValueError):
                return None  # not created by our checkout
            organisation_id = None
            # A subscription event ahead of its Checkout Session's: the
            # session links it to the organisation.
            if org_billing.awaiting_link(db, "stripe", meta):
                log.info("stripe subscription %s waits for its organisation checkout", sub["id"])
                return None
        items = (sub.get("items") or {}).get("data") or []
        item = items[0] if items else {}
        price = item.get("price") or {}
        price_id = price.get("id")
        row = service.price_by_provider_id(db, "stripe", price_id)
        founding = False
        if row is not None:
            tier, interval, founding = row.tier, row.interval, row.founding
        elif price_id and price_id == self.settings.stripe_price_pro:
            tier, interval = "pro", "month"  # the original monthly Pro price
        else:
            # A price made by hand in the Stripe dashboard: the metadata our
            # server wrote names the tier, never one sold only by hand.
            tier = str(meta.get("plan") or "")
            interval = (price.get("recurring") or {}).get("interval")
            if tier not in PLANS or not PLANS[tier].purchasable:
                log.warning("stripe subscription %s has no known price; ignored", sub["id"])
                return None
        applied = service.upsert_subscription(
            db,
            provider="stripe",
            provider_subscription_id=sub["id"],
            user_id=user_id,
            tier=tier,
            interval=interval,
            seats=int(item.get("quantity") or 1),
            status=_STATUS.get(sub.get("status", ""), "canceled"),
            current_period_end=_period_end(sub),
            cancel_at_period_end=bool(sub.get("cancel_at_period_end") or sub.get("cancel_at")),
            customer_id=str_or_none(sub.get("customer")),
            currency=str_or_none(sub.get("currency")),
            provider_price_id=str_or_none(price_id),
            founding=founding,
            event_at=event_at,
            organisation_id=organisation_id,
        )
        if applied is not None and founding:
            reference = service.founding_reference(
                db, "stripe", applied.user_id, str_or_none(meta.get("reference")), sub["id"]
            )
            service.count_founding(db, reference, applied.user_id)
        return applied

    def _apply_invoice(self, db: Session, inv: Any) -> bool:
        """A paid renewal invoice (billing_reason subscription_cycle) records
        the renewal; nothing else changes."""
        if inv.get("billing_reason") != "subscription_cycle" or not inv.get("id"):
            return False
        paid_at = (inv.get("status_transitions") or {}).get("paid_at") or inv.get("created")
        return service.record_renewal(
            db, "stripe", _invoice_subscription(inv), parse_time(paid_at), str(inv["id"])
        )

    def verify_payment(self, db: Session, payment: Payment) -> None:
        if not payment.provider_ref:
            return
        session = stripe.checkout.Session.retrieve(payment.provider_ref, api_key=self._key)
        self._apply_session(db, session, None)

    # --- Webhooks ------------------------------------------------------------------------

    def handle_webhook(self, db: Session, body: bytes, headers: Mapping[str, str]) -> str | None:
        signature = next(
            (v for k, v in headers.items() if k.lower() == "stripe-signature"), ""
        )
        try:
            event = stripe.Webhook.construct_event(
                body, signature, self.settings.stripe_webhook_secret
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise WebhookError("invalid Stripe signature") from exc

        kind = event["type"]
        event_id = str(event.get("id") or "")
        if event_id and service.event_seen(db, "stripe", event_id):
            return kind
        occurred = parse_time(event.get("created"))
        obj = event["data"]["object"]
        status = "ignored"
        if kind in ("checkout.session.completed", "checkout.session.expired"):
            self._apply_session(db, obj, occurred)
            status = "applied"
        elif kind in _SUBSCRIPTION_EVENTS:
            # Stripe stamps events to the second, so two can share a time and
            # arrive in either order: apply the subscription as it is now.
            fresh = stripe.Subscription.retrieve(obj["id"], api_key=self._key)
            applied = self._apply_subscription(db, fresh, None)
            status = "applied" if applied is not None else "skipped"
        elif kind in _INVOICE_EVENTS:
            status = "applied" if self._apply_invoice(db, obj) else "ignored"
        if event_id:
            service.record_event(db, "stripe", event_id, kind, occurred, status)
        return kind

    # --- Managing a subscription -------------------------------------------------------------

    def cancel_checkout(self, db: Session, payment: Payment) -> None:
        if payment.provider_ref:
            stripe.checkout.Session.expire(payment.provider_ref, api_key=self._key)

    def cancel_subscription(self, db: Session, sub: Subscription, *, immediately: bool) -> None:
        # Not applied here: customer.subscription.updated / .deleted does (PF2b).
        try:
            if immediately:
                stripe.Subscription.cancel(sub.provider_subscription_id, api_key=self._key)
            else:
                stripe.Subscription.modify(
                    sub.provider_subscription_id, api_key=self._key, cancel_at_period_end=True
                )
        except stripe.StripeError as exc:
            raise ProviderError(str(exc)) from exc

    def refund(
        self,
        db: Session,
        sub: Subscription,
        *,
        charge_id: str | None,
        share_ppm: int | None,
        reason: str,
    ) -> Refund:
        """Refund part or all of one paid invoice (the renewal's by default)
        through its payment intent."""
        try:
            invoice_id = charge_id or sub.renewal_charge_id
            if not invoice_id:
                current = stripe.Subscription.retrieve(sub.provider_subscription_id, api_key=self._key)
                invoice_id = _id_of(current.get("latest_invoice"))
            if not invoice_id:
                raise ProviderError("no invoice to refund")
            inv = stripe.Invoice.retrieve(invoice_id, api_key=self._key)
            if not inv or _invoice_subscription(inv) not in (None, sub.provider_subscription_id):
                raise ProviderError("that invoice belongs to another subscription")
            paid = int(inv.get("amount_paid") or 0)
            if paid <= 0:
                raise ProviderError("nothing was paid on that invoice")
            amount = refund_amount(paid, share_ppm)
            params: dict[str, Any] = {
                "amount": amount,
                "reason": "requested_by_customer",
                "metadata": {"subscription": sub.provider_subscription_id or "", "note": reason[:450]},
            }
            intent, charge = _id_of(inv.get("payment_intent")), _id_of(inv.get("charge"))
            if intent:
                params["payment_intent"] = intent
            elif charge:
                params["charge"] = charge
            else:
                raise ProviderError("no payment on that invoice")
            refund = stripe.Refund.create(api_key=self._key, **params)
        except stripe.StripeError as exc:
            raise ProviderError(str(exc)) from exc
        currency = str(inv.get("currency") or sub.currency or "").upper()
        return Refund(id=str(refund.get("id") or ""), amount_minor=amount, currency=currency)

    def portal_url(self, db: Session, user: User, sub: Subscription) -> str:
        customer = sub.provider_customer_id or service.customer_id(db, user, "stripe")
        if not customer:
            raise ProviderError("no Stripe customer")
        portal = stripe.billing_portal.Session.create(
            api_key=self._key,
            customer=customer,
            return_url=f"{self.settings.site_url}/dashboard/billing/"
            + (f"?org={sub.organisation_id}" if sub.organisation_id else ""),
        )
        return portal["url"]

    def _apply_change(
        self, db: Session, sub: Subscription, price: ProviderPrice, seats: int
    ) -> Subscription:
        try:
            current = stripe.Subscription.retrieve(sub.provider_subscription_id, api_key=self._key)
            item_id = current["items"]["data"][0]["id"]
            updated = stripe.Subscription.modify(
                sub.provider_subscription_id,
                api_key=self._key,
                items=[{"id": item_id, "price": price.provider_price_id, "quantity": seats}],
                # Charge or credit the difference now, as Paddle does.
                proration_behavior="always_invoice",
            )
        except stripe.StripeError as exc:
            raise ProviderError(str(exc)) from exc
        applied = self._apply_subscription(db, updated, None)
        db.refresh(sub)
        return applied or sub

    def list_invoices(
        self, db: Session, user: User, scope: InvoiceScope | None = None
    ) -> list[Invoice]:
        if scope is None:
            customer = service.customer_id(db, user, "stripe")
            if not customer:
                return []
            scope = InvoiceScope(customers=(customer,))
        out = []
        for customer in scope.customers:
            found = stripe.Invoice.list(api_key=self._key, customer=customer, limit=24)
            for inv in found.get("data") or []:
                sub_id = _invoice_subscription(inv)
                if inv.get("status") == "draft" or not scope.keeps(inv["id"], sub_id):
                    continue
                out.append(
                    Invoice(
                        id=inv["id"],
                        number=inv.get("number"),
                        issued_at=parse_time(inv.get("created")),
                        total_minor=int(inv.get("total") or 0),
                        tax_minor=_tax(inv),
                        currency=str(inv.get("currency") or "").upper(),
                        status=str(inv.get("status") or ""),
                        # Served through the API's signed, one-hour link.
                        pdf_url=None,
                        subscription_id=sub_id,
                    )
                )
        return out

    def invoice_pdf_url(
        self, db: Session, user: User, invoice_id: str, scope: InvoiceScope | None = None
    ) -> str:
        try:
            inv = stripe.Invoice.retrieve(invoice_id, api_key=self._key)
        except stripe.StripeError as exc:
            raise ProviderError(str(exc)) from exc
        if scope is None:
            customer = service.customer_id(db, user, "stripe")
            mine = bool(customer) and inv.get("customer") == customer
        else:
            mine = inv.get("customer") in scope.customers and scope.keeps(
                invoice_id, _invoice_subscription(inv)
            )
        if not mine or not inv.get("invoice_pdf"):
            raise ProviderError("not this customer's invoice")
        return inv["invoice_pdf"]

    def charge_usage(
        self,
        db: Session,
        sub: Subscription,
        metric: str,
        quantity: int,
        unit_amount_minor: int,
        description: str,
    ) -> str:
        item = stripe.InvoiceItem.create(
            api_key=self._key,
            customer=sub.provider_customer_id,
            subscription=sub.provider_subscription_id,
            amount=quantity * unit_amount_minor,
            currency=(sub.currency or "USD").lower(),
            description=f"{description} ({quantity} x {metric})",
        )
        return item["id"]

    def create_invoice(self, db: Session, customer: str, lines: list[InvoiceLine]) -> str:
        for line in lines:
            stripe.InvoiceItem.create(
                api_key=self._key,
                customer=customer,
                amount=line.amount_minor * line.quantity,
                currency=line.currency.lower(),
                description=line.description,
            )
        invoice = stripe.Invoice.create(
            api_key=self._key,
            customer=customer,
            collection_method="send_invoice",
            days_until_due=30,
            pending_invoice_items_behavior="include",
            automatic_tax={"enabled": bool(self.settings.stripe_tax_enabled)},
        )
        stripe.Invoice.finalize_invoice(invoice["id"], api_key=self._key)
        return invoice["id"]

    def reconcile(self, db: Session, subs: list[Subscription], payments: list[Payment]) -> int:
        checked = 0
        for payment in payments:
            try:
                self.verify_payment(db, payment)
                checked += 1
            except stripe.StripeError:
                log.exception("reconcile: payment %s", payment.reference)
        for sub in subs:
            if not sub.provider_subscription_id:
                continue
            try:
                fresh = stripe.Subscription.retrieve(sub.provider_subscription_id, api_key=self._key)
                self._apply_subscription(db, fresh, None)
                checked += 1
            except stripe.StripeError:
                log.exception("reconcile: subscription %s", sub.provider_subscription_id)
        return checked
