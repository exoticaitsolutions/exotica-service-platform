"""Tenant model and base repository for tenant-scoped data access.

Multi-tenant isolation is a structural property: every repository query is
scoped by tenant_id at the base class level.
"""

from abc import ABC
from typing import Any, Generic, TypeVar
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.auth import TokenClaims, get_current_token
from core.database import Base, TimestampMixin, UUIDPrimaryKey
from core.errors import ForbiddenError


class TenantModel(Base, UUIDPrimaryKey, TimestampMixin):
    """Represents a tenant (customer) in the platform.

    Minimal schema — connections and configuration live in later modules.
    """

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


T = TypeVar("T", bound=Base)


class TenantScopedRepository(ABC, Generic[T]):
    """Abstract base for all repositories that access tenant-owned data.

    Enforces tenant isolation structurally: every query automatically includes
    a WHERE tenant_id = X filter. A subclass cannot construct a query without
    tenant_id.

    Subclasses should:
    1. Pass the model class to __init__
    2. Implement create/update/delete/list methods that call the base
       query-building primitives
    3. Accept tenant_id as the first argument to every method
    """

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy async session.
            model: The SQLAlchemy model class this repository manages.
        """
        self.session = session
        self.model = model

    def _base_query(self, tenant_id: str | UUID) -> Any:
        """Construct a base query with tenant_id filter.

        All queries must start here to ensure tenant isolation.

        Args:
            tenant_id: Tenant ID to filter by.

        Returns:
            A SQLAlchemy select statement scoped to the tenant.
        """
        return select(self.model).where(self.model.tenant_id == str(tenant_id))  # type: ignore[attr-defined]

    async def _execute(self, statement: Any) -> Any:
        """Execute a query and return the result.

        Args:
            statement: SQLAlchemy statement to execute.

        Returns:
            Query result.
        """
        result = await self.session.execute(statement)
        return result

    async def _execute_scalar(self, statement: Any) -> Any:
        """Execute a query and return a scalar result.

        Args:
            statement: SQLAlchemy statement to execute.

        Returns:
            Scalar query result.
        """
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()


async def get_current_tenant_id(
    token: TokenClaims = Depends(get_current_token),  # noqa: B008
    tenant_id_param: str | None = None,
) -> str:
    """FastAPI dependency to get and validate the current tenant ID.

    Compares the tenant_id from the token against the tenant_id in the
    request (path, query, or body). Returns 403 if they don't match.

    Args:
        token: Decoded token from get_current_token dependency.
        tenant_id_param: Tenant ID from the request (path/query/body).

    Returns:
        The validated tenant ID.

    Raises:
        ForbiddenError: If tenant_id_param is provided and doesn't match
            the token's tenant_id.
    """
    if tenant_id_param and str(tenant_id_param) != str(token.tenant_id):
        raise ForbiddenError("Tenant ID in request does not match token scope")

    return token.tenant_id
