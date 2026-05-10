/**
 * Campaign Advertising API Service
 *
 * New API client for the campaign-based advertising platform.
 * Covers all three portals: Vendor Portal, Admin Console, and Planner interactions.
 *
 * This replaces the OLD advertisingApi.ts (which talked to sponsored_vendors endpoints).
 */

import { getApiBaseUrl } from '@/utils/env';
import {
  adminGet,
  adminMutation,
  type AdminApiRequest,
} from '@/services/adminApiRequest';

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

async function handlePortalResponse<T>(response: Response, errorPrefix: string): Promise<T> {
  if (!response.ok) {
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
  return handlePortalResponse<AdCampaign>(response, 'Failed to create campaign');
}

/** List vendor's campaigns with optional filters */
export async function listVendorCampaigns(
  token: string,
  params?: { status?: string; limit?: number; skip?: number }
): Promise<AdCampaign[]> {
  const response = await authenticatedGet('/portal/ads/campaigns', token, params);
  return handlePortalResponse<AdCampaign[]>(response, 'Failed to fetch campaigns');
}

/** Get a single campaign by ID */
export async function getVendorCampaign(
  token: string,
  campaignId: string
): Promise<AdCampaign> {
  const response = await authenticatedGet(`/portal/ads/campaigns/${campaignId}`, token);
  return handlePortalResponse<AdCampaign>(response, 'Failed to fetch campaign');
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
  return handlePortalResponse<AdCampaign>(response, 'Failed to update campaign');
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
  return handlePortalResponse<{ message: string }>(response, 'Failed to delete campaign');
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
  return handlePortalResponse<AdCampaign>(response, 'Failed to submit campaign');
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
  return handlePortalResponse<AdCampaign>(response, 'Failed to pause campaign');
}

/** Get campaign performance stats */
export async function getCampaignStats(
  token: string,
  campaignId: string,
  days?: number
): Promise<CampaignStatsResponse> {
  const response = await authenticatedGet(`/portal/ads/campaigns/${campaignId}/stats`, token, { days });
  return handlePortalResponse<CampaignStatsResponse>(response, 'Failed to fetch campaign stats');
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
  return handlePortalResponse<AdCreative>(response, 'Failed to create creative');
}

/** List creatives for a campaign */
export async function listCreatives(
  token: string,
  campaignId: string
): Promise<AdCreative[]> {
  const response = await authenticatedGet(`/portal/ads/campaigns/${campaignId}/creatives`, token);
  return handlePortalResponse<AdCreative[]>(response, 'Failed to fetch creatives');
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
  return handlePortalResponse<AdCreative>(response, 'Failed to update creative');
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
  return handlePortalResponse<AdCreative>(response, 'Failed to set primary creative');
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
  return handlePortalResponse<VendorMediaUploadResponse>(response, 'Failed to create upload URL');
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
  return handlePortalResponse<any[]>(response, 'Failed to fetch leads');
}

/** Get vendor billing summary */
export async function getVendorBilling(token: string): Promise<BillingSummaryResponse> {
  const response = await authenticatedGet('/portal/ads/billing', token);
  return handlePortalResponse<BillingSummaryResponse>(response, 'Failed to fetch billing');
}

// =============================================================================
// ADMIN CAMPAIGN API — /admin/ads/campaigns/*
// =============================================================================

/** Get the campaign review queue */
export async function getAdminReviewQueue(
  apiRequest: AdminApiRequest,
  params?: { status?: string; limit?: number; skip?: number }
): Promise<AdCampaign[] | undefined> {
  return adminGet<AdCampaign[]>(
    apiRequest,
    '/admin/ads/campaigns/review',
    { status: params?.status ?? 'pending_review', ...params },
  );
}

/** Get review queue status counts */
export async function getAdminReviewCounts(apiRequest: AdminApiRequest): Promise<ReviewCounts | undefined> {
  return adminGet<ReviewCounts>(apiRequest, '/admin/ads/campaigns/review/counts');
}

/** Approve a campaign */
export async function approveCampaign(
  apiRequest: AdminApiRequest,
  campaignId: string,
  data?: ReviewDecisionRequest
): Promise<AdCampaign | undefined> {
  return adminMutation<AdCampaign>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/${campaignId}/approve`,
    data || {},
  );
}

/** Reject a campaign */
export async function rejectCampaign(
  apiRequest: AdminApiRequest,
  campaignId: string,
  data?: ReviewDecisionRequest
): Promise<AdCampaign | undefined> {
  return adminMutation<AdCampaign>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/${campaignId}/reject`,
    data || {},
  );
}

/** Request changes on a campaign */
export async function requestCampaignChanges(
  apiRequest: AdminApiRequest,
  campaignId: string,
  data: { review_notes: string }
): Promise<AdCampaign | undefined> {
  return adminMutation<AdCampaign>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/${campaignId}/request-changes`,
    data,
  );
}

/** Get creative review queue */
export async function getCreativeReviewQueue(
  apiRequest: AdminApiRequest,
  params?: { limit?: number; skip?: number }
): Promise<AdCreative[] | undefined> {
  return adminGet<AdCreative[]>(
    apiRequest,
    '/admin/ads/campaigns/review/creatives',
    params,
  );
}

/** Approve a creative */
export async function approveCreative(
  apiRequest: AdminApiRequest,
  creativeId: string,
  data?: ReviewDecisionRequest
): Promise<AdCreative | undefined> {
  return adminMutation<AdCreative>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/review/creatives/${creativeId}/approve`,
    data || {},
  );
}

/** Reject a creative */
export async function rejectCreative(
  apiRequest: AdminApiRequest,
  creativeId: string,
  data?: ReviewDecisionRequest
): Promise<AdCreative | undefined> {
  return adminMutation<AdCreative>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/review/creatives/${creativeId}/reject`,
    data || {},
  );
}

/** List all campaigns (admin view with filters) */
export async function getAdminCampaigns(
  apiRequest: AdminApiRequest,
  params?: { status?: string; vendor_id?: string; limit?: number; skip?: number }
): Promise<AdCampaign[] | undefined> {
  return adminGet<AdCampaign[]>(apiRequest, '/admin/ads/campaigns/', params);
}

/** Admin pause a campaign */
export async function adminPauseCampaign(
  apiRequest: AdminApiRequest,
  campaignId: string,
  reason?: string
): Promise<AdCampaign | undefined> {
  return adminMutation<AdCampaign>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/${campaignId}/pause`,
    { reason },
  );
}

/** Admin deactivate a campaign */
export async function adminDeactivateCampaign(
  apiRequest: AdminApiRequest,
  campaignId: string,
  reason?: string
): Promise<AdCampaign | undefined> {
  return adminMutation<AdCampaign>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/${campaignId}/deactivate`,
    { reason },
  );
}

/** Get revenue and engagement summary */
export async function getAdminRevenue(
  apiRequest: AdminApiRequest,
  days?: number
): Promise<RevenueResponse | undefined> {
  return adminGet<RevenueResponse>(apiRequest, '/admin/ads/campaigns/revenue', { days });
}

/** Get planner feedback on ads */
export async function getAdminFeedback(
  apiRequest: AdminApiRequest,
  params?: { limit?: number; skip?: number }
): Promise<PlannerFeedbackEntry[] | undefined> {
  return adminGet<PlannerFeedbackEntry[]>(
    apiRequest,
    '/admin/ads/campaigns/feedback',
    params,
  );
}

/** Get fraud signals */
export async function getAdminFraudSignals(
  apiRequest: AdminApiRequest,
  params?: { status?: string; limit?: number; skip?: number }
): Promise<AdFraudSignal[] | undefined> {
  return adminGet<AdFraudSignal[]>(
    apiRequest,
    '/admin/ads/campaigns/fraud-signals',
    params,
  );
}

/** Update a fraud signal */
export async function updateFraudSignal(
  apiRequest: AdminApiRequest,
  signalId: string,
  data: { status: string; notes?: string }
): Promise<AdFraudSignal | undefined> {
  return adminMutation<AdFraudSignal>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/fraud-signals/${signalId}`,
    data,
  );
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
  apiRequest: AdminApiRequest,
  vendors: BulkVendorEntry[]
): Promise<BulkVendorResult | undefined> {
  return adminMutation<BulkVendorResult>(
    apiRequest,
    'POST',
    '/admin/ads/campaigns/vendors/bulk',
    vendors,
  );
}

/** Get vendor accounts with advanced filtering */
export async function getAdminVendorAccounts(
  apiRequest: AdminApiRequest,
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
): Promise<{ vendors: VendorAccountSummary[]; total: number; page: number; page_size: number } | undefined> {
  const payload = await adminGet<{
    items?: RawVendorAccountSummary[];
    total?: number;
    limit?: number;
    skip?: number;
  }>(apiRequest, '/admin/ads/campaigns/vendors', params);

  if (!payload) {
    return undefined;
  }

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
export async function getAdminConfig(apiRequest: AdminApiRequest): Promise<PlatformConfig | undefined> {
  return adminGet<PlatformConfig>(apiRequest, '/admin/ads/config');
}

/** Update platform advertising config */
export async function updateAdminConfig(
  apiRequest: AdminApiRequest,
  updates: Partial<PlatformConfig>
): Promise<PlatformConfig | undefined> {
  return adminMutation<PlatformConfig>(
    apiRequest,
    'PUT',
    '/admin/ads/config',
    updates,
  );
}

/** Get data pipeline status */
export async function getAdminPipelineStatus(apiRequest: AdminApiRequest): Promise<PipelineStatus | undefined> {
  return adminGet<PipelineStatus>(apiRequest, '/admin/ads/config/pipeline');
}

/** Export advertising data */
export async function exportAdminData(
  apiRequest: AdminApiRequest,
  dataset: string,
  dateRange: string = 'last_30_days',
  format: string = 'json',
  limit: number = 1000
): Promise<ExportResponse | undefined> {
  return adminGet<ExportResponse>(apiRequest, '/admin/ads/config/export', {
    dataset,
    date_range: dateRange,
    format,
    limit,
  });
}

// =============================================================================
// PLANNER API — /planner/ads/*
// =============================================================================

/** Get sponsored cards for the planner's vendor rail */
export async function getSponsoredCards(
  apiRequest: AdminApiRequest,
  params?: { location?: string; categories?: string; limit?: number }
): Promise<SponsoredCardsResponse | undefined> {
  return adminGet<SponsoredCardsResponse>(
    apiRequest,
    '/planner/ads/sponsored-cards',
    params,
  );
}

/** Add a vendor from an ad campaign to the planner's directory */
export async function addToDirectory(
  apiRequest: AdminApiRequest,
  data: AddToDirectoryRequest
): Promise<any | undefined> {
  return adminMutation<any>(apiRequest, 'POST', '/planner/ads/add-to-directory', data);
}

/** Request a quote from a vendor via an ad campaign */
export async function requestQuote(
  apiRequest: AdminApiRequest,
  data: RequestQuoteRequest
): Promise<any | undefined> {
  return adminMutation<any>(apiRequest, 'POST', '/planner/ads/request-quote', data);
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
  apiRequest: AdminApiRequest,
  data: DraftQuoteRequest
): Promise<DraftQuoteResponse | undefined> {
  return adminMutation<DraftQuoteResponse>(
    apiRequest,
    'POST',
    '/planner/ads/draft-quote',
    data,
  );
}

/** Check if a campaign's vendor is already in the planner's directory */
export async function getDirectoryStatus(
  apiRequest: AdminApiRequest,
  campaignId: string
): Promise<DirectoryStatusResponse | undefined> {
  return adminGet<DirectoryStatusResponse>(
    apiRequest,
    '/planner/ads/directory-status',
    { campaign_id: campaignId },
  );
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
export async function getAdPreferences(apiRequest: AdminApiRequest): Promise<PlannerAdPreferences | undefined> {
  return adminGet<PlannerAdPreferences>(apiRequest, '/planner/ads/preferences');
}

/** Hide a specific vendor from the sponsored rail */
export async function hideVendor(apiRequest: AdminApiRequest, vendorId: string): Promise<any | undefined> {
  return adminMutation(apiRequest, 'POST', '/planner/ads/preferences/hide-vendor', {
    vendor_id: vendorId,
  });
}

/** Unhide a previously hidden vendor */
export async function unhideVendor(apiRequest: AdminApiRequest, vendorId: string): Promise<any | undefined> {
  return adminMutation(apiRequest, 'POST', '/planner/ads/preferences/unhide-vendor', {
    vendor_id: vendorId,
  });
}

/** Suppress a vendor category from the sponsored rail */
export async function suppressCategory(apiRequest: AdminApiRequest, category: string): Promise<any | undefined> {
  return adminMutation(apiRequest, 'POST', '/planner/ads/preferences/suppress-category', {
    category,
  });
}

/** Unsuppress a vendor category */
export async function unsuppressCategory(apiRequest: AdminApiRequest, category: string): Promise<any | undefined> {
  return adminMutation(apiRequest, 'POST', '/planner/ads/preferences/unsuppress-category', {
    category,
  });
}

/** Toggle reduced ad frequency */
export async function setReducedFrequency(
  apiRequest: AdminApiRequest,
  reducedFrequency: boolean,
): Promise<any | undefined> {
  return adminMutation(apiRequest, 'PUT', '/planner/ads/preferences/frequency', {
    reduced_frequency: reducedFrequency,
  });
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
  apiRequest: AdminApiRequest,
  campaignId: string,
  body: { is_free: boolean; reason?: string },
): Promise<AdCampaign | undefined> {
  return adminMutation<AdCampaign>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/${campaignId}/free-tier`,
    body,
  );
}

/** Set vendor-level free tier */
export async function setVendorFreeTier(
  apiRequest: AdminApiRequest,
  vendorId: string,
  body: { is_free: boolean; reason?: string; expires_at?: string },
): Promise<FreeTierStatus | undefined> {
  return adminMutation<FreeTierStatus>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/vendors/${vendorId}/free-tier`,
    body,
  );
}

/** Get vendor free tier status */
export async function getVendorFreeTierStatus(
  apiRequest: AdminApiRequest,
  vendorId: string,
): Promise<FreeTierStatus | undefined> {
  return adminGet<FreeTierStatus>(
    apiRequest,
    `/admin/ads/campaigns/vendors/${vendorId}/free-tier`,
  );
}

/** List all free tier vendors */
export async function listFreeTierVendors(apiRequest: AdminApiRequest): Promise<FreeTierStatus[] | undefined> {
  return adminGet<FreeTierStatus[]>(
    apiRequest,
    '/admin/ads/campaigns/free-tier-vendors',
  );
}

/** Update CPL pricing on a campaign */
export async function updateCampaignCPLPricing(
  apiRequest: AdminApiRequest,
  campaignId: string,
  body: { cpl_quote_request?: number; cpl_directory_add?: number },
): Promise<{ status: string } | undefined> {
  return adminMutation<{ status: string }>(
    apiRequest,
    'PUT',
    `/admin/ads/campaigns/${campaignId}/cpl-pricing`,
    body,
  );
}

/** Get campaign billing summary */
export async function getCampaignBilling(
  apiRequest: AdminApiRequest,
  campaignId: string,
): Promise<CampaignBillingSummary | undefined> {
  return adminGet<CampaignBillingSummary>(
    apiRequest,
    `/admin/ads/campaigns/${campaignId}/billing`,
  );
}

/** Get individual lead charges for a campaign */
export async function getCampaignLeadCharges(
  apiRequest: AdminApiRequest,
  campaignId: string,
  params?: { limit?: number; skip?: number },
): Promise<LeadCharge[] | undefined> {
  return adminGet<LeadCharge[]>(
    apiRequest,
    `/admin/ads/campaigns/${campaignId}/lead-charges`,
    params,
  );
}


// =============================================================================
// VENDOR BILLING ENDPOINTS
// =============================================================================

/** Get vendor billing summary (vendor portal) */
export async function getVendorBillingSummary(token: string): Promise<VendorBillingSummary> {
  const res = await fetch(`${API_BASE}/portal/ads/billing`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handlePortalResponse<VendorBillingSummary>(res, 'Failed to get billing summary');
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
  return handlePortalResponse<LeadCharge[]>(res, 'Failed to get billing charges');
}

// =============================================================================
// VENDOR ACCOUNT MANAGEMENT (Phase 10)
// =============================================================================

/** Approve a pending vendor account. Sends temp password email. */
export async function approveVendorAccount(
  apiRequest: AdminApiRequest,
  vendorId: string,
): Promise<{ vendor_id: string; status: string; message: string } | undefined> {
  return adminMutation<{ vendor_id: string; status: string; message: string }>(
    apiRequest,
    'POST',
    `/admin/ads/campaigns/vendors/${vendorId}/approve`,
  );
}

/** Suspend an active vendor account. Pauses all their campaigns. */
export async function suspendVendorAccount(
  apiRequest: AdminApiRequest,
  vendorId: string,
  reason: string = '',
): Promise<{ vendor_id: string; status: string; campaigns_paused: number; message: string } | undefined> {
  return adminMutation<{ vendor_id: string; status: string; campaigns_paused: number; message: string }>(
    apiRequest,
    'POST',
    `/admin/ads/campaigns/vendors/${vendorId}/suspend`,
    { reason },
  );
}

/** Reactivate a suspended vendor account. Campaigns remain paused. */
export async function reactivateVendorAccount(
  apiRequest: AdminApiRequest,
  vendorId: string,
): Promise<{ vendor_id: string; status: string; message: string } | undefined> {
  return adminMutation<{ vendor_id: string; status: string; message: string }>(
    apiRequest,
    'POST',
    `/admin/ads/campaigns/vendors/${vendorId}/reactivate`,
  );
}
