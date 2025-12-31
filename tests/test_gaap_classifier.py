"""
Unit Tests for GAAP Classifier

Tests the fine-tuned GAAP classifier including:
- Section detection from PDF text
- Rule-based classification with section context
- Aggregation by category
- Healthcare/service industry patterns
"""

import pytest
from unittest.mock import patch, MagicMock
import asyncio

from backend.services.gaap_classifier import (
    GaapClassifier,
    Classification,
    get_gaap_classifier,
)


class TestSectionDetection:
    """Test enhanced section detection from PDF text."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    def test_detect_income_section(self):
        """Test detection of items under Income section."""
        raw_text = """Income
210 Social Security 133,058.90
220 Medicaid 120,437.20
Total Income 253,796.10
Expenses
310 Payroll 50,055.00"""
        
        section_map = self.classifier._detect_sections_enhanced(raw_text)
        
        assert "210 Social Security 133,058.90" in section_map
        assert section_map["210 Social Security 133,058.90"] == "income"
        assert "220 Medicaid 120,437.20" in section_map
        assert section_map["220 Medicaid 120,437.20"] == "income"
    
    def test_detect_expense_section(self):
        """Test detection of items under Expenses section."""
        raw_text = """Income
210 Social Security 133,058.90
Total Income 253,796.10
Expenses
310 Payroll 50,055.00
420 Bank fees 331.21"""
        
        section_map = self.classifier._detect_sections_enhanced(raw_text)
        
        assert "310 Payroll 50,055.00" in section_map
        assert section_map["310 Payroll 50,055.00"] == "expenses"
        assert "420 Bank fees 331.21" in section_map
        assert section_map["420 Bank fees 331.21"] == "expenses"
    
    def test_skip_totals(self):
        """Test that total rows are skipped in section detection."""
        raw_text = """Income
210 Social Security 133,058.90
Total Income 253,796.10
Expenses
Total Expenses 337,754.64"""
        
        section_map = self.classifier._detect_sections_enhanced(raw_text)
        
        # Totals should not be in the map
        assert "Total Income 253,796.10" not in section_map
        assert "Total Expenses 337,754.64" not in section_map
    
    def test_empty_text(self):
        """Test handling of empty text."""
        section_map = self.classifier._detect_sections_enhanced("")
        assert section_map == {}
    
    def test_no_sections(self):
        """Test handling of text without section headers."""
        raw_text = """Some random text
Without section headers
Just values"""
        
        section_map = self.classifier._detect_sections_enhanced(raw_text)
        assert section_map == {}


class TestRuleBasedClassification:
    """Test enhanced rule-based classification."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    def test_income_section_classifies_as_revenue(self):
        """Items in income section should classify as revenue."""
        result = self.classifier._classify_with_enhanced_rules(
            label="210 Social Security",
            value=133058.90,
            statement_type="income_statement",
            section_context="income"
        )
        
        assert result.category == "revenue"
        assert result.template_row == "Services"
        assert result.confidence >= 0.9
    
    def test_expense_section_classifies_as_operating_expenses(self):
        """Items in expense section should classify as operating expenses."""
        result = self.classifier._classify_with_enhanced_rules(
            label="310 Payroll, Administrator",
            value=50055.00,
            statement_type="income_statement",
            section_context="expenses"
        )
        
        assert result.category == "operating_expenses"
        assert result.template_row == "Selling, General, and Administrative"
        assert result.confidence >= 0.9
    
    def test_interest_classifies_as_other(self):
        """Interest expenses should classify as Other Income/Expenses."""
        result = self.classifier._classify_with_enhanced_rules(
            label="550 Mortgage Interest",
            value=53478.96,
            statement_type="income_statement",
            section_context="expenses"
        )
        
        assert result.category == "other_income_expenses"
        assert result.template_row == "Other Income/(Expenses), Net"
        assert result.confidence >= 0.9
    
    def test_total_income_classifies_as_calculated(self):
        """Total rows should classify as calculated."""
        result = self.classifier._classify_with_enhanced_rules(
            label="Total Income",
            value=253796.10,
            statement_type="income_statement",
            section_context=None
        )
        
        assert result.category == "calculated"
        assert result.template_row is None
        assert result.confidence >= 0.95
    
    def test_healthcare_revenue_keywords(self):
        """Healthcare revenue keywords should classify as revenue without section context."""
        keywords = ["Social Security", "Medicaid", "Medicare", "Patient fees"]
        
        for keyword in keywords:
            result = self.classifier._classify_with_enhanced_rules(
                label=f"100 {keyword}",
                value=10000.00,
                statement_type="income_statement",
                section_context=None  # No section context
            )
            
            assert result.category == "revenue", f"Failed for {keyword}"
            assert result.template_row == "Services"
    
    def test_bank_fees_as_expense(self):
        """Bank fees should classify as operating expense."""
        result = self.classifier._classify_with_enhanced_rules(
            label="420 Bank fees",
            value=331.21,
            statement_type="income_statement",
            section_context="expenses"
        )
        
        assert result.category == "operating_expenses"
        assert result.template_row == "Selling, General, and Administrative"


class TestAggregation:
    """Test aggregation by category."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    def test_aggregate_revenue(self):
        """Test aggregation of revenue items."""
        classifications = [
            Classification(
                original_label="Social Security",
                original_value=133058.90,
                category="revenue",
                template_row="Services",
                confidence=0.95,
            ),
            Classification(
                original_label="Medicaid",
                original_value=120437.20,
                category="revenue",
                template_row="Services",
                confidence=0.95,
            ),
        ]
        
        aggregated = self.classifier.aggregate_by_category(classifications)
        
        assert "Services" in aggregated
        assert aggregated["Services"] == pytest.approx(253496.10, rel=1e-2)
    
    def test_aggregate_expenses(self):
        """Test aggregation of expense items."""
        classifications = [
            Classification(
                original_label="Payroll",
                original_value=50055.00,
                category="operating_expenses",
                template_row="Selling, General, and Administrative",
                confidence=0.95,
            ),
            Classification(
                original_label="Bank fees",
                original_value=331.21,
                category="operating_expenses",
                template_row="Selling, General, and Administrative",
                confidence=0.95,
            ),
        ]
        
        aggregated = self.classifier.aggregate_by_category(classifications)
        
        assert "Selling, General, and Administrative" in aggregated
        assert aggregated["Selling, General, and Administrative"] == pytest.approx(50386.21, rel=1e-2)
    
    def test_skip_calculated_rows(self):
        """Test that calculated rows are not aggregated."""
        classifications = [
            Classification(
                original_label="Revenue item",
                original_value=100000.00,
                category="revenue",
                template_row="Services",
                confidence=0.95,
            ),
            Classification(
                original_label="Total Income",
                original_value=100000.00,
                category="calculated",
                template_row=None,
                confidence=0.95,
            ),
        ]
        
        aggregated = self.classifier.aggregate_by_category(classifications)
        
        assert "Services" in aggregated
        assert aggregated["Services"] == 100000.00
        # Total Income should not be aggregated
        assert None not in aggregated
    
    def test_skip_none_values(self):
        """Test that items with None values are skipped."""
        classifications = [
            Classification(
                original_label="Section Header",
                original_value=None,  # No value
                category="revenue",
                template_row="Services",
                confidence=0.95,
            ),
            Classification(
                original_label="Real Revenue",
                original_value=100000.00,
                category="revenue",
                template_row="Services",
                confidence=0.95,
            ),
        ]
        
        aggregated = self.classifier.aggregate_by_category(classifications)
        
        assert aggregated["Services"] == 100000.00


class TestClassifyItemsAsync:
    """Test async classify_items method."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    @pytest.mark.asyncio
    async def test_classify_with_section_context(self):
        """Test classification using section context from raw text."""
        raw_text = """Income
210 Social Security 133,058.90
220 Medicaid 120,437.20
Expenses
310 Payroll 50,055.00
420 Bank fees 331.21"""
        
        items = [
            {"label": "210 Social Security", "value": 133058.90},
            {"label": "220 Medicaid", "value": 120437.20},
            {"label": "310 Payroll", "value": 50055.00},
            {"label": "420 Bank fees", "value": 331.21},
        ]
        
        # Mock Gemini and Ollama to force rule-based
        self.classifier._gemini_model = None
        self.classifier._ollama_available = False
        
        results = await self.classifier.classify_items(items, "income_statement", raw_text)
        
        assert len(results) == 4
        
        # Check Social Security is revenue
        ss = next(r for r in results if "Social Security" in r.original_label)
        assert ss.category == "revenue"
        
        # Check Payroll is expense
        payroll = next(r for r in results if "Payroll" in r.original_label)
        assert payroll.category == "operating_expenses"
    
    @pytest.mark.asyncio
    async def test_classify_without_raw_text(self):
        """Test classification without raw text falls back to keyword matching."""
        items = [
            {"label": "Medicare Revenue", "value": 50000.00},
            {"label": "Mortgage Interest", "value": 10000.00},
        ]
        
        self.classifier._gemini_model = None
        self.classifier._ollama_available = False
        
        results = await self.classifier.classify_items(items, "income_statement", None)
        
        assert len(results) == 2
        
        # Medicare should be classified as revenue (keyword match)
        medicare = next(r for r in results if "Medicare" in r.original_label)
        assert medicare.category == "revenue"
        
        # Mortgage Interest should be Other
        interest = next(r for r in results if "Mortgage" in r.original_label)
        assert interest.category == "other_income_expenses"


class TestSingleton:
    """Test singleton pattern."""
    
    def test_get_gaap_classifier_returns_same_instance(self):
        """Test that get_gaap_classifier returns the same instance."""
        # Reset singleton
        import backend.services.gaap_classifier as module
        module._classifier_instance = None
        
        instance1 = get_gaap_classifier()
        instance2 = get_gaap_classifier()
        
        assert instance1 is instance2


class TestHealthcareIndustry:
    """Test healthcare-specific classification patterns."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    def test_healthcare_revenue_items(self):
        """Test healthcare revenue items are correctly classified."""
        healthcare_items = [
            ("Social Security income", "revenue"),
            ("Medicaid payments", "revenue"),
            ("Medicare reimbursement", "revenue"),
            ("Patient fees", "revenue"),
            ("Resident charges", "revenue"),
        ]
        
        for label, expected_category in healthcare_items:
            result = self.classifier._classify_with_enhanced_rules(
                label=label,
                value=10000.00,
                statement_type="income_statement",
                section_context=None
            )
            
            assert result.category == expected_category, f"Failed for {label}"
    
    def test_healthcare_expense_items(self):
        """Test healthcare expense items are correctly classified."""
        expense_items = [
            ("310 Payroll, CNA", "operating_expenses"),
            ("320 Payroll, Administrator", "operating_expenses"),
            ("430 AHCA fees", "operating_expenses"),
            ("530 Insurance, Property", "operating_expenses"),
            ("620 Electricity", "operating_expenses"),
        ]
        
        for label, expected_category in expense_items:
            result = self.classifier._classify_with_enhanced_rules(
                label=label,
                value=10000.00,
                statement_type="income_statement",
                section_context="expenses"
            )
            
            assert result.category == expected_category, f"Failed for {label}"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    def test_empty_label(self):
        """Test handling of empty label."""
        result = self.classifier._classify_with_enhanced_rules(
            label="",
            value=1000.00,
            statement_type="income_statement",
            section_context=None
        )
        
        # Should default to operating expenses
        assert result.category == "operating_expenses"
    
    def test_none_value(self):
        """Test handling of None value."""
        result = self.classifier._classify_with_enhanced_rules(
            label="Some Item",
            value=None,
            statement_type="income_statement",
            section_context=None
        )
        
        assert result.original_value is None
    
    def test_special_characters_in_label(self):
        """Test handling of special characters in label."""
        result = self.classifier._classify_with_enhanced_rules(
            label="450 Legal & Professional Fees",
            value=8445.31,
            statement_type="income_statement",
            section_context="expenses"
        )
        
        assert result.category == "operating_expenses"
    
    def test_numeric_prefix_in_label(self):
        """Test handling of account codes in label."""
        result = self.classifier._classify_with_enhanced_rules(
            label="210 Social Security",
            value=133058.90,
            statement_type="income_statement",
            section_context="income"
        )
        
        assert result.category == "revenue"
        assert result.original_label == "210 Social Security"


class TestStatementTypeDetection:
    """Test automatic statement type detection from PDF text."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    def test_detect_income_statement(self):
        """Test detection of Income Statement from text."""
        text = """Income Statement
        For the Year Ended December 31, 2024
        Revenue: 1,000,000
        Cost of Goods Sold: 500,000
        Gross Profit: 500,000
        Operating Expenses: 200,000
        Net Income: 300,000"""
        
        result = self.classifier.detect_statement_type(text)
        assert result == "income_statement"
    
    def test_detect_balance_sheet(self):
        """Test detection of Balance Sheet from text."""
        text = """Balance Sheet
        As of December 31, 2024
        Total Assets: 5,000,000
        Current Assets: 1,500,000
        Total Liabilities: 2,000,000
        Shareholders' Equity: 3,000,000
        Retained Earnings: 1,500,000"""
        
        result = self.classifier.detect_statement_type(text)
        assert result == "balance_sheet"
    
    def test_detect_cash_flow(self):
        """Test detection of Cash Flow Statement from text."""
        text = """Statement of Cash Flows
        For the Year Ended December 31, 2024
        Cash Flows from Operating Activities
        Net Income: 300,000
        Depreciation and Amortization: 50,000
        Cash Flows from Investing Activities
        Capital Expenditure: (100,000)
        Cash Flows from Financing Activities
        Dividends Paid: (50,000)"""
        
        result = self.classifier.detect_statement_type(text)
        assert result == "cash_flow"
    
    def test_detect_empty_text_defaults_to_income_statement(self):
        """Test that empty text defaults to income_statement."""
        result = self.classifier.detect_statement_type("")
        assert result == "income_statement"
    
    def test_detect_low_confidence_defaults_to_income_statement(self):
        """Test that low confidence matches default to income_statement."""
        text = "Random text without any financial keywords"
        result = self.classifier.detect_statement_type(text)
        assert result == "income_statement"
    
    def test_detect_profit_and_loss(self):
        """Test detection of P&L (alternative name for Income Statement)."""
        text = "Profit and Loss Statement for Q4 2024"
        result = self.classifier.detect_statement_type(text)
        assert result == "income_statement"
    
    def test_detect_statement_of_financial_position(self):
        """Test detection using formal IFRS terminology."""
        text = "Statement of Financial Position as of December 31, 2024"
        result = self.classifier.detect_statement_type(text)
        assert result == "balance_sheet"


class TestBalanceSheetClassification:
    """Test Balance Sheet item classification."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    def test_cash_classifies_as_current_asset(self):
        """Test cash and equivalents classification."""
        result = self.classifier._classify_balance_sheet_item(
            label="Cash and Cash Equivalents",
            value=100000.00,
            section_context="assets"
        )
        
        assert result.category == "current_assets"
        assert result.template_row == "Cash and Cash Equivalents"
    
    def test_accounts_receivable(self):
        """Test accounts receivable classification."""
        result = self.classifier._classify_balance_sheet_item(
            label="Accounts Receivable, Net",
            value=50000.00,
            section_context="assets"
        )
        
        assert result.category == "current_assets"
        assert result.template_row == "Accounts Receivable"
    
    def test_inventory(self):
        """Test inventory classification."""
        result = self.classifier._classify_balance_sheet_item(
            label="Inventory - Raw Materials",
            value=25000.00,
            section_context="assets"
        )
        
        assert result.category == "current_assets"
        assert result.template_row == "Inventory"
    
    def test_ppe_classifies_as_noncurrent_asset(self):
        """Test PP&E classification."""
        result = self.classifier._classify_balance_sheet_item(
            label="Property, Plant and Equipment",
            value=500000.00,
            section_context="assets"
        )
        
        assert result.category == "noncurrent_assets"
        assert result.template_row == "Property, Plant and Equipment"
    
    def test_accounts_payable_classifies_as_current_liability(self):
        """Test accounts payable classification."""
        result = self.classifier._classify_balance_sheet_item(
            label="Accounts Payable",
            value=30000.00,
            section_context="liabilities"
        )
        
        assert result.category == "current_liabilities"
        assert result.template_row == "Accounts Payable"
    
    def test_long_term_debt(self):
        """Test long-term debt classification."""
        result = self.classifier._classify_balance_sheet_item(
            label="Long-Term Debt",
            value=1000000.00,
            section_context="liabilities"
        )
        
        assert result.category == "noncurrent_liabilities"
        assert result.template_row == "Long-Term Debt"
    
    def test_retained_earnings_classifies_as_equity(self):
        """Test retained earnings classification."""
        result = self.classifier._classify_balance_sheet_item(
            label="Retained Earnings",
            value=800000.00,
            section_context="equity"
        )
        
        assert result.category == "equity"
        assert result.template_row == "Retained Earnings"
    
    def test_common_stock(self):
        """Test common stock classification."""
        result = self.classifier._classify_balance_sheet_item(
            label="Common Stock",
            value=100000.00,
            section_context="equity"
        )
        
        assert result.category == "equity"
        assert result.template_row == "Common Stock"


class TestCashFlowClassification:
    """Test Cash Flow Statement item classification."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    def test_depreciation_classifies_as_operating(self):
        """Test depreciation classification."""
        result = self.classifier._classify_cash_flow_item(
            label="Depreciation and Amortization",
            value=50000.00,
            section_context="operating"
        )
        
        assert result.category == "operating_activities"
        assert result.template_row == "Depreciation and Amortization"
    
    def test_change_in_accounts_receivable(self):
        """Test working capital change classification."""
        result = self.classifier._classify_cash_flow_item(
            label="Change in Accounts Receivable",
            value=-10000.00,
            section_context="operating"
        )
        
        assert result.category == "operating_activities"
        assert result.template_row == "Change in Accounts Receivable"
    
    def test_capex_classifies_as_investing(self):
        """Test capital expenditure classification."""
        result = self.classifier._classify_cash_flow_item(
            label="Capital Expenditures",
            value=-100000.00,
            section_context="investing"
        )
        
        assert result.category == "investing_activities"
        assert result.template_row == "Capital Expenditures"
    
    def test_debt_repayment_classifies_as_financing(self):
        """Test debt repayment classification."""
        result = self.classifier._classify_cash_flow_item(
            label="Repayment of Debt",
            value=-50000.00,
            section_context="financing"
        )
        
        assert result.category == "financing_activities"
        assert "Debt" in result.template_row or "Financing" in result.template_row
    
    def test_dividends_paid(self):
        """Test dividends paid classification."""
        result = self.classifier._classify_cash_flow_item(
            label="Dividends Paid",
            value=-25000.00,
            section_context="financing"
        )
        
        assert result.category == "financing_activities"
        assert result.template_row == "Dividends Paid"
    
    def test_net_cash_total_classifies_as_calculated(self):
        """Test that cash totals are classified as calculated."""
        result = self.classifier._classify_cash_flow_item(
            label="Net Cash from Operating Activities",
            value=200000.00,
            section_context=None
        )
        
        assert result.category == "calculated"


class TestYamlMappingIntegration:
    """Test YAML mapping loading and integration."""
    
    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()
    
    def test_is_mappings_loaded(self):
        """Test that Income Statement mappings are loaded."""
        assert self.classifier._is_mappings is not None
        assert len(self.classifier._is_mappings) > 0
    
    def test_bs_mappings_loaded(self):
        """Test that Balance Sheet mappings are loaded."""
        assert self.classifier._bs_mappings is not None
        assert len(self.classifier._bs_mappings) > 0
    
    def test_cf_mappings_loaded(self):
        """Test that Cash Flow mappings are loaded."""
        assert self.classifier._cf_mappings is not None
        assert len(self.classifier._cf_mappings) > 0
    
    def test_yaml_classification_returns_high_confidence(self):
        """Test that YAML classification returns high confidence."""
        result = self.classifier._classify_with_yaml(
            label="Subscription Revenue",
            value=10000.00,
            mappings=self.classifier._is_mappings,
            default_category="operating_expenses",
            default_template_row="SG&A"
        )
        
        assert result is not None
        assert result.confidence >= 0.8
    
    def test_yaml_classification_no_match_returns_none(self):
        """Test that no match returns None."""
        result = self.classifier._classify_with_yaml(
            label="XYZ123 Gibberish Item",
            value=100.00,
            mappings=self.classifier._is_mappings,
            default_category="operating_expenses",
            default_template_row="SG&A"
        )
        
        assert result is None
    
    def test_yaml_classification_normalizes_category(self):
        """Test that YAML categories are normalized to standard constants."""
        # Test that opex_sga gets normalized to operating_expenses
        result = self.classifier._classify_with_yaml(
            label="Legal Fees",
            value=5000.00,
            mappings=self.classifier._is_mappings,
            default_category="operating_expenses",
            default_template_row="SG&A"
        )

        if result:
            # Should be normalized to standard category constant
            assert result.category in [
                "operating_expenses", "revenue", "cogs",
                "other_income_expenses", "calculated"
            ]


class TestMultiStatementDetection:
    """Test multi-statement detection from PDF text."""

    def setup_method(self):
        """Create classifier instance for each test."""
        self.classifier = GaapClassifier()

    def test_detect_all_statements_income_only(self):
        """Test detection when only income statement is present."""
        text = """Income Statement
        For the Year Ended December 31, 2024
        Revenue: 1,000,000
        Net Income: 300,000"""

        result = self.classifier.detect_all_statement_types(text)

        assert len(result) >= 1
        assert result[0]["statement_type"] == "income_statement"
        assert result[0]["confidence"] > 0

    def test_detect_all_statements_balance_sheet_only(self):
        """Test detection when only balance sheet is present."""
        text = """Balance Sheet
        As of December 31, 2024
        Total Assets: 5,000,000
        Total Liabilities: 2,000,000
        Shareholders' Equity: 3,000,000"""

        result = self.classifier.detect_all_statement_types(text)

        assert len(result) >= 1
        statement_types = [r["statement_type"] for r in result]
        assert "balance_sheet" in statement_types

    def test_detect_all_statements_multi_statement_pdf(self):
        """Test detection when multiple statements are present (annual report)."""
        text = """Annual Report 2024

        Income Statement
        Revenue: 1,000,000
        Cost of Goods Sold: 400,000
        Gross Profit: 600,000
        Net Income: 200,000

        Balance Sheet
        Total Assets: 5,000,000
        Total Liabilities: 2,000,000
        Shareholders' Equity: 3,000,000
        Retained Earnings: 1,000,000

        Statement of Cash Flows
        Cash Flows from Operating Activities
        Net Income: 200,000
        Depreciation: 50,000
        Cash Flows from Investing Activities
        Capital Expenditures: (100,000)
        Cash Flows from Financing Activities
        Dividends Paid: (50,000)"""

        result = self.classifier.detect_all_statement_types(text)

        # Should detect all three statement types
        assert len(result) >= 3
        statement_types = [r["statement_type"] for r in result]
        assert "income_statement" in statement_types
        assert "balance_sheet" in statement_types
        assert "cash_flow" in statement_types

    def test_detect_all_statements_empty_text(self):
        """Test that empty text returns default income statement."""
        result = self.classifier.detect_all_statement_types("")

        assert len(result) == 1
        assert result[0]["statement_type"] == "income_statement"
        assert result[0]["confidence"] == 0.5

    def test_detect_all_statements_sorted_by_score(self):
        """Test that results are sorted by score descending."""
        text = """Balance Sheet
        Total Assets: 5,000,000
        Statement of Cash Flows
        Operating Activities"""

        result = self.classifier.detect_all_statement_types(text)

        if len(result) > 1:
            # Scores should be in descending order
            for i in range(len(result) - 1):
                assert result[i]["score"] >= result[i + 1]["score"]

    def test_detect_all_statements_confidence_normalized(self):
        """Test that confidence values are normalized between 0 and 1."""
        text = """Income Statement
        Revenue: 1,000,000
        Net Income: 300,000
        Gross Profit: 600,000
        Operating Income: 400,000"""

        result = self.classifier.detect_all_statement_types(text)

        for item in result:
            assert 0 <= item["confidence"] <= 1
