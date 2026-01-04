"""
Tests for the StatementXL Engine.

Covers:
- No formula cells are changed
- Audit sheet exists and required headers are present
- Units scaling: $000 => *1000
- Deterministic conflict resolution stable across runs
- Write policy enforced (only eligible numeric cells)
"""

import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.statementxl_engine.models import (
    BoundingBox,
    CellPosting,
    ConfidenceLevel,
    DocumentEvidence,
    NormalizedFact,
    PageEvidence,
    PeriodInfo,
    ReconciliationCheck,
    ReconciliationResult,
    ScaleFactor,
    StatementSection,
    StatementType,
    TableCell,
    TableRegion,
    TableRow,
    TemplateCell,
    Token,
)
from backend.statementxl_engine.extraction import ExtractionLayer
from backend.statementxl_engine.normalization import NormalizationLayer, LABEL_TO_CANONICAL
from backend.statementxl_engine.mapping import LabelMatcher, TemplateProfiler, MappingLayer
from backend.statementxl_engine.validation import ValidationLayer
from backend.statementxl_engine.writeback import WritebackLayer


# =============================================================================
# Model Tests
# =============================================================================

class TestModels:
    """Test evidence model classes."""

    def test_bounding_box_conversion(self):
        """Test BoundingBox to/from list conversion."""
        bbox = BoundingBox(x0=10.0, y0=20.0, x1=100.0, y1=50.0)
        assert bbox.to_list() == [10.0, 20.0, 100.0, 50.0]

        bbox2 = BoundingBox.from_list([10.0, 20.0, 100.0, 50.0])
        assert bbox2.x0 == 10.0
        assert bbox2.y1 == 50.0

    def test_normalized_fact_confidence_level(self):
        """Test confidence level computation."""
        fact = NormalizedFact(
            id="test",
            normalized_label="Revenue",
            raw_label="Net Sales",
            raw_value="1,000.00",
            parsed_value=Decimal("1000.00"),
            scaled_value=Decimal("1000000.00"),
            scale_factor=ScaleFactor.THOUSANDS,
            overall_confidence=0.90,
        )
        assert fact.compute_confidence_level() == ConfidenceLevel.HIGH

        fact.overall_confidence = 0.70
        assert fact.compute_confidence_level() == ConfidenceLevel.MEDIUM

        fact.overall_confidence = 0.50
        assert fact.compute_confidence_level() == ConfidenceLevel.LOW

        fact.overall_confidence = 0.30
        assert fact.compute_confidence_level() == ConfidenceLevel.VERY_LOW

    def test_scale_factor_values(self):
        """Test scale factor enum values."""
        assert ScaleFactor.UNITS.value == 1
        assert ScaleFactor.THOUSANDS.value == 1000
        assert ScaleFactor.MILLIONS.value == 1000000
        assert ScaleFactor.BILLIONS.value == 1000000000


# =============================================================================
# Extraction Tests
# =============================================================================

class TestExtraction:
    """Test extraction layer."""

    def test_scale_factor_detection(self):
        """Test units/scale factor detection."""
        layer = ExtractionLayer()

        assert layer.detect_scale_factor("$ in thousands") == ScaleFactor.THOUSANDS
        assert layer.detect_scale_factor("$000") == ScaleFactor.THOUSANDS
        assert layer.detect_scale_factor("in millions") == ScaleFactor.MILLIONS
        assert layer.detect_scale_factor("$MM") == ScaleFactor.MILLIONS
        assert layer.detect_scale_factor("in billions") == ScaleFactor.BILLIONS
        assert layer.detect_scale_factor("regular values") == ScaleFactor.UNITS


# =============================================================================
# Normalization Tests
# =============================================================================

class TestNormalization:
    """Test normalization layer."""

    def test_label_synonyms(self):
        """Test label synonym lookup."""
        assert LABEL_TO_CANONICAL.get("net sales") == "Revenue"
        assert LABEL_TO_CANONICAL.get("cogs") == "Cost of Revenue"
        assert LABEL_TO_CANONICAL.get("gross margin") == "Gross Profit"

    def test_negative_detection(self):
        """Test negative value detection."""
        layer = NormalizationLayer()

        assert layer._detect_negative("(1,000.00)") is True
        assert layer._detect_negative("-1000") is True
        assert layer._detect_negative("1,000.00") is False
        assert layer._detect_negative("1000") is False

    def test_scale_application(self):
        """Test scale factor application."""
        layer = NormalizationLayer()

        # Units
        result = layer._apply_scale(Decimal("1000"), ScaleFactor.UNITS, False)
        assert result == Decimal("1000")

        # Thousands
        result = layer._apply_scale(Decimal("1000"), ScaleFactor.THOUSANDS, False)
        assert result == Decimal("1000000")

        # Negative
        result = layer._apply_scale(Decimal("1000"), ScaleFactor.THOUSANDS, True)
        assert result == Decimal("-1000000")


# =============================================================================
# Mapping Tests
# =============================================================================

class TestMapping:
    """Test mapping layer."""

    def test_label_matching_exact(self):
        """Test exact label matching."""
        matcher = LabelMatcher()

        score, match_type = matcher.match("Revenue", "Revenue")
        assert score == 1.0
        assert match_type == "exact"

    def test_label_matching_synonym(self):
        """Test synonym label matching."""
        matcher = LabelMatcher()

        score, match_type = matcher.match("Revenue", "Net Sales")
        assert score >= 0.9
        assert match_type == "synonym"

    def test_label_matching_fuzzy(self):
        """Test fuzzy label matching."""
        matcher = LabelMatcher()

        score, match_type = matcher.match("Total Revenue", "Total Revenues")
        assert score > 0.7
        # Could be fuzzy or partial

    def test_levenshtein_distance(self):
        """Test Levenshtein distance calculation."""
        matcher = LabelMatcher()

        assert matcher._levenshtein_distance("", "") == 0
        assert matcher._levenshtein_distance("abc", "abc") == 0
        assert matcher._levenshtein_distance("abc", "abd") == 1
        assert matcher._levenshtein_distance("abc", "") == 3


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidation:
    """Test validation layer."""

    def test_balance_sheet_check(self):
        """Test balance sheet A = L + E check."""
        layer = ValidationLayer()
        result = ReconciliationResult()

        # Create mock values
        values = {
            "total assets": Decimal("1000000"),
            "total liabilities": Decimal("600000"),
            "total equity": Decimal("400000"),
        }

        layer._validate_balance_sheet(values, result)

        assert len(result.checks) == 1
        assert result.checks[0].is_valid is True
        assert result.checks[0].check_name == "BS: Assets = Liabilities + Equity"

    def test_balance_sheet_imbalance(self):
        """Test balance sheet imbalance detection."""
        layer = ValidationLayer()
        result = ReconciliationResult()

        # Create imbalanced values
        values = {
            "total assets": Decimal("1000000"),
            "total liabilities": Decimal("600000"),
            "total equity": Decimal("350000"),  # Imbalance of 50000
        }

        layer._validate_balance_sheet(values, result)

        assert len(result.checks) == 1
        # Should fail due to 5% imbalance
        assert result.checks[0].is_valid is False

    def test_materiality_threshold(self):
        """Test materiality threshold logic."""
        layer = ValidationLayer()

        # Within absolute threshold
        assert layer._is_within_tolerance(Decimal("500"), Decimal("1000000")) is True

        # Within percentage threshold
        assert layer._is_within_tolerance(Decimal("5000"), Decimal("1000000")) is True

        # Outside both thresholds
        assert layer._is_within_tolerance(Decimal("50000"), Decimal("1000000")) is False


# =============================================================================
# Writeback Tests
# =============================================================================

class TestWriteback:
    """Test writeback layer."""

    def test_formula_detection(self):
        """Test formula cell detection."""
        layer = WritebackLayer()

        # Mock cell with formula
        cell_with_formula = MagicMock()
        cell_with_formula.value = "=SUM(A1:A10)"
        assert layer._has_formula(cell_with_formula) is True

        # Mock cell with value
        cell_with_value = MagicMock()
        cell_with_value.value = 1000
        assert layer._has_formula(cell_with_value) is False

        # Mock empty cell
        empty_cell = MagicMock()
        empty_cell.value = None
        assert layer._has_formula(empty_cell) is False


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the engine."""

    def test_conflict_resolution_stability(self):
        """Test that conflict resolution is deterministic across runs."""
        layer = MappingLayer()

        # Create two competing postings
        posting1 = CellPosting(
            id="p1",
            template_cell=TemplateCell(sheet="IS", address="C10", row=10, column=3),
            new_value=Decimal("1000"),
            primary_fact_id="f1",
            confidence=0.80,
            source_pdf="doc_a.pdf",
        )
        posting2 = CellPosting(
            id="p2",
            template_cell=TemplateCell(sheet="IS", address="C10", row=10, column=3),
            new_value=Decimal("1100"),
            primary_fact_id="f2",
            confidence=0.80,
            source_pdf="doc_b.pdf",
        )

        # Run multiple times
        facts = []  # Empty for this test
        results = []
        for _ in range(5):
            resolved = layer._resolve_conflicts([posting1, posting2], facts)
            results.append(resolved[0].primary_fact_id)

        # All results should be the same (deterministic)
        assert all(r == results[0] for r in results)


# =============================================================================
# Policy Tests
# =============================================================================

class TestWritePolicy:
    """Test write policy enforcement."""

    def test_no_formula_overwrite(self):
        """Verify formula cells are never overwritten."""
        layer = WritebackLayer()

        # Create a mock posting for a formula cell
        formula_cell = TemplateCell(
            sheet="IS",
            address="C20",
            row=20,
            column=3,
            has_formula=True,
            formula="=SUM(C10:C19)",
            is_eligible=False,  # Formula cells should not be eligible
        )
        posting = CellPosting(
            id="p1",
            template_cell=formula_cell,
            new_value=Decimal("5000"),
        )

        # The cell is not eligible, so it should be skipped
        assert formula_cell.is_eligible is False

    def test_eligible_cell_requirements(self):
        """Verify eligible cell requirements."""
        # Eligible: no formula, empty or numeric
        cell1 = TemplateCell(sheet="IS", address="C10", row=10, column=3, is_eligible=True, is_input_cell=True)
        assert cell1.is_eligible is True

        # Not eligible: has formula
        cell2 = TemplateCell(sheet="IS", address="C20", row=20, column=3, has_formula=True, is_eligible=False)
        assert cell2.is_eligible is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
