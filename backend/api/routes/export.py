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
    
    # Build Excel file using DirectPopulator (preserves original PDF structure)
    try:
        from backend.services.excel_builder.direct_populator import DirectPopulator
        
        # Create populator with styling
        populator = DirectPopulator(
            style=request.style,
            colorway=request.colorway,
        )
        
        # Determine statement title
        statement_titles = {
            "income_statement": "Income Statement",
            "balance_sheet": "Balance Sheet",
            "cash_flow": "Cash Flow Statement",
        }
        statement_title = statement_titles.get(request.statement_type, "Financial Statement")
        
        # Populate workbook directly from extracted data
        populator.populate(
            extracted_items=extracted_items,
            periods=list(periods),
            company_name=request.company_name,
            statement_title=statement_title,
        )
        
        # Save to exports directory
        export_dir = settings.upload_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        export_id = str(uuid.uuid4())
        filename = f"{document.filename.rsplit('.', 1)[0]}_{request.style}_{request.colorway}.xlsx"
        output_path = export_dir / f"{export_id}_{filename}"
        
        populator.save(output_path)
        
        logger.info(
            "Export complete",
            export_id=export_id,
            filename=filename,
            periods=list(periods),
            items_exported=len(extracted_items),
        )
        
        return ExportResponse(
            export_id=export_id,
            filename=filename,
            download_url=f"/api/v1/export/download/{export_id}",
            style=request.style,
            colorway=request.colorway,
            periods=sorted(periods, reverse=True),
            rows_populated=len(extracted_items),
        )
        
    except Exception as e:
        logger.error("Export failed", error=str(e))
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
