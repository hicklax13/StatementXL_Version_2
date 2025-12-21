"""
Formula validator.

Validates that formula relationships are maintained after mapping.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class FormulaValidationResult:
    """Result of formula validation."""

    is_valid: bool
    formula: str
    expected_value: Optional[Decimal]
    actual_value: Optional[Decimal]
    difference: Optional[Decimal]
    cell_address: str
    message: str


class FormulaValidator:
    """
    Validator for formula integrity.

    Checks that calculated cells match their expected values
    based on input cell mappings.
    """

    # Tolerance for numeric comparison
    TOLERANCE = Decimal("0.01")

    def __init__(self):
        """Initialize validator."""
        pass

    def validate_formulas(
        self,
        formula_cells: List[Dict[str, Any]],
        mapped_values: Dict[str, Decimal],
    ) -> List[FormulaValidationResult]:
        """
        Validate formulas against mapped values.

        Args:
            formula_cells: List of cells with formulas.
            mapped_values: Dict of cell address → mapped value.

        Returns:
            List of FormulaValidationResults.
        """
        results = []

        for cell in formula_cells:
            address = cell.get("address")
            formula = cell.get("formula")
            expected = cell.get("expected_value")

            if not formula or not address:
                continue

            # Get the mapped value for this cell
            actual = mapped_values.get(address)

            if actual is None:
                # Cell not mapped, skip
                continue

            if expected is None:
                # No expected value to compare
                results.append(FormulaValidationResult(
                    is_valid=True,
                    formula=formula,
                    expected_value=None,
                    actual_value=actual,
                    difference=None,
                    cell_address=address,
                    message="No expected value for comparison",
                ))
                continue

            # Compare values
            try:
                expected_dec = Decimal(str(expected))
                actual_dec = Decimal(str(actual))
                diff = abs(expected_dec - actual_dec)

                is_valid = diff <= self.TOLERANCE

                results.append(FormulaValidationResult(
                    is_valid=is_valid,
                    formula=formula,
                    expected_value=expected_dec,
                    actual_value=actual_dec,
                    difference=diff,
                    cell_address=address,
                    message="" if is_valid else f"Value mismatch: expected {expected_dec}, got {actual_dec}",
                ))

            except (ValueError, TypeError) as e:
                results.append(FormulaValidationResult(
                    is_valid=False,
                    formula=formula,
                    expected_value=None,
                    actual_value=None,
                    difference=None,
                    cell_address=address,
                    message=f"Comparison error: {str(e)}",
                ))

        return results

    def check_sum_relationships(
        self,
        mappings: Dict[str, Any],
    ) -> List[FormulaValidationResult]:
        """
        Check common sum relationships.

        Args:
            mappings: Dict of ontology_id → value.

        Returns:
            List of validation results.
        """
        results = []

        # Income Statement: Gross Profit = Revenue - COGS
        revenue = self._get_decimal(mappings, "is:revenue")
        cogs = self._get_decimal(mappings, "is:cogs")
        gross_profit = self._get_decimal(mappings, "is:gross_profit")

        if all(v is not None for v in [revenue, cogs, gross_profit]):
            expected = revenue - cogs
            diff = abs(gross_profit - expected)

            results.append(FormulaValidationResult(
                is_valid=diff <= self.TOLERANCE,
                formula="Gross Profit = Revenue - COGS",
                expected_value=expected,
                actual_value=gross_profit,
                difference=diff,
                cell_address="is:gross_profit",
                message="" if diff <= self.TOLERANCE else f"Expected {expected}, got {gross_profit}",
            ))

        # Net Income = EBT - Taxes
        ebt = self._get_decimal(mappings, "is:ebt")
        taxes = self._get_decimal(mappings, "is:income_tax")
        net_income = self._get_decimal(mappings, "is:net_income")

        if all(v is not None for v in [ebt, taxes, net_income]):
            expected = ebt - taxes
            diff = abs(net_income - expected)

            results.append(FormulaValidationResult(
                is_valid=diff <= self.TOLERANCE,
                formula="Net Income = EBT - Taxes",
                expected_value=expected,
                actual_value=net_income,
                difference=diff,
                cell_address="is:net_income",
                message="" if diff <= self.TOLERANCE else f"Expected {expected}, got {net_income}",
            ))

        # Cash Flow: Net Change = CFO + CFI + CFF
        cfo = self._get_decimal(mappings, "cf:cfo")
        cfi = self._get_decimal(mappings, "cf:cfi")
        cff = self._get_decimal(mappings, "cf:cff")
        net_change = self._get_decimal(mappings, "cf:net_change_cash")

        if all(v is not None for v in [cfo, cfi, cff, net_change]):
            expected = cfo + cfi + cff
            diff = abs(net_change - expected)

            results.append(FormulaValidationResult(
                is_valid=diff <= self.TOLERANCE,
                formula="Net Change in Cash = CFO + CFI + CFF",
                expected_value=expected,
                actual_value=net_change,
                difference=diff,
                cell_address="cf:net_change_cash",
                message="" if diff <= self.TOLERANCE else f"Expected {expected}, got {net_change}",
            ))

        return results

    def _get_decimal(
        self, mappings: Dict[str, Any], key: str
    ) -> Optional[Decimal]:
        """Get value as Decimal."""
        value = mappings.get(key)
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None


# Singleton instance
_validator_instance: Optional[FormulaValidator] = None


def get_formula_validator() -> FormulaValidator:
    """Get singleton FormulaValidator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = FormulaValidator()
    return _validator_instance
