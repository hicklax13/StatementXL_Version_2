"""Subscription model for payment tracking."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.orm import relationship
import enum

from backend.database import Base


class SubscriptionPlan(str, enum.Enum):
    """Available subscription plans."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status values."""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"


class Subscription(Base):
    """
    Subscription model for tracking user payment status.
    
    Links to Stripe customer and subscription IDs.
    """
    __tablename__ = "subscriptions"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Stripe IDs
    stripe_customer_id = Column(String, unique=True, nullable=True, index=True)
    stripe_subscription_id = Column(String, unique=True, nullable=True, index=True)
    
    # Plan info
    plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE, nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    
    # Usage tracking
    exports_this_month = Column(String, default="0")  # JSON counter
    exports_limit = Column(String, default="5")  # Free tier limit
    
    # Timestamps
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="subscription")
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is in active state."""
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    
    @property
    def can_export(self) -> bool:
        """Check if user can perform exports."""
        if self.plan in [SubscriptionPlan.PRO, SubscriptionPlan.ENTERPRISE]:
            return True
        # Free tier - check limits
        exports = int(self.exports_this_month) if self.exports_this_month else 0
        limit = int(self.exports_limit) if self.exports_limit else 5
        return exports < limit
    
    def __repr__(self):
        return f"<Subscription {self.id} plan={self.plan} status={self.status}>"
