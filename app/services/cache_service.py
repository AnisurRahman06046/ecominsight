"""Caching service for query results."""

import json
import hashlib
from typing import Any, Optional
import logging
from datetime import timedelta

# Make Redis optional
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Service for caching query results."""

    def __init__(self):
        self.redis_client = None
        self.enabled = REDIS_AVAILABLE and settings.enable_cache and settings.redis_url
        self.ttl = settings.cache_ttl

        if not REDIS_AVAILABLE and settings.enable_cache:
            logger.warning("Redis not installed - caching disabled")

    async def initialize(self):
        """Initialize cache connection."""
        if not self.enabled:
            logger.info("Cache disabled or Redis URL not configured")
            return

        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis_client.ping()
            logger.info("Cache service connected to Redis")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Cache disabled.")
            self.enabled = False

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.enabled or not self.redis_client:
            return None

        try:
            # Hash the key for consistency
            hashed_key = self._hash_key(key)
            value = await self.redis_client.get(hashed_key)

            if value:
                return json.loads(value)
            return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL."""
        if not self.enabled or not self.redis_client:
            return False

        try:
            # Hash the key
            hashed_key = self._hash_key(key)

            # Serialize value
            serialized = json.dumps(value, default=str)

            # Set with TTL
            ttl_seconds = ttl or self.ttl
            await self.redis_client.setex(
                hashed_key,
                timedelta(seconds=ttl_seconds),
                serialized,
            )

            return True

        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.enabled or not self.redis_client:
            return False

        try:
            hashed_key = self._hash_key(key)
            await self.redis_client.delete(hashed_key)
            return True

        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if not self.enabled or not self.redis_client:
            return 0

        try:
            # Find all keys matching pattern
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)

            # Delete all matching keys
            if keys:
                await self.redis_client.delete(*keys)

            return len(keys)

        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            return 0

    async def ping(self) -> bool:
        """Check if cache is available."""
        if not self.enabled or not self.redis_client:
            return False

        try:
            await self.redis_client.ping()
            return True
        except:
            return False

    def _hash_key(self, key: str) -> str:
        """Hash key for consistent storage."""
        return f"ecom_insights:{hashlib.md5(key.encode()).hexdigest()}"

    async def close(self):
        """Close cache connection."""
        if self.redis_client:
            await self.redis_client.close()


# Global instance
cache_service = CacheService()