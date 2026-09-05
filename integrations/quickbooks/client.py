"""QuickBooks API client with OAuth2 and retry logic."""

import asyncio
import base64
from datetime import date
from typing import Any

import httpx
import structlog

from core.config import get_settings

logger = structlog.get_logger()

# QB API minor version for feature compatibility
QB_MINOR_VERSION = "65"

# QB API endpoints by environment
QB_API_HOSTS = {
    "sandbox": "https://sandbox-quickbooks.api.intuit.com",
    "production": "https://quickbooks.api.intuit.com",
}


class QuickBooksError(Exception):
    """Base error for QuickBooks API failures."""

    pass


class QuickBooksAuthError(QuickBooksError):
    """QuickBooks API authentication failed."""

    pass


class QuickBooksRateLimitError(QuickBooksError):
    """QuickBooks API rate limit exceeded."""

    pass


class QuickBooksClient:
    """QuickBooks API client with OAuth2 token management and retry logic."""

    def __init__(self, settings: Any = None) -> None:
        """Initialize QuickBooks client."""
        self.settings = settings or get_settings()
        self.realm_id = self.settings.quickbooks_realm_id
        self.client_id = self.settings.quickbooks_client_id
        self.client_secret = self.settings.quickbooks_client_secret
        self.refresh_token = self.settings.quickbooks_refresh_token
        self.environment = self.settings.quickbooks_environment
        self.endpoint = QB_API_HOSTS.get(self.environment, QB_API_HOSTS["sandbox"])
        self.timeout = self.settings.quickbooks_request_timeout
        self.max_retries = self.settings.http_max_retries
        self.backoff_factor = self.settings.http_retry_backoff_factor
        self._access_token: str | None = None

    @staticmethod
    def _escape_qbo_query_literal(value: str) -> str:
        """Escape single quotes in QB OBO query string literals.

        QB OBO query language uses single quotes; to include a literal quote,
        double it: O'Reilly -> O''Reilly.

        Args:
            value: String to escape

        Returns:
            Escaped string safe for QB OBO queries
        """
        return value.replace("'", "''")

    async def _get_access_token(self) -> str:
        """Get or refresh OAuth2 access token.

        Returns:
            Valid access token

        Raises:
            QuickBooksAuthError: Token refresh failed
        """
        if self._access_token:
            return self._access_token

        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    "https://oauth.platform.intuit.com/oauth2/tokens",
                    headers={"Authorization": f"Basic {auth_header}"},
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.refresh_token,
                    },
                )
                response.raise_for_status()
                data = response.json()
                self._access_token = data.get("access_token")
                if not self._access_token:
                    raise QuickBooksAuthError("No access token in OAuth response")
                return self._access_token
            except httpx.HTTPError as e:
                raise QuickBooksAuthError(f"OAuth token refresh failed: {e}")

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request with token refresh and exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/query")
            **kwargs: Additional httpx request kwargs

        Returns:
            Parsed JSON response

        Raises:
            QuickBooksAuthError: Authentication failed
            QuickBooksRateLimitError: Rate limited
            QuickBooksError: Other API errors
        """
        url = f"{self.endpoint}/v2/company/{self.realm_id}{path}"

        for attempt in range(self.max_retries + 1):
            try:
                token = await self._get_access_token()
                headers = kwargs.pop("headers", {})
                headers["Authorization"] = f"Bearer {token}"
                headers["Content-Type"] = "application/json"

                # Ensure minor version is included in query params
                params = kwargs.pop("params", {})
                params["minorversion"] = QB_MINOR_VERSION

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        **kwargs,
                    )

                    if response.status_code == 401:
                        self._access_token = None
                        if attempt < self.max_retries:
                            continue
                        raise QuickBooksAuthError("QuickBooks auth failed: 401")

                    if response.status_code == 403:
                        raise QuickBooksAuthError("QuickBooks forbidden: 403")

                    if response.status_code == 429:
                        if attempt < self.max_retries:
                            wait_time = (2**attempt) * self.backoff_factor
                            await asyncio.sleep(wait_time)
                            continue
                        raise QuickBooksRateLimitError("QuickBooks rate limit exceeded")

                    if response.status_code >= 500:
                        if attempt < self.max_retries:
                            wait_time = (2**attempt) * self.backoff_factor
                            await asyncio.sleep(wait_time)
                            continue
                        raise QuickBooksError(f"QuickBooks server error: {response.status_code}")

                    response.raise_for_status()
                    return response.json()  # type: ignore[no-any-return]

            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    wait_time = (2**attempt) * self.backoff_factor
                    await asyncio.sleep(wait_time)
                    continue
                raise QuickBooksError("QuickBooks request timeout")
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    wait_time = (2**attempt) * self.backoff_factor
                    await asyncio.sleep(wait_time)
                    continue
                raise QuickBooksError(f"QuickBooks request failed: {e}")

        raise QuickBooksError("Unexpected retry logic failure")

    async def fetch_journal_entries(
        self,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Fetch journal entries from QuickBooks within date range.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            List of journal entry objects

        Raises:
            QuickBooksAuthError: Authentication failed
            QuickBooksRateLimitError: Rate limited
            QuickBooksError: Other API errors
        """
        query = (
            f"SELECT * FROM JournalEntry WHERE "
            f"TxnDate >= '{date_from}' AND TxnDate <= '{date_to}'"
        )
        try:
            response = await self._request_with_retry(
                "POST",
                "/query",
                params={"query": query},
            )
            return response.get("QueryResponse", {}).get("JournalEntry", [])  # type: ignore[no-any-return]
        except (QuickBooksAuthError, QuickBooksRateLimitError):
            raise
        except QuickBooksError as e:
            logger.error("quickbooks_fetch_journal_entries_failed", error=str(e))
            raise

    async def fetch_customers(self) -> list[dict[str, Any]]:
        """Fetch all customers from QuickBooks.

        Returns:
            List of customer objects

        Raises:
            QuickBooksAuthError: Authentication failed
            QuickBooksRateLimitError: Rate limited
            QuickBooksError: Other API errors
        """
        query = "SELECT * FROM Customer"
        try:
            response = await self._request_with_retry(
                "POST",
                "/query",
                params={"query": query},
            )
            return response.get("QueryResponse", {}).get("Customer", [])  # type: ignore[no-any-return]
        except (QuickBooksAuthError, QuickBooksRateLimitError):
            raise
        except QuickBooksError as e:
            logger.error("quickbooks_fetch_customers_failed", error=str(e))
            raise
