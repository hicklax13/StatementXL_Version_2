"""
Extract model for storing extracted table data from documents.

Represents the extraction results from a PDF document.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from backend.database import Base


class Extract(Base):
    """
    SQLAlchemy model for document extraction results.

    Attributes:
        id: Unique identifier (UUID).
        document_id: Foreign key to the source document.
        tables_json: JSON blob containing extracted tables.
        confidence_score: Overall extraction confidence (0-1).
        metadata: Additional extraction metadata.
        created_at: Timestamp when extraction was performed.
    """

    __tablename__ = "extracts"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    document_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tables_json: List[Dict[str, Any]] = Column(JSON, nullable=False, default=list)
    confidence_score: float = Column(Float, nullable=True)
    metadata: Optional[Dict[str, Any]] = Column(JSON, nullable=True)
    created_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    document = relationship("Document", back_populates="extracts")
    line_items = relationship("LineItem", back_populates="extract", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Extract(id={self.id}, document_id={self.document_id}, confidence={self.confidence_score})>"
