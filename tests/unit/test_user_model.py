"""
Unit tests for User model.

Tests account lockout functionality and user methods.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from backend.models.user import User, UserRole


class TestUserModel:
    """Tests for User model basic functionality."""

    def test_user_repr(self):
        """Test user string representation."""
        user = User(email="test@example.com")
        assert repr(user) == "<User test@example.com>"

    def test_user_default_role(self):
        """Test that default role is ANALYST."""
        user = User(email="test@example.com", password_hash="hash")
        assert user.role == UserRole.ANALYST

    def test_user_default_active_status(self):
        """Test that users are active by default."""
        user = User(email="test@example.com", password_hash="hash")
        assert user.is_active is True

    def test_user_default_verified_status(self):
        """Test that users are not verified by default."""
        user = User(email="test@example.com", password_hash="hash")
        assert user.is_verified is False


class TestAccountLockout:
    """Tests for account lockout functionality."""

    def test_is_locked_when_not_locked(self):
        """Test is_locked returns False when account is not locked."""
        user = User(email="test@example.com", locked_until=None)
        assert user.is_locked() is False

    def test_is_locked_when_locked(self):
        """Test is_locked returns True when account is locked."""
        user = User(
            email="test@example.com",
            locked_until=datetime.utcnow() + timedelta(minutes=15)
        )
        assert user.is_locked() is True

    def test_is_locked_when_lock_expired(self):
        """Test is_locked returns False when lock has expired."""
        user = User(
            email="test@example.com",
            locked_until=datetime.utcnow() - timedelta(minutes=1)
        )
        assert user.is_locked() is False

    def test_increment_failed_attempts_first_failure(self):
        """Test incrementing failed attempts from zero."""
        user = User(email="test@example.com", failed_login_attempts=0)
        user.increment_failed_attempts()

        assert user.failed_login_attempts == 1
        assert user.locked_until is None  # Not locked yet

    def test_increment_failed_attempts_fourth_failure(self):
        """Test that 4 failures doesn't lock account."""
        user = User(email="test@example.com", failed_login_attempts=3)
        user.increment_failed_attempts()

        assert user.failed_login_attempts == 4
        assert user.locked_until is None  # Not locked yet

    def test_increment_failed_attempts_fifth_failure_locks(self):
        """Test that 5 failures locks the account for 15 minutes."""
        user = User(email="test@example.com", failed_login_attempts=4)
        user.increment_failed_attempts()

        assert user.failed_login_attempts == 5
        assert user.locked_until is not None
        assert user.is_locked() is True

        # Should be locked for approximately 15 minutes
        lock_duration = user.locked_until.replace(tzinfo=None) - datetime.utcnow()
        assert timedelta(minutes=14) < lock_duration < timedelta(minutes=16)

    def test_increment_failed_attempts_tenth_failure_locks_longer(self):
        """Test that 10 failures locks the account for 1 hour."""
        user = User(email="test@example.com", failed_login_attempts=9)
        user.increment_failed_attempts()

        assert user.failed_login_attempts == 10
        assert user.locked_until is not None
        assert user.is_locked() is True

        # Should be locked for approximately 1 hour
        lock_duration = user.locked_until.replace(tzinfo=None) - datetime.utcnow()
        assert timedelta(minutes=59) < lock_duration < timedelta(minutes=61)

    def test_reset_failed_attempts(self):
        """Test resetting failed attempts after successful login."""
        user = User(
            email="test@example.com",
            failed_login_attempts=3,
            locked_until=datetime.utcnow() + timedelta(minutes=15)
        )

        user.reset_failed_attempts()

        assert user.failed_login_attempts == 0
        assert user.locked_until is None

    def test_reset_failed_attempts_when_already_zero(self):
        """Test resetting when already at zero."""
        user = User(email="test@example.com", failed_login_attempts=0)
        user.reset_failed_attempts()

        assert user.failed_login_attempts == 0
        assert user.locked_until is None


class TestUserRole:
    """Tests for UserRole enum."""

    def test_role_values(self):
        """Test that all expected roles exist."""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.ANALYST.value == "analyst"
        assert UserRole.VIEWER.value == "viewer"
        assert UserRole.API_USER.value == "api_user"

    def test_role_from_string(self):
        """Test creating role from string value."""
        role = UserRole("admin")
        assert role == UserRole.ADMIN

    def test_invalid_role_raises_error(self):
        """Test that invalid role raises ValueError."""
        with pytest.raises(ValueError):
            UserRole("invalid_role")
