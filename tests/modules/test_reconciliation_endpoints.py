"""Tests for reconciliation endpoints."""

from datetime import UTC, datetime
from typing import Any

import pytest
import respx
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from modules.reconciliation.models import ReconciliationRunModel


@pytest.fixture
def rec_settings() -> Settings:
    """Settings for reconciliation tests."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        servicetitan_api_key="test-key",
        quickbooks_realm_id="test-realm",
        quickbooks_client_id="test-client",
        quickbooks_client_secret="test-secret",
        quickbooks_refresh_token="test-token",
        quickbooks_environment="sandbox",
    )


@pytest.mark.asyncio
async def test_trigger_reconciliation_success(
    test_client: Any,
    test_token: str,
    test_db_with_tenant: tuple[AsyncSession, str],
    rec_settings: Settings,
    sample_st_invoices: list[dict[str, Any]],
    sample_qb_invoices: list[dict[str, Any]],
) -> None:
    """Test successful reconciliation trigger."""
    session, tenant_id = test_db_with_tenant

    request_body = {
        "tenant_id": tenant_id,
        "trigger_source": "api",
    }

    with respx.mock:
        # Mock ServiceTitan API
        respx.get(
            "https://api.servicetitan.com/invoices",
        ).mock(return_value=Response(200, json={"data": sample_st_invoices}))

        # Mock QB OAuth
        respx.post("https://oauth.platform.intuit.com/oauth2/tokens").mock(
            return_value=Response(
                200,
                json={"access_token": "test-token", "token_type": "Bearer"},
            )
        )

        # Mock QB query (sandbox)
        respx.post(
            "https://sandbox-quickbooks.api.intuit.com/v2/company/test-realm/query",
        ).mock(
            return_value=Response(
                200,
                json={"QueryResponse": {"JournalEntry": sample_qb_invoices}},
            )
        )

        response = test_client.post(
            "/accounting/reconcile",
            json=request_body,
            headers={"Authorization": f"Bearer {test_token}"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["run_id"]
        assert data["tenant_id"] == tenant_id
        assert data["status"] in ["succeeded", "partial"]


@pytest.mark.asyncio
async def test_trigger_reconciliation_with_idempotency_key(
    test_client: Any,
    test_token: str,
    test_db_with_tenant: tuple[AsyncSession, str],
    sample_st_invoices: list[dict[str, Any]],
    sample_qb_invoices: list[dict[str, Any]],
) -> None:
    """Test reconciliation with idempotency key."""
    session, tenant_id = test_db_with_tenant

    request_body = {
        "tenant_id": tenant_id,
        "trigger_source": "api",
    }

    with respx.mock:
        # Mock both APIs
        respx.get("https://api.servicetitan.com/invoices").mock(
            return_value=Response(200, json={"data": sample_st_invoices})
        )
        respx.post("https://oauth.platform.intuit.com/oauth2/tokens").mock(
            return_value=Response(
                200,
                json={"access_token": "test-token", "token_type": "Bearer"},
            )
        )
        respx.post("https://quickbooks.api.intuit.com/v2/company/test-realm/query").mock(
            return_value=Response(
                200,
                json={"QueryResponse": {"JournalEntry": sample_qb_invoices}},
            )
        )

        # First request
        response1 = test_client.post(
            "/accounting/reconcile",
            json=request_body,
            headers={
                "Authorization": f"Bearer {test_token}",
                "Idempotency-Key": "idempotent-123",
            },
        )
        assert response1.status_code == 202
        run_id_1 = response1.json()["run_id"]

        # Second request with same key should return same run_id
        response2 = test_client.post(
            "/accounting/reconcile",
            json=request_body,
            headers={
                "Authorization": f"Bearer {test_token}",
                "Idempotency-Key": "idempotent-123",
            },
        )
        assert response2.status_code == 202
        run_id_2 = response2.json()["run_id"]
        assert run_id_1 == run_id_2


@pytest.mark.asyncio
async def test_trigger_reconciliation_idempotency_key_mismatch(
    test_client: Any,
    test_token: str,
    test_db_with_tenant: tuple[AsyncSession, str],
    sample_st_invoices: list[dict[str, Any]],
    sample_qb_invoices: list[dict[str, Any]],
) -> None:
    """Test idempotency key reuse with different body returns 409."""
    session, tenant_id = test_db_with_tenant

    request_body_1 = {
        "tenant_id": tenant_id,
        "trigger_source": "api",
    }
    request_body_2 = {
        "tenant_id": tenant_id,
        "trigger_source": "manual",
    }

    with respx.mock:
        respx.get("https://api.servicetitan.com/invoices").mock(
            return_value=Response(200, json={"data": sample_st_invoices})
        )
        respx.post("https://oauth.platform.intuit.com/oauth2/tokens").mock(
            return_value=Response(
                200,
                json={"access_token": "test-token", "token_type": "Bearer"},
            )
        )
        respx.post("https://quickbooks.api.intuit.com/v2/company/test-realm/query").mock(
            return_value=Response(
                200,
                json={"QueryResponse": {"JournalEntry": sample_qb_invoices}},
            )
        )

        # First request
        response1 = test_client.post(
            "/accounting/reconcile",
            json=request_body_1,
            headers={
                "Authorization": f"Bearer {test_token}",
                "Idempotency-Key": "idempotent-456",
            },
        )
        assert response1.status_code == 202

        # Second request with same key but different body
        response2 = test_client.post(
            "/accounting/reconcile",
            json=request_body_2,
            headers={
                "Authorization": f"Bearer {test_token}",
                "Idempotency-Key": "idempotent-456",
            },
        )
        assert response2.status_code == 409
        assert response2.json()["error"] == "idempotency_key_reuse_mismatch"


@pytest.mark.asyncio
async def test_get_reconciliation_run_success(
    test_client: Any,
    test_token: str,
    test_db_with_tenant: tuple[AsyncSession, str],
) -> None:
    """Test getting a reconciliation run."""
    session, tenant_id = test_db_with_tenant

    # Create a run directly
    run = ReconciliationRunModel(
        tenant_id=tenant_id,
        date_from="2026-09-01",
        date_to="2026-09-05",
        status="succeeded",
        trigger_source="api",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        servicetitan_invoice_count=2,
        quickbooks_invoice_count=2,
        matched_count=2,
        discrepancy_count=0,
    )
    session.add(run)
    await session.commit()

    response = test_client.get(
        f"/accounting/runs/{run.id}",
        headers={"Authorization": f"Bearer {test_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run.id
    assert data["status"] == "succeeded"
    assert data["matched_count"] == 2


@pytest.mark.asyncio
async def test_get_reconciliation_run_not_found(
    test_client: Any,
    test_token: str,
) -> None:
    """Test getting a non-existent run."""
    response = test_client.get(
        "/accounting/runs/nonexistent-run-id",
        headers={"Authorization": f"Bearer {test_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_reconciliation_auth_error(
    test_client: Any,
    test_token: str,
    test_db_with_tenant: tuple[AsyncSession, str],
) -> None:
    """Test reconciliation with ServiceTitan auth error."""
    session, tenant_id = test_db_with_tenant

    request_body = {
        "tenant_id": tenant_id,
        "trigger_source": "api",
    }

    with respx.mock:
        # Mock ServiceTitan returning 401
        respx.get("https://api.servicetitan.com/invoices").mock(
            return_value=Response(401, json={"error": "Unauthorized"})
        )

        response = test_client.post(
            "/accounting/reconcile",
            json=request_body,
            headers={"Authorization": f"Bearer {test_token}"},
        )

        assert response.status_code == 422
        assert "credentials" in response.json()["message"].lower()
