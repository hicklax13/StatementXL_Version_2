"""
Audit API routes.

Provides endpoints for audit log viewing and management.
"""
import uuid
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db

logger = structlog.get_logger(__name__)

router = APIRouter()


# Response Models
class AuditEntryResponse(BaseModel):
    """Response model for an audit entry."""
    id: str
    timestamp: datetime
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    user_id: Optional[str] = None
    details: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None


class AuditLogResponse(BaseModel):
    """Response model for paginated audit log."""
    entries: List[AuditEntryResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# In-memory audit log for now (would be database in production)
_audit_log: List[dict] = []


def log_audit_event(
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[str] = None,
    details: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
):
    """Log an audit event."""
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow(),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "user_id": user_id,
        "details": details,
        "old_value": old_value,
        "new_value": new_value,
    }
    _audit_log.insert(0, entry)  # Most recent first
    logger.info("audit_event", **entry)
    return entry


@router.get(
    "/audit",
    response_model=AuditLogResponse,
    summary="Get audit log",
    description="Retrieve paginated audit log entries.",
)
async def get_audit_log(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    db: Session = Depends(get_db),
) -> AuditLogResponse:
    """
    Get paginated audit log.

    Args:
        page: Page number (1-indexed).
        page_size: Number of items per page.
        resource_type: Optional filter by resource type.
        action: Optional filter by action.
        db: Database session.

    Returns:
        Paginated audit log entries.
    """
    # Filter entries
    filtered = _audit_log
    if resource_type:
        filtered = [e for e in filtered if e["resource_type"] == resource_type]
    if action:
        filtered = [e for e in filtered if e["action"] == action]

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_entries = filtered[start:end]

    return AuditLogResponse(
        entries=[AuditEntryResponse(**e) for e in page_entries],
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
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
) -> AuditEntryResponse:
    """
    Get a specific audit entry.

    Args:
        entry_id: Audit entry ID.
        db: Database session.

    Returns:
        Audit entry details.
    """
    from fastapi import HTTPException, status

    for entry in _audit_log:
        if entry["id"] == entry_id:
            return AuditEntryResponse(**entry)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Audit entry {entry_id} not found",
    )


# Log some initial events for demonstration
log_audit_event("system_start", "system", details="StatementXL API started")
