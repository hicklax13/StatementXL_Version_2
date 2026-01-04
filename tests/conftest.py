"""
Pytest configuration and fixtures.

Provides comprehensive test fixtures for:
- Database sessions (in-memory SQLite)
- Test client with authentication
- Sample users, organizations, and data
- Temporary files and directories
"""
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Dict, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.models.user import User, UserRole
from backend.models.organization import Organization, OrganizationMember, OrganizationRole
from backend.models.api_key import APIKey


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


# =============================================================================
# User Fixtures
# =============================================================================

@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.V6P4rOhFBJqPHi",  # "testpassword"
        full_name="Test User",
        role=UserRole.ANALYST,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin_user(db_session: Session) -> User:
    """Create a test admin user."""
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.V6P4rOhFBJqPHi",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# =============================================================================
# Organization Fixtures
# =============================================================================

@pytest.fixture
def test_organization(db_session: Session, test_user: User) -> Organization:
    """Create a test organization with the test user as owner."""
    org = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        slug="test-org",
        owner_id=test_user.id,
    )
    db_session.add(org)
    db_session.commit()

    # Add user as owner member
    member = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=test_user.id,
        role=OrganizationRole.OWNER,
    )
    db_session.add(member)

    # Update user's default org
    test_user.default_organization_id = org.id
    db_session.commit()
    db_session.refresh(org)

    return org


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest.fixture
def auth_headers(test_user: User) -> Dict[str, str]:
    """Generate authentication headers for test user."""
    from backend.auth.jwt import create_access_token

    token = create_access_token(
        data={"sub": str(test_user.id)},
        expires_delta=timedelta(hours=1),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin_user: User) -> Dict[str, str]:
    """Generate authentication headers for admin user."""
    from backend.auth.jwt import create_access_token

    token = create_access_token(
        data={"sub": str(test_admin_user.id)},
        expires_delta=timedelta(hours=1),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authenticated_client(client: TestClient, auth_headers: Dict[str, str]) -> TestClient:
    """Create a test client with authentication headers pre-configured."""
    client.headers.update(auth_headers)
    return client


# =============================================================================
# API Key Fixtures
# =============================================================================

@pytest.fixture
def test_api_key(db_session: Session, test_organization: Organization, test_user: User) -> tuple:
    """Create a test API key and return (APIKey, full_key_value)."""
    full_key, key_prefix, key_hash = APIKey.generate_key()

    api_key = APIKey(
        id=uuid.uuid4(),
        name="Test API Key",
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=["read", "write"],
        organization_id=test_organization.id,
        created_by_user_id=test_user.id,
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)

    return api_key, full_key


@pytest.fixture
def api_key_headers(test_api_key: tuple) -> Dict[str, str]:
    """Generate API key headers for testing."""
    _, full_key = test_api_key
    return {"X-API-Key": full_key}


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_financial_data() -> Dict[str, Any]:
    """Sample financial statement data for testing."""
    return {
        "revenue": 1500000.00,
        "cost_of_goods_sold": 900000.00,
        "gross_profit": 600000.00,
        "operating_expenses": 350000.00,
        "operating_income": 250000.00,
        "net_income": 187500.00,
        "total_assets": 2500000.00,
        "total_liabilities": 1000000.00,
        "shareholders_equity": 1500000.00,
    }


@pytest.fixture
def sample_line_items() -> list:
    """Sample classified line items for testing."""
    return [
        {"text": "Revenue", "label": "Revenue", "confidence": 0.95},
        {"text": "Cost of Goods Sold", "label": "CostOfGoodsSold", "confidence": 0.92},
        {"text": "Gross Profit", "label": "GrossProfit", "confidence": 0.98},
        {"text": "Operating Expenses", "label": "OperatingExpenses", "confidence": 0.89},
        {"text": "Net Income", "label": "NetIncome", "confidence": 0.97},
    ]


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def set_test_environment():
    """Set environment variables for testing."""
    original_env = os.environ.copy()

    os.environ["DEBUG"] = "true"
    os.environ["DATABASE_URL"] = SQLALCHEMY_DATABASE_URL
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key"

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
