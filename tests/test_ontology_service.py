"""
Unit tests for OntologyService.
"""
import pytest

from backend.services.ontology_service import OntologyService, get_ontology_service


class TestOntologyService:
    """Tests for OntologyService."""

    @pytest.fixture
    def ontology(self) -> OntologyService:
        """Get ontology service instance."""
        return get_ontology_service()

    def test_ontology_loads(self, ontology: OntologyService):
        """Test that ontology loads successfully."""
        assert ontology is not None
        assert ontology.item_count > 0

    def test_has_income_statement_items(self, ontology: OntologyService):
        """Test ontology has income statement items."""
        items = ontology.get_by_statement("income_statement")
        assert len(items) > 50  # Should have many IS items

    def test_has_balance_sheet_items(self, ontology: OntologyService):
        """Test ontology has balance sheet items."""
        items = ontology.get_by_statement("balance_sheet")
        assert len(items) > 50

    def test_has_cash_flow_items(self, ontology: OntologyService):
        """Test ontology has cash flow items."""
        items = ontology.get_by_statement("cash_flow")
        assert len(items) > 20

    def test_get_by_id(self, ontology: OntologyService):
        """Test get item by ID."""
        item = ontology.get_by_id("is:revenue")
        assert item is not None
        assert item.label == "Revenue"

    def test_get_by_label(self, ontology: OntologyService):
        """Test get item by exact label."""
        item = ontology.get_by_label("Revenue")
        assert item is not None
        assert item.id == "is:revenue"

    def test_get_by_label_case_insensitive(self, ontology: OntologyService):
        """Test get item by label is case insensitive."""
        item = ontology.get_by_label("REVENUE")
        assert item is not None
        assert item.id == "is:revenue"

    def test_get_by_alias(self, ontology: OntologyService):
        """Test get item by alias."""
        item = ontology.get_by_alias("Sales")
        assert item is not None
        assert item.id == "is:revenue"

    def test_get_by_alias_cogs(self, ontology: OntologyService):
        """Test COGS alias."""
        item = ontology.get_by_alias("COGS")
        assert item is not None
        assert "cogs" in item.id.lower() or "cost" in item.label.lower()

    def test_get_by_name(self, ontology: OntologyService):
        """Test get by name (label or alias)."""
        # By label
        item1 = ontology.get_by_name("Revenue")
        assert item1 is not None

        # By alias
        item2 = ontology.get_by_name("Net Sales")
        assert item2 is not None
        assert item1.id == item2.id

    def test_get_all_items(self, ontology: OntologyService):
        """Test get all items."""
        items = ontology.get_all_items()
        assert len(items) > 100  # Should have many items

    def test_search(self, ontology: OntologyService):
        """Test search functionality."""
        results = ontology.search("revenue")
        assert len(results) > 0
        assert any("revenue" in item.label.lower() for item in results)

    def test_balance_sheet_items(self, ontology: OntologyService):
        """Test balance sheet item lookup."""
        cash = ontology.get_by_id("bs:cash")
        assert cash is not None
        assert "cash" in cash.label.lower()

        ar = ontology.get_by_alias("A/R")
        assert ar is not None

    def test_cash_flow_items(self, ontology: OntologyService):
        """Test cash flow item lookup."""
        cfo = ontology.get_by_id("cf:cfo")
        assert cfo is not None

        capex = ontology.get_by_alias("CapEx")
        assert capex is not None


class TestOntologyItem:
    """Tests for OntologyItem properties."""

    @pytest.fixture
    def ontology(self) -> OntologyService:
        return get_ontology_service()

    def test_all_names_property(self, ontology: OntologyService):
        """Test all_names includes label and aliases."""
        item = ontology.get_by_id("is:revenue")
        assert item is not None

        all_names = item.all_names
        assert "Revenue" in all_names
        assert "Sales" in all_names

    def test_all_names_lower(self, ontology: OntologyService):
        """Test all_names_lower returns lowercase."""
        item = ontology.get_by_id("is:revenue")
        assert item is not None

        lower_names = item.all_names_lower
        assert all(name == name.lower() for name in lower_names)
