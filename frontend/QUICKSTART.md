# Dashboard Quick Start — 2 Minutes

## TL;DR

```bash
# Terminal 1
python -m uvicorn app:app --reload --port 8000

# Terminal 2
python -m http.server 8001

# Terminal 3
python scripts/generate_token.py "dev-jwt-secret"

# Browser
# 1. Open http://localhost:8001/frontend/dashboard.html
# 2. Paste token
# 3. Click Connect
```

Done! You'll see live reconciliation data.

---

## What You'll See

### 1. Auth Panel (Top)
```
[Paste your JWT token here...] [Connect] ✓ Connected
```

### 2. Metrics (Dashboard)
```
Health Score: 85%    |    Last Run: 2 hours ago    |    87/102 matched    |    15 discrepancies
```

### 3. Summary Cards
```
Missing in QB: 7    |    Missing in ST: 4    |    Amount Mismatch: 4    |    Open: 15
```

### 4. Discrepancies Table
```
Type                 | Customer        | Severity | ST ID  | QB ID  | ST $    | QB $    | Diff   | Status
missing_in_qb        | Acme Corp       | error    | ST-001 | —      | 1000.00 | —      | 1000   | open
amount_mismatch      | Tech Solutions  | warning  | ST-002 | QB-002 | 500.00  | 450.00 | 50.00  | open
```

---

## Filters

**Severity Filter**
- 🔴 Error — Missing invoices or big mismatches (≥$100)
- ⚠️ Warning — Small amount mismatches (<$100)
- ℹ️ Info — Future: timing/rounding issues

**Type Filter**
- Missing in QB — Invoice exists in ServiceTitan only
- Missing in ST — Invoice exists in QuickBooks only
- Amount Mismatch — Same invoice, different amounts

**Status Filter**
- Open — Awaiting resolution
- Resolved — Already fixed

**Pagination**
- Shows 10 per page
- Use Previous/Next buttons to browse

---

## Actions

### Trigger Reconciliation
Click **"▶ Start Reconciliation"** button (top right)
- Fetches invoices from both systems
- Matches by customer name + amount
- Creates discrepancy records
- Updates dashboard automatically

### Browse Discrepancies
- Use filters to narrow down
- Scroll table for more details
- Each row = one mismatch

---

## Common Issues

| Problem | Fix |
|---------|-----|
| Can't paste token | Token field is at the very top. Make sure you're scrolled to top. |
| "Connection Failed" | Token expired. Regenerate with `generate_token.py` |
| No discrepancies | Click "Start Reconciliation" to run matching |
| Page won't load | Check API is running: `curl http://localhost:8000/health` |

---

## Generate New Token

```bash
python scripts/generate_token.py "dev-jwt-secret" "my-user" "my-tenant"
```

Replace `dev-jwt-secret` with your JWT_SECRET from `.env`

---

## Behind the Scenes

Dashboard makes requests like:
```
GET /accounting/discrepancies?severity=error&limit=10&offset=0
    Authorization: Bearer eyJhbGc...
```

API responds with:
```json
{
  "items": [...],
  "page": { "total": 47, "has_more": true }
}
```

Dashboard renders it in the table.

---

## Next: Deep Dive

- See `INTEGRATION.md` for full setup guide
- See `../DASHBOARD_SETUP.md` for troubleshooting
- See `../openapi.yaml` for API spec
