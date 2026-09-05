"""Tests for ServiceTitan API client with retry logic."""

from datetime import date
from typing import Any

import pytest
import respx
from httpx import Response

from core.config import Settings
from integrations.servicetitan.client import (
    ServiceTitanAuthError,
    ServiceTitanClient,
)


@pytest.fixture
def st_settings() -> Settings:
    """Settings with ServiceTitan config."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        servicetitan_api_key="test-key-12345",
        servicetitan_api_endpoint="https://api.servicetitan.test",
    )


@pytest.fixture
def st_client(st_settings: Settings) -> ServiceTitanClient:
    """ServiceTitan client with test settings."""
    return ServiceTitanClient(st_settings)


@pytest.mark.asyncio
async def test_fetch_invoices_success(
    st_client: ServiceTitanClient,
    sample_st_invoices: list[dict[str, Any]],
) -> None:
    """Test successful invoice fetch."""
    date_from = date(2026, 9, 1)
    date_to = date(2026, 9, 5)

    with respx.mock:
        respx.get(
            "https://api.servicetitan.test/invoices",
            params={
                "dateFrom": "2026-09-01",
                "dateTo": "2026-09-05",
                "limit": 1000,
            },
        ).mock(return_value=Response(200, json={"data": sample_st_invoices}))

        invoices = await st_client.fetch_invoices(date_from, date_to)
        assert len(invoices) == 2
        assert invoices[0]["id"] == "INV-001"


@pytest.mark.asyncio
async def test_fetch_invoices_auth_error(st_client: ServiceTitanClient) -> None:
    """Test auth error handling (401)."""
    date_from = date(2026, 9, 1)
    date_to = date(2026, 9, 5)

    with respx.mock:
        respx.get(
            "https://api.servicetitan.test/invoices",
        ).mock(return_value=Response(401, json={"error": "Unauthorized"}))

        with pytest.raises(ServiceTitanAuthError):
            await st_client.fetch_invoices(date_from, date_to)


@pytest.mark.asyncio
async def test_fetch_invoices_rate_limit_retry(
    st_client: ServiceTitanClient,
    sample_st_invoices: list[dict[str, Any]],
) -> None:
    """Test rate limit retry logic."""
    date_from = date(2026, 9, 1)
    date_to = date(2026, 9, 5)

    with respx.mock:
        route = respx.get("https://api.servicetitan.test/invoices")
        route.side_effect = [
            Response(429),  # First attempt: rate limited
            Response(200, json={"data": sample_st_invoices}),  # Retry: success
        ]

        invoices = await st_client.fetch_invoices(date_from, date_to)
        assert len(invoices) == 2


@pytest.mark.asyncio
async def test_fetch_payments_success(
    st_client: ServiceTitanClient,
) -> None:
    """Test successful payment fetch."""
    date_from = date(2026, 9, 1)
    date_to = date(2026, 9, 5)

    payments = [
        {
            "id": "PAY-001",
            "invoiceId": "INV-001",
            "amount": "5000.00",
            "date": "2026-09-01",
        },
    ]

    with respx.mock:
        respx.get(
            "https://api.servicetitan.test/payments",
            params={
                "dateFrom": "2026-09-01",
                "dateTo": "2026-09-05",
                "limit": 1000,
            },
        ).mock(return_value=Response(200, json={"data": payments}))

        result = await st_client.fetch_payments(date_from, date_to)
        assert len(result) == 1
        assert result[0]["id"] == "PAY-001"
