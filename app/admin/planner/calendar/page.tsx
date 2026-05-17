'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { useAdmin } from '@/contexts/AdminContext';
import { useConfirmDialog } from '@/components/ui/ConfirmDialog';
import PageHeader from '../../components/PageHeader';
import TaskModal from './components/TaskModal';
import CalendarConnect from './components/CalendarConnect';
import CalendarStatusPill from './components/CalendarStatusPill';
import CalendarRightRail from './components/CalendarRightRail';
import DaySlideOver from './components/DaySlideOver';
import MetricStrip from './components/MetricStrip';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { useFocusTrap } from '@/hooks/useFocusTrap';
import {
  CalendarConnection,
  CATEGORY_LABELS,
  createCalendarMutationIntent,
  deleteMeeting,
  deleteTask,
  disconnectCalendarConnection,
  getCalendarPickerResume,
  getSharedCalendarView,
  getStaffAvailability,
  getTask,
  healthcheckCalendarConnection,
  listCalendarConnections,
  listPlannerWeddings,
  listTeamMembers,
  PlannerTask,
  PRIORITY_CONFIG,
  SharedCalendarEvent,
  TeamMemberSummary,
  WeddingSummary,
} from '@/services/calendarApi';
import { formatAdminDate, formatDateTime, DEFAULT_TIMEZONE } from '@/utils/dateFormat';

const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

type ViewMode = 'calendar' | 'list';
type SourceFilter = 'all' | 'internal_task' | 'internal_meeting' | 'external';
type VisibilityFilter = 'all' | 'details' | 'busy_only';

const PANEL_CLASS =
  'rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800';
const SUBTLE_PANEL_CLASS =
  'rounded-2xl border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60';
const INPUT_CLASS =
  'rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100';
const SECONDARY_BUTTON_CLASS =
  'rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60';
const PRIMARY_BUTTON_CLASS =
  'inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200';

function buildCalendarDays(year: number, month: number) {
  const firstDay = new Date(Date.UTC(year, month, 1));
  const lastDay = new Date(Date.UTC(year, month + 1, 0));
  const days: Array<number | null> = [];

  for (let index = 0; index < firstDay.getUTCDay(); index += 1) {
    days.push(null);
  }

  for (let day = 1; day <= lastDay.getUTCDate(); day += 1) {
    days.push(day);
  }

  return days;
}

function eventTone(event: SharedCalendarEvent) {
  if (String(event.source_type || '').startsWith('external')) {
    return 'border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-700/80 dark:text-slate-100';
  }
  if (event.source_type === 'internal_meeting') {
    return 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/50 dark:text-teal-200';
  }
  const priority = String(event.details.priority || '');
  if (priority === 'urgent')
    return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-200';
  if (priority === 'high')
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/50 dark:text-amber-200';
  return 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-200';
}

function eventDisplayTitle(event: SharedCalendarEvent) {
  if (
    String(event.source_type || '').startsWith('external') &&
    event.visibility_mode === 'busy_only'
  ) {
    return 'Busy';
  }
  return event.title || 'Untitled item';
}

export default function PlannerCalendarPage() {
  const { token, userProfile, fetchUserProfile, isLoading: authLoading } = useAdmin();
  const router = useRouter();
  const { confirm } = useConfirmDialog();
  const deleteMutationIntentsRef = useRef<Map<string, string>>(new Map());

  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth());
  const [viewMode, setViewMode] = useState<ViewMode>('calendar');
  const [weddings, setWeddings] = useState<WeddingSummary[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMemberSummary[]>([]);
  const [connections, setConnections] = useState<CalendarConnection[]>([]);
  const [events, setEvents] = useState<SharedCalendarEvent[]>([]);
  const [availability, setAvailability] = useState<{
    available_windows: Array<{ start: string; end: string }>;
    busy_events: SharedCalendarEvent[];
  } | null>(null);
  const [selectedAvailabilityStaffIds, setSelectedAvailabilityStaffIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<PlannerTask | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date | undefined>();
  const [filterWedding, setFilterWedding] = useState<string>('all');
  const [filterStaff, setFilterStaff] = useState<string>('all');
  const [filterSource, setFilterSource] = useState<SourceFilter>('all');
  const [filterVisibility, setFilterVisibility] = useState<VisibilityFilter>('all');

  // Phase 3 redesign state.
  // ``manageCalendarsOpen`` toggles the centered modal that wraps the
  // full <CalendarConnect> management surface — opened from the
  // CalendarStatusPill in the page header (popover footer link).
  // ``settingsAutoOpenConnectionId`` deep-links from the popover's
  // per-row Settings button into CalendarConnect's existing
  // per-calendar Settings modal.
  // ``daySlideOverIso`` (YYYY-MM-DD) controls the right-side
  // slide-over panel that replaces the inline day breakdown when a
  // grid cell is clicked.
  const [manageCalendarsOpen, setManageCalendarsOpen] = useState(false);
  const [settingsAutoOpenConnectionId, setSettingsAutoOpenConnectionId] = useState<
    string | null
  >(null);
  const [daySlideOverIso, setDaySlideOverIso] = useState<string | null>(null);
  // WAI-ARIA Dialog pattern — focus trap on the manage-calendars modal.
  const manageCalendarsDialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(manageCalendarsDialogRef, manageCalendarsOpen);

  // Picker-resume banner state — populated on mount via /picker-resume.
  // Surfaces an "in-flight calendar setup" the planner left behind
  // (refresh, tab close, auth bounce). One click sends them to the
  // callback page in resume mode, which re-renders the picker modal.
  const [resumeDraftId, setResumeDraftId] = useState<string | null>(null);
  const [resumeAccountEmail, setResumeAccountEmail] = useState<string | null>(
    null
  );

  const canViewCalendar =
    !!userProfile &&
    (userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.view_shared_calendar);
  const canViewAvailability =
    !!userProfile &&
    (userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.view_team_availability);
  const canCreateMeetings =
    !!userProfile &&
    (userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.schedule_meetings);
  const canEditMeetings =
    !!userProfile &&
    (userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.edit_meetings);
  const canManageGeneralTasks =
    !!userProfile &&
    (userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.manage_calendar_tasks);
  const canCreateItems =
    canCreateMeetings || canManageGeneralTasks;
  const defaultCreateCategory: 'meeting' | 'other' =
    canManageGeneralTasks ? 'other' : 'meeting';

  const ownerStaffOption = useMemo(() => {
    if (!userProfile) return null;

    const ownerId = userProfile.is_team_member
      ? userProfile.parent_planner_id || userProfile.team_member_id || userProfile.id
      : userProfile.id;
    const ownerEmail = userProfile.is_team_member
      ? userProfile.team_owner_email || userProfile.email
      : userProfile.email;
    if (!ownerId || !ownerEmail) return null;

    return {
      id: ownerId,
      email: ownerEmail,
      label: userProfile.is_team_member ? `Planner Owner (${ownerEmail})` : `Me (${ownerEmail})`,
    };
  }, [userProfile]);

  const staffOptions = useMemo(() => {
    const map = new Map<string, { id: string; email: string; label: string }>();

    if (ownerStaffOption) {
      map.set(ownerStaffOption.id, ownerStaffOption);
    }

    teamMembers
      .filter((member) => member.status === 'active' && member.user_id && member.email)
      .forEach((member) => {
        const label =
          [member.first_name, member.last_name].filter(Boolean).join(' ') || member.email;
        map.set(member.user_id as string, {
          id: member.user_id as string,
          email: member.email,
          label,
        });
      });

    if (userProfile?.is_team_member && userProfile.id && userProfile.email) {
      map.set(userProfile.id, {
        id: userProfile.id,
        email: userProfile.email,
        label:
          [userProfile.first_name, userProfile.last_name].filter(Boolean).join(' ') ||
          `${userProfile.email} (Me)`,
      });
    }

    return Array.from(map.values());
  }, [ownerStaffOption, teamMembers, userProfile]);

  // Use LOCAL midnight, not UTC midnight. Using Date.UTC here meant that
  // for users in negative-offset timezones (PT/CT/ET), the query start
  // landed on the previous day in local time — surfacing "Apr 30 7:00 PM"
  // as an available window when the user was looking at May. Local
  // midnight renders correctly in all timezones.
  const monthStart = useMemo(
    () => new Date(currentYear, currentMonth, 1),
    [currentMonth, currentYear]
  );
  const monthEnd = useMemo(
    () => new Date(currentYear, currentMonth + 1, 1),
    [currentMonth, currentYear]
  );

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      if (filterWedding !== 'all' && event.wedding_id !== filterWedding) return false;
      if (filterSource !== 'all' && event.source_type !== filterSource) return false;
      if (filterVisibility !== 'all' && event.visibility_mode !== filterVisibility) return false;
      if (filterStaff !== 'all' && !event.assigned_user_ids.includes(filterStaff)) return false;
      return true;
    });
  }, [events, filterSource, filterStaff, filterVisibility, filterWedding]);

  const eventsByDay = useMemo(() => {
    const grouped: Record<number, SharedCalendarEvent[]> = {};

    filteredEvents.forEach((event) => {
      if (!event.start_date) return;
      const date = new Date(event.start_date);
      if (Number.isNaN(date.getTime())) return;
      if (date.getUTCFullYear() !== currentYear || date.getUTCMonth() !== currentMonth) return;
      const day = date.getUTCDate();
      grouped[day] = [...(grouped[day] || []), event];
    });

    Object.values(grouped).forEach((group) =>
      group.sort((left, right) => (left.start_date || '').localeCompare(right.start_date || ''))
    );

    return grouped;
  }, [currentMonth, currentYear, filteredEvents]);

  const upcomingEvents = useMemo(() => {
    const now = new Date().toISOString();
    return filteredEvents
      .filter((event) => (event.start_date || '') >= now)
      .sort((left, right) => (left.start_date || '').localeCompare(right.start_date || ''))
      .slice(0, 8);
  }, [filteredEvents]);

  const calendarDays = useMemo(
    () => buildCalendarDays(currentYear, currentMonth),
    [currentMonth, currentYear]
  );

  const fetchReferenceData = useCallback(async () => {
    if (!token) return;

    const [weddingsResult, connectionsResult, teamResult] = await Promise.allSettled([
      listPlannerWeddings(token),
      listCalendarConnections(token),
      listTeamMembers(token),
    ]);

    if (weddingsResult.status === 'fulfilled') {
      setWeddings(weddingsResult.value);
    }

    if (connectionsResult.status === 'fulfilled') {
      setConnections(connectionsResult.value);
    }

    if (teamResult.status === 'fulfilled') {
      setTeamMembers(teamResult.value);
    } else if (userProfile?.is_team_member) {
      setTeamMembers([]);
    }
  }, [token, userProfile?.is_team_member]);

  const fetchEvents = useCallback(async () => {
    if (!token) return;

    const sharedEvents = await getSharedCalendarView(token, {
      start: monthStart.toISOString(),
      end: monthEnd.toISOString(),
    });

    setEvents(sharedEvents);
  }, [monthEnd, monthStart, token]);

  const refreshAll = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError('');
    try {
      await Promise.all([fetchReferenceData(), fetchEvents()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load planner calendar');
    } finally {
      setLoading(false);
    }
  }, [fetchEvents, fetchReferenceData, token]);

  const loadAvailability = useCallback(async () => {
    if (!token || !canViewAvailability || selectedAvailabilityStaffIds.length === 0) {
      setAvailability(null);
      return;
    }

    try {
      const result = await getStaffAvailability(
        token,
        selectedAvailabilityStaffIds,
        monthStart.toISOString(),
        monthEnd.toISOString()
      );
      setAvailability(result);
    } catch (err) {
      setAvailability(null);
      toast.error(err instanceof Error ? err.message : 'Failed to load availability');
    }
  }, [canViewAvailability, monthEnd, monthStart, selectedAvailabilityStaffIds, token]);

  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
      return;
    }

    if (!userProfile) {
      void fetchUserProfile();
      return;
    }

    if (!canViewCalendar) {
      router.push('/admin');
    }
  }, [canViewCalendar, fetchUserProfile, router, token, userProfile]);

  useEffect(() => {
    if (!token || !userProfile || !canViewCalendar) return;
    void refreshAll();
  }, [canViewCalendar, refreshAll, token, userProfile]);

  useEffect(() => {
    if (!selectedAvailabilityStaffIds.length && staffOptions.length > 0) {
      setSelectedAvailabilityStaffIds([staffOptions[0].id]);
    }
  }, [staffOptions, selectedAvailabilityStaffIds.length]);

  useEffect(() => {
    if (!canViewAvailability) return;
    void loadAvailability();
  }, [canViewAvailability, loadAvailability]);

  // Picker-resume probe — fires once on planner mount. If the planner
  // started a calendar OAuth, was bounced to login (or refreshed, or
  // closed the tab), and arrived back here, the draft they made is
  // still in Mongo (TTL 30 min). Surface a banner offering to continue
  // the setup instead of making them re-do OAuth.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const result = await getCalendarPickerResume(token);
        if (cancelled) return;
        if (result.needs_selection && result.draft_id) {
          setResumeDraftId(result.draft_id);
          setResumeAccountEmail(result.account_email ?? null);
        }
      } catch {
        // Silent — banner is opportunistic recovery, not a hard
        // dependency. The /picker-resume endpoint returns an empty
        // payload when no draft exists; only network / 5xx errors
        // would throw, and there's nothing the planner can do about
        // those here.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const openCreateModal = (date?: Date) => {
    setSelectedTask(null);
    setSelectedDate(date);
    setTaskModalOpen(true);
  };

  const openExistingItem = async (event: SharedCalendarEvent) => {
    if (!token) return;

    if (String(event.source_type || '').startsWith('external')) {
      toast.message('External events are read-only here. Change sharing or sync settings from the connection panel.');
      return;
    }
    if (event.source_type === 'internal_task' && !canManageGeneralTasks) {
      toast.message('You can view tasks on the shared calendar, but you need calendar task permission to edit them.');
      return;
    }

    try {
      const task = await getTask(token, event.id);
      setSelectedTask(task);
      setSelectedDate(undefined);
      setTaskModalOpen(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load schedule item');
    }
  };

  const handleDelete = async (task: PlannerTask) => {
    if (!token) return;

    const confirmed = await confirm({
      title: task.schedule_item_type === 'meeting' || task.category === 'meeting' ? 'Delete meeting' : 'Delete task',
      message:
        task.schedule_item_type === 'meeting' || task.category === 'meeting'
          ? 'Delete this meeting and all external calendar projections?'
          : 'Delete this task?',
      variant: 'danger',
      confirmText: 'Delete',
      cancelText: 'Cancel',
    });

    if (!confirmed) return;

    try {
      if (task.schedule_item_type === 'meeting' || task.category === 'meeting') {
        const deleteIntentKey = `${task.id}:${task.version}`;
        const mutationIntent =
          deleteMutationIntentsRef.current.get(deleteIntentKey) ||
          createCalendarMutationIntent();
        deleteMutationIntentsRef.current.set(deleteIntentKey, mutationIntent);
        await deleteMeeting(token, task.id, task.version, mutationIntent);
        deleteMutationIntentsRef.current.delete(deleteIntentKey);
      } else {
        await deleteTask(token, task.id);
      }
      setTaskModalOpen(false);
      setSelectedTask(null);
      await refreshAll();
      await loadAvailability();
      toast.success('Schedule item deleted');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete item');
    }
  };

  // Restored from the Phase-3 follow-up: the staff selector now lives
  // inside the CalendarRightRail Availability tab as a small popover
  // (anchored to the "Staff" button next to Refresh).
  const toggleAvailabilityStaff = useCallback((staffId: string) => {
    setSelectedAvailabilityStaffIds((current) =>
      current.includes(staffId)
        ? current.filter((value) => value !== staffId)
        : [...current, staffId]
    );
  }, []);

  const goToPreviousMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear((value) => value - 1);
      return;
    }
    setCurrentMonth((value) => value - 1);
  };

  const goToNextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear((value) => value + 1);
      return;
    }
    setCurrentMonth((value) => value + 1);
  };

  const goToToday = () => {
    const now = new Date();
    setCurrentYear(now.getFullYear());
    setCurrentMonth(now.getMonth());
  };

  const today = new Date();
  const isToday = (day: number) =>
    day === today.getDate() &&
    currentMonth === today.getMonth() &&
    currentYear === today.getFullYear();

  // ---------- Phase 3 redesign: status pill + slide-over wiring ----------

  /** Deep-link from the status-pill popover into the per-calendar
   *  Settings modal that lives inside <CalendarConnect>. We open the
   *  manage-calendars modal AND pass the connection id as autoOpen so
   *  the Settings popup appears immediately. */
  const handleOpenConnectionSettings = useCallback(
    (connection: CalendarConnection) => {
      setSettingsAutoOpenConnectionId(connection.id);
      setManageCalendarsOpen(true);
    },
    []
  );

  /** Manual healthcheck button on a popover row. Calls the existing
   *  backend endpoint and refreshes connections so any new
   *  ``last_error`` shows up in the popover. */
  const handleCheckConnectionHealth = useCallback(
    async (connection: CalendarConnection) => {
      if (!token) return;
      try {
        await healthcheckCalendarConnection(token, connection.id);
        toast.success('Healthcheck complete');
        await refreshAll();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Healthcheck failed');
      }
    },
    [refreshAll, token]
  );

  /** Disconnect a single connection from the popover. The teardown
   *  endpoint already handles its own confirmation flow upstream; we
   *  add a soft confirm here too because Disconnect is destructive. */
  const handleDisconnectConnection = useCallback(
    async (connection: CalendarConnection) => {
      if (!token) return;
      const ok = await confirm({
        title: 'Disconnect calendar',
        message: `Disconnect ${connection.calendar_name || connection.provider_account_email}? Synced events will be torn down.`,
        variant: 'danger',
        confirmText: 'Disconnect',
        cancelText: 'Cancel',
      });
      if (!ok) return;
      try {
        await disconnectCalendarConnection(token, connection.id);
        toast.success('Calendar disconnected');
        await refreshAll();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to disconnect');
      }
    },
    [confirm, refreshAll, token]
  );

  /** Day-cell click handler: opens the slide-over for that date.
   *  Re-clicking the same day closes it; clicking a different day
   *  re-targets the slide-over. */
  const openDaySlideOver = useCallback((day: number) => {
    const iso = new Date(Date.UTC(currentYear, currentMonth, day))
      .toISOString()
      .slice(0, 10);
    setDaySlideOverIso((prev) => (prev === iso ? null : iso));
  }, [currentMonth, currentYear]);

  // ``upcomingEvents`` is already declared above (filtered-event-based
  // memo) — we reuse that for the CalendarRightRail "Upcoming" tab so
  // the filter chips on the calendar page apply consistently.

  if (!token || authLoading || !userProfile) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900 dark:border-slate-700 dark:border-t-slate-100" />
      </div>
    );
  }

  if (!canViewCalendar) {
    return null;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Shared Planner Calendar"
        description="Business-owned meetings, team visibility, and explicit calendar projections."
      >
        <div className="flex items-center gap-3">
          <CalendarStatusPill
            connections={connections}
            onOpenSettings={handleOpenConnectionSettings}
            onCheckHealth={handleCheckConnectionHealth}
            onDisconnect={handleDisconnectConnection}
          />
          {canCreateItems && (
            <button
              onClick={() => openCreateModal(new Date())}
              className={PRIMARY_BUTTON_CLASS}
            >
              New schedule item
            </button>
          )}
        </div>
      </PageHeader>

      <MetricStrip
        values={{
          internalMeetings: events.filter(
            (event) => event.source_type === 'internal_meeting'
          ).length,
          sharedCalendars: connections.filter((c) => c.is_shared_in_team_view).length,
          busyFreeImports: events.filter(
            (event) =>
              String(event.source_type || '').startsWith('external') &&
              event.visibility_mode === 'busy_only'
          ).length,
          visibleItems: filteredEvents.length,
        }}
        context={`${MONTH_NAMES[currentMonth]} ${currentYear}`}
      />

      {/* Resume-calendar-setup banner — appears when /picker-resume on
          mount returned an in-flight draft. Most common cause: planner
          started OAuth, was bounced to login (session expired), came
          back here. Without this banner they'd think the OAuth never
          ran. The "Continue setup" CTA routes to the callback page in
          resume mode so the picker modal re-renders. */}
      {resumeDraftId && !loading && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-wedding-rose/30 bg-wedding-rose/5 px-4 py-3 dark:border-wedding-rose/40 dark:bg-wedding-rose/10">
          <div className="min-w-0">
            <p className="font-medium text-slate-900 dark:text-slate-100">
              You have a calendar setup waiting
            </p>
            {resumeAccountEmail && (
              <p className="mt-0.5 text-[12.5px] text-slate-600 dark:text-slate-300">
                Pick which calendars to sync on{' '}
                <span className="font-medium">{resumeAccountEmail}</span>.
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => router.push('/admin/planner/calendar/callback?resume=1')}
              className="rounded-full bg-rose-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-rose-700 dark:bg-rose-300 dark:text-slate-900 dark:hover:bg-rose-200"
            >
              Continue setup
            </button>
            <button
              type="button"
              onClick={() => setResumeDraftId(null)}
              className="rounded-full px-3 py-1.5 text-sm text-slate-500 transition hover:bg-white/60 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-700/60 dark:hover:text-slate-100"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Empty-state CTA — when zero connections and no in-flight
          draft, surface the path to add one without making the planner
          hunt for the status pill. */}
      {!resumeDraftId && !loading && connections.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-8 text-center dark:border-slate-700 dark:bg-slate-900/40">
          <p className="font-heading text-xl text-slate-900 dark:text-slate-100">
            Connect your first calendar
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-500 dark:text-slate-400">
            Pull your Google, Microsoft 365, iCloud, or Exchange calendar into
            your planner so meetings, availability, and external events stay in
            one place.
          </p>
          <button
            type="button"
            onClick={() => setManageCalendarsOpen(true)}
            className="mt-4 rounded-full bg-rose-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-rose-700 dark:bg-rose-300 dark:text-slate-900 dark:hover:bg-rose-200"
          >
            Connect a calendar
          </button>
        </div>
      )}

      {/* Manage-all-calendars modal — hosts the full <CalendarConnect>
          component. Triggered from the CalendarStatusPill popover.
          When the popover's per-row Settings button calls
          handleOpenConnectionSettings(conn), we set both the modal-open
          flag AND the autoOpen id so the per-calendar Settings popup
          inside <CalendarConnect> shows immediately. */}
      {manageCalendarsOpen && typeof document !== 'undefined' &&
        createPortal(
          <div
            className="fixed inset-0 z-[60] flex items-center justify-center"
            role="dialog"
            aria-modal="true"
          >
            <div
              className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm dark:bg-black/60"
              onClick={() => {
                setManageCalendarsOpen(false);
                setSettingsAutoOpenConnectionId(null);
              }}
              aria-hidden
            />
            <div
              ref={manageCalendarsDialogRef}
              className="relative z-[61] mx-4 max-h-[88vh] w-full max-w-[960px] overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="sticky top-0 z-[62] flex items-center justify-between border-b border-slate-200 bg-white/95 px-6 py-4 backdrop-blur dark:border-slate-700 dark:bg-slate-900/95">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary-700 dark:text-rose-200">
                    Manage calendars
                  </p>
                  <h2 className="font-heading text-xl text-slate-900 dark:text-slate-100">
                    Connections &amp; settings
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setManageCalendarsOpen(false);
                    setSettingsAutoOpenConnectionId(null);
                  }}
                  aria-label="Close manage calendars"
                  className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500 transition hover:bg-slate-200 hover:text-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700"
                >
                  <X size={16} />
                </button>
              </div>
              <div className="p-6">
                <CalendarConnect
                  connections={connections}
                  staffOptions={staffOptions}
                  weddings={weddings}
                  loading={loading}
                  onRefresh={refreshAll}
                  autoOpenSettingsForConnectionId={settingsAutoOpenConnectionId}
                  onSettingsClose={() => setSettingsAutoOpenConnectionId(null)}
                />
              </div>
            </div>
          </div>,
          document.body
        )}

      {/* Day-slide-over: replaces the inline day breakdown that used to
          live in the right rail. Rendered as a portal overlay so it
          floats over the grid without re-flowing it. */}
      {daySlideOverIso && (
        <DaySlideOver
          selectedDateIso={daySlideOverIso}
          events={events}
          onClose={() => setDaySlideOverIso(null)}
          onCreateTask={(iso) => openCreateModal(new Date(`${iso}T00:00:00`))}
          onCreateMeeting={(iso) => openCreateModal(new Date(`${iso}T00:00:00`))}
        />
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,0.95fr)]">
        <section className={PANEL_CLASS}>
          <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-700">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={goToPreviousMonth}
                  className={SECONDARY_BUTTON_CLASS}
                >
                  Prev
                </button>
                <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                  {MONTH_NAMES[currentMonth]} {currentYear}
                </h2>
                <button
                  onClick={goToNextMonth}
                  className={SECONDARY_BUTTON_CLASS}
                >
                  Next
                </button>
                <button
                  onClick={goToToday}
                  className={SECONDARY_BUTTON_CLASS}
                >
                  Today
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setViewMode('calendar')}
                  className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
                    viewMode === 'calendar'
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                      : 'border border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60'
                  }`}
                >
                  Calendar
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
                    viewMode === 'list'
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                      : 'border border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60'
                  }`}
                >
                  Agenda
                </button>
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <select
                value={filterWedding}
                onChange={(event) => setFilterWedding(event.target.value)}
                className={INPUT_CLASS}
              >
                <option value="all">All weddings</option>
                {weddings.map((wedding) => (
                  <option key={wedding.id} value={wedding.id}>
                    {wedding.couple_names}
                  </option>
                ))}
              </select>

              <select
                value={filterStaff}
                onChange={(event) => setFilterStaff(event.target.value)}
                className={INPUT_CLASS}
              >
                <option value="all">All staff</option>
                {staffOptions.map((staff) => (
                  <option key={staff.id} value={staff.id}>
                    {staff.label}
                  </option>
                ))}
              </select>

              <select
                value={filterSource}
                onChange={(event) => setFilterSource(event.target.value as SourceFilter)}
                className={INPUT_CLASS}
              >
                <option value="all">All sources</option>
                <option value="internal_task">Internal tasks</option>
                <option value="internal_meeting">Internal meetings</option>
                <option value="external">External calendars</option>
              </select>

              <select
                value={filterVisibility}
                onChange={(event) => setFilterVisibility(event.target.value as VisibilityFilter)}
                className={INPUT_CLASS}
              >
                <option value="all">All visibility</option>
                <option value="details">Full details</option>
                <option value="busy_only">Busy/free only</option>
              </select>
            </div>
          </div>

          <div className="p-3">
            {loading ? (
              <div className="flex h-40 items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900 dark:border-slate-700 dark:border-t-slate-100" />
              </div>
            ) : error ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
                {error}
              </div>
            ) : viewMode === 'calendar' ? (
              <>
                <div className="mb-1.5 grid grid-cols-7 gap-1.5">
                  {DAY_NAMES.map((day) => (
                    <div key={day} className="px-1 py-0.5 text-center text-[9.5px] font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                      {day}
                    </div>
                  ))}
                </div>

                {/* Calendar grid — compact density per the Phase-3
                    redesign. Cells use ``aspect-[1.4/1]`` so they
                    scale width-first to the column instead of being
                    locked at a fixed 130px tall (which made 6 rows
                    occupy ~780px on a 7-column grid). The event chips
                    inside cap at 2 lines + a "more" pill — anything
                    over that lives in the slide-over (day click). */}
                <div className="grid grid-cols-7 gap-1.5">
                  {calendarDays.map((day, index) => {
                    const cellIso = day
                      ? new Date(Date.UTC(currentYear, currentMonth, day))
                          .toISOString()
                          .slice(0, 10)
                      : null;
                    const isSelected = Boolean(
                      cellIso && cellIso === daySlideOverIso
                    );
                    const todayRing = day && isToday(day)
                      ? 'ring-1 ring-slate-900/20 dark:ring-slate-100/20'
                      : '';
                    const selectedRing = isSelected
                      ? 'ring-2 ring-wedding-rose'
                      : '';
                    const dayEvents = eventsByDay[day || 0] || [];
                    const visibleEvents = dayEvents.slice(0, 2);
                    const overflowCount = dayEvents.length - visibleEvents.length;
                    return (
                    <div
                      key={`${day ?? 'empty'}-${index}`}
                      onClick={() => day && openDaySlideOver(day)}
                      className={`aspect-[1.4/1] rounded-xl border p-1.5 transition overflow-hidden ${
                        day
                          ? 'cursor-pointer border-slate-200 bg-slate-50 hover:border-wedding-rose/50 dark:border-slate-700 dark:bg-slate-900/60 dark:hover:border-wedding-rose/40'
                          : 'border-transparent bg-transparent'
                      } ${todayRing} ${selectedRing}`}
                    >
                      {day && (
                        <div className="flex h-full flex-col gap-1">
                          <div className={`text-[11px] font-semibold leading-none ${isToday(day) ? 'text-primary-700 dark:text-rose-200' : 'text-slate-500 dark:text-slate-400'}`}>
                            {day}
                          </div>
                          <div className="flex flex-col gap-0.5 overflow-hidden">
                            {visibleEvents.map((event) => (
                              <button
                                key={event.id}
                                onClick={(clickEvent) => {
                                  clickEvent.stopPropagation();
                                  void openExistingItem(event);
                                }}
                                className={`w-full truncate rounded px-1.5 py-0.5 text-left text-[10px] font-medium leading-tight ${eventTone(event)}`}
                              >
                                {eventDisplayTitle(event)}
                              </button>
                            ))}
                            {overflowCount > 0 && (
                              <div className="px-1 text-[9.5px] text-slate-400 dark:text-slate-500">
                                +{overflowCount} more
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <div className="space-y-3">
                {filteredEvents.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center text-sm text-slate-500 dark:border-slate-600 dark:bg-slate-900/50 dark:text-slate-400">
                    No events match the current filters.
                  </div>
                ) : (
                  filteredEvents
                    .slice()
                    .sort((left, right) => (left.start_date || '').localeCompare(right.start_date || ''))
                    .map((event) => (
                      <button
                        key={`${event.source_type}-${event.id}`}
                        onClick={() => void openExistingItem(event)}
                        className="w-full rounded-2xl border border-slate-200 bg-slate-50 p-4 text-left transition hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900/60 dark:hover:border-slate-500"
                      >
                        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${eventTone(event)}`}>
                                {event.source_type.replace('_', ' ')}
                              </span>
                              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                                {eventDisplayTitle(event)}
                              </h3>
                            </div>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {event.start_date
                                ? formatDateTime(
                                    event.start_date,
                                    {
                                      month: 'short',
                                      day: 'numeric',
                                      hour: event.all_day ? undefined : 'numeric',
                                      minute: event.all_day ? undefined : '2-digit',
                                    },
                                    'en-US',
                                    DEFAULT_TIMEZONE
                                  )
                                : 'Time TBD'}
                            </p>
                            {event.wedding_id && (
                              <p className="text-xs text-slate-500 dark:text-slate-400">
                                {
                                  weddings.find((wedding) => wedding.id === event.wedding_id)?.couple_names ||
                                  'Wedding'
                                }
                              </p>
                            )}
                          </div>
                          <div className="text-xs text-slate-500 dark:text-slate-400">
                            {event.assigned_user_emails.length > 0
                              ? event.assigned_user_emails.join(', ')
                              : event.owner_planner_email || 'Planner workspace'}
                          </div>
                        </div>
                      </button>
                    ))
                )}
              </div>
            )}
          </div>
        </section>

        <aside>
          <CalendarRightRail
            upcoming={upcomingEvents}
            availabilityWindows={availability?.available_windows ?? []}
            availabilityLabel={
              selectedAvailabilityStaffIds.length > 0
                ? `For ${selectedAvailabilityStaffIds.length} selected staff`
                : 'Pick at least one staff member to see open windows.'
            }
            onRefreshUpcoming={() => void refreshAll()}
            onRefreshAvailability={canViewAvailability ? () => void loadAvailability() : undefined}
            staffOptions={canViewAvailability ? staffOptions : undefined}
            selectedStaffIds={selectedAvailabilityStaffIds}
            onToggleStaff={canViewAvailability ? toggleAvailabilityStaff : undefined}
          />
        </aside>
      </div>

      <TaskModal
        open={taskModalOpen}
        onOpenChange={setTaskModalOpen}
        task={selectedTask}
        weddings={weddings}
        defaultDate={selectedDate}
        defaultCategory={defaultCreateCategory}
        allowGeneralTasks={canManageGeneralTasks}
        allowMeetings={canCreateMeetings || canEditMeetings}
        connections={connections}
        staffOptions={staffOptions}
        onSuccess={async () => {
          await refreshAll();
          await loadAvailability();
        }}
        onDelete={handleDelete}
      />
    </div>
  );
}
