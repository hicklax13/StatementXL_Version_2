"""
GAAP Aggregator for mapping extracted line items to standard template categories.

Uses financial accounting logic to consolidate diverse PDF line items
into standardized Income Statement, Balance Sheet, and Cash Flow categories.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple
import re

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LineItemMapping:
    """Mapping configuration for a standard line item."""
    
    template_id: str  # e.g., "is:revenue"
    template_label: str  # e.g., "Revenue"
    aliases: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    exclude_keywords: List[str] = field(default_factory=list)
    is_subtraction: bool = False  # For items that reduce parent (e.g., discounts)


@dataclass
class AggregatedItem:
    """Result of aggregating extracted line items."""
    
    template_label: str
    values: Dict[int, Decimal]  # {year: value}
    source_items: List[str]  # Original labels that were aggregated
    confidence: float


class GAAPAggregator:
    """
    Consolidates diverse PDF line items to standard template categories.
    
    Uses GAAP-compliant logic to map variations like "Net Sales", "Gross Revenue",
    "Total Sales" all to the standard "Revenue" category.
    """
    
    # Income Statement Mappings
    IS_MAPPINGS: List[LineItemMapping] = [
        # Revenue Section
        LineItemMapping(
            template_id="is:product_revenue",
            template_label="Products",
            aliases=["product sales", "product revenue", "merchandise sales", "goods sold", "sales - products"],
            keywords=["product", "merchandise", "goods"],
        ),
        LineItemMapping(
            template_id="is:service_revenue",
            template_label="Services",
            aliases=["service revenue", "service sales", "service income", "consulting", "professional fees"],
            keywords=["service", "consulting", "professional"],
        ),
        LineItemMapping(
            template_id="is:total_revenue",
            template_label="Total Revenue",
            aliases=["revenue", "net revenue", "total sales", "net sales", "gross revenue", "sales"],
            keywords=["total revenue", "net revenue", "total sales"],
        ),
        
        # Cost of Goods Sold Section
        LineItemMapping(
            template_id="is:cogs_products",
            template_label="Products",
            aliases=["cost of products", "cost of goods", "product costs", "merchandise cost"],
            keywords=["cost", "product"],
        ),
        LineItemMapping(
            template_id="is:cogs_services",
            template_label="Services",
            aliases=["cost of services", "service costs", "direct labor"],
            keywords=["cost", "service"],
        ),
        LineItemMapping(
            template_id="is:total_cogs",
            template_label="Total Cost of Goods Sold",
            aliases=["cogs", "cost of goods sold", "cost of sales", "cost of revenue", "total cogs"],
            keywords=["cost of goods", "cost of sales", "cogs"],
        ),
        
        # Operating Expenses Section
        LineItemMapping(
            template_id="is:rd_expense",
            template_label="Research & Development",
            aliases=["r&d", "research and development", "research & development", "r & d", "development costs"],
            keywords=["research", "development", "r&d"],
        ),
        LineItemMapping(
            template_id="is:sga_expense",
            template_label="Selling, General, and Administrative",
            aliases=["sg&a", "sga", "selling general administrative", "general and administrative", "g&a", "admin expenses"],
            keywords=["selling", "general", "administrative", "sg&a", "g&a"],
        ),
        LineItemMapping(
            template_id="is:total_opex",
            template_label="Total Operating Expenses",
            aliases=["operating expenses", "total opex", "opex", "total operating expenses"],
            keywords=["operating expense", "opex"],
        ),
        
        # Other Income/Expenses
        LineItemMapping(
            template_id="is:other_income_expense",
            template_label="Other Income/(Expenses), Net",
            aliases=["other income", "other expense", "other income expense", "non-operating", "interest expense", "interest income"],
            keywords=["other", "non-operating", "interest"],
        ),
        
        # Tax
        LineItemMapping(
            template_id="is:income_tax",
            template_label="Provision for Income Taxes",
            aliases=["income tax", "tax expense", "provision for taxes", "income tax expense", "taxes"],
            keywords=["tax", "provision"],
        ),
    ]
    
    def __init__(self):
        """Initialize the aggregator with mapping indices."""
        self._build_indices()
    
    def _build_indices(self) -> None:
        """Build lookup indices for efficient matching."""
        self._alias_index: Dict[str, LineItemMapping] = {}
        self._keyword_index: Dict[str, List[LineItemMapping]] = {}
        
        for mapping in self.IS_MAPPINGS:
            # Index by normalized aliases
            for alias in mapping.aliases:
                normalized = self._normalize(alias)
                self._alias_index[normalized] = mapping
            
            # Index by keywords
            for keyword in mapping.keywords:
                normalized = self._normalize(keyword)
                if normalized not in self._keyword_index:
                    self._keyword_index[normalized] = []
                self._keyword_index[normalized].append(mapping)
    
    def _normalize(self, text: str) -> str:
        """Normalize text for matching."""
        # Lowercase, remove extra whitespace, remove special chars
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def match_line_item(self, label: str) -> Optional[LineItemMapping]:
        """
        Find the best matching template category for an extracted label.
        
        Args:
            label: Extracted line item label from PDF.
            
        Returns:
            Best matching LineItemMapping, or None if no match.
        """
        normalized = self._normalize(label)
        
        # 1. Exact alias match
        if normalized in self._alias_index:
            return self._alias_index[normalized]
        
        # 2. Substring alias match
        for alias, mapping in self._alias_index.items():
            if alias in normalized or normalized in alias:
                return mapping
        
        # 3. Keyword match
        best_match: Optional[LineItemMapping] = None
        best_score = 0
        
        for keyword, mappings in self._keyword_index.items():
            if keyword in normalized:
                for mapping in mappings:
                    # Check exclusions
                    excluded = False
                    for exclude in mapping.exclude_keywords:
                        if exclude.lower() in normalized:
                            excluded = True
                            break
                    
                    if not excluded:
                        score = len(keyword)
                        if score > best_score:
                            best_score = score
                            best_match = mapping
        
        return best_match
    
    def aggregate(
        self,
        extracted_items: List[Dict],
        periods: List[int],
    ) -> Dict[str, AggregatedItem]:
        """
        Aggregate extracted line items into template categories.
        
        Args:
            extracted_items: List of dicts with 'label' and period values.
            periods: List of years/periods in the data.
            
        Returns:
            Dict mapping template labels to aggregated values.
        """
        logger.info("Aggregating line items", count=len(extracted_items), periods=periods)
        
        # Group by template category
        aggregations: Dict[str, AggregatedItem] = {}
        
        for item in extracted_items:
            label = item.get("label", "")
            mapping = self.match_line_item(label)
            
            if mapping:
                template_label = mapping.template_label
                
                if template_label not in aggregations:
                    aggregations[template_label] = AggregatedItem(
                        template_label=template_label,
                        values={year: Decimal("0") for year in periods},
                        source_items=[],
                        confidence=0.0,
                    )
                
                # Add values for each period
                for year in periods:
                    year_key = str(year)
                    if year_key in item:
                        value = item[year_key]
                        if isinstance(value, (int, float, Decimal)):
                            aggregations[template_label].values[year] += Decimal(str(value))
                
                aggregations[template_label].source_items.append(label)
                
                logger.debug(
                    "Matched line item",
                    source=label,
                    target=template_label,
                )
            else:
                logger.warning("No match for line item", label=label)
        
        # Calculate confidence based on source item count
        for agg in aggregations.values():
            agg.confidence = min(1.0, len(agg.source_items) * 0.2)
        
        logger.info(
            "Aggregation complete",
            categories=len(aggregations),
            total_sources=sum(len(a.source_items) for a in aggregations.values()),
        )
        
        return aggregations


# Singleton instance
_aggregator_instance: Optional[GAAPAggregator] = None


def get_gaap_aggregator() -> GAAPAggregator:
    """Get singleton GAAPAggregator instance."""
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = GAAPAggregator()
    return _aggregator_instance
