/**
 * API client for reconciliation endpoints.
 * Handles authentication, error handling, and request/response transformation.
 */

interface ReconciliationRun {
  run_id: string;
  tenant_id: string;
  status: 'in_progress' | 'succeeded' | 'failed' | 'partial';
  trigger_source: string;
  date_from: string;
  date_to: string;
  started_at: string;
  completed_at: string | null;
  servicetitan_invoice_count: number | null;
  quickbooks_invoice_count: number | null;
  matched_count: number | null;
  discrepancy_count: number | null;
  health_score: number | null;
  source_errors: Array<{ source: string; error: string }>;
}

interface Discrepancy {
  discrepancy_id: string;
  run_id: string;
  tenant_id: string;
  type: 'missing_in_quickbooks' | 'missing_in_servicetitan' | 'amount_mismatch';
  severity: 'info' | 'warning' | 'error';
  status: 'open' | 'awaiting_approval' | 'resolved' | 'dismissed';
  servicetitan_invoice_id: string | null;
  quickbooks_invoice_id: string | null;
  customer_name: string | null;
  servicetitan_amount: string | null;
  quickbooks_amount: string | null;
  difference: string;
  currency: string;
  detected_at: string;
}

interface DiscrepanciesListResponse {
  items: Discrepancy[];
  page: {
    offset: number;
    limit: number;
    total: number;
    has_more: boolean;
  };
}

class ReconciliationApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.token = localStorage.getItem('auth_token');
  }

  setToken(token: string): void {
    this.token = token;
    localStorage.setItem('auth_token', token);
  }

  private getHeaders(): HeadersInit {
    return {
      'Content-Type': 'application/json',
      ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
    };
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: this.getHeaders(),
      ...(body ? { body: JSON.stringify(body) } : {}),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        error.error?.message || `HTTP ${response.status}`,
      );
    }

    return response.json() as Promise<T>;
  }

  async triggerReconciliation(
    tenant_id: string,
    date_from?: string,
    date_to?: string,
  ): Promise<ReconciliationRun> {
    return this.request('POST', '/accounting/reconcile', {
      tenant_id,
      date_from,
      date_to,
      trigger_source: 'dashboard',
    });
  }

  async getReconciliationRun(run_id: string): Promise<ReconciliationRun> {
    return this.request('GET', `/accounting/runs/${run_id}`);
  }

  async listRunDiscrepancies(
    run_id: string,
    options: {
      severity?: string;
      discrepancy_type?: string;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<DiscrepanciesListResponse> {
    const params = new URLSearchParams();
    if (options.severity) params.append('severity', options.severity);
    if (options.discrepancy_type) params.append('discrepancy_type', options.discrepancy_type);
    if (options.limit) params.append('limit', String(options.limit));
    if (options.offset) params.append('offset', String(options.offset));

    const query = params.toString();
    const path = `/accounting/runs/${run_id}/discrepancies${query ? `?${query}` : ''}`;
    return this.request('GET', path);
  }

  async listTenantDiscrepancies(
    options: {
      status?: string;
      severity?: string;
      discrepancy_type?: string;
      min_amount?: string;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<DiscrepanciesListResponse> {
    const params = new URLSearchParams();
    if (options.status) params.append('status', options.status);
    if (options.severity) params.append('severity', options.severity);
    if (options.discrepancy_type) params.append('discrepancy_type', options.discrepancy_type);
    if (options.min_amount) params.append('min_amount', options.min_amount);
    if (options.limit) params.append('limit', String(options.limit));
    if (options.offset) params.append('offset', String(options.offset));

    const query = params.toString();
    const path = `/accounting/discrepancies${query ? `?${query}` : ''}`;
    return this.request('GET', path);
  }

  async getDiscrepancy(discrepancy_id: string): Promise<Discrepancy> {
    return this.request('GET', `/accounting/discrepancies/${discrepancy_id}`);
  }
}

export { ReconciliationApiClient, ReconciliationRun, Discrepancy, DiscrepanciesListResponse };
