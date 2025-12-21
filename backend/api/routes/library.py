"""
Template library API routes.

Provides endpoints for managing the template library.
"""
import uuid
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.template import Template
from backend.models.mapping_profile import (
    MappingProfile,
    MappingFeedback,
    TemplateLibraryItem,
    FeedbackType,
)
from backend.services.learning_service import get_learning_service

logger = structlog.get_logger(__name__)

router = APIRouter()


# Request/Response Models
class TemplateLibraryCreate(BaseModel):
    """Request to add template to library."""

    template_id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    industry: Optional[str] = None
    tags: List[str] = []
    author: Optional[str] = None


class TemplateLibraryUpdate(BaseModel):
    """Request to update library item."""

    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    industry: Optional[str] = None
    tags: Optional[List[str]] = None
    is_featured: Optional[bool] = None


class TemplateLibraryResponse(BaseModel):
    """Response for library item."""

    id: str
    template_id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    industry: Optional[str]
    tags: List[str]
    download_count: int
    use_count: int
    rating: float
    is_featured: bool
    author: Optional[str]
    created_at: str


class ProfileResponse(BaseModel):
    """Response for mapping profile."""

    id: str
    name: str
    company_name: Optional[str]
    industry: Optional[str]
    times_used: int
    total_mappings: int
    auto_apply_success_rate: float
    created_at: str


class FeedbackCreate(BaseModel):
    """Request to record feedback."""

    source_label: str
    source_ontology_id: Optional[str] = None
    target_ontology_id: str
    feedback_type: str  # accepted, rejected, corrected, manual
    original_suggestion: Optional[str] = None
    profile_id: Optional[str] = None
    mapping_graph_id: Optional[str] = None
    user_email: Optional[str] = None


class AutoApplyRequest(BaseModel):
    """Request to auto-apply mappings."""

    source_labels: List[str]
    profile_id: Optional[str] = None
    company_name: Optional[str] = None


class AutoApplyResponse(BaseModel):
    """Response for auto-apply."""

    total_items: int
    auto_applied: int
    applied_mappings: List[dict]
    remaining_items: List[str]


# Library Endpoints
@router.get(
    "/library/templates",
    response_model=List[TemplateLibraryResponse],
    summary="List library templates",
)
async def list_library_templates(
    category: Optional[str] = None,
    industry: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    featured: Optional[bool] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> List[TemplateLibraryResponse]:
    """List templates in library with filtering."""
    query = db.query(TemplateLibraryItem).filter(
        TemplateLibraryItem.is_public == True
    )

    if category:
        query = query.filter(TemplateLibraryItem.category == category)
    if industry:
        query = query.filter(TemplateLibraryItem.industry == industry)
    if featured is not None:
        query = query.filter(TemplateLibraryItem.is_featured == featured)
    if search:
        query = query.filter(
            TemplateLibraryItem.name.ilike(f"%{search}%") |
            TemplateLibraryItem.description.ilike(f"%{search}%")
        )

    items = query.order_by(
        TemplateLibraryItem.is_featured.desc(),
        TemplateLibraryItem.use_count.desc(),
    ).offset(offset).limit(limit).all()

    return [
        TemplateLibraryResponse(
            id=str(item.id),
            template_id=str(item.template_id),
            name=item.name,
            description=item.description,
            category=item.category,
            industry=item.industry,
            tags=item.tags or [],
            download_count=item.download_count,
            use_count=item.use_count,
            rating=item.rating,
            is_featured=item.is_featured,
            author=item.author,
            created_at=item.created_at.isoformat(),
        )
        for item in items
    ]


@router.post(
    "/library/templates",
    response_model=TemplateLibraryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add template to library",
)
async def add_to_library(
    request: TemplateLibraryCreate,
    db: Session = Depends(get_db),
) -> TemplateLibraryResponse:
    """Add a template to the library."""
    # Verify template exists
    template = db.query(Template).filter(
        Template.id == uuid.UUID(request.template_id)
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {request.template_id} not found",
        )

    # Create library item
    item = TemplateLibraryItem(
        template_id=template.id,
        name=request.name,
        description=request.description,
        category=request.category,
        industry=request.industry,
        tags=request.tags,
        author=request.author,
        search_vector=f"{request.name} {request.description or ''} {' '.join(request.tags)}",
    )

    db.add(item)
    db.commit()

    logger.info("Template added to library", item_id=str(item.id))

    return TemplateLibraryResponse(
        id=str(item.id),
        template_id=str(item.template_id),
        name=item.name,
        description=item.description,
        category=item.category,
        industry=item.industry,
        tags=item.tags or [],
        download_count=item.download_count,
        use_count=item.use_count,
        rating=item.rating,
        is_featured=item.is_featured,
        author=item.author,
        created_at=item.created_at.isoformat(),
    )


@router.get(
    "/library/templates/{item_id}",
    response_model=TemplateLibraryResponse,
    summary="Get library item",
)
async def get_library_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> TemplateLibraryResponse:
    """Get a library item by ID."""
    item = db.query(TemplateLibraryItem).filter(
        TemplateLibraryItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library item {item_id} not found",
        )

    return TemplateLibraryResponse(
        id=str(item.id),
        template_id=str(item.template_id),
        name=item.name,
        description=item.description,
        category=item.category,
        industry=item.industry,
        tags=item.tags or [],
        download_count=item.download_count,
        use_count=item.use_count,
        rating=item.rating,
        is_featured=item.is_featured,
        author=item.author,
        created_at=item.created_at.isoformat(),
    )


@router.put(
    "/library/templates/{item_id}",
    response_model=TemplateLibraryResponse,
    summary="Update library item",
)
async def update_library_item(
    item_id: uuid.UUID,
    request: TemplateLibraryUpdate,
    db: Session = Depends(get_db),
) -> TemplateLibraryResponse:
    """Update a library item."""
    item = db.query(TemplateLibraryItem).filter(
        TemplateLibraryItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library item {item_id} not found",
        )

    # Update fields
    if request.name is not None:
        item.name = request.name
    if request.description is not None:
        item.description = request.description
    if request.category is not None:
        item.category = request.category
    if request.industry is not None:
        item.industry = request.industry
    if request.tags is not None:
        item.tags = request.tags
    if request.is_featured is not None:
        item.is_featured = request.is_featured

    item.updated_at = datetime.utcnow()
    db.commit()

    return TemplateLibraryResponse(
        id=str(item.id),
        template_id=str(item.template_id),
        name=item.name,
        description=item.description,
        category=item.category,
        industry=item.industry,
        tags=item.tags or [],
        download_count=item.download_count,
        use_count=item.use_count,
        rating=item.rating,
        is_featured=item.is_featured,
        author=item.author,
        created_at=item.created_at.isoformat(),
    )


@router.delete(
    "/library/templates/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove from library",
)
async def remove_from_library(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """Remove a template from the library."""
    item = db.query(TemplateLibraryItem).filter(
        TemplateLibraryItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library item {item_id} not found",
        )

    db.delete(item)
    db.commit()


@router.get(
    "/library/templates/{item_id}/recommend",
    response_model=List[TemplateLibraryResponse],
    summary="Get recommendations",
)
async def get_recommendations(
    item_id: uuid.UUID,
    limit: int = Query(default=5, le=20),
    db: Session = Depends(get_db),
) -> List[TemplateLibraryResponse]:
    """Get similar template recommendations."""
    item = db.query(TemplateLibraryItem).filter(
        TemplateLibraryItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library item {item_id} not found",
        )

    # Find similar by category/industry
    similar = db.query(TemplateLibraryItem).filter(
        TemplateLibraryItem.id != item_id,
        TemplateLibraryItem.is_public == True,
        (TemplateLibraryItem.category == item.category) |
        (TemplateLibraryItem.industry == item.industry)
    ).order_by(TemplateLibraryItem.use_count.desc()).limit(limit).all()

    return [
        TemplateLibraryResponse(
            id=str(i.id),
            template_id=str(i.template_id),
            name=i.name,
            description=i.description,
            category=i.category,
            industry=i.industry,
            tags=i.tags or [],
            download_count=i.download_count,
            use_count=i.use_count,
            rating=i.rating,
            is_featured=i.is_featured,
            author=i.author,
            created_at=i.created_at.isoformat(),
        )
        for i in similar
    ]


# Profile Endpoints
@router.get(
    "/profiles",
    response_model=List[ProfileResponse],
    summary="List mapping profiles",
)
async def list_profiles(
    company_name: Optional[str] = None,
    industry: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
) -> List[ProfileResponse]:
    """List mapping profiles."""
    query = db.query(MappingProfile).filter(MappingProfile.is_active == True)

    if company_name:
        query = query.filter(MappingProfile.company_name.ilike(f"%{company_name}%"))
    if industry:
        query = query.filter(MappingProfile.industry == industry)

    profiles = query.order_by(MappingProfile.times_used.desc()).limit(limit).all()

    return [
        ProfileResponse(
            id=str(p.id),
            name=p.name,
            company_name=p.company_name,
            industry=p.industry,
            times_used=p.times_used,
            total_mappings=p.total_mappings,
            auto_apply_success_rate=p.auto_apply_success_rate,
            created_at=p.created_at.isoformat(),
        )
        for p in profiles
    ]


# Feedback Endpoints
@router.post(
    "/feedback",
    summary="Record mapping feedback",
)
async def record_feedback(
    request: FeedbackCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Record analyst feedback on a mapping."""
    service = get_learning_service(db)

    feedback_type_map = {
        "accepted": FeedbackType.ACCEPTED,
        "rejected": FeedbackType.REJECTED,
        "corrected": FeedbackType.CORRECTED,
        "manual": FeedbackType.MANUAL,
    }

    feedback = service.record_feedback(
        source_label=request.source_label,
        source_ontology_id=request.source_ontology_id,
        target_ontology_id=request.target_ontology_id,
        feedback_type=feedback_type_map.get(request.feedback_type, FeedbackType.MANUAL),
        original_suggestion=request.original_suggestion,
        profile_id=uuid.UUID(request.profile_id) if request.profile_id else None,
        mapping_graph_id=uuid.UUID(request.mapping_graph_id) if request.mapping_graph_id else None,
        user_email=request.user_email,
    )

    return {"feedback_id": str(feedback.id), "message": "Feedback recorded"}


# Auto-Apply Endpoints
@router.post(
    "/auto-apply",
    response_model=AutoApplyResponse,
    summary="Auto-apply learned mappings",
)
async def auto_apply_mappings(
    request: AutoApplyRequest,
    db: Session = Depends(get_db),
) -> AutoApplyResponse:
    """Auto-apply learned mappings to new items."""
    service = get_learning_service(db)

    result = service.auto_apply_mappings(
        source_labels=request.source_labels,
        profile_id=uuid.UUID(request.profile_id) if request.profile_id else None,
        company_name=request.company_name,
    )

    return AutoApplyResponse(
        total_items=result.total_items,
        auto_applied=result.auto_applied,
        applied_mappings=result.applied_mappings,
        remaining_items=result.remaining_items,
    )
