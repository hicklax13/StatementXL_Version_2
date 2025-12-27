"""
GAAP Classifier Service

Uses Google Gemini API to classify extracted line items to standard GAAP categories.
This enables intelligent mapping of any financial document format to standardized templates.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
import yaml

logger = structlog.get_logger(__name__)


@dataclass
class Classification:
    """Result of classifying a line item."""
    
    original_label: str
    original_value: Optional[float]
    category: str  # revenue, cogs, operating_expenses, other, tax
    subcategory: Optional[str] = None  # e.g., sga, r_and_d
    template_row: Optional[str] = None  # Exact label in template
    confidence: float = 0.0
    reasoning: Optional[str] = None


class GaapClassifier:
    """
    Classifies extracted line items to GAAP categories using Gemini AI.
    
    Falls back to rule-based classification when AI is unavailable.
    """
    
    ONTOLOGY_PATH = Path("data/gaap_ontology.yaml")
    
    # Category constants
    CATEGORY_REVENUE = "revenue"
    CATEGORY_COGS = "cost_of_goods_sold"
    CATEGORY_OPERATING_EXPENSES = "operating_expenses"
    CATEGORY_OTHER = "other_income_expenses"
    CATEGORY_TAX = "tax_provision"
    CATEGORY_CALCULATED = "calculated"  # For rows like Gross Profit
    
    def __init__(self, use_ai: bool = True):
        """
        Initialize the classifier.
        
        Args:
            use_ai: Whether to use Gemini AI for classification
        """
        self.use_ai = use_ai
        self.ontology = self._load_ontology()
        self._cache: Dict[str, Classification] = {}
        
        # Initialize Gemini if available
        self._model = None
        if use_ai:
            try:
                import google.generativeai as genai
                from backend.core.config import settings
                
                if settings.GOOGLE_API_KEY:
                    genai.configure(api_key=settings.GOOGLE_API_KEY)
                    self._model = genai.GenerativeModel("gemini-1.5-flash")
                    logger.info("Gemini model initialized for GAAP classification")
                else:
                    logger.warning("No Google API key, falling back to rule-based classification")
                    self.use_ai = False
            except Exception as e:
                logger.warning("Failed to initialize Gemini", error=str(e))
                self.use_ai = False
    
    def _load_ontology(self) -> Dict:
        """Load GAAP ontology from YAML file."""
        if self.ONTOLOGY_PATH.exists():
            with open(self.ONTOLOGY_PATH, "r") as f:
                return yaml.safe_load(f)
        return {}
    
    async def classify_items(
        self,
        items: List[Dict[str, Any]],
        statement_type: str = "income_statement"
    ) -> List[Classification]:
        """
        Classify a list of extracted line items.
        
        Args:
            items: List of dicts with 'label' and 'value' keys
            statement_type: Type of financial statement
            
        Returns:
            List of Classification objects
        """
        classifications = []
        
        # Try batch AI classification first
        if self.use_ai and self._model:
            try:
                classifications = await self._classify_with_ai(items, statement_type)
                if classifications:
                    return classifications
            except Exception as e:
                logger.warning("AI classification failed, using rules", error=str(e))
        
        # Fall back to rule-based classification
        for item in items:
            label = item.get("label", "")
            value = item.get("value")
            
            classification = self._classify_with_rules(label, value, statement_type)
            classifications.append(classification)
        
        return classifications
    
    async def _classify_with_ai(
        self,
        items: List[Dict],
        statement_type: str
    ) -> List[Classification]:
        """Use Gemini to classify items."""
        
        # Build prompt
        items_text = "\n".join([
            f"- {item.get('label', '')}: {item.get('value', 'N/A')}"
            for item in items
        ])
        
        prompt = f"""
You are a GAAP accounting expert. Classify each financial line item below.

Statement Type: {statement_type}

Line Items:
{items_text}

For each item, determine:
1. category: One of [revenue, cost_of_goods_sold, operating_expenses, other_income_expenses, tax_provision, calculated]
2. subcategory: For operating_expenses, specify "sga" or "r_and_d"
3. template_row: The standard GAAP label to use (e.g., "Revenue", "Selling, General, and Administrative")
4. confidence: 0.0 to 1.0

Important rules:
- "Social Security", "Medicaid", patient fees = revenue
- Payroll, salaries, wages = operating_expenses (sga)
- Utilities, rent, insurance = operating_expenses (sga)
- Interest expense, mortgage = other_income_expenses
- "Total Income" maps to "Total Revenue"
- "Overall Total" or "Net" at bottom = calculated (Net Income)

Return ONLY a JSON array with objects containing:
{{"original_label": "...", "category": "...", "subcategory": "...", "template_row": "...", "confidence": 0.95, "reasoning": "..."}}
"""
        
        try:
            response = await self._model.generate_content_async(prompt)
            
            # Parse JSON from response
            response_text = response.text
            
            # Extract JSON array from response
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                results = json.loads(json_match.group())
                
                classifications = []
                for i, result in enumerate(results):
                    if i < len(items):
                        classifications.append(Classification(
                            original_label=result.get("original_label", items[i].get("label", "")),
                            original_value=items[i].get("value"),
                            category=result.get("category", self.CATEGORY_OPERATING_EXPENSES),
                            subcategory=result.get("subcategory"),
                            template_row=result.get("template_row"),
                            confidence=result.get("confidence", 0.8),
                            reasoning=result.get("reasoning"),
                        ))
                
                return classifications
                
        except Exception as e:
            logger.error("AI classification parsing failed", error=str(e))
            
        return []
    
    def _classify_with_rules(
        self,
        label: str,
        value: Optional[float],
        statement_type: str
    ) -> Classification:
        """
        Classify using rule-based logic from ontology.
        
        This is the fallback when AI is not available.
        """
        label_lower = label.lower().strip()
        
        # Check cache
        cache_key = f"{label_lower}_{statement_type}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return Classification(
                original_label=label,
                original_value=value,
                category=cached.category,
                subcategory=cached.subcategory,
                template_row=cached.template_row,
                confidence=cached.confidence,
            )
        
        # Get classification rules from ontology
        rules = self.ontology.get("classification_rules", {})
        
        category = self.CATEGORY_OPERATING_EXPENSES  # Default
        subcategory = "sga"
        template_row = "Selling, General, and Administrative"
        confidence = 0.7
        
        # Check for revenue
        revenue_keywords = rules.get("revenue_keywords", [])
        if any(kw in label_lower for kw in revenue_keywords):
            # Check if it's truly income (not expense that mentions income)
            if not any(exp in label_lower for exp in ["expense", "cost"]):
                category = self.CATEGORY_REVENUE
                template_row = "Revenue"
                confidence = 0.85
        
        # Check for specific revenue items (healthcare)
        healthcare_revenue = ["social security", "medicaid", "medicare", "patient", "resident"]
        if any(hr in label_lower for hr in healthcare_revenue):
            category = self.CATEGORY_REVENUE
            template_row = "Revenue"
            confidence = 0.9
        
        # Check for COGS
        cogs_keywords = ["cost of goods", "cogs", "direct cost", "materials cost"]
        if any(kw in label_lower for kw in cogs_keywords):
            category = self.CATEGORY_COGS
            template_row = "Cost of Goods Sold"
            confidence = 0.9
        
        # Check for other income/expenses (interest, mortgage)
        other_keywords = rules.get("other_keywords", [])
        if any(kw in label_lower for kw in other_keywords):
            category = self.CATEGORY_OTHER
            template_row = "Other Income/(Expenses), Net"
            confidence = 0.85
        
        # Check for tax
        if "tax" in label_lower and "income" in label_lower:
            category = self.CATEGORY_TAX
            template_row = "Provision for Income Taxes"
            confidence = 0.9
        
        # Check for calculated rows
        calculated_keywords = ["gross profit", "operating income", "net income", "net profit", "overall total", "total income"]
        if any(ck in label_lower for ck in calculated_keywords):
            category = self.CATEGORY_CALCULATED
            
            if "gross" in label_lower:
                template_row = "Gross Profit"
            elif "operating" in label_lower:
                template_row = "Operating Income"
            elif "net" in label_lower or "overall" in label_lower:
                template_row = "Net Income"
            elif "total income" in label_lower:
                template_row = "Total Revenue"
                category = self.CATEGORY_REVENUE
                
            confidence = 0.95
        
        # Check for total rows
        if label_lower.startswith("total "):
            # Keep the category but mark as total
            if "expense" in label_lower:
                template_row = "Total Operating Expenses"
            elif "revenue" in label_lower or "income" in label_lower:
                template_row = "Total Revenue"
                category = self.CATEGORY_REVENUE
        
        # Check SG&A specific keywords
        sga_keywords = rules.get("sga_keywords", [])
        if category == self.CATEGORY_OPERATING_EXPENSES:
            if any(kw in label_lower for kw in sga_keywords):
                subcategory = "sga"
                template_row = "Selling, General, and Administrative"
                confidence = 0.85
        
        classification = Classification(
            original_label=label,
            original_value=value,
            category=category,
            subcategory=subcategory,
            template_row=template_row,
            confidence=confidence,
        )
        
        # Cache result
        self._cache[cache_key] = classification
        
        return classification
    
    def aggregate_by_category(
        self,
        classifications: List[Classification]
    ) -> Dict[str, float]:
        """
        Aggregate classified items by GAAP category.
        
        Returns a dict mapping template row labels to aggregated values.
        """
        aggregated: Dict[str, float] = {}
        
        # Group by template row
        for classification in classifications:
            if classification.original_value is None:
                continue
            
            if classification.category == self.CATEGORY_CALCULATED:
                # Don't aggregate calculated rows, they'll be formulas
                continue
            
            template_row = classification.template_row or classification.category
            
            if template_row in aggregated:
                aggregated[template_row] += classification.original_value
            else:
                aggregated[template_row] = classification.original_value
        
        return aggregated


# Singleton instance
_classifier_instance: Optional[GaapClassifier] = None


def get_gaap_classifier() -> GaapClassifier:
    """Get singleton GaapClassifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = GaapClassifier()
    return _classifier_instance
