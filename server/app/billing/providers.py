"""The registry of payment providers behind the BillingProvider interface.

`get_provider(name)` returns an adapter; `checkout_provider()` the one
BILLING_PROVIDER offers at checkout. A provider is enabled only when its keys
are set in server/.env (Wayl also needs WAYL_ENABLED); otherwise it is hidden
from the site and its endpoints answer 404 or 503.

The HTTP client factories live here so tests can swap them for a mock
transport (`monkeypatch.setattr(providers, "_paddle_client", ...)`).
"""

import httpx

from ..config import Settings, get_settings
from . import paddle_provider, stripe_provider, wayl_provider
from .base import (
    BillingProvider,
    Invoice,
    InvoiceLine,
    InvoiceScope,
    NotSupported,
    ProviderError,
    WebhookError,
)

__all__ = [
    "BillingProvider",
    "Invoice",
    "InvoiceLine",
    "InvoiceScope",
    "NotSupported",
    "ProviderError",
    "WebhookError",
    "checkout_provider",
    "enabled_providers",
    "get_provider",
]

_CLASSES: dict[str, type[BillingProvider]] = {
    "paddle": paddle_provider.PaddleProvider,
    "stripe": stripe_provider.StripeProvider,
    "wayl": wayl_provider.WaylProvider,
}

# Listed on /billing/plans in this order; the site never offers wayl.
ORDER = ("paddle", "stripe", "wayl")


def _paddle_client(s: Settings) -> httpx.Client:
    return paddle_provider.make_client(s)


def _wayl_client(s: Settings) -> httpx.Client:
    return wayl_provider.make_client(s)


def get_provider(name: str, settings: Settings | None = None) -> BillingProvider:
    cls = _CLASSES.get(name)
    if cls is None:
        raise KeyError(name)
    return cls(settings or get_settings())


def enabled_providers(settings: Settings | None = None) -> list[str]:
    s = settings or get_settings()
    return [name for name in ORDER if get_provider(name, s).enabled()]


def checkout_provider(settings: Settings | None = None) -> BillingProvider | None:
    """BILLING_PROVIDER when its keys are set, else None (checkout answers 503)."""
    s = settings or get_settings()
    name = (s.billing_provider or "").lower()
    if name not in ("paddle", "stripe"):
        return None
    provider = get_provider(name, s)
    return provider if provider.enabled() else None
