"""
Webhook delivery service.

Handles sending webhook events to registered endpoints with retry logic.
"""
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import httpx
import structlog
from sqlalchemy.orm import Session

from backend.models.webhook import Webhook, WebhookDelivery, WebhookEvent, WebhookStatus

logger = structlog.get_logger(__name__)


class WebhookService:
    """Service for delivering webhooks to registered endpoints."""

    def __init__(self, db: Session):
        self.db = db
        self.timeout = 30.0  # Request timeout in seconds

    def generate_signature(self, secret: str, payload: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.

        The signature is sent in the X-Webhook-Signature header.
        Receivers should verify this signature to ensure the request
        is authentic.
        """
        return hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def deliver_webhook(
        self,
        webhook: Webhook,
        event_type: str,
        event_id: str,
        payload: Dict[str, Any],
    ) -> WebhookDelivery:
        """
        Deliver a single webhook event.

        Args:
            webhook: The webhook endpoint to deliver to
            event_type: Type of event (e.g., "document.uploaded")
            event_id: Unique identifier for this event
            payload: The event data

        Returns:
            WebhookDelivery record with delivery result
        """
        # Create delivery record
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=event_type,
            event_id=event_id,
            payload=payload,
            attempt_number=1,
        )
        self.db.add(delivery)
        self.db.commit()

        # Prepare request
        payload_json = json.dumps(payload, default=str)
        signature = self.generate_signature(webhook.secret, payload_json)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Webhook-Event-ID": event_id,
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Timestamp": str(int(time.time())),
            "User-Agent": "StatementXL-Webhooks/2.0",
        }

        # Add custom headers
        if webhook.custom_headers:
            headers.update(webhook.custom_headers)

        # Attempt delivery
        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook.url,
                    content=payload_json,
                    headers=headers,
                    timeout=self.timeout,
                )

            response_time_ms = int((time.time() - start_time) * 1000)

            # Update delivery record
            delivery.status_code = response.status_code
            delivery.response_time_ms = response_time_ms
            delivery.delivered_at = datetime.utcnow()

            # Consider 2xx status codes as success
            if 200 <= response.status_code < 300:
                delivery.success = True
                webhook.record_success()
                logger.info(
                    "webhook_delivered",
                    webhook_id=str(webhook.id),
                    event_type=event_type,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                )
            else:
                delivery.success = False
                delivery.error_message = f"HTTP {response.status_code}"
                delivery.response_body = response.text[:1000]  # Truncate
                webhook.record_failure(f"HTTP {response.status_code}")
                logger.warning(
                    "webhook_delivery_failed",
                    webhook_id=str(webhook.id),
                    event_type=event_type,
                    status_code=response.status_code,
                )

        except httpx.TimeoutException:
            response_time_ms = int((time.time() - start_time) * 1000)
            delivery.success = False
            delivery.error_message = "Request timeout"
            delivery.response_time_ms = response_time_ms
            webhook.record_failure("Request timeout")
            logger.warning(
                "webhook_timeout",
                webhook_id=str(webhook.id),
                event_type=event_type,
            )

        except httpx.RequestError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            delivery.success = False
            delivery.error_message = str(e)
            delivery.response_time_ms = response_time_ms
            webhook.record_failure(str(e))
            logger.error(
                "webhook_request_error",
                webhook_id=str(webhook.id),
                event_type=event_type,
                error=str(e),
            )

        except Exception as e:
            delivery.success = False
            delivery.error_message = f"Unexpected error: {str(e)}"
            webhook.record_failure(str(e))
            logger.error(
                "webhook_unexpected_error",
                webhook_id=str(webhook.id),
                event_type=event_type,
                error=str(e),
            )

        self.db.commit()
        return delivery

    async def trigger_event(
        self,
        organization_id: uuid.UUID,
        event_type: str,
        data: Dict[str, Any],
    ) -> List[WebhookDelivery]:
        """
        Trigger a webhook event for an organization.

        Finds all active webhooks subscribed to the event and delivers to them.

        Args:
            organization_id: The organization to send webhooks for
            event_type: Type of event to trigger
            data: Event data payload

        Returns:
            List of WebhookDelivery records
        """
        # Find subscribed webhooks
        webhooks = self.db.query(Webhook).filter(
            Webhook.organization_id == organization_id,
            Webhook.status == WebhookStatus.ACTIVE,
        ).all()

        # Filter to those subscribed to this event
        subscribed = [w for w in webhooks if w.is_subscribed_to(event_type)]

        if not subscribed:
            return []

        # Generate unique event ID
        event_id = str(uuid.uuid4())

        # Build payload
        payload = {
            "event": event_type,
            "event_id": event_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }

        # Deliver to all subscribed webhooks
        deliveries = []
        for webhook in subscribed:
            try:
                delivery = await self.deliver_webhook(
                    webhook, event_type, event_id, payload
                )
                deliveries.append(delivery)
            except Exception as e:
                logger.error(
                    "webhook_trigger_error",
                    webhook_id=str(webhook.id),
                    event_type=event_type,
                    error=str(e),
                )

        return deliveries

    async def retry_failed_deliveries(self) -> int:
        """
        Retry failed webhook deliveries that are due for retry.

        Returns:
            Number of deliveries retried
        """
        now = datetime.utcnow()

        # Find deliveries that need retry
        deliveries = self.db.query(WebhookDelivery).join(Webhook).filter(
            WebhookDelivery.success == False,
            WebhookDelivery.next_retry_at <= now,
            WebhookDelivery.attempt_number < Webhook.max_retries,
            Webhook.status == WebhookStatus.ACTIVE,
        ).all()

        retried = 0
        for delivery in deliveries:
            webhook = delivery.webhook

            # Create new delivery for retry
            new_delivery = WebhookDelivery(
                webhook_id=webhook.id,
                event_type=delivery.event_type,
                event_id=delivery.event_id,
                payload=delivery.payload,
                attempt_number=delivery.attempt_number + 1,
            )
            self.db.add(new_delivery)

            # Clear retry time on old delivery
            delivery.next_retry_at = None

            try:
                result = await self.deliver_webhook(
                    webhook,
                    delivery.event_type,
                    delivery.event_id,
                    delivery.payload,
                )

                if not result.success and result.attempt_number < webhook.max_retries:
                    # Schedule next retry with exponential backoff
                    delay = webhook.retry_delay_seconds * (2 ** (result.attempt_number - 1))
                    result.next_retry_at = now + timedelta(seconds=delay)

                retried += 1

            except Exception as e:
                logger.error(
                    "webhook_retry_error",
                    delivery_id=str(delivery.id),
                    error=str(e),
                )

        self.db.commit()
        return retried


# Convenience function for triggering events from anywhere
async def trigger_webhook_event(
    db: Session,
    organization_id: uuid.UUID,
    event_type: str,
    data: Dict[str, Any],
) -> List[WebhookDelivery]:
    """
    Trigger a webhook event.

    Example usage:
        await trigger_webhook_event(
            db,
            org_id,
            "document.uploaded",
            {"document_id": str(doc.id), "filename": doc.filename}
        )
    """
    service = WebhookService(db)
    return await service.trigger_event(organization_id, event_type, data)
