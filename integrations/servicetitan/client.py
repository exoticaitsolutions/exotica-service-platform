"""ServiceTitan API client with retry logic and error handling."""

import asyncio
from datetime import date
from typing import Any

import httpx
import structlog

from core.config import get_settings

logger = structlog.get_logger()


class ServiceTitanError(Exception):
    """Base error for ServiceTitan API failures."""

    pass


class ServiceTitanAuthError(ServiceTitanError):
    """ServiceTitan API authentication failed."""

    pass


class ServiceTitanRateLimitError(ServiceTitanError):
    """ServiceTitan API rate limit exceeded."""

    pass


class ServiceTitanClient:
    """ServiceTitan API client with retry logic for transient failures."""

    def __init__(self, settings: Any = None) -> None:
        """Initialize ServiceTitan client."""
        self.settings = settings or get_settings()
        self.api_key = self.settings.servicetitan_api_key
        self.endpoint = self.settings.servicetitan_api_endpoint
        self.timeout = self.settings.servicetitan_request_timeout
        self.max_retries = self.settings.http_max_retries
        self.backoff_factor = self.settings.http_retry_backoff_factor

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/invoices")
            **kwargs: Additional httpx request kwargs

        Returns:
            Parsed JSON response

        Raises:
            ServiceTitanAuthError: 401/403 responses
            ServiceTitanRateLimitError: 429 responses
            ServiceTitanError: Other non-retryable errors
        """
        url = f"{self.endpoint}{path}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.api_key}"
        headers["Content-Type"] = "application/json"

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        **kwargs,
                    )

                    if response.status_code == 401 or response.status_code == 403:
                        raise ServiceTitanAuthError(
                            f"ServiceTitan auth failed: {response.status_code}"
                        )

                    if response.status_code == 429:
                        if attempt < self.max_retries:
                            wait_time = (2**attempt) * self.backoff_factor
                            await asyncio.sleep(wait_time)
                            continue
                        raise ServiceTitanRateLimitError("ServiceTitan rate limit exceeded")

                    if response.status_code >= 500:
                        if attempt < self.max_retries:
                            wait_time = (2**attempt) * self.backoff_factor
                            await asyncio.sleep(wait_time)
                            continue
                        raise ServiceTitanError(
                            f"ServiceTitan server error: {response.status_code}"
                        )

                    response.raise_for_status()
                    return response.json()  # type: ignore[no-any-return]

            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    wait_time = (2**attempt) * self.backoff_factor
                    await asyncio.sleep(wait_time)
                    continue
                raise ServiceTitanError("ServiceTitan request timeout")
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    wait_time = (2**attempt) * self.backoff_factor
                    await asyncio.sleep(wait_time)
                    continue
                raise ServiceTitanError(f"ServiceTitan request failed: {e}")

        raise ServiceTitanError("Unexpected retry logic failure")

    async def fetch_invoices(
        self,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Fetch invoices from ServiceTitan within date range.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            List of invoice objects

        Raises:
            ServiceTitanAuthError: Authentication failed
            ServiceTitanRateLimitError: Rate limited
            ServiceTitanError: Other API errors
        """
        params = {
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
            "limit": 1000,
        }
        try:
            response = await self._request_with_retry(
                "GET",
                "/invoices",
                params=params,
            )
            return response.get("data", [])  # type: ignore[no-any-return]
        except (ServiceTitanAuthError, ServiceTitanRateLimitError):
            raise
        except ServiceTitanError as e:
            logger.error("servicetitan_fetch_invoices_failed", error=str(e))
            raise

    async def fetch_payments(
        self,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Fetch payments from ServiceTitan within date range.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            List of payment objects

        Raises:
            ServiceTitanAuthError: Authentication failed
            ServiceTitanRateLimitError: Rate limited
            ServiceTitanError: Other API errors
        """
        params = {
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
            "limit": 1000,
        }
        try:
            response = await self._request_with_retry(
                "GET",
                "/payments",
                params=params,
            )
            return response.get("data", [])  # type: ignore[no-any-return]
        except (ServiceTitanAuthError, ServiceTitanRateLimitError):
            raise
        except ServiceTitanError as e:
            logger.error("servicetitan_fetch_payments_failed", error=str(e))
            raise
