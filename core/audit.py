"""Immutable audit log for tracking all platform actions.

The audit log is append-only — there are no update or delete methods.
The repository exposes only create() and list().
Database-level triggers prevent UPDATE/DELETE even via raw SQL.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import String, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import select

from core.database import Base, UUIDPrimaryKey
from core.logging import get_logger
from core.tenancy import TenantScopedRepository


class AuditEventModel(Base, UUIDPrimaryKey):
    """Audit event record in the database.

    Mirrors the contract's AuditEvent schema. Append-only.
    Database rules prevent UPDATE/DELETE.
    """

    __tablename__ = "audit_events"

    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    action: Mapped[str] = mapped_column(nullable=False)
    actor_type: Mapped[str] = mapped_column(nullable=False)
    actor_id: Mapped[str] = mapped_column(nullable=False)
    actor_display_name: Mapped[str | None] = mapped_column(nullable=True)
    actor_email: Mapped[str | None] = mapped_column(nullable=True)
    actor_channel: Mapped[str | None] = mapped_column(nullable=True)
    target_system: Mapped[str | None] = mapped_column(nullable=True)
    target_ref: Mapped[str | None] = mapped_column(nullable=True)
    run_id: Mapped[str | None] = mapped_column(nullable=True)
    discrepancy_id: Mapped[str | None] = mapped_column(nullable=True)
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str | None] = mapped_column(nullable=True)


class AuditEventRequest(BaseModel):
    """Request payload for creating an audit event."""

    action: str
    actor_type: Literal["user", "system"]
    actor_id: str
    actor_display_name: str | None = None
    actor_email: str | None = None
    actor_channel: str | None = None
    target_system: str | None = None
    target_ref: str | None = None
    run_id: str | None = None
    discrepancy_id: str | None = None
    detail: str | None = None
    request_id: str | None = None


class AuditEventResponse(BaseModel):
    """Response for an audit event (mirrors contract schema)."""

    event_id: str
    tenant_id: str
    occurred_at: str
    action: str
    actor: dict[str, Any]
    target_system: str | None
    target_ref: str | None
    run_id: str | None
    discrepancy_id: str | None
    detail: str | None
    request_id: str | None


class AuditRepository(TenantScopedRepository[AuditEventModel]):
    """Repository for audit events — append-only, no update/delete.

    This class intentionally does NOT have update() or delete() methods.
    Attempting to call these methods will result in an AttributeError,
    enforcing the append-only semantic at the code level.
    At the database level, triggers prevent UPDATE/DELETE.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the audit repository.

        Args:
            session: SQLAlchemy async session.
        """
        super().__init__(session, AuditEventModel)

    async def create(
        self,
        tenant_id: str | UUID,
        occurred_at: datetime | None = None,
        action: str = "",
        actor_type: str = "",
        actor_id: str = "",
        actor_display_name: str | None = None,
        actor_email: str | None = None,
        actor_channel: str | None = None,
        target_system: str | None = None,
        target_ref: str | None = None,
        run_id: str | None = None,
        discrepancy_id: str | None = None,
        detail: str | None = None,
        request_id: str | None = None,
    ) -> AuditEventModel:
        """Create and persist an audit event.

        Args:
            tenant_id: Tenant ID.
            occurred_at: Event timestamp (defaults to now).
            action: Audit action type.
            actor_type: Type of actor ('user' or 'system').
            actor_id: ID of the actor.
            actor_display_name: Display name of the actor.
            actor_email: Email of the actor.
            actor_channel: Where the action originated (e.g., 'slack', 'api').
            target_system: Target system ('servicetitan' or 'quickbooks').
            target_ref: External record identifier.
            run_id: Associated run ID if applicable.
            discrepancy_id: Associated discrepancy ID if applicable.
            detail: Human-readable summary.
            request_id: Request ID for tracing.

        Returns:
            The created AuditEventModel.
        """
        logger = get_logger()
        logger.info(
            "audit_create",
            action=action,
            target_system=target_system,
            target_ref=target_ref,
        )

        if occurred_at is None:
            occurred_at = datetime.now(UTC)

        event = AuditEventModel(
            tenant_id=str(tenant_id),
            occurred_at=occurred_at,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_display_name=actor_display_name,
            actor_email=actor_email,
            actor_channel=actor_channel,
            target_system=target_system,
            target_ref=target_ref,
            run_id=run_id,
            discrepancy_id=discrepancy_id,
            detail=detail,
            request_id=request_id,
        )

        self.session.add(event)
        await self.session.flush()
        return event

    async def list(
        self,
        tenant_id: str | UUID,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
        action: str | None = None,
        target_system: str | None = None,
        target_ref: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditEventModel], int]:
        """List audit events for a tenant.

        Args:
            tenant_id: Tenant ID to filter by.
            occurred_after: Filter events after this time.
            occurred_before: Filter events before this time.
            action: Filter by action type.
            target_system: Filter by target system.
            target_ref: Filter by target reference.
            limit: Maximum number of events to return.
            offset: Number of events to skip.

        Returns:
            A tuple of (list of events, total count).
        """
        query = self._base_query(tenant_id)

        if occurred_after:
            query = query.where(AuditEventModel.occurred_at >= occurred_after)

        if occurred_before:
            query = query.where(AuditEventModel.occurred_at <= occurred_before)

        if action:
            query = query.where(AuditEventModel.action == action)

        if target_system:
            query = query.where(AuditEventModel.target_system == target_system)

        if target_ref:
            query = query.where(AuditEventModel.target_ref == target_ref)

        # Get total count using a count query
        count_query = select(func.count(AuditEventModel.id)).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total_count = count_result.scalar() or 0

        # Get paginated results, ordered by occurred_at DESC (newest first)
        query = query.order_by(AuditEventModel.occurred_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        events = result.scalars().all()

        return list(events), total_count
