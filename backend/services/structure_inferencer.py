"""
Structure inferencer service.

Analyzes Excel templates to detect sections, periods, and semantic structure.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import structlog

from backend.services.excel_parser import ParsedCell, ParsedSheet, ParsedWorkbook
from backend.services.ontology_service import get_ontology_service
from backend.services.classifiers.hybrid import get_hybrid_classifier

logger = structlog.get_logger(__name__)


@dataclass
class DetectedSection:
    """Represents a detected section in the template."""

    name: str
    section_type: str  # income_statement, balance_sheet, cash_flow, other
    sheet: str
    start_row: int
    end_row: int
    header_row: Optional[int] = None
    confidence: float = 0.0


@dataclass
class DetectedPeriod:
    """Represents a detected time period column."""

    column: int
    column_letter: str
    label: str
    frequency: str  # annual, quarterly, monthly
    year: Optional[int] = None
    quarter: Optional[int] = None


@dataclass
class InferredStructure:
    """Complete inferred structure of a template."""

    sections: List[DetectedSection]
    periods: List[DetectedPeriod]
    label_column: int
    data_start_column: int
    header_row: int
    confidence: float


class StructureInferencer:
    """
    Service for inferring template structure.

    Detects sections (Income Statement, Balance Sheet, etc.),
    periods (years, quarters), and label columns.
    """

    # Section header patterns
    SECTION_PATTERNS = {
        "income_statement": [
            r"income\s*statement",
            r"profit\s*(and|&)\s*loss",
            r"p\s*&\s*l",
            r"statement\s*of\s*operations",
            r"operating\s*results",
        ],
        "balance_sheet": [
            r"balance\s*sheet",
            r"statement\s*of\s*financial\s*position",
            r"financial\s*position",
            r"assets\s*and\s*liabilities",
        ],
        "cash_flow": [
            r"cash\s*flow",
            r"statement\s*of\s*cash\s*flows",
            r"sources\s*(and|&)\s*uses",
        ],
    }

    # Period patterns
    YEAR_PATTERN = re.compile(r"(20\d{2}|19\d{2})")
    QUARTER_PATTERN = re.compile(r"Q([1-4])", re.IGNORECASE)
    FISCAL_YEAR_PATTERN = re.compile(r"FY\s*\'?(\d{2,4})", re.IGNORECASE)

    def __init__(self):
        """Initialize structure inferencer."""
        self._ontology = get_ontology_service()
        self._classifier = get_hybrid_classifier()

    def infer_structure(self, workbook: ParsedWorkbook) -> Dict[str, InferredStructure]:
        """
        Infer structure for all sheets in workbook.

        Args:
            workbook: Parsed Excel workbook.

        Returns:
            Dict mapping sheet name to InferredStructure.
        """
        logger.info("Inferring template structure", filename=workbook.filename)

        results = {}

        for sheet in workbook.sheets:
            structure = self._infer_sheet_structure(sheet)
            results[sheet.name] = structure

        return results

    def _infer_sheet_structure(self, sheet: ParsedSheet) -> InferredStructure:
        """
        Infer structure for a single sheet.

        Args:
            sheet: Parsed worksheet.

        Returns:
            InferredStructure for the sheet.
        """
        # Detect sections
        sections = self._detect_sections(sheet)

        # Detect periods
        periods = self._detect_periods(sheet)

        # Find label column (typically column A or first non-empty column)
        label_column = self._find_label_column(sheet)

        # Find data start column
        data_start = label_column + 1
        if periods:
            data_start = min(p.column for p in periods)

        # Find header row
        header_row = self._find_header_row(sheet)

        # Calculate overall confidence
        section_conf = sum(s.confidence for s in sections) / len(sections) if sections else 0
        period_conf = 1.0 if periods else 0.5
        confidence = (section_conf + period_conf) / 2

        return InferredStructure(
            sections=sections,
            periods=periods,
            label_column=label_column,
            data_start_column=data_start,
            header_row=header_row,
            confidence=confidence,
        )

    def _detect_sections(self, sheet: ParsedSheet) -> List[DetectedSection]:
        """
        Detect sections in a sheet.

        Args:
            sheet: Parsed worksheet.

        Returns:
            List of detected sections.
        """
        sections = []
        current_section = None
        current_type = "other"
        section_start = 1

        # Get cells sorted by row
        cells_by_row: Dict[int, List[ParsedCell]] = {}
        for cell in sheet.cells:
            if cell.row not in cells_by_row:
                cells_by_row[cell.row] = []
            cells_by_row[cell.row].append(cell)

        for row_idx in range(1, sheet.max_row + 1):
            if row_idx not in cells_by_row:
                continue

            row_cells = cells_by_row[row_idx]

            # Check for section headers
            for cell in row_cells:
                if isinstance(cell.value, str):
                    section_type = self._identify_section_type(cell.value)

                    if section_type != "other":
                        # Close previous section
                        if current_section:
                            sections.append(DetectedSection(
                                name=current_section,
                                section_type=current_type,
                                sheet=sheet.name,
                                start_row=section_start,
                                end_row=row_idx - 1,
                                confidence=0.85,
                            ))

                        # Start new section
                        current_section = cell.value
                        current_type = section_type
                        section_start = row_idx

        # Close final section
        if current_section:
            sections.append(DetectedSection(
                name=current_section,
                section_type=current_type,
                sheet=sheet.name,
                start_row=section_start,
                end_row=sheet.max_row,
                confidence=0.85,
            ))

        # If no sections detected, create one for entire sheet
        if not sections:
            sections.append(DetectedSection(
                name=sheet.name,
                section_type="other",
                sheet=sheet.name,
                start_row=1,
                end_row=sheet.max_row,
                confidence=0.5,
            ))

        return sections

    def _identify_section_type(self, text: str) -> str:
        """
        Identify section type from header text.

        Args:
            text: Header text.

        Returns:
            Section type string.
        """
        text_lower = text.lower().strip()

        for section_type, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return section_type

        return "other"

    def _detect_periods(self, sheet: ParsedSheet) -> List[DetectedPeriod]:
        """
        Detect period columns in a sheet.

        Args:
            sheet: Parsed worksheet.

        Returns:
            List of detected periods.
        """
        periods = []

        # Look at first few rows for period headers
        header_cells = [c for c in sheet.cells if c.row <= 5 and isinstance(c.value, str)]

        for cell in header_cells:
            period = self._parse_period(cell.value, cell.column, cell.address)
            if period:
                periods.append(period)

        # Sort by column
        periods.sort(key=lambda p: p.column)

        return periods

    def _parse_period(
        self, text: str, column: int, address: str
    ) -> Optional[DetectedPeriod]:
        """
        Parse period from header text.

        Args:
            text: Header text.
            column: Column number.
            address: Cell address.

        Returns:
            DetectedPeriod if found.
        """
        if not text:
            return None

        # Check for year
        year_match = self.YEAR_PATTERN.search(text)
        fiscal_match = self.FISCAL_YEAR_PATTERN.search(text)
        quarter_match = self.QUARTER_PATTERN.search(text)

        year = None
        quarter = None
        frequency = "annual"

        if year_match:
            year = int(year_match.group(1))
        elif fiscal_match:
            fy = fiscal_match.group(1)
            if len(fy) == 2:
                year = 2000 + int(fy)
            else:
                year = int(fy)

        if quarter_match:
            quarter = int(quarter_match.group(1))
            frequency = "quarterly"

        if year or quarter:
            col_letter = re.match(r"([A-Z]+)", address).group(1) if address else ""
            return DetectedPeriod(
                column=column,
                column_letter=col_letter,
                label=text,
                frequency=frequency,
                year=year,
                quarter=quarter,
            )

        return None

    def _find_label_column(self, sheet: ParsedSheet) -> int:
        """Find the column containing row labels."""
        # Typically column A (1) contains labels
        # Check first column with text values
        for col in range(1, 5):
            text_count = sum(
                1 for c in sheet.cells
                if c.column == col and isinstance(c.value, str) and len(c.value) > 2
            )
            if text_count > 5:
                return col
        return 1

    def _find_header_row(self, sheet: ParsedSheet) -> int:
        """Find the header row."""
        # Look for row with period labels
        for row in range(1, 10):
            row_cells = [c for c in sheet.cells if c.row == row]
            period_count = sum(
                1 for c in row_cells
                if isinstance(c.value, str) and self.YEAR_PATTERN.search(c.value)
            )
            if period_count >= 2:
                return row
        return 1


# Singleton instance
_inferencer_instance: Optional[StructureInferencer] = None


def get_structure_inferencer() -> StructureInferencer:
    """Get singleton StructureInferencer instance."""
    global _inferencer_instance
    if _inferencer_instance is None:
        _inferencer_instance = StructureInferencer()
    return _inferencer_instance
