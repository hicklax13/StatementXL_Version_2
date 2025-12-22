"""
Period normalizer service for StatementXL.

Handles period detection, aggregation, and normalization.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


class PeriodType(Enum):
    """Types of financial periods."""
    
    ANNUAL = "annual"
    SEMI_ANNUAL = "semi_annual"
    QUARTERLY = "quarterly"
    MONTHLY = "monthly"
    YTD = "ytd"  # Year-to-date
    LTM = "ltm"  # Last twelve months
    UNKNOWN = "unknown"


@dataclass
class Period:
    """Represents a financial period."""
    
    period_type: PeriodType
    year: int
    quarter: Optional[int] = None  # 1-4
    month: Optional[int] = None  # 1-12
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    label: Optional[str] = None


@dataclass
class NormalizedValue:
    """A value normalized to a specific period."""
    
    original_value: Decimal
    normalized_value: Decimal
    original_period: Period
    target_period: Period
    normalization_method: str  # sum, average, end_of_period, prorated


class PeriodNormalizer:
    """
    Service for period detection and normalization.
    
    Features:
    - Detect period granularity from headers or context
    - Aggregate monthly → quarterly → annual
    - Handle partial periods (prorate to annual)
    - Maintain lineage through aggregation
    """
    
    # Patterns for period detection
    ANNUAL_PATTERNS = [
        r"FY\s*(\d{4})",
        r"Fiscal\s*Year\s*(\d{4})",
        r"Year\s*Ended?\s*(\d{4})",
        r"Annual\s*(\d{4})",
        r"^(\d{4})$",
    ]
    
    QUARTERLY_PATTERNS = [
        r"Q([1-4])\s*['\"]?(\d{2,4})",
        r"([1-4])Q\s*['\"]?(\d{2,4})",
        r"(\d{4})\s*Q([1-4])",
        r"Quarter\s*([1-4])[,\s]+(\d{4})",
    ]
    
    MONTHLY_PATTERNS = [
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-]*['\"]?(\d{2,4})",
        r"(\d{1,2})/(\d{4})",
        r"(\d{4})-(\d{2})",
    ]
    
    MONTH_MAP = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    
    def detect_period(self, text: str) -> Period:
        """
        Detect period from text (column header, label, etc.).
        
        Args:
            text: Text containing period information.
            
        Returns:
            Detected Period.
        """
        text = text.strip()
        
        # Try quarterly patterns first (more specific)
        for pattern in self.QUARTERLY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if groups[0].isdigit() and int(groups[0]) <= 4:
                    quarter = int(groups[0])
                    year = self._parse_year(groups[1])
                else:
                    year = self._parse_year(groups[0])
                    quarter = int(groups[1])
                
                return Period(
                    period_type=PeriodType.QUARTERLY,
                    year=year,
                    quarter=quarter,
                    label=text,
                )
        
        # Try monthly patterns
        for pattern in self.MONTHLY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if groups[0].lower()[:3] in self.MONTH_MAP:
                    month = self.MONTH_MAP[groups[0].lower()[:3]]
                    year = self._parse_year(groups[1])
                else:
                    month = int(groups[0]) if groups[0].isdigit() else int(groups[1])
                    year = self._parse_year(groups[1] if groups[0].isdigit() else groups[0])
                
                return Period(
                    period_type=PeriodType.MONTHLY,
                    year=year,
                    month=month,
                    label=text,
                )
        
        # Try annual patterns
        for pattern in self.ANNUAL_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                year = self._parse_year(match.group(1))
                return Period(
                    period_type=PeriodType.ANNUAL,
                    year=year,
                    label=text,
                )
        
        # Unknown
        return Period(
            period_type=PeriodType.UNKNOWN,
            year=datetime.now().year,
            label=text,
        )
    
    def _parse_year(self, year_str: str) -> int:
        """Parse year from string (handles 2-digit and 4-digit)."""
        year = int(year_str)
        if year < 100:
            year = 2000 + year if year < 50 else 1900 + year
        return year
    
    def aggregate_to_annual(
        self,
        values: List[Tuple[Period, Decimal]],
        is_flow_statement: bool = True,
    ) -> NormalizedValue:
        """
        Aggregate period values to annual.
        
        Args:
            values: List of (period, value) tuples.
            is_flow_statement: True for P&L/CF (sum), False for BS (end of period).
            
        Returns:
            NormalizedValue with aggregation details.
        """
        if not values:
            raise ValueError("No values to aggregate")
        
        # Sort by period
        sorted_values = sorted(
            values,
            key=lambda x: (x[0].year, x[0].quarter or 0, x[0].month or 0),
        )
        
        first_period = sorted_values[0][0]
        last_period = sorted_values[-1][0]
        
        if is_flow_statement:
            # Sum for flow statements (P&L, Cash Flow)
            total = sum(v[1] for v in sorted_values)
            method = "sum"
        else:
            # End of period for balance sheet
            total = sorted_values[-1][1]
            method = "end_of_period"
        
        # Determine if we need to prorate
        periods_covered = len(sorted_values)
        expected_periods = self._expected_periods(first_period.period_type)
        
        if is_flow_statement and periods_covered < expected_periods:
            # Prorate to annual
            prorate_factor = expected_periods / periods_covered
            normalized = total * Decimal(str(prorate_factor))
            method = "prorated"
        else:
            normalized = total
        
        return NormalizedValue(
            original_value=total,
            normalized_value=normalized,
            original_period=first_period,
            target_period=Period(
                period_type=PeriodType.ANNUAL,
                year=last_period.year,
            ),
            normalization_method=method,
        )
    
    def _expected_periods(self, period_type: PeriodType) -> int:
        """Get expected number of periods per year."""
        return {
            PeriodType.MONTHLY: 12,
            PeriodType.QUARTERLY: 4,
            PeriodType.SEMI_ANNUAL: 2,
            PeriodType.ANNUAL: 1,
        }.get(period_type, 1)
    
    def convert_period(
        self,
        value: Decimal,
        from_period: Period,
        to_period_type: PeriodType,
        is_flow_statement: bool = True,
    ) -> NormalizedValue:
        """
        Convert a value from one period type to another.
        
        Args:
            value: Original value.
            from_period: Source period.
            to_period_type: Target period type.
            is_flow_statement: Whether value is from flow statement.
            
        Returns:
            NormalizedValue with conversion details.
        """
        from_count = self._expected_periods(from_period.period_type)
        to_count = self._expected_periods(to_period_type)
        
        if is_flow_statement:
            # Scale up or down
            factor = Decimal(str(to_count)) / Decimal(str(from_count))
            normalized = value * factor
            method = "scaled"
        else:
            # Balance sheet values don't convert
            normalized = value
            method = "unchanged"
        
        return NormalizedValue(
            original_value=value,
            normalized_value=normalized,
            original_period=from_period,
            target_period=Period(
                period_type=to_period_type,
                year=from_period.year,
            ),
            normalization_method=method,
        )


def get_period_normalizer() -> PeriodNormalizer:
    """Get PeriodNormalizer instance."""
    return PeriodNormalizer()
