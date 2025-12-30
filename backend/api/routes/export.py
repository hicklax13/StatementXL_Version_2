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


class ExportPreviewResponse(BaseModel):
    """Response for export preview."""
    
    structure: dict
    aggregated_data: dict
    periods: List[int]
    statement_type: str


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



async def prepare_export_data(
    request: ExportRequest,
    db: Session,
):
    """
    Prepare data for export or preview.
    
    Returns:
        Tuple of (aggregated_data, classifications, periods, effective_statement_type, document, extracted_items)
    """
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
    
    if not periods:
        periods = {2025}  # Default to current year
    
    # GAAP Classification Logic
    import re
    from backend.services.gaap_classifier import get_gaap_classifier
    
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
                            break
                    
                    # Look for "Year Ended 2024" patterns
                    year_ended_match = re.search(r'year\s*ended.*?(\d{4})', cell_value, re.IGNORECASE)
                    if year_ended_match:
                        year_val = int(year_ended_match.group(1))
                        if 2000 <= year_val <= 2100:
                            detected_year = year_val
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
    
    # Extract text directly from PDF file for year detection AND context
    raw_pdf_text = None
    if document.file_path:
        try:
            import pdfplumber
            pdf_path = Path(document.file_path)
            if pdf_path.exists():
                with pdfplumber.open(pdf_path) as pdf:
                    if pdf.pages:
                        raw_pdf_text = pdf.pages[0].extract_text() or ""
                        # Use for year detection if not already found
                        if detected_year is None:
                            date_range_match = re.search(r'(\d{1,2}/\d{1,2}/(\d{4}))\s*[-–]\s*(\d{1,2}/\d{1,2}/(\d{4}))', raw_pdf_text)
                            if date_range_match:
                                year_val = int(date_range_match.group(4))
                                if 2000 <= year_val <= 2100:
                                    detected_year = year_val
        except Exception as e:
            logger.warning(f"Failed to extract PDF text: {e}")
    
    # Override the hardcoded 2025 with detected year
    if detected_year:
        # Remap items to use detected year
        for item in extracted_items:
            if "2025" in item:
                item[str(detected_year)] = item.pop("2025")
        periods = {detected_year}
    
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
    
    # Classify items using GAAP classifier (with raw PDF text for context)
    classifier = get_gaap_classifier()
    
    # Auto-detect statement type if set to 'auto' or if raw_pdf_text is available
    effective_statement_type = request.statement_type
    if effective_statement_type == "auto" and raw_pdf_text:
        effective_statement_type = classifier.detect_statement_type(raw_pdf_text)
    
    classifications = await classifier.classify_items(
        items_for_classification,
        statement_type=effective_statement_type,
        raw_text=raw_pdf_text,
    )
    
    # Aggregate by GAAP category
    aggregated = classifier.aggregate_by_category(classifications)
    
    return aggregated, classifications, periods, effective_statement_type, document, extracted_items


@router.post(
    "/export/preview",
    response_model=ExportPreviewResponse,
    summary="Preview Export",
    description="Get a JSON preview of the final Excel structure.",
)
async def preview_export(
    request: ExportRequest,
    db: Session = Depends(get_db),
) -> ExportPreviewResponse:
    """Generate preview data."""
    try:
        (
            aggregated, 
            classifications, 
            periods, 
            effective_statement_type, 
            _, 
            _
        ) = await prepare_export_data(request, db)
        
        # Load template structure (lightweight load)
        from backend.services.template_loader import get_template_loader
        loader = get_template_loader()
        # Note: We just need structure, so we might not need the actual workbook object heavily
        # But for now, using the same loader is fine
        _, structure = loader.load(
            statement_type=effective_statement_type, 
            style=request.style
        )
        
        # Transform flat aggregated data into nested structure for frontend preview
        # { Category: { Label: { Period: Value } } }
        nested_data = {}
        primary_period = str(periods[0]) if periods else str(datetime.now().year)

        # Helper to get category for a row
        def get_category_for_row(row_label):
            # Check classifications
            for c in classifications:
                if c.template_row == row_label:
                    return c.category
            # Check if calculated row
            if row_label in structure.calculated_rows:
                return "calculated"
            return "uncategorized"

        # Category display name mapping
        category_map = {
            "revenue": "Revenue",
            "cost_of_goods_sold": "Cost of Goods Sold",
            "operating_expenses": "Operating Expenses",
            "other_income_expenses": "Other Income & Expenses",
            "tax_provision": "Tax Provision",
            "calculated": "Summary",
            "current_assets": "Current Assets",
            "noncurrent_assets": "Non-Current Assets",
            "current_liabilities": "Current Liabilities",
            "noncurrent_liabilities": "Non-Current Liabilities",
            "equity": "Equity",
            "operating_activities": "Operating Activities",
            "investing_activities": "Investing Activities",
            "financing_activities": "Financing Activities",
        }

        for row_label, value in aggregated.items():
            raw_category = get_category_for_row(row_label)
            display_category = category_map.get(raw_category, raw_category.replace("_", " ").title())
            
            if display_category not in nested_data:
                nested_data[display_category] = {}
            
            # Format value as dict keyed by period (frontend expects this structure)
            nested_data[display_category][row_label] = {
                primary_period: value
            }
        
        return ExportPreviewResponse(
            structure=structure,
            aggregated_data=nested_data,
            periods=sorted(list(periods), reverse=True),
            statement_type=effective_statement_type
        )
        
    except Exception as e:
        logger.error("Preview failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview failed: {str(e)}",
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
    """
    logger.info(
        "Export requested",
        document_id=request.document_id,
        style=request.style,
        colorway=request.colorway,
    )
    
    try:
        # 1. Prepare Data
        (
            aggregated, 
            classifications, 
            periods, 
            effective_statement_type, 
            document, 
            _
        ) = await prepare_export_data(request, db)

        # 2. Load Template
        from backend.services.template_loader import get_template_loader
        from backend.services.template_populator import get_template_populator
        
        loader = get_template_loader()
        workbook, structure = loader.load(
            statement_type=effective_statement_type,
            style=request.style,
        )
        
        # 3. Populate Template
        populator = get_template_populator()
        workbook = populator.populate(
            workbook=workbook,
            structure=structure,
            aggregated_data=aggregated,
            classifications=classifications,
            periods=sorted(list(periods), reverse=True),
            company_name=request.company_name,
        )
        
        # 4. Save to File
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
            periods=sorted(list(periods), reverse=True),
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
