"""Small helpers every marketplace module shares: ids, the clock, money in
minor units (contract §6.3) and the errors of contract §7."""

import re
import secrets
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any

from ..contract_http import ContractError
from ..licence import clock

CONTRACT_NAME = "marketplace-api"
CONTRACT_MAJOR, CONTRACT_MINOR = 1, 1
CONTRACT_VERSION = f"{CONTRACT_NAME}/{CONTRACT_MAJOR}.{CONTRACT_MINOR}"

HEX32 = re.compile(r"^[0-9a-f]{32}$")
REGION_RE = re.compile(r"^[A-Z]{2}(-[A-Z0-9]{1,3})?$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

KINDS = ("object", "material", "finish", "theme")
AVAILABILITY_STATES = ("in_stock", "low_stock", "made_to_order", "out_of_stock", "discontinued")
# Lines in these states can be ordered (made_to_order with its lead time).
ORDERABLE_STATES = frozenset({"in_stock", "low_stock", "made_to_order"})


def new_id() -> str:
    """A fresh 32-hex id (suppliers, products, orders, reviews, feed runs)."""
    return secrets.token_hex(16)


def now() -> datetime:
    return clock.now()


rfc3339 = clock.rfc3339
aware = clock.aware


def is_hex32(value: Any) -> bool:
    return isinstance(value, str) and bool(HEX32.match(value))


# --- Money ------------------------------------------------------------------------------


def money(amount: int, currency: str, exponent: int) -> dict:
    return {"amount": int(amount), "currency": currency, "exponent": int(exponent)}


def div_half_even(numerator: int, denominator: int) -> int:
    """numerator / denominator rounded half to even, on integers only."""
    q, r = divmod(numerator, denominator)
    twice = 2 * r
    if twice > denominator or (twice == denominator and q % 2 == 1):
        q += 1
    return q


def net_of_tax(amount: int, rate_bp: int) -> int:
    """The value excluding tax of a tax-inclusive amount (GD1 §4.2:
    129 900 × 10 000 / 12 000, rounded half-even)."""
    return div_half_even(amount * 10_000, 10_000 + rate_bp)


def tax_on(amount: int, rate_bp: int, includes_tax: bool) -> int:
    """The tax contained in (inclusive) or added to (exclusive) an amount."""
    if includes_tax:
        return amount - net_of_tax(amount, rate_bp)
    return div_half_even(amount * rate_bp, 10_000)


def apply_bp(amount: int, rate_bp: int) -> int:
    return div_half_even(amount * rate_bp, 10_000)


_DECIMAL = re.compile(r"^(\d+)(?:\.(\d+))?$")


def parse_major(text: str, exponent: int) -> int:
    """`"1299.00"` with exponent 2 → 129900. Raises ValueError for a sign, a
    thousands separator, a currency symbol, more decimals than the currency
    has, or anything that is not a plain decimal (contract §6.4 bad_price)."""
    m = _DECIMAL.match(text.strip()) if isinstance(text, str) else None
    if m is None:
        raise ValueError("not a decimal")
    whole, frac = m.group(1), m.group(2) or ""
    if len(frac) > exponent:
        raise ValueError("too many decimals")
    value = int(whole) * 10**exponent + (int(frac.ljust(exponent, "0")) if exponent else 0)
    if value > 10**12:
        raise ValueError("too large")
    return value


def parse_percent_bp(text: str) -> int:
    """`"20"` → 2000, `"5.5"` → 550 (at most two decimals, 0–100 %)."""
    try:
        value = Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("not a number")
    if not value.is_finite() or value < 0 or value > 100:
        raise ValueError("out of range")
    bp = value * 100
    if bp != bp.to_integral_value(rounding=ROUND_HALF_EVEN):
        raise ValueError("too many decimals")
    return int(bp)


def format_major(amount: int, exponent: int) -> str:
    """129900, 2 → "1299.00" (reports and e-mails; never parsed back)."""
    if exponent == 0:
        return str(amount)
    sign = "-" if amount < 0 else ""
    whole, frac = divmod(abs(amount), 10**exponent)
    return f"{sign}{whole}.{frac:0{exponent}d}"


# --- Errors (contract §7) --------------------------------------------------------------


def not_found(what: str = "That item") -> ContractError:
    return ContractError("not_found", 404, f"{what} was not found.")


def invalid(field: str, message: str, where: str = "query") -> ContractError:
    return ContractError(
        "validation_failed",
        422,
        f"{field}: {message}",
        {"fields": [{"field": field, "in": where, "message": message}]},
    )


def forbidden(detail: str = "That belongs to another account.") -> ContractError:
    return ContractError("forbidden", 403, detail)
