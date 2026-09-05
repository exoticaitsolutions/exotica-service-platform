"""Health check endpoints for liveness and readiness.

/health — process is running (no I/O, <1s)
/ready — all dependencies are healthy (includes DB and Redis checks)
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from core.database import get_db_session
from core.logging import get_logger

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — process is running.

    Returns:
        {"status": "healthy"}
    """
    return {"status": "healthy"}


@router.get("/ready")
async def readiness(
    db_session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Readiness probe — checks database connectivity.

    Redis check is deferred since it's only used in later steps (Celery).

    Args:
        db_session: Database session from dependency.

    Returns:
        {"status": "healthy" | "degraded", "checks": {"db": "ok" | "error"}}
    """
    logger = get_logger()
    checks: dict[str, str] = {}
    status = "healthy"

    # Check database
    try:
        await db_session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        logger.error("readiness_db_check_failed", error=str(e))
        checks["db"] = "error"
        status = "degraded"

    return {
        "status": status,
        "checks": checks,
    }
