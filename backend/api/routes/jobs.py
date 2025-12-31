"""
Jobs API routes.

Provides endpoints for creating, tracking, and managing background jobs.
"""
import uuid
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.job import Job, JobStatus, JobType
from backend.auth.dependencies import get_current_active_user
from backend.exceptions import NotFoundError, ValidationError

logger = structlog.get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateJobRequest(BaseModel):
    """Request to create a background job."""
    job_type: str = Field(..., description="Type of job: pdf_extract, pdf_classify, excel_export, batch_process")
    document_id: Optional[str] = None
    options: Optional[dict] = None


class JobResponse(BaseModel):
    """Job status response."""
    id: str
    job_type: str
    status: str
    progress: float
    current_step: Optional[str]
    error_message: Optional[str]
    result_data: Optional[dict]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Response for job list."""
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


# =============================================================================
# Job Endpoints
# =============================================================================

@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create background job",
    description="Submit a new background job for processing.",
)
async def create_job(
    request: CreateJobRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JobResponse:
    """Create a new background job."""
    # Validate job type
    try:
        job_type = JobType(request.job_type)
    except ValueError:
        valid_types = [t.value for t in JobType]
        raise ValidationError(
            message="Invalid job type",
            errors=[{"field": "job_type", "message": f"Must be one of: {', '.join(valid_types)}"}]
        )

    # Parse document ID if provided
    document_uuid = None
    if request.document_id:
        try:
            document_uuid = uuid.UUID(request.document_id)
        except ValueError:
            raise ValidationError(
                message="Invalid document ID",
                errors=[{"field": "document_id", "message": "Invalid UUID format"}]
            )

    # Create job record
    job = Job(
        id=uuid.uuid4(),
        job_type=job_type,
        status=JobStatus.PENDING,
        user_id=current_user.id,
        organization_id=current_user.default_organization_id,
        document_id=document_uuid,
        input_data=request.options or {},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Submit to Celery queue
    try:
        from backend.tasks.pdf_tasks import process_pdf, export_excel

        if job_type == JobType.PDF_EXTRACT or job_type == JobType.PDF_CLASSIFY:
            if not document_uuid:
                raise ValidationError(
                    message="Document ID required",
                    errors=[{"field": "document_id", "message": "Document ID is required for PDF processing"}]
                )
            process_pdf.delay(
                str(job.id),
                str(document_uuid),
                str(current_user.id),
                request.options,
            )
        elif job_type == JobType.EXCEL_EXPORT:
            if not document_uuid:
                raise ValidationError(
                    message="Document ID required",
                    errors=[{"field": "document_id", "message": "Document ID is required for Excel export"}]
                )
            export_excel.delay(
                str(job.id),
                str(document_uuid),
                str(current_user.id),
                request.options or {},
            )

    except Exception as e:
        logger.error("failed_to_queue_job", job_id=str(job.id), error=str(e))
        # Job is created but not queued - will be picked up by a cleanup task
        job.error_message = f"Failed to queue: {str(e)}"
        db.commit()

    logger.info("job_created", job_id=str(job.id), job_type=job_type.value, user_id=str(current_user.id))

    return JobResponse(
        id=str(job.id),
        job_type=job.job_type.value,
        status=job.status.value,
        progress=job.progress,
        current_step=job.current_step,
        error_message=job.error_message,
        result_data=job.result_data,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get(
    "",
    response_model=JobListResponse,
    summary="List user's jobs",
    description="Get paginated list of current user's jobs.",
)
async def list_jobs(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JobListResponse:
    """List user's background jobs."""
    query = db.query(Job).filter(Job.user_id == current_user.id)

    # Filter by status if provided
    if status_filter:
        try:
            status_enum = JobStatus(status_filter)
            query = query.filter(Job.status == status_enum)
        except ValueError:
            pass  # Ignore invalid status filter

    # Get total count
    total = query.count()

    # Get paginated results
    offset = (page - 1) * page_size
    jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size).all()

    return JobListResponse(
        jobs=[
            JobResponse(
                id=str(j.id),
                job_type=j.job_type.value,
                status=j.status.value,
                progress=j.progress,
                current_step=j.current_step,
                error_message=j.error_message,
                result_data=j.result_data,
                created_at=j.created_at,
                started_at=j.started_at,
                completed_at=j.completed_at,
            )
            for j in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
    description="Get the current status and progress of a job.",
)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JobResponse:
    """Get job status by ID."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise NotFoundError("Job", job_id)

    job = db.query(Job).filter(
        Job.id == job_uuid,
        Job.user_id == current_user.id,
    ).first()

    if not job:
        raise NotFoundError("Job", job_id)

    return JobResponse(
        id=str(job.id),
        job_type=job.job_type.value,
        status=job.status.value,
        progress=job.progress,
        current_step=job.current_step,
        error_message=job.error_message,
        result_data=job.result_data,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.delete(
    "/{job_id}",
    response_model=MessageResponse,
    summary="Cancel job",
    description="Cancel a pending or processing job.",
)
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """Cancel a background job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise NotFoundError("Job", job_id)

    job = db.query(Job).filter(
        Job.id == job_uuid,
        Job.user_id == current_user.id,
    ).first()

    if not job:
        raise NotFoundError("Job", job_id)

    # Can only cancel pending or processing jobs
    if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
        raise ValidationError(
            message="Cannot cancel job",
            errors=[{"field": "status", "message": f"Job with status '{job.status.value}' cannot be cancelled"}]
        )

    # Try to revoke Celery task
    if job.celery_task_id:
        try:
            from backend.celery_app import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)
        except Exception as e:
            logger.warning("failed_to_revoke_task", job_id=job_id, error=str(e))

    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    db.commit()

    logger.info("job_cancelled", job_id=str(job.id), user_id=str(current_user.id))

    return MessageResponse(message="Job cancelled successfully")


@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    summary="Retry failed job",
    description="Retry a failed job.",
)
async def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JobResponse:
    """Retry a failed job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise NotFoundError("Job", job_id)

    job = db.query(Job).filter(
        Job.id == job_uuid,
        Job.user_id == current_user.id,
    ).first()

    if not job:
        raise NotFoundError("Job", job_id)

    # Can only retry failed jobs
    if job.status != JobStatus.FAILED:
        raise ValidationError(
            message="Cannot retry job",
            errors=[{"field": "status", "message": "Only failed jobs can be retried"}]
        )

    # Reset job status
    job.status = JobStatus.PENDING
    job.error_message = None
    job.progress = 0.0
    job.current_step = None
    job.started_at = None
    job.completed_at = None
    job.retry_count += 1
    db.commit()

    # Resubmit to queue
    try:
        from backend.tasks.pdf_tasks import process_pdf, export_excel

        if job.job_type in [JobType.PDF_EXTRACT, JobType.PDF_CLASSIFY]:
            process_pdf.delay(
                str(job.id),
                str(job.document_id),
                str(current_user.id),
                job.input_data,
            )
        elif job.job_type == JobType.EXCEL_EXPORT:
            export_excel.delay(
                str(job.id),
                str(job.document_id),
                str(current_user.id),
                job.input_data or {},
            )
    except Exception as e:
        logger.error("failed_to_requeue_job", job_id=str(job.id), error=str(e))
        job.error_message = f"Failed to requeue: {str(e)}"
        db.commit()

    logger.info("job_retried", job_id=str(job.id), user_id=str(current_user.id))

    return JobResponse(
        id=str(job.id),
        job_type=job.job_type.value,
        status=job.status.value,
        progress=job.progress,
        current_step=job.current_step,
        error_message=job.error_message,
        result_data=job.result_data,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
