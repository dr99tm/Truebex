"""Request bodies of the supplier portal and the feed source (PF8).
Unknown keys are ignored, strings are trimmed (as PF7's schemas)."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Iso2 = Annotated[str, Field(pattern=r"^[A-Za-z]{2}$")]
RegionCode = Annotated[str, Field(pattern=r"^[A-Za-z]{2}(-[A-Za-z0-9]{1,3})?$")]
Sku = Annotated[str, Field(min_length=1, max_length=64)]
VariantId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[^\s;,]+$")]
Days = Annotated[int, Field(ge=0, le=365)]
# Money is written as text in major units ("1299.00") and parsed with the
# region's exponent on the server (contract §6.4: never a float).
Major = Annotated[str, Field(min_length=1, max_length=20)]


class _Body(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# --- Sign-up -------------------------------------------------------------------------


class AddressIn(_Body):
    line1: Annotated[str, Field(min_length=1, max_length=200)]
    line2: Annotated[str, Field(max_length=200)] | None = None
    city: Annotated[str, Field(min_length=1, max_length=120)]
    postcode: Annotated[str, Field(max_length=20)] | None = None
    country: Iso2


class ContactIn(_Body):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: EmailStr
    phone: Annotated[str, Field(max_length=40)] | None = None


class ApplicationIn(_Body):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    legal_name: Annotated[str, Field(min_length=1, max_length=200)]
    country: Iso2
    company_number: Annotated[str, Field(min_length=1, max_length=40)]
    vat_id: Annotated[str, Field(max_length=40, pattern=r"^[A-Za-z0-9 .\-]{4,40}$")] | None = None
    website: Annotated[str, Field(max_length=300, pattern=r"^https://[^\s]+$")] | None = None
    address: AddressIn
    regions: Annotated[list[RegionCode], Field(min_length=1, max_length=50)]
    contact: ContactIn


# --- Catalogue -----------------------------------------------------------------------


class ProductIn(_Body):
    sku: Sku
    name: Annotated[str, Field(min_length=1, max_length=120)]
    kind: Literal["object", "material", "finish", "theme"] = "object"
    category: Annotated[str, Field(min_length=1, max_length=160)]
    description: Annotated[str, Field(max_length=2000)] = ""
    brand: Annotated[str, Field(max_length=70)] | None = None


class ProductPatch(_Body):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    kind: Literal["object", "material", "finish", "theme"] | None = None
    category: Annotated[str, Field(min_length=1, max_length=160)] | None = None
    description: Annotated[str, Field(max_length=2000)] | None = None
    brand: Annotated[str, Field(max_length=70)] | None = None


class Options(_Body):
    size: Annotated[str, Field(max_length=40)] | None = None
    colour: Annotated[str, Field(max_length=40)] | None = None
    finish: Annotated[str, Field(max_length=40)] | None = None


class VariantIn(_Body):
    variant_id: VariantId = "default"
    options: Options = Options()
    # [X width, Y height, Z depth] in whole millimetres (contract §6.1).
    dims_mm: Annotated[list[Annotated[int, Field(ge=1, le=100_000)]], Field(min_length=3, max_length=3)] | None = None
    materials: Annotated[list[Annotated[str, Field(min_length=1, max_length=40)]], Field(max_length=20)] = []
    gtin: Annotated[str, Field(pattern=r"^\d{8}$|^\d{12,14}$")] | None = None


class VariantPatch(_Body):
    options: Options | None = None
    dims_mm: Annotated[list[Annotated[int, Field(ge=1, le=100_000)]], Field(min_length=3, max_length=3)] | None = None
    materials: Annotated[list[Annotated[str, Field(min_length=1, max_length=40)]], Field(max_length=20)] | None = None
    gtin: Annotated[str, Field(pattern=r"^\d{8}$|^\d{12,14}$|^$")] | None = None
    status: Literal["active", "discontinued"] | None = None


class SubmitManyIn(_Body):
    # Empty = every draft and rejected product of the supplier.
    product_ids: Annotated[list[Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]], Field(max_length=500)] = []


# --- Prices and regions --------------------------------------------------------------


class PriceRowIn(_Body):
    """One cell row of the grid: the §6.4 row columns for a variant in the region."""

    sku: Sku
    variant_id: Annotated[str, Field(min_length=1, max_length=64)]
    currency: Annotated[str, Field(max_length=3)] = ""
    price: Annotated[str, Field(max_length=20)] = ""
    price_includes_tax: Annotated[str, Field(max_length=5)] | bool = ""
    tax_rate_percent: Annotated[str, Field(max_length=10)] = ""
    delivery_fee: Annotated[str, Field(max_length=20)] = ""
    delivery_days_min: Annotated[str, Field(max_length=9)] | int | None = ""
    delivery_days_max: Annotated[str, Field(max_length=9)] | int | None = ""
    stock: Annotated[str, Field(max_length=9)] | int | None = ""
    lead_time_days: Annotated[str, Field(max_length=9)] | int | None = ""
    availability: Annotated[str, Field(max_length=16)] = ""
    status: Annotated[str, Field(max_length=16)] = ""


class PricesIn(_Body):
    rows: Annotated[list[PriceRowIn], Field(min_length=1, max_length=2000)]


class RegionSettingIn(_Body):
    region: RegionCode
    active: bool = True
    default_delivery_fee: Annotated[str, Field(max_length=20)] | None = None
    delivery_days_min: Days | None = None
    delivery_days_max: Days | None = None


class RegionsIn(_Body):
    regions: Annotated[list[RegionSettingIn], Field(min_length=1, max_length=50)]


# --- Feeds ------------------------------------------------------------------------------


class FeedSourceIn(_Body):
    url: Annotated[str, Field(min_length=9, max_length=1000)]
    format: Literal["csv", "json"]
    mode: Literal["upsert", "replace"] = "replace"


# --- Inbox --------------------------------------------------------------------------------


class QuoteLineIn(_Body):
    sku: Sku
    variant_id: Annotated[str, Field(min_length=1, max_length=64)]
    price: Major


class InboxQuoteIn(_Body):
    # Lines left out keep the listed unit price.
    lines: Annotated[list[QuoteLineIn], Field(max_length=200)] = []
    delivery_fee: Major | None = None
    delivery_days_min: Days | None = None
    delivery_days_max: Days | None = None
    valid_days: Annotated[int, Field(ge=1, le=30)] = 30
    message: Annotated[str, Field(max_length=2000)] | None = None


class ReasonIn(_Body):
    reason: Annotated[str, Field(max_length=500)] | None = None


class ShipIn(_Body):
    carrier: Annotated[str, Field(min_length=1, max_length=80)]
    reference: Annotated[str, Field(min_length=1, max_length=120)]


# --- Billing and team ---------------------------------------------------------------------


class ListingIn(_Body):
    plan: Annotated[str, Field(min_length=1, max_length=32)]


class InviteIn(_Body):
    email: EmailStr
    role: Literal["owner", "catalogue", "orders", "viewer"]


class RoleIn(_Body):
    role: Literal["owner", "catalogue", "orders", "viewer"]


class AcceptInviteIn(_Body):
    token: Annotated[str, Field(min_length=20, max_length=100)]


class KeyIn(_Body):
    name: Annotated[str, Field(min_length=1, max_length=100)]
