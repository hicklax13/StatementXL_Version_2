"""
Third-party accounting integrations.

Provides OAuth flows and data sync for QuickBooks, Xero, etc.
"""
from backend.services.integrations.base import BaseIntegrationService
from backend.services.integrations.quickbooks import QuickBooksService
from backend.services.integrations.xero import XeroService

__all__ = ["BaseIntegrationService", "QuickBooksService", "XeroService"]
