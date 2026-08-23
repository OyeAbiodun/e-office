"""Redis-backed authentication rate-limit hook."""

from meetinghq_api.core.config import Settings
from meetinghq_api.core.errors import RateLimitError
from meetinghq_api.infrastructure.redis import redis_client


class AuthRateLimiter:
    """Fixed-window limiter for sensitive unauthenticated operations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check(self, action: str, identity: str) -> None:
        """Consume one request from the configured action/identity budget."""
        key = f"rate-limit:auth:{action}:{identity}"
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, self._settings.auth_rate_limit_window_seconds)
            if count > self._settings.auth_rate_limit_requests:
                raise RateLimitError("Too many requests. Please try again later.")
        except RateLimitError:
            raise
        except Exception:
            # Availability wins when the optional limiter is unavailable; production
            # monitoring must alert on Redis readiness independently.
            return
