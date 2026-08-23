"""Redis connection infrastructure."""

from redis.asyncio import Redis

from meetinghq_api.core.config import get_settings

redis_client: Redis = Redis.from_url(
    get_settings().redis_url,
    encoding="utf-8",
    decode_responses=True,
)
