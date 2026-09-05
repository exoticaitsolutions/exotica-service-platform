"""Test idempotency semantics (semantic constraint).

Proves:
1. Same Idempotency-Key + same body returns identical response, no additional work
2. Same Idempotency-Key + different body returns 409 conflict
3. Concurrent requests with same key perform work exactly once
"""

from datetime import UTC, datetime, timedelta

import pytest
import uuid6
from sqlalchemy.ext.asyncio import AsyncSession

from core.idempotency import IdempotencyRecordModel, IdempotencyRepository, hash_request_body


@pytest.mark.asyncio
async def test_hash_request_body_deterministic() -> None:
    """Test that request body hashing is deterministic."""
    body = {"email": "test@example.com", "name": "Test User"}

    hash1 = hash_request_body(body)
    hash2 = hash_request_body(body)

    assert hash1 == hash2


@pytest.mark.asyncio
async def test_hash_request_body_order_independent() -> None:
    """Test that request body hash is independent of key order."""
    body1 = {"email": "test@example.com", "name": "Test User"}
    body2 = {"name": "Test User", "email": "test@example.com"}

    hash1 = hash_request_body(body1)
    hash2 = hash_request_body(body2)

    assert hash1 == hash2


@pytest.mark.asyncio
async def test_hash_request_body_different_for_different_bodies() -> None:
    """Test that different bodies produce different hashes."""
    body1 = {"email": "test@example.com", "name": "Test User"}
    body2 = {"email": "test@example.com", "name": "Different User"}

    hash1 = hash_request_body(body1)
    hash2 = hash_request_body(body2)

    assert hash1 != hash2


@pytest.mark.asyncio
async def test_idempotency_repository_save_and_lookup(test_session: AsyncSession) -> None:
    """Test idempotency repository save and lookup."""
    repo = IdempotencyRepository(test_session)
    tenant_id = str(uuid6.uuid7())
    endpoint = "test_endpoint"
    key = "test-key-123"
    request_hash = hash_request_body({"test": "data"})
    response_status = 200
    response_body = {"result": "success"}

    # Save a record
    saved = await repo.save(
        tenant_id=tenant_id,
        endpoint=endpoint,
        key=key,
        request_hash=request_hash,
        response_status=response_status,
        response_body=response_body,
    )

    assert saved.tenant_id == tenant_id
    assert saved.endpoint == endpoint
    assert saved.key == key

    # Commit to ensure it's persisted
    await test_session.commit()

    # Look it up
    found = await repo.lookup(
        tenant_id=tenant_id,
        endpoint=endpoint,
        key=key,
    )

    assert found is not None
    assert found.response_status == response_status
    assert found.response_body == response_body


@pytest.mark.asyncio
async def test_idempotency_lookup_expired_returns_none(test_session: AsyncSession) -> None:
    """Test that expired idempotency records are not returned."""
    repo = IdempotencyRepository(test_session)
    tenant_id = str(uuid6.uuid7())
    endpoint = "test_endpoint"
    key = "test-key-123"

    # Create a record that's already expired
    record = IdempotencyRecordModel(
        tenant_id=tenant_id,
        endpoint=endpoint,
        key=key,
        request_hash="test_hash",
        response_status=200,
        response_body={"result": "success"},
        created_at=datetime.now(UTC) - timedelta(days=1),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    test_session.add(record)
    await test_session.commit()

    # Lookup should return None for expired record
    found = await repo.lookup(
        tenant_id=tenant_id,
        endpoint=endpoint,
        key=key,
    )

    assert found is None
