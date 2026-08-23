"""Typed application configuration."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed API settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MEETINGHQ_",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    environment: str = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"  # noqa: S104 - container bind address
    api_port: int = 8000
    api_cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    database_url: str = "postgresql+asyncpg://meetinghq:meetinghq_dev_only@localhost:5432/meetinghq"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = Field(
        default="local-development-secret-change-me",
        min_length=32,
        repr=False,
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = Field(default=15, gt=0)
    refresh_token_ttl_days: int = Field(default=30, gt=0)
    jwt_issuer: str = "meetinghq"
    jwt_audience: str = "meetinghq-api"
    refresh_cookie_name: str = "meetinghq_refresh"
    csrf_cookie_name: str = "meetinghq_csrf"
    secure_cookies: bool = False
    password_reset_ttl_minutes: int = Field(default=30, gt=0)
    email_verification_ttl_hours: int = Field(default=24, gt=0)
    login_max_failures: int = Field(default=5, gt=0)
    login_lock_minutes: int = Field(default=15, gt=0)
    auth_rate_limit_requests: int = Field(default=10, gt=0)
    auth_rate_limit_window_seconds: int = Field(default=60, gt=0)
    super_admin_email: str | None = None
    super_admin_password: str | None = Field(default=None, min_length=12, repr=False)
    super_admin_first_name: str = "Platform"
    super_admin_last_name: str = "Administrator"
    storage_provider: str = "local"
    local_storage_path: str = "./storage"
    public_storage_url: str = "/api/v1/storage"
    invitation_ttl_days: int = Field(default=7, gt=0)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, gt=0, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = Field(default=None, repr=False)
    smtp_from_email: str = "meetings@meetinghq.local"
    smtp_starttls: bool = True
    email_outbox_path: str = "./storage/outbox"
    reminder_poll_seconds: int = Field(default=30, ge=5, le=300)
    embedded_reminder_worker: bool = True
    initial_super_admin_email: str | None = Field(
        default=None, validation_alias="INITIAL_SUPER_ADMIN_EMAIL"
    )
    initial_super_admin_password: str | None = Field(
        default=None,
        min_length=8,
        repr=False,
        validation_alias="INITIAL_SUPER_ADMIN_PASSWORD",
    )
    initial_super_admin_first_name: str | None = Field(
        default=None, validation_alias="INITIAL_SUPER_ADMIN_FIRST_NAME"
    )
    initial_super_admin_last_name: str | None = Field(
        default=None, validation_alias="INITIAL_SUPER_ADMIN_LAST_NAME"
    )
    initial_organization_name: str | None = Field(
        default=None, validation_alias="INITIAL_ORGANIZATION_NAME"
    )
    initial_workspace_name: str | None = Field(
        default=None, validation_alias="INITIAL_WORKSPACE_NAME"
    )

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Normalize and validate the configured logging threshold."""
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""
    return Settings()
