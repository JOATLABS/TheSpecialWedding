/**
 * Calendar API client for planner scheduling, shared calendars, and Google connections.
 */
import { getApiBaseUrl } from '@/utils/env';

const BASE_URL = getApiBaseUrl();

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled';
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';
export type TaskCategory =
  | 'venue'
  | 'catering'
  | 'photography'
  | 'videography'
  | 'music'
  | 'flowers'
  | 'attire'
  | 'invitations'
  | 'transportation'
  | 'accommodation'
  | 'ceremony'
  | 'reception'
  | 'honeymoon'
  | 'legal'
  | 'budget'
  | 'guest_management'
  | 'meeting'
  | 'other';
export type ScheduleItemType = 'task' | 'meeting' | 'blocked_time';
export type VisibilityMode = 'details' | 'busy_only';
export type CalendarSyncPolicy = 'owner_only' | 'assigned_only' | 'owner_and_assigned' | 'custom';
export type InviteDeliveryMode = 'none' | 'email_ics' | 'portal_only';
export type ConnectionStatus = 'active' | 'expired' | 'revoked' | 'error';
export type SyncStatusValue = 'pending' | 'synced' | 'failed' | 'orphaned' | 'not_configured';
export type CalendarSchedulerRole = 'owner' | 'admin' | 'editor' | 'viewer';
export type CalendarSchedulerAccessMode =
  | 'workspace_default'
  | 'owner_only'
  | 'owner_and_connection_user'
  | 'workspace_permitted';
export type CalendarSyncTargetingMode = 'automatic_and_manual' | 'manual_only';

export interface TaskSyncSummary {
  row_count: number;
  synced_target_count: number;
  failed_target_count: number;
  orphaned_target_count: number;
  not_configured_target_count: number;
  pending_target_count: number;
  has_synced_target: boolean;
  has_configured_target: boolean;
  primary_external_event_id?: string | null;
  last_sync_at?: string | null;
}

export interface PlannerTask {
  id: string;
  planner_email: string;
  wedding_id?: string | null;
  wedding_name?: string | null;
  title: string;
  description?: string | null;
  category: string;
  priority: string;
  status: string;
  start_date: string;
  end_date?: string | null;
  all_day: boolean;
  due_date?: string | null;
  reminder_minutes?: number | null;
  external_sync_requested: boolean;
  is_recurring: boolean;
  recurrence_rule?: string | null;
  color?: string | null;
  notes?: string | null;
  owner_planner_id?: string | null;
  owner_planner_email?: string | null;
  created_by_user_id?: string | null;
  created_by_email?: string | null;
  assigned_user_ids: string[];
  assigned_user_emails: string[];
  schedule_item_type?: string | null;
  visibility_mode?: VisibilityMode | null;
  calendar_sync_policy?: CalendarSyncPolicy | null;
  sync_target_override_enabled?: boolean;
  sync_target_connection_ids: string[];
  timezone?: string | null;
  couple_attendee_emails: string[];
  conference_provider?: string | null;
  conference_url?: string | null;
  invite_delivery_mode?: InviteDeliveryMode | null;
  meeting_status?: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  completed_at?: string | null;
  sync_status_summary?: TaskSyncSummary | null;
}

export interface TaskListResponse {
  tasks: PlannerTask[];
  total: number;
  page: number;
  page_size: number;
}

export interface CalendarConnection {
  id: string;
  owner_planner_id?: string | null;
  owner_planner_email?: string | null;
  user_id?: string | null;
  user_email?: string | null;
  provider: string;
  provider_account_email?: string | null;
  provider_account_name?: string | null;
  calendar_id?: string | null;
  calendar_name?: string | null;
  access_role?: string | null;
  is_writable: boolean;
  is_primary: boolean;
  is_default_write_target: boolean;
  scheduler_access_mode: CalendarSchedulerAccessMode;
  sync_targeting_mode: CalendarSyncTargetingMode;
  allowed_scheduler_user_ids: string[];
  allowed_scheduler_roles: CalendarSchedulerRole[];
  allowed_schedule_item_types: ScheduleItemType[];
  allowed_wedding_ids: string[];
  is_shared_in_team_view: boolean;
  details_visibility: VisibilityMode;
  sync_enabled: boolean;
  couple_booking_auto_confirm?: boolean;
  conference_provider_default?: 'zoom' | 'teams' | 'webex' | null;
  connection_status: ConnectionStatus | string;
  token_expiry?: string | null;
  last_sync_at?: string | null;
  last_healthcheck_at?: string | null;
  last_error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CalendarSyncStatusItem {
  id: string;
  task_id: string;
  target_user_id?: string | null;
  target_user_email?: string | null;
  calendar_connection_id?: string | null;
  provider?: string | null;
  calendar_id?: string | null;
  external_event_id?: string | null;
  sync_status: SyncStatusValue | string;
  last_sync_at?: string | null;
  last_error?: string | null;
  last_error_category?: string | null;
  retryable_error?: boolean;
  retry_count?: number;
  next_retry_at?: string | null;
  last_retry_at?: string | null;
  last_drift_check_at?: string | null;
  updated_at?: string | null;
}

export interface SharedCalendarEvent {
  id: string;
  source_type: 'internal_task' | 'internal_meeting' | 'external_google' | string;
  title?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  all_day: boolean;
  wedding_id?: string | null;
  owner_planner_email?: string | null;
  assigned_user_ids: string[];
  assigned_user_emails: string[];
  visibility_mode: VisibilityMode | string;
  details: Record<string, unknown>;
}

export interface AvailabilityWindow {
  start: string;
  end: string;
}

export interface AvailabilityResponse {
  staff_ids: string[];
  start: string;
  end: string;
  busy_events: SharedCalendarEvent[];
  available_windows: AvailabilityWindow[];
}

export interface MeetingUpsertResponse {
  meeting: Record<string, unknown>;
  sync_status: CalendarSyncStatusItem[];
  invite_status: Array<Record<string, unknown>>;
}

export interface GoogleAuthUrlResponse {
  auth_url: string;
  message: string;
}

export interface TaskFilters {
  wedding_id?: string;
  status?: TaskStatus;
  category?: TaskCategory;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}

export interface SharedCalendarFilters {
  start?: string;
  end?: string;
  wedding_ids?: string[];
  staff_ids?: string[];
  source_types?: string[];
}

export interface ScheduleItemPayload {
  title: string;
  description?: string;
  wedding_id?: string;
  category?: TaskCategory;
  priority?: TaskPriority;
  status?: TaskStatus;
  start_date: string;
  end_date?: string;
  all_day?: boolean;
  due_date?: string;
  reminder_minutes?: number;
  is_recurring?: boolean;
  recurrence_rule?: string;
  color?: string;
  notes?: string;
  external_sync_requested?: boolean;
  assigned_user_ids?: string[];
  assigned_user_emails?: string[];
  schedule_item_type?: ScheduleItemType;
  visibility_mode?: VisibilityMode;
  calendar_sync_policy?: CalendarSyncPolicy;
  sync_target_override_enabled?: boolean;
  timezone?: string;
  couple_attendee_emails?: string[];
  conference_provider?: string;
  conference_url?: string;
  invite_delivery_mode?: InviteDeliveryMode;
  meeting_status?: string;
  sync_target_connection_ids?: string[];
  expected_version?: number;
}

function normalizeForStableStringify(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((entry) => normalizeForStableStringify(entry));
  }
  if (value && typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        acc[key] = normalizeForStableStringify((value as Record<string, unknown>)[key]);
        return acc;
      }, {});
  }
  return value;
}

export function createCalendarMutationIntent(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID();
  }
  return `calendar-intent-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function buildIdempotencyKey(
  intentId: string,
  method: string,
  path: string,
  payload: unknown
): Promise<string> {
  const body = JSON.stringify({
    intentId,
    method,
    path,
    payload: normalizeForStableStringify(payload),
  });
  if (typeof globalThis.crypto?.subtle !== 'undefined') {
    const digest = await globalThis.crypto.subtle.digest(
      'SHA-256',
      new TextEncoder().encode(body)
    );
    const hash = Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('');
    return `calendar-${hash}`;
  }
  return `calendar-${encodeURIComponent(body).slice(0, 180)}`;
}

export interface TeamMemberSummary {
  id: string;
  user_id?: string | null;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  status: string;
  role: string;
  permissions: Record<string, boolean>;
  wedding_access?: 'all' | 'assigned';
  assigned_wedding_ids?: string[];
}

export interface WeddingSummary {
  id: string;
  couple_names: string;
}

function buildQuery(params: Record<string, string | string[] | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined) return;
    if (Array.isArray(value)) {
      value.filter(Boolean).forEach((entry) => search.append(key, entry));
      return;
    }
    if (value !== '') {
      search.set(key, value);
    }
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}

async function authFetch<T>(
  token: string,
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail =
      typeof error.detail === 'string'
        ? error.detail
        : typeof error.detail?.message === 'string'
          ? error.detail.message
          : error.detail
            ? JSON.stringify(error.detail)
            : undefined;
    throw new Error(detail || error.message || 'Request failed');
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function createTask(token: string, task: ScheduleItemPayload): Promise<PlannerTask> {
  return authFetch<PlannerTask>(token, '/admin/planner/calendar/tasks', {
    method: 'POST',
    body: JSON.stringify(task),
  });
}

export async function listTasks(
  token: string,
  filters: TaskFilters = {}
): Promise<TaskListResponse> {
  return authFetch<TaskListResponse>(
    token,
    `/admin/planner/calendar/tasks${buildQuery({
      wedding_id: filters.wedding_id,
      status: filters.status,
      category: filters.category,
      start_date: filters.start_date,
      end_date: filters.end_date,
      page: filters.page ? String(filters.page) : undefined,
      page_size: filters.page_size ? String(filters.page_size) : undefined,
    })}`
  );
}

export async function getTask(token: string, taskId: string): Promise<PlannerTask> {
  return authFetch<PlannerTask>(token, `/admin/planner/calendar/tasks/${taskId}`);
}

export async function updateTask(
  token: string,
  taskId: string,
  updates: Partial<ScheduleItemPayload>
): Promise<PlannerTask> {
  return authFetch<PlannerTask>(token, `/admin/planner/calendar/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

export async function deleteTask(token: string, taskId: string): Promise<void> {
  await authFetch<void>(token, `/admin/planner/calendar/tasks/${taskId}`, {
    method: 'DELETE',
  });
}

export async function syncTaskToGoogle(token: string, taskId: string): Promise<PlannerTask> {
  return authFetch<PlannerTask>(token, `/admin/planner/calendar/tasks/${taskId}/sync`, {
    method: 'POST',
  });
}

export async function bulkUpdateTaskStatus(
  token: string,
  taskIds: string[],
  status: TaskStatus
): Promise<{ updated_count: number; status: string }> {
  return authFetch<{ updated_count: number; status: string }>(
    token,
    `/admin/planner/calendar/tasks/bulk/status?status=${encodeURIComponent(status)}`,
    {
      method: 'PATCH',
      body: JSON.stringify(taskIds),
    }
  );
}

export async function getMonthTasks(
  token: string,
  year: number,
  month: number
): Promise<PlannerTask[]> {
  return authFetch<PlannerTask[]>(token, `/admin/planner/calendar/month/${year}/${month}`);
}

export async function getUpcomingTasks(
  token: string,
  days: number = 7,
  limit: number = 20
): Promise<PlannerTask[]> {
  return authFetch<PlannerTask[]>(
    token,
    `/admin/planner/calendar/upcoming?days=${days}&limit=${limit}`
  );
}

export async function listPlannerWeddings(token: string): Promise<WeddingSummary[]> {
  const data = await authFetch<Array<Record<string, unknown>>>(token, '/admin/planner/weddings');
  return data.map((row) => ({
    id: String(row.id || row._id || ''),
    couple_names: String(row.couple_names || 'Untitled Wedding'),
  }));
}

export async function listTeamMembers(token: string): Promise<TeamMemberSummary[]> {
  const data = await authFetch<{ members: TeamMemberSummary[] }>(token, '/admin/team/members');
  return data.members || [];
}

export async function listCalendarConnections(token: string): Promise<CalendarConnection[]> {
  return authFetch<CalendarConnection[]>(token, '/admin/planner/calendar/connections');
}

export async function beginGoogleCalendarConnect(token: string): Promise<GoogleAuthUrlResponse> {
  return authFetch<GoogleAuthUrlResponse>(
    token,
    '/admin/planner/calendar/connections/google/connect',
    { method: 'POST' }
  );
}

export async function completeGoogleCalendarCallback(
  token: string,
  code: string,
  state: string
): Promise<Record<string, unknown>> {
  return authFetch<Record<string, unknown>>(
    token,
    `/admin/planner/calendar/connections/google/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
  );
}

// ============================================================================
// Aurinko (multi-provider) calendar connect/callback/disconnect.
//
// These hit /admin/planner/calendar/provider/* and replace the Google-only
// pair above for the planner UI's new per-provider buttons. The legacy
// /google/* functions remain so any other caller doesn't break mid-migration.
// ============================================================================

/** Planner-facing provider id pre-selected from a per-provider button. */
export type CalendarProviderId = 'google' | 'office365' | 'icloud' | 'ews';

export interface ProviderAuthUrlResponse {
  auth_url: string;
  message: string;
}

export interface ProviderCallbackCalendar {
  aurinko_calendar_id: string;
  name: string;
  access_role?: string | null;
  is_writable: boolean;
  is_primary: boolean;
  suggested_default_write: boolean;
}

export interface ProviderCallbackResponse {
  connected: boolean;
  calendar_id?: string | null;
  connections_created?: number;
  redirect_to?: string | null;
  message: string;
  warning?: string | null;
  /** Option-B picker fields — present on the OAuth callback hop, then
   *  cleared on /connections/select. Branch on ``needs_selection``. */
  needs_selection?: boolean;
  draft_id?: string | null;
  account_email?: string | null;
  account_name?: string | null;
  provider?: string | null;
  calendars?: ProviderCallbackCalendar[];
}

export interface CalendarSelectionPick {
  aurinko_calendar_id: string;
  is_default_write_target?: boolean;
  details_visibility?: 'details' | 'busy_only';
  is_shared_in_team_view?: boolean;
}

/** Build an Aurinko hosted-auth URL. When ``serviceType`` is set, Aurinko
 *  skips its picker and jumps to that provider's OAuth screen. When omitted
 *  (or null), the user gets Aurinko's provider chooser. */
export async function beginCalendarConnect(
  token: string,
  serviceType?: CalendarProviderId | null
): Promise<ProviderAuthUrlResponse> {
  const qs = serviceType ? `?service_type=${encodeURIComponent(serviceType)}` : '';
  return authFetch<ProviderAuthUrlResponse>(
    token,
    `/admin/planner/calendar/provider/connect${qs}`
  );
}

/** Exchange the ``code`` + ``state`` returned by Aurinko's callback for an
 *  account token. Under Option B, this DOES NOT yet create per-calendar
 *  connection rows; it returns a draft id + a calendar list for the
 *  picker modal. The actual rows + Aurinko webhook subscriptions are
 *  created when the picker submits to ``selectCalendars``. */
export async function completeCalendarCallback(
  token: string,
  code: string,
  state: string
): Promise<ProviderCallbackResponse> {
  return authFetch<ProviderCallbackResponse>(
    token,
    `/admin/planner/calendar/connections/provider/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
  );
}

/** Submit the planner's picker choices. The backend drains the draft
 *  identified by ``draftId`` into ``calendar_connections`` rows (one
 *  per picked calendar) and registers Aurinko webhook subscriptions
 *  for writable picks. Empty ``picks`` is the "Skip for now" path —
 *  the draft is deleted, zero rows are created. */
export async function selectCalendars(
  token: string,
  draftId: string,
  picks: CalendarSelectionPick[]
): Promise<ProviderCallbackResponse> {
  return authFetch<ProviderCallbackResponse>(
    token,
    `/admin/planner/calendar/connections/select`,
    {
      method: 'POST',
      body: JSON.stringify({ draft_id: draftId, picks }),
    }
  );
}

/** Tear down every connected calendar for the current user (unsubscribes
 *  per-calendar Aurinko subscriptions, revokes the account token, marks
 *  dependent sync rows ORPHANED, deletes local connection rows). */
export async function disconnectCalendar(
  token: string
): Promise<{ disconnected: boolean; message?: string }> {
  return authFetch<{ disconnected: boolean; message?: string }>(
    token,
    '/admin/planner/calendar/provider/disconnect',
    { method: 'DELETE' }
  );
}

export async function updateCalendarConnection(
  token: string,
  connectionId: string,
  updates: Partial<
    Pick<
      CalendarConnection,
      | 'allowed_scheduler_user_ids'
      | 'allowed_scheduler_roles'
      | 'allowed_schedule_item_types'
      | 'allowed_wedding_ids'
      | 'scheduler_access_mode'
      | 'sync_targeting_mode'
      | 'is_shared_in_team_view'
      | 'details_visibility'
      | 'sync_enabled'
      | 'is_default_write_target'
    >
  >
): Promise<CalendarConnection> {
  return authFetch<CalendarConnection>(
    token,
    `/admin/planner/calendar/connections/${connectionId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }
  );
}

export async function disconnectCalendarConnection(
  token: string,
  connectionId: string
): Promise<void> {
  await authFetch<void>(token, `/admin/planner/calendar/connections/${connectionId}`, {
    method: 'DELETE',
  });
}

export async function healthcheckCalendarConnection(
  token: string,
  connectionId: string
): Promise<CalendarConnection> {
  return authFetch<CalendarConnection>(
    token,
    `/admin/planner/calendar/connections/${connectionId}/healthcheck`,
    {
      method: 'POST',
    }
  );
}

export async function getSharedCalendarView(
  token: string,
  filters: SharedCalendarFilters = {}
): Promise<SharedCalendarEvent[]> {
  return authFetch<SharedCalendarEvent[]>(
    token,
    `/admin/planner/calendar/view${buildQuery({
      start: filters.start,
      end: filters.end,
      wedding_ids: filters.wedding_ids,
      staff_ids: filters.staff_ids,
      source_types: filters.source_types,
    })}`
  );
}

export async function getStaffAvailability(
  token: string,
  staffIds: string[],
  start: string,
  end: string
): Promise<AvailabilityResponse> {
  return authFetch<AvailabilityResponse>(
    token,
    `/admin/planner/calendar/availability${buildQuery({
      staff_ids: staffIds,
      start,
      end,
    })}`
  );
}

export async function createMeeting(
  token: string,
  payload: ScheduleItemPayload,
  mutationIntent: string
): Promise<MeetingUpsertResponse> {
  const path = '/admin/planner/calendar/meetings';
  return authFetch<MeetingUpsertResponse>(token, '/admin/planner/calendar/meetings', {
    method: 'POST',
    headers: {
      'Idempotency-Key': await buildIdempotencyKey(mutationIntent, 'POST', path, payload),
    },
    body: JSON.stringify(payload),
  });
}

export async function updateMeeting(
  token: string,
  meetingId: string,
  payload: Partial<ScheduleItemPayload>,
  mutationIntent: string
): Promise<MeetingUpsertResponse> {
  const path = `/admin/planner/calendar/meetings/${meetingId}`;
  return authFetch<MeetingUpsertResponse>(
    token,
    `/admin/planner/calendar/meetings/${meetingId}`,
    {
      method: 'PATCH',
      headers: {
        'Idempotency-Key': await buildIdempotencyKey(mutationIntent, 'PATCH', path, payload),
      },
      body: JSON.stringify(payload),
    }
  );
}

export async function deleteMeeting(
  token: string,
  meetingId: string,
  expectedVersion: number,
  mutationIntent: string
): Promise<void> {
  const path = `/admin/planner/calendar/meetings/${meetingId}`;
  await authFetch<void>(
    token,
    `/admin/planner/calendar/meetings/${meetingId}${buildQuery({
      expected_version: String(expectedVersion),
    })}`,
    {
      method: 'DELETE',
      headers: {
        'Idempotency-Key': await buildIdempotencyKey(mutationIntent, 'DELETE', path, {
          expected_version: expectedVersion,
        }),
      },
    }
  );
}

export async function sendMeetingInvites(
  token: string,
  meetingId: string
): Promise<Array<Record<string, unknown>>> {
  return authFetch<Array<Record<string, unknown>>>(
    token,
    `/admin/planner/calendar/meetings/${meetingId}/send-invites`,
    {
      method: 'POST',
    }
  );
}

export async function syncMeeting(
  token: string,
  meetingId: string
): Promise<CalendarSyncStatusItem[]> {
  return authFetch<CalendarSyncStatusItem[]>(
    token,
    `/admin/planner/calendar/meetings/${meetingId}/sync`,
    {
      method: 'POST',
    }
  );
}

export async function getMeetingSyncStatus(
  token: string,
  meetingId: string
): Promise<CalendarSyncStatusItem[]> {
  return authFetch<CalendarSyncStatusItem[]>(
    token,
    `/admin/planner/calendar/meetings/${meetingId}/sync-status`
  );
}

export const CATEGORY_LABELS: Record<TaskCategory, string> = {
  venue: 'Venue',
  catering: 'Catering',
  photography: 'Photography',
  videography: 'Videography',
  music: 'Music & Entertainment',
  flowers: 'Flowers & Decor',
  attire: 'Attire & Beauty',
  invitations: 'Invitations & Stationery',
  transportation: 'Transportation',
  accommodation: 'Accommodation',
  ceremony: 'Ceremony',
  reception: 'Reception',
  honeymoon: 'Honeymoon',
  legal: 'Legal & Documents',
  budget: 'Budget & Payments',
  guest_management: 'Guest Management',
  meeting: 'Couple Meeting',
  other: 'Other',
};

export const PRIORITY_CONFIG: Record<
  TaskPriority,
  { label: string; color: string; bgColor: string }
> = {
  low: { label: 'Low', color: 'text-gray-600', bgColor: 'bg-gray-100' },
  medium: { label: 'Medium', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  high: { label: 'High', color: 'text-orange-600', bgColor: 'bg-orange-100' },
  urgent: { label: 'Urgent', color: 'text-red-600', bgColor: 'bg-red-100' },
};

export const STATUS_CONFIG: Record<
  TaskStatus,
  { label: string; color: string; bgColor: string }
> = {
  pending: { label: 'Pending', color: 'text-gray-600', bgColor: 'bg-gray-100' },
  in_progress: { label: 'In Progress', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  completed: { label: 'Completed', color: 'text-green-600', bgColor: 'bg-green-100' },
  cancelled: { label: 'Cancelled', color: 'text-red-600', bgColor: 'bg-red-100' },
};

export function formatTaskDate(dateString: string, includeTime: boolean = false): string {
  const date = new Date(dateString);
  const options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  };

  if (includeTime) {
    options.hour = 'numeric';
    options.minute = '2-digit';
  }

  return date.toLocaleDateString('en-US', options);
}

export function getDaysUntil(dateString: string): number {
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = date.getTime() - now.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}
