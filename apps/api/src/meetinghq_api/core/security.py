"""JWT primitives for future authentication modules."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Protocol

import jwt

from meetinghq_api.core.config import Settings


class TokenCodec(Protocol):
    """Contract for encoding and decoding signed JWTs."""

    def encode(self, subject: str, claims: Mapping[str, object] | None = None) -> str:
        """Create a signed access token."""

    def decode(self, token: str) -> dict[str, object]:
        """Validate a token and return its claims."""


class JwtTokenCodec:
    """PyJWT-backed token codec without authentication policy."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def encode(self, subject: str, claims: Mapping[str, object] | None = None) -> str:
        now = datetime.now(UTC)
        payload: dict[str, object] = {
            **(claims or {}),
            "sub": subject,
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=self._settings.jwt_access_token_ttl_minutes),
        }
        return jwt.encode(
            payload,
            self._settings.jwt_secret,
            algorithm=self._settings.jwt_algorithm,
        )

    def decode(self, token: str) -> dict[str, object]:
        return jwt.decode(
            token,
            self._settings.jwt_secret,
            algorithms=[self._settings.jwt_algorithm],
            issuer=self._settings.jwt_issuer,
            audience=self._settings.jwt_audience,
        )
