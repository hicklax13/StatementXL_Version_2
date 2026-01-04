"""
StatementXL Engine - GPT-5.2-like Financial Statement Extraction and Mapping.

A reproducible, evidence-first engine for extracting financial data from PDFs
and mapping to Excel templates with full audit lineage.

Key Principles:
1. Evidence-first, never-invent - Numbers from PDF only, LLM for classification
2. Deterministic-first, LLM-last - Rules before AI
3. Multi-pass pipeline with verification
4. Template sanctity - Never modify formulas or formatting
5. Full audit lineage for every posted value
"""

from backend.statementxl_engine.orchestrator import run_engine, EngineOptions
from backend.statementxl_engine.models import (
    RunResult,
    StatementType,
    ConfidenceLevel,
)

__version__ = "1.0.0"
__all__ = [
    "run_engine",
    "EngineOptions",
    "RunResult",
    "StatementType",
    "ConfidenceLevel",
]
