"""Stripe: card subscriptions through Stripe Checkout, with Stripe Tax, and
business invoices (Enterprise, PF7 commissions, PF8 listing fees).

Truebex Ltd is the seller here: Stripe Tax calculates and collects, the
registrations and returns stay with the company (see PF2's provider
decision). The original monthly Pro price (STRIPE_PRICE_PRO) keeps mapping
to Pro for existing subscribers.
"""

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Payment, ProviderPrice, Subscription, User
from . import consent, service
from .base import (
    BillingProvider,
    Invoice,
    InvoiceLine,
    ProviderError,
    WebhookError,
    parse_time,
    str_or_none,
)

log = logging.getLogger("truebex.billing.stripe")

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


def _period_end(sub: Any) -> datetime | None:
    # Newer Stripe API versions moved current_period_end onto the items.
    ts = sub.get("current_period_end")
    if ts is None:
        items = (sub.get("items") or {}).get("data") or []
        if items:
            ts = items[0].get("current_period_end")
    return parse_time(ts)


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
        meta = {
            "user_id": str(user.id),
            "plan": payment.plan,
            "interval": payment.interval or "",
            "reference": payment.reference,
            "founding": "1" if service.is_founding_reference(db, payment.reference) else "0",
        }
        params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price.provider_price_id, "quantity": seats}],
            "client_reference_id": payment.reference,
            "success_url": f"{s.site_url}/dashboard/billing/?checkout=success&ref={payment.reference}",
            "cancel_url": f"{s.site_url}/dashboard/billing/?checkout=canceled&ref={payment.reference}",
            "metadata": meta,
            "subscription_data": {"metadata": meta},
            "automatic_tax": {"enabled": bool(s.stripe_tax_enabled)},
            "billing_address_collection": "required",
            "tax_id_collection": {"enabled": True},
            # Stripe's own box mirrors the consent given on our billing page.
            "consent_collection": {"terms_of_service": "required"},
            "custom_text": {
                "terms_of_service_acceptance": {"message": consent.STRIPE_MESSAGE}
            },
        }
        if discount:
            params["discounts"] = [{"promotion_code": discount}]
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
                payment.invoice_id = str_or_none(session.get("invoice")) or payment.invoice_id
                service.mark_payment_paid(db, payment)
                db.commit()
                service.consume_founding(db, payment, founding_hint=meta.get("founding") == "1")
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
            self._apply_subscription(db, sub, event_at)

    def _apply_subscription(
        self, db: Session, sub: Any, event_at: datetime | None
    ) -> Subscription | None:
        meta = sub.get("metadata") or {}
        existing = db.scalar(
            select(Subscription).where(
                Subscription.provider == "stripe",
                Subscription.provider_subscription_id == sub["id"],
            )
        )
        try:
            user_id = existing.user_id if existing else int(meta.get("user_id", ""))
        except ValueError:
            return None  # not created by our checkout
        items = (sub.get("items") or {}).get("data") or []
        item = items[0] if items else {}
        price = item.get("price") or {}
        price_id = price.get("id")
        row = service.price_by_provider_id(db, "stripe", price_id)
        if row is not None:
            tier, interval = row.tier, row.interval
        elif price_id and price_id == self.settings.stripe_price_pro:
            tier, interval = "pro", "month"  # the original monthly Pro price
        else:
            tier = meta.get("plan") or "pro"
            interval = (price.get("recurring") or {}).get("interval")
        return service.upsert_subscription(
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
            founding=meta.get("founding") == "1",
            event_at=event_at,
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
            applied = self._apply_subscription(db, obj, occurred)
            status = "applied" if applied is not None else "stale"
        if event_id:
            service.record_event(db, "stripe", event_id, kind, occurred, status)
        return kind

    # --- Managing a subscription -------------------------------------------------------------

    def portal_url(self, db: Session, user: User, sub: Subscription) -> str:
        customer = sub.provider_customer_id or service.customer_id(db, user, "stripe")
        if not customer:
            raise ProviderError("no Stripe customer")
        portal = stripe.billing_portal.Session.create(
            api_key=self._key,
            customer=customer,
            return_url=f"{self.settings.site_url}/dashboard/billing/",
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

    def list_invoices(self, db: Session, user: User) -> list[Invoice]:
        customer = service.customer_id(db, user, "stripe")
        if not customer:
            return []
        found = stripe.Invoice.list(api_key=self._key, customer=customer, limit=24)
        out = []
        for inv in found.get("data") or []:
            if inv.get("status") == "draft":
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
                    pdf_url=inv.get("invoice_pdf"),
                )
            )
        return out

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
            self.verify_payment(db, payment)
            checked += 1
        for sub in subs:
            if sub.provider_subscription_id:
                fresh = stripe.Subscription.retrieve(sub.provider_subscription_id, api_key=self._key)
                self._apply_subscription(db, fresh, None)
                checked += 1
        return checked
