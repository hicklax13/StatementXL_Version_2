"""
Template API routes.

Provides endpoints for uploading and analyzing Excel templates.
"""
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.models.template import (
    Template,
    TemplateCell,
    TemplateStatus,
    TemplateStructure,
    CellType,
)
from backend.services.excel_parser import get_excel_parser
from backend.services.tkg_builder import get_tkg_builder
from backend.services.structure_inferencer import get_structure_inferencer
from backend.services.semantic_aligner import get_semantic_aligner

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()


# Response Models
class SectionResponse(BaseModel):
    """Response model for a detected section."""

    name: str
    section_type: str
    sheet: str
    start_row: int
    end_row: int
    confidence: float


class PeriodResponse(BaseModel):
    """Response model for a detected period."""

    column: int
    column_letter: str
    label: str
    frequency: str
    year: Optional[int]
    quarter: Optional[int]


class CellResponse(BaseModel):
    """Response model for a template cell."""

    address: str
    sheet: str
    row: int
    column: int
    label: str
    ontology_id: Optional[str]
    ontology_label: Optional[str]
    confidence: float
    section_type: Optional[str]


class StructureResponse(BaseModel):
    """Response model for template structure."""

    sections: List[SectionResponse]
    periods: List[PeriodResponse]
    aligned_cells: List[CellResponse]
    total_cells: int
    aligned_count: int
    high_confidence_count: int
    input_cells: int
    calculated_cells: int


class TemplateUploadResponse(BaseModel):
    """Response model for template upload."""

    template_id: str
    filename: str
    sheet_count: int
    status: str
    processing_time_ms: float
    structure: Optional[StructureResponse]


class TemplateStatusResponse(BaseModel):
    """Response model for template status."""

    template_id: str
    filename: str
    status: str
    sheet_count: Optional[int]
    error_message: Optional[str]
    created_at: str


class GraphExportResponse(BaseModel):
    """Response model for graph export."""

    format: str
    content: str


def validate_excel_file(file: UploadFile) -> None:
    """Validate uploaded file is Excel."""
    valid_types = [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]

    if file.content_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Only Excel files accepted.",
        )

    if not file.filename or not (
        file.filename.endswith(".xlsx") or file.filename.endswith(".xls")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension. Only .xlsx or .xls files accepted.",
        )


def save_template_file(file: UploadFile, template_id: uuid.UUID) -> Path:
    """Save uploaded template file."""
    upload_dir = settings.upload_dir / "templates"
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(file.filename).suffix if file.filename else ".xlsx"
    file_path = upload_dir / f"{template_id}{extension}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


@router.post(
    "/template/upload",
    response_model=TemplateUploadResponse,
    summary="Upload Excel template",
    description="Upload an Excel template for structure analysis.",
)
async def upload_template(
    file: UploadFile = File(..., description="Excel file to analyze"),
    db: Session = Depends(get_db),
) -> TemplateUploadResponse:
    """
    Upload and analyze an Excel template.

    Args:
        file: Excel file.
        db: Database session.

    Returns:
        Template analysis results.
    """
    start_time = time.time()

    validate_excel_file(file)

    template_id = uuid.uuid4()

    try:
        # Save file
        file_path = save_template_file(file, template_id)

        logger.info(
            "Template uploaded",
            template_id=str(template_id),
            filename=file.filename,
        )

        # Create template record
        template = Template(
            id=template_id,
            filename=file.filename or "unknown.xlsx",
            file_path=str(file_path),
            status=TemplateStatus.PROCESSING,
        )
        db.add(template)
        db.commit()

        # Parse Excel
        parser = get_excel_parser()
        workbook = parser.parse(file_path)

        template.sheet_count = len(workbook.sheets)

        # Build dependency graph
        tkg_builder = get_tkg_builder()
        dep_graph = tkg_builder.build_graph(workbook)

        # Infer structure
        inferencer = get_structure_inferencer()
        structures = inferencer.infer_structure(workbook)

        # Semantic alignment
        aligner = get_semantic_aligner()
        alignment = aligner.align(workbook, structures)

        # Store structure
        first_sheet = list(structures.keys())[0] if structures else None
        first_structure = structures.get(first_sheet) if first_sheet else None

        template_structure = TemplateStructure(
            template_id=template_id,
            sections=[
                {
                    "name": s.name,
                    "type": s.section_type,
                    "sheet": s.sheet,
                    "start_row": s.start_row,
                    "end_row": s.end_row,
                    "confidence": s.confidence,
                }
                for sheet_struct in structures.values()
                for s in sheet_struct.sections
            ],
            periods=[
                {
                    "column": p.column,
                    "label": p.label,
                    "frequency": p.frequency,
                    "year": p.year,
                    "quarter": p.quarter,
                }
                for sheet_struct in structures.values()
                for p in sheet_struct.periods
            ],
            dependency_graph=tkg_builder.to_json(dep_graph),
            confidence_score=first_structure.confidence if first_structure else 0,
        )
        db.add(template_structure)

        # Store aligned cells
        for aligned in alignment.aligned_cells[:100]:  # Limit stored cells
            cell_type = CellType.INPUT if aligned.ontology_id else CellType.LABEL

            template_cell = TemplateCell(
                structure_id=template_structure.id,
                sheet=aligned.sheet,
                row=aligned.row,
                column=aligned.column,
                address=aligned.address,
                value=aligned.label,
                cell_type=cell_type,
                ontology_id=aligned.ontology_id,
                ontology_label=aligned.ontology_label,
                mapping_confidence=aligned.confidence,
                section_name=aligned.section_type,
            )
            db.add(template_cell)

        template.status = TemplateStatus.COMPLETED
        db.commit()

        processing_time = (time.time() - start_time) * 1000

        # Build response
        structure_response = StructureResponse(
            sections=[
                SectionResponse(
                    name=s.name,
                    section_type=s.section_type,
                    sheet=s.sheet,
                    start_row=s.start_row,
                    end_row=s.end_row,
                    confidence=s.confidence,
                )
                for sheet_struct in structures.values()
                for s in sheet_struct.sections
            ],
            periods=[
                PeriodResponse(
                    column=p.column,
                    column_letter=p.column_letter,
                    label=p.label,
                    frequency=p.frequency,
                    year=p.year,
                    quarter=p.quarter,
                )
                for sheet_struct in structures.values()
                for p in sheet_struct.periods
            ],
            aligned_cells=[
                CellResponse(
                    address=a.address,
                    sheet=a.sheet,
                    row=a.row,
                    column=a.column,
                    label=a.label,
                    ontology_id=a.ontology_id,
                    ontology_label=a.ontology_label,
                    confidence=a.confidence,
                    section_type=a.section_type,
                )
                for a in alignment.aligned_cells[:50]
            ],
            total_cells=alignment.total_cells,
            aligned_count=alignment.aligned_count,
            high_confidence_count=alignment.high_confidence_count,
            input_cells=len(dep_graph.input_cells),
            calculated_cells=len(dep_graph.calculated_cells),
        )

        logger.info(
            "Template processed",
            template_id=str(template_id),
            processing_time_ms=processing_time,
        )

        return TemplateUploadResponse(
            template_id=str(template_id),
            filename=file.filename or "unknown.xlsx",
            sheet_count=len(workbook.sheets),
            status="completed",
            processing_time_ms=processing_time,
            structure=structure_response,
        )

    except Exception as e:
        logger.error(
            "Template processing failed",
            template_id=str(template_id),
            error=str(e),
        )

        # Update status
        template_rec = db.query(Template).filter(Template.id == template_id).first()
        if template_rec:
            template_rec.status = TemplateStatus.FAILED
            template_rec.error_message = str(e)
            db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template processing failed: {str(e)}",
        )


@router.get(
    "/template/{template_id}",
    response_model=TemplateStatusResponse,
    summary="Get template status",
)
async def get_template_status(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> TemplateStatusResponse:
    """Get status of a template."""
    template = db.query(Template).filter(Template.id == template_id).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )

    return TemplateStatusResponse(
        template_id=str(template.id),
        filename=template.filename,
        status=template.status.value,
        sheet_count=template.sheet_count,
        error_message=template.error_message,
        created_at=template.created_at.isoformat(),
    )


@router.get(
    "/template/{template_id}/graph",
    response_model=GraphExportResponse,
    summary="Export dependency graph",
)
async def export_graph(
    template_id: uuid.UUID,
    format: str = "dot",
    db: Session = Depends(get_db),
) -> GraphExportResponse:
    """Export template dependency graph."""
    template = db.query(Template).filter(Template.id == template_id).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )

    structure = template.structure
    if not structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template structure not found",
        )

    if format == "json":
        import json
        content = json.dumps(structure.dependency_graph, indent=2)
    else:
        # DOT format
        content = f"// Dependency graph for {template.filename}\n"
        content += "digraph G {\n"
        graph_data = structure.dependency_graph
        for edge in graph_data.get("edges", []):
            content += f'  "{edge[0]}" -> "{edge[1]}";\n'
        content += "}\n"

    return GraphExportResponse(format=format, content=content)
