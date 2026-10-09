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

    # --- Shared plumbing (PF14 owns the production adapters) -----------------
    # "local": files under storage_dir, served by /files with HMAC-signed URLs.
    storage_backend: str = "local"
    storage_dir: str = "./storage"
    # HMAC key for local signed URLs; empty derives one from secret_key.
    storage_url_secret: str = ""
    # inline (an asyncio loop in the API process) | worker | off (tests).
    background_tasks: str = "inline"
    # memory (in-process token buckets).
    ratelimit_backend: str = "memory"

    # --- Mail (PF14 Plumbing; first user PF3) ----------------------------------
    # console: printed to the API log and kept in app.mail.OUTBOX (dev, tests).
    # smtp: PF14's relay adapter.
    mail_backend: str = "console"
    mail_from: str = "Truebex <no-reply@truebex.com>"

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
