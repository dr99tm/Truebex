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

Provider = Literal["stripe", "wayl"]


class PlanOut(BaseModel):
    id: str
    name: str
    price_usd_cents: int | None
    price_iqd: int | None
    monthly_requests: int
    max_api_keys: int
    purchasable: bool


class BillingCatalog(BaseModel):
    plans: list[PlanOut]
    providers: list[Provider]


class CheckoutRequest(BaseModel):
    plan: str = Field(max_length=32)
    provider: Provider


class CheckoutResponse(BaseModel):
    url: str
    reference: str


class SubscriptionOut(BaseModel):
    plan: str
    status: str
    provider: str | None
    current_period_end: datetime | None
    can_manage: bool


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
