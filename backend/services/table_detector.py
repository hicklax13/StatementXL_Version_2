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
        Detect tables using pdfplumber's find_tables.

        Args:
            page: pdfplumber page object.
            page_num: Page number (1-indexed).

        Returns:
            List of extracted tables.
        """
        try:
            # First try line-based detection
            tables = page.find_tables(
                table_settings={
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                }
            )
            
            # If empty, try stream-based (text-based) detection
            detection_method = "pdfplumber_lines"
            if not tables:
                tables = page.find_tables(
                    table_settings={
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    }
                )
                detection_method = "pdfplumber_text"

            extracted: List[ExtractedTable] = []

            for table in tables:
                # table is a pdfplumber.table.Table object
                # table.extract() returns List[List[str]]
                # table.rows is List[List[rect]] (where rect is (x0, top, x1, bottom))
                
                text_data = table.extract()
                if not text_data or len(text_data) <= 1:
                    continue

                rows: List[TableRow] = []
                
                for row_idx, row_text in enumerate(text_data):
                    cells: List[CellData] = []
                    
                    for col_idx, cell_value in enumerate(row_text):
                        val_str = str(cell_value).strip() if cell_value else ""
                        
                        # Get bbox from table.rows
                        # Note: table.rows is a list of lists of cells (rects)
                        bbox = None
                        if row_idx < len(table.rows) and col_idx < len(table.rows[row_idx]):
                            cell_rect = table.rows[row_idx][col_idx]
                            if cell_rect:
                                bbox = list(cell_rect)

                        # Try to parse numeric value
                        parsed = self._numeric_parser.parse(val_str)
                        is_numeric = parsed.value is not None

                        cells.append(
                            CellData(
                                value=val_str,
                                row=row_idx,
                                column=col_idx,
                                bbox=bbox,
                                confidence=parsed.confidence if is_numeric else 0.9,
                                parsed_value=float(parsed.value) if parsed.value else None,
                                is_numeric=is_numeric,
                            )
                        )
                    
                    rows.append(TableRow(cells=cells, row_index=row_idx))

                extracted.append(
                    ExtractedTable(
                        page=page_num,
                        rows=rows,
                        bbox=list(table.bbox),
                        confidence=0.85 if detection_method == "pdfplumber_lines" else 0.7,
                        detection_method=detection_method,
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
        Extract structured data from text lines with bounding boxes.
        """
        import re
        
        # Get words with bounding boxes
        # Each word: {'text': str, 'x0': float, 'x1': float, 'top': float, 'bottom': float, ...}
        words = page.extract_words()
        if not words:
            return []

        # Group words into lines
        # Determine strict line height or tolerance
        lines_of_words = []
        current_line = []
        last_top = None
        
        # Sort by top, then x0
        sorted_words = sorted(words, key=lambda w: (w['top'], w['x0']))
        
        for word in sorted_words:
            if last_top is None:
                current_line.append(word)
                last_top = word['top']
            else:
                # Tolerance of 3 points (approx 1mm)
                if abs(word['top'] - last_top) < 3:
                    current_line.append(word)
                else:
                    lines_of_words.append(sorted(current_line, key=lambda w: w['x0']))
                    current_line = [word]
                    last_top = word['top']
        
        if current_line:
            lines_of_words.append(sorted(current_line, key=lambda w: w['x0']))

        rows: List[TableRow] = []
        money_pattern = re.compile(r'[\$]?[\(]?[0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}[\)]?')

        for row_idx, word_line in enumerate(lines_of_words):
            # Reconstruct line text
            line_text = " ".join(w['text'] for w in word_line)
            
            # Skip if empty or header
            if not line_text.strip():
                continue
                
            # Skip header rows
            if any(m in line_text.upper() for m in ["JAN", "FEB", "MAR", "APR", "DEC"]) and len(money_pattern.findall(line_text)) > 3:
                continue

            cells: List[CellData] = []
            
            # Find numbers using regex on the FULL line text
            # This is safer than word-by-word because "$ 1,000.00" might be multiple words
            # BUT we need to map back to words/bboxes.
            
            # Strategy: Identify value strings, then find roughly corresponding words.
            # This is fuzzy but robust enough for overlays.
            
            numbers = money_pattern.findall(line_text)
            
            if numbers:
                # Split label vs values
                # Heuristic: Label is everything before the first number
                first_num_pos = line_text.find(numbers[0])
                label_text = line_text[:first_num_pos].strip() if first_num_pos > 0 else ""
                
                # Create Label Cell
                if label_text:
                    # Estimate bbox: Union of words that are left of the first number's approximate x position
                    # Better: Words that contributed to label_text.
                    # Since we sort by x0, first N words are likely the label.
                    
                    # We can iterate words and see where the break happens
                    # But finding exact word split is tricky if spacing is normalized.
                    
                    # Simple Approach: 
                    # Use all words whose x1 is less than the first number's estimated start?
                    # No, we don't know first number's start yet.
                    
                    # Let's count characters approx?
                    # Let's just create a bbox from the first N words that roughly match the length?
                    
                    # Alternative: Assume last M words are numbers match the `numbers` list count.
                    # This holds if every number is separate words.
                    # If "$1,000" is one word, good. If "$ 1,000" is two words, tricky.
                    
                    # Let's take the union of all words in the line for now as the row bbox?
                    # No, we want cell bboxes.
                    
                    # "Best Effort": 
                    # Union of all words in the line is the ROW bbox.
                    # Label bbox: Union of first word to K-th word.
                    # Value bbox: Union of words near the value?
                    
                    # Given the complexity, let's just assign the WHOLE LINE bbox to the label for now? 
                    # And maybe leave value bboxes empty or approximate?
                    
                    # Correct approach for MVP:
                    # Union all words -> Row BBox.
                    # Assign Label BBox = Union of words up to the first number-like word.
                    # Assign Value BBox = The specific word corresponding to the value.
                    
                    label_words = []
                    value_words_pool = list(word_line) # Copy
                    
                    # Scan for label words
                    # If a word looks like a number part, stop?
                    
                    pass 

                # Re-implementation using simpler word scanning
                current_label_words = []
                value_cells = []
                
                # We need to match valid numbers
                for word in word_line:
                    # Check if word is part of a number (contains digit, $, etc)
                    # Use simpler check
                    if re.search(r'[\d]', word['text']) and (re.search(r'\.', word['text']) or re.search(r',', word['text'])):
                         # Likely a number value
                         # Parse it
                         parsed = self._numeric_parser.parse(word['text'])
                         if parsed.value is not None:
                             value_cells.append(CellData(
                                 value=word['text'],
                                 row=row_idx,
                                 column=len(cells) + 1, # Placeholder, updated later
                                 bbox=[word['x0'], word['top'], word['x1'], word['bottom']],
                                 confidence=parsed.confidence,
                                 parsed_value=float(parsed.value),
                                 is_numeric=True
                             ))
                         else:
                             # Maybe part of label (e.g. "Year 2024")
                             current_label_words.append(word)
                    else:
                        current_label_words.append(word)
                
                # Construct Label
                if current_label_words:
                    lbl_text = " ".join(w['text'] for w in current_label_words)
                    lbl_bbox = [
                        min(w['x0'] for w in current_label_words),
                        min(w['top'] for w in current_label_words),
                        max(w['x1'] for w in current_label_words),
                        max(w['bottom'] for w in current_label_words)
                    ]
                    cells.append(CellData(
                        value=lbl_text,
                        row=row_idx,
                        column=0,
                        bbox=lbl_bbox,
                        confidence=0.9,
                        is_numeric=False
                    ))
                
                # Add value cells (fix columns)
                for i, vc in enumerate(value_cells):
                    vc.column = len(cells) # Append after label
                    cells.append(vc)

            else:
                # Text-only line (header or note)
                full_bbox = [
                    min(w['x0'] for w in word_line),
                    min(w['top'] for w in word_line),
                    max(w['x1'] for w in word_line),
                    max(w['bottom'] for w in word_line)
                ] if word_line else None
                
                cells.append(CellData(
                    value=line_text,
                    row=row_idx,
                    column=0,
                    bbox=full_bbox,
                    confidence=0.9,
                    is_numeric=False
                ))

            if cells:
                rows.append(TableRow(cells=cells, row_index=row_idx))

        if rows:
            return [ExtractedTable(
                page=page_num,
                rows=rows,
                confidence=0.9,
                detection_method="text_lines_bbox"
            )]
        
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
