'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { useAdmin } from '@/contexts/AdminContext';
import { useConfirmDialog } from '@/components/ui/ConfirmDialog';
import PageHeader from '../../components/PageHeader';
import TaskModal from './components/TaskModal';
import CalendarConnect from './components/CalendarConnect';
import {
  acceptExternalChange,
  approveCoupleBooking,
  CalendarConnection,
  CATEGORY_LABELS,
  createCalendarMutationIntent,
  declineCoupleBooking,
  deleteMeeting,
  deleteTask,
  getSharedCalendarView,
  getStaffAvailability,
  getTask,
  listCalendarConnections,
  listPlannerWeddings,
  listTeamMembers,
  PlannerTask,
  PRIORITY_CONFIG,
  rejectExternalChange,
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
  if (event.source_type === 'external') {
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
  if (event.source_type === 'external' && event.visibility_mode === 'busy_only') {
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

  const monthStart = useMemo(
    () => new Date(Date.UTC(currentYear, currentMonth, 1)),
    [currentMonth, currentYear]
  );
  const monthEnd = useMemo(
    () => new Date(Date.UTC(currentYear, currentMonth + 1, 1)),
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

  const openCreateModal = (date?: Date) => {
    setSelectedTask(null);
    setSelectedDate(date);
    setTaskModalOpen(true);
  };

  const openExistingItem = async (event: SharedCalendarEvent) => {
    if (!token) return;

    if (event.source_type === 'external') {
      const providerLabel =
        'external_provider' in event &&
        typeof event.external_provider === 'string' &&
        event.external_provider.trim().length > 0
          ? `External ${event.external_provider.trim()} events`
          : 'External calendar events';
      toast.message(`${providerLabel} are read-only here. Change sharing or sync settings from the connection panel.`);
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

  const toggleAvailabilityStaff = (staffId: string) => {
    setSelectedAvailabilityStaffIds((current) =>
      current.includes(staffId)
        ? current.filter((value) => value !== staffId)
        : [...current, staffId]
    );
  };

  const eventsNeedingReview = useMemo(
    () =>
      events.filter((event) => {
        if (event.source_type !== 'internal_meeting') return false;
        const status = event.details?.external_conflict_status;
        return status === 'pending_review' || status === 'auto_accepted';
      }),
    [events],
  );

  const eventsAwaitingApproval = useMemo(
    () =>
      events.filter(
        (event) =>
          event.source_type === 'internal_meeting' &&
          event.details?.meeting_status === 'pending_approval',
      ),
    [events],
  );

  const eventVersion = (event: SharedCalendarEvent): number => {
    const raw = event.details?.version;
    return typeof raw === 'number' && Number.isFinite(raw) ? raw : 1;
  };

  const handleAcceptExternalChange = async (event: SharedCalendarEvent) => {
    if (!token) return;
    try {
      await acceptExternalChange(
        token,
        event.id,
        eventVersion(event),
        createCalendarMutationIntent(),
      );
      toast.success('External change accepted.');
      await refreshAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to accept change');
    }
  };

  const handleRejectExternalChange = async (event: SharedCalendarEvent) => {
    if (!token) return;
    try {
      await rejectExternalChange(
        token,
        event.id,
        eventVersion(event),
        createCalendarMutationIntent(),
      );
      toast.success('External change rejected; canonical state pushed back.');
      await refreshAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to reject change');
    }
  };

  const handleApproveCoupleBooking = async (event: SharedCalendarEvent) => {
    if (!token) return;
    try {
      await approveCoupleBooking(
        token,
        event.id,
        eventVersion(event),
        createCalendarMutationIntent(),
      );
      toast.success('Booking approved and synced to your calendar.');
      await refreshAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to approve booking');
    }
  };

  const handleDeclineCoupleBooking = async (event: SharedCalendarEvent) => {
    if (!token) return;
    try {
      await declineCoupleBooking(
        token,
        event.id,
        eventVersion(event),
        createCalendarMutationIntent(),
      );
      toast.success('Booking declined.');
      await refreshAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to decline booking');
    }
  };

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
    <div className="space-y-6">
      <PageHeader
        title="Shared Planner Calendar"
        description="Business-owned meetings, team visibility, and explicit Google calendar projections."
      >
        {canCreateItems && (
          <button
            onClick={() => openCreateModal(new Date())}
            className={PRIMARY_BUTTON_CLASS}
          >
            New schedule item
          </button>
        )}
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className={`${PANEL_CLASS} p-5`}>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">Internal meetings</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-100">
            {events.filter((event) => event.source_type === 'internal_meeting').length}
          </p>
        </div>
        <div className={`${PANEL_CLASS} p-5`}>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">Shared calendars</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-100">
            {connections.filter((connection) => connection.is_shared_in_team_view).length}
          </p>
        </div>
        <div className={`${PANEL_CLASS} p-5`}>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">Busy/free imports</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-100">
            {
              events.filter(
                (event) => event.source_type === 'external' && event.visibility_mode === 'busy_only'
              ).length
            }
          </p>
        </div>
        <div className={`${PANEL_CLASS} p-5`}>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">Visible items</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-100">{filteredEvents.length}</p>
        </div>
      </div>

      {(eventsAwaitingApproval.length > 0 || eventsNeedingReview.length > 0) && (
        <section className={`${PANEL_CLASS} p-5 space-y-4`}>
          {eventsAwaitingApproval.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Couple booking requests ({eventsAwaitingApproval.length})
              </h3>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                These bookings will not land on your calendar or send a couple invite until you approve them.
              </p>
              <ul className="mt-3 space-y-2">
                {eventsAwaitingApproval.map((event) => (
                  <li
                    key={`approval-${event.id}`}
                    className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3 text-sm dark:border-amber-900 dark:bg-amber-950/30 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <div className="font-medium text-slate-900 dark:text-slate-100">
                        {event.title || 'Untitled meeting'}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">
                        {event.start_date ? formatDateTime(event.start_date) : '—'}
                        {event.assigned_user_emails?.length
                          ? ` • with ${event.assigned_user_emails[0]}`
                          : ''}
                      </div>
                    </div>
                    {canEditMeetings && (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => handleApproveCoupleBooking(event)}
                          className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeclineCoupleBooking(event)}
                          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60"
                        >
                          Decline
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {eventsNeedingReview.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                External calendar changes ({eventsNeedingReview.length})
              </h3>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Someone changed these meetings directly in their external calendar. Accept to apply
                the change here, or reject to push your canonical state back.
              </p>
              <ul className="mt-3 space-y-2">
                {eventsNeedingReview.map((event) => {
                  const detail = event.details ?? {};
                  const externalStart = detail.external_start_date as string | undefined;
                  const externalTitle = detail.external_title as string | undefined;
                  return (
                    <li
                      key={`conflict-${event.id}`}
                      className="flex flex-col gap-2 rounded-xl border border-rose-200 bg-rose-50/60 px-4 py-3 text-sm dark:border-rose-900 dark:bg-rose-950/30 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div>
                        <div className="font-medium text-slate-900 dark:text-slate-100">
                          {event.title || 'Untitled meeting'}
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                          {event.start_date ? formatDateTime(event.start_date) : '—'} (current)
                        </div>
                        {(externalStart || externalTitle) && (
                          <div className="text-xs text-rose-700 dark:text-rose-300">
                            External: {externalTitle || event.title}
                            {externalStart ? ` • ${formatDateTime(externalStart)}` : ''}
                          </div>
                        )}
                      </div>
                      {canEditMeetings && (
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => handleAcceptExternalChange(event)}
                            className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
                          >
                            Accept
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRejectExternalChange(event)}
                            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </section>
      )}

      <CalendarConnect
        connections={connections}
        staffOptions={staffOptions}
        weddings={weddings}
        loading={loading}
        onRefresh={refreshAll}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,0.95fr)]">
        <section className={PANEL_CLASS}>
          <div className="border-b border-slate-200 px-6 py-5 dark:border-slate-700">
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

          <div className="p-4">
            {loading ? (
              <div className="flex h-80 items-center justify-center">
                <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900 dark:border-slate-700 dark:border-t-slate-100" />
              </div>
            ) : error ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
                {error}
              </div>
            ) : viewMode === 'calendar' ? (
              <>
                <div className="mb-3 grid grid-cols-7 gap-2">
                  {DAY_NAMES.map((day) => (
                    <div key={day} className="px-2 py-1 text-center text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
                      {day}
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-7 gap-2">
                  {calendarDays.map((day, index) => (
                    <div
                      key={`${day ?? 'empty'}-${index}`}
                      onClick={() => day && canCreateItems && openCreateModal(new Date(Date.UTC(currentYear, currentMonth, day)))}
                      className={`min-h-[130px] rounded-2xl border p-2 transition ${
                        day
                          ? 'cursor-pointer border-slate-200 bg-slate-50 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900/60 dark:hover:border-slate-500'
                          : 'border-transparent bg-transparent'
                      } ${day && isToday(day) ? 'ring-1 ring-slate-900/20 dark:ring-slate-100/20' : ''}`}
                    >
                      {day && (
                        <>
                          <div className={`mb-2 text-sm font-semibold ${isToday(day) ? 'text-slate-900 dark:text-slate-100' : 'text-slate-500 dark:text-slate-400'}`}>
                            {day}
                          </div>
                          <div className="space-y-1.5">
                            {(eventsByDay[day] || []).slice(0, 4).map((event) => (
                              <button
                                key={event.id}
                                onClick={(clickEvent) => {
                                  clickEvent.stopPropagation();
                                  void openExistingItem(event);
                                }}
                                className={`w-full rounded-xl border px-2 py-1.5 text-left text-[11px] font-medium ${eventTone(event)}`}
                              >
                                <div className="truncate">{eventDisplayTitle(event)}</div>
                                <div className="truncate text-[10px] opacity-70">
                                  {event.all_day
                                    ? 'All day'
                                    : event.start_date
                                    ? formatDateTime(
                                        event.start_date,
                                        { hour: 'numeric', minute: '2-digit' },
                                        'en-US',
                                        DEFAULT_TIMEZONE
                                      )
                                    : 'Time TBD'}
                                </div>
                              </button>
                            ))}
                            {(eventsByDay[day] || []).length > 4 && (
                              <div className="px-1 text-[11px] text-slate-500 dark:text-slate-400">
                                +{(eventsByDay[day] || []).length - 4} more
                              </div>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  ))}
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

        <aside className="space-y-6">
          <section className={`${PANEL_CLASS} p-5`}>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Upcoming</h3>
              <button
                onClick={() => void refreshAll()}
                className={`${SECONDARY_BUTTON_CLASS} text-xs font-medium`}
              >
                Refresh
              </button>
            </div>
            <div className="mt-4 space-y-3">
              {upcomingEvents.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">No upcoming items in the current filtered view.</p>
              ) : (
                upcomingEvents.map((event) => (
                  <button
                    key={`upcoming-${event.id}`}
                    onClick={() => void openExistingItem(event)}
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900/60 dark:hover:border-slate-500"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                          {eventDisplayTitle(event)}
                        </p>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
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
                      </div>
                      <span className={`rounded-full border px-2 py-1 text-[11px] font-medium ${eventTone(event)}`}>
                        {event.source_type === 'internal_meeting'
                          ? 'Meeting'
                          : event.source_type === 'external'
                          ? (event.external_provider
                              ? event.external_provider.charAt(0).toUpperCase() + event.external_provider.slice(1)
                              : 'External')
                          : 'Task'}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          <section className={`${PANEL_CLASS} p-5`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Availability</h3>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Busy blocks and open windows for selected staff in this month.
                </p>
              </div>
              <button
                onClick={() => void loadAvailability()}
                disabled={!canViewAvailability}
                className="rounded-xl border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60"
              >
                Refresh
              </button>
            </div>

            {!canViewAvailability ? (
              <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
                Your role does not include team availability access.
              </p>
            ) : (
              <>
                <div className="mt-4 space-y-2">
                  {staffOptions.map((staff) => (
                    <label key={staff.id} className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
                      <input
                        type="checkbox"
                        checked={selectedAvailabilityStaffIds.includes(staff.id)}
                        onChange={() => toggleAvailabilityStaff(staff.id)}
                        className="h-4 w-4 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                      />
                      {staff.label}
                    </label>
                  ))}
                </div>

                <div className="mt-4 space-y-3">
                  {!availability || availability.available_windows.length === 0 ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      No open windows found for the selected staff in this range.
                    </p>
                  ) : (
                    availability.available_windows.slice(0, 5).map((window, index) => (
                      <div
                        key={`${window.start}-${index}`}
                        className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-3 dark:border-emerald-900 dark:bg-emerald-950/40"
                      >
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-200">
                          Available window
                        </p>
                        <p className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
                          {formatDateTime(
                            window.start,
                            {
                              month: 'short',
                              day: 'numeric',
                              hour: 'numeric',
                              minute: '2-digit',
                            },
                            'en-US',
                            DEFAULT_TIMEZONE
                          )}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          until{' '}
                          {formatDateTime(
                            window.end,
                            { hour: 'numeric', minute: '2-digit' },
                            'en-US',
                            DEFAULT_TIMEZONE
                          )}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </>
            )}
          </section>

          <section className={`${PANEL_CLASS} p-5`}>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Legend</h3>
            <div className="mt-4 space-y-2 text-sm text-slate-600 dark:text-slate-300">
              <div className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-full bg-blue-200 dark:bg-blue-400/70" />
                Internal task
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-full bg-teal-200 dark:bg-teal-400/70" />
                Internal meeting
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-full bg-slate-300 dark:bg-slate-500" />
                External Google event
              </div>
              <p className="pt-2 text-xs leading-6 text-slate-500 dark:text-slate-400">
                External calendars show busy/free only unless the connection enables full details.
                Couples receive email plus ICS for meetings; they do not connect calendars in v1.
              </p>
            </div>
          </section>
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
