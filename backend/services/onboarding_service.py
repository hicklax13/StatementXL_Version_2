"""
Onboarding Service.

Provides user onboarding management and feature tour tracking.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.onboarding import (
    UserOnboarding,
    OnboardingStepProgress,
    FeatureTour,
    OnboardingChecklist,
    TipOfTheDay,
    UserTipHistory,
    OnboardingStatus,
    OnboardingStep,
    FeatureTourType,
)
from backend.models.document import Document

logger = structlog.get_logger(__name__)


# Default onboarding steps configuration
DEFAULT_STEPS = [
    {
        "step": OnboardingStep.WELCOME,
        "title": "Welcome to StatementXL",
        "description": "Learn how to extract and analyze financial statements",
        "action_url": "/onboarding/welcome",
    },
    {
        "step": OnboardingStep.PROFILE_SETUP,
        "title": "Complete Your Profile",
        "description": "Add your name and preferences",
        "action_url": "/settings/profile",
    },
    {
        "step": OnboardingStep.ORGANIZATION_CREATE,
        "title": "Create or Join an Organization",
        "description": "Set up your team workspace",
        "action_url": "/organizations/new",
    },
    {
        "step": OnboardingStep.FIRST_UPLOAD,
        "title": "Upload Your First Document",
        "description": "Upload a PDF financial statement",
        "action_url": "/upload",
    },
    {
        "step": OnboardingStep.TEMPLATE_SELECT,
        "title": "Choose a Template",
        "description": "Select an output template for your data",
        "action_url": "/templates",
    },
    {
        "step": OnboardingStep.FIRST_EXPORT,
        "title": "Export Your Results",
        "description": "Download your structured data",
        "action_url": "/export",
    },
    {
        "step": OnboardingStep.EXPLORE_FEATURES,
        "title": "Explore More Features",
        "description": "Discover batch processing, integrations, and more",
        "action_url": "/features",
    },
]


class OnboardingService:
    """Service for managing user onboarding."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Onboarding Management ====================

    def get_or_create_onboarding(self, user_id: uuid.UUID) -> UserOnboarding:
        """Get or create onboarding record for user."""
        onboarding = self.db.query(UserOnboarding).filter(
            UserOnboarding.user_id == user_id
        ).first()

        if not onboarding:
            onboarding = UserOnboarding(
                user_id=user_id,
                status=OnboardingStatus.NOT_STARTED,
                current_step=OnboardingStep.WELCOME,
                total_steps=len(DEFAULT_STEPS),
            )
            self.db.add(onboarding)
            self.db.commit()

            # Create checklist items
            self._create_default_checklist(user_id)

        return onboarding

    def start_onboarding(self, user_id: uuid.UUID) -> UserOnboarding:
        """Start the onboarding process."""
        onboarding = self.get_or_create_onboarding(user_id)

        if onboarding.status == OnboardingStatus.NOT_STARTED:
            onboarding.status = OnboardingStatus.IN_PROGRESS
            onboarding.started_at = datetime.utcnow()
            self.db.commit()

        return onboarding

    def complete_step(
        self,
        user_id: uuid.UUID,
        step: OnboardingStep,
        data: Optional[Dict[str, Any]] = None,
    ) -> UserOnboarding:
        """Mark a step as completed."""
        onboarding = self.get_or_create_onboarding(user_id)

        # Get or create step progress
        step_progress = self.db.query(OnboardingStepProgress).filter(
            OnboardingStepProgress.onboarding_id == onboarding.id,
            OnboardingStepProgress.step == step,
        ).first()

        if not step_progress:
            step_progress = OnboardingStepProgress(
                onboarding_id=onboarding.id,
                step=step,
                started_at=datetime.utcnow(),
            )
            self.db.add(step_progress)

        # Mark as completed
        step_progress.status = OnboardingStatus.COMPLETED
        step_progress.completed_at = datetime.utcnow()
        if data:
            step_progress.data = data

        # Update onboarding progress
        completed_steps = onboarding.steps_completed or []
        if step.value not in completed_steps:
            completed_steps.append(step.value)
            onboarding.steps_completed = completed_steps

        onboarding.progress_percentage = int(
            (len(completed_steps) / onboarding.total_steps) * 100
        )
        onboarding.last_activity_at = datetime.utcnow()

        # Move to next step
        step_order = [s["step"] for s in DEFAULT_STEPS]
        try:
            current_idx = step_order.index(step)
            if current_idx + 1 < len(step_order):
                onboarding.current_step = step_order[current_idx + 1]
            else:
                onboarding.current_step = OnboardingStep.COMPLETE
                onboarding.status = OnboardingStatus.COMPLETED
                onboarding.completed_at = datetime.utcnow()
        except ValueError:
            pass

        self.db.commit()

        logger.info(
            "onboarding_step_completed",
            user_id=str(user_id),
            step=step.value,
            progress=onboarding.progress_percentage,
        )

        return onboarding

    def skip_step(self, user_id: uuid.UUID, step: OnboardingStep) -> UserOnboarding:
        """Skip a step."""
        onboarding = self.get_or_create_onboarding(user_id)

        step_progress = OnboardingStepProgress(
            onboarding_id=onboarding.id,
            step=step,
            status=OnboardingStatus.SKIPPED,
            completed_at=datetime.utcnow(),
        )
        self.db.add(step_progress)

        # Move to next step
        step_order = [s["step"] for s in DEFAULT_STEPS]
        try:
            current_idx = step_order.index(step)
            if current_idx + 1 < len(step_order):
                onboarding.current_step = step_order[current_idx + 1]
        except ValueError:
            pass

        onboarding.last_activity_at = datetime.utcnow()
        self.db.commit()

        return onboarding

    def skip_onboarding(self, user_id: uuid.UUID) -> UserOnboarding:
        """Skip entire onboarding process."""
        onboarding = self.get_or_create_onboarding(user_id)

        onboarding.status = OnboardingStatus.SKIPPED
        onboarding.current_step = OnboardingStep.COMPLETE
        onboarding.completed_at = datetime.utcnow()

        self.db.commit()

        return onboarding

    def get_progress(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get detailed onboarding progress."""
        onboarding = self.get_or_create_onboarding(user_id)

        # Get step details
        step_progress = self.db.query(OnboardingStepProgress).filter(
            OnboardingStepProgress.onboarding_id == onboarding.id
        ).all()

        step_status = {sp.step.value: sp.status.value for sp in step_progress}

        return {
            "status": onboarding.status.value,
            "current_step": onboarding.current_step.value,
            "progress_percentage": onboarding.progress_percentage,
            "steps_completed": onboarding.steps_completed or [],
            "total_steps": onboarding.total_steps,
            "started_at": onboarding.started_at.isoformat() if onboarding.started_at else None,
            "completed_at": onboarding.completed_at.isoformat() if onboarding.completed_at else None,
            "steps": [
                {
                    **step_config,
                    "step": step_config["step"].value,
                    "status": step_status.get(step_config["step"].value, "not_started"),
                }
                for step_config in DEFAULT_STEPS
            ],
        }

    # ==================== Feature Tours ====================

    def start_tour(self, user_id: uuid.UUID, tour_type: FeatureTourType) -> FeatureTour:
        """Start a feature tour."""
        tour = self.db.query(FeatureTour).filter(
            FeatureTour.user_id == user_id,
            FeatureTour.tour_type == tour_type,
        ).first()

        if not tour:
            tour = FeatureTour(
                user_id=user_id,
                tour_type=tour_type,
                first_viewed_at=datetime.utcnow(),
            )
            self.db.add(tour)
            self.db.commit()

        return tour

    def complete_tour_step(
        self,
        user_id: uuid.UUID,
        tour_type: FeatureTourType,
        step_index: int,
    ) -> FeatureTour:
        """Mark a tour step as viewed."""
        tour = self.start_tour(user_id, tour_type)

        steps_viewed = tour.steps_viewed or []
        if step_index not in steps_viewed:
            steps_viewed.append(step_index)
            tour.steps_viewed = steps_viewed
            tour.current_step = step_index

        self.db.commit()
        return tour

    def complete_tour(self, user_id: uuid.UUID, tour_type: FeatureTourType) -> FeatureTour:
        """Mark a tour as completed."""
        tour = self.start_tour(user_id, tour_type)

        tour.is_completed = True
        tour.completed_at = datetime.utcnow()

        self.db.commit()
        return tour

    def dismiss_tour(self, user_id: uuid.UUID, tour_type: FeatureTourType) -> FeatureTour:
        """Dismiss a tour."""
        tour = self.start_tour(user_id, tour_type)

        tour.is_dismissed = True
        tour.dismissed_at = datetime.utcnow()

        self.db.commit()
        return tour

    def get_tour_status(self, user_id: uuid.UUID) -> Dict[str, Dict]:
        """Get status of all feature tours."""
        tours = self.db.query(FeatureTour).filter(
            FeatureTour.user_id == user_id
        ).all()

        status = {}
        for tour_type in FeatureTourType:
            tour = next((t for t in tours if t.tour_type == tour_type), None)
            status[tour_type.value] = {
                "is_completed": tour.is_completed if tour else False,
                "is_dismissed": tour.is_dismissed if tour else False,
                "current_step": tour.current_step if tour else 0,
            }

        return status

    # ==================== Checklist ====================

    def _create_default_checklist(self, user_id: uuid.UUID) -> None:
        """Create default checklist items."""
        default_items = [
            ("Upload your first document", "Get started by uploading a PDF", "/upload"),
            ("Review extracted data", "Check the accuracy of extracted tables", None),
            ("Map to template", "Apply a template to your extracted data", "/templates"),
            ("Export results", "Download your structured data", "/export"),
            ("Invite team members", "Collaborate with your team", "/settings/team"),
        ]

        for i, (title, desc, url) in enumerate(default_items):
            item = OnboardingChecklist(
                user_id=user_id,
                title=title,
                description=desc,
                action_url=url,
                sort_order=i,
                is_system=True,
            )
            self.db.add(item)

    def get_checklist(self, user_id: uuid.UUID) -> List[OnboardingChecklist]:
        """Get user's checklist items."""
        return self.db.query(OnboardingChecklist).filter(
            OnboardingChecklist.user_id == user_id
        ).order_by(OnboardingChecklist.sort_order).all()

    def complete_checklist_item(
        self,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> Optional[OnboardingChecklist]:
        """Mark a checklist item as completed."""
        item = self.db.query(OnboardingChecklist).filter(
            OnboardingChecklist.id == item_id,
            OnboardingChecklist.user_id == user_id,
        ).first()

        if item:
            item.is_completed = True
            item.completed_at = datetime.utcnow()
            self.db.commit()

        return item

    def add_checklist_item(
        self,
        user_id: uuid.UUID,
        title: str,
        description: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> OnboardingChecklist:
        """Add a custom checklist item."""
        max_order = self.db.query(func.max(OnboardingChecklist.sort_order)).filter(
            OnboardingChecklist.user_id == user_id
        ).scalar() or 0

        item = OnboardingChecklist(
            user_id=user_id,
            title=title,
            description=description,
            action_url=action_url,
            sort_order=max_order + 1,
            is_system=False,
        )

        self.db.add(item)
        self.db.commit()

        return item

    # ==================== Tips ====================

    def get_tip_of_the_day(self, user_id: uuid.UUID) -> Optional[TipOfTheDay]:
        """Get a tip for the user."""
        # Get user's document count for targeting
        doc_count = self.db.query(func.count(Document.id)).filter(
            Document.user_id == user_id
        ).scalar()

        # Get tips user hasn't seen
        seen_tip_ids = self.db.query(UserTipHistory.tip_id).filter(
            UserTipHistory.user_id == user_id
        ).subquery()

        tip = self.db.query(TipOfTheDay).filter(
            TipOfTheDay.is_active == True,
            ~TipOfTheDay.id.in_(seen_tip_ids),
            TipOfTheDay.min_documents_processed <= doc_count,
        ).order_by(TipOfTheDay.priority.desc()).first()

        if tip:
            # Record that user saw this tip
            history = UserTipHistory(
                user_id=user_id,
                tip_id=tip.id,
            )
            self.db.add(history)
            self.db.commit()

        return tip

    def dismiss_tip(self, user_id: uuid.UUID, tip_id: uuid.UUID) -> None:
        """Dismiss a tip."""
        history = self.db.query(UserTipHistory).filter(
            UserTipHistory.user_id == user_id,
            UserTipHistory.tip_id == tip_id,
        ).first()

        if history:
            history.is_dismissed = True
            history.dismissed_at = datetime.utcnow()
            self.db.commit()

    def rate_tip(
        self,
        user_id: uuid.UUID,
        tip_id: uuid.UUID,
        is_helpful: bool,
    ) -> None:
        """Rate a tip as helpful or not."""
        history = self.db.query(UserTipHistory).filter(
            UserTipHistory.user_id == user_id,
            UserTipHistory.tip_id == tip_id,
        ).first()

        if history:
            history.is_helpful = is_helpful
            self.db.commit()

    # ==================== Auto-detection ====================

    def check_auto_completions(self, user_id: uuid.UUID) -> List[OnboardingStep]:
        """Check for automatically completed steps based on user activity."""
        onboarding = self.get_or_create_onboarding(user_id)
        completed = []

        # Check for first document upload
        doc_count = self.db.query(func.count(Document.id)).filter(
            Document.user_id == user_id
        ).scalar()

        if doc_count > 0 and OnboardingStep.FIRST_UPLOAD.value not in (onboarding.steps_completed or []):
            self.complete_step(user_id, OnboardingStep.FIRST_UPLOAD)
            completed.append(OnboardingStep.FIRST_UPLOAD)

        # Add more auto-detection logic as needed

        return completed


def get_onboarding_service(db: Session) -> OnboardingService:
    """Factory function to get onboarding service instance."""
    return OnboardingService(db)
