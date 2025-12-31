"""
Third-party integrations API routes.

Provides endpoints for connecting, managing, and syncing with
QuickBooks Online and Xero accounting software.
"""
import secrets
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.integration import Integration, IntegrationType, IntegrationStatus
from backend.auth.dependencies import get_current_active_user
from backend.exceptions import NotFoundError, ValidationError
from backend.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class IntegrationResponse(BaseModel):
    """Integration status response."""
    id: str
    integration_type: str
    status: str
    external_company_id: Optional[str]
    external_company_name: Optional[str]
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class IntegrationListResponse(BaseModel):
    """Response for integration list."""
    integrations: List[IntegrationResponse]


class ConnectRequest(BaseModel):
    """Request to initiate OAuth connection."""
    redirect_url: str = Field(..., description="URL to redirect after OAuth completion")


class ConnectResponse(BaseModel):
    """Response with OAuth authorization URL."""
    authorization_url: str


class DisconnectResponse(BaseModel):
    """Response after disconnecting integration."""
    message: str


class SyncResponse(BaseModel):
    """Response after initiating sync."""
    message: str
    job_id: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================

def _get_integration_service(integration: Integration):
    """Get the appropriate service class for an integration."""
    if integration.integration_type == IntegrationType.QUICKBOOKS:
        from backend.services.integrations.quickbooks import QuickBooksService
        return QuickBooksService(integration)
    elif integration.integration_type == IntegrationType.XERO:
        from backend.services.integrations.xero import XeroService
        return XeroService(integration)
    else:
        raise ValueError(f"Unknown integration type: {integration.integration_type}")


def _integration_to_response(integration: Integration) -> IntegrationResponse:
    """Convert integration model to response."""
    return IntegrationResponse(
        id=str(integration.id),
        integration_type=integration.integration_type.value,
        status=integration.status.value,
        external_company_id=integration.external_company_id,
        external_company_name=integration.external_company_name,
        last_sync_at=integration.last_sync_at,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


# =============================================================================
# Integration Endpoints
# =============================================================================

@router.get(
    "",
    response_model=IntegrationListResponse,
    summary="List integrations",
    description="Get all integrations for the current organization.",
)
async def list_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> IntegrationListResponse:
    """List all integrations for the user's organization."""
    org_id = current_user.default_organization_id
    if not org_id:
        return IntegrationListResponse(integrations=[])

    integrations = db.query(Integration).filter(
        Integration.organization_id == org_id,
        Integration.is_active == True,
    ).all()

    return IntegrationListResponse(
        integrations=[_integration_to_response(i) for i in integrations]
    )


@router.get(
    "/{integration_type}",
    response_model=IntegrationResponse,
    summary="Get integration status",
    description="Get status of a specific integration type.",
)
async def get_integration(
    integration_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> IntegrationResponse:
    """Get integration by type."""
    try:
        int_type = IntegrationType(integration_type)
    except ValueError:
        raise NotFoundError("Integration", integration_type)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Integration", integration_type)

    integration = db.query(Integration).filter(
        Integration.organization_id == org_id,
        Integration.integration_type == int_type,
        Integration.is_active == True,
    ).first()

    if not integration:
        raise NotFoundError("Integration", integration_type)

    return _integration_to_response(integration)


# =============================================================================
# QuickBooks Endpoints
# =============================================================================

@router.post(
    "/quickbooks/connect",
    response_model=ConnectResponse,
    summary="Connect QuickBooks",
    description="Initiate OAuth flow to connect QuickBooks Online.",
)
async def connect_quickbooks(
    request: ConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ConnectResponse:
    """Start QuickBooks OAuth connection flow."""
    import os

    client_id = os.getenv("QUICKBOOKS_CLIENT_ID")
    if not client_id:
        raise ValidationError(
            message="QuickBooks integration not configured",
            errors=[{"field": "config", "message": "QUICKBOOKS_CLIENT_ID not set"}]
        )

    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state in session or temporary storage
    # For now, we'll encode the redirect URL and org ID in the state
    org_id = current_user.default_organization_id
    if not org_id:
        raise ValidationError(
            message="Organization required",
            errors=[{"field": "organization", "message": "User must belong to an organization"}]
        )

    # Build authorization URL
    env = os.getenv("QUICKBOOKS_ENVIRONMENT", "sandbox")
    redirect_uri = f"{settings.backend_url}/api/v1/integrations/quickbooks/callback"

    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": "com.intuit.quickbooks.accounting openid profile email",
        "redirect_uri": redirect_uri,
        "state": state,
    }

    authorization_url = f"https://appcenter.intuit.com/connect/oauth2?{urlencode(params)}"

    # Store state for verification (in production, use Redis or DB)
    # For now, we'll create a pending integration record
    integration = Integration(
        organization_id=org_id,
        integration_type=IntegrationType.QUICKBOOKS,
        status=IntegrationStatus.PENDING,
        metadata={"state": state, "redirect_url": request.redirect_url},
    )
    db.add(integration)
    db.commit()

    logger.info(
        "quickbooks_oauth_initiated",
        user_id=str(current_user.id),
        org_id=str(org_id),
    )

    return ConnectResponse(authorization_url=authorization_url)


@router.get(
    "/quickbooks/callback",
    summary="QuickBooks OAuth callback",
    description="Handle OAuth callback from QuickBooks.",
)
async def quickbooks_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    realmId: str = Query(..., description="QuickBooks company ID"),
    db: Session = Depends(get_db),
):
    """Handle QuickBooks OAuth callback."""
    import os

    # Find pending integration with matching state
    integration = db.query(Integration).filter(
        Integration.integration_type == IntegrationType.QUICKBOOKS,
        Integration.status == IntegrationStatus.PENDING,
    ).order_by(Integration.created_at.desc()).first()

    if not integration or integration.metadata.get("state") != state:
        logger.warning("quickbooks_oauth_invalid_state", state=state)
        return RedirectResponse(url="/integrations?error=invalid_state")

    redirect_url = integration.metadata.get("redirect_url", "/integrations")

    try:
        # Exchange code for tokens
        from backend.services.integrations.quickbooks import QuickBooksService
        service = QuickBooksService(integration)

        redirect_uri = f"{settings.backend_url}/api/v1/integrations/quickbooks/callback"
        tokens = await service.exchange_code_for_tokens(code, redirect_uri)

        # Update integration with tokens
        integration.access_token = tokens.get("access_token")
        integration.refresh_token = tokens.get("refresh_token")
        integration.token_expires_at = datetime.utcnow()
        if tokens.get("expires_in"):
            from datetime import timedelta
            integration.token_expires_at += timedelta(seconds=tokens["expires_in"])
        integration.external_company_id = realmId
        integration.status = IntegrationStatus.CONNECTED

        # Try to get company info
        try:
            service = QuickBooksService(integration)
            company_info = await service.get_company_info()
            integration.external_company_name = company_info.get("CompanyName")
        except Exception as e:
            logger.warning("failed_to_get_company_info", error=str(e))

        db.commit()

        logger.info(
            "quickbooks_connected",
            integration_id=str(integration.id),
            realm_id=realmId,
        )

        return RedirectResponse(url=f"{redirect_url}?success=quickbooks_connected")

    except Exception as e:
        logger.error("quickbooks_oauth_failed", error=str(e))
        integration.status = IntegrationStatus.FAILED
        integration.error_message = str(e)
        db.commit()
        return RedirectResponse(url=f"{redirect_url}?error=oauth_failed")


@router.delete(
    "/quickbooks",
    response_model=DisconnectResponse,
    summary="Disconnect QuickBooks",
    description="Disconnect QuickBooks integration.",
)
async def disconnect_quickbooks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DisconnectResponse:
    """Disconnect QuickBooks integration."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Integration", "quickbooks")

    integration = db.query(Integration).filter(
        Integration.organization_id == org_id,
        Integration.integration_type == IntegrationType.QUICKBOOKS,
        Integration.is_active == True,
    ).first()

    if not integration:
        raise NotFoundError("Integration", "quickbooks")

    # Soft delete - mark as inactive
    integration.is_active = False
    integration.status = IntegrationStatus.DISCONNECTED
    integration.access_token = None
    integration.refresh_token = None
    db.commit()

    logger.info(
        "quickbooks_disconnected",
        integration_id=str(integration.id),
        user_id=str(current_user.id),
    )

    return DisconnectResponse(message="QuickBooks disconnected successfully")


# =============================================================================
# Xero Endpoints
# =============================================================================

@router.post(
    "/xero/connect",
    response_model=ConnectResponse,
    summary="Connect Xero",
    description="Initiate OAuth flow to connect Xero.",
)
async def connect_xero(
    request: ConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ConnectResponse:
    """Start Xero OAuth connection flow."""
    import os

    client_id = os.getenv("XERO_CLIENT_ID")
    if not client_id:
        raise ValidationError(
            message="Xero integration not configured",
            errors=[{"field": "config", "message": "XERO_CLIENT_ID not set"}]
        )

    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)

    org_id = current_user.default_organization_id
    if not org_id:
        raise ValidationError(
            message="Organization required",
            errors=[{"field": "organization", "message": "User must belong to an organization"}]
        )

    # Build authorization URL
    redirect_uri = f"{settings.backend_url}/api/v1/integrations/xero/callback"

    scopes = [
        "openid",
        "profile",
        "email",
        "accounting.transactions.read",
        "accounting.reports.read",
        "accounting.contacts.read",
        "accounting.settings.read",
        "offline_access",
    ]

    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": " ".join(scopes),
        "redirect_uri": redirect_uri,
        "state": state,
    }

    authorization_url = f"https://login.xero.com/identity/connect/authorize?{urlencode(params)}"

    # Create pending integration record
    integration = Integration(
        organization_id=org_id,
        integration_type=IntegrationType.XERO,
        status=IntegrationStatus.PENDING,
        metadata={"state": state, "redirect_url": request.redirect_url},
    )
    db.add(integration)
    db.commit()

    logger.info(
        "xero_oauth_initiated",
        user_id=str(current_user.id),
        org_id=str(org_id),
    )

    return ConnectResponse(authorization_url=authorization_url)


@router.get(
    "/xero/callback",
    summary="Xero OAuth callback",
    description="Handle OAuth callback from Xero.",
)
async def xero_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle Xero OAuth callback."""
    # Find pending integration with matching state
    integration = db.query(Integration).filter(
        Integration.integration_type == IntegrationType.XERO,
        Integration.status == IntegrationStatus.PENDING,
    ).order_by(Integration.created_at.desc()).first()

    if not integration or integration.metadata.get("state") != state:
        logger.warning("xero_oauth_invalid_state", state=state)
        return RedirectResponse(url="/integrations?error=invalid_state")

    redirect_url = integration.metadata.get("redirect_url", "/integrations")

    try:
        # Exchange code for tokens
        from backend.services.integrations.xero import XeroService
        service = XeroService(integration)

        redirect_uri = f"{settings.backend_url}/api/v1/integrations/xero/callback"
        tokens = await service.exchange_code_for_tokens(code, redirect_uri)

        # Update integration with tokens
        integration.access_token = tokens.get("access_token")
        integration.refresh_token = tokens.get("refresh_token")
        integration.token_expires_at = datetime.utcnow()
        if tokens.get("expires_in"):
            from datetime import timedelta
            integration.token_expires_at += timedelta(seconds=tokens["expires_in"])
        integration.status = IntegrationStatus.CONNECTED

        # Get connected tenants and use the first one
        try:
            service = XeroService(integration)
            connections = await service.get_connections()
            if connections:
                first_tenant = connections[0]
                integration.external_company_id = first_tenant.get("tenantId")
                integration.external_company_name = first_tenant.get("tenantName")
        except Exception as e:
            logger.warning("failed_to_get_xero_connections", error=str(e))

        db.commit()

        logger.info(
            "xero_connected",
            integration_id=str(integration.id),
            tenant_id=integration.external_company_id,
        )

        return RedirectResponse(url=f"{redirect_url}?success=xero_connected")

    except Exception as e:
        logger.error("xero_oauth_failed", error=str(e))
        integration.status = IntegrationStatus.FAILED
        integration.error_message = str(e)
        db.commit()
        return RedirectResponse(url=f"{redirect_url}?error=oauth_failed")


@router.delete(
    "/xero",
    response_model=DisconnectResponse,
    summary="Disconnect Xero",
    description="Disconnect Xero integration.",
)
async def disconnect_xero(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DisconnectResponse:
    """Disconnect Xero integration."""
    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Integration", "xero")

    integration = db.query(Integration).filter(
        Integration.organization_id == org_id,
        Integration.integration_type == IntegrationType.XERO,
        Integration.is_active == True,
    ).first()

    if not integration:
        raise NotFoundError("Integration", "xero")

    # Soft delete
    integration.is_active = False
    integration.status = IntegrationStatus.DISCONNECTED
    integration.access_token = None
    integration.refresh_token = None
    db.commit()

    logger.info(
        "xero_disconnected",
        integration_id=str(integration.id),
        user_id=str(current_user.id),
    )

    return DisconnectResponse(message="Xero disconnected successfully")


# =============================================================================
# Sync Endpoints
# =============================================================================

@router.post(
    "/{integration_type}/sync",
    response_model=SyncResponse,
    summary="Sync integration data",
    description="Trigger a data sync from the connected accounting software.",
)
async def sync_integration(
    integration_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SyncResponse:
    """Trigger sync for an integration."""
    try:
        int_type = IntegrationType(integration_type)
    except ValueError:
        raise NotFoundError("Integration", integration_type)

    org_id = current_user.default_organization_id
    if not org_id:
        raise NotFoundError("Integration", integration_type)

    integration = db.query(Integration).filter(
        Integration.organization_id == org_id,
        Integration.integration_type == int_type,
        Integration.status == IntegrationStatus.CONNECTED,
        Integration.is_active == True,
    ).first()

    if not integration:
        raise NotFoundError("Integration", integration_type)

    # Update sync status
    integration.status = IntegrationStatus.SYNCING
    integration.last_sync_at = datetime.utcnow()
    db.commit()

    # In a full implementation, this would queue a background job
    # For now, just mark as synced
    integration.status = IntegrationStatus.CONNECTED
    db.commit()

    logger.info(
        "integration_sync_triggered",
        integration_type=integration_type,
        integration_id=str(integration.id),
    )

    return SyncResponse(message=f"{integration_type.title()} sync initiated")
