"""
Data Transfer API routes.

Provides endpoints for importing and exporting data.
"""
import uuid
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.dependencies import get_current_active_user
from backend.models.user import User
from backend.services.import_export_service import (
    get_import_export_service,
    ExportFormat,
    ImportFormat,
    ExportOptions,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# ==================== Schemas ====================

class ExportRequest(BaseModel):
    """Export request options."""
    format: str = Field("json", pattern="^(json|csv|xlsx|xml)$")
    include_metadata: bool = True
    include_relationships: bool = False
    fields: Optional[List[str]] = None
    compress: bool = False
    ids: Optional[List[str]] = None


class ImportResponse(BaseModel):
    """Import result response."""
    success: bool
    total_records: int
    imported: int
    skipped: int
    errors: List[dict]
    warnings: List[str]


class BackupInfo(BaseModel):
    """Backup information."""
    filename: str
    size_bytes: int
    created_at: str
    contents: List[str]


# ==================== Export Endpoints ====================

@router.post(
    "/export/documents",
    summary="Export documents",
    response_class=Response,
)
async def export_documents(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    """
    Export documents in specified format.

    Supported formats: json, csv, xlsx, xml

    Options:
    - include_metadata: Include file paths and error messages
    - include_relationships: Include related extracts and line items
    - fields: Specific fields to include (empty = all)
    - compress: Compress output as ZIP
    - ids: Specific document IDs to export (empty = all)
    """
    service = get_import_export_service(db)

    # Parse document IDs
    document_ids = None
    if request.ids:
        try:
            document_ids = [uuid.UUID(id_str) for id_str in request.ids]
        except ValueError:
            raise HTTPException(400, "Invalid document ID format")

    # Build options
    format_map = {
        "json": ExportFormat.JSON,
        "csv": ExportFormat.CSV,
        "xlsx": ExportFormat.XLSX,
        "xml": ExportFormat.XML,
    }

    options = ExportOptions(
        format=format_map.get(request.format, ExportFormat.JSON),
        include_metadata=request.include_metadata,
        include_relationships=request.include_relationships,
        fields=request.fields,
        compress=request.compress,
    )

    # Export
    content, filename = service.export_documents(
        user_id=current_user.id,
        options=options,
        document_ids=document_ids,
    )

    # Determine content type
    content_types = {
        "json": "application/json",
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xml": "application/xml",
    }

    content_type = content_types.get(request.format, "application/octet-stream")
    if request.compress:
        content_type = "application/zip"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post(
    "/export/templates",
    summary="Export templates",
    response_class=Response,
)
async def export_templates(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    """Export templates in specified format."""
    service = get_import_export_service(db)

    template_ids = None
    if request.ids:
        try:
            template_ids = [uuid.UUID(id_str) for id_str in request.ids]
        except ValueError:
            raise HTTPException(400, "Invalid template ID format")

    format_map = {
        "json": ExportFormat.JSON,
        "csv": ExportFormat.CSV,
    }

    options = ExportOptions(
        format=format_map.get(request.format, ExportFormat.JSON),
        include_metadata=request.include_metadata,
        fields=request.fields,
        compress=request.compress,
    )

    content, filename = service.export_templates(
        user_id=current_user.id,
        options=options,
        template_ids=template_ids,
    )

    content_type = "application/json" if request.format == "json" else "text/csv"
    if request.compress:
        content_type = "application/zip"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post(
    "/export/backup",
    summary="Create full backup",
    response_class=Response,
)
async def create_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    """
    Create full data backup as ZIP archive.

    Includes all documents, templates, and mappings.
    Can be used to restore data or migrate to another instance.
    """
    service = get_import_export_service(db)

    content, filename = service.export_full_backup(
        user_id=current_user.id,
        organization_id=current_user.default_organization_id,
    )

    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ==================== Import Endpoints ====================

@router.post(
    "/import/documents",
    response_model=ImportResponse,
    summary="Import documents",
)
async def import_documents(
    file: UploadFile = File(...),
    format: str = Query("json", pattern="^(json|csv)$"),
    update_existing: bool = Query(False, description="Update existing records by ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ImportResponse:
    """
    Import document metadata from file.

    Supported formats: json, csv

    Note: This imports document metadata only. Actual PDF files
    must be uploaded separately via the upload endpoint.
    """
    service = get_import_export_service(db)

    # Read file content
    content = await file.read()

    format_map = {
        "json": ImportFormat.JSON,
        "csv": ImportFormat.CSV,
    }

    result = service.import_documents(
        file_content=content,
        format=format_map.get(format, ImportFormat.JSON),
        user_id=current_user.id,
        organization_id=current_user.default_organization_id,
        update_existing=update_existing,
    )

    return ImportResponse(
        success=result.success,
        total_records=result.total_records,
        imported=result.imported,
        skipped=result.skipped,
        errors=result.errors,
        warnings=result.warnings,
    )


@router.post(
    "/import/mappings",
    response_model=ImportResponse,
    summary="Import mapping profiles",
)
async def import_mappings(
    file: UploadFile = File(...),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ImportResponse:
    """Import mapping profiles from file."""
    service = get_import_export_service(db)

    content = await file.read()

    format_map = {
        "json": ImportFormat.JSON,
        "csv": ImportFormat.CSV,
    }

    result = service.import_mappings(
        file_content=content,
        format=format_map.get(format, ImportFormat.JSON),
        user_id=current_user.id,
    )

    return ImportResponse(
        success=result.success,
        total_records=result.total_records,
        imported=result.imported,
        skipped=result.skipped,
        errors=result.errors,
        warnings=result.warnings,
    )


@router.post(
    "/import/restore",
    summary="Restore from backup",
)
async def restore_backup(
    file: UploadFile = File(...),
    merge: bool = Query(False, description="Merge with existing data"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Restore data from backup ZIP file.

    Options:
    - merge: If true, updates existing records instead of skipping
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(400, "Backup file must be a ZIP archive")

    service = get_import_export_service(db)

    content = await file.read()

    results = service.restore_backup(
        file_content=content,
        user_id=current_user.id,
        merge=merge,
    )

    return {
        "success": all(r.success for r in results.values() if hasattr(r, 'success')),
        "results": {
            entity: {
                "imported": r.imported,
                "skipped": r.skipped,
                "errors": len(r.errors),
            }
            for entity, r in results.items()
            if hasattr(r, 'imported')
        },
    }


# ==================== Format Information ====================

@router.get(
    "/formats",
    summary="Get supported formats",
)
async def get_formats() -> dict:
    """Get information about supported import/export formats."""
    return {
        "export": {
            "json": {
                "name": "JSON",
                "extension": ".json",
                "mime_type": "application/json",
                "features": ["metadata", "relationships", "pretty_print", "compress"],
            },
            "csv": {
                "name": "CSV",
                "extension": ".csv",
                "mime_type": "text/csv",
                "features": ["compress"],
            },
            "xlsx": {
                "name": "Excel",
                "extension": ".xlsx",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "features": ["compress"],
            },
            "xml": {
                "name": "XML",
                "extension": ".xml",
                "mime_type": "application/xml",
                "features": ["metadata", "compress"],
            },
        },
        "import": {
            "json": {
                "name": "JSON",
                "extension": ".json",
            },
            "csv": {
                "name": "CSV",
                "extension": ".csv",
            },
        },
        "backup": {
            "format": "zip",
            "contents": ["documents.json", "templates.json", "manifest.json"],
        },
    }
