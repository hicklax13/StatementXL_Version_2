"""
Analytics API routes.

Provides endpoints for:
- Usage metrics and statistics
- Processing performance data
- Quota and limit information
- Organization usage reports
"""
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.analytics import MetricType, OrganizationQuota
from backend.auth.dependencies import get_current_active_user, require_admin
from backend.services.analytics_service import AnalyticsService
from backend.exceptions import NotFoundError, ForbiddenError

logger = structlog.get_logger(__name__)

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================

class MetricDataPoint(BaseModel):
    """Single metric data point."""
    date: str
    count: int
    value: Optional[float] = None


class MetricsSummaryResponse(BaseModel):
    """Summary of all metrics."""
    period: dict
    metrics: dict


class DailyMetricsResponse(BaseModel):
    """Daily breakdown of a metric."""
    metric_type: str
    period_days: int
    data: List[MetricDataPoint]


class ProcessingStatsResponse(BaseModel):
    """Processing statistics summary."""
    period_days: int
    total_documents: int
    successful: int
    failed: int
    success_rate: float
    avg_processing_time_ms: Optional[float]
    avg_pages_per_document: Optional[float]
    avg_classification_confidence: Optional[float]
    total_rows_extracted: int
    by_statement_type: dict


class DAUStatsResponse(BaseModel):
    """Daily active users statistics."""
    period_days: int
    monthly_active_users: int
    average_daily_active: float
    daily_breakdown: List[dict]


class QuotaResponse(BaseModel):
    """Organization quota information."""
    plan_name: str
    documents: dict
    api_requests: dict
    storage: dict
    limits: dict
    features: dict


class UsageReportResponse(BaseModel):
    """Comprehensive usage report."""
    organization_id: str
    plan: str
    generated_at: str
    quotas: dict
    limits: dict
    features: dict
    processing: dict
    users: dict


class QuotaCheckResponse(BaseModel):
    """Quota check result."""
    allowed: bool
    message: str
    usage: dict


class UpdateQuotaRequest(BaseModel):
    """Request to update organization quota."""
    plan_name: Optional[str] = None
    max_documents_per_month: Optional[int] = Field(None, ge=1)
    max_pages_per_document: Optional[int] = Field(None, ge=1)
    max_file_size_mb: Optional[int] = Field(None, ge=1)
    max_storage_gb: Optional[float] = Field(None, ge=0.1)
    max_api_requests_per_day: Optional[int] = Field(None, ge=1)
    max_users: Optional[int] = Field(None, ge=1)
    max_api_keys: Optional[int] = Field(None, ge=1)
    max_integrations: Optional[int] = Field(None, ge=0)
    allow_batch_processing: Optional[bool] = None
    allow_api_access: Optional[bool] = None
    allow_webhooks: Optional[bool] = None
    allow_integrations: Optional[bool] = None


# =============================================================================
# Metrics Endpoints
# =============================================================================

@router.get(
    "/metrics",
    response_model=MetricsSummaryResponse,
    summary="Get metrics summary",
    description="Get summarized usage metrics for your organization.",
)
async def get_metrics_summary(
    start_date: Optional[date] = Query(None, description="Start date for metrics"),
    end_date: Optional[date] = Query(None, description="End date for metrics"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MetricsSummaryResponse:
    """Get summarized metrics for the user's organization."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    result = service.get_metrics_summary(org_id, start_date, end_date)

    return MetricsSummaryResponse(**result)


@router.get(
    "/metrics/{metric_type}",
    response_model=DailyMetricsResponse,
    summary="Get daily metrics",
    description="Get daily breakdown of a specific metric.",
)
async def get_daily_metrics(
    metric_type: str,
    days: int = Query(30, ge=1, le=90, description="Number of days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DailyMetricsResponse:
    """Get daily breakdown of a metric."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    try:
        mt = MetricType(metric_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric type: {metric_type}",
        )

    service = AnalyticsService(db)
    data = service.get_daily_metrics(org_id, mt, days)

    return DailyMetricsResponse(
        metric_type=metric_type,
        period_days=days,
        data=[MetricDataPoint(**d) for d in data],
    )


@router.get(
    "/metrics/types",
    summary="List metric types",
    description="Get list of all available metric types.",
)
async def list_metric_types() -> dict:
    """List all available metric types."""
    return {
        "metric_types": [
            {"value": m.value, "name": m.name}
            for m in MetricType
        ]
    }


# =============================================================================
# Processing Stats Endpoints
# =============================================================================

@router.get(
    "/processing",
    response_model=ProcessingStatsResponse,
    summary="Get processing stats",
    description="Get document processing statistics.",
)
async def get_processing_stats(
    days: int = Query(30, ge=1, le=90, description="Number of days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProcessingStatsResponse:
    """Get processing statistics summary."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    result = service.get_processing_stats_summary(org_id, days)

    return ProcessingStatsResponse(**result)


# =============================================================================
# User Activity Endpoints
# =============================================================================

@router.get(
    "/users/activity",
    response_model=DAUStatsResponse,
    summary="Get user activity stats",
    description="Get daily active users statistics.",
)
async def get_user_activity_stats(
    days: int = Query(30, ge=1, le=90, description="Number of days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DAUStatsResponse:
    """Get daily active users statistics."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    result = service.get_dau_stats(org_id, days)

    return DAUStatsResponse(**result)


# =============================================================================
# Quota Endpoints
# =============================================================================

@router.get(
    "/quota",
    response_model=QuotaResponse,
    summary="Get organization quota",
    description="Get quota limits and current usage for your organization.",
)
async def get_quota(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> QuotaResponse:
    """Get organization quota and usage."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    quota = service.get_or_create_quota(org_id)

    # Get current usage
    _, _, doc_usage = service.check_quota(org_id, "documents")
    _, _, api_usage = service.check_quota(org_id, "api")
    _, _, storage_usage = service.check_quota(org_id, "storage")

    return QuotaResponse(
        plan_name=quota.plan_name,
        documents=doc_usage,
        api_requests=api_usage,
        storage=storage_usage,
        limits={
            "max_users": quota.max_users,
            "max_api_keys": quota.max_api_keys,
            "max_integrations": quota.max_integrations,
            "max_file_size_mb": quota.max_file_size_mb,
            "max_pages_per_document": quota.max_pages_per_document,
        },
        features={
            "batch_processing": quota.allow_batch_processing,
            "api_access": quota.allow_api_access,
            "webhooks": quota.allow_webhooks,
            "integrations": quota.allow_integrations,
        },
    )


@router.get(
    "/quota/check/{check_type}",
    response_model=QuotaCheckResponse,
    summary="Check quota",
    description="Check if a specific quota limit is reached.",
)
async def check_quota(
    check_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> QuotaCheckResponse:
    """Check if quota limit is reached."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    if check_type not in ["documents", "api", "storage"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid check type: {check_type}. Must be one of: documents, api, storage",
        )

    service = AnalyticsService(db)
    allowed, message, usage = service.check_quota(org_id, check_type)

    return QuotaCheckResponse(
        allowed=allowed,
        message=message,
        usage=usage,
    )


@router.put(
    "/quota/{organization_id}",
    response_model=QuotaResponse,
    summary="Update organization quota",
    description="Update quota limits for an organization (admin only).",
)
async def update_quota(
    organization_id: str,
    request: UpdateQuotaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> QuotaResponse:
    """Update organization quota (admin only)."""
    try:
        org_uuid = uuid.UUID(organization_id)
    except ValueError:
        raise NotFoundError("Organization", organization_id)

    service = AnalyticsService(db)
    quota = service.get_or_create_quota(org_uuid)

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(quota, field):
            setattr(quota, field, value)

    db.commit()
    db.refresh(quota)

    logger.info(
        "quota_updated",
        organization_id=organization_id,
        updated_by=str(current_user.id),
        fields=list(update_data.keys()),
    )

    # Get current usage
    _, _, doc_usage = service.check_quota(org_uuid, "documents")
    _, _, api_usage = service.check_quota(org_uuid, "api")
    _, _, storage_usage = service.check_quota(org_uuid, "storage")

    return QuotaResponse(
        plan_name=quota.plan_name,
        documents=doc_usage,
        api_requests=api_usage,
        storage=storage_usage,
        limits={
            "max_users": quota.max_users,
            "max_api_keys": quota.max_api_keys,
            "max_integrations": quota.max_integrations,
            "max_file_size_mb": quota.max_file_size_mb,
            "max_pages_per_document": quota.max_pages_per_document,
        },
        features={
            "batch_processing": quota.allow_batch_processing,
            "api_access": quota.allow_api_access,
            "webhooks": quota.allow_webhooks,
            "integrations": quota.allow_integrations,
        },
    )


# =============================================================================
# Reports Endpoints
# =============================================================================

@router.get(
    "/report",
    response_model=UsageReportResponse,
    summary="Get usage report",
    description="Get comprehensive usage report for your organization.",
)
async def get_usage_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UsageReportResponse:
    """Get comprehensive usage report."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    report = service.get_usage_report(org_id)

    return UsageReportResponse(**report)


@router.get(
    "/report/{organization_id}",
    response_model=UsageReportResponse,
    summary="Get organization usage report",
    description="Get usage report for a specific organization (admin only).",
)
async def get_organization_report(
    organization_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UsageReportResponse:
    """Get usage report for specific organization (admin only)."""
    try:
        org_uuid = uuid.UUID(organization_id)
    except ValueError:
        raise NotFoundError("Organization", organization_id)

    service = AnalyticsService(db)
    report = service.get_usage_report(org_uuid)

    return UsageReportResponse(**report)


# =============================================================================
# Admin Dashboard Endpoints
# =============================================================================

@router.get(
    "/admin/overview",
    summary="Get admin analytics overview",
    description="Get system-wide analytics overview (admin only).",
)
async def get_admin_overview(
    days: int = Query(30, ge=1, le=90, description="Number of days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """Get system-wide analytics overview (admin only)."""
    from sqlalchemy import func
    from backend.models.analytics import UsageMetric, ProcessingStats, DailyActiveUsers
    from backend.models.organization import Organization
    from backend.models.user import User as UserModel

    cutoff = date.today() - timedelta(days=days)

    # Total organizations
    total_orgs = db.query(func.count(Organization.id)).scalar() or 0

    # Total users
    total_users = db.query(func.count(UserModel.id)).scalar() or 0

    # Active users (in period)
    active_users = db.query(
        func.count(DailyActiveUsers.user_id.distinct())
    ).filter(
        DailyActiveUsers.activity_date >= cutoff,
    ).scalar() or 0

    # Documents processed
    docs_processed = db.query(func.sum(UsageMetric.count)).filter(
        UsageMetric.metric_type == MetricType.DOCUMENTS_PROCESSED,
        UsageMetric.metric_date >= cutoff,
    ).scalar() or 0

    # Processing success rate
    total_processed = db.query(func.count(ProcessingStats.id)).filter(
        ProcessingStats.created_at >= datetime.utcnow() - timedelta(days=days),
    ).scalar() or 0
    successful = db.query(func.count(ProcessingStats.id)).filter(
        ProcessingStats.created_at >= datetime.utcnow() - timedelta(days=days),
        ProcessingStats.success == True,
    ).scalar() or 0
    success_rate = (successful / total_processed * 100) if total_processed > 0 else 0

    # Top organizations by usage
    top_orgs = db.query(
        UsageMetric.organization_id,
        func.sum(UsageMetric.count).label("total"),
    ).filter(
        UsageMetric.metric_type == MetricType.DOCUMENTS_PROCESSED,
        UsageMetric.metric_date >= cutoff,
    ).group_by(UsageMetric.organization_id).order_by(
        func.sum(UsageMetric.count).desc()
    ).limit(10).all()

    return {
        "period_days": days,
        "totals": {
            "organizations": total_orgs,
            "users": total_users,
            "active_users": active_users,
            "documents_processed": docs_processed,
        },
        "processing": {
            "total": total_processed,
            "successful": successful,
            "success_rate": round(success_rate, 1),
        },
        "top_organizations": [
            {"organization_id": str(org_id), "documents": count}
            for org_id, count in top_orgs
        ],
    }
