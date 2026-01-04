"""
Integration tests for upload API endpoint.
"""
import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestUploadEndpoint:
    """Tests for POST /api/v1/upload endpoint."""

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_upload_invalid_content_type(self, authenticated_client: TestClient):
        """Test upload rejects non-PDF files."""
        # Create a fake text file
        content = b"This is not a PDF"
        files = {"file": ("test.txt", io.BytesIO(content), "text/plain")}

        response = authenticated_client.post("/api/v1/upload", files=files)

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_upload_invalid_extension(self, authenticated_client: TestClient):
        """Test upload rejects wrong file extension."""
        content = b"This is not a PDF"
        # Content-type is PDF but extension is not
        files = {"file": ("test.docx", io.BytesIO(content), "application/pdf")}

        response = authenticated_client.post("/api/v1/upload", files=files)

        assert response.status_code == 400
        assert "Invalid file extension" in response.json()["detail"]

    def test_upload_valid_pdf(self, authenticated_client: TestClient, sample_pdf_content: bytes):
        """Test successful PDF upload."""
        files = {"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")}

        with patch("backend.api.routes.upload.get_table_detector") as mock_detector:
            # Mock the detection result
            mock_instance = MagicMock()
            mock_instance.detect_tables.return_value = MagicMock(
                tables=[],
                page_count=1,
            )
            mock_detector.return_value = mock_instance

            response = authenticated_client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["filename"] == "test.pdf"
        assert "tables" in data
        assert "processing_time_ms" in data

    def test_upload_response_schema(self, authenticated_client: TestClient, sample_pdf_content: bytes):
        """Test upload response matches schema."""
        files = {"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")}

        with patch("backend.api.routes.upload.get_table_detector") as mock_detector:
            mock_instance = MagicMock()
            mock_instance.detect_tables.return_value = MagicMock(
                tables=[],
                page_count=1,
            )
            mock_detector.return_value = mock_instance

            response = authenticated_client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        required_fields = ["document_id", "filename", "page_count", "tables", "processing_time_ms", "created_at"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_get_document_not_found(self, client: TestClient):
        """Test getting non-existent document returns 404."""
        fake_id = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get(f"/api/v1/documents/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestAPIDocumentation:
    """Tests for API documentation."""

    def test_openapi_available(self, client: TestClient):
        """Test OpenAPI spec is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_available(self, client: TestClient):
        """Test Swagger UI is available."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_available(self, client: TestClient):
        """Test ReDoc is available."""
        response = client.get("/redoc")
        assert response.status_code == 200
