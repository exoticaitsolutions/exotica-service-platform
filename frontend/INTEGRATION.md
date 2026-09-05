# Dashboard Integration — Complete Setup

The reconciliation dashboard is fully connected to your backend API. This document shows how to run it end-to-end.

## 🚀 Start Here (3 Steps)

### Step 1: Terminal — Start the API
```bash
cd exotica-service-platform
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

✓ API running at `http://localhost:8000`

### Step 2: Terminal — Start Dashboard Server
```bash
cd exotica-service-platform
python -m http.server 8001
```

✓ Dashboard available at `http://localhost:8001/frontend/dashboard.html`

### Step 3: Generate Auth Token
```bash
cd exotica-service-platform
python scripts/generate_token.py "dev-jwt-secret"
```

Output:
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 📊 Open the Dashboard

1. Open http://localhost:8001/frontend/dashboard.html
2. Paste the token from Step 3 into the auth panel
3. Click **Connect**

The dashboard will load all discrepancies from the API.

## ✨ Features

### Authentication Panel
- Input field for JWT token
- Auto-saves token to localStorage
- Status indicator (Connected / Disconnected)

### Metrics
- **Health Score** — Visual gauge of reconciliation success
- **Last Run** — Timestamp and status of most recent run
- **Invoices Matched** — Count and ratio
- **Total Discrepancies** — Quick overview

### Discrepancy Table
- Real-time data from API
- Filter by severity, type, status
- Paginated (10 per page)
- Shows customer name, invoice IDs, amounts, differences

### Trigger Reconciliation
- **"▶ Start Reconciliation"** button in header
- Auto-detects last 60 days
- Runs synchronously (blocks until complete)
- Auto-refreshes dashboard when done

## 🔌 Data Flow

```
Dashboard (HTML/JS)
    ↓ (JWT in Authorization header)
API Server (FastAPI)
    ├→ Verify JWT token
    ├→ Extract tenant_id from claims
    ├→ Query DiscrepancyRepository
    └→ Return paginated results

Repository (SQLAlchemy)
    ├→ Filter by tenant_id (multi-tenant safety)
    ├→ Apply severity/type/status filters
    └→ Query PostgreSQL
```

## 📡 API Endpoints

### List Tenant Discrepancies
```
GET /accounting/discrepancies?severity=error&limit=50&offset=0
Authorization: Bearer <jwt>

Response:
{
  "items": [
    {
      "discrepancy_id": "uuid",
      "type": "missing_in_quickbooks",
      "severity": "error",
      "status": "open",
      "customer_name": "Acme Corp",
      "servicetitan_invoice_id": "ST-001",
      "quickbooks_invoice_id": null,
      "servicetitan_amount": "1000.00",
      "quickbooks_amount": null,
      "difference": "1000.00",
      "currency": "USD",
      "detected_at": "2026-09-05T14:30:00Z"
    }
  ],
  "page": {
    "offset": 0,
    "limit": 50,
    "total": 47,
    "has_more": false
  }
}
```

### Trigger Reconciliation
```
POST /accounting/reconcile
Authorization: Bearer <jwt>
Content-Type: application/json

Request:
{
  "tenant_id": "default-tenant",
  "date_from": "2026-07-06",
  "date_to": "2026-09-05",
  "trigger_source": "dashboard"
}

Response (202 Accepted):
{
  "run_id": "uuid",
  "status": "in_progress" | "succeeded" | "failed" | "partial",
  "matched_count": 87,
  "discrepancy_count": 15,
  "health_score": 0.85,
  "started_at": "2026-09-05T14:30:00Z",
  "completed_at": "2026-09-05T14:30:30Z"
}
```

## 🎯 Common Tasks

### Add Custom Filters
Edit `dashboard.html` lines 420–425 to add more filter options:
```javascript
// Add to typeFilter select
<option value="underpayment">Underpayment</option>
<option value="timing_mismatch">Timing Mismatch</option>
```

### Change Page Size
Edit line 409 to adjust pagination:
```javascript
const pageSize = 25; // was 10
```

### Auto-Refresh
Add this before closing `</script>` tag to auto-refresh every 30 seconds:
```javascript
setInterval(loadData, 30000);
```

### Dark Mode
Add this to the `<style>` block to automatically respect system dark mode preference:
```css
@media (prefers-color-scheme: dark) {
  :root {
    --bg-light: #1f2937;
    --bg-white: #111827;
    --text-primary: #f3f4f6;
    --text-secondary: #d1d5db;
    --border-light: #374151;
  }
}
```

## 🔐 Security

### Token Handling
- Tokens are stored in `localStorage` (browser-side only)
- Never logged or sent to third parties
- Included in every API request as `Authorization: Bearer <token>`
- Server verifies signature using `JWT_SECRET_ARN`

### Multi-Tenant Isolation
- Token contains `tenant_id` claim
- Server enforces this claim on every query
- DiscrepancyRepository base class prevents cross-tenant queries
- Even if a malicious token is used, server-side filtering prevents data leakage

### CORS
- Dashboard can only call API from whitelisted origins
- Configured in CORS_ALLOWED_ORIGINS (.env)
- Supports multiple local dev ports for flexibility

## 🧪 Testing

### Test API Endpoints with curl
```bash
# Get auth token
TOKEN=$(python scripts/generate_token.py "dev-jwt-secret" | grep "^ey")

# List discrepancies
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/accounting/discrepancies

# Trigger reconciliation
curl -X POST http://localhost:8000/accounting/reconcile \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default-tenant",
    "date_from": "2026-08-01",
    "date_to": "2026-09-05"
  }'
```

### Test Dashboard Offline
Open `frontend/dashboard.html` directly without running the server to verify HTML/CSS loads.

### Monitor API Logs
```bash
# Watch API logs in real-time
docker logs -f exotica-api
# Or with uvicorn (local):
# Already displayed in terminal
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection Failed: HTTP 401" | Token expired or invalid. Regenerate with `generate_token.py` |
| "Connection Failed: CORS error" | Dashboard URL not in CORS_ALLOWED_ORIGINS. Update .env and restart API |
| No discrepancies appear | Click "Start Reconciliation" to trigger a run |
| Table shows "Loading..." forever | Check browser console (F12) for network errors |
| API returns 404 on /accounting/discrepancies | Ensure reconciliation_router is registered in app.py |
| Authentication panel won't appear | Check browser console for JavaScript errors |

## 📋 Checklist

- [ ] API running on http://localhost:8000
- [ ] Dashboard server running on http://localhost:8001
- [ ] Generated JWT token
- [ ] Pasted token into dashboard auth panel
- [ ] Dashboard shows "Connected" status
- [ ] Table populated with discrepancies
- [ ] Filters working (try filtering by "error" severity)
- [ ] Pagination working (if >10 discrepancies)
- [ ] "Start Reconciliation" button visible and clickable

## 📚 Reference

- **OpenAPI Spec** — `openapi.yaml`
- **Backend Config** — `core/config.py` (CORS_ALLOWED_ORIGINS)
- **Database Setup** — `alembic/versions/`
- **Tests** — `tests/modules/test_matching_and_discrepancies.py`

## Next Steps

1. **Deploy to staging** — Build Docker image, push to registry
2. **Add AI analysis** — Step 4 (discrepancy root cause detection)
3. **Approval workflow** — Step 5 (manual discrepancy resolution)
4. **Notifications** — Webhooks on new high-severity mismatches
