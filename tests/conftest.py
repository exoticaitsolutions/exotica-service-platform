"""Test fixtures and configuration for pytest."""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import pytest
import uuid6
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import create_app
from core.config import Settings
from core.database import Base
from core.secrets import SecretsProvider
from core.tenancy import TenantModel


class FakeSecretsProvider(SecretsProvider):
    """Test secrets provider that returns values from a dict."""

    def __init__(self) -> None:
        """Initialize with test secrets."""
        self.secrets = {
            "dev-jwt-secret": "test-jwt-secret-key-must-be-at-least-32-characters-long!!!",
        }

    async def get_secret(self, key: str) -> str:
        """Get a secret from the test dict.

        Args:
            key: Secret key.

        Returns:
            Secret value.

        Raises:
            KeyError: If key not found.
        """
        if key not in self.secrets:
            raise KeyError(f"Secret {key} not found")
        return self.secrets[key]


@pytest.fixture
def fake_secrets_provider() -> FakeSecretsProvider:
    """Provide a fake secrets provider for tests."""
    return FakeSecretsProvider()


@pytest.fixture
def test_settings() -> Settings:
    """Provide test settings."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        environment="local",
        log_level="WARNING",
        secrets_provider="env",
        jwt_secret_arn="dev-jwt-secret",
        quickbooks_environment="sandbox",
    )


@pytest.fixture
async def test_engine(test_settings: Settings) -> AsyncGenerator[Any, None]:
    """Create a test database engine."""
    engine = create_async_engine(
        test_settings.database_url,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def test_db_with_tenant(test_session: AsyncSession) -> tuple[AsyncSession, str]:
    """Provide a test session with a test tenant pre-created.

    Returns:
        A tuple of (session, tenant_id).
    """
    tenant = TenantModel(
        id=str(uuid6.uuid7()),
        name="Test Tenant",
        is_active=True,
    )
    test_session.add(tenant)
    await test_session.commit()
    return test_session, tenant.id


@pytest.fixture
def test_token(fake_secrets_provider: FakeSecretsProvider) -> str:
    """Generate a test JWT token."""
    from jose import jwt

    claims = {
        "sub": "test-user",
        "tenant_id": str(uuid4()),
        "actor_type": "user",
        "scopes": ["read"],
        "exp": 9999999999,
    }
    token: str = jwt.encode(
        claims,
        fake_secrets_provider.secrets["dev-jwt-secret"],
        algorithm="HS256",
    )
    return token


@pytest.fixture
def test_client(test_settings: Settings) -> TestClient:
    """Provide a FastAPI test client.

    Note: This client uses an in-memory database for speed.
    For integration tests, use test_session directly.
    """
    app = create_app()
    return TestClient(app)


@pytest.fixture
async def test_tenant_id() -> str:
    """Generate a test tenant ID."""
    return str(uuid6.uuid7())


@pytest.fixture
def sample_st_invoices() -> list[dict[str, Any]]:
    """Sample ServiceTitan invoice responses."""
    return [
        {
            "id": "INV-001",
            "customerId": "CUST-001",
            "customerName": "Acme Corp",
            "date": "2026-09-01",
            "total": "5000.00",
            "paidAmount": "5000.00",
        },
        {
            "id": "INV-002",
            "customerId": "CUST-002",
            "customerName": "Beta Inc",
            "date": "2026-09-02",
            "total": "3000.00",
            "paidAmount": "1000.00",
        },
    ]


@pytest.fixture
def sample_qb_invoices() -> list[dict[str, Any]]:
    """Sample QuickBooks invoice responses."""
    return [
        {
            "Id": "QBI-001",
            "customerId": "QB-CUST-001",
            "customerName": "Acme Corp",
            "txnDate": "2026-09-01",
            "total": "5000.00",
            "paidAmount": "5000.00",
        },
        {
            "Id": "QBI-002",
            "customerId": "QB-CUST-002",
            "customerName": "Beta Inc",
            "txnDate": "2026-09-02",
            "total": "3000.00",
            "paidAmount": "3000.00",
        },
    ]


@pytest.fixture
def sample_date_range() -> tuple:
    """Sample date range for reconciliation."""
    from datetime import date

    return (date(2026, 9, 1), date(2026, 9, 5))
