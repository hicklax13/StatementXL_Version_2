"""
Audit log models for compliance and tracking.

Provides comprehensive audit logging for:
- API actions (CRUD operations)
- Authentication events (login, logout, password changes)
- Administrative actions
- Data access and exports
- Compliance events (GDPR requests, data deletions)
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, String, Text, Integer, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class AuditAction(str, Enum):
    """Types of auditable actions."""
    # CRUD operations
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"

    # Authentication
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"

    # API access
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_REQUEST = "api_request"

    # Administrative
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_LOCKED = "user_locked"
    USER_UNLOCKED = "user_unlocked"
    ROLE_CHANGED = "role_changed"

    # Organization
    ORG_CREATED = "org_created"
    ORG_UPDATED = "org_updated"
    ORG_DELETED = "org_deleted"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    MEMBER_ROLE_CHANGED = "member_role_changed"

    # Document operations
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_EXPORTED = "document_exported"
    DOCUMENT_DELETED = "document_deleted"

    # Integration
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_DISCONNECTED = "integration_disconnected"
    INTEGRATION_SYNCED = "integration_synced"

    # Compliance
    DATA_EXPORT_REQUESTED = "data_export_requested"
    DATA_EXPORT_COMPLETED = "data_export_completed"
    DATA_DELETION_REQUESTED = "data_deletion_requested"
    DATA_DELETION_COMPLETED = "data_deletion_completed"
    CONSENT_GIVEN = "consent_given"
    CONSENT_WITHDRAWN = "consent_withdrawn"

    # System
    SYSTEM_START = "system_start"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CONFIG_CHANGED = "config_changed"
    ERROR = "error"


class AuditResourceType(str, Enum):
    """Types of resources that can be audited."""
    USER = "user"
    ORGANIZATION = "organization"
    DOCUMENT = "document"
    TEMPLATE = "template"
    MAPPING = "mapping"
    EXPORT = "export"
    API_KEY = "api_key"
    WEBHOOK = "webhook"
    INTEGRATION = "integration"
    JOB = "job"
    SESSION = "session"
    SYSTEM = "system"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base):
    """Audit log entry for tracking all system actions."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event classification
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    resource_type = Column(SQLEnum(AuditResourceType), nullable=False, index=True)
    resource_id = Column(String(255), nullable=True, index=True)
    severity = Column(SQLEnum(AuditSeverity), default=AuditSeverity.INFO, nullable=False)

    # Actor information
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True)

    # Request context
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible, use String for SQLite
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(100), nullable=True, index=True)  # Correlation ID
    request_method = Column(String(10), nullable=True)
    request_path = Column(String(500), nullable=True)

    # Event details
    description = Column(Text, nullable=True)
    old_value = Column(JSON, nullable=True)  # Previous state
    new_value = Column(JSON, nullable=True)  # New state
    extra_data = Column(JSON, nullable=True)   # Additional context (renamed from 'metadata')

    # Status
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])

    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_audit_logs_user_created', 'user_id', 'created_at'),
        Index('ix_audit_logs_org_created', 'organization_id', 'created_at'),
        Index('ix_audit_logs_action_created', 'action', 'created_at'),
        Index('ix_audit_logs_resource', 'resource_type', 'resource_id'),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action.value} {self.resource_type.value}:{self.resource_id}>"

    @classmethod
    def create_entry(
        cls,
        action: AuditAction,
        resource_type: AuditResourceType,
        resource_id: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        request_method: Optional[str] = None,
        request_path: Optional[str] = None,
        api_key_id: Optional[uuid.UUID] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ) -> "AuditLog":
        """Factory method to create an audit log entry."""
        return cls(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            organization_id=organization_id,
            description=description,
            old_value=old_value,
            new_value=new_value,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            request_method=request_method,
            request_path=request_path,
            api_key_id=api_key_id,
            success=success,
            error_message=error_message,
            severity=severity,
        )


class DataRetentionPolicy(Base):
    """Data retention policy configuration."""

    __tablename__ = "data_retention_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Policy details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    resource_type = Column(SQLEnum(AuditResourceType), nullable=False)

    # Retention settings
    retention_days = Column(Integer, nullable=False, default=365)  # Days to keep data
    archive_before_delete = Column(Boolean, default=True)

    # Scope
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    is_global = Column(Boolean, default=False)  # Applies to all orgs if True

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<DataRetentionPolicy {self.name} {self.retention_days}d>"


class ComplianceRequest(Base):
    """GDPR and compliance data requests."""

    __tablename__ = "compliance_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Request type
    request_type = Column(String(50), nullable=False)  # data_export, data_deletion, consent_withdrawal
    status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed

    # Requester
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)

    # Request details
    reason = Column(Text, nullable=True)
    scope = Column(JSON, nullable=True)  # What data to include/delete

    # Processing
    processed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(JSON, nullable=True)  # Processing result/report
    error_message = Column(Text, nullable=True)

    # For data exports
    download_url = Column(String(1000), nullable=True)
    download_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="compliance_requests")
    processed_by = relationship("User", foreign_keys=[processed_by_user_id])

    def __repr__(self) -> str:
        return f"<ComplianceRequest {self.request_type} {self.status}>"
