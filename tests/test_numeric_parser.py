"""
Unit tests for NumericParser service.
"""
from decimal import Decimal

import pytest

from backend.services.numeric_parser import NumericParser, ParsedNumber


class TestNumericParser:
    """Tests for NumericParser class."""

    @pytest.fixture
    def parser(self) -> NumericParser:
        """Create parser instance."""
        return NumericParser()

    # Standard number tests
    def test_parse_integer(self, parser: NumericParser):
        """Test parsing simple integer."""
        result = parser.parse("1234")
        assert result.value == Decimal("1234")
        assert result.confidence == 1.0

    def test_parse_decimal(self, parser: NumericParser):
        """Test parsing decimal number."""
        result = parser.parse("1234.56")
        assert result.value == Decimal("1234.56")
        assert result.confidence == 1.0

    def test_parse_with_commas(self, parser: NumericParser):
        """Test parsing number with thousand separators."""
        result = parser.parse("1,234,567")
        assert result.value == Decimal("1234567")
        assert result.confidence >= 0.9

    def test_parse_with_commas_and_decimal(self, parser: NumericParser):
        """Test parsing US format with commas and decimal."""
        result = parser.parse("1,234,567.89")
        assert result.value == Decimal("1234567.89")
        assert result.confidence >= 0.9

    # Currency tests
    def test_parse_usd(self, parser: NumericParser):
        """Test parsing USD currency."""
        result = parser.parse("$1,234.56")
        assert result.value == Decimal("1234.56")
        assert result.currency == "$"

    def test_parse_euro(self, parser: NumericParser):
        """Test parsing Euro currency."""
        result = parser.parse("€1234")
        assert result.value == Decimal("1234")
        assert result.currency == "€"

    def test_parse_gbp(self, parser: NumericParser):
        """Test parsing GBP currency."""
        result = parser.parse("£999.99")
        assert result.value == Decimal("999.99")
        assert result.currency == "£"

    # Negative number tests
    def test_parse_negative_parentheses(self, parser: NumericParser):
        """Test parsing negative with parentheses (accounting format)."""
        result = parser.parse("(1234)")
        assert result.value == Decimal("-1234")
        assert result.is_negative is True

    def test_parse_negative_parentheses_with_currency(self, parser: NumericParser):
        """Test parsing negative currency with parentheses."""
        result = parser.parse("($1,234.56)")
        assert result.value == Decimal("-1234.56")
        assert result.is_negative is True
        assert result.currency == "$"

    def test_parse_negative_minus_sign(self, parser: NumericParser):
        """Test parsing negative with minus sign."""
        result = parser.parse("-1234.56")
        assert result.value == Decimal("-1234.56")
        assert result.is_negative is True

    # Unit multiplier tests
    def test_parse_thousands(self, parser: NumericParser):
        """Test parsing with K suffix."""
        result = parser.parse("123K")
        assert result.value == Decimal("123000")
        assert result.unit_multiplier == 1000

    def test_parse_millions(self, parser: NumericParser):
        """Test parsing with M suffix."""
        result = parser.parse("1.5M")
        assert result.value == Decimal("1500000")
        assert result.unit_multiplier == 1000000

    def test_parse_billions(self, parser: NumericParser):
        """Test parsing with B suffix."""
        result = parser.parse("2.5B")
        assert result.value == Decimal("2500000000")
        assert result.unit_multiplier == 1000000000

    def test_parse_mm_suffix(self, parser: NumericParser):
        """Test parsing with MM suffix (millions)."""
        result = parser.parse("100MM")
        assert result.value == Decimal("100000000")
        assert result.unit_multiplier == 1000000

    # Percentage tests
    def test_parse_percentage(self, parser: NumericParser):
        """Test parsing percentage."""
        result = parser.parse("12.5%")
        assert result.value == Decimal("12.5")
        assert result.is_percentage is True

    # Complex format tests
    def test_parse_complex_currency_negative_unit(self, parser: NumericParser):
        """Test parsing complex format with currency, negative, and units."""
        result = parser.parse("($1.5M)")
        assert result.value == Decimal("-1500000")
        assert result.is_negative is True
        assert result.currency == "$"

    # Edge cases
    def test_parse_empty_string(self, parser: NumericParser):
        """Test parsing empty string."""
        result = parser.parse("")
        assert result.value is None
        assert result.confidence == 0.0

    def test_parse_whitespace(self, parser: NumericParser):
        """Test parsing whitespace only."""
        result = parser.parse("   ")
        assert result.value is None
        assert result.confidence == 0.0

    def test_parse_with_leading_trailing_whitespace(self, parser: NumericParser):
        """Test parsing with whitespace."""
        result = parser.parse("  $1,234.56  ")
        assert result.value == Decimal("1234.56")

    def test_parse_plus_sign(self, parser: NumericParser):
        """Test parsing with explicit plus sign."""
        result = parser.parse("+1234")
        assert result.value == Decimal("1234")
        assert result.is_negative is False

    # European format tests
    def test_parse_european_decimal(self, parser: NumericParser):
        """Test parsing European decimal format (comma as decimal)."""
        result = parser.parse("1234,56")
        # Could be interpreted as either format
        assert result.value is not None

    def test_parse_european_full(self, parser: NumericParser):
        """Test parsing European format with period thousand separator."""
        result = parser.parse("1.234,56")
        assert result.value == Decimal("1234.56")

    # Batch parsing
    def test_parse_batch(self, parser: NumericParser):
        """Test batch parsing."""
        values = ["$100", "$200", "$300"]
        results = parser.parse_batch(values)
        assert len(results) == 3
        assert results[0].value == Decimal("100")
        assert results[1].value == Decimal("200")
        assert results[2].value == Decimal("300")


class TestParsedNumber:
    """Tests for ParsedNumber dataclass."""

    def test_parsed_number_defaults(self):
        """Test ParsedNumber default values."""
        result = ParsedNumber(value=Decimal("100"), raw_value="100", confidence=1.0)
        assert result.is_negative is False
        assert result.unit_multiplier == 1
        assert result.currency is None
        assert result.is_percentage is False
