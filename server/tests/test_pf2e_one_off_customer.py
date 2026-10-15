"""PF2e: a person's one-off payments (PF11's AI credit packs) record the
provider customer they were paid on, so a pack's VAT invoice is on the
person's own invoice list without a subscription of their own, and a second
Stripe pack opens on the first pack's customer.

Who buys packs without a subscription of their own: a trial user, a Team
member on a seat, and the buyer of an organisation whose only Stripe
subscription is the organisation's (PF3e keeps that customer off theirs).
Before PF2e `service.customer_id` read only the person's own subscriptions:
none, so `personal_scope` was None, GET /billing/invoices skipped the
provider, the personal PDF link refused every pack, and each Stripe pack sent
`customer_email`, so Stripe made a new customer for it.

Paddle is tests/mock_paddle.py served in-process (the `paddle` fixture; its
GET /transactions lists by customer_id). Stripe's side is PF3e's stand-in
with one-off sessions added: a completed session reports its `customer`, and
a customer's invoice list holds its packs' invoices beside its subscriptions'.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import Session

from app.billing import org_billing, service
from app.billing.base import InvoiceScope
from app.database import SessionLocal, init_db
from app.models import Payment, User
from app.routers.billing import _pdf_link

from . import test_pf3e_org_stripe_customer as pf3e
from .conftest import CONSENT, TEST_DATABASE_URL, checkout_body, signup
from .org_helpers import _clean_mail_and_caches, assign, join, make_org, me  # noqa: F401  (autouse fixture)
from .project_helpers import Person
from .test_billing import stripe_post
from .test_billing_orgs import org_buy
from .test_billing_pf2 import paddle_post, txn_of

BUYER = pf3e.BUYER
PACK = "credits-5000"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Stripe's side: PF3e's stand-in, with one-off sessions ------------------------------------


class _Stripe(pf3e._Stripe):
    """PF3e's `_Stripe`, plus AI credit packs: a one-off (payment mode)
    session runs on the customer it names, else on a new one (`cus_new_N`),
    exactly as a subscription session does. Stripe makes its invoice
    (`invoice_creation`) on that customer, and the customer's invoice list
    and `Invoice.retrieve` answer it beside its subscriptions' invoices."""

    def __init__(self, monkeypatch):
        super().__init__(monkeypatch)
        self.packs: dict[str, dict] = {}

    def pay_pack(self, *, country: str = "DE") -> tuple[str, str, str]:
        """Complete the last session, a pack's, paid from `country`. Returns
        our reference, the customer it ran on and the pack's invoice id."""
        params = self.last
        assert params["mode"] == "payment" and params["invoice_creation"] == {"enabled": True}, params
        customer = params.get("customer")
        if customer is None:
            self.new_customers += 1
            customer = f"cus_new_{self.new_customers}"
        price = params["line_items"][0]["price_data"]
        net, currency = int(price["unit_amount"]), price["currency"]
        invoice_id = f"in_pack_{len(self.packs) + 1}"
        self.packs[invoice_id] = {
            "id": invoice_id, "number": invoice_id.upper().replace("_", "-"), "customer": customer, "subscription": None,
            "created": int(_now().timestamp()), "total": net + net // 5, "tax": net // 5, "currency": currency,
            "status": "paid", "invoice_pdf": f"https://pay.stripe.test/{invoice_id}.pdf",
        }  # fmt: skip
        self.sessions[params["id"]] = {
            "id": params["id"], "object": "checkout.session", "mode": "payment",
            "client_reference_id": params["client_reference_id"], "status": "complete", "payment_status": "paid",
            "amount_total": net + net // 5, "total_details": {"amount_tax": net // 5}, "subscription": None,
            "invoice": invoice_id, "customer": customer, "metadata": params["metadata"],
            "customer_details": {"address": {"country": country}, "tax_ids": list(self.tax_ids.get(customer, []))},
        }  # fmt: skip
        return params["client_reference_id"], customer, invoice_id

    def _invoices(self, customer, **kw):
        listed = super()._invoices(customer, **kw)
        listed["data"] += [inv for inv in self.packs.values() if inv["customer"] == customer]
        return listed

    def _invoice(self, invoice_id, **kw):
        if invoice_id in self.packs:
            return self.packs[invoice_id]
        return super()._invoice(invoice_id, **kw)


@pytest.fixture()
def on_stripe(client, stripe_prices, monkeypatch) -> _Stripe:
    """Stripe as the checkout provider, its synced prices, and Stripe's side."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "billing_provider", "stripe")
    return _Stripe(monkeypatch)


# --- helpers -----------------------------------------------------------------------------------


def _pack(client, h) -> dict:
    """POST /account/ai/top-ups: the pack's checkout URL and our reference."""
    res = client.post("/account/ai/top-ups", json={"pack": PACK, "currency": "GBP", "consent": CONSENT}, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def _paddle_pack(client, paddle, h, country: str = "GB") -> str:
    """A pack bought on Paddle and its `transaction.completed` delivered
    (signed); returns its transaction id."""
    txn = parse_qs(urlparse(_pack(client, h)["url"]).query)["_ptxn"][0]
    events = paddle.pay(txn, country=country)
    assert [e["event_type"] for e in events] == ["transaction.completed"]
    for ev in events:
        assert paddle_post(client, ev).status_code == 200
    return txn


def _stripe_completed(client, on_stripe, reference: str) -> None:
    """Stripe's signed checkout.session.completed for the pack's session."""
    session = next(s for s in on_stripe.sessions.values() if s["client_reference_id"] == reference)
    event = {"id": f"evt_pf2e_{reference}", "object": "event", "type": "checkout.session.completed",
             "created": int(_now().timestamp()), "data": {"object": session}}  # fmt: skip
    assert stripe_post(client, event).status_code == 200


def _payment(reference: str) -> Payment:
    with SessionLocal() as db:
        return db.scalar(select(Payment).where(Payment.reference == reference))


def _reference(txn: str) -> str:
    with SessionLocal() as db:
        return db.scalar(select(Payment.reference).where(Payment.provider_ref == txn))


def _invoices(client, h, **params) -> list[dict]:
    res = client.get("/billing/invoices", params=params, headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def _opens(client, row_or_link) -> str:
    """Follow a signed PDF link: the provider URL it redirects to (302)."""
    link = row_or_link["pdf_url"] if isinstance(row_or_link, dict) else row_or_link
    res = client.get(link, follow_redirects=False)
    assert res.status_code == 302, (res.status_code, res.text)
    return res.headers["location"]


def _refused(client, user_id: int, provider: str, invoice_id: str) -> bool:
    """A personal PDF link signed for `user_id` (as the list would sign one)
    answers 404."""
    return client.get(_pdf_link(user_id, provider, invoice_id), follow_redirects=False).status_code == 404


def _paddle_customer(paddle, email: str) -> str:
    return next(c["id"] for c in paddle.STATE["customers"].values() if c["email"] == email)


def _row(db, uid: int, plan: str, customer: str | None, *, provider="stripe", status="paid", org_id=None,
         paid_ago=timedelta(days=3)) -> Payment:  # fmt: skip
    """A payment row as a verified checkout left it, with its recorded customer."""
    n = db.scalar(select(Payment.id).order_by(Payment.id.desc()).limit(1)) or 0
    row = Payment(
        user_id=uid, provider=provider, plan=plan, reference=f"tbx_pf2e_{n + 1}", provider_ref=f"ref_pf2e_{n + 1}",
        amount=900, currency="GBP", status=status, paid_at=_now() - paid_ago if status == "paid" else None,
        organisation_id=org_id, provider_customer_id=customer,
    )  # fmt: skip
    db.add(row)
    db.flush()
    return row


# --- 1. Paddle: a trial user's pack -------------------------------------------------------------


def test_paddle_pack_of_a_trial_user_is_on_their_invoices(client, paddle):
    """A Pro trial has no subscription row at Paddle. Their pack's
    `transaction.completed` records the Paddle customer it was paid on; their
    invoice list then holds exactly that transaction's invoice, whose signed
    PDF link opens. Another person's list and PDF links don't."""
    trial = Person(client, "trial@example.com")  # a Pro trial (holds ai.metered)
    other = Person(client, "other@example.com")
    with SessionLocal() as db:
        assert service.customer_id(db, db.get(User, trial.user_id), "paddle") is None

    txn = _paddle_pack(client, paddle, trial.session)
    customer = paddle.STATE["transactions"][txn]["customer_id"]
    assert customer == _paddle_customer(paddle, "trial@example.com")
    pack = _payment(_reference(txn))
    assert (pack.plan, pack.status, pack.provider_customer_id) == ("ai_credits", "paid", customer)
    with SessionLocal() as db:
        user = db.get(User, trial.user_id)
        assert service.customer_id(db, user, "paddle") == customer
        assert org_billing.personal_scope(db, user, "paddle") == InvoiceScope(customers=(customer,))

    rows = _invoices(client, trial.session)
    assert [(r["id"], r["number"]) for r in rows] == [(txn, paddle.STATE["transactions"][txn]["invoice_number"])]
    assert _opens(client, rows[0]).endswith(f"/invoices/{txn}.pdf")

    other_txn = _paddle_pack(client, paddle, other.session)
    assert [r["id"] for r in _invoices(client, other.session)] == [other_txn]
    assert _refused(client, other.user_id, "paddle", txn)  # someone else's pack never opens
    assert _refused(client, trial.user_id, "paddle", other_txn)
    assert _opens(client, _pdf_link(trial.user_id, "paddle", txn)).endswith(f"/invoices/{txn}.pdf")


# --- 2. Paddle: a Team member's pack ------------------------------------------------------------


def test_paddle_team_members_pack_is_theirs_not_the_organisations(client, paddle):
    """The buyer pays Team on Paddle for the organisation (on their own Paddle
    customer, one per e-mail). A member on a named seat buys a pack: their own
    list shows the pack's invoice and not the Team invoice; the
    organisation's list shows the Team invoice and not the pack. The buyer's
    own list holds neither, and a personal PDF link to the Team invoice is
    refused even though it is on the buyer's own customer."""
    buyer = signup(client, "owner@example.com")
    org = make_org(client, buyer)
    co, _ = org_buy(client, buyer, paddle, org["id"])
    team_txn = txn_of(co["url"])
    member = join(client, buyer, org["id"], "member@example.com", seat="named")
    member_id, buyer_id = me(client, member)["id"], me(client, buyer)["id"]

    pack_txn = _paddle_pack(client, paddle, member)
    member_customer = _paddle_customer(paddle, "member@example.com")
    assert member_customer != _paddle_customer(paddle, "owner@example.com")
    assert _payment(_reference(pack_txn)).provider_customer_id == member_customer

    rows = _invoices(client, member)
    assert [r["id"] for r in rows] == [pack_txn]
    assert _opens(client, rows[0]).endswith(f"/invoices/{pack_txn}.pdf")
    rows = _invoices(client, buyer, org_id=org["id"])
    assert [r["id"] for r in rows] == [team_txn]
    assert _opens(client, rows[0]).endswith(f"/invoices/{team_txn}.pdf")
    assert _invoices(client, buyer) == []

    assert _refused(client, member_id, "paddle", team_txn)
    assert _refused(client, buyer_id, "paddle", team_txn)  # the organisation's, on the buyer's own customer
    assert _refused(client, buyer_id, "paddle", pack_txn)


# --- 3. Stripe: the buyer of an organisation buys two packs ---------------------------------------


def test_stripe_packs_of_an_organisation_buyer_share_one_customer(client, on_stripe):
    """The buyer's only Stripe subscription is the organisation's (on its own
    customer, PF3e), and they use one of its seats. The first pack sends
    `customer_email`, so Stripe makes the buyer a customer; the second opens
    on that customer, and no new customer is made. Both invoices are on the
    buyer's own list and neither on the organisation's. The organisation's
    next checkout still opens on the organisation's own customer."""
    buyer, billing, org, uid = pf3e._people(client)
    org_customer = pf3e._org_bought(client, on_stripe, buyer, org["id"], "sub_org")
    assert assign(client, buyer, org["id"], uid, "named").status_code == 200  # AI credits come with the seat
    with SessionLocal() as db:
        assert service.customer_id(db, db.get(User, uid), "stripe") is None

    first = _pack(client, buyer)
    params = on_stripe.last
    assert "customer" not in params and params["customer_email"] == BUYER
    assert org_customer not in pf3e._named(params)
    _, customer, first_invoice = on_stripe.pay_pack()
    assert customer not in (org_customer,) and on_stripe.new_customers == 2
    _stripe_completed(client, on_stripe, first["reference"])
    assert _payment(first["reference"]).provider_customer_id == customer

    second = _pack(client, buyer)
    params = on_stripe.last
    assert params["customer"] == customer and params["customer_update"] == {"address": "auto", "name": "auto"}
    assert "customer_email" not in params and org_customer not in pf3e._named(params)
    _, again, second_invoice = on_stripe.pay_pack()
    assert again == customer and on_stripe.new_customers == 2  # no new customer
    assert pf3e._refresh(client, buyer, second["reference"])["status"] == "paid"
    assert _payment(second["reference"]).provider_customer_id == customer

    on_stripe.invoice_lists.clear()
    rows = _invoices(client, buyer)
    assert on_stripe.invoice_lists == [customer]
    assert sorted(r["id"] for r in rows) == sorted([first_invoice, second_invoice])
    for row in rows:
        assert _opens(client, row) == f"https://pay.stripe.test/{row['id']}.pdf"
    on_stripe.invoice_lists.clear()
    rows = _invoices(client, billing, org_id=org["id"])
    assert on_stripe.invoice_lists == [org_customer] and [r["id"] for r in rows] == ["in_sub_org"]
    assert _refused(client, uid, "stripe", "in_sub_org")  # the organisation's, never through a personal link
    assert _invoices(client, billing) == []

    pf3e._cancel(client, "sub_org")
    pf3e._org_checkout(client, billing, org["id"])
    params = on_stripe.last
    assert params["customer"] == org_customer and customer not in pf3e._named(params)
    with SessionLocal() as db:
        assert service.customer_id(db, db.get(User, uid), "stripe") == customer
        assert org_billing.org_customer(db, org["id"], "stripe") == org_customer
    assert on_stripe.tax_ids == {org_customer: [{"type": "eu_vat", "value": pf3e.VAT_ID}]}


# --- 4. Stripe: a person with their own Pro --------------------------------------------------------


def test_stripe_pack_with_own_pro_opens_on_the_pros_customer(client, on_stripe):
    """A person with their own Pro on `cus_pro`: a pack still opens on
    `cus_pro`, records it, and their invoice scope and list are as before
    (Stripe is asked for `cus_pro` only, which holds the Pro and the pack)."""
    h = signup(client, BUYER)
    uid = me(client, h)["id"]
    with SessionLocal() as db:
        pf3e._sub(db, uid, "pro", "sub_pro", "cus_pro")
        db.commit()
        before = org_billing.personal_scope(db, db.get(User, uid), "stripe")
    assert before == InvoiceScope(customers=("cus_pro",))

    pack = _pack(client, h)
    params = on_stripe.last
    assert params["customer"] == "cus_pro" and "customer_email" not in params
    _, customer, invoice = on_stripe.pay_pack()
    assert customer == "cus_pro" and on_stripe.new_customers == 0
    assert pf3e._refresh(client, h, pack["reference"])["status"] == "paid"
    assert _payment(pack["reference"]).provider_customer_id == "cus_pro"
    with SessionLocal() as db:
        user = db.get(User, uid)
        assert service.customer_id(db, user, "stripe") == "cus_pro"
        assert org_billing.personal_scope(db, user, "stripe") == before

    on_stripe.invoice_lists.clear()
    rows = _invoices(client, h)
    assert on_stripe.invoice_lists == ["cus_pro"]
    assert sorted(r["id"] for r in rows) == sorted(["in_sub_pro", invoice])


def test_stripe_pro_after_a_pack_opens_on_the_packs_customer(client, on_stripe):
    """A trial user's pack made them a Stripe customer. Their Pro checkout,
    and their next pack, open on that customer rather than a new one each."""
    trial = Person(client, BUYER)
    pack = _pack(client, trial.session)
    _, customer, _ = on_stripe.pay_pack()
    _stripe_completed(client, on_stripe, pack["reference"])

    res = client.post("/billing/checkout", json=checkout_body(), headers=trial.session)
    assert res.status_code == 200, res.text
    params = on_stripe.last
    assert params["mode"] == "subscription" and params["customer"] == customer and "customer_email" not in params
    reference, on = on_stripe.pay("sub_pro_after_pack", country="DE")
    assert on == customer and pf3e._refresh(client, trial.session, reference)["status"] == "paid"
    _pack(client, trial.session)
    assert on_stripe.last["customer"] == customer and on_stripe.new_customers == 1
    on_stripe.invoice_lists.clear()
    assert len(_invoices(client, trial.session)) == 2 and on_stripe.invoice_lists == [customer]


# --- 5. Whose customer is the person's own ----------------------------------------------------------


def test_customer_id_ignores_listing_and_organisation_payments(client):
    """Only the person's own paid one-off payments count: never a listing
    plan's payment, an organisation's, a plan's checkout, an unpaid one or
    someone else's. On Stripe, a pack recorded on a customer an
    organisation's subscription uses is not the person's either (PF3e). A
    person with a subscription of their own keeps its customer, and their
    invoice scope adds their packs' customers to it."""
    h = signup(client, BUYER)
    uid = me(client, h)["id"]
    other = me(client, signup(client, "other@example.com"))["id"]
    org = make_org(client, h)
    with SessionLocal() as db:
        user = db.get(User, uid)
        _row(db, uid, "listing_standard", "cus_supplier")  # a supplier's listing plan (PF8b)
        _row(db, uid, "team", "cus_org", org_id=org["id"])  # an organisation's Team (PF3e)
        _row(db, uid, "ai_credits", "cus_org_item", org_id=org["id"])  # any one-off row naming an organisation
        _row(db, uid, "pro", "cus_plan")  # a plan's checkout: its subscription row is what counts
        _row(db, uid, "ai_credits", "cus_pending", status="pending", paid_ago=timedelta(0))
        _row(db, other, "ai_credits", "cus_other")
        _row(db, uid, "ai_credits", None, paid_ago=timedelta(hours=1))  # paid before PF2e: nothing recorded
        _row(db, uid, "ai_credits", "ctm_paddle", provider="paddle")
        db.commit()
        assert service.customer_id(db, user, "stripe") is None
        assert org_billing.personal_scope(db, user, "stripe") is None
        assert service.customer_id(db, user, "paddle") == "ctm_paddle"  # each provider its own

        _row(db, uid, "ai_credits", "cus_pack_old", paid_ago=timedelta(days=2))
        _row(db, uid, "ai_credits", "cus_pack", paid_ago=timedelta(days=1))
        db.commit()
        assert service.customer_id(db, user, "stripe") == "cus_pack"  # the latest pack's
        assert org_billing.personal_scope(db, user, "stripe") == InvoiceScope(customers=("cus_pack", "cus_pack_old"))

        # A pack on a customer that an organisation's subscription uses (a
        # session opened before PF3e): never the person's on Stripe.
        pf3e._sub(db, uid, "team", "sub_org", "cus_shared", org_id=org["id"])
        _row(db, uid, "ai_credits", "cus_shared", paid_ago=timedelta(minutes=5))
        db.commit()
        assert service.customer_id(db, user, "stripe") == "cus_pack"
        assert "cus_shared" not in org_billing.personal_scope(db, user, "stripe").customers

        # Their own subscription's customer wins, as before PF2e (even an ended one).
        pf3e._sub(db, uid, "pro", "sub_pro", "cus_pro", status="canceled", ends_in=-timedelta(days=1))
        db.commit()
        assert service.customer_id(db, user, "stripe") == "cus_pro"
        scope = org_billing.personal_scope(db, user, "stripe")
        assert scope.customers == ("cus_pro", "cus_pack", "cus_pack_old")
        assert org_billing.org_customer(db, org["id"], "stripe") is None  # cus_shared holds the person's pack


# --- 6. The column ----------------------------------------------------------------------------------


@pytest.fixture()
def pg_engine():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    yield engine
    engine.dispose()


@pytest.mark.parametrize("dialect", ["sqlite", pytest.param("postgresql", marks=pytest.mark.postgres)])
def test_pf2e_column_added_by_init_db(dialect, request, tmp_path):
    """A database whose `payments` table is master's (no
    `provider_customer_id`) gains the column at this branch's `init_db`,
    its rows read NULL (nothing recorded, no back-fill), and a second
    `init_db` runs no DDL on it."""
    if dialect == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'master.db'}")
    else:
        engine = request.getfixturevalue("pg_engine")
    try:
        init_db(engine, seed=False)
        with Session(engine) as db:
            user = User(email="before@example.com", hashed_password="x")
            db.add(user)
            db.flush()
            db.add(Payment(user_id=user.id, provider="paddle", plan="ai_credits", reference="tbx_before", amount=900,
                           currency="GBP", status="paid", paid_at=_now()))  # fmt: skip
            db.commit()
        with engine.begin() as conn:  # the table as master's models made it
            conn.execute(text("ALTER TABLE payments DROP COLUMN provider_customer_id"))
        assert "provider_customer_id" not in {c["name"] for c in inspect(engine).get_columns("payments")}

        init_db(engine, seed=False)
        cols = {c["name"]: c for c in inspect(engine).get_columns("payments")}
        assert "provider_customer_id" in cols and cols["provider_customer_id"]["nullable"]
        assert getattr(cols["provider_customer_id"]["type"], "length", None) == 128
        with Session(engine) as db:
            row = db.scalar(select(Payment).where(Payment.reference == "tbx_before"))
            assert row.provider_customer_id is None
            row.provider_customer_id = "ctm_after"
            db.commit()

        ddl: list[str] = []

        def seen(_conn, _cursor, statement, *_args):
            if statement.lstrip().upper().startswith("ALTER"):
                ddl.append(statement)

        event.listen(engine, "before_cursor_execute", seen)
        try:
            init_db(engine, seed=False)
        finally:
            event.remove(engine, "before_cursor_execute", seen)
        assert ddl == []
        with Session(engine) as db:
            assert db.scalar(select(Payment.provider_customer_id).where(Payment.reference == "tbx_before")) == "ctm_after"
    finally:
        engine.dispose()
