"""
Unit tests for TableDetector service.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.services.table_detector import (
    CellData,
    ExtractedTable,
    TableDetectionResult,
    TableDetector,
    TableRow,
)


class TestTableDetector:
    """Tests for TableDetector class."""

    @pytest.fixture
    def detector(self) -> TableDetector:
        """Create detector instance."""
        return TableDetector()

    def test_init(self, detector: TableDetector):
        """Test detector initialization."""
        assert detector is not None

    def test_detect_tables_returns_result(
        self, detector: TableDetector, sample_pdf_content: bytes, temp_dir: Path
    ):
        """Test that detect_tables returns TableDetectionResult."""
        pdf_path = temp_dir / "test.pdf"
        pdf_path.write_bytes(sample_pdf_content)

        result = detector.detect_tables(pdf_path)

        assert isinstance(result, TableDetectionResult)
        assert result.page_count >= 1

    def test_detect_tables_invalid_file_raises(self, detector: TableDetector, temp_dir: Path):
        """Test that invalid file raises exception."""
        invalid_path = temp_dir / "nonexistent.pdf"

        with pytest.raises(Exception):
            detector.detect_tables(invalid_path)


class TestCellData:
    """Tests for CellData dataclass."""

    def test_cell_data_creation(self):
        """Test creating a CellData."""
        cell = CellData(
            value="$1,234.56",
            row=0,
            column=1,
            bbox=[100.0, 200.0, 200.0, 220.0],
            confidence=0.95,
            parsed_value=1234.56,
            is_numeric=True,
        )

        assert cell.value == "$1,234.56"
        assert cell.row == 0
        assert cell.column == 1
        assert cell.parsed_value == 1234.56
        assert cell.is_numeric is True

    def test_cell_data_text_cell(self):
        """Test creating a text (non-numeric) cell."""
        cell = CellData(
            value="Revenue",
            row=0,
            column=0,
            confidence=0.9,
        )

        assert cell.value == "Revenue"
        assert cell.parsed_value is None
        assert cell.is_numeric is False
        assert cell.bbox is None

    def test_cell_data_defaults(self):
        """Test CellData default values."""
        cell = CellData(value="Test", row=0, column=0)

        assert cell.confidence == 1.0
        assert cell.parsed_value is None
        assert cell.is_numeric is False
        assert cell.bbox is None


class TestTableRow:
    """Tests for TableRow dataclass."""

    def test_table_row_creation(self):
        """Test creating a TableRow."""
        cells = [
            CellData(value="Label", row=0, column=0),
            CellData(value="100", row=0, column=1, parsed_value=100.0, is_numeric=True),
        ]

        row = TableRow(cells=cells, row_index=0)

        assert len(row.cells) == 2
        assert row.row_index == 0

    def test_table_row_empty(self):
        """Test creating an empty TableRow."""
        row = TableRow(cells=[], row_index=0)
        assert len(row.cells) == 0


class TestExtractedTable:
    """Tests for ExtractedTable dataclass."""

    def test_extracted_table_creation(self):
        """Test creating an ExtractedTable."""
        rows = [
            TableRow(cells=[CellData(value="Header", row=0, column=0)], row_index=0),
            TableRow(cells=[CellData(value="Data", row=1, column=0)], row_index=1),
        ]

        table = ExtractedTable(
            page=1,
            rows=rows,
            bbox=[50.0, 100.0, 500.0, 400.0],
            confidence=0.92,
            detection_method="pdfplumber_lines",
        )

        assert table.page == 1
        assert len(table.rows) == 2
        assert table.confidence == 0.92
        assert table.detection_method == "pdfplumber_lines"

    def test_extracted_table_defaults(self):
        """Test ExtractedTable default values."""
        table = ExtractedTable(page=1, rows=[])

        assert table.bbox is None
        assert table.confidence == 1.0
        assert table.detection_method == "pdfplumber"


class TestTableDetectionResult:
    """Tests for TableDetectionResult dataclass."""

    def test_table_detection_result_creation(self):
        """Test creating a TableDetectionResult."""
        tables = [
            ExtractedTable(page=1, rows=[], confidence=0.9),
            ExtractedTable(page=2, rows=[], confidence=0.85),
        ]

        result = TableDetectionResult(tables=tables, page_count=3)

        assert len(result.tables) == 2
        assert result.page_count == 3

    def test_table_detection_result_empty(self):
        """Test TableDetectionResult with no tables."""
        result = TableDetectionResult(tables=[], page_count=1)

        assert len(result.tables) == 0
        assert result.page_count == 1
