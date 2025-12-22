"""
Trend validator for StatementXL.

Detects anomalies and outliers in financial data across periods.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TrendAnomaly:
    """Represents a detected trend anomaly."""
    
    line_item: str
    period: str
    value: Decimal
    previous_value: Optional[Decimal]
    change_percent: float
    anomaly_type: str  # spike, drop, sign_change, zero_value
    severity: str  # low, medium, high, critical
    message: str


@dataclass
class TrendValidationResult:
    """Result of trend validation."""
    
    is_valid: bool
    anomalies: List[TrendAnomaly]
    warnings: List[str]
    line_items_checked: int
    periods_checked: int


class TrendValidator:
    """
    Validator for detecting anomalies in financial trends.
    
    Features:
    - Detect large YoY changes (>50%)
    - Detect sign changes (positive to negative)
    - Detect zero values in key metrics
    - Severity scoring based on impact
    """
    
    # Thresholds for anomaly detection
    SPIKE_THRESHOLD = 0.50  # 50% increase
    DROP_THRESHOLD = -0.30  # 30% decrease
    CRITICAL_DROP_THRESHOLD = -0.50  # 50% decrease
    
    # Line items that should never be negative
    NON_NEGATIVE_ITEMS = {
        "is:revenue", "is:gross_profit", "bs:total_assets",
        "bs:cash", "bs:inventory", "bs:accounts_receivable",
    }
    
    # Key metrics that should not be zero
    KEY_METRICS = {
        "is:revenue", "is:net_income", "bs:total_assets",
        "bs:total_equity", "cf:cfo",
    }
    
    def validate_trend(
        self,
        data: Dict[str, Dict[str, Decimal]],
        periods: List[str],
    ) -> TrendValidationResult:
        """
        Validate trends across periods.
        
        Args:
            data: Dict of {line_item_id: {period: value}}.
            periods: Ordered list of period keys.
            
        Returns:
            TrendValidationResult with detected anomalies.
        """
        anomalies: List[TrendAnomaly] = []
        warnings: List[str] = []
        
        for line_item, period_values in data.items():
            # Check each consecutive period pair
            for i in range(1, len(periods)):
                prev_period = periods[i - 1]
                curr_period = periods[i]
                
                prev_value = period_values.get(prev_period)
                curr_value = period_values.get(curr_period)
                
                if prev_value is None or curr_value is None:
                    continue
                
                # Calculate change
                if prev_value != 0:
                    change_pct = float((curr_value - prev_value) / abs(prev_value))
                else:
                    change_pct = float("inf") if curr_value != 0 else 0
                
                # Check for spikes
                if change_pct > self.SPIKE_THRESHOLD:
                    anomalies.append(TrendAnomaly(
                        line_item=line_item,
                        period=curr_period,
                        value=curr_value,
                        previous_value=prev_value,
                        change_percent=change_pct * 100,
                        anomaly_type="spike",
                        severity="medium",
                        message=f"{line_item} increased {change_pct * 100:.1f}% from {prev_period} to {curr_period}",
                    ))
                
                # Check for critical drops
                if change_pct < self.CRITICAL_DROP_THRESHOLD:
                    anomalies.append(TrendAnomaly(
                        line_item=line_item,
                        period=curr_period,
                        value=curr_value,
                        previous_value=prev_value,
                        change_percent=change_pct * 100,
                        anomaly_type="drop",
                        severity="critical",
                        message=f"{line_item} dropped {abs(change_pct) * 100:.1f}% from {prev_period} to {curr_period}",
                    ))
                elif change_pct < self.DROP_THRESHOLD:
                    anomalies.append(TrendAnomaly(
                        line_item=line_item,
                        period=curr_period,
                        value=curr_value,
                        previous_value=prev_value,
                        change_percent=change_pct * 100,
                        anomaly_type="drop",
                        severity="high",
                        message=f"{line_item} dropped {abs(change_pct) * 100:.1f}% from {prev_period} to {curr_period}",
                    ))
                
                # Check for sign changes
                if prev_value > 0 and curr_value < 0:
                    anomalies.append(TrendAnomaly(
                        line_item=line_item,
                        period=curr_period,
                        value=curr_value,
                        previous_value=prev_value,
                        change_percent=change_pct * 100,
                        anomaly_type="sign_change",
                        severity="high",
                        message=f"{line_item} changed from positive to negative in {curr_period}",
                    ))
            
            # Check for negative values in non-negative items
            for period, value in period_values.items():
                if value and value < 0 and any(
                    line_item.startswith(prefix) for prefix in self.NON_NEGATIVE_ITEMS
                ):
                    anomalies.append(TrendAnomaly(
                        line_item=line_item,
                        period=period,
                        value=value,
                        previous_value=None,
                        change_percent=0,
                        anomaly_type="negative_value",
                        severity="high",
                        message=f"{line_item} has unexpected negative value in {period}",
                    ))
            
            # Check for zero values in key metrics
            for period, value in period_values.items():
                if value == 0 and any(
                    line_item.startswith(prefix) for prefix in self.KEY_METRICS
                ):
                    warnings.append(
                        f"{line_item} is zero in {period} - verify if intentional"
                    )
        
        return TrendValidationResult(
            is_valid=len([a for a in anomalies if a.severity in ("high", "critical")]) == 0,
            anomalies=anomalies,
            warnings=warnings,
            line_items_checked=len(data),
            periods_checked=len(periods),
        )
    
    def validate_yoy_growth(
        self,
        current_value: Decimal,
        prior_value: Decimal,
        line_item: str,
    ) -> Optional[TrendAnomaly]:
        """
        Validate year-over-year growth for a single item.
        
        Args:
            current_value: Current period value.
            prior_value: Prior period value.
            line_item: Line item identifier.
            
        Returns:
            TrendAnomaly if issue detected, None otherwise.
        """
        if prior_value == 0:
            return None
        
        change_pct = float((current_value - prior_value) / abs(prior_value))
        
        if change_pct < self.CRITICAL_DROP_THRESHOLD:
            return TrendAnomaly(
                line_item=line_item,
                period="current",
                value=current_value,
                previous_value=prior_value,
                change_percent=change_pct * 100,
                anomaly_type="drop",
                severity="critical",
                message=f"{line_item} dropped {abs(change_pct) * 100:.1f}% YoY - potential error",
            )
        
        return None


def get_trend_validator() -> TrendValidator:
    """Get TrendValidator instance."""
    return TrendValidator()
