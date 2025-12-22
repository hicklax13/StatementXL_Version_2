"""
Authentication API routes.

Provides endpoints for user registration, login, and token management.
"""
import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.auth.utils import (
    hash_password,
    verify_password,
    create_tokens,
    verify_refresh_token,
    TokenResponse,
)
from backend.auth.dependencies import get_current_active_user
from backend.exceptions import (
    InvalidCredentialsError,
    AuthenticationError,
    ValidationError,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# Request/Response Models
class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
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
    # Check if email already exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise ValidationError(
            message="Email already registered",
            errors=[{"field": "email", "message": "This email is already in use"}]
        )
    
    # Create new user
    user = User(
        id=uuid.uuid4(),
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
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
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Login a user.
    
    Args:
        request: Login credentials
        db: Database session
        
    Returns:
        Access and refresh tokens
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise InvalidCredentialsError()
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise InvalidCredentialsError()
    
    # Check if user is active
    if not user.is_active:
        raise AuthenticationError("Account is disabled")
    
    # Update last login
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
    
    user = db.query(User).filter(User.id == user_id).first()
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
