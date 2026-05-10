/**
 * Campaign Advertising API Service
 *
 * New API client for the campaign-based advertising platform.
 * Covers all three portals: Vendor Portal, Admin Console, and Planner interactions.
 *
 * This replaces the OLD advertisingApi.ts (which talked to sponsored_vendors endpoints).
 */

import { getApiBaseUrl } from '@/utils/env';
import { redirectOnBillingBlock } from '@/utils/adminApiAuthGuard';

const API_BASE = getApiBaseUrl();

// =============================================================================
// ENUMS
// =============================================================================

export type CampaignGoal = 'profile_visits' | 'quote_requests' | 'bookings';
export type CampaignStatus = 'draft' | 'pending_review' | 'active' | 'paused' | 'completed' | 'rejected';
export type CreativeReviewStatus = 'pending' | 'approved' | 'rejected' | 'changes_requested';
export type CreativeType = 'image' | 'text';
export type PacingStrategy = 'even' | 'accelerated';
export type BidStrategy = 'fixed' | 'auto';
export type FraudSignalType = 'unusual_traffic' | 'duplicate_click' | 'bot_pattern' | 'geographic_anomaly' | 'rapid_clicks';
export type FraudSignalStatus = 'pending' | 'investigated' | 'false_alarm' | 'confirmed_fraud';
export type VendorAccountStatus = 'pending_approval' | 'active' | 'suspended' | 'inactive';
export type VendorMediaAssetKind = 'creative' | 'vendor_logo';

// =============================================================================
// TYPES — Campaign Models
// =============================================================================

export interface AdCampaign {
  _id: string;
  vendor_id: string;
  vendor_email: string;
  vendor_name: string;
  campaign_name: string;
  campaign_description?: string;
  goal: CampaignGoal;
  status: CampaignStatus;
  target_categories: string[];
  target_wedding_stages: string[];
  target_placements: string[];
  target_regions: string[];
  target_budget_min?: number;
  target_budget_max?: number;
  daily_budget: number;
  total_budget: number;
  budget_consumed: number;
  pacing_strategy: PacingStrategy;
  start_date?: string;
  end_date?: string;
  bid_amount: number;
  bid_strategy: BidStrategy;
  quality_score: number;
  impression_count: number;
  click_count: number;
  lead_count: number;
  conversion_count: number;
  primary_creative_id?: string;
  creative_ids: string[];
  submitted_at?: string;
  reviewed_at?: string;
  reviewed_by?: string;
  review_notes?: string;
  is_free_tier?: boolean;
  vendor_category?: string;
  vendor_service_area?: string;
  vendor_logo_url?: string;
  created_by: string;
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AdCreative {
  _id: string;
  campaign_id: string;
  vendor_id: string;
  creative_type: CreativeType;
  image_url?: string;
  image_alt_text?: string;
  headline: string;
  description: string;
  offer?: string;
  call_to_action: string;
  review_status: CreativeReviewStatus;
  submitted_at?: string;
  reviewed_at?: string;
  reviewed_by?: string;
  review_notes?: string;
  is_primary: boolean;
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface CampaignDayStats {
  _id: string;
  date: string;
  campaign_id: string;
  vendor_id: string;
  events: Record<string, number>;
  leads_by_type: Record<string, number>;
  leads_by_status: Record<string, number>;
  unique_planners: number;
  unique_weddings: number;
  hourly_impressions: number[];
  hourly_clicks: number[];
  ctr: number;
  conversion_rate: number;
  spend: number;
  created_at: string;
  updated_at: string;
}

export interface AdFraudSignal {
  _id: string;
  signal_type: FraudSignalType;
  campaign_id?: string;
  vendor_id?: string;
  planner_id?: string;
  session_id?: string;
  click_velocity?: number;
  details: Record<string, any>;
  status: FraudSignalStatus;
  flagged_at: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface VendorAdBilling {
  _id: string;
  vendor_id: string;
  campaign_id: string;
  billing_period_start: string;
  billing_period_end: string;
  impressions: number;
  clicks: number;
  leads: number;
  conversions: number;
  total_spend: number;
  currency: string;
  payment_status: string;
  stripe_invoice_id?: string;
  created_at: string;
  updated_at: string;
}

// =============================================================================
// TYPES — Request Models
// =============================================================================

export interface CreateCampaignRequest {
  campaign_name: string;
  campaign_description?: string;
  goal?: CampaignGoal;
  target_categories?: string[];
  target_wedding_stages?: string[];
  target_placements?: string[];
  target_regions?: string[];
  target_budget_min?: number;
  target_budget_max?: number;
  daily_budget?: number;
  total_budget?: number;
  pacing_strategy?: PacingStrategy;
  start_date?: string;
  end_date?: string;
  vendor_category?: string;
  vendor_service_area?: string;
  metadata?: Record<string, any>;
}

export interface UpdateCampaignRequest {
  campaign_name?: string;
  campaign_description?: string;
  goal?: CampaignGoal;
  target_categories?: string[];
  target_wedding_stages?: string[];
  target_placements?: string[];
  target_regions?: string[];
  target_budget_min?: number;
  target_budget_max?: number;
  daily_budget?: number;
  total_budget?: number;
  pacing_strategy?: PacingStrategy;
  start_date?: string;
  end_date?: string;
  vendor_category?: string;
  vendor_service_area?: string;
  metadata?: Record<string, any>;
}

export interface CreateCreativeRequest {
  creative_type?: CreativeType;
  image_url?: string | null;
  image_alt_text?: string | null;
  headline: string;
  description: string;
  offer?: string;
  call_to_action?: string;
  is_primary?: boolean;
  metadata?: Record<string, any>;
}

export interface VendorMediaUploadRequest {
  filename: string;
  content_type: string;
  asset_kind: VendorMediaAssetKind;
  replace_url?: string | null;
}

export interface VendorMediaUploadResponse {
  upload_url: string;
  key: string;
  cdn_url: string;
  asset_kind: VendorMediaAssetKind;
  max_size_bytes: number;
  allowed_content_types: string[];
  replaced_asset?: {
    key: string;
    cdn_url: string;
    asset_kind: VendorMediaAssetKind;
  };
}

export interface ReviewDecisionRequest {
  review_notes?: string;
}

export interface WeddingContext {
  date?: string;
  location?: string;
  guest_count?: number;
  venue?: string;
  budget_range?: string;
}

export interface AddToDirectoryRequest {
  campaign_id: string;
  click_id?: string;
}

export interface RequestQuoteRequest {
  campaign_id: string;
  message: string;
  wedding_id?: string;
  wedding_context?: WeddingContext;
  click_id?: string;
  auto_add_to_directory?: boolean;
}

// =============================================================================
// TYPES — Response Models
// =============================================================================

export interface ReviewCounts {
  pending_review: number;
  active: number;
  paused: number;
  rejected: number;
  draft: number;
  completed: number;
  total: number;
}

export interface SponsoredCard {
  campaign_id: string;
  vendor_id: string;
  vendor_name: string;
  vendor_email: string;
  vendor_category?: string;
  vendor_service_area?: string;
  vendor_logo_url?: string;
  headline: string;
  description: string;
  offer?: string;
  call_to_action: string;
  image_url?: string;
  image_alt_text?: string;
  creative_id?: string;
  goal: CampaignGoal;
  placement_match?: string;
  quality_score: number;
  targeting_reason?: string;
  // Auction metadata (populated when auction engine is active)
  adrank?: number;
  position?: number;
  effective_cost?: number;
  estimated_action_rate?: number;
}

export interface SponsoredCardsResponse {
  cards: SponsoredCard[];
  count: number;
}

export interface DirectoryStatusResponse {
  in_directory: boolean;
  vendor_profile_id?: string;
  added_at?: string;
  campaign_id: string;
}

export interface CampaignStatsResponse {
  campaign_id: string;
  period_days: number;
  totals: {
    impressions: number;
    clicks: number;
    leads: number;
    conversions: number;
    ctr: number;
    conversion_rate: number;
    spend: number;
  };
  daily_series: CampaignDayStats[];
}

export interface RevenueResponse {
  period_days: number;
  total_revenue: number;
  total_impressions: number;
  total_clicks: number;
  total_leads: number;
  total_conversions: number;
  active_campaigns: number;
  active_vendors: number;
  avg_ctr: number;
  daily_series: Array<{
    date: string;
    revenue: number;
    impressions: number;
    clicks: number;
    leads: number;
  }>;
}

export interface BillingSummaryResponse {
  vendor_id: string;
  total_spend: number;
  current_period_spend: number;
  campaigns_count: number;
  billing_records: VendorAdBilling[];
  free_tier: boolean;
}

export interface VendorAccountSummary {
  vendor_id: string;
  vendor_email: string;
  vendor_name: string;
  status: VendorAccountStatus;
  is_free_tier?: boolean;
  campaigns_count: number;
  active_campaigns: number;
  total_impressions: number;
  total_clicks: number;
  total_leads: number;
  joined_at: string;
}

interface RawVendorAccountSummary {
  _id?: string;
  vendor_id?: string;
  email?: string;
  vendor_email?: string;
  business_name?: string;
  vendor_name?: string;
  name?: string;
  vendor_account_status?: VendorAccountStatus;
  status?: VendorAccountStatus;
  is_free_tier?: boolean;
  campaigns_count?: number;
  total_campaigns?: number;
  active_campaigns?: number;
  total_impressions?: number;
  total_clicks?: number;
  total_leads?: number;
  joined_at?: string;
  created_at?: string;
}

export interface PlatformConfig {
  // Feature Flags
  ads_enabled: boolean;
  show_sponsored_badge: boolean;
  enable_event_tracking: boolean;
  require_creative_review: boolean;
  auto_approve_returning_vendors: boolean;
  // Serving Limits
  max_sponsored_per_page: number;
  impressions_per_session: number;
  freq_cap_per_campaign_planner_day: number;
  review_sla_hours: number;
  max_campaigns_per_vendor: number;
  // Fraud Detection
  max_clicks_per_planner_campaign_hour: number;
  hide_rate_auto_pause_threshold: number;
  click_velocity_window_minutes: number;
  auto_void_suspicious_clicks: boolean;
  // Vendor Signup
  vendor_domain: string;
  auto_approve_signups: boolean;
  require_profile_completion: boolean;
  min_images_for_campaign: number;
  // Metadata
  updated_at?: string;
  updated_by?: string;
  [key: string]: any;
}

export interface PipelineStatus {
  rollup_health: string;
  last_rollup_at: string | null;
  collections: Record<string, { count: number; size_bytes: number }>;
  ttl_policies: Record<string, number>;
}

export interface ExportResponse {
  dataset: string;
  date_range: string;
  total?: number;
  returned?: number;
  row_count: number;
  rows: any[];
}

export interface PlannerFeedbackEntry {
  _id: string;
  planner_email: string;
  campaign_id?: string;
  feedback_type: string;
  message: string;
  created_at: string;
}

// =============================================================================
// HELPERS
// =============================================================================

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = `${API_BASE}${path}`;
  if (!params) return url;

  const queryParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      queryParams.append(key, String(value));
    }
  }

  const qs = queryParams.toString();
  return qs ? `${url}?${qs}` : url;
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

function jsonHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

function authenticatedGet(path: string, token: string, params?: Record<string, string | number | boolean | undefined>) {
  return fetch(buildUrl(path, params), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
}

async function handleResponse<T>(response: Response, errorPrefix: string): Promise<T> {
  if (!response.ok) {
    // Centralized 402 → /admin/planner/billing redirect. See
    // AGENTS.md → "Known Open Issues" item 5. The throw below still fires
    // but the page unloads before any UI can render the error.
    redirectOnBillingBlock(response);
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.message || error.detail || `${errorPrefix}`);
  }
  return response.json();
}

// =============================================================================
// VENDOR PORTAL API — /portal/ads/*
// =============================================================================

/** Create a new ad campaign */
export async function createCampaign(
  token: string,
  data: CreateCampaignRequest
): Promise<AdCampaign> {
  const response = await fetch(buildUrl('/portal/ads/campaigns'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<AdCampaign>(response, 'Failed to create campaign');
}

/** List vendor's campaigns with optional filters */
export async function listVendorCampaigns(
  token: string,
  params?: { status?: string; limit?: number; skip?: number }
): Promise<AdCampaign[]> {
  const response = await authenticatedGet('/portal/ads/campaigns', token, params);
  return handleResponse<AdCampaign[]>(response, 'Failed to fetch campaigns');
}

/** Get a single campaign by ID */
export async function getVendorCampaign(
  token: string,
  campaignId: string
): Promise<AdCampaign> {
  const response = await authenticatedGet(`/portal/ads/campaigns/${campaignId}`, token);
  return handleResponse<AdCampaign>(response, 'Failed to fetch campaign');
}

/** Update a campaign (draft/rejected only) */
export async function updateCampaign(
  token: string,
  campaignId: string,
  data: UpdateCampaignRequest
): Promise<AdCampaign> {
  const response = await fetch(buildUrl(`/portal/ads/campaigns/${campaignId}`), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<AdCampaign>(response, 'Failed to update campaign');
}

/** Delete a campaign (draft only) */
export async function deleteCampaign(
  token: string,
  campaignId: string
): Promise<{ message: string }> {
  const response = await fetch(buildUrl(`/portal/ads/campaigns/${campaignId}`), {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  return handleResponse<{ message: string }>(response, 'Failed to delete campaign');
}

/** Submit campaign for review */
export async function submitCampaignForReview(
  token: string,
  campaignId: string
): Promise<AdCampaign> {
  const response = await fetch(buildUrl(`/portal/ads/campaigns/${campaignId}/submit`), {
    method: 'POST',
    headers: authHeaders(token),
  });
  return handleResponse<AdCampaign>(response, 'Failed to submit campaign');
}

/** Pause an active campaign */
export async function pauseVendorCampaign(
  token: string,
  campaignId: string
): Promise<AdCampaign> {
  const response = await fetch(buildUrl(`/portal/ads/campaigns/${campaignId}/pause`), {
    method: 'POST',
    headers: authHeaders(token),
  });
  return handleResponse<AdCampaign>(response, 'Failed to pause campaign');
}

/** Get campaign performance stats */
export async function getCampaignStats(
  token: string,
  campaignId: string,
  days?: number
): Promise<CampaignStatsResponse> {
  const response = await authenticatedGet(`/portal/ads/campaigns/${campaignId}/stats`, token, { days });
  return handleResponse<CampaignStatsResponse>(response, 'Failed to fetch campaign stats');
}

/** Add a creative to a campaign */
export async function createCreative(
  token: string,
  campaignId: string,
  data: CreateCreativeRequest
): Promise<AdCreative> {
  const response = await fetch(buildUrl(`/portal/ads/campaigns/${campaignId}/creatives`), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<AdCreative>(response, 'Failed to create creative');
}

/** List creatives for a campaign */
export async function listCreatives(
  token: string,
  campaignId: string
): Promise<AdCreative[]> {
  const response = await authenticatedGet(`/portal/ads/campaigns/${campaignId}/creatives`, token);
  return handleResponse<AdCreative[]>(response, 'Failed to fetch creatives');
}

/** Update a creative */
export async function updateCreative(
  token: string,
  creativeId: string,
  data: CreateCreativeRequest
): Promise<AdCreative> {
  const response = await fetch(buildUrl(`/portal/ads/creatives/${creativeId}`), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<AdCreative>(response, 'Failed to update creative');
}

/** Set a creative as the primary creative for its campaign */
export async function setPrimaryCreative(
  token: string,
  campaignId: string,
  creativeId: string
): Promise<AdCreative> {
  const response = await fetch(
    buildUrl(`/portal/ads/campaigns/${campaignId}/creatives/${creativeId}/set-primary`),
    { method: 'POST', headers: authHeaders(token) }
  );
  return handleResponse<AdCreative>(response, 'Failed to set primary creative');
}

/** Request a vendor-scoped upload contract for ad portal media. */
export async function requestVendorMediaUpload(
  token: string,
  data: VendorMediaUploadRequest
): Promise<VendorMediaUploadResponse> {
  const response = await fetch(buildUrl('/portal/ads/media/upload-url'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<VendorMediaUploadResponse>(response, 'Failed to create upload URL');
}

/** Upload a vendor media file and return the persisted upload contract. */
export async function uploadVendorMediaAsset(
  token: string,
  file: File,
  assetKind: VendorMediaAssetKind,
  replaceUrl?: string | null
): Promise<VendorMediaUploadResponse> {
  const upload = await requestVendorMediaUpload(token, {
    filename: file.name,
    content_type: file.type,
    asset_kind: assetKind,
    replace_url: replaceUrl ?? undefined,
  });

  const uploadResponse = await fetch(upload.upload_url, {
    method: 'PUT',
    headers: { 'Content-Type': file.type },
    body: file,
  });

  if (!uploadResponse.ok) {
    throw new Error(`Upload failed: ${uploadResponse.status}`);
  }

  return upload;
}

/** Get vendor's leads */
export async function getVendorLeads(
  token: string,
  params?: { status?: string; lead_type?: string; limit?: number; skip?: number }
): Promise<any[]> {
  const response = await authenticatedGet('/portal/ads/leads', token, params);
  return handleResponse<any[]>(response, 'Failed to fetch leads');
}

/** Get vendor billing summary */
export async function getVendorBilling(token: string): Promise<BillingSummaryResponse> {
  const response = await authenticatedGet('/portal/ads/billing', token);
  return handleResponse<BillingSummaryResponse>(response, 'Failed to fetch billing');
}

// =============================================================================
// ADMIN CAMPAIGN API — /admin/ads/campaigns/*
// =============================================================================

/** Get the campaign review queue */
export async function getAdminReviewQueue(
  token: string,
  params?: { status?: string; limit?: number; skip?: number }
): Promise<AdCampaign[]> {
  const response = await authenticatedGet(
    '/admin/ads/campaigns/review',
    token,
    { status: params?.status ?? 'pending_review', ...params },
  );
  return handleResponse<AdCampaign[]>(response, 'Failed to fetch review queue');
}

/** Get review queue status counts */
export async function getAdminReviewCounts(token: string): Promise<ReviewCounts> {
  const response = await authenticatedGet('/admin/ads/campaigns/review/counts', token);
  return handleResponse<ReviewCounts>(response, 'Failed to fetch review counts');
}

/** Approve a campaign */
export async function approveCampaign(
  token: string,
  campaignId: string,
  data?: ReviewDecisionRequest
): Promise<AdCampaign> {
  const response = await fetch(buildUrl(`/admin/ads/campaigns/${campaignId}/approve`), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify(data || {}),
  });
  return handleResponse<AdCampaign>(response, 'Failed to approve campaign');
}

/** Reject a campaign */
export async function rejectCampaign(
  token: string,
  campaignId: string,
  data?: ReviewDecisionRequest
): Promise<AdCampaign> {
  const response = await fetch(buildUrl(`/admin/ads/campaigns/${campaignId}/reject`), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify(data || {}),
  });
  return handleResponse<AdCampaign>(response, 'Failed to reject campaign');
}

/** Request changes on a campaign */
export async function requestCampaignChanges(
  token: string,
  campaignId: string,
  data: { review_notes: string }
): Promise<AdCampaign> {
  const response = await fetch(buildUrl(`/admin/ads/campaigns/${campaignId}/request-changes`), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<AdCampaign>(response, 'Failed to request changes');
}

/** Get creative review queue */
export async function getCreativeReviewQueue(
  token: string,
  params?: { limit?: number; skip?: number }
): Promise<AdCreative[]> {
  const response = await authenticatedGet('/admin/ads/campaigns/review/creatives', token, params);
  return handleResponse<AdCreative[]>(response, 'Failed to fetch creative review queue');
}

/** Approve a creative */
export async function approveCreative(
  token: string,
  creativeId: string,
  data?: ReviewDecisionRequest
): Promise<AdCreative> {
  const response = await fetch(
    buildUrl(`/admin/ads/campaigns/review/creatives/${creativeId}/approve`),
    { method: 'PUT', headers: jsonHeaders(token), body: JSON.stringify(data || {}) }
  );
  return handleResponse<AdCreative>(response, 'Failed to approve creative');
}

/** Reject a creative */
export async function rejectCreative(
  token: string,
  creativeId: string,
  data?: ReviewDecisionRequest
): Promise<AdCreative> {
  const response = await fetch(
    buildUrl(`/admin/ads/campaigns/review/creatives/${creativeId}/reject`),
    { method: 'PUT', headers: jsonHeaders(token), body: JSON.stringify(data || {}) }
  );
  return handleResponse<AdCreative>(response, 'Failed to reject creative');
}

/** List all campaigns (admin view with filters) */
export async function getAdminCampaigns(
  token: string,
  params?: { status?: string; vendor_id?: string; limit?: number; skip?: number }
): Promise<AdCampaign[]> {
  const response = await authenticatedGet('/admin/ads/campaigns/', token, params);
  return handleResponse<AdCampaign[]>(response, 'Failed to fetch campaigns');
}

/** Admin pause a campaign */
export async function adminPauseCampaign(
  token: string,
  campaignId: string,
  reason?: string
): Promise<AdCampaign> {
  const response = await fetch(buildUrl(`/admin/ads/campaigns/${campaignId}/pause`), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify({ reason }),
  });
  return handleResponse<AdCampaign>(response, 'Failed to pause campaign');
}

/** Admin deactivate a campaign */
export async function adminDeactivateCampaign(
  token: string,
  campaignId: string,
  reason?: string
): Promise<AdCampaign> {
  const response = await fetch(buildUrl(`/admin/ads/campaigns/${campaignId}/deactivate`), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify({ reason }),
  });
  return handleResponse<AdCampaign>(response, 'Failed to deactivate campaign');
}

/** Get revenue and engagement summary */
export async function getAdminRevenue(
  token: string,
  days?: number
): Promise<RevenueResponse> {
  const response = await authenticatedGet('/admin/ads/campaigns/revenue', token, { days });
  return handleResponse<RevenueResponse>(response, 'Failed to fetch revenue data');
}

/** Get planner feedback on ads */
export async function getAdminFeedback(
  token: string,
  params?: { limit?: number; skip?: number }
): Promise<PlannerFeedbackEntry[]> {
  const response = await authenticatedGet('/admin/ads/campaigns/feedback', token, params);
  return handleResponse<PlannerFeedbackEntry[]>(response, 'Failed to fetch feedback');
}

/** Get fraud signals */
export async function getAdminFraudSignals(
  token: string,
  params?: { status?: string; limit?: number; skip?: number }
): Promise<AdFraudSignal[]> {
  const response = await authenticatedGet('/admin/ads/campaigns/fraud-signals', token, params);
  return handleResponse<AdFraudSignal[]>(response, 'Failed to fetch fraud signals');
}

/** Update a fraud signal */
export async function updateFraudSignal(
  token: string,
  signalId: string,
  data: { status: string; notes?: string }
): Promise<AdFraudSignal> {
  const response = await fetch(buildUrl(`/admin/ads/campaigns/fraud-signals/${signalId}`), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<AdFraudSignal>(response, 'Failed to update fraud signal');
}

/** Bulk-create vendor accounts */
export interface BulkVendorEntry {
  email: string;
  business_name: string;
  category?: string;
  location?: string;
  phone?: string;
  website?: string;
  is_free_tier?: boolean;
}

export interface BulkVendorResult {
  total_submitted: number;
  created: number;
  skipped: number;
  failed: number;
  details: {
    created: Array<{ index: number; email: string; business_name: string; _id: string }>;
    skipped: Array<{ index: number; email: string; reason: string }>;
    failed: Array<{ index: number; email: string; reason: string }>;
  };
}

export async function bulkCreateVendors(
  token: string,
  vendors: BulkVendorEntry[]
): Promise<BulkVendorResult> {
  const response = await fetch(buildUrl('/admin/ads/campaigns/vendors/bulk'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(vendors),
  });
  return handleResponse<BulkVendorResult>(response, 'Failed to bulk create vendors');
}

/** Get vendor accounts with advanced filtering */
export async function getAdminVendorAccounts(
  token: string,
  params?: {
    status?: string;
    category?: string;
    location?: string;
    date_from?: string;
    date_to?: string;
    search?: string;
    sort_by?: string;
    sort_order?: number;
    limit?: number;
    skip?: number;
  }
): Promise<{ vendors: VendorAccountSummary[]; total: number; page: number; page_size: number }> {
  const response = await authenticatedGet('/admin/ads/campaigns/vendors', token, params);
  const payload = await handleResponse<{ items?: RawVendorAccountSummary[]; total?: number; limit?: number; skip?: number }>(response, 'Failed to fetch vendor accounts');

  const vendors = (payload.items || []).map((vendor): VendorAccountSummary => ({
    vendor_id: vendor.vendor_id || vendor._id || '',
    vendor_email: vendor.vendor_email || vendor.email || '',
    vendor_name: vendor.vendor_name || vendor.business_name || vendor.name || 'Unknown vendor',
    status: vendor.status || vendor.vendor_account_status || 'inactive',
    is_free_tier: vendor.is_free_tier || false,
    campaigns_count: vendor.campaigns_count ?? vendor.total_campaigns ?? 0,
    active_campaigns: vendor.active_campaigns ?? 0,
    total_impressions: vendor.total_impressions ?? 0,
    total_clicks: vendor.total_clicks ?? 0,
    total_leads: vendor.total_leads ?? 0,
    joined_at: vendor.joined_at || vendor.created_at || '',
  }));

  const limit = payload.limit || params?.limit || vendors.length;
  const skip = payload.skip || params?.skip || 0;
  const pageSize = limit > 0 ? limit : vendors.length || 1;
  const page = Math.floor(skip / pageSize) + 1;

  return {
    vendors,
    total: payload.total || vendors.length,
    page,
    page_size: pageSize,
  };
}

/** Get platform advertising config */
export async function getAdminConfig(token: string): Promise<PlatformConfig> {
  const response = await authenticatedGet('/admin/ads/config', token);
  return handleResponse<PlatformConfig>(response, 'Failed to fetch config');
}

/** Update platform advertising config */
export async function updateAdminConfig(
  token: string,
  updates: Partial<PlatformConfig>
): Promise<PlatformConfig> {
  const response = await fetch(buildUrl('/admin/ads/config'), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify(updates),
  });
  return handleResponse<PlatformConfig>(response, 'Failed to update config');
}

/** Get data pipeline status */
export async function getAdminPipelineStatus(token: string): Promise<PipelineStatus> {
  const response = await authenticatedGet('/admin/ads/config/pipeline', token);
  return handleResponse<PipelineStatus>(response, 'Failed to fetch pipeline status');
}

/** Export advertising data */
export async function exportAdminData(
  token: string,
  dataset: string,
  dateRange: string = 'last_30_days',
  format: string = 'json',
  limit: number = 1000
): Promise<ExportResponse> {
  const response = await authenticatedGet('/admin/ads/config/export', token, {
    dataset,
    date_range: dateRange,
    format,
    limit,
  });
  return handleResponse<ExportResponse>(response, 'Failed to export data');
}

// =============================================================================
// PLANNER API — /planner/ads/*
// =============================================================================

/** Get sponsored cards for the planner's vendor rail */
export async function getSponsoredCards(
  token: string,
  params?: { location?: string; categories?: string; limit?: number }
): Promise<SponsoredCardsResponse> {
  const response = await authenticatedGet('/planner/ads/sponsored-cards', token, params);
  return handleResponse<SponsoredCardsResponse>(response, 'Failed to fetch sponsored cards');
}

/** Add a vendor from an ad campaign to the planner's directory */
export async function addToDirectory(
  token: string,
  data: AddToDirectoryRequest
): Promise<any> {
  const response = await fetch(buildUrl('/planner/ads/add-to-directory'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<any>(response, 'Failed to add vendor to directory');
}

/** Request a quote from a vendor via an ad campaign */
export async function requestQuote(
  token: string,
  data: RequestQuoteRequest
): Promise<any> {
  const response = await fetch(buildUrl('/planner/ads/request-quote'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<any>(response, 'Failed to request quote');
}

/** AI-generate a personalized quote request draft */
export interface DraftQuoteRequest {
  campaign_id: string;
  wedding_context?: WeddingContext;
}

export interface DraftQuoteResponse {
  draft: {
    subject: string;
    body: string;
    tone: string;
  };
  credits_used: number;
  model_used: string;
}

export async function draftQuote(
  token: string,
  data: DraftQuoteRequest
): Promise<DraftQuoteResponse> {
  const response = await fetch(buildUrl('/planner/ads/draft-quote'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<DraftQuoteResponse>(response, 'Failed to generate quote draft');
}

/** Check if a campaign's vendor is already in the planner's directory */
export async function getDirectoryStatus(
  token: string,
  campaignId: string
): Promise<DirectoryStatusResponse> {
  const response = await authenticatedGet('/planner/ads/directory-status', token, { campaign_id: campaignId });
  return handleResponse<DirectoryStatusResponse>(response, 'Failed to check directory status');
}

// =============================================================================
// PLANNER PREFERENCES API — /planner/ads/preferences/*
// =============================================================================

export interface PlannerAdPreferences {
  planner_id: string;
  hidden_vendor_ids: string[];
  suppressed_categories: string[];
  reduced_frequency: boolean;
}

/** Get planner's ad preferences */
export async function getAdPreferences(token: string): Promise<PlannerAdPreferences> {
  const response = await authenticatedGet('/planner/ads/preferences', token);
  return handleResponse<PlannerAdPreferences>(response, 'Failed to fetch ad preferences');
}

/** Hide a specific vendor from the sponsored rail */
export async function hideVendor(token: string, vendorId: string): Promise<any> {
  const response = await fetch(buildUrl('/planner/ads/preferences/hide-vendor'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify({ vendor_id: vendorId }),
  });
  return handleResponse(response, 'Failed to hide vendor');
}

/** Unhide a previously hidden vendor */
export async function unhideVendor(token: string, vendorId: string): Promise<any> {
  const response = await fetch(buildUrl('/planner/ads/preferences/unhide-vendor'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify({ vendor_id: vendorId }),
  });
  return handleResponse(response, 'Failed to unhide vendor');
}

/** Suppress a vendor category from the sponsored rail */
export async function suppressCategory(token: string, category: string): Promise<any> {
  const response = await fetch(buildUrl('/planner/ads/preferences/suppress-category'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify({ category }),
  });
  return handleResponse(response, 'Failed to suppress category');
}

/** Unsuppress a vendor category */
export async function unsuppressCategory(token: string, category: string): Promise<any> {
  const response = await fetch(buildUrl('/planner/ads/preferences/unsuppress-category'), {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify({ category }),
  });
  return handleResponse(response, 'Failed to unsuppress category');
}

/** Toggle reduced ad frequency */
export async function setReducedFrequency(token: string, reducedFrequency: boolean): Promise<any> {
  const response = await fetch(buildUrl('/planner/ads/preferences/frequency'), {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify({ reduced_frequency: reducedFrequency }),
  });
  return handleResponse(response, 'Failed to update ad frequency');
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

export function getCampaignGoalLabel(goal: CampaignGoal): string {
  const labels: Record<CampaignGoal, string> = {
    profile_visits: 'Profile Visits',
    quote_requests: 'Quote Requests',
    bookings: 'Bookings',
  };
  return labels[goal] || goal;
}

export function getCampaignStatusLabel(status: CampaignStatus): string {
  const labels: Record<CampaignStatus, string> = {
    draft: 'Draft',
    pending_review: 'Pending Review',
    active: 'Active',
    paused: 'Paused',
    completed: 'Completed',
    rejected: 'Rejected',
  };
  return labels[status] || status;
}

export function getCampaignStatusColor(status: CampaignStatus): string {
  const colors: Record<CampaignStatus, string> = {
    draft: 'bg-slate-100 text-slate-700',
    pending_review: 'bg-amber-100 text-amber-700',
    active: 'bg-emerald-100 text-emerald-700',
    paused: 'bg-orange-100 text-orange-700',
    completed: 'bg-blue-100 text-blue-700',
    rejected: 'bg-red-100 text-red-700',
  };
  return colors[status] || 'bg-slate-100 text-slate-700';
}

export function getCreativeStatusLabel(status: CreativeReviewStatus): string {
  const labels: Record<CreativeReviewStatus, string> = {
    pending: 'Pending',
    approved: 'Approved',
    rejected: 'Rejected',
    changes_requested: 'Changes Requested',
  };
  return labels[status] || status;
}

export function getCreativeStatusColor(status: CreativeReviewStatus): string {
  const colors: Record<CreativeReviewStatus, string> = {
    pending: 'bg-amber-100 text-amber-700',
    approved: 'bg-emerald-100 text-emerald-700',
    rejected: 'bg-red-100 text-red-700',
    changes_requested: 'bg-orange-100 text-orange-700',
  };
  return colors[status] || 'bg-slate-100 text-slate-700';
}

export function getFraudSignalLabel(type: FraudSignalType): string {
  const labels: Record<FraudSignalType, string> = {
    unusual_traffic: 'Unusual Traffic',
    duplicate_click: 'Duplicate Click',
    bot_pattern: 'Bot Pattern',
    geographic_anomaly: 'Geographic Anomaly',
    rapid_clicks: 'Rapid Clicks',
  };
  return labels[type] || type;
}

export function formatCurrency(amount: number): string {
  if (amount == null || isNaN(amount)) return '$0';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatNumber(num: number): string {
  if (num == null || isNaN(num)) return '0';
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return num.toLocaleString();
}

export function formatPercent(value: number): string {
  if (value == null || isNaN(value)) return '0.00%';
  return `${(value * 100).toFixed(2)}%`;
}


// =============================================================================
// BILLING TYPES
// =============================================================================

export interface LeadCharge {
  _id: string;
  lead_id: string;
  campaign_id: string;
  vendor_id: string;
  lead_type: 'quote_request' | 'add_to_directory';
  charge_amount: number;
  currency: string;
  is_free_tier: boolean;
  charge_status: 'pending' | 'charged' | 'free' | 'failed';
  stripe_invoice_item_id?: string;
  planner_id?: string;
  click_id?: string;
  created_at: string;
}

export interface BillingPeriod {
  _id: string;
  vendor_id: string;
  campaign_id: string;
  billing_period_start: string;
  billing_period_end: string;
  leads: number;
  quote_request_leads: number;
  directory_add_leads: number;
  total_spend: number;
  is_free_tier: boolean;
  payment_status: string;
}

export interface VendorBillingSummary {
  vendor_id: string;
  billing_model: string;
  is_free_tier: boolean;
  free_tier_reason: string;
  free_tier_expires_at?: string;
  total_spend: number;
  currency: string;
  total_leads: number;
  quote_request_leads: number;
  directory_add_leads: number;
  billing_periods: BillingPeriod[];
}

export interface CampaignBillingSummary {
  total_charges: number;
  total_leads: number;
  quote_requests: number;
  directory_adds: number;
  free_leads: number;
  paid_leads: number;
}

export interface FreeTierStatus {
  vendor_id: string;
  is_free: boolean;
  reason?: string;
  expires_at?: string;
  granted_by?: string;
}


// =============================================================================
// ADMIN BILLING ENDPOINTS
// =============================================================================

/** Set campaign-level free tier */
export async function setCampaignFreeTier(
  token: string,
  campaignId: string,
  body: { is_free: boolean; reason?: string },
): Promise<AdCampaign> {
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/${campaignId}/free-tier`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to set free tier');
  return res.json();
}

/** Set vendor-level free tier */
export async function setVendorFreeTier(
  token: string,
  vendorId: string,
  body: { is_free: boolean; reason?: string; expires_at?: string },
): Promise<FreeTierStatus> {
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/vendors/${vendorId}/free-tier`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to set vendor free tier');
  return res.json();
}

/** Get vendor free tier status */
export async function getVendorFreeTierStatus(
  token: string,
  vendorId: string,
): Promise<FreeTierStatus> {
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/vendors/${vendorId}/free-tier`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to get free tier status');
  return res.json();
}

/** List all free tier vendors */
export async function listFreeTierVendors(token: string): Promise<FreeTierStatus[]> {
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/free-tier-vendors`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to list free tier vendors');
  return res.json();
}

/** Update CPL pricing on a campaign */
export async function updateCampaignCPLPricing(
  token: string,
  campaignId: string,
  body: { cpl_quote_request?: number; cpl_directory_add?: number },
): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/${campaignId}/cpl-pricing`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to update pricing');
  return res.json();
}

/** Get campaign billing summary */
export async function getCampaignBilling(
  token: string,
  campaignId: string,
): Promise<CampaignBillingSummary> {
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/${campaignId}/billing`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to get campaign billing');
  return res.json();
}

/** Get individual lead charges for a campaign */
export async function getCampaignLeadCharges(
  token: string,
  campaignId: string,
  params?: { limit?: number; skip?: number },
): Promise<LeadCharge[]> {
  const sp = new URLSearchParams();
  if (params?.limit) sp.set('limit', params.limit.toString());
  if (params?.skip) sp.set('skip', params.skip.toString());
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/${campaignId}/lead-charges?${sp}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to get lead charges');
  return res.json();
}


// =============================================================================
// VENDOR BILLING ENDPOINTS
// =============================================================================

/** Get vendor billing summary (vendor portal) */
export async function getVendorBillingSummary(token: string): Promise<VendorBillingSummary> {
  const res = await fetch(`${API_BASE}/portal/ads/billing`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to get billing summary');
  return res.json();
}

/** Get vendor billing charges (vendor portal) */
export async function getVendorBillingCharges(
  token: string,
  params?: { campaign_id?: string; limit?: number; skip?: number },
): Promise<LeadCharge[]> {
  const sp = new URLSearchParams();
  if (params?.campaign_id) sp.set('campaign_id', params.campaign_id);
  if (params?.limit) sp.set('limit', params.limit.toString());
  if (params?.skip) sp.set('skip', params.skip.toString());
  const res = await fetch(`${API_BASE}/portal/ads/billing/charges?${sp}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to get billing charges');
  return res.json();
}

// =============================================================================
// VENDOR ACCOUNT MANAGEMENT (Phase 10)
// =============================================================================

/** Approve a pending vendor account. Sends temp password email. */
export async function approveVendorAccount(
  token: string,
  vendorId: string,
): Promise<{ vendor_id: string; status: string; message: string }> {
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/vendors/${vendorId}/approve`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to approve vendor');
  return res.json();
}

/** Suspend an active vendor account. Pauses all their campaigns. */
export async function suspendVendorAccount(
  token: string,
  vendorId: string,
  reason: string = '',
): Promise<{ vendor_id: string; status: string; campaigns_paused: number; message: string }> {
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/vendors/${vendorId}/suspend`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to suspend vendor');
  return res.json();
}

/** Reactivate a suspended vendor account. Campaigns remain paused. */
export async function reactivateVendorAccount(
  token: string,
  vendorId: string,
): Promise<{ vendor_id: string; status: string; message: string }> {
  const res = await fetch(`${API_BASE}/admin/ads/campaigns/vendors/${vendorId}/reactivate`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to reactivate vendor');
  return res.json();
}
