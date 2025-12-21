"""
Unit tests for classifiers.
"""
import pytest

from backend.services.ontology_service import get_ontology_service
from backend.services.classifiers.rule_based import (
    RuleBasedClassifier,
    get_rule_based_classifier,
)
from backend.services.classifiers.hybrid import (
    HybridClassifier,
    get_hybrid_classifier,
)


class TestRuleBasedClassifier:
    """Tests for RuleBasedClassifier."""

    @pytest.fixture
    def classifier(self) -> RuleBasedClassifier:
        """Get classifier instance."""
        return get_rule_based_classifier()

    def test_exact_label_match(self, classifier: RuleBasedClassifier):
        """Test exact label matching."""
        result = classifier.classify("Revenue")
        assert result.item is not None
        assert result.item.id == "is:revenue"
        assert result.confidence == 1.0
        assert result.match_type == "exact_label"

    def test_exact_alias_match(self, classifier: RuleBasedClassifier):
        """Test exact alias matching."""
        result = classifier.classify("Sales")
        assert result.item is not None
        assert result.item.id == "is:revenue"
        assert result.confidence == 0.95
        assert result.match_type == "exact_alias"

    def test_case_insensitive(self, classifier: RuleBasedClassifier):
        """Test case insensitive matching."""
        result1 = classifier.classify("revenue")
        result2 = classifier.classify("REVENUE")
        result3 = classifier.classify("ReVeNuE")

        assert result1.item.id == result2.item.id == result3.item.id == "is:revenue"

    def test_abbreviation_expansion(self, classifier: RuleBasedClassifier):
        """Test abbreviation expansion."""
        result = classifier.classify("COGS")
        assert result.item is not None
        assert result.confidence >= 0.9

    def test_sg_and_a(self, classifier: RuleBasedClassifier):
        """Test SG&A matching."""
        result = classifier.classify("SG&A")
        assert result.item is not None
        assert result.confidence >= 0.9

    def test_balance_sheet_items(self, classifier: RuleBasedClassifier):
        """Test balance sheet item classification."""
        result = classifier.classify("Accounts Receivable")
        assert result.item is not None
        assert "bs:" in result.item.id or "receivable" in result.item.label.lower()

    def test_partial_match(self, classifier: RuleBasedClassifier):
        """Test partial matching."""
        result = classifier.classify("Total Net Revenue")
        assert result.item is not None
        # Should find something related to revenue
        assert result.confidence > 0.0

    def test_no_match(self, classifier: RuleBasedClassifier):
        """Test handling of unrecognized text."""
        result = classifier.classify("XYZ Random Text 123")
        # Should have low confidence or no match
        assert result.confidence < 0.9

    def test_empty_string(self, classifier: RuleBasedClassifier):
        """Test handling of empty string."""
        result = classifier.classify("")
        assert result.item is None
        assert result.confidence == 0.0

    def test_whitespace_handling(self, classifier: RuleBasedClassifier):
        """Test whitespace is trimmed."""
        result = classifier.classify("  Revenue  ")
        assert result.item is not None
        assert result.item.id == "is:revenue"

    def test_batch_classify(self, classifier: RuleBasedClassifier):
        """Test batch classification."""
        texts = ["Revenue", "COGS", "Operating Income"]
        results = classifier.classify_batch(texts)
        assert len(results) == 3
        assert all(r.item is not None for r in results)


class TestHybridClassifier:
    """Tests for HybridClassifier."""

    @pytest.fixture
    def classifier(self) -> HybridClassifier:
        """Get classifier instance."""
        return get_hybrid_classifier()

    def test_rule_based_first(self, classifier: HybridClassifier):
        """Test that rule-based matches are used first."""
        classifier.reset_stats()

        result = classifier.classify("Revenue")
        assert result.item is not None
        assert result.confidence >= 0.9
        assert "rule" in result.match_type.lower()

        stats = classifier.get_stats()
        assert stats.rule_based >= 1

    def test_cascade_behavior(self, classifier: HybridClassifier):
        """Test cascade from rule-based to embedding."""
        classifier.reset_stats()

        # This should go through rule-based
        result1 = classifier.classify("Revenue")
        assert "rule" in result1.match_type.lower()

        # This might need embedding (if not exact match)
        result2 = classifier.classify("Net Sales Revenue from Products")
        assert result2.confidence > 0

    def test_stats_tracking(self, classifier: HybridClassifier):
        """Test classification statistics are tracked."""
        classifier.reset_stats()

        classifier.classify("Revenue")
        classifier.classify("COGS")
        classifier.classify("Operating Income")

        stats = classifier.get_stats()
        assert stats.total == 3

    def test_batch_classify(self, classifier: HybridClassifier):
        """Test batch classification."""
        texts = ["Revenue", "Cost of Goods Sold", "Net Income"]
        results = classifier.classify_batch(texts)
        assert len(results) == 3


class TestClassificationResults:
    """Tests for classification result structure."""

    @pytest.fixture
    def classifier(self) -> RuleBasedClassifier:
        return get_rule_based_classifier()

    def test_result_has_required_fields(self, classifier: RuleBasedClassifier):
        """Test classification result has all required fields."""
        result = classifier.classify("Revenue")

        assert hasattr(result, "item")
        assert hasattr(result, "confidence")
        assert hasattr(result, "match_type")
        assert hasattr(result, "candidates")

    def test_candidates_list(self, classifier: RuleBasedClassifier):
        """Test candidates are provided for partial matches."""
        result = classifier.classify("Total Revenue from Operations")

        # Should have candidates
        assert isinstance(result.candidates, list)
