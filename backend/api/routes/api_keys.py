"""
API Keys management routes.

Provides endpoints for creating, listing, and managing API keys.
"""
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.api_key import APIKey, APIKeyScope
from backend.auth.dependencies import get_current_active_user
from backend.exceptions import NotFoundError, ValidationError, ForbiddenError

logger = structlog.get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateAPIKeyRequest(BaseModel):
    """Request to create an API key."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    scopes: List[str] = Field(default_factory=lambda: ["read"])
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)
    rate_limit_per_day: int = Field(default=10000, ge=1, le=100000)
    allowed_ips: Optional[List[str]] = None


class APIKeyResponse(BaseModel):
    """API key response (without the actual key)."""
    id: str
    name: str
    description: Optional[str]
    key_prefix: str
    scopes: List[str]
    rate_limit_per_minute: int
    rate_limit_per_day: int
    allowed_ips: Optional[List[str]]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreatedResponse(BaseModel):
    """Response when creating an API key (includes the full key once)."""
    id: str
    name: str
    key: str  # Full API key - only shown once!
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime]
    created_at: datetime
    warning: str = "Store this API key securely. It will not be shown again."


class APIKeyListResponse(BaseModel):
    """Response for API key list."""
    keys: List[APIKeyResponse]
    total: int


class UpdateAPIKeyRequest(BaseModel):
    """Request to update an API key."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    scopes: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=1000)
    rate_limit_per_day: Optional[int] = Field(None, ge=1, le=100000)
    allowed_ips: Optional[List[str]] = None


class RevokeAPIKeyRequest(BaseModel):
    """Request to revoke an API key."""
    reason: Optional[str] = None


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

def _validate_scopes(scopes: List[str]) -> None:
    """Validate that all scopes are valid."""
    valid_scopes = {s.value for s in APIKeyScope}
    invalid = [s for s in scopes if s not in valid_scopes]
    if invalid:
        raise ValidationError(
            message="Invalid scopes",
            errors=[{"field": "scopes", "message": f"Invalid scopes: {', '.join(invalid)}"}]
        )


def _key_to_response(key: APIKey) -> APIKeyResponse:
    """Convert API key model to response."""
    return APIKeyResponse(
        id=str(key.id),
        name=key.name,
        description=key.description,
        key_prefix=key.key_prefix,
        scopes=key.scopes or [],
        rate_limit_per_minute=key.rate_limit_per_minute,
        rate_limit_per_day=key.rate_limit_per_day,
        allowed_ips=key.allowed_ips,
        expires_at=key.expires_at,
        last_used_at=key.last_used_at,
        usage_count=key.usage_count,
        is_active=key.is_active,
        created_at=key.created_at,
    )


# =============================================================================
# API Key Endpoints
# =============================================================================

@router.post(
    "",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Create a new API key for programmatic access.",
)
async def create_api_key(
    request: CreateAPIKeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> APIKeyCreatedResponse:
    """Create a new API key."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise ValidationError(
            message="Organization required",
            errors=[{"field": "organization", "message": "User must belong to an organization"}]
        )

    # Validate scopes
    _validate_scopes(request.scopes)

    # Generate key
    full_key, key_prefix, key_hash = APIKey.generate_key()

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    # Create key record
    api_key = APIKey(
        name=request.name,
        description=request.description,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=request.scopes,
        rate_limit_per_minute=request.rate_limit_per_minute,
        rate_limit_per_day=request.rate_limit_per_day,
        allowed_ips=request.allowed_ips,
        expires_at=expires_at,
        organization_id=org_id,
        created_by_user_id=current_user.id,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    logger.info(
        "api_key_created",
        key_id=str(api_key.id),
        user_id=str(current_user.id),
        org_id=str(org_id),
    )

    return APIKeyCreatedResponse(
        id=str(api_key.id),
        name=api_key.name,
        key=full_key,  # Only shown once!
        key_prefix=key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get(
    "",
    response_model=APIKeyListResponse,
    summary="List API keys",
    description="List all API keys for the organization.",
)
async def list_api_keys(
    include_revoked: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> APIKeyListResponse:
    """List all API keys."""
    org_id = current_user.default_organization_id
    if not org_id:
        return APIKeyListResponse(keys=[], total=0)

    query = db.query(APIKey).filter(APIKey.organization_id == org_id)

    if not include_revoked:
        query = query.filter(APIKey.is_active == True)

    keys = query.order_by(APIKey.created_at.desc()).all()

    return APIKeyListResponse(
        keys=[_key_to_response(k) for k in keys],
        total=len(keys),
    )


@router.get(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Get API key",
    description="Get details of a specific API key.",
)
async def get_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> APIKeyResponse:
    """Get API key details."""
    import uuid

    try:
        key_uuid = uuid.UUID(key_id)
    except ValueError:
        raise NotFoundError("API Key", key_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("API Key", key_id)

    api_key = db.query(APIKey).filter(
        APIKey.id == key_uuid,
        APIKey.organization_id == org_id,
    ).first()

    if not api_key:
        raise NotFoundError("API Key", key_id)

    return _key_to_response(api_key)


@router.patch(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Update API key",
    description="Update an API key's settings.",
)
async def update_api_key(
    key_id: str,
    request: UpdateAPIKeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> APIKeyResponse:
    """Update API key settings."""
    import uuid

    try:
        key_uuid = uuid.UUID(key_id)
    except ValueError:
        raise NotFoundError("API Key", key_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("API Key", key_id)

    api_key = db.query(APIKey).filter(
        APIKey.id == key_uuid,
        APIKey.organization_id == org_id,
        APIKey.is_active == True,
    ).first()

    if not api_key:
        raise NotFoundError("API Key", key_id)

    # Update fields
    if request.name is not None:
        api_key.name = request.name
    if request.description is not None:
        api_key.description = request.description
    if request.scopes is not None:
        _validate_scopes(request.scopes)
        api_key.scopes = request.scopes
    if request.rate_limit_per_minute is not None:
        api_key.rate_limit_per_minute = request.rate_limit_per_minute
    if request.rate_limit_per_day is not None:
        api_key.rate_limit_per_day = request.rate_limit_per_day
    if request.allowed_ips is not None:
        api_key.allowed_ips = request.allowed_ips

    db.commit()
    db.refresh(api_key)

    logger.info(
        "api_key_updated",
        key_id=str(api_key.id),
        user_id=str(current_user.id),
    )

    return _key_to_response(api_key)


@router.delete(
    "/{key_id}",
    response_model=MessageResponse,
    summary="Revoke API key",
    description="Revoke an API key, immediately disabling it.",
)
async def revoke_api_key(
    key_id: str,
    request: RevokeAPIKeyRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """Revoke an API key."""
    import uuid

    try:
        key_uuid = uuid.UUID(key_id)
    except ValueError:
        raise NotFoundError("API Key", key_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("API Key", key_id)

    api_key = db.query(APIKey).filter(
        APIKey.id == key_uuid,
        APIKey.organization_id == org_id,
    ).first()

    if not api_key:
        raise NotFoundError("API Key", key_id)

    if not api_key.is_active:
        raise ValidationError(
            message="Key already revoked",
            errors=[{"field": "key", "message": "This API key has already been revoked"}]
        )

    reason = request.reason if request else None
    api_key.revoke(reason)
    db.commit()

    logger.info(
        "api_key_revoked",
        key_id=str(api_key.id),
        user_id=str(current_user.id),
        reason=reason,
    )

    return MessageResponse(message="API key revoked successfully")


@router.get(
    "/{key_id}/usage",
    summary="Get API key usage",
    description="Get usage statistics for an API key.",
)
async def get_api_key_usage(
    key_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get API key usage statistics."""
    import uuid
    from datetime import timedelta
    from sqlalchemy import func

    try:
        key_uuid = uuid.UUID(key_id)
    except ValueError:
        raise NotFoundError("API Key", key_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("API Key", key_id)

    api_key = db.query(APIKey).filter(
        APIKey.id == key_uuid,
        APIKey.organization_id == org_id,
    ).first()

    if not api_key:
        raise NotFoundError("API Key", key_id)

    from backend.models.api_key import APIKeyUsageLog

    # Get usage stats for the time period
    cutoff = datetime.utcnow() - timedelta(days=days)

    total_requests = db.query(func.count(APIKeyUsageLog.id)).filter(
        APIKeyUsageLog.api_key_id == key_uuid,
        APIKeyUsageLog.created_at >= cutoff,
    ).scalar() or 0

    # Get endpoint breakdown
    endpoint_stats = db.query(
        APIKeyUsageLog.endpoint,
        func.count(APIKeyUsageLog.id).label("count"),
    ).filter(
        APIKeyUsageLog.api_key_id == key_uuid,
        APIKeyUsageLog.created_at >= cutoff,
    ).group_by(APIKeyUsageLog.endpoint).all()

    # Get status code breakdown
    status_stats = db.query(
        APIKeyUsageLog.status_code,
        func.count(APIKeyUsageLog.id).label("count"),
    ).filter(
        APIKeyUsageLog.api_key_id == key_uuid,
        APIKeyUsageLog.created_at >= cutoff,
    ).group_by(APIKeyUsageLog.status_code).all()

    return {
        "key_id": key_id,
        "period_days": days,
        "total_requests": total_requests,
        "lifetime_requests": api_key.usage_count,
        "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        "endpoints": [{"endpoint": e, "count": c} for e, c in endpoint_stats],
        "status_codes": [{"status": s, "count": c} for s, c in status_stats],
    }
