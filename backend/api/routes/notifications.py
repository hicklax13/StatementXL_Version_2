"""
Notification API routes.

Provides endpoints for managing user notifications.
"""
import uuid
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.dependencies import get_current_active_user
from backend.models.user import User
from backend.models.notification import NotificationType, NotificationPriority
from backend.services.notification_service import get_notification_service

logger = structlog.get_logger(__name__)

router = APIRouter()


# ==================== Schemas ====================

class NotificationResponse(BaseModel):
    """Response for a notification."""
    id: str
    type: str
    priority: str
    title: str
    message: str
    action_url: Optional[str]
    action_label: Optional[str]
    related_entity_type: Optional[str]
    related_entity_id: Optional[str]
    sender_id: Optional[str]
    group_key: Optional[str]
    group_count: int
    is_read: bool
    read_at: Optional[str]
    data: dict
    created_at: str


class NotificationListResponse(BaseModel):
    """Response for notification list."""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationPreferenceUpdate(BaseModel):
    """Request to update notification preference."""
    in_app_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    slack_enabled: Optional[bool] = None
    digest_enabled: Optional[bool] = None
    digest_frequency: Optional[str] = Field(None, pattern="^(immediate|daily|weekly)$")


class NotificationPreferenceResponse(BaseModel):
    """Response for notification preference."""
    notification_type: str
    in_app_enabled: bool
    email_enabled: bool
    push_enabled: bool
    sms_enabled: bool
    slack_enabled: bool
    digest_enabled: bool
    digest_frequency: Optional[str]


class PushSubscriptionCreate(BaseModel):
    """Request to create push subscription."""
    endpoint: str
    p256dh_key: str
    auth_key: str
    device_type: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None


class PushSubscriptionResponse(BaseModel):
    """Response for push subscription."""
    id: str
    endpoint: str
    device_type: Optional[str]
    browser: Optional[str]
    is_active: bool
    created_at: str


class MarkReadRequest(BaseModel):
    """Request to mark notifications as read."""
    notification_ids: List[str]


# ==================== Notification Endpoints ====================

@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications",
)
async def list_notifications(
    unread_only: bool = False,
    types: Optional[str] = Query(None, description="Comma-separated notification types"),
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationListResponse:
    """Get notifications for the current user."""
    service = get_notification_service(db)

    # Parse notification types
    notification_types = None
    if types:
        try:
            notification_types = [
                NotificationType(t.strip()) for t in types.split(",")
            ]
        except ValueError:
            pass

    notifications = service.get_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        notification_types=notification_types,
        limit=limit,
        offset=offset,
    )

    unread_count = service.get_unread_count(current_user.id)

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=str(n.id),
                type=n.type.value,
                priority=n.priority.value,
                title=n.title,
                message=n.message,
                action_url=n.action_url,
                action_label=n.action_label,
                related_entity_type=n.related_entity_type,
                related_entity_id=str(n.related_entity_id) if n.related_entity_id else None,
                sender_id=str(n.sender_id) if n.sender_id else None,
                group_key=n.group_key,
                group_count=n.group_count,
                is_read=n.is_read,
                read_at=n.read_at.isoformat() if n.read_at else None,
                data=n.data or {},
                created_at=n.created_at.isoformat(),
            )
            for n in notifications
        ],
        total=len(notifications),
        unread_count=unread_count,
    )


@router.get(
    "/unread-count",
    summary="Get unread count",
)
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get count of unread notifications."""
    service = get_notification_service(db)
    count = service.get_unread_count(current_user.id)

    return {"unread_count": count}


# ==================== Preference Endpoints ====================
# NOTE: These must be defined BEFORE /{notification_id} to avoid route conflicts

@router.get(
    "/preferences",
    response_model=List[NotificationPreferenceResponse],
    summary="Get notification preferences",
)
async def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[NotificationPreferenceResponse]:
    """Get all notification preferences for the current user."""
    service = get_notification_service(db)
    preferences = service.get_user_preferences(current_user.id)

    # Return preferences for all notification types
    result = []
    for notification_type in NotificationType:
        pref = preferences.get(notification_type)
        if pref:
            result.append(NotificationPreferenceResponse(
                notification_type=notification_type.value,
                in_app_enabled=pref.in_app_enabled,
                email_enabled=pref.email_enabled,
                push_enabled=pref.push_enabled,
                sms_enabled=pref.sms_enabled,
                slack_enabled=pref.slack_enabled,
                digest_enabled=pref.digest_enabled,
                digest_frequency=pref.digest_frequency,
            ))
        else:
            # Return defaults
            result.append(NotificationPreferenceResponse(
                notification_type=notification_type.value,
                in_app_enabled=True,
                email_enabled=True,
                push_enabled=True,
                sms_enabled=False,
                slack_enabled=False,
                digest_enabled=False,
                digest_frequency=None,
            ))

    return result


@router.put(
    "/preferences/{notification_type}",
    response_model=NotificationPreferenceResponse,
    summary="Update notification preference",
)
async def update_preference(
    notification_type: str,
    request: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationPreferenceResponse:
    """Update notification preference for a specific type."""
    try:
        nt = NotificationType(notification_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid notification type: {notification_type}",
        )

    service = get_notification_service(db)
    pref = service.update_preference(
        user_id=current_user.id,
        notification_type=nt,
        in_app_enabled=request.in_app_enabled,
        email_enabled=request.email_enabled,
        push_enabled=request.push_enabled,
        sms_enabled=request.sms_enabled,
        slack_enabled=request.slack_enabled,
        digest_enabled=request.digest_enabled,
        digest_frequency=request.digest_frequency,
    )

    return NotificationPreferenceResponse(
        notification_type=pref.notification_type.value,
        in_app_enabled=pref.in_app_enabled,
        email_enabled=pref.email_enabled,
        push_enabled=pref.push_enabled,
        sms_enabled=pref.sms_enabled,
        slack_enabled=pref.slack_enabled,
        digest_enabled=pref.digest_enabled,
        digest_frequency=pref.digest_frequency,
    )


@router.post(
    "/preferences/bulk",
    summary="Bulk update preferences",
)
async def bulk_update_preferences(
    in_app_enabled: Optional[bool] = None,
    email_enabled: Optional[bool] = None,
    push_enabled: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Bulk update preferences for all notification types."""
    service = get_notification_service(db)

    count = 0
    for notification_type in NotificationType:
        service.update_preference(
            user_id=current_user.id,
            notification_type=notification_type,
            in_app_enabled=in_app_enabled,
            email_enabled=email_enabled,
            push_enabled=push_enabled,
        )
        count += 1

    return {"message": f"Updated {count} preferences"}


# ==================== Push Subscription Endpoints ====================
# NOTE: These must be defined BEFORE /{notification_id} to avoid route conflicts

@router.post(
    "/push/subscribe",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to push notifications",
)
async def subscribe_push(
    request: PushSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PushSubscriptionResponse:
    """Subscribe to push notifications."""
    service = get_notification_service(db)

    subscription = service.register_push_subscription(
        user_id=current_user.id,
        endpoint=request.endpoint,
        p256dh_key=request.p256dh_key,
        auth_key=request.auth_key,
        device_type=request.device_type,
        browser=request.browser,
        os=request.os,
    )

    return PushSubscriptionResponse(
        id=str(subscription.id),
        endpoint=subscription.endpoint,
        device_type=subscription.device_type,
        browser=subscription.browser,
        is_active=subscription.is_active,
        created_at=subscription.created_at.isoformat(),
    )


@router.delete(
    "/push/unsubscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unsubscribe from push notifications",
)
async def unsubscribe_push(
    endpoint: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Unsubscribe from push notifications."""
    service = get_notification_service(db)
    service.unregister_push_subscription(current_user.id, endpoint)


@router.get(
    "/push/subscriptions",
    response_model=List[PushSubscriptionResponse],
    summary="List push subscriptions",
)
async def list_push_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[PushSubscriptionResponse]:
    """List all push subscriptions for the current user."""
    from backend.models.notification import PushSubscription

    subscriptions = db.query(PushSubscription).filter(
        PushSubscription.user_id == current_user.id,
        PushSubscription.is_active == True,
    ).all()

    return [
        PushSubscriptionResponse(
            id=str(s.id),
            endpoint=s.endpoint,
            device_type=s.device_type,
            browser=s.browser,
            is_active=s.is_active,
            created_at=s.created_at.isoformat(),
        )
        for s in subscriptions
    ]


# ==================== Test Endpoint ====================
# NOTE: Must be defined BEFORE /{notification_id} to avoid route conflicts

@router.post(
    "/test",
    summary="Send test notification",
)
async def send_test_notification(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Send a test notification to yourself."""
    service = get_notification_service(db)

    notification = service.create_notification(
        user_id=current_user.id,
        notification_type=NotificationType.SYSTEM_UPDATE,
        title="Test Notification",
        message="This is a test notification to verify your notification settings are working correctly.",
        priority=NotificationPriority.NORMAL,
        action_url="/settings/notifications",
        action_label="View Settings",
    )

    return {
        "message": "Test notification sent",
        "notification_id": str(notification.id),
    }


# ==================== Batch Read Endpoints ====================
# NOTE: Must be defined BEFORE /{notification_id} to avoid route conflicts

@router.post(
    "/read-all",
    summary="Mark all as read",
)
async def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark all notifications as read."""
    service = get_notification_service(db)
    count = service.mark_all_as_read(current_user.id)

    return {"message": f"Marked {count} notifications as read", "count": count}


@router.post(
    "/read-batch",
    summary="Mark batch as read",
)
async def mark_batch_as_read(
    request: MarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark multiple notifications as read."""
    service = get_notification_service(db)

    count = 0
    for notification_id in request.notification_ids:
        try:
            result = service.mark_as_read(
                uuid.UUID(notification_id),
                current_user.id,
            )
            if result:
                count += 1
        except ValueError:
            pass

    return {"message": f"Marked {count} notifications as read", "count": count}


# ==================== Individual Notification Endpoints ====================
# NOTE: /{notification_id} routes must come AFTER all /specific-path routes

@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Get notification",
)
async def get_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationResponse:
    """Get a specific notification."""
    service = get_notification_service(db)

    notifications = service.get_notifications(
        user_id=current_user.id,
        limit=1,
    )

    # Find the specific notification
    from backend.models.notification import Notification
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return NotificationResponse(
        id=str(notification.id),
        type=notification.type.value,
        priority=notification.priority.value,
        title=notification.title,
        message=notification.message,
        action_url=notification.action_url,
        action_label=notification.action_label,
        related_entity_type=notification.related_entity_type,
        related_entity_id=str(notification.related_entity_id) if notification.related_entity_id else None,
        sender_id=str(notification.sender_id) if notification.sender_id else None,
        group_key=notification.group_key,
        group_count=notification.group_count,
        is_read=notification.is_read,
        read_at=notification.read_at.isoformat() if notification.read_at else None,
        data=notification.data or {},
        created_at=notification.created_at.isoformat(),
    )


@router.post(
    "/{notification_id}/read",
    summary="Mark as read",
)
async def mark_as_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark a notification as read."""
    service = get_notification_service(db)
    notification = service.mark_as_read(notification_id, current_user.id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return {"message": "Notification marked as read"}


@router.post(
    "/{notification_id}/archive",
    summary="Archive notification",
)
async def archive_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Archive a notification."""
    service = get_notification_service(db)
    notification = service.archive_notification(notification_id, current_user.id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return {"message": "Notification archived"}


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification",
)
async def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Delete a notification."""
    service = get_notification_service(db)
    deleted = service.delete_notification(notification_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
