"""
Batch processor service for StatementXL.

Handles parallel processing of multiple PDF financial statements.
"""
import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import structlog

from backend.services.table_detector import get_table_detector

logger = structlog.get_logger(__name__)


@dataclass
class BatchJob:
    """Represents a batch processing job."""
    
    id: uuid.UUID
    files: List[Path]
    template_id: Optional[uuid.UUID]
    company_name: Optional[str]
    status: str  # pending, processing, completed, failed
    progress: float  # 0.0 to 1.0
    results: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    created_at: datetime
    completed_at: Optional[datetime] = None


@dataclass
class BatchResult:
    """Result of a batch processing operation."""
    
    job_id: uuid.UUID
    total_files: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    processing_time_ms: float


class BatchProcessor:
    """
    Service for batch processing multiple PDF files.
    
    Features:
    - Parallel processing with configurable concurrency
    - Progress tracking per file
    - Error isolation (one failure doesn't stop batch)
    - Result aggregation
    """
    
    DEFAULT_CONCURRENCY = 3
    
    def __init__(self, max_concurrency: int = DEFAULT_CONCURRENCY):
        """Initialize batch processor."""
        self._max_concurrency = max_concurrency
        self._jobs: Dict[uuid.UUID, BatchJob] = {}
        self._detector = get_table_detector()
    
    def create_job(
        self,
        files: List[Path],
        template_id: Optional[uuid.UUID] = None,
        company_name: Optional[str] = None,
    ) -> BatchJob:
        """
        Create a new batch job.
        
        Args:
            files: List of PDF file paths to process.
            template_id: Optional template to apply to all files.
            company_name: Optional company name for mapping profiles.
            
        Returns:
            Created BatchJob.
        """
        job = BatchJob(
            id=uuid.uuid4(),
            files=files,
            template_id=template_id,
            company_name=company_name,
            status="pending",
            progress=0.0,
            results=[],
            errors=[],
            created_at=datetime.utcnow(),
        )
        self._jobs[job.id] = job
        
        logger.info("Batch job created", job_id=str(job.id), file_count=len(files))
        return job
    
    async def process_job(self, job_id: uuid.UUID) -> BatchResult:
        """
        Process a batch job asynchronously.
        
        Args:
            job_id: ID of the job to process.
            
        Returns:
            BatchResult with all processing outcomes.
        """
        import time
        start_time = time.time()
        
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        job.status = "processing"
        total_files = len(job.files)
        
        # Process files with controlled concurrency
        semaphore = asyncio.Semaphore(self._max_concurrency)
        
        async def process_file(file_path: Path, index: int) -> Dict[str, Any]:
            async with semaphore:
                try:
                    # Run extraction in thread pool (CPU-bound)
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        self._extract_file,
                        file_path,
                    )
                    
                    job.results.append({
                        "file": str(file_path),
                        "status": "success",
                        "tables": result.get("table_count", 0),
                        "confidence": result.get("confidence", 0.0),
                    })
                    
                    return {"status": "success", "file": str(file_path)}
                    
                except Exception as e:
                    error_info = {
                        "file": str(file_path),
                        "error": str(e),
                    }
                    job.errors.append(error_info)
                    
                    logger.warning(
                        "Batch file processing failed",
                        file=str(file_path),
                        error=str(e),
                    )
                    
                    return {"status": "failed", "file": str(file_path), "error": str(e)}
                finally:
                    # Update progress
                    job.progress = (index + 1) / total_files
        
        # Process all files concurrently
        tasks = [
            process_file(file_path, i)
            for i, file_path in enumerate(job.files)
        ]
        await asyncio.gather(*tasks)
        
        # Finalize job
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        
        processing_time = (time.time() - start_time) * 1000
        
        result = BatchResult(
            job_id=job.id,
            total_files=total_files,
            successful=len(job.results),
            failed=len(job.errors),
            results=job.results,
            errors=job.errors,
            processing_time_ms=processing_time,
        )
        
        logger.info(
            "Batch job completed",
            job_id=str(job.id),
            successful=result.successful,
            failed=result.failed,
            time_ms=processing_time,
        )
        
        return result
    
    def _extract_file(self, file_path: Path) -> Dict[str, Any]:
        """Extract tables from a single file."""
        result = self._detector.detect_tables(file_path)
        
        confidence = 0.0
        if result.tables:
            confidence = sum(t.confidence for t in result.tables) / len(result.tables)
        
        return {
            "table_count": len(result.tables),
            "page_count": result.page_count,
            "confidence": confidence,
            "tables": [
                {
                    "page": t.page,
                    "rows": len(t.rows),
                    "confidence": t.confidence,
                }
                for t in result.tables
            ],
        }
    
    def get_job(self, job_id: uuid.UUID) -> Optional[BatchJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def get_job_progress(self, job_id: uuid.UUID) -> Optional[float]:
        """Get job progress (0.0 to 1.0)."""
        job = self._jobs.get(job_id)
        return job.progress if job else None


def get_batch_processor(max_concurrency: int = 3) -> BatchProcessor:
    """Get BatchProcessor instance."""
    return BatchProcessor(max_concurrency=max_concurrency)
