"""
Template database models.

Defines models for storing parsed Excel templates and their structure.
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


class TemplateStatus(enum.Enum):
    """Template processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CellType(enum.Enum):
    """Types of cells in a template."""

    INPUT = "input"  # User inputs data
    CALCULATED = "calculated"  # Contains formula
    LABEL = "label"  # Text label/header
    EMPTY = "empty"  # Empty cell


class Template(Base):
    """
    Represents an uploaded Excel template.

    Stores metadata about the template file and its processing status.
    """

    __tablename__ = "templates"

    id = Column(
        UUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    status = Column(
        Enum(TemplateStatus),
        default=TemplateStatus.PENDING,
        nullable=False,
    )
    sheet_count = Column(Integer)
    error_message = Column(Text)

    # Metadata from parsing
    extra_data = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    structure = relationship(
        "TemplateStructure",
        back_populates="template",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Template(id={self.id}, filename={self.filename})>"


class TemplateStructure(Base):
    """
    Stores the parsed structure of a template.

    Contains detected sections, periods, and semantic mappings.
    """

    __tablename__ = "template_structures"

    id = Column(
        UUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    template_id = Column(
        UUID(),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Detected sections (JSON: [{name, sheet, start_row, end_row, type}])
    sections = Column(JSON, default=list)

    # Detected periods (JSON: [{column, label, start_date, end_date, frequency}])
    periods = Column(JSON, default=list)

    # Sheet metadata (JSON: {sheet_name: {rows, cols, active_range}})
    sheets = Column(JSON, default=dict)

    # Formula dependency graph (JSON serialized for storage)
    dependency_graph = Column(JSON, default=dict)

    # Overall confidence score
    confidence_score = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    template = relationship("Template", back_populates="structure")
    cells = relationship(
        "TemplateCell",
        back_populates="structure",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TemplateStructure(id={self.id}, template_id={self.template_id})>"


class TemplateCell(Base):
    """
    Represents a cell in a template with semantic information.

    Stores cell location, type, formula, and ontology mapping.
    """

    __tablename__ = "template_cells"

    id = Column(
        UUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    structure_id = Column(
        UUID(),
        ForeignKey("template_structures.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Cell location
    sheet = Column(String(100), nullable=False)
    row = Column(Integer, nullable=False)
    column = Column(Integer, nullable=False)
    address = Column(String(20), nullable=False)  # e.g., "A1", "B2"

    # Cell content
    value = Column(Text)  # Current value
    formula = Column(Text)  # Formula if any
    cell_type = Column(Enum(CellType), default=CellType.EMPTY)

    # Semantic mapping
    ontology_id = Column(String(50))  # e.g., "is:revenue"
    ontology_label = Column(String(255))
    mapping_confidence = Column(Float, default=0.0)

    # Period association
    period_index = Column(Integer)  # Which period column this belongs to

    # Section association
    section_name = Column(String(100))

    # Formatting hints
    is_header = Column(Boolean, default=False)
    is_total = Column(Boolean, default=False)
    indent_level = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    structure = relationship("TemplateStructure", back_populates="cells")

    def __repr__(self) -> str:
        return f"<TemplateCell(id={self.id}, address={self.address})>"
