"""
Application configuration using pydantic-settings.

Loads configuration from environment variables with sensible defaults.
"""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database (SQLite for local dev, PostgreSQL for production)
    database_url: str = "sqlite:///./statementxl.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # File Storage
    upload_dir: Path = Path("./uploads")
    max_upload_size_mb: int = 50

    # Application
    debug: bool = False
    log_level: str = "INFO"

    # OCR Settings
    tesseract_cmd: Optional[str] = None

    @property
    def max_upload_size_bytes(self) -> int:
        """Get maximum upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

# Clear cache on module load
get_settings.cache_clear()
