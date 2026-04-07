"""
Redis caching layer for performance optimization
"""

import json
import pickle
from typing import Any, Optional, Union
import logging
from datetime import timedelta
import redis.asyncio as redis
from app.core.settings import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Async Redis cache manager with connection pooling
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = settings.redis_enabled

    async def connect(self):
        """Connect to Redis with connection pooling"""
        if not self.enabled:
            logger.info("Redis caching is disabled")
            return
        try:
            # Create connection pool
            pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                max_connections=settings.redis_max_connections,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                decode_responses=False,  # We'll handle encoding ourselves
            )

            self.redis_client = redis.Redis(connection_pool=pool)

            # Test connection
            await self.redis_client.ping()
            logger.info("Connected to Redis cache")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.enabled = False
            self.redis_client = None

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")

    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage"""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value).encode("utf-8")
        else:
            return pickle.dumps(value)

    def _deserialize_value(self, value: bytes) -> Any:
        """Deserialize value from storage"""
        try:
            # Try JSON first (for simple types)
            return json.loads(value.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to pickle for complex objects
            return pickle.loads(value)

    def _get_key_with_prefix(self, key: str, prefix: str = "wedding_app") -> str:
        """Get key with application prefix"""
        return f"{prefix}:{key}"

    def build_key(self, key: str) -> str:
        """Expose the prefixed Redis key for low-level cache operations."""
        return self._get_key_with_prefix(key)

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        if not self.enabled or not self.redis_client:
            return default

        try:
            prefixed_key = self._get_key_with_prefix(key)
            value = await self.redis_client.get(prefixed_key)

            if value is None:
                return default

            return self._deserialize_value(value)

        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {str(e)}")
            return default

    async def set(
        self, key: str, value: Any, expire: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """
        Set value in cache
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds or timedelta
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            prefixed_key = self._get_key_with_prefix(key)
            serialized_value = self._serialize_value(value)

            if expire:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                await self.redis_client.setex(prefixed_key, expire, serialized_value)
            else:
                await self.redis_client.set(prefixed_key, serialized_value)

            return True

        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False
        try:
            prefixed_key = self._get_key_with_prefix(key)
            result = await self.redis_client.delete(prefixed_key)
            return bool(result)

        except Exception as e:
            logger.warning(f"Cache delete failed for key {key}: {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False
        try:
            prefixed_key = self._get_key_with_prefix(key)
            result = await self.redis_client.exists(prefixed_key)
            return bool(result)

        except Exception as e:
            logger.warning(f"Cache exists check failed for key {key}: {str(e)}")
            return False

    async def increment(
        self,
        key: str,
        amount: int = 1,
        expire: Optional[Union[int, timedelta]] = None,
    ) -> Optional[int]:
        """
        Atomically increment a numeric cache key.

        Args:
            key: Cache key
            amount: Increment amount
            expire: Optional expiration set on first increment

        Returns:
            New counter value, or None if Redis is unavailable
        """
        if not self.enabled or not self.redis_client:
            return None

        try:
            prefixed_key = self._get_key_with_prefix(key)
            current_value = await self.redis_client.incrby(prefixed_key, amount)

            if current_value == amount and expire:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                await self.redis_client.expire(prefixed_key, expire)

            return int(current_value)
        except Exception as e:
            logger.warning(f"Cache increment failed for key {key}: {str(e)}")
            return None

    async def acquire_lock(
        self,
        key: str,
        value: str,
        expire: Optional[Union[int, timedelta]] = None,
    ) -> Optional[bool]:
        """
        Acquire a distributed lock if it is not already held.

        Returns:
            True if the lock was acquired, False if it is already held,
            or None if Redis is unavailable.
        """
        if not self.enabled or not self.redis_client:
            return None

        try:
            prefixed_key = self._get_key_with_prefix(key)
            kwargs = {"nx": True}

            if expire:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                kwargs["ex"] = expire

            result = await self.redis_client.set(prefixed_key, value, **kwargs)
            return bool(result)
        except Exception as e:
            logger.warning(f"Cache lock acquire failed for key {key}: {str(e)}")
            return None

    async def release_lock(self, key: str, value: str) -> Optional[bool]:
        """
        Release a distributed lock only if it is still owned by value.

        Returns:
            True if the lock was released, False if it was not owned,
            or None if Redis is unavailable.
        """
        if not self.enabled or not self.redis_client:
            return None

        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        end
        return 0
        """

        try:
            prefixed_key = self._get_key_with_prefix(key)
            result = await self.redis_client.eval(
                release_script, 1, prefixed_key, value
            )
            return bool(result)
        except Exception as e:
            logger.warning(f"Cache lock release failed for key {key}: {str(e)}")
            return None

    async def ttl(self, key: str) -> int:
        """
        Get the remaining TTL for a cache key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds, or -2 if unavailable/not found
        """
        if not self.enabled or not self.redis_client:
            return -2

        try:
            prefixed_key = self._get_key_with_prefix(key)
            return int(await self.redis_client.ttl(prefixed_key))
        except Exception as e:
            logger.warning(f"Cache TTL lookup failed for key {key}: {str(e)}")
            return -2

    async def expire(self, key: str, time: Union[int, timedelta]) -> bool:
        """
        Set expiration time for key

        Args:
            key: Cache key
            time: Expiration time in seconds or timedelta

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            prefixed_key = self._get_key_with_prefix(key)

            if isinstance(time, timedelta):
                time = int(time.total_seconds())

            result = await self.redis_client.expire(prefixed_key, time)
            return bool(result)

        except Exception as e:
            logger.warning(f"Cache expire failed for key {key}: {str(e)}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching pattern

        Args:
            pattern: Key pattern (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis_client:
            return 0

        try:
            prefixed_pattern = self._get_key_with_prefix(pattern)
            keys = await self.redis_client.keys(prefixed_pattern)

            if keys:
                deleted = await self.redis_client.delete(*keys)
                return deleted

            return 0

        except Exception as e:
            logger.warning(f"Cache clear pattern failed for {pattern}: {str(e)}")
            return 0

    async def get_or_set(
        self,
        key: str,
        func,
        expire: Optional[Union[int, timedelta]] = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Get value from cache or set it by calling the function
        Args:
            key: Cache key
            func: Function to call if cache miss (can be async)
            expire: Expiration time in seconds or timedelta
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function
        Returns:
            Cached or computed value
        """
        # Try to get from cache first
        value = await self.get(key)

        if value is not None:
            return value

        # Cache miss - compute value
        try:
            if callable(func):
                if hasattr(func, "__call__") and hasattr(func, "__await__"):
                    # Async function
                    value = await func(*args, **kwargs)
                else:
                    # Sync function
                    value = func(*args, **kwargs)
            else:
                value = func

            # Cache the computed value
            await self.set(key, value, expire)
            return value

        except Exception as e:
            logger.error(f"Function call failed in get_or_set for key {key}: {str(e)}")
            return None


# Global cache manager instance
cache = CacheManager()


async def init_cache():
    """Initialize cache connection"""
    await cache.connect()


async def close_cache():
    """Close cache connection"""
    await cache.disconnect()


# Convenience functions
async def cached(key: str, expire: Union[int, timedelta] = timedelta(minutes=15)):
    """
    Decorator for caching function results
    Args:
        key: Cache key template (can use {arg_name} for formatting)
        expire: Cache expiration time
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Format cache key with function arguments
            try:
                formatted_key = key.format(*args, **kwargs)
            except (KeyError, IndexError):
                # If formatting fails, use base key with function name
                formatted_key = f"{func.__name__}:{key}"
            return await cache.get_or_set(formatted_key, func, expire, *args, **kwargs)

        return wrapper

    return decorator


# Cache key generators
class CacheKeys:
    """Standard cache key generators"""

    @staticmethod
    def user(user_id: str) -> str:
        return f"user:{user_id}"

    @staticmethod
    def user_subscription(user_id: str) -> str:
        return f"user:{user_id}:subscription"

    @staticmethod
    def wedding(wedding_id: str) -> str:
        return f"wedding:{wedding_id}"

    @staticmethod
    def wedding_guests(wedding_id: str) -> str:
        return f"wedding:{wedding_id}:guests"

    @staticmethod
    def form(form_id: str) -> str:
        return f"form:{form_id}"

    @staticmethod
    def subscription_plan(plan_id: str) -> str:
        return f"plan:{plan_id}"

    @staticmethod
    def subscription_plans_active() -> str:
        return "plans:active"

    @staticmethod
    def rate_limit(ip_address: str, endpoint: str) -> str:
        return f"rate_limit:{ip_address}:{endpoint}"

    @staticmethod
    def session(session_id: str) -> str:
        return f"session:{session_id}"

    @staticmethod
    def couple_portal_dashboard(wedding_id: str, couple_email: str) -> str:
        return f"couple_portal_dashboard:{wedding_id}:{couple_email}"

    @staticmethod
    def planner_weddings(scope: str, include_cancelled: bool) -> str:
        return f"planner_weddings:{scope}:include_cancelled:{int(include_cancelled)}"

    @staticmethod
    def wedding_privacy_info(slug: str) -> str:
        return f"wedding_privacy_info:{slug}"
