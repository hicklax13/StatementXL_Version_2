"""
GAAP Classifier Service

Uses Google Gemini API (primary) or Ollama (fallback) to classify extracted 
line items to standard GAAP categories with CONTEXT-AWARE section understanding.
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
    Classifies extracted line items to GAAP categories using AI.
    
    Primary: Google Gemini API (free tier)
    Fallback: Ollama with llama3.2:3b (local, free)
    Last resort: Rule-based classification
    """
    
    ONTOLOGY_PATH = Path("data/gaap_ontology.yaml")
    
    # Category constants
    CATEGORY_REVENUE = "revenue"
    CATEGORY_COGS = "cost_of_goods_sold"
    CATEGORY_OPERATING_EXPENSES = "operating_expenses"
    CATEGORY_OTHER = "other_income_expenses"
    CATEGORY_TAX = "tax_provision"
    CATEGORY_CALCULATED = "calculated"  # For rows like Gross Profit
    
    def __init__(self):
        """Initialize the classifier with Gemini and Ollama."""
        self.ontology = self._load_ontology()
        self._cache: Dict[str, Classification] = {}
        
        # Initialize Gemini
        self._gemini_model = None
        self._ollama_available = False
        
        self._init_gemini()
        self._init_ollama()
    
    def _init_gemini(self) -> None:
        """Initialize Google Gemini API."""
        try:
            import google.generativeai as genai
            from backend.config import get_settings
            
            settings = get_settings()
            if settings.google_api_key:
                genai.configure(api_key=settings.google_api_key)
                self._gemini_model = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("Gemini initialized for GAAP classification")
            else:
                logger.warning("No GOOGLE_API_KEY in .env, Gemini unavailable")
        except Exception as e:
            logger.warning("Failed to initialize Gemini", error=str(e))
    
    def _init_ollama(self) -> None:
        """Check if Ollama is available."""
        try:
            import httpx
            response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
            if response.status_code == 200:
                self._ollama_available = True
                logger.info("Ollama available as fallback")
        except Exception:
            logger.info("Ollama not available")
    
    def _load_ontology(self) -> Dict:
        """Load GAAP ontology from YAML file."""
        if self.ONTOLOGY_PATH.exists():
            with open(self.ONTOLOGY_PATH, "r") as f:
                return yaml.safe_load(f)
        return {}
    
    async def classify_items(
        self,
        items: List[Dict[str, Any]],
        statement_type: str = "income_statement",
        raw_text: Optional[str] = None
    ) -> List[Classification]:
        """
        Classify a list of extracted line items with section context.
        
        Args:
            items: List of dicts with 'label' and 'value' keys
            statement_type: Type of financial statement
            raw_text: Optional raw PDF text for section context
            
        Returns:
            List of Classification objects
        """
        # Try Gemini first (best accuracy with context understanding)
        if self._gemini_model:
            try:
                classifications = await self._classify_with_gemini(items, statement_type, raw_text)
                if classifications:
                    logger.info("Classification via Gemini successful", count=len(classifications))
                    return classifications
            except Exception as e:
                logger.warning("Gemini classification failed", error=str(e))
        
        # Fallback to Ollama (local, free)
        if self._ollama_available:
            try:
                classifications = await self._classify_with_ollama(items, statement_type, raw_text)
                if classifications:
                    logger.info("Classification via Ollama successful", count=len(classifications))
                    return classifications
            except Exception as e:
                logger.warning("Ollama classification failed", error=str(e))
        
        # Last resort: Rule-based classification
        logger.info("Using rule-based classification")
        classifications = []
        
        # Detect section context from raw_text
        section_context = self._detect_sections(raw_text) if raw_text else {}
        
        for item in items:
            label = item.get("label", "")
            value = item.get("value")
            
            # Use section context if available
            current_section = section_context.get(label, None)
            classification = self._classify_with_rules(label, value, statement_type, current_section)
            classifications.append(classification)
        
        return classifications
    
    def _build_context_prompt(
        self, 
        items: List[Dict], 
        statement_type: str,
        raw_text: Optional[str]
    ) -> str:
        """Build a context-aware prompt for AI classification."""
        
        # Format items with values
        items_text = "\n".join([
            f"- {item.get('label', '')}: {item.get('value', 'N/A')}"
            for item in items if item.get('value') is not None
        ])
        
        # Include raw text excerpt for context (first 2000 chars)
        context_section = ""
        if raw_text:
            context_section = f"""
IMPORTANT: Here is the original PDF document structure showing which items appear 
under which section headers (Income vs Expenses). USE THIS to determine classification:

```
{raw_text[:2000]}
```

Items appearing after "Income" and before "Expenses" are REVENUE.
Items appearing after "Expenses" are OPERATING EXPENSES or OTHER.
"""
        
        prompt = f"""You are a GAAP accounting expert. Classify each line item below.

Statement Type: {statement_type}
{context_section}

Line Items to classify:
{items_text}

CRITICAL RULES:
1. Items under "Income" section = revenue (template_row: "Services")
2. Items under "Expenses" section:
   - Payroll, salaries, wages, training, fees, advertising = operating_expenses (template_row: "Selling, General, and Administrative")
   - Mortgage interest, interest expense = other_income_expenses (template_row: "Other Income/(Expenses), Net")
   - Insurance, utilities, repairs = operating_expenses (template_row: "Selling, General, and Administrative")
3. "Total Income" = calculated (skip)
4. "Total Expenses" = calculated (skip)
5. "Overall Total" or "Net" = calculated (skip)

Return ONLY a valid JSON array. Each object must have:
- original_label: exact label from input
- category: one of [revenue, operating_expenses, other_income_expenses, calculated]
- template_row: "Services" for revenue, "Selling, General, and Administrative" for opex, "Other Income/(Expenses), Net" for interest
- confidence: 0.0 to 1.0

Example output:
[
  {{"original_label": "210 Social Security", "category": "revenue", "template_row": "Services", "confidence": 0.95}},
  {{"original_label": "310 Payroll", "category": "operating_expenses", "template_row": "Selling, General, and Administrative", "confidence": 0.95}}
]
"""
        return prompt
    
    async def _classify_with_gemini(
        self,
        items: List[Dict],
        statement_type: str,
        raw_text: Optional[str]
    ) -> List[Classification]:
        """Use Gemini to classify items with context."""
        
        prompt = self._build_context_prompt(items, statement_type, raw_text)
        
        response = await self._gemini_model.generate_content_async(prompt)
        response_text = response.text
        
        # Extract JSON array from response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if not json_match:
            raise ValueError("No JSON array in Gemini response")
        
        results = json.loads(json_match.group())
        
        # Build classification objects
        classifications = []
        result_map = {r.get("original_label", "").lower(): r for r in results}
        
        for item in items:
            label = item.get("label", "")
            value = item.get("value")
            
            # Find matching result
            result = result_map.get(label.lower(), {})
            
            if result:
                classifications.append(Classification(
                    original_label=label,
                    original_value=value,
                    category=result.get("category", self.CATEGORY_OPERATING_EXPENSES),
                    subcategory=result.get("subcategory"),
                    template_row=result.get("template_row", "Selling, General, and Administrative"),
                    confidence=result.get("confidence", 0.8),
                    reasoning=result.get("reasoning"),
                ))
            else:
                # Item not in AI response, use rules
                classifications.append(self._classify_with_rules(label, value, statement_type, None))
        
        return classifications
    
    async def _classify_with_ollama(
        self,
        items: List[Dict],
        statement_type: str,
        raw_text: Optional[str]
    ) -> List[Classification]:
        """Use Ollama (llama3.2:3b) to classify items."""
        import httpx
        
        prompt = self._build_context_prompt(items, statement_type, raw_text)
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                }
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "")
        
        # Extract JSON array from response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if not json_match:
            raise ValueError("No JSON array in Ollama response")
        
        results = json.loads(json_match.group())
        
        # Build classification objects (same logic as Gemini)
        classifications = []
        result_map = {r.get("original_label", "").lower(): r for r in results}
        
        for item in items:
            label = item.get("label", "")
            value = item.get("value")
            
            result = result_map.get(label.lower(), {})
            
            if result:
                classifications.append(Classification(
                    original_label=label,
                    original_value=value,
                    category=result.get("category", self.CATEGORY_OPERATING_EXPENSES),
                    subcategory=result.get("subcategory"),
                    template_row=result.get("template_row", "Selling, General, and Administrative"),
                    confidence=result.get("confidence", 0.7),
                    reasoning=result.get("reasoning"),
                ))
            else:
                classifications.append(self._classify_with_rules(label, value, statement_type, None))
        
        return classifications
    
    def _detect_sections(self, raw_text: str) -> Dict[str, str]:
        """
        Detect which section each label belongs to based on PDF text structure.
        
        Returns dict mapping label -> section (e.g., "210 Social Security" -> "income")
        """
        if not raw_text:
            return {}
        
        lines = raw_text.split('\n')
        current_section = None
        section_map = {}
        
        for line in lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Detect section headers
            if line_lower in ["income", "income:", "revenue", "revenue:"]:
                current_section = "income"
            elif line_lower in ["expenses", "expenses:", "expense", "expense:"]:
                current_section = "expenses"
            elif "total income" in line_lower or "total revenue" in line_lower:
                # Mark but don't change section
                pass
            elif "total expenses" in line_lower:
                pass
            elif current_section:
                # Map this line's label to current section
                section_map[line_stripped] = current_section
        
        return section_map
    
    def _classify_with_rules(
        self,
        label: str,
        value: Optional[float],
        statement_type: str,
        section_context: Optional[str] = None
    ) -> Classification:
        """
        Classify using rule-based logic with optional section context.
        
        This is the fallback when AI is not available.
        """
        label_lower = label.lower().strip()
        
        # Default category
        category = self.CATEGORY_OPERATING_EXPENSES
        subcategory = "sga"
        template_row = "Selling, General, and Administrative"
        confidence = 0.7
        
        # CRITICAL: Use section context if available
        if section_context == "income":
            category = self.CATEGORY_REVENUE
            template_row = "Services"
            confidence = 0.9
        elif section_context == "expenses":
            # Check for interest/mortgage (goes to Other)
            if any(kw in label_lower for kw in ["interest", "mortgage"]):
                category = self.CATEGORY_OTHER
                template_row = "Other Income/(Expenses), Net"
                confidence = 0.9
            else:
                category = self.CATEGORY_OPERATING_EXPENSES
                template_row = "Selling, General, and Administrative"
                confidence = 0.9
        
        # Check for calculated rows (totals)
        calculated_keywords = ["total income", "total expenses", "overall total", 
                              "gross profit", "operating income", "net income"]
        if any(ck in label_lower for ck in calculated_keywords):
            category = self.CATEGORY_CALCULATED
            template_row = None
            confidence = 0.95
        
        # Specific keyword overrides (without section context)
        if section_context is None:
            # Healthcare revenue keywords
            healthcare_revenue = ["social security", "medicaid", "medicare", "patient", "resident"]
            if any(hr in label_lower for hr in healthcare_revenue):
                category = self.CATEGORY_REVENUE
                template_row = "Services"
                confidence = 0.9
            
            # Interest/mortgage -> Other
            if any(kw in label_lower for kw in ["interest", "mortgage"]):
                category = self.CATEGORY_OTHER
                template_row = "Other Income/(Expenses), Net"
                confidence = 0.85
        
        return Classification(
            original_label=label,
            original_value=value,
            category=category,
            subcategory=subcategory,
            template_row=template_row,
            confidence=confidence,
        )
    
    def aggregate_by_category(
        self,
        classifications: List[Classification]
    ) -> Dict[str, float]:
        """
        Aggregate classified items by GAAP category.
        
        Returns a dict mapping template row labels to aggregated values.
        """
        aggregated: Dict[str, float] = {}
        
        for classification in classifications:
            if classification.original_value is None:
                continue
            
            if classification.category == self.CATEGORY_CALCULATED:
                # Don't aggregate calculated rows, they'll be formulas
                continue
            
            template_row = classification.template_row
            if not template_row:
                continue
            
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
