"""
Integration models for third-party accounting software connections.

Stores OAuth tokens and connection state for QuickBooks, Xero, etc.
"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class IntegrationType(str, Enum):
    """Supported integration types."""
    QUICKBOOKS = "quickbooks"
    XERO = "xero"


class IntegrationStatus(str, Enum):
    """Integration connection status."""
    DISCONNECTED = "disconnected"
    PENDING = "pending"        # OAuth flow in progress
    CONNECTED = "connected"
    SYNCING = "syncing"        # Sync in progress
    ERROR = "error"
    FAILED = "failed"          # Connection failed
    EXPIRED = "expired"        # Token expired, needs refresh


class Integration(Base):
    """Third-party integration connection model."""

    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Connection info
    integration_type = Column(SQLEnum(IntegrationType), nullable=False)
    status = Column(SQLEnum(IntegrationStatus), default=IntegrationStatus.DISCONNECTED, nullable=False)

    # OAuth tokens (encrypted in production)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Provider-specific identifiers
    external_company_id = Column(String(255), nullable=True)  # QuickBooks realm_id / Xero tenant_id
    external_company_name = Column(String(255), nullable=True)

    # Sync settings
    sync_enabled = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_error = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)  # General error message

    # Active flag for soft delete
    is_active = Column(Boolean, default=True, nullable=False)

    # Metadata
    settings = Column(JSON, nullable=True)  # Integration-specific settings
    extra_data = Column(JSON, nullable=True)  # OAuth state, redirect URLs, etc. (renamed from 'metadata')

    # Relationships
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", backref="integrations")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self) -> str:
        return f"<Integration {self.integration_type.value} org={self.organization_id} status={self.status.value}>"

    def is_token_expired(self) -> bool:
        """Check if the access token has expired."""
        if not self.token_expires_at:
            return True
        return datetime.utcnow() > self.token_expires_at.replace(tzinfo=None)

    def mark_connected(self, access_token: str, refresh_token: str, expires_at: datetime) -> None:
        """Mark integration as connected with tokens."""
        self.status = IntegrationStatus.CONNECTED
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = expires_at
        self.last_sync_error = None

    def mark_error(self, error_message: str) -> None:
        """Mark integration as having an error."""
        self.status = IntegrationStatus.ERROR
        self.last_sync_error = error_message

    def disconnect(self) -> None:
        """Disconnect the integration."""
        self.status = IntegrationStatus.DISCONNECTED
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.external_company_id = None
        self.external_company_name = None
