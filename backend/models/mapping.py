"""
Mapping database models.

Defines models for storing mapping graphs, assignments, and conflicts.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.types import UUID


class MappingStatus(enum.Enum):
    """Mapping processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ConflictSeverity(enum.Enum):
    """Severity level for conflicts."""

    CRITICAL = "critical"  # Missing required data
    HIGH = "high"  # Validation failure
    MEDIUM = "medium"  # Ambiguous match
    LOW = "low"  # Optional data missing
    INFO = "info"  # FYI only


class ConflictType(enum.Enum):
    """Types of mapping conflicts."""

    MISSING_REQUIRED = "missing_required"
    AMBIGUOUS_MATCH = "ambiguous_match"
    VALIDATION_FAILURE = "validation_failure"
    PERIOD_MISMATCH = "period_mismatch"
    DUPLICATE_MAPPING = "duplicate_mapping"
    LOW_CONFIDENCE = "low_confidence"
    FORMULA_BREAK = "formula_break"


class MappingGraph(Base):
    """
    Represents a mapping between an Extract and a Template.

    Stores the complete mapping graph with assignments and conflicts.
    """

    __tablename__ = "mapping_graphs"

    id = Column(
        UUID(),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Source references
    extract_id = Column(
        UUID(),
        ForeignKey("extracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id = Column(
        UUID(),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    status = Column(
        Enum(MappingStatus),
        default=MappingStatus.PENDING,
        nullable=False,
    )

    # Mapping statistics
    total_items = Column(Integer, default=0)
    mapped_items = Column(Integer, default=0)
    auto_mapped_items = Column(Integer, default=0)  # Confidence >= 0.7
    conflict_count = Column(Integer, default=0)

    # Overall confidence
    average_confidence = Column(Float, default=0.0)

    # Full mapping graph as JSON
    graph_data = Column(JSON, default=dict)

    # Metadata
    extra_data = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assignments = relationship(
        "MappingAssignment",
        back_populates="mapping_graph",
        cascade="all, delete-orphan",
    )
    conflicts = relationship(
        "Conflict",
        back_populates="mapping_graph",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MappingGraph(id={self.id}, status={self.status.value})>"


class MappingAssignment(Base):
    """
    Represents a single mapping assignment: Extract item → Template cell.

    Stores the source, target, confidence, and lineage.
    """

    __tablename__ = "mapping_assignments"

    id = Column(
        UUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    mapping_graph_id = Column(
        UUID(),
        ForeignKey("mapping_graphs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Source (from Extract)
    source_label = Column(String(255), nullable=False)
    source_value = Column(Text)
    source_ontology_id = Column(String(50))
    source_page = Column(Integer)
    source_row = Column(Integer)

    # Target (Template cell)
    target_sheet = Column(String(100))
    target_address = Column(String(20))
    target_ontology_id = Column(String(50))
    target_period = Column(String(50))  # e.g., "2023", "Q1 2024"

    # Mapping quality
    confidence = Column(Float, default=0.0)
    match_type = Column(String(50))  # exact, ontology, embedding, manual
    is_auto_mapped = Column(Boolean, default=False)
    is_confirmed = Column(Boolean, default=False)

    # Lineage (for audit trail)
    lineage = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    mapping_graph = relationship("MappingGraph", back_populates="assignments")

    def __repr__(self) -> str:
        return f"<MappingAssignment(id={self.id}, source={self.source_label})>"


class Conflict(Base):
    """
    Represents a mapping conflict that needs review.

    Prioritized by severity for the review queue.
    """

    __tablename__ = "mapping_conflicts"

    id = Column(
        UUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    mapping_graph_id = Column(
        UUID(),
        ForeignKey("mapping_graphs.id", ondelete="CASCADE"),
        nullable=False,
    )

    conflict_type = Column(Enum(ConflictType), nullable=False)
    severity = Column(Enum(ConflictSeverity), nullable=False)

    # Description
    description = Column(Text, nullable=False)
    details = Column(JSON, default=dict)

    # Affected items
    source_label = Column(String(255))
    target_address = Column(String(50))

    # Suggestions for resolution
    suggestions = Column(JSON, default=list)

    # Resolution status
    is_resolved = Column(Boolean, default=False)
    resolution = Column(Text)
    resolved_by = Column(String(100))
    resolved_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    mapping_graph = relationship("MappingGraph", back_populates="conflicts")

    def __repr__(self) -> str:
        return f"<Conflict(id={self.id}, type={self.conflict_type.value})>"
