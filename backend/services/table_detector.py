"""
Table detection service for extracting tables from PDFs.

Uses Camelot for bordered tables and pdfplumber for borderless tables.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber
import structlog

from backend.services.numeric_parser import NumericParser, get_numeric_parser

logger = structlog.get_logger(__name__)


@dataclass
class CellData:
    """Represents a single cell in an extracted table."""

    value: str
    row: int
    column: int
    bbox: Optional[List[float]] = None  # [x0, y0, x1, y1]
    confidence: float = 1.0
    parsed_value: Optional[Any] = None
    is_numeric: bool = False


@dataclass
class TableRow:
    """Represents a row in an extracted table."""

    cells: List[CellData]
    row_index: int


@dataclass
class ExtractedTable:
    """Represents an extracted table with metadata."""

    page: int
    rows: List[TableRow]
    bbox: Optional[List[float]] = None
    confidence: float = 1.0
    detection_method: str = "pdfplumber"


@dataclass
class TableDetectionResult:
    """Complete table detection result for a document."""

    tables: List[ExtractedTable]
    page_count: int


class TableDetector:
    """
    Service for detecting and extracting tables from PDF documents.

    Uses multiple strategies:
    1. Camelot lattice mode for bordered tables
    2. pdfplumber for borderless/stream tables
    """

    def __init__(self):
        """Initialize table detector."""
        self._camelot_available = self._check_camelot()
        self._numeric_parser = get_numeric_parser()

    def _check_camelot(self) -> bool:
        """Check if Camelot is available and properly configured."""
        try:
            import camelot

            # Camelot requires Ghostscript
            return True
        except ImportError:
            logger.warning("Camelot not available")
            return False
        except Exception as e:
            logger.warning("Camelot check failed", error=str(e))
            return False

    def detect_tables(self, pdf_path: Path) -> TableDetectionResult:
        """
        Detect and extract all tables from a PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            TableDetectionResult with all extracted tables.
        """
        logger.info("Detecting tables in PDF", path=str(pdf_path))

        all_tables: List[ExtractedTable] = []
        page_count = 0

        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, start=1):
                    # Try text line extraction first (preserves full labels)
                    text_tables = self._extract_text_lines(page, page_num)
                    if text_tables and len(text_tables[0].rows) > 5:  # Has substantial content
                        all_tables.extend(text_tables)
                        continue  # Skip table-based extraction for this page
                    
                    # Try Camelot for bordered tables
                    if self._camelot_available:
                        camelot_tables = self._detect_with_camelot(pdf_path, page_num)
                        all_tables.extend(camelot_tables)

                    # Use pdfplumber for additional/borderless tables
                    pdfplumber_tables = self._detect_with_pdfplumber(page, page_num)

                    # Add pdfplumber tables that don't overlap with Camelot results
                    for pt in pdfplumber_tables:
                        if not self._overlaps_existing(pt, all_tables):
                            all_tables.append(pt)

            logger.info(
                "Table detection complete",
                path=str(pdf_path),
                table_count=len(all_tables),
            )

            return TableDetectionResult(
                tables=all_tables,
                page_count=page_count,
            )

        except Exception as e:
            logger.error("Table detection failed", path=str(pdf_path), error=str(e))
            raise

    def _detect_with_camelot(self, pdf_path: Path, page_num: int) -> List[ExtractedTable]:
        """
        Detect tables using Camelot lattice mode.

        Args:
            pdf_path: Path to the PDF file.
            page_num: Page number (1-indexed).

        Returns:
            List of extracted tables.
        """
        try:
            import camelot

            # Use lattice mode for bordered tables
            tables = camelot.read_pdf(
                str(pdf_path),
                pages=str(page_num),
                flavor="lattice",
                suppress_stdout=True,
            )

            extracted: List[ExtractedTable] = []

            for table in tables:
                if table.accuracy > 50:  # Filter low-quality detections
                    rows = self._process_camelot_table(table, page_num)
                    extracted.append(
                        ExtractedTable(
                            page=page_num,
                            rows=rows,
                            bbox=self._get_camelot_bbox(table),
                            confidence=table.accuracy / 100.0,
                            detection_method="camelot_lattice",
                        )
                    )

            return extracted

        except Exception as e:
            logger.warning(
                "Camelot detection failed for page",
                page=page_num,
                error=str(e),
            )
            return []

    def _detect_with_pdfplumber(
        self, page: pdfplumber.page.Page, page_num: int
    ) -> List[ExtractedTable]:
        """
        Detect tables using pdfplumber.

        Args:
            page: pdfplumber page object.
            page_num: Page number (1-indexed).

        Returns:
            List of extracted tables.
        """
        try:
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                }
            )

            extracted: List[ExtractedTable] = []

            for table_data in tables:
                if table_data and len(table_data) > 1:  # At least header + 1 row
                    rows = self._process_pdfplumber_table(table_data, page_num)
                    extracted.append(
                        ExtractedTable(
                            page=page_num,
                            rows=rows,
                            confidence=0.85,  # pdfplumber has decent accuracy
                            detection_method="pdfplumber_lines",
                        )
                    )

            # Try stream mode for borderless tables if no tables found
            if not extracted:
                tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    }
                )

                for table_data in tables:
                    if table_data and len(table_data) > 1:
                        rows = self._process_pdfplumber_table(table_data, page_num)
                        extracted.append(
                            ExtractedTable(
                                page=page_num,
                                rows=rows,
                                confidence=0.7,  # Lower confidence for stream mode
                                detection_method="pdfplumber_text",
                            )
                        )

            return extracted

        except Exception as e:
            logger.warning(
                "pdfplumber detection failed for page",
                page=page_num,
                error=str(e),
            )
            return []

    def _process_camelot_table(self, table, page_num: int) -> List[TableRow]:
        """
        Process a Camelot table into structured rows.

        Args:
            table: Camelot table object.
            page_num: Page number.

        Returns:
            List of TableRow objects.
        """
        rows: List[TableRow] = []
        df = table.df

        for row_idx, row in df.iterrows():
            cells: List[CellData] = []

            for col_idx, value in enumerate(row):
                cell_value = str(value).strip() if value else ""

                # Try to parse numeric value
                parsed = self._numeric_parser.parse(cell_value)
                is_numeric = parsed.value is not None

                cells.append(
                    CellData(
                        value=cell_value,
                        row=row_idx,
                        column=col_idx,
                        confidence=0.9 if is_numeric else 0.95,
                        parsed_value=float(parsed.value) if parsed.value else None,
                        is_numeric=is_numeric,
                    )
                )

            rows.append(TableRow(cells=cells, row_index=row_idx))

        return rows

    def _process_pdfplumber_table(
        self, table_data: List[List], page_num: int
    ) -> List[TableRow]:
        """
        Process pdfplumber table data into structured rows.

        Args:
            table_data: Raw table data from pdfplumber.
            page_num: Page number.

        Returns:
            List of TableRow objects.
        """
        rows: List[TableRow] = []

        for row_idx, row in enumerate(table_data):
            cells: List[CellData] = []

            for col_idx, value in enumerate(row):
                cell_value = str(value).strip() if value else ""

                # Try to parse numeric value
                parsed = self._numeric_parser.parse(cell_value)
                is_numeric = parsed.value is not None

                cells.append(
                    CellData(
                        value=cell_value,
                        row=row_idx,
                        column=col_idx,
                        confidence=parsed.confidence if is_numeric else 0.9,
                        parsed_value=float(parsed.value) if parsed.value else None,
                        is_numeric=is_numeric,
                    )
                )

            rows.append(TableRow(cells=cells, row_index=row_idx))

        return rows

    def _get_camelot_bbox(self, table) -> Optional[List[float]]:
        """Extract bounding box from Camelot table."""
        try:
            cells = table.cells
            if cells:
                x0 = min(c.x1 for c in cells)
                y0 = min(c.y1 for c in cells)
                x1 = max(c.x2 for c in cells)
                y1 = max(c.y2 for c in cells)
                return [x0, y0, x1, y1]
        except Exception:
            pass
        return None
    
    def _extract_text_lines(self, page, page_num: int) -> List[ExtractedTable]:
        """
        Extract structured data from text lines (fallback for tables that truncate).
        
        Uses full line text extraction and regex parsing to separate labels from values.
        This preserves full label text that table extraction might truncate.
        Handles both single-column (label value) and multi-column (label v1 v2 v3...) formats.
        """
        import re
        
        text = page.extract_text()
        if not text:
            return []
        
        lines = text.strip().split('\n')
        rows: List[TableRow] = []
        
        # Pattern to find all numeric values in a line
        # Matches: 123,456.78, $1,234.56, (1,234.56), 1234
        number_pattern = re.compile(r'\$?[\(\-]?[\d,]+\.?\d*[\)]?')
        
        for row_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            cells: List[CellData] = []
            
            # Pattern to find FINANCIAL numeric values (with comma/decimal formatting or $ sign)
            # This excludes plain numbers like "210" which could be account codes
            money_pattern = re.compile(r'[\$]?[\(]?[0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}[\)]?')
            numbers = money_pattern.findall(line)
            
            if numbers:
                # Extract label: everything up to the first money value
                first_num_pos = line.find(numbers[0])
                label = line[:first_num_pos].strip() if first_num_pos > 0 else ""
                
                # Skip header rows that contain year patterns like "JAN 2025 FEB 2025"
                if any(m in line.upper() for m in ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]) and len(numbers) > 3:
                    continue
                
                # Label cell (include even if label is account code like "210 Payroll")
                if label:
                    cells.append(
                        CellData(
                            value=label,
                            row=row_idx,
                            column=0,
                            confidence=0.95,
                            is_numeric=False,
                        )
                    )
                
                # Add numeric cells
                for col_idx, num_str in enumerate(numbers):
                    parsed = self._numeric_parser.parse(num_str)
                    cells.append(
                        CellData(
                            value=num_str,
                            row=row_idx,
                            column=col_idx + 1 if label else col_idx,
                            confidence=parsed.confidence if parsed.value else 0.9,
                            parsed_value=float(parsed.value) if parsed.value else None,
                            is_numeric=parsed.value is not None,
                        )
                    )
            else:
                # Line is label-only (section header or total without value)
                cells.append(
                    CellData(
                        value=line,
                        row=row_idx,
                        column=0,
                        confidence=0.9,
                        is_numeric=False,
                    )
                )
            
            if cells:  # Only add row if we have cells
                rows.append(TableRow(cells=cells, row_index=row_idx))
        
        if rows:
            return [
                ExtractedTable(
                    page=page_num,
                    rows=rows,
                    confidence=0.95,  # High confidence for text extraction
                    detection_method="text_lines",
                )
            ]
        
        return []

    def _overlaps_existing(
        self, new_table: ExtractedTable, existing: List[ExtractedTable]
    ) -> bool:
        """
        Check if a new table overlaps with existing tables.

        Args:
            new_table: Table to check.
            existing: List of existing tables.

        Returns:
            True if there's significant overlap.
        """
        # Simple check: if same page and similar row count, might be duplicate
        for table in existing:
            if table.page == new_table.page:
                if abs(len(table.rows) - len(new_table.rows)) <= 1:
                    # Check if first row content is similar
                    if table.rows and new_table.rows:
                        existing_first = " ".join(c.value for c in table.rows[0].cells)
                        new_first = " ".join(c.value for c in new_table.rows[0].cells)
                        if existing_first and new_first:
                            # Simple similarity check
                            if existing_first[:50] == new_first[:50]:
                                return True
        return False


# Singleton instance
_detector_instance: Optional[TableDetector] = None


def get_table_detector() -> TableDetector:
    """Get singleton TableDetector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = TableDetector()
    return _detector_instance
