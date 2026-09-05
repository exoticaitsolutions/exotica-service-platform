# Dashboard Integration Guide

This guide explains how to run the connected reconciliation dashboard with the backend API.

## Quick Start (5 minutes)

### 1. Start the Backend API

```bash
# Terminal 1: Start the API server
cd exotica-service-platform
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
- OpenAPI docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 2. Serve the Dashboard

```bash
# Terminal 2: Serve the dashboard
cd exotica-service-platform
python -m http.server 8001 --directory .
```

The dashboard will be available at `http://localhost:8001/dashboard_connected.html`

### 3. Generate a JWT Token

You need a JWT token to authenticate. You can generate one using the auth system:

```python
from core.auth import encode_token
from datetime import datetime, timedelta, UTC

token = encode_token(
    sub="user-123",
    tenant_id="default-tenant",
    actor_type="user",
    scopes=["reconciliation:read", "reconciliation:write"],
    exp=datetime.now(UTC) + timedelta(hours=24)
)
print(token)
```

Or use curl to generate it if an endpoint exists:
```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo",
    "password": "demo"
  }'
```

### 4. Open the Dashboard

1. Open http://localhost:8001/dashboard_connected.html in your browser
2. Paste your JWT token into the "Enter JWT token" field
3. Click "Connect"
4. The dashboard will load all discrepancies from the API

## Features

### Authenticate
- Paste a JWT token into the auth panel
- Token is saved to localStorage for subsequent visits
- Status indicator shows connection status

### View Metrics
- **Health Score** — Percentage of successfully matched invoices
- **Last Run** — Timestamp of the most recent reconciliation
- **Invoices Matched** — Count of matched vs total invoices
- **Total Discrepancies** — Overall count of mismatches

### Browse Discrepancies
- **Filter by Severity** — Error, Warning, Info
- **Filter by Type** — Missing in QB, Missing in ST, Amount Mismatch
- **Filter by Status** — Open, Resolved
- **Pagination** — 10 items per page

### Trigger Reconciliation
- Click **"▶ Start Reconciliation"** button in the header
- Automatically sets date range (last 60 days)
- Real-time status updates
- Dashboard refreshes after reconciliation completes

## Architecture

### Dashboard Components

**dashboard_connected.html**
- Vanilla JavaScript (no build required)
- Embedded API client class
- Auto-loads saved token from localStorage
- Real-time data fetching and filtering

**api_client.ts** (TypeScript reference)
- Reusable API client for React/Vue/other frameworks
- Type-safe endpoints
- Proper error handling

### API Endpoints Used

```
POST   /accounting/reconcile              → Start reconciliation run
GET    /accounting/discrepancies          → List all discrepancies (with filters)
GET    /accounting/runs/{run_id}          → Get specific run details
GET    /accounting/discrepancies/{id}     → Get single discrepancy
```

All endpoints require JWT authentication via `Authorization: Bearer <token>` header.

## Environment Variables

Configure these in `.env` or as system environment variables:

```bash
# Database (required)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/exotica_dev

# Secrets
SECRETS_PROVIDER=env
JWT_SECRET_ARN=your-jwt-secret-key

# ServiceTitan
SERVICETITAN_API_KEY=your-st-api-key
SERVICETITAN_API_ENDPOINT=https://api.servicetitan.com

# QuickBooks
QUICKBOOKS_REALM_ID=your-realm-id
QUICKBOOKS_CLIENT_ID=your-client-id
QUICKBOOKS_CLIENT_SECRET=your-secret
QUICKBOOKS_REFRESH_TOKEN=your-refresh-token
QUICKBOOKS_ENVIRONMENT=sandbox

# CORS (dashboard URLs)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8001,http://localhost:8000

# Logging
ENVIRONMENT=local
LOG_LEVEL=DEBUG
```

## Token Generation Examples

### Using Python
```python
import jwt
from datetime import datetime, timedelta, UTC

secret = "your-jwt-secret-key"
payload = {
    "sub": "user-123",
    "tenant_id": "default-tenant",
    "actor_type": "user",
    "scopes": ["reconciliation:read", "reconciliation:write"],
    "exp": datetime.now(UTC) + timedelta(hours=24)
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(f"Token: {token}")
```

### Using Node.js
```javascript
const jwt = require('jsonwebtoken');

const secret = 'your-jwt-secret-key';
const token = jwt.sign({
  sub: 'user-123',
  tenant_id: 'default-tenant',
  actor_type: 'user',
  scopes: ['reconciliation:read', 'reconciliation:write'],
  exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60)
}, secret, { algorithm: 'HS256' });

console.log(`Token: ${token}`);
```

## Troubleshooting

### "Connection Failed: HTTP 401"
- Token is invalid or expired
- Regenerate a new token and try again
- Check that JWT_SECRET_ARN matches the token's signing key

### "Connection Failed: HTTP 403"
- Token is valid but not authorized for this tenant
- Verify the `tenant_id` in your token matches the API request

### "Connection Failed: CORS error"
- Dashboard is served from a URL not in CORS_ALLOWED_ORIGINS
- Update `CORS_ALLOWED_ORIGINS` in `.env` to include the dashboard URL
- Restart the API server

### No discrepancies appear
- No reconciliation runs have been completed yet
- Click **"▶ Start Reconciliation"** to trigger a run
- Wait for the run to complete (2-5 seconds typically)
- Dashboard will auto-refresh when complete

### "Failed to load data"
- Check browser console for error messages
- Verify the API is running on http://localhost:8000
- Verify token is valid (check /docs/auth endpoint)
- Check backend logs for errors

## Deployment

### Development
```bash
# Serve locally without build
python -m http.server 8001
```

### Production
1. Build API Docker image: `docker build -t exotica-api .`
2. Serve dashboard from CDN or static hosting
3. Update API base URL in dashboard to production domain
4. Update CORS_ALLOWED_ORIGINS to include dashboard domain
5. Use production JWT secrets (AWS Secrets Manager)

Example production environment:
```bash
ENVIRONMENT=production
CORS_ALLOWED_ORIGINS=https://dashboard.example.com,https://api.example.com
SECRETS_PROVIDER=aws
JWT_SECRET_ARN=arn:aws:secretsmanager:us-east-1:123456789:secret:jwt-secret
```

## Next Steps

- [API Documentation](openapi.yaml) — Full endpoint specification
- [Testing](tests/) — Unit and integration tests
- [Architecture](docs/) — Design decisions and patterns

## Support

For issues or questions:
1. Check the [troubleshooting](#troubleshooting) section
2. Review backend logs: `docker logs exotica-api`
3. Check browser console: F12 → Console tab
4. Review test coverage: `pytest --cov`
