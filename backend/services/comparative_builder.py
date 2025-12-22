"""
Comparative statement builder for StatementXL.

Combines multiple period statements into aligned multi-year views.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from backend.services.period_normalizer import Period, PeriodType, get_period_normalizer

logger = structlog.get_logger(__name__)


@dataclass
class AlignedLineItem:
    """A line item aligned across multiple periods."""
    
    ontology_id: str
    label: str
    values: Dict[str, Decimal]  # period_key -> value
    confidence: Dict[str, float]  # period_key -> confidence


@dataclass
class ComparativeStatement:
    """A multi-period comparative statement."""
    
    id: uuid.UUID
    statement_type: str  # income_statement, balance_sheet, cash_flow
    periods: List[Period]
    line_items: List[AlignedLineItem]
    period_keys: List[str]  # Column order
    created_at: datetime
    
    @property
    def period_count(self) -> int:
        return len(self.periods)
    
    @property
    def line_item_count(self) -> int:
        return len(self.line_items)


@dataclass
class AlignmentResult:
    """Result of aligning extracts across periods."""
    
    aligned: int
    mismatched: int
    added: int  # Items only in one period
    warnings: List[str]


class ComparativeBuilder:
    """
    Service for building comparative financial statements.
    
    Features:
    - Align line items across multiple periods
    - Detect renamed line items (semantic matching)
    - Handle missing values
    - Generate multi-column output
    """
    
    # Similarity threshold for matching renamed items
    SIMILARITY_THRESHOLD = 0.85
    
    def __init__(self):
        """Initialize comparative builder."""
        self._normalizer = get_period_normalizer()
    
    def build_comparative(
        self,
        extracts: List[Dict[str, Any]],
        statement_type: str = "income_statement",
    ) -> ComparativeStatement:
        """
        Build a comparative statement from multiple extracts.
        
        Args:
            extracts: List of extraction results with period info.
            statement_type: Type of statement to build.
            
        Returns:
            ComparativeStatement with aligned data.
        """
        if not extracts:
            raise ValueError("No extracts provided")
        
        # Sort extracts by period
        sorted_extracts = self._sort_by_period(extracts)
        
        # Extract periods
        periods = [self._get_period(e) for e in sorted_extracts]
        period_keys = [self._period_key(p) for p in periods]
        
        # Build line item index
        all_items: Dict[str, AlignedLineItem] = {}
        
        for extract, period_key in zip(sorted_extracts, period_keys):
            line_items = extract.get("line_items", [])
            
            for item in line_items:
                ontology_id = item.get("ontology_id", item.get("label", "unknown"))
                label = item.get("label", ontology_id)
                value = Decimal(str(item.get("value", 0)))
                confidence = float(item.get("confidence", 0.0))
                
                if ontology_id not in all_items:
                    all_items[ontology_id] = AlignedLineItem(
                        ontology_id=ontology_id,
                        label=label,
                        values={},
                        confidence={},
                    )
                
                all_items[ontology_id].values[period_key] = value
                all_items[ontology_id].confidence[period_key] = confidence
        
        # Sort line items by typical financial statement order
        sorted_items = self._sort_line_items(list(all_items.values()))
        
        comparative = ComparativeStatement(
            id=uuid.uuid4(),
            statement_type=statement_type,
            periods=periods,
            line_items=sorted_items,
            period_keys=period_keys,
            created_at=datetime.utcnow(),
        )
        
        logger.info(
            "Comparative statement built",
            statement_id=str(comparative.id),
            periods=len(periods),
            line_items=len(sorted_items),
        )
        
        return comparative
    
    def _sort_by_period(
        self, extracts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sort extracts by period."""
        def period_sort_key(extract: Dict[str, Any]) -> Tuple[int, int, int]:
            period_str = extract.get("period", "")
            period = self._normalizer.detect_period(period_str)
            return (period.year, period.quarter or 0, period.month or 0)
        
        return sorted(extracts, key=period_sort_key)
    
    def _get_period(self, extract: Dict[str, Any]) -> Period:
        """Get period from extract."""
        period_str = extract.get("period", str(datetime.now().year))
        return self._normalizer.detect_period(period_str)
    
    def _period_key(self, period: Period) -> str:
        """Generate string key for period (for column headers)."""
        if period.period_type == PeriodType.ANNUAL:
            return f"FY{period.year}"
        elif period.period_type == PeriodType.QUARTERLY:
            return f"Q{period.quarter} {period.year}"
        elif period.period_type == PeriodType.MONTHLY:
            return f"{period.month:02d}/{period.year}"
        else:
            return period.label or str(period.year)
    
    def _sort_line_items(
        self, items: List[AlignedLineItem]
    ) -> List[AlignedLineItem]:
        """Sort line items by financial statement order."""
        # Define category order
        category_order = {
            "is:revenue": 1,
            "is:cogs": 2,
            "is:gross_profit": 3,
            "is:opex": 4,
            "is:operating_income": 5,
            "is:ebitda": 6,
            "is:interest_expense": 7,
            "is:ebt": 8,
            "is:income_tax": 9,
            "is:net_income": 10,
            "bs:current_assets": 11,
            "bs:non_current_assets": 12,
            "bs:total_assets": 13,
            "bs:current_liabilities": 14,
            "bs:non_current_liabilities": 15,
            "bs:total_liabilities": 16,
            "bs:total_equity": 17,
            "cf:cfo": 18,
            "cf:cfi": 19,
            "cf:cff": 20,
        }
        
        def sort_key(item: AlignedLineItem) -> int:
            # Check for prefix matches
            for prefix, order in category_order.items():
                if item.ontology_id.startswith(prefix.split(":")[0]):
                    return order
            return 100  # Unknown items at end
        
        return sorted(items, key=sort_key)
    
    def detect_renamed_items(
        self,
        extracts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Detect line items that may have been renamed across periods.
        
        Args:
            extracts: List of extraction results.
            
        Returns:
            List of potential rename mappings.
        """
        # Collect all unique labels per period
        period_labels: Dict[str, Set[str]] = {}
        
        for extract in extracts:
            period = extract.get("period", "unknown")
            labels = {
                item.get("label", "")
                for item in extract.get("line_items", [])
            }
            period_labels[period] = labels
        
        # Find labels that appear in only some periods
        all_labels = set()
        for labels in period_labels.values():
            all_labels.update(labels)
        
        renames = []
        for label in all_labels:
            present_in = [p for p, labels in period_labels.items() if label in labels]
            if len(present_in) < len(period_labels):
                renames.append({
                    "label": label,
                    "present_in": present_in,
                    "missing_from": [
                        p for p in period_labels.keys() if p not in present_in
                    ],
                })
        
        return renames
    
    def to_excel_format(
        self, comparative: ComparativeStatement
    ) -> Dict[str, Any]:
        """
        Convert comparative statement to Excel-ready format.
        
        Returns:
            Dict with headers and rows ready for Excel output.
        """
        headers = ["Line Item"] + comparative.period_keys
        
        rows = []
        for item in comparative.line_items:
            row = [item.label]
            for period_key in comparative.period_keys:
                value = item.values.get(period_key)
                row.append(float(value) if value else None)
            rows.append(row)
        
        return {
            "headers": headers,
            "rows": rows,
            "statement_type": comparative.statement_type,
            "period_count": comparative.period_count,
        }


def get_comparative_builder() -> ComparativeBuilder:
    """Get ComparativeBuilder instance."""
    return ComparativeBuilder()
