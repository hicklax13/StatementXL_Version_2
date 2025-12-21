"""
Document model for storing uploaded PDF metadata.

Represents an immutable record of an uploaded financial document.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database import Base


class DocumentStatus(str, enum.Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    """
    SQLAlchemy model for uploaded PDF documents.

    Attributes:
        id: Unique identifier (UUID).
        filename: Original filename of the uploaded PDF.
        file_path: Storage path where the PDF is saved.
        page_count: Number of pages in the document.
        status: Current processing status.
        error_message: Error message if processing failed.
        created_at: Timestamp when document was uploaded.
        updated_at: Timestamp of last update.
    """

    __tablename__ = "documents"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    filename: str = Column(String(255), nullable=False)
    file_path: str = Column(String(500), nullable=False)
    page_count: int = Column(Integer, nullable=True)
    status: DocumentStatus = Column(
        Enum(DocumentStatus),
        default=DocumentStatus.PENDING,
        nullable=False,
    )
    error_message: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    extracts = relationship("Extract", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}', status={self.status})>"
