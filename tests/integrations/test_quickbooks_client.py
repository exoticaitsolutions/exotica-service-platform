"""Tests for QuickBooks API client with OAuth2 and retry logic."""

from datetime import date
from typing import Any

import pytest
import respx
from httpx import Response

from core.config import Settings
from integrations.quickbooks.client import (
    QuickBooksAuthError,
    QuickBooksClient,
)


@pytest.fixture
def qb_settings() -> Settings:
    """Settings with QuickBooks config."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        quickbooks_realm_id="test-realm-123",
        quickbooks_client_id="test-client-id",
        quickbooks_client_secret="test-client-secret",
        quickbooks_refresh_token="test-refresh-token",
        quickbooks_environment="sandbox",
    )


@pytest.fixture
def qb_client(qb_settings: Settings) -> QuickBooksClient:
    """QuickBooks client with test settings."""
    return QuickBooksClient(qb_settings)


@pytest.mark.asyncio
async def test_fetch_journal_entries_success(
    qb_client: QuickBooksClient,
    sample_qb_invoices: list[dict[str, Any]],
) -> None:
    """Test successful journal entry fetch."""
    date_from = date(2026, 9, 1)
    date_to = date(2026, 9, 5)

    with respx.mock:
        # Mock OAuth token endpoint
        respx.post("https://oauth.platform.intuit.com/oauth2/tokens").mock(
            return_value=Response(
                200,
                json={"access_token": "test-access-token", "token_type": "Bearer"},
            )
        )

        # Mock query endpoint (sandbox)
        respx.post(
            "https://sandbox-quickbooks.api.intuit.com/v2/company/test-realm-123/query",
        ).mock(
            return_value=Response(
                200,
                json={"QueryResponse": {"JournalEntry": sample_qb_invoices}},
            )
        )

        entries = await qb_client.fetch_journal_entries(date_from, date_to)
        assert len(entries) == 2
        assert entries[0]["Id"] == "QBI-001"


@pytest.mark.asyncio
async def test_fetch_journal_entries_auth_error(qb_client: QuickBooksClient) -> None:
    """Test auth error handling (401 triggers token refresh, then fails)."""
    date_from = date(2026, 9, 1)
    date_to = date(2026, 9, 5)

    with respx.mock:
        # Mock OAuth token endpoint to fail
        respx.post("https://oauth.platform.intuit.com/oauth2/tokens").mock(
            return_value=Response(401, json={"error": "invalid_client"})
        )

        with pytest.raises(QuickBooksAuthError):
            await qb_client.fetch_journal_entries(date_from, date_to)


@pytest.mark.asyncio
async def test_fetch_customers_success(
    qb_client: QuickBooksClient,
) -> None:
    """Test successful customer fetch."""
    customers = [
        {"Id": "1", "DisplayName": "Acme Corp"},
        {"Id": "2", "DisplayName": "Beta Inc"},
    ]

    with respx.mock:
        respx.post("https://oauth.platform.intuit.com/oauth2/tokens").mock(
            return_value=Response(
                200,
                json={"access_token": "test-access-token", "token_type": "Bearer"},
            )
        )

        respx.post(
            "https://sandbox-quickbooks.api.intuit.com/v2/company/test-realm-123/query",
        ).mock(return_value=Response(200, json={"QueryResponse": {"Customer": customers}}))

        result = await qb_client.fetch_customers()
        assert len(result) == 2
        assert result[0]["DisplayName"] == "Acme Corp"


@pytest.mark.asyncio
async def test_token_refresh_on_401(
    qb_client: QuickBooksClient,
    sample_qb_invoices: list[dict[str, Any]],
) -> None:
    """Test that 401 triggers token refresh and retry."""
    date_from = date(2026, 9, 1)
    date_to = date(2026, 9, 5)

    with respx.mock:
        # First token request
        respx.post("https://oauth.platform.intuit.com/oauth2/tokens").mock(
            return_value=Response(
                200,
                json={"access_token": "old-token", "token_type": "Bearer"},
            )
        )

        # First request fails with 401, triggers token refresh
        route = respx.post(
            "https://sandbox-quickbooks.api.intuit.com/v2/company/test-realm-123/query",
        )
        route.side_effect = [
            Response(401),  # First attempt: unauthorized (triggers refresh)
            Response(
                200,
                json={"QueryResponse": {"JournalEntry": sample_qb_invoices}},
            ),  # Retry: success (with new token)
        ]

        entries = await qb_client.fetch_journal_entries(date_from, date_to)
        assert len(entries) == 2
