'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/Dialog';
import {
  CalendarConnection,
  CATEGORY_LABELS,
  CalendarSyncPolicy,
  approveCoupleBooking,
  createCalendarMutationIntent,
  createMeeting,
  createTask,
  declineCoupleBooking,
  InviteDeliveryMode,
  PlannerTask,
  PRIORITY_CONFIG,
  ScheduleItemPayload,
  TaskCategory,
  TaskPriority,
  updateMeeting,
  updateTask,
  VisibilityMode,
} from '@/services/calendarApi';
import { useAdmin } from '@/contexts/AdminContext';
import { getLocalDateString } from '@/utils/dateFormat';

interface StaffOption {
  id: string;
  email: string;
  label: string;
}

interface TaskModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  task?: PlannerTask | null;
  weddings?: Array<{ id: string; couple_names: string }>;
  defaultDate?: Date;
  defaultCategory?: TaskCategory;
  allowGeneralTasks?: boolean;
  allowMeetings?: boolean;
  allowBookingApproval?: boolean;
  connections?: CalendarConnection[];
  staffOptions?: StaffOption[];
  onSuccess?: () => void;
  onDelete?: (task: PlannerTask) => Promise<void> | void;
}

const CATEGORIES: TaskCategory[] = [
  'venue',
  'catering',
  'photography',
  'videography',
  'music',
  'flowers',
  'attire',
  'invitations',
  'transportation',
  'accommodation',
  'ceremony',
  'reception',
  'honeymoon',
  'legal',
  'budget',
  'guest_management',
  'meeting',
  'other',
];

const PRIORITIES: TaskPriority[] = ['low', 'medium', 'high', 'urgent'];
const VISIBILITY_OPTIONS: Array<{ value: VisibilityMode; label: string }> = [
  { value: 'details', label: 'Full details' },
  { value: 'busy_only', label: 'Busy/free only' },
];
const SYNC_POLICY_OPTIONS: Array<{ value: CalendarSyncPolicy; label: string }> = [
  { value: 'assigned_only', label: 'Assigned staff only' },
  { value: 'owner_only', label: 'Owner only' },
  { value: 'owner_and_assigned', label: 'Owner and assigned staff' },
  { value: 'custom', label: 'Custom targets' },
];
const INVITE_OPTIONS: Array<{ value: InviteDeliveryMode; label: string }> = [
  { value: 'email_ics', label: 'Email + ICS' },
  { value: 'portal_only', label: 'Portal only' },
];

const FIELD_CLASS =
  'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100';
const LABEL_CLASS = 'mb-1.5 block font-medium text-slate-700 dark:text-slate-300';
const CHECKBOX_TEXT_CLASS = 'text-sm text-slate-700 dark:text-slate-200';
const SUBTLE_PANEL_CLASS =
  'rounded-2xl border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60';
const INNER_PANEL_CLASS =
  'rounded-2xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800';
const SECONDARY_BUTTON_CLASS =
  'rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-60 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60';
const PRIMARY_BUTTON_CLASS =
  'rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200';

function getZonedDateParts(value: string, timezone: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  });
  const parts = formatter.formatToParts(date);
  const map = new Map(parts.map((part) => [part.type, part.value]));

  return {
    year: map.get('year') || '0000',
    month: map.get('month') || '01',
    day: map.get('day') || '01',
    hour: map.get('hour') || '00',
    minute: map.get('minute') || '00',
  };
}

function toDateInput(value?: string | null, timezone: string = 'UTC') {
  if (!value) return '';
  const parts = getZonedDateParts(value, timezone);
  if (!parts) return '';
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function toTimeInput(value?: string | null, timezone: string = 'UTC') {
  if (!value) return '09:00';
  const parts = getZonedDateParts(value, timezone);
  if (!parts) return '09:00';
  return `${parts.hour}:${parts.minute}`;
}

function buildIso(date: string, time: string, allDay: boolean, endOfDay: boolean = false) {
  if (!date) return '';
  if (allDay) {
    return `${date}T${endOfDay ? '23:59:59' : '00:00:00'}`;
  }
  return `${date}T${time}:00`;
}

export default function TaskModal({
  open,
  onOpenChange,
  task,
  weddings = [],
  defaultDate,
  defaultCategory = 'other',
  allowGeneralTasks = true,
  allowMeetings = true,
  allowBookingApproval = false,
  connections = [],
  staffOptions = [],
  onSuccess,
  onDelete,
}: TaskModalProps) {
  const { token } = useAdmin();
  const isEditing = Boolean(task);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [weddingId, setWeddingId] = useState('');
  const [category, setCategory] = useState<TaskCategory>('other');
  const [priority, setPriority] = useState<TaskPriority>('medium');
  const [startDate, setStartDate] = useState('');
  const [startTime, setStartTime] = useState('09:00');
  const [endDate, setEndDate] = useState('');
  const [endTime, setEndTime] = useState('10:00');
  const [allDay, setAllDay] = useState(false);
  const [dueDate, setDueDate] = useState('');
  const [reminderMinutes, setReminderMinutes] = useState<number | ''>('');
  const [notes, setNotes] = useState('');
  const [color, setColor] = useState('');
  const [syncToGoogle, setSyncToGoogle] = useState(true);
  const [isRecurring, setIsRecurring] = useState(false);
  const [recurrencePreset, setRecurrencePreset] = useState<'weekly' | 'biweekly' | 'monthly'>('weekly');
  const [recurrenceCount, setRecurrenceCount] = useState(8);
  const [assignedUserIds, setAssignedUserIds] = useState<string[]>([]);
  const [coupleAttendeeEmails, setCoupleAttendeeEmails] = useState('');
  const [timezone, setTimezone] = useState('UTC');
  const [visibilityMode, setVisibilityMode] = useState<VisibilityMode>('details');
  const [calendarSyncPolicy, setCalendarSyncPolicy] = useState<CalendarSyncPolicy>('owner_only');
  const [inviteDeliveryMode, setInviteDeliveryMode] = useState<InviteDeliveryMode>('email_ics');
  const [conferenceProvider, setConferenceProvider] = useState('');
  const [conferenceUrl, setConferenceUrl] = useState('');
  const [customTargetsEnabled, setCustomTargetsEnabled] = useState(false);
  const [selectedConnectionIds, setSelectedConnectionIds] = useState<string[]>([]);
  const [syncPolicyTouched, setSyncPolicyTouched] = useState(false);
  const [meetingMutationIntent, setMeetingMutationIntent] = useState(() =>
    createCalendarMutationIntent()
  );
  const [loading, setLoading] = useState(false);
  const [resolutionLoading, setResolutionLoading] = useState<'approve' | 'decline' | null>(null);
  const [error, setError] = useState('');

  const writableConnections = useMemo(
    () =>
      connections.filter(
        (connection) =>
          connection.is_writable &&
          connection.sync_enabled &&
          connection.connection_status === 'active'
      ),
    [connections]
  );
  const writableTaskConnections = useMemo(
    () =>
      connections.filter(
        (connection) =>
          connection.connection_status === 'active' &&
          connection.task_sync_enabled &&
          Boolean(connection.task_sync_tasklist_id)
      ),
    [connections]
  );
  const availableCategories = useMemo(() => {
    const allowed = new Set<TaskCategory>(
      CATEGORIES.filter((item) => {
        if (item === 'meeting') return allowMeetings;
        return allowGeneralTasks;
      })
    );
    if (task?.category && CATEGORIES.includes(task.category as TaskCategory)) {
      allowed.add(task.category as TaskCategory);
    }
    return CATEGORIES.filter((item) => allowed.has(item));
  }, [allowGeneralTasks, allowMeetings, task?.category]);
  const defaultSelectableCategory = useMemo(() => {
    if (availableCategories.includes(defaultCategory)) {
      return defaultCategory;
    }
    return availableCategories[0] || 'meeting';
  }, [availableCategories, defaultCategory]);

  const isMeetingMode =
    category === 'meeting' || task?.schedule_item_type === 'meeting' || task?.category === 'meeting';
  const canResolvePendingBooking = Boolean(
    isEditing &&
      task &&
      isMeetingMode &&
      task.meeting_status === 'pending_approval' &&
      allowBookingApproval
  );

  useEffect(() => {
    if (!open) return;

    const initialDate = defaultDate ? getLocalDateString(defaultDate) : getLocalDateString();
    const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

    if (task) {
      const taskTimezone = task.timezone || browserTimezone;
      setTitle(task.title);
      setDescription(task.description || task.notes || '');
      setWeddingId(task.wedding_id || '');
      setCategory((task.category as TaskCategory) || 'other');
      setPriority((task.priority as TaskPriority) || 'medium');
      setStartDate(toDateInput(task.start_date, taskTimezone));
      setStartTime(toTimeInput(task.start_date, taskTimezone));
      setEndDate(toDateInput(task.end_date || task.start_date, taskTimezone));
      setEndTime(toTimeInput(task.end_date || task.start_date, taskTimezone));
      setAllDay(task.all_day);
      setDueDate(toDateInput(task.due_date, taskTimezone));
      setReminderMinutes(task.reminder_minutes ?? '');
      setNotes(task.notes || '');
      setColor(task.color || '');
      setSyncToGoogle(task.external_sync_requested);
      setIsRecurring(task.is_recurring || false);
      setAssignedUserIds(task.assigned_user_ids || []);
      setCoupleAttendeeEmails((task.couple_attendee_emails || []).join(', '));
      setTimezone(taskTimezone);
      setVisibilityMode((task.visibility_mode as VisibilityMode) || 'details');
      setCalendarSyncPolicy((task.calendar_sync_policy as CalendarSyncPolicy) || 'owner_only');
      setInviteDeliveryMode((task.invite_delivery_mode as InviteDeliveryMode) || 'email_ics');
      setConferenceProvider(task.conference_provider || '');
      setConferenceUrl(task.conference_url || '');
      setCustomTargetsEnabled(Boolean(task.sync_target_override_enabled));
      setSelectedConnectionIds(task.sync_target_connection_ids || []);
      setSyncPolicyTouched(true);

      if (task.recurrence_rule) {
        if (task.recurrence_rule.includes('INTERVAL=2')) {
          setRecurrencePreset('biweekly');
        } else if (task.recurrence_rule.includes('FREQ=MONTHLY')) {
          setRecurrencePreset('monthly');
        } else {
          setRecurrencePreset('weekly');
        }
        const countMatch = task.recurrence_rule.match(/COUNT=(\d+)/);
        setRecurrenceCount(countMatch ? Number.parseInt(countMatch[1], 10) : 8);
      } else {
        setRecurrencePreset('weekly');
        setRecurrenceCount(8);
      }
    } else {
      setTitle('');
      setDescription('');
      setWeddingId('');
      setCategory(defaultSelectableCategory);
      setPriority('medium');
      setStartDate(initialDate);
      setStartTime('09:00');
      setEndDate(initialDate);
      setEndTime('10:00');
      setAllDay(false);
      setDueDate('');
      setReminderMinutes('');
      setNotes('');
      setColor('');
      setSyncToGoogle(writableTaskConnections.length > 0);
      setIsRecurring(false);
      setRecurrencePreset('weekly');
      setRecurrenceCount(8);
      setAssignedUserIds([]);
      setCoupleAttendeeEmails('');
      setTimezone(browserTimezone);
      setVisibilityMode('details');
      setCalendarSyncPolicy('owner_only');
      setInviteDeliveryMode('email_ics');
      setConferenceProvider('');
      setConferenceUrl('');
      setCustomTargetsEnabled(false);
      setSelectedConnectionIds([]);
      setSyncPolicyTouched(false);
    }

    setMeetingMutationIntent(createCalendarMutationIntent());
    setError('');
  }, [defaultSelectableCategory, open, task, defaultDate, writableTaskConnections.length]);

  useEffect(() => {
    if (category !== 'meeting') {
      setCalendarSyncPolicy('owner_only');
      setInviteDeliveryMode('email_ics');
      setVisibilityMode('details');
      setCustomTargetsEnabled(false);
      setSelectedConnectionIds([]);
      setSyncPolicyTouched(false);
    } else if (!syncPolicyTouched) {
      setCalendarSyncPolicy(assignedUserIds.length > 0 ? 'assigned_only' : 'owner_only');
    }
  }, [assignedUserIds.length, category, syncPolicyTouched]);

  const buildRecurrenceRule = () => {
    if (!isRecurring) return undefined;

    const start = startDate ? new Date(`${startDate}T${startTime || '09:00'}`) : new Date();
    const byDay = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA'][start.getDay()] || 'MO';

    switch (recurrencePreset) {
      case 'biweekly':
        return `FREQ=WEEKLY;INTERVAL=2;BYDAY=${byDay};COUNT=${recurrenceCount}`;
      case 'monthly':
        return `FREQ=MONTHLY;COUNT=${recurrenceCount}`;
      case 'weekly':
      default:
        return `FREQ=WEEKLY;BYDAY=${byDay};COUNT=${recurrenceCount}`;
    }
  };

  const toggleArrayValue = (
    value: string,
    values: string[],
    setter: React.Dispatch<React.SetStateAction<string[]>>
  ) => {
    setter(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!token) {
      setError('Not authenticated');
      return;
    }

    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    if (!startDate) {
      setError('Start date is required');
      return;
    }

    const startDateTime = buildIso(startDate, startTime, allDay);
    const endDateTime = buildIso(endDate || startDate, endTime, allDay, allDay);
    const attendeeEmails = coupleAttendeeEmails
      .split(',')
      .map((entry) => entry.trim())
      .filter(Boolean);

    const payload: ScheduleItemPayload = {
      title: title.trim(),
      description: description.trim() || undefined,
      wedding_id: weddingId || undefined,
      category,
      priority,
      start_date: startDateTime,
      end_date: endDateTime,
      all_day: allDay,
      due_date: dueDate ? `${dueDate}T23:59:59` : undefined,
      reminder_minutes: reminderMinutes || undefined,
      is_recurring: isRecurring,
      recurrence_rule: buildRecurrenceRule(),
      color: color || undefined,
      notes: notes || undefined,
      assigned_user_ids: isMeetingMode ? assignedUserIds : undefined,
      schedule_item_type: isMeetingMode ? 'meeting' : 'task',
      visibility_mode: isMeetingMode ? visibilityMode : undefined,
      calendar_sync_policy: isMeetingMode ? calendarSyncPolicy : undefined,
      sync_target_override_enabled: isMeetingMode ? customTargetsEnabled : undefined,
      timezone: timezone || undefined,
      couple_attendee_emails: isMeetingMode ? attendeeEmails : undefined,
      conference_provider: isMeetingMode ? conferenceProvider || undefined : undefined,
      conference_url: isMeetingMode ? conferenceUrl || undefined : undefined,
      invite_delivery_mode: isMeetingMode ? inviteDeliveryMode : undefined,
      sync_target_connection_ids:
        isMeetingMode && customTargetsEnabled ? selectedConnectionIds : undefined,
      external_sync_requested: !isMeetingMode
        ? syncToGoogle && writableTaskConnections.length > 0
        : undefined,
      expected_version: isMeetingMode && task ? task.version : undefined,
    };

    setLoading(true);
    setError('');

    try {
      if (isMeetingMode) {
        if (task) {
          await updateMeeting(token, task.id, payload, meetingMutationIntent);
        } else {
          await createMeeting(token, payload, meetingMutationIntent);
        }
      } else if (task) {
        await updateTask(token, task.id, payload);
      } else {
        await createTask(token, payload);
      }

      onSuccess?.();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save schedule item');
    } finally {
      setLoading(false);
    }
  };

  const handleApproveBooking = async () => {
    if (!token || !task) return;
    setResolutionLoading('approve');
    setError('');
    try {
      await approveCoupleBooking(token, task.id, task.version);
      onSuccess?.();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve booking');
    } finally {
      setResolutionLoading(null);
    }
  };

  const handleDeclineBooking = async () => {
    if (!token || !task) return;
    const reason = window.prompt('Optional decline reason')?.trim() || undefined;
    setResolutionLoading('decline');
    setError('');
    try {
      await declineCoupleBooking(token, task.id, task.version, reason);
      onSuccess?.();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to decline booking');
    } finally {
      setResolutionLoading(null);
    }
  };

  const colorOptions = [
    { value: '', label: 'Default' },
    { value: '#a4bdfc', label: 'Lavender' },
    { value: '#7ae7bf', label: 'Sage' },
    { value: '#dbadff', label: 'Grape' },
    { value: '#ff887c', label: 'Flamingo' },
    { value: '#fbd75b', label: 'Banana' },
    { value: '#ffb878', label: 'Tangerine' },
    { value: '#46d6db', label: 'Peacock' },
    { value: '#5484ed', label: 'Blueberry' },
    { value: '#51b749', label: 'Basil' },
    { value: '#dc2127', label: 'Tomato' },
  ];

  const reminderOptions = [
    { value: '', label: 'No reminder' },
    { value: 15, label: '15 minutes before' },
    { value: 30, label: '30 minutes before' },
    { value: 60, label: '1 hour before' },
    { value: 120, label: '2 hours before' },
    { value: 1440, label: '1 day before' },
    { value: 2880, label: '2 days before' },
    { value: 10080, label: '1 week before' },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto rounded-3xl border border-slate-200 bg-white text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
        <DialogHeader>
          <DialogTitle className="text-slate-900 dark:text-slate-100">
            {isEditing ? 'Edit Schedule Item' : 'Create Schedule Item'}
          </DialogTitle>
          <DialogDescription className="text-slate-500 dark:text-slate-400">
            Tasks stay internal by default. Meetings use the planner-business scheduling flow and
            sync to explicit external calendar targets.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
              {error}
            </div>
          )}

          {canResolvePendingBooking && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-900 dark:bg-amber-950/30">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">
                    Couple booking pending approval
                  </p>
                  <p className="mt-1 text-xs leading-5 text-amber-800 dark:text-amber-200">
                    Approving syncs the meeting to the selected calendar target and queues the
                    invite. Declining cancels the request.
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={() => void handleDeclineBooking()}
                    disabled={Boolean(resolutionLoading) || loading}
                    className="rounded-lg border border-amber-300 px-3 py-2 text-xs font-semibold text-amber-900 transition hover:bg-amber-100 disabled:opacity-60 dark:border-amber-700 dark:text-amber-100 dark:hover:bg-amber-900/50"
                  >
                    {resolutionLoading === 'decline' ? 'Declining...' : 'Decline'}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleApproveBooking()}
                    disabled={Boolean(resolutionLoading) || loading}
                    className="rounded-lg bg-amber-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-amber-800 disabled:opacity-60 dark:bg-amber-200 dark:text-amber-950 dark:hover:bg-amber-100"
                  >
                    {resolutionLoading === 'approve' ? 'Approving...' : 'Approve'}
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <label className={`text-sm ${LABEL_CLASS}`}>Title</label>
              <input
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className={`${FIELD_CLASS} text-sm`}
                placeholder="Planning call, venue walkthrough, checklist review..."
                required
              />
            </div>

            <label className="text-sm">
              <span className={LABEL_CLASS}>Wedding</span>
              <select
                value={weddingId}
                onChange={(event) => setWeddingId(event.target.value)}
                className={FIELD_CLASS}
              >
                <option value="">No wedding</option>
                {weddings.map((wedding) => (
                  <option key={wedding.id} value={wedding.id}>
                    {wedding.couple_names}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm">
              <span className={LABEL_CLASS}>Type</span>
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value as TaskCategory)}
                className={FIELD_CLASS}
                disabled={!isEditing && availableCategories.length === 1}
              >
                {availableCategories.map((item) => (
                  <option key={item} value={item}>
                    {CATEGORY_LABELS[item]}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm">
              <span className={LABEL_CLASS}>Priority</span>
              <select
                value={priority}
                onChange={(event) => setPriority(event.target.value as TaskPriority)}
                className={FIELD_CLASS}
              >
                {PRIORITIES.map((item) => (
                  <option key={item} value={item}>
                    {PRIORITY_CONFIG[item].label}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm">
              <span className={LABEL_CLASS}>Timezone</span>
              <input
                type="text"
                value={timezone}
                onChange={(event) => setTimezone(event.target.value)}
                className={FIELD_CLASS}
                placeholder="America/Chicago"
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className={`block text-sm ${LABEL_CLASS}`}>Start</label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className={`${FIELD_CLASS} text-sm`}
                  required
                />
                {!allDay && (
                  <input
                    type="time"
                    value={startTime}
                    onChange={(event) => setStartTime(event.target.value)}
                    className={`w-36 ${FIELD_CLASS} text-sm`}
                  />
                )}
              </div>
            </div>

            <div className="space-y-2">
              <label className={`block text-sm ${LABEL_CLASS}`}>End</label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={endDate}
                  onChange={(event) => setEndDate(event.target.value)}
                  className={`${FIELD_CLASS} text-sm`}
                />
                {!allDay && (
                  <input
                    type="time"
                    value={endTime}
                    onChange={(event) => setEndTime(event.target.value)}
                    className={`w-36 ${FIELD_CLASS} text-sm`}
                  />
                )}
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-4">
            <label className={`flex items-center gap-2 px-3 py-3 ${SUBTLE_PANEL_CLASS} ${CHECKBOX_TEXT_CLASS}`}>
              <input
                type="checkbox"
                checked={allDay}
                onChange={(event) => setAllDay(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
              />
              All day
            </label>

            <label className="text-sm md:col-span-2">
              <span className={LABEL_CLASS}>Reminder</span>
              <select
                value={reminderMinutes}
                onChange={(event) =>
                  setReminderMinutes(event.target.value ? Number(event.target.value) : '')
                }
                className={FIELD_CLASS}
              >
                {reminderOptions.map((option) => (
                  <option key={String(option.value)} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm">
              <span className={LABEL_CLASS}>Color</span>
              <select
                value={color}
                onChange={(event) => setColor(event.target.value)}
                className={FIELD_CLASS}
              >
                {colorOptions.map((option) => (
                  <option key={option.value || 'default'} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm">
              <span className={LABEL_CLASS}>Due date</span>
              <input
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                className={FIELD_CLASS}
              />
            </label>

            {!isMeetingMode && (
              <label className={`flex items-center gap-2 px-3 py-3 ${SUBTLE_PANEL_CLASS} ${CHECKBOX_TEXT_CLASS}`}>
                <input
                  type="checkbox"
                  checked={syncToGoogle && writableTaskConnections.length > 0}
                  onChange={(event) => setSyncToGoogle(event.target.checked)}
                  disabled={writableTaskConnections.length === 0}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                />
                Sync this task to the connected task list
              </label>
            )}
          </div>

          <div className={`${SUBTLE_PANEL_CLASS} p-4`}>
            <div className="flex flex-wrap items-center gap-4">
              <label className={`flex items-center gap-2 ${CHECKBOX_TEXT_CLASS}`}>
                <input
                  type="checkbox"
                  checked={isRecurring}
                  onChange={(event) => setIsRecurring(event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                />
                Recurring
              </label>
              {isRecurring && (
                <>
                  <select
                    value={recurrencePreset}
                    onChange={(event) =>
                      setRecurrencePreset(event.target.value as 'weekly' | 'biweekly' | 'monthly')
                    }
                    className={`${FIELD_CLASS} text-sm`}
                  >
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Every 2 weeks</option>
                    <option value="monthly">Monthly</option>
                  </select>
                  <input
                    type="number"
                    min={1}
                    max={52}
                    value={recurrenceCount}
                    onChange={(event) =>
                      setRecurrenceCount(
                        Math.max(1, Math.min(52, Number.parseInt(event.target.value || '1', 10)))
                      )
                    }
                    className={`w-28 ${FIELD_CLASS} text-sm`}
                  />
                </>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <label className={`block text-sm ${LABEL_CLASS}`}>Description</label>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className={`${FIELD_CLASS} text-sm`}
              placeholder="Agenda, context, next steps, or task notes..."
            />
          </div>

          {isMeetingMode && (
            <section className={`space-y-4 p-4 ${INNER_PANEL_CLASS}`}>
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Meeting delivery and sync</h3>
                <p className="mt-1 text-xs leading-6 text-slate-500 dark:text-slate-400">
                  Default target resolution is: explicit override, else assigned staff default
                  writable calendar if allowed, else owner default writable calendar if allowed,
                  else internal-only with sync marked not configured.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className={`block text-sm ${LABEL_CLASS}`}>Assigned staff</label>
                  <div className={`space-y-2 p-3 ${SUBTLE_PANEL_CLASS}`}>
                    {staffOptions.length === 0 ? (
                      <p className="text-xs text-slate-500 dark:text-slate-400">No staff options available.</p>
                    ) : (
                      staffOptions.map((staff) => (
                        <label
                          key={staff.id}
                          className={`flex items-center gap-2 ${CHECKBOX_TEXT_CLASS}`}
                        >
                          <input
                            type="checkbox"
                            checked={assignedUserIds.includes(staff.id)}
                            onChange={() =>
                              toggleArrayValue(staff.id, assignedUserIds, setAssignedUserIds)
                            }
                            className="h-4 w-4 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                          />
                          {staff.label}
                        </label>
                      ))
                    )}
                  </div>
                </div>

                <div className="space-y-4">
                  <label className="text-sm">
                    <span className={LABEL_CLASS}>
                      Couple attendee emails
                    </span>
                    <textarea
                      value={coupleAttendeeEmails}
                      onChange={(event) => setCoupleAttendeeEmails(event.target.value)}
                      rows={4}
                      className={`${FIELD_CLASS} text-sm`}
                      placeholder="comma-separated emails"
                    />
                  </label>

                  <label className="text-sm">
                    <span className={LABEL_CLASS}>Invite delivery</span>
                    <select
                      value={inviteDeliveryMode}
                      onChange={(event) =>
                        setInviteDeliveryMode(event.target.value as InviteDeliveryMode)
                      }
                      className={FIELD_CLASS}
                    >
                      {INVITE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm">
                  <span className={LABEL_CLASS}>Sync policy</span>
                  <select
                    value={calendarSyncPolicy}
                    onChange={(event) => {
                      setCalendarSyncPolicy(event.target.value as CalendarSyncPolicy);
                      setSyncPolicyTouched(true);
                    }}
                    className={FIELD_CLASS}
                  >
                    {SYNC_POLICY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="text-sm">
                  <span className={LABEL_CLASS}>Internal visibility</span>
                  <select
                    value={visibilityMode}
                    onChange={(event) => setVisibilityMode(event.target.value as VisibilityMode)}
                    className={FIELD_CLASS}
                  >
                    {VISIBILITY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm">
                  <span className={LABEL_CLASS}>
                    Conference provider
                  </span>
                  <input
                    type="text"
                    value={conferenceProvider}
                    onChange={(event) => setConferenceProvider(event.target.value)}
                    className={FIELD_CLASS}
                    placeholder="Zoom, Google Meet, phone call..."
                  />
                </label>

                <label className="text-sm">
                  <span className={LABEL_CLASS}>Conference URL</span>
                  <input
                    type="url"
                    value={conferenceUrl}
                    onChange={(event) => setConferenceUrl(event.target.value)}
                    className={FIELD_CLASS}
                    placeholder="https://..."
                  />
                </label>
              </div>

              <div className={`${SUBTLE_PANEL_CLASS} p-4`}>
                <label className={`flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200`}>
                  <input
                    type="checkbox"
                    checked={customTargetsEnabled}
                    onChange={(event) => {
                      setCustomTargetsEnabled(event.target.checked);
                      if (!event.target.checked) {
                        setSelectedConnectionIds([]);
                      }
                    }}
                    className="h-4 w-4 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                  />
                  Use explicit calendar target override
                </label>

                {customTargetsEnabled && (
                  <div className="mt-3 space-y-2">
                    {writableConnections.length === 0 ? (
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        No writable active calendar connections are available.
                      </p>
                    ) : (
                      writableConnections.map((connection) => (
                        <label
                          key={connection.id}
                          className={`flex items-center gap-2 ${CHECKBOX_TEXT_CLASS}`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedConnectionIds.includes(connection.id)}
                            onChange={() =>
                              toggleArrayValue(
                                connection.id,
                                selectedConnectionIds,
                                setSelectedConnectionIds
                              )
                            }
                            className="h-4 w-4 rounded border-slate-300 text-slate-900 dark:border-slate-600 dark:bg-slate-800"
                          />
                          <span>
                            {connection.calendar_name || connection.calendar_id || 'Calendar'} •{' '}
                            {connection.user_email || connection.provider_account_email || 'Unknown user'}
                          </span>
                        </label>
                      ))
                    )}
                    <p className="text-xs leading-6 text-slate-500 dark:text-slate-400">
                      Only targets allowed by permission and sync policy will be honored. If none
                      are allowed, the meeting stays internal-only.
                    </p>
                  </div>
                )}
              </div>
            </section>
          )}

          <DialogFooter className="border-t border-slate-200 pt-4 dark:border-slate-700">
            <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                {isEditing && task && onDelete && (
                  <button
                    type="button"
                    onClick={() => void onDelete(task)}
                    disabled={loading}
                    className="rounded-xl border border-rose-300 px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-60 dark:border-rose-900 dark:text-rose-200 dark:hover:bg-rose-950/40"
                  >
                    Delete
                  </button>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => onOpenChange(false)}
                  disabled={loading || Boolean(resolutionLoading)}
                  className={SECONDARY_BUTTON_CLASS}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading || Boolean(resolutionLoading)}
                  className={PRIMARY_BUTTON_CLASS}
                >
                  {loading ? 'Saving...' : isEditing ? 'Save changes' : 'Create'}
                </button>
              </div>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
