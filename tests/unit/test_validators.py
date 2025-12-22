"""
Unit tests for input validation utilities.

Tests password validation, file type checking, and input sanitization.
"""
import pytest

from backend.validation import (
    PasswordValidator,
    validate_file_type,
    sanitize_filename,
    sanitize_text_input,
    check_sql_injection,
)


class TestPasswordValidator:
    """Tests for PasswordValidator class."""
    
    def test_valid_password(self):
        """Test that a strong password passes validation."""
        is_valid, errors = PasswordValidator.validate("SecurePass123")
        assert is_valid is True
        assert len(errors) == 0
    
    def test_too_short(self):
        """Test that short passwords fail."""
        is_valid, errors = PasswordValidator.validate("Short1")
        assert is_valid is False
        assert any("at least 8 characters" in err for err in errors)
    
    def test_no_uppercase(self):
        """Test that passwords without uppercase fail."""
        is_valid, errors = PasswordValidator.validate("nouppercase123")
        assert is_valid is False
        assert any("uppercase" in err for err in errors)
    
    def test_no_lowercase(self):
        """Test that passwords without lowercase fail."""
        is_valid, errors = PasswordValidator.validate("NOLOWERCASE123")
        assert is_valid is False
        assert any("lowercase" in err for err in errors)
    
    def test_no_digit(self):
        """Test that passwords without digits fail."""
        is_valid, errors = PasswordValidator.validate("NoDigitsHere")
        assert is_valid is False
        assert any("digit" in err for err in errors)
    
    def test_common_password(self):
        """Test that common passwords fail."""
        is_valid, errors = PasswordValidator.validate("password")
        assert is_valid is False
        assert any("common" in err for err in errors)
    
    def test_strength_score_weak(self):
        """Test that weak passwords get low scores."""
        score = PasswordValidator.get_strength_score("weak")
        assert score < 30
    
    def test_strength_score_strong(self):
        """Test that strong passwords get high scores."""
        score = PasswordValidator.get_strength_score("Str0ng!P@ssw0rd#2024")
        assert score > 70


class TestFileTypeValidation:
    """Tests for file type validation by magic bytes."""
    
    def test_valid_pdf(self):
        """Test PDF detection by magic bytes."""
        pdf_bytes = b"%PDF-1.4 some content"
        is_valid, detected = validate_file_type(pdf_bytes, ["pdf"])
        assert is_valid is True
        assert detected == "pdf"
    
    def test_valid_xlsx(self):
        """Test XLSX detection (ZIP format)."""
        xlsx_bytes = b"PK\x03\x04 some content"
        is_valid, detected = validate_file_type(xlsx_bytes, ["xlsx"])
        assert is_valid is True
        assert detected == "xlsx"
    
    def test_invalid_file_type(self):
        """Test rejection of unknown file types."""
        invalid_bytes = b"This is not a valid file"
        is_valid, detected = validate_file_type(invalid_bytes, ["pdf"])
        assert is_valid is False
        assert detected is None
    
    def test_multiple_expected_types(self):
        """Test detection with multiple allowed types."""
        pdf_bytes = b"%PDF-1.4 content"
        is_valid, detected = validate_file_type(pdf_bytes, ["pdf", "xlsx"])
        assert is_valid is True
        assert detected == "pdf"


class TestSanitizeFilename:
    """Tests for filename sanitization."""
    
    def test_normal_filename(self):
        """Test that normal filenames pass through."""
        result = sanitize_filename("document.pdf")
        assert result == "document.pdf"
    
    def test_path_traversal(self):
        """Test that path traversal is prevented."""
        result = sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
    
    def test_unsafe_characters(self):
        """Test that unsafe characters are removed."""
        result = sanitize_filename('file<>:"/\\|?*.pdf')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
    
    def test_empty_becomes_unnamed(self):
        """Test that empty filename becomes 'unnamed'."""
        result = sanitize_filename("")
        assert result == "unnamed"
    
    def test_max_length(self):
        """Test that long filenames are truncated."""
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) <= 50
        assert result.endswith(".pdf")


class TestSanitizeTextInput:
    """Tests for text input sanitization."""
    
    def test_normal_text(self):
        """Test that normal text passes through."""
        result = sanitize_text_input("Hello World")
        assert result == "Hello World"
    
    def test_html_stripped(self):
        """Test that HTML tags are stripped."""
        result = sanitize_text_input("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "</script>" not in result
        assert "Hello" in result
    
    def test_html_entities_escaped(self):
        """Test that HTML entities are escaped."""
        result = sanitize_text_input("a < b && c > d")
        assert "&lt;" in result or "<" not in result
    
    def test_null_bytes_removed(self):
        """Test that null bytes are removed."""
        result = sanitize_text_input("Hello\x00World")
        assert "\x00" not in result
    
    def test_whitespace_normalized(self):
        """Test that excessive whitespace is normalized."""
        result = sanitize_text_input("Hello    World")
        assert result == "Hello World"
    
    def test_max_length_enforced(self):
        """Test that max length is enforced."""
        long_text = "a" * 20000
        result = sanitize_text_input(long_text, max_length=100)
        assert len(result) <= 100


class TestSQLInjectionDetection:
    """Tests for SQL injection pattern detection."""
    
    def test_normal_text_safe(self):
        """Test that normal text is not flagged."""
        assert check_sql_injection("John Doe") is False
    
    def test_union_select_detected(self):
        """Test that UNION SELECT is detected."""
        assert check_sql_injection("1 UNION SELECT * FROM users") is True
    
    def test_drop_table_detected(self):
        """Test that DROP TABLE is detected."""
        assert check_sql_injection("'; DROP TABLE users; --") is True
    
    def test_comment_injection_detected(self):
        """Test that comment injection is detected."""
        assert check_sql_injection("admin'--") is True
