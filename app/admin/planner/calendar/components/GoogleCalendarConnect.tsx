'use client';

import React, { useMemo, useState } from 'react';
import {
  beginGoogleCalendarConnect,
  CalendarConnection,
  disconnectCalendarConnection,
  healthcheckCalendarConnection,
  updateCalendarConnection,
} from '@/services/calendarApi';
import type {
  CalendarSchedulerAccessMode,
  CalendarSyncTargetingMode,
} from '@/services/calendarApi';
import { useAdmin } from '@/contexts/AdminContext';
import { useConfirmDialog } from '@/components/ui/ConfirmDialog';
import { formatAdminTimestamp } from '@/utils/dateFormat';
import { toast } from 'sonner';

interface StaffOption {
  id: string;
  email: string;
  label: string;
  role?: string;
}

interface GoogleCalendarConnectProps {
  connections: CalendarConnection[];
  staffOptions?: StaffOption[];
  weddings?: Array<{ id: string; couple_names: string }>;
  loading?: boolean;
  onRefresh: () => Promise<void> | void;
}

const SCHEDULER_ROLE_OPTIONS: Array<{
  value: 'owner' | 'admin' | 'editor' | 'viewer';
  label: string;
}> = [
  { value: 'owner', label: 'Owner' },
  { value: 'admin', label: 'Admin' },
  { value: 'editor', label: 'Editor' },
  { value: 'viewer', label: 'Viewer' },
];

const SCHEDULE_ITEM_TYPE_OPTIONS: Array<{
  value: 'task' | 'meeting' | 'blocked_time';
  label: string;
}> = [
  { value: 'task', label: 'Tasks' },
  { value: 'meeting', label: 'Meetings' },
  { value: 'blocked_time', label: 'Blocked time' },
];

const SCHEDULER_ACCESS_MODE_OPTIONS: Array<{
  value: CalendarSchedulerAccessMode;
  label: string;
  description: string;
}> = [
  {
    value: 'workspace_default',
    label: 'Workspace default',
    description:
      'Owner calendars are available to permitted team schedulers. Staff calendars stay limited to the owner and the connected staff user unless extra user grants are added.',
  },
  {
    value: 'owner_only',
    label: 'Owner only',
    description:
      'Only the planner owner can target this calendar unless you add specific user grants.',
  },
  {
    value: 'owner_and_connection_user',
    label: 'Owner + connected user',
    description:
      'Only the planner owner and the workspace user who connected this calendar can target it unless you add specific user grants.',
  },
  {
    value: 'workspace_permitted',
    label: 'Any permitted scheduler',
    description:
      'Any workspace scheduler inside owner scope can target this calendar, then role, item-type, and wedding filters narrow access.',
  },
];

const SYNC_TARGETING_MODE_OPTIONS: Array<{
  value: CalendarSyncTargetingMode;
  label: string;
  description: string;
}> = [
  {
    value: 'automatic_and_manual',
    label: 'Automatic + manual',
    description:
      'This calendar can be selected automatically by sync policy and by explicit scheduler override.',
  },
  {
    value: 'manual_only',
    label: 'Manual override only',
    description:
      'This calendar is never auto-selected by sync policy. It can only be used when a scheduler explicitly picks it.',
  },
];

const PANEL_CLASS =
  'rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800';
const SUBTLE_PANEL_CLASS =
  'rounded-2xl border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60';
const INPUT_CLASS =
  'w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-xs text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100';
const SECONDARY_BUTTON_CLASS =
  'rounded-xl border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-60 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60';
const TOGGLE_CARD_CLASS =
  'rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200';

function statusTone(status: string) {
  switch (status) {
    case 'active':
      return 'text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-200 dark:bg-emerald-950/40 dark:border-emerald-900';
    case 'expired':
      return 'text-amber-700 bg-amber-50 border-amber-200 dark:text-amber-200 dark:bg-amber-950/40 dark:border-amber-900';
    case 'error':
      return 'text-rose-700 bg-rose-50 border-rose-200 dark:text-rose-200 dark:bg-rose-950/40 dark:border-rose-900';
    case 'revoked':
      return 'text-slate-600 bg-slate-100 border-slate-200 dark:text-slate-300 dark:bg-slate-700/70 dark:border-slate-600';
    default:
      return 'text-slate-600 bg-slate-100 border-slate-200 dark:text-slate-300 dark:bg-slate-700/70 dark:border-slate-600';
  }
}

function visibilityLabel(mode: string) {
  return mode === 'details' ? 'Full details' : 'Busy/free';
}

export default function GoogleCalendarConnect({
  connections,
  staffOptions = [],
  weddings = [],
  loading = false,
  onRefresh,
}: GoogleCalendarConnectProps) {
  const { token } = useAdmin();
  const { confirm } = useConfirmDialog();
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [error, setError] = useState('');

  const groupedConnections = useMemo(() => {
    const groups = new Map<string, CalendarConnection[]>();

    connections.forEach((connection) => {
      const key = connection.provider_account_email || connection.user_email || connection.id;
      const current = groups.get(key) || [];
      current.push(connection);
      groups.set(key, current);
    });

    return Array.from(groups.entries()).map(([accountEmail, rows]) => ({
      accountEmail,
      rows: rows.sort((left, right) => {
        if (left.is_default_write_target) return -1;
        if (right.is_default_write_target) return 1;
        if (left.is_primary) return -1;
        if (right.is_primary) return 1;
        return (left.calendar_name || '').localeCompare(right.calendar_name || '');
      }),
    }));
  }, [connections]);

  const activeConnections = connections.filter((connection) => connection.connection_status === 'active');
  const sharedConnections = connections.filter((connection) => connection.is_shared_in_team_view);

  const withAction = async (actionKey: string, fn: () => Promise<void>) => {
    setActiveAction(actionKey);
    setError('');
    try {
      await fn();
      await onRefresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Request failed';
      setError(message);
      toast.error(message);
    } finally {
      setActiveAction(null);
    }
  };

  const handleConnect = async () => {
    if (!token) return;

    setActiveAction('connect');
    setError('');
    try {
      const { auth_url } = await beginGoogleCalendarConnect(token);
      window.location.href = auth_url;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to start Google Calendar connection';
      setError(message);
      setActiveAction(null);
    }
  };

  const handleDisconnect = async (connection: CalendarConnection) => {
    if (!token) return;

    const confirmed = await confirm({
      title: 'Disconnect Google Calendar',
      message:
        'Disconnect this calendar connection? Internal meetings stay in the platform, but external sync stops and Google access is revoked when applicable.',
      variant: 'warning',
      confirmText: 'Disconnect',
      cancelText: 'Cancel',
    });

    if (!confirmed) return;

    await withAction(`disconnect:${connection.id}`, async () => {
      await disconnectCalendarConnection(token, connection.id);
      toast.success('Calendar connection removed');
    });
  };

  const handleHealthcheck = async (connection: CalendarConnection) => {
    if (!token) return;

    await withAction(`health:${connection.id}`, async () => {
      await healthcheckCalendarConnection(token, connection.id);
      toast.success('Connection health refreshed');
    });
  };

  const handleToggle = async (
    connection: CalendarConnection,
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
    >,
    successMessage: string
  ) => {
    if (!token) return;

    await withAction(`update:${connection.id}:${Object.keys(updates).join(',')}`, async () => {
      await updateCalendarConnection(token, connection.id, updates);
      toast.success(successMessage);
    });
  };

  const handleSchedulerToggle = async (
    connection: CalendarConnection,
    schedulerUserId: string
  ) => {
    const currentIds = connection.allowed_scheduler_user_ids || [];
    const nextIds = currentIds.includes(schedulerUserId)
      ? currentIds.filter((value) => value !== schedulerUserId)
      : [...currentIds, schedulerUserId];

    await handleToggle(
      connection,
      { allowed_scheduler_user_ids: nextIds },
      'Calendar scheduler access updated'
    );
  };

  const handleSchedulerRoleToggle = async (
    connection: CalendarConnection,
    schedulerRole: 'owner' | 'admin' | 'editor' | 'viewer'
  ) => {
    const currentRoles = connection.allowed_scheduler_roles || [];
    const nextRoles = currentRoles.includes(schedulerRole)
      ? currentRoles.filter((value) => value !== schedulerRole)
      : [...currentRoles, schedulerRole];

    await handleToggle(
      connection,
      { allowed_scheduler_roles: nextRoles },
      'Calendar scheduler roles updated'
    );
  };

  const handleSchedulerAccessModeChange = async (
    connection: CalendarConnection,
    schedulerAccessMode: CalendarSchedulerAccessMode
  ) => {
    await handleToggle(
      connection,
      { scheduler_access_mode: schedulerAccessMode },
      'Calendar scheduling policy updated'
    );
  };

  const handleSyncTargetingModeChange = async (
    connection: CalendarConnection,
    syncTargetingMode: CalendarSyncTargetingMode
  ) => {
    await handleToggle(
      connection,
      { sync_targeting_mode: syncTargetingMode },
      'Calendar targeting mode updated'
    );
  };

  const handleScheduleItemTypeToggle = async (
    connection: CalendarConnection,
    scheduleItemType: 'task' | 'meeting' | 'blocked_time'
  ) => {
    const currentTypes = connection.allowed_schedule_item_types || [];
    const nextTypes = currentTypes.includes(scheduleItemType)
      ? currentTypes.filter((value) => value !== scheduleItemType)
      : [...currentTypes, scheduleItemType];

    await handleToggle(
      connection,
      { allowed_schedule_item_types: nextTypes },
      'Calendar item policy updated'
    );
  };

  const handleWeddingScopeToggle = async (
    connection: CalendarConnection,
    weddingId: string
  ) => {
    const currentWeddingIds = connection.allowed_wedding_ids || [];
    const nextWeddingIds = currentWeddingIds.includes(weddingId)
      ? currentWeddingIds.filter((value) => value !== weddingId)
      : [...currentWeddingIds, weddingId];

    await handleToggle(
      connection,
      { allowed_wedding_ids: nextWeddingIds },
      'Calendar wedding scope updated'
    );
  };

  if (loading) {
    return (
      <div className={`${PANEL_CLASS} p-6`}>
        <div className="flex items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-slate-700 dark:border-slate-700 dark:border-t-slate-200" />
          Loading calendar connections...
        </div>
      </div>
    );
  }

  return (
    <section className={PANEL_CLASS}>
      <div className="flex flex-col gap-4 border-b border-slate-200 px-6 py-5 dark:border-slate-700 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900">
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19.5 3h-15A1.5 1.5 0 003 4.5v15A1.5 1.5 0 004.5 21h15a1.5 1.5 0 001.5-1.5v-15A1.5 1.5 0 0019.5 3zM12 17.25a5.25 5.25 0 110-10.5 5.25 5.25 0 010 10.5z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Google Calendar Connections</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Shared view is opt-in per connection. Personal external calendars stay busy/free
                only unless the owner enables full details.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3 text-xs text-slate-600 dark:text-slate-300">
            <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-700/70">
              {activeConnections.length} active
            </span>
            <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-700/70">
              {sharedConnections.length} shared in team view
            </span>
          </div>
        </div>

        <button
          onClick={handleConnect}
          disabled={activeAction === 'connect'}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
        >
          {activeAction === 'connect' ? (
            <>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              Connecting...
            </>
          ) : (
            'Connect Google Calendar'
          )}
        </button>
      </div>

      {error && (
        <div className="mx-6 mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          {error}
        </div>
      )}

      <div className="space-y-5 px-6 py-5">
        {groupedConnections.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center dark:border-slate-600 dark:bg-slate-900/50">
            <h4 className="text-base font-semibold text-slate-900 dark:text-slate-100">No calendars connected yet</h4>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Connect the planner owner or a permitted team member account to enable shared
              visibility, assigned-staff sync targets, and availability checks.
            </p>
          </div>
        ) : (
          groupedConnections.map((group) => (
            <div key={group.accountEmail} className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{group.accountEmail}</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {group.rows[0]?.provider_account_name || 'Google account'} •{' '}
                    {group.rows[0]?.user_email || 'Workspace user'}
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                {group.rows.map((connection) => {
                  const updateLoading =
                    activeAction?.startsWith(`update:${connection.id}`) ||
                    activeAction === `disconnect:${connection.id}` ||
                    activeAction === `health:${connection.id}`;

                  return (
                    <div
                      key={connection.id}
                      className={`${SUBTLE_PANEL_CLASS} p-4`}
                    >
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <h5 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                              {connection.calendar_name || connection.calendar_id || 'Unnamed calendar'}
                            </h5>
                            <span
                              className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${statusTone(connection.connection_status)}`}
                            >
                              {connection.connection_status}
                            </span>
                            {connection.is_default_write_target && (
                              <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-medium text-white dark:bg-slate-100 dark:text-slate-900">
                                Default write
                              </span>
                            )}
                            {connection.is_primary && (
                              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                                Primary
                              </span>
                            )}
                            {!connection.is_writable && (
                              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                                Read only
                              </span>
                            )}
                          </div>

                          <div className="grid gap-2 text-xs text-slate-500 dark:text-slate-400 sm:grid-cols-2 xl:grid-cols-4">
                            <p>Workspace user: {connection.user_email || 'Unknown'}</p>
                            <p>Access role: {connection.access_role || 'Unknown'}</p>
                            <p>Visibility: {visibilityLabel(connection.details_visibility)}</p>
                            <p>
                              Last healthcheck:{' '}
                              {connection.last_healthcheck_at
                                ? formatAdminTimestamp(connection.last_healthcheck_at)
                                : 'Not checked'}
                            </p>
                          </div>

                          {connection.last_error && (
                            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                              {connection.last_error}
                            </p>
                          )}

                          {connection.is_writable && (
                            <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
                              <div className="flex flex-col gap-1">
                                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                                  Scheduler access
                                </p>
                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                  Precedence is fixed: base scheduling access, then extra user
                                  grants, then restrictive role, item-type, and wedding filters,
                                  then targeting mode, and only then sync policy chooses targets.
                                </p>
                              </div>

                              <label className="block rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200">
                                <span className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
                                  Base scheduling access
                                </span>
                                <select
                                  value={connection.scheduler_access_mode}
                                  onChange={(event) =>
                                    void handleSchedulerAccessModeChange(
                                      connection,
                                      event.target.value as CalendarSchedulerAccessMode
                                    )
                                  }
                                  disabled={updateLoading}
                                  className={INPUT_CLASS}
                                >
                                  {SCHEDULER_ACCESS_MODE_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </select>
                                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                                  {
                                    SCHEDULER_ACCESS_MODE_OPTIONS.find(
                                      (option) => option.value === connection.scheduler_access_mode
                                    )?.description
                                  }
                                </p>
                              </label>

                              <label className="block rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200">
                                <span className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
                                  Targeting mode
                                </span>
                                <select
                                  value={connection.sync_targeting_mode}
                                  onChange={(event) =>
                                    void handleSyncTargetingModeChange(
                                      connection,
                                      event.target.value as CalendarSyncTargetingMode
                                    )
                                  }
                                  disabled={updateLoading}
                                  className={INPUT_CLASS}
                                >
                                  {SYNC_TARGETING_MODE_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </select>
                                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                                  {
                                    SYNC_TARGETING_MODE_OPTIONS.find(
                                      (option) => option.value === connection.sync_targeting_mode
                                    )?.description
                                  }
                                </p>
                              </label>

                              {staffOptions.length > 0 ? (
                                <div>
                                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
                                    Extra user grants
                                  </p>
                                  <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
                                    Use this to allow specific staff onto a calendar even when the
                                    base access mode would normally block them.
                                  </p>
                                  <div className="flex flex-wrap gap-2">
                                    {staffOptions.map((staff) => {
                                      const checked = connection.allowed_scheduler_user_ids.includes(
                                        staff.id
                                      );
                                      return (
                                        <label
                                          key={`${connection.id}-${staff.id}`}
                                          className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-700 dark:border-slate-700 dark:text-slate-200"
                                        >
                                          <input
                                            type="checkbox"
                                            checked={checked}
                                            onChange={() =>
                                              void handleSchedulerToggle(connection, staff.id)
                                            }
                                            disabled={updateLoading}
                                            className="h-3.5 w-3.5 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                                          />
                                          {staff.label}
                                        </label>
                                      );
                                    })}
                                  </div>
                                </div>
                              ) : null}

                              <div>
                                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
                                  Allowed roles
                                </p>
                                <div className="flex flex-wrap gap-2">
                                  {SCHEDULER_ROLE_OPTIONS.map((role) => {
                                    const checked = connection.allowed_scheduler_roles.includes(
                                      role.value
                                    );
                                    return (
                                      <label
                                        key={`${connection.id}-${role.value}`}
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-700 dark:border-slate-700 dark:text-slate-200"
                                      >
                                        <input
                                          type="checkbox"
                                          checked={checked}
                                          onChange={() =>
                                            void handleSchedulerRoleToggle(connection, role.value)
                                          }
                                          disabled={updateLoading}
                                          className="h-3.5 w-3.5 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                                        />
                                        {role.label}
                                      </label>
                                    );
                                  })}
                                </div>
                              </div>

                              <div>
                                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
                                  Allowed item types
                                </p>
                                <div className="flex flex-wrap gap-2">
                                  {SCHEDULE_ITEM_TYPE_OPTIONS.map((itemType) => {
                                    const checked =
                                      connection.allowed_schedule_item_types.includes(
                                        itemType.value
                                      );
                                    return (
                                      <label
                                        key={`${connection.id}-${itemType.value}`}
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-700 dark:border-slate-700 dark:text-slate-200"
                                      >
                                        <input
                                          type="checkbox"
                                          checked={checked}
                                          onChange={() =>
                                            void handleScheduleItemTypeToggle(
                                              connection,
                                              itemType.value
                                            )
                                          }
                                          disabled={updateLoading}
                                          className="h-3.5 w-3.5 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                                        />
                                        {itemType.label}
                                      </label>
                                    );
                                  })}
                                </div>
                              </div>

                              {weddings.length > 0 ? (
                                <div>
                                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
                                    Wedding scope
                                  </p>
                                  <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
                                    Leave empty to allow all workspace weddings on this calendar.
                                  </p>
                                  <div className="flex flex-wrap gap-2">
                                    {weddings.map((wedding) => {
                                      const checked = connection.allowed_wedding_ids.includes(
                                        wedding.id
                                      );
                                      return (
                                        <label
                                          key={`${connection.id}-${wedding.id}`}
                                          className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-700 dark:border-slate-700 dark:text-slate-200"
                                        >
                                          <input
                                            type="checkbox"
                                            checked={checked}
                                            onChange={() =>
                                              void handleWeddingScopeToggle(connection, wedding.id)
                                            }
                                            disabled={updateLoading}
                                            className="h-3.5 w-3.5 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                                          />
                                          {wedding.couple_names}
                                        </label>
                                      );
                                    })}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          )}
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={() => handleHealthcheck(connection)}
                            disabled={updateLoading}
                            className={SECONDARY_BUTTON_CLASS}
                          >
                            Check health
                          </button>
                          <button
                            onClick={() => handleDisconnect(connection)}
                            disabled={updateLoading}
                            className="rounded-xl border border-rose-300 px-3 py-2 text-xs font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-60 dark:border-rose-900 dark:text-rose-200 dark:hover:bg-rose-950/40"
                          >
                            Disconnect
                          </button>
                        </div>
                      </div>

                      <div className="mt-4 grid gap-3 border-t border-slate-200 pt-4 dark:border-slate-700 md:grid-cols-2 xl:grid-cols-4">
                        <label className={`flex items-center justify-between gap-3 ${TOGGLE_CARD_CLASS}`}>
                          Shared in team view
                          <input
                            type="checkbox"
                            checked={connection.is_shared_in_team_view}
                            onChange={(event) =>
                              handleToggle(
                                connection,
                                { is_shared_in_team_view: event.target.checked },
                                event.target.checked
                                  ? 'Calendar shared in team view'
                                  : 'Calendar hidden from team view'
                              )
                            }
                            disabled={updateLoading}
                            className="h-4 w-4 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                          />
                        </label>

                        <label className={`flex items-center justify-between gap-3 ${TOGGLE_CARD_CLASS}`}>
                          Sync enabled
                          <input
                            type="checkbox"
                            checked={connection.sync_enabled}
                            onChange={(event) =>
                              handleToggle(
                                connection,
                                { sync_enabled: event.target.checked },
                                event.target.checked ? 'Sync enabled' : 'Sync disabled'
                              )
                            }
                            disabled={updateLoading || !connection.is_writable}
                            className="h-4 w-4 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                          />
                        </label>

                        <label className={TOGGLE_CARD_CLASS}>
                          <span className="mb-2 block">Visibility mode</span>
                          <select
                            value={connection.details_visibility}
                            onChange={(event) =>
                              handleToggle(
                                connection,
                                {
                                  details_visibility: event.target.value as 'details' | 'busy_only',
                                },
                                'Visibility mode updated'
                              )
                            }
                            disabled={updateLoading}
                            className={INPUT_CLASS}
                          >
                            <option value="busy_only">Busy/free only</option>
                            <option value="details">Full details</option>
                          </select>
                        </label>

                        <div className={TOGGLE_CARD_CLASS}>
                          <span className="mb-2 block">Default write target</span>
                          <button
                            onClick={() =>
                              handleToggle(
                                connection,
                                { is_default_write_target: true },
                                'Default write target updated'
                              )
                            }
                            disabled={updateLoading || !connection.is_writable}
                            className="w-full rounded-lg border border-slate-300 px-3 py-2 font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-60 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60"
                          >
                            {connection.is_default_write_target ? 'Selected' : 'Set as default'}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
