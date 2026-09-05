"""JWT token verification and authentication dependencies."""

from fastapi import Header
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from core.config import get_settings
from core.errors import UnauthorizedError
from core.logging import get_logger
from core.secrets import get_secrets_provider


class TokenClaims(BaseModel):
    """Decoded JWT token claims."""

    sub: str = Field(..., description="Subject (user ID)")
    tenant_id: str = Field(..., description="Tenant ID the token is scoped to")
    actor_type: str = Field(..., description="Actor type: 'user' or 'system'")
    scopes: list[str] = Field(default_factory=list, description="Granted scopes")
    exp: int = Field(..., description="Token expiration timestamp")


async def decode_and_verify_token(token: str) -> TokenClaims:
    """Decode and verify a JWT token using the configured secret.

    Args:
        token: The JWT token string (without 'Bearer ' prefix).

    Returns:
        Decoded TokenClaims.

    Raises:
        UnauthorizedError: If the token is invalid, expired, or verification fails.
    """
    settings = get_settings()
    secrets_provider = get_secrets_provider()

    try:
        # Get the JWT secret from the secrets provider
        secret = await secrets_provider.get_secret(settings.jwt_secret_arn)
    except Exception:
        # Do not log the secret or the error details — could leak the ARN or secret
        logger = get_logger()
        logger.error("Failed to retrieve JWT secret")
        raise UnauthorizedError() from None

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        claims = TokenClaims(**payload)
        return claims
    except JWTError:
        # All JWT errors (malformed, expired, bad signature) -> generic 401
        raise UnauthorizedError() from None
    except ValueError:
        # Invalid claims shape
        raise UnauthorizedError() from None


async def get_current_token(
    authorization: str = Header(..., description="Bearer token"),
) -> TokenClaims:
    """FastAPI dependency to verify and extract the current token.

    Args:
        authorization: Authorization header value (e.g., "Bearer eyJ...").

    Returns:
        Decoded TokenClaims.

    Raises:
        UnauthorizedError: If the header is missing, malformed, or token is invalid.
    """
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise UnauthorizedError()
    except ValueError:
        # Header is malformed (missing space or scheme)
        raise UnauthorizedError() from None

    return await decode_and_verify_token(token)
