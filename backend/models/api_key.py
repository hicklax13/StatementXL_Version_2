"""
API Key models for public API access.

Provides secure API key generation and management for third-party integrations.
"""
import secrets
import hashlib
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class APIKeyScope(str, Enum):
    """API key permission scopes."""
    READ = "read"              # Read-only access
    WRITE = "write"            # Create/update access
    DELETE = "delete"          # Delete access
    UPLOAD = "upload"          # Upload documents
    EXPORT = "export"          # Export data
    CLASSIFY = "classify"      # Use classification API
    ADMIN = "admin"            # Full admin access


class APIKey(Base):
    """API key for external integrations."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Key identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Key value (hashed for security - only shown once on creation)
    key_prefix = Column(String(10), nullable=False)  # First 8 chars for identification
    key_hash = Column(String(64), nullable=False)     # SHA-256 hash of full key

    # Permissions
    scopes = Column(ARRAY(String), nullable=False, default=list)

    # Usage tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)

    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60, nullable=False)
    rate_limit_per_day = Column(Integer, default=10000, nullable=False)

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(String(500), nullable=True)

    # IP restrictions (optional)
    allowed_ips = Column(ARRAY(String), nullable=True)  # CIDR notation allowed

    # Ownership
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", backref="api_keys")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self) -> str:
        return f"<APIKey {self.key_prefix}... {self.name}>"

    @classmethod
    def generate_key(cls) -> tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            Tuple of (full_key, key_prefix, key_hash)
        """
        # Generate a secure random key: sxl_live_<32 random chars>
        random_part = secrets.token_urlsafe(32)
        full_key = f"sxl_live_{random_part}"

        # Get prefix for identification
        key_prefix = full_key[:10]

        # Hash the full key for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()

        return full_key, key_prefix, key_hash

    @classmethod
    def verify_key(cls, full_key: str, stored_hash: str) -> bool:
        """Verify an API key against a stored hash."""
        computed_hash = hashlib.sha256(full_key.encode()).hexdigest()
        return secrets.compare_digest(computed_hash, stored_hash)

    def is_valid(self) -> bool:
        """Check if the API key is currently valid."""
        if not self.is_active:
            return False
        if self.revoked_at is not None:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at.replace(tzinfo=None):
            return False
        return True

    def has_scope(self, scope: str) -> bool:
        """Check if the key has a specific scope."""
        if APIKeyScope.ADMIN.value in (self.scopes or []):
            return True
        return scope in (self.scopes or [])

    def record_usage(self) -> None:
        """Record that the API key was used."""
        self.last_used_at = datetime.utcnow()
        self.usage_count += 1

    def revoke(self, reason: Optional[str] = None) -> None:
        """Revoke the API key."""
        self.is_active = False
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason


class APIKeyUsageLog(Base):
    """Log of API key usage for analytics and debugging."""

    __tablename__ = "api_key_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Reference to key
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)

    # Request details
    endpoint = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=True)

    # Request metadata
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    api_key = relationship("APIKey", backref="usage_logs")
