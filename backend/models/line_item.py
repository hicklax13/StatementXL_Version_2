"""
LineItem model for storing individual extracted line items.

Represents a single financial line item with value, location, and confidence.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, JSON
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.types import UUID


class LineItem(Base):
    """
    SQLAlchemy model for extracted line items.

    Attributes:
        id: Unique identifier (UUID).
        extract_id: Foreign key to the parent extract.
        label: Line item label/name.
        value: Parsed numeric value (Decimal for precision).
        raw_value: Original text value as extracted.
        source_page: PDF page number (1-indexed).
        bbox: Bounding box coordinates [x0, y0, x1, y1].
        confidence: Confidence score for this line item (0-1).
        row_index: Row position in the source table.
        column_index: Column position in the source table.
        created_at: Timestamp when line item was created.
    """

    __tablename__ = "line_items"

    id: uuid.UUID = Column(
        UUID(),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    extract_id: uuid.UUID = Column(
        UUID(),
        ForeignKey("extracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: str = Column(String(500), nullable=True)
    value: Optional[Decimal] = Column(Numeric(precision=20, scale=4), nullable=True)
    raw_value: str = Column(Text, nullable=False)
    source_page: int = Column(Integer, nullable=False)
    bbox: List[float] = Column(JSON, nullable=True)  # [x0, y0, x1, y1]
    confidence: float = Column(Float, nullable=True)
    row_index: int = Column(Integer, nullable=True)
    column_index: int = Column(Integer, nullable=True)
    created_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    extract = relationship("Extract", back_populates="line_items")

    def __repr__(self) -> str:
        return f"<LineItem(id={self.id}, label='{self.label}', value={self.value})>"
