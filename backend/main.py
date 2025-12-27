"""
FastAPI application entry point.

Configures the application with routes, middleware, and settings.
"""
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.api.routes import upload
from backend.api.routes import classify
from backend.api.routes import template
from backend.api.routes import mapping
from backend.api.routes import library
from backend.api.routes import batch
from backend.api.routes import audit
from backend.api.routes import auth
from backend.api.routes import export
from backend.config import get_settings
from backend.database import init_db
from backend.middleware.logging import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    add_correlation_id_processor,
    redact_sensitive_processor,
)

# Configure structured logging with enhanced processors
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        add_correlation_id_processor,  # Add correlation ID to all logs
        redact_sensitive_processor,     # Redact passwords, tokens, etc.
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title="StatementXL API",
    description="Financial statement PDF extraction and normalization API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS with proper origins
from backend.middleware.security import SecurityHeadersMiddleware, get_cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),  # Whitelist specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add logging middleware (order matters: correlation ID first)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# Add GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure rate limiter
from backend.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Include API routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])
app.include_router(classify.router, prefix="/api/v1", tags=["Classification"])
app.include_router(template.router, prefix="/api/v1", tags=["Template"])
app.include_router(mapping.router, prefix="/api/v1", tags=["Mapping"])
app.include_router(library.router, prefix="/api/v1", tags=["Library"])
app.include_router(batch.router, prefix="/api/v1", tags=["Batch"])
app.include_router(audit.router, prefix="/api/v1", tags=["Audit"])
app.include_router(export.router, prefix="/api/v1", tags=["Export"])

# Monitoring routes (no prefix for easy access)
from backend.api.routes import monitoring
app.include_router(monitoring.router, tags=["Monitoring"])


# Global Exception Handlers
from fastapi import Request
from fastapi.responses import JSONResponse
from backend.exceptions import StatementXLError


@app.exception_handler(StatementXLError)
async def statementxl_exception_handler(request: Request, exc: StatementXLError):
    """Handle all StatementXL custom exceptions."""
    logger.error(
        "statementxl_error",
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        path=str(request.url.path),
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": True,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with consistent format."""
    import traceback
    
    logger.error(
        "unhandled_error",
        error_type=type(exc).__name__,
        message=str(exc),
        path=str(request.url.path),
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": "SXL-999",
            "message": "An unexpected error occurred. Please try again.",
            "details": {"error_type": type(exc).__name__} if settings.debug else {},
        },
    )


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application on startup."""
    logger.info("Starting StatementXL API", debug=settings.debug)
    
    # Ensure upload directory exists
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize database tables
    init_db()
    
    logger.info("StatementXL API started successfully")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on application shutdown."""
    logger.info("Shutting down StatementXL API")


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "version": "2.0.0"}
