"""
Export API routes for generating Excel statements.

Provides endpoints for exporting extracted PDF data to formatted Excel files
using the ExcelBuilder module.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.models.document import Document
from backend.models.extract import Extract
from backend.services.excel_builder import ExcelBuilder, STYLES, COLORWAYS

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class ExportRequest(BaseModel):
    """Request model for Excel export."""
    
    document_id: str = Field(..., description="ID of the document to export")
    statement_type: Literal["income_statement", "balance_sheet", "cash_flow"] = Field(
        default="income_statement",
        description="Type of financial statement",
    )
    style: Literal["basic", "corporate", "professional"] = Field(
        default="basic",
        description="Template style variant",
    )
    colorway: str = Field(
        default="green",
        description="Color palette name",
    )
    company_name: Optional[str] = Field(
        default=None,
        description="Company name for the header",
    )


class StyleInfo(BaseModel):
    """Information about a style."""
    
    id: str
    name: str
    description: str


class ColorwayInfo(BaseModel):
    """Information about a colorway."""
    
    id: str
    name: str
    primary_color: str


class ExportOptionsResponse(BaseModel):
    """Response with available export options."""
    
    styles: List[StyleInfo]
    colorways: List[ColorwayInfo]
    statement_types: List[str]


class ExportResponse(BaseModel):
    """Response after successful export."""
    
    export_id: str
    filename: str
    download_url: str
    style: str
    colorway: str
    periods: List[int]
    rows_populated: int


# =============================================================================
# API Endpoints
# =============================================================================

@router.get(
    "/export/options",
    response_model=ExportOptionsResponse,
    summary="Get export options",
    description="Get available styles, colorways, and statement types for export.",
)
async def get_export_options() -> ExportOptionsResponse:
    """Get available export configuration options."""
    
    styles = [
        StyleInfo(
            id="basic",
            name="Basic",
            description="Clean, minimal formatting with thin borders",
        ),
        StyleInfo(
            id="corporate",
            name="Corporate",
            description="Bold colored headers with professional appearance",
        ),
        StyleInfo(
            id="professional",
            name="Professional",
            description="Subtle styling with alternating row colors",
        ),
    ]
    
    colorways = [
        ColorwayInfo(id=key, name=value.name, primary_color=f"#{value.primary}")
        for key, value in COLORWAYS.items()
    ]
    
    return ExportOptionsResponse(
        styles=styles,
        colorways=colorways,
        statement_types=["income_statement", "balance_sheet", "cash_flow"],
    )


@router.post(
    "/export/excel",
    response_model=ExportResponse,
    summary="Export to Excel",
    description="Generate a formatted Excel file from extracted document data.",
)
async def export_to_excel(
    request: ExportRequest,
    db: Session = Depends(get_db),
) -> ExportResponse:
    """
    Export extracted document data to a formatted Excel file.
    
    Args:
        request: Export configuration.
        db: Database session.
        
    Returns:
        ExportResponse with download URL.
    """
    logger.info(
        "Export requested",
        document_id=request.document_id,
        style=request.style,
        colorway=request.colorway,
    )
    
    # Validate colorway
    if request.colorway not in COLORWAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid colorway: {request.colorway}. Available: {list(COLORWAYS.keys())}",
        )
    
    # Get document
    try:
        doc_uuid = uuid.UUID(request.document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format",
        )
    
    document = db.query(Document).filter(Document.id == doc_uuid).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {request.document_id} not found",
        )
    
    # Get extractions
    extracts = db.query(Extract).filter(Extract.document_id == doc_uuid).all()
    if not extracts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No extraction data found for this document",
        )
    
    # Parse extracted data into line items with improved logic
    extracted_items = []
    periods = set()
    
    for extract in extracts:
        if not extract.tables_json:
            continue
            
        for table in extract.tables_json:
            rows = table.get("rows", [])
            
            for row in rows:
                cells = row.get("cells", [])
                if len(cells) < 2:
                    continue
                
                # Find the label cell (first non-numeric cell)
                label = ""
                label_col = 0
                for i, cell in enumerate(cells):
                    if isinstance(cell, dict):
                        if not cell.get("is_numeric", False):
                            label = str(cell.get("value", "")).strip()
                            label_col = i
                            break
                    else:
                        label = str(cell).strip()
                        break
                
                # Skip empty labels or header-like rows
                if not label or len(label) < 2:
                    continue
                
                # Skip rows that look like headers
                label_lower = label.lower()
                if any(skip in label_lower for skip in ["year ended", "fiscal", "period", "quarter"]):
                    continue
                
                item = {"label": label}
                value_count = 0
                
                # Extract numeric values from remaining cells
                for i, cell in enumerate(cells):
                    if i <= label_col:
                        continue  # Skip label column
                    
                    if isinstance(cell, dict):
                        # Use parsed_value if available (more accurate)
                        if cell.get("is_numeric") and cell.get("parsed_value") is not None:
                            numeric_value = float(cell["parsed_value"])
                            # Assign to period based on column position
                            period_year = 2025 - value_count
                            item[str(period_year)] = numeric_value
                            periods.add(period_year)
                            value_count += 1
                        else:
                            # Try manual parsing as fallback
                            raw_value = str(cell.get("value", "")).strip()
                            if raw_value:
                                try:
                                    # Clean and parse
                                    cleaned = raw_value.replace(",", "").replace("$", "").replace("%", "")
                                    if cleaned.startswith("(") and cleaned.endswith(")"):
                                        cleaned = "-" + cleaned[1:-1]
                                    if cleaned and cleaned not in ["-", "—", "–"]:
                                        numeric_value = float(cleaned)
                                        period_year = 2025 - value_count
                                        item[str(period_year)] = numeric_value
                                        periods.add(period_year)
                                        value_count += 1
                                except (ValueError, TypeError):
                                    pass
                
                # Include all items that have values OR are section headers
                section_keywords = ["income", "revenue", "expenses", "expense", "costs", "operating"]
                is_section_header = any(kw in label.lower() for kw in section_keywords) and len(label.split()) <= 2
                
                if value_count > 0 or is_section_header:
                    extracted_items.append(item)
                    logger.debug("Extracted item", label=label, values=value_count, is_section=is_section_header)
    
    logger.info(
        "Data extraction complete",
        total_items=len(extracted_items),
        periods=list(periods),
    )
    
    if not periods:
        periods = {2025}  # Default to current year
    
    # Build Excel file using Template-based approach with GAAP classification
    try:
        import re
        from backend.services.gaap_classifier import get_gaap_classifier
        from backend.services.template_loader import get_template_loader
        from backend.services.template_populator import get_template_populator
        
        # Detect year from raw tables_json (look for date patterns)
        detected_year = None
        
        # Search through all extract tables for date patterns
        for extract in extracts:
            if not extract.tables_json:
                continue
            for table in extract.tables_json:
                rows = table.get("rows", [])
                for row in rows:
                    cells = row.get("cells", [])
                    for cell in cells:
                        cell_value = ""
                        if isinstance(cell, dict):
                            cell_value = str(cell.get("value", ""))
                        else:
                            cell_value = str(cell)
                        
                        # Look for date range patterns like "01/01/2024 - 12/31/2024"
                        date_range_match = re.search(r'(\d{1,2}/\d{1,2}/(\d{4}))\s*[-–]\s*(\d{1,2}/\d{1,2}/(\d{4}))', cell_value)
                        if date_range_match:
                            # Use the end year (second date)
                            year_val = int(date_range_match.group(4))
                            if 2000 <= year_val <= 2100:
                                detected_year = year_val
                                logger.info(f"Detected year from date range: {detected_year}")
                                break
                        
                        # Look for "Year Ended 2024" patterns
                        year_ended_match = re.search(r'year\s*ended.*?(\d{4})', cell_value, re.IGNORECASE)
                        if year_ended_match:
                            year_val = int(year_ended_match.group(1))
                            if 2000 <= year_val <= 2100:
                                detected_year = year_val
                                logger.info(f"Detected year from 'year ended': {detected_year}")
                                break
                    
                    if detected_year:
                        break
                if detected_year:
                    break
            if detected_year:
                break
        
        # Fallback to extracted_items if still not found
        if detected_year is None:
            for item in extracted_items:
                label = item.get("label", "")
                year_match = re.search(r'(\d{4})', label)
                if year_match:
                    year_val = int(year_match.group(1))
                    if 2000 <= year_val <= 2100:
                        detected_year = year_val
                        break
        
        # Final fallback: Extract text directly from PDF file
        if detected_year is None and document.file_path:
            try:
                import pdfplumber
                pdf_path = Path(document.file_path)
                if pdf_path.exists():
                    with pdfplumber.open(pdf_path) as pdf:
                        if pdf.pages:
                            text = pdf.pages[0].extract_text() or ""
                            # Look for date range patterns
                            date_range_match = re.search(r'(\d{1,2}/\d{1,2}/(\d{4}))\s*[-–]\s*(\d{1,2}/\d{1,2}/(\d{4}))', text)
                            if date_range_match:
                                year_val = int(date_range_match.group(4))
                                if 2000 <= year_val <= 2100:
                                    detected_year = year_val
                                    logger.info(f"Detected year from PDF text: {detected_year}")
            except Exception as e:
                logger.warning(f"Failed to extract year from PDF: {e}")
        
        # Override the hardcoded 2025 with detected year
        if detected_year:
            # Remap items to use detected year
            for item in extracted_items:
                if "2025" in item:
                    item[str(detected_year)] = item.pop("2025")
            periods = {detected_year}
            logger.info(f"Using detected year: {detected_year}")
        
        # Convert extracted items to classifier format
        items_for_classification = []
        for item in extracted_items:
            label = item.get("label", "")
            # Get first available value
            value = None
            for key in item.keys():
                if key != "label" and isinstance(item[key], (int, float)):
                    value = item[key]
                    break
            
            items_for_classification.append({
                "label": label,
                "value": value,
            })
        
        # Classify items using GAAP classifier
        classifier = get_gaap_classifier()
        classifications = await classifier.classify_items(
            items_for_classification,
            statement_type=request.statement_type,
        )
        
        logger.info(
            "Classification complete",
            total_classified=len(classifications),
            sample=[c.category for c in classifications[:5]],
        )
        
        # Aggregate by GAAP category
        aggregated = classifier.aggregate_by_category(classifications)
        
        logger.info(
            "Aggregation complete",
            categories=list(aggregated.keys()),
            values=list(aggregated.values()),
        )
        
        # Load template
        loader = get_template_loader()
        workbook, structure = loader.load(
            statement_type=request.statement_type,
            style=request.style,
        )
        
        # Populate template
        populator = get_template_populator()
        workbook = populator.populate(
            workbook=workbook,
            structure=structure,
            aggregated_data=aggregated,
            classifications=classifications,
            periods=sorted(periods, reverse=True),
            company_name=request.company_name,
        )
        
        # Save to exports directory
        export_dir = settings.upload_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        export_id = str(uuid.uuid4())
        filename = f"{document.filename.rsplit('.', 1)[0]}_{request.style}_{request.colorway}.xlsx"
        output_path = export_dir / f"{export_id}_{filename}"
        
        workbook.save(output_path)
        
        logger.info(
            "Export complete",
            export_id=export_id,
            filename=filename,
            periods=list(periods),
            items_classified=len(classifications),
            categories_populated=len(aggregated),
        )
        
        return ExportResponse(
            export_id=export_id,
            filename=filename,
            download_url=f"/api/v1/export/download/{export_id}",
            style=request.style,
            colorway=request.colorway,
            periods=sorted(periods, reverse=True),
            rows_populated=len(aggregated),
        )
        
    except Exception as e:
        logger.error("Export failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )


@router.get(
    "/export/download/{export_id}",
    summary="Download exported file",
    description="Download a previously exported Excel file.",
)
async def download_export(export_id: str) -> FileResponse:
    """
    Download an exported Excel file.
    
    Args:
        export_id: ID of the export.
        
    Returns:
        FileResponse with the Excel file.
    """
    export_dir = settings.upload_dir / "exports"
    
    # Find file with matching export ID
    for file in export_dir.glob(f"{export_id}_*.xlsx"):
        return FileResponse(
            path=file,
            filename=file.name.replace(f"{export_id}_", ""),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Export {export_id} not found",
    )
