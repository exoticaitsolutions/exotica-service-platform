"""Repositories for reconciliation runs and discrepancies."""

from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.tenancy import TenantScopedRepository
from modules.reconciliation.models import (
    DiscrepancyModel,
    ReconciliationRunModel,
)


class ReconciliationRunRepository(TenantScopedRepository[ReconciliationRunModel]):
    """Repository for reconciliation runs."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, ReconciliationRunModel)

    async def get(self, tenant_id: str, run_id: str) -> ReconciliationRunModel | None:
        """Get a reconciliation run by ID.

        Args:
            tenant_id: Tenant ID (for tenant isolation)
            run_id: Run ID

        Returns:
            ReconciliationRunModel or None if not found or cross-tenant access

        Raises:
            AssertionError: tenant_id is None
        """
        assert tenant_id, "tenant_id is required"

        query = self._base_query(tenant_id).where(ReconciliationRunModel.id == run_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_run(self, tenant_id: str) -> ReconciliationRunModel | None:
        """Get the active (in_progress) run for a tenant, if any.

        Args:
            tenant_id: Tenant ID

        Returns:
            Active ReconciliationRunModel or None

        Raises:
            AssertionError: tenant_id is None
        """
        assert tenant_id, "tenant_id is required"

        query = self._base_query(tenant_id).where(ReconciliationRunModel.status == "in_progress")
        result = await self.session.execute(query)
        return result.scalars().first()

    async def create_run(
        self,
        tenant_id: str,
        date_from: str,
        date_to: str,
        trigger_source: str = "api",
    ) -> ReconciliationRunModel:
        """Create a new reconciliation run.

        Args:
            tenant_id: Tenant ID
            date_from: Start date (ISO format)
            date_to: End date (ISO format)
            trigger_source: Why reconciliation was triggered

        Returns:
            Newly created ReconciliationRunModel
        """
        run = ReconciliationRunModel(
            tenant_id=tenant_id,
            date_from=date_from,
            date_to=date_to,
            trigger_source=trigger_source,
            status="in_progress",
        )
        self.session.add(run)
        await self.session.flush()
        return run


class DiscrepancyRepository(TenantScopedRepository[DiscrepancyModel]):
    """Repository for discrepancies with filtering and pagination."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(session, DiscrepancyModel)

    async def list_by_run(
        self,
        tenant_id: str,
        run_id: str,
        severity: str | None = None,
        discrepancy_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DiscrepancyModel], int]:
        """List discrepancies for a specific run with optional filtering.

        Args:
            tenant_id: Tenant ID
            run_id: Run ID
            severity: Filter by severity (info, warning, error) or None for all
            discrepancy_type: Filter by type or None for all
            limit: Max results to return
            offset: Number of results to skip

        Returns:
            Tuple of (list of discrepancies, total count)
        """
        assert tenant_id, "tenant_id is required"
        assert run_id, "run_id is required"

        conditions = [
            DiscrepancyModel.tenant_id == tenant_id,
            DiscrepancyModel.run_id == run_id,
        ]
        if severity:
            conditions.append(DiscrepancyModel.severity == severity)
        if discrepancy_type:
            conditions.append(DiscrepancyModel.type == discrepancy_type)

        count_query = select(DiscrepancyModel).where(and_(*conditions))
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())

        query = (
            select(DiscrepancyModel)
            .where(and_(*conditions))
            .order_by(DiscrepancyModel.detected_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all(), total

    async def list_for_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
        severity: str | None = None,
        discrepancy_type: str | None = None,
        min_amount: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DiscrepancyModel], int]:
        """List discrepancies across all runs for a tenant with optional filtering.

        Args:
            tenant_id: Tenant ID
            status: Filter by status (open, awaiting_approval, resolved, dismissed)
            severity: Filter by severity (info, warning, error)
            discrepancy_type: Filter by type
            min_amount: Filter to discrepancies with difference >= this amount
            limit: Max results to return
            offset: Number of results to skip

        Returns:
            Tuple of (list of discrepancies, total count)
        """
        assert tenant_id, "tenant_id is required"

        conditions = [DiscrepancyModel.tenant_id == tenant_id]
        if status:
            conditions.append(DiscrepancyModel.status == status)
        if severity:
            conditions.append(DiscrepancyModel.severity == severity)
        if discrepancy_type:
            conditions.append(DiscrepancyModel.type == discrepancy_type)
        if min_amount:
            from decimal import Decimal
            conditions.append(DiscrepancyModel.difference >= Decimal(min_amount))

        count_query = select(DiscrepancyModel).where(and_(*conditions))
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())

        query = (
            select(DiscrepancyModel)
            .where(and_(*conditions))
            .order_by(DiscrepancyModel.detected_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all(), total

    async def get(self, tenant_id: str, discrepancy_id: str) -> DiscrepancyModel | None:
        """Get a single discrepancy by ID.

        Args:
            tenant_id: Tenant ID (for tenant isolation)
            discrepancy_id: Discrepancy ID

        Returns:
            DiscrepancyModel or None if not found or cross-tenant access
        """
        assert tenant_id, "tenant_id is required"

        query = self._base_query(tenant_id).where(DiscrepancyModel.id == discrepancy_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
