"""
Webhook management routes.

Provides endpoints for creating, managing, and testing webhooks.
"""
import uuid
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.webhook import Webhook, WebhookEvent, WebhookStatus, WebhookDelivery
from backend.auth.dependencies import get_current_active_user
from backend.exceptions import NotFoundError, ValidationError

logger = structlog.get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateWebhookRequest(BaseModel):
    """Request to create a webhook."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    url: str = Field(..., max_length=2048)
    events: List[str] = Field(..., min_length=1)
    custom_headers: Optional[dict] = None
    max_retries: int = Field(default=3, ge=0, le=10)


class WebhookResponse(BaseModel):
    """Webhook response."""
    id: str
    name: str
    description: Optional[str]
    url: str
    events: List[str]
    status: str
    secret: str  # Needed for signature verification
    failure_count: int
    last_triggered_at: Optional[datetime]
    last_success_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    last_failure_reason: Optional[str]
    max_retries: int
    custom_headers: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookListResponse(BaseModel):
    """Response for webhook list."""
    webhooks: List[WebhookResponse]
    total: int


class UpdateWebhookRequest(BaseModel):
    """Request to update a webhook."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    url: Optional[str] = Field(None, max_length=2048)
    events: Optional[List[str]] = None
    custom_headers: Optional[dict] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    status: Optional[str] = None


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery log response."""
    id: str
    event_type: str
    event_id: str
    status_code: Optional[int]
    success: bool
    error_message: Optional[str]
    response_time_ms: Optional[int]
    attempt_number: int
    created_at: datetime
    delivered_at: Optional[datetime]

    class Config:
        from_attributes = True


class WebhookDeliveryListResponse(BaseModel):
    """Response for delivery list."""
    deliveries: List[WebhookDeliveryResponse]
    total: int


class TestWebhookRequest(BaseModel):
    """Request to test a webhook."""
    event_type: str = "test.ping"


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


class AvailableEventsResponse(BaseModel):
    """List of available webhook events."""
    events: List[dict]


# =============================================================================
# Helper Functions
# =============================================================================

def _validate_events(events: List[str]) -> None:
    """Validate that all events are valid."""
    valid_events = {e.value for e in WebhookEvent}
    valid_events.add("*")  # Wildcard
    # Also allow prefix wildcards like "document.*"
    prefixes = {e.value.split(".")[0] for e in WebhookEvent}

    for event in events:
        if event in valid_events:
            continue
        if event.endswith(".*") and event[:-2] in prefixes:
            continue
        raise ValidationError(
            message="Invalid event type",
            errors=[{"field": "events", "message": f"Invalid event: {event}"}]
        )


def _webhook_to_response(webhook: Webhook) -> WebhookResponse:
    """Convert webhook model to response."""
    return WebhookResponse(
        id=str(webhook.id),
        name=webhook.name,
        description=webhook.description,
        url=webhook.url,
        events=webhook.events or [],
        status=webhook.status.value,
        secret=webhook.secret,
        failure_count=webhook.failure_count,
        last_triggered_at=webhook.last_triggered_at,
        last_success_at=webhook.last_success_at,
        last_failure_at=webhook.last_failure_at,
        last_failure_reason=webhook.last_failure_reason,
        max_retries=webhook.max_retries,
        custom_headers=webhook.custom_headers,
        created_at=webhook.created_at,
    )


def _delivery_to_response(delivery: WebhookDelivery) -> WebhookDeliveryResponse:
    """Convert delivery model to response."""
    return WebhookDeliveryResponse(
        id=str(delivery.id),
        event_type=delivery.event_type,
        event_id=delivery.event_id,
        status_code=delivery.status_code,
        success=delivery.success,
        error_message=delivery.error_message,
        response_time_ms=delivery.response_time_ms,
        attempt_number=delivery.attempt_number,
        created_at=delivery.created_at,
        delivered_at=delivery.delivered_at,
    )


# =============================================================================
# Webhook Endpoints
# =============================================================================

@router.get(
    "/events",
    response_model=AvailableEventsResponse,
    summary="List available events",
    description="Get list of all available webhook event types.",
)
async def list_available_events() -> AvailableEventsResponse:
    """List all available webhook events."""
    events = []
    for event in WebhookEvent:
        category, action = event.value.split(".", 1)
        events.append({
            "event": event.value,
            "category": category,
            "action": action,
            "description": f"{category.title()} {action.replace('_', ' ')} event",
        })
    return AvailableEventsResponse(events=events)


@router.post(
    "",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description="Create a new webhook endpoint.",
)
async def create_webhook(
    request: CreateWebhookRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WebhookResponse:
    """Create a new webhook."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise ValidationError(
            message="Organization required",
            errors=[{"field": "organization", "message": "User must belong to an organization"}]
        )

    # Validate events
    _validate_events(request.events)

    # Generate secret
    secret = Webhook.generate_secret()

    # Create webhook
    webhook = Webhook(
        name=request.name,
        description=request.description,
        url=request.url,
        events=request.events,
        secret=secret,
        custom_headers=request.custom_headers,
        max_retries=request.max_retries,
        organization_id=org_id,
        created_by_user_id=current_user.id,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    logger.info(
        "webhook_created",
        webhook_id=str(webhook.id),
        user_id=str(current_user.id),
        events=request.events,
    )

    return _webhook_to_response(webhook)


@router.get(
    "",
    response_model=WebhookListResponse,
    summary="List webhooks",
    description="List all webhooks for the organization.",
)
async def list_webhooks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WebhookListResponse:
    """List all webhooks."""
    org_id = current_user.default_organization_id
    if not org_id:
        return WebhookListResponse(webhooks=[], total=0)

    webhooks = db.query(Webhook).filter(
        Webhook.organization_id == org_id,
    ).order_by(Webhook.created_at.desc()).all()

    return WebhookListResponse(
        webhooks=[_webhook_to_response(w) for w in webhooks],
        total=len(webhooks),
    )


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook",
    description="Get details of a specific webhook.",
)
async def get_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WebhookResponse:
    """Get webhook details."""
    try:
        webhook_uuid = uuid.UUID(webhook_id)
    except ValueError:
        raise NotFoundError("Webhook", webhook_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Webhook", webhook_id)

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_uuid,
        Webhook.organization_id == org_id,
    ).first()

    if not webhook:
        raise NotFoundError("Webhook", webhook_id)

    return _webhook_to_response(webhook)


@router.patch(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update webhook",
    description="Update a webhook's configuration.",
)
async def update_webhook(
    webhook_id: str,
    request: UpdateWebhookRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WebhookResponse:
    """Update webhook settings."""
    try:
        webhook_uuid = uuid.UUID(webhook_id)
    except ValueError:
        raise NotFoundError("Webhook", webhook_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Webhook", webhook_id)

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_uuid,
        Webhook.organization_id == org_id,
    ).first()

    if not webhook:
        raise NotFoundError("Webhook", webhook_id)

    # Update fields
    if request.name is not None:
        webhook.name = request.name
    if request.description is not None:
        webhook.description = request.description
    if request.url is not None:
        webhook.url = request.url
    if request.events is not None:
        _validate_events(request.events)
        webhook.events = request.events
    if request.custom_headers is not None:
        webhook.custom_headers = request.custom_headers
    if request.max_retries is not None:
        webhook.max_retries = request.max_retries
    if request.status is not None:
        try:
            webhook.status = WebhookStatus(request.status)
        except ValueError:
            raise ValidationError(
                message="Invalid status",
                errors=[{"field": "status", "message": f"Invalid status: {request.status}"}]
            )

    db.commit()
    db.refresh(webhook)

    logger.info(
        "webhook_updated",
        webhook_id=str(webhook.id),
        user_id=str(current_user.id),
    )

    return _webhook_to_response(webhook)


@router.delete(
    "/{webhook_id}",
    response_model=MessageResponse,
    summary="Delete webhook",
    description="Delete a webhook.",
)
async def delete_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """Delete a webhook."""
    try:
        webhook_uuid = uuid.UUID(webhook_id)
    except ValueError:
        raise NotFoundError("Webhook", webhook_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Webhook", webhook_id)

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_uuid,
        Webhook.organization_id == org_id,
    ).first()

    if not webhook:
        raise NotFoundError("Webhook", webhook_id)

    db.delete(webhook)
    db.commit()

    logger.info(
        "webhook_deleted",
        webhook_id=webhook_id,
        user_id=str(current_user.id),
    )

    return MessageResponse(message="Webhook deleted successfully")


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookDeliveryResponse,
    summary="Test webhook",
    description="Send a test event to verify webhook configuration.",
)
async def test_webhook(
    webhook_id: str,
    request: TestWebhookRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WebhookDeliveryResponse:
    """Test a webhook with a ping event."""
    try:
        webhook_uuid = uuid.UUID(webhook_id)
    except ValueError:
        raise NotFoundError("Webhook", webhook_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Webhook", webhook_id)

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_uuid,
        Webhook.organization_id == org_id,
    ).first()

    if not webhook:
        raise NotFoundError("Webhook", webhook_id)

    # Create test delivery
    from backend.services.webhook_service import WebhookService

    event_type = request.event_type if request else "test.ping"
    event_id = f"test_{uuid.uuid4().hex[:8]}"
    payload = {
        "event": event_type,
        "event_id": event_id,
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "message": "This is a test webhook delivery",
            "triggered_by": str(current_user.id),
        },
    }

    service = WebhookService(db)
    delivery = await service.deliver_webhook(webhook, event_type, event_id, payload)

    return _delivery_to_response(delivery)


@router.post(
    "/{webhook_id}/rotate-secret",
    response_model=WebhookResponse,
    summary="Rotate webhook secret",
    description="Generate a new secret for the webhook.",
)
async def rotate_webhook_secret(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WebhookResponse:
    """Rotate the webhook secret."""
    try:
        webhook_uuid = uuid.UUID(webhook_id)
    except ValueError:
        raise NotFoundError("Webhook", webhook_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Webhook", webhook_id)

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_uuid,
        Webhook.organization_id == org_id,
    ).first()

    if not webhook:
        raise NotFoundError("Webhook", webhook_id)

    webhook.secret = Webhook.generate_secret()
    db.commit()
    db.refresh(webhook)

    logger.info(
        "webhook_secret_rotated",
        webhook_id=webhook_id,
        user_id=str(current_user.id),
    )

    return _webhook_to_response(webhook)


@router.get(
    "/{webhook_id}/deliveries",
    response_model=WebhookDeliveryListResponse,
    summary="List webhook deliveries",
    description="Get delivery history for a webhook.",
)
async def list_webhook_deliveries(
    webhook_id: str,
    page: int = 1,
    page_size: int = 20,
    success_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WebhookDeliveryListResponse:
    """List webhook delivery history."""
    try:
        webhook_uuid = uuid.UUID(webhook_id)
    except ValueError:
        raise NotFoundError("Webhook", webhook_id)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Webhook", webhook_id)

    # Verify webhook belongs to org
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_uuid,
        Webhook.organization_id == org_id,
    ).first()

    if not webhook:
        raise NotFoundError("Webhook", webhook_id)

    # Query deliveries
    query = db.query(WebhookDelivery).filter(
        WebhookDelivery.webhook_id == webhook_uuid,
    )

    if success_only:
        query = query.filter(WebhookDelivery.success == True)

    total = query.count()
    offset = (page - 1) * page_size
    deliveries = query.order_by(
        WebhookDelivery.created_at.desc()
    ).offset(offset).limit(page_size).all()

    return WebhookDeliveryListResponse(
        deliveries=[_delivery_to_response(d) for d in deliveries],
        total=total,
    )
