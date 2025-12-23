/**
 * Calendar API client for planner task management and Google Calendar integration.
 */
import { getApiBaseUrl } from '@/utils/env';

const BASE_URL = getApiBaseUrl();

// ============================================================================
// Types
// ============================================================================

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
  | 'other';

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
  google_event_id?: string | null;
  synced_to_google: boolean;
  is_recurring: boolean;
  recurrence_rule?: string | null;
  color?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface TaskListResponse {
  tasks: PlannerTask[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateTaskInput {
  title: string;
  description?: string;
  wedding_id?: string;
  category?: TaskCategory;
  priority?: TaskPriority;
  start_date: string; // ISO datetime string
  end_date?: string;
  all_day?: boolean;
  due_date?: string;
  reminder_minutes?: number;
  is_recurring?: boolean;
  recurrence_rule?: string;
  color?: string;
  notes?: string;
  sync_to_google?: boolean;
}

export interface UpdateTaskInput {
  title?: string;
  description?: string;
  wedding_id?: string;
  category?: string;
  priority?: string;
  status?: TaskStatus;
  start_date?: string;
  end_date?: string;
  all_day?: boolean;
  due_date?: string;
  reminder_minutes?: number;
  is_recurring?: boolean;
  recurrence_rule?: string;
  color?: string;
  notes?: string;
}

export interface GoogleCalendarStatus {
  connected: boolean;
  calendar_id?: string | null;
  last_sync?: string | null;
  sync_enabled: boolean;
  events_synced: number;
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

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get Google Calendar connection status for the current user.
 */
export async function getGoogleCalendarStatus(token: string): Promise<GoogleCalendarStatus> {
  const response = await fetch(`${BASE_URL}/admin/planner/calendar/google/status`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to get Google Calendar status');
  }

  return response.json();
}

/**
 * Get the Google OAuth authorization URL to connect calendar.
 */
export async function getGoogleAuthUrl(token: string): Promise<GoogleAuthUrlResponse> {
  const response = await fetch(`${BASE_URL}/admin/planner/calendar/google/connect`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to get Google auth URL');
  }

  return response.json();
}

/**
 * Disconnect Google Calendar for the current user.
 */
export async function disconnectGoogleCalendar(token: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/admin/planner/calendar/google/disconnect`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to disconnect Google Calendar');
  }
}

/**
 * Fetch events from connected Google Calendar.
 */
export async function fetchGoogleEvents(
  token: string,
  daysAhead: number = 30
): Promise<unknown[]> {
  const response = await fetch(
    `${BASE_URL}/admin/planner/calendar/google/events?days_ahead=${daysAhead}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    throw new Error('Failed to fetch Google events');
  }

  return response.json();
}

/**
 * Create a new task/event.
 */
export async function createTask(token: string, task: CreateTaskInput): Promise<PlannerTask> {
  const response = await fetch(`${BASE_URL}/admin/planner/calendar/tasks`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(task),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to create task');
  }

  return response.json();
}

/**
 * List tasks with optional filters.
 */
export async function listTasks(
  token: string,
  filters: TaskFilters = {}
): Promise<TaskListResponse> {
  const params = new URLSearchParams();

  if (filters.wedding_id) params.set('wedding_id', filters.wedding_id);
  if (filters.status) params.set('status', filters.status);
  if (filters.category) params.set('category', filters.category);
  if (filters.start_date) params.set('start_date', filters.start_date);
  if (filters.end_date) params.set('end_date', filters.end_date);
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));

  const queryString = params.toString();
  const url = `${BASE_URL}/admin/planner/calendar/tasks${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to list tasks');
  }

  return response.json();
}

/**
 * Get a single task by ID.
 */
export async function getTask(token: string, taskId: string): Promise<PlannerTask> {
  const response = await fetch(`${BASE_URL}/admin/planner/calendar/tasks/${taskId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to get task');
  }

  return response.json();
}

/**
 * Update a task.
 */
export async function updateTask(
  token: string,
  taskId: string,
  updates: UpdateTaskInput
): Promise<PlannerTask> {
  const response = await fetch(`${BASE_URL}/admin/planner/calendar/tasks/${taskId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to update task');
  }

  return response.json();
}

/**
 * Delete a task.
 */
export async function deleteTask(token: string, taskId: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/admin/planner/calendar/tasks/${taskId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to delete task');
  }
}

/**
 * Manually sync a task to Google Calendar.
 */
export async function syncTaskToGoogle(token: string, taskId: string): Promise<PlannerTask> {
  const response = await fetch(`${BASE_URL}/admin/planner/calendar/tasks/${taskId}/sync`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to sync task to Google Calendar');
  }

  return response.json();
}

/**
 * Bulk update task statuses.
 */
export async function bulkUpdateTaskStatus(
  token: string,
  taskIds: string[],
  status: TaskStatus
): Promise<{ updated_count: number; status: string }> {
  const params = new URLSearchParams();
  params.set('status', status);

  const response = await fetch(
    `${BASE_URL}/admin/planner/calendar/tasks/bulk/status?${params.toString()}`,
    {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(taskIds),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to bulk update tasks');
  }

  return response.json();
}

/**
 * Get tasks for a specific month (for calendar view).
 */
export async function getMonthTasks(
  token: string,
  year: number,
  month: number
): Promise<PlannerTask[]> {
  const response = await fetch(`${BASE_URL}/admin/planner/calendar/month/${year}/${month}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to get month tasks');
  }

  return response.json();
}

/**
 * Get upcoming tasks for dashboard widget.
 */
export async function getUpcomingTasks(
  token: string,
  days: number = 7,
  limit: number = 20
): Promise<PlannerTask[]> {
  const response = await fetch(
    `${BASE_URL}/admin/planner/calendar/upcoming?days=${days}&limit=${limit}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    throw new Error('Failed to get upcoming tasks');
  }

  return response.json();
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Category display labels.
 */
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
  other: 'Other',
};

/**
 * Priority display labels with colors.
 */
export const PRIORITY_CONFIG: Record<TaskPriority, { label: string; color: string; bgColor: string }> = {
  low: { label: 'Low', color: 'text-gray-600', bgColor: 'bg-gray-100' },
  medium: { label: 'Medium', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  high: { label: 'High', color: 'text-orange-600', bgColor: 'bg-orange-100' },
  urgent: { label: 'Urgent', color: 'text-red-600', bgColor: 'bg-red-100' },
};

/**
 * Status display labels with colors.
 */
export const STATUS_CONFIG: Record<TaskStatus, { label: string; color: string; bgColor: string }> = {
  pending: { label: 'Pending', color: 'text-gray-600', bgColor: 'bg-gray-100' },
  in_progress: { label: 'In Progress', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  completed: { label: 'Completed', color: 'text-green-600', bgColor: 'bg-green-100' },
  cancelled: { label: 'Cancelled', color: 'text-red-600', bgColor: 'bg-red-100' },
};

/**
 * Format a date for display.
 */
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

/**
 * Get days until a date.
 */
export function getDaysUntil(dateString: string): number {
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = date.getTime() - now.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}
