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

export type AdPlacement = 'vendor_rail' | 'vendor_detail' | 'milestone_module' | 'directory_boost';
export type AdEventType = 'impression' | 'click' | 'dismiss' | 'hover' | 'detail_view' | 'contact_click' | 'assignment';

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
// UTILITY FUNCTIONS
// =============================================================================

export function getAdPlacementLabel(placement: AdPlacement): string {
  const labels: Record<AdPlacement, string> = {
    vendor_rail: 'Vendor Rail',
    vendor_detail: 'Vendor Detail',
    milestone_module: 'Milestone Module',
    directory_boost: 'Directory Boost',
  };
  return labels[placement] || placement;
}

export function getEventTypeLabel(eventType: AdEventType): string {
  const labels: Record<AdEventType, string> = {
    impression: 'Impression',
    click: 'Click',
    dismiss: 'Dismiss',
    hover: 'Hover',
    detail_view: 'Detail View',
    contact_click: 'Contact Click',
    assignment: 'Assignment',
  };
  return labels[eventType] || eventType;
}
