"""
Analytics models for usage tracking and metrics.

Provides comprehensive tracking of:
- Document processing metrics
- API usage statistics
- Storage consumption
- Organization quotas and limits
"""
import uuid
from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Date, Enum as SQLEnum, ForeignKey, String, Text, Integer, Float, BigInteger, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class MetricType(str, Enum):
    """Types of metrics tracked."""
    # Document metrics
    DOCUMENTS_UPLOADED = "documents_uploaded"
    DOCUMENTS_PROCESSED = "documents_processed"
    DOCUMENTS_FAILED = "documents_failed"
    PAGES_PROCESSED = "pages_processed"

    # Export metrics
    EXPORTS_GENERATED = "exports_generated"
    EXPORTS_DOWNLOADED = "exports_downloaded"

    # API metrics
    API_REQUESTS = "api_requests"
    API_ERRORS = "api_errors"

    # Storage metrics
    STORAGE_USED_BYTES = "storage_used_bytes"

    # Classification metrics
    CLASSIFICATIONS_RUN = "classifications_run"
    CLASSIFICATIONS_MANUAL = "classifications_manual"

    # Integration metrics
    INTEGRATION_SYNCS = "integration_syncs"

    # User metrics
    ACTIVE_USERS = "active_users"
    LOGIN_COUNT = "login_count"


class UsageMetric(Base):
    """Daily usage metrics aggregated by organization."""

    __tablename__ = "usage_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scope
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_date = Column(Date, nullable=False, index=True)
    metric_type = Column(SQLEnum(MetricType), nullable=False, index=True)

    # Values
    count = Column(BigInteger, default=0, nullable=False)
    total_value = Column(Float, default=0.0, nullable=True)  # For things like processing time

    # Metadata
    metadata = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", backref="usage_metrics")

    # Composite indexes
    __table_args__ = (
        Index('ix_usage_metrics_org_date', 'organization_id', 'metric_date'),
        Index('ix_usage_metrics_org_type_date', 'organization_id', 'metric_type', 'metric_date'),
    )

    def __repr__(self) -> str:
        return f"<UsageMetric {self.metric_type.value} {self.metric_date} count={self.count}>"


class OrganizationQuota(Base):
    """Quota limits for organizations."""

    __tablename__ = "organization_quotas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scope
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Document limits
    max_documents_per_month = Column(Integer, default=100, nullable=False)
    max_pages_per_document = Column(Integer, default=50, nullable=False)
    max_file_size_mb = Column(Integer, default=25, nullable=False)

    # Storage limits
    max_storage_gb = Column(Float, default=5.0, nullable=False)

    # API limits
    max_api_requests_per_day = Column(Integer, default=1000, nullable=False)
    max_api_requests_per_minute = Column(Integer, default=60, nullable=False)

    # User limits
    max_users = Column(Integer, default=5, nullable=False)
    max_api_keys = Column(Integer, default=10, nullable=False)

    # Integration limits
    max_integrations = Column(Integer, default=2, nullable=False)

    # Feature flags
    allow_batch_processing = Column(Boolean, default=True, nullable=False)
    allow_api_access = Column(Boolean, default=True, nullable=False)
    allow_webhooks = Column(Boolean, default=True, nullable=False)
    allow_integrations = Column(Boolean, default=False, nullable=False)

    # Billing
    plan_name = Column(String(50), default="free", nullable=False)
    billing_cycle_start = Column(Date, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    organization = relationship("Organization", backref="quota", uselist=False)

    def __repr__(self) -> str:
        return f"<OrganizationQuota {self.plan_name} org={self.organization_id}>"


class ProcessingStats(Base):
    """Individual document processing statistics."""

    __tablename__ = "processing_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Reference
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    document_id = Column(String(255), nullable=True, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)

    # Document info
    filename = Column(String(500), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    page_count = Column(Integer, nullable=True)
    statement_type = Column(String(50), nullable=True)

    # Processing metrics
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_duration_ms = Column(Integer, nullable=True)

    # Stage timings
    upload_duration_ms = Column(Integer, nullable=True)
    extraction_duration_ms = Column(Integer, nullable=True)
    classification_duration_ms = Column(Integer, nullable=True)
    export_duration_ms = Column(Integer, nullable=True)

    # Results
    tables_extracted = Column(Integer, nullable=True)
    rows_extracted = Column(Integer, nullable=True)
    items_classified = Column(Integer, nullable=True)
    classification_confidence_avg = Column(Float, nullable=True)

    # Status
    success = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    error_stage = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organization = relationship("Organization")
    user = relationship("User")

    # Indexes
    __table_args__ = (
        Index('ix_processing_stats_org_created', 'organization_id', 'created_at'),
    )

    def __repr__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"<ProcessingStats {status} {self.filename}>"

    def calculate_duration(self) -> Optional[int]:
        """Calculate total processing duration in milliseconds."""
        if self.processing_started_at and self.processing_completed_at:
            delta = self.processing_completed_at - self.processing_started_at
            return int(delta.total_seconds() * 1000)
        return None


class DailyActiveUsers(Base):
    """Track daily active users per organization."""

    __tablename__ = "daily_active_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    activity_date = Column(Date, nullable=False)

    # Activity counts
    login_count = Column(Integer, default=0, nullable=False)
    api_request_count = Column(Integer, default=0, nullable=False)
    document_uploads = Column(Integer, default=0, nullable=False)
    exports_created = Column(Integer, default=0, nullable=False)

    # Session info
    first_activity_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('ix_dau_org_date', 'organization_id', 'activity_date'),
        Index('ix_dau_user_date', 'user_id', 'activity_date', unique=True),
    )

    def __repr__(self) -> str:
        return f"<DailyActiveUsers {self.activity_date} user={self.user_id}>"


class BillingEvent(Base):
    """Track billable events for usage-based billing."""

    __tablename__ = "billing_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scope
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Event details
    event_type = Column(String(50), nullable=False)  # document_processed, api_call, storage_used, etc.
    quantity = Column(Float, default=1.0, nullable=False)
    unit = Column(String(20), nullable=True)  # documents, requests, GB, etc.

    # Pricing
    unit_price = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=True)
    currency = Column(String(3), default="USD", nullable=False)

    # Reference
    reference_id = Column(String(255), nullable=True)  # Document ID, Job ID, etc.
    reference_type = Column(String(50), nullable=True)

    # Billing period
    billing_period_start = Column(Date, nullable=True)
    billing_period_end = Column(Date, nullable=True)

    # Status
    is_billed = Column(Boolean, default=False, nullable=False)
    billed_at = Column(DateTime(timezone=True), nullable=True)
    invoice_id = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    organization = relationship("Organization", backref="billing_events")

    __table_args__ = (
        Index('ix_billing_events_org_created', 'organization_id', 'created_at'),
        Index('ix_billing_events_unbilled', 'organization_id', 'is_billed'),
    )

    def __repr__(self) -> str:
        return f"<BillingEvent {self.event_type} qty={self.quantity}>"
