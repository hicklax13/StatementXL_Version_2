"""
Learning and reuse database models.

Defines models for mapping profiles, feedback, and template library.
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
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import relationship

from backend.database import Base


class FeedbackType(enum.Enum):
    """Types of mapping feedback."""

    ACCEPTED = "accepted"  # Analyst accepted suggestion
    REJECTED = "rejected"  # Analyst rejected suggestion
    CORRECTED = "corrected"  # Analyst provided correction
    MANUAL = "manual"  # Analyst entered manually


class MappingProfile(Base):
    """
    Stores learned mappings for reuse.

    Profiles are created per company or template to enable
    auto-applying previous decisions.
    """

    __tablename__ = "mapping_profiles"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Profile identification
    name = Column(String(255), nullable=False)
    company_name = Column(String(255), index=True)
    industry = Column(String(100), index=True)

    # Template association (optional)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Learned mappings (JSON: [{source_pattern, target_ontology_id, confidence}])
    mappings = Column(JSON, default=list)

    # Statistics
    times_used = Column(Integer, default=0)
    auto_apply_success_rate = Column(Float, default=0.0)
    total_mappings = Column(Integer, default=0)

    # Metadata
    tags = Column(JSON, default=list)  # e.g., ["lbo", "dcf", "tech"]
    metadata = Column(JSON, default=dict)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    feedback = relationship(
        "MappingFeedback",
        back_populates="profile",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MappingProfile(id={self.id}, name={self.name})>"


class MappingFeedback(Base):
    """
    Records individual mapping decisions by analysts.

    Used to improve future auto-mapping accuracy.
    """

    __tablename__ = "mapping_feedback"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mapping_profiles.id", ondelete="CASCADE"),
        nullable=True,
    )
    mapping_graph_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mapping_graphs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Source pattern
    source_label = Column(String(255), nullable=False, index=True)
    source_ontology_id = Column(String(50))
    source_pattern = Column(String(255))  # Normalized pattern for matching

    # Target
    target_ontology_id = Column(String(50), nullable=False)
    target_label = Column(String(255))
    target_address = Column(String(50))

    # Feedback
    feedback_type = Column(Enum(FeedbackType), nullable=False)
    original_suggestion = Column(String(50))  # What was suggested
    final_decision = Column(String(50))  # What analyst chose

    # Quality metrics
    confidence_before = Column(Float)
    confidence_after = Column(Float, default=1.0)

    # User tracking
    user_id = Column(String(100))
    user_email = Column(String(255))

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("MappingProfile", back_populates="feedback")

    # Indexes for fast lookup
    __table_args__ = (
        Index('idx_source_pattern', 'source_pattern'),
        Index('idx_target_ontology', 'target_ontology_id'),
    )

    def __repr__(self) -> str:
        return f"<MappingFeedback(id={self.id}, source={self.source_label})>"


class TemplateLibraryItem(Base):
    """
    Curated template in the library for reuse.

    Includes metadata, tags, and thumbnail for discovery.
    """

    __tablename__ = "template_library"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Display info
    name = Column(String(255), nullable=False)
    description = Column(Text)
    thumbnail_url = Column(String(512))

    # Categorization
    category = Column(String(100), index=True)  # e.g., "lbo", "dcf", "valuation"
    industry = Column(String(100), index=True)
    tags = Column(JSON, default=list)

    # Search (for Postgres full-text search)
    search_vector = Column(Text)  # Concatenated searchable text

    # Usage stats
    download_count = Column(Integer, default=0)
    use_count = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)

    # Metadata
    author = Column(String(255))
    version = Column(String(50), default="1.0")
    is_featured = Column(Boolean, default=False)
    is_public = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    template = relationship("Template")

    def __repr__(self) -> str:
        return f"<TemplateLibraryItem(id={self.id}, name={self.name})>"
