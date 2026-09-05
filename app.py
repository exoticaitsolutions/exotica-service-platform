"""FastAPI application factory with middleware, exception handlers, and route registration."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.errors import PlatformError, ReplayResponse
from core.health import router as health_router
from core.logging import configure_logging, get_logger
from core.request_context import RequestContextMiddleware
from modules.reconciliation.routes import router as reconciliation_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app instance.
    """
    settings = get_settings()

    # Configure logging
    configure_logging(settings.environment, settings.log_level)
    logger = get_logger()
    logger.info("app_startup", environment=settings.environment)

    # Create app
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.environment == "local" else None,
        redoc_url="/redoc" if settings.environment == "local" else None,
        openapi_url="/openapi.json" if settings.environment == "local" else None,
    )

    # Middleware
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(PlatformError)
    async def platform_error_handler(request: Request, exc: PlatformError) -> JSONResponse:
        """Handle PlatformError exceptions and return contract-compliant error responses."""
        from core.logging import get_request_id

        request_id = get_request_id()
        logger = get_logger()
        logger.error(
            "platform_error",
            error_code=exc.error_code,
            http_status=exc.http_status,
        )

        error_response: dict[str, Any] = {
            "error": exc.error_code,
            "message": exc.message,
            "request_id": request_id,
        }

        if exc.details:
            error_response["details"] = exc.details

        # Add any extra fields (e.g., active_run_id on 409)
        error_response.update(exc.extra_fields)

        return JSONResponse(status_code=exc.http_status, content=error_response)

    @app.exception_handler(ReplayResponse)
    async def replay_response_handler(request: Request, exc: ReplayResponse) -> JSONResponse:
        """Handle ReplayResponse for idempotent endpoint replays."""
        return JSONResponse(status_code=exc.status_code, content=exc.body)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unhandled exceptions — never expose internal details."""
        from core.logging import get_request_id

        request_id = get_request_id()
        logger = get_logger()
        logger.exception("unhandled_exception", exc_info=exc)

        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An internal server error occurred",
                "request_id": request_id,
            },
        )

    # Register routers
    app.include_router(health_router)
    app.include_router(reconciliation_router)

    logger.info("app_initialized")
    return app


app = create_app()
