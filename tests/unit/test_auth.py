"""
Unit tests for authentication utilities.

Tests JWT tokens, password hashing, and token verification.
"""
import pytest
from datetime import timedelta

from backend.core.security import (
    hash_password,
    verify_password,
)
from backend.auth.utils import (
    create_access_token,
    create_refresh_token,
    create_tokens,
    verify_access_token,
    verify_refresh_token,
    decode_token,
    create_verification_token,
    verify_verification_token,
    create_password_reset_token,
    verify_password_reset_token,
)


class TestPasswordHashing:
    """Tests for password hashing and verification."""
    
    def test_hash_password(self):
        """Test that passwords are hashed."""
        password = "SecurePass123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 20
    
    def test_verify_correct_password(self):
        """Test verification of correct password."""
        password = "SecurePass123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_wrong_password(self):
        """Test rejection of wrong password."""
        password = "SecurePass123"
        hashed = hash_password(password)
        
        assert verify_password("WrongPassword", hashed) is False
    
    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salt)."""
        password = "SecurePass123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2  # Different salts


class TestAccessToken:
    """Tests for JWT access token generation and verification."""
    
    def test_create_access_token(self):
        """Test access token creation."""
        token = create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="analyst",
        )
        
        assert token is not None
        assert len(token) > 50  # JWT tokens are long
    
    def test_verify_valid_access_token(self):
        """Test verification of valid access token."""
        token = create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="analyst",
        )
        
        data = verify_access_token(token)
        
        assert data is not None
        assert data.user_id == "user-123"
        assert data.email == "test@example.com"
        assert data.role == "analyst"
    
    def test_verify_invalid_token(self):
        """Test rejection of invalid token."""
        data = verify_access_token("invalid-token")
        assert data is None
    
    def test_custom_expiration(self):
        """Test token with custom expiration."""
        token = create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="analyst",
            expires_delta=timedelta(hours=1),
        )
        
        data = verify_access_token(token)
        assert data is not None


class TestRefreshToken:
    """Tests for JWT refresh token generation and verification."""
    
    def test_create_refresh_token(self):
        """Test refresh token creation."""
        token = create_refresh_token(user_id="user-123")
        
        assert token is not None
        assert len(token) > 50
    
    def test_verify_valid_refresh_token(self):
        """Test verification of valid refresh token."""
        token = create_refresh_token(user_id="user-123")
        
        user_id = verify_refresh_token(token)
        
        assert user_id == "user-123"
    
    def test_verify_invalid_refresh_token(self):
        """Test rejection of invalid refresh token."""
        user_id = verify_refresh_token("invalid-token")
        assert user_id is None
    
    def test_access_token_not_valid_as_refresh(self):
        """Test that access token cannot be used as refresh token."""
        access_token = create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="analyst",
        )
        
        # Access token has type="access", should fail refresh verification
        user_id = verify_refresh_token(access_token)
        assert user_id is None


class TestCreateTokens:
    """Tests for combined token creation."""
    
    def test_create_tokens_returns_both(self):
        """Test that create_tokens returns both tokens."""
        response = create_tokens(
            user_id="user-123",
            email="test@example.com",
            role="analyst",
        )
        
        assert response.access_token is not None
        assert response.refresh_token is not None
        assert response.token_type == "bearer"
        assert response.expires_in > 0
    
    def test_tokens_are_different(self):
        """Test that access and refresh tokens are different."""
        response = create_tokens(
            user_id="user-123",
            email="test@example.com",
            role="analyst",
        )
        
        assert response.access_token != response.refresh_token


class TestDecodeToken:
    """Tests for general token decoding."""
    
    def test_decode_valid_token(self):
        """Test decoding a valid token."""
        token = create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="analyst",
        )
        
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
    
    def test_decode_invalid_token(self):
        """Test decoding an invalid token returns None."""
        payload = decode_token("not.a.valid.token")
        assert payload is None


class TestVerificationToken:
    """Tests for email verification tokens."""

    def test_create_verification_token(self):
        """Test verification token creation."""
        token = create_verification_token(
            user_id="user-123",
            email="test@example.com",
        )

        assert token is not None
        assert len(token) > 50

    def test_verify_valid_verification_token(self):
        """Test verification of valid verification token."""
        token = create_verification_token(
            user_id="user-123",
            email="test@example.com",
        )

        result = verify_verification_token(token)

        assert result is not None
        assert result[0] == "user-123"
        assert result[1] == "test@example.com"

    def test_verify_invalid_verification_token(self):
        """Test rejection of invalid verification token."""
        result = verify_verification_token("invalid-token")
        assert result is None

    def test_access_token_not_valid_as_verification(self):
        """Test that access token cannot be used as verification token."""
        access_token = create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="analyst",
        )

        result = verify_verification_token(access_token)
        assert result is None


class TestPasswordResetToken:
    """Tests for password reset tokens."""

    def test_create_password_reset_token(self):
        """Test password reset token creation."""
        token = create_password_reset_token(
            user_id="user-123",
            email="test@example.com",
        )

        assert token is not None
        assert len(token) > 50

    def test_verify_valid_password_reset_token(self):
        """Test verification of valid password reset token."""
        token = create_password_reset_token(
            user_id="user-123",
            email="test@example.com",
        )

        result = verify_password_reset_token(token)

        assert result is not None
        assert result[0] == "user-123"
        assert result[1] == "test@example.com"

    def test_verify_invalid_password_reset_token(self):
        """Test rejection of invalid password reset token."""
        result = verify_password_reset_token("invalid-token")
        assert result is None

    def test_verification_token_not_valid_as_password_reset(self):
        """Test that verification token cannot be used as password reset token."""
        verification_token = create_verification_token(
            user_id="user-123",
            email="test@example.com",
        )

        result = verify_password_reset_token(verification_token)
        assert result is None

    def test_password_reset_token_not_valid_as_verification(self):
        """Test that password reset token cannot be used as verification token."""
        reset_token = create_password_reset_token(
            user_id="user-123",
            email="test@example.com",
        )

        result = verify_verification_token(reset_token)
        assert result is None