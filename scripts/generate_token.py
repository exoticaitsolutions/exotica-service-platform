#!/usr/bin/env python3
"""Generate a JWT token for dashboard authentication."""

import sys
from datetime import datetime, timedelta, UTC

from jose import jwt


def generate_token(
    secret: str,
    subject: str = "demo-user",
    tenant_id: str = "default-tenant",
    actor_type: str = "user",
    hours_valid: int = 24,
) -> str:
    """Generate a HS256-signed JWT token.

    Args:
        secret: JWT signing secret (must match JWT_SECRET_ARN in config)
        subject: User/actor ID
        tenant_id: Tenant UUID this token is scoped to
        actor_type: Either 'user' or 'system'
        hours_valid: Token expiration time in hours

    Returns:
        Signed JWT token string
    """
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "actor_type": actor_type,
        "scopes": ["reconciliation:read", "reconciliation:write"],
        "exp": datetime.now(UTC) + timedelta(hours=hours_valid),
    }

    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_token.py <secret> [subject] [tenant_id]")
        print()
        print("Example:")
        print("  python generate_token.py 'dev-jwt-secret' demo-user default-tenant")
        print()
        print("Environment variables:")
        print("  JWT_SECRET: Override via environment variable")
        sys.exit(1)

    secret = sys.argv[1]
    subject = sys.argv[2] if len(sys.argv) > 2 else "demo-user"
    tenant_id = sys.argv[3] if len(sys.argv) > 3 else "default-tenant"

    token = generate_token(secret, subject, tenant_id)

    print("=" * 70)
    print("JWT Token Generated")
    print("=" * 70)
    print()
    print("Token (copy this into the dashboard):")
    print(token)
    print()
    print("Token Details:")
    print(f"  Subject: {subject}")
    print(f"  Tenant ID: {tenant_id}")
    print(f"  Actor Type: user")
    print(f"  Expires: {datetime.now(UTC) + timedelta(hours=24)}")
    print()
    print("Usage:")
    print("  1. Open http://localhost:8001/dashboard_connected.html")
    print("  2. Paste the token into the 'Enter JWT token' field")
    print("  3. Click 'Connect'")
    print()
