"""
Monitoring and metrics endpoints.

Provides health checks, readiness probes, and basic metrics.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
from backend.utils.performance import metrics, cache

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str = "2.0.0"


class ReadinessResponse(BaseModel):
    """Readiness check response with component status."""
    status: str
    database: str
    cache: str
    timestamp: str


class MetricsResponse(BaseModel):
    """Basic metrics response."""
    requests_total: int
    requests_avg_ms: float
    requests_p95_ms: float
    requests_p99_ms: float
    errors_total: int
    cache_hit_rate: float
    uptime_seconds: float


# Track server start time
_start_time = datetime.utcnow()


@router.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    
    Returns 200 if the server is running.
    Used by Docker HEALTHCHECK and load balancers.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/ready", response_model=ReadinessResponse, tags=["Monitoring"])
async def readiness_check(db: Session = Depends(get_db)) -> ReadinessResponse:
    """
    Readiness check for Kubernetes/container orchestration.
    
    Checks database and cache connectivity.
    """
    # Check database
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
    
    # Check cache (simple test)
    cache_status = "healthy"
    try:
        cache.set("health_check", "ok", ttl_seconds=10)
        if cache.get("health_check") != "ok":
            cache_status = "unhealthy"
    except Exception:
        cache_status = "unhealthy"
    
    overall = "healthy" if db_status == "healthy" and cache_status == "healthy" else "degraded"
    
    return ReadinessResponse(
        status=overall,
        database=db_status,
        cache=cache_status,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/metrics", response_model=MetricsResponse, tags=["Monitoring"])
async def get_metrics() -> MetricsResponse:
    """
    Basic application metrics.

    For production, consider Prometheus integration.
    """
    stats = metrics.get_stats()
    uptime = (datetime.utcnow() - _start_time).total_seconds()

    return MetricsResponse(
        requests_total=stats["count"],
        requests_avg_ms=round(stats["avg_ms"], 2),
        requests_p95_ms=round(stats["p95_ms"], 2),
        requests_p99_ms=round(stats["p99_ms"], 2),
        errors_total=stats["error_count"],
        cache_hit_rate=round(stats["cache_hit_rate"], 4),
        uptime_seconds=round(uptime, 2),
    )


class DetailedMetricsResponse(BaseModel):
    """Detailed metrics including system and application stats."""
    # System metrics
    uptime_seconds: float
    memory_used_mb: float
    memory_available_mb: float
    cpu_percent: Optional[float] = None

    # Request metrics
    requests_total: int
    requests_avg_ms: float
    requests_p95_ms: float
    requests_p99_ms: float
    errors_total: int
    cache_hit_rate: float

    # Application metrics
    documents_total: int
    documents_processed: int
    documents_failed: int
    users_total: int
    users_active: int
    exports_total: int

    timestamp: str


@router.get("/metrics/detailed", response_model=DetailedMetricsResponse, tags=["Monitoring"])
async def get_detailed_metrics(db: Session = Depends(get_db)) -> DetailedMetricsResponse:
    """
    Detailed application and system metrics.

    Includes document processing stats, user counts, and system resources.
    """
    import os

    # Get request stats
    stats = metrics.get_stats()
    uptime = (datetime.utcnow() - _start_time).total_seconds()

    # System metrics (basic, cross-platform)
    try:
        import psutil
        memory = psutil.virtual_memory()
        memory_used_mb = memory.used / (1024 * 1024)
        memory_available_mb = memory.available / (1024 * 1024)
        cpu_percent = psutil.cpu_percent(interval=0.1)
    except ImportError:
        # Fallback if psutil not available
        memory_used_mb = 0.0
        memory_available_mb = 0.0
        cpu_percent = None

    # Application metrics from database
    from backend.models.document import Document
    from backend.models.user import User

    try:
        documents_total = db.query(Document).count()
        documents_processed = db.query(Document).filter(Document.status == "completed").count()
        documents_failed = db.query(Document).filter(Document.status == "failed").count()
        users_total = db.query(User).count()
        users_active = db.query(User).filter(User.is_active == True).count()

        # Count exports (if there's an Export model, otherwise estimate from audit)
        exports_total = documents_processed  # Approximation
    except Exception:
        documents_total = 0
        documents_processed = 0
        documents_failed = 0
        users_total = 0
        users_active = 0
        exports_total = 0

    return DetailedMetricsResponse(
        uptime_seconds=round(uptime, 2),
        memory_used_mb=round(memory_used_mb, 2),
        memory_available_mb=round(memory_available_mb, 2),
        cpu_percent=round(cpu_percent, 2) if cpu_percent is not None else None,
        requests_total=stats["count"],
        requests_avg_ms=round(stats["avg_ms"], 2),
        requests_p95_ms=round(stats["p95_ms"], 2),
        requests_p99_ms=round(stats["p99_ms"], 2),
        errors_total=stats["error_count"],
        cache_hit_rate=round(stats["cache_hit_rate"], 4),
        documents_total=documents_total,
        documents_processed=documents_processed,
        documents_failed=documents_failed,
        users_total=users_total,
        users_active=users_active,
        exports_total=exports_total,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/version", tags=["Monitoring"])
async def get_version() -> dict:
    """
    Get application version and build info.
    """
    import os

    return {
        "version": "2.0.0",
        "build": os.getenv("BUILD_NUMBER", "dev"),
        "commit": os.getenv("GIT_COMMIT", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "python_version": os.sys.version.split()[0],
    }
