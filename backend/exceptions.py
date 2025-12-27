"""
Custom exceptions for StatementXL.

Provides a hierarchy of exceptions with error codes for consistent error handling.
"""
from typing import Optional, Dict, Any


class StatementXLError(Exception):
    """
    Base exception for all StatementXL errors.
    
    Attributes:
        error_code: Unique error code (e.g., SXL-001)
        message: Human-readable error message
        details: Additional error context
    """
    error_code: str = "SXL-000"
    http_status: int = 500
    
    def __init__(
        self,
        message: str = "An unexpected error occurred",
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message
        self.details = details or {}
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# Document Processing Errors (SXL-1XX)
class DocumentProcessingError(StatementXLError):
    """Error during document processing."""
    error_code = "SXL-100"
    http_status = 422

    def __init__(self, message: str = "Failed to process document", **kwargs):
        super().__init__(message, **kwargs)


class DocumentNotFoundError(StatementXLError):
    """Document not found in database."""
    error_code = "SXL-101"
    http_status = 404
    
    def __init__(self, document_id: str, **kwargs):
        message = f"Document {document_id} not found"
        super().__init__(message, details={"document_id": document_id}, **kwargs)


class InvalidFileTypeError(StatementXLError):
    """Invalid file type uploaded."""
    error_code = "SXL-102"
    http_status = 400
    
    def __init__(self, filename: str, expected_types: list, **kwargs):
        message = f"Invalid file type. Expected: {', '.join(expected_types)}"
        super().__init__(message, details={"filename": filename, "expected_types": expected_types}, **kwargs)


class FileTooLargeError(StatementXLError):
    """File exceeds maximum size limit."""
    error_code = "SXL-103"
    http_status = 413
    
    def __init__(self, size: int, max_size: int, **kwargs):
        message = f"File too large. Maximum size: {max_size // (1024*1024)}MB"
        super().__init__(message, details={"size": size, "max_size": max_size}, **kwargs)


# Table Extraction Errors (SXL-2XX)
class TableExtractionError(StatementXLError):
    """Error during table extraction from PDF."""
    error_code = "SXL-200"
    http_status = 422
    
    def __init__(self, message: str = "Failed to extract tables from document", **kwargs):
        super().__init__(message, **kwargs)


class NoTablesFoundError(StatementXLError):
    """No tables found in document."""
    error_code = "SXL-201"
    http_status = 422
    
    def __init__(self, document_id: str, **kwargs):
        message = "No tables found in document"
        super().__init__(message, details={"document_id": document_id}, **kwargs)


class OCRError(StatementXLError):
    """Error during OCR processing."""
    error_code = "SXL-202"
    http_status = 422
    
    def __init__(self, message: str = "OCR processing failed", **kwargs):
        super().__init__(message, **kwargs)


# Mapping Errors (SXL-3XX)
class MappingError(StatementXLError):
    """Error during data mapping."""
    error_code = "SXL-300"
    http_status = 400
    
    def __init__(self, message: str = "Failed to create mapping", **kwargs):
        super().__init__(message, **kwargs)


class MappingNotFoundError(StatementXLError):
    """Mapping not found."""
    error_code = "SXL-301"
    http_status = 404
    
    def __init__(self, mapping_id: str, **kwargs):
        message = f"Mapping {mapping_id} not found"
        super().__init__(message, details={"mapping_id": mapping_id}, **kwargs)


class ConflictNotFoundError(StatementXLError):
    """Mapping conflict not found."""
    error_code = "SXL-302"
    http_status = 404
    
    def __init__(self, conflict_id: str, **kwargs):
        message = f"Conflict {conflict_id} not found"
        super().__init__(message, details={"conflict_id": conflict_id}, **kwargs)


class UnresolvedConflictsError(StatementXLError):
    """Cannot proceed with unresolved conflicts."""
    error_code = "SXL-303"
    http_status = 400
    
    def __init__(self, conflict_count: int, **kwargs):
        message = f"Cannot export: {conflict_count} unresolved conflicts"
        super().__init__(message, details={"conflict_count": conflict_count}, **kwargs)


# Template Errors (SXL-4XX)
class TemplateError(StatementXLError):
    """Error during template processing."""
    error_code = "SXL-400"
    http_status = 400
    
    def __init__(self, message: str = "Failed to process template", **kwargs):
        super().__init__(message, **kwargs)


class TemplateNotFoundError(StatementXLError):
    """Template not found."""
    error_code = "SXL-401"
    http_status = 404
    
    def __init__(self, template_id: str, **kwargs):
        message = f"Template {template_id} not found"
        super().__init__(message, details={"template_id": template_id}, **kwargs)


class InvalidTemplateError(StatementXLError):
    """Template format is invalid."""
    error_code = "SXL-402"
    http_status = 400
    
    def __init__(self, message: str = "Invalid template format", **kwargs):
        super().__init__(message, **kwargs)


# Authentication Errors (SXL-5XX)
class AuthenticationError(StatementXLError):
    """Authentication failed."""
    error_code = "SXL-500"
    http_status = 401
    
    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(message, **kwargs)


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password."""
    error_code = "SXL-501"
    http_status = 401

    def __init__(self, **kwargs):
        message = "Invalid email or password"
        super().__init__(message, **kwargs)


class TokenExpiredError(StatementXLError):
    """Authentication token has expired."""
    error_code = "SXL-502"
    http_status = 401
    
    def __init__(self, **kwargs):
        message = "Token has expired. Please log in again."
        super().__init__(message, **kwargs)


class InvalidTokenError(AuthenticationError):
    """Authentication token is invalid."""
    error_code = "SXL-502"
    http_status = 401

    def __init__(self, **kwargs):
        message = "Invalid authentication token"
        super().__init__(message, **kwargs)


# Authorization Errors (SXL-6XX)
class AuthorizationError(StatementXLError):
    """User not authorized for this action."""
    error_code = "SXL-600"
    http_status = 403
    
    def __init__(self, message: str = "You do not have permission to perform this action", **kwargs):
        super().__init__(message, **kwargs)


class InsufficientPermissionsError(AuthorizationError):
    """User lacks required permissions."""
    error_code = "SXL-601"
    http_status = 403

    def __init__(self, required_role: str, **kwargs):
        message = f"Requires {required_role} role"
        super().__init__(message, details={"required_role": required_role}, **kwargs)


# Validation Errors (SXL-7XX)
class ValidationError(StatementXLError):
    """Input validation failed."""
    error_code = "SXL-700"
    http_status = 400

    def __init__(self, message: str = "Validation failed", errors: list = None, **kwargs):
        details = kwargs.get("details", {})
        details["errors"] = errors or []
        super().__init__(message, details=details, **kwargs)


# Database Errors (SXL-8XX)
class DatabaseError(StatementXLError):
    """Database operation failed."""
    error_code = "SXL-800"
    http_status = 500
    
    def __init__(self, message: str = "Database operation failed", **kwargs):
        super().__init__(message, **kwargs)


# External Service Errors (SXL-9XX)
class ExternalServiceError(StatementXLError):
    """External service call failed."""
    error_code = "SXL-900"
    http_status = 502
    
    def __init__(self, service_name: str, message: str = None, **kwargs):
        msg = message or f"External service '{service_name}' is unavailable"
        super().__init__(msg, details={"service": service_name}, **kwargs)
