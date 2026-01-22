'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import PageHeader from '@/admin/components/PageHeader';
import {
  PlannerTask,
  getMonthTasks,
  getUpcomingTasks,
  updateTask,
  deleteTask,
  CATEGORY_LABELS,
  PRIORITY_CONFIG,
  STATUS_CONFIG,
  TaskCategory,
} from '@/services/calendarApi';
import TaskModal from './components/TaskModal';
import GoogleCalendarConnect from './components/GoogleCalendarConnect';
import { toast } from 'sonner';

// AI Types
interface TaskPrioritization {
  priority_tasks: Array<{
    task: string;
    urgency: string;
    due_by: string;
    reason: string;
    category: string;
  }>;
  weekly_focus: string;
  warnings: string[];
  upcoming_milestones: Array<{
    milestone: string;
    date: string;
    importance: string;
  }>;
}

interface TimelineData {
  timeline: Array<{
    phase: string;
    start_date: string;
    end_date: string;
    milestones: Array<{
      task: string;
      category: string;
      deadline: string;
      priority: string;
      notes: string;
    }>;
  }>;
  key_dates: Array<{
    date: string;
    event: string;
    importance: string;
  }>;
  cultural_considerations: string[];
  budget_tips: string[];
}

// Helper to generate calendar grid
function generateCalendarDays(year: number, month: number) {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const daysInMonth = lastDay.getDate();
  const startingDay = firstDay.getDay(); // 0 = Sunday

  const days: (number | null)[] = [];

  // Add empty cells for days before the 1st
  for (let i = 0; i < startingDay; i++) {
    days.push(null);
  }

  // Add all days in the month
  for (let i = 1; i <= daysInMonth; i++) {
    days.push(i);
  }

  return days;
}

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

interface Wedding {
  id: string;
  couple_names: string;
}

export default function PlannerCalendarPage() {
  const { token, userProfile, fetchUserProfile } = useAdmin();
  const router = useRouter();

  // Calendar state
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth());
  const [tasks, setTasks] = useState<PlannerTask[]>([]);
  const [upcomingTasks, setUpcomingTasks] = useState<PlannerTask[]>([]);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Modal state
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<PlannerTask | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date | undefined>();

  // Filter state
  const [filterWedding, setFilterWedding] = useState<string>('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [viewMode, setViewMode] = useState<'calendar' | 'list'>('calendar');

  // AI State
  const [showAiPanel, setShowAiPanel] = useState(false);
  const [aiPrioritization, setAiPrioritization] = useState<TaskPrioritization | null>(null);
  const [aiTimeline, setAiTimeline] = useState<TimelineData | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiActiveTab, setAiActiveTab] = useState<'prioritize' | 'timeline'>('prioritize');

  // AI Functions
  const fetchAiPrioritization = async (weddingId: string) => {
    if (!token || !weddingId) return;

    setAiLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/ai/weddings/${weddingId}/prioritize-tasks`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.status === 402) {
        toast.error('Insufficient AI credits');
        return;
      }

      if (!response.ok) throw new Error('Failed to get prioritization');

      const data = await response.json();
      setAiPrioritization(data.prioritization);
      toast.success(`Got prioritization! Used ${data.credits_used} credits`);
    } catch {
      toast.error('Failed to prioritize tasks');
    } finally {
      setAiLoading(false);
    }
  };

  const fetchAiTimeline = async (weddingId: string) => {
    if (!token || !weddingId) return;

    setAiLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/ai/generate-timeline`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ wedding_id: weddingId }),
      });

      if (response.status === 402) {
        toast.error('Insufficient AI credits');
        return;
      }

      if (!response.ok) throw new Error('Failed to generate timeline');

      const data = await response.json();
      setAiTimeline(data.timeline);
      toast.success(`Generated timeline! Used ${data.credits_used} credits`);
    } catch {
      toast.error('Failed to generate timeline');
    } finally {
      setAiLoading(false);
    }
  };

  // Auth check
  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
      return;
    }

    if (!userProfile) {
      fetchUserProfile();
      return;
    }

    if (userProfile && !userProfile.is_wedding_planner && !userProfile.is_root_admin) {
      router.push('/admin');
      return;
    }
  }, [token, userProfile, fetchUserProfile, router]);

  // Fetch weddings for dropdown
  useEffect(() => {
    if (!token) return;

    const fetchWeddings = async () => {
      try {
        const baseUrl = getApiBaseUrl();
        const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setWeddings(data.map((w: any) => ({ id: w.id, couple_names: w.couple_names })));
        }
      } catch (err) {
        console.error('Failed to fetch weddings:', err);
      }
    };

    fetchWeddings();
  }, [token]);

  // Fetch tasks for current month
  const fetchTasks = useCallback(async () => {
    if (!token) return;

    try {
      setLoading(true);
      const monthTasks = await getMonthTasks(token, currentYear, currentMonth + 1);
      setTasks(monthTasks);
    } catch (err) {
      setError('Failed to load tasks');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token, currentYear, currentMonth]);

  // Fetch upcoming tasks for sidebar
  const fetchUpcoming = useCallback(async () => {
    if (!token) return;

    try {
      const upcoming = await getUpcomingTasks(token, 14, 10);
      setUpcomingTasks(upcoming);
    } catch (err) {
      console.error('Failed to fetch upcoming tasks:', err);
    }
  }, [token]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    fetchUpcoming();
  }, [fetchUpcoming]);

  // Generate calendar days
  const calendarDays = useMemo(
    () => generateCalendarDays(currentYear, currentMonth),
    [currentYear, currentMonth]
  );

  // Filter tasks
  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      if (filterWedding && task.wedding_id !== filterWedding) return false;
      if (filterCategory && task.category !== filterCategory) return false;
      return true;
    });
  }, [tasks, filterWedding, filterCategory]);

  // Group tasks by day
  const tasksByDay = useMemo(() => {
    const grouped: Record<number, PlannerTask[]> = {};

    filteredTasks.forEach((task) => {
      const taskDate = new Date(task.start_date);
      if (
        taskDate.getFullYear() === currentYear &&
        taskDate.getMonth() === currentMonth
      ) {
        const day = taskDate.getDate();
        if (!grouped[day]) grouped[day] = [];
        grouped[day].push(task);
      }
    });

    return grouped;
  }, [filteredTasks, currentYear, currentMonth]);

  // Navigation
  const goToPreviousMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear(currentYear - 1);
    } else {
      setCurrentMonth(currentMonth - 1);
    }
  };

  const goToNextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear(currentYear + 1);
    } else {
      setCurrentMonth(currentMonth + 1);
    }
  };

  const goToToday = () => {
    const today = new Date();
    setCurrentYear(today.getFullYear());
    setCurrentMonth(today.getMonth());
  };

  // Task handlers
  const handleDayClick = (day: number) => {
    setSelectedTask(null);
    setSelectedDate(new Date(currentYear, currentMonth, day));
    setTaskModalOpen(true);
  };

  const handleTaskClick = (task: PlannerTask, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedTask(task);
    setSelectedDate(undefined);
    setTaskModalOpen(true);
  };

  const handleTaskSuccess = (task: PlannerTask) => {
    fetchTasks();
    fetchUpcoming();
  };

  const handleQuickStatusChange = async (task: PlannerTask, newStatus: string) => {
    if (!token) return;

    try {
      await updateTask(token, task.id, { status: newStatus as any });
      fetchTasks();
      fetchUpcoming();
    } catch (err) {
      console.error('Failed to update task status:', err);
    }
  };

  const handleDeleteTask = async (task: PlannerTask) => {
    if (!token) return;

    const confirmed = window.confirm('Are you sure you want to delete this task?');
    if (!confirmed) return;

    try {
      await deleteTask(token, task.id);
      fetchTasks();
      fetchUpcoming();
    } catch (err) {
      console.error('Failed to delete task:', err);
    }
  };

  const today = new Date();
  const isToday = (day: number) =>
    day === today.getDate() &&
    currentMonth === today.getMonth() &&
    currentYear === today.getFullYear();

  if (!token || !userProfile) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Planning Calendar"
        subtitle="Manage your tasks and schedule"
      >
        <button
          onClick={() => {
            setSelectedTask(null);
            setSelectedDate(new Date());
            setTaskModalOpen(true);
          }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
          New Task
        </button>
      </PageHeader>

      {/* Google Calendar Connection */}
      <GoogleCalendarConnect />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Calendar Section */}
        <div className="lg:col-span-3">
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
            {/* Calendar Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <button
                    onClick={goToPreviousMonth}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  >
                    <svg
                      className="w-5 h-5 text-gray-600 dark:text-gray-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15 19l-7-7 7-7"
                      />
                    </svg>
                  </button>

                  <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                    {MONTH_NAMES[currentMonth]} {currentYear}
                  </h2>

                  <button
                    onClick={goToNextMonth}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  >
                    <svg
                      className="w-5 h-5 text-gray-600 dark:text-gray-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                  </button>

                  <button
                    onClick={goToToday}
                    className="px-3 py-1 text-sm text-indigo-600 dark:text-indigo-400 border border-indigo-300 dark:border-indigo-700 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
                  >
                    Today
                  </button>
                </div>

                {/* Filters */}
                <div className="flex items-center gap-2">
                  <select
                    value={filterWedding}
                    onChange={(e) => setFilterWedding(e.target.value)}
                    className="text-sm px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100"
                  >
                    <option value="">All Weddings</option>
                    {weddings.map((w, index) => (
                      <option key={w.id || `wedding-${index}`} value={w.id}>
                        {w.couple_names}
                      </option>
                    ))}
                  </select>

                  <select
                    value={filterCategory}
                    onChange={(e) => setFilterCategory(e.target.value)}
                    className="text-sm px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-gray-100"
                  >
                    <option value="">All Categories</option>
                    {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Calendar Grid */}
            <div className="p-4">
              {loading ? (
                <div className="flex items-center justify-center h-96">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                </div>
              ) : (
                <>
                  {/* Day Headers */}
                  <div className="grid grid-cols-7 gap-1 mb-2">
                    {DAY_NAMES.map((day) => (
                      <div
                        key={day}
                        className="text-center text-sm font-medium text-gray-500 dark:text-gray-400 py-2"
                      >
                        {day}
                      </div>
                    ))}
                  </div>

                  {/* Calendar Days */}
                  <div className="grid grid-cols-7 gap-1">
                    {calendarDays.map((day, index) => (
                      <div
                        key={index}
                        onClick={() => day && handleDayClick(day)}
                        className={`
                          min-h-24 p-1 border rounded-lg transition-colors cursor-pointer
                          ${
                            day
                              ? 'border-gray-200 dark:border-gray-700 hover:border-indigo-300 dark:hover:border-indigo-700 hover:bg-indigo-50 dark:hover:bg-indigo-900/10'
                              : 'border-transparent bg-gray-50 dark:bg-gray-800/50'
                          }
                          ${
                            day && isToday(day)
                              ? 'bg-indigo-50 dark:bg-indigo-900/20 border-indigo-300 dark:border-indigo-700'
                              : ''
                          }
                        `}
                      >
                        {day && (
                          <>
                            <div
                              className={`text-sm font-medium mb-1 ${
                                isToday(day)
                                  ? 'text-indigo-600 dark:text-indigo-400'
                                  : 'text-gray-700 dark:text-gray-300'
                              }`}
                            >
                              {day}
                            </div>

                            {/* Tasks for this day */}
                            <div className="space-y-0.5 overflow-hidden max-h-16">
                              {tasksByDay[day]?.slice(0, 3).map((task) => (
                                <div
                                  key={task.id}
                                  onClick={(e) => handleTaskClick(task, e)}
                                  className={`
                                    text-xs px-1 py-0.5 rounded truncate cursor-pointer
                                    ${
                                      task.status === 'completed'
                                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 line-through'
                                        : task.priority === 'urgent'
                                        ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                                        : task.priority === 'high'
                                        ? 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400'
                                        : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                                    }
                                  `}
                                  style={
                                    task.color
                                      ? { backgroundColor: `${task.color}30`, borderLeft: `3px solid ${task.color}` }
                                      : undefined
                                  }
                                >
                                  {task.title}
                                </div>
                              ))}
                              {tasksByDay[day]?.length > 3 && (
                                <div className="text-xs text-gray-500 dark:text-gray-400 pl-1">
                                  +{tasksByDay[day].length - 3} more
                                </div>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar - Upcoming Tasks */}
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
              Upcoming Tasks
            </h3>

            {upcomingTasks.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No upcoming tasks in the next 2 weeks
              </p>
            ) : (
              <div className="space-y-3">
                {upcomingTasks.map((task) => (
                  <div
                    key={task.id}
                    className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-indigo-300 dark:hover:border-indigo-700 cursor-pointer transition-colors"
                    onClick={() => {
                      setSelectedTask(task);
                      setTaskModalOpen(true);
                    }}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                          {task.title}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {new Date(task.start_date).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            hour: task.all_day ? undefined : 'numeric',
                            minute: task.all_day ? undefined : '2-digit',
                          })}
                        </p>
                        {task.wedding_name && (
                          <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-0.5">
                            {task.wedding_name}
                          </p>
                        )}
                      </div>

                      <span
                        className={`ml-2 px-1.5 py-0.5 text-xs rounded ${
                          PRIORITY_CONFIG[task.priority as keyof typeof PRIORITY_CONFIG]?.bgColor || 'bg-gray-100'
                        } ${
                          PRIORITY_CONFIG[task.priority as keyof typeof PRIORITY_CONFIG]?.color || 'text-gray-600'
                        }`}
                      >
                        {task.priority}
                      </span>
                    </div>

                    {/* Quick status buttons */}
                    <div className="mt-2 flex items-center gap-1">
                      {task.status !== 'completed' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleQuickStatusChange(task, 'completed');
                          }}
                          className="text-xs text-green-600 dark:text-green-400 hover:text-green-700 px-2 py-0.5 bg-green-50 dark:bg-green-900/20 rounded"
                        >
                          Complete
                        </button>
                      )}
                      {task.status === 'pending' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleQuickStatusChange(task, 'in_progress');
                          }}
                          className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 px-2 py-0.5 bg-blue-50 dark:bg-blue-900/20 rounded"
                        >
                          Start
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Category Legend */}
          <div className="mt-4 bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
              Priority Legend
            </h3>
            <div className="space-y-2">
              {Object.entries(PRIORITY_CONFIG).map(([key, config]) => (
                <div key={key} className="flex items-center gap-2">
                  <div
                    className={`w-3 h-3 rounded ${config.bgColor}`}
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {config.label}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* AI Assistant Card */}
          <div className="mt-4 bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-lg border border-indigo-200 dark:border-indigo-800 p-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                AI Planning Assistant
              </h3>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
              Get AI-powered task prioritization and timeline suggestions
            </p>
            <button
              onClick={() => setShowAiPanel(true)}
              disabled={weddings.length === 0}
              className="w-full px-3 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              AI Prioritize
            </button>
          </div>
        </div>
      </div>

      {/* AI Panel Modal */}
      {showAiPanel && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-indigo-500 to-purple-600">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">AI Planning Assistant</h3>
                    <p className="text-sm text-indigo-100">Get prioritized tasks and timeline suggestions</p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setShowAiPanel(false);
                    setAiPrioritization(null);
                    setAiTimeline(null);
                  }}
                  className="p-2 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Tab Buttons */}
            <div className="px-6 py-3 border-b border-gray-200 dark:border-gray-700 flex gap-2">
              <button
                onClick={() => setAiActiveTab('prioritize')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  aiActiveTab === 'prioritize'
                    ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                Task Prioritization
              </button>
              <button
                onClick={() => setAiActiveTab('timeline')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  aiActiveTab === 'timeline'
                    ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`}
              >
                Timeline Generator
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {/* Wedding Selector */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Select Wedding
                </label>
                <select
                  value={filterWedding}
                  onChange={(e) => setFilterWedding(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                >
                  <option value="">Select a wedding...</option>
                  {weddings.map((w) => (
                    <option key={w.id} value={w.id}>{w.couple_names}</option>
                  ))}
                </select>
              </div>

              {aiActiveTab === 'prioritize' && (
                <div>
                  {!aiPrioritization && (
                    <button
                      onClick={() => filterWedding && fetchAiPrioritization(filterWedding)}
                      disabled={aiLoading || !filterWedding}
                      className="w-full px-4 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      {aiLoading ? (
                        <>
                          <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          Analyzing tasks...
                        </>
                      ) : (
                        <>
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                          </svg>
                          Prioritize Tasks (2 credits)
                        </>
                      )}
                    </button>
                  )}

                  {aiPrioritization && (
                    <div className="space-y-6">
                      {/* Weekly Focus */}
                      {aiPrioritization.weekly_focus && (
                        <div className="p-4 bg-indigo-50 dark:bg-indigo-900/20 rounded-lg border border-indigo-200 dark:border-indigo-800">
                          <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                            <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                            This Week&apos;s Focus
                          </h4>
                          <p className="text-gray-700 dark:text-gray-300">{aiPrioritization.weekly_focus}</p>
                        </div>
                      )}

                      {/* Warnings */}
                      {aiPrioritization.warnings?.length > 0 && (
                        <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                          <h4 className="font-semibold text-red-700 dark:text-red-400 mb-2 flex items-center gap-2">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            Warnings
                          </h4>
                          <ul className="space-y-1">
                            {aiPrioritization.warnings.map((warning, i) => (
                              <li key={i} className="text-red-700 dark:text-red-400 flex items-start gap-2">
                                <span>•</span> {warning}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Priority Tasks */}
                      {aiPrioritization.priority_tasks?.length > 0 && (
                        <div>
                          <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Priority Tasks</h4>
                          <div className="space-y-2">
                            {aiPrioritization.priority_tasks.map((task, i) => (
                              <div key={i} className="p-3 bg-gray-50 dark:bg-slate-700 rounded-lg">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="font-medium text-gray-900 dark:text-gray-100">{task.task}</span>
                                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                                    task.urgency === 'critical' ? 'bg-red-100 text-red-700' :
                                    task.urgency === 'high' ? 'bg-orange-100 text-orange-700' :
                                    task.urgency === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                                    'bg-green-100 text-green-700'
                                  }`}>
                                    {task.urgency}
                                  </span>
                                </div>
                                <div className="text-sm text-gray-600 dark:text-gray-400">
                                  <span className="mr-3">Due: {task.due_by}</span>
                                  <span className="text-gray-400">|</span>
                                  <span className="ml-3">{task.category}</span>
                                </div>
                                <p className="text-xs text-gray-500 mt-1">{task.reason}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Milestones */}
                      {aiPrioritization.upcoming_milestones?.length > 0 && (
                        <div>
                          <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Upcoming Milestones</h4>
                          <div className="space-y-2">
                            {aiPrioritization.upcoming_milestones.map((m, i) => (
                              <div key={i} className="flex items-start gap-3 p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                                <div className="w-8 h-8 bg-purple-100 dark:bg-purple-900/30 rounded-lg flex items-center justify-center text-purple-600 text-sm font-bold">
                                  {new Date(m.date).getDate()}
                                </div>
                                <div>
                                  <p className="font-medium text-gray-900 dark:text-gray-100">{m.milestone}</p>
                                  <p className="text-sm text-gray-600 dark:text-gray-400">{m.importance}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <button
                        onClick={() => setAiPrioritization(null)}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
                      >
                        Re-analyze
                      </button>
                    </div>
                  )}
                </div>
              )}

              {aiActiveTab === 'timeline' && (
                <div>
                  {!aiTimeline && (
                    <button
                      onClick={() => filterWedding && fetchAiTimeline(filterWedding)}
                      disabled={aiLoading || !filterWedding}
                      className="w-full px-4 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      {aiLoading ? (
                        <>
                          <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          Generating timeline...
                        </>
                      ) : (
                        <>
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                          Generate Timeline (2 credits)
                        </>
                      )}
                    </button>
                  )}

                  {aiTimeline && (
                    <div className="space-y-6">
                      {/* Cultural Considerations */}
                      {aiTimeline.cultural_considerations?.length > 0 && (
                        <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                          <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Cultural Considerations</h4>
                          <ul className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
                            {aiTimeline.cultural_considerations.map((c, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <span className="text-amber-500">•</span> {c}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Key Dates */}
                      {aiTimeline.key_dates?.length > 0 && (
                        <div>
                          <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Key Dates</h4>
                          <div className="space-y-2">
                            {aiTimeline.key_dates.map((d, i) => (
                              <div key={i} className="flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                                <div className="w-16 text-center">
                                  <div className="text-xs text-gray-500">{new Date(d.date).toLocaleDateString('en-US', { month: 'short' })}</div>
                                  <div className="text-lg font-bold text-blue-600">{new Date(d.date).getDate()}</div>
                                </div>
                                <div>
                                  <p className="font-medium text-gray-900 dark:text-gray-100">{d.event}</p>
                                  <p className="text-sm text-gray-600 dark:text-gray-400">{d.importance}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Timeline Phases */}
                      {aiTimeline.timeline?.length > 0 && (
                        <div>
                          <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Planning Phases</h4>
                          <div className="space-y-4">
                            {aiTimeline.timeline.map((phase, i) => (
                              <div key={i} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                                <div className="bg-gray-50 dark:bg-slate-700 px-4 py-2 flex items-center justify-between">
                                  <span className="font-medium text-gray-900 dark:text-gray-100">{phase.phase}</span>
                                  <span className="text-sm text-gray-500">
                                    {new Date(phase.start_date).toLocaleDateString()} - {new Date(phase.end_date).toLocaleDateString()}
                                  </span>
                                </div>
                                <div className="p-4 space-y-2">
                                  {phase.milestones?.slice(0, 5).map((m, j) => (
                                    <div key={j} className="flex items-center justify-between text-sm">
                                      <span className="text-gray-700 dark:text-gray-300">{m.task}</span>
                                      <span className={`text-xs px-2 py-0.5 rounded ${
                                        m.priority === 'critical' ? 'bg-red-100 text-red-700' :
                                        m.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                                        'bg-gray-100 text-gray-700'
                                      }`}>
                                        {m.priority}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Budget Tips */}
                      {aiTimeline.budget_tips?.length > 0 && (
                        <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                          <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Budget Tips</h4>
                          <ul className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
                            {aiTimeline.budget_tips.map((tip, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <span className="text-green-500">•</span> {tip}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <button
                        onClick={() => setAiTimeline(null)}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
                      >
                        Generate New Timeline
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Task Modal */}
      <TaskModal
        open={taskModalOpen}
        onOpenChange={setTaskModalOpen}
        task={selectedTask}
        weddings={weddings}
        defaultDate={selectedDate}
        onSuccess={handleTaskSuccess}
      />
    </div>
  );
}
