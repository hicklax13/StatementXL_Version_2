"""
Validation layer for the StatementXL Engine.

Pass 5: Reconciliation checks and internal consistency validation.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

import structlog

from backend.statementxl_engine.models import (
    CellPosting,
    NormalizedFact,
    ReconciliationCheck,
    ReconciliationResult,
    StatementType,
)

logger = structlog.get_logger(__name__)


class ValidationLayer:
    """
    Validation layer for reconciliation and consistency checks.

    Computes and validates:
    - Income statement: Gross Profit = Revenue - COGS
    - Balance sheet: Assets = Liabilities + Equity
    - Cash flow: End Cash = Beg Cash + Net Change
    - Internal sum relationships

    Never modifies values - only flags issues and adjusts confidence.
    """

    # Materiality threshold for reconciliation differences
    MATERIALITY_THRESHOLD_PERCENT = 0.01  # 1%
    MATERIALITY_THRESHOLD_ABS = Decimal("1000")  # $1,000

    # Label mappings for reconciliation
    INCOME_STATEMENT_LABELS = {
        "revenue": ["Revenue", "Total Revenue", "Net Sales"],
        "cogs": ["Cost of Revenue", "Cost of Goods Sold", "COGS", "Total Cost of Goods Sold"],
        "gross_profit": ["Gross Profit", "Gross Margin"],
        "operating_expenses": ["Operating Expenses", "Total Operating Expenses"],
        "operating_income": ["Operating Income", "Income from Operations"],
        "net_income": ["Net Income", "Net Earnings"],
    }

    BALANCE_SHEET_LABELS = {
        "total_assets": ["Total Assets"],
        "total_liabilities": ["Total Liabilities"],
        "total_equity": ["Total Equity", "Stockholders' Equity", "Shareholders' Equity"],
        "current_assets": ["Total Current Assets", "Current Assets"],
        "current_liabilities": ["Total Current Liabilities", "Current Liabilities"],
    }

    CASH_FLOW_LABELS = {
        "cfo": ["Cash from Operations", "Net Cash from Operating Activities"],
        "cfi": ["Cash from Investing", "Net Cash from Investing Activities"],
        "cff": ["Cash from Financing", "Net Cash from Financing Activities"],
        "net_change": ["Net Change in Cash", "Net Increase in Cash"],
        "begin_cash": ["Beginning Cash", "Cash at Beginning"],
        "end_cash": ["Ending Cash", "Cash at End"],
    }

    def validate(
        self,
        postings: List[CellPosting],
        facts: List[NormalizedFact],
        statement_type: Optional[StatementType] = None,
    ) -> ReconciliationResult:
        """
        Run all validation checks.

        Args:
            postings: Cell postings to validate.
            facts: All normalized facts.
            statement_type: Type of statement being validated.

        Returns:
            ReconciliationResult with all check results.
        """
        result = ReconciliationResult()

        # Build value lookup from postings
        values = self._build_value_lookup(postings)

        # Run appropriate checks based on statement type
        if statement_type == StatementType.INCOME_STATEMENT or statement_type is None:
            self._validate_income_statement(values, result)

        if statement_type == StatementType.BALANCE_SHEET or statement_type is None:
            self._validate_balance_sheet(values, result)

        if statement_type == StatementType.CASH_FLOW or statement_type is None:
            self._validate_cash_flow(values, result)

        # Log results
        logger.info(
            "Validation complete",
            checks=len(result.checks),
            passed=sum(1 for c in result.checks if c.is_valid),
            failed=sum(1 for c in result.checks if not c.is_valid),
        )

        return result

    def _build_value_lookup(
        self,
        postings: List[CellPosting],
    ) -> Dict[str, Decimal]:
        """Build lookup from normalized labels to values."""
        values: Dict[str, Decimal] = {}

        for posting in postings:
            if posting.source_raw_labels:
                # Use the first label
                label = posting.source_raw_labels[0]
                values[label.lower()] = posting.new_value

        return values

    def _get_value(
        self,
        values: Dict[str, Decimal],
        label_category: str,
        label_mapping: Dict[str, List[str]],
    ) -> Optional[Decimal]:
        """Get value for a label category."""
        if label_category not in label_mapping:
            return None

        for label in label_mapping[label_category]:
            key = label.lower()
            if key in values:
                return values[key]

        return None

    def _validate_income_statement(
        self,
        values: Dict[str, Decimal],
        result: ReconciliationResult,
    ) -> None:
        """Validate income statement reconciliations."""
        # Check: Gross Profit = Revenue - COGS
        revenue = self._get_value(values, "revenue", self.INCOME_STATEMENT_LABELS)
        cogs = self._get_value(values, "cogs", self.INCOME_STATEMENT_LABELS)
        gross_profit = self._get_value(values, "gross_profit", self.INCOME_STATEMENT_LABELS)

        if all(v is not None for v in [revenue, cogs, gross_profit]):
            expected = revenue - cogs
            delta = abs(expected - gross_profit)
            is_valid = self._is_within_tolerance(delta, expected)

            result.add_check(ReconciliationCheck(
                check_name="IS: Gross Profit = Revenue - COGS",
                is_valid=is_valid,
                expected_value=expected,
                actual_value=gross_profit,
                delta=delta,
                delta_percent=float(delta / abs(expected) * 100) if expected != 0 else None,
                severity="warning" if not is_valid else "info",
                message=f"Gross Profit check: Expected {expected}, Actual {gross_profit}, Delta {delta}",
            ))

        # Check: Operating Income = Gross Profit - Operating Expenses
        opex = self._get_value(values, "operating_expenses", self.INCOME_STATEMENT_LABELS)
        operating_income = self._get_value(values, "operating_income", self.INCOME_STATEMENT_LABELS)

        if all(v is not None for v in [gross_profit, opex, operating_income]):
            expected = gross_profit - opex
            delta = abs(expected - operating_income)
            is_valid = self._is_within_tolerance(delta, expected)

            result.add_check(ReconciliationCheck(
                check_name="IS: Operating Income = Gross Profit - OpEx",
                is_valid=is_valid,
                expected_value=expected,
                actual_value=operating_income,
                delta=delta,
                delta_percent=float(delta / abs(expected) * 100) if expected != 0 else None,
                severity="warning" if not is_valid else "info",
                message=f"Operating Income check: Expected {expected}, Actual {operating_income}",
            ))

    def _validate_balance_sheet(
        self,
        values: Dict[str, Decimal],
        result: ReconciliationResult,
    ) -> None:
        """Validate balance sheet reconciliations."""
        # Check: Assets = Liabilities + Equity
        total_assets = self._get_value(values, "total_assets", self.BALANCE_SHEET_LABELS)
        total_liabilities = self._get_value(values, "total_liabilities", self.BALANCE_SHEET_LABELS)
        total_equity = self._get_value(values, "total_equity", self.BALANCE_SHEET_LABELS)

        if all(v is not None for v in [total_assets, total_liabilities, total_equity]):
            expected = total_liabilities + total_equity
            delta = abs(total_assets - expected)
            is_valid = self._is_within_tolerance(delta, total_assets)

            result.add_check(ReconciliationCheck(
                check_name="BS: Assets = Liabilities + Equity",
                is_valid=is_valid,
                expected_value=expected,
                actual_value=total_assets,
                delta=delta,
                delta_percent=float(delta / abs(total_assets) * 100) if total_assets != 0 else None,
                severity="error" if not is_valid else "info",
                message=f"Balance Sheet check: Assets={total_assets}, L+E={expected}, Delta={delta}",
            ))

    def _validate_cash_flow(
        self,
        values: Dict[str, Decimal],
        result: ReconciliationResult,
    ) -> None:
        """Validate cash flow statement reconciliations."""
        # Check: Net Change = CFO + CFI + CFF
        cfo = self._get_value(values, "cfo", self.CASH_FLOW_LABELS)
        cfi = self._get_value(values, "cfi", self.CASH_FLOW_LABELS)
        cff = self._get_value(values, "cff", self.CASH_FLOW_LABELS)
        net_change = self._get_value(values, "net_change", self.CASH_FLOW_LABELS)

        if all(v is not None for v in [cfo, cfi, cff, net_change]):
            expected = cfo + cfi + cff
            delta = abs(expected - net_change)
            is_valid = self._is_within_tolerance(delta, expected)

            result.add_check(ReconciliationCheck(
                check_name="CF: Net Change = CFO + CFI + CFF",
                is_valid=is_valid,
                expected_value=expected,
                actual_value=net_change,
                delta=delta,
                delta_percent=float(delta / abs(expected) * 100) if expected != 0 else None,
                severity="warning" if not is_valid else "info",
                message=f"Cash Flow check: Expected {expected}, Actual {net_change}",
            ))

        # Check: End Cash = Begin Cash + Net Change
        begin_cash = self._get_value(values, "begin_cash", self.CASH_FLOW_LABELS)
        end_cash = self._get_value(values, "end_cash", self.CASH_FLOW_LABELS)

        if all(v is not None for v in [begin_cash, net_change, end_cash]):
            expected = begin_cash + net_change
            delta = abs(expected - end_cash)
            is_valid = self._is_within_tolerance(delta, expected)

            result.add_check(ReconciliationCheck(
                check_name="CF: End Cash = Begin Cash + Net Change",
                is_valid=is_valid,
                expected_value=expected,
                actual_value=end_cash,
                delta=delta,
                delta_percent=float(delta / abs(expected) * 100) if expected != 0 else None,
                severity="warning" if not is_valid else "info",
                message=f"End Cash check: Expected {expected}, Actual {end_cash}",
            ))

    def _is_within_tolerance(self, delta: Decimal, reference: Decimal) -> bool:
        """Check if delta is within tolerance."""
        # Check absolute tolerance
        if delta <= self.MATERIALITY_THRESHOLD_ABS:
            return True

        # Check percentage tolerance
        if reference != 0:
            pct = abs(delta / reference)
            if pct <= Decimal(str(self.MATERIALITY_THRESHOLD_PERCENT)):
                return True

        return False


def get_validation_layer() -> ValidationLayer:
    """Get ValidationLayer instance."""
    return ValidationLayer()
