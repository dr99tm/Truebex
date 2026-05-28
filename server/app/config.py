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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
