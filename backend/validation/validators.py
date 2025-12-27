"""
Input validation and sanitization utilities.

Provides comprehensive validation for user inputs to prevent security issues.
"""
import re
import html
import unicodedata
from pathlib import Path
from typing import Optional, Tuple

from pydantic import field_validator, ValidationInfo
import structlog

logger = structlog.get_logger(__name__)


# File type magic bytes signatures
MAGIC_BYTES = {
    "pdf": [b"%PDF"],
    "xlsx": [b"PK\x03\x04"],  # ZIP-based (Office Open XML)
    "xls": [b"\xd0\xcf\x11\xe0"],  # Compound File Binary
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
}

# Dangerous filename characters
UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# HTML tag pattern
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')

# SQL injection patterns (basic detection)
SQL_INJECTION_PATTERNS = [
    re.compile(r'\b(union|select|insert|update|delete|drop|truncate)\b', re.I),
    re.compile(r'--'),
    re.compile(r';.*\b(select|insert|update|delete)\b', re.I),
]


class PasswordValidator:
    """Password strength validation."""
    
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    
    # Character class requirements
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = False  # Optional but encouraged
    
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    @classmethod
    def validate(cls, password: str) -> Tuple[bool, list[str]]:
        """
        Validate password strength.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Password must be at least {cls.MIN_LENGTH} characters")
        
        if len(password) > cls.MAX_LENGTH:
            errors.append(f"Password cannot exceed {cls.MAX_LENGTH} characters")
        
        if cls.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if cls.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if cls.REQUIRE_DIGIT and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if cls.REQUIRE_SPECIAL and not any(c in cls.SPECIAL_CHARS for c in password):
            errors.append("Password must contain at least one special character")
        
        # Check for common weak passwords
        weak_passwords = {"password", "12345678", "qwerty", "letmein", "welcome"}
        if password.lower() in weak_passwords:
            errors.append("Password is too common")
        
        return (len(errors) == 0, errors)
    
    @classmethod
    def get_strength_score(cls, password: str) -> int:
        """
        Get password strength score (0-100).

        Factors:
        - Length (up to 20 points)
        - Character variety (up to 40 points)
        - No common patterns (up to 40 points)
        """
        score = 0

        # Length score (1 point per char, max 20)
        score += min(len(password), 20)

        # Character variety (10 points each, up to 40)
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in cls.SPECIAL_CHARS for c in password)

        if has_upper:
            score += 10
        if has_lower:
            score += 10
        if has_digit:
            score += 10
        if has_special:
            score += 10

        # Penalty for lack of variety (only lowercase = weak)
        variety_count = sum([has_upper, has_lower, has_digit, has_special])
        if variety_count >= 3:
            score += 20  # Good variety bonus
        elif variety_count == 2:
            score += 10  # Some variety bonus

        # No common patterns bonus
        if not re.search(r'(.)\1{2,}', password):  # No 3+ repeated chars
            score += 5
        if not re.search(r'(012|123|234|345|456|567|678|789|abc|bcd)', password.lower()):
            score += 5
        if password.lower() not in {"password", "qwerty", "letmein", "welcome", "weak"}:
            score += 5

        return min(score, 100)


def validate_file_type(file_content: bytes, expected_types: list[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate file type by checking magic bytes.
    
    Args:
        file_content: First few bytes of file
        expected_types: List of expected file types (e.g., ["pdf", "xlsx"])
        
    Returns:
        Tuple of (is_valid, detected_type or None)
    """
    for file_type in expected_types:
        if file_type.lower() in MAGIC_BYTES:
            for signature in MAGIC_BYTES[file_type.lower()]:
                if file_content.startswith(signature):
                    return (True, file_type)
    
    return (False, None)


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.
    
    Args:
        filename: Original filename
        max_length: Maximum allowed length
        
    Returns:
        Sanitized filename
    """
    # Normalize unicode
    filename = unicodedata.normalize("NFKD", filename)
    
    # Remove path components
    filename = Path(filename).name
    
    # Remove unsafe characters
    filename = UNSAFE_FILENAME_CHARS.sub("_", filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")
    
    # Ensure filename is not empty
    if not filename:
        filename = "unnamed"
    
    # Truncate if too long (preserve extension)
    if len(filename) > max_length:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        max_name_len = max_length - len(ext) - 1 if ext else max_length
        filename = name[:max_name_len] + ("." + ext if ext else "")
    
    return filename


def sanitize_text_input(text: str, max_length: int = 10000) -> str:
    """
    Sanitize text input to prevent XSS and other attacks.
    
    Args:
        text: Raw user input
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Truncate to max length
    text = text[:max_length]
    
    # Remove null bytes
    text = text.replace("\x00", "")
    
    # Strip HTML tags
    text = HTML_TAG_PATTERN.sub("", text)
    
    # Escape remaining HTML entities
    text = html.escape(text)
    
    # Normalize whitespace
    text = " ".join(text.split())
    
    return text.strip()


def check_sql_injection(text: str) -> bool:
    """
    Check if text contains potential SQL injection patterns.
    
    Returns:
        True if suspicious patterns detected
    """
    for pattern in SQL_INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "potential_sql_injection_detected",
                pattern=pattern.pattern,
            )
            return True
    return False


def validate_email_domain(email: str, blocked_domains: Optional[list[str]] = None) -> bool:
    """
    Validate email domain is not blocked.
    
    Args:
        email: Email address to check
        blocked_domains: List of blocked domains (e.g., ["tempmail.com"])
        
    Returns:
        True if email domain is allowed
    """
    if not blocked_domains:
        return True
    
    domain = email.split("@")[-1].lower()
    return domain not in [d.lower() for d in blocked_domains]


def validate_numeric_range(
    value: float,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate numeric value is within range.
    
    Returns:
        Tuple of (is_valid, error_message or None)
    """
    if min_value is not None and value < min_value:
        return (False, f"Value must be at least {min_value}")
    
    if max_value is not None and value > max_value:
        return (False, f"Value cannot exceed {max_value}")
    
    return (True, None)


# Pydantic custom validators for common use cases
def password_validator(cls, v: str) -> str:
    """Pydantic validator for password fields."""
    is_valid, errors = PasswordValidator.validate(v)
    if not is_valid:
        raise ValueError("; ".join(errors))
    return v


def sanitized_string_validator(cls, v: str) -> str:
    """Pydantic validator that sanitizes string input."""
    return sanitize_text_input(v)
