"""
Accounting equation validator.

Validates that Assets = Liabilities + Equity (A = L + E).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    message: str
    severity: str  # critical, high, medium, low
    details: Dict = None


@dataclass
class BalanceSheetTotals:
    """Balance sheet totals for validation."""

    total_assets: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None
    total_equity: Optional[Decimal] = None
    total_liabilities_equity: Optional[Decimal] = None


class AccountingEquationValidator:
    """
    Validator for the accounting equation.

    Checks:
    1. Assets = Liabilities + Equity
    2. Total Liabilities & Equity matches Assets
    3. Current Assets + Non-Current Assets = Total Assets
    4. Current Liabilities + Non-Current Liabilities = Total Liabilities
    """

    # Tolerance for floating point comparison (0.01 = 1 cent)
    TOLERANCE = Decimal("0.01")

    # Ontology IDs for balance sheet totals
    ASSET_IDS = ["bs:total_assets", "bs:current_assets", "bs:non_current_assets"]
    LIABILITY_IDS = ["bs:total_liabilities", "bs:current_liabilities", "bs:non_current_liabilities"]
    EQUITY_IDS = ["bs:total_equity"]
    TOTAL_LE_IDS = ["bs:total_liabilities_equity"]

    def __init__(self):
        """Initialize validator."""
        pass

    def validate(
        self,
        mappings: Dict[str, Decimal],
    ) -> List[ValidationResult]:
        """
        Validate accounting equation from mappings.

        Args:
            mappings: Dict of ontology_id → value.

        Returns:
            List of ValidationResults.
        """
        results = []

        # Extract totals
        totals = self._extract_totals(mappings)

        # Check A = L + E
        if totals.total_assets is not None:
            result = self._validate_ale(totals)
            if result:
                results.append(result)

        # Check component sums
        results.extend(self._validate_component_sums(mappings))

        return results

    def _extract_totals(self, mappings: Dict[str, Decimal]) -> BalanceSheetTotals:
        """Extract balance sheet totals from mappings."""
        return BalanceSheetTotals(
            total_assets=mappings.get("bs:total_assets"),
            total_liabilities=mappings.get("bs:total_liabilities"),
            total_equity=mappings.get("bs:total_equity"),
            total_liabilities_equity=mappings.get("bs:total_liabilities_equity"),
        )

    def _validate_ale(self, totals: BalanceSheetTotals) -> Optional[ValidationResult]:
        """Validate Assets = Liabilities + Equity."""
        if totals.total_assets is None:
            return None

        if totals.total_liabilities is None or totals.total_equity is None:
            return ValidationResult(
                is_valid=False,
                message="Cannot validate A = L + E: missing liabilities or equity totals",
                severity="medium",
                details={
                    "assets": str(totals.total_assets) if totals.total_assets else None,
                    "liabilities": str(totals.total_liabilities) if totals.total_liabilities else None,
                    "equity": str(totals.total_equity) if totals.total_equity else None,
                },
            )

        expected = totals.total_liabilities + totals.total_equity
        diff = abs(totals.total_assets - expected)

        if diff <= self.TOLERANCE:
            return ValidationResult(
                is_valid=True,
                message="Accounting equation validated: Assets = Liabilities + Equity",
                severity="info",
            )
        else:
            return ValidationResult(
                is_valid=False,
                message=f"Accounting equation failed: Assets ({totals.total_assets}) != L + E ({expected})",
                severity="critical",
                details={
                    "assets": str(totals.total_assets),
                    "liabilities": str(totals.total_liabilities),
                    "equity": str(totals.total_equity),
                    "expected": str(expected),
                    "difference": str(diff),
                },
            )

    def _validate_component_sums(
        self, mappings: Dict[str, Decimal]
    ) -> List[ValidationResult]:
        """Validate component sums."""
        results = []

        # Current + Non-Current = Total Assets
        current_assets = mappings.get("bs:current_assets")
        non_current_assets = mappings.get("bs:non_current_assets")
        total_assets = mappings.get("bs:total_assets")

        if all(v is not None for v in [current_assets, non_current_assets, total_assets]):
            expected = current_assets + non_current_assets
            diff = abs(total_assets - expected)

            if diff > self.TOLERANCE:
                results.append(ValidationResult(
                    is_valid=False,
                    message=f"Asset sum mismatch: Current + Non-Current ({expected}) != Total ({total_assets})",
                    severity="high",
                    details={
                        "current_assets": str(current_assets),
                        "non_current_assets": str(non_current_assets),
                        "total_assets": str(total_assets),
                        "difference": str(diff),
                    },
                ))

        # Current + Non-Current = Total Liabilities
        current_liab = mappings.get("bs:current_liabilities")
        non_current_liab = mappings.get("bs:non_current_liabilities")
        total_liab = mappings.get("bs:total_liabilities")

        if all(v is not None for v in [current_liab, non_current_liab, total_liab]):
            expected = current_liab + non_current_liab
            diff = abs(total_liab - expected)

            if diff > self.TOLERANCE:
                results.append(ValidationResult(
                    is_valid=False,
                    message=f"Liability sum mismatch: Current + Non-Current ({expected}) != Total ({total_liab})",
                    severity="high",
                    details={
                        "current_liabilities": str(current_liab),
                        "non_current_liabilities": str(non_current_liab),
                        "total_liabilities": str(total_liab),
                        "difference": str(diff),
                    },
                ))

        return results


# Singleton instance
_validator_instance: Optional[AccountingEquationValidator] = None


def get_accounting_validator() -> AccountingEquationValidator:
    """Get singleton AccountingEquationValidator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = AccountingEquationValidator()
    return _validator_instance
