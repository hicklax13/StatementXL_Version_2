"""
Rate limiting middleware for API protection.

Prevents DoS attacks and brute force attempts using slowapi.
"""
import os
from typing import Callable

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)


def get_client_identifier(request: Request) -> str:
    """
    Get client identifier for rate limiting.
    
    Uses authenticated user ID if available, otherwise falls back to IP.
    """
    # Check for authenticated user
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"
    
    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    return get_remote_address(request)


# Create rate limiter with in-memory storage (use Redis in production)
# Set storage_uri to Redis URL for production: redis://localhost:6379/0
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    limiter = Limiter(
        key_func=get_client_identifier,
        storage_uri=REDIS_URL,
    )
else:
    # In-memory storage for development
    limiter = Limiter(key_func=get_client_identifier)


# Rate limit configurations
RATE_LIMITS = {
    "global": "1000/hour",         # 1000 requests per hour per client
    "auth": "10/minute",           # 10 auth attempts per minute (brute force protection)
    "upload": "20/hour",           # 20 file uploads per hour
    "api": "100/minute",           # 100 API calls per minute
    "export": "30/hour",           # 30 exports per hour
}


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom handler for rate limit exceeded errors.
    
    Returns a user-friendly JSON response with retry information.
    """
    logger.warning(
        "rate_limit_exceeded",
        client=get_client_identifier(request),
        path=request.url.path,
        limit=str(exc.detail),
    )
    
    # Parse retry-after from exception if available
    retry_after = 60  # Default to 60 seconds
    
    return JSONResponse(
        status_code=429,
        content={
            "error": True,
            "error_code": "SXL-429",
            "message": "Too many requests. Please slow down.",
            "details": {
                "limit": str(exc.detail),
                "retry_after_seconds": retry_after,
            },
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(exc.detail).split("/")[0] if "/" in str(exc.detail) else "1000",
        },
    )


# Decorator functions for common rate limits
def auth_rate_limit():
    """Rate limit decorator for authentication endpoints."""
    return limiter.limit(RATE_LIMITS["auth"])


def upload_rate_limit():
    """Rate limit decorator for upload endpoints."""
    return limiter.limit(RATE_LIMITS["upload"])


def api_rate_limit():
    """Rate limit decorator for general API endpoints."""
    return limiter.limit(RATE_LIMITS["api"])


def export_rate_limit():
    """Rate limit decorator for export endpoints."""
    return limiter.limit(RATE_LIMITS["export"])
