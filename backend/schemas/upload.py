"""
Pydantic schemas for upload API endpoints.

Defines request and response models for document upload and extraction.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CellResponse(BaseModel):
    """Response model for a single table cell."""

    value: str = Field(..., description="Cell text value")
    parsed_value: Optional[float] = Field(None, description="Parsed numeric value if applicable")
    is_numeric: bool = Field(False, description="Whether the cell contains a numeric value")
    row: int = Field(..., description="Row index (0-based)")
    column: int = Field(..., description="Column index (0-based)")
    bbox: Optional[List[float]] = Field(None, description="Bounding box [x0, y0, x1, y1]")
    confidence: float = Field(1.0, description="Extraction confidence (0-1)")


class RowResponse(BaseModel):
    """Response model for a table row."""

    cells: List[CellResponse] = Field(..., description="Cells in this row")
    row_index: int = Field(..., description="Row index (0-based)")


class TableResponse(BaseModel):
    """Response model for an extracted table."""

    page: int = Field(..., description="Page number (1-indexed)")
    rows: List[RowResponse] = Field(..., description="Table rows")
    bbox: Optional[List[float]] = Field(None, description="Table bounding box [x0, y0, x1, y1]")
    confidence: float = Field(..., description="Table extraction confidence (0-1)")
    detection_method: str = Field(..., description="Method used for detection")


class UploadResponse(BaseModel):
    """Response model for document upload."""

    document_id: UUID = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    page_count: int = Field(..., description="Number of pages in document")
    tables: List[TableResponse] = Field(..., description="Extracted tables")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    created_at: datetime = Field(..., description="Upload timestamp")

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class DocumentStatusResponse(BaseModel):
    """Response model for document status query."""

    document_id: UUID = Field(..., description="Document identifier")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    page_count: Optional[int] = Field(None, description="Number of pages")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ErrorResponse(BaseModel):
    """Response model for API errors."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
