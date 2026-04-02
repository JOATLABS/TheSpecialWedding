/**
 * Vendor Management API Service
 *
 * Handles all vendor directory, contracts, and payments operations.
 */

import { getApiBaseUrl } from '@/utils/env';

const API_BASE = getApiBaseUrl();

/**
 * Extract a human-readable error message from FastAPI error responses.
 * Handles three response shapes:
 * - string detail: "Some error"
 * - structured dict: {error, message, feature}  (feature gates)
 * - Pydantic validation array: [{type, msg, loc}] (422 errors)
 */
function extractErrorMessage(errBody: any, fallback: string): string {
  const detail = errBody?.detail;
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (typeof detail === 'object' && !Array.isArray(detail) && detail.message) return detail.message;
  if (Array.isArray(detail) && detail.length > 0 && detail[0].msg) {
    return detail.map((d: any) => d.msg).join('; ');
  }
  return fallback;
}

// =============================================================================
// TYPES
// =============================================================================

export type VendorCategory =
  | 'photographer'
  | 'videographer'
  | 'florist'
  | 'caterer'
  | 'venue'
  | 'dj'
  | 'mc'
  | 'band'
  | 'officiant'
  | 'planner'
  | 'decorator'
  | 'cake'
  | 'hair_makeup'
  | 'transportation'
  | 'stationery'
  | 'rentals'
  | 'lighting'
  | 'photo_booth'
  | 'jewelry'
  | 'attire'
  | 'other';

export interface VendorProfile {
  _id: string;
  business_name: string;
  contact_name?: string;
  email: string;
  phone?: string;
  website?: string;
  logo_url?: string;
  address?: string;
  city?: string;
  state?: string;
  service_category: VendorCategory;
  custom_service_category?: string;
  service_subcategories: string[];
  service_description?: string;
  internal_notes?: string;
  internal_rating?: number;
  is_preferred: boolean;
  tags: string[];
  portfolio_urls: string[];
  typical_price_min?: number;
  typical_price_max?: number;
  currency: string;
  weddings_count: number;
  total_revenue: number;
  is_active: boolean;
  service_radius?: number;
  country?: string;
  postal_code?: string;
  created_at: string;
  updated_at: string;
}

export interface ContractTemplate {
  _id: string;
  name: string;
  description?: string;
  service_category: VendorCategory;
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  placeholders: Placeholder[];
  default_deposit_percentage?: number;
  default_payment_schedule: PaymentScheduleItem[];
  is_system_template: boolean;
  is_public: boolean;
  usage_count: number;
}

export interface ContractSection {
  id: string;
  title: string;
  content: string;
  order: number;
}

export interface Placeholder {
  key: string;
  label: string;
  source: string;
  field_path?: string;
}

export interface PaymentScheduleItem {
  percentage: number;
  description: string;
  days_before_event?: number;
}

export interface VendorContract {
  _id: string;
  id?: string;  // Backend returns both; prefer `id` in new code
  wedding_id: string;
  vendor_profile_id?: string;
  vendor_name: string;
  vendor_email: string;
  vendor_phone?: string;
  service_category: VendorCategory;
  custom_service_category?: string;
  contract_title: string;
  contract_number?: string;
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  total_amount: number;
  currency: string;
  deposit_amount?: number;
  deposit_due_date?: string;
  status: ContractStatus;
  sent_at?: string;
  viewed_at?: string;
  signed_at?: string;
  signed_by_name?: string;
  service_date?: string;
  service_location?: string;
  created_at: string;
  updated_at: string;
}

export type ContractStatus =
  | 'draft'
  | 'pending_review'
  | 'sent'
  | 'viewed'
  | 'signed'
  | 'active'
  | 'completed'
  | 'cancelled'
  | 'expired';

export interface PaymentMilestone {
  _id: string;
  contract_id: string;
  wedding_id: string;
  description: string;
  amount: number;
  currency: string;
  due_date: string;
  status: 'pending' | 'due' | 'overdue' | 'paid' | 'partial';
  paid_amount: number;
  paid_at?: string;
  payment_method?: string;
  vendor_name: string;
  vendor_email: string;
}

export interface VendorAssignment {
  _id: string;
  wedding_id: string;
  vendor_profile_id: string;
  budget_category_id?: string;
  status: 'inquiry' | 'quoted' | 'contracted' | 'confirmed' | 'completed' | 'cancelled';
  vendor_name: string;
  vendor_email: string;
  service_category: VendorCategory;
  custom_service_category?: string;
  quoted_amount?: number;
  contracted_amount?: number;
  paid_amount: number;
}

export interface VendorDashboard {
  vendors: {
    total: number;
    preferred: number;
  };
  contracts: {
    total: number;
    pending: number;
    signed: number;
    recent: VendorContract[];
  };
  payments: {
    pending_count: number;
    overdue_count: number;
    total_paid: number;
    total_due: number;
    upcoming: PaymentMilestone[];
  };
}

// =============================================================================
// VENDOR DIRECTORY API
// =============================================================================

export async function getVendorDirectory(
  token: string,
  params?: {
    category?: string;
    is_preferred?: boolean;
    search?: string;
    tags?: string;
    skip?: number;
    limit?: number;
  }
): Promise<VendorProfile[]> {
  const queryParams = new URLSearchParams();
  if (params?.category) queryParams.append('category', params.category);
  if (params?.is_preferred !== undefined) queryParams.append('is_preferred', String(params.is_preferred));
  if (params?.search) queryParams.append('search', params.search);
  if (params?.tags) queryParams.append('tags', params.tags);
  if (params?.skip) queryParams.append('skip', String(params.skip));
  if (params?.limit) queryParams.append('limit', String(params.limit));

  const url = `${API_BASE}/admin/directory?${queryParams.toString()}`;
  let response: Response;
  try {
    response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error('Vendor directory is not available. The backend endpoint may not be set up yet.');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to fetch vendors'));
  }

  return response.json();
}

export async function createVendorProfile(
  token: string,
  data: Partial<VendorProfile>
): Promise<VendorProfile> {
  const response = await fetch(`${API_BASE}/admin/directory`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to create vendor'));
  }

  return response.json();
}

export async function updateVendorProfile(
  token: string,
  vendorId: string,
  data: Partial<VendorProfile>
): Promise<VendorProfile> {
  const response = await fetch(`${API_BASE}/admin/directory/${vendorId}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to update vendor'));
  }

  return response.json();
}

export async function deleteVendorProfile(token: string, vendorId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/admin/directory/${vendorId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to delete vendor'));
  }
}

export async function getVendorCategories(token: string): Promise<string[]> {
  const response = await fetch(`${API_BASE}/admin/directory/all-categories`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    console.error('Failed to fetch vendor categories:', err);
    throw new Error(extractErrorMessage(err, 'Failed to fetch vendor categories'));
  }
  const data = await response.json();
  return data.categories || [];
}

// =============================================================================
// VENDOR ASSIGNMENTS API
// =============================================================================

export async function assignVendorToWedding(
  token: string,
  data: {
    vendor_profile_id: string;
    wedding_id: string;
    budget_category_id?: string;
    service_notes?: string;
  }
): Promise<VendorAssignment> {
  const response = await fetch(`${API_BASE}/admin/assign`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to assign vendor'));
  }

  return response.json();
}

export async function getWeddingVendors(token: string, weddingId: string): Promise<VendorAssignment[]> {
  const response = await fetch(`${API_BASE}/admin/weddings/${weddingId}/vendors`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    console.error('Failed to fetch wedding vendors:', err);
    throw new Error(extractErrorMessage(err, 'Failed to fetch wedding vendors'));
  }
  return response.json();
}

// =============================================================================
// CONTRACT TEMPLATES API
// =============================================================================

export async function getContractTemplates(
  token: string,
  category?: string
): Promise<ContractTemplate[]> {
  const url = category
    ? `${API_BASE}/admin/templates?category=${category}`
    : `${API_BASE}/admin/templates`;

  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    console.error('Failed to fetch contract templates:', err);
    throw new Error(extractErrorMessage(err, 'Failed to fetch contract templates'));
  }
  return response.json();
}

export async function getContractTemplate(token: string, templateId: string): Promise<ContractTemplate> {
  const response = await fetch(`${API_BASE}/admin/templates/${templateId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error('Failed to fetch template');
  }

  return response.json();
}

// =============================================================================
// CONTRACTS API
// =============================================================================

export async function createContract(
  token: string,
  data: {
    wedding_id: string;
    vendor_profile_id: string;
    total_amount: number;
    template_id?: string;
    quote_id?: string;
    deposit_percentage?: number;
    service_date?: string;
    service_location?: string;
    custom_sections?: ContractSection[];
  }
): Promise<VendorContract> {
  const params = new URLSearchParams();
  params.append('wedding_id', data.wedding_id);
  params.append('vendor_profile_id', data.vendor_profile_id);
  params.append('total_amount', String(data.total_amount));
  if (data.template_id) params.append('template_id', data.template_id);
  if (data.quote_id) params.append('quote_id', data.quote_id);
  if (data.deposit_percentage) params.append('deposit_percentage', String(data.deposit_percentage));
  if (data.service_date) params.append('service_date', data.service_date);
  if (data.service_location) params.append('service_location', data.service_location);

  const response = await fetch(`${API_BASE}/admin/contracts?${params.toString()}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: data.custom_sections ? JSON.stringify(data.custom_sections) : undefined,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to create contract'));
  }

  return response.json();
}

export async function getContracts(
  token: string,
  params?: {
    wedding_id?: string;
    vendor_profile_id?: string;
    status?: ContractStatus;
  }
): Promise<VendorContract[]> {
  const queryParams = new URLSearchParams();
  if (params?.wedding_id) queryParams.append('wedding_id', params.wedding_id);
  if (params?.vendor_profile_id) queryParams.append('vendor_profile_id', params.vendor_profile_id);
  if (params?.status) queryParams.append('status', params.status);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/admin/contracts?${queryParams.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error('Contracts endpoint is not available. The backend endpoint may not be set up yet.');
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(err, 'Failed to fetch contracts'));
  }
  return response.json();
}

export async function getContract(token: string, contractId: string): Promise<VendorContract> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error('Failed to fetch contract');
  }

  return response.json();
}

export async function updateContract(
  token: string,
  contractId: string,
  data: Partial<VendorContract>
): Promise<VendorContract> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to update contract'));
  }

  return response.json();
}

export async function sendContract(
  token: string,
  contractId: string,
  message?: string
): Promise<{ message: string; sent_to: string }> {
  const params = new URLSearchParams();
  if (message) params.append('message', message);

  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/send?${params.toString()}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to send contract'));
  }

  return response.json();
}

export async function getFormDataForContract(
  token: string,
  contractId: string
): Promise<{
  submissions: Array<{ _id: string; submission_data: Record<string, unknown> }>;
  available_fields: Record<string, { value: unknown; source_id: string }>;
  suggested_mappings: Record<string, string>;
}> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/form-data`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    return { submissions: [], available_fields: {}, suggested_mappings: {} };
  }

  return response.json();
}

// =============================================================================
// PAYMENT MILESTONES API
// =============================================================================

export async function createPaymentMilestones(
  token: string,
  contractId: string,
  milestones: Array<{
    description: string;
    amount: number;
    due_date: string;
    percentage_of_total?: number;
  }>
): Promise<PaymentMilestone[]> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/milestones`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(milestones),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to create milestones'));
  }

  return response.json();
}

export async function getPaymentMilestones(
  token: string,
  params?: {
    contract_id?: string;
    wedding_id?: string;
    status?: string;
  }
): Promise<PaymentMilestone[]> {
  const queryParams = new URLSearchParams();
  if (params?.contract_id) queryParams.append('contract_id', params.contract_id);
  if (params?.wedding_id) queryParams.append('wedding_id', params.wedding_id);
  if (params?.status) queryParams.append('status', params.status);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/admin/milestones?${queryParams.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error('Payment milestones endpoint is not available. The backend endpoint may not be set up yet.');
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(err, 'Failed to fetch payment milestones'));
  }
  return response.json();
}

export async function recordPayment(
  token: string,
  milestoneId: string,
  data: {
    amount: number;
    payment_method: string;
    payment_date?: string;
    notes?: string;
  }
): Promise<PaymentMilestone> {
  const params = new URLSearchParams();
  params.append('amount', String(data.amount));
  params.append('payment_method', data.payment_method);
  if (data.payment_date) params.append('payment_date', data.payment_date);
  if (data.notes) params.append('notes', data.notes);

  const response = await fetch(`${API_BASE}/admin/milestones/${milestoneId}/pay?${params.toString()}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to record payment'));
  }

  return response.json();
}

// =============================================================================
// DASHBOARD API
// =============================================================================

export async function getVendorDashboard(
  token: string,
  weddingId?: string
): Promise<VendorDashboard> {
  const url = weddingId
    ? `${API_BASE}/admin/dashboard?wedding_id=${weddingId}`
    : `${API_BASE}/admin/dashboard`;

  let response: Response;
  try {
    response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error('Vendor dashboard is not available. The backend endpoint may not be set up yet.');
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const detail = err.detail;
    const message = typeof detail === 'string'
      ? detail
      : detail?.message || 'Failed to fetch vendor dashboard';
    throw new Error(message);
  }

  return response.json();
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

export const VENDOR_CATEGORIES: { value: VendorCategory; label: string }[] = [
  { value: 'photographer', label: 'Photographer' },
  { value: 'videographer', label: 'Videographer' },
  { value: 'florist', label: 'Florist' },
  { value: 'caterer', label: 'Caterer' },
  { value: 'venue', label: 'Venue' },
  { value: 'dj', label: 'DJ' },
  { value: 'mc', label: 'MC / Host' },
  { value: 'band', label: 'Band/Musicians' },
  { value: 'officiant', label: 'Officiant' },
  { value: 'planner', label: 'Wedding Planner' },
  { value: 'decorator', label: 'Decorator' },
  { value: 'cake', label: 'Cake/Bakery' },
  { value: 'hair_makeup', label: 'Hair & Makeup' },
  { value: 'transportation', label: 'Transportation' },
  { value: 'stationery', label: 'Stationery' },
  { value: 'rentals', label: 'Rentals' },
  { value: 'lighting', label: 'Lighting' },
  { value: 'photo_booth', label: 'Photo Booth' },
  { value: 'jewelry', label: 'Jewelry' },
  { value: 'attire', label: 'Attire' },
  { value: 'other', label: 'Other' },
];

export function getCategoryLabel(category: VendorCategory, customServiceCategory?: string): string {
  if (category === 'other' && customServiceCategory?.trim()) {
    return customServiceCategory.trim();
  }

  return VENDOR_CATEGORIES.find((c) => c.value === category)?.label || category;
}

export function getContractStatusColor(status: ContractStatus): string {
  const colors: Record<ContractStatus, string> = {
    draft: 'bg-gray-100 text-gray-800',
    pending_review: 'bg-yellow-100 text-yellow-800',
    sent: 'bg-blue-100 text-blue-800',
    viewed: 'bg-indigo-100 text-indigo-800',
    signed: 'bg-green-100 text-green-800',
    active: 'bg-teal-100 text-teal-800',
    completed: 'bg-emerald-100 text-emerald-800',
    cancelled: 'bg-red-100 text-red-800',
    expired: 'bg-orange-100 text-orange-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

export function getPaymentStatusColor(status: PaymentMilestone['status']): string {
  const colors = {
    pending: 'bg-gray-100 text-gray-800',
    due: 'bg-yellow-100 text-yellow-800',
    overdue: 'bg-red-100 text-red-800',
    paid: 'bg-green-100 text-green-800',
    partial: 'bg-blue-100 text-blue-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

// =============================================================================
// PAYMENT LINKS
// =============================================================================

export type PayerType = 'couple' | 'vendor' | 'planner';
export type RecipientType = 'vendor' | 'planner' | 'couple';
export type PaymentLinkStatus = 'draft' | 'sent' | 'clicked' | 'paid' | 'expired' | 'cancelled';

export interface PaymentLink {
  _id: string;
  wedding_id?: string;
  contract_id?: string;
  milestone_id?: string;
  vendor_profile_id?: string;
  payer_type: PayerType;
  payer_email: string;
  payer_name: string;
  payer_phone?: string;
  recipient_type: RecipientType;
  recipient_email: string;
  recipient_name: string;
  amount: number;
  currency: string;
  description: string;
  due_date?: string;
  stripe_payment_link_url?: string;
  status: PaymentLinkStatus;
  sent_at?: string;
  paid_at?: string;
  created_at: string;
}

export interface CreatePaymentLinkRequest {
  payer_type: PayerType;
  payer_email: string;
  payer_name: string;
  payer_phone?: string;
  recipient_type: RecipientType;
  recipient_email: string;
  recipient_name: string;
  amount: number;
  currency?: string;
  description: string;
  due_date?: string;
  wedding_id?: string;
  contract_id?: string;
  milestone_id?: string;
  vendor_profile_id?: string;
  email_subject?: string;
  email_message?: string;
}

export async function createPaymentLink(
  token: string,
  data: CreatePaymentLinkRequest
): Promise<PaymentLink> {
  const response = await fetch(`${API_BASE}/admin/payment-links`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to create payment link'));
  }

  return response.json();
}

export async function sendPaymentLink(
  token: string,
  paymentLinkId: string,
  customMessage?: string
): Promise<{ message: string; sent_to: string }> {
  const params = new URLSearchParams();
  if (customMessage) params.append('custom_message', customMessage);

  const response = await fetch(
    `${API_BASE}/admin/payment-links/${paymentLinkId}/send?${params.toString()}`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to send payment link'));
  }

  return response.json();
}

export async function getPaymentLinks(
  token: string,
  params?: {
    wedding_id?: string;
    status?: PaymentLinkStatus;
    skip?: number;
    limit?: number;
  }
): Promise<PaymentLink[]> {
  const queryParams = new URLSearchParams();
  if (params?.wedding_id) queryParams.append('wedding_id', params.wedding_id);
  if (params?.status) queryParams.append('status', params.status);
  if (params?.skip) queryParams.append('skip', String(params.skip));
  if (params?.limit) queryParams.append('limit', String(params.limit));

  const response = await fetch(`${API_BASE}/admin/payment-links?${queryParams.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(err, 'Failed to fetch payment links'));
  }
  return response.json();
}

// =============================================================================
// PDF CONTRACT UPLOAD
// =============================================================================

export async function uploadContractPdf(
  token: string,
  file: File,
  data: {
    wedding_id: string;
    vendor_profile_id: string;
    contract_title: string;
    total_amount: number;
    deposit_amount?: number;
    service_date?: string;
    service_location?: string;
    notes?: string;
  }
): Promise<VendorContract> {
  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams();
  params.append('wedding_id', data.wedding_id);
  params.append('vendor_profile_id', data.vendor_profile_id);
  params.append('contract_title', data.contract_title);
  params.append('total_amount', String(data.total_amount));
  if (data.deposit_amount) params.append('deposit_amount', String(data.deposit_amount));
  if (data.service_date) params.append('service_date', data.service_date);
  if (data.service_location) params.append('service_location', data.service_location);
  if (data.notes) params.append('notes', data.notes);

  const response = await fetch(`${API_BASE}/admin/contracts/upload-pdf?${params.toString()}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to upload contract PDF'));
  }

  return response.json();
}

// =============================================================================
// FORM DATA FOR CONTRACTS
// =============================================================================

export interface FormDataForContract {
  vendor_submissions: Array<{
    _id: string;
    form_name: string;
    submitted_at?: string;
    data: Record<string, unknown>;
  }>;
  available_fields: Record<string, {
    value: unknown;
    source: string;
    source_id: string;
    original_key: string;
  }>;
  suggested_contract_fields: Record<string, {
    value: unknown;
    source_field: string;
  }>;
}

export async function getContractFormData(
  token: string,
  contractId: string
): Promise<FormDataForContract> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/form-data`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    return { vendor_submissions: [], available_fields: {}, suggested_contract_fields: {} };
  }

  return response.json();
}

export async function applyFormDataToContract(
  token: string,
  contractId: string,
  formDataMappings: Record<string, { value: unknown } | string>
): Promise<VendorContract> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/apply-form-data`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(formDataMappings),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to apply form data'));
  }

  return response.json();
}

// =============================================================================
// CONTRACT SECTION EDITING
// =============================================================================

export async function updateContractSections(
  token: string,
  contractId: string,
  data: {
    sections: ContractSection[];
    terms_and_conditions?: string;
    cancellation_policy?: string;
    custom_clauses?: string;
  }
): Promise<VendorContract> {
  const response = await fetch(`${API_BASE}/admin/contracts/${contractId}/sections`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to update contract sections'));
  }

  return response.json();
}

// =============================================================================
// UTILITY: Payment Link Status Colors
// =============================================================================

export function getPaymentLinkStatusColor(status: PaymentLinkStatus): string {
  const colors: Record<PaymentLinkStatus, string> = {
    draft: 'bg-gray-100 text-gray-800',
    sent: 'bg-blue-100 text-blue-800',
    clicked: 'bg-indigo-100 text-indigo-800',
    paid: 'bg-green-100 text-green-800',
    expired: 'bg-orange-100 text-orange-800',
    cancelled: 'bg-red-100 text-red-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

// =============================================================================
// PUBLIC CONTRACT ACCESS (No Auth Required)
// =============================================================================

export interface PublicContract {
  _id: string;
  id?: string;
  contract_title: string;
  contract_number?: string;
  vendor_name: string;
  vendor_email: string;
  planner_name?: string;
  planner_company?: string;
  couple_names?: string;
  wedding_date?: string;
  service_date?: string;
  service_location?: string;
  service_category: VendorCategory;
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  total_amount: number;
  deposit_amount?: number;
  currency: string;
  status: ContractStatus;
  sent_at?: string;
  viewed_at?: string;
  signed_at?: string;
  signed_by_name?: string;
}

export async function getPublicContract(
  contractId: string,
  accessToken: string
): Promise<PublicContract> {
  const response = await fetch(
    `${API_BASE}/vendor-contract/public/contracts/${contractId}/${encodeURIComponent(accessToken)}`
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Contract not found');
    } else if (response.status === 403) {
      throw new Error('Access denied - invalid or expired link');
    }
    throw new Error('Failed to fetch contract');
  }

  return response.json();
}

export async function signPublicContract(
  contractId: string,
  accessToken: string,
  signerName: string,
  signerEmail: string
): Promise<{ message: string; signed_at: string }> {
  const response = await fetch(
    `${API_BASE}/vendor-contract/public/contracts/${contractId}/${encodeURIComponent(accessToken)}/sign`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        signer_name: signerName,
        signer_email: signerEmail,
      }),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to sign contract'));
  }

  return response.json();
}

// =============================================================================
// CONTRACT TEMPLATES - Create Custom
// =============================================================================

export interface CreateTemplateRequest {
  name: string;
  description?: string;
  service_category: VendorCategory;
  sections: ContractSection[];
  terms_and_conditions?: string;
  cancellation_policy?: string;
  default_deposit_percentage?: number;
  default_payment_schedule?: PaymentScheduleItem[];
  is_public?: boolean;
}

export async function createContractTemplate(
  token: string,
  data: CreateTemplateRequest
): Promise<ContractTemplate> {
  const response = await fetch(`${API_BASE}/admin/templates`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to create template'));
  }

  return response.json();
}

export async function saveContractAsTemplate(
  token: string,
  contractId: string,
  templateName: string,
  description?: string
): Promise<ContractTemplate> {
  // First get the contract
  const contract = await getContract(token, contractId);

  // Create template from contract
  return createContractTemplate(token, {
    name: templateName,
    description: description || `Template created from ${contract.contract_title}`,
    service_category: contract.service_category,
    sections: contract.sections,
    terms_and_conditions: contract.terms_and_conditions,
    cancellation_policy: contract.cancellation_policy,
    is_public: false,
  });
}
