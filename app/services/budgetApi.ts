// Budget API service functions
import { getApiBaseUrl } from '@/utils/env';
import type {
  BudgetCategory,
  BudgetSummary,
  VendorQuote,
  BudgetTemplate,
  CreateBudgetCategoryRequest,
  UpdateBudgetCategoryRequest,
  CreateVendorQuoteRequest,
  BudgetAlert,
  PaymentRecord,
  RecordPaymentRequest,
  CreateBudgetTemplatePayload,
  ApplyBudgetTemplateResult
} from '../types/budget';

const BASE_URL = getApiBaseUrl();

class BudgetApiService {
  private getHeaders(token: string) {
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }

  // Budget Categories
  async getBudgetCategories(token: string, weddingId: string): Promise<BudgetCategory[]> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${weddingId}/budget`,
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to fetch budget categories');
    const budgetData = await response.json();
    const categories = budgetData?.data?.categories ?? budgetData.categories ?? [];
    return Array.isArray(categories)
      ? categories.map((category) => this.normaliseCategory(category))
      : [];
  }

  async createBudgetCategory(token: string, data: CreateBudgetCategoryRequest): Promise<BudgetCategory> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${data.wedding_id}/budget/category`,
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify(data)
      }
    );
    if (!response.ok) throw new Error('Failed to create budget category');
    const payload = await response.json();
    return this.normaliseCategory(this.unwrapCategoryPayload(payload));
  }

  async updateBudgetCategory(token: string, categoryId: string, data: UpdateBudgetCategoryRequest): Promise<BudgetCategory> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/category/${categoryId}`,
      {
        method: 'PUT',
        headers: this.getHeaders(token),
        body: JSON.stringify(data)
      }
    );
    if (!response.ok) throw new Error('Failed to update budget category');
    const payload = await response.json();
    return this.normaliseCategory(this.unwrapCategoryPayload(payload));
  }

  async deleteBudgetCategory(token: string, categoryId: string): Promise<void> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/category/${categoryId}`,
      {
        method: 'DELETE',
        headers: this.getHeaders(token)
      }
    );
    if (!response.ok) throw new Error('Failed to delete budget category');
  }

  // Total Budget
  async setTotalBudget(token: string, weddingId: string, totalBudget: number): Promise<{ total_budget: number }> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${weddingId}/budget/total`,
      {
        method: 'PUT',
        headers: this.getHeaders(token),
        body: JSON.stringify({ total_budget: totalBudget })
      }
    );
    if (!response.ok) throw new Error('Failed to update total budget');
    return response.json();
  }

  // Budget Summary
  async getBudgetSummary(token: string, weddingId: string): Promise<BudgetSummary> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${weddingId}/budget`,
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to fetch budget summary');
    const budgetData = await response.json();
    return budgetData.summary || budgetData;
  }

  // Vendor Quotes
  async getVendorQuotes(token: string, weddingId: string, category?: string): Promise<VendorQuote[]> {
    const url = category
      ? `${BASE_URL}/admin/weddings/${weddingId}/quotes?service_category=${encodeURIComponent(category)}`
      : `${BASE_URL}/admin/weddings/${weddingId}/quotes`;

    const response = await fetch(url, { headers: this.getHeaders(token) });
    if (!response.ok) throw new Error('Failed to fetch vendor quotes');
    const payload = await response.json();
    // Backend returns {quotes: [...], count: N} — unwrap the array
    return Array.isArray(payload.quotes) ? payload.quotes : (Array.isArray(payload) ? payload : []);
  }

  async createVendorQuote(token: string, data: CreateVendorQuoteRequest): Promise<VendorQuote> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${data.wedding_id}/quotes`,
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify(data)
      }
    );
    if (!response.ok) throw new Error('Failed to create vendor quote');
    const payload = await response.json();
    // Backend returns {message, quote} — unwrap
    return payload.quote || payload;
  }

  async updateVendorQuoteStatus(token: string, quoteId: string, status: string): Promise<VendorQuote> {
    const response = await fetch(
      `${BASE_URL}/admin/quotes/${quoteId}/status`,
      {
        method: 'PUT',
        headers: this.getHeaders(token),
        body: JSON.stringify({ status })
      }
    );
    if (!response.ok) throw new Error('Failed to update vendor quote status');
    const payload = await response.json();
    // Backend returns {message, quote} — unwrap
    return payload.quote || payload;
  }

  async rateVendorQuote(token: string, quoteId: string, rating: number, notes?: string): Promise<VendorQuote> {
    const response = await fetch(
      `${BASE_URL}/admin/quotes/${quoteId}/rating`,
      {
        method: 'PUT',
        headers: this.getHeaders(token),
        body: JSON.stringify({ rating, notes })
      }
    );
    if (!response.ok) throw new Error('Failed to rate vendor quote');
    return response.json();
  }

  // Budget Templates
  async getBudgetTemplates(token: string): Promise<BudgetTemplate[]> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/templates`,
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to fetch budget templates');

    const payload = await response.json();
    const templates: unknown = Array.isArray(payload?.templates) ? payload.templates : payload;
    if (!Array.isArray(templates)) {
      return [];
    }

    return templates.map((template) => this.normaliseTemplate(template));
  }

  async createBudgetTemplate(
    token: string,
    data: CreateBudgetTemplatePayload
  ): Promise<BudgetTemplate> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/templates`,
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify(data),
      }
    );

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      const message = typeof errorPayload?.detail === 'string'
        ? errorPayload.detail
        : 'Failed to create budget template';
      throw new Error(message);
    }

    const payload = await response.json();
    const templateData = payload?.template ?? payload;
    return this.normaliseTemplate(templateData);
  }

  async applyBudgetTemplate(
    token: string,
    weddingId: string,
    templateId: string,
    totalBudget: number
  ): Promise<ApplyBudgetTemplateResult> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${weddingId}/budget/apply-template`,
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify({ template_id: templateId, total_budget: totalBudget })
      }
    );
    if (!response.ok) throw new Error('Failed to apply budget template');
    const payload = await response.json();
    return payload?.result ?? payload;
  }

  // Cost Estimation
  async getCostEstimate(token: string, weddingType: string, guestCount: number, region: string): Promise<any> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/estimate`,
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify({
          wedding_type: weddingType,
          guest_count: guestCount,
          region: region
        })
      }
    );
    if (!response.ok) throw new Error('Failed to get cost estimate');
    return response.json();
  }

  // Budget Alerts
  async getBudgetAlerts(token: string, weddingId: string): Promise<BudgetAlert[]> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/alerts/${weddingId}`,
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to fetch budget alerts');
    const payload = await response.json();
    return Array.isArray(payload.alerts) ? payload.alerts : (Array.isArray(payload) ? payload : []);
  }

  async markAlertAsRead(token: string, alertId: string): Promise<void> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/alerts/${alertId}/read`,
      {
        method: 'PUT',
        headers: this.getHeaders(token)
      }
    );
    if (!response.ok) throw new Error('Failed to mark alert as read');
  }

  async resolveAlert(token: string, alertId: string): Promise<void> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/alerts/${alertId}/resolve`,
      {
        method: 'PUT',
        headers: this.getHeaders(token)
      }
    );
    if (!response.ok) throw new Error('Failed to resolve alert');
  }

  // Financial Reports
  async getFinancialReport(token: string, weddingId: string, format: 'pdf' | 'excel'): Promise<Blob> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${weddingId}/budget/report?format=${format}`,
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to generate financial report');
    return response.blob();
  }

  // Vendor Quote Comparison
  async compareVendorQuotes(token: string, weddingId: string, category: string): Promise<any> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${weddingId}/quotes/compare/${encodeURIComponent(category)}`,
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to compare vendor quotes');
    return response.json();
  }

  // Payments
  async recordPayment(
    token: string,
    categoryId: string,
    data: RecordPaymentRequest
  ): Promise<PaymentRecord> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/category/${categoryId}/payment`,
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify(data)
      }
    );

    if (!response.ok) throw new Error('Failed to record payment');

    const payload = await response.json();
    return this.unwrapPaymentPayload(payload);
  }

  async getPaymentHistory(token: string, weddingId: string): Promise<PaymentRecord[]> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${weddingId}/payments`,
      { headers: this.getHeaders(token) }
    );

    if (!response.ok) throw new Error('Failed to fetch payment history');

    const payload = await response.json();
    const payments = this.unwrapPaymentListPayload(payload);
    return Array.isArray(payments) ? payments : [];
  }

  async updatePayment(
    token: string,
    paymentId: string,
    data: RecordPaymentRequest
  ): Promise<PaymentRecord> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/payment/${paymentId}`,
      {
        method: 'PUT',
        headers: this.getHeaders(token),
        body: JSON.stringify(data)
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to update payment');
    }

    const payload = await response.json();
    return this.unwrapPaymentPayload(payload);
  }

  async deletePayment(token: string, paymentId: string): Promise<void> {
    const response = await fetch(
      `${BASE_URL}/admin/budget/payment/${paymentId}`,
      {
        method: 'DELETE',
        headers: this.getHeaders(token)
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to delete payment');
    }
  }

  private normaliseTemplate(template: unknown): BudgetTemplate {
    if (!template || typeof template !== 'object') {
      throw new Error('Invalid template payload received from server');
    }

    const raw = template as Record<string, unknown>;
    const identifier = typeof raw.id === 'string'
      ? raw.id
      : typeof raw._id === 'string'
        ? raw._id
        : typeof raw._id === 'object' && raw._id && 'oid' in raw._id
          ? String((raw._id as Record<string, unknown>).oid)
          : typeof (raw._id as { $oid?: string })?.$oid === 'string'
            ? (raw._id as { $oid: string }).$oid
            : '';

    const guestRange = (raw.guest_count_range ?? {}) as Record<string, unknown>;

    const categories = Array.isArray(raw.categories)
      ? raw.categories.map((category) => {
          const cat = category as Record<string, unknown>;
          return {
            name: String(cat.name ?? ''),
            percentage: Number(cat.percentage ?? 0),
            priority: Number(cat.priority ?? 3),
          };
        })
      : [];

    return {
      id: identifier,
      _id: identifier,
      name: String(raw.name ?? ''),
      description: raw.description ? String(raw.description) : undefined,
      wedding_type: String(raw.wedding_type ?? ''),
      target_budget_min: Number(raw.target_budget_min ?? 0),
      target_budget_max: Number(raw.target_budget_max ?? 0),
      guest_count_range: {
        min: Number(guestRange.min ?? guestRange['$min'] ?? 0),
        max: Number(guestRange.max ?? guestRange['$max'] ?? 0),
      },
      categories,
      created_by: raw.created_by ? String(raw.created_by) : undefined,
      is_public: Boolean(raw.is_public),
      created_at: String(raw.created_at ?? ''),
      updated_at: String(raw.updated_at ?? raw.created_at ?? ''),
    };
  }

  private unwrapCategoryPayload(payload: unknown): unknown {
    if (!payload || typeof payload !== 'object') {
      return payload;
    }

    const raw = payload as Record<string, unknown>;
    const data = raw.data;

    if (data && typeof data === 'object' && 'category' in data) {
      return (data as Record<string, unknown>).category;
    }

    if ('category' in raw) {
      return raw.category;
    }

    return payload;
  }

  private unwrapPaymentPayload(payload: unknown): PaymentRecord {
    const payment = this.unwrapNamedPayload(payload, 'payment');

    if (!payment || typeof payment !== 'object') {
      throw new Error('Invalid payment payload received from server');
    }

    return payment as PaymentRecord;
  }

  private unwrapPaymentListPayload(payload: unknown): unknown {
    return this.unwrapNamedPayload(payload, 'payments');
  }

  private unwrapNamedPayload(payload: unknown, key: string): unknown {
    if (!payload || typeof payload !== 'object') {
      return payload;
    }

    const raw = payload as Record<string, unknown>;
    const data = raw.data;

    if (data && typeof data === 'object' && key in data) {
      return (data as Record<string, unknown>)[key];
    }

    if (key in raw) {
      return raw[key];
    }

    return payload;
  }

  private normaliseCategory(category: unknown): BudgetCategory {
    if (!category || typeof category !== 'object') {
      throw new Error('Invalid budget category payload received from server');
    }

    const raw = category as Record<string, unknown>;
    const identifier = typeof raw.id === 'string'
      ? raw.id
      : typeof raw._id === 'string'
        ? raw._id
        : typeof (raw._id as { $oid?: string })?.$oid === 'string'
          ? (raw._id as { $oid: string }).$oid
          : '';

    if (!identifier || typeof raw.name !== 'string') {
      throw new Error('Invalid budget category payload received from server');
    }

    return {
      ...(raw as unknown as BudgetCategory),
      id: identifier,
      _id: identifier,
      name: raw.name,
      description: typeof raw.description === 'string' ? raw.description : undefined,
      budgeted_amount: Number(raw.budgeted_amount ?? 0),
      actual_spent: Number(raw.actual_spent ?? 0),
      payment_status: this.normalisePaymentStatus(raw.payment_status),
      priority: this.normalisePriority(raw.priority),
      percentage_of_total: raw.percentage_of_total == null
        ? undefined
        : Number(raw.percentage_of_total),
      subcategories: Array.isArray(raw.subcategories) ? raw.subcategories : [],
      vendor_quotes: Array.isArray(raw.vendor_quotes) ? raw.vendor_quotes : [],
      payments: Array.isArray(raw.payments) ? raw.payments : [],
      created_at: String(raw.created_at ?? ''),
      updated_at: String(raw.updated_at ?? raw.created_at ?? ''),
    };
  }

  private normalisePaymentStatus(status: unknown): BudgetCategory['payment_status'] {
    return status === 'partial' || status === 'paid' || status === 'overdue'
      ? status
      : 'pending';
  }

  private normalisePriority(priority: unknown): BudgetCategory['priority'] {
    const parsed = Number(priority);
    return parsed === 1 || parsed === 2 || parsed === 3 || parsed === 4 || parsed === 5
      ? parsed
      : 3;
  }
}

export const budgetApi = new BudgetApiService();
