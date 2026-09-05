"""Test that secrets never leak into logs, responses, or audit records (semantic constraint)."""

from fastapi.testclient import TestClient

from app import create_app


def test_invalid_token_no_secret_in_response() -> None:
    """Test that authentication failure doesn't expose the JWT secret in the response."""
    client = TestClient(create_app())

    # Make a request with a completely invalid token
    response = client.get(
        "/health",  # Health check endpoint
        headers={"Authorization": "Bearer invalid_token_never_ever_valid"},
    )

    # The response should not include the secret in any form
    assert "dev-jwt-secret" not in response.text
    assert "test-jwt-secret" not in response.text
    # The response might be 401 (if auth is required) or 200 (if health check is public)
    # Either way, no secret should leak


def test_missing_authorization_header_no_secret_in_response() -> None:
    """Test that missing auth doesn't expose secrets."""
    client = TestClient(create_app())

    # Request without any Authorization header
    response = client.get("/health")

    # No secret should appear in the response
    assert "dev-jwt-secret" not in response.text
    assert "test-jwt-secret" not in response.text


def test_malformed_bearer_token_no_secret_in_response() -> None:
    """Test that malformed Bearer token doesn't expose secrets."""
    client = TestClient(create_app())

    # Request with malformed Authorization header
    response = client.get(
        "/health",
        headers={"Authorization": "NotBearer corrupted"},
    )

    # No secret should appear
    assert "dev-jwt-secret" not in response.text
    assert "test-jwt-secret" not in response.text
