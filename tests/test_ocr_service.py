"""
Unit tests for OCRService.
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.services.ocr_service import OCRResult, OCRService, PageText, TextBlock


class TestOCRService:
    """Tests for OCRService class."""

    @pytest.fixture
    def ocr_service(self) -> OCRService:
        """Create OCR service instance."""
        return OCRService()

    def test_init_checks_tesseract(self, ocr_service: OCRService):
        """Test that initialization checks for Tesseract."""
        # Service should initialize without error
        assert ocr_service is not None

    def test_get_page_count(self, ocr_service: OCRService, sample_pdf_content: bytes, temp_dir: Path):
        """Test getting page count from PDF."""
        pdf_path = temp_dir / "test.pdf"
        pdf_path.write_bytes(sample_pdf_content)

        count = ocr_service.get_page_count(pdf_path)
        assert count >= 1

    def test_extract_text_returns_ocr_result(
        self, ocr_service: OCRService, sample_pdf_content: bytes, temp_dir: Path
    ):
        """Test that extract_text returns OCRResult."""
        pdf_path = temp_dir / "test.pdf"
        pdf_path.write_bytes(sample_pdf_content)

        result = ocr_service.extract_text(pdf_path)

        assert isinstance(result, OCRResult)
        assert result.page_count >= 1
        assert len(result.pages) >= 1

    def test_extract_text_has_page_info(
        self, ocr_service: OCRService, sample_pdf_content: bytes, temp_dir: Path
    ):
        """Test that extracted pages have correct structure."""
        pdf_path = temp_dir / "test.pdf"
        pdf_path.write_bytes(sample_pdf_content)

        result = ocr_service.extract_text(pdf_path)

        for page in result.pages:
            assert isinstance(page, PageText)
            assert page.page_number >= 1
            assert page.width > 0
            assert page.height > 0

    def test_extract_text_invalid_file_raises(self, ocr_service: OCRService, temp_dir: Path):
        """Test that invalid file raises exception."""
        invalid_path = temp_dir / "nonexistent.pdf"

        with pytest.raises(Exception):
            ocr_service.extract_text(invalid_path)


class TestTextBlock:
    """Tests for TextBlock dataclass."""

    def test_text_block_creation(self):
        """Test creating a TextBlock."""
        block = TextBlock(
            text="Revenue",
            page=1,
            bbox=[100.0, 200.0, 300.0, 220.0],
            confidence=0.95,
        )

        assert block.text == "Revenue"
        assert block.page == 1
        assert len(block.bbox) == 4
        assert block.confidence == 0.95

    def test_text_block_default_confidence(self):
        """Test TextBlock default confidence."""
        block = TextBlock(text="Test", page=1, bbox=[0, 0, 100, 100])
        assert block.confidence == 1.0


class TestPageText:
    """Tests for PageText dataclass."""

    def test_page_text_creation(self):
        """Test creating a PageText."""
        page = PageText(
            page_number=1,
            text="Sample text",
            blocks=[],
            width=612.0,
            height=792.0,
        )

        assert page.page_number == 1
        assert page.text == "Sample text"
        assert page.width == 612.0
        assert page.height == 792.0
        assert page.is_scanned is False

    def test_page_text_with_blocks(self):
        """Test PageText with text blocks."""
        blocks = [
            TextBlock(text="Hello", page=1, bbox=[0, 0, 50, 10]),
            TextBlock(text="World", page=1, bbox=[60, 0, 110, 10]),
        ]

        page = PageText(
            page_number=1,
            text="Hello World",
            blocks=blocks,
            width=612.0,
            height=792.0,
        )

        assert len(page.blocks) == 2
        assert page.blocks[0].text == "Hello"
        assert page.blocks[1].text == "World"


class TestOCRResult:
    """Tests for OCRResult dataclass."""

    def test_ocr_result_creation(self):
        """Test creating an OCRResult."""
        pages = [
            PageText(page_number=1, text="Page 1", blocks=[], width=612, height=792),
            PageText(page_number=2, text="Page 2", blocks=[], width=612, height=792),
        ]

        result = OCRResult(
            pages=pages,
            page_count=2,
            is_scanned=False,
            confidence=0.95,
        )

        assert len(result.pages) == 2
        assert result.page_count == 2
        assert result.is_scanned is False
        assert result.confidence == 0.95
