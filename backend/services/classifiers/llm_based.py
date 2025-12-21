"""
LLM-based classifier for financial line items.

Uses OpenAI GPT-4o-mini (or Claude Haiku as fallback) for low-confidence classifications.
"""
import os
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

# Try to import OpenAI, gracefully handle if not installed
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai not installed, LLM classifier will use fallback")


@dataclass
class LLMClassificationResult:
    """Result from LLM classification."""

    item_id: Optional[str]
    label: Optional[str]
    confidence: float
    reasoning: str
    tokens_used: int


class LLMClassifier:
    """
    LLM-based classifier using OpenAI GPT-4o-mini.

    This classifier is used as a fallback when rule-based and
    embedding classifiers have low confidence. It provides
    high-quality classification with reasoning.
    """

    MODEL = "gpt-4o-mini"
    MAX_TOKENS = 256
    TEMPERATURE = 0.1  # Low temperature for consistent results

    # System prompt for classification
    SYSTEM_PROMPT = """You are a financial statement expert. Your task is to classify financial line items into standard accounting categories.

Given a line item text from a financial statement, identify the most likely standard accounting category it belongs to.

Categories include:
- Income Statement: Revenue, COGS, Operating Expenses, Operating Income, Interest, Taxes, Net Income
- Balance Sheet: Assets (Current/Non-Current), Liabilities (Current/Non-Current), Equity
- Cash Flow: Operating Activities, Investing Activities, Financing Activities

Respond in JSON format:
{
  "category": "income_statement|balance_sheet|cash_flow",
  "item_id": "is:revenue|bs:cash|cf:cfo|etc",
  "label": "Standard Label",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation"
}"""

    def __init__(
        self,
        ontology_service: Optional[OntologyService] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize LLM classifier.

        Args:
            ontology_service: Ontology service instance.
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).
        """
        self._ontology = ontology_service or get_ontology_service()
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None
        self._total_tokens = 0
        self._call_count = 0

        if OPENAI_AVAILABLE and self._api_key:
            self._client = OpenAI(api_key=self._api_key)
            logger.info("LLM classifier initialized with OpenAI")
        else:
            logger.warning("LLM classifier running in mock mode (no API key)")

    def _build_prompt(
        self, text: str, candidates: List[Tuple[OntologyItem, float]] = None
    ) -> str:
        """
        Build classification prompt.

        Args:
            text: Line item text to classify.
            candidates: Optional candidate items from other classifiers.

        Returns:
            Formatted prompt string.
        """
        prompt = f'Classify this financial line item: "{text}"'

        if candidates:
            prompt += "\n\nPossible matches from our taxonomy (use these IDs if applicable):"
            for item, score in candidates[:5]:
                prompt += f"\n- {item.id}: {item.label} (similarity: {score:.2f})"

        prompt += "\n\nRespond with JSON only."

        return prompt

    def classify(
        self,
        text: str,
        candidates: List[Tuple[OntologyItem, float]] = None,
    ) -> ClassificationResult:
        """
        Classify a line item using LLM.

        Args:
            text: Line item text to classify.
            candidates: Optional candidate items from other classifiers.

        Returns:
            ClassificationResult with LLM classification.
        """
        if not text or not text.strip():
            return ClassificationResult(
                item=None,
                confidence=0.0,
                match_type="none",
            )

        # If no client available, return mock result
        if self._client is None:
            return self._mock_classify(text, candidates)

        try:
            prompt = self._build_prompt(text, candidates)

            response = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
                response_format={"type": "json_object"},
            )

            # Track usage
            self._call_count += 1
            if response.usage:
                self._total_tokens += response.usage.total_tokens

            # Parse response
            content = response.choices[0].message.content
            result = self._parse_response(content)

            logger.info(
                "LLM classification complete",
                text=text[:50],
                item_id=result.item_id,
                confidence=result.confidence,
                tokens=result.tokens_used,
            )

            # Look up item in ontology
            item = None
            if result.item_id:
                item = self._ontology.get_by_id(result.item_id)

            return ClassificationResult(
                item=item,
                confidence=result.confidence,
                match_type="llm",
                candidates=candidates or [],
            )

        except Exception as e:
            logger.error("LLM classification failed", error=str(e), text=text[:50])
            return self._mock_classify(text, candidates)

    def _parse_response(self, content: str) -> LLMClassificationResult:
        """
        Parse LLM response JSON.

        Args:
            content: JSON response from LLM.

        Returns:
            Parsed LLMClassificationResult.
        """
        import json

        try:
            data = json.loads(content)
            return LLMClassificationResult(
                item_id=data.get("item_id"),
                label=data.get("label"),
                confidence=float(data.get("confidence", 0.8)),
                reasoning=data.get("reasoning", ""),
                tokens_used=0,  # Will be updated from response
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse LLM response", error=str(e))
            return LLMClassificationResult(
                item_id=None,
                label=None,
                confidence=0.0,
                reasoning="Parse error",
                tokens_used=0,
            )

    def _mock_classify(
        self,
        text: str,
        candidates: List[Tuple[OntologyItem, float]] = None,
    ) -> ClassificationResult:
        """
        Mock classification when API is unavailable.

        Uses best candidate if available.
        """
        if candidates and len(candidates) > 0:
            best_item, best_score = candidates[0]
            return ClassificationResult(
                item=best_item,
                confidence=min(best_score + 0.1, 0.95),  # Slight boost
                match_type="llm_mock",
                candidates=candidates,
            )

        return ClassificationResult(
            item=None,
            confidence=0.0,
            match_type="llm_unavailable",
        )

    def classify_batch(
        self, texts: List[str]
    ) -> List[ClassificationResult]:
        """
        Classify multiple line items.

        Args:
            texts: List of texts to classify.

        Returns:
            List of ClassificationResults.
        """
        return [self.classify(text) for text in texts]

    @property
    def call_count(self) -> int:
        """Get total API calls made."""
        return self._call_count

    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return self._total_tokens

    @property
    def estimated_cost(self) -> float:
        """Estimate cost in USD (GPT-4o-mini pricing)."""
        # GPT-4o-mini: $0.15/1M input, $0.60/1M output
        # Approximating as $0.30/1M average
        return (self._total_tokens / 1_000_000) * 0.30


# Singleton instance
_classifier_instance: Optional[LLMClassifier] = None


def get_llm_classifier() -> LLMClassifier:
    """Get singleton LLMClassifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = LLMClassifier()
    return _classifier_instance
