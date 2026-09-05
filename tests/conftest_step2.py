"""Fixtures for Step 2 integration tests (ServiceTitan and QuickBooks)."""

from datetime import date
from typing import Any

import pytest


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
def sample_date_range() -> tuple[date, date]:
    """Sample date range for reconciliation."""
    return (date(2026, 9, 1), date(2026, 9, 5))
