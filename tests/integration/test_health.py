"""
Integration tests for health and utility endpoints.

Tests basic API health and functionality.
"""
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_check(self, client: TestClient):
        """Test health endpoint returns OK."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestDocsEndpoint:
    """Tests for documentation endpoints."""
    
    def test_docs_accessible(self, client: TestClient):
        """Test Swagger docs are accessible."""
        response = client.get("/docs")
        
        assert response.status_code == 200
    
    def test_openapi_json(self, client: TestClient):
        """Test OpenAPI JSON schema is accessible."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "StatementXL API"
        assert "paths" in data


class TestSecurityHeaders:
    """Tests for security headers in responses."""
    
    def test_security_headers_present(self, client: TestClient):
        """Test that security headers are in responses."""
        response = client.get("/health")
        
        # Check security headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "Content-Security-Policy" in response.headers
    
    def test_correlation_id_in_response(self, client: TestClient):
        """Test that correlation ID is returned."""
        response = client.get("/health")
        
        assert "X-Correlation-ID" in response.headers
        assert len(response.headers["X-Correlation-ID"]) > 0
    
    def test_custom_correlation_id(self, client: TestClient):
        """Test that custom correlation ID is echoed."""
        custom_id = "test-correlation-123"
        response = client.get(
            "/health",
            headers={"X-Correlation-ID": custom_id}
        )
        
        assert response.headers.get("X-Correlation-ID") == custom_id


class TestCORS:
    """Tests for CORS configuration."""
    
    def test_cors_preflight(self, client: TestClient):
        """Test CORS preflight request."""
        response = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            }
        )
        
        # Should return 200 for valid origin
        assert response.status_code == 200
