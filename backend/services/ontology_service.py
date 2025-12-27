"""
Ontology service for loading and querying financial line item taxonomy.

Provides lookup by ID, label, alias, and category.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import structlog
import yaml

logger = structlog.get_logger(__name__)


@dataclass
class OntologyItem:
    """Represents a single item in the financial ontology."""

    id: str
    label: str
    aliases: List[str] = field(default_factory=list)
    category: str = ""
    parent: Optional[str] = None
    formula: Optional[str] = None
    statement_type: str = ""  # income_statement, balance_sheet, cash_flow, ratios

    @property
    def all_names(self) -> List[str]:
        """Get all possible names for this item (label + aliases)."""
        return [self.label] + self.aliases

    @property
    def all_names_lower(self) -> List[str]:
        """Get all names in lowercase for matching."""
        return [name.lower() for name in self.all_names]


@dataclass
class ClassificationResult:
    """Result of classifying a line item."""

    item: Optional[OntologyItem]
    confidence: float
    match_type: str  # exact, alias, fuzzy, embedding, llm
    candidates: List[tuple] = field(default_factory=list)  # [(item, score), ...]


class OntologyService:
    """
    Service for managing and querying the financial ontology.

    Loads ontology from YAML and provides efficient lookup methods.
    """

    def __init__(self, ontology_path: Optional[Path] = None):
        """
        Initialize ontology service.

        Args:
            ontology_path: Path to ontology YAML file.
        """
        self._items: Dict[str, OntologyItem] = {}
        self._label_index: Dict[str, OntologyItem] = {}
        self._alias_index: Dict[str, OntologyItem] = {}
        self._category_index: Dict[str, List[OntologyItem]] = {}
        self._statement_index: Dict[str, List[OntologyItem]] = {}

        if ontology_path is None:
            # Default path relative to project root
            ontology_path = Path(__file__).parent.parent.parent / "data" / "ontology.yaml"

        self._load_ontology(ontology_path)

    def _load_ontology(self, path: Path) -> None:
        """
        Load ontology from YAML file.

        Args:
            path: Path to ontology YAML file.
        """
        logger.info("Loading ontology", path=str(path))

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Process each statement type
            for statement_type in ["income_statement", "balance_sheet", "cash_flow", "ratios"]:
                if statement_type not in data:
                    continue

                statement_data = data[statement_type]

                # Handle different structures (categories vs direct items)
                if isinstance(statement_data, dict):
                    for category_name, category_data in statement_data.items():
                        if category_name == "description":
                            continue

                        if isinstance(category_data, list):
                            self._process_items(category_data, statement_type, category_name)
                        elif isinstance(category_data, dict):
                            # Some categories might have nested structure
                            for key, value in category_data.items():
                                if isinstance(value, list):
                                    self._process_items(value, statement_type, category_name)

            logger.info(
                "Ontology loaded",
                total_items=len(self._items),
                labels=len(self._label_index),
                aliases=len(self._alias_index),
            )

        except Exception as e:
            logger.error("Failed to load ontology", path=str(path), error=str(e))
            raise

    def _process_items(
        self, items: List[Dict], statement_type: str, category: str
    ) -> None:
        """
        Process a list of ontology items.

        Args:
            items: List of item dictionaries.
            statement_type: Statement type (income_statement, etc.).
            category: Category within statement type.
        """
        for item_data in items:
            if not isinstance(item_data, dict) or "id" not in item_data:
                continue

            item = OntologyItem(
                id=item_data["id"],
                label=item_data.get("label", ""),
                aliases=item_data.get("aliases", []),
                category=item_data.get("category", category),
                parent=item_data.get("parent"),
                formula=item_data.get("formula"),
                statement_type=statement_type,
            )

            # Add to main index
            self._items[item.id] = item

            # Add to label index (lowercase)
            label_lower = item.label.lower()
            self._label_index[label_lower] = item

            # Add to alias index (lowercase)
            for alias in item.aliases:
                alias_lower = alias.lower()
                self._alias_index[alias_lower] = item

            # Add to category index
            if item.category not in self._category_index:
                self._category_index[item.category] = []
            self._category_index[item.category].append(item)

            # Add to statement index
            if statement_type not in self._statement_index:
                self._statement_index[statement_type] = []
            self._statement_index[statement_type].append(item)

    def get_by_id(self, item_id: str) -> Optional[OntologyItem]:
        """
        Get item by ID.

        Args:
            item_id: Ontology item ID (e.g., "is:revenue").

        Returns:
            OntologyItem if found, None otherwise.
        """
        return self._items.get(item_id)

    def get_by_label(self, label: str) -> Optional[OntologyItem]:
        """
        Get item by exact label match (case-insensitive).

        Args:
            label: Label to search for.

        Returns:
            OntologyItem if found, None otherwise.
        """
        return self._label_index.get(label.lower())

    def get_by_alias(self, alias: str) -> Optional[OntologyItem]:
        """
        Get item by alias match (case-insensitive).

        Args:
            alias: Alias to search for.

        Returns:
            OntologyItem if found, None otherwise.
        """
        return self._alias_index.get(alias.lower())

    def get_by_name(self, name: str) -> Optional[OntologyItem]:
        """
        Get item by any name (label or alias, case-insensitive).

        Args:
            name: Name to search for.

        Returns:
            OntologyItem if found, None otherwise.
        """
        name_lower = name.lower().strip()

        # Try exact label match first
        if name_lower in self._label_index:
            return self._label_index[name_lower]

        # Try alias match
        if name_lower in self._alias_index:
            return self._alias_index[name_lower]

        return None

    def get_by_category(self, category: str) -> List[OntologyItem]:
        """
        Get all items in a category.

        Args:
            category: Category name.

        Returns:
            List of items in the category.
        """
        return self._category_index.get(category, [])

    def get_by_statement(self, statement_type: str) -> List[OntologyItem]:
        """
        Get all items for a statement type.

        Args:
            statement_type: Statement type (income_statement, balance_sheet, cash_flow, ratios).

        Returns:
            List of items for the statement type.
        """
        return self._statement_index.get(statement_type, [])

    def get_all_items(self) -> List[OntologyItem]:
        """Get all ontology items."""
        return list(self._items.values())

    def get_all_labels(self) -> List[str]:
        """Get all unique labels."""
        return [item.label for item in self._items.values()]

    def get_all_names(self) -> List[str]:
        """Get all names (labels + aliases)."""
        names = []
        for item in self._items.values():
            names.extend(item.all_names)
        return names

    def search(self, query: str, limit: int = 10) -> List[OntologyItem]:
        """
        Search for items matching query (fuzzy).

        Args:
            query: Search query.
            limit: Maximum results to return.

        Returns:
            List of matching items.
        """
        query_lower = query.lower().strip()
        matches = []

        for item in self._items.values():
            # Check if query is substring of any name
            for name in item.all_names_lower:
                if query_lower in name or name in query_lower:
                    matches.append(item)
                    break

        return matches[:limit]

    @property
    def item_count(self) -> int:
        """Get total number of items."""
        return len(self._items)


# Singleton instance
_ontology_instance: Optional[OntologyService] = None


def get_ontology_service() -> OntologyService:
    """Get singleton OntologyService instance."""
    global _ontology_instance
    if _ontology_instance is None:
        _ontology_instance = OntologyService()
    return _ontology_instance
