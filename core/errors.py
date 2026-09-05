"""Custom exception hierarchy for the platform.

All exceptions must be PlatformError subclasses. Never raise bare Exception.
Map to HTTP status codes and contract Error schema.
"""

from typing import Any, TypeAlias

ErrorDetail: TypeAlias = dict[str, Any]


class PlatformError(Exception):
    """Base exception for all platform errors.

    Attributes:
        error_code: Machine-readable stable error code (e.g., 'validation_failed').
        message: Human-readable explanation.
        http_status: HTTP status code to return.
        details: Optional error details (e.g., field validation errors).
        extra_fields: Optional extra fields to include in the error response
            (used for contract-specified extra fields like active_run_id on 409).
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        http_status: int = 500,
        details: list[ErrorDetail] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a PlatformError.

        Args:
            error_code: Machine-readable error code.
            message: Human-readable message.
            http_status: HTTP status code. Defaults to 500.
            details: Optional list of error detail objects.
            extra_fields: Optional extra fields for the response.
        """
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.http_status = http_status
        self.details = details or []
        self.extra_fields = extra_fields or {}


class ValidationError(PlatformError):
    """Request validation failed (400)."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: list[ErrorDetail] | None = None,
    ) -> None:
        """Initialize ValidationError.

        Args:
            message: Human-readable message.
            details: Optional validation error details.
        """
        super().__init__(
            error_code="validation_failed",
            message=message,
            http_status=400,
            details=details,
        )


class UnauthorizedError(PlatformError):
    """Missing or invalid authentication (401)."""

    def __init__(
        self,
        message: str = "Missing or invalid authentication credentials",
    ) -> None:
        """Initialize UnauthorizedError.

        Args:
            message: Human-readable message.
        """
        super().__init__(
            error_code="unauthorized",
            message=message,
            http_status=401,
        )


class ForbiddenError(PlatformError):
    """Authenticated but not authorized for this resource (403)."""

    def __init__(
        self,
        message: str = "Not authorized for this resource",
    ) -> None:
        """Initialize ForbiddenError.

        Args:
            message: Human-readable message.
        """
        super().__init__(
            error_code="forbidden",
            message=message,
            http_status=403,
        )


class NotFoundError(PlatformError):
    """Resource not found (404)."""

    def __init__(
        self,
        message: str = "Resource not found",
    ) -> None:
        """Initialize NotFoundError.

        Args:
            message: Human-readable message.
        """
        super().__init__(
            error_code="not_found",
            message=message,
            http_status=404,
        )


class ConflictError(PlatformError):
    """Conflict: resource state prevents the operation (409)."""

    def __init__(
        self,
        error_code: str,
        message: str = "Conflict",
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ConflictError.

        Args:
            error_code: Specific conflict code (e.g., 'run_in_progress').
            message: Human-readable message.
            extra_fields: Optional extra fields for the response.
        """
        super().__init__(
            error_code=error_code,
            message=message,
            http_status=409,
            extra_fields=extra_fields,
        )


class UnprocessableError(PlatformError):
    """Validation passed but semantics are invalid (422).

    Used when a tenant is missing required config (e.g., no OAuth tokens).
    """

    def __init__(
        self,
        message: str = "Request is unprocessable",
        details: list[ErrorDetail] | None = None,
    ) -> None:
        """Initialize UnprocessableError.

        Args:
            message: Human-readable message.
            details: Optional error details.
        """
        super().__init__(
            error_code="unprocessable_entity",
            message=message,
            http_status=422,
            details=details,
        )


class RateLimitedError(PlatformError):
    """Too many requests (429).

    Attributes:
        retry_after_seconds: Seconds to wait before retrying.
    """

    def __init__(
        self,
        message: str = "Too many requests",
        retry_after_seconds: int = 60,
    ) -> None:
        """Initialize RateLimitedError.

        Args:
            message: Human-readable message.
            retry_after_seconds: Seconds to wait before retrying.
        """
        super().__init__(
            error_code="rate_limited",
            message=message,
            http_status=429,
        )
        self.retry_after_seconds = retry_after_seconds


class ReplayResponse(Exception):
    """Control-flow exception to short-circuit and replay an idempotent response.

    Not a PlatformError — used internally to bypass route handlers on
    idempotency key replay.
    """

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        """Initialize ReplayResponse.

        Args:
            status_code: HTTP status code to return.
            body: Response body to return.
        """
        super().__init__()
        self.status_code = status_code
        self.body = body
