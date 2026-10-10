"""Request bodies of the marketplace API (contract §5) and its admin routes.
Unknown keys are ignored (contract §3: readers ignore unknown keys)."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Id32 = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
Sku = Annotated[str, Field(min_length=1, max_length=64)]
VariantId = Annotated[str, Field(min_length=1, max_length=64)]
RegionCode = Annotated[str, Field(min_length=2, max_length=8)]
Amount = Annotated[int, Field(ge=0, le=10**12)]


class _Body(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# --- 5.5 ------------------------------------------------------------------------------


class PriceItem(_Body):
    supplier_id: Id32
    sku: Sku
    variant_id: VariantId
    qty: Annotated[int, Field(ge=1, le=100_000)] | None = None


class PricesRequest(_Body):
    region: RegionCode
    # The 500-line cap answers 413 `too_large` (contract §7), so it is checked
    # by the route rather than here.
    items: list[PriceItem]


# --- 5.7 ------------------------------------------------------------------------------


class PriceSeen(_Body):
    amount: int
    currency: Annotated[str, Field(min_length=3, max_length=3)]


class OrderLineIn(_Body):
    supplier_id: Id32
    sku: Sku
    variant_id: VariantId
    qty: Annotated[int, Field(ge=1, le=999)]
    price_seen: PriceSeen | None = None


class ProjectIn(_Body):
    name: Annotated[str, Field(max_length=200)] | None = None
    project_id: Annotated[str, Field(max_length=64)] | None = None
    # MK4's planned MINOR (CL0's ProjectUid); stored when sent.
    project_uid: Annotated[str, Field(max_length=32)] | None = None


class ContactIn(_Body):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: EmailStr
    phone: Annotated[str, Field(max_length=40)] | None = None
    message: Annotated[str, Field(max_length=2000)] | None = None


class DeliveryIn(_Body):
    country: Annotated[str, Field(pattern=r"^[A-Za-z]{2}$")]
    city: Annotated[str, Field(max_length=120)] | None = None
    postcode: Annotated[str, Field(max_length=20)] | None = None
    address: Annotated[str, Field(max_length=300)] | None = None


class OrderRequest(_Body):
    kind: Literal["order", "quote"]
    region: RegionCode
    project: ProjectIn = ProjectIn()
    contact: ContactIn
    delivery: DeliveryIn
    lines: Annotated[list[OrderLineIn], Field(min_length=1, max_length=200)]


# --- Supplier answers (PF8's inbox; the admin page acts for a supplier) ----------------


class QuoteLineIn(_Body):
    sku: Sku
    variant_id: VariantId
    unit_amount: Amount


class SupplierQuoteIn(_Body):
    # Lines left out keep the listed unit price.
    lines: list[QuoteLineIn] = []
    delivery_fee: Amount | None = None
    delivery_days_min: Annotated[int, Field(ge=0, le=365)] | None = None
    delivery_days_max: Annotated[int, Field(ge=0, le=365)] | None = None
    valid_days: Annotated[int, Field(ge=1, le=30)] = 30
    message: Annotated[str, Field(max_length=2000)] | None = None


class ReasonIn(_Body):
    reason: Annotated[str, Field(min_length=1, max_length=500)]


# --- Reviews --------------------------------------------------------------------------


class ReviewIn(_Body):
    rating: Annotated[int, Field(ge=1, le=5)]
    text: Annotated[str, Field(max_length=2000)] = ""


# --- Admin ----------------------------------------------------------------------------


class SupplierIn(_Body):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    country: Annotated[str, Field(pattern=r"^[A-Za-z]{2}$")]
    legal_name: Annotated[str, Field(max_length=200)] | None = None
    company_number: Annotated[str, Field(max_length=40)] | None = None
    vat_id: Annotated[str, Field(max_length=40)] | None = None
    website: Annotated[str, Field(max_length=300, pattern=r"^https://")] | None = None
    contact_email: EmailStr | None = None
    regions: list[RegionCode] = []
    owner_email: EmailStr | None = None


class SupplierPatch(_Body):
    status: Literal["applied", "verified", "suspended"] | None = None
    reason: Annotated[str, Field(max_length=300)] | None = None
    commission_bp: Annotated[int, Field(ge=0, le=5000)] | None = None
    clear_commission: bool = False
    listing_plan: Annotated[str, Field(max_length=32)] | None = None
    connect_account_id: Annotated[str, Field(pattern=r"^acct_[A-Za-z0-9]{1,60}$")] | None = None
    connect_ready: bool | None = None
    billing_customer_id: Annotated[str, Field(pattern=r"^cus_[A-Za-z0-9]{1,60}$")] | None = None
    regions: list[RegionCode] | None = None


class MemberIn(_Body):
    email: EmailStr
    role: Literal["owner", "catalogue", "orders", "viewer"]


class CategoryIn(_Body):
    path: Annotated[str, Field(min_length=1, max_length=160)]
    label: Annotated[str, Field(min_length=1, max_length=80)]


class SupplierActionIn(_Body):
    reason: Annotated[str, Field(max_length=500)] | None = None
