"""
Upload API routes.

Provides endpoints for PDF document upload and extraction.
"""
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.models.document import Document, DocumentStatus
from backend.models.extract import Extract
from backend.models.line_item import LineItem
from backend.schemas.upload import (
    CellResponse,
    DocumentStatusResponse,
    ErrorResponse,
    RowResponse,
    TableResponse,
    UploadResponse,
)
from backend.services.table_detector import ExtractedTable, get_table_detector
from backend.auth.quota import check_document_quota
from backend.services.analytics_service import AnalyticsService
from backend.models.analytics import MetricType
from backend.middleware.rate_limit import upload_rate_limit

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()


def validate_pdf_file(file: UploadFile) -> None:
    """
    Validate that uploaded file is a PDF.

    Args:
        file: Uploaded file.

    Raises:
        HTTPException: If file is not a valid PDF.
    """
    # Check content type
    if file.content_type not in ["application/pdf", "application/x-pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Only PDF files are accepted.",
        )

    # Check file extension
    if file.filename and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension. Only .pdf files are accepted.",
        )


def save_uploaded_file(file: UploadFile, document_id: uuid.UUID) -> Path:
    """
    Save uploaded file to disk.

    Args:
        file: Uploaded file.
        document_id: Document UUID for filename.

    Returns:
        Path to saved file.
    """
    # Ensure upload directory exists
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Create unique filename
    extension = Path(file.filename).suffix if file.filename else ".pdf"
    file_path = upload_dir / f"{document_id}{extension}"

    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


def convert_table_to_response(table: ExtractedTable) -> TableResponse:
    """
    Convert ExtractedTable to TableResponse schema.

    Args:
        table: Extracted table data.

    Returns:
        TableResponse for API response.
    """
    rows = []
    for row in table.rows:
        cells = [
            CellResponse(
                value=cell.value,
                parsed_value=cell.parsed_value,
                is_numeric=cell.is_numeric,
                row=cell.row,
                column=cell.column,
                bbox=cell.bbox,
                confidence=cell.confidence,
            )
            for cell in row.cells
        ]
        rows.append(RowResponse(cells=cells, row_index=row.row_index))

    return TableResponse(
        page=table.page,
        rows=rows,
        bbox=table.bbox,
        confidence=table.confidence,
        detection_method=table.detection_method,
    )


@router.post(
    "/upload",
    response_model=UploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        413: {"model": ErrorResponse, "description": "File too large"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Processing error"},
    },
    summary="Upload PDF for extraction",
    description="Upload a PDF document to extract financial tables and data. Limited to 20 uploads per hour.",
)
@upload_rate_limit()
async def upload_pdf(
    request: Request,
    file: UploadFile = File(..., description="PDF file to process"),
    db: Session = Depends(get_db),
    _quota_check: bool = Depends(check_document_quota),
) -> UploadResponse:
    """
    Upload and process a PDF document.

    Args:
        file: PDF file to process.
        db: Database session.

    Returns:
        UploadResponse with extracted tables and metadata.
    """
    start_time = time.time()

    # Validate file
    validate_pdf_file(file)

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {file_size} exceeds maximum allowed {settings.max_upload_size_bytes}",
        )

    # Create document record
    document_id = uuid.uuid4()

    try:
        # Save file
        file_path = save_uploaded_file(file, document_id)

        logger.info(
            "File uploaded",
            document_id=str(document_id),
            filename=file.filename,
            size=file_size,
        )

        # Create document record
        document = Document(
            id=document_id,
            filename=file.filename or "unknown.pdf",
            file_path=str(file_path),
            status=DocumentStatus.PROCESSING,
        )
        db.add(document)
        db.commit()

        # Extract tables
        detector = get_table_detector()
        result = detector.detect_tables(file_path)

        # Update document with page count
        document.page_count = result.page_count
        document.status = DocumentStatus.COMPLETED

        # Calculate overall confidence
        if result.tables:
            overall_confidence = sum(t.confidence for t in result.tables) / len(result.tables)
        else:
            overall_confidence = 0.0

        # Create extract record with FULL row data
        def serialize_tables(tables):
            """Serialize tables with full row/cell data for export."""
            result = []
            for table in tables:
                rows_data = []
                for row in table.rows:
                    cells_data = []
                    for cell in row.cells:
                        cells_data.append({
                            "value": str(cell.value) if cell.value else "",
                            "row": cell.row,
                            "column": cell.column,
                            "confidence": cell.confidence,
                            "is_numeric": cell.is_numeric,
                            "parsed_value": float(cell.parsed_value) if cell.parsed_value is not None else None,
                            "bbox": list(cell.bbox) if cell.bbox else None,
                            "reasoning": getattr(cell, "reasoning", None),
                        })
                    rows_data.append({
                        "cells": cells_data,
                        "row_index": row.row_index,
                    })
                
                result.append({
                    "page": table.page,
                    "rows": rows_data,
                    "row_count": len(table.rows),
                    "confidence": table.confidence,
                    "method": table.detection_method,
                })
            return result
        
        extract = Extract(
            document_id=document_id,
            tables_json=serialize_tables(result.tables),
            confidence_score=overall_confidence,
        )
        db.add(extract)
        db.flush()  # Get extract.id without committing

        # Create line items for extracted values
        from decimal import Decimal, InvalidOperation
        line_item_count = 0
        for table in result.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.is_numeric and cell.parsed_value is not None:
                        try:
                            # Use round() to avoid precision issues with floats
                            value = Decimal(str(round(float(cell.parsed_value), 4)))
                        except (InvalidOperation, ValueError, TypeError):
                            continue  # Skip problematic values
                        
                        line_item = LineItem(
                            extract_id=extract.id,
                            label=None,  # Label detection is Phase 2
                            value=value,
                            raw_value=str(cell.value) if cell.value else "",
                            source_page=table.page,
                            bbox=list(cell.bbox) if cell.bbox else None,
                            confidence=float(cell.confidence) if cell.confidence else 0.0,
                            row_index=int(cell.row) if cell.row is not None else 0,
                            column_index=int(cell.column) if cell.column is not None else 0,
                        )
                        db.add(line_item)
                        line_item_count += 1

        db.commit()
        logger.info("Created line items", count=line_item_count)

        # Convert to response
        table_responses = [convert_table_to_response(t) for t in result.tables]

        processing_time = (time.time() - start_time) * 1000

        logger.info(
            "Document processed successfully",
            document_id=str(document_id),
            tables=len(table_responses),
            processing_time_ms=processing_time,
        )

        # Record usage metrics (if user has organization)
        try:
            from backend.auth.dependencies import get_current_active_user
            # Note: In production, you'd get the user from auth context
            # For now, we just record the metric if we can determine the org
            pass  # Metric recording happens via check_document_quota dependency
        except Exception:
            pass  # Continue even if metric recording fails

        return UploadResponse(
            document_id=document_id,
            filename=file.filename or "unknown.pdf",
            page_count=result.page_count,
            tables=table_responses,
            processing_time_ms=processing_time,
            created_at=document.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(
            "Document processing failed",
            document_id=str(document_id),
            error=str(e),
            traceback=error_traceback,
        )
        print(f"UPLOAD ERROR: {error_traceback}")  # Debug print

        # Update document status to failed
        if document_id:
            try:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.status = DocumentStatus.FAILED
                    doc.error_message = str(e)
                    db.commit()
            except Exception as db_error:
                logger.warning(
                    "failed_to_update_document_status",
                    document_id=str(document_id),
                    error=str(db_error),
                )
                db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentStatusResponse,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
    summary="Get document status",
    description="Retrieve the status and metadata of a previously uploaded document.",
)
async def get_document_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentStatusResponse:
    """
    Get status of a document.

    Args:
        document_id: Document UUID.
        db: Database session.

    Returns:
        Document status and metadata.
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    return DocumentStatusResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status.value,
        page_count=document.page_count,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get(
    "/documents/{document_id}/extractions",
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
    summary="Get document extractions",
    description="Retrieve all extracted tables and data for a document.",
)
async def get_document_extractions(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Get extracted tables for a document.

    Args:
        document_id: Document UUID.
        db: Database session.

    Returns:
        List of extracted tables with rows and cells.
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Get all extracts for this document
    extracts = db.query(Extract).filter(Extract.document_id == document_id).all()

    tables = []
    for extract in extracts:
        # Get tables from tables_json field
        if extract.tables_json:
            for table_data in extract.tables_json:
                tables.append({
                    "page": table_data.get("page", 1),
                    "title": table_data.get("title", f"Table {len(tables) + 1}"),
                    "rows": table_data.get("rows", []),
                    "confidence": table_data.get("confidence", extract.confidence_score or 0.0),
                })

    return {
        "document_id": str(document_id),
        "filename": document.filename,
        "tables": tables,
        "total_tables": len(tables),
    }


from pydantic import BaseModel
class CellUpdate(BaseModel):
    page_index: int
    row_index: int
    column_index: int
    reasoning: str | None = None
    value: str | None = None

@router.patch("/documents/{document_id}/extractions/cell")
async def update_extraction_cell(
    document_id: uuid.UUID,
    update: CellUpdate,
    db: Session = Depends(get_db),
):
    """Update a specific cell's data (reasoning or value) in the storage."""
    extract = db.query(Extract).filter(Extract.document_id == document_id).first()
    if not extract or not extract.tables_json:
        raise HTTPException(404, "Extraction not found")

    modified = False
    new_tables = list(extract.tables_json)
    
    # Iterate to find the matching cell
    for table in new_tables:
        if table.get("page") == update.page_index:
            for row in table.get("rows", []):
                if row.get("row_index") == update.row_index:
                    for cell in row.get("cells", []):
                        if cell.get("column") == update.column_index:
                            # Found the cell, update it
                            if update.reasoning is not None:
                                cell["reasoning"] = update.reasoning
                                modified = True
                            if update.value is not None:
                                cell["value"] = update.value
                                modified = True
    
    if modified:
        # Create a new list to force SQLAlchemy to detect the change
        # (JSONB mutation tracking can be tricky)
        extract.tables_json = list(new_tables)
        # Force the update
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(extract, "tables_json")
        
        db.commit()
        return {"success": True, "message": "Cell updated"}
    
    raise HTTPException(404, "Cell not found")

    raise HTTPException(404, "Cell not found")

from fastapi.responses import FileResponse

@router.get(
    "/documents/{document_id}/download",
    response_class=FileResponse,
    summary="Download PDF document",
    description="Download the original PDF document.",
)
async def download_pdf(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Download the PDF file."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(404, "Document not found")
    
    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(404, "File not found on server")
        
    return FileResponse(
        path=file_path,
        filename=document.filename,
        media_type="application/pdf"
    )
