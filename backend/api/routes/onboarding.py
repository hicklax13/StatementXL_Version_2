"""
Onboarding API routes.

Provides endpoints for user onboarding and feature tours.
"""
import uuid
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.dependencies import get_current_active_user
from backend.models.user import User
from backend.models.onboarding import OnboardingStep, FeatureTourType
from backend.services.onboarding_service import get_onboarding_service

logger = structlog.get_logger(__name__)

router = APIRouter()


# ==================== Schemas ====================

class OnboardingProgressResponse(BaseModel):
    """Onboarding progress response."""
    status: str
    current_step: str
    progress_percentage: int
    steps_completed: List[str]
    total_steps: int
    started_at: Optional[str]
    completed_at: Optional[str]
    steps: List[dict]


class StepCompleteRequest(BaseModel):
    """Request to complete a step."""
    step: str
    data: Optional[dict] = None


class ChecklistItemCreate(BaseModel):
    """Request to create checklist item."""
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    action_url: Optional[str] = None


class ChecklistItemResponse(BaseModel):
    """Checklist item response."""
    id: str
    title: str
    description: Optional[str]
    action_url: Optional[str]
    is_completed: bool
    is_system: bool
    sort_order: int


class TourStatusResponse(BaseModel):
    """Tour status response."""
    tours: dict


class TipResponse(BaseModel):
    """Tip response."""
    id: str
    title: str
    content: str
    category: Optional[str]
    icon: Optional[str]
    action_url: Optional[str]
    action_label: Optional[str]


# ==================== Onboarding Endpoints ====================

@router.get(
    "/progress",
    response_model=OnboardingProgressResponse,
    summary="Get onboarding progress",
)
async def get_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OnboardingProgressResponse:
    """Get the current user's onboarding progress."""
    service = get_onboarding_service(db)
    progress = service.get_progress(current_user.id)

    return OnboardingProgressResponse(**progress)


@router.post(
    "/start",
    response_model=OnboardingProgressResponse,
    summary="Start onboarding",
)
async def start_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OnboardingProgressResponse:
    """Start the onboarding process."""
    service = get_onboarding_service(db)
    service.start_onboarding(current_user.id)
    progress = service.get_progress(current_user.id)

    return OnboardingProgressResponse(**progress)


@router.post(
    "/step/complete",
    response_model=OnboardingProgressResponse,
    summary="Complete step",
)
async def complete_step(
    request: StepCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OnboardingProgressResponse:
    """Mark an onboarding step as completed."""
    service = get_onboarding_service(db)

    try:
        step = OnboardingStep(request.step)
    except ValueError:
        raise HTTPException(400, f"Invalid step: {request.step}")

    service.complete_step(current_user.id, step, request.data)
    progress = service.get_progress(current_user.id)

    return OnboardingProgressResponse(**progress)


@router.post(
    "/step/{step}/skip",
    response_model=OnboardingProgressResponse,
    summary="Skip step",
)
async def skip_step(
    step: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OnboardingProgressResponse:
    """Skip an onboarding step."""
    service = get_onboarding_service(db)

    try:
        step_enum = OnboardingStep(step)
    except ValueError:
        raise HTTPException(400, f"Invalid step: {step}")

    service.skip_step(current_user.id, step_enum)
    progress = service.get_progress(current_user.id)

    return OnboardingProgressResponse(**progress)


@router.post(
    "/skip",
    response_model=OnboardingProgressResponse,
    summary="Skip entire onboarding",
)
async def skip_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OnboardingProgressResponse:
    """Skip the entire onboarding process."""
    service = get_onboarding_service(db)
    service.skip_onboarding(current_user.id)
    progress = service.get_progress(current_user.id)

    return OnboardingProgressResponse(**progress)


# ==================== Feature Tour Endpoints ====================

@router.get(
    "/tours",
    response_model=TourStatusResponse,
    summary="Get tour status",
)
async def get_tours(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TourStatusResponse:
    """Get status of all feature tours."""
    service = get_onboarding_service(db)
    status = service.get_tour_status(current_user.id)

    return TourStatusResponse(tours=status)


@router.post(
    "/tours/{tour_type}/start",
    summary="Start tour",
)
async def start_tour(
    tour_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Start a feature tour."""
    service = get_onboarding_service(db)

    try:
        tour_enum = FeatureTourType(tour_type)
    except ValueError:
        raise HTTPException(400, f"Invalid tour type: {tour_type}")

    tour = service.start_tour(current_user.id, tour_enum)

    return {
        "tour_type": tour.tour_type.value,
        "current_step": tour.current_step,
        "is_completed": tour.is_completed,
    }


@router.post(
    "/tours/{tour_type}/step/{step_index}",
    summary="Complete tour step",
)
async def complete_tour_step(
    tour_type: str,
    step_index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark a tour step as viewed."""
    service = get_onboarding_service(db)

    try:
        tour_enum = FeatureTourType(tour_type)
    except ValueError:
        raise HTTPException(400, f"Invalid tour type: {tour_type}")

    tour = service.complete_tour_step(current_user.id, tour_enum, step_index)

    return {
        "tour_type": tour.tour_type.value,
        "current_step": tour.current_step,
        "steps_viewed": tour.steps_viewed,
    }


@router.post(
    "/tours/{tour_type}/complete",
    summary="Complete tour",
)
async def complete_tour(
    tour_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark a tour as completed."""
    service = get_onboarding_service(db)

    try:
        tour_enum = FeatureTourType(tour_type)
    except ValueError:
        raise HTTPException(400, f"Invalid tour type: {tour_type}")

    tour = service.complete_tour(current_user.id, tour_enum)

    return {"message": "Tour completed", "tour_type": tour.tour_type.value}


@router.post(
    "/tours/{tour_type}/dismiss",
    summary="Dismiss tour",
)
async def dismiss_tour(
    tour_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Dismiss a tour."""
    service = get_onboarding_service(db)

    try:
        tour_enum = FeatureTourType(tour_type)
    except ValueError:
        raise HTTPException(400, f"Invalid tour type: {tour_type}")

    service.dismiss_tour(current_user.id, tour_enum)

    return {"message": "Tour dismissed"}


# ==================== Checklist Endpoints ====================

@router.get(
    "/checklist",
    response_model=List[ChecklistItemResponse],
    summary="Get checklist",
)
async def get_checklist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[ChecklistItemResponse]:
    """Get the user's onboarding checklist."""
    service = get_onboarding_service(db)
    items = service.get_checklist(current_user.id)

    return [
        ChecklistItemResponse(
            id=str(item.id),
            title=item.title,
            description=item.description,
            action_url=item.action_url,
            is_completed=item.is_completed,
            is_system=item.is_system,
            sort_order=item.sort_order,
        )
        for item in items
    ]


@router.post(
    "/checklist",
    response_model=ChecklistItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add checklist item",
)
async def add_checklist_item(
    request: ChecklistItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ChecklistItemResponse:
    """Add a custom checklist item."""
    service = get_onboarding_service(db)

    item = service.add_checklist_item(
        user_id=current_user.id,
        title=request.title,
        description=request.description,
        action_url=request.action_url,
    )

    return ChecklistItemResponse(
        id=str(item.id),
        title=item.title,
        description=item.description,
        action_url=item.action_url,
        is_completed=item.is_completed,
        is_system=item.is_system,
        sort_order=item.sort_order,
    )


@router.post(
    "/checklist/{item_id}/complete",
    summary="Complete checklist item",
)
async def complete_checklist_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark a checklist item as completed."""
    service = get_onboarding_service(db)

    item = service.complete_checklist_item(current_user.id, item_id)
    if not item:
        raise HTTPException(404, "Checklist item not found")

    return {"message": "Item completed", "id": str(item.id)}


# ==================== Tips Endpoints ====================

@router.get(
    "/tip",
    response_model=Optional[TipResponse],
    summary="Get tip of the day",
)
async def get_tip(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Optional[TipResponse]:
    """Get a tip for the user."""
    service = get_onboarding_service(db)
    tip = service.get_tip_of_the_day(current_user.id)

    if not tip:
        return None

    return TipResponse(
        id=str(tip.id),
        title=tip.title,
        content=tip.content,
        category=tip.category,
        icon=tip.icon,
        action_url=tip.action_url,
        action_label=tip.action_label,
    )


@router.post(
    "/tip/{tip_id}/dismiss",
    summary="Dismiss tip",
)
async def dismiss_tip(
    tip_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Dismiss a tip."""
    service = get_onboarding_service(db)
    service.dismiss_tip(current_user.id, tip_id)

    return {"message": "Tip dismissed"}


@router.post(
    "/tip/{tip_id}/rate",
    summary="Rate tip",
)
async def rate_tip(
    tip_id: uuid.UUID,
    is_helpful: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Rate a tip as helpful or not."""
    service = get_onboarding_service(db)
    service.rate_tip(current_user.id, tip_id, is_helpful)

    return {"message": "Rating recorded"}
