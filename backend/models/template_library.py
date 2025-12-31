"""
Enhanced Template Library models.

Provides models for template versioning, sharing, reviews, and categories.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional, List

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
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.types import UUID


class TemplateVisibility(enum.Enum):
    """Template visibility levels."""
    PRIVATE = "private"  # Only owner can see
    ORGANIZATION = "organization"  # Organization members can see
    PUBLIC = "public"  # Anyone can see


class TemplateCategory(Base):
    """
    Template category for organizing templates.

    Categories can be hierarchical with parent/child relationships.
    """
    __tablename__ = "template_categories"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    icon = Column(String(50))  # Icon name or emoji
    color = Column(String(20))  # Hex color code

    # Hierarchical categories
    parent_id = Column(UUID(), ForeignKey("template_categories.id"))

    # Ordering
    sort_order = Column(Integer, default=0)

    # Stats
    template_count = Column(Integer, default=0)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    parent = relationship("TemplateCategory", remote_side=[id], backref="children")

    def __repr__(self) -> str:
        return f"<TemplateCategory(name={self.name})>"


class TemplateVersion(Base):
    """
    Tracks versions of a template.

    Each version stores a snapshot of the template at a point in time.
    """
    __tablename__ = "template_versions"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Version info
    version_number = Column(String(20), nullable=False)  # Semantic versioning
    version_label = Column(String(100))  # Optional friendly name

    # Snapshot of template data
    file_path = Column(String(512), nullable=False)
    file_hash = Column(String(64))  # SHA-256 hash for integrity
    file_size = Column(Integer)

    # Structure snapshot (JSON)
    structure_snapshot = Column(JSON, default=dict)

    # Change tracking
    change_summary = Column(Text)
    changed_by_id = Column(UUID(), ForeignKey("users.id"))

    # Status
    is_published = Column(Boolean, default=False)
    is_latest = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        UniqueConstraint("template_id", "version_number", name="uq_template_version"),
        Index("ix_template_versions_template", "template_id"),
    )

    def __repr__(self) -> str:
        return f"<TemplateVersion(template_id={self.template_id}, version={self.version_number})>"


class SharedTemplate(Base):
    """
    Tracks template sharing between users/organizations.

    Enables collaborative access to templates.
    """
    __tablename__ = "shared_templates"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Sharing target (either user or organization, not both)
    shared_with_user_id = Column(UUID(), ForeignKey("users.id"))
    shared_with_org_id = Column(UUID(), ForeignKey("organizations.id"))

    # Sharing details
    shared_by_id = Column(UUID(), ForeignKey("users.id"), nullable=False)
    permission = Column(String(20), default="view")  # view, edit, admin

    # Optional message
    share_message = Column(Text)

    # Expiration
    expires_at = Column(DateTime)

    # Status
    is_accepted = Column(Boolean, default=False)
    accepted_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_shared_templates_user", "shared_with_user_id"),
        Index("ix_shared_templates_org", "shared_with_org_id"),
    )

    def __repr__(self) -> str:
        return f"<SharedTemplate(template_id={self.template_id})>"


class TemplateFork(Base):
    """
    Tracks template forks (copies).

    Maintains relationship between original and forked templates.
    """
    __tablename__ = "template_forks"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)

    # Original template
    source_template_id = Column(
        UUID(),
        ForeignKey("templates.id", ondelete="SET NULL"),
    )
    source_version_id = Column(UUID(), ForeignKey("template_versions.id"))

    # Forked template
    forked_template_id = Column(
        UUID(),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Fork metadata
    forked_by_id = Column(UUID(), ForeignKey("users.id"), nullable=False)
    fork_reason = Column(Text)

    # Track if fork is kept in sync
    sync_enabled = Column(Boolean, default=False)
    last_synced_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_template_forks_source", "source_template_id"),
        Index("ix_template_forks_forked", "forked_template_id"),
    )

    def __repr__(self) -> str:
        return f"<TemplateFork(source={self.source_template_id}, forked={self.forked_template_id})>"


class TemplateReview(Base):
    """
    User reviews and ratings for templates.
    """
    __tablename__ = "template_reviews"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Rating (1-5 stars)
    rating = Column(Integer, nullable=False)

    # Review content
    title = Column(String(200))
    content = Column(Text)

    # Structured feedback
    pros = Column(JSON, default=list)  # List of pros
    cons = Column(JSON, default=list)  # List of cons

    # Usage context
    use_case = Column(String(100))  # What they used it for
    experience_level = Column(String(50))  # beginner, intermediate, advanced

    # Moderation
    is_verified_purchase = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)

    # Helpfulness voting
    helpful_count = Column(Integer, default=0)
    not_helpful_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("template_id", "user_id", name="uq_template_user_review"),
        Index("ix_template_reviews_template", "template_id"),
    )

    def __repr__(self) -> str:
        return f"<TemplateReview(template_id={self.template_id}, rating={self.rating})>"


class TemplateReviewVote(Base):
    """
    Tracks helpful/not helpful votes on reviews.
    """
    __tablename__ = "template_review_votes"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    review_id = Column(
        UUID(),
        ForeignKey("template_reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    is_helpful = Column(Boolean, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("review_id", "user_id", name="uq_review_user_vote"),
    )


class TemplateUsageHistory(Base):
    """
    Tracks template usage for analytics and recommendations.
    """
    __tablename__ = "template_usage_history"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    organization_id = Column(
        UUID(),
        ForeignKey("organizations.id", ondelete="SET NULL"),
    )

    # Usage details
    action = Column(String(50), nullable=False)  # viewed, downloaded, used, cloned

    # Context
    document_id = Column(UUID(), ForeignKey("documents.id", ondelete="SET NULL"))
    source = Column(String(50))  # api, web, batch

    # Session info
    session_id = Column(String(100))

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_template_usage_template", "template_id"),
        Index("ix_template_usage_user", "user_id"),
        Index("ix_template_usage_created", "created_at"),
    )


class TemplateCollection(Base):
    """
    User-curated collections of templates.
    """
    __tablename__ = "template_collections"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)

    # Owner
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(
        UUID(),
        ForeignKey("organizations.id", ondelete="SET NULL"),
    )

    # Collection details
    name = Column(String(200), nullable=False)
    description = Column(Text)
    slug = Column(String(200))

    # Visibility
    visibility = Column(
        Enum(TemplateVisibility),
        default=TemplateVisibility.PRIVATE,
    )

    # Appearance
    cover_image_url = Column(String(500))
    color = Column(String(20))

    # Stats
    template_count = Column(Integer, default=0)
    follower_count = Column(Integer, default=0)

    is_featured = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_template_collections_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<TemplateCollection(name={self.name})>"


class CollectionTemplate(Base):
    """
    Junction table for templates in collections.
    """
    __tablename__ = "collection_templates"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    collection_id = Column(
        UUID(),
        ForeignKey("template_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id = Column(
        UUID(),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Ordering within collection
    sort_order = Column(Integer, default=0)

    # Optional notes
    notes = Column(Text)

    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("collection_id", "template_id", name="uq_collection_template"),
    )


class CollectionFollower(Base):
    """
    Tracks users following collections.
    """
    __tablename__ = "collection_followers"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    collection_id = Column(
        UUID(),
        ForeignKey("template_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("collection_id", "user_id", name="uq_collection_follower"),
    )
