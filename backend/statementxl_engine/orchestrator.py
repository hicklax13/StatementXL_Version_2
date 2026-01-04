"""
Orchestrator for the StatementXL Engine.

Main entry point that coordinates the multi-pass pipeline:
Pass 1-2: Extract (tokens, bboxes, tables, OCR)
Pass 3: Structure (table cells, row/col grouping, numeric parsing)
Pass 4: Normalize (units, signs, periods, canonical labels)
Pass 5: Map (template line items + periods)
Pass 6: Validate (reconciliations + internal consistency)
Pass 7: Writeback (template-safe edits only)
Pass 8: Audit synthesis (lineage + exceptions + recon deltas)
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from backend.statementxl_engine.models import (
    ConfidenceLevel,
    DocumentEvidence,
    NormalizedFact,
    RunAudit,
    RunResult,
    ScaleFactor,
    StatementSection,
    StatementType,
)
from backend.statementxl_engine.extraction import get_extraction_layer
from backend.statementxl_engine.normalization import get_normalization_layer
from backend.statementxl_engine.mapping import get_mapping_layer
from backend.statementxl_engine.validation import get_validation_layer
from backend.statementxl_engine.writeback import get_writeback_layer
from backend.statementxl_engine.audit_sheet import get_audit_sheet_generator

logger = structlog.get_logger(__name__)


@dataclass
class EngineOptions:
    """Configuration options for the engine."""
    # Statement type (or auto-detect)
    statement_type: Optional[str] = None  # "income_statement", "balance_sheet", "cash_flow"
    # Period filtering
    target_period: Optional[str] = None  # e.g., "FY2024"
    auto_detect_periods: bool = True
    # Mapping thresholds
    min_confidence: float = 0.30
    auto_map_threshold: float = 0.70
    # Validation
    skip_validation: bool = False
    # LLM settings (for classification only)
    use_llm_classification: bool = False
    llm_model: str = "gpt-4"
    # Output
    output_filename_pattern: str = "StatementXL_Mapped_{statement_type}_{template_name}.xlsx"
    # Debug
    verbose: bool = False


def run_engine(
    template_path: str | Path,
    pdf_paths: List[str | Path],
    statement_type: Optional[str] = None,
    options: Optional[EngineOptions] = None,
) -> RunResult:
    """
    Main entry point for the StatementXL Engine.

    Orchestrates the complete pipeline:
    1. Extract data from PDFs
    2. Normalize values (units, signs, periods, labels)
    3. Map to template cells
    4. Validate reconciliations
    5. Write to output template
    6. Generate audit sheet

    Args:
        template_path: Path to the Excel template.
        pdf_paths: List of PDF file paths to process.
        statement_type: Optional statement type ("income_statement", "balance_sheet", "cash_flow").
        options: Engine configuration options.

    Returns:
        RunResult with output path, audit data, and metrics.
    """
    # Initialize
    run_id = str(uuid.uuid4())
    options = options or EngineOptions()
    template_path = Path(template_path)
    pdf_paths = [Path(p) for p in pdf_paths]

    logger.info(
        "Starting StatementXL Engine",
        run_id=run_id,
        template=template_path.name,
        pdfs=[p.name for p in pdf_paths],
        statement_type=statement_type or options.statement_type,
    )

    # Initialize audit
    audit = RunAudit(
        run_id=run_id,
        template_path=str(template_path),
        template_filename=template_path.name,
        pdf_paths=[str(p) for p in pdf_paths],
        pdf_filenames=[p.name for p in pdf_paths],
        options=_options_to_dict(options),
    )

    try:
        # Determine statement type
        stmt_type = _parse_statement_type(statement_type or options.statement_type)
        audit.statement_type = stmt_type

        # =================================================================
        # Pass 1-2: EXTRACTION
        # =================================================================
        logger.info("Pass 1-2: Extraction")
        extraction_layer = get_extraction_layer()

        all_documents: List[DocumentEvidence] = []
        all_scale_factors: Dict[str, ScaleFactor] = {}

        for pdf_path in pdf_paths:
            doc = extraction_layer.extract_document(pdf_path)
            all_documents.append(doc)
            audit.document_evidence.append(doc)

            # Detect scale factors
            for page in doc.pages:
                scale = extraction_layer.detect_scale_factor(page.raw_text)
                if scale != ScaleFactor.UNITS:
                    key = f"{doc.filename}_p{page.page_num}"
                    all_scale_factors[key] = scale
                    audit.detected_scale_factors[key] = scale

        logger.info(
            "Extraction complete",
            documents=len(all_documents),
            total_tables=sum(len(d.all_tables()) for d in all_documents),
        )

        # =================================================================
        # Pass 3: STATEMENT CLASSIFICATION
        # =================================================================
        logger.info("Pass 3: Statement Classification")
        statement_sections = _classify_sections(all_documents, stmt_type)
        audit.statement_sections = statement_sections

        # =================================================================
        # Pass 4: NORMALIZATION
        # =================================================================
        logger.info("Pass 4: Normalization")
        normalization_layer = get_normalization_layer()

        all_facts: List[NormalizedFact] = []
        for doc in all_documents:
            # Get scale factors for this document
            doc_scales = {
                k: v for k, v in all_scale_factors.items()
                if k.startswith(doc.filename)
            }
            # Convert keys to just page numbers
            page_scales = {}
            for k, v in doc_scales.items():
                match = re.search(r'_p(\d+)$', k)
                if match:
                    page_scales[f"p{match.group(1)}"] = v

            facts = normalization_layer.normalize_document(
                doc, statement_sections, page_scales
            )
            all_facts.extend(facts)

            # Record period mappings
            for fact in facts:
                if fact.period:
                    audit.period_mappings.append({
                        "raw_header": fact.period.raw_header,
                        "normalized_key": fact.period.normalized_key,
                        "end_date": fact.period.end_date.isoformat() if fact.period.end_date else "",
                        "duration_months": fact.period.duration_months,
                    })

        audit.normalized_facts = all_facts
        audit.total_facts = len(all_facts)

        logger.info("Normalization complete", facts=len(all_facts))

        # =================================================================
        # Pass 5: MAPPING
        # =================================================================
        logger.info("Pass 5: Mapping")
        mapping_layer = get_mapping_layer()

        profile, postings = mapping_layer.map_facts_to_template(
            all_facts,
            template_path,
            target_period=options.target_period,
        )

        audit.cell_postings = postings
        audit.mapped_facts = len(set(p.primary_fact_id for p in postings))
        audit.posted_cells = len(postings)

        # Record unmatched template items
        matched_labels = set()
        for posting in postings:
            if posting.template_cell.row_label:
                matched_labels.add(posting.template_cell.row_label.lower())

        for cell in profile.get_eligible_cells():
            if cell.row_label and cell.row_label.lower() not in matched_labels:
                if cell.row_label not in audit.unmatched_template_items:
                    audit.unmatched_template_items.append(cell.row_label)

        logger.info(
            "Mapping complete",
            postings=len(postings),
            mapped=audit.mapped_facts,
        )

        # =================================================================
        # Pass 6: VALIDATION
        # =================================================================
        if not options.skip_validation:
            logger.info("Pass 6: Validation")
            validation_layer = get_validation_layer()

            recon_result = validation_layer.validate(
                postings, all_facts, stmt_type
            )
            audit.reconciliation = recon_result

            logger.info(
                "Validation complete",
                checks=len(recon_result.checks),
                passed=recon_result.all_passed,
            )
        else:
            logger.info("Pass 6: Validation SKIPPED")

        # =================================================================
        # Pass 7: WRITEBACK
        # =================================================================
        logger.info("Pass 7: Writeback")
        writeback_layer = get_writeback_layer()

        # Generate output filename
        stmt_name = stmt_type.value if stmt_type else "mixed"
        output_filename = options.output_filename_pattern.format(
            statement_type=stmt_name,
            template_name=template_path.stem,
        )
        output_path = template_path.parent / output_filename

        writeback_layer.write_postings(
            template_path, output_path, postings, profile
        )

        logger.info("Writeback complete", output=str(output_path))

        # =================================================================
        # Pass 8: AUDIT SHEET
        # =================================================================
        logger.info("Pass 8: Audit Sheet Generation")
        audit_generator = get_audit_sheet_generator()
        audit_generator.generate_audit_sheet(output_path, audit)

        logger.info("Audit sheet generated")

        # =================================================================
        # FINAL RESULT
        # =================================================================
        # Calculate overall confidence
        if postings:
            avg_conf = sum(p.confidence for p in postings) / len(postings)
            if avg_conf >= 0.85:
                conf_level = ConfidenceLevel.HIGH
            elif avg_conf >= 0.65:
                conf_level = ConfidenceLevel.MEDIUM
            elif avg_conf >= 0.40:
                conf_level = ConfidenceLevel.LOW
            else:
                conf_level = ConfidenceLevel.VERY_LOW
        else:
            conf_level = ConfidenceLevel.VERY_LOW

        recon_passed = audit.reconciliation.all_passed if audit.reconciliation else True

        result = RunResult(
            success=True,
            run_id=run_id,
            output_path=str(output_path),
            audit=audit,
            total_facts_extracted=len(all_facts),
            facts_mapped=audit.mapped_facts,
            cells_posted=len(postings),
            reconciliation_passed=recon_passed,
            confidence_level=conf_level,
        )

        logger.info(
            "StatementXL Engine complete",
            run_id=run_id,
            success=True,
            output=str(output_path),
            facts=len(all_facts),
            mapped=audit.mapped_facts,
            posted=len(postings),
            recon_passed=recon_passed,
        )

        return result

    except Exception as e:
        import traceback
        error_msg = str(e)
        error_tb = traceback.format_exc()

        logger.error(
            "StatementXL Engine failed",
            run_id=run_id,
            error=error_msg,
            traceback=error_tb,
        )

        audit.add_exception(
            category="engine_error",
            severity="error",
            message=error_msg,
            traceback=error_tb,
        )

        return RunResult(
            success=False,
            run_id=run_id,
            output_path="",
            audit=audit,
            error_message=error_msg,
        )


def _parse_statement_type(type_str: Optional[str]) -> Optional[StatementType]:
    """Parse statement type string to enum."""
    if not type_str:
        return None

    type_map = {
        "income_statement": StatementType.INCOME_STATEMENT,
        "is": StatementType.INCOME_STATEMENT,
        "p&l": StatementType.INCOME_STATEMENT,
        "pnl": StatementType.INCOME_STATEMENT,
        "balance_sheet": StatementType.BALANCE_SHEET,
        "bs": StatementType.BALANCE_SHEET,
        "cash_flow": StatementType.CASH_FLOW,
        "cf": StatementType.CASH_FLOW,
    }

    return type_map.get(type_str.lower())


def _classify_sections(
    documents: List[DocumentEvidence],
    hint_type: Optional[StatementType],
) -> List[StatementSection]:
    """
    Classify statement sections in documents.

    Uses deterministic heuristics first, LLM only if ambiguous.
    """
    sections: List[StatementSection] = []

    # Keywords for classification
    IS_KEYWORDS = ["revenue", "net sales", "cost of goods", "gross profit", "operating income", "net income"]
    BS_KEYWORDS = ["total assets", "total liabilities", "shareholders equity", "current assets"]
    CF_KEYWORDS = ["cash from operations", "investing activities", "financing activities"]

    for doc in documents:
        for table in doc.all_tables():
            # Get all text from table
            table_text = " ".join(
                cell.raw_text.lower()
                for row in table.rows
                for cell in row.cells
            )

            # Score each type
            is_score = sum(1 for kw in IS_KEYWORDS if kw in table_text)
            bs_score = sum(1 for kw in BS_KEYWORDS if kw in table_text)
            cf_score = sum(1 for kw in CF_KEYWORDS if kw in table_text)

            # Determine type
            if hint_type:
                stmt_type = hint_type
                confidence = 0.95
                method = "user_specified"
                rationale = f"User specified {hint_type.value}"
            elif is_score > bs_score and is_score > cf_score and is_score > 0:
                stmt_type = StatementType.INCOME_STATEMENT
                confidence = min(0.5 + is_score * 0.1, 0.95)
                method = "deterministic"
                rationale = f"Matched {is_score} IS keywords"
            elif bs_score > is_score and bs_score > cf_score and bs_score > 0:
                stmt_type = StatementType.BALANCE_SHEET
                confidence = min(0.5 + bs_score * 0.1, 0.95)
                method = "deterministic"
                rationale = f"Matched {bs_score} BS keywords"
            elif cf_score > 0:
                stmt_type = StatementType.CASH_FLOW
                confidence = min(0.5 + cf_score * 0.1, 0.95)
                method = "deterministic"
                rationale = f"Matched {cf_score} CF keywords"
            else:
                stmt_type = StatementType.UNKNOWN
                confidence = 0.3
                method = "fallback"
                rationale = "No clear keywords matched"

            # Get title from first row
            title = ""
            if table.rows and table.rows[0].cells:
                title = table.rows[0].cells[0].raw_text[:100]

            section = StatementSection(
                id="",
                statement_type=stmt_type,
                title=title or f"Table on page {table.page}",
                source_table_id=table.id,
                page=table.page,
                start_row=0,
                end_row=len(table.rows),
                confidence=confidence,
                classification_method=method,
                rationale=rationale,
            )
            sections.append(section)

            # Update table with classification
            table.statement_type = stmt_type

    return sections


def _options_to_dict(options: EngineOptions) -> Dict[str, Any]:
    """Convert options to dict for audit."""
    return {
        "statement_type": options.statement_type,
        "target_period": options.target_period,
        "auto_detect_periods": options.auto_detect_periods,
        "min_confidence": options.min_confidence,
        "auto_map_threshold": options.auto_map_threshold,
        "skip_validation": options.skip_validation,
        "use_llm_classification": options.use_llm_classification,
        "llm_model": options.llm_model,
    }
