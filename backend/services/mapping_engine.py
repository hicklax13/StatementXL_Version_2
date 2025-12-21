"""
Mapping engine service.

Core logic for mapping extracted items to template cells.
"""
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import structlog

from backend.services.ontology_service import get_ontology_service
from backend.services.classifiers.hybrid import get_hybrid_classifier
from backend.services.validators.accounting_equation import (
    AccountingEquationValidator,
    get_accounting_validator,
)
from backend.services.validators.formula_validator import (
    FormulaValidator,
    get_formula_validator,
)

logger = structlog.get_logger(__name__)


@dataclass
class ExtractedItem:
    """Represents an item extracted from a PDF."""

    label: str
    value: Optional[Decimal]
    raw_value: str
    ontology_id: Optional[str]
    confidence: float
    page: int
    row_index: int


@dataclass
class TemplateTarget:
    """Represents a target cell in the template."""

    sheet: str
    address: str
    ontology_id: Optional[str]
    period: Optional[str]
    is_input: bool
    row_label: Optional[str]


@dataclass
class MappingCandidate:
    """A candidate mapping between source and target."""

    source: ExtractedItem
    target: TemplateTarget
    score: float
    match_type: str
    components: Dict[str, float] = field(default_factory=dict)


@dataclass
class Assignment:
    """A confirmed mapping assignment."""

    source: ExtractedItem
    target: TemplateTarget
    score: float
    match_type: str
    is_auto: bool


@dataclass
class MappingConflict:
    """A detected conflict in the mapping."""

    conflict_type: str
    severity: str
    description: str
    source_label: Optional[str]
    target_address: Optional[str]
    suggestions: List[str] = field(default_factory=list)


@dataclass
class MappingResult:
    """Result of the mapping process."""

    assignments: List[Assignment]
    conflicts: List[MappingConflict]
    total_items: int
    mapped_count: int
    auto_mapped_count: int
    average_confidence: float


class MappingEngine:
    """
    Engine for mapping extracted items to template cells.

    Process:
    1. Generate candidates (cartesian product with filters)
    2. Score each candidate (ontology match + period match + value sanity)
    3. Greedy assignment (highest scores first, no duplicates)
    4. Detect conflicts (missing, ambiguous, validation)
    5. Run validators (accounting equation, formulas)
    """

    # Scoring weights
    ONTOLOGY_WEIGHT = 0.50
    PERIOD_WEIGHT = 0.20
    LABEL_WEIGHT = 0.20
    VALUE_WEIGHT = 0.10

    # Thresholds
    AUTO_MAP_THRESHOLD = 0.70
    MIN_CANDIDATE_SCORE = 0.30

    def __init__(self):
        """Initialize mapping engine."""
        self._ontology = get_ontology_service()
        self._classifier = get_hybrid_classifier()
        self._acct_validator = get_accounting_validator()
        self._formula_validator = get_formula_validator()

    def map(
        self,
        extracted_items: List[ExtractedItem],
        template_targets: List[TemplateTarget],
        period: Optional[str] = None,
    ) -> MappingResult:
        """
        Map extracted items to template targets.

        Args:
            extracted_items: Items from PDF extraction.
            template_targets: Input cells from template.
            period: Optional period filter (e.g., "2023").

        Returns:
            MappingResult with assignments and conflicts.
        """
        logger.info(
            "Starting mapping",
            sources=len(extracted_items),
            targets=len(template_targets),
        )

        # Step 1: Generate candidates
        candidates = self._generate_candidates(extracted_items, template_targets, period)

        logger.info("Candidates generated", count=len(candidates))

        # Step 2: Greedy assignment
        assignments = self._greedy_assign(candidates)

        # Step 3: Detect conflicts
        conflicts = self._detect_conflicts(
            extracted_items, template_targets, assignments
        )

        # Step 4: Run validators
        validation_conflicts = self._run_validators(assignments)
        conflicts.extend(validation_conflicts)

        # Calculate statistics
        auto_mapped = sum(1 for a in assignments if a.is_auto)
        avg_confidence = (
            sum(a.score for a in assignments) / len(assignments)
            if assignments else 0.0
        )

        result = MappingResult(
            assignments=assignments,
            conflicts=conflicts,
            total_items=len(extracted_items),
            mapped_count=len(assignments),
            auto_mapped_count=auto_mapped,
            average_confidence=avg_confidence,
        )

        logger.info(
            "Mapping complete",
            mapped=result.mapped_count,
            auto=result.auto_mapped_count,
            conflicts=len(result.conflicts),
        )

        return result

    def _generate_candidates(
        self,
        sources: List[ExtractedItem],
        targets: List[TemplateTarget],
        period: Optional[str],
    ) -> List[MappingCandidate]:
        """Generate candidate mappings."""
        candidates = []

        for source in sources:
            for target in targets:
                # Filter by period if specified
                if period and target.period and target.period != period:
                    continue

                # Only consider input cells
                if not target.is_input:
                    continue

                # Calculate score
                score, components = self._score_candidate(source, target)

                if score >= self.MIN_CANDIDATE_SCORE:
                    candidates.append(MappingCandidate(
                        source=source,
                        target=target,
                        score=score,
                        match_type=self._determine_match_type(components),
                        components=components,
                    ))

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        return candidates

    def _score_candidate(
        self,
        source: ExtractedItem,
        target: TemplateTarget,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Score a candidate mapping.

        Returns:
            (total_score, component_scores)
        """
        components = {}

        # Ontology match
        if source.ontology_id and target.ontology_id:
            if source.ontology_id == target.ontology_id:
                components["ontology"] = 1.0
            else:
                # Check if same category
                source_item = self._ontology.get_by_id(source.ontology_id)
                target_item = self._ontology.get_by_id(target.ontology_id)

                if source_item and target_item:
                    if source_item.category == target_item.category:
                        components["ontology"] = 0.6
                    elif source_item.statement_type == target_item.statement_type:
                        components["ontology"] = 0.3
                    else:
                        components["ontology"] = 0.0
                else:
                    components["ontology"] = 0.0
        else:
            components["ontology"] = 0.0

        # Label similarity (if no ontology match)
        if components["ontology"] < 0.5:
            label_result = self._classifier.classify(source.label)
            if label_result.item and target.row_label:
                target_result = self._classifier.classify(target.row_label)
                if target_result.item and label_result.item.id == target_result.item.id:
                    components["label"] = 0.8
                else:
                    components["label"] = 0.0
            else:
                components["label"] = 0.0
        else:
            components["label"] = 0.0

        # Period match (if both have periods)
        components["period"] = 1.0  # Assume match or no period specified

        # Value sanity (basic check)
        if source.value is not None:
            # Check for reasonable financial values
            abs_value = abs(source.value)
            if abs_value > Decimal("1e15"):  # Unreasonably large
                components["value"] = 0.5
            else:
                components["value"] = 1.0
        else:
            components["value"] = 0.5

        # Calculate weighted score
        total = (
            components.get("ontology", 0) * self.ONTOLOGY_WEIGHT +
            components.get("label", 0) * self.LABEL_WEIGHT +
            components.get("period", 0) * self.PERIOD_WEIGHT +
            components.get("value", 0) * self.VALUE_WEIGHT
        )

        return total, components

    def _determine_match_type(self, components: Dict[str, float]) -> str:
        """Determine the primary match type."""
        if components.get("ontology", 0) >= 0.8:
            return "ontology_exact"
        elif components.get("ontology", 0) >= 0.5:
            return "ontology_category"
        elif components.get("label", 0) >= 0.5:
            return "label_match"
        else:
            return "low_confidence"

    def _greedy_assign(
        self, candidates: List[MappingCandidate]
    ) -> List[Assignment]:
        """Perform greedy assignment (no source or target reuse)."""
        assignments = []
        used_sources = set()
        used_targets = set()

        for candidate in candidates:
            source_key = (candidate.source.label, candidate.source.row_index)
            target_key = (candidate.target.sheet, candidate.target.address)

            if source_key in used_sources or target_key in used_targets:
                continue

            is_auto = candidate.score >= self.AUTO_MAP_THRESHOLD

            assignments.append(Assignment(
                source=candidate.source,
                target=candidate.target,
                score=candidate.score,
                match_type=candidate.match_type,
                is_auto=is_auto,
            ))

            used_sources.add(source_key)
            used_targets.add(target_key)

        return assignments

    def _detect_conflicts(
        self,
        sources: List[ExtractedItem],
        targets: List[TemplateTarget],
        assignments: List[Assignment],
    ) -> List[MappingConflict]:
        """Detect mapping conflicts."""
        conflicts = []

        # Find unmapped sources
        mapped_sources = {
            (a.source.label, a.source.row_index) for a in assignments
        }
        for source in sources:
            key = (source.label, source.row_index)
            if key not in mapped_sources:
                conflicts.append(MappingConflict(
                    conflict_type="unmapped_source",
                    severity="low",
                    description=f"Extracted item '{source.label}' was not mapped",
                    source_label=source.label,
                    target_address=None,
                    suggestions=["Review manually or mark as unused"],
                ))

        # Find unmapped required targets
        mapped_targets = {
            (a.target.sheet, a.target.address) for a in assignments
        }
        for target in targets:
            if not target.is_input:
                continue

            key = (target.sheet, target.address)
            if key not in mapped_targets:
                conflicts.append(MappingConflict(
                    conflict_type="missing_required",
                    severity="high",
                    description=f"Template cell '{target.address}' has no mapping",
                    source_label=None,
                    target_address=target.address,
                    suggestions=["Search for similar items", "Enter value manually"],
                ))

        # Find low-confidence mappings
        for assignment in assignments:
            if 0.3 <= assignment.score < self.AUTO_MAP_THRESHOLD:
                conflicts.append(MappingConflict(
                    conflict_type="low_confidence",
                    severity="medium",
                    description=f"Low confidence ({assignment.score:.2f}) mapping for '{assignment.source.label}'",
                    source_label=assignment.source.label,
                    target_address=assignment.target.address,
                    suggestions=["Verify mapping is correct"],
                ))

        return conflicts

    def _run_validators(
        self, assignments: List[Assignment]
    ) -> List[MappingConflict]:
        """Run validators on assignments."""
        conflicts = []

        # Build mappings dict for validators
        mappings: Dict[str, Decimal] = {}
        for assignment in assignments:
            if assignment.source.ontology_id and assignment.source.value is not None:
                mappings[assignment.source.ontology_id] = assignment.source.value

        # Run accounting equation validator
        acct_results = self._acct_validator.validate(mappings)
        for result in acct_results:
            if not result.is_valid:
                conflicts.append(MappingConflict(
                    conflict_type="validation_failure",
                    severity=result.severity,
                    description=result.message,
                    source_label=None,
                    target_address=None,
                    suggestions=["Check balance sheet totals"],
                ))

        # Run formula validator
        formula_results = self._formula_validator.check_sum_relationships(mappings)
        for result in formula_results:
            if not result.is_valid:
                conflicts.append(MappingConflict(
                    conflict_type="formula_break",
                    severity="high",
                    description=result.message,
                    source_label=None,
                    target_address=result.cell_address,
                    suggestions=[f"Expected: {result.expected_value}"],
                ))

        return conflicts


# Singleton instance
_engine_instance: Optional[MappingEngine] = None


def get_mapping_engine() -> MappingEngine:
    """Get singleton MappingEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MappingEngine()
    return _engine_instance
