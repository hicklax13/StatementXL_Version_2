"""
Performance optimization utilities.

Provides caching, query profiling, and performance monitoring.
"""
import time
import functools
from typing import Any, Callable, Optional
from datetime import timedelta

import structlog

logger = structlog.get_logger(__name__)


class SimpleCache:
    """
    Simple in-memory cache with TTL support.
    
    For production, use Redis with the same interface.
    """
    
    def __init__(self):
        self._cache: dict[str, tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Set value in cache with TTL."""
        expiry = time.time() + ttl_seconds
        self._cache[key] = (value, expiry)
    
    def delete(self, key: str) -> None:
        """Delete value from cache."""
        self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries, return count removed."""
        now = time.time()
        expired = [k for k, (_, exp) in self._cache.items() if now >= exp]
        for k in expired:
            del self._cache[k]
        return len(expired)


# Global cache instance
cache = SimpleCache()


def cached(ttl_seconds: int = 300, key_prefix: str = ""):
    """
    Decorator to cache function results.
    
    Args:
        ttl_seconds: Time to live in seconds
        key_prefix: Prefix for cache key
        
    Usage:
        @cached(ttl_seconds=60, key_prefix="templates")
        def get_templates():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and args
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            # Check cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug("cache_hit", key=cache_key)
                return cached_value
            
            # Execute and cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds)
            logger.debug("cache_miss", key=cache_key)
            return result
        
        return wrapper
    return decorator


class QueryProfiler:
    """
    Context manager for profiling database queries.
    
    Usage:
        with QueryProfiler("get_documents"):
            results = db.query(Document).all()
    """
    
    # Threshold for slow query warning (ms)
    SLOW_QUERY_THRESHOLD_MS = 100
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.perf_counter() - self.start_time) * 1000
            
            if duration_ms > self.SLOW_QUERY_THRESHOLD_MS:
                logger.warning(
                    "slow_query",
                    operation=self.operation_name,
                    duration_ms=round(duration_ms, 2),
                )
            else:
                logger.debug(
                    "query_profile",
                    operation=self.operation_name,
                    duration_ms=round(duration_ms, 2),
                )
        
        return False  # Don't suppress exceptions


def profile_query(operation_name: str):
    """
    Decorator for query profiling.
    
    Usage:
        @profile_query("get_user_documents")
        def get_documents(user_id: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with QueryProfiler(operation_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Performance metrics collector
class PerformanceMetrics:
    """Collects and reports performance metrics."""
    
    def __init__(self):
        self.request_times: list[float] = []
        self.error_count: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0
    
    def record_request(self, duration_ms: float) -> None:
        """Record request duration."""
        self.request_times.append(duration_ms)
        # Keep last 1000 requests
        if len(self.request_times) > 1000:
            self.request_times = self.request_times[-1000:]
    
    def get_stats(self) -> dict:
        """Get current performance statistics."""
        if not self.request_times:
            return {
                "avg_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "count": 0,
                "error_count": self.error_count,
                "cache_hit_rate": 0,
            }
        
        sorted_times = sorted(self.request_times)
        count = len(sorted_times)
        
        return {
            "avg_ms": sum(sorted_times) / count,
            "p95_ms": sorted_times[int(count * 0.95)] if count > 10 else sorted_times[-1],
            "p99_ms": sorted_times[int(count * 0.99)] if count > 10 else sorted_times[-1],
            "count": count,
            "error_count": self.error_count,
            "cache_hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) 
                if (self.cache_hits + self.cache_misses) > 0 else 0,
        }


# Global metrics instance
metrics = PerformanceMetrics()
