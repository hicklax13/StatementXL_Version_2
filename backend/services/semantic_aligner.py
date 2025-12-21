"""
Semantic aligner service.

Maps template cells to ontology items using the hybrid classifier.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict

import structlog

from backend.services.excel_parser import ParsedCell, ParsedWorkbook
from backend.services.ontology_service import OntologyItem, get_ontology_service
from backend.services.classifiers.hybrid import get_hybrid_classifier
from backend.services.structure_inferencer import InferredStructure

logger = structlog.get_logger(__name__)


@dataclass
class AlignedCell:
    """Represents a cell aligned to the ontology."""

    address: str
    sheet: str
    row: int
    column: int
    label: str  # Original cell text
    ontology_id: Optional[str]
    ontology_label: Optional[str]
    confidence: float
    section_type: Optional[str] = None
    alternatives: List[tuple] = None  # [(ontology_id, label, confidence), ...]


@dataclass
class AlignmentResult:
    """Result of semantic alignment."""

    aligned_cells: List[AlignedCell]
    total_cells: int
    aligned_count: int
    high_confidence_count: int  # confidence >= 0.9
    low_confidence_count: int  # confidence < 0.7
    unaligned_count: int


class SemanticAligner:
    """
    Service for aligning template cells to ontology items.

    Uses the hybrid classifier to map row labels to standardized
    financial line items.
    """

    HIGH_CONFIDENCE_THRESHOLD = 0.9
    LOW_CONFIDENCE_THRESHOLD = 0.7

    def __init__(self):
        """Initialize semantic aligner."""
        self._ontology = get_ontology_service()
        self._classifier = get_hybrid_classifier()

    def align(
        self,
        workbook: ParsedWorkbook,
        structures: Dict[str, InferredStructure],
    ) -> AlignmentResult:
        """
        Align label cells to ontology items.

        Args:
            workbook: Parsed Excel workbook.
            structures: Inferred structures by sheet name.

        Returns:
            AlignmentResult with all aligned cells.
        """
        logger.info("Starting semantic alignment", filename=workbook.filename)

        aligned_cells: List[AlignedCell] = []
        total = 0
        high_conf = 0
        low_conf = 0
        unaligned = 0

        for sheet in workbook.sheets:
            structure = structures.get(sheet.name)
            if not structure:
                continue

            # Get label column cells
            label_cells = [
                c for c in sheet.cells
                if c.column == structure.label_column
                and isinstance(c.value, str)
                and len(c.value.strip()) > 1
                and c.row > structure.header_row
            ]

            for cell in label_cells:
                total += 1
                aligned = self._align_cell(cell, structure)
                aligned_cells.append(aligned)

                if aligned.ontology_id:
                    if aligned.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
                        high_conf += 1
                    elif aligned.confidence < self.LOW_CONFIDENCE_THRESHOLD:
                        low_conf += 1
                else:
                    unaligned += 1

        result = AlignmentResult(
            aligned_cells=aligned_cells,
            total_cells=total,
            aligned_count=total - unaligned,
            high_confidence_count=high_conf,
            low_confidence_count=low_conf,
            unaligned_count=unaligned,
        )

        logger.info(
            "Semantic alignment complete",
            total=total,
            aligned=result.aligned_count,
            high_confidence=high_conf,
            unaligned=unaligned,
        )

        return result

    def _align_cell(
        self, cell: ParsedCell, structure: InferredStructure
    ) -> AlignedCell:
        """
        Align a single cell to the ontology.

        Args:
            cell: Cell to align.
            structure: Inferred structure for context.

        Returns:
            AlignedCell with alignment result.
        """
        text = str(cell.value).strip()

        # Find section this cell belongs to
        section_type = None
        for section in structure.sections:
            if section.start_row <= cell.row <= section.end_row:
                section_type = section.section_type
                break

        # Classify the text
        result = self._classifier.classify(text)

        alternatives = []
        for item, score in result.candidates[:3]:
            alternatives.append((item.id, item.label, score))

        return AlignedCell(
            address=cell.address,
            sheet=cell.sheet,
            row=cell.row,
            column=cell.column,
            label=text,
            ontology_id=result.item.id if result.item else None,
            ontology_label=result.item.label if result.item else None,
            confidence=result.confidence,
            section_type=section_type,
            alternatives=alternatives,
        )

    def align_single(self, text: str, section_type: Optional[str] = None) -> AlignedCell:
        """
        Align a single text to the ontology.

        Args:
            text: Text to align.
            section_type: Optional section context.

        Returns:
            AlignedCell with alignment result.
        """
        result = self._classifier.classify(text)

        alternatives = []
        for item, score in result.candidates[:3]:
            alternatives.append((item.id, item.label, score))

        return AlignedCell(
            address="",
            sheet="",
            row=0,
            column=0,
            label=text,
            ontology_id=result.item.id if result.item else None,
            ontology_label=result.item.label if result.item else None,
            confidence=result.confidence,
            section_type=section_type,
            alternatives=alternatives,
        )


# Singleton instance
_aligner_instance: Optional[SemanticAligner] = None


def get_semantic_aligner() -> SemanticAligner:
    """Get singleton SemanticAligner instance."""
    global _aligner_instance
    if _aligner_instance is None:
        _aligner_instance = SemanticAligner()
    return _aligner_instance
