"""Safe application errors exposed by the HTTP boundary."""


class ApplicationError(Exception):
    """Base class for expected client-safe failures."""

    status_code = 400
    code = "application_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AuthenticationError(ApplicationError):
    """Authentication failed without revealing identity state."""

    status_code = 401
    code = "authentication_failed"


class AuthorizationError(ApplicationError):
    """The authenticated identity lacks a capability."""

    status_code = 403
    code = "permission_denied"


class ConflictError(ApplicationError):
    """A unique identity or tenant attribute already exists."""

    status_code = 409
    code = "conflict"


class NotFoundError(ApplicationError):
    """The requested resource is not visible to the caller."""

    status_code = 404
    code = "not_found"


class RateLimitError(ApplicationError):
    """The caller exceeded a configured request budget."""

    status_code = 429
    code = "rate_limited"


class InfrastructureUnavailableError(ApplicationError):
    """A required security or infrastructure dependency is unavailable."""

    status_code = 503
    code = "infrastructure_unavailable"
