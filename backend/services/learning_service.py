"""
Learning service.

Stores feedback, builds profiles, and auto-applies learned mappings.
"""
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy.orm import Session

from backend.models.mapping_profile import (
    MappingProfile,
    MappingFeedback,
    FeedbackType,
)

logger = structlog.get_logger(__name__)


@dataclass
class LearnedMapping:
    """A learned mapping from feedback."""

    source_pattern: str
    target_ontology_id: str
    confidence: float
    times_used: int


@dataclass
class AutoApplyResult:
    """Result of auto-applying learned mappings."""

    total_items: int
    auto_applied: int
    applied_mappings: List[Dict[str, Any]]
    remaining_items: List[str]


class LearningService:
    """
    Service for learning from analyst decisions.

    Key features:
    - Store feedback when analysts resolve conflicts
    - Build profiles per company/template
    - Auto-apply previous mappings on repeat uploads
    """

    # Minimum confidence to auto-apply
    AUTO_APPLY_THRESHOLD = 0.85

    # Minimum times a mapping must be seen to auto-apply
    MIN_OCCURRENCES = 2

    def __init__(self, db: Session):
        """Initialize learning service."""
        self._db = db

    def record_feedback(
        self,
        source_label: str,
        source_ontology_id: Optional[str],
        target_ontology_id: str,
        feedback_type: FeedbackType,
        original_suggestion: Optional[str] = None,
        profile_id: Optional[uuid.UUID] = None,
        mapping_graph_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
        confidence_before: Optional[float] = None,
    ) -> MappingFeedback:
        """
        Record an analyst's mapping decision.

        Args:
            source_label: The source label that was mapped.
            source_ontology_id: Ontology ID of source.
            target_ontology_id: Ontology ID of target.
            feedback_type: Type of feedback.
            original_suggestion: What was originally suggested.
            profile_id: Associated profile ID.
            mapping_graph_id: Associated mapping graph.
            user_email: User who made the decision.
            confidence_before: Confidence before correction.

        Returns:
            Created MappingFeedback record.
        """
        # Create normalized pattern for matching
        pattern = self._normalize_label(source_label)

        feedback = MappingFeedback(
            profile_id=profile_id,
            mapping_graph_id=mapping_graph_id,
            source_label=source_label,
            source_ontology_id=source_ontology_id,
            source_pattern=pattern,
            target_ontology_id=target_ontology_id,
            feedback_type=feedback_type,
            original_suggestion=original_suggestion,
            final_decision=target_ontology_id,
            user_email=user_email,
            confidence_before=confidence_before,
            confidence_after=1.0,  # Analyst decisions are 100% confident
        )

        self._db.add(feedback)
        self._db.commit()

        logger.info(
            "Feedback recorded",
            source=source_label,
            target=target_ontology_id,
            type=feedback_type.value,
        )

        # Update profile if exists
        if profile_id:
            self._update_profile_mappings(profile_id, pattern, target_ontology_id)

        return feedback

    def get_or_create_profile(
        self,
        company_name: Optional[str] = None,
        industry: Optional[str] = None,
        template_id: Optional[uuid.UUID] = None,
    ) -> MappingProfile:
        """
        Get existing profile or create new one.

        Args:
            company_name: Company name for lookup.
            industry: Industry tag.
            template_id: Associated template.

        Returns:
            MappingProfile instance.
        """
        # Try to find existing profile
        query = self._db.query(MappingProfile).filter(MappingProfile.is_active == True)

        if company_name:
            query = query.filter(MappingProfile.company_name == company_name)
        if template_id:
            query = query.filter(MappingProfile.template_id == template_id)

        profile = query.first()

        if profile:
            logger.info("Found existing profile", profile_id=str(profile.id))
            return profile

        # Create new profile
        profile = MappingProfile(
            name=company_name or f"Profile-{uuid.uuid4().hex[:8]}",
            company_name=company_name,
            industry=industry,
            template_id=template_id,
            mappings=[],
        )

        self._db.add(profile)
        self._db.commit()

        logger.info("Created new profile", profile_id=str(profile.id))
        return profile

    def auto_apply_mappings(
        self,
        source_labels: List[str],
        profile_id: Optional[uuid.UUID] = None,
        company_name: Optional[str] = None,
    ) -> AutoApplyResult:
        """
        Auto-apply learned mappings to new items.

        Args:
            source_labels: Labels to map.
            profile_id: Specific profile to use.
            company_name: Company name for profile lookup.

        Returns:
            AutoApplyResult with applied mappings.
        """
        # Get profile
        profile = None
        if profile_id:
            profile = self._db.query(MappingProfile).filter(
                MappingProfile.id == profile_id
            ).first()
        elif company_name:
            profile = self._db.query(MappingProfile).filter(
                MappingProfile.company_name == company_name,
                MappingProfile.is_active == True,
            ).first()

        # Get all feedback for matching
        learned_mappings = self._get_learned_mappings(profile)

        applied_mappings = []
        remaining_items = []

        for label in source_labels:
            pattern = self._normalize_label(label)
            match = self._find_best_match(pattern, learned_mappings)

            if match and match.confidence >= self.AUTO_APPLY_THRESHOLD:
                applied_mappings.append({
                    "source_label": label,
                    "target_ontology_id": match.target_ontology_id,
                    "confidence": match.confidence,
                    "match_type": "learned",
                })
            else:
                remaining_items.append(label)

        # Update profile usage stats
        if profile and applied_mappings:
            profile.times_used += 1
            self._db.commit()

        logger.info(
            "Auto-apply complete",
            total=len(source_labels),
            applied=len(applied_mappings),
            remaining=len(remaining_items),
        )

        return AutoApplyResult(
            total_items=len(source_labels),
            auto_applied=len(applied_mappings),
            applied_mappings=applied_mappings,
            remaining_items=remaining_items,
        )

    def _normalize_label(self, label: str) -> str:
        """Normalize a label for pattern matching."""
        # Lowercase, remove special chars, normalize whitespace
        normalized = label.lower()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def _get_learned_mappings(
        self, profile: Optional[MappingProfile]
    ) -> List[LearnedMapping]:
        """Get learned mappings from feedback."""
        query = self._db.query(MappingFeedback)

        if profile:
            query = query.filter(MappingFeedback.profile_id == profile.id)

        # Group by pattern and target
        feedback_list = query.all()

        # Aggregate by pattern -> target
        pattern_counts: Dict[str, Dict[str, int]] = {}
        for fb in feedback_list:
            if fb.source_pattern not in pattern_counts:
                pattern_counts[fb.source_pattern] = {}
            if fb.target_ontology_id not in pattern_counts[fb.source_pattern]:
                pattern_counts[fb.source_pattern][fb.target_ontology_id] = 0
            pattern_counts[fb.source_pattern][fb.target_ontology_id] += 1

        # Convert to LearnedMapping
        mappings = []
        for pattern, targets in pattern_counts.items():
            total = sum(targets.values())
            for target_id, count in targets.items():
                if count >= self.MIN_OCCURRENCES:
                    mappings.append(LearnedMapping(
                        source_pattern=pattern,
                        target_ontology_id=target_id,
                        confidence=count / total,
                        times_used=count,
                    ))

        return mappings

    def _find_best_match(
        self, pattern: str, mappings: List[LearnedMapping]
    ) -> Optional[LearnedMapping]:
        """Find best matching learned mapping."""
        best_match = None
        best_score = 0.0

        for mapping in mappings:
            if mapping.source_pattern == pattern:
                score = mapping.confidence * 1.0  # Exact match bonus
            elif pattern in mapping.source_pattern or mapping.source_pattern in pattern:
                score = mapping.confidence * 0.8  # Partial match
            else:
                continue

            if score > best_score:
                best_score = score
                best_match = mapping

        return best_match

    def _update_profile_mappings(
        self,
        profile_id: uuid.UUID,
        pattern: str,
        target_ontology_id: str,
    ) -> None:
        """Update profile with new mapping."""
        profile = self._db.query(MappingProfile).filter(
            MappingProfile.id == profile_id
        ).first()

        if not profile:
            return

        # Update or add mapping
        mappings = profile.mappings or []
        found = False

        for mapping in mappings:
            if mapping.get("source_pattern") == pattern:
                mapping["target_ontology_id"] = target_ontology_id
                mapping["count"] = mapping.get("count", 0) + 1
                found = True
                break

        if not found:
            mappings.append({
                "source_pattern": pattern,
                "target_ontology_id": target_ontology_id,
                "count": 1,
            })

        profile.mappings = mappings
        profile.total_mappings = len(mappings)
        self._db.commit()


def get_learning_service(db: Session) -> LearningService:
    """Get LearningService instance."""
    return LearningService(db)
