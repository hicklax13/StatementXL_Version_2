"""
Numeric parser service for financial value extraction.

Handles parsing of numeric values in various formats:
- Currency: $1,234.56, €1.234,56
- Negative: (123), -123
- Units: 123K, 1.2M, 5B
- Percentages: 12.5%
"""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ParsedNumber:
    """Result of parsing a numeric string."""

    value: Optional[Decimal]
    raw_value: str
    confidence: float
    is_negative: bool = False
    unit_multiplier: int = 1
    currency: Optional[str] = None
    is_percentage: bool = False


class NumericParser:
    """
    Parser for financial numeric values.

    Handles various number formats commonly found in financial statements:
    - Standard numbers: 1234, 1,234.56
    - Currency symbols: $, €, £, ¥
    - Negative notation: parentheses (123) or minus sign -123
    - Unit suffixes: K (thousands), M (millions), B (billions), T (trillions)
    - Percentages: 12.5%
    """

    # Currency symbols
    CURRENCY_SYMBOLS = {"$", "€", "£", "¥", "₹", "CHF", "CAD", "AUD", "USD", "EUR", "GBP"}

    # Unit multipliers
    UNIT_MULTIPLIERS = {
        "K": 1_000,
        "k": 1_000,
        "M": 1_000_000,
        "m": 1_000_000,
        "MM": 1_000_000,
        "B": 1_000_000_000,
        "b": 1_000_000_000,
        "BN": 1_000_000_000,
        "T": 1_000_000_000_000,
        "t": 1_000_000_000_000,
        "thousand": 1_000,
        "thousands": 1_000,
        "million": 1_000_000,
        "millions": 1_000_000,
        "billion": 1_000_000_000,
        "billions": 1_000_000_000,
        "trillion": 1_000_000_000_000,
        "trillions": 1_000_000_000_000,
    }

    # Regex patterns
    PARENTHESES_PATTERN = re.compile(r"^\s*\(([^)]+)\)\s*$")
    CURRENCY_PATTERN = re.compile(r"^[\$€£¥₹]|USD|EUR|GBP|CAD|AUD|CHF")
    UNIT_PATTERN = re.compile(
        r"([KkMmBbTt]|MM|BN|thousand|thousands|million|millions|billion|billions|trillion|trillions)\s*$",
        re.IGNORECASE,
    )
    PERCENTAGE_PATTERN = re.compile(r"%\s*$")
    NUMBER_PATTERN = re.compile(r"^[+-]?\d{1,3}(?:[,.\s]\d{3})*(?:[.,]\d+)?$|^[+-]?\d+(?:[.,]\d+)?$")

    def parse(self, value_str: str) -> ParsedNumber:
        """
        Parse a string value into a numeric result.

        Args:
            value_str: The string to parse.

        Returns:
            ParsedNumber with parsed value and metadata.
        """
        if not value_str or not value_str.strip():
            return ParsedNumber(
                value=None,
                raw_value=value_str or "",
                confidence=0.0,
            )

        original = value_str
        value_str = value_str.strip()

        # Check for negative (parentheses notation)
        is_negative = False
        paren_match = self.PARENTHESES_PATTERN.match(value_str)
        if paren_match:
            value_str = paren_match.group(1).strip()
            is_negative = True

        # Check for minus sign
        if value_str.startswith("-"):
            is_negative = True
            value_str = value_str[1:].strip()
        elif value_str.startswith("+"):
            value_str = value_str[1:].strip()

        # Extract currency symbol
        currency = None
        for symbol in self.CURRENCY_SYMBOLS:
            if value_str.startswith(symbol):
                currency = symbol
                value_str = value_str[len(symbol):].strip()
                break

        # Check for percentage
        is_percentage = False
        if self.PERCENTAGE_PATTERN.search(value_str):
            is_percentage = True
            value_str = self.PERCENTAGE_PATTERN.sub("", value_str).strip()

        # Extract unit multiplier
        unit_multiplier = 1
        unit_match = self.UNIT_PATTERN.search(value_str)
        if unit_match:
            unit = unit_match.group(1)
            unit_multiplier = self.UNIT_MULTIPLIERS.get(unit, 1)
            value_str = self.UNIT_PATTERN.sub("", value_str).strip()

        # Parse the numeric value
        parsed_value, confidence = self._parse_number(value_str)

        if parsed_value is not None:
            # Apply multiplier
            parsed_value = parsed_value * unit_multiplier

            # Apply negative
            if is_negative:
                parsed_value = -parsed_value

            # Convert percentage to decimal if needed
            # (keeping as-is for display purposes, user can convert if needed)

        return ParsedNumber(
            value=parsed_value,
            raw_value=original,
            confidence=confidence,
            is_negative=is_negative,
            unit_multiplier=unit_multiplier,
            currency=currency,
            is_percentage=is_percentage,
        )

    def _parse_number(self, value_str: str) -> Tuple[Optional[Decimal], float]:
        """
        Parse a cleaned numeric string into a Decimal.

        Args:
            value_str: Cleaned string containing only the number.

        Returns:
            Tuple of (parsed Decimal or None, confidence score).
        """
        if not value_str:
            return None, 0.0

        # Remove spaces
        value_str = value_str.replace(" ", "")

        # Handle different decimal/thousand separators
        # Count commas and periods to determine format
        comma_count = value_str.count(",")
        period_count = value_str.count(".")

        try:
            if comma_count == 0 and period_count == 0:
                # Pure integer: 1234
                return Decimal(value_str), 1.0

            elif comma_count == 0 and period_count == 1:
                # US format with decimal: 1234.56
                return Decimal(value_str), 1.0

            elif comma_count >= 1 and period_count == 0:
                # Could be US thousand separator: 1,234,567
                # Or European decimal: 1,5
                if self._is_thousand_separator(value_str, ","):
                    cleaned = value_str.replace(",", "")
                    return Decimal(cleaned), 0.95
                else:
                    # European decimal
                    cleaned = value_str.replace(",", ".")
                    return Decimal(cleaned), 0.85

            elif comma_count >= 1 and period_count >= 1:
                # Mixed format - determine by position
                # US format: 1,234.56 (comma before period)
                # EU format: 1.234,56 (period before comma)
                last_comma_pos = value_str.rfind(",")
                last_period_pos = value_str.rfind(".")

                if last_period_pos > last_comma_pos:
                    # US format: period is decimal, comma is thousands
                    cleaned = value_str.replace(",", "")
                    return Decimal(cleaned), 0.95
                else:
                    # EU format: comma is decimal, period is thousands
                    cleaned = value_str.replace(".", "").replace(",", ".")
                    return Decimal(cleaned), 0.9

            else:
                # Multiple periods - unusual, try to parse anyway
                # Assume last separator is decimal
                last_period = value_str.rfind(".")
                last_comma = value_str.rfind(",")

                if last_period > last_comma:
                    cleaned = value_str.replace(",", "")
                else:
                    cleaned = value_str.replace(".", "").replace(",", ".")

                return Decimal(cleaned), 0.7

        except (InvalidOperation, ValueError) as e:
            logger.warning("Failed to parse number", value=value_str, error=str(e))
            return None, 0.0

    def _is_thousand_separator(self, value_str: str, separator: str) -> bool:
        """
        Check if a separator is being used as thousand separator.

        Args:
            value_str: The string to check.
            separator: The separator character.

        Returns:
            True if separator appears to be thousand separator.
        """
        parts = value_str.split(separator)

        # For thousand separator, all parts after first should be exactly 3 digits
        if len(parts) < 2:
            return False

        for part in parts[1:]:
            if len(part) != 3 or not part.isdigit():
                return False

        return True

    def parse_batch(self, values: list[str]) -> list[ParsedNumber]:
        """
        Parse multiple values.

        Args:
            values: List of strings to parse.

        Returns:
            List of ParsedNumber results.
        """
        return [self.parse(v) for v in values]


# Singleton instance
_parser_instance: Optional[NumericParser] = None


def get_numeric_parser() -> NumericParser:
    """Get singleton NumericParser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = NumericParser()
    return _parser_instance
