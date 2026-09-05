"""Test tenant isolation at the repository layer (semantic constraint).

Proves:
1. A token scoped to tenant A cannot read tenant B's data
2. Tenant isolation is enforced at the query level, not by convention
"""

from datetime import UTC, datetime

import pytest
import uuid6
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import AuditEventModel, AuditRepository
from core.tenancy import TenantModel


@pytest.mark.asyncio
async def test_audit_repository_filters_by_tenant(test_session: AsyncSession) -> None:
    """Test that AuditRepository queries are automatically scoped to tenant_id."""
    # Create two tenants
    tenant_a_id = str(uuid6.uuid7())
    tenant_b_id = str(uuid6.uuid7())

    tenant_a = TenantModel(id=tenant_a_id, name="Tenant A")
    tenant_b = TenantModel(id=tenant_b_id, name="Tenant B")
    test_session.add(tenant_a)
    test_session.add(tenant_b)
    await test_session.flush()

    # Create audit events for each tenant
    event_a = AuditEventModel(
        tenant_id=tenant_a_id,
        occurred_at=datetime.now(UTC),
        action="test_action",
        actor_type="system",
        actor_id="test",
        detail="event for tenant A",
    )
    event_b = AuditEventModel(
        tenant_id=tenant_b_id,
        occurred_at=datetime.now(UTC),
        action="test_action",
        actor_type="system",
        actor_id="test",
        detail="event for tenant B",
    )
    test_session.add(event_a)
    test_session.add(event_b)
    await test_session.flush()
    await test_session.commit()

    # Query as tenant A
    repo_a = AuditRepository(test_session)
    events_a, count_a = await repo_a.list(tenant_a_id)

    # Should only see tenant A's events
    assert len(events_a) == 1
    assert events_a[0].tenant_id == tenant_a_id
    assert events_a[0].detail == "event for tenant A"

    # Query as tenant B
    repo_b = AuditRepository(test_session)
    events_b, count_b = await repo_b.list(tenant_b_id)

    # Should only see tenant B's events
    assert len(events_b) == 1
    assert events_b[0].tenant_id == tenant_b_id
    assert events_b[0].detail == "event for tenant B"


@pytest.mark.asyncio
async def test_audit_repository_cannot_cross_tenant_boundary(
    test_session: AsyncSession,
) -> None:
    """Test that even if tenant_id is wrong, the repository still filters correctly."""
    # Create two tenants
    tenant_a_id = str(uuid6.uuid7())
    tenant_b_id = str(uuid6.uuid7())

    tenant_a = TenantModel(id=tenant_a_id, name="Tenant A")
    tenant_b = TenantModel(id=tenant_b_id, name="Tenant B")
    test_session.add(tenant_a)
    test_session.add(tenant_b)
    await test_session.flush()

    # Create event for tenant B
    event_b = AuditEventModel(
        tenant_id=tenant_b_id,
        occurred_at=datetime.now(UTC),
        action="test_action",
        actor_type="system",
        actor_id="test",
    )
    test_session.add(event_b)
    await test_session.flush()
    await test_session.commit()

    # Try to read tenant B's events using tenant A's repository scope
    repo = AuditRepository(test_session)
    events_a, _ = await repo.list(tenant_a_id)

    # Should get no results — the base query filters by tenant_id
    assert len(events_a) == 0
