"""Database models for reconciliation runs and related data."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, TimestampMixin, UUIDPrimaryKey


class ReconciliationRunModel(Base, UUIDPrimaryKey, TimestampMixin):
    """Reconciliation run: state and results of fetching and matching.

    A run represents one invocation of the reconciliation process for a tenant
    over a date range. It tracks:
    - What data was fetched from each source system
    - How many matches were found
    - How many discrepancies were detected
    - Partial success if one source failed
    """

    __tablename__ = "reconciliation_runs"

    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        nullable=False,
        default="in_progress",
        comment="in_progress, succeeded, failed, partial",
    )

    date_from: Mapped[str] = mapped_column(nullable=False)  # ISO date
    date_to: Mapped[str] = mapped_column(nullable=False)  # ISO date

    trigger_source: Mapped[str] = mapped_column(
        nullable=False,
        default="api",
        comment="manual, scheduled, api",
    )

    started_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Counts from each source system
    servicetitan_invoice_count: Mapped[int | None] = mapped_column(nullable=True)
    quickbooks_invoice_count: Mapped[int | None] = mapped_column(nullable=True)
    matched_count: Mapped[int | None] = mapped_column(nullable=True)
    discrepancy_count: Mapped[int | None] = mapped_column(nullable=True)

    # Health score: matched_count / max(st_count, qb_count)
    health_score: Mapped[Decimal | None] = mapped_column(nullable=True)

    # Source errors: list of {"source": "servicetitan"|"quickbooks", "error": "..."}
    source_errors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=[],
    )

    __table_args__ = (
        Index("idx_reconciliation_runs_tenant_id", "tenant_id"),
        Index("idx_reconciliation_runs_status", "status"),
        Index("idx_reconciliation_runs_started_at", "started_at"),
    )


class STInvoiceModel(Base, UUIDPrimaryKey, TimestampMixin):
    """ServiceTitan invoice record (normalized).

    Stores invoices fetched from ServiceTitan for reconciliation.
    Append-only: no updates after initial fetch.
    """

    __tablename__ = "st_invoices"

    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(nullable=False, index=True)

    servicetitan_id: Mapped[str] = mapped_column(nullable=False)  # ST invoice ID
    customer_id: Mapped[str] = mapped_column(nullable=False)
    customer_name: Mapped[str] = mapped_column(nullable=False)

    invoice_date: Mapped[str] = mapped_column(nullable=False)  # ISO date
    amount: Mapped[Decimal] = mapped_column(nullable=False)  # USD
    paid_amount: Mapped[Decimal] = mapped_column(nullable=False)  # USD

    # Raw response from ST API (for debugging)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("idx_st_invoices_tenant_id", "tenant_id"),
        Index("idx_st_invoices_run_id", "run_id"),
    )


class QBInvoiceModel(Base, UUIDPrimaryKey, TimestampMixin):
    """QuickBooks invoice record (normalized).

    Stores invoices/journal entries fetched from QB for reconciliation.
    Append-only: no updates after initial fetch.
    """

    __tablename__ = "qb_invoices"

    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(nullable=False, index=True)

    quickbooks_id: Mapped[str] = mapped_column(nullable=False)  # QB doc ID
    customer_id: Mapped[str] = mapped_column(nullable=False)
    customer_name: Mapped[str] = mapped_column(nullable=False)

    invoice_date: Mapped[str] = mapped_column(nullable=False)  # ISO date
    amount: Mapped[Decimal] = mapped_column(nullable=False)  # USD
    paid_amount: Mapped[Decimal] = mapped_column(nullable=False)  # USD

    # Raw response from QB API (for debugging)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("idx_qb_invoices_tenant_id", "tenant_id"),
        Index("idx_qb_invoices_run_id", "run_id"),
    )


class DiscrepancyModel(Base, UUIDPrimaryKey, TimestampMixin):
    """Detected mismatch between ServiceTitan and QuickBooks.

    Records each discrepancy found during a reconciliation run,
    classified by type (missing, amount mismatch, etc.) and severity.
    Append-only after creation; status transitions tracked separately.
    """

    __tablename__ = "discrepancies"

    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(nullable=False, index=True)

    # Discrepancy metadata
    type: Mapped[str] = mapped_column(
        nullable=False,
        comment="missing_in_quickbooks, missing_in_servicetitan, amount_mismatch, "
        "underpayment, overpayment, payment_count_mismatch, timing_mismatch, duplicate_invoice",
    )
    severity: Mapped[str] = mapped_column(
        nullable=False,
        comment="info, warning, error",
    )
    status: Mapped[str] = mapped_column(
        nullable=False,
        default="open",
        comment="open, awaiting_approval, resolved, dismissed",
    )

    # Reference to source invoices (one or both may be null for missing_in_* cases)
    st_invoice_id: Mapped[str | None] = mapped_column(nullable=True, index=True)
    qb_invoice_id: Mapped[str | None] = mapped_column(nullable=True, index=True)

    customer_name: Mapped[str | None] = mapped_column(nullable=True)

    # Amounts
    st_amount: Mapped[Decimal | None] = mapped_column(nullable=True)  # USD
    qb_amount: Mapped[Decimal | None] = mapped_column(nullable=True)  # USD
    difference: Mapped[Decimal] = mapped_column(nullable=False)  # Absolute difference

    currency: Mapped[str] = mapped_column(nullable=False, default="USD")

    detected_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("idx_discrepancies_tenant_id", "tenant_id"),
        Index("idx_discrepancies_run_id", "run_id"),
        Index("idx_discrepancies_status", "status"),
        Index("idx_discrepancies_type", "type"),
        Index("idx_discrepancies_severity", "severity"),
    )
