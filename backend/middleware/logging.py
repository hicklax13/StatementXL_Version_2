"""
Logging middleware and utilities for production-grade observability.

Provides correlation ID tracking, request/response logging, and performance timing.
"""
import time
import uuid
from contextvars import ContextVar
from typing import Callable, Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

# Context variable for correlation ID (thread-safe)
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

# Logger instance
logger = structlog.get_logger(__name__)

# Sensitive fields to redact from logs
SENSITIVE_FIELDS = {
    "password", "password_hash", "hashed_password",
    "token", "access_token", "refresh_token",
    "authorization", "api_key", "secret",
    "credit_card", "ssn", "social_security",
}


def get_correlation_id() -> str:
    """Get the current request's correlation ID."""
    return correlation_id.get()


def redact_sensitive_data(data: dict, depth: int = 0) -> dict:
    """
    Recursively redact sensitive fields from a dictionary.
    
    Args:
        data: Dictionary to redact
        depth: Current recursion depth (to prevent infinite loops)
        
    Returns:
        Dictionary with sensitive values replaced with "[REDACTED]"
    """
    if depth > 5 or not isinstance(data, dict):
        return data
    
    redacted = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value, depth + 1)
        elif isinstance(value, list):
            redacted[key] = [
                redact_sensitive_data(item, depth + 1) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value
    
    return redacted


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that adds correlation ID to each request."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get correlation ID from header or generate new one
        request_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        
        # Set correlation ID in context
        correlation_id.set(request_id)
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response header
        response.headers["X-Correlation-ID"] = request_id
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all requests with timing information."""
    
    # Paths to skip detailed logging
    SKIP_PATHS = {"/health", "/metrics", "/docs", "/redoc", "/openapi.json"}
    
    # Maximum body size to log (in bytes)
    MAX_BODY_LOG_SIZE = 1000
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for certain paths
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        
        # Start timing
        start_time = time.perf_counter()
        
        # Get request info
        request_info = {
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params) if request.query_params else None,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("User-Agent", "")[:100],  # Truncate
            "correlation_id": get_correlation_id(),
        }
        
        # Log request start
        logger.info("request_started", **request_info)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log response
            logger.info(
                "request_completed",
                **request_info,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            
            # Log warning for slow requests
            if duration_ms > 1000:  # > 1 second
                logger.warning(
                    "slow_request",
                    **request_info,
                    duration_ms=round(duration_ms, 2),
                )
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log error
            logger.error(
                "request_failed",
                **request_info,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
            )
            raise


def log_performance(operation_name: str):
    """
    Decorator to log performance timing for functions.
    
    Usage:
        @log_performance("pdf_extraction")
        async def extract_pdf(file):
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()
            correlation = get_correlation_id()
            
            logger.debug(
                "operation_started",
                operation=operation_name,
                correlation_id=correlation,
            )
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                logger.info(
                    "operation_completed",
                    operation=operation_name,
                    duration_ms=round(duration_ms, 2),
                    correlation_id=correlation,
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                logger.error(
                    "operation_failed",
                    operation=operation_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round(duration_ms, 2),
                    correlation_id=correlation,
                )
                raise
        
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()
            correlation = get_correlation_id()
            
            logger.debug(
                "operation_started",
                operation=operation_name,
                correlation_id=correlation,
            )
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                logger.info(
                    "operation_completed",
                    operation=operation_name,
                    duration_ms=round(duration_ms, 2),
                    correlation_id=correlation,
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                logger.error(
                    "operation_failed",
                    operation=operation_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round(duration_ms, 2),
                    correlation_id=correlation,
                )
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def add_correlation_id_processor(
    logger: Any, method_name: str, event_dict: dict
) -> dict:
    """Structlog processor that adds correlation ID to all log entries."""
    event_dict["correlation_id"] = get_correlation_id()
    return event_dict


def redact_sensitive_processor(
    logger: Any, method_name: str, event_dict: dict
) -> dict:
    """Structlog processor that redacts sensitive data from log entries."""
    return redact_sensitive_data(event_dict)
