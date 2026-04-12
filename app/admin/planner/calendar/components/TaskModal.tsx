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
  createCalendarMutationIntent,
  createMeeting,
  createTask,
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

  useEffect(() => {
    if (!open) return;

    const initialDate = defaultDate ? defaultDate.toISOString().slice(0, 10) : new Date().toISOString().slice(0, 10);
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
      setSyncToGoogle(task.external_sync_requested ?? task.synced_to_google);
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
      setSyncToGoogle(true);
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
  }, [defaultSelectableCategory, open, task, defaultDate]);

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
      external_sync_requested: !isMeetingMode ? syncToGoogle : undefined,
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
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Schedule Item' : 'Create Schedule Item'}</DialogTitle>
          <DialogDescription>
            Tasks stay internal by default. Meetings use the planner-business scheduling flow and
            sync to explicit external calendar targets.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Title</label>
              <input
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900"
                placeholder="Planning call, venue walkthrough, checklist review..."
                required
              />
            </div>

            <label className="text-sm">
              <span className="mb-1.5 block font-medium text-slate-700">Wedding</span>
              <select
                value={weddingId}
                onChange={(event) => setWeddingId(event.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
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
              <span className="mb-1.5 block font-medium text-slate-700">Type</span>
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value as TaskCategory)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
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
              <span className="mb-1.5 block font-medium text-slate-700">Priority</span>
              <select
                value={priority}
                onChange={(event) => setPriority(event.target.value as TaskPriority)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
              >
                {PRIORITIES.map((item) => (
                  <option key={item} value={item}>
                    {PRIORITY_CONFIG[item].label}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm">
              <span className="mb-1.5 block font-medium text-slate-700">Timezone</span>
              <input
                type="text"
                value={timezone}
                onChange={(event) => setTimezone(event.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
                placeholder="America/Chicago"
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">Start</label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900"
                  required
                />
                {!allDay && (
                  <input
                    type="time"
                    value={startTime}
                    onChange={(event) => setStartTime(event.target.value)}
                    className="w-36 rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900"
                  />
                )}
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">End</label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={endDate}
                  onChange={(event) => setEndDate(event.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900"
                />
                {!allDay && (
                  <input
                    type="time"
                    value={endTime}
                    onChange={(event) => setEndTime(event.target.value)}
                    className="w-36 rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900"
                  />
                )}
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-4">
            <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={allDay}
                onChange={(event) => setAllDay(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-slate-900"
              />
              All day
            </label>

            <label className="text-sm md:col-span-2">
              <span className="mb-1.5 block font-medium text-slate-700">Reminder</span>
              <select
                value={reminderMinutes}
                onChange={(event) =>
                  setReminderMinutes(event.target.value ? Number(event.target.value) : '')
                }
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
              >
                {reminderOptions.map((option) => (
                  <option key={String(option.value)} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm">
              <span className="mb-1.5 block font-medium text-slate-700">Color</span>
              <select
                value={color}
                onChange={(event) => setColor(event.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
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
              <span className="mb-1.5 block font-medium text-slate-700">Due date</span>
              <input
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
              />
            </label>

            {!isMeetingMode && (
              <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={syncToGoogle}
                  onChange={(event) => setSyncToGoogle(event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900"
                />
                Sync this task to the default writable calendar
              </label>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={isRecurring}
                  onChange={(event) => setIsRecurring(event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900"
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
                    className="rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900"
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
                    className="w-28 rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900"
                  />
                </>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-700">Description</label>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900"
              placeholder="Agenda, context, next steps, or task notes..."
            />
          </div>

          {isMeetingMode && (
            <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Meeting delivery and sync</h3>
                <p className="mt-1 text-xs leading-6 text-slate-500">
                  Default target resolution is: explicit override, else assigned staff default
                  writable calendar if allowed, else owner default writable calendar if allowed,
                  else internal-only with sync marked not configured.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-slate-700">Assigned staff</label>
                  <div className="space-y-2 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    {staffOptions.length === 0 ? (
                      <p className="text-xs text-slate-500">No staff options available.</p>
                    ) : (
                      staffOptions.map((staff) => (
                        <label
                          key={staff.id}
                          className="flex items-center gap-2 text-sm text-slate-700"
                        >
                          <input
                            type="checkbox"
                            checked={assignedUserIds.includes(staff.id)}
                            onChange={() =>
                              toggleArrayValue(staff.id, assignedUserIds, setAssignedUserIds)
                            }
                            className="h-4 w-4 rounded border-slate-300 text-slate-900"
                          />
                          {staff.label}
                        </label>
                      ))
                    )}
                  </div>
                </div>

                <div className="space-y-4">
                  <label className="text-sm">
                    <span className="mb-1.5 block font-medium text-slate-700">
                      Couple attendee emails
                    </span>
                    <textarea
                      value={coupleAttendeeEmails}
                      onChange={(event) => setCoupleAttendeeEmails(event.target.value)}
                      rows={4}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900"
                      placeholder="comma-separated emails"
                    />
                  </label>

                  <label className="text-sm">
                    <span className="mb-1.5 block font-medium text-slate-700">Invite delivery</span>
                    <select
                      value={inviteDeliveryMode}
                      onChange={(event) =>
                        setInviteDeliveryMode(event.target.value as InviteDeliveryMode)
                      }
                      className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
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
                  <span className="mb-1.5 block font-medium text-slate-700">Sync policy</span>
                  <select
                    value={calendarSyncPolicy}
                    onChange={(event) => {
                      setCalendarSyncPolicy(event.target.value as CalendarSyncPolicy);
                      setSyncPolicyTouched(true);
                    }}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
                  >
                    {SYNC_POLICY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="text-sm">
                  <span className="mb-1.5 block font-medium text-slate-700">Internal visibility</span>
                  <select
                    value={visibilityMode}
                    onChange={(event) => setVisibilityMode(event.target.value as VisibilityMode)}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
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
                  <span className="mb-1.5 block font-medium text-slate-700">
                    Conference provider
                  </span>
                  <input
                    type="text"
                    value={conferenceProvider}
                    onChange={(event) => setConferenceProvider(event.target.value)}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
                    placeholder="Zoom, Google Meet, phone call..."
                  />
                </label>

                <label className="text-sm">
                  <span className="mb-1.5 block font-medium text-slate-700">Conference URL</span>
                  <input
                    type="url"
                    value={conferenceUrl}
                    onChange={(event) => setConferenceUrl(event.target.value)}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-slate-900"
                    placeholder="https://..."
                  />
                </label>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={customTargetsEnabled}
                    onChange={(event) => {
                      setCustomTargetsEnabled(event.target.checked);
                      if (!event.target.checked) {
                        setSelectedConnectionIds([]);
                      }
                    }}
                    className="h-4 w-4 rounded border-slate-300 text-slate-900"
                  />
                  Use explicit calendar target override
                </label>

                {customTargetsEnabled && (
                  <div className="mt-3 space-y-2">
                    {writableConnections.length === 0 ? (
                      <p className="text-xs text-slate-500">
                        No writable active calendar connections are available.
                      </p>
                    ) : (
                      writableConnections.map((connection) => (
                        <label
                          key={connection.id}
                          className="flex items-center gap-2 text-sm text-slate-700"
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
                            className="h-4 w-4 rounded border-slate-300 text-slate-900"
                          />
                          <span>
                            {connection.calendar_name || connection.calendar_id || 'Calendar'} •{' '}
                            {connection.user_email || connection.provider_account_email || 'Unknown user'}
                          </span>
                        </label>
                      ))
                    )}
                    <p className="text-xs leading-6 text-slate-500">
                      Only targets allowed by permission and sync policy will be honored. If none
                      are allowed, the meeting stays internal-only.
                    </p>
                  </div>
                )}
              </div>
            </section>
          )}

          <DialogFooter className="border-t border-slate-200 pt-4">
            <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                {isEditing && task && onDelete && (
                  <button
                    type="button"
                    onClick={() => void onDelete(task)}
                    disabled={loading}
                    className="rounded-xl border border-rose-300 px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-60"
                  >
                    Delete
                  </button>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => onOpenChange(false)}
                  disabled={loading}
                  className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-60"
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
