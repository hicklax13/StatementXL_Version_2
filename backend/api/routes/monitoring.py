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
