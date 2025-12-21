"""
Rule-based classifier for financial line items.

Uses exact matching, alias matching, and fuzzy matching against the ontology.
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import structlog

from backend.services.ontology_service import (
    ClassificationResult,
    OntologyItem,
    OntologyService,
    get_ontology_service,
)

logger = structlog.get_logger(__name__)


@dataclass
class RuleMatch:
    """Result of a rule-based match."""

    item: OntologyItem
    confidence: float
    match_type: str


class RuleBasedClassifier:
    """
    Rule-based classifier using exact and fuzzy matching.

    Classification cascade:
    1. Exact label match → confidence 1.0
    2. Exact alias match → confidence 0.95
    3. Normalized match (after cleaning) → confidence 0.9
    4. Partial match (substring) → confidence 0.7-0.85
    """

    # Common words to remove for normalization
    STOPWORDS = {
        "total", "net", "gross", "and", "the", "of", "from", "for",
        "in", "on", "to", "a", "an", "&", "-", "/", "(", ")", ","
    }

    # Common abbreviation expansions
    ABBREVIATIONS = {
        "a/r": "accounts receivable",
        "ar": "accounts receivable",
        "a/p": "accounts payable",
        "ap": "accounts payable",
        "pp&e": "property plant equipment",
        "ppe": "property plant equipment",
        "d&a": "depreciation amortization",
        "da": "depreciation amortization",
        "sg&a": "selling general administrative",
        "sga": "selling general administrative",
        "r&d": "research development",
        "rd": "research development",
        "cogs": "cost of goods sold",
        "cos": "cost of sales",
        "ebit": "operating income",
        "ebitda": "earnings before interest taxes depreciation amortization",
        "eps": "earnings per share",
        "fcf": "free cash flow",
        "cfo": "cash flow operations",
        "cfi": "cash flow investing",
        "cff": "cash flow financing",
        "roe": "return on equity",
        "roa": "return on assets",
        "roic": "return on invested capital",
    }

    def __init__(self, ontology_service: Optional[OntologyService] = None):
        """
        Initialize rule-based classifier.

        Args:
            ontology_service: Ontology service instance.
        """
        self._ontology = ontology_service or get_ontology_service()
        self._build_normalized_index()

    def _build_normalized_index(self) -> None:
        """Build index of normalized item names for fuzzy matching."""
        self._normalized_index: dict[str, OntologyItem] = {}

        for item in self._ontology.get_all_items():
            for name in item.all_names:
                normalized = self._normalize(name)
                if normalized:
                    self._normalized_index[normalized] = item

    def _normalize(self, text: str) -> str:
        """
        Normalize text for fuzzy matching.

        Args:
            text: Text to normalize.

        Returns:
            Normalized text.
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower().strip()

        # Expand abbreviations
        if text in self.ABBREVIATIONS:
            text = self.ABBREVIATIONS[text]

        # Remove special characters
        text = re.sub(r"[^\w\s]", " ", text)

        # Remove stopwords
        words = text.split()
        words = [w for w in words if w not in self.STOPWORDS]

        # Sort words for order-independent matching
        return " ".join(sorted(words))

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a line item text.

        Args:
            text: Line item text to classify.

        Returns:
            ClassificationResult with best match.
        """
        if not text or not text.strip():
            return ClassificationResult(
                item=None,
                confidence=0.0,
                match_type="none",
            )

        text = text.strip()
        text_lower = text.lower()

        # 1. Exact label match
        item = self._ontology.get_by_label(text)
        if item:
            return ClassificationResult(
                item=item,
                confidence=1.0,
                match_type="exact_label",
            )

        # 2. Exact alias match
        item = self._ontology.get_by_alias(text)
        if item:
            return ClassificationResult(
                item=item,
                confidence=0.95,
                match_type="exact_alias",
            )

        # 3. Abbreviation expansion match
        if text_lower in self.ABBREVIATIONS:
            expanded = self.ABBREVIATIONS[text_lower]
            item = self._ontology.get_by_name(expanded)
            if item:
                return ClassificationResult(
                    item=item,
                    confidence=0.92,
                    match_type="abbreviation",
                )

        # 4. Normalized match
        normalized = self._normalize(text)
        if normalized in self._normalized_index:
            return ClassificationResult(
                item=self._normalized_index[normalized],
                confidence=0.88,
                match_type="normalized",
            )

        # 5. Partial match (substring)
        partial_matches = self._find_partial_matches(text_lower)
        if partial_matches:
            best = partial_matches[0]
            return ClassificationResult(
                item=best[0],
                confidence=best[1],
                match_type="partial",
                candidates=partial_matches[:5],
            )

        # No match found
        return ClassificationResult(
            item=None,
            confidence=0.0,
            match_type="none",
        )

    def _find_partial_matches(
        self, text: str, min_confidence: float = 0.6
    ) -> List[Tuple[OntologyItem, float]]:
        """
        Find partial matches using substring matching.

        Args:
            text: Text to match.
            min_confidence: Minimum confidence threshold.

        Returns:
            List of (item, confidence) tuples, sorted by confidence.
        """
        matches = []
        text_words = set(text.split())

        for item in self._ontology.get_all_items():
            for name in item.all_names_lower:
                # Check substring containment
                if text in name:
                    # Text is substring of name
                    ratio = len(text) / len(name)
                    confidence = 0.6 + (ratio * 0.25)  # 0.6 - 0.85
                    matches.append((item, confidence))
                    break
                elif name in text:
                    # Name is substring of text
                    ratio = len(name) / len(text)
                    confidence = 0.6 + (ratio * 0.2)  # 0.6 - 0.8
                    matches.append((item, confidence))
                    break
                else:
                    # Check word overlap
                    name_words = set(name.split())
                    overlap = text_words & name_words
                    if overlap:
                        ratio = len(overlap) / max(len(text_words), len(name_words))
                        if ratio >= 0.5:
                            confidence = 0.5 + (ratio * 0.3)  # 0.5 - 0.8
                            matches.append((item, confidence))
                            break

        # Sort by confidence descending
        matches.sort(key=lambda x: x[1], reverse=True)

        # Filter by minimum confidence
        return [(item, conf) for item, conf in matches if conf >= min_confidence]

    def classify_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple line items.

        Args:
            texts: List of texts to classify.

        Returns:
            List of ClassificationResults.
        """
        return [self.classify(text) for text in texts]


# Singleton instance
_classifier_instance: Optional[RuleBasedClassifier] = None


def get_rule_based_classifier() -> RuleBasedClassifier:
    """Get singleton RuleBasedClassifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = RuleBasedClassifier()
    return _classifier_instance
