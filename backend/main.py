"""
FastAPI application entry point.

Configures the application with routes, middleware, and settings.
"""
import os
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# Initialize Sentry for error tracking (must be done early)
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=os.getenv("ENVIRONMENT", "development"),
        release=os.getenv("APP_VERSION", "2.0.0"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            LoggingIntegration(level=None, event_level="ERROR"),
        ],
        # Don't send PII by default
        send_default_pii=False,
        # Filter sensitive data
        before_send=lambda event, hint: _filter_sensitive_data(event),
    )


def _filter_sensitive_data(event: dict) -> dict:
    """Filter sensitive data from Sentry events before sending."""
    sensitive_keys = {"password", "token", "secret", "authorization", "api_key", "credit_card"}

    def _redact(obj):
        if isinstance(obj, dict):
            return {
                k: "[REDACTED]" if any(s in k.lower() for s in sensitive_keys) else _redact(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [_redact(item) for item in obj]
        return obj

    if "request" in event and "data" in event["request"]:
        event["request"]["data"] = _redact(event["request"]["data"])
    if "extra" in event:
        event["extra"] = _redact(event["extra"])

    return event


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

# Create FastAPI application with comprehensive OpenAPI documentation
app = FastAPI(
    title="StatementXL API",
    description="""
## Financial Statement PDF Extraction and Normalization API

StatementXL provides comprehensive tools for extracting, classifying, and exporting 
financial data from PDF documents into structured Excel templates.

### Key Features

- **PDF Upload & Extraction**: Upload financial statement PDFs for automatic table detection and data extraction
- **GAAP Classification**: AI-powered classification of financial line items using YAML mappings (300+ items)
- **Auto-Detection**: Automatic identification of statement type (Income Statement, Balance Sheet, Cash Flow)
- **Template Export**: Export to formatted Excel templates with proper formulas and styling

### Statement Types Supported

| Type | Description |
|------|-------------|
| Income Statement | Revenue, expenses, profit & loss |
| Balance Sheet | Assets, liabilities, equity |
| Cash Flow | Operating, investing, financing activities |

### Authentication

Protected endpoints require a valid JWT token in the Authorization header.
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Authentication", "description": "User authentication and token management"},
        {"name": "Upload", "description": "PDF document upload and processing"},
        {"name": "Classification", "description": "GAAP line item classification"},
        {"name": "Export", "description": "Excel template export and download"},
        {"name": "Template", "description": "Template management and configuration"},
        {"name": "Mapping", "description": "Data mapping between extracted items and templates"},
        {"name": "Library", "description": "Mapping library and presets"},
        {"name": "Batch", "description": "Batch processing operations"},
        {"name": "Audit", "description": "Audit logging and history"},
        {"name": "Monitoring", "description": "Health checks and metrics"},
    ],
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

# Payment routes
from backend.api.routes import payments
app.include_router(payments.router, prefix="/api/v1", tags=["Payments"])

# Organization routes
from backend.api.routes import organization
app.include_router(organization.router, prefix="/api/v1/organizations", tags=["Organizations"])

# Jobs routes (background processing)
from backend.api.routes import jobs
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])

# Monitoring routes (no prefix for easy access)
from backend.api.routes import monitoring
app.include_router(monitoring.router, tags=["Monitoring"])

# Mount static files (Frontend)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Serve static files if they exist (Production)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

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

    # Capture exception in Sentry
    sentry_sdk.capture_exception(exc)

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

    # Log Sentry status
    if sentry_dsn:
        logger.info("Sentry error tracking enabled", environment=os.getenv("ENVIRONMENT", "development"))
    else:
        logger.warning("Sentry error tracking not configured (SENTRY_DSN not set)")

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
