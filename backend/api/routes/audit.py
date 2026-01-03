"""
Audit API routes.

Provides endpoints for viewing, searching, and exporting audit logs.
Includes compliance features for GDPR data export and deletion requests.
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.audit import (
    AuditLog,
    AuditAction,
    AuditResourceType,
    AuditSeverity,
    ComplianceRequest,
)
from backend.auth.dependencies import get_current_active_user, require_admin
from backend.exceptions import NotFoundError, ForbiddenError

logger = structlog.get_logger(__name__)

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================

class AuditEntryResponse(BaseModel):
    """Response model for an audit entry."""
    id: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    severity: str
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    ip_address: Optional[str] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    description: Optional[str] = None
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Response model for paginated audit log."""
    entries: List[AuditEntryResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class AuditStatsResponse(BaseModel):
    """Response model for audit statistics."""
    total_events: int
    events_today: int
    events_this_week: int
    failed_events: int
    by_action: dict
    by_resource_type: dict
    by_severity: dict


class ComplianceRequestCreate(BaseModel):
    """Request to create a compliance request."""
    request_type: str = Field(..., pattern="^(data_export|data_deletion|consent_withdrawal)$")
    reason: Optional[str] = None
    scope: Optional[dict] = None


class ComplianceRequestResponse(BaseModel):
    """Response for a compliance request."""
    id: str
    request_type: str
    status: str
    reason: Optional[str] = None
    download_url: Optional[str] = None
    download_expires_at: Optional[datetime] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ComplianceListResponse(BaseModel):
    """Response for compliance request list."""
    requests: List[ComplianceRequestResponse]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================

def _entry_to_response(entry: AuditLog) -> AuditEntryResponse:
    """Convert audit log model to response."""
    return AuditEntryResponse(
        id=str(entry.id),
        action=entry.action.value,
        resource_type=entry.resource_type.value,
        resource_id=entry.resource_id,
        severity=entry.severity.value,
        user_id=str(entry.user_id) if entry.user_id else None,
        organization_id=str(entry.organization_id) if entry.organization_id else None,
        ip_address=str(entry.ip_address) if entry.ip_address else None,
        request_method=entry.request_method,
        request_path=entry.request_path,
        description=entry.description,
        success=entry.success,
        error_message=entry.error_message,
        metadata=entry.extra_data,
        created_at=entry.created_at,
    )


# =============================================================================
# Audit Log Endpoints
# =============================================================================

@router.get(
    "/audit",
    response_model=AuditLogResponse,
    summary="Get audit log",
    description="Retrieve paginated audit log entries with filtering.",
)
async def get_audit_log(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    search: Optional[str] = Query(None, description="Search in description and path"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AuditLogResponse:
    """Get paginated audit log with filtering."""
    query = db.query(AuditLog)

    # Non-admins can only see their own organization's logs
    if not current_user.is_superuser:
        if current_user.default_organization_id:
            query = query.filter(
                or_(
                    AuditLog.organization_id == current_user.default_organization_id,
                    AuditLog.user_id == current_user.id,
                )
            )
        else:
            query = query.filter(AuditLog.user_id == current_user.id)

    # Apply filters
    if resource_type:
        try:
            rt = AuditResourceType(resource_type)
            query = query.filter(AuditLog.resource_type == rt)
        except ValueError:
            pass

    if action:
        try:
            act = AuditAction(action)
            query = query.filter(AuditLog.action == act)
        except ValueError:
            pass

    if severity:
        try:
            sev = AuditSeverity(severity)
            query = query.filter(AuditLog.severity == sev)
        except ValueError:
            pass

    if user_id:
        try:
            query = query.filter(AuditLog.user_id == uuid.UUID(user_id))
        except ValueError:
            pass

    if success is not None:
        query = query.filter(AuditLog.success == success)

    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)

    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                AuditLog.description.ilike(search_term),
                AuditLog.request_path.ilike(search_term),
            )
        )

    # Get total count
    total = query.count()

    # Paginate
    offset = (page - 1) * page_size
    entries = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size).all()

    return AuditLogResponse(
        entries=[_entry_to_response(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + page_size) < total,
    )


@router.get(
    "/audit/stats",
    response_model=AuditStatsResponse,
    summary="Get audit statistics",
    description="Get aggregated audit log statistics.",
)
async def get_audit_stats(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> AuditStatsResponse:
    """Get audit log statistics (admin only)."""
    now = datetime.utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_day - timedelta(days=start_of_day.weekday())
    cutoff = now - timedelta(days=days)

    base_query = db.query(AuditLog).filter(AuditLog.created_at >= cutoff)

    # Total events
    total_events = base_query.count()

    # Events today
    events_today = base_query.filter(AuditLog.created_at >= start_of_day).count()

    # Events this week
    events_this_week = base_query.filter(AuditLog.created_at >= start_of_week).count()

    # Failed events
    failed_events = base_query.filter(AuditLog.success == False).count()

    # By action
    action_counts = db.query(
        AuditLog.action, func.count(AuditLog.id)
    ).filter(AuditLog.created_at >= cutoff).group_by(AuditLog.action).all()
    by_action = {a.value: c for a, c in action_counts}

    # By resource type
    resource_counts = db.query(
        AuditLog.resource_type, func.count(AuditLog.id)
    ).filter(AuditLog.created_at >= cutoff).group_by(AuditLog.resource_type).all()
    by_resource_type = {r.value: c for r, c in resource_counts}

    # By severity
    severity_counts = db.query(
        AuditLog.severity, func.count(AuditLog.id)
    ).filter(AuditLog.created_at >= cutoff).group_by(AuditLog.severity).all()
    by_severity = {s.value: c for s, c in severity_counts}

    return AuditStatsResponse(
        total_events=total_events,
        events_today=events_today,
        events_this_week=events_this_week,
        failed_events=failed_events,
        by_action=by_action,
        by_resource_type=by_resource_type,
        by_severity=by_severity,
    )


@router.get(
    "/audit/export",
    summary="Export audit log",
    description="Export audit log as CSV for compliance purposes.",
)
async def export_audit_log(
    start_date: datetime = Query(..., description="Export from date"),
    end_date: datetime = Query(..., description="Export to date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> StreamingResponse:
    """Export audit log as CSV (admin only)."""
    import csv
    import io

    query = db.query(AuditLog).filter(
        AuditLog.created_at >= start_date,
        AuditLog.created_at <= end_date,
    ).order_by(AuditLog.created_at.desc())

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID", "Timestamp", "Action", "Resource Type", "Resource ID",
        "User ID", "Organization ID", "IP Address", "Method", "Path",
        "Success", "Severity", "Description", "Error Message"
    ])

    # Data rows
    for entry in query.yield_per(1000):
        writer.writerow([
            str(entry.id),
            entry.created_at.isoformat(),
            entry.action.value,
            entry.resource_type.value,
            entry.resource_id or "",
            str(entry.user_id) if entry.user_id else "",
            str(entry.organization_id) if entry.organization_id else "",
            str(entry.ip_address) if entry.ip_address else "",
            entry.request_method or "",
            entry.request_path or "",
            str(entry.success),
            entry.severity.value,
            entry.description or "",
            entry.error_message or "",
        ])

    output.seek(0)

    filename = f"audit_log_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/audit/{entry_id}",
    response_model=AuditEntryResponse,
    summary="Get audit entry",
    description="Retrieve a specific audit log entry.",
)
async def get_audit_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AuditEntryResponse:
    """Get a specific audit entry."""
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError:
        raise NotFoundError("Audit entry", entry_id)

    entry = db.query(AuditLog).filter(AuditLog.id == entry_uuid).first()

    if not entry:
        raise NotFoundError("Audit entry", entry_id)

    # Check access permissions
    if not current_user.is_superuser:
        if entry.organization_id != current_user.default_organization_id and entry.user_id != current_user.id:
            raise ForbiddenError("You don't have access to this audit entry")

    return _entry_to_response(entry)


# =============================================================================
# Compliance Endpoints (GDPR)
# =============================================================================

@router.post(
    "/compliance/requests",
    response_model=ComplianceRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create compliance request",
    description="Request data export or deletion (GDPR).",
)
async def create_compliance_request(
    request: ComplianceRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ComplianceRequestResponse:
    """Create a GDPR compliance request."""
    # Check for pending requests of same type
    pending = db.query(ComplianceRequest).filter(
        ComplianceRequest.user_id == current_user.id,
        ComplianceRequest.request_type == request.request_type,
        ComplianceRequest.status.in_(["pending", "processing"]),
    ).first()

    if pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already have a pending {request.request_type} request",
        )

    compliance_request = ComplianceRequest(
        user_id=current_user.id,
        organization_id=current_user.default_organization_id,
        request_type=request.request_type,
        reason=request.reason,
        scope=request.scope,
        status="pending",
    )
    db.add(compliance_request)
    db.commit()
    db.refresh(compliance_request)

    logger.info(
        "compliance_request_created",
        request_id=str(compliance_request.id),
        request_type=request.request_type,
        user_id=str(current_user.id),
    )

    return ComplianceRequestResponse(
        id=str(compliance_request.id),
        request_type=compliance_request.request_type,
        status=compliance_request.status,
        reason=compliance_request.reason,
        created_at=compliance_request.created_at,
        completed_at=compliance_request.completed_at,
    )


@router.get(
    "/compliance/requests",
    response_model=ComplianceListResponse,
    summary="List compliance requests",
    description="Get your compliance request history.",
)
async def list_compliance_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ComplianceListResponse:
    """List user's compliance requests."""
    requests = db.query(ComplianceRequest).filter(
        ComplianceRequest.user_id == current_user.id,
    ).order_by(ComplianceRequest.created_at.desc()).all()

    return ComplianceListResponse(
        requests=[
            ComplianceRequestResponse(
                id=str(r.id),
                request_type=r.request_type,
                status=r.status,
                reason=r.reason,
                download_url=r.download_url,
                download_expires_at=r.download_expires_at,
                created_at=r.created_at,
                completed_at=r.completed_at,
            )
            for r in requests
        ],
        total=len(requests),
    )


@router.get(
    "/compliance/requests/{request_id}",
    response_model=ComplianceRequestResponse,
    summary="Get compliance request",
    description="Get details of a specific compliance request.",
)
async def get_compliance_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ComplianceRequestResponse:
    """Get a specific compliance request."""
    try:
        request_uuid = uuid.UUID(request_id)
    except ValueError:
        raise NotFoundError("Compliance request", request_id)

    comp_request = db.query(ComplianceRequest).filter(
        ComplianceRequest.id == request_uuid,
    ).first()

    if not comp_request:
        raise NotFoundError("Compliance request", request_id)

    # Check ownership
    if comp_request.user_id != current_user.id and not current_user.is_superuser:
        raise ForbiddenError("You don't have access to this request")

    return ComplianceRequestResponse(
        id=str(comp_request.id),
        request_type=comp_request.request_type,
        status=comp_request.status,
        reason=comp_request.reason,
        download_url=comp_request.download_url,
        download_expires_at=comp_request.download_expires_at,
        created_at=comp_request.created_at,
        completed_at=comp_request.completed_at,
    )


# =============================================================================
# Available Actions/Types Endpoints
# =============================================================================

@router.get(
    "/audit/actions",
    summary="List audit actions",
    description="Get list of all possible audit action types.",
)
async def list_audit_actions() -> dict:
    """List all audit action types."""
    return {
        "actions": [
            {"value": a.value, "name": a.name}
            for a in AuditAction
        ]
    }


@router.get(
    "/audit/resource-types",
    summary="List resource types",
    description="Get list of all possible audit resource types.",
)
async def list_resource_types() -> dict:
    """List all resource types."""
    return {
        "resource_types": [
            {"value": r.value, "name": r.name}
            for r in AuditResourceType
        ]
    }
