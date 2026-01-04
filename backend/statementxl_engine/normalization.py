"""
Normalization layer for the StatementXL Engine.

Pass 3: Normalize units, signs, periods, and canonical labels.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import structlog

from backend.statementxl_engine.models import (
    ConfidenceLevel,
    DocumentEvidence,
    NormalizedFact,
    PeriodInfo,
    ScaleFactor,
    StatementSection,
    StatementType,
    TableCell,
    TableRegion,
)
from backend.services.period_normalizer import PeriodNormalizer as BasePeriodNormalizer

logger = structlog.get_logger(__name__)


# =============================================================================
# Label Synonyms and Normalization
# =============================================================================

LABEL_SYNONYMS: Dict[str, List[str]] = {
    # Revenue
    "Revenue": ["Net Sales", "Sales", "Net Revenue", "Total Revenue", "Revenues", "Net sales"],
    "Product Revenue": ["Products", "Product Sales", "Product", "Net product sales"],
    "Service Revenue": ["Services", "Service Sales", "Service", "Net service sales"],
    # Cost of Revenue
    "Cost of Revenue": ["Cost of Goods Sold", "COGS", "Cost of Sales", "Cost of products sold", "Cost of services"],
    "Cost of Products": ["Cost of product sales", "Products cost", "Cost of goods"],
    "Cost of Services": ["Cost of service sales", "Services cost"],
    # Gross Profit
    "Gross Profit": ["Gross Margin", "Gross Income"],
    # Operating Expenses
    "Research and Development": ["R&D", "Research & Development", "R&D Expenses"],
    "Sales and Marketing": ["Selling and Marketing", "Marketing", "Sales & Marketing", "Selling, general and administrative"],
    "General and Administrative": ["G&A", "Administrative", "General & Administrative"],
    "Operating Expenses": ["Total Operating Expenses", "Operating Costs", "Operating expenses"],
    # Operating Income
    "Operating Income": ["Income from Operations", "Operating Profit", "EBIT", "Operating income (loss)"],
    # Other Income/Expense
    "Interest Income": ["Interest and dividend income", "Interest revenue"],
    "Interest Expense": ["Interest cost", "Finance costs", "Interest and debt expense"],
    "Other Income": ["Other income, net", "Other, net", "Miscellaneous income"],
    "Other Expense": ["Other expenses, net", "Miscellaneous expense"],
    # Income Before Tax
    "Income Before Tax": ["Income Before Income Taxes", "Pre-tax Income", "EBT", "Income before provision for income taxes"],
    # Tax
    "Income Tax Expense": ["Provision for Income Taxes", "Income Taxes", "Tax Expense", "Provision for income taxes"],
    # Net Income
    "Net Income": ["Net Earnings", "Net Profit", "Net Income (Loss)", "Net income attributable to common shareholders"],
    # Balance Sheet - Assets
    "Total Assets": ["Assets", "Total assets"],
    "Cash and Cash Equivalents": ["Cash", "Cash & Equivalents", "Cash and short-term investments"],
    "Accounts Receivable": ["Trade Receivables", "Receivables", "Trade accounts receivable, net"],
    "Inventory": ["Inventories", "Merchandise inventory"],
    "Total Current Assets": ["Current Assets"],
    "Property Plant and Equipment": ["PP&E", "Fixed Assets", "Property, plant and equipment, net"],
    "Total Non-Current Assets": ["Non-Current Assets", "Long-term assets"],
    # Balance Sheet - Liabilities
    "Total Liabilities": ["Liabilities", "Total liabilities"],
    "Accounts Payable": ["Trade Payables", "Payables"],
    "Short-term Debt": ["Current Portion of Long-term Debt", "Short-term borrowings"],
    "Total Current Liabilities": ["Current Liabilities"],
    "Long-term Debt": ["Long-term borrowings", "Notes payable"],
    "Total Non-Current Liabilities": ["Non-Current Liabilities", "Long-term liabilities"],
    # Balance Sheet - Equity
    "Total Equity": ["Stockholders' Equity", "Shareholders' Equity", "Total shareholders' equity"],
    "Common Stock": ["Common Shares", "Share Capital"],
    "Retained Earnings": ["Accumulated Deficit", "Retained earnings (accumulated deficit)"],
    # Cash Flow
    "Cash from Operations": ["Net Cash from Operating Activities", "Operating Cash Flow", "Net cash provided by operating activities"],
    "Cash from Investing": ["Net Cash from Investing Activities", "Investing Cash Flow", "Net cash used in investing activities"],
    "Cash from Financing": ["Net Cash from Financing Activities", "Financing Cash Flow", "Net cash used in financing activities"],
    "Net Change in Cash": ["Change in Cash", "Increase in Cash", "Net increase (decrease) in cash"],
}

# Build reverse lookup
LABEL_TO_CANONICAL: Dict[str, str] = {}
for canonical, synonyms in LABEL_SYNONYMS.items():
    LABEL_TO_CANONICAL[canonical.lower()] = canonical
    for syn in synonyms:
        LABEL_TO_CANONICAL[syn.lower()] = canonical


class NormalizationLayer:
    """
    Normalization layer for financial data.

    Handles:
    - Units detection and scaling (thousands, millions)
    - Sign normalization (parentheses = negative)
    - Period normalization (raw headers to normalized keys)
    - Label normalization (to canonical labels)
    """

    def __init__(self):
        self._period_normalizer = BasePeriodNormalizer()

    def normalize_document(
        self,
        doc_evidence: DocumentEvidence,
        statement_sections: List[StatementSection],
        detected_scale_factors: Dict[str, ScaleFactor],
    ) -> List[NormalizedFact]:
        """
        Normalize all extracted data from a document.

        Args:
            doc_evidence: Extracted document evidence.
            statement_sections: Classified statement sections.
            detected_scale_factors: Scale factors by section/page.

        Returns:
            List of normalized facts with full provenance.
        """
        facts: List[NormalizedFact] = []

        for page in doc_evidence.pages:
            for table in page.tables:
                # Get scale factor for this table
                scale_key = f"p{page.page_num}"
                scale_factor = detected_scale_factors.get(scale_key, ScaleFactor.UNITS)

                # Detect periods from header row
                periods = self._detect_periods_from_table(table)

                # Get statement type from sections
                stmt_type = self._get_statement_type_for_table(table, statement_sections)

                # Process each row
                for row in table.rows:
                    if row.is_header:
                        continue

                    row_facts = self._normalize_row(
                        row=row,
                        table=table,
                        periods=periods,
                        scale_factor=scale_factor,
                        statement_type=stmt_type,
                        doc_evidence=doc_evidence,
                    )
                    facts.extend(row_facts)

        logger.info(
            "Document normalization complete",
            doc_id=doc_evidence.id,
            total_facts=len(facts),
        )

        return facts

    def _detect_periods_from_table(
        self,
        table: TableRegion,
    ) -> Dict[int, PeriodInfo]:
        """Detect periods from table header row."""
        periods: Dict[int, PeriodInfo] = {}

        # Find header row (usually first row or marked)
        header_row = None
        for row in table.rows:
            if row.is_header:
                header_row = row
                break
        if not header_row and table.rows:
            header_row = table.rows[0]

        if not header_row:
            return periods

        # Parse period from each cell
        for cell in header_row.cells:
            if cell.column == 0:  # Skip label column
                continue

            if cell.raw_text:
                period_info = self._parse_period(cell.raw_text)
                if period_info:
                    periods[cell.column] = period_info

        return periods

    def _parse_period(self, text: str) -> Optional[PeriodInfo]:
        """Parse period information from text."""
        period = self._period_normalizer.detect_period(text)

        if period.period_type.value == "unknown":
            return None

        # Build normalized key
        if period.quarter:
            normalized_key = f"Q{period.quarter}_{period.year}"
        elif period.month:
            month_str = f"{period.month:02d}"
            normalized_key = f"{period.year}-{month_str}"
        else:
            normalized_key = f"FY{period.year}"

        # Detect if restated
        is_restated = any(
            kw in text.lower()
            for kw in ["restated", "revised", "adjusted", "as restated"]
        )

        return PeriodInfo(
            raw_header=text,
            normalized_key=normalized_key,
            end_date=period.end_date,
            duration_months=self._get_duration_months(period.period_type.value),
            is_restated=is_restated,
        )

    def _get_duration_months(self, period_type: str) -> int:
        """Get duration in months for period type."""
        return {
            "annual": 12,
            "semi_annual": 6,
            "quarterly": 3,
            "monthly": 1,
        }.get(period_type, 12)

    def _get_statement_type_for_table(
        self,
        table: TableRegion,
        sections: List[StatementSection],
    ) -> Optional[StatementType]:
        """Get statement type for a table from classified sections."""
        for section in sections:
            if section.source_table_id == table.id:
                return section.statement_type
        return table.statement_type

    def _normalize_row(
        self,
        row,
        table: TableRegion,
        periods: Dict[int, PeriodInfo],
        scale_factor: ScaleFactor,
        statement_type: Optional[StatementType],
        doc_evidence: DocumentEvidence,
    ) -> List[NormalizedFact]:
        """Normalize a single row into facts."""
        facts: List[NormalizedFact] = []

        # Get label from first cell
        label_cell = next((c for c in row.cells if c.is_label), None)
        if not label_cell and row.cells:
            label_cell = row.cells[0]

        if not label_cell:
            return facts

        raw_label = label_cell.raw_text.strip()
        if not raw_label:
            return facts

        # Normalize label
        normalized_label = self._normalize_label(raw_label)

        # Detect if this is a total row
        is_total = row.is_total or any(
            kw in raw_label.lower()
            for kw in ["total", "net income", "gross profit", "subtotal"]
        )

        # Process each numeric cell
        for cell in row.cells:
            if not cell.is_numeric or cell.parsed_value is None:
                continue

            # Get period for this column
            period = periods.get(cell.column)

            # Normalize value with scale and sign
            raw_value = cell.raw_text
            parsed_value = cell.parsed_value
            is_negative = self._detect_negative(raw_value)
            scaled_value = self._apply_scale(parsed_value, scale_factor, is_negative)

            # Calculate confidence
            parse_conf = cell.confidence
            label_conf = self._calculate_label_confidence(raw_label, normalized_label)
            overall_conf = (parse_conf * 0.6 + label_conf * 0.4)

            fact = NormalizedFact(
                id="",  # Will be auto-generated
                normalized_label=normalized_label,
                raw_label=raw_label,
                raw_value=raw_value,
                parsed_value=parsed_value,
                scaled_value=scaled_value,
                scale_factor=scale_factor,
                is_negative=is_negative,
                period=period,
                source_document_id=doc_evidence.id,
                source_page=table.page,
                source_table_id=table.id,
                source_cell_id=cell.id,
                source_bbox=cell.bbox,
                statement_type=statement_type,
                parse_confidence=parse_conf,
                label_confidence=label_conf,
                overall_confidence=overall_conf,
                is_total=is_total,
            )
            fact.confidence_level = fact.compute_confidence_level()

            facts.append(fact)

        return facts

    def _normalize_label(self, raw_label: str) -> str:
        """Normalize label to canonical form."""
        # Clean label
        cleaned = self._clean_label(raw_label)

        # Try exact match
        lookup_key = cleaned.lower()
        if lookup_key in LABEL_TO_CANONICAL:
            return LABEL_TO_CANONICAL[lookup_key]

        # Try fuzzy match (simple prefix/suffix stripping)
        # Remove common prefixes/suffixes
        for prefix in ["total ", "net "]:
            if lookup_key.startswith(prefix):
                stripped = lookup_key[len(prefix):]
                if stripped in LABEL_TO_CANONICAL:
                    return LABEL_TO_CANONICAL[stripped]

        # No match found, return cleaned original
        return cleaned

    def _clean_label(self, label: str) -> str:
        """Clean label by removing footnote markers, extra whitespace, etc."""
        # Remove footnote markers like (1), *, etc.
        cleaned = re.sub(r'\s*\([0-9]+\)\s*', ' ', label)
        cleaned = re.sub(r'\s*\*+\s*', ' ', cleaned)
        cleaned = re.sub(r'\s*\[\d+\]\s*', ' ', cleaned)

        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())

        return cleaned.strip()

    def _calculate_label_confidence(self, raw_label: str, normalized_label: str) -> float:
        """Calculate confidence in label normalization."""
        if raw_label.lower().strip() == normalized_label.lower().strip():
            return 1.0
        if raw_label.lower().strip() in LABEL_TO_CANONICAL:
            return 0.95
        # Fuzzy match
        return 0.75

    def _detect_negative(self, raw_value: str) -> bool:
        """Detect if value is negative from formatting."""
        # Parentheses indicate negative
        if re.match(r'^\s*\(.*\)\s*$', raw_value):
            return True
        # Leading minus
        if re.match(r'^\s*-', raw_value):
            return True
        return False

    def _apply_scale(
        self,
        value: Decimal,
        scale_factor: ScaleFactor,
        is_negative: bool,
    ) -> Decimal:
        """Apply scale factor and sign to value."""
        scaled = value * Decimal(scale_factor.value)
        if is_negative:
            scaled = -abs(scaled)
        return scaled


def get_normalization_layer() -> NormalizationLayer:
    """Get NormalizationLayer instance."""
    return NormalizationLayer()
