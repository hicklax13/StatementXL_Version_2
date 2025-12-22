"""
Unit tests for custom exceptions.

Tests exception hierarchy and error formatting.
"""
import pytest

from backend.exceptions import (
    StatementXLError,
    DocumentProcessingError,
    TableExtractionError,
    MappingError,
    TemplateError,
    AuthenticationError,
    InvalidCredentialsError,
    InvalidTokenError,
    AuthorizationError,
    InsufficientPermissionsError,
    ValidationError,
    DatabaseError,
    ExternalServiceError,
)


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""
    
    def test_base_exception(self):
        """Test base StatementXLError."""
        exc = StatementXLError("Test error")
        
        assert exc.error_code == "SXL-000"
        assert exc.message == "Test error"
        assert exc.http_status == 500
    
    def test_document_processing_error(self):
        """Test DocumentProcessingError inherits correctly."""
        exc = DocumentProcessingError("PDF failed")
        
        assert isinstance(exc, StatementXLError)
        assert exc.error_code == "SXL-100"
        assert exc.http_status == 422
    
    def test_table_extraction_error(self):
        """Test TableExtractionError."""
        exc = TableExtractionError("No tables found")
        
        assert isinstance(exc, StatementXLError)
        assert exc.error_code == "SXL-200"
    
    def test_mapping_error(self):
        """Test MappingError."""
        exc = MappingError("Invalid mapping")
        
        assert isinstance(exc, StatementXLError)
        assert exc.error_code == "SXL-300"
    
    def test_template_error(self):
        """Test TemplateError."""
        exc = TemplateError("Template not found")
        
        assert isinstance(exc, StatementXLError)
        assert exc.error_code == "SXL-400"


class TestAuthExceptions:
    """Tests for authentication exceptions."""
    
    def test_authentication_error(self):
        """Test AuthenticationError."""
        exc = AuthenticationError("Not authenticated")
        
        assert isinstance(exc, StatementXLError)
        assert exc.error_code == "SXL-500"
        assert exc.http_status == 401
    
    def test_invalid_credentials(self):
        """Test InvalidCredentialsError."""
        exc = InvalidCredentialsError()
        
        assert isinstance(exc, AuthenticationError)
        assert exc.error_code == "SXL-501"
        assert "Invalid" in exc.message
    
    def test_invalid_token(self):
        """Test InvalidTokenError."""
        exc = InvalidTokenError()
        
        assert isinstance(exc, AuthenticationError)
        assert exc.error_code == "SXL-502"
    
    def test_authorization_error(self):
        """Test AuthorizationError."""
        exc = AuthorizationError("Access denied")
        
        assert isinstance(exc, StatementXLError)
        assert exc.error_code == "SXL-600"
        assert exc.http_status == 403
    
    def test_insufficient_permissions(self):
        """Test InsufficientPermissionsError."""
        exc = InsufficientPermissionsError(required_role="admin")
        
        assert isinstance(exc, AuthorizationError)
        assert exc.error_code == "SXL-601"
        assert "admin" in exc.message


class TestValidationError:
    """Tests for ValidationError."""
    
    def test_validation_error_basic(self):
        """Test basic ValidationError."""
        exc = ValidationError("Invalid input")
        
        assert isinstance(exc, StatementXLError)
        assert exc.error_code == "SXL-700"
        assert exc.http_status == 400
    
    def test_validation_error_with_errors(self):
        """Test ValidationError with field errors."""
        exc = ValidationError(
            message="Validation failed",
            errors=[
                {"field": "email", "message": "Invalid email"},
                {"field": "password", "message": "Too short"},
            ]
        )
        
        assert len(exc.details["errors"]) == 2


class TestExceptionDetails:
    """Tests for exception details handling."""
    
    def test_custom_details(self):
        """Test exceptions with custom details."""
        exc = DocumentProcessingError(
            message="PDF failed",
            details={"page": 5, "reason": "corrupt"}
        )
        
        assert exc.details["page"] == 5
        assert exc.details["reason"] == "corrupt"
    
    def test_exception_can_be_raised(self):
        """Test that exceptions can be raised and caught."""
        with pytest.raises(StatementXLError) as exc_info:
            raise DocumentProcessingError("Test error")
        
        assert exc_info.value.error_code == "SXL-100"
