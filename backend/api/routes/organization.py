"""
Organization API routes.

Provides endpoints for organization management, membership, and invitations.
"""
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.organization import (
    Organization,
    OrganizationMember,
    OrganizationInvite,
    OrganizationRole,
    InviteStatus,
)
from backend.auth.dependencies import get_current_active_user
from backend.exceptions import (
    NotFoundError,
    ValidationError,
    AuthorizationError,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateOrganizationRequest(BaseModel):
    """Request to create a new organization."""
    name: str = Field(..., min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    billing_email: Optional[EmailStr] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug can only contain lowercase letters, numbers, and hyphens")
        return v


class UpdateOrganizationRequest(BaseModel):
    """Request to update an organization."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    billing_email: Optional[EmailStr] = None
    allow_member_invites: Optional[bool] = None


class OrganizationResponse(BaseModel):
    """Organization response."""
    id: str
    name: str
    slug: str
    description: Optional[str]
    billing_email: Optional[str]
    subscription_tier: str
    subscription_status: str
    is_active: bool
    allow_member_invites: bool
    max_members: int
    member_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class MemberResponse(BaseModel):
    """Organization member response."""
    id: str
    user_id: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    joined_at: datetime


class InviteMemberRequest(BaseModel):
    """Request to invite a member to organization."""
    email: EmailStr
    role: str = Field(default="member")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ["admin", "member", "viewer"]
        if v not in valid_roles:
            raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v


class InviteResponse(BaseModel):
    """Invitation response."""
    id: str
    email: str
    role: str
    status: str
    invited_by: Optional[str]
    created_at: datetime
    expires_at: datetime


class AcceptInviteRequest(BaseModel):
    """Request to accept an invitation."""
    token: str


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


# =============================================================================
# Organization CRUD Endpoints
# =============================================================================

@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization",
    description="Create a new organization. The creating user becomes the owner.",
)
async def create_organization(
    request: CreateOrganizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OrganizationResponse:
    """Create a new organization."""
    # Generate slug from name if not provided
    slug = request.slug
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", request.name.lower()).strip("-")

    # Check if slug is unique
    existing = db.query(Organization).filter(Organization.slug == slug).first()
    if existing:
        # Append random suffix
        slug = f"{slug}-{secrets.token_hex(3)}"

    # Create organization
    org = Organization(
        id=uuid.uuid4(),
        name=request.name,
        slug=slug,
        description=request.description,
        billing_email=request.billing_email or current_user.email,
    )
    db.add(org)
    db.flush()

    # Add creating user as owner
    membership = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=current_user.id,
        role=OrganizationRole.OWNER,
    )
    db.add(membership)

    # Set as user's default organization if they don't have one
    if current_user.default_organization_id is None:
        current_user.default_organization_id = org.id

    db.commit()
    db.refresh(org)

    logger.info("organization_created", org_id=str(org.id), user_id=str(current_user.id))

    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        billing_email=org.billing_email,
        subscription_tier=org.subscription_tier,
        subscription_status=org.subscription_status,
        is_active=org.is_active,
        allow_member_invites=org.allow_member_invites,
        max_members=org.max_members,
        member_count=1,
        created_at=org.created_at,
    )


@router.get(
    "",
    response_model=List[OrganizationResponse],
    summary="List user's organizations",
    description="Get all organizations the current user is a member of.",
)
async def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[OrganizationResponse]:
    """List organizations user belongs to."""
    memberships = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
        )
        .all()
    )

    result = []
    for membership in memberships:
        org = membership.organization
        member_count = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.is_active == True,
            )
            .count()
        )
        result.append(
            OrganizationResponse(
                id=str(org.id),
                name=org.name,
                slug=org.slug,
                description=org.description,
                billing_email=org.billing_email,
                subscription_tier=org.subscription_tier,
                subscription_status=org.subscription_status,
                is_active=org.is_active,
                allow_member_invites=org.allow_member_invites,
                max_members=org.max_members,
                member_count=member_count,
                created_at=org.created_at,
            )
        )

    return result


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization",
    description="Get organization details. User must be a member.",
)
async def get_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OrganizationResponse:
    """Get organization by ID."""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise NotFoundError("Organization", org_id)

    # Check user is a member
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_uuid,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
        )
        .first()
    )

    if not membership:
        raise NotFoundError("Organization", org_id)

    org = membership.organization
    member_count = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.is_active == True,
        )
        .count()
    )

    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        billing_email=org.billing_email,
        subscription_tier=org.subscription_tier,
        subscription_status=org.subscription_status,
        is_active=org.is_active,
        allow_member_invites=org.allow_member_invites,
        max_members=org.max_members,
        member_count=member_count,
        created_at=org.created_at,
    )


@router.patch(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization",
    description="Update organization settings. Requires admin or owner role.",
)
async def update_organization(
    org_id: str,
    request: UpdateOrganizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OrganizationResponse:
    """Update organization settings."""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise NotFoundError("Organization", org_id)

    # Check user has admin/owner role
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_uuid,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
            OrganizationMember.role.in_([OrganizationRole.OWNER, OrganizationRole.ADMIN]),
        )
        .first()
    )

    if not membership:
        raise AuthorizationError("You don't have permission to update this organization")

    org = membership.organization

    # Apply updates
    if request.name is not None:
        org.name = request.name
    if request.description is not None:
        org.description = request.description
    if request.billing_email is not None:
        org.billing_email = request.billing_email
    if request.allow_member_invites is not None:
        org.allow_member_invites = request.allow_member_invites

    db.commit()
    db.refresh(org)

    member_count = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.is_active == True,
        )
        .count()
    )

    logger.info("organization_updated", org_id=str(org.id), user_id=str(current_user.id))

    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        billing_email=org.billing_email,
        subscription_tier=org.subscription_tier,
        subscription_status=org.subscription_status,
        is_active=org.is_active,
        allow_member_invites=org.allow_member_invites,
        max_members=org.max_members,
        member_count=member_count,
        created_at=org.created_at,
    )


# =============================================================================
# Member Management Endpoints
# =============================================================================

@router.get(
    "/{org_id}/members",
    response_model=List[MemberResponse],
    summary="List organization members",
    description="Get all members of an organization.",
)
async def list_members(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[MemberResponse]:
    """List organization members."""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise NotFoundError("Organization", org_id)

    # Check user is a member
    user_membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_uuid,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
        )
        .first()
    )

    if not user_membership:
        raise NotFoundError("Organization", org_id)

    # Get all active members
    memberships = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_uuid,
            OrganizationMember.is_active == True,
        )
        .all()
    )

    return [
        MemberResponse(
            id=str(m.id),
            user_id=str(m.user_id),
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role.value,
            is_active=m.is_active,
            joined_at=m.joined_at,
        )
        for m in memberships
    ]


@router.post(
    "/{org_id}/invite",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite member",
    description="Send an invitation to join the organization.",
)
async def invite_member(
    org_id: str,
    request: InviteMemberRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InviteResponse:
    """Invite a new member to the organization."""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise NotFoundError("Organization", org_id)

    # Check user has admin/owner role (or member if allow_member_invites)
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_uuid,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
        )
        .first()
    )

    if not membership:
        raise NotFoundError("Organization", org_id)

    org = membership.organization

    # Check permission to invite
    can_invite = membership.role in [OrganizationRole.OWNER, OrganizationRole.ADMIN]
    if not can_invite and org.allow_member_invites:
        can_invite = membership.role == OrganizationRole.MEMBER

    if not can_invite:
        raise AuthorizationError("You don't have permission to invite members")

    # Check member limit
    current_count = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_uuid,
            OrganizationMember.is_active == True,
        )
        .count()
    )

    if current_count >= org.max_members:
        raise ValidationError(
            message="Member limit reached",
            errors=[{"field": "organization", "message": f"Maximum {org.max_members} members allowed"}]
        )

    # Check if user is already a member
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        existing_membership = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == org_uuid,
                OrganizationMember.user_id == existing_user.id,
            )
            .first()
        )
        if existing_membership:
            raise ValidationError(
                message="User already a member",
                errors=[{"field": "email", "message": "This user is already a member of the organization"}]
            )

    # Check for existing pending invite
    existing_invite = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.organization_id == org_uuid,
            OrganizationInvite.email == request.email,
            OrganizationInvite.status == InviteStatus.PENDING,
        )
        .first()
    )

    if existing_invite:
        raise ValidationError(
            message="Invite already sent",
            errors=[{"field": "email", "message": "An invitation has already been sent to this email"}]
        )

    # Create invitation
    invite = OrganizationInvite(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        email=request.email,
        role=OrganizationRole(request.role),
        token=secrets.token_urlsafe(32),
        invited_by_user_id=current_user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    # TODO: Send invitation email

    logger.info(
        "member_invited",
        org_id=str(org_uuid),
        email=request.email,
        invited_by=str(current_user.id),
    )

    return InviteResponse(
        id=str(invite.id),
        email=invite.email,
        role=invite.role.value,
        status=invite.status.value,
        invited_by=current_user.email,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
    )


@router.post(
    "/invites/accept",
    response_model=MessageResponse,
    summary="Accept invitation",
    description="Accept an organization invitation using the token.",
)
async def accept_invite(
    request: AcceptInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """Accept an organization invitation."""
    invite = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.token == request.token,
            OrganizationInvite.status == InviteStatus.PENDING,
        )
        .first()
    )

    if not invite:
        raise NotFoundError("Invitation", "token")

    if invite.is_expired():
        invite.status = InviteStatus.EXPIRED
        db.commit()
        raise ValidationError(
            message="Invitation expired",
            errors=[{"field": "token", "message": "This invitation has expired"}]
        )

    # Check email matches
    if invite.email.lower() != current_user.email.lower():
        raise AuthorizationError("This invitation was sent to a different email address")

    # Create membership
    membership = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=invite.organization_id,
        user_id=current_user.id,
        role=invite.role,
    )
    db.add(membership)

    # Update invite status
    invite.status = InviteStatus.ACCEPTED
    invite.responded_at = datetime.utcnow()

    # Set as default organization if user doesn't have one
    if current_user.default_organization_id is None:
        current_user.default_organization_id = invite.organization_id

    db.commit()

    logger.info(
        "invite_accepted",
        org_id=str(invite.organization_id),
        user_id=str(current_user.id),
    )

    return MessageResponse(message="Successfully joined the organization")


@router.delete(
    "/{org_id}/members/{user_id}",
    response_model=MessageResponse,
    summary="Remove member",
    description="Remove a member from the organization. Requires admin or owner role.",
)
async def remove_member(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """Remove a member from the organization."""
    try:
        org_uuid = uuid.UUID(org_id)
        target_user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("Resource", "id")

    # Check user has admin/owner role
    actor_membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_uuid,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
            OrganizationMember.role.in_([OrganizationRole.OWNER, OrganizationRole.ADMIN]),
        )
        .first()
    )

    if not actor_membership:
        raise AuthorizationError("You don't have permission to remove members")

    # Find target membership
    target_membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_uuid,
            OrganizationMember.user_id == target_user_uuid,
            OrganizationMember.is_active == True,
        )
        .first()
    )

    if not target_membership:
        raise NotFoundError("Member", user_id)

    # Can't remove owner unless you're the owner
    if target_membership.role == OrganizationRole.OWNER:
        if actor_membership.role != OrganizationRole.OWNER:
            raise AuthorizationError("Only owners can remove other owners")
        # Check this isn't the last owner
        owner_count = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == org_uuid,
                OrganizationMember.role == OrganizationRole.OWNER,
                OrganizationMember.is_active == True,
            )
            .count()
        )
        if owner_count <= 1:
            raise ValidationError(
                message="Cannot remove last owner",
                errors=[{"field": "user_id", "message": "Organization must have at least one owner"}]
            )

    # Soft delete membership
    target_membership.is_active = False
    db.commit()

    logger.info(
        "member_removed",
        org_id=str(org_uuid),
        removed_user_id=str(target_user_uuid),
        removed_by=str(current_user.id),
    )

    return MessageResponse(message="Member removed successfully")
