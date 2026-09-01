"""Integration Center API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

SmtpState = Literal[
    "not_configured", "configured", "testing", "healthy", "degraded", "failed", "disabled"
]
SmtpPriority = Literal["low", "normal", "high"]


class IntegrationResponse(BaseModel):
    key: str
    name: str
    category: str
    description: str
    auth_type: str
    enabled: bool
    configured: bool
    validated: bool
    health: Literal["healthy", "attention", "disabled"]
    updated_at: datetime | None
    last_tested_at: datetime | None


class IntegrationConfigurationUpdate(BaseModel):
    values: dict[str, object] = Field(min_length=1)


class IntegrationOperationResponse(BaseModel):
    key: str
    configured: bool
    message: str


class IntegrationTestResponse(BaseModel):
    key: str
    status: Literal["healthy", "attention"]
    message: str
    latency_ms: int
    checked_at: datetime


class IntegrationAuditResponse(BaseModel):
    action: str
    status: str
    created_at: datetime
    actor_id: str | None
    latency_ms: int | None = None
    diagnostic: str | None = None
    recipient: str | None = None
    revision: int | None = None


class SmtpConfigurationUpdate(BaseModel):
    """Validated tenant SMTP settings; passwords are write-only."""

    provider_display_name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(gt=0, le=65535)
    security_mode: Literal["starttls", "ssl_tls", "none"] = "starttls"
    allow_insecure: bool = False
    connection_timeout: int = Field(default=20, ge=1, le=120)
    authentication_enabled: bool = True
    authentication_method: Literal["password"] = "password"
    username: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, max_length=2048, repr=False)
    from_email: EmailStr
    from_name: str = Field(default="MeetingHQ", min_length=1, max_length=120)
    reply_to: EmailStr | None = None
    return_path: EmailStr | None = None
    enabled: bool = True
    max_retry_attempts: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: float = Field(default=1, ge=0, le=300)
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    default_priority: SmtpPriority = "normal"

    @model_validator(mode="after")
    def validate_security(self) -> "SmtpConfigurationUpdate":
        if self.security_mode == "none" and not self.allow_insecure:
            raise ValueError("Unencrypted SMTP requires explicit insecure transport approval")
        if self.authentication_enabled and not (self.username or "").strip():
            raise ValueError("Username is required when SMTP authentication is enabled")
        return self


class SmtpConfigurationResponse(BaseModel):
    provider_display_name: str
    host: str
    port: int
    security_mode: Literal["starttls", "ssl_tls", "none"]
    allow_insecure: bool
    connection_timeout: int
    authentication_enabled: bool
    authentication_method: str
    username: str | None
    password_configured: bool
    password_mask: str | None
    from_email: str
    from_name: str
    reply_to: str | None
    return_path: str | None
    enabled: bool
    max_retry_attempts: int
    retry_delay_seconds: float
    timeout_seconds: int
    default_priority: SmtpPriority
    state: SmtpState
    revision: int
    updated_at: datetime | None
    last_validated_at: datetime | None


class SmtpTestEmailRequest(BaseModel):
    recipient: EmailStr


class SmtpTestEmailResponse(BaseModel):
    status: Literal["accepted", "failed"]
    message: str
    recipient: EmailStr
    message_id: str | None
    latency_ms: int
    accepted_at: datetime | None
