# Reconciliation Dashboard

A real-time dashboard for ServiceTitan ↔ QuickBooks financial reconciliation, displaying invoice matching status, discrepancies, and health metrics.

## Features

- **Reconciliation Health Score** — Visual indicator of matching success rate
- **Run Metrics** — Total invoices, matched count, discrepancy summary
- **Discrepancy Detection** — Categorizes mismatches by type and severity
  - Missing in QuickBooks (ST invoice not synced)
  - Missing in ServiceTitan (QB entry not reconciled)
  - Amount Mismatch (same invoice, different totals)
- **Advanced Filtering** — Filter by severity (error/warning/info), type, or status
- **Paginated View** — Browse discrepancies in chunks (10 per page)

## Quick Start

### Using Mock Data (Demo)
Open `reconciliation_dashboard.html` directly in a browser. The dashboard loads with randomly-generated sample data.

### Connecting to Live API

Use the provided TypeScript API client to connect to your backend:

```typescript
import { ReconciliationApiClient } from './api_client';

const client = new ReconciliationApiClient('http://localhost:8000');
client.setToken('your-jwt-token');

// Trigger a reconciliation run
const run = await client.triggerReconciliation(
  'tenant-uuid',
  '2026-08-01',
  '2026-09-05'
);

// List discrepancies for a specific run
const discrepancies = await client.listRunDiscrepancies(run.run_id, {
  severity: 'error',
  limit: 50,
  offset: 0,
});

// Get tenant-wide discrepancies with filters
const all = await client.listTenantDiscrepancies({
  status: 'open',
  severity: 'warning',
  min_amount: '100.00',
  limit: 25,
});
```

## API Endpoints

All endpoints require JWT authentication (`Authorization: Bearer <token>`).

### Trigger Reconciliation
```
POST /accounting/reconcile
{
  "tenant_id": "uuid",
  "date_from": "2026-08-01",
  "date_to": "2026-09-05",
  "trigger_source": "dashboard"
}
→ 202 Accepted with ReconciliationRun
```

### Get Run Details
```
GET /accounting/runs/{run_id}
→ 200 ReconciliationRun
```

### List Run Discrepancies
```
GET /accounting/runs/{run_id}/discrepancies?severity=error&discrepancy_type=missing_in_quickbooks&limit=50&offset=0
→ 200 { items: Discrepancy[], page: { offset, limit, total, has_more } }
```

### List Tenant-Wide Discrepancies
```
GET /accounting/discrepancies?status=open&severity=warning&min_amount=100.00&limit=25
→ 200 { items: Discrepancy[], page: { offset, limit, total, has_more } }
```

### Get Single Discrepancy
```
GET /accounting/discrepancies/{discrepancy_id}
→ 200 Discrepancy
```

## Data Structures

### ReconciliationRun
```typescript
{
  run_id: string;                    // UUID of the reconciliation run
  tenant_id: string;                 // Tenant this run belongs to
  status: 'in_progress' | 'succeeded' | 'failed' | 'partial';
  date_from: string;                 // Start date (YYYY-MM-DD)
  date_to: string;                   // End date (YYYY-MM-DD)
  started_at: string;                // ISO8601 timestamp
  completed_at: string | null;       // ISO8601 timestamp
  servicetitan_invoice_count: number | null;
  quickbooks_invoice_count: number | null;
  matched_count: number | null;      // Successfully matched invoices
  discrepancy_count: number | null;  // Total discrepancies found
  health_score: float | null;        // 0.0–1.0; matched_count / max(st, qb)
  source_errors: Array<{ source: string; error: string }>;
}
```

### Discrepancy
```typescript
{
  discrepancy_id: string;                 // UUID
  run_id: string;                         // Parent run
  tenant_id: string;                      // Tenant
  type: 'missing_in_quickbooks' | 'missing_in_servicetitan' | 'amount_mismatch';
  severity: 'info' | 'warning' | 'error'; // Based on amount or mismatch type
  status: 'open' | 'awaiting_approval' | 'resolved' | 'dismissed';
  servicetitan_invoice_id: string | null;
  quickbooks_invoice_id: string | null;
  customer_name: string | null;
  servicetitan_amount: string | null;     // Decimal as string
  quickbooks_amount: string | null;       // Decimal as string
  difference: string;                     // Absolute difference as decimal
  currency: string;                       // e.g., "USD"
  detected_at: string;                    // ISO8601
}
```

## Severity Classification

- **error** (🔴)
  - Any `missing_in_quickbooks` discrepancy
  - Any `missing_in_servicetitan` discrepancy
  - `amount_mismatch` with difference ≥ $100
- **warning** (⚠️)
  - `amount_mismatch` with difference < $100
- **info** (ℹ️)
  - Reserved for future rounding/timing issues

## Deployment

### Development
```bash
# Serve the dashboard locally
python -m http.server 8001 --directory frontend/

# Open in browser
open http://localhost:8001/reconciliation_dashboard.html
```

### Production
- Serve `reconciliation_dashboard.html` from a CDN or static hosting
- Update API base URL in `api_client.ts` to production endpoint
- Ensure CORS is properly configured on the backend (allowed origin must include dashboard domain)

## Architecture Notes

The dashboard and API client are intentionally decoupled:
- **Dashboard** is a vanilla JavaScript + HTML/CSS page (no build step required)
- **API Client** is TypeScript and can be imported into any frontend framework (React, Vue, Svelte)
- Both handle tenant isolation via JWT claims and server-side repository checks

The backend enforces tenant isolation at every query layer, so the dashboard cannot accidentally query across tenants even if a malicious token is used.

## Future Enhancements

Step 4/5 will add:
- AI-powered analysis of discrepancies (root cause detection)
- Approval workflow for write-backs
- Manual discrepancy resolution UI
- Export discrepancies as CSV
- Webhook notifications on new high-severity mismatches
