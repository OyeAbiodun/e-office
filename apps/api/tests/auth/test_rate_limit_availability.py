"""Authentication limiting fails securely in hardened environments."""

import pytest

from meetinghq_api.core.config import Settings
from meetinghq_api.core.errors import InfrastructureUnavailableError
from meetinghq_api.modules.auth.infrastructure import rate_limit
from meetinghq_api.modules.auth.infrastructure.rate_limit import AuthRateLimiter

original_check = AuthRateLimiter.check


async def test_rate_limiter_fails_closed_when_required(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unavailable(_key: str) -> int:
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(rate_limit.redis_client, "incr", unavailable)
    settings = Settings(
        jwt_secret="a-secure-test-secret-that-is-long-enough",  # noqa: S106
        auth_rate_limit_fail_closed=True,
    )

    with pytest.raises(InfrastructureUnavailableError):
        await original_check(AuthRateLimiter(settings), "login", "127.0.0.1:user@example.test")


async def test_rate_limiter_can_fail_open_for_local_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(_key: str) -> int:
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(rate_limit.redis_client, "incr", unavailable)
    settings = Settings(
        jwt_secret="a-secure-test-secret-that-is-long-enough",  # noqa: S106
        auth_rate_limit_fail_closed=False,
    )

    await original_check(AuthRateLimiter(settings), "login", "127.0.0.1:user@example.test")
