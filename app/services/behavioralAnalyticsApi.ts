/**
 * Behavioral Analytics API Service
 *
 * Provides product-level metrics: WAU, activation funnels,
 * retention cohorts, engagement signals, MRR movement,
 * and per-wedding engagement data.
 */

import { getApiBaseUrl } from '@/utils/env';
import { adminGet, type AdminApiRequest } from '@/services/adminApiRequest';

const API_BASE = getApiBaseUrl();

// =============================================================================
// TYPES
// =============================================================================

export interface WAUMetrics {
  current: number;
  previous_week: number;
  change: number;
  change_percent: number;
  mau: number;
  stickiness_ratio: number;
}

export interface FunnelStep {
  name: string;
  count: number;
  rate: number;
}

export interface ActivationFunnel {
  period: string;
  steps: FunnelStep[];
  conversion_rate: number;
  signups_90d: number;
}

export interface RetentionCohort {
  month: string;
  cohort_size: number;
  d7: number | null;
  d30: number | null;
  d60: number | null;
  d90: number | null;
}

export interface RSVPVelocity {
  current_7d: number;
  previous_7d: number;
  change: number;
  trend: 'up' | 'down' | 'flat';
}

export interface EngagementSignals {
  rsvp_velocity: RSVPVelocity;
  platform_response_rate: number;
  active_engaged_weddings: number;
  north_star_metric: number;
}

export interface MRRMovement {
  current_mrr: number;
  new_mrr: number;
  churned_mrr: number;
  net_change: number;
  net_change_percent: number;
  trial_conversions: number;
  trial_conversion_rate: number;
}

export interface WoWChange {
  current: number;
  previous: number;
  change: number;
  change_percent: number;
  trend: 'up' | 'down' | 'flat';
}

export interface WeekOverWeek {
  new_users: WoWChange;
  new_weddings: WoWChange;
  new_rsvps: WoWChange;
  active_users: WoWChange;
}

export interface BehavioralAnalyticsResponse {
  generated_at: string;
  timeframe: string;
  weekly_active_users: WAUMetrics;
  activation_funnel: ActivationFunnel;
  retention_cohorts: { cohorts: RetentionCohort[] };
  engagement_signals: EngagementSignals;
  mrr_movement: MRRMovement;
  week_over_week: WeekOverWeek;
}

// Planner engagement signals
export interface WeddingEngagementSignal {
  wedding_id: string;
  couple_names: string;
  wedding_date: string;
  last_activity_at: string | null;
  days_since_activity: number | null;
  guest_count: number;
  invited_count: number;
  rsvp_count: number;
  response_rate: number;
  rsvps_last_7d: number;
  forms_total: number;
  forms_completed: number;
  needs_attention: string[];
}

// Couple portal: non-responders
export interface NonResponder {
  guest_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  invite_sent_date: string | null;
  days_since_invite: number | null;
  group_id: string | null;
}

// Couple portal: budget breakdown
export interface BudgetCategory {
  category_id: string;
  name: string;
  budgeted: number;
  spent: number;
  remaining: number;
  percent_of_total_budget: number;
  percent_spent: number;
  payment_status: string;
  priority: number;
}

export interface BudgetBreakdown {
  wedding_id: string;
  total_budgeted: number;
  total_spent: number;
  total_remaining: number;
  percent_spent: number;
  categories: BudgetCategory[];
  category_count: number;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Fetch full behavioral analytics (ROOT_ADMIN only)
 */
export async function fetchBehavioralAnalytics(
  apiRequest: AdminApiRequest,
  timeframe: string = '30d'
): Promise<BehavioralAnalyticsResponse | undefined> {
  return adminGet<BehavioralAnalyticsResponse>(
    apiRequest,
    '/admin/behavioral-analytics',
    { timeframe },
  );
}

/**
 * Fetch per-wedding engagement signals (planner)
 */
export async function fetchEngagementSignals(
  apiRequest: AdminApiRequest
): Promise<{ signals: WeddingEngagementSignal[]; count: number } | undefined> {
  return adminGet<{ signals: WeddingEngagementSignal[]; count: number }>(
    apiRequest,
    '/admin/engagement-signals',
  );
}

/**
 * Fetch non-responders for a wedding (admin/planner — uses Bearer token)
 */
export async function fetchNonResponders(
  apiRequest: AdminApiRequest,
  weddingId: string
): Promise<{ wedding_id: string; non_responders: NonResponder[]; count: number } | undefined> {
  return adminGet<{ wedding_id: string; non_responders: NonResponder[]; count: number }>(
    apiRequest,
    `/admin/weddings/${weddingId}/non-responders`,
  );
}

/**
 * Fetch budget category breakdown (admin/planner — uses Bearer token)
 */
export async function fetchBudgetBreakdown(
  apiRequest: AdminApiRequest,
  weddingId: string
): Promise<BudgetBreakdown | undefined> {
  return adminGet<BudgetBreakdown>(
    apiRequest,
    `/admin/weddings/${weddingId}/budget-breakdown`,
  );
}

// ---------------------------------------------------------------------------
// Couple-auth versions (cookie-based JWT — use with coupleFetch or directly)
// ---------------------------------------------------------------------------

/**
 * Fetch non-responders for the couple's wedding (couple auth — cookie-based)
 */
export async function fetchCoupleNonResponders(): Promise<{
  wedding_id: string;
  non_responders: NonResponder[];
  count: number;
}> {
  const res = await fetch(`${API_BASE}/couple/portal/non-responders`, {
    credentials: 'include',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || 'Failed to fetch non-responders');
  }
  return res.json();
}

/**
 * Fetch budget breakdown for the couple's wedding (couple auth — cookie-based)
 */
export async function fetchCoupleBudgetBreakdown(): Promise<BudgetBreakdown> {
  const res = await fetch(`${API_BASE}/couple/portal/budget-breakdown`, {
    credentials: 'include',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || 'Failed to fetch budget breakdown');
  }
  return res.json();
}
