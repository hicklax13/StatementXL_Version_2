"""
GAAP Classifier Service - Fine-tuned for Financial Accuracy

Uses Google Gemini API (primary) or Ollama (fallback) to classify extracted 
line items to standard GAAP categories with CONTEXT-AWARE section understanding.

Enhanced with comprehensive GAAP knowledge, accounting terminology, and
industry-specific classification patterns.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    
    Fine-tuned with comprehensive GAAP knowledge for financial accuracy.
    
    Primary: Google Gemini API (free tier)
    Fallback: Ollama with llama3.2:3b (local, free)
    Last resort: Rule-based classification with section awareness
    """
    
    ONTOLOGY_PATH = Path("data/gaap_ontology.yaml")
    
    # Income Statement category constants
    CATEGORY_REVENUE = "revenue"
    CATEGORY_COGS = "cost_of_goods_sold"
    CATEGORY_OPERATING_EXPENSES = "operating_expenses"
    CATEGORY_OTHER = "other_income_expenses"
    CATEGORY_TAX = "tax_provision"
    CATEGORY_CALCULATED = "calculated"
    
    # Balance Sheet category constants
    CATEGORY_CURRENT_ASSETS = "current_assets"
    CATEGORY_NONCURRENT_ASSETS = "noncurrent_assets"
    CATEGORY_CURRENT_LIABILITIES = "current_liabilities"
    CATEGORY_NONCURRENT_LIABILITIES = "noncurrent_liabilities"
    CATEGORY_EQUITY = "equity"
    
    def __init__(self):
        """Initialize the classifier with Gemini and Ollama."""
        self.ontology = self._load_ontology()
        self._cache: Dict[str, Classification] = {}
        
        # Initialize AI models
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
    
    def _detect_sections_enhanced(self, raw_text: str) -> Dict[str, str]:
        """
        Enhanced section detection using line-by-line parsing.
        
        Returns dict mapping each line label to its section (income/expenses).
        """
        if not raw_text:
            return {}
        
        lines = raw_text.split('\n')
        current_section = None
        section_map = {}
        
        for line in lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Section header detection (be very specific)
            if line_lower in ["income", "income:", "revenue", "revenue:", "revenues", "revenues:"]:
                current_section = "income"
                continue
            elif line_lower in ["expenses", "expenses:", "expense", "expense:", "operating expenses", "operating expenses:"]:
                current_section = "expenses"
                continue
            
            # Skip totals and calculated lines
            if any(kw in line_lower for kw in ["total income", "total expenses", "overall total", "net income", "gross profit"]):
                continue
            
            # Skip headers and empty lines
            if not line_stripped or len(line_stripped) < 3:
                continue
            
            # Map this line to current section
            if current_section:
                section_map[line_stripped] = current_section
        
        return section_map
    
    async def classify_items(
        self,
        items: List[Dict[str, Any]],
        statement_type: str = "income_statement",
        raw_text: Optional[str] = None
    ) -> List[Classification]:
        """
        Classify a list of extracted line items with section context.
        """
        # Enhanced section detection
        section_map = self._detect_sections_enhanced(raw_text) if raw_text else {}
        
        # Try Gemini first (best accuracy)
        if self._gemini_model:
            try:
                classifications = await self._classify_with_gemini(items, statement_type, raw_text, section_map)
                if classifications:
                    logger.info("Classification via Gemini successful", count=len(classifications))
                    return classifications
            except Exception as e:
                logger.warning("Gemini classification failed", error=str(e))
        
        # Fallback to Ollama
        if self._ollama_available:
            try:
                classifications = await self._classify_with_ollama(items, statement_type, raw_text, section_map)
                if classifications:
                    logger.info("Classification via Ollama successful", count=len(classifications))
                    return classifications
            except Exception as e:
                logger.warning("Ollama classification failed", error=str(e))
        
        # Last resort: Enhanced rule-based classification
        logger.info("Using enhanced rule-based classification with section context")
        classifications = []
        
        for item in items:
            label = item.get("label", "")
            value = item.get("value")
            
            # Find section for this item
            current_section = None
            for key in section_map:
                if label in key or key in label:
                    current_section = section_map[key]
                    break
            
            classification = self._classify_with_enhanced_rules(label, value, statement_type, current_section)
            classifications.append(classification)
        
        return classifications
    
    def _build_gaap_expert_prompt(
        self, 
        items: List[Dict], 
        statement_type: str,
        raw_text: Optional[str],
        section_map: Dict[str, str]
    ) -> str:
        """
        Build a comprehensive, fine-tuned prompt with deep GAAP knowledge.
        """
        
        # Pre-classify items with section context for the prompt
        items_with_sections = []
        for item in items:
            label = item.get('label', '')
            value = item.get('value', 'N/A')
            
            # Find section
            section = "UNKNOWN"
            for key in section_map:
                if label in key or key in label:
                    section = section_map[key].upper()
                    break
            
            items_with_sections.append(f"- [{section}] {label}: {value}")
        
        items_text = "\n".join(items_with_sections)
        
        prompt = f'''You are a Senior CPA and GAAP Expert with 20+ years of experience. Your task is to classify financial line items with 100% accuracy.

=== STATEMENT TYPE ===
{statement_type}

=== DOCUMENT STRUCTURE (CRITICAL - READ CAREFULLY) ===
```
{raw_text[:2500] if raw_text else "No document context provided"}
```

=== ITEMS TO CLASSIFY ===
{items_text}

=== GAAP CLASSIFICATION RULES ===

**INCOME STATEMENT STRUCTURE (ASC 220)**

1. **REVENUE (Top Line)**
   - ALL items appearing under "Income" section header = REVENUE
   - Healthcare: Social Security, Medicare, Medicaid, patient fees
   - Services: consulting fees, service revenue, subscription income
   - Products: product sales, merchandise, retail sales
   - Other revenue: rental income, royalties, licensing fees
   → Template Row: "Services" (for service businesses) or "Products" (for retail)

2. **COST OF GOODS SOLD (COGS)**
   - Direct costs of producing goods/services
   - Materials, direct labor, manufacturing overhead
   - NOT applicable to pure service businesses
   → Template Row: "Products" or "Services" (under COGS section)

3. **OPERATING EXPENSES (SG&A)**
   - ALL items appearing under "Expenses" section header = OPERATING EXPENSES (unless interest-related)
   - **Personnel**: payroll, salaries, wages, benefits, training, employee-related
   - **Facilities**: rent, utilities, maintenance, repairs
   - **Administrative**: office supplies, software, telephone
   - **Marketing**: advertising, promotions
   - **Professional**: legal fees, accounting fees, consulting fees (when expense)
   - **Insurance**: property, liability, health (when expense)
   - **Bank fees, AHCA fees, license fees** = OPERATING EXPENSE
   → Template Row: "Selling, General, and Administrative"

4. **OTHER INCOME/(EXPENSES)**
   - Interest expense, mortgage interest, loan interest
   - Interest income
   - Gains/losses on asset sales
   - Foreign exchange gains/losses
   → Template Row: "Other Income/(Expenses), Net"

5. **CALCULATED (Skip - will be formulas)**
   - Total Income, Total Revenue, Total Expenses
   - Gross Profit, Operating Income, Net Income
   - Overall Total, subtotals

=== CRITICAL SECTION DETECTION RULES ===

The PDF document shows clear section headers:
- "Income" or "Revenue" header = Everything below is REVENUE until "Expenses"
- "Expenses" header = Everything below is an EXPENSE

NEVER classify something under "Expenses" as revenue!
ALWAYS use the section context to determine classification!

=== OUTPUT FORMAT ===

Return ONLY a valid JSON array. Each object must have:
- "original_label": exact label from input
- "category": one of [revenue, operating_expenses, other_income_expenses, calculated]
- "template_row": exact template row name
- "confidence": 0.0 to 1.0
- "reasoning": brief explanation

Example:
[
  {{"original_label": "210 Social Security", "category": "revenue", "template_row": "Services", "confidence": 0.98, "reasoning": "Healthcare income under Income section"}},
  {{"original_label": "310 Payroll", "category": "operating_expenses", "template_row": "Selling, General, and Administrative", "confidence": 0.98, "reasoning": "Personnel expense under Expenses section"}},
  {{"original_label": "550 Mortgage Interest", "category": "other_income_expenses", "template_row": "Other Income/(Expenses), Net", "confidence": 0.95, "reasoning": "Interest expense"}},
  {{"original_label": "420 Bank fees", "category": "operating_expenses", "template_row": "Selling, General, and Administrative", "confidence": 0.95, "reasoning": "Administrative expense under Expenses section"}}
]
'''
        return prompt
    
    async def _classify_with_gemini(
        self,
        items: List[Dict],
        statement_type: str,
        raw_text: Optional[str],
        section_map: Dict[str, str]
    ) -> List[Classification]:
        """Use Gemini with fine-tuned GAAP expert prompt."""
        
        prompt = self._build_gaap_expert_prompt(items, statement_type, raw_text, section_map)
        
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
            
            result = result_map.get(label.lower(), {})
            
            if result and result.get("category") != "calculated":
                classifications.append(Classification(
                    original_label=label,
                    original_value=value,
                    category=result.get("category", self.CATEGORY_OPERATING_EXPENSES),
                    subcategory=result.get("subcategory"),
                    template_row=result.get("template_row", "Selling, General, and Administrative"),
                    confidence=result.get("confidence", 0.9),
                    reasoning=result.get("reasoning"),
                ))
            elif result.get("category") == "calculated":
                classifications.append(Classification(
                    original_label=label,
                    original_value=value,
                    category=self.CATEGORY_CALCULATED,
                    template_row=None,
                    confidence=0.95,
                ))
            else:
                # Use section-aware fallback
                current_section = None
                for key in section_map:
                    if label in key or key in label:
                        current_section = section_map[key]
                        break
                classifications.append(self._classify_with_enhanced_rules(label, value, statement_type, current_section))
        
        return classifications
    
    async def _classify_with_ollama(
        self,
        items: List[Dict],
        statement_type: str,
        raw_text: Optional[str],
        section_map: Dict[str, str]
    ) -> List[Classification]:
        """Use Ollama with fine-tuned GAAP expert prompt."""
        import httpx
        
        prompt = self._build_gaap_expert_prompt(items, statement_type, raw_text, section_map)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 4096}
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
        
        # Build classification objects
        classifications = []
        result_map = {r.get("original_label", "").lower(): r for r in results}
        
        for item in items:
            label = item.get("label", "")
            value = item.get("value")
            
            result = result_map.get(label.lower(), {})
            
            if result and result.get("category") != "calculated":
                classifications.append(Classification(
                    original_label=label,
                    original_value=value,
                    category=result.get("category", self.CATEGORY_OPERATING_EXPENSES),
                    subcategory=result.get("subcategory"),
                    template_row=result.get("template_row", "Selling, General, and Administrative"),
                    confidence=result.get("confidence", 0.85),
                    reasoning=result.get("reasoning"),
                ))
            elif result.get("category") == "calculated":
                classifications.append(Classification(
                    original_label=label,
                    original_value=value,
                    category=self.CATEGORY_CALCULATED,
                    template_row=None,
                    confidence=0.95,
                ))
            else:
                current_section = None
                for key in section_map:
                    if label in key or key in label:
                        current_section = section_map[key]
                        break
                classifications.append(self._classify_with_enhanced_rules(label, value, statement_type, current_section))
        
        return classifications
    
    def _classify_with_enhanced_rules(
        self,
        label: str,
        value: Optional[float],
        statement_type: str,
        section_context: Optional[str] = None
    ) -> Classification:
        """
        Enhanced rule-based classification with comprehensive GAAP knowledge.
        Uses section context as the PRIMARY classifier.
        """
        label_lower = label.lower().strip()
        
        # Default to operating expenses (safest default)
        category = self.CATEGORY_OPERATING_EXPENSES
        template_row = "Selling, General, and Administrative"
        confidence = 0.7
        
        # ============================================
        # STEP 1: Check for calculated/total rows FIRST
        # ============================================
        calculated_keywords = [
            "total income", "total expenses", "total revenue",
            "overall total", "gross profit", "operating income", 
            "net income", "income before", "ebit", "ebitda",
            "subtotal"
        ]
        if any(ck in label_lower for ck in calculated_keywords):
            return Classification(
                original_label=label,
                original_value=value,
                category=self.CATEGORY_CALCULATED,
                template_row=None,
                confidence=0.98,
            )
        
        # ============================================
        # STEP 2: Use section context (MOST RELIABLE)
        # ============================================
        if section_context == "income":
            category = self.CATEGORY_REVENUE
            template_row = "Services"
            confidence = 0.95
            
            # Double-check for interest items that might be miscategorized
            if any(kw in label_lower for kw in ["interest income", "interest earned"]):
                category = self.CATEGORY_OTHER
                template_row = "Other Income/(Expenses), Net"
            
        elif section_context == "expenses":
            # Default to SG&A for most expenses
            category = self.CATEGORY_OPERATING_EXPENSES
            template_row = "Selling, General, and Administrative"
            confidence = 0.95
            
            # Check for interest/financing expenses → Other
            interest_keywords = ["interest", "mortgage", "loan interest", "financing"]
            if any(kw in label_lower for kw in interest_keywords):
                category = self.CATEGORY_OTHER
                template_row = "Other Income/(Expenses), Net"
                confidence = 0.95
        
        # ============================================
        # STEP 3: Keyword-based fallback (no section context)
        # ============================================
        if section_context is None:
            # Revenue indicators (healthcare, services)
            revenue_indicators = [
                "social security", "medicaid", "medicare", "patient",
                "resident", "service revenue", "sales", "subscription",
                "rental income", "royalty", "license revenue", "fee income"
            ]
            if any(ri in label_lower for ri in revenue_indicators):
                category = self.CATEGORY_REVENUE
                template_row = "Services"
                confidence = 0.85
            
            # Expense indicators
            expense_indicators = [
                "payroll", "salary", "wage", "benefit", "insurance",
                "utility", "utilities", "rent", "advertising", "training",
                "office", "supplies", "professional", "consulting",
                "bank fee", "license fee", "ahca", "legal"
            ]
            if any(ei in label_lower for ei in expense_indicators):
                category = self.CATEGORY_OPERATING_EXPENSES
                template_row = "Selling, General, and Administrative"
                confidence = 0.85
            
            # Interest/financing → Other
            if any(kw in label_lower for kw in ["interest", "mortgage"]):
                category = self.CATEGORY_OTHER
                template_row = "Other Income/(Expenses), Net"
                confidence = 0.9
        
        return Classification(
            original_label=label,
            original_value=value,
            category=category,
            subcategory="sga" if category == self.CATEGORY_OPERATING_EXPENSES else None,
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
                continue
            
            template_row = classification.template_row
            if not template_row:
                continue
            
            if template_row in aggregated:
                aggregated[template_row] += classification.original_value
            else:
                aggregated[template_row] = classification.original_value
        
        return aggregated
    
    def _classify_balance_sheet_item(
        self,
        label: str,
        value: Optional[float],
        section_context: Optional[str] = None
    ) -> Classification:
        """
        Classify balance sheet line items to GAAP categories.
        
        Balance Sheet sections:
        - Assets (Current, Non-Current)
        - Liabilities (Current, Non-Current)
        - Shareholders' Equity
        """
        label_lower = label.lower().strip()
        
        # Default to current assets
        category = self.CATEGORY_CURRENT_ASSETS
        template_row = "Other Current Assets"
        confidence = 0.7
        
        # ============================================
        # STEP 1: Check for calculated/total rows
        # ============================================
        calculated_keywords = [
            "total assets", "total liabilities", "total equity",
            "total current assets", "total non-current assets",
            "total current liabilities", "total non-current liabilities",
            "total shareholders", "total liabilities and equity"
        ]
        if any(ck in label_lower for ck in calculated_keywords):
            return Classification(
                original_label=label,
                original_value=value,
                category=self.CATEGORY_CALCULATED,
                template_row=None,
                confidence=0.98,
            )
        
        # ============================================
        # STEP 2: Use section context if available
        # ============================================
        if section_context:
            section_lower = section_context.lower()
            
            if "current asset" in section_lower:
                category = self.CATEGORY_CURRENT_ASSETS
                template_row = "Other Current Assets"
                confidence = 0.9
            elif "non-current asset" in section_lower or "fixed asset" in section_lower:
                category = self.CATEGORY_NONCURRENT_ASSETS
                template_row = "Other Non-Current Assets"
                confidence = 0.9
            elif "current liabilit" in section_lower:
                category = self.CATEGORY_CURRENT_LIABILITIES
                template_row = "Other Current Liabilities"
                confidence = 0.9
            elif "non-current liabilit" in section_lower or "long-term" in section_lower:
                category = self.CATEGORY_NONCURRENT_LIABILITIES
                template_row = "Other Non-Current Liabilities"
                confidence = 0.9
            elif "equity" in section_lower or "shareholder" in section_lower:
                category = self.CATEGORY_EQUITY
                template_row = "Retained Earnings"
                confidence = 0.9
        
        # ============================================
        # STEP 3: Keyword-based classification
        # ============================================
        
        # CURRENT ASSETS
        if any(kw in label_lower for kw in ["cash", "bank account", "checking", "savings"]):
            category = self.CATEGORY_CURRENT_ASSETS
            template_row = "Cash and Cash Equivalents"
            confidence = 0.95
        elif any(kw in label_lower for kw in ["accounts receivable", "a/r", "receivable", "due from"]):
            category = self.CATEGORY_CURRENT_ASSETS
            template_row = "Accounts Receivable"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["inventory", "stock", "merchandise"]):
            category = self.CATEGORY_CURRENT_ASSETS
            template_row = "Inventory"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["prepaid", "advance payment"]):
            category = self.CATEGORY_CURRENT_ASSETS
            template_row = "Prepaid Expenses"
            confidence = 0.9
        
        # NON-CURRENT ASSETS
        elif any(kw in label_lower for kw in ["property", "building", "land", "equipment", "machinery", "furniture", "vehicle"]):
            category = self.CATEGORY_NONCURRENT_ASSETS
            template_row = "Property, Plant and Equipment"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["depreciation", "accumulated depreciation"]):
            category = self.CATEGORY_NONCURRENT_ASSETS
            template_row = "Accumulated Depreciation"
            confidence = 0.95
        elif any(kw in label_lower for kw in ["intangible", "goodwill", "patent", "trademark", "copyright"]):
            category = self.CATEGORY_NONCURRENT_ASSETS
            template_row = "Intangible Assets"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["investment", "securities", "long-term investment"]):
            category = self.CATEGORY_NONCURRENT_ASSETS
            template_row = "Long-Term Investments"
            confidence = 0.85
        
        # CURRENT LIABILITIES
        elif any(kw in label_lower for kw in ["accounts payable", "a/p", "payable", "due to"]):
            category = self.CATEGORY_CURRENT_LIABILITIES
            template_row = "Accounts Payable"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["accrued", "accrual", "accrued expense"]):
            category = self.CATEGORY_CURRENT_LIABILITIES
            template_row = "Accrued Expenses"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["short-term debt", "short term loan", "line of credit", "credit line"]):
            category = self.CATEGORY_CURRENT_LIABILITIES
            template_row = "Short-Term Debt"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["current portion", "current maturities"]):
            category = self.CATEGORY_CURRENT_LIABILITIES
            template_row = "Current Portion of Long-Term Debt"
            confidence = 0.9
        
        # NON-CURRENT LIABILITIES
        elif any(kw in label_lower for kw in ["long-term debt", "long term loan", "mortgage", "notes payable", "bonds"]):
            category = self.CATEGORY_NONCURRENT_LIABILITIES
            template_row = "Long-Term Debt"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["deferred tax", "deferred liability"]):
            category = self.CATEGORY_NONCURRENT_LIABILITIES
            template_row = "Deferred Tax Liabilities"
            confidence = 0.9
        
        # EQUITY
        elif any(kw in label_lower for kw in ["common stock", "capital stock", "share capital"]):
            category = self.CATEGORY_EQUITY
            template_row = "Common Stock"
            confidence = 0.95
        elif any(kw in label_lower for kw in ["additional paid", "paid-in capital", "apic"]):
            category = self.CATEGORY_EQUITY
            template_row = "Additional Paid-In Capital"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["retained earnings", "accumulated deficit", "retained profit"]):
            category = self.CATEGORY_EQUITY
            template_row = "Retained Earnings"
            confidence = 0.95
        elif any(kw in label_lower for kw in ["treasury stock", "treasury shares"]):
            category = self.CATEGORY_EQUITY
            template_row = "Treasury Stock"
            confidence = 0.9
        elif any(kw in label_lower for kw in ["accumulated other comprehensive", "aoci", "oci"]):
            category = self.CATEGORY_EQUITY
            template_row = "Accumulated Other Comprehensive Income"
            confidence = 0.9
        
        return Classification(
            original_label=label,
            original_value=value,
            category=category,
            template_row=template_row,
            confidence=confidence,
        )


# Singleton instance
_classifier_instance: Optional[GaapClassifier] = None


def get_gaap_classifier() -> GaapClassifier:
    """Get singleton GaapClassifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = GaapClassifier()
    return _classifier_instance
