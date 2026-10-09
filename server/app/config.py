"""Application settings, loaded from environment / .env file."""

from functools import lru_cache

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

    # Stripe (card subscriptions). Empty secret key disables Stripe.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Stripe Price id (price_...) of the recurring monthly Pro price.
    stripe_price_pro: str = ""

    # Wayl (Iraq: QiCard, FIB, ZainCash). Empty key disables Wayl.
    wayl_api_key: str = ""
    wayl_api_base: str = "https://api.thewayl.com"
    # "live" or "test".
    wayl_env: str = "live"
    # Secret Wayl echoes back on webhooks (10-255 chars).
    wayl_webhook_secret: str = ""
    # Price of one Pro month in IQD (Wayl's minimum is 1000).
    wayl_price_pro_iqd: int = 130_000

    # --- Operations (PF14) ----------------------------------------------------
    # Blob storage: "local" (files under storage_dir, served by /files with
    # HMAC-signed URLs) or "s3" (any S3-compatible bucket, presigned URLs).
    storage_backend: str = "local"
    storage_dir: str = "./storage"
    # Signs /files URLs of the local adapter. Empty = derived from secret_key.
    storage_signing_key: str = ""
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

    # Background jobs: "inline" (asyncio loop inside the API process),
    # "worker" (the separate `python -m app.worker` process) or "off".
    background_tasks: str = "inline"
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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
