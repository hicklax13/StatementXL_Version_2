"""
OCR service for PDF text extraction.

Provides text extraction from PDFs using pdfplumber as primary
with Tesseract OCR fallback for scanned documents.
"""
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber
import structlog
from PIL import Image

from backend.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class TextBlock:
    """Represents an extracted text block with position."""

    text: str
    page: int
    bbox: List[float]  # [x0, y0, x1, y1]
    confidence: float = 1.0


@dataclass
class PageText:
    """Extracted text from a single page."""

    page_number: int
    text: str
    blocks: List[TextBlock] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    is_scanned: bool = False


@dataclass
class OCRResult:
    """Complete OCR result for a document."""

    pages: List[PageText]
    page_count: int
    is_scanned: bool = False
    confidence: float = 1.0


class OCRService:
    """
    Service for extracting text from PDF documents.

    Uses pdfplumber for native PDFs and falls back to Tesseract
    for scanned documents.
    """

    def __init__(self):
        """Initialize OCR service."""
        self._tesseract_available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        """Check if Tesseract OCR is available."""
        try:
            import pytesseract

            if settings.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.warning("Tesseract OCR not available", error=str(e))
            return False

    def extract_text(self, pdf_path: Path) -> OCRResult:
        """
        Extract text from a PDF file.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            OCRResult containing extracted text and metadata.
        """
        logger.info("Extracting text from PDF", path=str(pdf_path))

        pages: List[PageText] = []
        is_scanned = False

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_text = self._extract_page_text(page, page_num)

                    # Check if page appears to be scanned (very little text)
                    if len(page_text.text.strip()) < 50 and self._tesseract_available:
                        logger.info("Page appears scanned, using OCR", page=page_num)
                        page_text = self._ocr_page(page, page_num)
                        page_text.is_scanned = True
                        is_scanned = True

                    pages.append(page_text)

            # Calculate overall confidence
            if pages:
                total_confidence = sum(
                    sum(b.confidence for b in p.blocks) / max(len(p.blocks), 1)
                    for p in pages
                ) / len(pages)
            else:
                total_confidence = 0.0

            return OCRResult(
                pages=pages,
                page_count=len(pages),
                is_scanned=is_scanned,
                confidence=total_confidence,
            )

        except Exception as e:
            logger.error("Failed to extract text from PDF", path=str(pdf_path), error=str(e))
            raise

    def _extract_page_text(self, page: pdfplumber.page.Page, page_num: int) -> PageText:
        """
        Extract text from a single pdfplumber page.

        Args:
            page: pdfplumber page object.
            page_num: Page number (1-indexed).

        Returns:
            PageText with extracted content.
        """
        blocks: List[TextBlock] = []

        # Extract words with bounding boxes
        words = page.extract_words(
            keep_blank_chars=True,
            x_tolerance=3,
            y_tolerance=3,
        )

        for word in words:
            bbox = [
                float(word["x0"]),
                float(word["top"]),
                float(word["x1"]),
                float(word["bottom"]),
            ]
            blocks.append(
                TextBlock(
                    text=word["text"],
                    page=page_num,
                    bbox=bbox,
                    confidence=1.0,  # pdfplumber native text is high confidence
                )
            )

        # Get full page text
        full_text = page.extract_text() or ""

        return PageText(
            page_number=page_num,
            text=full_text,
            blocks=blocks,
            width=float(page.width),
            height=float(page.height),
            is_scanned=False,
        )

    def _ocr_page(self, page: pdfplumber.page.Page, page_num: int) -> PageText:
        """
        Perform OCR on a scanned page.

        Args:
            page: pdfplumber page object.
            page_num: Page number (1-indexed).

        Returns:
            PageText with OCR results.
        """
        try:
            import pytesseract

            # Convert page to image
            img = page.to_image(resolution=300)
            pil_image = img.original

            # Perform OCR with detailed output
            ocr_data = pytesseract.image_to_data(
                pil_image,
                output_type=pytesseract.Output.DICT,
            )

            blocks: List[TextBlock] = []
            texts: List[str] = []

            for i, text in enumerate(ocr_data["text"]):
                if text.strip():
                    confidence = float(ocr_data["conf"][i]) / 100.0
                    if confidence > 0:  # Filter out low-confidence garbage
                        bbox = [
                            float(ocr_data["left"][i]),
                            float(ocr_data["top"][i]),
                            float(ocr_data["left"][i] + ocr_data["width"][i]),
                            float(ocr_data["top"][i] + ocr_data["height"][i]),
                        ]
                        blocks.append(
                            TextBlock(
                                text=text,
                                page=page_num,
                                bbox=bbox,
                                confidence=confidence,
                            )
                        )
                        texts.append(text)

            return PageText(
                page_number=page_num,
                text=" ".join(texts),
                blocks=blocks,
                width=float(page.width),
                height=float(page.height),
                is_scanned=True,
            )

        except Exception as e:
            logger.error("OCR failed for page", page=page_num, error=str(e))
            # Return empty result on failure
            return PageText(
                page_number=page_num,
                text="",
                blocks=[],
                width=float(page.width),
                height=float(page.height),
                is_scanned=True,
            )

    def get_page_count(self, pdf_path: Path) -> int:
        """
        Get the number of pages in a PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Number of pages.
        """
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)


# Singleton instance
_ocr_service_instance: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """Get singleton OCRService instance."""
    global _ocr_service_instance
    if _ocr_service_instance is None:
        _ocr_service_instance = OCRService()
    return _ocr_service_instance
