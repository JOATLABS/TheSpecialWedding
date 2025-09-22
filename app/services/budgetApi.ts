// Budget API service functions
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
  RecordPaymentRequest
} from '../types/budget';

// Specialized response models
export interface CostEstimateItem {
  category: string;
  estimated_min: number;
  estimated_max: number;
  average?: number;
  notes?: string;
}

export interface CostEstimateResult {
  wedding_type: string;
  guest_count: number;
  location: string;
  currency?: string;
  total_min: number;
  total_max: number;
  items: CostEstimateItem[];
  generated_at?: string;
}

export interface VendorQuoteComparisonEntry {
  quote_id: string;
  vendor_name: string;
  quote_amount: number;
  rating?: number;
  status: string;
  includes_count?: number;
  excludes_count?: number;
}

export interface VendorQuoteComparison {
  category: string;
  wedding_id: string;
  quotes: VendorQuoteComparisonEntry[];
  average_quote?: number;
  min_quote?: number;
  max_quote?: number;
  generated_at?: string;
}

import { buildApiUrl } from '@/utils/api-base';

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
      buildApiUrl(`/admin/weddings/${weddingId}/budget`),
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to fetch budget categories');
    const budgetData = await response.json();
    return budgetData.categories || [];
  }

  async createBudgetCategory(token: string, data: CreateBudgetCategoryRequest): Promise<BudgetCategory> {
    const response = await fetch(
      buildApiUrl(`/admin/weddings/${data.wedding_id}/budget/category`),
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify(data)
      }
    );
    if (!response.ok) throw new Error('Failed to create budget category');
    return response.json();
  }

  async updateBudgetCategory(token: string, categoryId: string, data: UpdateBudgetCategoryRequest): Promise<BudgetCategory> {
    const response = await fetch(
      buildApiUrl(`/admin/budget/category/${categoryId}`),
      {
        method: 'PUT',
        headers: this.getHeaders(token),
        body: JSON.stringify(data)
      }
    );
    if (!response.ok) throw new Error('Failed to update budget category');
    return response.json();
  }

  async deleteBudgetCategory(token: string, categoryId: string): Promise<void> {
    const response = await fetch(
      buildApiUrl(`/admin/budget/categories/${categoryId}`),
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
      buildApiUrl(`/admin/weddings/${weddingId}/budget/summary`),
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to fetch budget summary');
    return response.json();
  }

  // Vendor Quotes
  async getVendorQuotes(token: string, weddingId: string, category?: string): Promise<VendorQuote[]> {
    const url = category 
      ? buildApiUrl(`/admin/weddings/${weddingId}/vendor-quotes?category=${category}`)
      : buildApiUrl(`/admin/weddings/${weddingId}/vendor-quotes`);
    
    const response = await fetch(url, { headers: this.getHeaders(token) });
    if (!response.ok) throw new Error('Failed to fetch vendor quotes');
    return response.json();
  }

  async createVendorQuote(token: string, data: CreateVendorQuoteRequest): Promise<VendorQuote> {
    const response = await fetch(
      buildApiUrl(`/admin/weddings/${data.wedding_id}/vendor-quotes`),
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify(data)
      }
    );
    if (!response.ok) throw new Error('Failed to create vendor quote');
    return response.json();
  }

  async updateVendorQuoteStatus(token: string, quoteId: string, status: string): Promise<VendorQuote> {
    const response = await fetch(
      buildApiUrl(`/admin/vendor-quotes/${quoteId}/status`),
      {
        method: 'PUT',
        headers: this.getHeaders(token),
        body: JSON.stringify({ status })
      }
    );
    if (!response.ok) throw new Error('Failed to update vendor quote status');
    return response.json();
  }

  async rateVendorQuote(token: string, quoteId: string, rating: number, notes?: string): Promise<VendorQuote> {
    const response = await fetch(
      buildApiUrl(`/admin/vendor-quotes/${quoteId}/rating`),
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
      buildApiUrl(`/admin/budget/templates`),
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to fetch budget templates');
    return response.json();
  }

  async applyBudgetTemplate(token: string, weddingId: string, templateId: string, totalBudget: number): Promise<BudgetCategory[]> {
    const response = await fetch(
      buildApiUrl(`/admin/weddings/${weddingId}/budget/apply-template`),
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
  async getCostEstimate(token: string, weddingType: string, guestCount: number, location: string): Promise<CostEstimateResult> {
    const response = await fetch(
      buildApiUrl(`/admin/budget/estimate`),
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify({
          wedding_type: weddingType,
          guest_count: guestCount,
          location: location
        })
      }
    );
    if (!response.ok) throw new Error('Failed to get cost estimate');
    return response.json();
  }

  // Budget Alerts
  async getBudgetAlerts(token: string, weddingId: string): Promise<BudgetAlert[]> {
    const response = await fetch(
      buildApiUrl(`/admin/weddings/${weddingId}/budget/alerts`),
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to fetch budget alerts');
    return response.json();
  }

  async markAlertAsRead(token: string, alertId: string): Promise<void> {
    const response = await fetch(
      buildApiUrl(`/admin/budget/alerts/${alertId}/read`),
      {
        method: 'PUT',
        headers: this.getHeaders(token)
      }
    );
    if (!response.ok) throw new Error('Failed to mark alert as read');
  }

  async resolveAlert(token: string, alertId: string): Promise<void> {
    const response = await fetch(
      buildApiUrl(`/admin/budget/alerts/${alertId}/resolve`),
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
      buildApiUrl(`/admin/weddings/${weddingId}/budget/report?format=${format}`),
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to generate financial report');
    return response.blob();
  }

  // Vendor Quote Comparison
  async compareVendorQuotes(token: string, weddingId: string, category: string): Promise<VendorQuoteComparison> {
    const response = await fetch(
      buildApiUrl(`/admin/weddings/${weddingId}/budget/compare-quotes?category=${category}`),
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to compare vendor quotes');
    return response.json();
  }

  // Payment Tracking
  async recordPayment(token: string, categoryId: string, data: RecordPaymentRequest): Promise<{ message: string; payment: PaymentRecord }> {
    const response = await fetch(
      buildApiUrl(`/admin/budget/category/${categoryId}/payment`),
      {
        method: 'POST',
        headers: this.getHeaders(token),
        body: JSON.stringify(data)
      }
    );
    if (!response.ok) throw new Error('Failed to record payment');
    return response.json();
  }

  async getPaymentHistory(token: string, weddingId: string): Promise<PaymentRecord[]> {
    const response = await fetch(
      buildApiUrl(`/admin/weddings/${weddingId}/payments`),
      { headers: this.getHeaders(token) }
    );
    if (!response.ok) throw new Error('Failed to fetch payment history');
    return response.json();
  }
}

export const budgetApi = new BudgetApiService();