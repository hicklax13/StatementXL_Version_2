# StatementXL Engine Implementation Progress

This log tracks the implementation of the GPT-5.2-like engine for StatementXL.

## Overview

The engine implements a reproducible, evidence-first financial statement extraction and mapping system with these key principles:

1. **Evidence-first, never-invent** - Numbers from PDF only, LLM for classification only
2. **Deterministic-first, LLM-last** - Rules before AI
3. **Multi-pass pipeline** - Extract → Structure → Normalize → Map → Validate → Writeback → Audit
4. **Template sanctity** - Never modify formulas or formatting
5. **Full audit lineage** - Every posted value traceable to source

## Implementation Status

### Completed

1. **Evidence Model** (`models.py`) ✅
   - `DocumentEvidence`, `PageEvidence`, `TableRegion`, `TableCell`, `Token`
   - `NormalizedFact` with full provenance tracking
   - `TemplateProfile`, `TemplateCell`, `TemplateGrid`
   - `CellPosting` for audit lineage
   - `ReconciliationResult` for validation
   - `RunAudit` for complete run audit

2. **Extraction Layer** (`extraction.py`) ✅
   - Layout-aware PDF parsing with pdfplumber
   - Camelot integration for bordered tables
   - Word-level bbox extraction for overlay support
   - Text-line extraction for financial statements
   - OCR detection (threshold-based, implementation TODO)
   - Scale factor detection (thousands/millions)

3. **Normalization Layer** (`normalization.py`) ✅
   - Label normalization with synonym dictionary
   - Period detection and normalization (FY, Q, monthly)
   - Units scaling (thousands, millions)
   - Sign detection (parentheses = negative)
   - Confidence calculation

4. **Mapping Layer** (`mapping.py`) ✅
   - Template profiling (detect grids, eligible cells)
   - Label matching (exact, synonym, fuzzy via Levenshtein)
   - Period alignment
   - Greedy assignment with scoring
   - Conflict resolution (deterministic tie-breakers)

5. **Validation Layer** (`validation.py`) ✅
   - Reconciliation checks (BS: A = L + E, IS: GP = Rev - COGS, etc.)
   - Materiality thresholds (1% or $1000)
   - Cross-statement validation

6. **Writeback Layer** (`writeback.py`) ✅
   - Template-safe Excel updates
   - Only modify eligible cells
   - Never touch formulas (enforced check)

7. **Audit Sheet** (`audit_sheet.py`) ✅
   - Generate Audit sheet with all required sections
   - Lineage table with 17 columns
   - Metadata, sections, scale factors, periods, exceptions, recon results

8. **Orchestrator** (`orchestrator.py`) ✅
   - `run_engine()` entry point
   - 8-pass pipeline coordination
   - Statement section classification (deterministic)
   - Error handling with audit logging

9. **Tests** (`tests/test_engine.py`) ✅
   - Unit tests for each layer (models, extraction, normalization, mapping, validation, writeback)
   - Integration tests (conflict resolution stability)
   - Policy tests (no formula overwrite, eligible cell requirements)

10. **Wire into Backend** (`api/routes/engine.py`) ✅
    - POST /api/v1/engine/run - Synchronous engine run
    - POST /api/v1/engine/run-async - Background job
    - GET /api/v1/engine/status/{run_id} - Job status
    - GET /api/v1/engine/download/{run_id}/{filename} - Download output

## IMPLEMENTATION COMPLETE ✅

## File Structure

```
backend/statementxl_engine/
├── __init__.py           # Package exports ✅
├── models.py             # Evidence model and data structures ✅
├── extraction.py         # PDF extraction layer ✅
├── normalization.py      # Units/signs/periods/labels normalization ✅
├── mapping.py            # Template mapping layer ✅
├── validation.py         # Reconciliation layer ✅
├── writeback.py          # Template writeback layer ✅
├── audit_sheet.py        # Audit sheet generation ✅
├── orchestrator.py       # Main entry point ✅
├── tests/
│   ├── __init__.py       # Test package ✅
│   └── test_engine.py    # Comprehensive tests ✅
└── ENGINE_PROGRESS.md    # This file

backend/api/routes/
└── engine.py             # API endpoints ✅
```

## Key Design Decisions

1. **Wrapper Pattern**: Engine wraps existing services (TableDetector, MappingEngine) rather than replacing them
2. **Evidence Store**: All extracted data persisted with provenance for audit
3. **Deterministic Conflict Resolution**: Tie-breakers based on restated flag, units, consistency, filename date
4. **No LLM for Numbers**: LLM only used for classification/disambiguation, never for value extraction
5. **Template Sanctity**: Never modify formulas, styles, or formatting - only write to eligible input cells

## Running the Engine

### Via Python
```python
from backend.statementxl_engine import run_engine, EngineOptions

options = EngineOptions(
    statement_type="income_statement",
    auto_detect_periods=True,
)

result = run_engine(
    template_path="/path/to/template.xlsx",
    pdf_paths=["/path/to/financial.pdf"],
    statement_type="income_statement",
    options=options,
)

print(f"Output: {result.output_path}")
print(f"Audit: {result.audit.run_id}")
```

### Via API

```bash
# Upload template and PDFs, run engine
curl -X POST "http://localhost:8000/api/v1/engine/run" \
  -H "Authorization: Bearer <token>" \
  -F "template=@template.xlsx" \
  -F "pdfs=@financial_statement.pdf" \
  -F "statement_type=income_statement"

# Download output
curl "http://localhost:8000/api/v1/engine/download/<run_id>/<filename>" \
  -H "Authorization: Bearer <token>" \
  -o output.xlsx
```

## Acceptance Checklist

- [x] **Extraction correctness**: Tables extracted with bounding boxes, numeric values parsed
- [x] **Mapping correctness**: Facts matched to template cells with confidence scores
- [x] **Auditability**: Every posted value has full lineage in Audit sheet
- [x] **Template sanctity**: Formulas never overwritten, formatting preserved

---
Last Updated: 2026-01-04
