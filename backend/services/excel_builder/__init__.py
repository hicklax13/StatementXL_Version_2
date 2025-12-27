"""
Excel Builder module for StatementXL.

Provides tools for generating formatted Excel financial statements
from extracted PDF data using standardized templates.
"""

from backend.services.excel_builder.builder import ExcelBuilder
from backend.services.excel_builder.aggregator import GAAPAggregator
from backend.services.excel_builder.template_parser import TemplateParser
from backend.services.excel_builder.formula_engine import FormulaEngine
from backend.services.excel_builder.styles import STYLES, COLORWAYS

__all__ = [
    "ExcelBuilder",
    "GAAPAggregator",
    "TemplateParser",
    "FormulaEngine",
    "STYLES",
    "COLORWAYS",
]
