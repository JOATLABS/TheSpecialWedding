'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
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
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Planning Calendar
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Manage your tasks and schedule
          </p>
        </div>

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
      </div>

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
        </div>
      </div>

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
