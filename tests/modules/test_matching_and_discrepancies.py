"""Tests for matching algorithm and discrepancy detection (Step 3)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from integrations.quickbooks.client import QuickBooksClient
from integrations.servicetitan.client import ServiceTitanClient
from modules.reconciliation.models import (
    DiscrepancyModel,
    QBInvoiceModel,
    ReconciliationRunModel,
    STInvoiceModel,
)
from modules.reconciliation.repositories import DiscrepancyRepository
from modules.reconciliation.service import ReconciliationService


@pytest.fixture
def st_mock() -> ServiceTitanClient:
    """Mock ServiceTitan client."""
    client = ServiceTitanClient()
    return client


@pytest.fixture
def qb_mock() -> QuickBooksClient:
    """Mock QuickBooks client."""
    client = QuickBooksClient()
    return client


@pytest.mark.asyncio
async def test_matching_exact_match(
    test_session: AsyncSession,
    st_mock: ServiceTitanClient,
    qb_mock: QuickBooksClient,
) -> None:
    """Test matching when invoices have exact amounts."""
    tenant_id = "test-tenant"
    run = ReconciliationRunModel(
        tenant_id=tenant_id,
        date_from="2026-09-01",
        date_to="2026-09-05",
        status="in_progress",
    )
    test_session.add(run)
    await test_session.flush()

    st_invoice = STInvoiceModel(
        tenant_id=tenant_id,
        run_id=run.id,
        servicetitan_id="ST-001",
        customer_id="CUST-001",
        customer_name="Acme Corp",
        invoice_date="2026-09-01",
        amount=Decimal("1000.00"),
        paid_amount=Decimal("1000.00"),
        raw_data={},
    )
    qb_invoice = QBInvoiceModel(
        tenant_id=tenant_id,
        run_id=run.id,
        quickbooks_id="QB-001",
        customer_id="QB-CUST-001",
        customer_name="Acme Corp",
        invoice_date="2026-09-01",
        amount=Decimal("1000.00"),
        paid_amount=Decimal("1000.00"),
        raw_data={},
    )
    test_session.add(st_invoice)
    test_session.add(qb_invoice)
    await test_session.flush()

    service = ReconciliationService(test_session, st_mock, qb_mock)
    matched_count = await service._perform_matching(run.id, tenant_id)

    assert matched_count == 1

    discrepancies = (
        await test_session.query(DiscrepancyModel)
        .filter(DiscrepancyModel.run_id == run.id)
        .all()
    ) if hasattr(test_session, 'query') else []
    # Note: sqlalchemy.ext.asyncio doesn't have .query(), use select() instead
    from sqlalchemy import select
    result = await test_session.execute(
        select(DiscrepancyModel).where(DiscrepancyModel.run_id == run.id)
    )
    discrepancies = result.scalars().all()
    assert len(discrepancies) == 0


@pytest.mark.asyncio
async def test_matching_missing_in_quickbooks(
    test_session: AsyncSession,
    st_mock: ServiceTitanClient,
    qb_mock: QuickBooksClient,
) -> None:
    """Test discrepancy when invoice exists only in ServiceTitan."""
    tenant_id = "test-tenant"
    run = ReconciliationRunModel(
        tenant_id=tenant_id,
        date_from="2026-09-01",
        date_to="2026-09-05",
        status="in_progress",
    )
    test_session.add(run)
    await test_session.flush()

    st_invoice = STInvoiceModel(
        tenant_id=tenant_id,
        run_id=run.id,
        servicetitan_id="ST-001",
        customer_id="CUST-001",
        customer_name="Acme Corp",
        invoice_date="2026-09-01",
        amount=Decimal("1000.00"),
        paid_amount=Decimal("1000.00"),
        raw_data={},
    )
    test_session.add(st_invoice)
    await test_session.flush()

    service = ReconciliationService(test_session, st_mock, qb_mock)
    matched_count = await service._perform_matching(run.id, tenant_id)

    assert matched_count == 0

    from sqlalchemy import select
    result = await test_session.execute(
        select(DiscrepancyModel).where(DiscrepancyModel.run_id == run.id)
    )
    discrepancies = result.scalars().all()
    assert len(discrepancies) == 1
    assert discrepancies[0].type == "missing_in_quickbooks"
    assert discrepancies[0].severity == "error"
    assert discrepancies[0].st_invoice_id == "ST-001"
    assert discrepancies[0].qb_invoice_id is None


@pytest.mark.asyncio
async def test_matching_missing_in_servicetitan(
    test_session: AsyncSession,
    st_mock: ServiceTitanClient,
    qb_mock: QuickBooksClient,
) -> None:
    """Test discrepancy when invoice exists only in QuickBooks."""
    tenant_id = "test-tenant"
    run = ReconciliationRunModel(
        tenant_id=tenant_id,
        date_from="2026-09-01",
        date_to="2026-09-05",
        status="in_progress",
    )
    test_session.add(run)
    await test_session.flush()

    qb_invoice = QBInvoiceModel(
        tenant_id=tenant_id,
        run_id=run.id,
        quickbooks_id="QB-001",
        customer_id="QB-CUST-001",
        customer_name="Acme Corp",
        invoice_date="2026-09-01",
        amount=Decimal("1000.00"),
        paid_amount=Decimal("1000.00"),
        raw_data={},
    )
    test_session.add(qb_invoice)
    await test_session.flush()

    service = ReconciliationService(test_session, st_mock, qb_mock)
    matched_count = await service._perform_matching(run.id, tenant_id)

    assert matched_count == 0

    from sqlalchemy import select
    result = await test_session.execute(
        select(DiscrepancyModel).where(DiscrepancyModel.run_id == run.id)
    )
    discrepancies = result.scalars().all()
    assert len(discrepancies) == 1
    assert discrepancies[0].type == "missing_in_servicetitan"
    assert discrepancies[0].severity == "error"
    assert discrepancies[0].st_invoice_id is None
    assert discrepancies[0].qb_invoice_id == "QB-001"


@pytest.mark.asyncio
async def test_matching_amount_mismatch(
    test_session: AsyncSession,
    st_mock: ServiceTitanClient,
    qb_mock: QuickBooksClient,
) -> None:
    """Test discrepancy when amounts differ."""
    tenant_id = "test-tenant"
    run = ReconciliationRunModel(
        tenant_id=tenant_id,
        date_from="2026-09-01",
        date_to="2026-09-05",
        status="in_progress",
    )
    test_session.add(run)
    await test_session.flush()

    st_invoice = STInvoiceModel(
        tenant_id=tenant_id,
        run_id=run.id,
        servicetitan_id="ST-001",
        customer_id="CUST-001",
        customer_name="Acme Corp",
        invoice_date="2026-09-01",
        amount=Decimal("1000.00"),
        paid_amount=Decimal("1000.00"),
        raw_data={},
    )
    qb_invoice = QBInvoiceModel(
        tenant_id=tenant_id,
        run_id=run.id,
        quickbooks_id="QB-001",
        customer_id="QB-CUST-001",
        customer_name="Acme Corp",
        invoice_date="2026-09-01",
        amount=Decimal("950.00"),  # Different amount
        paid_amount=Decimal("950.00"),
        raw_data={},
    )
    test_session.add(st_invoice)
    test_session.add(qb_invoice)
    await test_session.flush()

    service = ReconciliationService(test_session, st_mock, qb_mock)
    matched_count = await service._perform_matching(run.id, tenant_id)

    assert matched_count == 0

    from sqlalchemy import select
    result = await test_session.execute(
        select(DiscrepancyModel).where(DiscrepancyModel.run_id == run.id)
    )
    discrepancies = result.scalars().all()
    assert len(discrepancies) == 1
    assert discrepancies[0].type == "amount_mismatch"
    assert discrepancies[0].st_amount == Decimal("1000.00")
    assert discrepancies[0].qb_amount == Decimal("950.00")
    assert discrepancies[0].difference == Decimal("50.00")


@pytest.mark.asyncio
async def test_discrepancy_repository_list_by_run(
    test_session: AsyncSession,
) -> None:
    """Test listing discrepancies by run with filtering."""
    tenant_id = "test-tenant"
    run = ReconciliationRunModel(
        tenant_id=tenant_id,
        date_from="2026-09-01",
        date_to="2026-09-05",
        status="in_progress",
    )
    test_session.add(run)
    await test_session.flush()

    # Create two discrepancies with different severities
    d1 = DiscrepancyModel(
        tenant_id=tenant_id,
        run_id=run.id,
        type="missing_in_quickbooks",
        severity="error",
        st_invoice_id="ST-001",
        difference=Decimal("1000.00"),
    )
    d2 = DiscrepancyModel(
        tenant_id=tenant_id,
        run_id=run.id,
        type="amount_mismatch",
        severity="warning",
        st_invoice_id="ST-002",
        qb_invoice_id="QB-002",
        difference=Decimal("50.00"),
    )
    test_session.add(d1)
    test_session.add(d2)
    await test_session.flush()

    repo = DiscrepancyRepository(test_session)

    all_discrepancies, total = await repo.list_by_run(tenant_id, run.id)
    assert len(all_discrepancies) == 2
    assert total == 2

    error_only, error_total = await repo.list_by_run(
        tenant_id, run.id, severity="error"
    )
    assert len(error_only) == 1
    assert error_only[0].severity == "error"

    missing_only, missing_total = await repo.list_by_run(
        tenant_id, run.id, discrepancy_type="missing_in_quickbooks"
    )
    assert len(missing_only) == 1
    assert missing_only[0].type == "missing_in_quickbooks"


@pytest.mark.asyncio
async def test_discrepancy_repository_list_for_tenant(
    test_session: AsyncSession,
) -> None:
    """Test listing discrepancies across runs with filtering."""
    tenant_id = "test-tenant"
    run1 = ReconciliationRunModel(
        tenant_id=tenant_id,
        date_from="2026-09-01",
        date_to="2026-09-05",
        status="succeeded",
    )
    run2 = ReconciliationRunModel(
        tenant_id=tenant_id,
        date_from="2026-08-01",
        date_to="2026-08-31",
        status="succeeded",
    )
    test_session.add(run1)
    test_session.add(run2)
    await test_session.flush()

    # Create discrepancies across both runs
    d1 = DiscrepancyModel(
        tenant_id=tenant_id,
        run_id=run1.id,
        type="missing_in_quickbooks",
        severity="error",
        status="open",
        st_invoice_id="ST-001",
        difference=Decimal("1000.00"),
    )
    d2 = DiscrepancyModel(
        tenant_id=tenant_id,
        run_id=run2.id,
        type="amount_mismatch",
        severity="warning",
        status="resolved",
        st_invoice_id="ST-002",
        difference=Decimal("50.00"),
    )
    test_session.add(d1)
    test_session.add(d2)
    await test_session.flush()

    repo = DiscrepancyRepository(test_session)

    all_disc, total = await repo.list_for_tenant(tenant_id)
    assert total == 2

    open_only, open_total = await repo.list_for_tenant(tenant_id, status="open")
    assert open_total == 1
    assert open_only[0].status == "open"

    large_only, large_total = await repo.list_for_tenant(
        tenant_id, min_amount="100.00"
    )
    assert large_total == 1
    assert large_only[0].difference >= Decimal("100.00")
