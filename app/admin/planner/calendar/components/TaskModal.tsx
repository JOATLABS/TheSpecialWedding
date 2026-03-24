'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/Dialog';
import {
  PlannerTask,
  CreateTaskInput,
  UpdateTaskInput,
  TaskCategory,
  TaskPriority,
  CATEGORY_LABELS,
  PRIORITY_CONFIG,
  createTask,
  updateTask,
} from '@/services/calendarApi';
import { useAdmin } from '@/contexts/AdminContext';

interface TaskModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  task?: PlannerTask | null; // If provided, we're editing
  weddings?: Array<{ id: string; couple_names: string }>;
  defaultDate?: Date;
  onSuccess?: (task: PlannerTask) => void;
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

export default function TaskModal({
  open,
  onOpenChange,
  task,
  weddings = [],
  defaultDate,
  onSuccess,
}: TaskModalProps) {
  const { token } = useAdmin();
  const isEditing = !!task;

  // Form state
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

  // Recurrence state
  const [isRecurring, setIsRecurring] = useState(false);
  const [recurrencePreset, setRecurrencePreset] = useState<'weekly' | 'biweekly' | 'monthly'>('weekly');
  const [recurrenceCount, setRecurrenceCount] = useState(8);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Reset form when modal opens/closes or task changes
  useEffect(() => {
    if (open) {
      if (task) {
        // Editing existing task
        setTitle(task.title);
        setDescription(task.description || '');
        setWeddingId(task.wedding_id || '');
        setCategory((task.category as TaskCategory) || 'other');
        setPriority((task.priority as TaskPriority) || 'medium');
        setAllDay(task.all_day);
        setNotes(task.notes || '');
        setColor(task.color || '');
        setSyncToGoogle(task.synced_to_google);

        // Parse dates
        if (task.start_date) {
          const start = new Date(task.start_date);
          setStartDate(start.toISOString().split('T')[0]);
          setStartTime(start.toTimeString().slice(0, 5));
        }
        if (task.end_date) {
          const end = new Date(task.end_date);
          setEndDate(end.toISOString().split('T')[0]);
          setEndTime(end.toTimeString().slice(0, 5));
        }
        if (task.due_date) {
          const due = new Date(task.due_date);
          setDueDate(due.toISOString().split('T')[0]);
        }
        if (task.reminder_minutes) {
          setReminderMinutes(task.reminder_minutes);
        }
        // Load recurrence
        setIsRecurring(task.is_recurring || false);
        if (task.recurrence_rule) {
          // Parse existing RRULE to determine preset
          const rule = task.recurrence_rule;
          if (rule.includes('INTERVAL=2')) {
            setRecurrencePreset('biweekly');
          } else if (rule.includes('FREQ=MONTHLY')) {
            setRecurrencePreset('monthly');
          } else {
            setRecurrencePreset('weekly');
          }
          const countMatch = rule.match(/COUNT=(\d+)/);
          if (countMatch) {
            setRecurrenceCount(parseInt(countMatch[1]));
          }
        }
      } else {
        // Creating new task
        resetForm();
        if (defaultDate) {
          setStartDate(defaultDate.toISOString().split('T')[0]);
          setEndDate(defaultDate.toISOString().split('T')[0]);
        } else {
          const today = new Date().toISOString().split('T')[0];
          setStartDate(today);
          setEndDate(today);
        }
      }
    }
  }, [open, task, defaultDate]);

  const resetForm = () => {
    setTitle('');
    setDescription('');
    setWeddingId('');
    setCategory('other');
    setPriority('medium');
    setStartDate('');
    setStartTime('09:00');
    setEndDate('');
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
    setError('');
  };

  // Build iCal RRULE string from preset options
  const buildRecurrenceRule = (): string | undefined => {
    if (!isRecurring) return undefined;
    const dayMap: Record<string, string> = {
      '0': 'SU', '1': 'MO', '2': 'TU', '3': 'WE', '4': 'TH', '5': 'FR', '6': 'SA',
    };
    const startDayOfWeek = startDate
      ? dayMap[new Date(`${startDate}T${startTime || '09:00'}`).getDay().toString()] || 'MO'
      : 'MO';
    switch (recurrencePreset) {
      case 'weekly':
        return `FREQ=WEEKLY;BYDAY=${startDayOfWeek};COUNT=${recurrenceCount}`;
      case 'biweekly':
        return `FREQ=WEEKLY;INTERVAL=2;BYDAY=${startDayOfWeek};COUNT=${recurrenceCount}`;
      case 'monthly':
        return `FREQ=MONTHLY;COUNT=${recurrenceCount}`;
      default:
        return `FREQ=WEEKLY;BYDAY=${startDayOfWeek};COUNT=${recurrenceCount}`;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

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

    setLoading(true);
    setError('');

    try {
      // Build datetime strings
      const startDateTime = allDay
        ? `${startDate}T00:00:00Z`
        : `${startDate}T${startTime}:00Z`;

      const endDateTime = allDay
        ? (endDate ? `${endDate}T23:59:59Z` : `${startDate}T23:59:59Z`)
        : (endDate ? `${endDate}T${endTime}:00Z` : startDateTime);

      if (isEditing && task) {
        // Update existing task
        const updates: UpdateTaskInput = {
          title,
          description: description || undefined,
          wedding_id: weddingId || undefined,
          category,
          priority,
          start_date: startDateTime,
          end_date: endDateTime,
          all_day: allDay,
          due_date: dueDate ? `${dueDate}T23:59:59Z` : undefined,
          reminder_minutes: reminderMinutes || undefined,
          is_recurring: isRecurring,
          recurrence_rule: buildRecurrenceRule(),
          notes: notes || undefined,
          color: color || undefined,
        };

        const updatedTask = await updateTask(token, task.id, updates);
        onSuccess?.(updatedTask);
      } else {
        // Create new task
        const newTask: CreateTaskInput = {
          title,
          description: description || undefined,
          wedding_id: weddingId || undefined,
          category,
          priority,
          start_date: startDateTime,
          end_date: endDateTime,
          all_day: allDay,
          due_date: dueDate ? `${dueDate}T23:59:59Z` : undefined,
          reminder_minutes: reminderMinutes || undefined,
          is_recurring: isRecurring,
          recurrence_rule: buildRecurrenceRule(),
          notes: notes || undefined,
          color: color || undefined,
          sync_to_google: syncToGoogle,
        };

        const createdTask = await createTask(token, newTask);
        onSuccess?.(createdTask);
      }

      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save task');
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
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? 'Edit Task' : 'Create New Task'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3 mt-3">
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-2">
              <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
            </div>
          )}

          {/* Row 1: Title */}
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Task title *"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
            required
          />

          {/* Row 2: Wedding, Category, Priority, Color */}
          <div className="grid grid-cols-4 gap-3">
            <select
              value={weddingId}
              onChange={(e) => setWeddingId(e.target.value)}
              className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100"
            >
              <option value="">No wedding</option>
              {weddings.map((w, idx) => (
                <option key={w.id || `wedding-${idx}`} value={w.id}>{w.couple_names}</option>
              ))}
            </select>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as TaskCategory)}
              className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>{CATEGORY_LABELS[cat]}</option>
              ))}
            </select>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskPriority)}
              className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100"
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>{PRIORITY_CONFIG[p].label}</option>
              ))}
            </select>
            <select
              value={color}
              onChange={(e) => setColor(e.target.value)}
              className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100"
            >
              {colorOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Row 3: Start date/time, End date/time, All-day */}
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Start *</label>
              <div className="flex gap-1.5">
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                  className="flex-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100" required />
                {!allDay && <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)}
                  className="w-32 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100" />}
              </div>
            </div>
            <div className="flex-1">
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">End</label>
              <div className="flex gap-1.5">
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                  className="flex-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100" />
                {!allDay && <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)}
                  className="w-32 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100" />}
              </div>
            </div>
            <label className="flex items-center gap-1.5 pb-1.5 whitespace-nowrap cursor-pointer">
              <input type="checkbox" checked={allDay} onChange={(e) => setAllDay(e.target.checked)}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded" />
              <span className="text-xs text-gray-600 dark:text-gray-400">All-day</span>
            </label>
          </div>

          {/* Row 4: Due date, Reminder, Google sync */}
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Due date</label>
              <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100" />
            </div>
            <div className="flex-1">
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Reminder</label>
              <select value={reminderMinutes} onChange={(e) => setReminderMinutes(e.target.value ? Number(e.target.value) : '')}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100">
                {reminderOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            {!isEditing && (
              <label className="flex items-center gap-1.5 pb-1.5 whitespace-nowrap cursor-pointer">
                <input type="checkbox" checked={syncToGoogle} onChange={(e) => setSyncToGoogle(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 border-gray-300 rounded" />
                <span className="text-xs text-gray-600 dark:text-gray-400">Google Cal</span>
              </label>
            )}
          </div>

          {/* Row 5: Recurrence */}
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" checked={isRecurring} onChange={(e) => setIsRecurring(e.target.checked)}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded" />
              <span className="text-xs text-gray-600 dark:text-gray-400">Recurring</span>
            </label>
            {isRecurring && (
              <>
                <select value={recurrencePreset} onChange={(e) => setRecurrencePreset(e.target.value as 'weekly' | 'biweekly' | 'monthly')}
                  className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100">
                  <option value="weekly">Weekly</option>
                  <option value="biweekly">Every 2 weeks</option>
                  <option value="monthly">Monthly</option>
                </select>
                <div className="flex items-center gap-1.5">
                  <input type="number" value={recurrenceCount} onChange={(e) => setRecurrenceCount(Math.max(1, Math.min(52, parseInt(e.target.value) || 1)))}
                    min={1} max={52}
                    className="w-16 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100" />
                  <span className="text-xs text-gray-500 dark:text-gray-400">occurrences</span>
                </div>
              </>
            )}
          </div>

          {/* Row 6: Description (single field, replaces both Description + Notes) */}
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description / notes..."
            rows={2}
            className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100"
          />

          {/* Hidden notes field to preserve data for existing tasks */}
          {isEditing && notes && (
            <input type="hidden" value={notes} />
          )}

          {/* Row 6: Actions */}
          <DialogFooter className="pt-2 border-t border-gray-200 dark:border-gray-700">
            <button type="button" onClick={() => onOpenChange(false)}
              className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              disabled={loading}>
              Cancel
            </button>
            <button type="submit" disabled={loading}
              className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50">
              {loading ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Task'}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
