"""Structured logging configuration using structlog.

All logging goes through structlog, even stdlib logging (uvicorn, sqlalchemy).
JSON in staging/production, console in local. Zero print() calls.
Request context (tenant_id, request_id) is bound to each log entry.
"""

import contextvars
import logging
import logging.config
from typing import Any
from uuid import UUID

import structlog

# Context variables for request-scoped data
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
_tenant_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)


def get_request_id() -> str | None:
    """Get current request ID from context."""
    return _request_id_var.get()


def get_tenant_id() -> str | None:
    """Get current tenant ID from context."""
    return _tenant_id_var.get()


def bind_request_context(request_id: str | UUID, tenant_id: str | UUID | None = None) -> None:
    """Bind request context to structlog and all subsequent logs.

    Args:
        request_id: Request ID (UUID or string).
        tenant_id: Tenant ID (UUID or string, optional).
    """
    _request_id_var.set(str(request_id))
    if tenant_id:
        _tenant_id_var.set(str(tenant_id))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=str(request_id))
    if tenant_id:
        structlog.contextvars.bind_contextvars(tenant_id=str(tenant_id))


def clear_request_context() -> None:
    """Clear request context from structlog."""
    _request_id_var.set(None)
    _tenant_id_var.set(None)
    structlog.contextvars.clear_contextvars()


def _add_context_vars(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Add request context to every log entry."""
    event_dict["request_id"] = get_request_id()
    event_dict["tenant_id"] = get_tenant_id()
    return event_dict


def configure_logging(environment: str, log_level: str) -> None:
    """Configure structlog and stdlib logging.

    Args:
        environment: 'local', 'staging', or 'production'.
        log_level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR').
    """
    # Structlog processors
    if environment == "local":
        processors = [
            structlog.contextvars.merge_contextvars,
            _add_context_vars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    else:
        processors = [
            structlog.contextvars.merge_contextvars,
            _add_context_vars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    # Configure stdlib logging to use structlog
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": (
                        structlog.dev.ConsoleRenderer()
                        if environment == "local"
                        else structlog.processors.JSONRenderer()
                    ),
                },
            },
            "handlers": {
                "default": {
                    "level": log_level.upper(),
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "loggers": {
                "": {
                    "handlers": ["default"],
                    "level": log_level.upper(),
                    "propagate": True,
                },
            },
        }
    )


def get_logger() -> structlog.stdlib.BoundLogger:
    """Get a bound logger instance.

    Returns:
        A structlog logger with context variables already bound.
    """
    return structlog.get_logger()  # type: ignore[no-any-return]
