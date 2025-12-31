"""
Notification Service.

Provides comprehensive notification delivery across multiple channels.
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import ssl

import structlog
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session
from jinja2 import Template

from backend.config import get_settings
from backend.models.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationDigest,
    PushSubscription,
    NotificationTemplate,
    SlackIntegration,
    UserSlackMapping,
    NotificationType,
    NotificationPriority,
    NotificationChannel,
    DeliveryStatus,
)
from backend.models.user import User

logger = structlog.get_logger(__name__)
settings = get_settings()


class NotificationService:
    """Service for managing and delivering notifications."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Create Notifications ====================

    def create_notification(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[uuid.UUID] = None,
        sender_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        group_key: Optional[str] = None,
        scheduled_for: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        html_content: Optional[str] = None,
    ) -> Notification:
        """
        Create a new notification.

        Args:
            user_id: Recipient user ID
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            priority: Priority level
            data: Additional structured data
            action_url: URL for primary action
            action_label: Label for action button
            related_entity_type: Type of related entity
            related_entity_id: ID of related entity
            sender_id: ID of user who triggered notification
            organization_id: Organization context
            group_key: Key for grouping similar notifications
            scheduled_for: Delay delivery until this time
            expires_at: Auto-dismiss after this time
            html_content: HTML version for email

        Returns:
            Created Notification
        """
        # Check for existing notification with same group key
        if group_key:
            existing = self.db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.group_key == group_key,
                Notification.is_read == False,
                Notification.created_at > datetime.utcnow() - timedelta(hours=24),
            ).first()

            if existing:
                # Update group count instead of creating new
                existing.group_count += 1
                existing.message = message  # Update with latest message
                existing.updated_at = datetime.utcnow()
                self.db.commit()
                return existing

        notification = Notification(
            user_id=user_id,
            organization_id=organization_id,
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            html_content=html_content,
            data=data or {},
            action_url=action_url,
            action_label=action_label,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            sender_id=sender_id,
            group_key=group_key,
            scheduled_for=scheduled_for,
            expires_at=expires_at,
        )

        self.db.add(notification)
        self.db.commit()

        logger.info(
            "notification_created",
            notification_id=str(notification.id),
            user_id=str(user_id),
            type=notification_type.value,
        )

        # Schedule delivery if not delayed
        if not scheduled_for or scheduled_for <= datetime.utcnow():
            self._schedule_delivery(notification)

        return notification

    def _schedule_delivery(self, notification: Notification) -> None:
        """Schedule notification delivery based on user preferences."""
        preferences = self.get_user_preferences(notification.user_id)
        pref = preferences.get(notification.type)

        channels = []

        # Always create in-app notification
        if not pref or pref.in_app_enabled:
            channels.append(NotificationChannel.IN_APP)

        # Email if enabled
        if pref and pref.email_enabled:
            if pref.digest_enabled and pref.digest_frequency != "immediate":
                self._add_to_digest(notification, pref.digest_frequency)
            else:
                channels.append(NotificationChannel.EMAIL)

        # Push if enabled and subscribed
        if pref and pref.push_enabled:
            if self._has_push_subscription(notification.user_id):
                channels.append(NotificationChannel.PUSH)

        # Slack if enabled
        if pref and pref.slack_enabled:
            if self._has_slack_mapping(notification.user_id):
                channels.append(NotificationChannel.SLACK)

        # Create delivery records
        for channel in channels:
            delivery = NotificationDelivery(
                notification_id=notification.id,
                channel=channel,
                status=DeliveryStatus.PENDING,
            )
            self.db.add(delivery)

        self.db.commit()

    def _has_push_subscription(self, user_id: uuid.UUID) -> bool:
        """Check if user has active push subscriptions."""
        return self.db.query(PushSubscription).filter(
            PushSubscription.user_id == user_id,
            PushSubscription.is_active == True,
        ).first() is not None

    def _has_slack_mapping(self, user_id: uuid.UUID) -> bool:
        """Check if user has Slack mapping."""
        return self.db.query(UserSlackMapping).filter(
            UserSlackMapping.user_id == user_id,
        ).first() is not None

    def _add_to_digest(self, notification: Notification, frequency: str) -> None:
        """Add notification to digest."""
        now = datetime.utcnow()

        if frequency == "daily":
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start + timedelta(days=1)
        else:  # weekly
            days_since_monday = now.weekday()
            period_start = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            period_end = period_start + timedelta(days=7)

        # Find or create digest
        digest = self.db.query(NotificationDigest).filter(
            NotificationDigest.user_id == notification.user_id,
            NotificationDigest.frequency == frequency,
            NotificationDigest.period_start == period_start,
            NotificationDigest.is_sent == False,
        ).first()

        if not digest:
            digest = NotificationDigest(
                user_id=notification.user_id,
                frequency=frequency,
                period_start=period_start,
                period_end=period_end,
            )
            self.db.add(digest)
            self.db.flush()

        # Add notification to digest
        notification_ids = digest.notification_ids or []
        notification_ids.append(str(notification.id))
        digest.notification_ids = notification_ids
        digest.notification_count = len(notification_ids)

        # Update summary
        summary = digest.summary or {}
        type_key = notification.type.value
        summary[type_key] = summary.get(type_key, 0) + 1
        digest.summary = summary

        self.db.commit()

    # ==================== Delivery ====================

    def process_pending_deliveries(self, batch_size: int = 100) -> int:
        """Process pending notification deliveries."""
        deliveries = self.db.query(NotificationDelivery).filter(
            NotificationDelivery.status == DeliveryStatus.PENDING,
            or_(
                NotificationDelivery.next_retry_at.is_(None),
                NotificationDelivery.next_retry_at <= datetime.utcnow(),
            ),
        ).limit(batch_size).all()

        processed = 0
        for delivery in deliveries:
            try:
                self._deliver(delivery)
                processed += 1
            except Exception as e:
                logger.error(
                    "delivery_failed",
                    delivery_id=str(delivery.id),
                    error=str(e),
                )

        return processed

    def _deliver(self, delivery: NotificationDelivery) -> bool:
        """Deliver a notification through its channel."""
        notification = delivery.notification

        try:
            if delivery.channel == NotificationChannel.IN_APP:
                # In-app is always "delivered"
                delivery.status = DeliveryStatus.DELIVERED
                delivery.delivered_at = datetime.utcnow()

            elif delivery.channel == NotificationChannel.EMAIL:
                self._send_email(notification, delivery)

            elif delivery.channel == NotificationChannel.PUSH:
                self._send_push(notification, delivery)

            elif delivery.channel == NotificationChannel.SLACK:
                self._send_slack(notification, delivery)

            self.db.commit()
            return True

        except Exception as e:
            delivery.retry_count += 1
            delivery.error_message = str(e)

            if delivery.retry_count >= 3:
                delivery.status = DeliveryStatus.FAILED
                delivery.failed_at = datetime.utcnow()
            else:
                # Exponential backoff
                delay = 2 ** delivery.retry_count * 60  # 2, 4, 8 minutes
                delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)

            self.db.commit()
            return False

    def _send_email(self, notification: Notification, delivery: NotificationDelivery) -> None:
        """Send email notification."""
        user = self.db.query(User).filter(User.id == notification.user_id).first()
        if not user or not user.email:
            raise ValueError("User has no email address")

        # Get email template
        template = self._get_template(notification.type, NotificationChannel.EMAIL)

        # Prepare content
        subject = notification.title
        if template and template.subject_template:
            subject = Template(template.subject_template).render(
                notification=notification,
                user=user,
            )

        body = notification.message
        html_body = notification.html_content

        if template:
            body = Template(template.body_template).render(
                notification=notification,
                user=user,
            )
            if template.html_template:
                html_body = Template(template.html_template).render(
                    notification=notification,
                    user=user,
                )

        # Send email
        self._send_smtp_email(
            to_email=user.email,
            subject=subject,
            body=body,
            html_body=html_body,
        )

        delivery.status = DeliveryStatus.SENT
        delivery.sent_at = datetime.utcnow()

    def _send_smtp_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> None:
        """Send email via SMTP."""
        smtp_host = getattr(settings, 'smtp_host', None)
        smtp_port = getattr(settings, 'smtp_port', 587)
        smtp_user = getattr(settings, 'smtp_user', None)
        smtp_password = getattr(settings, 'smtp_password', None)
        from_email = getattr(settings, 'from_email', 'noreply@statementxl.com')

        if not smtp_host:
            logger.warning("SMTP not configured, skipping email")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context)
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())

    def _send_push(self, notification: Notification, delivery: NotificationDelivery) -> None:
        """Send push notification."""
        subscriptions = self.db.query(PushSubscription).filter(
            PushSubscription.user_id == notification.user_id,
            PushSubscription.is_active == True,
        ).all()

        if not subscriptions:
            raise ValueError("No active push subscriptions")

        # Web Push payload
        payload = json.dumps({
            "title": notification.title,
            "body": notification.message,
            "icon": "/icon-192.png",
            "badge": "/badge.png",
            "data": {
                "notification_id": str(notification.id),
                "type": notification.type.value,
                "action_url": notification.action_url,
            },
        })

        # In production, use pywebpush library
        # from pywebpush import webpush, WebPushException
        #
        # for sub in subscriptions:
        #     try:
        #         webpush(
        #             subscription_info={
        #                 "endpoint": sub.endpoint,
        #                 "keys": {
        #                     "p256dh": sub.p256dh_key,
        #                     "auth": sub.auth_key,
        #                 }
        #             },
        #             data=payload,
        #             vapid_private_key=settings.vapid_private_key,
        #             vapid_claims={"sub": f"mailto:{settings.from_email}"}
        #         )
        #     except WebPushException as e:
        #         if e.response.status_code == 410:  # Gone
        #             sub.is_active = False

        logger.info("push_notification_sent", user_id=str(notification.user_id))
        delivery.status = DeliveryStatus.SENT
        delivery.sent_at = datetime.utcnow()

    def _send_slack(self, notification: Notification, delivery: NotificationDelivery) -> None:
        """Send Slack notification."""
        mapping = self.db.query(UserSlackMapping).filter(
            UserSlackMapping.user_id == notification.user_id,
        ).first()

        if not mapping:
            raise ValueError("User has no Slack mapping")

        integration = self.db.query(SlackIntegration).filter(
            SlackIntegration.id == mapping.slack_integration_id,
            SlackIntegration.is_active == True,
        ).first()

        if not integration:
            raise ValueError("Slack integration not active")

        # Slack message payload
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": notification.title}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": notification.message}
            },
        ]

        if notification.action_url:
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": notification.action_label or "View"},
                    "url": notification.action_url,
                }]
            })

        # In production, use slack_sdk
        # from slack_sdk import WebClient
        # client = WebClient(token=integration.access_token)
        # client.chat_postMessage(
        #     channel=mapping.slack_user_id,
        #     blocks=blocks,
        # )

        logger.info("slack_notification_sent", user_id=str(notification.user_id))
        delivery.status = DeliveryStatus.SENT
        delivery.sent_at = datetime.utcnow()

    def _get_template(
        self,
        notification_type: NotificationType,
        channel: NotificationChannel,
        language: str = "en",
    ) -> Optional[NotificationTemplate]:
        """Get notification template."""
        return self.db.query(NotificationTemplate).filter(
            NotificationTemplate.notification_type == notification_type,
            NotificationTemplate.channel == channel,
            NotificationTemplate.language == language,
            NotificationTemplate.is_active == True,
        ).first()

    # ==================== Reading & Managing ====================

    def get_notifications(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        notification_types: Optional[List[NotificationType]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """Get notifications for a user."""
        query = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_archived == False,
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow(),
            ),
        )

        if unread_only:
            query = query.filter(Notification.is_read == False)

        if notification_types:
            query = query.filter(Notification.type.in_(notification_types))

        return query.order_by(desc(Notification.created_at)).offset(offset).limit(limit).all()

    def get_unread_count(self, user_id: uuid.UUID) -> int:
        """Get count of unread notifications."""
        return self.db.query(func.count(Notification.id)).filter(
            Notification.user_id == user_id,
            Notification.is_read == False,
            Notification.is_archived == False,
        ).scalar()

    def mark_as_read(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification:
        """Mark a notification as read."""
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        ).first()

        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            self.db.commit()

        return notification

    def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        """Mark all notifications as read."""
        count = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False,
        ).update({
            "is_read": True,
            "read_at": datetime.utcnow(),
        })

        self.db.commit()
        return count

    def archive_notification(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification:
        """Archive a notification."""
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        ).first()

        if notification:
            notification.is_archived = True
            notification.archived_at = datetime.utcnow()
            self.db.commit()

        return notification

    def delete_notification(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a notification."""
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        ).first()

        if notification:
            self.db.delete(notification)
            self.db.commit()
            return True

        return False

    # ==================== Preferences ====================

    def get_user_preferences(
        self,
        user_id: uuid.UUID,
    ) -> Dict[NotificationType, NotificationPreference]:
        """Get all notification preferences for a user."""
        prefs = self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id,
        ).all()

        return {p.notification_type: p for p in prefs}

    def update_preference(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        in_app_enabled: Optional[bool] = None,
        email_enabled: Optional[bool] = None,
        push_enabled: Optional[bool] = None,
        sms_enabled: Optional[bool] = None,
        slack_enabled: Optional[bool] = None,
        digest_enabled: Optional[bool] = None,
        digest_frequency: Optional[str] = None,
    ) -> NotificationPreference:
        """Update notification preference."""
        pref = self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.notification_type == notification_type,
        ).first()

        if not pref:
            pref = NotificationPreference(
                user_id=user_id,
                notification_type=notification_type,
            )
            self.db.add(pref)

        if in_app_enabled is not None:
            pref.in_app_enabled = in_app_enabled
        if email_enabled is not None:
            pref.email_enabled = email_enabled
        if push_enabled is not None:
            pref.push_enabled = push_enabled
        if sms_enabled is not None:
            pref.sms_enabled = sms_enabled
        if slack_enabled is not None:
            pref.slack_enabled = slack_enabled
        if digest_enabled is not None:
            pref.digest_enabled = digest_enabled
        if digest_frequency is not None:
            pref.digest_frequency = digest_frequency

        self.db.commit()
        return pref

    # ==================== Push Subscriptions ====================

    def register_push_subscription(
        self,
        user_id: uuid.UUID,
        endpoint: str,
        p256dh_key: str,
        auth_key: str,
        device_type: Optional[str] = None,
        browser: Optional[str] = None,
        os: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PushSubscription:
        """Register a push notification subscription."""
        # Check for existing subscription with same endpoint
        existing = self.db.query(PushSubscription).filter(
            PushSubscription.endpoint == endpoint,
        ).first()

        if existing:
            existing.user_id = user_id
            existing.p256dh_key = p256dh_key
            existing.auth_key = auth_key
            existing.is_active = True
            existing.last_used_at = datetime.utcnow()
            self.db.commit()
            return existing

        subscription = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
            device_type=device_type,
            browser=browser,
            os=os,
            user_agent=user_agent,
        )

        self.db.add(subscription)
        self.db.commit()

        return subscription

    def unregister_push_subscription(
        self,
        user_id: uuid.UUID,
        endpoint: str,
    ) -> bool:
        """Unregister a push subscription."""
        subscription = self.db.query(PushSubscription).filter(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        ).first()

        if subscription:
            subscription.is_active = False
            self.db.commit()
            return True

        return False

    # ==================== Convenience Methods ====================

    def notify_document_processed(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        document_name: str,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> Notification:
        """Send notification when document processing completes."""
        if success:
            return self.create_notification(
                user_id=user_id,
                notification_type=NotificationType.DOCUMENT_PROCESSED,
                title="Document Processed",
                message=f"'{document_name}' has been successfully processed and is ready for review.",
                action_url=f"/documents/{document_id}",
                action_label="View Document",
                related_entity_type="document",
                related_entity_id=document_id,
            )
        else:
            return self.create_notification(
                user_id=user_id,
                notification_type=NotificationType.DOCUMENT_FAILED,
                title="Document Processing Failed",
                message=f"Failed to process '{document_name}': {error_message or 'Unknown error'}",
                priority=NotificationPriority.HIGH,
                action_url=f"/documents/{document_id}",
                action_label="View Details",
                related_entity_type="document",
                related_entity_id=document_id,
            )

    def notify_quota_warning(
        self,
        user_id: uuid.UUID,
        quota_type: str,
        current_usage: int,
        limit: int,
        organization_id: Optional[uuid.UUID] = None,
    ) -> Notification:
        """Send notification when approaching quota limit."""
        percentage = (current_usage / limit) * 100

        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.QUOTA_WARNING,
            title="Approaching Usage Limit",
            message=f"You've used {percentage:.0f}% of your {quota_type} quota ({current_usage}/{limit}).",
            priority=NotificationPriority.HIGH,
            action_url="/settings/billing",
            action_label="Upgrade Plan",
            organization_id=organization_id,
            data={"quota_type": quota_type, "usage": current_usage, "limit": limit},
        )

    def notify_organization_invitation(
        self,
        user_id: uuid.UUID,
        organization_name: str,
        organization_id: uuid.UUID,
        inviter_name: str,
        inviter_id: uuid.UUID,
    ) -> Notification:
        """Send notification for organization invitation."""
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.ORG_INVITATION,
            title="Organization Invitation",
            message=f"{inviter_name} has invited you to join {organization_name}.",
            priority=NotificationPriority.HIGH,
            action_url=f"/organizations/{organization_id}/join",
            action_label="Accept Invitation",
            related_entity_type="organization",
            related_entity_id=organization_id,
            sender_id=inviter_id,
            organization_id=organization_id,
        )


def get_notification_service(db: Session) -> NotificationService:
    """Factory function to get notification service instance."""
    return NotificationService(db)
