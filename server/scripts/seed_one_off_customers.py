r"""PF2e: which provider customer each AI credit pack is paid on, and what each
person's and organisation's invoice list holds, run through the app's own
billing code on a scratch database. Paddle's side is tests/mock_paddle.py,
Stripe's is stood in for in this process: no keys, nothing sent anywhere.

    cd server
    # PowerShell window 1: the Paddle stand-in (its state lives while it runs)
    .venv\Scripts\python.exe -m uvicorn tests.mock_paddle:app --port 8098
    # PowerShell window 2
    $env:DATABASE_URL="sqlite:///./pf2e-test.db"; $env:PADDLE_API_BASE="http://127.0.0.1:8098"
    .venv\Scripts\python.exe scripts\seed_one_off_customers.py --email pf2e@example.com

Without PADDLE_API_BASE the mock runs inside this process instead: the same
lines, but the API cannot list those Paddle invoices afterwards.

It writes, now (UTC), with password `password123` unless --password:

* `<email>`: a Pro trial (as POST /licence/trial starts one), no subscription
  of their own;
* `<name>.buyer@<domain>` owns "PF2e Studio" and `<name>.member@<domain>`
  holds a named seat in it;
* `<name>.stripe@<domain>` owns "PF2e Stripe Studio" and holds a named seat;
  `<name>.pro@<domain>` has nobody's seat;
* Stripe prices for Team (annual, GBP) and Pro (monthly, GBP), stand-ins for
  the ones sync_prices.py makes; Paddle's are synced into the mock.

Then, through the app's code (PF2's adapters, PF3a's organisation billing,
PF11's top-up), each checkout paid on the stand-in and applied as the
return page's refresh applies it (`verify_payment`):

Paddle (the default provider)
1. the trial user buys a pack, paid from GB;
2. the buyer buys Team x3 for PF2e Studio; the member buys a pack;
3. the invoice lists GET /billing/invoices would show: the trial user's, the
   member's, PF2e Studio's (`?org_id=`) and the buyer's own.
Stripe
4. the Stripe buyer buys Team x3 for PF2e Stripe Studio (their only Stripe
   subscription), then two packs;
5. the Stripe buyer's own invoices and the organisation's;
6. the organisation's Team ends and the buyer opens a Team checkout again;
7. the Pro user buys their own Pro, then a pack; their own invoices.

It prints the customer each checkout opens on, the customer each payment
records, and the customers each invoice list asks the provider for. Run it
once per scratch database (and per mock: Paddle keeps one customer per
e-mail address).
"""

import argparse
import contextlib
import io
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
from scripts.seed_org_checkouts import _StripeStandIn  # noqa: E402  (PF3e's)

PACK = "credits-5000"
ORG = "PF2e Studio"
STRIPE_ORG = "PF2e Stripe Studio"
TEAM_PRICE = "price_seed_pf2e_team_gbp"
PRO_PRICE = "price_seed_pf2e_pro_gbp"
PADDLE_SECRET = "pdl_ntfset_mock_secret"  # the mock's default MOCK_PADDLE_WEBHOOK_SECRET


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _account(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        user = User(email=email, hashed_password=hash_password(password))
        db.add(user)
        db.flush()
    return user


def people(email: str) -> dict[str, str]:
    name, _, domain = email.strip().lower().partition("@")
    return {"trial": f"{name}@{domain}", **{k: f"{name}.{k}@{domain}" for k in ("buyer", "member", "stripe", "pro")}}


def _recorded(payment: Payment) -> str:
    # getattr: the same script runs on code from before PF2e, for contrast.
    return getattr(payment, "provider_customer_id", "(no such column)") or "nothing"


class _Stripe(_StripeStandIn):
    """PF3e's stand-in, plus AI credit packs: a one-off session runs on the
    customer it names, else on a new one (`cus_sim_N`), whose invoice list
    then holds the pack's invoice (`invoice_creation`)."""

    def __init__(self) -> None:
        super().__init__()
        self.packs: dict[str, dict] = {}

    def pay_pack(self, payment: Payment, *, country: str) -> tuple[str, str]:
        """Complete the pack's session; returns (the customer, the pack's invoice)."""
        params = self.params[payment.provider_ref]
        customer = params.get("customer") or f"cus_sim_{len(self.tax_ids) + 1}"
        self.tax_ids.setdefault(customer, [])
        invoice_id = f"in_pack_{len(self.packs) + 1}"
        amount = int(params["line_items"][0]["price_data"]["unit_amount"])
        self.packs[invoice_id] = {
            "id": invoice_id, "customer": customer, "subscription": None, "status": "paid", "total": amount,
            "tax": 0, "currency": "gbp", "created": int(_now().timestamp()),
        }  # fmt: skip
        self.sessions[payment.provider_ref] = {
            "id": payment.provider_ref, "object": "checkout.session", "mode": "payment",
            "client_reference_id": payment.reference, "status": "complete", "payment_status": "paid",
            "amount_total": amount, "total_details": {"amount_tax": 0}, "subscription": None, "invoice": invoice_id,
            "customer": customer, "metadata": params["metadata"],
            "customer_details": {"address": {"country": country}, "tax_ids": list(self.tax_ids[customer])},
        }  # fmt: skip
        return customer, invoice_id

    def _invoices(self, customer, **kw):
        listed = super()._invoices(customer, **kw)
        listed["data"] += [inv for inv in self.packs.values() if inv["customer"] == customer]
        return listed


class Run:
    def __init__(self, db: Session, emails: dict[str, str], password: str) -> None:
        from app.config import get_settings

        self.db, self.emails, self.password = db, emails, password
        self.s = get_settings()
        self.now = _now()
        self.what: dict[str, str] = {}  # provider invoice id -> what it bills, for the "listed" lines

    # --- people and organisations ------------------------------------------------------------

    def seed(self) -> None:
        db, e = self.db, self.emails
        trial = db.scalar(select(User).where(User.email == e["trial"]))
        if trial is not None and db.scalar(select(Payment.id).where(Payment.user_id == trial.id)) is not None:
            raise SystemExit(f"{e['trial']} already bought a pack: delete the scratch database to run this again")
        self.users = {k: _account(db, email, self.password) for k, email in e.items()}
        trial = self.users["trial"]
        db.add(Subscription(user_id=trial.id, plan="pro", provider="trial", status="active",
                            current_period_end=self.now + timedelta(days=self.s.trial_days)))  # fmt: skip
        trial.trial_used_at = self.now
        for tier, interval, price_id in (("team", "year", TEAM_PRICE), ("pro", "month", PRO_PRICE)):
            if db.scalar(select(ProviderPrice).where(ProviderPrice.provider_price_id == price_id)) is None:
                db.add(ProviderPrice(provider="stripe", tier=tier, interval=interval, currency="GBP",
                                     amount_minor=PLANS[tier].price(interval, "GBP").amount_minor, provider_price_id=price_id))  # fmt: skip
        db.commit()

    def org(self, owner: User, name: str, member: User | None = None) -> Organisation:
        from app.orgs import service as orgs

        org, _ = orgs.create(self.db, owner, name, self.now)
        if member is not None:
            orgs.add_member(self.db, org, member, "member", self.now, actor=owner.id, via="invite")
        self.db.commit()
        return org

    def seat(self, org: Organisation, user: User) -> None:
        from app.orgs import seats

        with contextlib.redirect_stderr(io.StringIO()):  # the console mail "you have a seat"
            seats.assign(self.db, org, org.created_by, user.id, "named", self.now)

    # --- checkouts, as the routers open them -------------------------------------------------------

    def checkout(self, provider, user: User, tier: str, *, org: Organisation | None = None, seats: int = 1) -> Payment:
        """As POST /billing/checkout opens one (an organisation's purchase is a business one, PF3a)."""
        from app.billing import pricing
        from app.billing.consent import CONSENT_VERSION

        interval = "year" if tier == "team" else "month"
        if provider.name == "stripe":
            price = self.db.scalar(select(ProviderPrice).where(
                ProviderPrice.provider_price_id == (TEAM_PRICE if tier == "team" else PRO_PRICE)))  # fmt: skip
        else:
            price = pricing.resolve(self.db, provider.name, tier, interval, "GBP", False)
        payment = Payment(
            user_id=user.id, provider=provider.name, plan=tier, reference=f"tbx_{secrets.token_hex(12)}",
            amount=price.amount_minor * seats, currency="GBP", status="pending", interval=interval, seats=seats,
            consent_version=CONSENT_VERSION, consent_at=_now(), business=org is not None,
            organisation_id=org.id if org is not None else None,
        )  # fmt: skip
        provider.create_checkout(self.db, user, payment, price, seats, None)
        self.db.add(payment)
        self.db.commit()
        self.what[payment.provider_ref] = f"Team for {org.name}" if org else f"{user.email}'s own {PLANS[tier].name}"
        return payment

    def pack(self, user: User) -> Payment:
        """As POST /account/ai/top-ups opens one (PF11)."""
        from app.ai import topups
        from app.billing.consent import CONSENT_VERSION

        _, reference = topups.start(self.db, user, PACK, "GBP", CONSENT_VERSION)
        payment = self.db.scalar(select(Payment).where(Payment.reference == reference))
        self.what[payment.provider_ref] = f"{user.email}'s AI pack"
        return payment

    def applied(self, provider, payment: Payment) -> Payment:
        """The return page's refresh (POST /billing/payments/{reference}/refresh)."""
        provider.verify_payment(self.db, payment)
        self.db.refresh(payment)
        return payment

    def invoices(self, provider, label: str, user: User, scope) -> None:
        if scope is None:
            print(f"  {label}: no customer, so {provider.name.title()} is not asked; listed none")
            return
        rows = provider.list_invoices(self.db, user, scope)
        listed = ", ".join(f"{r.id} ({self.what.get(r.id, '?')})" for r in rows)
        print(f"  {label}: {provider.name.title()} asked for {', '.join(scope.customers)}; listed {listed or 'none'}")

    # --- Paddle ------------------------------------------------------------------------------------

    def paddle(self) -> None:
        from app.billing import org_billing, providers
        from scripts import sync_prices

        s, u = self.s, self.users
        s.billing_provider = "paddle"  # this process only
        s.paddle_api_key = s.paddle_api_key or "pdl_mock_seed_pf2e"
        s.paddle_webhook_secret = s.paddle_webhook_secret or PADDLE_SECRET
        if s.paddle_api_base:
            import httpx

            where, pay_page = s.paddle_api_url, httpx.Client(base_url=s.paddle_api_url, timeout=30)
        else:
            from fastapi.testclient import TestClient

            from tests import mock_paddle

            mock_paddle.WEBHOOK["send"] = False
            providers._paddle_client = lambda st: TestClient(
                mock_paddle.app, base_url=st.paddle_api_url,
                headers={"Authorization": f"Bearer {st.paddle_api_key}", "Paddle-Version": "1"},
            )  # fmt: skip
            where, pay_page = "the mock in this process", TestClient(mock_paddle.app)
        with contextlib.redirect_stdout(io.StringIO()):
            synced = sync_prices.sync_paddle(s)
        sync_prices.store(self.db, "paddle", synced)
        provider = providers.get_provider("paddle", s)

        def pay(payment: Payment, country: str = "GB") -> Payment:
            res = pay_page.post(f"/pay/{payment.provider_ref}", data={"country": country}, follow_redirects=False)
            assert res.status_code == 303, (res.status_code, res.text)
            return self.applied(provider, payment)

        print(f"Paddle, the default provider ({where})")
        trial = u["trial"]
        print(f"trial user {trial.email}: Pro trial, no subscription of their own")
        pack = self.pack(trial)
        pay(pack)
        print(f"  AI pack {pack.reference} (transaction {pack.provider_ref}): {pack.status}; "
              f"the payment records customer {_recorded(pack)}")  # fmt: skip

        org = self.org(u["buyer"], ORG, u["member"])
        team = pay(self.checkout(provider, u["buyer"], "team", org=org, seats=3))
        sub = org_billing.managed_subscription(self.db, org.id)
        print(f"organisation {ORG}: Team x3 bought by {u['buyer'].email}: {team.status}, "
              f"subscription {sub.provider_subscription_id} on {sub.provider_customer_id}")  # fmt: skip
        self.seat(org, u["member"])
        member_pack = pay(self.pack(u["member"]))
        print(f"  {u['member'].email} on a named seat: AI pack {member_pack.reference} (transaction "
              f"{member_pack.provider_ref}): {member_pack.status}; "
              f"the payment records customer {_recorded(member_pack)}")  # fmt: skip

        print("invoice lists (GET /billing/invoices):")
        self.invoices(provider, trial.email, trial, org_billing.personal_scope(self.db, trial, "paddle"))
        self.invoices(provider, u["member"].email, u["member"], org_billing.personal_scope(self.db, u["member"], "paddle"))
        self.invoices(provider, f"{ORG} (?org_id=)", u["buyer"], org_billing.org_scope(self.db, org.id, "paddle"))
        self.invoices(provider, u["buyer"].email, u["buyer"], org_billing.personal_scope(self.db, u["buyer"], "paddle"))

    # --- Stripe ------------------------------------------------------------------------------------

    def stripe(self) -> None:
        from app.billing import org_billing, providers, service

        s, u = self.s, self.users
        if not (s.stripe_secret_key and s.stripe_webhook_secret):
            s.stripe_secret_key, s.stripe_webhook_secret = "sk_test_seed_pf2e", "whsec_seed_pf2e"  # this process only
        s.billing_provider = "stripe"  # this process only: the top-up's checkout provider
        stripe = _Stripe()
        provider = providers.get_provider("stripe", s)

        def pay(payment: Payment) -> Payment:
            if payment.plan in service.ONE_OFF_ITEMS:
                _, invoice_id = stripe.pay_pack(payment, country="DE")
                self.what[invoice_id] = self.what[payment.provider_ref]
            else:
                _, sub_id = stripe.pay(payment, country="DE")
                self.what[f"in_{sub_id}"] = self.what[sub_id] = self.what[payment.provider_ref]
            return self.applied(provider, payment)

        print("Stripe (stood in for in this process)")
        buyer = u["stripe"]
        org = self.org(buyer, STRIPE_ORG)
        team = pay(self.checkout(provider, buyer, "team", org=org, seats=3))
        sub = org_billing.managed_subscription(self.db, org.id)
        self.seat(org, buyer)
        print(f"{buyer.email}: Team x3 for {STRIPE_ORG} on {sub.provider_customer_id} ({team.status}), their only "
              f"Stripe subscription; they hold one of its seats")  # fmt: skip
        for n in ("first", "second"):
            pack = self.pack(buyer)
            print(f"  {n} AI pack {pack.reference}: opens on {stripe.opens_on(pack)}")
            pay(pack)
            print(f"    paid; the payment records customer {_recorded(pack)}")
        self.invoices(provider, f"{buyer.email}'s own invoices", buyer, org_billing.personal_scope(self.db, buyer, "stripe"))
        self.invoices(provider, f"{STRIPE_ORG}'s invoices", buyer, org_billing.org_scope(self.db, org.id, "stripe"))
        stripe.subscriptions[sub.provider_subscription_id]["status"] = "canceled"
        provider.reconcile(self.db, [sub], [])
        again = self.checkout(provider, buyer, "team", org=org, seats=3)
        print(f"  {STRIPE_ORG}'s Team ended; Team again: opens on {stripe.opens_on(again)}")

        pro_user = u["pro"]
        pro = pay(self.checkout(provider, pro_user, "pro"))
        own = service.managed_subscription(self.db, pro_user)
        print(f"{pro_user.email}: their own Pro on {own.provider_customer_id} ({pro.status})")
        pack = self.pack(pro_user)
        print(f"  AI pack {pack.reference}: opens on {stripe.opens_on(pack)}")
        pay(pack)
        print(f"    paid; the payment records customer {_recorded(pack)}")
        self.invoices(provider, f"{pro_user.email}'s own invoices", pro_user,
                      org_billing.personal_scope(self.db, pro_user, "stripe"))  # fmt: skip

        held = {}
        for sub_id, row in stripe.subscriptions.items():
            held.setdefault(row["customer"], []).append(self.what.get(sub_id, sub_id))
        for row in stripe.packs.values():
            held.setdefault(row["customer"], []).append("an AI pack")
        print(f"Stripe customers made: {len(stripe.tax_ids)}")
        for customer in stripe.tax_ids:
            print(f"  {customer}: {', '.join(held.get(customer, [])) or 'nothing'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--email", required=True, help="the trial user's sign-in address (the others are made from it)")
    ap.add_argument("--password", default="password123", help="for new accounts (default password123)")
    args = ap.parse_args(argv)
    init_db()
    with SessionLocal() as db:
        run = Run(db, people(args.email), args.password)
        run.seed()
        run.paddle()
        run.stripe()
    return 0


if __name__ == "__main__":
    sys.exit(main())
