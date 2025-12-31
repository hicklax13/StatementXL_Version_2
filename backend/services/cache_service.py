"""
Caching Service.

Provides multi-tier caching with Redis support and in-memory fallback.
"""
import json
import hashlib
import pickle
import time
from datetime import datetime, timedelta
from typing import Optional, Any, Callable, TypeVar, Dict, List
from functools import wraps
from dataclasses import dataclass
from enum import Enum
import threading
from collections import OrderedDict

import structlog
from backend.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

T = TypeVar('T')


class CacheBackend(str, Enum):
    """Cache backend types."""
    MEMORY = "memory"
    REDIS = "redis"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    created_at: float
    expires_at: float
    hits: int = 0
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def ttl_remaining(self) -> float:
        return max(0, self.expires_at - time.time())


class LRUCache:
    """Thread-safe LRU cache implementation."""

    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._current_memory = 0
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry and move to end (most recently used)."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]
            if entry.is_expired:
                self._remove(key)
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._hits += 1
            return entry

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Set entry with TTL."""
        with self._lock:
            # Calculate size
            try:
                size = len(pickle.dumps(value))
            except Exception:
                size = 1024  # Default estimate

            # Remove existing entry if present
            if key in self._cache:
                self._remove(key)

            # Evict if needed
            while (len(self._cache) >= self.max_size or
                   self._current_memory + size > self.max_memory_bytes):
                if not self._cache:
                    break
                # Remove least recently used (first item)
                oldest_key = next(iter(self._cache))
                self._remove(oldest_key)

            # Add new entry
            now = time.time()
            entry = CacheEntry(
                value=value,
                created_at=now,
                expires_at=now + ttl_seconds,
                size_bytes=size,
            )
            self._cache[key] = entry
            self._current_memory += size

    def delete(self, key: str) -> bool:
        """Delete an entry."""
        with self._lock:
            if key in self._cache:
                self._remove(key)
                return True
            return False

    def _remove(self, key: str) -> None:
        """Remove entry and update memory counter."""
        if key in self._cache:
            self._current_memory -= self._cache[key].size_bytes
            del self._cache[key]

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self._current_memory = 0

    def clear_pattern(self, pattern: str) -> int:
        """Clear entries matching pattern."""
        with self._lock:
            import fnmatch
            keys_to_delete = [
                k for k in self._cache.keys()
                if fnmatch.fnmatch(k, pattern)
            ]
            for key in keys_to_delete:
                self._remove(key)
            return len(keys_to_delete)

    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "memory_bytes": self._current_memory,
                "max_memory_bytes": self.max_memory_bytes,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0,
            }


class RedisCache:
    """Redis cache backend."""

    def __init__(self, url: str = None):
        self.url = url or getattr(settings, 'redis_url', None)
        self._client = None

    @property
    def client(self):
        """Lazy initialize Redis client."""
        if self._client is None and self.url:
            try:
                import redis
                self._client = redis.from_url(self.url)
                self._client.ping()
            except Exception as e:
                logger.warning("redis_connection_failed", error=str(e))
                self._client = None
        return self._client

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        if not self.client:
            return None

        try:
            data = self.client.get(key)
            if data:
                return pickle.loads(data)
        except Exception as e:
            logger.error("redis_get_error", key=key, error=str(e))
        return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Set value in Redis."""
        if not self.client:
            return False

        try:
            data = pickle.dumps(value)
            self.client.setex(key, ttl_seconds, data)
            return True
        except Exception as e:
            logger.error("redis_set_error", key=key, error=str(e))
        return False

    def delete(self, key: str) -> bool:
        """Delete value from Redis."""
        if not self.client:
            return False

        try:
            return self.client.delete(key) > 0
        except Exception as e:
            logger.error("redis_delete_error", key=key, error=str(e))
        return False

    def clear_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        if not self.client:
            return 0

        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
        except Exception as e:
            logger.error("redis_clear_pattern_error", pattern=pattern, error=str(e))
        return 0


class CacheService:
    """
    Multi-tier caching service with Redis and in-memory fallback.
    """

    def __init__(self):
        self._memory_cache = LRUCache(
            max_size=getattr(settings, 'cache_max_size', 1000),
            max_memory_mb=getattr(settings, 'cache_max_memory_mb', 100),
        )
        self._redis_cache = RedisCache()

    def get(self, key: str, use_redis: bool = True) -> Optional[Any]:
        """
        Get value from cache.

        Checks memory cache first, then Redis if enabled.
        """
        # Check memory cache first
        entry = self._memory_cache.get(key)
        if entry:
            return entry.value

        # Check Redis if enabled
        if use_redis and self._redis_cache.client:
            value = self._redis_cache.get(key)
            if value is not None:
                # Store in memory cache for faster access
                self._memory_cache.set(key, value, 60)  # 1 minute local cache
                return value

        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 300,
        use_redis: bool = True,
    ) -> None:
        """Set value in cache."""
        # Always set in memory cache
        self._memory_cache.set(key, value, ttl_seconds)

        # Set in Redis if enabled
        if use_redis:
            self._redis_cache.set(key, value, ttl_seconds)

    def delete(self, key: str) -> bool:
        """Delete from all cache tiers."""
        memory_deleted = self._memory_cache.delete(key)
        redis_deleted = self._redis_cache.delete(key)
        return memory_deleted or redis_deleted

    def clear(self) -> None:
        """Clear all caches."""
        self._memory_cache.clear()
        if self._redis_cache.client:
            try:
                self._redis_cache.client.flushdb()
            except Exception:
                pass

    def clear_pattern(self, pattern: str) -> int:
        """Clear entries matching pattern from all tiers."""
        memory_count = self._memory_cache.clear_pattern(pattern)
        redis_count = self._redis_cache.clear_pattern(pattern)
        return memory_count + redis_count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "memory": self._memory_cache.stats,
            "redis_available": self._redis_cache.client is not None,
        }

    def cache_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()


# Global cache instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get global cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def cached(
    ttl_seconds: int = 300,
    key_prefix: str = "",
    use_redis: bool = True,
    key_builder: Optional[Callable] = None,
):
    """
    Decorator for caching function results.

    Args:
        ttl_seconds: Time to live in seconds
        key_prefix: Prefix for cache keys
        use_redis: Whether to use Redis tier
        key_builder: Custom function to build cache key

    Example:
        @cached(ttl_seconds=600, key_prefix="user")
        def get_user(user_id: str) -> User:
            return db.query(User).filter(User.id == user_id).first()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            cache = get_cache_service()

            # Build cache key
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                key = cache.cache_key(*args, **kwargs)

            if key_prefix:
                key = f"{key_prefix}:{key}"
            else:
                key = f"{func.__module__}.{func.__name__}:{key}"

            # Try to get from cache
            cached_value = cache.get(key, use_redis=use_redis)
            if cached_value is not None:
                logger.debug("cache_hit", key=key)
                return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(key, result, ttl_seconds, use_redis=use_redis)
                logger.debug("cache_set", key=key, ttl=ttl_seconds)

            return result

        # Add cache control methods
        wrapper.cache_clear = lambda: get_cache_service().clear_pattern(f"{key_prefix}:*")
        wrapper.cache_key = lambda *a, **kw: (
            f"{key_prefix}:{key_builder(*a, **kw)}" if key_builder
            else f"{func.__module__}.{func.__name__}:{get_cache_service().cache_key(*a, **kw)}"
        )

        return wrapper
    return decorator


def invalidate_cache(*patterns: str) -> int:
    """
    Invalidate cache entries matching patterns.

    Args:
        patterns: Glob patterns to match

    Returns:
        Number of entries invalidated
    """
    cache = get_cache_service()
    total = 0
    for pattern in patterns:
        total += cache.clear_pattern(pattern)
    return total


# Query result caching utilities
class QueryCache:
    """Helper for caching database query results."""

    def __init__(self, cache: CacheService = None):
        self.cache = cache or get_cache_service()

    def get_or_set(
        self,
        key: str,
        query_func: Callable[[], T],
        ttl_seconds: int = 300,
    ) -> T:
        """Get from cache or execute query and cache result."""
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        result = query_func()
        if result is not None:
            self.cache.set(key, result, ttl_seconds)
        return result

    def invalidate(self, *keys: str) -> None:
        """Invalidate specific keys."""
        for key in keys:
            self.cache.delete(key)

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate keys matching pattern."""
        return self.cache.clear_pattern(pattern)
