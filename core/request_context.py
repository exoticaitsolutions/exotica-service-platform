"""ASGI middleware for request context management.

Generates/propagates request_id, binds it to structlog context,
echoes it on the response, and clears context after.
"""

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.logging import bind_request_context, clear_request_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that manages request context (request_id, tenant_id).

    - Generates/propagates request_id (from X-Request-Id or new UUID)
    - Binds request context to structlog for all log entries
    - Echoes request_id on the response
    - Clears context after the request
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        """Process the request with context management.

        Args:
            request: The incoming request.
            call_next: Callable to pass the request to the next middleware/handler.

        Returns:
            The response with X-Request-Id header.
        """
        # Generate or extract request_id
        request_id = request.headers.get("X-Request-Id", str(uuid4()))

        # Bind context
        bind_request_context(request_id)

        try:
            # Call the next handler
            response = await call_next(request)

            # Echo request_id in response
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            # Always clear context
            clear_request_context()
