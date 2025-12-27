"""
Template Loader Service

Loads Excel template files for population with financial data.
"""

from pathlib import Path
from typing import Optional

import structlog
from openpyxl import load_workbook
from openpyxl.workbook import Workbook

from backend.services.template_parser import TemplateParser, TemplateStructure, get_template_parser

logger = structlog.get_logger(__name__)


class TemplateLoader:
    """
    Loads Excel template files and prepares them for data population.
    """
    
    BASE_DIR = Path("Excel Templates")
    
    def __init__(self):
        """Initialize the template loader."""
        self._parser = get_template_parser()
    
    def load(
        self,
        statement_type: str = "income_statement",
        style: str = "basic"
    ) -> tuple[Workbook, TemplateStructure]:
        """
        Load a template file and parse its structure.
        
        Args:
            statement_type: Type of statement (income_statement, balance_sheet, cash_flow)
            style: Template style (basic, corporate, professional)
            
        Returns:
            Tuple of (Workbook, TemplateStructure)
        """
        # Parse template structure first
        structure = self._parser.parse(statement_type, style)
        
        # Load workbook for editing
        wb = load_workbook(structure.file_path)
        
        logger.info(
            "Template loaded",
            path=str(structure.file_path),
            rows=len(structure.rows),
        )
        
        return wb, structure
    
    def get_template_path(
        self,
        statement_type: str,
        style: str
    ) -> Optional[Path]:
        """Get the path to a template file."""
        
        # Map statement types to folder names
        folder_map = {
            "income_statement": "Income Statement",
            "balance_sheet": "Balance Sheet",
            "cash_flow": "Cash Flow",
        }
        
        # Map styles to file names (basic uses the main template)
        file_map = {
            "basic": "StatementXL_Income_Statement_Template.xlsx",
            "corporate": "corporate.xlsx",
            "professional": "professional.xlsx",
        }
        
        folder = folder_map.get(statement_type)
        filename = file_map.get(style)
        
        if folder and filename:
            path = self.BASE_DIR / folder / filename
            if path.exists():
                return path
            
            # Try basic template as fallback
            if style != "basic":
                basic_path = self.BASE_DIR / folder / file_map["basic"]
                if basic_path.exists():
                    return basic_path
        
        return None


# Singleton instance
_loader_instance: Optional[TemplateLoader] = None


def get_template_loader() -> TemplateLoader:
    """Get singleton TemplateLoader instance."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = TemplateLoader()
    return _loader_instance
