#!/usr/bin/env python3
"""QuickBooks OAuth2 authorization script. One-time setup to get refresh token and realm ID.

Usage:
    QUICKBOOKS_CLIENT_ID=<your-id> \
    QUICKBOOKS_CLIENT_SECRET=<your-secret> \
    python scripts/quickbooks_oauth.py

This opens your browser for approval, then prints the tokens to add to .env
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import httpx

CLIENT_ID = os.getenv("QUICKBOOKS_CLIENT_ID")
CLIENT_SECRET = os.getenv("QUICKBOOKS_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8765/callback"
AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/tokens"

auth_code = None
realm_id = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from Intuit."""

    def do_get(self) -> None:
        """Handle GET request from OAuth redirect."""
        global auth_code, realm_id

        query = urlparse(self.path).query
        params = parse_qs(query)

        if "code" in params:
            auth_code = params["code"][0]
            realm_id = params.get("realmId", [None])[0]

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Success!</h1>"
                b"<p>You can close this window and return to the terminal.</p>"
                b"</body></html>"
            )
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authorization Failed</h1>"
                b"<p>No authorization code received.</p>"
                b"</body></html>"
            )

    def log_message(self, format: str, *args: object) -> None:
        """Suppress logging."""
        pass


def get_refresh_token(code: str) -> dict[str, str]:
    """Exchange authorization code for refresh token."""
    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(CLIENT_ID, CLIENT_SECRET),
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    """Run OAuth flow."""
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: QUICKBOOKS_CLIENT_ID and QUICKBOOKS_CLIENT_SECRET env vars required")
        sys.exit(1)

    print("=" * 70)
    print("QuickBooks OAuth Authorization")
    print("=" * 70)
    print()
    print("Starting local callback server on http://localhost:8765...")

    server = HTTPServer(("localhost", 8765), OAuthCallbackHandler)

    print("Opening your browser for authorization...")
    print()

    auth_params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "com.intuit.quickbooks.accounting",
        "redirect_uri": REDIRECT_URI,
        "state": "exotica-service-platform",
    }

    auth_url = f"{AUTH_URL}?{'&'.join(f'{k}={v}' for k, v in auth_params.items())}"
    webbrowser.open(auth_url)

    print("Waiting for authorization... (listening on http://localhost:8765/callback)")
    print()

    try:
        server.handle_request()
    except KeyboardInterrupt:
        print("\nCanceled by user")
        sys.exit(1)

    if not auth_code:
        print("Error: No authorization code received")
        sys.exit(1)

    print()
    print("Authorization code received. Exchanging for refresh token...")

    try:
        token_data = get_refresh_token(auth_code)
    except httpx.HTTPError as e:
        print(f"Error: Token exchange failed: {e}")
        sys.exit(1)

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        print("Error: No refresh token in response")
        sys.exit(1)

    print()
    print("=" * 70)
    print("✅ Success! Add these to your .env file:")
    print("=" * 70)
    print()
    print(f"QUICKBOOKS_REALM_ID={realm_id}")
    print(f"QUICKBOOKS_REFRESH_TOKEN={refresh_token}")
    print(f"QUICKBOOKS_CLIENT_ID={CLIENT_ID}")
    print(f"QUICKBOOKS_CLIENT_SECRET={CLIENT_SECRET}")
    print(f"QUICKBOOKS_ENVIRONMENT=sandbox")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
