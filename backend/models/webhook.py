"""
Webhook models for event notifications.

Enables organizations to receive real-time notifications for system events.
"""
import secrets
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, String, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class WebhookEvent(str, Enum):
    """Webhook event types."""
    # Document events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_FAILED = "document.failed"
    DOCUMENT_DELETED = "document.deleted"

    # Job events
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"

    # Export events
    EXPORT_READY = "export.ready"
    EXPORT_FAILED = "export.failed"

    # Integration events
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_DISCONNECTED = "integration.disconnected"
    INTEGRATION_SYNC_COMPLETED = "integration.sync_completed"
    INTEGRATION_SYNC_FAILED = "integration.sync_failed"

    # User events (for admin webhooks)
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"

    # Organization events
    ORGANIZATION_UPDATED = "organization.updated"
    MEMBER_ADDED = "organization.member_added"
    MEMBER_REMOVED = "organization.member_removed"


class WebhookStatus(str, Enum):
    """Webhook endpoint status."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    FAILED = "failed"  # Too many failures


class Webhook(Base):
    """Webhook endpoint configuration."""

    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Endpoint configuration
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(2048), nullable=False)  # Webhook delivery URL

    # Authentication
    secret = Column(String(64), nullable=False)  # For HMAC signature verification

    # Event subscriptions
    events = Column(JSON, nullable=False, default=list)  # Store as JSON array for SQLite compatibility

    # Status and health
    status = Column(SQLEnum(WebhookStatus), default=WebhookStatus.ACTIVE, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_reason = Column(Text, nullable=True)

    # Retry settings
    max_retries = Column(Integer, default=3, nullable=False)
    retry_delay_seconds = Column(Integer, default=60, nullable=False)

    # Headers to include
    custom_headers = Column(JSON, nullable=True)

    # Ownership
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", backref="webhooks")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self) -> str:
        return f"<Webhook {self.name} -> {self.url}>"

    @classmethod
    def generate_secret(cls) -> str:
        """Generate a secure webhook secret."""
        return secrets.token_hex(32)

    def is_subscribed_to(self, event: str) -> bool:
        """Check if webhook is subscribed to an event."""
        if not self.events:
            return False
        # Support wildcard subscriptions
        for subscribed in self.events:
            if subscribed == "*":
                return True
            if subscribed == event:
                return True
            # Check prefix matching (e.g., "document.*" matches "document.uploaded")
            if subscribed.endswith(".*"):
                prefix = subscribed[:-2]
                if event.startswith(prefix + "."):
                    return True
        return False

    def record_success(self) -> None:
        """Record a successful delivery."""
        self.last_triggered_at = datetime.utcnow()
        self.last_success_at = datetime.utcnow()
        self.failure_count = 0
        if self.status == WebhookStatus.FAILED:
            self.status = WebhookStatus.ACTIVE

    def record_failure(self, reason: str) -> None:
        """Record a failed delivery."""
        self.last_triggered_at = datetime.utcnow()
        self.last_failure_at = datetime.utcnow()
        self.last_failure_reason = reason
        self.failure_count += 1

        # Disable after too many failures
        if self.failure_count >= 10:
            self.status = WebhookStatus.FAILED


class WebhookDelivery(Base):
    """Log of webhook delivery attempts."""

    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Reference to webhook
    webhook_id = Column(UUID(as_uuid=True), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)

    # Event details
    event_type = Column(String(100), nullable=False)
    event_id = Column(String(100), nullable=False)  # Unique event identifier
    payload = Column(JSON, nullable=False)

    # Delivery status
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=True)

    # Success/failure
    success = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)

    # Retry tracking
    attempt_number = Column(Integer, default=1, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    webhook = relationship("Webhook", backref="deliveries")

    def __repr__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"<WebhookDelivery {status} {self.event_type}>"
