/**
 * Vendor Management API Service
 *
 * Handles vendor directory, assignments, dashboard, payment links,
 * import utilities, and shared vendor metadata.
 *
 * Vendor contract-domain helpers live in `vendorContractsApi.ts`.
 */

import { getApiBaseUrl } from '@/utils/env';

const API_BASE = getApiBaseUrl();

/**
 * Extract a human-readable error message from FastAPI error responses.
 * Handles three response shapes:
 * - string detail: "Some error"
 * - structured dict: {error, message, feature} (feature gates)
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
  contract_id?: string;
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
    recent: Array<{
      _id: string;
      id?: string;
      vendor_name: string;
      contract_title: string;
      total_amount: number;
      status: 'draft' | 'pending_review' | 'sent' | 'viewed' | 'signed' | 'active' | 'completed' | 'cancelled' | 'expired';
    }>;
  };
  payments: {
    pending_count: number;
    overdue_count: number;
    total_paid: number;
    total_due: number;
    upcoming: Array<{
      _id: string;
      contract_id?: string;
      wedding_id?: string;
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
    }>;
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
    throw new Error(extractErrorMessage(err, 'Failed to fetch wedding vendors'));
  }

  return response.json();
}

/**
 * Partial update to a vendor assignment. Used by the Budget page to:
 *   - re-link an existing assignment to a different budget category,
 *   - or detach it (pass `budget_category_id: null`).
 *
 * Sending an undefined field leaves it untouched; explicit `null`
 * clears it on the server. This shape mirrors the
 * `UpdateVendorAssignmentRequest` Pydantic body and the backend's
 * `model_dump(exclude_unset=True)` semantics.
 */
export async function updateVendorAssignment(
  token: string,
  assignmentId: string,
  data: {
    budget_category_id?: string | null;
    service_notes?: string | null;
  }
): Promise<VendorAssignment> {
  // Strip undefined keys so they don't get sent as JSON `null` by
  // accident — undefined means "do not touch", null means "clear".
  const body: Record<string, unknown> = {};
  if (Object.prototype.hasOwnProperty.call(data, 'budget_category_id')) {
    body.budget_category_id = data.budget_category_id ?? null;
  }
  if (Object.prototype.hasOwnProperty.call(data, 'service_notes')) {
    body.service_notes = data.service_notes ?? null;
  }

  const response = await fetch(`${API_BASE}/admin/assignments/${assignmentId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to update vendor assignment'));
  }

  return response.json();
}

/**
 * Soft-delete a vendor assignment. The backend sets `is_deleted: true`
 * and stamps `deleted_at`. Used by the Unlinked Vendors panel's
 * "Remove from wedding" action.
 */
export async function deleteVendorAssignment(
  token: string,
  assignmentId: string,
): Promise<void> {
  const response = await fetch(`${API_BASE}/admin/assignments/${assignmentId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to remove vendor assignment'));
  }
}

// =============================================================================
// VENDOR DASHBOARD API
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
// SHARED VENDOR UTILITIES
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
// VENDOR IMPORT (Root Admin Only)
// =============================================================================

export interface VendorImportItem {
  google_place_id?: string;
  business_name: string;
  email?: string;
  phone?: string;
  website?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  service_category: string;
  service_description?: string;
  logo_url?: string;
  typical_price_min?: number;
  typical_price_max?: number;
  currency?: string;
  tags?: string[];
  scraped_from_state?: string;
}

export interface VendorImportResponse {
  inserted: number;
  updated: number;
  skipped: number;
  errors: number;
  error_details: Array<{ index: number; business_name: string; error: string }>;
  total: number;
}

/**
 * Import scraped vendors via JSON.
 * ROOT_ADMIN only — used with the vendor scraper CLI export.
 */
export async function importVendors(
  token: string,
  vendors: VendorImportItem[],
): Promise<VendorImportResponse> {
  const res = await fetch(`${API_BASE}/admin/vendors/import`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    credentials: 'include',
    body: JSON.stringify({ vendors }),
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(errBody, 'Failed to import vendors'));
  }

  return res.json();
}
