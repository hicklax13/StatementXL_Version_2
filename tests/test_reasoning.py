import pytest
from backend.services.gaap_classifier import GaapClassifier

@pytest.mark.asyncio
class TestReasoningLogic:
    """Test the reasoning capabilities for ambiguous line items."""
    
    async def test_reasoning_ahca_fees(self):
        """Test that 'AHCA Fees' (ambiguous) is correctly reasoned as SG&A."""
        classifier = GaapClassifier()
        
        # AHCA Fees = Agency for Health Care Administration (Regulatory/License fee)
        # Should be Operating Expense / SG&A
        items = [{"label": "AHCA Fees", "value": 1200.0}]
        
        results = await classifier.classify_items(items, statement_type="income_statement")
        
        assert len(results) == 1
        c = results[0]
        
        print(f"Classified as: {c.category} / {c.template_row} (Conf: {c.confidence})")
        print(f"Reasoning: {c.reasoning}")
        
        assert c.category == "operating_expenses"
        assert c.template_row == "Selling, General, and Administrative"
        # We expect a high confidence after reasoning
        assert c.confidence > 0.85
        # We expect the reasoning field to be populated
        assert c.reasoning is not None
        assert len(c.reasoning) > 10

    async def test_reasoning_amazon_purchase(self):
        """Test that 'Amazon' (very generic) is reasoned based on likely context."""
        classifier = GaapClassifier()
        
        # Generic vendor, likely office supplies -> SG&A
        items = [{"label": "Amazon Mktp Purchase", "value": 45.99}]
        
        results = await classifier.classify_items(items, statement_type="income_statement")
        
        c = results[0]
        assert c.category == "operating_expenses"
        assert c.template_row == "Selling, General, and Administrative"
        # Reasoning might be None if primary classifier was confident (which is good!)

    async def test_reasoning_zelle_transfer(self):
        """Test reasoning for difficult transfer items."""
        classifier = GaapClassifier()
        
        items = [{"label": "Zelle Transfer to J. Smith", "value": 500.0}]
        
        results = await classifier.classify_items(items, statement_type="income_statement")
        
        c = results[0]
        # This is tough, but likely Contractor (OpEx) or Draw (Equity)
        # We at least want it to NOT be Revenue
        print(f"Zelle Classification: {c.category} (Conf: {c.confidence})")
        assert c.category != "revenue"

