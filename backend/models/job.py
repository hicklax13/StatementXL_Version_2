"""
Job model for tracking background tasks.

Stores job status, progress, and results for async task processing.
"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"      # Job created, waiting for worker
    PROCESSING = "processing"  # Worker picked up the job
    COMPLETED = "completed"  # Job finished successfully
    FAILED = "failed"        # Job failed with error
    CANCELLED = "cancelled"  # Job was cancelled
    RETRYING = "retrying"    # Job is being retried


class JobType(str, Enum):
    """Job type enumeration."""
    PDF_EXTRACT = "pdf_extract"      # Extract tables from PDF
    PDF_CLASSIFY = "pdf_classify"    # Classify extracted items
    EXCEL_EXPORT = "excel_export"    # Export to Excel template
    BATCH_PROCESS = "batch_process"  # Process multiple PDFs


class Job(Base):
    """Background job tracking model."""

    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Job identification
    celery_task_id = Column(String(255), unique=True, nullable=True, index=True)
    job_type = Column(SQLEnum(JobType), nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False)

    # Progress tracking
    progress = Column(Float, default=0.0, nullable=False)  # 0.0 to 1.0
    current_step = Column(String(255), nullable=True)
    total_steps = Column(Integer, default=1, nullable=False)
    completed_steps = Column(Integer, default=0, nullable=False)

    # Input/Output
    input_data = Column(JSONB, nullable=True)  # Job parameters
    result_data = Column(JSONB, nullable=True)  # Job results
    error_message = Column(Text, nullable=True)

    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    # Retry tracking
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="jobs")

    def __repr__(self) -> str:
        return f"<Job {self.id} type={self.job_type} status={self.status}>"

    def update_progress(self, progress: float, current_step: str = None) -> None:
        """Update job progress."""
        self.progress = min(max(progress, 0.0), 1.0)
        if current_step:
            self.current_step = current_step
        self.updated_at = datetime.utcnow()

    def mark_processing(self) -> None:
        """Mark job as processing."""
        self.status = JobStatus.PROCESSING
        self.started_at = datetime.utcnow()

    def mark_completed(self, result_data: dict = None) -> None:
        """Mark job as completed."""
        self.status = JobStatus.COMPLETED
        self.progress = 1.0
        self.completed_at = datetime.utcnow()
        if result_data:
            self.result_data = result_data

    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.utcnow()

    def should_retry(self) -> bool:
        """Check if job should be retried."""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """Increment retry counter."""
        self.retry_count += 1
        self.status = JobStatus.RETRYING
