"""
Organization models for multi-tenancy.

Provides organization and membership management for team collaboration.
"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class OrganizationRole(str, Enum):
    """Organization-level role enumeration."""
    OWNER = "owner"      # Full control, can delete organization
    ADMIN = "admin"      # Can manage members and settings
    MEMBER = "member"    # Standard access
    VIEWER = "viewer"    # Read-only access


class InviteStatus(str, Enum):
    """Invitation status enumeration."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class Organization(Base):
    """Organization model for multi-tenant data isolation."""

    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Billing and subscription
    billing_email = Column(String(255), nullable=True)
    stripe_customer_id = Column(String(255), nullable=True, unique=True)
    subscription_tier = Column(String(50), default="free", nullable=False)
    subscription_status = Column(String(50), default="active", nullable=False)

    # Settings
    is_active = Column(Boolean, default=True, nullable=False)
    allow_member_invites = Column(Boolean, default=False, nullable=False)
    max_members = Column(Integer, default=5, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    invitations = relationship("OrganizationInvite", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Organization {self.name}>"


class OrganizationMember(Base):
    """Organization membership linking users to organizations."""

    __tablename__ = "organization_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(SQLEnum(OrganizationRole), default=OrganizationRole.MEMBER, nullable=False)

    # Membership status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="members")
    user = relationship("User", backref="organization_memberships")

    # Unique constraint: user can only be in an organization once
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    def __repr__(self) -> str:
        return f"<OrganizationMember org={self.organization_id} user={self.user_id}>"


class OrganizationInvite(Base):
    """Pending invitations to join an organization."""

    __tablename__ = "organization_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    role = Column(SQLEnum(OrganizationRole), default=OrganizationRole.MEMBER, nullable=False)
    status = Column(SQLEnum(InviteStatus), default=InviteStatus.PENDING, nullable=False)

    # Invite token for email verification
    token = Column(String(255), unique=True, nullable=False, index=True)

    # Who sent the invite
    invited_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="invitations")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])

    # Unique constraint: only one pending invite per email per org
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_org_invite_email"),
    )

    def __repr__(self) -> str:
        return f"<OrganizationInvite {self.email} -> {self.organization_id}>"

    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)
