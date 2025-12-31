"""
Audit logging middleware.

Automatically captures and logs API requests for compliance and debugging.
"""
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Callable, Dict, Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.models.audit import AuditLog, AuditAction, AuditResourceType, AuditSeverity

logger = structlog.get_logger(__name__)

# Context variable for current request audit context
_audit_context: ContextVar[Dict[str, Any]] = ContextVar("audit_context", default={})


def get_audit_context() -> Dict[str, Any]:
    """Get the current audit context."""
    return _audit_context.get()


def set_audit_context(**kwargs) -> None:
    """Update the audit context with additional data."""
    ctx = _audit_context.get().copy()
    ctx.update(kwargs)
    _audit_context.set(ctx)


# Mapping of HTTP methods to audit actions
METHOD_ACTION_MAP = {
    "GET": AuditAction.READ,
    "POST": AuditAction.CREATE,
    "PUT": AuditAction.UPDATE,
    "PATCH": AuditAction.UPDATE,
    "DELETE": AuditAction.DELETE,
}

# Path patterns to resource types
RESOURCE_TYPE_PATTERNS = [
    ("/api/v1/auth", AuditResourceType.SESSION),
    ("/api/v1/users", AuditResourceType.USER),
    ("/api/v1/organizations", AuditResourceType.ORGANIZATION),
    ("/api/v1/documents", AuditResourceType.DOCUMENT),
    ("/api/v1/upload", AuditResourceType.DOCUMENT),
    ("/api/v1/templates", AuditResourceType.TEMPLATE),
    ("/api/v1/mappings", AuditResourceType.MAPPING),
    ("/api/v1/export", AuditResourceType.EXPORT),
    ("/api/v1/api-keys", AuditResourceType.API_KEY),
    ("/api/v1/webhooks", AuditResourceType.WEBHOOK),
    ("/api/v1/integrations", AuditResourceType.INTEGRATION),
    ("/api/v1/jobs", AuditResourceType.JOB),
]

# Paths to skip auditing (health checks, static files, etc.)
SKIP_PATHS = [
    "/health",
    "/healthz",
    "/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
]

# Sensitive paths that require extra logging
SENSITIVE_PATHS = [
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/password",
    "/api/v1/api-keys",
    "/api/v1/users",
]


def _get_resource_type(path: str) -> AuditResourceType:
    """Determine resource type from request path."""
    for pattern, resource_type in RESOURCE_TYPE_PATTERNS:
        if path.startswith(pattern):
            return resource_type
    return AuditResourceType.SYSTEM


def _get_resource_id(path: str) -> Optional[str]:
    """Extract resource ID from path if present."""
    parts = path.rstrip("/").split("/")
    # Look for UUID-like segments
    for part in reversed(parts):
        try:
            # Try to parse as UUID
            uuid.UUID(part)
            return part
        except ValueError:
            # Not a UUID, might still be an ID
            if part.isdigit() or (len(part) > 8 and part.isalnum()):
                return part
    return None


def _should_skip_path(path: str) -> bool:
    """Check if path should be skipped from auditing."""
    for skip in SKIP_PATHS:
        if path.startswith(skip):
            return True
    return False


def _get_severity(status_code: int, path: str) -> AuditSeverity:
    """Determine severity based on status code and path."""
    if status_code >= 500:
        return AuditSeverity.ERROR
    if status_code >= 400:
        return AuditSeverity.WARNING
    if any(path.startswith(p) for p in SENSITIVE_PATHS):
        return AuditSeverity.INFO
    return AuditSeverity.DEBUG


def _get_audit_action(method: str, path: str, status_code: int) -> AuditAction:
    """Determine specific audit action based on request context."""
    # Handle authentication-specific actions
    if "/auth/login" in path:
        return AuditAction.LOGIN if status_code < 400 else AuditAction.LOGIN_FAILED
    if "/auth/logout" in path:
        return AuditAction.LOGOUT
    if "/auth/password" in path:
        return AuditAction.PASSWORD_CHANGE

    # Handle API key actions
    if "/api-keys" in path:
        if method == "POST":
            return AuditAction.API_KEY_CREATED
        if method == "DELETE":
            return AuditAction.API_KEY_REVOKED

    # Handle integration actions
    if "/integrations" in path:
        if "connect" in path:
            return AuditAction.INTEGRATION_CONNECTED
        if "disconnect" in path or method == "DELETE":
            return AuditAction.INTEGRATION_DISCONNECTED
        if "sync" in path:
            return AuditAction.INTEGRATION_SYNCED

    # Default to method-based action
    return METHOD_ACTION_MAP.get(method, AuditAction.READ)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all API requests for audit purposes."""

    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: Optional[list] = None,
        log_request_body: bool = False,
        log_response_body: bool = False,
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or SKIP_PATHS
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log audit entry."""
        path = request.url.path

        # Skip excluded paths
        if _should_skip_path(path):
            return await call_next(request)

        # Generate request ID if not present
        request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Initialize audit context
        _audit_context.set({
            "request_id": request_id,
            "start_time": time.time(),
            "path": path,
            "method": request.method,
        })

        # Get client info
        client_ip = None
        if request.client:
            client_ip = request.client.host
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        user_agent = request.headers.get("User-Agent", "")[:500]

        # Process request
        start_time = time.time()
        try:
            response = await call_next(request)
            success = response.status_code < 400
            error_message = None
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)

            # Get response status
            status_code = response.status_code if 'response' in locals() else 500

            # Determine audit details
            action = _get_audit_action(request.method, path, status_code)
            resource_type = _get_resource_type(path)
            resource_id = _get_resource_id(path)
            severity = _get_severity(status_code, path)

            # Get user/org from request state if set by auth middleware
            user_id = getattr(request.state, "user_id", None)
            organization_id = getattr(request.state, "organization_id", None)
            api_key_id = getattr(request.state, "api_key_id", None)

            # Build metadata
            metadata = {
                "duration_ms": duration_ms,
                "status_code": status_code,
            }

            # Get any additional context set during request processing
            ctx = get_audit_context()
            if ctx.get("extra_metadata"):
                metadata.update(ctx["extra_metadata"])

            # Log the audit entry (async to not block response)
            self._log_audit_entry(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=user_id,
                organization_id=organization_id,
                api_key_id=api_key_id,
                ip_address=client_ip,
                user_agent=user_agent,
                request_id=request_id,
                request_method=request.method,
                request_path=path,
                success=success,
                error_message=error_message,
                severity=severity,
                metadata=metadata,
                old_value=ctx.get("old_value"),
                new_value=ctx.get("new_value"),
            )

        return response

    def _log_audit_entry(self, **kwargs) -> None:
        """Log audit entry to database and structured logger."""
        # Log to structured logger immediately
        logger.info(
            "audit_event",
            action=kwargs.get("action").value if kwargs.get("action") else None,
            resource_type=kwargs.get("resource_type").value if kwargs.get("resource_type") else None,
            resource_id=kwargs.get("resource_id"),
            user_id=str(kwargs.get("user_id")) if kwargs.get("user_id") else None,
            success=kwargs.get("success"),
            duration_ms=kwargs.get("metadata", {}).get("duration_ms"),
        )

        # Queue database write (in production, use background task)
        # For now, we'll skip DB write in middleware to avoid blocking
        # The audit service should be used for important events


def log_audit_event(
    db,
    action: AuditAction,
    resource_type: AuditResourceType,
    resource_id: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    organization_id: Optional[uuid.UUID] = None,
    description: Optional[str] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    severity: AuditSeverity = AuditSeverity.INFO,
) -> AuditLog:
    """
    Log an audit event to the database.

    Use this function for important events that need to be persisted.
    The middleware handles routine request logging.

    Example:
        from backend.middleware.audit import log_audit_event
        from backend.models.audit import AuditAction, AuditResourceType

        log_audit_event(
            db,
            action=AuditAction.USER_CREATED,
            resource_type=AuditResourceType.USER,
            resource_id=str(new_user.id),
            user_id=current_user.id,
            description="New user account created",
            new_value={"email": new_user.email},
        )
    """
    # Get context from middleware if available
    ctx = get_audit_context()

    entry = AuditLog.create_entry(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        organization_id=organization_id,
        description=description,
        old_value=old_value,
        new_value=new_value,
        metadata=metadata,
        ip_address=ctx.get("ip_address"),
        user_agent=ctx.get("user_agent"),
        request_id=ctx.get("request_id"),
        request_method=ctx.get("method"),
        request_path=ctx.get("path"),
        severity=severity,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info(
        "audit_event_persisted",
        audit_id=str(entry.id),
        action=action.value,
        resource_type=resource_type.value,
    )

    return entry
