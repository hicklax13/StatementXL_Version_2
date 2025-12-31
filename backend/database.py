"""
Database configuration and session management.

Provides SQLAlchemy engine, session factory, and FastAPI dependency.
"""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.config import get_settings

settings = get_settings()

# Create SQLAlchemy engine
# SQLite doesn't support pool_size/max_overflow
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Yields:
        Database session that is automatically closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    # Import models to ensure they're registered with Base
    from backend.models import user  # noqa: F401
    from backend.models import organization  # noqa: F401
    from backend.models import job  # noqa: F401
    from backend.models import integration  # noqa: F401
    from backend.models import api_key  # noqa: F401
    from backend.models import webhook  # noqa: F401
    from backend.models import audit  # noqa: F401
    from backend.models import analytics  # noqa: F401
    from backend.models import template_library  # noqa: F401

    Base.metadata.create_all(bind=engine)
