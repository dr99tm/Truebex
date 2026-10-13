r"""Seed a supplier owner's listing checkouts beside their own Pro plan, for
trying PF8a on a local API in a scratch database: PF2b's consumer rules skip
the listing plan, and the listing sync matches each checkout to its own
subscription. No listing fee exists until GD7, so the paid listing checkout
is written through the app's models, as PF2's Stripe webhook leaves it.

    cd server
    $env:DATABASE_URL="sqlite:///./pf8a-test.db"; $env:MAIL_BACKEND="console"
    $env:LEGAL_WORDING_APPROVED="true"; $env:SUBSCRIPTION_NOTICES_ENABLED="true"; $env:SUBSCRIPTION_RULES_FROM="2020-01-01"
    .venv\Scripts\python.exe scripts\seed_listing_checkouts.py --email pf8a@example.com
    .venv\Scripts\python.exe -m app.worker --run billing.subscription_notices supplier.listing.sync
    .venv\Scripts\python.exe scripts\seed_listing_checkouts.py --email pf8a@example.com --show

Writes, now (UTC):

* the account (password `password123` unless --password) if it does not exist;
* a verified supplier it owns, "PF8a Listing" (GB);
* the Stripe price `price_listing_standard_gbp` (GBP 49.00 a month) for the
  Standard listing plan, a stand-in for the one sync_prices.py makes once GD7
  sets the fee;
* two Standard listing checkouts: one paid, whose payment names its Stripe
  subscription (renewing in 2 days), and one never paid, opened 25 hours ago;
* the owner's own Pro plan on Stripe, paid, renewing in 2 days.

Each paid payment then goes through consumer.payment_paid, as PF2's adapter
does once a checkout is paid. With LEGAL_WORDING_APPROVED=true and the
console mail backend, only Pro's order confirmation is printed.

--show prints the listing checkouts, the supplier's plan, the renewal
reminders sent and the order confirmations.

PF8b (a separate block, its own supplier): which Stripe customer a listing
checkout and the owner's own Pro checkout open on, with Stripe's side stood
in for in this process (no keys, nothing sent anywhere):

    $env:DATABASE_URL="sqlite:///./pf8b-test.db"; $env:EU_WITHDRAWAL_ENABLED="true"
    .venv\Scripts\python.exe scripts\seed_listing_checkouts.py --email pf8b@example.com --pf8b
    .venv\Scripts\python.exe scripts\seed_listing_checkouts.py --email pf8b@example.com --checkouts

--pf8b writes the account, a verified supplier "PF8b Listing" (GB, VAT id
GB123456789, no billing customer yet), the owner's earlier Pro plan on their
own Stripe customer `cus_seed_pro` (ended 10 days ago, so they can buy it
again), and Stripe prices for Standard's listing fee and for Pro.

--checkouts runs the app's own code: the portal's listing checkout for
Standard (`supplier.listing.choose`, with GD7's fee stood in as GBP 49.00),
completed from GB with the VAT id; the listing sync; then the owner's Pro
checkout (PF2's Stripe `create_checkout`), completed from Germany without a
VAT id. Stripe's stand-in runs each session on the customer it names, else on
a new one, saves a VAT id onto that customer, and reports a customer's saved
tax ids on its later sessions, as Stripe Checkout does. It prints the
customer each checkout opens on, each payment's business flag, the
supplier's billing customer and whether Pro offers the EU withdrawal. Run it
once per scratch database.
"""

import argparse
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app  # noqa: E402, F401  (before SQLAlchemy: keeps platform off WMI on Windows)
import app.main  # noqa: E402, F401  (every feature's tables, so foreign keys resolve)
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.billing import consumer  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.market.models import Supplier, SupplierMember  # noqa: E402
from app.models import Payment, ProviderPrice, Subscription, SubscriptionNotice, User  # noqa: E402
from app.plans import PLANS  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.supplier.models import ListingSubscription  # noqa: E402

FEE = 4900  # GBP 49.00, a placeholder until GD7
PRICE_ID = "price_listing_standard_gbp"


def _user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def _supplier_of(db: Session, user: User) -> Supplier | None:
    return db.scalar(
        select(Supplier)
        .join(SupplierMember, SupplierMember.supplier_id == Supplier.supplier_id)
        .where(SupplierMember.user_id == user.id, SupplierMember.role == "owner")
    )


def seed(db: Session, email: str, password: str) -> dict:
    now = datetime.now(timezone.utc)
    user = _user(db, email)
    if user is None:
        user = User(email=email.strip().lower(), hashed_password=hash_password(password))
        db.add(user)
        db.flush()
    if _supplier_of(db, user) is not None:
        raise SystemExit(f"{email} already owns a supplier: delete the scratch database to seed again")

    supplier = Supplier(
        supplier_id=secrets.token_hex(16), name="PF8a Listing", legal_name="PF8a Listing Ltd", country="GB",
        contact_email=user.email, status="verified", verified_at=now, created_at=now, updated_at=now,
    )  # fmt: skip
    db.add(supplier)
    db.flush()
    db.add(SupplierMember(supplier_id=supplier.supplier_id, user_id=user.id, role="owner", created_at=now))
    if db.scalar(select(ProviderPrice).where(ProviderPrice.provider_price_id == PRICE_ID)) is None:
        db.add(ProviderPrice(provider="stripe", tier="listing_standard", interval="month", currency="GBP",
                             amount_minor=FEE, provider_price_id=PRICE_ID))  # fmt: skip

    def checkout(plan: str, sub_id: str | None, *, opened: datetime) -> Payment:
        listing = plan.startswith("listing_")
        payment = Payment(
            user_id=user.id, provider="stripe", plan=plan, reference=f"{'lst' if listing else 'tbx'}_{secrets.token_hex(12)}",
            provider_ref=f"cs_seed_{secrets.token_hex(8)}", currency="GBP", interval="month", seats=1,
            amount=FEE if listing else PLANS[plan].price("month", "GBP").amount_minor,
            status="paid" if sub_id else "pending", paid_at=opened if sub_id else None, created_at=opened,
            provider_subscription_id=sub_id, country="GB",
        )  # fmt: skip
        db.add(payment)
        return payment

    def subscription(plan: str, sub_id: str, price_id: str | None) -> None:
        db.add(
            Subscription(
                user_id=user.id, plan=plan, provider="stripe", status="active", interval="month", currency="GBP",
                seats=1, provider_subscription_id=sub_id, provider_customer_id="cus_seed_pf8a",
                provider_price_id=price_id, current_period_end=now + timedelta(days=2),
            )
        )  # fmt: skip

    tag = secrets.token_hex(4)
    listing_sub, pro_sub = f"sub_seed_listing_{tag}", f"sub_seed_pro_{tag}"
    paid_listing = checkout("listing_standard", listing_sub, opened=now - timedelta(minutes=30))
    unpaid_listing = checkout("listing_standard", None, opened=now - timedelta(hours=25))
    pro = checkout("pro", pro_sub, opened=now - timedelta(minutes=20))
    subscription("listing_standard", listing_sub, PRICE_ID)
    subscription("pro", pro_sub, None)
    for payment, opened in ((paid_listing, now - timedelta(minutes=30)), (unpaid_listing, now - timedelta(hours=25))):
        db.add(
            ListingSubscription(
                supplier_id=supplier.supplier_id, plan="standard", provider="stripe", status="checkout",
                currency="GBP", amount=FEE, payment_ref=payment.reference, created_by=user.id, created_at=opened,
            )
        )  # fmt: skip
    db.commit()

    # PF2's adapter calls this once a checkout is paid (LEGAL_WORDING_APPROVED decides).
    confirmed = [p.plan for p in (paid_listing, pro) if consumer.payment_paid(db, p)]
    return {"supplier": supplier.supplier_id, "listing": paid_listing.reference, "unpaid": unpaid_listing.reference,
            "pro": pro.reference, "confirmed": confirmed}  # fmt: skip


def show(db: Session, email: str) -> None:
    user = _user(db, email)
    supplier = _supplier_of(db, user) if user else None
    if supplier is None:
        raise SystemExit(f"nothing seeded for {email}")
    print(f"supplier {supplier.name}: listing plan {supplier.listing_plan or 'founding (default)'}")
    rows = db.scalars(
        select(ListingSubscription)
        .where(ListingSubscription.supplier_id == supplier.supplier_id)
        .order_by(ListingSubscription.id)
    )
    for row in rows:
        payment = db.scalar(select(Payment).where(Payment.reference == row.payment_ref))
        print(
            f"  listing checkout {row.payment_ref} (payment {payment.status if payment else '-'}): "
            f"{row.status}, subscription {row.provider_subscription_id or '-'}"
        )
    notices = db.execute(
        select(Subscription.plan, SubscriptionNotice.kind)
        .join(Subscription, Subscription.id == SubscriptionNotice.subscription_id)
        .where(Subscription.user_id == user.id)
        .order_by(SubscriptionNotice.id)
    ).all()
    print(f"renewal reminders sent: {', '.join(f'{plan} ({kind})' for plan, kind in notices) or 'none'}")
    confirmed = db.scalars(
        select(Payment.plan).where(Payment.user_id == user.id, Payment.confirmation_sent_at.is_not(None))
    ).all()
    print(f"order confirmations sent: {', '.join(confirmed) or 'none'}")


# --- PF8b: the listing plan on the supplier's own Stripe customer ------------------------------------

PF8B_SUPPLIER = "PF8b Listing"
PF8B_VAT_ID = "GB123456789"
PF8B_PRO_CUSTOMER = "cus_seed_pro"
PF8B_PRO_PRICE = "price_seed_pro_gbp"


def seed_pf8b(db: Session, email: str, password: str) -> dict:
    now = datetime.now(timezone.utc)
    user = _user(db, email)
    if user is None:
        user = User(email=email.strip().lower(), hashed_password=hash_password(password))
        db.add(user)
        db.flush()
    if _supplier_of(db, user) is not None:
        raise SystemExit(f"{email} already owns a supplier: delete the scratch database to seed again")
    supplier = Supplier(
        supplier_id=secrets.token_hex(16), name=PF8B_SUPPLIER, legal_name=f"{PF8B_SUPPLIER} Ltd", country="GB",
        vat_id=PF8B_VAT_ID, contact_email=user.email, status="verified", verified_at=now, created_at=now, updated_at=now,
    )  # fmt: skip
    db.add(supplier)
    db.flush()
    db.add(SupplierMember(supplier_id=supplier.supplier_id, user_id=user.id, role="owner", created_at=now))
    pro_amount = PLANS["pro"].price("month", "GBP").amount_minor
    for tier, amount, price_id in (("listing_standard", FEE, PRICE_ID), ("pro", pro_amount, PF8B_PRO_PRICE)):
        if db.scalar(select(ProviderPrice).where(ProviderPrice.provider_price_id == price_id)) is None:
            db.add(ProviderPrice(provider="stripe", tier=tier, interval="month", currency="GBP", amount_minor=amount,
                                 provider_price_id=price_id))  # fmt: skip
    ended = now - timedelta(days=10)
    db.add(
        Subscription(
            user_id=user.id, plan="pro", provider="stripe", status="canceled", interval="month", currency="GBP",
            seats=1, provider_subscription_id=f"sub_seed_pro_{secrets.token_hex(4)}", provider_customer_id=PF8B_PRO_CUSTOMER,
            provider_price_id=PF8B_PRO_PRICE, current_period_end=ended, updated_at=ended,
        )
    )  # fmt: skip
    db.commit()
    return {"supplier": supplier.supplier_id}


class _StripeStandIn:
    """Stripe's side of the Checkout Sessions, in this process only. A
    session runs on the customer it names, else on a new one; a VAT id
    entered at checkout is saved onto that customer (Checkout asks a customer
    that has one for none), and a session reports its customer's saved tax
    ids (`customer_details.tax_ids`)."""

    def __init__(self) -> None:
        import stripe

        self.params: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.subscriptions: dict[str, dict] = {}
        self.tax_ids: dict[str, list[dict]] = {PF8B_PRO_CUSTOMER: []}
        stripe.checkout.Session.create = self._create
        stripe.checkout.Session.retrieve = lambda session_id, **_kw: self.sessions[session_id]
        stripe.Subscription.retrieve = lambda sub_id, **_kw: self.subscriptions[sub_id]

    def _create(self, **params):
        session_id = f"cs_seed_pf8b_{len(self.params) + 1}"
        self.params[session_id] = params
        return {"id": session_id, "url": f"https://checkout.stripe.test/{session_id}"}

    def opens_on(self, payment: Payment) -> str:
        params = self.params[payment.provider_ref]
        if params.get("customer"):
            return f"customer {params['customer']}"
        return f"a new customer (customer_email {params['customer_email']})"

    def pay(self, payment: Payment, *, country: str, vat_id: str | None = None) -> tuple[str, str]:
        """Complete the payment's session; returns (the customer, its subscription)."""
        params = self.params[payment.provider_ref]
        customer = params.get("customer") or f"cus_sim_{len(self.tax_ids)}"
        if vat_id and not self.tax_ids.get(customer):
            self.tax_ids[customer] = [{"type": "gb_vat", "value": vat_id}]
        self.tax_ids.setdefault(customer, [])
        sub_id = f"sub_sim_{len(self.subscriptions) + 1}"
        item = {"id": f"si_{sub_id}", "quantity": 1, "price": {"id": params["line_items"][0]["price"], "recurring": {"interval": "month"}},
                "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())}  # fmt: skip
        self.subscriptions[sub_id] = {
            "id": sub_id, "object": "subscription", "customer": customer, "currency": "gbp", "status": "active",
            "cancel_at_period_end": False, "metadata": params["metadata"], "items": {"data": [item]},
        }  # fmt: skip
        self.sessions[payment.provider_ref] = {
            "id": payment.provider_ref, "object": "checkout.session", "client_reference_id": payment.reference,
            "status": "complete", "payment_status": "paid", "subscription": sub_id, "invoice": f"in_{sub_id}",
            "customer": customer, "metadata": params["metadata"],
            "customer_details": {"address": {"country": country}, "tax_ids": list(self.tax_ids[customer])},
        }  # fmt: skip
        return customer, sub_id


def checkouts(db: Session, email: str) -> None:
    from app.billing import service
    from app.billing.consent import CONSENT_VERSION
    from app.billing.providers import get_provider
    from app.config import get_settings
    from app.market import listing as market_listing
    from app.supplier import listing
    from app.supplier.common import Member

    user = _user(db, email)
    supplier = _supplier_of(db, user) if user else None
    if supplier is None or supplier.name != PF8B_SUPPLIER:
        raise SystemExit(f"seed {email} with --pf8b first")
    if db.scalar(select(ListingSubscription).where(ListingSubscription.supplier_id == supplier.supplier_id)) is not None:
        raise SystemExit("--checkouts already ran here: delete the scratch database to run it again")
    s = get_settings()
    if not (s.stripe_secret_key and s.stripe_webhook_secret):
        s.stripe_secret_key, s.stripe_webhook_secret = "sk_test_seed_pf8b", "whsec_seed_pf8b"  # this process only
    stripe = _StripeStandIn()
    provider = get_provider("stripe", s)
    every = dict(market_listing.plans())
    every["standard"] = market_listing.ListingPlan("standard", every["standard"].name, every["standard"].commission_bp, {"GBP": FEE})
    market_listing.plans = lambda: every  # GD7's fee, stood in
    market_listing.plan_of = lambda sup: every.get(sup.listing_plan or "founding") or every["founding"]

    print(f"owner {user.email}: earlier Pro on {PF8B_PRO_CUSTOMER}; supplier {supplier.name}, VAT id {supplier.vat_id}, "
          f"billing customer {supplier.billing_customer_id or '-'}")  # fmt: skip
    listing.choose(db, Member(user=user, supplier=supplier, role="owner"), "standard")
    row = listing.current(db, supplier)
    paid = db.scalar(select(Payment).where(Payment.reference == row.payment_ref))
    print(f"listing checkout {paid.reference}: opens on {stripe.opens_on(paid)}")
    customer, _ = stripe.pay(paid, country="GB", vat_id=PF8B_VAT_ID)
    provider.verify_payment(db, paid)
    db.refresh(paid)
    print(f"  paid from GB with VAT id {PF8B_VAT_ID} on {customer}: business {paid.business}")
    listing.sync(db, datetime.now(timezone.utc), supplier.supplier_id)
    db.refresh(supplier)
    print(f"  supplier billing customer after the sync: {supplier.billing_customer_id}")

    price = db.scalar(select(ProviderPrice).where(ProviderPrice.provider_price_id == PF8B_PRO_PRICE))
    now = datetime.now(timezone.utc)
    pro = Payment(
        user_id=user.id, provider="stripe", plan="pro", reference=f"tbx_{secrets.token_hex(12)}", amount=price.amount_minor,
        currency="GBP", status="pending", interval="month", seats=1, consent_version=CONSENT_VERSION, consent_at=now,
        business=False,  # as PF2's checkout sets it: the business box unticked
    )  # fmt: skip
    provider.create_checkout(db, user, pro, price, 1, None)
    db.add(pro)
    db.commit()
    print(f"Pro checkout {pro.reference}: opens on {stripe.opens_on(pro)}")
    customer, sub_id = stripe.pay(pro, country="DE")
    provider.verify_payment(db, pro)
    db.refresh(pro)
    tax = ", ".join(t["value"] for t in stripe.tax_ids[customer]) or "none"
    print(f"  paid from DE without a VAT id on {customer} (its saved tax ids: {tax}): business {pro.business}")
    until = consumer.withdrawal_until(db, service.find_subscription(db, "stripe", sub_id))
    switch = "" if s.eu_withdrawal_enabled else " (EU_WITHDRAWAL_ENABLED is off)"
    print(f"  EU withdrawal: {'offered until ' + until.strftime('%Y-%m-%d %H:%M UTC') if until else 'not offered'}{switch}")
    print("Stripe customers: " + "; ".join(
        f"{c} ({', '.join(t['value'] for t in ids) or 'no tax id'})" for c, ids in stripe.tax_ids.items()
    ))  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--email", required=True, help="the supplier owner's sign-in address")
    ap.add_argument("--password", default="password123", help="for a new account (default password123)")
    ap.add_argument("--show", action="store_true", help="print what was seeded and what the jobs did")
    ap.add_argument("--pf8b", action="store_true", help="seed PF8b's supplier and the owner's earlier Pro instead")
    ap.add_argument("--checkouts", action="store_true", help="PF8b: open and pay the listing and Pro checkouts")
    args = ap.parse_args(argv)
    init_db()
    with SessionLocal() as db:
        if args.checkouts:
            checkouts(db, args.email)
            return 0
        if args.pf8b:
            out = seed_pf8b(db, args.email, args.password)
            print(f"seeded supplier {out['supplier']} ({PF8B_SUPPLIER}) for {args.email}, Pro ended on {PF8B_PRO_CUSTOMER}")
            return 0
        if args.show:
            show(db, args.email)
            return 0
        out = seed(db, args.email, args.password)
    print(
        f"seeded supplier {out['supplier']} for {args.email}: paid listing checkout {out['listing']}, "
        f"unpaid listing checkout {out['unpaid']}, Pro checkout {out['pro']}"
    )
    print(f"order confirmations sent now: {', '.join(out['confirmed']) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
