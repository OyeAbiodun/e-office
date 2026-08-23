"""Shared API test fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from meetinghq_api.main import app
from meetinghq_api.modules.auth.infrastructure.rate_limit import AuthRateLimiter


@pytest.fixture(autouse=True)
def disable_auth_rate_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep isolated API tests independent from shared Redis rate-limit windows."""

    async def allow_request(_: AuthRateLimiter, __: str, ___: str) -> None:
        return None

    monkeypatch.setattr(AuthRateLimiter, "check", allow_request)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Provide an in-process HTTP client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
