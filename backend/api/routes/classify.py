"""
Classification API routes.

Provides endpoints for classifying financial line items.
"""
from typing import List, Optional

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.classifiers.hybrid import get_hybrid_classifier

logger = structlog.get_logger(__name__)

router = APIRouter()


class ClassifyRequest(BaseModel):
    """Request model for classification."""

    text: str = Field(..., description="Line item text to classify", min_length=1)
    top_k: int = Field(5, description="Number of candidates to return", ge=1, le=10)


class ClassifyBatchRequest(BaseModel):
    """Request model for batch classification."""

    texts: List[str] = Field(..., description="Line items to classify", min_items=1, max_items=100)
    top_k: int = Field(5, description="Number of candidates per item", ge=1, le=10)


class CandidateResponse(BaseModel):
    """Response model for a classification candidate."""

    item_id: str = Field(..., description="Ontology item ID")
    label: str = Field(..., description="Standard label")
    confidence: float = Field(..., description="Match confidence (0-1)")


class ClassifyResponse(BaseModel):
    """Response model for classification."""

    text: str = Field(..., description="Original input text")
    item_id: Optional[str] = Field(None, description="Best match ontology ID")
    label: Optional[str] = Field(None, description="Best match label")
    confidence: float = Field(..., description="Classification confidence")
    match_type: str = Field(..., description="Classification method used")
    candidates: List[CandidateResponse] = Field(
        default_factory=list, description="Top candidate matches"
    )


class ClassifyBatchResponse(BaseModel):
    """Response model for batch classification."""

    results: List[ClassifyResponse] = Field(..., description="Classification results")
    total: int = Field(..., description="Total items classified")


class ClassificationStatsResponse(BaseModel):
    """Response model for classification statistics."""

    total: int = Field(..., description="Total classifications")
    rule_based: int = Field(..., description="Rule-based matches")
    embedding: int = Field(..., description="Embedding matches")
    llm: int = Field(..., description="LLM classifications")
    unclassified: int = Field(..., description="Unclassified items")
    rule_based_pct: float = Field(..., description="Rule-based percentage")
    embedding_pct: float = Field(..., description="Embedding percentage")
    llm_pct: float = Field(..., description="LLM percentage")


@router.post(
    "/classify",
    response_model=ClassifyResponse,
    summary="Classify a financial line item",
    description="Classify a single financial line item text and return the best matching ontology item.",
)
async def classify_item(request: ClassifyRequest) -> ClassifyResponse:
    """
    Classify a financial line item.

    Args:
        request: Classification request with text.

    Returns:
        Classification result with best match.
    """
    classifier = get_hybrid_classifier()
    result = classifier.classify(request.text)

    # Build candidates list
    candidates = []
    for item, score in result.candidates[:request.top_k]:
        candidates.append(CandidateResponse(
            item_id=item.id,
            label=item.label,
            confidence=score,
        ))

    return ClassifyResponse(
        text=request.text,
        item_id=result.item.id if result.item else None,
        label=result.item.label if result.item else None,
        confidence=result.confidence,
        match_type=result.match_type,
        candidates=candidates,
    )


@router.post(
    "/classify/batch",
    response_model=ClassifyBatchResponse,
    summary="Classify multiple line items",
    description="Classify a batch of financial line items.",
)
async def classify_batch(request: ClassifyBatchRequest) -> ClassifyBatchResponse:
    """
    Classify multiple financial line items.

    Args:
        request: Batch classification request.

    Returns:
        List of classification results.
    """
    classifier = get_hybrid_classifier()
    results = []

    for text in request.texts:
        result = classifier.classify(text)

        candidates = []
        for item, score in result.candidates[:request.top_k]:
            candidates.append(CandidateResponse(
                item_id=item.id,
                label=item.label,
                confidence=score,
            ))

        results.append(ClassifyResponse(
            text=text,
            item_id=result.item.id if result.item else None,
            label=result.item.label if result.item else None,
            confidence=result.confidence,
            match_type=result.match_type,
            candidates=candidates,
        ))

    return ClassifyBatchResponse(
        results=results,
        total=len(results),
    )


@router.get(
    "/classify/stats",
    response_model=ClassificationStatsResponse,
    summary="Get classification statistics",
    description="Get statistics about classification methods used.",
)
async def get_classification_stats() -> ClassificationStatsResponse:
    """
    Get classification statistics.

    Returns:
        Statistics about classification methods used.
    """
    classifier = get_hybrid_classifier()
    stats = classifier.get_stats()

    return ClassificationStatsResponse(
        total=stats.total,
        rule_based=stats.rule_based,
        embedding=stats.embedding,
        llm=stats.llm,
        unclassified=stats.unclassified,
        rule_based_pct=stats.rule_based_pct,
        embedding_pct=stats.embedding_pct,
        llm_pct=stats.llm_pct,
    )


@router.post(
    "/classify/reset-stats",
    summary="Reset classification statistics",
    description="Reset the classification statistics counters.",
)
async def reset_classification_stats() -> dict:
    """
    Reset classification statistics.

    Returns:
        Confirmation message.
    """
    classifier = get_hybrid_classifier()
    classifier.reset_stats()

    return {"message": "Statistics reset successfully"}
