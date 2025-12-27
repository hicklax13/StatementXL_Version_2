"""
Pytest configuration and fixtures.
"""
import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database override."""
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_pdf_content() -> bytes:
    """Generate simple PDF content for testing."""
    # Minimal valid PDF
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Revenue: $1,500,000) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF"""
    return pdf_content


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset global singleton instances before each test for proper isolation."""
    # Reset classifier singletons
    import backend.services.classifiers.rule_based as rule_based_module
    import backend.services.classifiers.hybrid as hybrid_module
    import backend.services.classifiers.embedding_based as embedding_module
    import backend.services.ontology_service as ontology_module

    # Store original values
    original_rule_instance = rule_based_module._classifier_instance
    original_hybrid_instance = hybrid_module._classifier_instance
    original_embedding_instance = embedding_module._classifier_instance
    original_ontology_instance = ontology_module._ontology_instance

    # Reset before test
    rule_based_module._classifier_instance = None
    hybrid_module._classifier_instance = None
    embedding_module._classifier_instance = None
    ontology_module._ontology_instance = None

    yield

    # Cleanup after test
    rule_based_module._classifier_instance = None
    hybrid_module._classifier_instance = None
    embedding_module._classifier_instance = None
    ontology_module._ontology_instance = None
