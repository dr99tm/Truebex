"""Pydantic request/response schemas."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    # PF3: an owner's one-time code when their organisation requires SSO.
    break_glass_code: str | None = Field(default=None, max_length=64)


class GoogleLogin(BaseModel):
    # The ID token ("credential") returned by Google Identity Services.
    credential: str = Field(min_length=20, max_length=8192)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime
    plan: str
    name: str | None = None
    avatar_url: str | None = None
    has_password: bool = True
    google_linked: bool = False
    is_admin: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- API keys ---------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    # The full secret. Returned once, at creation; never stored or shown again.
    key: str


# --- Usage --------------------------------------------------------------------


class UsageDay(BaseModel):
    day: date
    count: int


class UsageSummary(BaseModel):
    plan: str
    period_start: date
    period_end: date
    used: int
    limit: int
    remaining: int
    daily: list[UsageDay]
    by_endpoint: dict[str, int]
    by_key: dict[str, int]


# --- Billing ------------------------------------------------------------------

Provider = Literal["paddle", "stripe"]
Interval = Literal["month", "year"]


class PriceOut(BaseModel):
    interval: Interval
    currency: str
    # Per seat, in minor units of `currency` (pence, cents).
    amount_minor: int


class TierOut(BaseModel):
    id: str
    name: str
    purchasable: bool
    per_seat: bool
    min_seats: int
    prices: list[PriceOut]


class FoundingOut(BaseModel):
    # Open, seats left and a checkout provider set up.
    enabled: bool
    total: int
    remaining: int
    discount_percent: int
    ends_at: datetime | None
    # The tiers and billing intervals the founding price applies to.
    tiers: list[str] = []
    intervals: list[str] = []


class RulesOut(BaseModel):
    """PF2b: which subscription consumer rules are switched on (GD5 §7)."""

    # GD5 7.4 wording approved: checkout asks for the key information and
    # the draft consent; the order confirmation is mailed.
    wording_approved: bool
    # QS-17: digital_content | service.
    consent_variant: str
    # The consent version checkout must carry now.
    consent_version: str
    # The key information version to acknowledge (null while not approved).
    key_info_version: str | None
    # The EU withdrawal function (Art. 11a).
    eu_withdrawal: bool
    # The UK DMCC rules are on: renewal reminders and the cooling-off refund.
    renewal_notices: bool


class BillingCatalog(BaseModel):
    tiers: list[TierOut]
    founding: FoundingOut
    # The provider offered at checkout, or null while none is set up.
    provider: Provider | None
    currencies: list[str]
    # Every provider switched on (wayl only with WAYL_ENABLED; never offered
    # on the website).
    providers: list[str]
    rules: RulesOut


class ConsentIn(BaseModel):
    version: str = Field(min_length=1, max_length=32)
    accepted: Literal[True]


class KeyInfoIn(BaseModel):
    """The key pre-contract information was shown and acknowledged (PF2b)."""

    version: str = Field(min_length=1, max_length=32)
    acknowledged: Literal[True]


class CheckoutRequest(BaseModel):
    tier: str = Field(max_length=32)
    interval: Interval = "month"
    currency: str = Field(default="GBP", pattern=r"^[A-Za-z]{3}$")
    seats: int = Field(default=1, ge=1, le=1000)
    coupon: str | None = Field(default=None, max_length=64)
    consent: ConsentIn
    # Required while LEGAL_WORDING_APPROVED (PF2b); ignored before.
    key_info: KeyInfoIn | None = None
    # GD5 7.4's business box: no consumer cancellation rights.
    business: bool = False
    # Only "wayl" (dormant, WAYL_ENABLED); otherwise BILLING_PROVIDER decides.
    provider: Literal["wayl"] | None = None


class CheckoutResponse(BaseModel):
    url: str
    reference: str
    founding: bool
    # The key information stored with the payment (null while not approved).
    key_info: str | None = None


class SubscriptionOut(BaseModel):
    tier: str
    interval: str | None
    seats: int
    status: str
    provider: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    founding: bool
    can_manage: bool
    currency: str | None = None
    # PF2b: the easy exit is open; the renewal cooling-off and the EU
    # withdrawal period end then (null when not offered).
    can_cancel: bool = False
    cooling_off_until: datetime | None = None
    withdrawal_until: datetime | None = None


class CancelRequest(BaseModel):
    # The confirm step: the customer pressed "Confirm".
    confirm: Literal[True]
    # The renewal cooling-off: cancel now and refund the rest of the year.
    refund: bool = False


class WithdrawRequest(BaseModel):
    confirm: Literal[True]


class ExitOut(BaseModel):
    """A cancellation made in Billing. The plan changes when the provider's
    webhook confirms it."""

    kind: Literal["cancel", "cooling_off", "withdrawal"]
    requested_at: datetime
    # When the plan ends.
    effective_at: datetime | None
    refund_minor: int | None
    currency: str | None
    # done: the provider took it; processing: retried until it does.
    status: Literal["done", "processing"]


class SeatsRequest(BaseModel):
    seats: int = Field(ge=1, le=1000)


class ChangeRequest(BaseModel):
    tier: str | None = Field(default=None, max_length=32)
    interval: Interval | None = None


class InvoiceOut(BaseModel):
    id: str
    number: str | None
    issued_at: datetime | None
    total_minor: int
    tax_minor: int
    currency: str
    status: str
    pdf_url: str | None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reference: str
    provider: str
    plan: str
    amount: int
    currency: str
    status: str
    created_at: datetime
    paid_at: datetime | None
    interval: str | None = None
    seats: int | None = None
    tax_minor: int | None = None
    # PF2b: what the buyer agreed to.
    consent_version: str | None = None
    key_info: str | None = None
    key_info_at: datetime | None = None
    business: bool | None = None


# --- Admin: growth ------------------------------------------------------------


class GrowthDay(BaseModel):
    day: date
    signups: int
    downloads: int
    trials: int
    checkouts: int
    paid: int


class GrowthTotals(BaseModel):
    signups: int
    downloads: int
    trials: int
    checkouts: int
    paid: int


class GrowthOut(BaseModel):
    """Conversions per UTC day, counted from the platform's own records.
    Counts only: no e-mail addresses, names or ids."""

    model_config = ConfigDict(populate_by_name=True)

    from_: date = Field(alias="from")
    to: date
    days: list[GrowthDay]
    totals: GrowthTotals
