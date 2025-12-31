"""
QuickBooks Online integration service.

Provides OAuth2 flow and API access for QuickBooks Online.

To use this integration, you need:
1. Create a QuickBooks Developer account: https://developer.intuit.com
2. Create an app in the developer portal
3. Get your Client ID and Client Secret
4. Set environment variables:
   - QUICKBOOKS_CLIENT_ID
   - QUICKBOOKS_CLIENT_SECRET
   - QUICKBOOKS_ENVIRONMENT (sandbox or production)
"""
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

import httpx
import structlog

from backend.services.integrations.base import BaseIntegrationService

logger = structlog.get_logger(__name__)


class QuickBooksService(BaseIntegrationService):
    """QuickBooks Online integration service."""

    @property
    def integration_type(self) -> str:
        return "quickbooks"

    @property
    def oauth_authorize_url(self) -> str:
        return "https://appcenter.intuit.com/connect/oauth2"

    @property
    def oauth_token_url(self) -> str:
        return "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

    @property
    def api_base_url(self) -> str:
        env = os.getenv("QUICKBOOKS_ENVIRONMENT", "sandbox")
        if env == "production":
            return "https://quickbooks.api.intuit.com"
        return "https://sandbox-quickbooks.api.intuit.com"

    def get_oauth_scopes(self) -> List[str]:
        return ["com.intuit.quickbooks.accounting", "openid", "profile", "email"]

    def _get_client_id(self) -> str:
        client_id = os.getenv("QUICKBOOKS_CLIENT_ID")
        if not client_id:
            raise ValueError("QUICKBOOKS_CLIENT_ID environment variable not set")
        return client_id

    def _get_client_secret(self) -> str:
        client_secret = os.getenv("QUICKBOOKS_CLIENT_SECRET")
        if not client_secret:
            raise ValueError("QUICKBOOKS_CLIENT_SECRET environment variable not set")
        return client_secret

    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        import base64

        # QuickBooks uses Basic auth for token exchange
        credentials = base64.b64encode(
            f"{self._get_client_id()}:{self._get_client_secret()}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.oauth_token_url,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh the access token."""
        import base64

        if not self.integration.refresh_token:
            raise ValueError("No refresh token available")

        credentials = base64.b64encode(
            f"{self._get_client_id()}:{self._get_client_secret()}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.oauth_token_url,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.integration.refresh_token,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_company_info(self) -> Dict[str, Any]:
        """Get connected company information."""
        realm_id = self.integration.external_company_id
        if not realm_id:
            raise ValueError("No company connected")

        data = await self._make_api_request(
            "GET",
            f"v3/company/{realm_id}/companyinfo/{realm_id}",
        )
        return data.get("CompanyInfo", {})

    async def get_chart_of_accounts(self) -> List[Dict[str, Any]]:
        """Get the chart of accounts."""
        realm_id = self.integration.external_company_id
        if not realm_id:
            raise ValueError("No company connected")

        data = await self._make_api_request(
            "GET",
            f"v3/company/{realm_id}/query",
            params={"query": "SELECT * FROM Account MAXRESULTS 1000"},
        )
        return data.get("QueryResponse", {}).get("Account", [])

    async def get_financial_reports(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get financial reports.

        Args:
            report_type: 'profit_loss', 'balance_sheet', or 'cash_flow'
            start_date: Report start date
            end_date: Report end date
        """
        realm_id = self.integration.external_company_id
        if not realm_id:
            raise ValueError("No company connected")

        # Map report types to QuickBooks report names
        report_map = {
            "profit_loss": "ProfitAndLoss",
            "balance_sheet": "BalanceSheet",
            "cash_flow": "CashFlow",
        }

        qb_report_name = report_map.get(report_type)
        if not qb_report_name:
            raise ValueError(f"Unknown report type: {report_type}")

        data = await self._make_api_request(
            "GET",
            f"v3/company/{realm_id}/reports/{qb_report_name}",
            params={
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
        )
        return data

    async def get_profit_and_loss(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get Profit & Loss report (convenience method)."""
        return await self.get_financial_reports("profit_loss", start_date, end_date)

    async def get_balance_sheet(self, as_of_date: datetime) -> Dict[str, Any]:
        """Get Balance Sheet report (convenience method)."""
        return await self.get_financial_reports("balance_sheet", as_of_date, as_of_date)

    async def get_customers(self) -> List[Dict[str, Any]]:
        """Get list of customers."""
        realm_id = self.integration.external_company_id
        if not realm_id:
            raise ValueError("No company connected")

        data = await self._make_api_request(
            "GET",
            f"v3/company/{realm_id}/query",
            params={"query": "SELECT * FROM Customer MAXRESULTS 1000"},
        )
        return data.get("QueryResponse", {}).get("Customer", [])

    async def get_vendors(self) -> List[Dict[str, Any]]:
        """Get list of vendors."""
        realm_id = self.integration.external_company_id
        if not realm_id:
            raise ValueError("No company connected")

        data = await self._make_api_request(
            "GET",
            f"v3/company/{realm_id}/query",
            params={"query": "SELECT * FROM Vendor MAXRESULTS 1000"},
        )
        return data.get("QueryResponse", {}).get("Vendor", [])
