"""Test the error hierarchy and contract compliance."""

from core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PlatformError,
    RateLimitedError,
    UnauthorizedError,
    UnprocessableError,
    ValidationError,
)


def test_platform_error_base() -> None:
    """Test basic PlatformError creation."""
    error = PlatformError(
        error_code="test_error",
        message="Test message",
        http_status=400,
    )
    assert error.error_code == "test_error"
    assert error.message == "Test message"
    assert error.http_status == 400
    assert error.details == []


def test_platform_error_with_details() -> None:
    """Test PlatformError with details."""
    details = [{"field": "email", "issue": "Must be valid"}]
    error = PlatformError(
        error_code="validation_error",
        message="Validation failed",
        http_status=400,
        details=details,
    )
    assert error.details == details


def test_platform_error_with_extra_fields() -> None:
    """Test PlatformError with extra fields (for contract special cases)."""
    extra = {"active_run_id": "123"}
    error = ConflictError(
        error_code="run_in_progress",
        message="A run is already in progress",
        extra_fields=extra,
    )
    assert error.extra_fields == extra


def test_validation_error() -> None:
    """Test ValidationError creates correct HTTP status."""
    error = ValidationError("Email is invalid")
    assert error.error_code == "validation_failed"
    assert error.http_status == 400


def test_unauthorized_error() -> None:
    """Test UnauthorizedError creates correct HTTP status."""
    error = UnauthorizedError()
    assert error.error_code == "unauthorized"
    assert error.http_status == 401


def test_forbidden_error() -> None:
    """Test ForbiddenError creates correct HTTP status."""
    error = ForbiddenError("You don't have access")
    assert error.error_code == "forbidden"
    assert error.http_status == 403


def test_not_found_error() -> None:
    """Test NotFoundError creates correct HTTP status."""
    error = NotFoundError("Resource not found")
    assert error.error_code == "not_found"
    assert error.http_status == 404


def test_conflict_error() -> None:
    """Test ConflictError with explicit error code."""
    error = ConflictError(
        error_code="run_in_progress",
        message="Another run is already active",
    )
    assert error.error_code == "run_in_progress"
    assert error.http_status == 409


def test_unprocessable_error() -> None:
    """Test UnprocessableError creates correct HTTP status."""
    error = UnprocessableError("Tenant missing OAuth tokens")
    assert error.error_code == "unprocessable_entity"
    assert error.http_status == 422


def test_rate_limited_error() -> None:
    """Test RateLimitedError with retry_after."""
    error = RateLimitedError(retry_after_seconds=30)
    assert error.error_code == "rate_limited"
    assert error.http_status == 429
    assert error.retry_after_seconds == 30
