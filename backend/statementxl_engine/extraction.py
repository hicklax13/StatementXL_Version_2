"""
Extraction layer for the StatementXL Engine.

Pass 1-2: Extract tokens, bboxes, tables, OCR when needed.
Implements layout-aware parsing with full evidence tracking.
"""

import hashlib
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional, Tuple

import pdfplumber
import structlog

from backend.statementxl_engine.models import (
    BoundingBox,
    DocumentEvidence,
    ExtractionMode,
    NormalizedFact,
    PageEvidence,
    ScaleFactor,
    StatementType,
    TableCell,
    TableRegion,
    TableRow,
    Token,
)
from backend.services.numeric_parser import get_numeric_parser

logger = structlog.get_logger(__name__)


class ExtractionLayer:
    """
    Layout-aware extraction layer.

    Uses:
    - PyMuPDF/pdfplumber for word-level bbox extraction
    - pdfplumber for table heuristics and row grouping
    - Camelot (lattice/stream) where applicable
    - OCR fallback for low text density pages
    """

    # Text density threshold for OCR detection
    OCR_TEXT_DENSITY_THRESHOLD = 0.05  # If < 5% of page has text, try OCR

    # Patterns for units detection
    UNITS_PATTERNS = [
        (r"\$\s*in\s*thousands", ScaleFactor.THOUSANDS),
        (r"\$\s*000", ScaleFactor.THOUSANDS),
        (r"in\s*thousands", ScaleFactor.THOUSANDS),
        (r"\$\s*in\s*millions", ScaleFactor.MILLIONS),
        (r"\$\s*MM", ScaleFactor.MILLIONS),
        (r"in\s*millions", ScaleFactor.MILLIONS),
        (r"\$\s*in\s*billions", ScaleFactor.BILLIONS),
        (r"in\s*billions", ScaleFactor.BILLIONS),
    ]

    def __init__(self):
        self._numeric_parser = get_numeric_parser()
        self._camelot_available = self._check_camelot()

    def _check_camelot(self) -> bool:
        """Check if Camelot is available."""
        try:
            import camelot
            return True
        except ImportError:
            logger.warning("Camelot not available, using pdfplumber only")
            return False

    def extract_document(self, pdf_path: Path) -> DocumentEvidence:
        """
        Extract all evidence from a PDF document.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            DocumentEvidence with all extracted data.
        """
        logger.info("Extracting document", path=str(pdf_path))

        doc_id = hashlib.md5(str(pdf_path).encode()).hexdigest()[:16]
        pages: List[PageEvidence] = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, start=1):
                    page_evidence = self._extract_page(page, page_num, pdf_path)
                    pages.append(page_evidence)

            # Calculate overall confidence
            all_tables = [t for p in pages for t in p.tables]
            if all_tables:
                overall_conf = sum(t.confidence for t in all_tables) / len(all_tables)
            else:
                overall_conf = 0.5

            doc = DocumentEvidence(
                id=doc_id,
                source_path=str(pdf_path),
                filename=pdf_path.name,
                page_count=page_count,
                pages=pages,
                overall_confidence=overall_conf,
            )

            logger.info(
                "Document extraction complete",
                path=str(pdf_path),
                pages=page_count,
                tables=len(all_tables),
            )

            return doc

        except Exception as e:
            logger.error("Document extraction failed", path=str(pdf_path), error=str(e))
            raise

    def _extract_page(
        self,
        page: pdfplumber.page.Page,
        page_num: int,
        pdf_path: Path,
    ) -> PageEvidence:
        """Extract evidence from a single page."""
        # Get page dimensions
        width = page.width
        height = page.height

        # Extract words with bounding boxes
        words = page.extract_words()
        tokens = self._convert_words_to_tokens(words, page_num, width, height)

        # Calculate text density for OCR detection
        text_density = self._calculate_text_density(words, width, height)

        # Determine extraction mode
        mode = ExtractionMode.TEXT
        if text_density < self.OCR_TEXT_DENSITY_THRESHOLD:
            mode = ExtractionMode.OCR
            # TODO: Implement OCR fallback with pytesseract
            logger.warning("Low text density, OCR recommended", page=page_num, density=text_density)

        # Extract tables
        tables = self._extract_tables(page, page_num, pdf_path, width, height)

        # Get raw text
        raw_text = page.extract_text() or ""

        return PageEvidence(
            page_num=page_num,
            tokens=tokens,
            tables=tables,
            mode=mode,
            text_density=text_density,
            raw_text=raw_text,
        )

    def _convert_words_to_tokens(
        self,
        words: List[dict],
        page_num: int,
        page_width: float,
        page_height: float,
    ) -> List[Token]:
        """Convert pdfplumber words to Token objects."""
        tokens = []
        for i, word in enumerate(words):
            bbox = BoundingBox(
                x0=word["x0"],
                y0=word["top"],
                x1=word["x1"],
                y1=word["bottom"],
                page_width=page_width,
                page_height=page_height,
            )
            token = Token(
                id=f"p{page_num}_w{i}",
                text=word["text"],
                bbox=bbox,
                page=page_num,
                confidence=1.0,
                mode=ExtractionMode.TEXT,
            )
            tokens.append(token)
        return tokens

    def _calculate_text_density(
        self,
        words: List[dict],
        page_width: float,
        page_height: float,
    ) -> float:
        """Calculate text density as ratio of text area to page area."""
        if not words or page_width == 0 or page_height == 0:
            return 0.0

        page_area = page_width * page_height
        text_area = sum(
            (w["x1"] - w["x0"]) * (w["bottom"] - w["top"])
            for w in words
        )
        return text_area / page_area

    def _extract_tables(
        self,
        page: pdfplumber.page.Page,
        page_num: int,
        pdf_path: Path,
        page_width: float,
        page_height: float,
    ) -> List[TableRegion]:
        """Extract tables from a page using multiple strategies."""
        tables: List[TableRegion] = []

        # Strategy 1: Try text-line extraction for financial statements
        text_tables = self._extract_text_lines(page, page_num, page_width, page_height)
        if text_tables and text_tables[0].row_count > 5:
            tables.extend(text_tables)
            return tables  # Text lines worked, skip table detection

        # Strategy 2: Try Camelot for bordered tables
        if self._camelot_available:
            camelot_tables = self._extract_with_camelot(pdf_path, page_num)
            tables.extend(camelot_tables)

        # Strategy 3: pdfplumber table detection
        pdfplumber_tables = self._extract_with_pdfplumber(page, page_num, page_width, page_height)

        # Add non-overlapping pdfplumber tables
        for pt in pdfplumber_tables:
            if not self._overlaps_existing(pt, tables):
                tables.append(pt)

        return tables

    def _extract_text_lines(
        self,
        page: pdfplumber.page.Page,
        page_num: int,
        page_width: float,
        page_height: float,
    ) -> List[TableRegion]:
        """Extract structured data from text lines with bounding boxes."""
        words = page.extract_words()
        if not words:
            return []

        # Group words into lines by y-position
        lines = self._group_words_into_lines(words)
        if not lines:
            return []

        rows: List[TableRow] = []
        money_pattern = re.compile(r'[\$]?[\(]?[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?[\)]?')

        for row_idx, word_line in enumerate(lines):
            line_text = " ".join(w["text"] for w in word_line)

            # Skip empty lines
            if not line_text.strip():
                continue

            # Detect if this is a header row
            is_header = self._is_header_row(line_text)

            # Parse cells from line
            cells = self._parse_line_to_cells(word_line, row_idx, money_pattern, page_width, page_height)

            if cells:
                # Detect if this is a total row
                is_total = any(
                    kw in line_text.lower()
                    for kw in ["total", "net income", "gross profit"]
                )
                rows.append(TableRow(row_index=row_idx, cells=cells, is_header=is_header, is_total=is_total))

        if rows:
            table = TableRegion(
                id=f"p{page_num}_text",
                page=page_num,
                rows=rows,
                confidence=0.90,
                detection_method="text_lines_bbox",
            )
            return [table]

        return []

    def _group_words_into_lines(self, words: List[dict]) -> List[List[dict]]:
        """Group words into lines based on y-position."""
        if not words:
            return []

        # Sort by y, then x
        sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))

        lines = []
        current_line = []
        last_top = None

        for word in sorted_words:
            if last_top is None:
                current_line.append(word)
                last_top = word["top"]
            elif abs(word["top"] - last_top) < 3:  # Same line (3pt tolerance)
                current_line.append(word)
            else:
                if current_line:
                    lines.append(sorted(current_line, key=lambda w: w["x0"]))
                current_line = [word]
                last_top = word["top"]

        if current_line:
            lines.append(sorted(current_line, key=lambda w: w["x0"]))

        return lines

    def _is_header_row(self, line_text: str) -> bool:
        """Check if line is a header row."""
        header_patterns = [
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
            r"\bQ[1-4]\b",
            r"\bFY\d{2,4}\b",
            r"\b20\d{2}\b.*\b20\d{2}\b",  # Multiple years
        ]
        for pattern in header_patterns:
            if re.search(pattern, line_text, re.IGNORECASE):
                return True
        return False

    def _parse_line_to_cells(
        self,
        word_line: List[dict],
        row_idx: int,
        money_pattern: re.Pattern,
        page_width: float,
        page_height: float,
    ) -> List[TableCell]:
        """Parse a line of words into table cells."""
        cells = []
        label_words = []
        value_cells = []

        for word in word_line:
            text = word["text"]

            # Check if word is a numeric value
            if re.search(r'[\d]', text) and (re.search(r'[.,]', text) or re.search(r'\d{3,}', text)):
                parsed = self._numeric_parser.parse(text)
                if parsed.value is not None:
                    bbox = BoundingBox(
                        x0=word["x0"],
                        y0=word["top"],
                        x1=word["x1"],
                        y1=word["bottom"],
                        page_width=page_width,
                        page_height=page_height,
                    )
                    try:
                        value = Decimal(str(round(float(parsed.value), 4)))
                    except (InvalidOperation, ValueError):
                        value = None

                    cell = TableCell(
                        id=f"r{row_idx}_c{len(value_cells)+1}",
                        raw_text=text,
                        row=row_idx,
                        column=len(cells) + len(value_cells) + 1,
                        bbox=bbox,
                        confidence=parsed.confidence,
                        parsed_value=value,
                        is_numeric=True,
                    )
                    value_cells.append(cell)
                else:
                    label_words.append(word)
            else:
                label_words.append(word)

        # Create label cell from label words
        if label_words:
            label_text = " ".join(w["text"] for w in label_words)
            bbox = BoundingBox(
                x0=min(w["x0"] for w in label_words),
                y0=min(w["top"] for w in label_words),
                x1=max(w["x1"] for w in label_words),
                y1=max(w["bottom"] for w in label_words),
                page_width=page_width,
                page_height=page_height,
            )
            cells.append(TableCell(
                id=f"r{row_idx}_c0",
                raw_text=label_text,
                row=row_idx,
                column=0,
                bbox=bbox,
                confidence=0.95,
                is_label=True,
            ))

        # Add value cells
        for vc in value_cells:
            vc.column = len(cells)
            cells.append(vc)

        return cells

    def _extract_with_camelot(
        self,
        pdf_path: Path,
        page_num: int,
    ) -> List[TableRegion]:
        """Extract tables using Camelot lattice mode."""
        try:
            import camelot

            tables = camelot.read_pdf(
                str(pdf_path),
                pages=str(page_num),
                flavor="lattice",
                suppress_stdout=True,
            )

            extracted = []
            for i, table in enumerate(tables):
                if table.accuracy > 50:
                    rows = self._process_camelot_df(table.df, page_num, i)
                    extracted.append(TableRegion(
                        id=f"p{page_num}_cam{i}",
                        page=page_num,
                        rows=rows,
                        confidence=table.accuracy / 100.0,
                        detection_method="camelot_lattice",
                    ))

            return extracted

        except Exception as e:
            logger.warning("Camelot extraction failed", page=page_num, error=str(e))
            return []

    def _process_camelot_df(self, df, page_num: int, table_idx: int) -> List[TableRow]:
        """Process Camelot DataFrame into TableRows."""
        rows = []
        for row_idx, row in df.iterrows():
            cells = []
            for col_idx, value in enumerate(row):
                cell_text = str(value).strip() if value else ""
                parsed = self._numeric_parser.parse(cell_text)
                is_numeric = parsed.value is not None

                try:
                    parsed_val = Decimal(str(round(float(parsed.value), 4))) if parsed.value else None
                except (InvalidOperation, ValueError):
                    parsed_val = None

                cells.append(TableCell(
                    id=f"p{page_num}_t{table_idx}_r{row_idx}_c{col_idx}",
                    raw_text=cell_text,
                    row=row_idx,
                    column=col_idx,
                    confidence=0.9 if is_numeric else 0.95,
                    parsed_value=parsed_val,
                    is_numeric=is_numeric,
                    is_label=col_idx == 0 and not is_numeric,
                ))
            rows.append(TableRow(row_index=row_idx, cells=cells))
        return rows

    def _extract_with_pdfplumber(
        self,
        page: pdfplumber.page.Page,
        page_num: int,
        page_width: float,
        page_height: float,
    ) -> List[TableRegion]:
        """Extract tables using pdfplumber."""
        try:
            # Try line-based detection first
            tables = page.find_tables(
                table_settings={
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                }
            )

            detection_method = "pdfplumber_lines"
            if not tables:
                tables = page.find_tables(
                    table_settings={
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    }
                )
                detection_method = "pdfplumber_text"

            extracted = []
            for i, table in enumerate(tables):
                text_data = table.extract()
                if not text_data or len(text_data) <= 1:
                    continue

                rows = self._process_pdfplumber_table(text_data, page_num, i, table)

                bbox = None
                if table.bbox:
                    bbox = BoundingBox(
                        x0=table.bbox[0],
                        y0=table.bbox[1],
                        x1=table.bbox[2],
                        y1=table.bbox[3],
                        page_width=page_width,
                        page_height=page_height,
                    )

                extracted.append(TableRegion(
                    id=f"p{page_num}_plumb{i}",
                    page=page_num,
                    rows=rows,
                    bbox=bbox,
                    confidence=0.85 if detection_method == "pdfplumber_lines" else 0.7,
                    detection_method=detection_method,
                ))

            return extracted

        except Exception as e:
            logger.warning("pdfplumber extraction failed", page=page_num, error=str(e))
            return []

    def _process_pdfplumber_table(
        self,
        text_data: List[List],
        page_num: int,
        table_idx: int,
        table_obj,
    ) -> List[TableRow]:
        """Process pdfplumber table data into TableRows."""
        rows = []
        for row_idx, row_text in enumerate(text_data):
            cells = []
            for col_idx, cell_value in enumerate(row_text):
                cell_text = str(cell_value).strip() if cell_value else ""
                parsed = self._numeric_parser.parse(cell_text)
                is_numeric = parsed.value is not None

                try:
                    parsed_val = Decimal(str(round(float(parsed.value), 4))) if parsed.value else None
                except (InvalidOperation, ValueError):
                    parsed_val = None

                # Get bbox if available
                bbox = None
                if hasattr(table_obj, 'rows') and row_idx < len(table_obj.rows):
                    row_cells = table_obj.rows[row_idx]
                    if col_idx < len(row_cells) and row_cells[col_idx]:
                        cell_rect = row_cells[col_idx]
                        bbox = BoundingBox.from_list(list(cell_rect))

                cells.append(TableCell(
                    id=f"p{page_num}_t{table_idx}_r{row_idx}_c{col_idx}",
                    raw_text=cell_text,
                    row=row_idx,
                    column=col_idx,
                    bbox=bbox,
                    confidence=parsed.confidence if is_numeric else 0.9,
                    parsed_value=parsed_val,
                    is_numeric=is_numeric,
                    is_label=col_idx == 0 and not is_numeric,
                ))
            rows.append(TableRow(row_index=row_idx, cells=cells))
        return rows

    def _overlaps_existing(
        self,
        new_table: TableRegion,
        existing: List[TableRegion],
    ) -> bool:
        """Check if new table overlaps with existing tables."""
        for table in existing:
            if table.page == new_table.page:
                if abs(table.row_count - new_table.row_count) <= 1:
                    # Check first row content
                    if table.rows and new_table.rows:
                        existing_first = " ".join(c.raw_text for c in table.rows[0].cells)
                        new_first = " ".join(c.raw_text for c in new_table.rows[0].cells)
                        if existing_first[:50] == new_first[:50]:
                            return True
        return False

    def detect_scale_factor(self, text: str) -> ScaleFactor:
        """Detect units scale factor from text."""
        text_lower = text.lower()
        for pattern, scale in self.UNITS_PATTERNS:
            if re.search(pattern, text_lower):
                return scale
        return ScaleFactor.UNITS


def get_extraction_layer() -> ExtractionLayer:
    """Get ExtractionLayer instance."""
    return ExtractionLayer()
