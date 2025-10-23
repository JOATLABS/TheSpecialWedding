// Budget system type definitions
export interface BudgetSubcategory {
  id: string;
  name: string;
  budgeted_amount: number;
  actual_spent: number;
  notes?: string;
}

export interface BudgetCategory {
  id: string;
  _id: string;
  wedding_id: string;
  name: string;
  description?: string;
  budgeted_amount: number;
  actual_spent: number;
  payment_status: 'pending' | 'partial' | 'paid' | 'overdue';
  priority: 1 | 2 | 3 | 4 | 5;
  percentage_of_total?: number;
  subcategories: BudgetSubcategory[];
  vendor_quotes: string[];
  payments: PaymentRecord[];
  created_at: string;
  updated_at: string;
}

export interface VendorQuote {
  id: string;
  _id: string;
  wedding_id: string;
  vendor_id?: string;
  vendor_name: string;
  vendor_email?: string;
  vendor_phone?: string;
  service_category: string;
  quote_amount: number;
  quote_details: Record<string, any>;
  includes: string[];
  excludes: string[];
  terms_conditions?: string;
  status: 'pending' | 'accepted' | 'rejected' | 'expired';
  valid_until?: string;
  notes?: string;
  rating?: number;
  created_at: string;
  updated_at: string;
}

export interface BudgetTemplate {
  id: string;
  _id: string;
  name: string;
  description?: string;
  wedding_type: string;
  target_budget_min: number;
  target_budget_max: number;
  guest_count_range: { min: number; max: number };
  categories: Array<{
    name: string;
    percentage: number;
    priority: number;
  }>;
  created_by?: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface BudgetTemplateCategoryInput {
  name: string;
  percentage: number;
  priority: number;
}

export interface CreateBudgetTemplatePayload {
  name: string;
  description?: string;
  wedding_type: string;
  target_budget_min: number;
  target_budget_max: number;
  guest_count_range: { min: number; max: number };
  categories: BudgetTemplateCategoryInput[];
  is_public?: boolean;
}

export interface BudgetSummary {
  wedding_id: string;
  total_budget: number;
  total_spent: number;
  total_committed: number;
  remaining_budget: number;
  budget_variance: number;
  variance_percentage: number;
  categories_count: number;
  paid_categories: number;
  overdue_categories: number;
  vendor_quotes_count: number;
  last_updated: string;
}

export interface PaymentRecord {
  id: string;
  category_id: string;
  vendor_name?: string;
  amount: number;
  payment_method: 'cash' | 'check' | 'card' | 'transfer';
  payment_date: string;
  description?: string;
  receipt_url?: string;
  status: 'pending' | 'completed' | 'failed';
  notes?: string;
  created_at: string;
  category_name?: string;
}

export interface RecordPaymentRequest {
  vendor_name?: string;
  amount: number;
  payment_method: 'cash' | 'check' | 'card' | 'transfer';
  payment_date: string;
  description?: string;
  receipt_url?: string;
  status?: 'pending' | 'completed' | 'failed';
  notes?: string;
}

export interface BudgetAlert {
  id: string;
  wedding_id: string;
  category_id?: string;
  alert_type: 'over_budget' | 'payment_due' | 'quote_expired';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  amount?: number;
  threshold?: number;
  is_read: boolean;
  is_resolved: boolean;
  created_at: string;
  resolved_at?: string;
}

// Form interfaces for creating/updating
export interface CreateBudgetCategoryRequest {
  wedding_id: string;
  name: string;
  description?: string;
  budgeted_amount: number;
  priority?: number;
  percentage_of_total?: number;
}

export interface UpdateBudgetCategoryRequest {
  name?: string;
  description?: string;
  budgeted_amount?: number;
  actual_spent?: number;
  payment_status?: 'pending' | 'partial' | 'paid' | 'overdue';
  priority?: number;
  percentage_of_total?: number;
}

export interface CreateVendorQuoteRequest {
  wedding_id: string;
  vendor_name: string;
  vendor_email?: string;
  vendor_phone?: string;
  service_category: string;
  quote_amount: number;
  quote_details?: Record<string, any>;
  includes?: string[];
  excludes?: string[];
  terms_conditions?: string;
  valid_until?: string;
  notes?: string;
}