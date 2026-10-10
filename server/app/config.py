"""Application settings, loaded from environment / .env file."""

from datetime import date
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Secret used to sign JWTs. MUST be overridden in production via .env.
    secret_key: str = "CHANGE_ME_TO_A_LONG_RANDOM_STRING"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # SQLite file living next to the server. Use an absolute path in prod.
    database_url: str = "sqlite:///./auth.db"

    # Comma-separated list of allowed CORS origins for the browser frontend.
    # Include your cloudflared hostname and any local dev origins.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Public URLs, used to build payment redirect and webhook URLs.
    site_url: str = "https://truebex.com"
    api_url: str = "https://api.truebex.com"

    # Google Sign-In: the OAuth 2.0 Web client ID from Google Cloud Console.
    # Empty disables POST /auth/google.
    google_client_id: str = ""

    # --- Billing (PF2) ---------------------------------------------------------
    # The provider offered at checkout: "paddle" (merchant of record, the
    # default) or "stripe". Prices come from catalogue.json, mirrored to the
    # provider by scripts/sync_prices.py into the provider_prices table.
    billing_provider: str = "paddle"

    # Paddle Billing. Empty API key disables Paddle.
    # "sandbox" or "production".
    paddle_env: str = "sandbox"
    paddle_api_key: str = ""
    # The notification destination's secret key (pdl_ntfset_...).
    paddle_webhook_secret: str = ""
    # Client-side token for Paddle.js on /checkout/. Public by design.
    paddle_client_token: str = ""
    # Override the API host (tests, server/tests/mock_paddle.py). Empty means
    # Paddle's host for paddle_env.
    paddle_api_base: str = ""

    # Stripe (card subscriptions, business invoices). Empty secret key
    # disables Stripe.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Price id (price_...) of the original monthly Pro price. New checkouts
    # use provider_prices; this stays so existing subscribers keep Pro.
    stripe_price_pro: str = ""
    # Stripe Tax: automatic_tax on Checkout and invoices.
    stripe_tax_enabled: bool = False

    # Background jobs (server/app/tasks.py): inline | worker | off.
    background_tasks: str = "inline"

    # Wayl (Iraq: QiCard, FIB, ZainCash). Dormant: off unless WAYL_ENABLED
    # is true AND its keys are set. Never offered on the website.
    wayl_enabled: bool = False
    wayl_api_key: str = ""
    wayl_api_base: str = "https://api.thewayl.com"
    # "live" or "test".
    wayl_env: str = "live"
    # Secret Wayl echoes back on webhooks (10-255 chars).
    wayl_webhook_secret: str = ""
    # Price of one Pro month in IQD (Wayl's minimum is 1000).
    wayl_price_pro_iqd: int = 130_000

    # --- Subscription consumer rules (PF2b; guides/GD5 §7.1-7.4) -------------
    # Built now, switched OFF until the owner's solicitor approves the wording.
    # UK DMCC Act 2024 subscription rules: renewal reminders, the trial-end
    # notice and the renewal cooling-off refund (GD5 §7.3; QS-18).
    subscription_notices_enabled: bool = False
    # Nothing is sent or offered before this day (GD5: "January 2027",
    # confirm at writing time).
    subscription_rules_from: date = date(2027, 1, 1)
    # Reminder lead times in days. GD5 names none: 14 before an annual
    # renewal, 3 before a monthly one, 3 before a trial ends.
    renewal_reminder_days_year: int = 14
    renewal_reminder_days_month: int = 3
    trial_end_notice_days: int = 3
    # The EU withdrawal function, Directive 2011/83/EU Art. 11a (GD5 §7.2; QS-18).
    eu_withdrawal_enabled: bool = False
    # GD5 §7.4 is a DRAFT. While false no 7.4 sentence renders on a page or in
    # a mail, and today's placeholder consent (billing/consent.py) stays. The
    # site needs NEXT_PUBLIC_LEGAL_WORDING_APPROVED=true at build time as well.
    legal_wording_approved: bool = False
    # QS-17: is the plan digital content (consent ends the right to cancel) or
    # a service (a customer who cancels pays for the days used)?
    consent_variant: Literal["digital_content", "service"] = "digital_content"
    # Trading disclosures in the confirmation e-mail (GD5 §1.3, QS-2): the
    # company's registered office; links to the documents in force. An empty
    # EULA_URL uses the terms page.
    company_address: str = ""
    eula_url: str = ""

    # --- Licence API (PF1, contract licence-api) -------------------------------
    # base64url Ed25519 seed that signs entitlements (server/scripts/
    # make_signing_key.py --kind lic). Lives only in server/.env. Empty
    # switches activation, entitlements and trials off (503 unavailable).
    licence_signing_key: str = ""
    licence_key_id: str = "lic-2026-10"
    # Public halves published by GET /licence/keys, as "kid:key,kid:key".
    # The rel-* private seeds never live on this host.
    release_public_keys: str = ""
    # Older lic-* public keys kept valid during a rotation (contract §3).
    signing_keys_extra: str = ""
    trial_days: int = 14

    # --- Operations and shared plumbing (PF14) --------------------------------
    # Blob storage: "local" (files under storage_dir, served by /files with
    # HMAC-signed URLs) or "s3" (any S3-compatible bucket, presigned URLs).
    storage_backend: str = "local"
    storage_dir: str = "./storage"
    # HMAC key for local signed URLs; empty derives one from secret_key.
    storage_url_secret: str = ""
    s3_endpoint: str = ""
    s3_region: str = "auto"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    # CDN hostname in front of the public, cacheable prefixes (tiles/, shares/,
    # releases/). Empty = presigned URLs for everything.
    cdn_base_url: str = ""

    # Mail: "console" (kept in app.mail.OUTBOX and logged) or "smtp".
    mail_backend: str = "console"
    mail_from: str = "Truebex <hello@truebex.com>"
    support_email: str = "hello@truebex.com"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # background_tasks (inline | worker | off) is under Billing above:
    # "inline" runs the asyncio loop inside the API process, "worker" the
    # separate `python -m app.worker` process.
    # "memory" (one API process) or "db" (shared buckets in the database).
    ratelimit_backend: str = "memory"

    # Alerts from the server's own checks (backups); uptime alerts come from
    # the hosted monitor. alert_push_url: an ntfy-style topic URL (phone push).
    alert_email: str = ""
    alert_push_url: str = ""
    # True on the production host: a missing backup marker is then an alert.
    backup_expected: bool = False

    # Telemetry ingestion (contracts/telemetry.md). The kill switch stops
    # usage events (5.1 `enabled: false`); ingestion off answers 503.
    telemetry_events_enabled: bool = True
    telemetry_ingestion_enabled: bool = True
    # rust-minidump's stackwalker; absent = symbolicate the sent callstack only.
    minidump_stackwalk: str = "minidump-stackwalk"

    # --- Organisations, seats and SSO (PF3) -------------------------------------
    # Fernet key sealing SSO client secrets (python -c "from cryptography.fernet
    # import Fernet; print(Fernet.generate_key().decode())"). Empty derives one
    # from SECRET_KEY.
    sso_secret_key: str = ""
    # The SAML entity id of this service provider. Empty: each organisation's
    # own SP metadata URL ({API_URL}/auth/sso/saml/<slug>/metadata).
    saml_sp_entity_id: str = ""
    # Audit events are kept this long (24 months until GD5 says otherwise).
    audit_retention_days: int = 730

    # --- Share pages (PF5, contract share-bundle) ------------------------------
    # Share links are ${SHARE_BASE_URL}/view/{slug}; empty = API_URL (PF14 later
    # points share.truebex.com at the API and sets this).
    share_base_url: str = ""
    # Longest expiry and bytes per bundle until GD7 sets them per tier
    # (licence-api §6.3 MINOR proposal: limits.share_days, limits.share_bytes).
    share_max_days: int = 30
    share_max_bytes: int = 1024 * 1024 * 1024

    @property
    def share_base(self) -> str:
        return (self.share_base_url or self.api_url).rstrip("/")

    # --- Marketplace (PF7, contract marketplace-api) --------------------------
    # Card payments for orders. Off until GD5 signs off the marketplace terms:
    # every supplier is quote-only while it is off.
    market_payments_enabled: bool = False
    # Signing secret(s) of the Stripe endpoint for /market/webhooks/stripe
    # (checkout and Connect account events), "whsec_a,whsec_b". Empty = 404.
    stripe_connect_webhook_secret: str = ""
    # Anonymous catalogue reads (5.1-5.6) per address per minute.
    market_reads_per_minute: int = 120
    # Picture search: "" (off), "stub" (tests, local trials) or "clip-vit-b32"
    # (ONNX files fetched into EMBEDDING_DIR by scripts/fetch_models.py).
    embedding_model: str = ""
    embedding_dir: str = "./models"

    # --- Supplier portal (PF8) --------------------------------------------------
    # The daily pull of registered feed URLs (contract 5.12), hour in UTC.
    feed_pull_hour_utc: int = 2
    # Local trials only: a fixture folder whose media-map.json serves the
    # feed's picture and 3D URLs from files (tests/contracts/marketplace), so
    # the contract's feed imports without the internet. Empty in production.
    market_media_fixtures: str = ""

    # --- Project service (PF4, contract project-log) ---------------------------
    # Presence (5.17): "memory" (one API process) or "db" (the presence table,
    # several processes; PF14).
    projects_presence_backend: str = "memory"
    # Long-poll pulls (5.7) waiting at once per account; more answer 429.
    projects_max_waiting_pulls: int = 20

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def paddle_api_url(self) -> str:
        if self.paddle_api_base:
            return self.paddle_api_base.rstrip("/")
        if self.paddle_env == "production":
            return "https://api.paddle.com"
        return "https://sandbox-api.paddle.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
