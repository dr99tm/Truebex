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
    enabled: bool
    total: int
    remaining: int
    discount_percent: int
    ends_at: datetime | None


class BillingCatalog(BaseModel):
    tiers: list[TierOut]
    founding: FoundingOut
    # The provider offered at checkout, or null while none is set up.
    provider: Provider | None
    currencies: list[str]
    # Every provider switched on (wayl only with WAYL_ENABLED; never offered
    # on the website).
    providers: list[str]


class ConsentIn(BaseModel):
    version: str = Field(min_length=1, max_length=32)
    accepted: Literal[True]


class CheckoutRequest(BaseModel):
    tier: str = Field(max_length=32)
    interval: Interval = "month"
    currency: str = Field(default="GBP", pattern=r"^[A-Za-z]{3}$")
    seats: int = Field(default=1, ge=1, le=1000)
    coupon: str | None = Field(default=None, max_length=64)
    consent: ConsentIn
    # Only "wayl" (dormant, WAYL_ENABLED); otherwise BILLING_PROVIDER decides.
    provider: Literal["wayl"] | None = None


class CheckoutResponse(BaseModel):
    url: str
    reference: str
    founding: bool


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
