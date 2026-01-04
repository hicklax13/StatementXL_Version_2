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

### In Progress

4. **Mapping Layer** (`mapping.py`) - NEXT
   - Template profiling (detect grids, eligible cells)
   - Label matching (exact, synonym, fuzzy, embedding)
   - Period alignment
   - Granularity bridging (aggregate/disaggregate)
   - Conflict resolution (deterministic tie-breakers)

### Pending

5. **Validation Layer** (`validation.py`)
   - Reconciliation checks (BS: A = L + E, etc.)
   - Formula consistency
   - Cross-statement validation

6. **Writeback Layer** (`writeback.py`)
   - Template-safe Excel updates
   - Only modify eligible cells
   - Never touch formulas

7. **Audit Sheet** (`audit_sheet.py`)
   - Generate Audit sheet in output
   - Lineage table with all required columns

8. **Orchestrator** (`orchestrator.py`)
   - `run_engine()` entry point
   - Pipeline coordination
   - Error handling

9. **Tests** (`tests/`)
   - Unit tests for each layer
   - Integration tests
   - Golden run fixture

10. **Wire into Backend**
    - API endpoint integration
    - Job runner support

## File Structure

```
backend/statementxl_engine/
├── __init__.py           # Package exports
├── models.py             # Evidence model and data structures
├── extraction.py         # PDF extraction layer
├── normalization.py      # Units/signs/periods/labels normalization
├── mapping.py            # Template mapping layer (TODO)
├── validation.py         # Reconciliation layer (TODO)
├── writeback.py          # Template writeback layer (TODO)
├── audit_sheet.py        # Audit sheet generation (TODO)
├── orchestrator.py       # Main entry point (TODO)
└── ENGINE_PROGRESS.md    # This file
```

## Key Design Decisions

1. **Wrapper Pattern**: Engine wraps existing services (TableDetector, MappingEngine) rather than replacing them
2. **Evidence Store**: All extracted data persisted with provenance for audit
3. **Deterministic Conflict Resolution**: Tie-breakers based on restated flag, units, consistency, filename date
4. **No LLM for Numbers**: LLM only used for classification/disambiguation, never for value extraction

## Next Steps for Future Agents

1. Continue with `mapping.py` - implement template profiling and mapping logic
2. Then `validation.py` - reconciliation checks
3. Then `writeback.py` - template-safe updates
4. Then `audit_sheet.py` - audit generation
5. Finally `orchestrator.py` - tie it all together
6. Write tests throughout

## Running the Engine

(After completion)
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

---
Last Updated: 2026-01-04
