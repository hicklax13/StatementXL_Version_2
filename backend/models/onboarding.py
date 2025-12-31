"""
User Onboarding models.

Provides models for tracking user onboarding progress and feature tours.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum as SAEnum,
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


class OnboardingStatus(str, enum.Enum):
    """Onboarding status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class OnboardingStep(str, enum.Enum):
    """Predefined onboarding steps."""
    WELCOME = "welcome"
    PROFILE_SETUP = "profile_setup"
    ORGANIZATION_CREATE = "organization_create"
    FIRST_UPLOAD = "first_upload"
    TEMPLATE_SELECT = "template_select"
    FIRST_EXPORT = "first_export"
    EXPLORE_FEATURES = "explore_features"
    COMPLETE = "complete"


class FeatureTourType(str, enum.Enum):
    """Types of feature tours."""
    DOCUMENT_UPLOAD = "document_upload"
    TABLE_EXTRACTION = "table_extraction"
    MAPPING_EDITOR = "mapping_editor"
    TEMPLATE_LIBRARY = "template_library"
    BATCH_PROCESSING = "batch_processing"
    ANALYTICS_DASHBOARD = "analytics_dashboard"
    INTEGRATIONS = "integrations"
    API_KEYS = "api_keys"


class UserOnboarding(Base):
    """
    Tracks user's overall onboarding progress.
    """
    __tablename__ = "user_onboarding"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Overall status
    status = Column(
        SAEnum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED,
    )

    # Current step
    current_step = Column(
        SAEnum(OnboardingStep),
        default=OnboardingStep.WELCOME,
    )

    # Progress tracking
    steps_completed = Column(JSON, default=list)  # List of completed step names
    total_steps = Column(Integer, default=7)
    progress_percentage = Column(Integer, default=0)

    # User preferences
    show_tips = Column(Boolean, default=True)
    email_tips = Column(Boolean, default=True)

    # Timestamps
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    last_activity_at = Column(DateTime, default=datetime.utcnow)

    # Metrics
    time_spent_seconds = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    step_details = relationship(
        "OnboardingStepProgress",
        back_populates="onboarding",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<UserOnboarding(user_id={self.user_id}, status={self.status})>"


class OnboardingStepProgress(Base):
    """
    Detailed progress for each onboarding step.
    """
    __tablename__ = "onboarding_step_progress"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    onboarding_id = Column(
        UUID(),
        ForeignKey("user_onboarding.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Step identification
    step = Column(SAEnum(OnboardingStep), nullable=False)

    # Status
    status = Column(
        SAEnum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED,
    )

    # Progress data
    data = Column(JSON, default=dict)  # Step-specific progress data

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    time_spent_seconds = Column(Integer, default=0)

    # Interactions
    interactions = Column(JSON, default=list)  # [{action, timestamp}]

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    onboarding = relationship("UserOnboarding", back_populates="step_details")

    __table_args__ = (
        UniqueConstraint("onboarding_id", "step", name="uq_onboarding_step"),
    )


class FeatureTour(Base):
    """
    Feature tour completion tracking.
    """
    __tablename__ = "feature_tours"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Tour type
    tour_type = Column(SAEnum(FeatureTourType), nullable=False)

    # Status
    is_completed = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)

    # Progress
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    steps_viewed = Column(JSON, default=list)  # List of viewed step indices

    # Timing
    first_viewed_at = Column(DateTime)
    completed_at = Column(DateTime)
    dismissed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "tour_type", name="uq_user_tour"),
        Index("ix_feature_tours_user", "user_id"),
    )


class OnboardingChecklist(Base):
    """
    Custom checklist items for onboarding.
    """
    __tablename__ = "onboarding_checklists"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Checklist item
    title = Column(String(200), nullable=False)
    description = Column(Text)
    action_url = Column(String(500))

    # Status
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)

    # Ordering
    sort_order = Column(Integer, default=0)

    # Type (system-generated or custom)
    is_system = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_onboarding_checklist_user", "user_id"),
    )


class TipOfTheDay(Base):
    """
    Tips shown to users.
    """
    __tablename__ = "tips_of_the_day"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)

    # Content
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50))

    # Targeting
    target_user_type = Column(String(50))  # new, experienced, admin
    min_documents_processed = Column(Integer, default=0)
    max_documents_processed = Column(Integer)

    # Display
    icon = Column(String(50))
    action_url = Column(String(500))
    action_label = Column(String(100))

    # Status
    is_active = Column(Boolean, default=True)

    # Ordering
    priority = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)


class UserTipHistory(Base):
    """
    Tracks which tips a user has seen.
    """
    __tablename__ = "user_tip_history"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tip_id = Column(
        UUID(),
        ForeignKey("tips_of_the_day.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Status
    is_dismissed = Column(Boolean, default=False)
    is_helpful = Column(Boolean)  # User feedback

    shown_at = Column(DateTime, default=datetime.utcnow)
    dismissed_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("user_id", "tip_id", name="uq_user_tip"),
    )
