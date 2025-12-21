"""
Mapping API routes.

Provides endpoints for creating and managing mappings between extracts and templates.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.mapping import (
    MappingGraph,
    MappingAssignment,
    Conflict,
    MappingStatus,
    ConflictSeverity,
    ConflictType,
)
from backend.services.mapping_engine import (
    MappingEngine,
    ExtractedItem,
    TemplateTarget,
    get_mapping_engine,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# Request/Response Models
class ExtractedItemRequest(BaseModel):
    """Request model for an extracted item."""

    label: str
    value: Optional[float] = None
    raw_value: str = ""
    ontology_id: Optional[str] = None
    confidence: float = 0.0
    page: int = 1
    row_index: int = 0


class TemplateTargetRequest(BaseModel):
    """Request model for a template target."""

    sheet: str
    address: str
    ontology_id: Optional[str] = None
    period: Optional[str] = None
    is_input: bool = True
    row_label: Optional[str] = None


class CreateMappingRequest(BaseModel):
    """Request model for creating a mapping."""

    extract_id: Optional[str] = None
    template_id: Optional[str] = None
    extracted_items: List[ExtractedItemRequest]
    template_targets: List[TemplateTargetRequest]
    period: Optional[str] = None


class AssignmentResponse(BaseModel):
    """Response model for a mapping assignment."""

    source_label: str
    source_value: Optional[float]
    source_ontology_id: Optional[str]
    target_sheet: str
    target_address: str
    target_ontology_id: Optional[str]
    confidence: float
    match_type: str
    is_auto_mapped: bool


class ConflictResponse(BaseModel):
    """Response model for a conflict."""

    id: str
    conflict_type: str
    severity: str
    description: str
    source_label: Optional[str]
    target_address: Optional[str]
    suggestions: List[str]
    is_resolved: bool


class MappingResponse(BaseModel):
    """Response model for a mapping."""

    mapping_id: str
    status: str
    total_items: int
    mapped_count: int
    auto_mapped_count: int
    conflict_count: int
    average_confidence: float
    assignments: List[AssignmentResponse]
    conflicts: List[ConflictResponse]


class MappingStatusResponse(BaseModel):
    """Response model for mapping status."""

    mapping_id: str
    status: str
    mapped_count: int
    conflict_count: int
    created_at: str


class ResolveConflictRequest(BaseModel):
    """Request model for resolving a conflict."""

    conflict_id: str
    resolution: str
    resolved_by: Optional[str] = None


@router.post(
    "/map",
    response_model=MappingResponse,
    summary="Create a mapping",
    description="Map extracted items to template cells.",
)
async def create_mapping(
    request: CreateMappingRequest,
    db: Session = Depends(get_db),
) -> MappingResponse:
    """
    Create a mapping between extracted items and template.

    Args:
        request: Mapping request with items and targets.
        db: Database session.

    Returns:
        Mapping result with assignments and conflicts.
    """
    logger.info(
        "Creating mapping",
        items=len(request.extracted_items),
        targets=len(request.template_targets),
    )

    # Convert request to engine types
    extracted_items = [
        ExtractedItem(
            label=item.label,
            value=Decimal(str(item.value)) if item.value is not None else None,
            raw_value=item.raw_value,
            ontology_id=item.ontology_id,
            confidence=item.confidence,
            page=item.page,
            row_index=item.row_index,
        )
        for item in request.extracted_items
    ]

    template_targets = [
        TemplateTarget(
            sheet=target.sheet,
            address=target.address,
            ontology_id=target.ontology_id,
            period=target.period,
            is_input=target.is_input,
            row_label=target.row_label,
        )
        for target in request.template_targets
    ]

    # Run mapping engine
    engine = get_mapping_engine()
    result = engine.map(extracted_items, template_targets, request.period)

    # Create database records
    mapping_graph = MappingGraph(
        extract_id=uuid.UUID(request.extract_id) if request.extract_id else None,
        template_id=uuid.UUID(request.template_id) if request.template_id else None,
        status=MappingStatus.COMPLETED if not result.conflicts else MappingStatus.NEEDS_REVIEW,
        total_items=result.total_items,
        mapped_items=result.mapped_count,
        auto_mapped_items=result.auto_mapped_count,
        conflict_count=len(result.conflicts),
        average_confidence=result.average_confidence,
    )
    db.add(mapping_graph)
    db.flush()

    # Create assignment records
    for assignment in result.assignments:
        db_assignment = MappingAssignment(
            mapping_graph_id=mapping_graph.id,
            source_label=assignment.source.label,
            source_value=str(assignment.source.value) if assignment.source.value else None,
            source_ontology_id=assignment.source.ontology_id,
            source_page=assignment.source.page,
            source_row=assignment.source.row_index,
            target_sheet=assignment.target.sheet,
            target_address=assignment.target.address,
            target_ontology_id=assignment.target.ontology_id,
            target_period=assignment.target.period,
            confidence=assignment.score,
            match_type=assignment.match_type,
            is_auto_mapped=assignment.is_auto,
        )
        db.add(db_assignment)

    # Create conflict records
    conflict_responses = []
    for conflict in result.conflicts:
        severity_map = {
            "critical": ConflictSeverity.CRITICAL,
            "high": ConflictSeverity.HIGH,
            "medium": ConflictSeverity.MEDIUM,
            "low": ConflictSeverity.LOW,
        }
        type_map = {
            "missing_required": ConflictType.MISSING_REQUIRED,
            "unmapped_source": ConflictType.LOW_CONFIDENCE,
            "low_confidence": ConflictType.LOW_CONFIDENCE,
            "validation_failure": ConflictType.VALIDATION_FAILURE,
            "formula_break": ConflictType.FORMULA_BREAK,
        }

        db_conflict = Conflict(
            mapping_graph_id=mapping_graph.id,
            conflict_type=type_map.get(conflict.conflict_type, ConflictType.LOW_CONFIDENCE),
            severity=severity_map.get(conflict.severity, ConflictSeverity.MEDIUM),
            description=conflict.description,
            source_label=conflict.source_label,
            target_address=conflict.target_address,
            suggestions=conflict.suggestions,
        )
        db.add(db_conflict)
        db.flush()

        conflict_responses.append(ConflictResponse(
            id=str(db_conflict.id),
            conflict_type=conflict.conflict_type,
            severity=conflict.severity,
            description=conflict.description,
            source_label=conflict.source_label,
            target_address=conflict.target_address,
            suggestions=conflict.suggestions,
            is_resolved=False,
        ))

    db.commit()

    # Build response
    assignment_responses = [
        AssignmentResponse(
            source_label=a.source.label,
            source_value=float(a.source.value) if a.source.value else None,
            source_ontology_id=a.source.ontology_id,
            target_sheet=a.target.sheet,
            target_address=a.target.address,
            target_ontology_id=a.target.ontology_id,
            confidence=a.score,
            match_type=a.match_type,
            is_auto_mapped=a.is_auto,
        )
        for a in result.assignments
    ]

    return MappingResponse(
        mapping_id=str(mapping_graph.id),
        status=mapping_graph.status.value,
        total_items=result.total_items,
        mapped_count=result.mapped_count,
        auto_mapped_count=result.auto_mapped_count,
        conflict_count=len(result.conflicts),
        average_confidence=result.average_confidence,
        assignments=assignment_responses,
        conflicts=conflict_responses,
    )


@router.get(
    "/mapping/{mapping_id}",
    response_model=MappingStatusResponse,
    summary="Get mapping status",
)
async def get_mapping_status(
    mapping_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> MappingStatusResponse:
    """Get status of a mapping."""
    mapping = db.query(MappingGraph).filter(MappingGraph.id == mapping_id).first()

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found",
        )

    return MappingStatusResponse(
        mapping_id=str(mapping.id),
        status=mapping.status.value,
        mapped_count=mapping.mapped_items or 0,
        conflict_count=mapping.conflict_count or 0,
        created_at=mapping.created_at.isoformat(),
    )


@router.get(
    "/mapping/{mapping_id}/conflicts",
    response_model=List[ConflictResponse],
    summary="Get mapping conflicts",
)
async def get_mapping_conflicts(
    mapping_id: uuid.UUID,
    resolved: Optional[bool] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[ConflictResponse]:
    """Get conflicts for a mapping."""
    mapping = db.query(MappingGraph).filter(MappingGraph.id == mapping_id).first()

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found",
        )

    query = db.query(Conflict).filter(Conflict.mapping_graph_id == mapping_id)

    if resolved is not None:
        query = query.filter(Conflict.is_resolved == resolved)

    conflicts = query.all()

    return [
        ConflictResponse(
            id=str(c.id),
            conflict_type=c.conflict_type.value,
            severity=c.severity.value,
            description=c.description,
            source_label=c.source_label,
            target_address=c.target_address,
            suggestions=c.suggestions or [],
            is_resolved=c.is_resolved,
        )
        for c in conflicts
    ]


@router.put(
    "/mapping/{mapping_id}/conflicts/{conflict_id}/resolve",
    summary="Resolve a conflict",
)
async def resolve_conflict(
    mapping_id: uuid.UUID,
    conflict_id: uuid.UUID,
    request: ResolveConflictRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Resolve a mapping conflict."""
    conflict = db.query(Conflict).filter(
        Conflict.id == conflict_id,
        Conflict.mapping_graph_id == mapping_id,
    ).first()

    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conflict {conflict_id} not found",
        )

    conflict.is_resolved = True
    conflict.resolution = request.resolution
    conflict.resolved_by = request.resolved_by
    conflict.resolved_at = datetime.utcnow()

    # Update mapping status if all conflicts resolved
    mapping = db.query(MappingGraph).filter(MappingGraph.id == mapping_id).first()
    unresolved = db.query(Conflict).filter(
        Conflict.mapping_graph_id == mapping_id,
        Conflict.is_resolved == False,
    ).count()

    if unresolved == 0:
        mapping.status = MappingStatus.COMPLETED

    db.commit()

    return {"message": "Conflict resolved successfully"}
