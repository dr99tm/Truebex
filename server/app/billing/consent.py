"""The consumer cancellation consent taken before checkout opens.

The Consumer Contracts Regulations 2013 reg. 37: digital content supplied
within the 14-day cancellation period needs the consumer's express consent
and acknowledgement that the right to cancel is then lost. The site shows the
text (BILLING.consent in src/lib/constants.ts, same version string) and sends
`{version, accepted: true}`; the version and time are stored on the payment.
Wording is a placeholder until guides/GD5; the owner signs it off before
production, then bumps the version here and on the site together.
"""

CONSENT_VERSION = "2026-10-09"

# Stripe's terms-of-service box on its Checkout page mirrors the same consent.
STRIPE_MESSAGE = (
    "I want my plan to start now. I understand that I lose my 14-day right to "
    "cancel once it starts, and that I can cancel future renewals at any time."
)
