"""
Search API routes.

Provides advanced search and filtering endpoints.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

import structlog
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.dependencies import get_current_active_user
from backend.models.user import User
from backend.services.search_service import (
    get_search_service,
    SearchQuery,
    Filter,
    SortField,
    FilterOperator,
    SortOrder,
    parse_filters,
    parse_sort,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# ==================== Schemas ====================

class SearchRequest(BaseModel):
    """Search request body."""
    query: Optional[str] = Field(None, description="Search query text")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filter conditions")
    sort: Optional[str] = Field(None, description="Sort fields (e.g., '-created_at,name')")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class FacetValue(BaseModel):
    """Facet value with count."""
    value: Any
    count: int


class FacetResponse(BaseModel):
    """Facet response."""
    field: str
    label: str
    values: List[FacetValue]


class SearchResponse(BaseModel):
    """Search response."""
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
    facets: List[FacetResponse]
    query_time_ms: float


class DocumentSearchResult(BaseModel):
    """Document search result."""
    id: str
    filename: str
    status: str
    page_count: Optional[int]
    created_at: str


class TemplateSearchResult(BaseModel):
    """Template search result."""
    id: str
    template_id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    industry: Optional[str]
    rating: float
    use_count: int
    is_featured: bool


# ==================== Endpoints ====================

@router.get(
    "/documents",
    response_model=SearchResponse,
    summary="Search documents",
)
async def search_documents(
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[datetime] = Query(None, description="Created after"),
    date_to: Optional[datetime] = Query(None, description="Created before"),
    sort: Optional[str] = Query("-created_at", description="Sort fields"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SearchResponse:
    """
    Search documents with filtering and pagination.

    Filters:
    - status: Document status (pending, processing, completed, failed)
    - date_from: Created after date
    - date_to: Created before date

    Sort:
    - Use field name for ascending, -field for descending
    - Multiple fields: -created_at,filename
    """
    service = get_search_service(db)

    result = service.search_documents(
        query=q,
        status=status,
        user_id=current_user.id,
        organization_id=current_user.default_organization_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    return SearchResponse(
        items=[
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "page_count": doc.page_count,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        facets=[
            FacetResponse(
                field=f.field,
                label=f.label,
                values=[FacetValue(**v) for v in f.values],
            )
            for f in result.facets
        ],
        query_time_ms=result.query_time_ms,
    )


@router.get(
    "/templates",
    response_model=SearchResponse,
    summary="Search templates",
)
async def search_templates(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    featured: Optional[bool] = Query(None, description="Filter featured only"),
    sort: Optional[str] = Query("-use_count", description="Sort fields"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Search template library with filtering and facets.

    Returns public templates with category and industry facets.
    """
    service = get_search_service(db)

    result = service.search_templates(
        query=q,
        category=category,
        industry=industry,
        featured=featured,
        page=page,
        page_size=page_size,
    )

    return SearchResponse(
        items=[
            {
                "id": str(t.id),
                "template_id": str(t.template_id),
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "industry": t.industry,
                "rating": t.rating,
                "use_count": t.use_count,
                "is_featured": t.is_featured,
            }
            for t in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        facets=[
            FacetResponse(
                field=f.field,
                label=f.label,
                values=[FacetValue(**v) for v in f.values],
            )
            for f in result.facets
        ],
        query_time_ms=result.query_time_ms,
    )


@router.post(
    "/advanced",
    response_model=SearchResponse,
    summary="Advanced search",
)
async def advanced_search(
    request: SearchRequest,
    entity: str = Query(..., description="Entity type to search (documents, templates)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SearchResponse:
    """
    Advanced search with flexible filters.

    Supports complex filter operators:
    - eq: Equal
    - ne: Not equal
    - gt/gte: Greater than (or equal)
    - lt/lte: Less than (or equal)
    - in: In list (comma-separated)
    - like/ilike: Pattern matching
    - between: Range (comma-separated values)

    Example filter: {"status__in": "completed,failed", "created_at__gte": "2024-01-01"}
    """
    service = get_search_service(db)

    # Parse filters
    filters = []
    if request.filters:
        filters = parse_filters(request.filters)

    # Parse sort
    sort_fields = parse_sort(request.sort) if request.sort else []

    # Determine model based on entity
    from backend.models.document import Document
    from backend.models.mapping_profile import TemplateLibraryItem

    model_map = {
        "documents": Document,
        "templates": TemplateLibraryItem,
    }

    model = model_map.get(entity)
    if not model:
        from fastapi import HTTPException
        raise HTTPException(400, f"Unknown entity type: {entity}")

    # Add user filter for documents
    if entity == "documents":
        filters.append(Filter("user_id", FilterOperator.EQ, current_user.id))

    # Build search query
    search_query = SearchQuery(
        query=request.query,
        filters=filters,
        sort=sort_fields if sort_fields else [SortField("created_at", SortOrder.DESC)],
        page=request.page,
        page_size=request.page_size,
        search_fields=["filename"] if entity == "documents" else ["name", "description"],
    )

    result = service.search(model, search_query)

    # Serialize items based on entity type
    if entity == "documents":
        items = [
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "page_count": doc.page_count,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in result.items
        ]
    else:
        items = [
            {
                "id": str(t.id),
                "template_id": str(t.template_id),
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "industry": t.industry,
            }
            for t in result.items
        ]

    return SearchResponse(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        facets=[
            FacetResponse(
                field=f.field,
                label=f.label,
                values=[FacetValue(**v) for v in f.values],
            )
            for f in result.facets
        ],
        query_time_ms=result.query_time_ms,
    )


@router.get(
    "/suggestions",
    summary="Get search suggestions",
)
async def get_suggestions(
    q: str = Query(..., min_length=2, description="Search query"),
    entity: str = Query("all", description="Entity type (documents, templates, all)"),
    limit: int = Query(10, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, List[str]]:
    """
    Get search suggestions based on partial query.

    Returns suggestions grouped by entity type.
    """
    from backend.models.document import Document
    from backend.models.mapping_profile import TemplateLibraryItem

    suggestions = {}

    if entity in ("all", "documents"):
        # Note: Document model doesn't have user_id, so we just filter by filename
        # In production, add user association to Document model
        docs = db.query(Document.filename).filter(
            Document.filename.ilike(f"%{q}%"),
        ).limit(limit).all()
        suggestions["documents"] = [d.filename for d in docs]

    if entity in ("all", "templates"):
        templates = db.query(TemplateLibraryItem.name).filter(
            TemplateLibraryItem.is_public == True,
            TemplateLibraryItem.name.ilike(f"%{q}%"),
        ).limit(limit).all()
        suggestions["templates"] = [t.name for t in templates]

    return suggestions


@router.get(
    "/recent",
    summary="Get recent searches",
)
async def get_recent_searches(
    limit: int = Query(10, le=20),
    current_user: User = Depends(get_current_active_user),
) -> List[str]:
    """
    Get user's recent search queries.

    Note: Requires search history tracking (stored in user preferences or separate table).
    """
    # For now, return empty list
    # In production, this would query a search_history table
    return []
