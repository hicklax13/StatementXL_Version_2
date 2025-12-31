"""
API Key authentication for public API access.

Provides middleware and dependencies for authenticating requests using API keys.
"""
import time
from typing import Optional, Tuple

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.api_key import APIKey, APIKeyUsageLog

logger = structlog.get_logger(__name__)

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key_from_header(
    api_key: Optional[str] = Depends(api_key_header),
) -> Optional[str]:
    """Extract API key from header."""
    return api_key


def get_api_key_from_request(request: Request) -> Optional[str]:
    """Extract API key from request (header or query param)."""
    # Try header first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key

    # Fall back to query parameter (for webhooks testing, etc.)
    api_key = request.query_params.get("api_key")
    return api_key


async def verify_api_key(
    request: Request,
    db: Session = Depends(get_db),
    api_key: Optional[str] = Depends(get_api_key_from_header),
) -> Tuple[APIKey, str]:
    """
    Verify an API key and return the key object.

    Returns:
        Tuple of (APIKey, full_key_value)

    Raises:
        HTTPException: If key is invalid, expired, or missing
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Pass it via X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Extract prefix for lookup
    if len(api_key) < 10:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    key_prefix = api_key[:10]

    # Find keys with matching prefix
    potential_keys = db.query(APIKey).filter(
        APIKey.key_prefix == key_prefix,
        APIKey.is_active == True,
    ).all()

    if not potential_keys:
        logger.warning("api_key_not_found", prefix=key_prefix)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Verify the full key
    matched_key = None
    for key in potential_keys:
        if APIKey.verify_key(api_key, key.key_hash):
            matched_key = key
            break

    if not matched_key:
        logger.warning("api_key_verification_failed", prefix=key_prefix)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Check if key is valid (not expired, not revoked)
    if not matched_key.is_valid():
        logger.warning(
            "api_key_invalid",
            key_id=str(matched_key.id),
            expired=matched_key.expires_at is not None,
            revoked=matched_key.revoked_at is not None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is expired or revoked",
        )

    # Check IP restrictions
    if matched_key.allowed_ips:
        client_ip = request.client.host if request.client else None
        if client_ip and client_ip not in matched_key.allowed_ips:
            logger.warning(
                "api_key_ip_denied",
                key_id=str(matched_key.id),
                client_ip=client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP address not allowed for this API key",
            )

    # Record usage
    matched_key.record_usage()
    db.commit()

    return matched_key, api_key


async def require_scope(required_scope: str):
    """
    Dependency factory to require a specific API key scope.

    Usage:
        @router.get("/data", dependencies=[Depends(require_scope("read"))])
        async def get_data():
            ...
    """
    async def check_scope(
        key_info: Tuple[APIKey, str] = Depends(verify_api_key),
    ) -> APIKey:
        api_key, _ = key_info
        if not api_key.has_scope(required_scope):
            logger.warning(
                "api_key_insufficient_scope",
                key_id=str(api_key.id),
                required=required_scope,
                available=api_key.scopes,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key does not have required scope: {required_scope}",
            )
        return api_key

    return check_scope


class APIKeyRateLimiter:
    """Rate limiter for API key requests."""

    def __init__(self):
        self._requests: dict = {}  # key_id -> list of timestamps

    def is_rate_limited(self, api_key: APIKey) -> bool:
        """Check if an API key is rate limited."""
        key_id = str(api_key.id)
        now = time.time()

        # Get request history
        if key_id not in self._requests:
            self._requests[key_id] = []

        # Clean old requests (older than 1 day)
        day_ago = now - 86400
        self._requests[key_id] = [
            ts for ts in self._requests[key_id]
            if ts > day_ago
        ]

        requests = self._requests[key_id]

        # Check per-minute limit
        minute_ago = now - 60
        recent_requests = sum(1 for ts in requests if ts > minute_ago)
        if recent_requests >= api_key.rate_limit_per_minute:
            return True

        # Check per-day limit
        if len(requests) >= api_key.rate_limit_per_day:
            return True

        # Record this request
        self._requests[key_id].append(now)
        return False


# Global rate limiter instance
_rate_limiter = APIKeyRateLimiter()


async def check_rate_limit(
    key_info: Tuple[APIKey, str] = Depends(verify_api_key),
) -> APIKey:
    """Check if the API key request is rate limited."""
    api_key, _ = key_info

    if _rate_limiter.is_rate_limited(api_key):
        logger.warning(
            "api_key_rate_limited",
            key_id=str(api_key.id),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit-Minute": str(api_key.rate_limit_per_minute),
                "X-RateLimit-Limit-Day": str(api_key.rate_limit_per_day),
            },
        )

    return api_key


def log_api_usage(
    request: Request,
    db: Session,
    api_key: APIKey,
    status_code: int,
    response_time_ms: int,
) -> None:
    """Log API key usage for analytics."""
    log_entry = APIKeyUsageLog(
        api_key_id=api_key.id,
        endpoint=str(request.url.path),
        method=request.method,
        status_code=status_code,
        response_time_ms=response_time_ms,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(log_entry)
    db.commit()
