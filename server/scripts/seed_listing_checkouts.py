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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--email", required=True, help="the supplier owner's sign-in address")
    ap.add_argument("--password", default="password123", help="for a new account (default password123)")
    ap.add_argument("--show", action="store_true", help="print what was seeded and what the jobs did")
    args = ap.parse_args(argv)
    init_db()
    with SessionLocal() as db:
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
