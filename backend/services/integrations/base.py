"""
Base integration service class.

Provides common functionality for third-party accounting integrations.
"""
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List

import httpx
import structlog
from sqlalchemy.orm import Session

from backend.models.integration import Integration, IntegrationStatus

logger = structlog.get_logger(__name__)


class BaseIntegrationService(ABC):
    """Abstract base class for accounting integrations."""

    def __init__(self, db: Session, integration: Integration):
        """
        Initialize the integration service.

        Args:
            db: Database session
            integration: Integration model instance
        """
        self.db = db
        self.integration = integration
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    @abstractmethod
    def integration_type(self) -> str:
        """Return the integration type identifier."""
        pass

    @property
    @abstractmethod
    def oauth_authorize_url(self) -> str:
        """Return the OAuth authorization URL."""
        pass

    @property
    @abstractmethod
    def oauth_token_url(self) -> str:
        """Return the OAuth token exchange URL."""
        pass

    @property
    @abstractmethod
    def api_base_url(self) -> str:
        """Return the API base URL."""
        pass

    @abstractmethod
    def get_oauth_scopes(self) -> List[str]:
        """Return required OAuth scopes."""
        pass

    @abstractmethod
    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access tokens.

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: Redirect URI used in authorization

        Returns:
            Dict with access_token, refresh_token, expires_in
        """
        pass

    @abstractmethod
    async def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refresh the access token using the refresh token.

        Returns:
            Dict with new access_token and optionally new refresh_token
        """
        pass

    @abstractmethod
    async def get_company_info(self) -> Dict[str, Any]:
        """
        Get connected company information.

        Returns:
            Dict with company name, id, and other metadata
        """
        pass

    @abstractmethod
    async def get_chart_of_accounts(self) -> List[Dict[str, Any]]:
        """
        Get the chart of accounts from the connected company.

        Returns:
            List of account objects
        """
        pass

    @abstractmethod
    async def get_financial_reports(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get financial reports from the connected company.

        Args:
            report_type: Type of report (profit_loss, balance_sheet, cash_flow)
            start_date: Report start date
            end_date: Report end date

        Returns:
            Report data
        """
        pass

    def build_authorize_url(self, redirect_uri: str, state: str) -> str:
        """
        Build the OAuth authorization URL.

        Args:
            redirect_uri: Where to redirect after authorization
            state: CSRF protection state parameter

        Returns:
            Full authorization URL
        """
        scopes = " ".join(self.get_oauth_scopes())
        params = {
            "client_id": self._get_client_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scopes,
            "state": state,
        }
        # Add any provider-specific parameters
        params.update(self._get_additional_auth_params())

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.oauth_authorize_url}?{query}"

    def _get_additional_auth_params(self) -> Dict[str, str]:
        """Override to add provider-specific auth parameters."""
        return {}

    @abstractmethod
    def _get_client_id(self) -> str:
        """Get the OAuth client ID from environment."""
        pass

    @abstractmethod
    def _get_client_secret(self) -> str:
        """Get the OAuth client secret from environment."""
        pass

    async def ensure_valid_token(self) -> bool:
        """
        Ensure the access token is valid, refreshing if necessary.

        Returns:
            True if token is valid or was successfully refreshed
        """
        if self.integration.status != IntegrationStatus.CONNECTED:
            return False

        if not self.integration.is_token_expired():
            return True

        try:
            tokens = await self.refresh_access_token()
            self.integration.access_token = tokens["access_token"]
            if "refresh_token" in tokens:
                self.integration.refresh_token = tokens["refresh_token"]
            if "expires_in" in tokens:
                from datetime import timedelta
                self.integration.token_expires_at = datetime.utcnow() + timedelta(seconds=tokens["expires_in"])
            self.db.commit()
            return True
        except Exception as e:
            logger.error("token_refresh_failed", integration_id=str(self.integration.id), error=str(e))
            self.integration.mark_error(f"Token refresh failed: {str(e)}")
            self.db.commit()
            return False

    async def _make_api_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make an authenticated API request.

        Args:
            method: HTTP method
            endpoint: API endpoint (appended to base URL)
            data: Request body data
            params: Query parameters

        Returns:
            Response JSON data
        """
        if not await self.ensure_valid_token():
            raise Exception("Unable to authenticate with integration")

        url = f"{self.api_base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.integration.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=30.0,
            )

            if response.status_code == 401:
                # Token might be invalid, try to refresh
                if await self.ensure_valid_token():
                    headers["Authorization"] = f"Bearer {self.integration.access_token}"
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=data,
                        params=params,
                        timeout=30.0,
                    )

            response.raise_for_status()
            return response.json()
