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
    setError('');
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
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? 'Edit Task' : 'Create New Task'}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the task details below.'
              : 'Add a new task to your planning calendar.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6 mt-4">
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
              <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Book photographer consultation"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
              required
            />
          </div>

          {/* Wedding & Category Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Wedding (optional)
              </label>
              <select
                value={weddingId}
                onChange={(e) => setWeddingId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
              >
                <option value="">No specific wedding</option>
                {weddings.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.couple_names}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as TaskCategory)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {CATEGORY_LABELS[cat]}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Priority & Color Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Priority
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as TaskPriority)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_CONFIG[p].label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Color
              </label>
              <div className="flex items-center gap-2">
                <select
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
                >
                  {colorOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                {color && (
                  <div
                    className="w-8 h-8 rounded-lg border border-gray-300"
                    style={{ backgroundColor: color }}
                  />
                )}
              </div>
            </div>
          </div>

          {/* All Day Toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="allDay"
              checked={allDay}
              onChange={(e) => setAllDay(e.target.checked)}
              className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
            />
            <label
              htmlFor="allDay"
              className="text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              All-day event
            </label>
          </div>

          {/* Date/Time Fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Start Date <span className="text-red-500">*</span>
              </label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
                  required
                />
                {!allDay && (
                  <input
                    type="time"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="w-28 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
                  />
                )}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                End Date
              </label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
                />
                {!allDay && (
                  <input
                    type="time"
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    className="w-28 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
                  />
                )}
              </div>
            </div>
          </div>

          {/* Due Date & Reminder */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Due Date (optional)
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Reminder
              </label>
              <select
                value={reminderMinutes}
                onChange={(e) =>
                  setReminderMinutes(e.target.value ? Number(e.target.value) : '')
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
              >
                {reminderOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add more details about this task..."
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Additional notes..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-gray-700 dark:text-gray-100"
            />
          </div>

          {/* Google Calendar Sync (only for new tasks) */}
          {!isEditing && (
            <div className="flex items-center gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
              <input
                type="checkbox"
                id="syncToGoogle"
                checked={syncToGoogle}
                onChange={(e) => setSyncToGoogle(e.target.checked)}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
              />
              <label
                htmlFor="syncToGoogle"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Sync to Google Calendar (if connected)
              </label>
            </div>
          )}

          <DialogFooter className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Task'}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
