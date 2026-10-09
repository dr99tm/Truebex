"""Subscription consumer rules (PF2b; guides/GD5 §7.1-7.4): who may cancel,
get a renewal refund or withdraw, the notices the DMCC Act 2024 asks for, and
the confirmation on a durable medium. Built now, switched off by default:

* SUBSCRIPTION_NOTICES_ENABLED, from SUBSCRIPTION_RULES_FROM (UK, DMCC Act
  2024 Part 4 Chapter 2): renewal reminders, the trial-end notice and the
  renewal cooling-off refund after an annual renewal.
* EU_WITHDRAWAL_ENABLED: the withdrawal function of Directive 2011/83/EU
  Art. 11a for EU consumers inside the withdrawal period.
* LEGAL_WORDING_APPROVED: every GD5 §7.4 draft (key information at checkout,
  the consent variants, the business box, the trial notice, the order
  confirmation e-mail). Until then today's placeholder consent stays.
* CONSENT_VARIANT: QS-17's digital-content or service consent.

The easy exit (cancel in Billing at the period end) needs no switch.

As everywhere in billing, a customer's request is recorded and the provider
is asked, but a plan changes only from the provider's verified webhook
(service.py). Wording comes from notices.py.
"""

import logging
from datetime import datetime, time, timedelta, timezone

import httpx
import stripe
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import mail
from ..config import get_settings
from ..models import Payment, Subscription, SubscriptionExit, SubscriptionNotice, User
from ..plans import PLANS, currency_digits
from . import consent, notices, service
from .base import ProviderError

log = logging.getLogger("truebex.billing.consumer")

# Directive 2011/83/EU applies in the 27 member states (the EEA follows once
# Directive 2023/2673 is incorporated; GD5 QS-18).
EU_COUNTRIES = frozenset(
    "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split()
)
COOLING_OFF_DAYS = 14
WITHDRAWAL_DAYS = 14
# Provider steps of an exit are retried this long (billing.exits.retry).
EXIT_RETRY_WINDOW = timedelta(days=7)
# Exits that end the plan now and refund.
IMMEDIATE = ("cooling_off", "withdrawal")
FULL = 1_000_000  # parts per million

_PROVIDER_ERRORS = (ProviderError, httpx.HTTPError, stripe.StripeError)

# Shown to the provider (Paddle's dashboard, Stripe's refund), not the customer.
_REFUND_REASONS = {
    "cooling_off": "Renewal cooling-off: cancelled in Billing within 14 days of an annual renewal (DMCC Act 2024).",
    "withdrawal": "EU right of withdrawal exercised in Billing (Directive 2011/83/EU Art. 11a).",
}

_aware = service._aware


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- the switches --------------------------------------------------------------------


def wording_approved() -> bool:
    return bool(get_settings().legal_wording_approved)


def dmcc_active(now: datetime | None = None) -> bool:
    """The UK subscription rules are on: switched on and in force."""
    s = get_settings()
    now = now or _now()
    return bool(s.subscription_notices_enabled) and now.date() >= s.subscription_rules_from


def consent_version() -> str:
    """The consent the checkout must carry: GD5 7.4's box in the QS-17
    variant once the wording is approved, today's placeholder until then."""
    if wording_approved():
        return notices.CONSENT_DRAFT[get_settings().consent_variant].version
    return consent.CONSENT_VERSION


_CONSENT_TEXTS = {
    consent.CONSENT_VERSION: consent.STRIPE_MESSAGE,
    **{w.version: w.text for w in notices.CONSENT_DRAFT.values()},
}
# Consents that give up the right to cancel once access starts (digital
# content: reg. 37, Art. 16(m)), and those that keep it with a proportionate
# payment (services: reg. 36, Art. 14(3)).
_WAIVING = {consent.CONSENT_VERSION, notices.CONSENT_DRAFT["digital_content"].version}
_SERVICE = {notices.CONSENT_DRAFT["service"].version}


def consent_text(version: str | None) -> str | None:
    return _CONSENT_TEXTS.get(version or "")


def rules(now: datetime | None = None) -> dict:
    """What the site needs to know (GET /billing/plans `rules`)."""
    s = get_settings()
    approved = wording_approved()
    return {
        "wording_approved": approved,
        "consent_variant": s.consent_variant,
        "consent_version": consent_version(),
        "key_info_version": notices.KEY_INFO.version if approved else None,
        "eu_withdrawal": bool(s.eu_withdrawal_enabled),
        "renewal_notices": dmcc_active(now),
    }


# --- formatting (the site formats the same way: en-GB) ----------------------------------

_SYMBOLS = {"GBP": "£", "USD": "US$", "EUR": "€"}


def money(amount_minor: int, currency: str) -> str:
    code = (currency or "").upper()
    digits = currency_digits(code)
    value = f"{amount_minor / 10**digits:,.{digits}f}"
    symbol = _SYMBOLS.get(code)
    return f"{symbol}{value}" if symbol else f"{value} {code}"


def long_date(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    d = _aware(dt).astimezone(timezone.utc)
    return f"{d.day} {d:%B %Y}"


def clock(dt: datetime) -> str:
    return f"{_aware(dt).astimezone(timezone.utc):%H:%M}"


def stamp(dt: datetime | None) -> str:
    """A date and time to the second, for the record of a consent."""
    if dt is None:
        return "unknown"
    return f"{long_date(dt)}, {_aware(dt).astimezone(timezone.utc):%H:%M:%S} UTC"


def plan_name(tier: str) -> str:
    plan = PLANS.get(tier)
    return plan.name if plan else tier.title()


def plan_label(tier: str, seats: int) -> str:
    plan = PLANS.get(tier)
    if plan is not None and plan.per_seat:
        return f"{plan.name}, {seats} seats"
    return plan_name(tier)


def _site(path: str) -> str:
    return f"{get_settings().site_url.rstrip('/')}{path}"


def billing_url() -> str:
    return _site("/dashboard/billing/")


def terms_url() -> str:
    return _site("/terms/")


def eula_url() -> str:
    return get_settings().eula_url or terms_url()


def key_info_text(
    tier: str, seats: int, interval: str, currency: str, total_minor: int, provider: str
) -> str:
    """GD5 7.4's summary beside the pay button, for one chosen price."""
    return notices.KEY_INFO.render(
        plan=plan_label(tier, seats),
        price=money(total_minor, currency),
        interval=interval,
        currency=currency.upper(),
        seller=notices.SELLERS.get(provider, notices.SELLERS["stripe"]),
    )


# --- mail ----------------------------------------------------------------------------------


def _send(to: str, template: str, subject: str, **data: object) -> bool:
    values = {
        "subject": subject,
        "footer": notices.FOOTER.render(support_email=get_settings().support_email),
        **data,
    }
    try:
        mail.send_mail(to, template, values)
    except Exception:  # noqa: BLE001 - a mail failure is retried, never fatal
        log.exception("could not mail %s to %s", template, to)
        return False
    return True


# --- reminder notices (billing.subscription_notices) --------------------------------------


def _claim(db: Session, sub: Subscription, kind: str, period_end: datetime) -> SubscriptionNotice | None:
    """Reserve the one notice of this kind for this period (None: already sent)."""
    exists = db.scalar(
        select(SubscriptionNotice.id).where(
            SubscriptionNotice.subscription_id == sub.id,
            SubscriptionNotice.kind == kind,
            SubscriptionNotice.period_end == period_end,
        )
    )
    if exists is not None:
        return None
    row = SubscriptionNotice(subscription_id=sub.id, kind=kind, period_end=period_end, sent_at=_now())
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # another run took it
        return None
    return row


def _release(db: Session, row: SubscriptionNotice) -> None:
    db.delete(row)
    db.commit()


def _renewal_amount(db: Session, sub: Subscription) -> int | None:
    """What the next renewal charges: the synced price it pays x seats."""
    row = service.price_by_provider_id(db, sub.provider, sub.provider_price_id)
    unit = row.amount_minor if row is not None else None
    if unit is None:
        plan = PLANS.get(sub.plan)
        price = plan.price(sub.interval or "month", sub.currency or "") if plan else None
        unit = price.amount_minor if price else None
    return None if unit is None else unit * (sub.seats or 1)


def send_due_notices(db: Session, now: datetime) -> int:
    """Mail the reminders that are due. A no-op while the DMCC switch is off
    or before SUBSCRIPTION_RULES_FROM. Returns how many were sent."""
    if not dmcc_active(now):
        return 0
    sent = _renewal_reminders(db, now)
    # The trial text is GD5 7.4 draft wording.
    if wording_approved():
        sent += _trial_notices(db, now)
    return sent


def _renewal_reminders(db: Session, now: datetime) -> int:
    s = get_settings()
    longest = max(s.renewal_reminder_days_year, s.renewal_reminder_days_month)
    subs = db.scalars(
        select(Subscription).where(
            Subscription.provider.in_(service.MANAGED_PROVIDERS),
            Subscription.status == "active",
            Subscription.current_period_end > now,
            Subscription.current_period_end <= now + timedelta(days=longest),
            or_(Subscription.cancel_at_period_end.is_(None), Subscription.cancel_at_period_end.is_(False)),
        )
    ).all()
    sent = 0
    for sub in subs:
        end = _aware(sub.current_period_end)
        annual = sub.interval == "year"
        lead = timedelta(days=s.renewal_reminder_days_year if annual else s.renewal_reminder_days_month)
        if now < end - lead:
            continue
        user = db.get(User, sub.user_id)
        amount = _renewal_amount(db, sub)
        if user is None or amount is None or not sub.currency:
            log.warning("no renewal reminder for subscription %s: no address or price", sub.id)
            continue
        row = _claim(db, sub, "renewal_reminder", end)
        if row is None:
            continue
        plan = plan_label(sub.plan, sub.seats or 1)
        ok = _send(
            user.email,
            "renewal_reminder",
            notices.SUBJECTS["renewal_reminder"].render(plan=plan, date=long_date(end)),
            reminder=notices.RENEWAL_REMINDER.render(
                plan=plan,
                date=long_date(end),
                price=money(amount, sub.currency),
                currency=sub.currency.upper(),
                billing_url=billing_url(),
            ),
            cooling_off=notices.RENEWAL_COOLING_OFF.text if annual else "",
            billing_url=billing_url(),
        )
        if ok:
            sent += 1
        else:
            _release(db, row)  # tried again next run
    return sent


def _trial_notices(db: Session, now: datetime) -> int:
    s = get_settings()
    subs = db.scalars(
        select(Subscription).where(
            Subscription.provider == service.TRIAL_PROVIDER,
            Subscription.status == "active",
            Subscription.current_period_end > now,
            Subscription.current_period_end <= now + timedelta(days=s.trial_end_notice_days),
        )
    ).all()
    sent = 0
    for sub in subs:
        end = _aware(sub.current_period_end)
        user = db.get(User, sub.user_id)
        if user is None:
            continue
        row = _claim(db, sub, "trial_end", end)
        if row is None:
            continue
        name = plan_name(sub.plan)
        ok = _send(
            user.email,
            "trial_end",
            notices.SUBJECTS["trial_end"].render(plan=name, date=long_date(end)),
            notice=notices.TRIAL_END.render(days=s.trial_days, plan=name, date=long_date(end)),
            billing_url=billing_url(),
        )
        if ok:
            sent += 1
        else:
            _release(db, row)
    return sent


# --- the confirmation on a durable medium (GD5 7.4) ----------------------------------------


def payment_paid(db: Session, payment: Payment) -> bool:
    """Mail the order confirmation once a checkout is paid (behind
    LEGAL_WORDING_APPROVED; until then the provider's receipt is the only
    one). Idempotent. Returns True when it was sent now."""
    if not wording_approved() or payment.status != "paid" or payment.confirmation_sent_at is not None:
        return False
    user = db.get(User, payment.user_id)
    if user is None:
        return False
    plan = plan_label(payment.plan, payment.seats or 1)
    if not _send(user.email, "order_confirmation", notices.SUBJECTS["order"].render(plan=plan),
                 **_order_data(payment, plan)):
        return False
    payment.confirmation_sent_at = _now()
    db.add(payment)
    db.commit()
    return True


def _order_data(payment: Payment, plan: str) -> dict:
    s = get_settings()
    interval = payment.interval or "month"
    order = f"Truebex {plan}, billed every {interval}: {money(payment.amount, payment.currency)}"
    if payment.tax_minor:
        order += f" (tax {money(payment.tax_minor, payment.currency)})"
    order += f".\nReference {payment.reference}, paid {stamp(payment.paid_at)}."
    company = "Truebex Ltd" + (f", {s.company_address}" if s.company_address else "")
    seller = company if payment.provider == "stripe" else f"{notices.SELLERS.get(payment.provider, '')}\n{company}"
    agreed = []
    text = consent_text(payment.consent_version)
    if text:
        agreed.append(f'"{text}"\nVersion {payment.consent_version}, accepted {stamp(payment.consent_at)}.')
    if payment.key_info:
        agreed.append(
            f'"{payment.key_info}"\nVersion {payment.key_info_version}, acknowledged {stamp(payment.key_info_at)}.'
        )
    if payment.business:
        agreed.append(f'"{notices.BUSINESS.text}" (ticked)')
    return {
        "order": order,
        "renewal": notices.RENEWAL_TERMS.render(interval=interval),
        "seller": seller.strip(),
        "agreed": "\n\n".join(agreed),
        "how_to_cancel": notices.HOW_TO_CANCEL.render(billing_url=billing_url()),
        "terms_url": terms_url(),
        "eula_url": eula_url(),
    }


# --- who may do what, now ------------------------------------------------------------------


def _day_end(dt: datetime) -> datetime:
    return datetime.combine(_aware(dt).astimezone(timezone.utc).date(), time(23, 59, 59), tzinfo=timezone.utc)


def _provider_on(name: str) -> bool:
    from . import providers  # the registry imports the adapters, which import us

    try:
        return providers.get_provider(name).enabled()
    except KeyError:
        return False


def checkout_payment(db: Session, sub: Subscription) -> Payment | None:
    """The paid checkout that started this subscription."""
    if sub.provider_subscription_id:
        found = db.scalar(
            select(Payment)
            .where(
                Payment.provider == sub.provider,
                Payment.provider_subscription_id == sub.provider_subscription_id,
                Payment.status == "paid",
            )
            .order_by(Payment.paid_at.asc())
        )
        if found is not None:
            return found
    # Payments from before PF2b carry no subscription id: the user's latest
    # paid checkout with this provider (one live subscription at a time).
    found = db.scalar(
        select(Payment)
        .where(Payment.user_id == sub.user_id, Payment.provider == sub.provider, Payment.status == "paid")
        .order_by(Payment.paid_at.desc())
    )
    created = _aware(sub.created_at)
    if found is None or (created and _aware(found.paid_at) and _aware(found.paid_at) < created - timedelta(days=1)):
        return None
    return found


def _unfinished(ex: SubscriptionExit) -> bool:
    return ex.canceled_at is None or (ex.kind in IMMEDIATE and ex.refunded_at is None)


def pending_exit(db: Session, sub: Subscription, now: datetime | None = None) -> SubscriptionExit | None:
    """An exit still on its way: provider steps left to do, or done but not
    yet confirmed by the provider's webhook (the subscription unchanged since)."""
    now = now or _now()
    updated = _aware(sub.updated_at)
    for ex in db.scalars(
        select(SubscriptionExit)
        .where(SubscriptionExit.subscription_id == sub.id)
        .order_by(SubscriptionExit.id.desc())
    ):
        requested = _aware(ex.requested_at)
        if _unfinished(ex) and requested >= now - EXIT_RETRY_WINDOW:
            return ex
        if updated is None or requested > updated:
            return ex
    return None


def _managed_live(sub: Subscription | None, now: datetime) -> bool:
    return sub is not None and sub.provider in service.MANAGED_PROVIDERS and service.is_live(sub, now)


def can_cancel(db: Session, sub: Subscription | None, now: datetime | None = None) -> bool:
    """The easy exit is open: a live Paddle or Stripe subscription that is not
    already ending, with no cancellation on its way."""
    now = now or _now()
    return (
        _managed_live(sub, now)
        and not sub.cancel_at_period_end
        and _provider_on(sub.provider)
        and pending_exit(db, sub, now) is None
    )


def cooling_off_until(db: Session, sub: Subscription | None, now: datetime | None = None) -> datetime | None:
    """The end of the renewal cooling-off (DMCC): 14 days after an annual
    renewal billed while the rules are in force; None when not open."""
    now = now or _now()
    if not dmcc_active(now) or not _managed_live(sub, now) or sub.interval != "year":
        return None
    renewed = _aware(sub.renewed_at)
    if renewed is None or renewed.date() < get_settings().subscription_rules_from:
        return None
    until = _day_end(renewed + timedelta(days=COOLING_OFF_DAYS))
    if now > until or not _provider_on(sub.provider) or pending_exit(db, sub, now) is not None:
        return None
    return until


def right_waived(payment: Payment) -> bool:
    """Digital content: express consent, the acknowledgement and the
    confirmation on a durable medium together end the right to cancel
    (GD5 7.1); without all three it stays."""
    return payment.consent_version in _WAIVING and payment.confirmation_sent_at is not None


def withdrawal_until(db: Session, sub: Subscription | None, now: datetime | None = None) -> datetime | None:
    """The end of the EU withdrawal period for this subscription, or None
    when the function is off or this purchase has no right to withdraw (not
    an EU consumer, a business purchase, waived, or out of time)."""
    now = now or _now()
    if not get_settings().eu_withdrawal_enabled or not _managed_live(sub, now):
        return None
    pay = checkout_payment(db, sub)
    if pay is None or pay.paid_at is None or pay.business:
        return None
    if (pay.country or "").upper() not in EU_COUNTRIES or right_waived(pay):
        return None
    until = _day_end(_aware(pay.paid_at) + timedelta(days=WITHDRAWAL_DAYS))
    if now > until or not _provider_on(sub.provider) or pending_exit(db, sub, now) is not None:
        return None
    return until


def unused_ppm(start: datetime | None, end: datetime | None, now: datetime) -> int:
    """The share of a paid period still to come, in parts per million."""
    start, end = _aware(start), _aware(end)
    if start is None or end is None or end <= start:
        return FULL
    left = (end - max(now, start)).total_seconds() / (end - start).total_seconds()
    return max(0, min(FULL, round(left * FULL)))


# --- exits ------------------------------------------------------------------------------------


def start_exit(db: Session, user: User, sub: Subscription, kind: str, now: datetime) -> SubscriptionExit:
    """Record the customer's statement, ask the provider, mail the
    confirmation. The callers check the window first."""
    ex = SubscriptionExit(
        user_id=user.id, subscription_id=sub.id, kind=kind, requested_at=now, currency=sub.currency
    )
    if kind == "cancel":
        ex.effective_at = sub.current_period_end
    elif kind == "cooling_off":
        ex.effective_at = now
        ex.refund_charge_id = sub.renewal_charge_id
        # The rest of the renewed year comes back (a proportionate amount
        # is kept for the days used; QS-18).
        ex.refund_ppm = unused_ppm(sub.renewed_at, sub.current_period_end, now)
    else:  # withdrawal
        ex.effective_at = now
        pay = checkout_payment(db, sub)
        if pay is not None:
            ex.refund_charge_id = pay.provider_ref if sub.provider == "paddle" else pay.invoice_id
        # Digital content without a complete waiver: nothing is owed (reg. 37,
        # Art. 14(4)(b)); a service started on request: the days used (Art. 14(3)).
        service_consent = pay is not None and pay.consent_version in _SERVICE
        ex.refund_ppm = unused_ppm(pay.paid_at, sub.current_period_end, now) if service_consent else FULL
    db.add(ex)
    db.commit()
    complete_exit(db, ex, now)
    mail_exit(db, ex)
    return ex


def complete_exit(db: Session, ex: SubscriptionExit, now: datetime | None = None) -> bool:
    """Do the provider steps still open (cancel, then refund). Returns True
    once all are done; a provider error is kept and retried later."""
    from . import providers

    now = now or _now()
    sub = db.get(Subscription, ex.subscription_id)
    if sub is None:
        return False
    adapter = providers.get_provider(sub.provider)
    if not adapter.enabled():
        ex.error = f"{sub.provider} is not configured"
        db.commit()
        return False
    try:
        if ex.canceled_at is None:
            # Already cancelled at the provider (the portal, or a webhook raced us).
            done = sub.status == "canceled" or (ex.kind == "cancel" and bool(sub.cancel_at_period_end))
            if not done:
                adapter.cancel_subscription(db, sub, immediately=ex.kind in IMMEDIATE)
            ex.canceled_at = now
            db.commit()
        if ex.kind in IMMEDIATE and ex.refunded_at is None:
            refund = adapter.refund(
                db, sub, charge_id=ex.refund_charge_id, share_ppm=ex.refund_ppm, reason=_REFUND_REASONS[ex.kind]
            )
            ex.refund_id = refund.id
            ex.refund_minor = refund.amount_minor
            ex.currency = refund.currency or ex.currency
            ex.refunded_at = now
            db.commit()
    except _PROVIDER_ERRORS as exc:
        log.warning("exit %s (%s) not finished: %s", ex.id, ex.kind, exc)
        ex.error = str(exc)[:500]
        db.commit()
        return False
    if ex.error:
        ex.error = None
        db.commit()
    return True


def mail_exit(db: Session, ex: SubscriptionExit) -> bool:
    """The confirmation (cancel, cooling-off) or the acknowledgement on a
    durable medium (withdrawal, with the date and time). Once."""
    if ex.mail_sent_at is not None:
        return False
    user = db.get(User, ex.user_id)
    sub = db.get(Subscription, ex.subscription_id)
    if user is None or sub is None:
        return False
    plan = plan_label(sub.plan, sub.seats or 1)
    when = long_date(ex.requested_at)
    if ex.refunded_at is not None and ex.refund_minor is not None:
        refund = notices.REFUND_AMOUNT.render(amount=money(ex.refund_minor, ex.currency or sub.currency or ""))
    else:
        refund = notices.REFUND_PENDING.text
    if ex.kind == "cancel":
        ok = _send(
            user.email,
            "cancel_confirmation",
            notices.SUBJECTS["cancel"].render(plan=plan),
            statement=notices.CANCEL_DONE.render(plan=plan, date=when, end=long_date(ex.effective_at)),
            refund="",
            billing_url=billing_url(),
        )
    elif ex.kind == "cooling_off":
        ok = _send(
            user.email,
            "cancel_confirmation",
            notices.SUBJECTS["cooling_off"].render(plan=plan),
            statement=notices.COOLING_OFF_DONE.render(plan=plan, date=when),
            refund=refund,
            billing_url=billing_url(),
        )
    else:
        pay = checkout_payment(db, sub)
        ok = _send(
            user.email,
            "withdrawal_acknowledgement",
            notices.SUBJECTS["withdrawal"].render(),
            acknowledgement=notices.WITHDRAW_ACK.render(plan=plan, date=when, time=clock(ex.requested_at)),
            statement=notices.WITHDRAW_DONE.text,
            refund=f"{refund} {notices.WITHDRAW_REFUND.text}",
            contract=f"Truebex {plan}" + (f", order {pay.reference}" if pay else ""),
            billing_url=billing_url(),
        )
    if ok:
        ex.mail_sent_at = _now()
        db.commit()
    return ok


def retry_exits(db: Session, now: datetime) -> int:
    """Finish exits whose provider steps failed (billing.exits.retry), and
    mail any confirmation that could not be sent. Returns how many exits were
    finished in this run."""
    rows = db.scalars(
        select(SubscriptionExit).where(
            SubscriptionExit.requested_at >= now - EXIT_RETRY_WINDOW,
            or_(
                SubscriptionExit.canceled_at.is_(None),
                and_(SubscriptionExit.kind.in_(IMMEDIATE), SubscriptionExit.refunded_at.is_(None)),
                SubscriptionExit.mail_sent_at.is_(None),
            ),
        )
    ).all()
    finished = 0
    for ex in rows:
        if _unfinished(ex) and complete_exit(db, ex, now):
            finished += 1
        if ex.mail_sent_at is None:
            mail_exit(db, ex)
    return finished


def exit_status(ex: SubscriptionExit) -> str:
    return "processing" if _unfinished(ex) else "done"
