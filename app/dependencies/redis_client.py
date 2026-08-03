"""
Shared async Redis client used for the token blacklist, rate limiting,
and general-purpose caching.
"""

from redis.asyncio import Redis, from_url

from app.core.config import settings

_redis: Redis | None = None


def get_redis_pool() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def get_redis() -> Redis:
    """FastAPI dependency."""
    return get_redis_pool()


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
