"""
Advanced Search Service.

Provides full-text search, filtering, and faceted search capabilities.
"""
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Type, TypeVar
from dataclasses import dataclass, field
from enum import Enum

import structlog
from sqlalchemy import or_, and_, func, desc, asc, text
from sqlalchemy.orm import Session, Query

from backend.database import Base
from backend.models.document import Document
from backend.models.template import Template
from backend.models.mapping_profile import TemplateLibraryItem

logger = structlog.get_logger(__name__)

T = TypeVar('T', bound=Base)


class SortOrder(str, Enum):
    """Sort order options."""
    ASC = "asc"
    DESC = "desc"


class FilterOperator(str, Enum):
    """Filter operators."""
    EQ = "eq"           # Equal
    NE = "ne"           # Not equal
    GT = "gt"           # Greater than
    GTE = "gte"         # Greater than or equal
    LT = "lt"           # Less than
    LTE = "lte"         # Less than or equal
    IN = "in"           # In list
    NIN = "nin"         # Not in list
    LIKE = "like"       # SQL LIKE
    ILIKE = "ilike"     # Case-insensitive LIKE
    BETWEEN = "between" # Between two values
    NULL = "null"       # Is null
    NOTNULL = "notnull" # Is not null


@dataclass
class Filter:
    """Single filter condition."""
    field: str
    operator: FilterOperator
    value: Any


@dataclass
class SortField:
    """Sort specification."""
    field: str
    order: SortOrder = SortOrder.DESC


@dataclass
class SearchQuery:
    """Complete search query specification."""
    query: Optional[str] = None
    filters: List[Filter] = field(default_factory=list)
    sort: List[SortField] = field(default_factory=list)
    page: int = 1
    page_size: int = 20
    search_fields: List[str] = field(default_factory=list)
    include_count: bool = True
    highlight: bool = False


@dataclass
class Facet:
    """Facet definition."""
    field: str
    label: str
    values: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SearchResult:
    """Search result with metadata."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    facets: List[Facet] = field(default_factory=list)
    query_time_ms: float = 0
    highlights: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "facets": [
                {"field": f.field, "label": f.label, "values": f.values}
                for f in self.facets
            ],
            "query_time_ms": self.query_time_ms,
            "highlights": self.highlights,
        }


class SearchService:
    """
    Advanced search service with filtering, sorting, and facets.
    """

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        model: Type[T],
        query: SearchQuery,
        base_query: Query = None,
        facet_fields: List[str] = None,
    ) -> SearchResult:
        """
        Execute search query on a model.

        Args:
            model: SQLAlchemy model class
            query: Search query specification
            base_query: Optional base query to extend
            facet_fields: Fields to calculate facets for

        Returns:
            SearchResult with items and metadata
        """
        import time
        start_time = time.time()

        # Start with base query or model query
        db_query = base_query if base_query is not None else self.db.query(model)

        # Apply text search
        if query.query and query.search_fields:
            db_query = self._apply_text_search(db_query, model, query.query, query.search_fields)

        # Apply filters
        for filter_spec in query.filters:
            db_query = self._apply_filter(db_query, model, filter_spec)

        # Get total count before pagination
        total = 0
        if query.include_count:
            total = db_query.count()

        # Apply sorting
        for sort_spec in query.sort:
            db_query = self._apply_sort(db_query, model, sort_spec)

        # Apply pagination
        offset = (query.page - 1) * query.page_size
        db_query = db_query.offset(offset).limit(query.page_size)

        # Execute query
        items = db_query.all()

        # Calculate facets if requested
        facets = []
        if facet_fields:
            facets = self._calculate_facets(model, facet_fields, query.filters)

        # Calculate highlights if requested
        highlights = {}
        if query.highlight and query.query:
            highlights = self._calculate_highlights(items, query.query, query.search_fields)

        query_time = (time.time() - start_time) * 1000
        total_pages = (total + query.page_size - 1) // query.page_size if total > 0 else 0

        return SearchResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
            facets=facets,
            query_time_ms=query_time,
            highlights=highlights,
        )

    def _apply_text_search(
        self,
        query: Query,
        model: Type[T],
        search_text: str,
        search_fields: List[str],
    ) -> Query:
        """Apply text search across multiple fields."""
        if not search_text or not search_fields:
            return query

        # Escape special characters
        search_text = search_text.replace("%", "\\%").replace("_", "\\_")
        search_pattern = f"%{search_text}%"

        conditions = []
        for field_name in search_fields:
            if hasattr(model, field_name):
                column = getattr(model, field_name)
                conditions.append(column.ilike(search_pattern))

        if conditions:
            query = query.filter(or_(*conditions))

        return query

    def _apply_filter(
        self,
        query: Query,
        model: Type[T],
        filter_spec: Filter,
    ) -> Query:
        """Apply single filter to query."""
        if not hasattr(model, filter_spec.field):
            logger.warning("unknown_filter_field", field=filter_spec.field)
            return query

        column = getattr(model, filter_spec.field)

        if filter_spec.operator == FilterOperator.EQ:
            query = query.filter(column == filter_spec.value)
        elif filter_spec.operator == FilterOperator.NE:
            query = query.filter(column != filter_spec.value)
        elif filter_spec.operator == FilterOperator.GT:
            query = query.filter(column > filter_spec.value)
        elif filter_spec.operator == FilterOperator.GTE:
            query = query.filter(column >= filter_spec.value)
        elif filter_spec.operator == FilterOperator.LT:
            query = query.filter(column < filter_spec.value)
        elif filter_spec.operator == FilterOperator.LTE:
            query = query.filter(column <= filter_spec.value)
        elif filter_spec.operator == FilterOperator.IN:
            query = query.filter(column.in_(filter_spec.value))
        elif filter_spec.operator == FilterOperator.NIN:
            query = query.filter(~column.in_(filter_spec.value))
        elif filter_spec.operator == FilterOperator.LIKE:
            query = query.filter(column.like(f"%{filter_spec.value}%"))
        elif filter_spec.operator == FilterOperator.ILIKE:
            query = query.filter(column.ilike(f"%{filter_spec.value}%"))
        elif filter_spec.operator == FilterOperator.BETWEEN:
            if isinstance(filter_spec.value, (list, tuple)) and len(filter_spec.value) == 2:
                query = query.filter(column.between(filter_spec.value[0], filter_spec.value[1]))
        elif filter_spec.operator == FilterOperator.NULL:
            query = query.filter(column.is_(None))
        elif filter_spec.operator == FilterOperator.NOTNULL:
            query = query.filter(column.isnot(None))

        return query

    def _apply_sort(
        self,
        query: Query,
        model: Type[T],
        sort_spec: SortField,
    ) -> Query:
        """Apply sorting to query."""
        if not hasattr(model, sort_spec.field):
            logger.warning("unknown_sort_field", field=sort_spec.field)
            return query

        column = getattr(model, sort_spec.field)

        if sort_spec.order == SortOrder.ASC:
            query = query.order_by(asc(column))
        else:
            query = query.order_by(desc(column))

        return query

    def _calculate_facets(
        self,
        model: Type[T],
        facet_fields: List[str],
        filters: List[Filter],
    ) -> List[Facet]:
        """Calculate facet counts for fields."""
        facets = []

        for field_name in facet_fields:
            if not hasattr(model, field_name):
                continue

            column = getattr(model, field_name)

            # Build query for facet
            facet_query = self.db.query(
                column,
                func.count(column).label("count")
            )

            # Apply filters (except for this facet field)
            for filter_spec in filters:
                if filter_spec.field != field_name and hasattr(model, filter_spec.field):
                    facet_query = self._apply_filter(facet_query, model, filter_spec)

            # Group and order by count
            facet_query = facet_query.group_by(column).order_by(desc("count")).limit(50)

            values = [
                {"value": row[0], "count": row[1]}
                for row in facet_query.all()
                if row[0] is not None
            ]

            facets.append(Facet(
                field=field_name,
                label=field_name.replace("_", " ").title(),
                values=values,
            ))

        return facets

    def _calculate_highlights(
        self,
        items: List[Any],
        query: str,
        search_fields: List[str],
    ) -> Dict[str, List[str]]:
        """Calculate text highlights for search matches."""
        highlights = {}
        query_lower = query.lower()

        for item in items:
            item_id = str(getattr(item, 'id', id(item)))
            item_highlights = []

            for field_name in search_fields:
                value = getattr(item, field_name, None)
                if value and isinstance(value, str):
                    # Find matches and create highlight snippets
                    if query_lower in value.lower():
                        # Extract snippet around match
                        start = max(0, value.lower().find(query_lower) - 50)
                        end = min(len(value), start + 100 + len(query))
                        snippet = value[start:end]
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(value):
                            snippet = snippet + "..."
                        item_highlights.append(snippet)

            if item_highlights:
                highlights[item_id] = item_highlights

        return highlights

    # Convenience search methods
    def search_documents(
        self,
        query: str = None,
        status: str = None,
        user_id: uuid.UUID = None,
        organization_id: uuid.UUID = None,
        date_from: datetime = None,
        date_to: datetime = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResult:
        """Search documents with common filters."""
        filters = []

        if status:
            filters.append(Filter("status", FilterOperator.EQ, status))
        if user_id:
            filters.append(Filter("user_id", FilterOperator.EQ, user_id))
        if organization_id:
            filters.append(Filter("organization_id", FilterOperator.EQ, organization_id))
        if date_from:
            filters.append(Filter("created_at", FilterOperator.GTE, date_from))
        if date_to:
            filters.append(Filter("created_at", FilterOperator.LTE, date_to))

        search_query = SearchQuery(
            query=query,
            filters=filters,
            search_fields=["filename"],
            sort=[SortField("created_at", SortOrder.DESC)],
            page=page,
            page_size=page_size,
        )

        return self.search(
            Document,
            search_query,
            facet_fields=["status"],
        )

    def search_templates(
        self,
        query: str = None,
        category: str = None,
        industry: str = None,
        featured: bool = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResult:
        """Search template library."""
        filters = []

        if category:
            filters.append(Filter("category", FilterOperator.EQ, category))
        if industry:
            filters.append(Filter("industry", FilterOperator.EQ, industry))
        if featured is not None:
            filters.append(Filter("is_featured", FilterOperator.EQ, featured))

        # Only show public templates
        filters.append(Filter("is_public", FilterOperator.EQ, True))

        search_query = SearchQuery(
            query=query,
            filters=filters,
            search_fields=["name", "description"],
            sort=[
                SortField("is_featured", SortOrder.DESC),
                SortField("use_count", SortOrder.DESC),
            ],
            page=page,
            page_size=page_size,
        )

        return self.search(
            TemplateLibraryItem,
            search_query,
            facet_fields=["category", "industry"],
        )


def get_search_service(db: Session) -> SearchService:
    """Factory function to get search service instance."""
    return SearchService(db)


# Query parameter parsing utilities
def parse_filters(filter_params: Dict[str, str]) -> List[Filter]:
    """
    Parse filter parameters from query string.

    Format: field__operator=value
    Example: created_at__gte=2024-01-01

    Args:
        filter_params: Dictionary of filter parameters

    Returns:
        List of Filter objects
    """
    filters = []
    operator_map = {
        "eq": FilterOperator.EQ,
        "ne": FilterOperator.NE,
        "gt": FilterOperator.GT,
        "gte": FilterOperator.GTE,
        "lt": FilterOperator.LT,
        "lte": FilterOperator.LTE,
        "in": FilterOperator.IN,
        "nin": FilterOperator.NIN,
        "like": FilterOperator.LIKE,
        "ilike": FilterOperator.ILIKE,
        "between": FilterOperator.BETWEEN,
        "null": FilterOperator.NULL,
        "notnull": FilterOperator.NOTNULL,
    }

    for key, value in filter_params.items():
        if "__" in key:
            field, op_str = key.rsplit("__", 1)
            operator = operator_map.get(op_str, FilterOperator.EQ)
        else:
            field = key
            operator = FilterOperator.EQ

        # Parse value for special operators
        if operator == FilterOperator.IN:
            value = value.split(",")
        elif operator == FilterOperator.BETWEEN:
            value = value.split(",")
        elif operator in (FilterOperator.NULL, FilterOperator.NOTNULL):
            value = None

        filters.append(Filter(field, operator, value))

    return filters


def parse_sort(sort_param: str) -> List[SortField]:
    """
    Parse sort parameter.

    Format: field1,-field2 (- prefix for descending)

    Args:
        sort_param: Sort parameter string

    Returns:
        List of SortField objects
    """
    if not sort_param:
        return []

    sorts = []
    for field in sort_param.split(","):
        field = field.strip()
        if field.startswith("-"):
            sorts.append(SortField(field[1:], SortOrder.DESC))
        else:
            sorts.append(SortField(field, SortOrder.ASC))

    return sorts
