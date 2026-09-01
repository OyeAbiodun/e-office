"""Typed application configuration."""

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
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

    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"  # noqa: S104 - container bind address
    api_port: int = 8000
    api_cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    web_app_url: str = "http://localhost:5173"

    database_url: str = "postgresql+asyncpg://meetinghq:meetinghq_dev_only@localhost:5432/meetinghq"
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=200)
    database_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = Field(
        default="local-development-secret-change-me",
        min_length=32,
        repr=False,
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = Field(default=15, gt=0)
    refresh_token_ttl_days: int = Field(default=30, gt=0)
    refresh_token_cookie_retry_grace_seconds: int = Field(default=10, ge=0, le=60)
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
    auth_rate_limit_fail_closed: bool = False
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
    smtp_timeout_seconds: int = Field(default=20, ge=1, le=120)
    smtp_max_attempts: int = Field(default=3, ge=1, le=5)
    smtp_retry_base_seconds: float = Field(default=0.5, ge=0, le=30)
    delivery_max_attempts: int = Field(default=5, ge=1, le=20)
    delivery_retry_base_seconds: int = Field(default=60, ge=5, le=3600)
    email_outbox_path: str = "./storage/outbox"
    reminder_poll_seconds: int = Field(default=30, ge=5, le=300)
    embedded_reminder_worker: bool = True
    storage_warning_free_percent: float = Field(default=10, ge=0, le=100)
    storage_critical_free_percent: float = Field(default=5, ge=0, le=100)
    disk_warning_used_percent: float = Field(default=90, ge=0, le=100)
    disk_critical_used_percent: float = Field(default=97, ge=0, le=100)
    memory_warning_used_percent: float = Field(default=90, ge=0, le=100)
    memory_critical_used_percent: float = Field(default=97, ge=0, le=100)
    cpu_warning_used_percent: float = Field(default=90, ge=0, le=100)
    cpu_critical_used_percent: float = Field(default=98, ge=0, le=100)
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

    @field_validator("web_app_url")
    @classmethod
    def normalize_web_app_url(cls, value: str) -> str:
        """Require an absolute HTTP(S) origin for generated application links."""
        normalized = value.rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("web_app_url must be an absolute HTTP(S) URL")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("web_app_url must contain only scheme, host, and optional port")
        return normalized

    @model_validator(mode="after")
    def validate_operational_profile(self) -> Self:
        """Fail closed when staging or production is configured unsafely."""
        if self.storage_critical_free_percent > self.storage_warning_free_percent:
            raise ValueError(
                "storage_critical_free_percent cannot exceed storage_warning_free_percent"
            )
        for critical, warning, label in (
            (self.disk_critical_used_percent, self.disk_warning_used_percent, "disk"),
            (self.memory_critical_used_percent, self.memory_warning_used_percent, "memory"),
            (self.cpu_critical_used_percent, self.cpu_warning_used_percent, "cpu"),
        ):
            if critical < warning:
                raise ValueError(f"{label}_critical_used_percent cannot be below warning")
        if self.environment not in {"staging", "production"}:
            return self
        problems: list[str] = []
        if self.jwt_secret == "local-development-secret-change-me":
            problems.append("MEETINGHQ_JWT_SECRET must not use the development value")
        if not self.secure_cookies:
            problems.append("MEETINGHQ_SECURE_COOKIES must be true")
        if not self.redis_url:
            problems.append("MEETINGHQ_REDIS_URL is required")
        if not self.auth_rate_limit_fail_closed:
            problems.append("MEETINGHQ_AUTH_RATE_LIMIT_FAIL_CLOSED must be true")
        if urlparse(self.web_app_url).scheme != "https":
            problems.append("MEETINGHQ_WEB_APP_URL must use HTTPS")
        if not self.api_cors_origins or any(
            origin == "*" or urlparse(origin).scheme != "https" for origin in self.api_cors_origins
        ):
            problems.append("MEETINGHQ_API_CORS_ORIGINS must contain explicit HTTPS origins")
        if not self.trusted_hosts or "*" in self.trusted_hosts:
            problems.append("MEETINGHQ_TRUSTED_HOSTS must contain explicit hosts")
        if self.environment == "production" and self.storage_provider == "local":
            problems.append("MEETINGHQ_STORAGE_PROVIDER must be production object storage")
        if problems:
            raise ValueError("Unsafe deployment configuration: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""
    return Settings()
