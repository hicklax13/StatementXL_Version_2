"""
StatementXL Engine API routes.

Provides endpoints for running the GPT-5.2-like financial statement extraction
and mapping engine.
"""

import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.auth.dependencies import get_current_active_user
from backend.models.user import User

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class EngineRunRequest(BaseModel):
    """Request to run the StatementXL engine."""
    statement_type: Optional[str] = Field(
        None,
        description="Statement type: 'income_statement', 'balance_sheet', 'cash_flow', or None for auto-detect"
    )
    target_period: Optional[str] = Field(
        None,
        description="Target period to filter (e.g., 'FY2024', 'Q3_2024')"
    )
    skip_validation: bool = Field(
        False,
        description="Skip reconciliation validation checks"
    )


class EngineRunResponse(BaseModel):
    """Response from engine run."""
    run_id: str
    success: bool
    output_filename: Optional[str] = None
    download_url: Optional[str] = None
    facts_extracted: int = 0
    facts_mapped: int = 0
    cells_posted: int = 0
    reconciliation_passed: bool = True
    confidence_level: str = "high"
    error_message: Optional[str] = None


class EngineJobStatus(BaseModel):
    """Status of an engine job."""
    run_id: str
    status: str  # pending, processing, completed, failed
    progress: float = 0.0
    current_step: Optional[str] = None
    result: Optional[EngineRunResponse] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/engine/run",
    response_model=EngineRunResponse,
    summary="Run StatementXL Engine",
    description="Process PDF(s) and populate Excel template with extracted financial data.",
)
async def run_engine_sync(
    template: UploadFile = File(..., description="Excel template file"),
    pdfs: List[UploadFile] = File(..., description="PDF files to process"),
    statement_type: Optional[str] = Form(None),
    target_period: Optional[str] = Form(None),
    skip_validation: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> EngineRunResponse:
    """
    Run the StatementXL engine synchronously.

    Uploads template and PDF files, runs the engine, and returns the result.
    The output file is available for download via the returned URL.
    """
    run_id = str(uuid.uuid4())

    logger.info(
        "Engine run requested",
        run_id=run_id,
        template=template.filename,
        pdfs=[p.filename for p in pdfs],
        statement_type=statement_type,
        user_id=str(current_user.id),
    )

    try:
        # Create temp directory for this run
        run_dir = settings.upload_dir / "engine_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save template
        template_path = run_dir / template.filename
        with open(template_path, "wb") as f:
            shutil.copyfileobj(template.file, f)

        # Save PDFs
        pdf_paths = []
        for pdf in pdfs:
            pdf_path = run_dir / pdf.filename
            with open(pdf_path, "wb") as f:
                shutil.copyfileobj(pdf.file, f)
            pdf_paths.append(pdf_path)

        # Import and run engine
        from backend.statementxl_engine import run_engine, EngineOptions

        options = EngineOptions(
            statement_type=statement_type,
            target_period=target_period,
            skip_validation=skip_validation,
        )

        result = run_engine(
            template_path=template_path,
            pdf_paths=pdf_paths,
            statement_type=statement_type,
            options=options,
        )

        if result.success:
            output_path = Path(result.output_path)
            download_url = f"/api/v1/engine/download/{run_id}/{output_path.name}"

            return EngineRunResponse(
                run_id=run_id,
                success=True,
                output_filename=output_path.name,
                download_url=download_url,
                facts_extracted=result.total_facts_extracted,
                facts_mapped=result.facts_mapped,
                cells_posted=result.cells_posted,
                reconciliation_passed=result.reconciliation_passed,
                confidence_level=result.confidence_level.value,
            )
        else:
            return EngineRunResponse(
                run_id=run_id,
                success=False,
                error_message=result.error_message,
            )

    except Exception as e:
        import traceback
        error_tb = traceback.format_exc()
        logger.error(
            "Engine run failed",
            run_id=run_id,
            error=str(e),
            traceback=error_tb,
        )
        return EngineRunResponse(
            run_id=run_id,
            success=False,
            error_message=str(e),
        )


@router.get(
    "/engine/download/{run_id}/{filename}",
    response_class=FileResponse,
    summary="Download engine output",
    description="Download the output Excel file from an engine run.",
)
async def download_engine_output(
    run_id: str,
    filename: str,
    current_user: User = Depends(get_current_active_user),
):
    """Download the output file from an engine run."""
    run_dir = settings.upload_dir / "engine_runs" / run_id
    file_path = run_dir / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file not found",
        )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post(
    "/engine/run-async",
    response_model=EngineJobStatus,
    summary="Run StatementXL Engine (Async)",
    description="Start engine run as background job. Poll status endpoint for progress.",
)
async def run_engine_async(
    background_tasks: BackgroundTasks,
    template: UploadFile = File(...),
    pdfs: List[UploadFile] = File(...),
    statement_type: Optional[str] = Form(None),
    target_period: Optional[str] = Form(None),
    skip_validation: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> EngineJobStatus:
    """
    Start engine run as background task.

    Returns immediately with job ID. Poll /engine/status/{run_id} for progress.
    """
    run_id = str(uuid.uuid4())

    # Save files
    run_dir = settings.upload_dir / "engine_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    template_path = run_dir / template.filename
    with open(template_path, "wb") as f:
        shutil.copyfileobj(template.file, f)

    pdf_paths = []
    for pdf in pdfs:
        pdf_path = run_dir / pdf.filename
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(pdf.file, f)
        pdf_paths.append(str(pdf_path))

    # Add background task
    background_tasks.add_task(
        _run_engine_background,
        run_id=run_id,
        template_path=str(template_path),
        pdf_paths=pdf_paths,
        statement_type=statement_type,
        target_period=target_period,
        skip_validation=skip_validation,
    )

    return EngineJobStatus(
        run_id=run_id,
        status="pending",
        progress=0.0,
        current_step="Queued for processing",
    )


async def _run_engine_background(
    run_id: str,
    template_path: str,
    pdf_paths: List[str],
    statement_type: Optional[str],
    target_period: Optional[str],
    skip_validation: bool,
):
    """Background task to run the engine."""
    try:
        from backend.statementxl_engine import run_engine, EngineOptions

        options = EngineOptions(
            statement_type=statement_type,
            target_period=target_period,
            skip_validation=skip_validation,
        )

        result = run_engine(
            template_path=Path(template_path),
            pdf_paths=[Path(p) for p in pdf_paths],
            statement_type=statement_type,
            options=options,
        )

        # Store result (in production, would store in Redis/DB)
        logger.info(
            "Background engine run complete",
            run_id=run_id,
            success=result.success,
        )

    except Exception as e:
        logger.error(
            "Background engine run failed",
            run_id=run_id,
            error=str(e),
        )


@router.get(
    "/engine/status/{run_id}",
    response_model=EngineJobStatus,
    summary="Get engine job status",
    description="Get status of an async engine job.",
)
async def get_engine_status(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
) -> EngineJobStatus:
    """Get status of an async engine job."""
    run_dir = settings.upload_dir / "engine_runs" / run_id

    if not run_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Check for output file
    output_files = list(run_dir.glob("StatementXL_Mapped_*.xlsx"))

    if output_files:
        output_file = output_files[0]
        return EngineJobStatus(
            run_id=run_id,
            status="completed",
            progress=1.0,
            current_step="Complete",
            result=EngineRunResponse(
                run_id=run_id,
                success=True,
                output_filename=output_file.name,
                download_url=f"/api/v1/engine/download/{run_id}/{output_file.name}",
            ),
        )

    # Still processing
    return EngineJobStatus(
        run_id=run_id,
        status="processing",
        progress=0.5,
        current_step="Processing...",
    )
