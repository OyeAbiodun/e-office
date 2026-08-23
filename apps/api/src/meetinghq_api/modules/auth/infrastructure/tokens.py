"""Access, refresh, and one-time token primitives."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from meetinghq_api.core.config import Settings


def hash_token(token: str) -> str:
    """Return the non-reversible lookup hash for an opaque token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_opaque_token() -> str:
    """Create a URL-safe token with 256 bits of entropy."""
    return secrets.token_urlsafe(32)


def create_csrf_token() -> str:
    """Create a CSRF double-submit token."""
    return secrets.token_urlsafe(24)


class AccessTokenService:
    """Issue and validate short-lived JWT access tokens."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, user_id: uuid.UUID, organization_id: uuid.UUID, permissions: set[str]) -> str:
        """Issue an access token containing tenant and authorization context."""
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "org": str(organization_id),
            "permissions": sorted(permissions),
            "type": "access",
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=self._settings.jwt_access_token_ttl_minutes),
        }
        return jwt.encode(
            payload, self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm
        )

    def decode(self, token: str) -> dict[str, object]:
        """Validate an access token and return its claims."""
        claims: dict[str, object] = jwt.decode(
            token,
            self._settings.jwt_secret,
            algorithms=[self._settings.jwt_algorithm],
            issuer=self._settings.jwt_issuer,
            audience=self._settings.jwt_audience,
        )
        if claims.get("type") != "access":
            raise jwt.InvalidTokenError("Unexpected token type")
        return claims
