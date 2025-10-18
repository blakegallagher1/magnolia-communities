"""
Redis cache client configuration.
"""

import json
from typing import Any, Optional

from redis.asyncio import Redis, from_url

from app.core.config import settings
from app.core.metrics import record_cache_operation

redis_client: Optional[Redis] = None


async def get_redis() -> Redis:
    """Get Redis client instance."""
    global redis_client
    if redis_client is None:
        redis_client = from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
        )
    return redis_client


async def close_redis():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()


class CacheService:
    """Redis caching service with JSON serialization."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        value = await self.redis.get(key)
        if value is not None:
            record_cache_operation("hit")
            return json.loads(value)
        record_cache_operation("miss")
        return None

    async def set(
        self, key: str, value: Any, ttl: int = settings.REDIS_CACHE_TTL
    ) -> bool:
        """Set value in cache with TTL."""
        serialized = json.dumps(value, default=str)
        success = await self.redis.setex(key, ttl, serialized)
        if success:
            record_cache_operation("set")
        return success

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        deleted = bool(await self.redis.delete(key))
        if deleted:
            record_cache_operation("delete")
        return deleted

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        exists = bool(await self.redis.exists(key))
        record_cache_operation("exists")
        return exists

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            deleted = await self.redis.delete(*keys)
            if deleted:
                record_cache_operation("invalidate")
            return deleted
        return 0
