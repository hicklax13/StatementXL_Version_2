"""
Evidence model and data structures for the StatementXL Engine.

Implements durable evidence store supporting:
- Document, Page, Token (text + bbox), TableRegion, TableCell
- StatementSection classification results with rationale
- NormalizedFact records with provenance
- TemplateProfile of detected grids + eligible cells
- CellPosting records (old/new values + contributing fact ids)
- RunAudit summary
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class StatementType(str, Enum):
    """Financial statement types."""
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Confidence levels for decisions."""
    HIGH = "high"      # >= 0.85
    MEDIUM = "medium"  # >= 0.65
    LOW = "low"        # >= 0.40
    VERY_LOW = "very_low"  # < 0.40


class ExtractionMode(str, Enum):
    """Extraction mode used for a page/region."""
    TEXT = "text"       # Native text extraction
    TABLE = "table"     # Table detection (pdfplumber/camelot)
    OCR = "ocr"         # Optical character recognition


class ScaleFactor(int, Enum):
    """Units scale factor."""
    UNITS = 1
    THOUSANDS = 1_000
    MILLIONS = 1_000_000
    BILLIONS = 1_000_000_000


# =============================================================================
# Token/BBox Level Evidence
# =============================================================================

@dataclass
class BoundingBox:
    """Bounding box coordinates in PDF points."""
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: Optional[float] = None
    page_height: Optional[float] = None

    def to_list(self) -> List[float]:
        return [self.x0, self.y0, self.x1, self.y1]

    @classmethod
    def from_list(cls, coords: List[float]) -> "BoundingBox":
        return cls(x0=coords[0], y0=coords[1], x1=coords[2], y1=coords[3])


@dataclass
class Token:
    """A single text token with location."""
    id: str
    text: str
    bbox: BoundingBox
    page: int
    confidence: float = 1.0
    mode: ExtractionMode = ExtractionMode.TEXT
    font_size: Optional[float] = None
    is_bold: bool = False

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]


@dataclass
class TableCell:
    """A single cell in an extracted table."""
    id: str
    raw_text: str
    row: int
    column: int
    bbox: Optional[BoundingBox] = None
    confidence: float = 1.0
    parsed_value: Optional[Decimal] = None
    is_numeric: bool = False
    is_header: bool = False
    is_label: bool = False
    tokens: List[Token] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]


@dataclass
class TableRow:
    """A row in an extracted table."""
    row_index: int
    cells: List[TableCell]
    is_header: bool = False
    is_total: bool = False


@dataclass
class TableRegion:
    """A detected table region in a PDF page."""
    id: str
    page: int
    rows: List[TableRow]
    bbox: Optional[BoundingBox] = None
    confidence: float = 1.0
    detection_method: str = "pdfplumber"
    statement_type: Optional[StatementType] = None
    title: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return max((len(r.cells) for r in self.rows), default=0)


@dataclass
class PageEvidence:
    """Evidence extracted from a single PDF page."""
    page_num: int
    tokens: List[Token] = field(default_factory=list)
    tables: List[TableRegion] = field(default_factory=list)
    mode: ExtractionMode = ExtractionMode.TEXT
    text_density: float = 1.0  # For OCR detection
    raw_text: str = ""


@dataclass
class DocumentEvidence:
    """All evidence extracted from a PDF document."""
    id: str
    source_path: str
    filename: str
    page_count: int
    pages: List[PageEvidence] = field(default_factory=list)
    extraction_timestamp: datetime = field(default_factory=datetime.utcnow)
    overall_confidence: float = 1.0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def all_tables(self) -> List[TableRegion]:
        """Get all tables from all pages."""
        tables = []
        for page in self.pages:
            tables.extend(page.tables)
        return tables


# =============================================================================
# Statement Section Classification
# =============================================================================

@dataclass
class LLMDecision:
    """Record of an LLM decision for audit."""
    prompt_version: str
    prompt_hash: str
    model_id: str
    raw_response: str
    parsed_json: Dict[str, Any]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0


@dataclass
class StatementSection:
    """A classified section of a financial statement."""
    id: str
    statement_type: StatementType
    title: str
    source_table_id: str
    page: int
    start_row: int
    end_row: int
    confidence: float
    classification_method: str  # "deterministic" or "llm"
    rationale: str
    llm_decision: Optional[LLMDecision] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]


# =============================================================================
# Normalized Facts
# =============================================================================

@dataclass
class PeriodInfo:
    """Period information for a value."""
    raw_header: str
    normalized_key: str  # e.g., "FY2024", "Q3_2024", "3M_2024-09-30"
    end_date: Optional[datetime] = None
    duration_months: Optional[int] = None
    is_ytd: bool = False
    is_restated: bool = False


@dataclass
class NormalizedFact:
    """A normalized financial fact with full provenance."""
    id: str
    # Identity
    normalized_label: str  # Canonical label (e.g., "Revenue", "Total Assets")
    raw_label: str         # Original label from PDF
    # Value
    raw_value: str         # Original text
    parsed_value: Decimal  # Parsed numeric value
    scaled_value: Decimal  # After applying scale factor
    scale_factor: ScaleFactor = ScaleFactor.UNITS
    is_negative: bool = False
    # Period
    period: Optional[PeriodInfo] = None
    # Provenance
    source_document_id: str = ""
    source_page: int = 0
    source_table_id: str = ""
    source_cell_id: str = ""
    source_bbox: Optional[BoundingBox] = None
    # Classification
    statement_type: Optional[StatementType] = None
    ontology_id: Optional[str] = None
    category: Optional[str] = None
    # Confidence
    parse_confidence: float = 1.0
    label_confidence: float = 1.0
    overall_confidence: float = 1.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    # Flags
    is_total: bool = False
    is_subtotal: bool = False
    is_restated: bool = False
    has_conflict: bool = False
    # Aggregation (if this fact was derived from components)
    is_aggregated: bool = False
    aggregation_formula: Optional[str] = None
    component_fact_ids: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def compute_confidence_level(self) -> ConfidenceLevel:
        """Compute confidence level from overall confidence."""
        if self.overall_confidence >= 0.85:
            return ConfidenceLevel.HIGH
        elif self.overall_confidence >= 0.65:
            return ConfidenceLevel.MEDIUM
        elif self.overall_confidence >= 0.40:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


# =============================================================================
# Template Profile
# =============================================================================

@dataclass
class TemplateCell:
    """A cell in the template that can receive data."""
    sheet: str
    address: str  # e.g., "C10"
    row: int
    column: int
    # Content
    current_value: Optional[Any] = None
    has_formula: bool = False
    formula: Optional[str] = None
    # Eligibility
    is_eligible: bool = True  # Can receive data
    is_input_cell: bool = True  # Hardcoded numeric (not formula)
    # Semantic mapping
    row_label: Optional[str] = None
    ontology_id: Optional[str] = None
    period_header: Optional[str] = None
    normalized_period: Optional[str] = None


@dataclass
class TemplateGrid:
    """A detected data grid in the template."""
    sheet: str
    # Label column
    label_column: int
    label_start_row: int
    label_end_row: int
    # Period headers
    period_header_row: int
    period_columns: List[int]
    period_headers: List[str]
    # Value grid
    value_start_row: int
    value_end_row: int
    value_columns: List[int]
    # Eligible cells
    eligible_cells: List[TemplateCell] = field(default_factory=list)


@dataclass
class TemplateProfile:
    """Complete profile of a template's structure."""
    id: str
    source_path: str
    filename: str
    sheet_names: List[str]
    detected_statement_type: Optional[StatementType] = None
    grids: List[TemplateGrid] = field(default_factory=list)
    all_cells: Dict[str, TemplateCell] = field(default_factory=dict)  # key: "Sheet!A1"
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def get_eligible_cells(self) -> List[TemplateCell]:
        """Get all eligible cells across all grids."""
        cells = []
        for grid in self.grids:
            cells.extend(grid.eligible_cells)
        return cells


# =============================================================================
# Mapping and Posting
# =============================================================================

@dataclass
class MappingCandidate:
    """A candidate mapping between a fact and a template cell."""
    fact: NormalizedFact
    target_cell: TemplateCell
    score: float
    match_type: str  # exact, synonym, fuzzy, embedding, llm
    match_components: Dict[str, float] = field(default_factory=dict)


@dataclass
class CellPosting:
    """Record of a value posted to a template cell."""
    id: str
    # Target
    template_cell: TemplateCell
    # Values
    old_value: Optional[Any] = None
    new_value: Decimal = Decimal(0)
    # Source facts
    contributing_fact_ids: List[str] = field(default_factory=list)
    primary_fact_id: str = ""
    # Aggregation
    is_aggregated: bool = False
    aggregation_formula: Optional[str] = None
    aggregation_components: List[str] = field(default_factory=list)
    # Confidence
    confidence: float = 1.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    # Conflict
    had_conflict: bool = False
    conflict_resolution: Optional[str] = None
    rejected_candidates: List[str] = field(default_factory=list)
    # Lineage
    source_pdf: str = ""
    source_section_title: str = ""
    source_page: int = 0
    source_raw_labels: List[str] = field(default_factory=list)
    source_raw_values: List[str] = field(default_factory=list)
    scale_factor: ScaleFactor = ScaleFactor.UNITS
    notes: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]


# =============================================================================
# Reconciliation
# =============================================================================

@dataclass
class ReconciliationCheck:
    """A single reconciliation check result."""
    check_name: str  # e.g., "BS: Assets = Liabilities + Equity"
    is_valid: bool
    expected_value: Optional[Decimal] = None
    actual_value: Optional[Decimal] = None
    delta: Optional[Decimal] = None
    delta_percent: Optional[float] = None
    severity: str = "info"  # info, warning, error
    message: str = ""


@dataclass
class ReconciliationResult:
    """Results of all reconciliation checks."""
    checks: List[ReconciliationCheck] = field(default_factory=list)
    all_passed: bool = True
    critical_failures: int = 0
    warnings: int = 0

    def add_check(self, check: ReconciliationCheck):
        self.checks.append(check)
        if not check.is_valid:
            if check.severity == "error":
                self.critical_failures += 1
                self.all_passed = False
            elif check.severity == "warning":
                self.warnings += 1


# =============================================================================
# Audit and Run Result
# =============================================================================

@dataclass
class RunException:
    """An exception/issue encountered during the run."""
    category: str  # unmatched_template, missing_period, ambiguity, etc.
    severity: str  # info, warning, error
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunAudit:
    """Complete audit record for an engine run."""
    run_id: str
    # Metadata
    system: str = "StatementXL"
    engine_version: str = "1.0.0"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    # Inputs
    template_path: str = ""
    template_filename: str = ""
    pdf_paths: List[str] = field(default_factory=list)
    pdf_filenames: List[str] = field(default_factory=list)
    statement_type: Optional[StatementType] = None
    options: Dict[str, Any] = field(default_factory=dict)
    # Documents
    document_evidence: List[DocumentEvidence] = field(default_factory=list)
    # Sections
    statement_sections: List[StatementSection] = field(default_factory=list)
    # Units/Scale
    detected_scale_factors: Dict[str, ScaleFactor] = field(default_factory=dict)
    # Periods
    period_mappings: List[Dict[str, Any]] = field(default_factory=list)
    # Facts
    normalized_facts: List[NormalizedFact] = field(default_factory=list)
    # Postings
    cell_postings: List[CellPosting] = field(default_factory=list)
    # Reconciliation
    reconciliation: Optional[ReconciliationResult] = None
    # Exceptions
    exceptions: List[RunException] = field(default_factory=list)
    # Summary
    total_facts: int = 0
    mapped_facts: int = 0
    posted_cells: int = 0
    unmatched_template_items: List[str] = field(default_factory=list)
    missing_periods: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.run_id:
            self.run_id = str(uuid.uuid4())

    def add_exception(self, category: str, severity: str, message: str, **details):
        self.exceptions.append(RunException(
            category=category,
            severity=severity,
            message=message,
            details=details,
        ))


@dataclass
class RunResult:
    """Final result of an engine run."""
    success: bool
    run_id: str
    output_path: str
    audit: RunAudit
    error_message: Optional[str] = None
    # Quick access to key metrics
    total_facts_extracted: int = 0
    facts_mapped: int = 0
    cells_posted: int = 0
    reconciliation_passed: bool = True
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
