"""AI credit packs bought on the website through PF2's one-off checkout.

    start(db, user, "credits-5000", "GBP", consent_version) -> (url, reference)

The server picks the price (credits.json, GD7 placeholders); a `payments` row
(plan "ai_credits") and an `ai_top_ups` row share one reference. The credits
arrive only when the provider's own state says paid — a signed webhook or the
refresh after checkout — through `billing.service.PAID_HOOKS`, once per
reference (the ledger is unique per top-up reference).
"""

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..billing import providers, service as billing
from ..billing.base import ProviderError
from ..billing.consent import CONSENT_VERSION
from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock
from ..models import Payment, User
from . import credits
from .models import AiTopUp

ITEM = "ai_credits"
RETURN_PATH = "dashboard/cloud"


def packs_json(currency: str) -> list[dict]:
    out = []
    for p in credits.packs():
        price = (p.get("prices") or {}).get(currency.upper())
        if price is not None:
            out.append({"id": p["id"], "credits": int(p["credits"]), "amount_minor": int(price), "currency": currency.upper()})
    return out


def start(db: Session, user: User, pack_id: str, currency: str, consent_version: str) -> tuple[str, str]:
    if consent_version != CONSENT_VERSION:
        raise ContractError("validation_failed", 422, "The purchase terms changed. Reload the page and accept them again.", {"fields": [{"field": "consent"}]})
    plan = credits.plan_of(db, user)
    if credits.FEATURE not in plan.features:
        raise ContractError(
            "plan_required", 403, "AI credits come with Pro, Studio, Team and the trial.",
            {"feature": credits.FEATURE, "plan": plan.id, "plan_needed": credits.plan_needed(plan)},
        )
    pack = credits.pack(pack_id)
    currency = (currency or "").upper()
    price = ((pack or {}).get("prices") or {}).get(currency)
    if pack is None or price is None:
        raise ContractError("validation_failed", 422, "Choose one of the credit packs on this page.", {"fields": [{"field": "pack"}]})
    adapter = providers.checkout_provider(get_settings())
    if adapter is None:
        raise ContractError("unavailable", 503, "Online payment isn't available yet.", {})
    reference = f"tbx_{secrets.token_hex(12)}"
    payment = Payment(
        user_id=user.id, provider=adapter.name, plan=ITEM, reference=reference, amount=int(price), currency=currency,
        interval=None, seats=1, consent_version=consent_version, consent_at=datetime.now(timezone.utc),
    )
    description = f"Truebex AI credits ({int(pack['credits']):,})"
    try:
        url = adapter.create_one_time_checkout(db, user, payment, description, RETURN_PATH)
    except ProviderError:
        raise ContractError("provider_unavailable", 502, "The payment provider didn't respond. Please try again.", {})
    db.add(payment)
    db.add(
        AiTopUp(
            reference=reference, user_id=user.id, pack=pack["id"], credits=int(pack["credits"]), amount_minor=int(price),
            currency=currency, state="pending", created_at=clock.now(),
        )
    )
    db.commit()
    return url, reference


def on_paid(db: Session, payment: Payment) -> None:
    """billing PAID_HOOK: credit the pack a verified payment bought (once)."""
    if payment.plan != ITEM:
        return
    top_up = db.get(AiTopUp, payment.reference)
    if top_up is None or top_up.state == "credited":
        return
    user = db.get(User, payment.user_id)
    if user is None:
        return
    credits.add_top_up(db, user, int(top_up.credits), payment.reference)
    top_up.state = "credited"
    top_up.credited_at = clock.now()


billing.PAID_HOOKS.append(on_paid)
billing.ONE_OFF_ITEMS.add(ITEM)
