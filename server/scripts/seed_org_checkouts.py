r"""PF3e: which Stripe customer an organisation's checkout, its buyer's own
Pro and AI top-up, the two portals and the two invoice lists use, run through
the app's own billing code with Stripe's side stood in for in this process
(no keys, nothing sent anywhere), on a scratch database.

    cd server
    $env:DATABASE_URL="sqlite:///./pf3e-test.db"; $env:EU_WITHDRAWAL_ENABLED="true"
    .venv\Scripts\python.exe scripts\seed_org_checkouts.py --email pf3e@example.com

It writes, now (UTC):

* the buyer's account and a billing member's (`<name>.billing@<domain>`),
  password `password123` unless --password;
* the organisation "PF3e Studio", owned by the buyer, with the billing member,
  and a second one, "PF3e Studio South";
* Stripe prices for Team (annual, GBP) and Pro (monthly, GBP), stand-ins for
  the ones sync_prices.py makes.

Then, through the app's code (PF2's Stripe adapter, PF3a's organisation
billing, PF11's top-up):

1. Team x3 for PF3e Studio, paid from Germany with its VAT id DE123456789;
2. the buyer's own Pro, paid from Germany without a VAT id, and whether PF2b's
   EU withdrawal is offered for it (EU_WITHDRAWAL_ENABLED);
3. the buyer's AI top-up checkout (not paid);
4. the billing member adds a seat (3 to 4);
5. the organisation's portal, opened by the billing member, and the buyer's
   own portal; the organisation's invoices and the buyer's own;
6. the organisation's subscription ends; the billing member buys Team again
   and pays (entering the VAT id only if Checkout asks for one);
7. the buyer opens a Team checkout for PF3e Studio South (not paid).

Stripe's stand-in runs each Checkout Session on the customer it names, else on
a new one (`cus_sim_N`), saves a VAT id entered at checkout onto that
customer (Checkout asks a customer that has one for none), and reports a
customer's saved tax ids on its later sessions, as Stripe Checkout does. It
prints the customer each checkout opens on, each payment's business flag,
the customer each portal and invoice list is opened for, and what each
customer holds. Run it once per scratch database.
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

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Payment, ProviderPrice, Subscription, User  # noqa: E402
from app.orgs.models import Organisation  # noqa: E402
from app.plans import PLANS  # noqa: E402
from app.security import hash_password  # noqa: E402

ORG = "PF3e Studio"
SECOND_ORG = "PF3e Studio South"
VAT_ID = "DE123456789"
TEAM_PRICE = "price_seed_pf3e_team_gbp"
PRO_PRICE = "price_seed_pf3e_pro_gbp"


def _user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def _account(db: Session, email: str, password: str) -> User:
    user = _user(db, email)
    if user is None:
        user = User(email=email.strip().lower(), hashed_password=hash_password(password))
        db.add(user)
        db.flush()
    return user


def billing_email(email: str) -> str:
    name, _, domain = email.strip().lower().partition("@")
    return f"{name}.billing@{domain}"


def seed(db: Session, email: str, password: str) -> tuple[User, User, Organisation, Organisation]:
    from app.orgs import service as orgs

    now = datetime.now(timezone.utc)
    buyer = _account(db, email, password)
    billing = _account(db, billing_email(email), password)
    if db.scalar(select(Organisation).where(Organisation.created_by == buyer.id, Organisation.name == ORG)) is not None:
        raise SystemExit(f"{email} already has {ORG}: delete the scratch database to run this again")
    for tier, interval, price_id in (("team", "year", TEAM_PRICE), ("pro", "month", PRO_PRICE)):
        if db.scalar(select(ProviderPrice).where(ProviderPrice.provider_price_id == price_id)) is None:
            db.add(ProviderPrice(provider="stripe", tier=tier, interval=interval, currency="GBP",
                                 amount_minor=PLANS[tier].price(interval, "GBP").amount_minor, provider_price_id=price_id))  # fmt: skip
    org, _ = orgs.create(db, buyer, ORG, now)
    orgs.add_member(db, org, billing, "billing", now, actor=buyer.id, via="invite")
    db.commit()
    second, _ = orgs.create(db, buyer, SECOND_ORG, now)
    return buyer, billing, org, second


class _StripeStandIn:
    """Stripe's side, in this process only (see the module docstring)."""

    def __init__(self) -> None:
        import stripe

        self.params: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.subscriptions: dict[str, dict] = {}
        self.tax_ids: dict[str, list[dict]] = {}
        self.opened: list[str] = []  # the customer of each portal session and invoice list
        stripe.checkout.Session.create = self._create
        stripe.checkout.Session.retrieve = lambda session_id, **_kw: self.sessions[session_id]
        stripe.Subscription.retrieve = lambda sub_id, **_kw: self.subscriptions[sub_id]
        stripe.Subscription.modify = self._modify
        stripe.billing_portal.Session.create = self._portal
        stripe.Invoice.list = self._invoices

    def _create(self, **params):
        session_id = f"cs_seed_pf3e_{len(self.params) + 1}"
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
        customer = params.get("customer") or f"cus_sim_{len(self.tax_ids) + 1}"
        if vat_id and not self.tax_ids.get(customer):
            self.tax_ids[customer] = [{"type": "eu_vat", "value": vat_id}]
        self.tax_ids.setdefault(customer, [])
        sub_id = f"sub_sim_{len(self.subscriptions) + 1}"
        line = params["line_items"][0]
        item = {"id": f"si_{sub_id}", "quantity": line["quantity"], "price": {"id": line["price"]},
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

    def _modify(self, sub_id, items, **_kw):
        item = self.subscriptions[sub_id]["items"]["data"][0]
        item["price"], item["quantity"] = {"id": items[0]["price"]}, items[0]["quantity"]
        return self.subscriptions[sub_id]

    def _portal(self, customer, **_kw):
        self.opened.append(customer)
        return {"url": f"https://billing.stripe.test/p/{customer}"}

    def _invoices(self, customer, **_kw):
        self.opened.append(customer)
        return {"data": [
            {"id": f"in_{s['id']}", "customer": customer, "subscription": s["id"], "status": "paid", "total": 0,
             "tax": 0, "currency": "gbp", "created": int(datetime.now(timezone.utc).timestamp())}
            for s in self.subscriptions.values() if s["customer"] == customer
        ]}  # fmt: skip

    def holds(self, customer: str, names: dict[str, str]) -> str:
        """What a customer's Stripe account shows: its subscriptions."""
        subs = [names.get(sub_id, sub_id) for sub_id, s in self.subscriptions.items() if s["customer"] == customer]
        return ", ".join(subs) or "nothing"


def checkouts(db: Session, buyer: User, billing: User, org: Organisation, second: Organisation) -> None:
    from app.ai import topups
    from app.billing import consumer, org_billing, service
    from app.billing.consent import CONSENT_VERSION
    from app.billing.providers import get_provider
    from app.config import get_settings

    s = get_settings()
    if not (s.stripe_secret_key and s.stripe_webhook_secret):
        s.stripe_secret_key, s.stripe_webhook_secret = "sk_test_seed_pf3e", "whsec_seed_pf3e"  # this process only
    s.billing_provider = "stripe"  # this process only: the top-up's checkout provider
    stripe = _StripeStandIn()
    provider = get_provider("stripe", s)
    names: dict[str, str] = {}  # Stripe subscription id -> what it is, for the "holds" lines

    def open_checkout(user: User, tier: str, *, organisation: Organisation | None = None, seats: int = 1) -> Payment:
        """As POST /billing/checkout makes one: an organisation's purchase is a business one (PF3a)."""
        interval = "year" if tier == "team" else "month"
        price = db.scalar(select(ProviderPrice).where(ProviderPrice.provider_price_id == (TEAM_PRICE if tier == "team" else PRO_PRICE)))
        now = datetime.now(timezone.utc)
        payment = Payment(
            user_id=user.id, provider="stripe", plan=tier, reference=f"tbx_{secrets.token_hex(12)}",
            amount=price.amount_minor * seats, currency="GBP", status="pending", interval=interval, seats=seats,
            consent_version=CONSENT_VERSION, consent_at=now, business=organisation is not None,
            organisation_id=organisation.id if organisation is not None else None,
        )  # fmt: skip
        provider.create_checkout(db, user, payment, price, seats, None)
        db.add(payment)
        db.commit()
        return payment

    def paid(payment: Payment, label: str, *, vat_id: str | None = None) -> tuple[str, str]:
        customer, sub_id = stripe.pay(payment, country="DE", vat_id=vat_id)
        names[sub_id] = label
        provider.verify_payment(db, payment)
        db.refresh(payment)
        return customer, sub_id

    print(f"buyer {buyer.email}: no Stripe customer yet; organisation {org.name}, billing member {billing.email}")

    team = open_checkout(buyer, "team", organisation=org, seats=3)
    print(f"organisation Team checkout {team.reference}: opens on {stripe.opens_on(team)}")
    org_customer, org_sub = paid(team, f"Team for {org.name}", vat_id=VAT_ID)
    print(f"  paid from DE with VAT id {VAT_ID} on {org_customer}: business {team.business}")

    pro = open_checkout(buyer, "pro")
    print(f"buyer's own Pro checkout {pro.reference}: opens on {stripe.opens_on(pro)}")
    pro_customer, pro_sub = paid(pro, "the buyer's own Pro")
    tax = ", ".join(t["value"] for t in stripe.tax_ids[pro_customer]) or "none"
    print(f"  paid from DE without a VAT id on {pro_customer} (its saved tax ids: {tax}): business {pro.business}")
    until = consumer.withdrawal_until(db, service.find_subscription(db, "stripe", pro_sub))
    switch = "" if s.eu_withdrawal_enabled else " (EU_WITHDRAWAL_ENABLED is off)"
    offered = f"offered until {until.strftime('%Y-%m-%d %H:%M UTC')}" if until else "not offered"
    print(f"  EU withdrawal for the buyer's own Pro: {offered}{switch}")

    _, reference = topups.start(db, buyer, "credits-5000", "GBP", CONSENT_VERSION)
    top_up = db.scalar(select(Payment).where(Payment.reference == reference))
    print(f"buyer's AI top-up checkout {reference}: opens on {stripe.opens_on(top_up)}")

    sub = org_billing.managed_subscription(db, org.id)
    org_billing.require_billing(db, org.id, billing)
    provider.change_subscription(db, sub, seats=4)
    db.refresh(sub)
    print(f"organisation seats 3 -> {sub.seats}, by {billing.email}: subscription {sub.provider_subscription_id} "
          f"on {sub.provider_customer_id}")  # fmt: skip

    provider.portal_url(db, billing, org_billing.managed_subscription(db, org.id))
    seen = stripe.opened[-1]
    print(f"organisation portal opened by {billing.email}: customer {seen} (holds: {stripe.holds(seen, names)})")
    provider.portal_url(db, buyer, service.managed_subscription(db, buyer))
    seen = stripe.opened[-1]
    print(f"buyer's own portal: customer {seen} (holds: {stripe.holds(seen, names)})")

    for label, user, scope in (
        ("organisation invoices", billing, org_billing.org_scope(db, org.id, "stripe")),
        ("buyer's own invoices", buyer, org_billing.personal_scope(db, buyer, "stripe")),
    ):
        stripe.opened.clear()
        listed = provider.list_invoices(db, user, scope)
        print(f"{label}: Stripe asked for {', '.join(stripe.opened)}; listed {', '.join(i.id for i in listed) or 'none'}")

    stripe.subscriptions[org_sub]["status"] = "canceled"
    provider.reconcile(db, [sub], [])
    again = open_checkout(billing, "team", organisation=org, seats=3)
    print(f"organisation subscription ended; Team again by {billing.email}: opens on {stripe.opens_on(again)}")
    customer, _ = paid(again, f"Team for {org.name} (again)", vat_id=VAT_ID)  # entered only if Checkout asks
    saved = ", ".join(t["value"] for t in stripe.tax_ids[customer])
    print(f"  paid from DE on {customer} (its saved tax ids: {saved}): business {again.business}")
    other = open_checkout(buyer, "team", organisation=second, seats=3)
    print(f"second organisation {second.name}, Team by the buyer: opens on {stripe.opens_on(other)}")
    print("Stripe customers: " + "; ".join(
        f"{c} ({', '.join(t['value'] for t in ids) or 'no tax id'})" for c, ids in stripe.tax_ids.items()
    ))  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--email", required=True, help="the buyer's sign-in address")
    ap.add_argument("--password", default="password123", help="for new accounts (default password123)")
    args = ap.parse_args(argv)
    init_db()
    with SessionLocal() as db:
        buyer, billing, org, second = seed(db, args.email, args.password)
        checkouts(db, buyer, billing, org, second)
    return 0


if __name__ == "__main__":
    sys.exit(main())
