"""Wayl: one-time IQD payment links (QiCard, FIB, ZainCash). Dormant.

Retired from the website and the plan catalogue (PF2: billing runs through
the UK company); the code stays behind WAYL_ENABLED=false and its tests keep
running under the flag so it does not rot. Each paid link buys one 30-day Pro
period. API: https://api.thewayl.com/reference
"""

import json
import logging
from collections.abc import Mapping
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Payment, ProviderPrice, Subscription, User
from ..plans import get_plan
from . import service
from .base import BillingProvider, Invoice, NotSupported, WebhookError

log = logging.getLogger("truebex.billing.wayl")

WAYL_PAID = {"Complete", "Delivered"}
WAYL_FAILED = {"Cancelled", "Rejected", "Returned"}


def make_client(s: Settings) -> httpx.Client:
    return httpx.Client(
        base_url=s.wayl_api_base,
        headers={"X-WAYL-AUTHENTICATION": s.wayl_api_key},
        timeout=30,
    )


def _client(s: Settings) -> httpx.Client:
    from . import providers  # the registry; tests patch providers._wayl_client

    return providers._wayl_client(s)


def reference_from_webhook(body: dict[str, Any]) -> str | None:
    for container in (body, body.get("data") or {}):
        ref = container.get("referenceId") if isinstance(container, dict) else None
        if isinstance(ref, str) and ref:
            return ref
    return None


class WaylProvider(BillingProvider):
    name = "wayl"

    def enabled(self) -> bool:
        s = self.settings
        return bool(s.wayl_enabled and s.wayl_api_key and s.wayl_webhook_secret)

    def create_checkout(
        self,
        db: Session,
        user: User,
        payment: Payment,
        price: ProviderPrice | None,
        seats: int,
        discount: str | None,
    ) -> str:
        s = self.settings
        plan = get_plan(payment.plan)
        body = {
            "env": s.wayl_env,
            "referenceId": payment.reference,
            "total": payment.amount,
            "currency": "IQD",
            "customParameter": f"user:{user.id}",
            "lineItem": [
                {
                    "label": f"Truebex {plan.name} - 30 days",
                    "amount": payment.amount,
                    "type": "increase",
                }
            ],
            "webhookUrl": f"{s.api_url}/billing/webhooks/wayl",
            "webhookSecret": s.wayl_webhook_secret,
            "redirectionUrl": f"{s.site_url}/dashboard/billing/?checkout=success",
            "linkExpiresIn": "24h",
        }
        with _client(s) as client:
            res = client.post("/api/v1/links", json=body)
            res.raise_for_status()
            data = res.json()["data"]
        payment.provider_ref = str(data.get("id") or "")
        return data["url"]

    def fetch_status(self, reference: str) -> dict[str, Any]:
        with _client(self.settings) as client:
            res = client.get(f"/api/v1/links/{reference}")
            res.raise_for_status()
            return res.json()["data"]

    def sync(self, db: Session, payment: Payment) -> str:
        """Ask Wayl for the link's real status and apply it. Returns the status.

        Webhook bodies are never trusted: they only tell us which link to check.
        """
        link = self.fetch_status(payment.reference)
        status = str(link.get("status", ""))
        try:
            total = int(float(link.get("total", 0)))
        except (TypeError, ValueError):
            total = 0
        if status in WAYL_PAID and total >= payment.amount:
            service.grant_wayl_period(db, payment)
        elif status in WAYL_FAILED and payment.status == "pending":
            payment.status = "failed"
            db.add(payment)
            db.commit()
        return status

    def verify_payment(self, db: Session, payment: Payment) -> None:
        self.sync(db, payment)

    def handle_webhook(self, db: Session, body: bytes, headers: Mapping[str, str]) -> str | None:
        """A hint only: returns the link's status fetched from Wayl, or None
        for an unknown reference (acknowledged so Wayl stops retrying)."""
        try:
            parsed = json.loads(body)
        except ValueError as exc:
            raise WebhookError("expected JSON") from exc
        reference = reference_from_webhook(parsed if isinstance(parsed, dict) else {})
        payment = (
            db.scalar(
                select(Payment).where(Payment.reference == reference, Payment.provider == "wayl")
            )
            if reference
            else None
        )
        if payment is None:
            return None
        return self.sync(db, payment)

    def portal_url(self, db: Session, user: User, sub: Subscription) -> str:
        raise NotSupported("Wayl periods are prepaid; there is nothing to manage")

    def _apply_change(
        self, db: Session, sub: Subscription, price: ProviderPrice, seats: int
    ) -> Subscription:
        raise NotSupported("Wayl periods are prepaid; buy another period instead")

    def list_invoices(self, db: Session, user: User, scope=None) -> list[Invoice]:
        return []

    def charge_usage(
        self,
        db: Session,
        sub: Subscription,
        metric: str,
        quantity: int,
        unit_amount_minor: int,
        description: str,
    ) -> str:
        raise NotSupported("Wayl has no subscriptions to charge")

    def reconcile(self, db: Session, subs: list[Subscription], payments: list[Payment]) -> int:
        for payment in payments:
            self.sync(db, payment)
        return len(payments)
