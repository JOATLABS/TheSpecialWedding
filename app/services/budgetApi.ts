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
  CreateBudgetTemplatePayload
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
    return budgetData.categories || [];
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
    // Backend returns {message, category}, extract just the category
    return payload.category || payload;
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
    // Backend returns {message, category}, extract just the category
    return payload.category || payload;
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

  async applyBudgetTemplate(token: string, weddingId: string, templateId: string, totalBudget: number): Promise<BudgetCategory[]> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${weddingId}/budget/apply-template`,
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify({ template_id: templateId, total_budget: totalBudget })
      }
    );
    if (!response.ok) throw new Error('Failed to apply budget template');
    return response.json();
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
    return payload.payment as PaymentRecord;
  }

  async getPaymentHistory(token: string, weddingId: string): Promise<PaymentRecord[]> {
    const response = await fetch(
      `${BASE_URL}/admin/weddings/${weddingId}/payments`,
      { headers: this.getHeaders(token) }
    );

    if (!response.ok) throw new Error('Failed to fetch payment history');

    const payload = await response.json();
    return Array.isArray(payload.payments) ? payload.payments as PaymentRecord[] : [];
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
    return payload.payment as PaymentRecord;
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
}

export const budgetApi = new BudgetApiService();