"""
Notification system models.

Provides models for in-app, email, and push notifications.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.types import UUID


class NotificationType(enum.Enum):
    """Types of notifications."""
    # Document notifications
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_FAILED = "document_failed"
    DOCUMENT_SHARED = "document_shared"

    # Batch notifications
    BATCH_STARTED = "batch_started"
    BATCH_COMPLETED = "batch_completed"
    BATCH_FAILED = "batch_failed"

    # Template notifications
    TEMPLATE_SHARED = "template_shared"
    TEMPLATE_FORKED = "template_forked"
    TEMPLATE_REVIEW = "template_review"
    TEMPLATE_VERSION = "template_version"

    # Organization notifications
    ORG_INVITATION = "org_invitation"
    ORG_MEMBER_JOINED = "org_member_joined"
    ORG_MEMBER_LEFT = "org_member_left"
    ORG_ROLE_CHANGED = "org_role_changed"

    # Integration notifications
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_DISCONNECTED = "integration_disconnected"
    INTEGRATION_SYNC_COMPLETE = "integration_sync_complete"
    INTEGRATION_SYNC_FAILED = "integration_sync_failed"

    # Quota notifications
    QUOTA_WARNING = "quota_warning"
    QUOTA_EXCEEDED = "quota_exceeded"
    QUOTA_RESET = "quota_reset"

    # Billing notifications
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"

    # Security notifications
    LOGIN_NEW_DEVICE = "login_new_device"
    PASSWORD_CHANGED = "password_changed"
    API_KEY_CREATED = "api_key_created"
    API_KEY_EXPIRING = "api_key_expiring"

    # System notifications
    SYSTEM_MAINTENANCE = "system_maintenance"
    SYSTEM_UPDATE = "system_update"
    FEATURE_ANNOUNCEMENT = "feature_announcement"

    # Webhook notifications
    WEBHOOK_DELIVERY_FAILED = "webhook_delivery_failed"

    # Comment/Collaboration
    COMMENT_ADDED = "comment_added"
    MENTION = "mention"

    # Export notifications
    EXPORT_READY = "export_ready"
    EXPORT_FAILED = "export_failed"


class NotificationPriority(enum.Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(enum.Enum):
    """Delivery channels for notifications."""
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"


class DeliveryStatus(enum.Enum):
    """Status of notification delivery."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"


class Notification(Base):
    """
    Core notification model.

    Stores notification content and metadata.
    """
    __tablename__ = "notifications"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)

    # Recipient
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(
        UUID(),
        ForeignKey("organizations.id", ondelete="SET NULL"),
    )

    # Notification type and priority
    type = Column(Enum(NotificationType), nullable=False)
    priority = Column(
        Enum(NotificationPriority),
        default=NotificationPriority.NORMAL,
    )

    # Content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    # Rich content (optional)
    html_content = Column(Text)  # For email

    # Structured data
    data = Column(JSON, default=dict)  # Additional context

    # Action URLs
    action_url = Column(String(500))  # Primary action
    action_label = Column(String(100))
    secondary_actions = Column(JSON, default=list)  # [{url, label}]

    # Related entities
    related_entity_type = Column(String(50))  # document, template, etc.
    related_entity_id = Column(UUID())

    # Sender (for social notifications)
    sender_id = Column(UUID(), ForeignKey("users.id", ondelete="SET NULL"))

    # Grouping
    group_key = Column(String(100))  # For grouping similar notifications
    group_count = Column(Integer, default=1)  # Count of grouped items

    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime)

    # Scheduling
    scheduled_for = Column(DateTime)  # For delayed notifications
    expires_at = Column(DateTime)  # Auto-dismiss after

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("ix_notifications_user", "user_id"),
        Index("ix_notifications_user_unread", "user_id", "is_read"),
        Index("ix_notifications_type", "type"),
        Index("ix_notifications_created", "created_at"),
        Index("ix_notifications_group", "group_key"),
    )

    # Relationships
    deliveries = relationship(
        "NotificationDelivery",
        back_populates="notification",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.type.value})>"


class NotificationDelivery(Base):
    """
    Tracks delivery of notifications through different channels.
    """
    __tablename__ = "notification_deliveries"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    notification_id = Column(
        UUID(),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Channel
    channel = Column(Enum(NotificationChannel), nullable=False)

    # Status
    status = Column(
        Enum(DeliveryStatus),
        default=DeliveryStatus.PENDING,
    )

    # Delivery details
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)
    failed_at = Column(DateTime)

    # Error tracking
    error_message = Column(Text)
    error_code = Column(String(50))
    retry_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime)

    # External IDs (for tracking)
    external_id = Column(String(255))  # Email message ID, push notification ID

    # Metadata
    metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    notification = relationship("Notification", back_populates="deliveries")

    __table_args__ = (
        Index("ix_delivery_notification", "notification_id"),
        Index("ix_delivery_status", "status"),
        Index("ix_delivery_channel", "channel"),
    )


class NotificationPreference(Base):
    """
    User preferences for notification delivery.
    """
    __tablename__ = "notification_preferences"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Notification type
    notification_type = Column(Enum(NotificationType), nullable=False)

    # Channel preferences
    in_app_enabled = Column(Boolean, default=True)
    email_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=False)
    slack_enabled = Column(Boolean, default=False)

    # Digest settings
    digest_enabled = Column(Boolean, default=False)
    digest_frequency = Column(String(20))  # immediate, daily, weekly

    # Quiet hours
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String(5))  # HH:MM format
    quiet_hours_end = Column(String(5))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "notification_type", name="uq_user_notification_pref"),
        Index("ix_notification_prefs_user", "user_id"),
    )


class NotificationDigest(Base):
    """
    Aggregated notifications for digest delivery.
    """
    __tablename__ = "notification_digests"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Digest period
    frequency = Column(String(20), nullable=False)  # daily, weekly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Content
    notification_count = Column(Integer, default=0)
    notification_ids = Column(JSON, default=list)  # List of notification IDs
    summary = Column(JSON, default=dict)  # Summarized by type

    # Status
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_digest_user", "user_id"),
        Index("ix_digest_period", "period_start", "period_end"),
    )


class PushSubscription(Base):
    """
    Web push notification subscriptions.
    """
    __tablename__ = "push_subscriptions"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Subscription data (Web Push)
    endpoint = Column(Text, nullable=False)
    p256dh_key = Column(Text, nullable=False)  # Public key
    auth_key = Column(Text, nullable=False)  # Auth secret

    # Device info
    device_type = Column(String(50))  # browser, mobile, desktop
    browser = Column(String(50))
    os = Column(String(50))
    user_agent = Column(Text)

    # Status
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime)
    failed_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_push_sub_user", "user_id"),
        Index("ix_push_sub_active", "is_active"),
    )


class NotificationTemplate(Base):
    """
    Templates for notification content.
    """
    __tablename__ = "notification_templates"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)

    # Template identification
    name = Column(String(100), nullable=False, unique=True)
    notification_type = Column(Enum(NotificationType), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)

    # Content templates (supports Jinja2)
    subject_template = Column(String(255))  # For email
    title_template = Column(String(255), nullable=False)
    body_template = Column(Text, nullable=False)
    html_template = Column(Text)  # For email

    # Default values
    default_priority = Column(
        Enum(NotificationPriority),
        default=NotificationPriority.NORMAL,
    )
    default_action_label = Column(String(100))

    # Localization
    language = Column(String(10), default="en")

    # Status
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("notification_type", "channel", "language", name="uq_template_type_channel_lang"),
    )


class SlackIntegration(Base):
    """
    Slack workspace integration for notifications.
    """
    __tablename__ = "slack_integrations"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Slack workspace
    workspace_id = Column(String(50), nullable=False)
    workspace_name = Column(String(255))

    # OAuth tokens
    access_token = Column(Text, nullable=False)  # Encrypted
    bot_user_id = Column(String(50))

    # Default channel
    default_channel_id = Column(String(50))
    default_channel_name = Column(String(100))

    # Scopes
    scopes = Column(JSON, default=list)

    # Status
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", name="uq_org_slack_workspace"),
    )


class UserSlackMapping(Base):
    """
    Maps users to Slack user IDs.
    """
    __tablename__ = "user_slack_mappings"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    slack_integration_id = Column(
        UUID(),
        ForeignKey("slack_integrations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Slack user info
    slack_user_id = Column(String(50), nullable=False)
    slack_username = Column(String(100))
    slack_email = Column(String(255))

    # Preferences
    dm_enabled = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "slack_integration_id", name="uq_user_slack_integration"),
    )
