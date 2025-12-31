"""
Payment routes for Stripe integration.

Handles checkout sessions, webhooks, and subscription management.
"""
import os
import stripe
import structlog
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.models.user import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/payments", tags=["Payments"])

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Pricing configuration
PRICE_IDS = {
    "pro": os.getenv("STRIPE_PRO_PRICE_ID", "price_pro_monthly"),
    "enterprise": os.getenv("STRIPE_ENTERPRISE_PRICE_ID", "price_enterprise_monthly"),
}


class CheckoutRequest(BaseModel):
    """Request to create a checkout session."""
    plan: str  # "pro" or "enterprise"
    success_url: str = "https://statementxl.com/success"
    cancel_url: str = "https://statementxl.com/pricing"


class CheckoutResponse(BaseModel):
    """Checkout session response."""
    checkout_url: str
    session_id: str


class SubscriptionResponse(BaseModel):
    """Current subscription status."""
    plan: str
    status: str
    exports_used: int
    exports_limit: int
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False


@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe Checkout session for subscription.
    
    Returns a URL to redirect the user to Stripe's hosted checkout page.
    """
    if request.plan not in PRICE_IDS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {request.plan}")
    
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        # Create or retrieve Stripe customer
        customer = None
        if hasattr(current_user, 'subscription') and current_user.subscription:
            customer = current_user.subscription.stripe_customer_id
        
        if not customer:
            stripe_customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": current_user.id}
            )
            customer = stripe_customer.id
        
        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer,
            payment_method_types=["card"],
            line_items=[{
                "price": PRICE_IDS[request.plan],
                "quantity": 1,
            }],
            mode="subscription",
            success_url=request.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.cancel_url,
            metadata={
                "user_id": current_user.id,
                "plan": request.plan,
            },
        )
        
        logger.info(
            "checkout_session_created",
            user_id=current_user.id,
            plan=request.plan,
            session_id=session.id
        )
        
        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id
        )
        
    except stripe.error.StripeError as e:
        logger.error("stripe_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    """
    Handle Stripe webhook events.
    
    Events handled:
    - checkout.session.completed: New subscription created
    - customer.subscription.updated: Plan changed or renewed
    - customer.subscription.deleted: Subscription canceled
    - invoice.payment_failed: Payment failed
    """
    payload = await request.body()
    
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("stripe_webhook_secret_not_configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("invalid_stripe_signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event["type"]
    data = event["data"]["object"]
    
    logger.info("stripe_webhook_received", event_type=event_type)
    
    # Handle different event types
    if event_type == "checkout.session.completed":
        await handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(data)
    elif event_type == "invoice.payment_failed":
        await handle_payment_failed(data)
    
    return {"status": "success"}


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
):
    """Get current user's subscription status."""
    subscription = getattr(current_user, 'subscription', None)
    
    if not subscription:
        return SubscriptionResponse(
            plan="free",
            status="active",
            exports_used=0,
            exports_limit=5,
        )
    
    return SubscriptionResponse(
        plan=subscription.plan.value if subscription.plan else "free",
        status=subscription.status.value if subscription.status else "active",
        exports_used=int(subscription.exports_this_month or 0),
        exports_limit=int(subscription.exports_limit or 5),
        current_period_end=subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        cancel_at_period_end=subscription.canceled_at is not None,
    )


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
):
    """Cancel current subscription at period end."""
    subscription = getattr(current_user, 'subscription', None)
    
    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription")
    
    try:
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        logger.info("subscription_canceled", user_id=current_user.id)
        
        return {"status": "canceled", "message": "Your subscription will end at the current period end"}
        
    except stripe.error.StripeError as e:
        logger.error("stripe_cancel_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# Webhook handlers
async def handle_checkout_completed(session: dict):
    """Handle successful checkout - create or update subscription."""
    user_id = session.get("metadata", {}).get("user_id")
    plan = session.get("metadata", {}).get("plan", "pro")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    
    logger.info(
        "checkout_completed",
        user_id=user_id,
        plan=plan,
        customer_id=customer_id
    )
    
    # Update subscription in database
    from backend.database import get_db
    from backend.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
    from sqlalchemy.orm import Session
    
    db: Session = next(get_db())
    try:
        subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
        if subscription:
            subscription.stripe_customer_id = customer_id
            subscription.stripe_subscription_id = subscription_data.get("id")
            subscription.plan = SubscriptionPlan(plan)
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.current_period_start = datetime.fromtimestamp(subscription_data.get("current_period_start"))
            subscription.current_period_end = datetime.fromtimestamp(subscription_data.get("current_period_end"))
            db.commit()
            logger.info("subscription_updated_in_db", user_id=user_id, subscription_id=subscription.id)
    except Exception as e:
        logger.error("failed_to_update_subscription", error=str(e), user_id=user_id)
        db.rollback()
    finally:
        db.close()


async def handle_subscription_updated(subscription: dict):
    """Handle subscription updates (renewals, plan changes)."""
    subscription_id = subscription.get("id")
    status = subscription.get("status")
    
    logger.info(
        "subscription_updated",
        subscription_id=subscription_id,
        status=status
    )
    
    # Update subscription status in database
    from backend.database import get_db
    from backend.models.subscription import Subscription, SubscriptionStatus
    from sqlalchemy.orm import Session
    
    db: Session = next(get_db())
    try:
        sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
        if sub:
            sub.status = SubscriptionStatus(status)
            sub.current_period_start = datetime.fromtimestamp(subscription.get("current_period_start"))
            sub.current_period_end = datetime.fromtimestamp(subscription.get("current_period_end"))
            db.commit()
            logger.info("subscription_status_updated", subscription_id=subscription_id, new_status=status)
    except Exception as e:
        logger.error("failed_to_update_subscription_status", error=str(e))
        db.rollback()
    finally:
        db.close()


async def handle_subscription_deleted(subscription: dict):
    """Handle subscription cancellation."""
    subscription_id = subscription.get("id")
    
    logger.info("subscription_deleted", subscription_id=subscription_id)
    
    # Mark subscription as canceled in database
    from backend.database import get_db
    from backend.models.subscription import Subscription, SubscriptionStatus
    from sqlalchemy.orm import Session
    
    db: Session = next(get_db())
    try:
        sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
        if sub:
            sub.status = SubscriptionStatus.CANCELED
            sub.canceled_at = datetime.utcnow()
            db.commit()
            logger.info("subscription_marked_canceled", subscription_id=subscription_id)
    except Exception as e:
        logger.error("failed_to_cancel_subscription", error=str(e))
        db.rollback()
    finally:
        db.close()


async def handle_payment_failed(invoice: dict):
    """Handle failed payment."""
    customer_id = invoice.get("customer")
    
    logger.warning("payment_failed", customer_id=customer_id)
    
    # Update subscription status to past_due
    from backend.database import get_db
    from backend.models.subscription import Subscription, SubscriptionStatus
    from backend.services.email_service import EmailService
    from sqlalchemy.orm import Session
    
    db: Session = next(get_db())
    try:
        sub = db.query(Subscription).filter(Subscription.stripe_customer_id == customer_id).first()
        if sub:
            sub.status = SubscriptionStatus.PAST_DUE
            db.commit()
            logger.info("subscription_marked_past_due", customer_id=customer_id)
            
            # Send notification email to user
            try:
                email_service = EmailService()
                user = sub.user
                email_service.send_payment_failed_notification(
                    to_email=user.email,
                    user_name=user.full_name or user.email
                )
                logger.info("payment_failed_email_sent", user_id=sub.user_id)
            except Exception as email_error:
                logger.error("failed_to_send_payment_failed_email", error=str(email_error))
    except Exception as e:
        logger.error("failed_to_handle_payment_failure", error=str(e))
        db.rollback()
    finally:
        db.close()
