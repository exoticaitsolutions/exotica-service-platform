"""Idempotency support for mutating endpoints.

Endpoints decorated with @idempotent_endpoint guarantee that replayed
requests with the same Idempotency-Key return the original response
without re-executing the operation.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, UUIDPrimaryKey


class IdempotencyRecordModel(Base, UUIDPrimaryKey):
    """Stores idempotency key records and cached responses.

    Uniqueness constraint on (tenant_id, endpoint, key) ensures that
    concurrent requests with the same key don't double-execute.
    """

    __tablename__ = "idempotency_records"

    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(nullable=False)
    key: Mapped[str] = mapped_column(nullable=False)
    request_hash: Mapped[str] = mapped_column(nullable=False)
    response_status: Mapped[int] = mapped_column(nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)


def hash_request_body(body: dict[str, Any] | None) -> str:
    """Hash a request body for idempotency comparison.

    Canonicalizes the JSON and computes a SHA-256 hash.

    Args:
        body: Request body to hash (or None for GET requests).

    Returns:
        Hex-encoded SHA-256 hash.
    """
    if body is None:
        body = {}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class IdempotencyRepository:
    """Repository for managing idempotency records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def lookup(
        self,
        tenant_id: str | UUID,
        endpoint: str,
        key: str,
    ) -> IdempotencyRecordModel | None:
        """Look up an unexpired idempotency record.

        Args:
            tenant_id: Tenant ID.
            endpoint: Endpoint route name.
            key: Idempotency key.

        Returns:
            The idempotency record if found and not expired, else None.
        """
        query = select(IdempotencyRecordModel).where(
            and_(
                IdempotencyRecordModel.tenant_id == str(tenant_id),
                IdempotencyRecordModel.endpoint == endpoint,
                IdempotencyRecordModel.key == key,
                IdempotencyRecordModel.expires_at > datetime.now(UTC),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def save(
        self,
        tenant_id: str | UUID,
        endpoint: str,
        key: str,
        request_hash: str,
        response_status: int,
        response_body: dict[str, Any],
        ttl_hours: int = 24,
    ) -> IdempotencyRecordModel:
        """Save an idempotency record.

        Args:
            tenant_id: Tenant ID.
            endpoint: Endpoint route name.
            key: Idempotency key.
            request_hash: SHA-256 hash of the request body.
            response_status: HTTP status code of the response.
            response_body: Response body (as dict).
            ttl_hours: Time to live for this record (default 24 hours).

        Returns:
            The created IdempotencyRecordModel.
        """
        now = datetime.now(UTC)
        record = IdempotencyRecordModel(
            tenant_id=str(tenant_id),
            endpoint=endpoint,
            key=key,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
        self.session.add(record)
        await self.session.flush()
        return record
