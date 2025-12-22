"""
Batch processing API routes for StatementXL.

Provides endpoints for batch file uploads and processing.
"""
import asyncio
import uuid
from pathlib import Path
from typing import List, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.batch_processor import get_batch_processor, BatchResult

logger = structlog.get_logger(__name__)

router = APIRouter()


class BatchJobCreate(BaseModel):
    """Request to create batch job."""
    template_id: Optional[str] = None
    company_name: Optional[str] = None


class BatchJobResponse(BaseModel):
    """Response for batch job creation."""
    job_id: str
    file_count: int
    status: str


class BatchStatusResponse(BaseModel):
    """Response for batch job status."""
    job_id: str
    status: str
    progress: float
    successful: int
    failed: int
    total: int


class BatchResultResponse(BaseModel):
    """Response for batch job completion."""
    job_id: str
    total_files: int
    successful: int
    failed: int
    processing_time_ms: float
    results: List[dict]
    errors: List[dict]


# In-memory storage for uploaded files (replace with proper storage in production)
_batch_files: dict = {}


@router.post(
    "/batch/upload",
    response_model=BatchJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload files for batch processing",
)
async def upload_batch_files(
    files: List[UploadFile] = File(...),
    template_id: Optional[str] = None,
    company_name: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
) -> BatchJobResponse:
    """
    Upload multiple PDF files for batch processing.
    
    Args:
        files: List of PDF files to process.
        template_id: Optional template to apply.
        company_name: Optional company name for mapping.
        
    Returns:
        BatchJobResponse with job ID.
    """
    # Validate files
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {file.filename} is not a PDF",
            )
    
    # Create batch processor
    processor = get_batch_processor()
    
    # Save files temporarily and create job
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    
    file_paths = []
    for file in files:
        file_path = temp_dir / f"{uuid.uuid4()}_{file.filename}"
        content = await file.read()
        file_path.write_bytes(content)
        file_paths.append(file_path)
    
    # Create job
    job = processor.create_job(
        files=file_paths,
        template_id=uuid.UUID(template_id) if template_id else None,
        company_name=company_name,
    )
    
    # Store file paths for cleanup
    _batch_files[str(job.id)] = file_paths
    
    logger.info(
        "Batch job created",
        job_id=str(job.id),
        file_count=len(files),
    )
    
    return BatchJobResponse(
        job_id=str(job.id),
        file_count=len(files),
        status="pending",
    )


@router.post(
    "/batch/{job_id}/process",
    response_model=BatchResultResponse,
    summary="Start batch processing",
)
async def process_batch(
    job_id: str,
    db: Session = Depends(get_db),
) -> BatchResultResponse:
    """
    Start processing a batch job.
    
    Args:
        job_id: ID of the batch job.
        
    Returns:
        BatchResultResponse with processing results.
    """
    processor = get_batch_processor()
    job = processor.get_job(uuid.UUID(job_id))
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch job {job_id} not found",
        )
    
    # Process the job
    result = await processor.process_job(uuid.UUID(job_id))
    
    # Cleanup temp files
    file_paths = _batch_files.pop(job_id, [])
    for path in file_paths:
        try:
            path.unlink()
        except Exception:
            pass
    
    return BatchResultResponse(
        job_id=str(result.job_id),
        total_files=result.total_files,
        successful=result.successful,
        failed=result.failed,
        processing_time_ms=result.processing_time_ms,
        results=result.results,
        errors=result.errors,
    )


@router.get(
    "/batch/{job_id}",
    response_model=BatchStatusResponse,
    summary="Get batch job status",
)
async def get_batch_status(
    job_id: str,
) -> BatchStatusResponse:
    """
    Get the status of a batch job.
    
    Args:
        job_id: ID of the batch job.
        
    Returns:
        BatchStatusResponse with current status.
    """
    processor = get_batch_processor()
    job = processor.get_job(uuid.UUID(job_id))
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch job {job_id} not found",
        )
    
    return BatchStatusResponse(
        job_id=str(job.id),
        status=job.status,
        progress=job.progress,
        successful=len(job.results),
        failed=len(job.errors),
        total=len(job.files),
    )


@router.delete(
    "/batch/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel batch job",
)
async def cancel_batch(
    job_id: str,
) -> None:
    """
    Cancel a pending batch job.
    
    Args:
        job_id: ID of the batch job to cancel.
    """
    # Cleanup temp files
    file_paths = _batch_files.pop(job_id, [])
    for path in file_paths:
        try:
            path.unlink()
        except Exception:
            pass
    
    logger.info("Batch job cancelled", job_id=job_id)
