"""
Xero integration service.

Provides OAuth2 flow and API access for Xero accounting software.

To use this integration, you need:
1. Create a Xero Developer account: https://developer.xero.com
2. Create an app in the Xero Developer Portal
3. Get your Client ID and Client Secret
4. Set environment variables:
   - XERO_CLIENT_ID
   - XERO_CLIENT_SECRET
"""
import os
from datetime import datetime
from typing import Dict, Any, List

import httpx
import structlog

from backend.services.integrations.base import BaseIntegrationService

logger = structlog.get_logger(__name__)


class XeroService(BaseIntegrationService):
    """Xero accounting integration service."""

    @property
    def integration_type(self) -> str:
        return "xero"

    @property
    def oauth_authorize_url(self) -> str:
        return "https://login.xero.com/identity/connect/authorize"

    @property
    def oauth_token_url(self) -> str:
        return "https://identity.xero.com/connect/token"

    @property
    def api_base_url(self) -> str:
        return "https://api.xero.com/api.xro/2.0"

    def get_oauth_scopes(self) -> List[str]:
        return [
            "openid",
            "profile",
            "email",
            "accounting.transactions.read",
            "accounting.reports.read",
            "accounting.contacts.read",
            "accounting.settings.read",
            "offline_access",
        ]

    def _get_client_id(self) -> str:
        client_id = os.getenv("XERO_CLIENT_ID")
        if not client_id:
            raise ValueError("XERO_CLIENT_ID environment variable not set")
        return client_id

    def _get_client_secret(self) -> str:
        client_secret = os.getenv("XERO_CLIENT_SECRET")
        if not client_secret:
            raise ValueError("XERO_CLIENT_SECRET environment variable not set")
        return client_secret

    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        import base64

        # Xero uses Basic auth for token exchange
        credentials = base64.b64encode(
            f"{self._get_client_id()}:{self._get_client_secret()}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.oauth_token_url,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
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
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.integration.refresh_token,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_connections(self) -> List[Dict[str, Any]]:
        """Get list of connected Xero organizations (tenants)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.xero.com/connections",
                headers={
                    "Authorization": f"Bearer {self.integration.access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def _get_tenant_id(self) -> str:
        """Get the connected tenant (organization) ID."""
        tenant_id = self.integration.external_company_id
        if not tenant_id:
            raise ValueError("No Xero organization connected")
        return tenant_id

    async def get_organisation(self) -> Dict[str, Any]:
        """Get connected organisation information."""
        tenant_id = self._get_tenant_id()

        data = await self._make_api_request(
            "GET",
            "Organisation",
            headers={"Xero-tenant-id": tenant_id},
        )
        organisations = data.get("Organisations", [])
        return organisations[0] if organisations else {}

    async def get_accounts(self) -> List[Dict[str, Any]]:
        """Get chart of accounts."""
        tenant_id = self._get_tenant_id()

        data = await self._make_api_request(
            "GET",
            "Accounts",
            headers={"Xero-tenant-id": tenant_id},
        )
        return data.get("Accounts", [])

    async def get_profit_and_loss(
        self,
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, Any]:
        """
        Get Profit and Loss report.

        Args:
            from_date: Report start date
            to_date: Report end date
        """
        tenant_id = self._get_tenant_id()

        data = await self._make_api_request(
            "GET",
            "Reports/ProfitAndLoss",
            headers={"Xero-tenant-id": tenant_id},
            params={
                "fromDate": from_date.strftime("%Y-%m-%d"),
                "toDate": to_date.strftime("%Y-%m-%d"),
            },
        )
        reports = data.get("Reports", [])
        return reports[0] if reports else {}

    async def get_balance_sheet(self, date: datetime) -> Dict[str, Any]:
        """
        Get Balance Sheet report.

        Args:
            date: Report date
        """
        tenant_id = self._get_tenant_id()

        data = await self._make_api_request(
            "GET",
            "Reports/BalanceSheet",
            headers={"Xero-tenant-id": tenant_id},
            params={
                "date": date.strftime("%Y-%m-%d"),
            },
        )
        reports = data.get("Reports", [])
        return reports[0] if reports else {}

    async def get_trial_balance(self, date: datetime) -> Dict[str, Any]:
        """
        Get Trial Balance report.

        Args:
            date: Report date
        """
        tenant_id = self._get_tenant_id()

        data = await self._make_api_request(
            "GET",
            "Reports/TrialBalance",
            headers={"Xero-tenant-id": tenant_id},
            params={
                "date": date.strftime("%Y-%m-%d"),
            },
        )
        reports = data.get("Reports", [])
        return reports[0] if reports else {}

    async def get_contacts(self) -> List[Dict[str, Any]]:
        """Get list of contacts (customers/suppliers)."""
        tenant_id = self._get_tenant_id()

        data = await self._make_api_request(
            "GET",
            "Contacts",
            headers={"Xero-tenant-id": tenant_id},
        )
        return data.get("Contacts", [])

    async def get_invoices(
        self,
        modified_since: datetime = None,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get invoices.

        Args:
            modified_since: Only return invoices modified after this date
            status: Filter by invoice status (DRAFT, SUBMITTED, AUTHORISED, etc.)
        """
        tenant_id = self._get_tenant_id()

        headers = {"Xero-tenant-id": tenant_id}
        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%Y-%m-%dT%H:%M:%S")

        params = {}
        if status:
            params["where"] = f'Status=="{status}"'

        data = await self._make_api_request(
            "GET",
            "Invoices",
            headers=headers,
            params=params if params else None,
        )
        return data.get("Invoices", [])

    async def get_bank_transactions(
        self,
        modified_since: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get bank transactions."""
        tenant_id = self._get_tenant_id()

        headers = {"Xero-tenant-id": tenant_id}
        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%Y-%m-%dT%H:%M:%S")

        data = await self._make_api_request(
            "GET",
            "BankTransactions",
            headers=headers,
        )
        return data.get("BankTransactions", [])
