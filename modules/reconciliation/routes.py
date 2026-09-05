"""API endpoints for reconciliation operations."""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import TokenClaims, get_current_token
from core.database import get_db_session
from core.errors import ConflictError, ReplayResponse, UnprocessableError
from core.idempotency import IdempotencyRepository, hash_request_body
from core.logging import bind_request_context
from core.tenancy import get_current_tenant_id
from modules.reconciliation.models import DiscrepancyModel, ReconciliationRunModel
from modules.reconciliation.repositories import (
    DiscrepancyRepository,
    ReconciliationRunRepository,
)
from modules.reconciliation.service import ReconciliationService

router = APIRouter(prefix="/accounting", tags=["Reconciliation"])


# ─────────────────────────────────────────────────────────────────────────
# Request/Response schemas
# ─────────────────────────────────────────────────────────────────────────


class ReconciliationRunRequest(BaseModel):
    """Request to start a reconciliation run."""

    tenant_id: str = Field(..., description="Tenant UUID")
    date_from: date | None = Field(
        None,
        description="Start date (defaults to 60 days before date_to)",
    )
    date_to: date | None = Field(None, description="End date (defaults to today)")
    trigger_source: str = Field(
        default="api",
        description="manual, scheduled, or api",
    )


class ReconciliationRunResponse(BaseModel):
    """Response after starting a reconciliation run."""

    run_id: str = Field(..., description="Reconciliation run UUID")
    tenant_id: str
    status: str = Field(description="in_progress, succeeded, failed, partial")
    trigger_source: str
    date_from: str
    date_to: str
    started_at: str  # ISO8601
    completed_at: str | None
    servicetitan_invoice_count: int | None
    quickbooks_invoice_count: int | None
    matched_count: int | None
    discrepancy_count: int | None
    health_score: float | None
    source_errors: list[dict[str, Any]]


class DiscrepancyResponse(BaseModel):
    """Response representing a detected discrepancy."""

    discrepancy_id: str = Field(..., description="Discrepancy UUID")
    run_id: str
    tenant_id: str
    type: str = Field(
        description="missing_in_quickbooks, missing_in_servicetitan, amount_mismatch, "
        "underpayment, overpayment, payment_count_mismatch, timing_mismatch, duplicate_invoice"
    )
    severity: str = Field(description="info, warning, error")
    status: str = Field(description="open, awaiting_approval, resolved, dismissed")
    servicetitan_invoice_id: str | None
    quickbooks_invoice_id: str | None
    customer_name: str | None
    servicetitan_amount: str | None = Field(None, description="Decimal string")
    quickbooks_amount: str | None = Field(None, description="Decimal string")
    difference: str = Field(..., description="Absolute difference as decimal string")
    currency: str
    detected_at: str  # ISO8601


class DiscrepanciesListResponse(BaseModel):
    """Paginated list of discrepancies."""

    items: list[DiscrepancyResponse]
    page: dict[str, Any] = Field(description="Pagination info")


def _model_to_response(run: ReconciliationRunModel) -> ReconciliationRunResponse:
    """Convert ReconciliationRunModel to response schema."""
    return ReconciliationRunResponse(
        run_id=run.id,
        tenant_id=run.tenant_id,
        status=run.status,
        trigger_source=run.trigger_source,
        date_from=run.date_from,
        date_to=run.date_to,
        started_at=run.started_at.isoformat() + "Z",
        completed_at=run.completed_at.isoformat() + "Z" if run.completed_at else None,
        servicetitan_invoice_count=run.servicetitan_invoice_count,
        quickbooks_invoice_count=run.quickbooks_invoice_count,
        matched_count=run.matched_count,
        discrepancy_count=run.discrepancy_count,
        health_score=float(run.health_score) if run.health_score else None,
        source_errors=run.source_errors,
    )


def _discrepancy_to_response(discrepancy: DiscrepancyModel) -> DiscrepancyResponse:
    """Convert DiscrepancyModel to response schema."""
    return DiscrepancyResponse(
        discrepancy_id=discrepancy.id,
        run_id=discrepancy.run_id,
        tenant_id=discrepancy.tenant_id,
        type=discrepancy.type,
        severity=discrepancy.severity,
        status=discrepancy.status,
        servicetitan_invoice_id=discrepancy.st_invoice_id,
        quickbooks_invoice_id=discrepancy.qb_invoice_id,
        customer_name=discrepancy.customer_name,
        servicetitan_amount=str(discrepancy.st_amount) if discrepancy.st_amount else None,
        quickbooks_amount=str(discrepancy.qb_amount) if discrepancy.qb_amount else None,
        difference=str(discrepancy.difference),
        currency=discrepancy.currency,
        detected_at=discrepancy.detected_at.isoformat() + "Z",
    )


# ─────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────


@router.post(
    "/reconcile",
    response_model=ReconciliationRunResponse,
    status_code=202,
)
async def trigger_reconciliation(
    request: ReconciliationRunRequest,
    token: TokenClaims = Depends(get_current_token),  # noqa: B008
    tenant_id: str = Depends(get_current_tenant_id),  # noqa: B008
    db_session: AsyncSession = Depends(get_db_session),  # noqa: B008
    idempotency_key: str = Header(None),  # noqa: B008
) -> ReconciliationRunResponse:
    """Start a reconciliation run for a tenant.

    Reconciliation runs synchronously for now. This endpoint blocks until
    the run completes (or fails).

    Idempotency: same Idempotency-Key with same request body returns the
    same run_id; same key with different body returns 409.

    Args:
        request: Reconciliation parameters
        token: JWT token claims
        tenant_id: Tenant ID (validated against token)
        db_session: Database session
        idempotency_key: Optional idempotency key

    Returns:
        202 Accepted with run details

    Raises:
        UnprocessableError: Credentials missing or invalid
        ConflictError: Idempotency-key reuse mismatch
    """
    bind_request_context(request.tenant_id, None)

    # Idempotency guard
    if idempotency_key:
        idempotency_repo = IdempotencyRepository(db_session)
        request_hash = hash_request_body(request.model_dump())
        stored = await idempotency_repo.lookup(
            request.tenant_id,
            "POST /accounting/reconcile",
            idempotency_key,
        )

        if stored:
            if stored.request_hash != request_hash:
                raise ConflictError(
                    error_code="idempotency_key_reuse_mismatch",
                    message="Idempotency-Key reused with different request body",
                )
            # Replay: return the stored response
            if stored.response_status == 202:
                # Parse the stored response body
                stored_run = ReconciliationRunResponse(**stored.response_body)
                raise ReplayResponse(
                    status_code=202,
                    body=stored_run.model_dump(),
                )

    # Check for active run
    run_repo = ReconciliationRunRepository(db_session)
    active_run = await run_repo.get_active_run(request.tenant_id)
    if active_run:
        raise ConflictError(
            error_code="run_in_progress",
            message=f"A reconciliation run is already in progress: {active_run.id}",
            extra_fields={"active_run_id": active_run.id},
        )

    # Default dates
    date_to = request.date_to or date.today()
    date_from = request.date_from or date_to - timedelta(days=60)

    # Execute reconciliation (synchronous)
    service = ReconciliationService(db_session)
    try:
        completed_run = await service.reconcile(
            tenant_id=request.tenant_id,
            date_from=date_from,
            date_to=date_to,
            trigger_source=request.trigger_source,
        )
    except UnprocessableError:
        # Credentials missing/invalid
        raise

    response = _model_to_response(completed_run)

    # Save idempotency record (in same transaction)
    if idempotency_key:
        idempotency_repo = IdempotencyRepository(db_session)
        await idempotency_repo.save(
            tenant_id=request.tenant_id,
            endpoint="POST /accounting/reconcile",
            key=idempotency_key,
            request_hash=hash_request_body(request.model_dump()),
            response_status=202,
            response_body=response.model_dump(),
            ttl_hours=24,
        )
        await db_session.commit()

    return response


@router.get("/runs/{run_id}", response_model=ReconciliationRunResponse)
async def get_reconciliation_run(
    run_id: Annotated[str, Path(description="Reconciliation run UUID")],  # noqa: B008
    token: TokenClaims = Depends(get_current_token),  # noqa: B008
    db_session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ReconciliationRunResponse:
    """Get a reconciliation run by ID.

    Args:
        run_id: Run UUID
        token: JWT token claims
        db_session: Database session

    Returns:
        ReconciliationRun details

    Raises:
        404: Run not found
        403: Tenant mismatch (cross-tenant access attempt)
    """
    run_repo = ReconciliationRunRepository(db_session)
    run = await run_repo.get(token.tenant_id, run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return _model_to_response(run)


@router.get(
    "/runs/{run_id}/discrepancies",
    response_model=DiscrepanciesListResponse,
)
async def list_run_discrepancies(
    run_id: Annotated[str, Path(description="Reconciliation run UUID")],  # noqa: B008
    token: TokenClaims = Depends(get_current_token),  # noqa: B008
    db_session: AsyncSession = Depends(get_db_session),  # noqa: B008
    severity: str | None = None,  # noqa: B008
    discrepancy_type: str | None = None,  # noqa: B008
    limit: int = 50,  # noqa: B008
    offset: int = 0,  # noqa: B008
) -> DiscrepanciesListResponse:
    """List discrepancies found by a specific run.

    Args:
        run_id: Run UUID
        token: JWT token claims
        db_session: Database session
        severity: Optional filter (info, warning, error)
        discrepancy_type: Optional filter by discrepancy type
        limit: Max results (default 50, max 200)
        offset: Skip N results

    Returns:
        Paginated list of discrepancies

    Raises:
        404: Run not found
        403: Tenant mismatch
    """
    run_repo = ReconciliationRunRepository(db_session)
    run = await run_repo.get(token.tenant_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    discrepancy_repo = DiscrepancyRepository(db_session)
    discrepancies, total = await discrepancy_repo.list_by_run(
        tenant_id=token.tenant_id,
        run_id=run_id,
        severity=severity,
        discrepancy_type=discrepancy_type,
        limit=min(limit, 200),
        offset=offset,
    )

    return DiscrepanciesListResponse(
        items=[_discrepancy_to_response(d) for d in discrepancies],
        page={
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": offset + limit < total,
        },
    )


@router.get("/discrepancies", response_model=DiscrepanciesListResponse)
async def list_discrepancies(
    token: TokenClaims = Depends(get_current_token),  # noqa: B008
    db_session: AsyncSession = Depends(get_db_session),  # noqa: B008
    status: str | None = None,  # noqa: B008
    severity: str | None = None,  # noqa: B008
    discrepancy_type: str | None = None,  # noqa: B008
    min_amount: str | None = None,  # noqa: B008
    limit: int = 50,  # noqa: B008
    offset: int = 0,  # noqa: B008
) -> DiscrepanciesListResponse:
    """List discrepancies across all runs for tenant.

    Tenant-wide view with optional filtering by status, severity, type, and
    minimum amount.

    Args:
        token: JWT token claims (provides tenant_id)
        db_session: Database session
        status: Optional filter (open, awaiting_approval, resolved, dismissed)
        severity: Optional filter (info, warning, error)
        discrepancy_type: Optional filter by type
        min_amount: Optional minimum difference amount (decimal string)
        limit: Max results (default 50, max 200)
        offset: Skip N results

    Returns:
        Paginated list of discrepancies
    """
    discrepancy_repo = DiscrepancyRepository(db_session)
    discrepancies, total = await discrepancy_repo.list_for_tenant(
        tenant_id=token.tenant_id,
        status=status,
        severity=severity,
        discrepancy_type=discrepancy_type,
        min_amount=min_amount,
        limit=min(limit, 200),
        offset=offset,
    )

    return DiscrepanciesListResponse(
        items=[_discrepancy_to_response(d) for d in discrepancies],
        page={
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": offset + limit < total,
        },
    )


@router.get("/discrepancies/{discrepancy_id}", response_model=DiscrepancyResponse)
async def get_discrepancy(
    discrepancy_id: Annotated[str, Path(description="Discrepancy UUID")],  # noqa: B008
    token: TokenClaims = Depends(get_current_token),  # noqa: B008
    db_session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> DiscrepancyResponse:
    """Get a single discrepancy by ID.

    Args:
        discrepancy_id: Discrepancy UUID
        token: JWT token claims
        db_session: Database session

    Returns:
        Discrepancy details (AI analysis added in Step 5)

    Raises:
        404: Discrepancy not found
        403: Tenant mismatch
    """
    discrepancy_repo = DiscrepancyRepository(db_session)
    discrepancy = await discrepancy_repo.get(token.tenant_id, discrepancy_id)

    if not discrepancy:
        raise HTTPException(status_code=404, detail="Discrepancy not found")

    return _discrepancy_to_response(discrepancy)
