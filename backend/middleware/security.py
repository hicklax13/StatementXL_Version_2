"""
Security headers middleware for API hardening.

Adds essential security headers to all responses.
"""
import os
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.
    
    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security (for HTTPS)
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    """
    
    # Whether to enable HSTS (should be True in production with HTTPS)
    ENABLE_HSTS = os.getenv("ENABLE_HSTS", "false").lower() == "true"
    
    # HSTS max-age in seconds (1 year)
    HSTS_MAX_AGE = 31536000
    
    # Content Security Policy
    CSP_POLICY = "; ".join([
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Allow inline for React
        "style-src 'self' 'unsafe-inline'",  # Allow inline styles
        "img-src 'self' data: blob: https:",  # Allow images from various sources
        "font-src 'self' data: https://fonts.gstatic.com",
        "connect-src 'self' http://localhost:* ws://localhost:*",  # Allow API calls
        "frame-ancestors 'none'",  # No embedding in iframes
        "base-uri 'self'",
        "form-action 'self'",
    ])
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # XSS protection (legacy, but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions policy (disable dangerous features)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), "
            "payment=(), usb=()"
        )
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.CSP_POLICY
        
        # HSTS for HTTPS connections
        if self.ENABLE_HSTS:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.HSTS_MAX_AGE}; includeSubDomains; preload"
            )
        
        # Remove server header if present
        if "Server" in response.headers:
            del response.headers["Server"]
        
        return response


# CORS configuration for production
def get_cors_origins() -> list[str]:
    """
    Get allowed CORS origins from environment.
    
    In development, allows all origins.
    In production, should whitelist specific domains.
    """
    origins_str = os.getenv("CORS_ORIGINS", "")
    
    if origins_str:
        return [origin.strip() for origin in origins_str.split(",")]
    
    # Development: allow common local development URLs
    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


# Request size limits
MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB", "50"))
MAX_REQUEST_SIZE_BYTES = MAX_REQUEST_SIZE_MB * 1024 * 1024
