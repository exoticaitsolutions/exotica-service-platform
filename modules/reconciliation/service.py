"""Reconciliation service: orchestrate fetch, match, and persist."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import UnprocessableError
from integrations.quickbooks.client import (
    QuickBooksAuthError,
    QuickBooksClient,
    QuickBooksError,
    QuickBooksRateLimitError,
)
from integrations.servicetitan.client import (
    ServiceTitanAuthError,
    ServiceTitanClient,
    ServiceTitanError,
    ServiceTitanRateLimitError,
)
from modules.reconciliation.models import (
    DiscrepancyModel,
    QBInvoiceModel,
    ReconciliationRunModel,
    STInvoiceModel,
)

logger = structlog.get_logger()


class ReconciliationService:
    """Orchestrate reconciliation: fetch, normalize, match, and persist."""

    def __init__(
        self,
        session: AsyncSession,
        st_client: ServiceTitanClient | None = None,
        qb_client: QuickBooksClient | None = None,
    ) -> None:
        """Initialize reconciliation service.

        Args:
            session: Database session
            st_client: ServiceTitan client (default: new instance)
            qb_client: QuickBooks client (default: new instance)
        """
        self.session = session
        self.st_client = st_client or ServiceTitanClient()
        self.qb_client = qb_client or QuickBooksClient()

    async def reconcile(
        self,
        tenant_id: str,
        date_from: date,
        date_to: date,
        trigger_source: str = "api",
    ) -> ReconciliationRunModel:
        """Execute a reconciliation run synchronously.

        Fetches invoices/payments from both systems, normalizes them,
        performs basic matching, and persists results.

        Args:
            tenant_id: Tenant UUID
            date_from: Start date (inclusive)
            date_to: End date (inclusive)
            trigger_source: Why reconciliation was triggered

        Returns:
            Completed (or partial) ReconciliationRunModel

        Raises:
            UnprocessableError: Tenant credentials missing or invalid
        """
        run = ReconciliationRunModel(
            tenant_id=tenant_id,
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            trigger_source=trigger_source,
            status="in_progress",
        )
        self.session.add(run)
        await self.session.flush()

        logger.info(
            "reconciliation_started",
            run_id=run.id,
            tenant_id=tenant_id,
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
        )

        source_errors: list[dict[str, Any]] = []

        # Fetch from ServiceTitan
        st_invoices: list[dict[str, Any]] = []
        try:
            st_invoices = await self.st_client.fetch_invoices(date_from, date_to)
            logger.info(
                "servicetitan_invoices_fetched",
                run_id=run.id,
                count=len(st_invoices),
            )
        except ServiceTitanAuthError as e:
            error_msg = "ServiceTitan credentials invalid or expired"
            logger.error("servicetitan_auth_failed", error=str(e), run_id=run.id)
            source_errors.append({"source": "servicetitan", "error": error_msg})
            raise UnprocessableError(error_msg)
        except (ServiceTitanRateLimitError, ServiceTitanError) as e:
            error_msg = f"ServiceTitan API error: {type(e).__name__}"
            logger.error("servicetitan_fetch_failed", error=str(e), run_id=run.id)
            source_errors.append({"source": "servicetitan", "error": error_msg})

        # Fetch from QuickBooks
        qb_invoices: list[dict[str, Any]] = []
        try:
            qb_invoices = await self.qb_client.fetch_journal_entries(date_from, date_to)
            logger.info(
                "quickbooks_invoices_fetched",
                run_id=run.id,
                count=len(qb_invoices),
            )
        except QuickBooksAuthError as e:
            error_msg = "QuickBooks credentials invalid or expired"
            logger.error("quickbooks_auth_failed", error=str(e), run_id=run.id)
            source_errors.append({"source": "quickbooks", "error": error_msg})
            raise UnprocessableError(error_msg)
        except (QuickBooksRateLimitError, QuickBooksError) as e:
            error_msg = f"QuickBooks API error: {type(e).__name__}"
            logger.error("quickbooks_fetch_failed", error=str(e), run_id=run.id)
            source_errors.append({"source": "quickbooks", "error": error_msg})

        # Normalize and persist ST invoices
        for st_inv in st_invoices:
            st_record = STInvoiceModel(
                tenant_id=tenant_id,
                run_id=run.id,
                servicetitan_id=st_inv.get("id", ""),
                customer_id=st_inv.get("customerId", ""),
                customer_name=st_inv.get("customerName", ""),
                invoice_date=st_inv.get("date", date_from.isoformat()),
                amount=Decimal(str(st_inv.get("total", 0))),
                paid_amount=Decimal(str(st_inv.get("paidAmount", 0))),
                raw_data=st_inv,
            )
            self.session.add(st_record)

        # Normalize and persist QB invoices
        for qb_inv in qb_invoices:
            qb_record = QBInvoiceModel(
                tenant_id=tenant_id,
                run_id=run.id,
                quickbooks_id=qb_inv.get("Id", ""),
                customer_id=qb_inv.get("customerId", ""),
                customer_name=qb_inv.get("customerName", ""),
                invoice_date=qb_inv.get("txnDate", date_from.isoformat()),
                amount=Decimal(str(qb_inv.get("total", 0))),
                paid_amount=Decimal(str(qb_inv.get("paidAmount", 0))),
                raw_data=qb_inv,
            )
            self.session.add(qb_record)

        await self.session.flush()

        # Perform matching and detect discrepancies
        matched_count = await self._perform_matching(run.id, tenant_id)

        # Calculate health score
        st_count = len(st_invoices)
        qb_count = len(qb_invoices)
        discrepancy_count = abs(st_count - matched_count) + abs(qb_count - matched_count)

        if max(st_count, qb_count) > 0:
            health_score = Decimal(str(matched_count / max(st_count, qb_count)))
        else:
            health_score = Decimal("1.0")

        # Update run with final status
        run.status = "partial" if source_errors else "succeeded"
        run.servicetitan_invoice_count = st_count if st_invoices else None
        run.quickbooks_invoice_count = qb_count if qb_invoices else None
        run.matched_count = matched_count
        run.discrepancy_count = discrepancy_count
        run.health_score = health_score
        run.source_errors = source_errors
        run.completed_at = datetime.now(UTC)

        await self.session.flush()
        await self.session.commit()

        logger.info(
            "reconciliation_completed",
            run_id=run.id,
            status=run.status,
            matched_count=matched_count,
            discrepancy_count=discrepancy_count,
            health_score=float(health_score),
        )

        return run

    async def _perform_matching(
        self,
        run_id: str,
        tenant_id: str,
    ) -> int:
        """Perform matching of ST and QB invoices and detect discrepancies.

        Matches invoices by customer name and amount (with tolerance).
        Creates DiscrepancyModel records for unmatched invoices classified
        by type (missing_in_*, amount_mismatch, etc.).

        Args:
            run_id: Reconciliation run ID
            tenant_id: Tenant ID

        Returns:
            Count of matched invoices
        """
        from sqlalchemy import and_, select

        amount_tolerance = Decimal("0.01")

        st_invoices = (
            await self.session.execute(
                select(STInvoiceModel).where(
                    and_(
                        STInvoiceModel.run_id == run_id,
                        STInvoiceModel.tenant_id == tenant_id,
                    )
                )
            )
        ).scalars().all()

        qb_invoices = (
            await self.session.execute(
                select(QBInvoiceModel).where(
                    and_(
                        QBInvoiceModel.run_id == run_id,
                        QBInvoiceModel.tenant_id == tenant_id,
                    )
                )
            )
        ).scalars().all()

        matched_count = 0
        matched_st_ids = set()
        matched_qb_ids = set()

        for st_inv in st_invoices:
            for qb_inv in qb_invoices:
                if qb_inv.quickbooks_id in matched_qb_ids:
                    continue

                if (
                    st_inv.customer_name.lower() == qb_inv.customer_name.lower()
                    and abs(st_inv.amount - qb_inv.amount) <= amount_tolerance
                ):
                    matched_st_ids.add(st_inv.servicetitan_id)
                    matched_qb_ids.add(qb_inv.quickbooks_id)
                    matched_count += 1
                    break

        for st_inv in st_invoices:
            if st_inv.servicetitan_id in matched_st_ids:
                continue

            qb_match = next(
                (
                    qb
                    for qb in qb_invoices
                    if qb.customer_name.lower() == st_inv.customer_name.lower()
                    and qb.quickbooks_id not in matched_qb_ids
                ),
                None,
            )

            if not qb_match:
                discrepancy = DiscrepancyModel(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    type="missing_in_quickbooks",
                    severity="error",
                    st_invoice_id=st_inv.servicetitan_id,
                    qb_invoice_id=None,
                    customer_name=st_inv.customer_name,
                    st_amount=st_inv.amount,
                    qb_amount=None,
                    difference=st_inv.amount,
                )
                self.session.add(discrepancy)
            else:
                discrepancy = DiscrepancyModel(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    type="amount_mismatch",
                    severity="warning" if abs(st_inv.amount - qb_match.amount) < Decimal("100") else "error",
                    st_invoice_id=st_inv.servicetitan_id,
                    qb_invoice_id=qb_match.quickbooks_id,
                    customer_name=st_inv.customer_name,
                    st_amount=st_inv.amount,
                    qb_amount=qb_match.amount,
                    difference=abs(st_inv.amount - qb_match.amount),
                )
                self.session.add(discrepancy)
                matched_qb_ids.add(qb_match.quickbooks_id)

        for qb_inv in qb_invoices:
            if qb_inv.quickbooks_id not in matched_qb_ids:
                discrepancy = DiscrepancyModel(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    type="missing_in_servicetitan",
                    severity="error",
                    st_invoice_id=None,
                    qb_invoice_id=qb_inv.quickbooks_id,
                    customer_name=qb_inv.customer_name,
                    st_amount=None,
                    qb_amount=qb_inv.amount,
                    difference=qb_inv.amount,
                )
                self.session.add(discrepancy)

        await self.session.flush()
        return matched_count
