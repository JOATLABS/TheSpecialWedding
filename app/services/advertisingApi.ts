/**
 * Advertising API Service
 *
 * Handles sponsored vendor, feature flag, and ad event tracking operations.
 */

import { getApiBaseUrl } from '@/utils/env';

const API_BASE = getApiBaseUrl();

// =============================================================================
// TYPES
// =============================================================================

export type AdPlacement = 'vendor_rail' | 'vendor_detail' | 'milestone_module' | 'directory_boost' | 'dashboard_rail';
// Matches backend AdEventType enum exactly — no legacy aliases
export type AdEventType = 'impression_served' | 'impression_viewable' | 'click' | 'dismiss' | 'hover' | 'contact_click' | 'vendor_profile_view' | 'vendor_added_to_wedding' | 'lead_created' | 'vendor_invited' | 'lead_accepted' | 'vendor_responded';

export interface SponsoredVendor {
  _id: string;
  vendor_profile_id: string;
  placement: AdPlacement;
  priority: number;
  headline?: string;
  description?: string;
  is_active: boolean;
  start_date?: string;
  end_date?: string;
  target_categories: string[];
  target_wedding_stages: string[];
  created_by: string;
  click_count: number;
  impression_count: number;
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface FeatureFlag {
  _id: string;
  feature_key: string;
  is_enabled: boolean;
  enabled_by?: string;
  enabled_at?: string;
  config: {
    max_sponsored_per_page: number;
    show_sponsored_badge: boolean;
    show_sponsored_label: boolean;
    enable_tracking: boolean;
    min_priority_threshold: number;
    impressions_per_session_limit: number;
  };
}

export interface AdStats {
  sponsored_vendor_id: string;
  vendor_profile_id: string;
  placement: AdPlacement;
  total_impressions: number;
  total_clicks: number;
  ctr: number;
  recent_events_count: number;
  period_days: number;
}

export interface RecordAdEventRequest {
  sponsored_vendor_id: string;
  vendor_profile_id: string;
  event_type: AdEventType;
  placement: AdPlacement;
  user_id?: string;
  metadata?: Record<string, any>;
}

export interface CreateSponsoredVendorRequest {
  vendor_profile_id: string;
  placement: AdPlacement;
  priority: number;
  headline?: string;
  description?: string;
  is_active?: boolean;
  start_date?: string;
  end_date?: string;
  target_categories?: string[];
  target_wedding_stages?: string[];
  metadata?: Record<string, any>;
}

export type LeadStatus = 'pending' | 'contacted' | 'responded' | 'converted' | 'closed';
export type AdLeadType = 'quote_request' | 'message' | 'add_to_wedding' | 'vendor_invite';

export interface AdLead {
  _id: string;
  sponsored_vendor_id: string;
  vendor_profile_id: string;
  planner_id: string;
  wedding_id?: string;
  lead_type: AdLeadType;
  status: LeadStatus;
  click_id?: string;
  placement: AdPlacement;
  message?: string;
  quote_amount?: number;
  responded_at?: string;
  converted_at?: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface CreateAdLeadRequest {
  sponsored_vendor_id: string;
  vendor_profile_id: string;
  wedding_id?: string;
  lead_type: AdLeadType;
  message?: string;
  quote_amount?: number;
  click_id?: string;
  placement?: AdPlacement;
  metadata?: Record<string, any>;
}

export interface UpdateAdLeadStatusRequest {
  status: LeadStatus;
  responded_at?: string;
  converted_at?: string;
}

// Dashboard types (rollup-backed)
export interface DashboardDailySeries {
  date: string;
  impressions: number;
  clicks: number;
  leads: number;
  ctr: number;
  vendor_profile_views: number;
  vendor_added_to_wedding: number;
}

export interface DashboardStats {
  period_days: number;
  totals: {
    impressions: number;
    clicks: number;
    leads: number;
    conversions: number;
    unique_planners: number;
    unique_weddings: number;
    ctr: number;
  };
  leads_by_type: Record<string, number>;
  leads_by_status: Record<string, number>;
  hourly_clicks: number[];
  daily_series: DashboardDailySeries[];
}

export interface VendorLeaderboardEntry {
  sponsored_vendor_id: string;
  vendor_profile_id: string;
  total_impressions: number;
  total_clicks: number;
  total_leads: number;
  total_conversions: number;
  unique_planners: number;
  days_active: number;
  ctr: number;
}

export interface AdPreferences {
  _id: string;
  planner_id: string;
  hidden_vendor_ids: string[];
  hidden_categories: string[];
  reduced_frequency: boolean;
  wedding_overrides: Record<string, {
    hidden_vendor_ids?: string[];
    hidden_categories?: string[];
  }>;
  updated_at: string;
}

// =============================================================================
// FEATURE FLAG API
// =============================================================================

export async function getFeatureFlag(token: string): Promise<FeatureFlag> {
  const response = await fetch(`${API_BASE}/admin/ads/feature-flag`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to fetch feature flag');
  }

  return response.json();
}

export async function toggleFeatureFlag(token: string, isEnabled: boolean): Promise<FeatureFlag> {
  const response = await fetch(`${API_BASE}/admin/ads/feature-flag?is_enabled=${isEnabled}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to update feature flag');
  }

  return response.json();
}

// =============================================================================
// SPONSORED VENDORS API
// =============================================================================

export async function getSponsoredVendors(
  token: string,
  params?: {
    placement?: AdPlacement;
    category?: string;
    wedding_stage?: string;
    limit?: number;
  }
): Promise<SponsoredVendor[]> {
  const queryParams = new URLSearchParams();
  if (params?.placement) queryParams.append('placement', params.placement);
  if (params?.category) queryParams.append('category', params.category);
  if (params?.wedding_stage) queryParams.append('wedding_stage', params.wedding_stage);
  if (params?.limit) queryParams.append('limit', String(params.limit));

  const url = `${API_BASE}/admin/ads/sponsored-vendors?${queryParams.toString()}`;
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to fetch sponsored vendors');
  }

  return response.json();
}

export async function createSponsoredVendor(
  token: string,
  data: CreateSponsoredVendorRequest
): Promise<SponsoredVendor> {
  const response = await fetch(`${API_BASE}/admin/ads/sponsored-vendors`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to create sponsored vendor');
  }

  return response.json();
}

export async function updateSponsoredVendor(
  token: string,
  id: string,
  data: Partial<CreateSponsoredVendorRequest>
): Promise<SponsoredVendor> {
  const response = await fetch(`${API_BASE}/admin/ads/sponsored-vendors/${id}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to update sponsored vendor');
  }

  return response.json();
}

export async function deleteSponsoredVendor(token: string, id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/admin/ads/sponsored-vendors/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to delete sponsored vendor');
  }
}

// =============================================================================
// AD EVENTS API
// =============================================================================

export async function recordAdEvent(
  token: string,
  event: RecordAdEventRequest
): Promise<void> {
  const response = await fetch(`${API_BASE}/admin/ads/events`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(event),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    console.error('Failed to record ad event:', error);
    // Don't throw - silently fail for analytics
  }
}

// =============================================================================
// AD STATS API
// =============================================================================

export async function getAdStats(
  token: string,
  id: string,
  days?: number
): Promise<AdStats> {
  const queryParams = new URLSearchParams();
  if (days) queryParams.append('days', String(days));

  const url = `${API_BASE}/admin/ads/sponsored-vendors/${id}/stats?${queryParams.toString()}`;
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to fetch ad stats');
  }

  return response.json();
}

// =============================================================================
// AD LEADS API
// =============================================================================

export async function createAdLead(
  token: string,
  data: CreateAdLeadRequest
): Promise<AdLead> {
  const response = await fetch(`${API_BASE}/admin/ads/leads`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to create lead');
  }

  return response.json();
}

export async function getAdLeads(
  token: string,
  filters?: {
    status?: LeadStatus;
    vendor_id?: string;
    wedding_id?: string;
    limit?: number;
    offset?: number;
  }
): Promise<AdLead[]> {
  const queryParams = new URLSearchParams();
  if (filters?.status) queryParams.append('status', filters.status);
  if (filters?.vendor_id) queryParams.append('vendor_id', filters.vendor_id);
  if (filters?.wedding_id) queryParams.append('wedding_id', filters.wedding_id);
  if (filters?.limit) queryParams.append('limit', String(filters.limit));
  if (filters?.offset) queryParams.append('skip', String(filters.offset));

  const url = `${API_BASE}/admin/ads/leads?${queryParams.toString()}`;
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to fetch leads');
  }

  return response.json();
}

export async function updateAdLeadStatus(
  token: string,
  leadId: string,
  update: UpdateAdLeadStatusRequest
): Promise<AdLead> {
  const response = await fetch(`${API_BASE}/admin/ads/leads/${leadId}/status`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(update),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to update lead');
  }

  return response.json();
}

// =============================================================================
// AD PREFERENCES API
// =============================================================================

export async function getAdPreferences(token: string): Promise<AdPreferences> {
  const response = await fetch(`${API_BASE}/admin/ads/preferences`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to fetch ad preferences');
  }

  return response.json();
}

export async function hideAdVendor(token: string, vendorId: string): Promise<AdPreferences> {
  const response = await fetch(`${API_BASE}/admin/ads/preferences/hide-vendor?vendor_id=${encodeURIComponent(vendorId)}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to hide vendor');
  }

  return response.json();
}

export async function unhideAdVendor(token: string, vendorId: string): Promise<AdPreferences> {
  const response = await fetch(`${API_BASE}/admin/ads/preferences/unhide-vendor/${encodeURIComponent(vendorId)}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to unhide vendor');
  }

  return response.json();
}

export async function hideAdCategory(token: string, category: string): Promise<AdPreferences> {
  const response = await fetch(`${API_BASE}/admin/ads/preferences/hide-category?category=${encodeURIComponent(category)}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to hide category');
  }

  return response.json();
}

export async function toggleReducedFrequency(token: string, reduced: boolean): Promise<AdPreferences> {
  const response = await fetch(`${API_BASE}/admin/ads/preferences/reduce-frequency?reduce=${reduced}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to update frequency settings');
  }

  return response.json();
}

// =============================================================================
// DASHBOARD API (Rollup-backed)
// =============================================================================

export async function getDashboardStats(
  token: string,
  params?: {
    days?: number;
    sponsored_vendor_id?: string;
    placement?: string;
  }
): Promise<DashboardStats> {
  const queryParams = new URLSearchParams();
  if (params?.days) queryParams.append('days', String(params.days));
  if (params?.sponsored_vendor_id) queryParams.append('sponsored_vendor_id', params.sponsored_vendor_id);
  if (params?.placement) queryParams.append('placement', params.placement);

  const url = `${API_BASE}/admin/ads/dashboard/stats?${queryParams.toString()}`;
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to fetch dashboard stats');
  }

  return response.json();
}

export async function getVendorLeaderboard(
  token: string,
  params?: {
    days?: number;
    limit?: number;
  }
): Promise<VendorLeaderboardEntry[]> {
  const queryParams = new URLSearchParams();
  if (params?.days) queryParams.append('days', String(params.days));
  if (params?.limit) queryParams.append('limit', String(params.limit));

  const url = `${API_BASE}/admin/ads/dashboard/leaderboard?${queryParams.toString()}`;
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to fetch vendor leaderboard');
  }

  return response.json();
}

export async function triggerRollup(
  token: string,
  targetDate?: string
): Promise<{ status: string; documents_upserted: number; target_date: string }> {
  const queryParams = new URLSearchParams();
  if (targetDate) queryParams.append('target_date', targetDate);

  const url = `${API_BASE}/admin/ads/dashboard/rollup?${queryParams.toString()}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to trigger rollup');
  }

  return response.json();
}

export async function backfillRollups(
  token: string,
  daysBack?: number
): Promise<{ status: string; total_documents: number; days_backfilled: number }> {
  const queryParams = new URLSearchParams();
  if (daysBack) queryParams.append('days_back', String(daysBack));

  const url = `${API_BASE}/admin/ads/dashboard/backfill?${queryParams.toString()}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || 'Failed to backfill rollups');
  }

  return response.json();
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

export function getAdPlacementLabel(placement: AdPlacement): string {
  const labels: Record<AdPlacement, string> = {
    vendor_rail: 'Vendor Rail',
    vendor_detail: 'Vendor Detail',
    milestone_module: 'Milestone Module',
    directory_boost: 'Directory Boost',
    dashboard_rail: 'Dashboard Rail',
  };
  return labels[placement] || placement;
}

export function getEventTypeLabel(eventType: AdEventType): string {
  const labels: Record<AdEventType, string> = {
    impression_served: 'Impression Served',
    impression_viewable: 'Impression Viewable',
    click: 'Click',
    dismiss: 'Dismiss',
    hover: 'Hover',
    contact_click: 'Contact Click',
    vendor_profile_view: 'Vendor Profile View',
    vendor_added_to_wedding: 'Vendor Added to Wedding',
    lead_created: 'Lead Created',
    vendor_invited: 'Vendor Invited',
    lead_accepted: 'Lead Accepted',
    vendor_responded: 'Vendor Responded',
  };
  return labels[eventType] || eventType;
}
