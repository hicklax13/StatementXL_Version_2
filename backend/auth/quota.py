"""
Quota enforcement dependencies.

Provides FastAPI dependencies for checking and enforcing organization quotas.
"""
from typing import Optional
from functools import wraps

import structlog
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.auth.dependencies import get_current_active_user
from backend.services.analytics_service import AnalyticsService

logger = structlog.get_logger(__name__)


class QuotaExceededError(HTTPException):
    """Exception raised when a quota limit is exceeded."""

    def __init__(self, quota_type: str, message: str, usage: dict):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "quota_type": quota_type,
                "message": message,
                "usage": usage,
            },
        )


async def check_document_quota(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> bool:
    """
    Check if the organization has remaining document quota.

    Raises QuotaExceededError if the quota is exceeded.
    """
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    allowed, message, usage = service.check_quota(org_id, "documents")

    if not allowed:
        logger.warning(
            "document_quota_exceeded",
            organization_id=str(org_id),
            user_id=str(current_user.id),
            usage=usage,
        )
        raise QuotaExceededError("documents", message, usage)

    return True


async def check_api_quota(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> bool:
    """
    Check if the organization has remaining API request quota.

    Raises QuotaExceededError if the quota is exceeded.
    """
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    allowed, message, usage = service.check_quota(org_id, "api")

    if not allowed:
        logger.warning(
            "api_quota_exceeded",
            organization_id=str(org_id),
            user_id=str(current_user.id),
            usage=usage,
        )
        raise QuotaExceededError("api", message, usage)

    return True


async def check_storage_quota(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> bool:
    """
    Check if the organization has remaining storage quota.

    Raises QuotaExceededError if the quota is exceeded.
    """
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    allowed, message, usage = service.check_quota(org_id, "storage")

    if not allowed:
        logger.warning(
            "storage_quota_exceeded",
            organization_id=str(org_id),
            user_id=str(current_user.id),
            usage=usage,
        )
        raise QuotaExceededError("storage", message, usage)

    return True


async def check_batch_processing_allowed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> bool:
    """
    Check if the organization has batch processing enabled.

    Raises HTTPException if batch processing is not allowed.
    """
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    quota = service.get_or_create_quota(org_id)

    if not quota.allow_batch_processing:
        logger.warning(
            "batch_processing_not_allowed",
            organization_id=str(org_id),
            user_id=str(current_user.id),
            plan=quota.plan_name,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "batch_processing",
                "message": "Batch processing is not available on your current plan",
                "plan": quota.plan_name,
            },
        )

    return True


async def check_api_access_allowed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> bool:
    """
    Check if the organization has API access enabled.

    Raises HTTPException if API access is not allowed.
    """
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    quota = service.get_or_create_quota(org_id)

    if not quota.allow_api_access:
        logger.warning(
            "api_access_not_allowed",
            organization_id=str(org_id),
            user_id=str(current_user.id),
            plan=quota.plan_name,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "api_access",
                "message": "API access is not available on your current plan",
                "plan": quota.plan_name,
            },
        )

    return True


async def check_webhooks_allowed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> bool:
    """
    Check if the organization has webhooks enabled.

    Raises HTTPException if webhooks are not allowed.
    """
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    quota = service.get_or_create_quota(org_id)

    if not quota.allow_webhooks:
        logger.warning(
            "webhooks_not_allowed",
            organization_id=str(org_id),
            user_id=str(current_user.id),
            plan=quota.plan_name,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "webhooks",
                "message": "Webhooks are not available on your current plan",
                "plan": quota.plan_name,
            },
        )

    return True


async def check_integrations_allowed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> bool:
    """
    Check if the organization has integrations enabled.

    Raises HTTPException if integrations are not allowed.
    """
    org_id = current_user.default_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    service = AnalyticsService(db)
    quota = service.get_or_create_quota(org_id)

    if not quota.allow_integrations:
        logger.warning(
            "integrations_not_allowed",
            organization_id=str(org_id),
            user_id=str(current_user.id),
            plan=quota.plan_name,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "integrations",
                "message": "Integrations are not available on your current plan",
                "plan": quota.plan_name,
            },
        )

    return True


def get_file_size_limit(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> int:
    """
    Get the maximum file size limit in bytes for the organization.

    Returns the limit in bytes.
    """
    org_id = current_user.default_organization_id
    if not org_id:
        # Default to 25MB if no organization
        return 25 * 1024 * 1024

    service = AnalyticsService(db)
    quota = service.get_or_create_quota(org_id)

    return quota.max_file_size_mb * 1024 * 1024


def get_max_pages_limit(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> int:
    """
    Get the maximum pages per document limit for the organization.

    Returns the page limit.
    """
    org_id = current_user.default_organization_id
    if not org_id:
        # Default to 50 pages if no organization
        return 50

    service = AnalyticsService(db)
    quota = service.get_or_create_quota(org_id)

    return quota.max_pages_per_document
