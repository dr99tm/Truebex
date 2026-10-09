"""The wording of the subscription consumer rules (PF2b; guides/GD5 §7.1-7.4).

One source on the server, mirrored by BILLING in src/lib/constants.ts (same
texts, same versions: test_pf2b_wording_matches_site). Change a text, bump its
version here and on the site together, as with consent.CONSENT_VERSION.

Two kinds of text:
* GD5 §7.4 DRAFTS (DRAFT_VERSION): "not to be shown to customers until
  approved". They render on a page or in a mail only while
  LEGAL_WORDING_APPROVED is true; until then consent.py's placeholder consent
  stays. On the site they are compiled in only with
  NEXT_PUBLIC_LEGAL_WORDING_APPROVED=true (the out/ build check proves it).
* Truebex's own notice texts (NOTICE_VERSION): the DMCC reminders and the
  cancellation and withdrawal mails. They go out only behind their switches
  (SUBSCRIPTION_NOTICES_ENABLED from SUBSCRIPTION_RULES_FROM; the easy exit;
  EU_WITHDRAWAL_ENABLED), and the solicitor reads them too (QS-18).

`{name}` marks a value filled in when the text is used.

Mail goes out through PF14's plumbing, `send_mail(to, template, data, *,
reply_to=None)` with templates in app/mail/templates/. This is its only import
in PF2b: until PF14 is merged into this branch `send_mail` is None, and every
notice, confirmation and acknowledgement is logged and left unsent (the
billing.subscription_notices job does nothing; billing.exits.retry sends the
exit mails once mail exists, for 7 days).
"""

from dataclasses import dataclass

try:
    from app.mail import send_mail
except ImportError:  # PF14's app.mail not merged yet
    send_mail = None


@dataclass(frozen=True)
class Wording:
    version: str
    text: str

    def render(self, **values: object) -> str:
        return self.text.format(**values)


DRAFT_VERSION = "gd5-2026-10-09"
NOTICE_VERSION = "pf2b-2026-10-09"

# --- GD5 §7.4 drafts -------------------------------------------------------------------

# "Before payment (the summary beside the button)": the key pre-contract
# information (DMCC), acknowledged at the last step.
KEY_INFO = Wording(
    DRAFT_VERSION,
    "Truebex {plan} — {price} incl. VAT a {interval} ({currency}). Renews automatically every "
    "{interval} until you cancel. Cancel any time in Billing; your plan stays active until the end "
    "of the period you paid for. Sold by {seller}.",
)
KEY_INFO_ACK = Wording(DRAFT_VERSION, "I've read the key information above.")

# "The consent box" in both QS-17 variants (settings.consent_variant). The
# version is stored with the payment, as the placeholder's is today.
CONSENT_DRAFT = {
    "digital_content": Wording(
        f"{DRAFT_VERSION}-digital",
        "Start my plan now. I ask Truebex to give me access straight away, before the 14-day "
        "cancellation period ends. I understand that once access starts I lose my right to cancel.",
    ),
    "service": Wording(
        f"{DRAFT_VERSION}-service",
        "Start my plan now. I ask Truebex to give me access straight away, before the 14-day "
        "cancellation period ends. I understand that if I cancel within 14 days I pay for the days I used.",
    ),
}

# "The business box" (optional; a business purchase has no consumer rights).
BUSINESS = Wording(
    DRAFT_VERSION,
    "I'm buying for a business. (Consumer cancellation rights don't apply to business purchases.)",
)

# "The trial".
TRIAL_END = Wording(
    DRAFT_VERSION,
    "Your {days}-day {plan} trial ends on {date}. You won't be charged — Truebex returns to Free "
    "unless you choose a plan.",
)

# "For EU consumers": the withdrawal function's two steps (Art. 11a).
WITHDRAW_BUTTON = Wording(DRAFT_VERSION, "Withdraw from contract")
WITHDRAW_CONFIRM = Wording(DRAFT_VERSION, "Confirm withdrawal")

# "The confirmation email": its renewal and cancellation lines.
RENEWAL_TERMS = Wording(DRAFT_VERSION, "Renews automatically every {interval} until you cancel.")
HOW_TO_CANCEL = Wording(
    DRAFT_VERSION,
    "Cancel any time in Billing: {billing_url}. Your plan stays active until the end of the period "
    "you paid for.",
)

# The confirmation's seller block when a reseller sells: who licenses the app.
LICENSOR = Wording(DRAFT_VERSION, "The software is licensed to you by {company}.")

# Who sells, by the provider that takes the payment ("Sold by {seller}").
SELLERS = {
    "paddle": "Paddle.com, our reseller and Merchant of Record",
    "stripe": "Truebex Ltd",
}

# The 7.4 drafts a customer page could show: none of them may be in out/
# while the wording is unapproved (server/tests/test_site_pf2.py).
SITE_DRAFTS = (
    KEY_INFO,
    KEY_INFO_ACK,
    CONSENT_DRAFT["digital_content"],
    CONSENT_DRAFT["service"],
    BUSINESS,
    TRIAL_END,
    WITHDRAW_BUTTON,
    WITHDRAW_CONFIRM,
)

# --- Truebex's notices (DMCC reminders, exits) -------------------------------------------

RENEWAL_REMINDER = Wording(
    NOTICE_VERSION,
    "Your Truebex {plan} plan renews automatically on {date} for {price} ({currency}). If you don't "
    "want it to renew, cancel before then in Billing: {billing_url}. Your plan stays active until {date}.",
)
# Added to the reminder before an annual renewal (the renewal cooling-off).
RENEWAL_COOLING_OFF = Wording(
    NOTICE_VERSION,
    "After an annual renewal you can still cancel within 14 days and get a refund for the rest of the "
    "year: choose Cancel and get a refund in Billing.",
)
CANCEL_DONE = Wording(
    NOTICE_VERSION,
    "You cancelled your Truebex {plan} plan on {date}. It stays active until {end} and won't renew; "
    "you won't be charged again.",
)
COOLING_OFF_DONE = Wording(
    NOTICE_VERSION,
    "You cancelled your Truebex {plan} plan on {date}, within 14 days of its renewal. Your plan has ended.",
)
# The acknowledgement on a durable medium of an EU withdrawal (Art. 11a(3)).
WITHDRAW_ACK = Wording(
    NOTICE_VERSION,
    "We received your withdrawal from your Truebex {plan} contract on {date} at {time} UTC.",
)
WITHDRAW_DONE = Wording(NOTICE_VERSION, "Your plan has ended and won't renew.")
REFUND_AMOUNT = Wording(NOTICE_VERSION, "Your refund of {amount} goes back to the card you paid with.")
REFUND_PENDING = Wording(
    NOTICE_VERSION,
    "Your refund goes back to the card you paid with. We'll finish it with the payment provider shortly.",
)
WITHDRAW_REFUND = Wording(NOTICE_VERSION, "We refund you within 14 days of your withdrawal.")

SUBJECTS = {
    "renewal_reminder": Wording(NOTICE_VERSION, "Your Truebex {plan} plan renews on {date}"),
    "trial_end": Wording(DRAFT_VERSION, "Your Truebex {plan} trial ends on {date}"),
    "cancel": Wording(NOTICE_VERSION, "Your Truebex {plan} plan is cancelled"),
    "cooling_off": Wording(NOTICE_VERSION, "Your Truebex {plan} plan is cancelled and refunded"),
    "withdrawal": Wording(NOTICE_VERSION, "We received your withdrawal from your Truebex contract"),
    "order": Wording(DRAFT_VERSION, "Your Truebex order: {plan}"),
}

FOOTER = Wording(NOTICE_VERSION, "Questions? Reply to this e-mail or write to {support_email}.")
