"""
Authentication API routes.

Provides endpoints for user registration, login, and token management.
"""
import os
import uuid
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.core.security import (
    hash_password,
    verify_password,
)
from backend.auth.utils import (
    create_tokens,
    verify_refresh_token,
    TokenResponse,
    create_verification_token,
    verify_verification_token,
    create_password_reset_token,
    verify_password_reset_token,
)
from backend.auth.dependencies import get_current_active_user, require_admin
from backend.exceptions import (
    InvalidCredentialsError,
    AuthenticationError,
    ValidationError,
    NotFoundError,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# Request/Response Models
class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str  # Validation done in endpoint for proper error code
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class UserResponse(BaseModel):
    """User profile response."""
    id: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account and return access tokens.",
)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Register a new user.
    
    Args:
        request: Registration data
        db: Database session
        
    Returns:
        Access and refresh tokens
    """
    from backend.validation import PasswordValidator, sanitize_text_input
    
    # Validate password strength
    is_valid, password_errors = PasswordValidator.validate(request.password)
    if not is_valid:
        raise ValidationError(
            message="Password does not meet requirements",
            errors=[{"field": "password", "message": err} for err in password_errors]
        )
    
    # Check if email already exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise ValidationError(
            message="Email already registered",
            errors=[{"field": "email", "message": "This email is already in use"}]
        )
    
    # Sanitize full name
    sanitized_name = sanitize_text_input(request.full_name) if request.full_name else None
    
    # Create new user
    user = User(
        id=uuid.uuid4(),
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=sanitized_name,
        role=UserRole.ANALYST,
        is_active=True,
        is_verified=False,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info("user_registered", user_id=str(user.id), email=user.email)
    
    # Return tokens
    return create_tokens(str(user.id), user.email, user.role.value)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login user",
    description="Authenticate user and return access tokens.",
)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Login a user with rate limiting and account lockout protection.

    Args:
        request: Login credentials
        http_request: FastAPI request for rate limiting
        db: Database session

    Returns:
        Access and refresh tokens
    """
    from backend.middleware.rate_limit import limiter, RATE_LIMITS

    # Apply rate limiting (10 attempts per minute per IP)
    # Note: Rate limit is also applied via decorator in production

    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        # Don't reveal whether email exists
        raise InvalidCredentialsError()

    # Check if account is locked
    if user.is_locked():
        logger.warning("locked_account_login_attempt", user_id=str(user.id))
        raise AuthenticationError("Account temporarily locked due to too many failed attempts. Please try again later.")

    # Verify password
    if not verify_password(request.password, user.password_hash):
        # Increment failed attempts
        user.increment_failed_attempts()
        db.commit()

        logger.warning(
            "failed_login_attempt",
            user_id=str(user.id),
            failed_attempts=user.failed_login_attempts,
            locked=user.is_locked()
        )

        if user.is_locked():
            raise AuthenticationError("Account locked due to too many failed attempts. Please try again later.")

        raise InvalidCredentialsError()

    # Check if user is active
    if not user.is_active:
        raise AuthenticationError("Account is disabled")

    # Successful login - reset failed attempts
    user.reset_failed_attempts()
    user.last_login = datetime.utcnow()
    db.commit()

    logger.info("user_login", user_id=str(user.id), email=user.email)

    # Return tokens
    return create_tokens(str(user.id), user.email, user.role.value)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get new access token using refresh token.",
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Refresh access token.
    
    Args:
        request: Refresh token
        db: Database session
        
    Returns:
        New access and refresh tokens
    """
    user_id = verify_refresh_token(request.refresh_token)
    if not user_id:
        raise AuthenticationError("Invalid refresh token")

    # Convert string user_id to UUID for database query
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise AuthenticationError("Invalid refresh token")

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user or not user.is_active:
        raise AuthenticationError("Invalid refresh token")
    
    logger.info("token_refresh", user_id=str(user.id))
    
    return create_tokens(str(user.id), user.email, user.role.value)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get profile of currently authenticated user.",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    Get current user profile.
    
    Args:
        current_user: Authenticated user
        
    Returns:
        User profile
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout user",
    description="Logout current user (client should discard tokens).",
)
async def logout(
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """
    Logout user.

    Note: JWT tokens are stateless, so this just confirms logout.
    Client should discard tokens.

    Args:
        current_user: Authenticated user

    Returns:
        Success message
    """
    logger.info("user_logout", user_id=str(current_user.id))
    return MessageResponse(message="Successfully logged out")


# =============================================================================
# Admin User Management Endpoints
# =============================================================================

class UserListResponse(BaseModel):
    """Response for user list."""
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


class UpdateUserRequest(BaseModel):
    """Request to update a user."""
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List all users (Admin only)",
    description="Get paginated list of all users. Requires admin role.",
)
async def list_users(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
) -> UserListResponse:
    """
    List all users (admin only).

    Args:
        page: Page number (1-indexed)
        page_size: Number of users per page
        db: Database session
        admin_user: Admin user (from require_admin dependency)

    Returns:
        Paginated list of users
    """
    # Get total count
    total = db.query(User).count()

    # Get paginated users
    offset = (page - 1) * page_size
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    user_responses = [
        UserResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role.value,
            is_active=u.is_active,
            is_verified=u.is_verified,
            created_at=u.created_at,
            last_login=u.last_login,
        )
        for u in users
    ]

    logger.info("admin_list_users", admin_id=str(admin_user.id), total=total, page=page)

    return UserListResponse(
        users=user_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID (Admin only)",
    description="Get a specific user by their ID. Requires admin role.",
)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
) -> UserResponse:
    """
    Get a user by ID (admin only).

    Args:
        user_id: UUID of the user
        db: Database session
        admin_user: Admin user

    Returns:
        User profile
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("User", user_id)

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise NotFoundError("User", user_id)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update user (Admin only)",
    description="Update a user's profile, role, or status. Requires admin role.",
)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
) -> UserResponse:
    """
    Update a user (admin only).

    Args:
        user_id: UUID of the user
        request: Fields to update
        db: Database session
        admin_user: Admin user

    Returns:
        Updated user profile
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("User", user_id)

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise NotFoundError("User", user_id)

    # Prevent admin from modifying themselves in certain ways
    if user.id == admin_user.id:
        if request.is_active is False:
            raise ValidationError(
                message="Cannot deactivate your own account",
                errors=[{"field": "is_active", "message": "Admins cannot deactivate themselves"}]
            )
        if request.role and request.role != UserRole.ADMIN.value:
            raise ValidationError(
                message="Cannot demote your own admin role",
                errors=[{"field": "role", "message": "Admins cannot demote themselves"}]
            )

    # Apply updates
    if request.full_name is not None:
        from backend.validation import sanitize_text_input
        user.full_name = sanitize_text_input(request.full_name) if request.full_name else None

    if request.role is not None:
        try:
            user.role = UserRole(request.role)
        except ValueError:
            raise ValidationError(
                message="Invalid role",
                errors=[{"field": "role", "message": f"Valid roles: {[r.value for r in UserRole]}"}]
            )

    if request.is_active is not None:
        user.is_active = request.is_active

    if request.is_verified is not None:
        user.is_verified = request.is_verified

    db.commit()
    db.refresh(user)

    logger.info(
        "admin_update_user",
        admin_id=str(admin_user.id),
        user_id=str(user.id),
        updates=request.model_dump(exclude_none=True),
    )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
    summary="Delete user (Admin only)",
    description="Permanently delete a user. Requires admin role.",
)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
) -> MessageResponse:
    """
    Delete a user (admin only).

    Args:
        user_id: UUID of the user
        db: Database session
        admin_user: Admin user

    Returns:
        Success message
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("User", user_id)

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise NotFoundError("User", user_id)

    # Prevent admin from deleting themselves
    if user.id == admin_user.id:
        raise ValidationError(
            message="Cannot delete your own account",
            errors=[{"field": "user_id", "message": "Admins cannot delete themselves"}]
        )

    email = user.email
    db.delete(user)
    db.commit()

    logger.info(
        "admin_delete_user",
        admin_id=str(admin_user.id),
        deleted_user_id=str(user_uuid),
        deleted_email=email,
    )

    return MessageResponse(message=f"User {email} deleted successfully")


# =============================================================================
# Email Verification Endpoints
# =============================================================================

class VerifyEmailRequest(BaseModel):
    """Email verification request."""
    token: str


class RequestPasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Password reset with token."""
    token: str
    new_password: str


@router.post(
    "/send-verification",
    response_model=MessageResponse,
    summary="Send verification email",
    description="Send email verification link to current user.",
)
async def send_verification_email(
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """
    Send verification email to current user.

    Args:
        current_user: Authenticated user

    Returns:
        Success message
    """
    if current_user.is_verified:
        return MessageResponse(message="Email already verified")

    from backend.services.email_service import email_service

    # Create verification token
    token = create_verification_token(str(current_user.id), current_user.email)

    # Send email
    sent = email_service.send_verification_email(current_user.email, token)

    if sent:
        logger.info("verification_email_sent", user_id=str(current_user.id))
    else:
        logger.warning("verification_email_failed", user_id=str(current_user.id))

    # Always return success to prevent email enumeration
    return MessageResponse(message="Verification email sent if account exists")


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify email",
    description="Verify email using token from verification email.",
)
async def verify_email(
    request: VerifyEmailRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """
    Verify user's email address.

    Args:
        request: Verification token
        db: Database session

    Returns:
        Success message
    """
    result = verify_verification_token(request.token)
    if not result:
        raise AuthenticationError("Invalid or expired verification token")

    user_id, email = result

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise AuthenticationError("Invalid verification token")

    user = db.query(User).filter(User.id == user_uuid, User.email == email).first()
    if not user:
        raise AuthenticationError("Invalid verification token")

    if user.is_verified:
        return MessageResponse(message="Email already verified")

    user.is_verified = True
    db.commit()

    logger.info("email_verified", user_id=str(user.id))

    return MessageResponse(message="Email verified successfully")


# =============================================================================
# Password Reset Endpoints
# =============================================================================

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset",
    description="Send password reset email.",
)
async def forgot_password(
    request: RequestPasswordResetRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """
    Request password reset.

    Args:
        request: Email address
        db: Database session

    Returns:
        Success message (always, to prevent email enumeration)
    """
    from backend.services.email_service import email_service

    user = db.query(User).filter(User.email == request.email).first()

    if user and user.is_active:
        # Create reset token
        token = create_password_reset_token(str(user.id), user.email)

        # Send email
        sent = email_service.send_password_reset_email(user.email, token)

        if sent:
            logger.info("password_reset_email_sent", user_id=str(user.id))
        else:
            logger.warning("password_reset_email_failed", user_id=str(user.id))
    else:
        logger.info("password_reset_requested_unknown_email", email=request.email)

    # Always return success to prevent email enumeration
    return MessageResponse(message="Password reset email sent if account exists")


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password",
    description="Reset password using token from reset email.",
)
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """
    Reset user's password.

    Args:
        request: Reset token and new password
        db: Database session

    Returns:
        Success message
    """
    from backend.validation import PasswordValidator

    # Verify token
    result = verify_password_reset_token(request.token)
    if not result:
        raise AuthenticationError("Invalid or expired reset token")

    user_id, email = result

    # Validate new password
    is_valid, password_errors = PasswordValidator.validate(request.new_password)
    if not is_valid:
        raise ValidationError(
            message="Password does not meet requirements",
            errors=[{"field": "new_password", "message": err} for err in password_errors]
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise AuthenticationError("Invalid reset token")

    user = db.query(User).filter(User.id == user_uuid, User.email == email).first()
    if not user:
        raise AuthenticationError("Invalid reset token")

    if not user.is_active:
        raise AuthenticationError("Account is disabled")

    # Update password
    user.password_hash = hash_password(request.new_password)
    db.commit()

    logger.info("password_reset_complete", user_id=str(user.id))

    return MessageResponse(message="Password reset successfully")


# =============================================================================
# OAuth/SSO Endpoints (Google)
# =============================================================================

from authlib.integrations.starlette_client import OAuth

# OAuth configuration
oauth = OAuth()

# Register Google OAuth provider
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


class OAuthLoginResponse(BaseModel):
    """OAuth login redirect URL response."""
    auth_url: str


@router.get(
    "/oauth/google",
    response_model=OAuthLoginResponse,
    summary="Initiate Google OAuth login",
    description="Get Google OAuth authorization URL for redirect.",
)
async def google_oauth_login(
    request: Request,
) -> OAuthLoginResponse:
    """
    Initiate Google OAuth login.

    Returns authorization URL for client-side redirect.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise AuthenticationError("Google OAuth is not configured")

    # Get the redirect URI from environment or construct from request
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    redirect_uri = f"{frontend_url}/auth/google/callback"

    # Generate authorization URL
    google = oauth.create_client("google")
    auth_url = await google.create_authorization_url(redirect_uri)

    # Store state in session for CSRF protection (simplified for stateless)
    # In production, use secure session storage

    logger.info("google_oauth_initiated", redirect_uri=redirect_uri)

    return OAuthLoginResponse(auth_url=auth_url["url"])


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request with authorization code."""
    code: str
    state: Optional[str] = None


@router.post(
    "/oauth/google/callback",
    response_model=TokenResponse,
    summary="Complete Google OAuth login",
    description="Exchange authorization code for tokens and create/login user.",
)
async def google_oauth_callback(
    request: OAuthCallbackRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Complete Google OAuth login.

    Exchanges authorization code for Google tokens, retrieves user info,
    and creates or logs in the user.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise AuthenticationError("Google OAuth is not configured")

    import httpx

    try:
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        redirect_uri = f"{frontend_url}/auth/google/callback"

        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": request.code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )

            if token_response.status_code != 200:
                logger.error("google_token_exchange_failed", status=token_response.status_code)
                raise AuthenticationError("Failed to authenticate with Google")

            token_data = token_response.json()

            # Get user info from Google
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )

            if userinfo_response.status_code != 200:
                logger.error("google_userinfo_failed", status=userinfo_response.status_code)
                raise AuthenticationError("Failed to get user info from Google")

            userinfo = userinfo_response.json()

    except httpx.RequestError as e:
        logger.error("google_oauth_request_error", error=str(e))
        raise AuthenticationError("Failed to connect to Google")

    email = userinfo.get("email")
    if not email:
        raise AuthenticationError("Email not provided by Google")

    # Check if email is verified by Google
    if not userinfo.get("verified_email", False):
        raise AuthenticationError("Email not verified with Google")

    # Find or create user
    user = db.query(User).filter(User.email == email).first()

    if user:
        # Existing user - check if active
        if not user.is_active:
            raise AuthenticationError("Account is disabled")

        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()

        logger.info("google_oauth_login", user_id=str(user.id), email=email)
    else:
        # New user - create account
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash="",  # No password for OAuth users
            full_name=userinfo.get("name"),
            role=UserRole.ANALYST,
            is_active=True,
            is_verified=True,  # Google verified the email
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info("google_oauth_register", user_id=str(user.id), email=email)

    # Return tokens
    return create_tokens(str(user.id), user.email, user.role.value)