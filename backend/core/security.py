"""
Security utilities for password hashing.

Uses bcrypt directly for Python 3.14 compatibility.
"""
from typing import Union
import bcrypt
from fastapi import HTTPException, status

# bcrypt maximum accepted password length in bytes
MAX_PASSWORD_BYTES = 72

def _to_bytes(password: Union[str, bytes]) -> bytes:
    if isinstance(password, bytes):
        return password
    return password.encode("utf-8")

def validate_password_length(password: str) -> None:
    """
    Raise HTTPException(400) if password's UTF-8 encoding exceeds bcrypt's limit.
    """
    if len(_to_bytes(password)) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at most {MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
        )

def validate_password_strength(password: str) -> None:
    """
    Basic strength check. Raise HTTPException(400) if password is too weak.
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one letter and one digit."
        )

def hash_password(password: str, truncate: bool = False) -> str:
    """
    Hash password using bcrypt. By default, reject >72 byte passwords with HTTP 400.
    """
    pw_bytes = _to_bytes(password)
    if len(pw_bytes) > MAX_PASSWORD_BYTES:
        if not truncate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password must be at most {MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
            )
        pw_bytes = pw_bytes[:MAX_PASSWORD_BYTES]
    
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")

def verify_password(password: str, hashed: str, truncate: bool = False) -> bool:
    """
    Verify password against hashed value.
    """
    pw_bytes = _to_bytes(password)
    if len(pw_bytes) > MAX_PASSWORD_BYTES:
        if not truncate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password must be at most {MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
            )
        pw_bytes = pw_bytes[:MAX_PASSWORD_BYTES]
    
    hashed_bytes = hashed.encode("utf-8")
    return bcrypt.checkpw(pw_bytes, hashed_bytes)