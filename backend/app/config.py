"""Application configuration.

All runtime configuration is sourced from environment variables (or a local
`.env` file during development). Nothing secret is ever hardcoded here.
"""

from __future__ import annotations

import functools
from typing import Literal

from pydantic import Field, ValidationInfo, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "staging", "production"]

# Placeholder values shipped in `.env.example`. They must never reach a
# non-development deployment.
_FORBIDDEN_SECRETS = {
    "CHANGE_ME",
    "CHANGE_ME_GENERATE_A_LONG_RANDOM_SECRET",
    "secret",
    "changeme",
}


class Settings(BaseSettings):
    """Typed, validated view over the process environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application --------------------------------------------------------
    app_name: str = "Kumaran Crackers API"
    app_env: AppEnv = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # ---- Security -----------------------------------------------------------
    secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    refresh_token_expire_days: int = Field(default=30, gt=0)

    # ---- Database -----------------------------------------------------------
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str = "kumaran"
    postgres_password: str = ""
    postgres_db: str = "kumaran_crackers"
    database_url: str | None = None
    test_database_url: str | None = None

    # ---- CORS ---------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Bootstrap admin ----------------------------------------------------
    first_admin_email: str = "admin@kumarancrackers.local"
    first_admin_password: str | None = None
    first_admin_full_name: str = "Kumaran Admin"

    # ---- Business rules -----------------------------------------------------
    currency: str = "INR"
    delivery_charge: float = 50.00
    free_delivery_threshold: float = 2000.00

    # ---- Regulatory ---------------------------------------------------------
    minimum_purchase_age: int = 18
    require_age_confirmation: bool = True

    # ---- Validators ---------------------------------------------------------
    @field_validator("secret_key")
    @classmethod
    def _reject_placeholder_secret(cls, value: str, info: ValidationInfo) -> str:
        """Refuse to boot a non-development server with a placeholder secret."""
        env = (info.data or {}).get("app_env", "development")
        if env != "development" and value in _FORBIDDEN_SECRETS:
            raise ValueError(
                "SECRET_KEY is still set to a placeholder value. Generate a real "
                'secret with: python -c "import secrets; '
                'print(secrets.token_urlsafe(64))"'
            )
        return value

    # ---- Derived values -----------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        """Full SQLAlchemy URL, built from parts unless explicitly overridden."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        """`CORS_ORIGINS` parsed into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@functools.lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so the `.env` file is parsed once. Tests clear the cache via
    `get_settings.cache_clear()` after patching the environment.
    """
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
