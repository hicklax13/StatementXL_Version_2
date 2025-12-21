"""
Hybrid classifier combining rule-based, embedding, and LLM classifiers.

Implements a cascade approach:
1. Rule-based → if confidence >0.9, return
2. Embedding → if confidence >0.8, return
3. LLM (optional) → final classification
"""
from dataclasses import dataclass
from typing import List, Optional

import structlog

from backend.services.ontology_service import (
    ClassificationResult,
    OntologyService,
    get_ontology_service,
)
from backend.services.classifiers.rule_based import (
    RuleBasedClassifier,
    get_rule_based_classifier,
)
from backend.services.classifiers.embedding_based import (
    EmbeddingClassifier,
    get_embedding_classifier,
    EMBEDDINGS_AVAILABLE,
)

logger = structlog.get_logger(__name__)


@dataclass
class ClassificationStats:
    """Statistics for hybrid classification."""

    total: int = 0
    rule_based: int = 0
    embedding: int = 0
    llm: int = 0
    unclassified: int = 0

    @property
    def rule_based_pct(self) -> float:
        return (self.rule_based / self.total * 100) if self.total else 0

    @property
    def embedding_pct(self) -> float:
        return (self.embedding / self.total * 100) if self.total else 0

    @property
    def llm_pct(self) -> float:
        return (self.llm / self.total * 100) if self.total else 0


class HybridClassifier:
    """
    Hybrid classifier combining multiple classification strategies.

    Cascade logic:
    1. Rule-based (exact/alias match) → if confidence ≥ 0.9, return
    2. Embedding similarity → if confidence ≥ 0.8, return
    3. LLM fallback → for remaining items (optional, requires API key)

    This approach minimizes LLM costs while maintaining accuracy.
    """

    # Confidence thresholds
    RULE_THRESHOLD = 0.9
    EMBEDDING_THRESHOLD = 0.8
    FINAL_THRESHOLD = 0.7

    def __init__(
        self,
        ontology_service: Optional[OntologyService] = None,
        rule_classifier: Optional[RuleBasedClassifier] = None,
        embedding_classifier: Optional[EmbeddingClassifier] = None,
        use_llm: bool = False,
    ):
        """
        Initialize hybrid classifier.

        Args:
            ontology_service: Ontology service instance.
            rule_classifier: Rule-based classifier instance.
            embedding_classifier: Embedding classifier instance.
            use_llm: Whether to use LLM fallback.
        """
        self._ontology = ontology_service or get_ontology_service()
        self._rule_classifier = rule_classifier or get_rule_based_classifier()
        self._embedding_classifier = embedding_classifier
        self._use_llm = use_llm
        self._stats = ClassificationStats()

        # Lazy load embedding classifier
        if embedding_classifier is None and EMBEDDINGS_AVAILABLE:
            try:
                self._embedding_classifier = get_embedding_classifier()
            except Exception as e:
                logger.warning("Failed to load embedding classifier", error=str(e))
                self._embedding_classifier = None

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a line item using hybrid approach.

        Args:
            text: Line item text to classify.

        Returns:
            ClassificationResult with best match.
        """
        self._stats.total += 1

        if not text or not text.strip():
            self._stats.unclassified += 1
            return ClassificationResult(
                item=None,
                confidence=0.0,
                match_type="none",
            )

        # Step 1: Rule-based classification
        rule_result = self._rule_classifier.classify(text)

        if rule_result.confidence >= self.RULE_THRESHOLD:
            self._stats.rule_based += 1
            return ClassificationResult(
                item=rule_result.item,
                confidence=rule_result.confidence,
                match_type=f"hybrid_rule:{rule_result.match_type}",
                candidates=rule_result.candidates,
            )

        # Step 2: Embedding-based classification
        if self._embedding_classifier is not None:
            embedding_result = self._embedding_classifier.classify(text)

            if embedding_result.confidence >= self.EMBEDDING_THRESHOLD:
                self._stats.embedding += 1
                return ClassificationResult(
                    item=embedding_result.item,
                    confidence=embedding_result.confidence,
                    match_type="hybrid_embedding",
                    candidates=embedding_result.candidates,
                )

            # Combine candidates from both methods
            all_candidates = rule_result.candidates + embedding_result.candidates

            # If embedding gives a reasonable result, use it
            if embedding_result.confidence >= self.FINAL_THRESHOLD:
                self._stats.embedding += 1
                return ClassificationResult(
                    item=embedding_result.item,
                    confidence=embedding_result.confidence,
                    match_type="hybrid_embedding_fallback",
                    candidates=all_candidates[:5],
                )

        # Step 3: LLM fallback (optional, not implemented in Phase 2)
        if self._use_llm:
            llm_result = self._classify_with_llm(text, rule_result, None)
            if llm_result.confidence >= self.FINAL_THRESHOLD:
                self._stats.llm += 1
                return llm_result

        # Return best available result
        if rule_result.confidence > 0:
            # Rule-based is still best
            if rule_result.confidence >= self.FINAL_THRESHOLD:
                self._stats.rule_based += 1
            else:
                self._stats.unclassified += 1

            return ClassificationResult(
                item=rule_result.item,
                confidence=rule_result.confidence,
                match_type=f"hybrid_low_confidence:{rule_result.match_type}",
                candidates=rule_result.candidates,
            )

        self._stats.unclassified += 1
        return ClassificationResult(
            item=None,
            confidence=0.0,
            match_type="unclassified",
        )

    def _classify_with_llm(
        self,
        text: str,
        rule_result: ClassificationResult,
        embedding_result: Optional[ClassificationResult],
    ) -> ClassificationResult:
        """
        Classify using LLM API (placeholder for future implementation).

        Args:
            text: Line item text.
            rule_result: Result from rule-based classifier.
            embedding_result: Result from embedding classifier.

        Returns:
            ClassificationResult from LLM.
        """
        # TODO: Implement in Phase 2 when LLM integration is added
        # Will use GPT-4o-mini or Claude Haiku with zero-shot prompt
        logger.info("LLM classification requested but not implemented", text=text)

        # Return empty result for now
        return ClassificationResult(
            item=None,
            confidence=0.0,
            match_type="llm_not_implemented",
        )

    def classify_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple line items.

        Args:
            texts: List of texts to classify.

        Returns:
            List of ClassificationResults.
        """
        return [self.classify(text) for text in texts]

    def get_stats(self) -> ClassificationStats:
        """Get classification statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset classification statistics."""
        self._stats = ClassificationStats()


# Singleton instance
_classifier_instance: Optional[HybridClassifier] = None


def get_hybrid_classifier() -> HybridClassifier:
    """Get singleton HybridClassifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = HybridClassifier()
    return _classifier_instance
