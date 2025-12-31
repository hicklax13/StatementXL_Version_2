"""
Enhanced Template Library API routes.

Provides endpoints for template versioning, sharing, reviews, and collections.
"""
import uuid
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.dependencies import get_current_active_user
from backend.models.user import User
from backend.models.template_library import TemplateVisibility
from backend.services.template_library_service import get_template_library_service

logger = structlog.get_logger(__name__)

router = APIRouter()


# ==================== Request/Response Schemas ====================

# Versions
class VersionCreate(BaseModel):
    """Request to create a template version."""
    version_number: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    version_label: Optional[str] = None
    change_summary: Optional[str] = None
    publish: bool = False


class VersionResponse(BaseModel):
    """Response for a template version."""
    id: str
    template_id: str
    version_number: str
    version_label: Optional[str]
    change_summary: Optional[str]
    file_hash: Optional[str]
    file_size: Optional[int]
    is_published: bool
    is_latest: bool
    created_at: str


# Sharing
class ShareRequest(BaseModel):
    """Request to share a template."""
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    permission: str = Field(default="view", pattern="^(view|edit|admin)$")
    message: Optional[str] = None
    expires_in_days: Optional[int] = None


class ShareResponse(BaseModel):
    """Response for a share."""
    id: str
    template_id: str
    shared_with_user_id: Optional[str]
    shared_with_org_id: Optional[str]
    permission: str
    is_accepted: bool
    expires_at: Optional[str]
    created_at: str


# Forking
class ForkRequest(BaseModel):
    """Request to fork a template."""
    new_name: Optional[str] = None
    reason: Optional[str] = None


class ForkResponse(BaseModel):
    """Response for a fork."""
    original_template_id: str
    forked_template_id: str
    forked_template_name: str
    fork_id: str


# Reviews
class ReviewCreate(BaseModel):
    """Request to create a review."""
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    pros: Optional[List[str]] = None
    cons: Optional[List[str]] = None
    use_case: Optional[str] = None
    experience_level: Optional[str] = Field(
        None, pattern="^(beginner|intermediate|advanced)$"
    )


class ReviewResponse(BaseModel):
    """Response for a review."""
    id: str
    template_id: str
    user_id: str
    rating: int
    title: Optional[str]
    content: Optional[str]
    pros: List[str]
    cons: List[str]
    use_case: Optional[str]
    experience_level: Optional[str]
    is_verified_purchase: bool
    helpful_count: int
    not_helpful_count: int
    created_at: str


class ReviewVoteRequest(BaseModel):
    """Request to vote on a review."""
    is_helpful: bool


# Collections
class CollectionCreate(BaseModel):
    """Request to create a collection."""
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    visibility: str = Field(default="private", pattern="^(private|organization|public)$")


class CollectionResponse(BaseModel):
    """Response for a collection."""
    id: str
    name: str
    description: Optional[str]
    slug: str
    visibility: str
    template_count: int
    follower_count: int
    is_featured: bool
    created_at: str


class CollectionTemplateAdd(BaseModel):
    """Request to add template to collection."""
    template_id: str
    notes: Optional[str] = None


# Categories
class CategoryResponse(BaseModel):
    """Response for a category."""
    id: str
    name: str
    slug: str
    description: Optional[str]
    icon: Optional[str]
    color: Optional[str]
    template_count: int
    children: List["CategoryResponse"] = []


# Usage stats
class UsageStatsResponse(BaseModel):
    """Response for usage statistics."""
    period_days: int
    action_counts: dict
    unique_users: int
    daily_usage: List[dict]


# ==================== Version Endpoints ====================

@router.post(
    "/templates/{template_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create template version",
)
async def create_version(
    template_id: uuid.UUID,
    request: VersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> VersionResponse:
    """Create a new version of a template."""
    service = get_template_library_service(db)

    try:
        version = service.create_version(
            template_id=template_id,
            version_number=request.version_number,
            changed_by_id=current_user.id,
            change_summary=request.change_summary,
            version_label=request.version_label,
            publish=request.publish,
        )

        return VersionResponse(
            id=str(version.id),
            template_id=str(version.template_id),
            version_number=version.version_number,
            version_label=version.version_label,
            change_summary=version.change_summary,
            file_hash=version.file_hash,
            file_size=version.file_size,
            is_published=version.is_published,
            is_latest=version.is_latest,
            created_at=version.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/templates/{template_id}/versions",
    response_model=List[VersionResponse],
    summary="List template versions",
)
async def list_versions(
    template_id: uuid.UUID,
    published_only: bool = False,
    db: Session = Depends(get_db),
) -> List[VersionResponse]:
    """List all versions of a template."""
    service = get_template_library_service(db)
    versions = service.get_versions(template_id, published_only)

    return [
        VersionResponse(
            id=str(v.id),
            template_id=str(v.template_id),
            version_number=v.version_number,
            version_label=v.version_label,
            change_summary=v.change_summary,
            file_hash=v.file_hash,
            file_size=v.file_size,
            is_published=v.is_published,
            is_latest=v.is_latest,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]


@router.post(
    "/versions/{version_id}/publish",
    response_model=VersionResponse,
    summary="Publish version",
)
async def publish_version(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> VersionResponse:
    """Publish a template version."""
    service = get_template_library_service(db)

    try:
        version = service.publish_version(version_id)

        return VersionResponse(
            id=str(version.id),
            template_id=str(version.template_id),
            version_number=version.version_number,
            version_label=version.version_label,
            change_summary=version.change_summary,
            file_hash=version.file_hash,
            file_size=version.file_size,
            is_published=version.is_published,
            is_latest=version.is_latest,
            created_at=version.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/versions/{version_id}/restore",
    summary="Restore version",
)
async def restore_version(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Restore a template to a previous version."""
    service = get_template_library_service(db)

    try:
        template = service.restore_version(version_id, current_user.id)
        return {
            "message": "Template restored successfully",
            "template_id": str(template.id),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== Sharing Endpoints ====================

@router.post(
    "/templates/{template_id}/share",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Share template",
)
async def share_template(
    template_id: uuid.UUID,
    request: ShareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ShareResponse:
    """Share a template with a user or organization."""
    service = get_template_library_service(db)

    try:
        share = service.share_template(
            template_id=template_id,
            shared_by_id=current_user.id,
            user_id=uuid.UUID(request.user_id) if request.user_id else None,
            organization_id=uuid.UUID(request.organization_id) if request.organization_id else None,
            permission=request.permission,
            message=request.message,
            expires_in_days=request.expires_in_days,
        )

        return ShareResponse(
            id=str(share.id),
            template_id=str(share.template_id),
            shared_with_user_id=str(share.shared_with_user_id) if share.shared_with_user_id else None,
            shared_with_org_id=str(share.shared_with_org_id) if share.shared_with_org_id else None,
            permission=share.permission,
            is_accepted=share.is_accepted,
            expires_at=share.expires_at.isoformat() if share.expires_at else None,
            created_at=share.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/shared-with-me",
    response_model=List[ShareResponse],
    summary="Get templates shared with me",
)
async def get_shared_with_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[ShareResponse]:
    """Get templates shared with the current user."""
    service = get_template_library_service(db)

    # Get user's organization IDs
    org_ids = [current_user.default_organization_id] if current_user.default_organization_id else []

    shares = service.get_shared_with_me(current_user.id, org_ids)

    return [
        ShareResponse(
            id=str(s.id),
            template_id=str(s.template_id),
            shared_with_user_id=str(s.shared_with_user_id) if s.shared_with_user_id else None,
            shared_with_org_id=str(s.shared_with_org_id) if s.shared_with_org_id else None,
            permission=s.permission,
            is_accepted=s.is_accepted,
            expires_at=s.expires_at.isoformat() if s.expires_at else None,
            created_at=s.created_at.isoformat(),
        )
        for s in shares
    ]


@router.post(
    "/shares/{share_id}/accept",
    response_model=ShareResponse,
    summary="Accept share invitation",
)
async def accept_share(
    share_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ShareResponse:
    """Accept a template share invitation."""
    service = get_template_library_service(db)

    try:
        share = service.accept_share(share_id)

        return ShareResponse(
            id=str(share.id),
            template_id=str(share.template_id),
            shared_with_user_id=str(share.shared_with_user_id) if share.shared_with_user_id else None,
            shared_with_org_id=str(share.shared_with_org_id) if share.shared_with_org_id else None,
            permission=share.permission,
            is_accepted=share.is_accepted,
            expires_at=share.expires_at.isoformat() if share.expires_at else None,
            created_at=share.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke share",
)
async def revoke_share(
    share_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Revoke a template share."""
    service = get_template_library_service(db)
    service.revoke_share(share_id)


# ==================== Fork Endpoints ====================

@router.post(
    "/templates/{template_id}/fork",
    response_model=ForkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Fork template",
)
async def fork_template(
    template_id: uuid.UUID,
    request: ForkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ForkResponse:
    """Fork (copy) a template to create your own version."""
    service = get_template_library_service(db)

    try:
        template, fork = service.fork_template(
            template_id=template_id,
            user_id=current_user.id,
            new_name=request.new_name,
            reason=request.reason,
        )

        return ForkResponse(
            original_template_id=str(template_id),
            forked_template_id=str(template.id),
            forked_template_name=template.filename,
            fork_id=str(fork.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/templates/{template_id}/fork-count",
    summary="Get fork count",
)
async def get_fork_count(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Get the number of times a template has been forked."""
    service = get_template_library_service(db)
    count = service.get_fork_count(template_id)

    return {"template_id": str(template_id), "fork_count": count}


# ==================== Review Endpoints ====================

@router.post(
    "/templates/{template_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add review",
)
async def add_review(
    template_id: uuid.UUID,
    request: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ReviewResponse:
    """Add a review for a template."""
    service = get_template_library_service(db)

    review = service.add_review(
        template_id=template_id,
        user_id=current_user.id,
        rating=request.rating,
        title=request.title,
        content=request.content,
        pros=request.pros,
        cons=request.cons,
        use_case=request.use_case,
        experience_level=request.experience_level,
    )

    return ReviewResponse(
        id=str(review.id),
        template_id=str(review.template_id),
        user_id=str(review.user_id),
        rating=review.rating,
        title=review.title,
        content=review.content,
        pros=review.pros or [],
        cons=review.cons or [],
        use_case=review.use_case,
        experience_level=review.experience_level,
        is_verified_purchase=review.is_verified_purchase,
        helpful_count=review.helpful_count,
        not_helpful_count=review.not_helpful_count,
        created_at=review.created_at.isoformat(),
    )


@router.get(
    "/templates/{template_id}/reviews",
    response_model=List[ReviewResponse],
    summary="Get reviews",
)
async def get_reviews(
    template_id: uuid.UUID,
    sort_by: str = Query(default="helpful", pattern="^(helpful|recent|rating_high|rating_low)$"),
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> List[ReviewResponse]:
    """Get reviews for a template."""
    service = get_template_library_service(db)
    reviews = service.get_reviews(template_id, limit, offset, sort_by)

    return [
        ReviewResponse(
            id=str(r.id),
            template_id=str(r.template_id),
            user_id=str(r.user_id),
            rating=r.rating,
            title=r.title,
            content=r.content,
            pros=r.pros or [],
            cons=r.cons or [],
            use_case=r.use_case,
            experience_level=r.experience_level,
            is_verified_purchase=r.is_verified_purchase,
            helpful_count=r.helpful_count,
            not_helpful_count=r.not_helpful_count,
            created_at=r.created_at.isoformat(),
        )
        for r in reviews
    ]


@router.post(
    "/reviews/{review_id}/vote",
    summary="Vote on review",
)
async def vote_review(
    review_id: uuid.UUID,
    request: ReviewVoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Vote on whether a review is helpful."""
    service = get_template_library_service(db)
    service.vote_review(review_id, current_user.id, request.is_helpful)

    return {"message": "Vote recorded"}


# ==================== Collection Endpoints ====================

@router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create collection",
)
async def create_collection(
    request: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CollectionResponse:
    """Create a template collection."""
    service = get_template_library_service(db)

    visibility_map = {
        "private": TemplateVisibility.PRIVATE,
        "organization": TemplateVisibility.ORGANIZATION,
        "public": TemplateVisibility.PUBLIC,
    }

    collection = service.create_collection(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        visibility=visibility_map.get(request.visibility, TemplateVisibility.PRIVATE),
    )

    return CollectionResponse(
        id=str(collection.id),
        name=collection.name,
        description=collection.description,
        slug=collection.slug,
        visibility=collection.visibility.value,
        template_count=collection.template_count,
        follower_count=collection.follower_count,
        is_featured=collection.is_featured,
        created_at=collection.created_at.isoformat(),
    )


@router.post(
    "/collections/{collection_id}/templates",
    status_code=status.HTTP_201_CREATED,
    summary="Add template to collection",
)
async def add_to_collection(
    collection_id: uuid.UUID,
    request: CollectionTemplateAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Add a template to a collection."""
    service = get_template_library_service(db)

    service.add_to_collection(
        collection_id=collection_id,
        template_id=uuid.UUID(request.template_id),
        notes=request.notes,
    )

    return {"message": "Template added to collection"}


@router.delete(
    "/collections/{collection_id}/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove from collection",
)
async def remove_from_collection(
    collection_id: uuid.UUID,
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Remove a template from a collection."""
    service = get_template_library_service(db)
    service.remove_from_collection(collection_id, template_id)


@router.post(
    "/collections/{collection_id}/follow",
    summary="Follow collection",
)
async def follow_collection(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Follow a collection."""
    service = get_template_library_service(db)
    service.follow_collection(collection_id, current_user.id)

    return {"message": "Now following collection"}


@router.delete(
    "/collections/{collection_id}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unfollow collection",
)
async def unfollow_collection(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Unfollow a collection."""
    service = get_template_library_service(db)
    service.unfollow_collection(collection_id, current_user.id)


# ==================== Usage Tracking ====================

@router.post(
    "/templates/{template_id}/track",
    summary="Track template usage",
)
async def track_usage(
    template_id: uuid.UUID,
    action: str = Query(..., pattern="^(viewed|downloaded|used|cloned)$"),
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Track template usage for analytics."""
    service = get_template_library_service(db)

    service.record_usage(
        template_id=template_id,
        action=action,
        user_id=current_user.id,
        organization_id=current_user.default_organization_id,
        source=source,
    )

    return {"message": "Usage tracked"}


@router.get(
    "/templates/{template_id}/stats",
    response_model=UsageStatsResponse,
    summary="Get usage stats",
)
async def get_usage_stats(
    template_id: uuid.UUID,
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_db),
) -> UsageStatsResponse:
    """Get usage statistics for a template."""
    service = get_template_library_service(db)
    stats = service.get_usage_stats(template_id, days)

    return UsageStatsResponse(**stats)


# ==================== Category Endpoints ====================

@router.get(
    "/categories",
    response_model=List[CategoryResponse],
    summary="List categories",
)
async def list_categories(
    parent_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
) -> List[CategoryResponse]:
    """List template categories."""
    service = get_template_library_service(db)
    categories = service.get_categories(parent_id)

    def category_to_response(cat) -> CategoryResponse:
        return CategoryResponse(
            id=str(cat.id),
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            icon=cat.icon,
            color=cat.color,
            template_count=cat.template_count,
            children=[category_to_response(c) for c in (cat.children or [])],
        )

    return [category_to_response(c) for c in categories]
