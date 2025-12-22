"""
Authentication dependencies for FastAPI routes.

Provides dependency injection for protected routes.
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.utils import verify_access_token, TokenData
from backend.models.user import User, UserRole
from backend.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    TokenExpiredError,
    AuthorizationError,
    InsufficientPermissionsError,
)

# HTTP Bearer token extractor
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        Authenticated User object
        
    Raises:
        AuthenticationError: If no token provided
        InvalidTokenError: If token is invalid
    """
    if not credentials:
        raise AuthenticationError("Authentication required")
    
    token_data = verify_access_token(credentials.credentials)
    if not token_data:
        raise InvalidTokenError()
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise InvalidTokenError()
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current active user.
    
    Args:
        current_user: User from get_current_user
        
    Returns:
        Active User object
        
    Raises:
        AuthorizationError: If user is inactive
    """
    if not current_user.is_active:
        raise AuthorizationError("User account is disabled")
    
    return current_user


def require_role(required_roles: list[UserRole]):
    """
    Dependency factory for role-based access control.
    
    Args:
        required_roles: List of roles that are allowed
        
    Returns:
        Dependency function that checks user role
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in required_roles:
            raise InsufficientPermissionsError(
                required_role=", ".join(r.value for r in required_roles)
            )
        return current_user
    
    return role_checker


# Convenience dependencies for common role checks
require_admin = require_role([UserRole.ADMIN])
require_analyst = require_role([UserRole.ADMIN, UserRole.ANALYST])
require_viewer = require_role([UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER])


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Get the current user if authenticated, None otherwise.
    
    Useful for endpoints that work differently for authenticated vs anonymous users.
    """
    if not credentials:
        return None
    
    token_data = verify_access_token(credentials.credentials)
    if not token_data:
        return None
    
    return db.query(User).filter(User.id == token_data.user_id).first()
