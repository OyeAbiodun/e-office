"""Canonical shared application exceptions."""

from meetinghq_api.core.errors import (
    ApplicationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)


class ValidationError(ConflictError):
    """A business input violates deterministic domain rules."""

    status_code = 422
    code = "validation_error"


__all__ = [
    "ApplicationError",
    "AuthorizationError",
    "ConflictError",
    "NotFoundError",
    "ValidationError",
]
